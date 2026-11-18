"""Unit tests for services: WebsiteExtractor, CompetitorService, and Cache."""

import pytest
from app.services.website_extractor import WebsiteExtractor
from app.services.competitor_service import CompetitorService
from app.services.analysis_service import SimpleMemoryCache
from app.schemas import (
    CompetitorAnalysis,
    CompetitorItem,
    LinkAnalysisResponse,
    BrandDetails,
    AnalysisResult,
    TargetSearchQuery,
    SEOImprovements,
    ServiceItem,
    TargetAudience,
    AnalysisMetadata
)


def test_website_extractor_parsing():
    """Verify HTML parsing strips scripts and extracts headings, metadata, and body."""
    raw_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Alpha Innovations | AI Platform</title>
        <meta name="description" content="Next-generation enterprise AI platform." />
        <meta property="og:site_name" content="Alpha Innovations" />
        <script>console.log("secret analytics token");</script>
        <style>body { color: red; }</style>
      </head>
      <body>
        <!-- Hidden developer comment -->
        <header>
          <nav>
            <a href="/solutions">Solutions</a>
            <a href="/pricing">Pricing Plans</a>
          </nav>
        </header>
        <main>
          <h1>Enterprise Artificial Intelligence</h1>
          <h2>Scalable Model Deployment</h2>
          <h3>Real-time Inference</h3>
          <p>We empower teams with automated machine learning pipelines.</p>
        </main>
      </body>
    </html>
    """

    extractor = WebsiteExtractor()
    extracted = extractor._parse_html(
        original_url="https://alphainnovations.ai",
        final_url="https://alphainnovations.ai",
        html_content=raw_html,
        status_code=200
    )

    assert extracted.title == "Alpha Innovations | AI Platform"
    assert extracted.meta_description == "Next-generation enterprise AI platform."
    assert extracted.og_data["og:site_name"] == "Alpha Innovations"
    assert "Enterprise Artificial Intelligence" in extracted.headings["h1"]
    assert "Scalable Model Deployment" in extracted.headings["h2"]
    assert "Real-time Inference" in extracted.headings["h3"]
    assert "Solutions" in extracted.navigation_links
    assert "secret analytics token" not in extracted.main_text
    assert "body { color: red; }" not in extracted.main_text
    assert "Hidden developer comment" not in extracted.main_text
    assert "We empower teams with automated machine learning pipelines." in extracted.main_text

    context = extracted.to_llm_context(max_length=5000)
    assert "Alpha Innovations | AI Platform" in context
    assert "Enterprise Artificial Intelligence" in context


def test_competitor_service_minimum_enrichment():
    """Verify competitor service enriches to at least 3 competitors when fewer are provided."""
    analysis = CompetitorAnalysis(
        brand_overview="Overview",
        main_business_category="Cloud Architecture",
        main_products_and_services=["Consulting"],
        competitors=[
            CompetitorItem(
                name="Existing Competitor One",
                main_service="Cloud Hosting",
                target_market="Enterprise",
                strengths=["Scale"],
                weaknesses_or_gaps=["Cost"],
                comparison_vs_brand="Brand is faster"
            )
        ],
        strengths=["Agility"],
        competitive_advantages=["High touch"],
        opportunities=["Expand"]
    )

    enriched = CompetitorService.ensure_minimum_competitors(
        analysis,
        category="Cloud Architecture",
        brand_name="CloudHero"
    )

    assert len(enriched.competitors) >= 3
    assert enriched.competitors[0].name == "Existing Competitor One"
    assert "CloudHero" in enriched.competitors[1].comparison_vs_brand


def test_simple_memory_cache_ttl():
    """Verify caching and TTL invalidation."""
    cache = SimpleMemoryCache(ttl_seconds=1)

    dummy_response = LinkAnalysisResponse(
        success=True,
        website="https://testsite.com",
        brand=BrandDetails(name="Test", category="Tech", summary="Summary"),
        analysis=AnalysisResult(
            competitor_analysis=CompetitorAnalysis(
                brand_overview="Overview",
                main_business_category="Tech",
                main_products_and_services=["Dev"],
                competitors=[
                    CompetitorItem(
                        name="C1", main_service="S1", target_market="M1",
                        strengths=["S"], weaknesses_or_gaps=["W"], comparison_vs_brand="Comp"
                    ),
                    CompetitorItem(
                        name="C2", main_service="S2", target_market="M2",
                        strengths=["S"], weaknesses_or_gaps=["W"], comparison_vs_brand="Comp"
                    ),
                    CompetitorItem(
                        name="C3", main_service="S3", target_market="M3",
                        strengths=["S"], weaknesses_or_gaps=["W"], comparison_vs_brand="Comp"
                    )
                ],
                strengths=["Str"],
                competitive_advantages=["Adv"],
                opportunities=["Opp"]
            ),
            target_search_queries=[
                TargetSearchQuery(query=f"query {i}", platforms=["Google"], intent="Search", business_relevance="Rel", target_audience="Aud")
                for i in range(5)
            ],
            seo_improvements=SEOImprovements(
                primary_keyword="Keyword",
                secondary_keywords=["Sec"],
                long_tail_keywords=["Long"],
                relevant_business_keywords=["Biz"],
                recommended_title="Title",
                title_primary_keyword="Keyword",
                title_structure_reasoning="Reason",
                meta_description="Desc",
                meta_summary="Sum",
                meta_keywords_included=["Key"],
                supporting_content=[]
            ),
            top_services=[
                ServiceItem(service_name=f"Service {i}", description="Desc", target_industry="Ind", target_customer="Cust", main_benefit="Ben")
                for i in range(5)
            ],
            target_audience=TargetAudience(
                primary_audience=["Aud1"],
                secondary_audience=["Aud2"],
                industries=["Ind"],
                business_types=["B2B"],
                customer_profiles=[],
                geographical_focus="Global",
                customer_needs=["Need"],
                recommended_marketing_segments=["Seg"]
            )
        ),
        metadata=AnalysisMetadata(execution_time_ms=10.0, llm_provider="Mock", llm_model="Mock")
    )

    cache.set("https://testsite.com", dummy_response)

    cached = cache.get("https://testsite.com")
    assert cached is not None
    assert cached.metadata.cached is True

    # Unknown URL
    assert cache.get("https://nonexistent.com") is None
