"""Orchestrator service executing URL extraction, LLM intelligence, and cache management."""

import hashlib
import time
from typing import Dict, Optional, Tuple

from app.config import settings
from app.schemas import (
    LinkAnalysisResponse,
    AnalysisMetadata,
)
from app.utils.validators import validate_and_sanitize_url
from app.services.website_extractor import WebsiteExtractor
from app.services.llm_service import LLMService


class SimpleMemoryCache:
    """In-memory cache with Time-To-Live (TTL) for API cost optimization."""

    def __init__(self, ttl_seconds: int = settings.CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[float, LinkAnalysisResponse]] = {}

    def _hash_key(self, url: str) -> str:
        return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()

    def get(self, url: str) -> Optional[LinkAnalysisResponse]:
        if not settings.CACHE_ENABLED:
            return None

        key = self._hash_key(url)
        entry = self._cache.get(key)
        if not entry:
            return None

        created_at, response = entry
        if (time.time() - created_at) > self.ttl_seconds:
            del self._cache[key]
            return None

        # Return a copy so the cached original metadata is not mutated.
        cached_response = response.model_copy(deep=True)
        if cached_response.metadata:
            cached_response.metadata.cached = True
        return cached_response

    def set(self, url: str, response: LinkAnalysisResponse) -> None:
        if not settings.CACHE_ENABLED:
            return

        key = self._hash_key(url)
        self._cache[key] = (time.time(), response.model_copy(deep=True))

    def clear(self) -> None:
        self._cache.clear()


class AnalysisService:
    """Coordinate validation, extraction, LLM analysis, and response creation."""

    def __init__(self):
        self.extractor = WebsiteExtractor()
        self.llm_service = LLMService()
        self.cache = SimpleMemoryCache()

    async def analyze_url(self, raw_url: str) -> LinkAnalysisResponse:
        """Analyze a website URL and return the structured analysis."""
        # 1. Validate URL and apply SSRF protections.
        validated_url = validate_and_sanitize_url(raw_url)

        # 2. Return a cached result when available.
        cached_result = self.cache.get(validated_url)
        if cached_result:
            return cached_result

        start_time = time.time()

        # 3. Extract website content.
        extracted_data = await self.extractor.extract(validated_url)

        # 4. Prepare context for the LLM.
        llm_context = extracted_data.to_llm_context(
            max_length=settings.MAX_CONTENT_LENGTH
        )

        # 5. Run Gemini analysis, with the configured fallback behavior.
        brand, analysis_result, llm_meta = await self.llm_service.analyze(llm_context)
        llm_meta = llm_meta or {}

        provider = str(llm_meta.get("llm_provider", "Unknown"))
        model = str(llm_meta.get("llm_model", "Unknown"))
        fallback_used = bool(
            llm_meta.get(
                "fallback_used",
                provider.lower() in {"mockllmprovider", "mock"},
            )
        )
        fallback_reason = llm_meta.get("fallback_reason")

        # Do not present mock-generated competitor names as verified research.
        if fallback_used:
            analysis_result.competitor_analysis.competitors = []
            analysis_result.competitor_analysis.source_attribution = (
                "Competitor research is unavailable because the primary AI "
                "provider failed. No competitors are presented as verified."
            )

            # Do not label mock-generated service suggestions as website-extracted facts.
            for service in analysis_result.top_services:
                service.source = "not_verified"

        total_duration_ms = round((time.time() - start_time) * 1000, 2)

        metadata = AnalysisMetadata(
            execution_time_ms=total_duration_ms,
            llm_provider=provider,
            llm_model=model,
            tokens_estimated=llm_meta.get("tokens_estimated", {}),
            cached=False,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

        response = LinkAnalysisResponse(
            success=True,
            website=validated_url,
            brand=brand,
            analysis=analysis_result,
            metadata=metadata,
        )

        # 6. Cache the completed response.
        self.cache.set(validated_url, response)
        return response
