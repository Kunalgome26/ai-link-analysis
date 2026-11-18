"""LLM Service orchestrating multiple providers (Gemini, OpenAI, and Mock)."""



import json

import logging

import re

import time

from typing import Dict, Any, Tuple

from abc import ABC, abstractmethod



from app.config import settings

from app.schemas import (

    AnalysisResult,

    BrandDetails,

    CompetitorAnalysis,

    CompetitorItem,

    TargetSearchQuery,

    SEOImprovements,

    SupportingContentItem,

    ServiceItem,

    TargetAudience,

    CustomerProfile

)



logger = logging.getLogger(__name__)



SYSTEM_PROMPT = """You are an elite Chief Digital Officer, Brand Strategist, and Technical SEO Architect.

Your task is to analyze the provided website content extraction and produce a comprehensive, deep, and actionable 5-section business and SEO intelligence report in structured JSON format.



CRITICAL INSTRUCTIONS:

1. Ground your analysis strictly in the provided website content. Do not hallucinate fictitious services or business models.

2. In Section 1 (Competitors): Identify at least 3 credible, realistic competitors in this industry. If direct competitors are not stated on the site, identify the most likely market rivals based on the business category and clearly mark this in the comparison.

3. In Section 2 (Search Queries): Generate EXACTLY 5 high-intent search queries. Cover the specified platforms (Google, Facebook, Instagram, LinkedIn, X/Twitter). State the search intent, business relevance, and target audience. DO NOT invent fake search volumes or ranking figures.

4. In Section 3 (SEO Improvements): Provide keyword research (primary, secondary, long-tail, business keywords), an optimized SEO title tag (50-60 chars) with structural reasoning, a high-converting meta description (150-160 chars), and at least 3 strategic supporting content ideas (service pages, industry pages, FAQs, or blog guides).

5. In Section 4 (Top 5 Services): Identify EXACTLY 5 primary services or products. Clearly label whether each was "explicitly extracted from website" or "inferred recommendation".

6. In Section 5 (Target Audience): Identify primary/secondary audiences, industry segments, business types, at least 3 detailed customer persona profiles with pain points and interests, geographical focus, and actionable marketing segments.



You must return a valid JSON object matching this exact top-level schema:

{

  "brand": {

    "name": "Brand Name",

    "category": "Main Category",

    "summary": "Concise business overview"

  },

  "analysis": {

    "competitor_analysis": {

      "brand_overview": "...",

      "main_business_category": "...",

      "main_products_and_services": ["..."],

      "competitors": [

        {

          "name": "...",

          "main_service": "...",

          "target_market": "...",

          "strengths": ["..."],

          "weaknesses_or_gaps": ["..."],

          "comparison_vs_brand": "..."

        }

      ],

      "strengths": ["..."],

      "competitive_advantages": ["..."],

      "opportunities": ["..."],

      "source_attribution": "AI-generated competitor research based on extracted brand positioning and verified market category."

    },

    "target_search_queries": [

      {

        "query": "...",

        "platforms": ["Google", "LinkedIn"],

        "intent": "...",

        "business_relevance": "...",

        "target_audience": "..."

      }

    ],

    "seo_improvements": {

      "primary_keyword": "...",

      "secondary_keywords": ["..."],

      "long_tail_keywords": ["..."],

      "relevant_business_keywords": ["..."],

      "recommended_title": "...",

      "title_primary_keyword": "...",

      "title_structure_reasoning": "...",

      "meta_description": "...",

      "meta_summary": "...",

      "meta_keywords_included": ["..."],

      "supporting_content": [

        {

          "content_type": "...",

          "title": "...",

          "description": "...",

          "target_keywords": ["..."]

        }

      ]

    },

    "top_services": [

      {

        "service_name": "...",

        "description": "...",

        "target_industry": "...",

        "target_customer": "...",

        "main_benefit": "...",

        "source": "explicitly extracted from website"

      }

    ],

    "target_audience": {

      "primary_audience": ["..."],

      "secondary_audience": ["..."],

      "industries": ["..."],

      "business_types": ["..."],

      "customer_profiles": [

        {

          "segment": "...",

          "business_type": "...",

          "key_requirement": "...",

          "pain_points": ["..."],

          "potential_interests": ["..."]

        }

      ],

      "geographical_focus": "...",

      "customer_needs": ["..."],

      "recommended_marketing_segments": ["..."]

    }

  }

}



Return ONLY raw JSON. Do not include markdown codeblocks or conversational preamble.

"""





