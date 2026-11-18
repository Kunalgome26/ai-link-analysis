"""Pydantic schemas and models for the AI-Powered Website Link Analysis API."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class LinkAnalysisRequest(BaseModel):
    """Input payload for link analysis."""
    url: str = Field(
        ...,
        description="The full website URL to analyze (e.g., https://example.com)",
        examples=["https://example.com"]
    )


# ---------------------------------------------------------
# Section 1: Brand & Competitor Analysis
# ---------------------------------------------------------

class CompetitorItem(BaseModel):
    """Details comparing an individual competitor with the brand."""
    name: str = Field(..., description="Name of the competitor")
    main_service: str = Field(..., description="Competitor's primary product or service")
    target_market: str = Field(..., description="Competitor's primary target market (e.g., Enterprise, SMB)")
    strengths: List[str] = Field(default_factory=list, description="Key competitor strengths")
    weaknesses_or_gaps: List[str] = Field(default_factory=list, description="Competitor weaknesses or market gaps")
    comparison_vs_brand: str = Field(..., description="Direct comparative positioning against the brand")


class CompetitorAnalysis(BaseModel):
    """Section 1: Competitor vs Your Brand Details."""
    brand_overview: str = Field(..., description="Comprehensive business overview of the analyzed brand")
    main_business_category: str = Field(..., description="Primary business industry/category")
    main_products_and_services: List[str] = Field(default_factory=list, description="Primary products or services offered")
    competitors: List[CompetitorItem] = Field(
        default_factory=list,
        description="Identified competitors (minimum 3 where available)"
    )
    strengths: List[str] = Field(default_factory=list, description="Your brand's key strengths")
    competitive_advantages: List[str] = Field(default_factory=list, description="Your brand's core competitive differentiators")
    opportunities: List[str] = Field(default_factory=list, description="Opportunities to improve market positioning")
    source_attribution: str = Field(
        default="AI-generated competitor research based on extracted brand positioning and verified market category.",
        description="Transparency note on competitor information source"
    )


# ---------------------------------------------------------
# Section 2: Top 5 Target Search Queries
# ---------------------------------------------------------

class TargetSearchQuery(BaseModel):
    """Section 2: High-intent search query across major search and social channels."""
    query: str = Field(..., description="The exact search phrase potential customers would use")
    platforms: List[str] = Field(
        default_factory=list,
        description="Relevant discovery platforms: Google, Facebook, Instagram, LinkedIn, or X (Twitter)"
    )
    intent: str = Field(..., description="Search intent (e.g., Service Discovery, B2B Search, Inspiration, Commercial)")
    business_relevance: str = Field(..., description="Why this query directly matters to the brand")
    target_audience: str = Field(..., description="Audience demographic or persona conducting this search")


# ---------------------------------------------------------
# Section 3: SEO Improvement
# ---------------------------------------------------------

class SupportingContentItem(BaseModel):
    """Recommended support content to improve search visibility and authority."""
    content_type: str = Field(..., description="Type: Service Landing Page, Industry Page, FAQ, Blog Topic, etc.")
    title: str = Field(..., description="Proposed content headline or page title")
    description: str = Field(..., description="Summary of what this content should cover and its user value")
    target_keywords: List[str] = Field(default_factory=list, description="Key search terms this content will rank for")


class SEOImprovements(BaseModel):
    """Section 3: Practical SEO enhancements based on website content."""
    # A. Keyword Recommendations
    primary_keyword: str = Field(..., description="Single highest-priority target keyword for the homepage/brand")
    secondary_keywords: List[str] = Field(default_factory=list, description="Important supporting keywords")
    long_tail_keywords: List[str] = Field(default_factory=list, description="High-intent long-tail keyword phrases")
    relevant_business_keywords: List[str] = Field(default_factory=list, description="Industry and semantic keywords")

    # B. SEO Title
    recommended_title: str = Field(..., description="Optimized SEO Title tag (50-60 characters)")
    title_primary_keyword: str = Field(..., description="Primary keyword included in title")
    title_structure_reasoning: str = Field(..., description="Explanation of improved title structure")

    # C. Meta Description
    meta_description: str = Field(..., description="Compelling, human-friendly meta description (150-160 characters)")
    meta_summary: str = Field(..., description="Short business summary conveyed in meta tag")
    meta_keywords_included: List[str] = Field(default_factory=list, description="Key terms incorporated into meta tag")

    # D. Supporting Content Suggestions
    supporting_content: List[SupportingContentItem] = Field(
        default_factory=list,
        description="Strategic content additions (service pages, FAQs, blog topics, industry guides)"
    )


# ---------------------------------------------------------
# Section 4: Top 5 Services
# ---------------------------------------------------------

class ServiceItem(BaseModel):
    """Section 4: Top core service or product identified from the website."""
    service_name: str = Field(..., description="Name of the service")
    description: str = Field(..., description="Short service explanation")
    target_industry: str = Field(..., description="Relevant business industry")
    target_customer: str = Field(..., description="Potential customer type or persona")
    main_benefit: str = Field(..., description="Why customers choose or need this service")
    source: str = Field(
        default="explicitly extracted from website",
        description="Source distinction: 'explicitly extracted from website' or 'inferred recommendation'"
    )


# ---------------------------------------------------------
# Section 5: Target Audience Identification
# ---------------------------------------------------------

class CustomerProfile(BaseModel):
    """Detailed target customer profile segment."""
    segment: str = Field(..., description="Audience segment name")
    business_type: str = Field(..., description="Customer business type (e.g., Startups, SMB, Enterprise)")
    key_requirement: str = Field(..., description="Primary need or requirement")
    pain_points: List[str] = Field(default_factory=list, description="Key challenges and problems faced")
    potential_interests: List[str] = Field(default_factory=list, description="Interests and search behavior")


class TargetAudience(BaseModel):
    """Section 5: Comprehensive target audience analysis."""
    primary_audience: List[str] = Field(default_factory=list, description="Primary customer demographics/personas")
    secondary_audience: List[str] = Field(default_factory=list, description="Secondary customer groups or influencers")
    industries: List[str] = Field(default_factory=list, description="Target industry segments")
    business_types: List[str] = Field(default_factory=list, description="Types of businesses served (B2B, B2C, D2C)")
    customer_profiles: List[CustomerProfile] = Field(default_factory=list, description="Granular customer persona breakdowns")
    geographical_focus: Optional[str] = Field(None, description="Location focus (regional, national, or global)")
    customer_needs: List[str] = Field(default_factory=list, description="Core customer needs and challenges")
    recommended_marketing_segments: List[str] = Field(
        default_factory=list,
        description="Actionable audience segments recommended for marketing campaigns"
    )


# ---------------------------------------------------------
# Brand Overview Summary
# ---------------------------------------------------------

class BrandDetails(BaseModel):
    """Brand identity summary extracted from website."""
    name: str = Field(..., description="Brand or business name")
    category: str = Field(..., description="Primary business category")
    summary: str = Field(..., description="Brief company overview")


# ---------------------------------------------------------
# Complete Structured Analysis
# ---------------------------------------------------------

class AnalysisResult(BaseModel):
    """Aggregated 5-section analysis."""
    competitor_analysis: CompetitorAnalysis
    target_search_queries: List[TargetSearchQuery] = Field(..., min_length=5, max_length=5)
    seo_improvements: SEOImprovements
    top_services: List[ServiceItem] = Field(..., min_length=5, max_length=5)
    target_audience: TargetAudience


class AnalysisMetadata(BaseModel):
    """Execution metadata and LLM usage statistics."""
    execution_time_ms: float
    llm_provider: str
    llm_model: str
    tokens_estimated: Dict[str, int] = Field(default_factory=dict)
    cached: bool = False


class LinkAnalysisResponse(BaseModel):
    """Top-level success response adhering to required format."""
    success: bool = True
    website: str
    brand: BrandDetails
    analysis: AnalysisResult
    metadata: Optional[AnalysisMetadata] = None


class ErrorResponse(BaseModel):
    """Structured error response for client failures."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    website: Optional[str] = None
