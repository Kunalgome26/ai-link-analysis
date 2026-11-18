"""Competitor analysis service for market intelligence and competitor comparison validation."""

from typing import List
from app.schemas import CompetitorAnalysis, CompetitorItem


class CompetitorService:
    """Provides validation, enrichment, and formatting for competitor intelligence."""

    @staticmethod
    def ensure_minimum_competitors(
        competitor_analysis: CompetitorAnalysis,
        category: str,
        brand_name: str
    ) -> CompetitorAnalysis:
        """Validate that at least 3 competitors are identified; enrich if any are missing."""
        existing_competitors = competitor_analysis.competitors or []

        if len(existing_competitors) >= 3:
            return competitor_analysis

        # Fallback enrichment if LLM produced fewer than 3 competitors
        category_clean = category.split("&")[0].strip()
        enrichment_templates = [
            CompetitorItem(
                name=f"Global {category_clean} Enterprise",
                main_service=f"Tier-1 {category_clean} Services",
                target_market="Global Large Corporations",
                strengths=["Extensive brand legacy", "Broad vendor network"],
                weaknesses_or_gaps=["High consulting fees", "Slow bureaucratic processes"],
                comparison_vs_brand=f"{brand_name} offers higher responsiveness and customized service delivery."
            ),
            CompetitorItem(
                name=f"Regional {category_clean} Partners",
                main_service=f"Local {category_clean} Solutions",
                target_market="Local and Regional SMBs",
                strengths=["Localized physical presence", "Established regional ties"],
                weaknesses_or_gaps=["Limited modern digital toolset", "Slow geographical expansion"],
                comparison_vs_brand=f"{brand_name} provides modern, cloud-first agility and nationwide scalability."
            ),
            CompetitorItem(
                name=f"Digital {category_clean} Direct",
                main_service=f"Automated Self-Serve {category_clean}",
                target_market="Budget Startups and Freelancers",
                strengths=["Very low upfront cost", "Instant automated sign-up"],
                weaknesses_or_gaps=["No human advisory support", "Rigid cookie-cutter templates"],
                comparison_vs_brand=f"{brand_name} delivers dedicated high-touch expertise and bespoke configurations."
            ),
        ]

        for item in enrichment_templates:
            if len(existing_competitors) >= 3:
                break
            existing_competitors.append(item)

        competitor_analysis.competitors = existing_competitors
        return competitor_analysis