def _clean_json_response(raw_text: str) -> str:

    """Clean markdown backticks or formatting from LLM JSON response."""

    text = raw_text.strip()

    if text.startswith("```"):

        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)

        text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()

    return text





class BaseLLMProvider(ABC):

    """Abstract base class for LLM providers."""



    @abstractmethod

    async def generate_analysis(self, prompt: str) -> Tuple[Dict[str, Any], Dict[str, int]]:

        """Generate structured analysis from website context.



        Returns:

            Tuple of (parsed_json_dict, token_usage_dict)

        """

        pass





class GeminiProvider(BaseLLMProvider):

    """Google Gemini LLM provider using the google-genai SDK or API."""



    def __init__(self, api_key: str, model: str = settings.GEMINI_MODEL):

        self.api_key = api_key

        self.model = model

        from google import genai

        from google.genai import types

        self.client = genai.Client(

            api_key=self.api_key,

            http_options=types.HttpOptions(

                timeout=15000,

                retry_options=types.HttpRetryOptions(

                    attempts=1,

                    initial_delay=0.5,

                    max_delay=1.5,

                    exp_base=2.0,

                    jitter=0.2,

                    http_status_codes=[500, 502, 503, 504],

                ),

            ),

        )

        self.types = types



    async def generate_analysis(self, prompt: str) -> Tuple[Dict[str, Any], Dict[str, int]]:

        import asyncio



        def _call_gemini():

            response = self.client.models.generate_content(

                model=self.model,

                contents=prompt,

                config=self.types.GenerateContentConfig(

                    system_instruction=SYSTEM_PROMPT,

                    response_mime_type="application/json",

                    temperature=0.2,

                )

            )

            return response



        # Run the synchronous SDK call in a worker thread. The SDK HTTP timeout
        # is 15 seconds; this outer timeout bounds the API wait and triggers fallback.
        loop = asyncio.get_running_loop()
        logger.info("Gemini analysis started (model=%s).", self.model)
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call_gemini),
                timeout=20,
            )
        except asyncio.TimeoutError:
            logger.error("Gemini analysis exceeded the 20-second application timeout.")
            raise TimeoutError("Gemini analysis exceeded the 20-second application timeout.")

        logger.info("Gemini response received; parsing JSON response.")
        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        clean_text = _clean_json_response(response.text)

        parsed = json.loads(clean_text)



        tokens = {

            "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) if hasattr(response, "usage_metadata") else 0,

            "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) if hasattr(response, "usage_metadata") else 0,

            "total_tokens": getattr(response.usage_metadata, "total_token_count", 0) if hasattr(response, "usage_metadata") else 0,

        }

        return parsed, tokens





class OpenAIProvider(BaseLLMProvider):

    """OpenAI LLM provider using the official OpenAI client."""



    def __init__(self, api_key: str, model: str = settings.OPENAI_MODEL):

        self.api_key = api_key

        self.model = model

        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=self.api_key)



    async def generate_analysis(self, prompt: str) -> Tuple[Dict[str, Any], Dict[str, int]]:

        response = await self.client.chat.completions.create(

            model=self.model,

            response_format={"type": "json_object"},

            temperature=0.2,

            messages=[

                {"role": "system", "content": SYSTEM_PROMPT},

                {"role": "user", "content": prompt}

            ]

        )



        content = response.choices[0].message.content or "{}"

        parsed = json.loads(_clean_json_response(content))



        tokens = {

            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,

            "completion_tokens": response.usage.completion_tokens if response.usage else 0,

            "total_tokens": response.usage.total_tokens if response.usage else 0,

        }

        return parsed, tokens





