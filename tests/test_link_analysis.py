"""Integration tests for the Link Analysis API endpoints."""

from unittest.mock import AsyncMock, patch
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.website_extractor import ExtractedWebsiteData, WebsiteExtractionException

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns API status and documentation link."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "/link-analysis" in data["endpoints"]["link_analysis"]["path"]


def test_health_endpoint():
    """Verify health check endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ssrf_forbidden_via_api():
    """Verify attempting to analyze localhost or private IP returns 403 Forbidden."""
    response = client.post("/link-analysis", json={"url": "http://127.0.0.1:8000"})
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert "SSRF" in data["error"]


def test_invalid_url_format_via_api():
    """Verify malformed protocol returns 400 Bad Request."""
    response = client.post("/link-analysis", json={"url": "ftp://files.example.com"})
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Invalid URL" in data["error"]


def test_missing_payload_field():
    """Verify missing required url field returns 422 Unprocessable Entity."""
    response = client.post("/link-analysis", json={})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False


@patch("socket.getaddrinfo", return_value=[(2, 1, 0, "", ("93.184.216.34", 0))])
def test_successful_link_analysis_with_mock_extractor(mock_dns):
    """Verify complete 5-section response structure using a simulated website extraction."""
    mock_extracted = ExtractedWebsiteData(
        url="https://dxoratech.com",
        final_url="https://dxoratech.com",
        title="Dxora Technologies | Innovative AI & Cloud Engineering",
        meta_description="Dxora Technologies provides enterprise AI consulting, full-stack development, and scalable cloud solutions.",
        og_data={"og:site_name": "Dxora Technologies", "og:title": "Dxora Technologies"},
        headings={
            "h1": ["Enterprise AI & Modern Cloud Solutions"],
            "h2": ["Our Core Services", "Why Partner with Dxora", "Client Testimonials"],
            "h3": ["Custom AI Models", "Full-Stack Development", "Cloud DevOps"]
        },
        navigation_links=["Services", "Solutions", "About Us", "Contact"],
        main_text="We build transformative digital software, robust AI pipelines, and high-performance cloud applications for scaling companies.",
        status_code=200
    )

    with patch("app.services.analysis_service.WebsiteExtractor.extract", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_extracted

        response = client.post("/link-analysis", json={"url": "https://dxoratech.com"})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["website"] == "https://dxoratech.com"

        # Check Brand Details
        assert "brand" in data
        assert "name" in data["brand"]
        assert "category" in data["brand"]
        assert "summary" in data["brand"]

        analysis = data["analysis"]

        # Section 1: Competitor vs Your Brand Details
        comp = analysis["competitor_analysis"]
        assert "brand_overview" in comp
        assert len(comp["competitors"]) >= 3
        for competitor in comp["competitors"]:
            assert "name" in competitor
            assert "main_service" in competitor
            assert "target_market" in competitor
            assert "strengths" in competitor
            assert "weaknesses_or_gaps" in competitor
            assert "comparison_vs_brand" in competitor
        assert len(comp["strengths"]) > 0
        assert len(comp["opportunities"]) > 0
        assert len(comp["competitive_advantages"]) > 0

        # Section 2: Top 5 Target Search Queries
        queries = analysis["target_search_queries"]
        assert len(queries) == 5
        for q in queries:
            assert "query" in q
            assert len(q["platforms"]) >= 1
            assert "intent" in q
            assert "business_relevance" in q
            assert "target_audience" in q

        # Section 3: SEO Improvement
        seo = analysis["seo_improvements"]
        assert seo["primary_keyword"]
        assert len(seo["secondary_keywords"]) > 0
        assert len(seo["long_tail_keywords"]) > 0
        assert seo["recommended_title"]
        assert seo["meta_description"]
        assert len(seo["supporting_content"]) >= 1

        # Section 4: Top 5 Services
        services = analysis["top_services"]
        assert len(services) == 5
        for s in services:
            assert s["service_name"]
            assert s["description"]
            assert s["target_industry"]
            assert s["target_customer"]
            assert s["main_benefit"]
            assert s["source"] in ("explicitly extracted from website", "inferred recommendation")

        # Section 5: Target Audience Identification
        aud = analysis["target_audience"]
        assert len(aud["primary_audience"]) > 0
        assert len(aud["industries"]) > 0
        assert len(aud["customer_profiles"]) >= 1
        assert len(aud["customer_needs"]) > 0
        assert len(aud["recommended_marketing_segments"]) > 0

        # Metadata
        assert "metadata" in data
        assert data["metadata"]["execution_time_ms"] > 0


@patch("socket.getaddrinfo", return_value=[(2, 1, 0, "", ("93.184.216.34", 0))])
def test_inaccessible_website_404_handling(mock_dns):
    """Verify website 404 returns structured error response."""
    with patch(
        "app.services.analysis_service.WebsiteExtractor.extract",
        side_effect=WebsiteExtractionException("Website returned 404 Not Found at https://notfound.example.com", status_code=404)
    ):
        response = client.post("/link-analysis", json={"url": "https://notfound.example.com"})
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "Website Inaccessible" in data["error"]
