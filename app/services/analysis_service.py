"""Orchestrator service executing URL extraction, LLM intelligence, and cache management."""

import hashlib
import time
from typing import Dict, Optional, Tuple
from app.config import settings
from app.schemas import (
    LinkAnalysisResponse,
    AnalysisMetadata,
    BrandDetails,
    AnalysisResult
)
from app.utils.validators import validate_and_sanitize_url
from app.services.website_extractor import WebsiteExtractor
from app.services.llm_service import LLMService
from app.services.competitor_service import CompetitorService


class SimpleMemoryCache:
    """Thread-safe in-memory cache with Time-To-Live (TTL) for API cost optimization."""

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
            # Expired
            del self._cache[key]
            return None

        # Return a cached copy with metadata flagged as cached
        if response.metadata:
            response.metadata.cached = True
        return response

    def set(self, url: str, response: LinkAnalysisResponse) -> None:
        if not settings.CACHE_ENABLED:
            return
        key = self._hash_key(url)
        self._cache[key] = (time.time(), response)

    def clear(self) -> None:
        self._cache.clear()


class AnalysisService:
    """End-to-end service coordinating validation, extraction, LLM reasoning, and response structuring."""

    def __init__(self):
        self.extractor = WebsiteExtractor()
        self.llm_service = LLMService()
        self.cache = SimpleMemoryCache()

    async def analyze_url(self, raw_url: str) -> LinkAnalysisResponse:
        """Analyze a website URL and return comprehensive 5-section intelligence."""
        # 1. URL Validation & SSRF Prevention
        validated_url = validate_and_sanitize_url(raw_url)

        # 2. Check Cache
        cached_result = self.cache.get(validated_url)
        if cached_result:
            return cached_result

        start_time = time.time()

        # 3. Extract Website Content
        extracted_data = await self.extractor.extract(validated_url)

        # 4. Prepare Token-Efficient Context for LLM
        llm_context = extracted_data.to_llm_context(max_length=settings.MAX_CONTENT_LENGTH)

        # 5. Execute LLM Reasoning
        brand, analysis_result, llm_meta = await self.llm_service.analyze(llm_context)

        # 6. Ensure Competitor Intelligence Integrity (min 3 competitors)
        analysis_result.competitor_analysis = CompetitorService.ensure_minimum_competitors(
            analysis_result.competitor_analysis,
            category=brand.category,
            brand_name=brand.name
        )

        total_duration_ms = round((time.time() - start_time) * 1000, 2)

        metadata = AnalysisMetadata(
            execution_time_ms=total_duration_ms,
            llm_provider=llm_meta.get("llm_provider", "Unknown"),
            llm_model=llm_meta.get("llm_model", "Unknown"),
            tokens_estimated=llm_meta.get("tokens_estimated", {}),
            cached=False
        )

        response = LinkAnalysisResponse(
            success=True,
            website=validated_url,
            brand=brand,
            analysis=analysis_result,
            metadata=metadata
        )

        # 7. Store in Cache
        self.cache.set(validated_url, response)

        return response