class MockLLMProvider(BaseLLMProvider):

    """Intelligent offline mock LLM provider.



    Extracts keywords, headings, and domain context from the prompt to generate

    realistic, tailored 5-section analysis for testing and offline evaluation.

    """



    async def generate_analysis(self, prompt: str) -> Tuple[Dict[str, Any], Dict[str, int]]:

        # Extract title and URL from prompt if available

        title_match = re.search(r"TITLE:\s*(.+)", prompt)

        url_match = re.search(r"URL:\s*(https?://[^\s/]+)", prompt)

        meta_match = re.search(r"META DESCRIPTION:\s*(.+)", prompt)

        h1_match = re.search(
            r"PRIMARY HEADINGS\s+\*{0,2}\(?(?:H1|&#x48;&#x31;)\)?\*{0,2}:\s*(.+)",
            prompt,
            re.IGNORECASE,
        )



        raw_title = title_match.group(1).strip() if title_match else "Digital Solutions"

        domain = url_match.group(1).split("//")[-1] if url_match else "example.com"

        meta_desc = meta_match.group(1).strip() if meta_match else "Premier digital and technology solutions provider."

        h1 = h1_match.group(1).strip() if h1_match else "Empowering Modern Business"



        brand_name = raw_title.split("|")[0].split("-")[0].strip()

        if len(brand_name) > 30 or not brand_name or brand_name.lower() in ("home", "welcome"):

            brand_name = domain.split(".")[0].capitalize()



        category = "Technology Services & Digital Solutions"

        if any(w in prompt.lower() for w in ("law", "legal", "attorney")):

            category = "Legal Services & Advisory"

        elif any(w in prompt.lower() for w in ("health", "clinic", "medical", "doctor")):

            category = "Healthcare & Medical Services"

        elif any(w in prompt.lower() for w in ("shop", "store", "ecommerce", "cart")):

            category = "E-Commerce & Retail"

        elif any(w in prompt.lower() for w in ("finance", "fintech", "invest", "banking")):

            category = "Financial & Investment Services"

        elif any(w in prompt.lower() for w in ("software", "cloud", "saas", "api", "dev")):

            category = "Software & Cloud Technology"



        result = {

            "brand": {

                "name": brand_name,

                "category": category,

                "summary": meta_desc if meta_desc and meta_desc != "None" else f"{brand_name} is a leading provider in {category}, delivering innovative and specialized solutions to clients worldwide."

            },

            "analysis": {

                "competitor_analysis": {

                    "brand_overview": f"{brand_name} operates in the {category} sector, focusing on modern customer experiences, scalable execution, and personalized client partnerships.",

                    "main_business_category": category,

                    "main_products_and_services": [

                        f"{category} Strategy & Consulting",

                        "End-to-End Solution Implementation",

                        "Customer Support & Account Management",

                        "Custom Integration Services"

                    ],

                    "competitors": [

                        {

                            "name": f"Global{category.split()[0]} Corp",

                            "main_service": f"Enterprise {category.split()[0]} Services",

                            "target_market": "Fortune 500 Enterprises",

                            "strengths": ["Large existing market share", "Extensive international sales network"],

                            "weaknesses_or_gaps": ["High cost structure", "Slow implementation cycles and rigid processes"],

                            "comparison_vs_brand": f"{brand_name} provides significantly faster turnaround times and more dedicated client attention than Global{category.split()[0]} Corp."

                        },

                        {

                            "name": f"Apex {category.split()[-1]} Group",

                            "main_service": f"Standardized {category.split()[-1]} Packages",

                            "target_market": "Mid-market Organizations",

                            "strengths": ["Competitive entry-level pricing", "Well-known regional brand"],

                            "weaknesses_or_gaps": ["Limited customization capabilities", "Inflexible service agreements"],

                            "comparison_vs_brand": f"{brand_name} excels in delivering tailor-made client solutions rather than one-size-fits-all packages."

                        },

                        {

                            "name": f"NextGen {brand_name} Dynamics",

                            "main_service": f"Cloud-based {category.split()[0]} Automation",

                            "target_market": "Digital Startups & Scaleups",

                            "strengths": ["Modern user interface", "Aggressive social media presence"],

                            "weaknesses_or_gaps": ["Lacks enterprise security compliance", "Shallow customer support tier"],

                            "comparison_vs_brand": f"{brand_name} offers superior domain expertise and reliable, enterprise-grade stability."

                        }

                    ],

                    "strengths": [

                        "Agile delivery with rapid onboarding",

                        "Tailored solutions with high client satisfaction",

                        "Transparent pricing structure without hidden fees"

                    ],

                    "competitive_advantages": [

                        "Direct access to senior domain specialists",

                        "Modern technology stack and modern architecture",

                        "Strong focus on measurable business ROI for clients"

                    ],

                    "opportunities": [

                        "Expand digital content marketing and thought leadership",

                        "Establish interactive client case studies and ROI calculators",

                        "Strengthen organic search presence across high-intent transactional keywords"

                    ],

                    "source_attribution": "AI-generated competitor research based on extracted brand positioning and verified market category."

                },

                "target_search_queries": [

                    {

                        "query": f"Best {category.lower()} provider for businesses",

                        "platforms": ["Google", "LinkedIn"],

                        "intent": "Service Discovery",

                        "business_relevance": f"Direct commercial search for buyers seeking reputable vendors in {category}.",

                        "target_audience": "C-suite executives, VP of Operations, and Business Owners"

                    },

                    {

                        "query": f"{brand_name} services review and client case studies",

                        "platforms": ["Google", "LinkedIn", "X (Twitter)"],

                        "intent": "Brand Evaluation / Decision Phase",

                        "business_relevance": "Prospects validating credibility before scheduling an introductory sales consultation.",

                        "target_audience": "Procurement Managers and Project Leaders"

                    },

                    {

                        "query": f"Top trends in {category.lower()} 2026",

                        "platforms": ["LinkedIn", "X (Twitter)"],

                        "intent": "Thought Leadership / B2B Search",

                        "business_relevance": f"Builds organic top-of-funnel brand authority for {brand_name}.",

                        "target_audience": "Industry Practitioners and Technology Directors"

                    },

                    {

                        "query": f"How to choose affordable {category.lower()} solutions",

                        "platforms": ["Google", "Facebook"],

                        "intent": "Informational / Commercial Investigation",

                        "business_relevance": f"Attracts cost-conscious SMB buyers searching for high-value alternatives in {category}.",

                        "target_audience": "Small Business Founders and Department Heads"

                    },

                    {

                        "query": f"Modern {category.lower()} ideas and transformation inspiration",

                        "platforms": ["Instagram", "LinkedIn"],

                        "intent": "Visual Inspiration & Awareness",

                        "business_relevance": "Captures creative decision makers browsing visual portfolios and product showcases.",

                        "target_audience": "Creative Directors and Digital Innovators"

                    }

                ],

                "seo_improvements": {

                    "primary_keyword": f"{brand_name} {category.split()[0]} Solutions",

                    "secondary_keywords": [

                        f"{category} consulting services",

                        f"best {category.lower()} firm",

                        "enterprise digital transformation",

                        "custom business optimization"

                    ],

                    "long_tail_keywords": [

                        f"how to hire a dedicated {category.lower()} company",

                        f"best {category.lower()} strategies for scaling companies",

                        f"affordable professional {category.lower()} for mid-market"

                    ],

                    "relevant_business_keywords": [

                        "operational efficiency",

                        "client ROI optimization",

                        "seamless integration",

                        "scalable architecture"

                    ],

                    "recommended_title": f"{brand_name} | Premier {category} & Growth Solutions",

                    "title_primary_keyword": f"{category} & Growth Solutions",

                    "title_structure_reasoning": "Brand Name upfront for authoritative recognition, followed by primary service keyword and high-converting value proposition within optimal 55-character limit.",

                    "meta_description": f"Accelerate your business with {brand_name}. We deliver cutting-edge {category.lower()} designed to scale operations, maximize ROI, and boost performance.",

                    "meta_summary": f"Comprehensive {category.lower()} and advisory services from {brand_name}.",

                    "meta_keywords_included": [

                        f"{category.lower()}",

                        "scale operations",

                        "maximize ROI"

                    ],

                    "supporting_content": [

                        {

                            "content_type": "Service Landing Page",

                            "title": f"Enterprise {category.split()[0]} Consulting & Implementation",

                            "description": "Comprehensive landing page detailing methodology, engagement tiers, and technical specifications.",

                            "target_keywords": [f"enterprise {category.lower()}", "strategic consulting"]

                        },

                        {

                            "content_type": "Frequently Asked Questions (FAQ)",

                            "title": f"Frequently Asked Questions: Working with {brand_name}",

                            "description": "Structured FAQ targeting long-tail voice and search queries regarding pricing, onboarding, and timelines.",

                            "target_keywords": [f"{brand_name} pricing", f"how {category.lower()} works"]

                        },

                        {

                            "content_type": "Industry Guide / Blog",

                            "title": f"The Complete 2026 Roadmap to Modern {category}",

                            "description": "High-authority pillar content analyzing current market challenges and architectural best practices.",

                            "target_keywords": [f"{category.lower()} guide 2026", "operational modernization"]

                        }

                    ]

                },

                "top_services": [

                    {

                        "service_name": f"Core {category.split()[0]} Advisory",

                        "description": f"Strategic assessment and audit of existing workflows to identify high-impact growth opportunities in {category}.",

                        "target_industry": "Technology, Finance, and Professional Services",

                        "target_customer": "Chief Operating Officers and Managing Directors",

                        "main_benefit": "Identifies bottlenecks and provides an actionable blueprint to boost productivity.",

                        "source": "explicitly extracted from website"

                    },

                    {

                        "service_name": "Custom Solution Implementation",

                        "description": "Turnkey engineering and project delivery customized to unique business specifications and infrastructure.",

                        "target_industry": "Mid-market & High-Growth Companies",

                        "target_customer": "Technical Project Leads & VP of Engineering",

                        "main_benefit": "Seamless deployment without business disruption or downtime.",

                        "source": "explicitly extracted from website"

                    },

                    {

                        "service_name": "Performance Optimization & Maintenance",

                        "description": "Continuous monitoring, proactive upgrades, and 24/7 dedicated system support.",

                        "target_industry": "All Commercial Enterprises",

                        "target_customer": "IT Managers and Operations Directors",

                        "main_benefit": "Ensures uninterrupted uptime and sustained operational efficiency.",

                        "source": "explicitly extracted from website"

                    },

                    {

                        "service_name": "Digital Modernization & Cloud Integration",

                        "description": "Upgrading legacy systems to agile, cloud-native frameworks with automated data pipelines.",

                        "target_industry": "Digital First & Traditional Businesses",

                        "target_customer": "CTOs and Digital Transformation Executives",

                        "main_benefit": "Reduces infrastructure costs while increasing scalability and security.",

                        "source": "inferred recommendation"

                    },

                    {

                        "service_name": "Executive Training & Knowledge Transfer",

                        "description": "Structured workshops and documentation to empower internal client teams for long-term self-sufficiency.",

                        "target_industry": "Corporate Teams & Growing Startups",

                        "target_customer": "Team Leads & HR Directors",

                        "main_benefit": "Accelerates user adoption and builds durable internal capabilities.",

                        "source": "inferred recommendation"

                    }

                ],

                "target_audience": {

                    "primary_audience": [

                        "Founders and CEOs of scaling businesses seeking digital leverage",

                        "Chief Technology Officers & VP of Engineering looking for specialized bandwidth"

                    ],

                    "secondary_audience": [

                        "Procurement Managers evaluating reliable technology service partners",

                        "Operations Leads seeking automated, efficient workflow solutions"

                    ],

                    "industries": [

                        "Information Technology & SaaS",

                        "E-Commerce & Digital Retail",

                        "Financial Services & FinTech",

                        "Healthcare & Life Sciences",

                        "Professional Business Consulting"

                    ],

                    "business_types": [

                        "B2B SaaS Companies",

                        "Growing Startups (Seed to Series B)",

                        "Mid-Market Commercial Enterprises",

                        "Digital Agencies"

                    ],

                    "customer_profiles": [

                        {

                            "segment": "High-Growth Startup Founders",

                            "business_type": "Venture-backed Startups",

                            "key_requirement": "Rapid implementation with high quality and predictable budgeting",

                            "pain_points": [

                                "Limited internal engineering bandwidth",

                                "Need to beat competitors to market without technical debt"

                            ],

                            "potential_interests": [

                                "Modern tech stacks",

                                "Scalable system architectures",

                                "Agile product development"

                            ]

                        },

                        {

                            "segment": "Mid-Market Operations Directors",

                            "business_type": "Established Commercial Businesses",

                            "key_requirement": "Robust integrations that eliminate operational friction and manual tasks",

                            "pain_points": [

                                "Legacy tools slowing down customer fulfillment",

                                "High cost of maintaining disjointed legacy platforms"

                            ],

                            "potential_interests": [

                                "Workflow automation",

                                "Cloud migrations",

                                "Enterprise security compliance"

                            ]

                        },

                        {

                            "segment": "Enterprise Innovation Leaders",

                            "business_type": "Large Corporates",

                            "key_requirement": "Specialized domain knowledge and risk-mitigated technical execution",

                            "pain_points": [

                                "Slow procurement approvals and rigid vendor contracts",

                                "Difficulty finding reliable, agile partner teams"

                            ],

                            "potential_interests": [

                                "AI-driven analytics",

                                "Scalable microservices",

                                "SLA-backed support agreements"

                            ]

                        }

                    ],

                    "geographical_focus": "Global / North America & Europe (English-speaking commercial markets)",

                    "customer_needs": [

                        "Reliable, responsive communication and transparent deliverables",

                        "Cost-effective alternative to expensive Tier-1 consulting firms",

                        "Proven technical expertise with zero security compromise"

                    ],

                    "recommended_marketing_segments": [

                        "Tech decision-makers on LinkedIn with titles VP Engineering / CTO",

                        "High-intent Google Search campaigns for commercial B2B service queries",

                        "Retargeting website visitors with verified customer case studies and ROI proofs"

                    ]

                }

            }

        }

        tokens = {"prompt_tokens": 1200, "completion_tokens": 1450, "total_tokens": 2650}

        return result, tokens





class LLMService:

    """Orchestrates LLM providers with automatic fallback and schema validation."""



    def __init__(self):

        self.provider_name = settings.LLM_PROVIDER.lower()

        self.provider = self._init_provider(self.provider_name)



    def _init_provider(self, name: str) -> BaseLLMProvider:

        if name == "gemini":

            if settings.GEMINI_API_KEY:

                try:

                    return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)

                except Exception as exc:

                    logger.warning(f"Failed to initialize Gemini provider ({exc}). Falling back to Mock.")

            else:

                logger.info("GEMINI_API_KEY not set. Using MockLLMProvider for offline reliability.")

        elif name == "openai":

            if settings.OPENAI_API_KEY:

                try:

                    return OpenAIProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)

                except Exception as exc:

                    logger.warning(f"Failed to initialize OpenAI provider ({exc}). Falling back to Mock.")

            else:

                logger.info("OPENAI_API_KEY not set. Using MockLLMProvider for offline reliability.")



        return MockLLMProvider()



    async def analyze(self, extracted_context: str) -> Tuple[BrandDetails, AnalysisResult, Dict[str, Any]]:

        """Run LLM analysis and validate output against Pydantic schema."""

        start_time = time.time()



        active_provider = self.provider

        # If the configured provider could not be initialized and the service

        # started with Mock, report that accurately (unless Mock was selected

        # explicitly in configuration).

        fallback_used = (

            isinstance(active_provider, MockLLMProvider)

            and self.provider_name != "mock"

        )

        fallback_reason = (

            "Primary provider was unavailable or not configured during initialization."

            if fallback_used

            else None

        )



        try:

            raw_data, token_stats = await active_provider.generate_analysis(extracted_context)

        except Exception as exc:

            if isinstance(active_provider, MockLLMProvider):

                raise



            logger.exception(

                "Primary LLM provider %s failed. Using MockLLMProvider fallback.",

                type(active_provider).__name__,

            )

            active_provider = MockLLMProvider()

            fallback_used = True

            error_code = getattr(exc, "code", None)
            error_text = str(exc)

            if error_code == 429 or "RESOURCE_EXHAUSTED" in error_text or "quota" in error_text.lower():
                fallback_reason = (
                    f"Gemini quota exhausted (HTTP 429). "
                    f"Check your Gemini API usage and billing limits. Details: {error_text}"
                )
            elif error_code == 503 or "UNAVAILABLE" in error_text:
                fallback_reason = f"Gemini service temporarily unavailable (HTTP 503): {error_text}"
            elif isinstance(exc, TimeoutError) or error_code == 504 or "DEADLINE_EXCEEDED" in error_text:
                fallback_reason = f"{type(self.provider).__name__} request timed out: {error_text}"
            else:
                fallback_reason = f"{type(self.provider).__name__} failed: {error_text}"

            raw_data, token_stats = await active_provider.generate_analysis(extracted_context)



        execution_time_ms = round((time.time() - start_time) * 1000, 2)



        # Validate Brand Details

        brand_raw = raw_data.get("brand", {})

        brand = BrandDetails(

            name=brand_raw.get("name", "Website Brand"),

            category=brand_raw.get("category", "General Business"),

            summary=brand_raw.get("summary", "A business providing services.")

        )



        # Validate 5 Sections

        analysis_raw = raw_data.get("analysis", {})

        analysis = AnalysisResult.model_validate(analysis_raw)



        logger.info(
            "LLM analysis completed (provider=%s, fallback_used=%s, duration_ms=%s).",
            type(active_provider).__name__,
            fallback_used,
            execution_time_ms,
        )

        metadata = {

            "execution_time_ms": execution_time_ms,

            "llm_provider": type(active_provider).__name__,

            "llm_model": getattr(active_provider, "model", "mock-engine-v1"),

            "fallback_used": fallback_used,

            "fallback_reason": fallback_reason,

            "tokens_estimated": token_stats,

        }



        return brand, analysis, metadata