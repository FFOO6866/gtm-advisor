"""Company Enricher Agent - Website analysis and company profile enrichment.

This agent is the FIRST agent in the analysis flow. It:
1. Scrapes/analyzes the user's company website
2. Extracts structured company information
3. Publishes discoveries to the AgentBus for other agents

Other agents subscribe to these discoveries and use them to enhance their analysis.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import (
    AgentBus,
    DiscoveryType,
    get_agent_bus,
)
from packages.core.src.types import IndustryVertical
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.llm.src import get_llm_manager

# SSIC description keyword → IndustryVertical mapping (text-based, no section letter lookup)
_SSIC_DESC_TO_VERTICAL: list[tuple[str, IndustryVertical]] = [
    ("financial", IndustryVertical.FINTECH),
    ("fintech", IndustryVertical.FINTECH),
    ("insurance", IndustryVertical.FINTECH),
    ("banking", IndustryVertical.FINTECH),
    ("information technology", IndustryVertical.SAAS),
    ("software", IndustryVertical.SAAS),
    ("computer", IndustryVertical.SAAS),
    ("data processing", IndustryVertical.SAAS),
    ("information and communication", IndustryVertical.SAAS),
    ("telecommunication", IndustryVertical.SAAS),
    ("retail", IndustryVertical.ECOMMERCE),
    ("wholesale", IndustryVertical.ECOMMERCE),
    ("e-commerce", IndustryVertical.ECOMMERCE),
    ("health", IndustryVertical.HEALTHTECH),
    ("medical", IndustryVertical.HEALTHTECH),
    ("hospital", IndustryVertical.HEALTHTECH),
    ("pharmaceutical", IndustryVertical.HEALTHTECH),
    ("education", IndustryVertical.EDTECH),
    ("training", IndustryVertical.EDTECH),
    ("real estate", IndustryVertical.PROPTECH),
    ("property", IndustryVertical.PROPTECH),
    ("construction", IndustryVertical.PROPTECH),
    ("transport", IndustryVertical.LOGISTICS),
    ("logistics", IndustryVertical.LOGISTICS),
    ("storage", IndustryVertical.LOGISTICS),
    ("freight", IndustryVertical.LOGISTICS),
    ("manufacturing", IndustryVertical.MANUFACTURING),
    ("professional", IndustryVertical.PROFESSIONAL_SERVICES),
    ("consulting", IndustryVertical.PROFESSIONAL_SERVICES),
    ("legal", IndustryVertical.PROFESSIONAL_SERVICES),
    ("accounting", IndustryVertical.PROFESSIONAL_SERVICES),
]


def _vertical_from_ssic_desc(ssic_desc: str) -> IndustryVertical | None:
    """Map SSIC description text to the nearest IndustryVertical, or None if no match."""
    if not ssic_desc:
        return None
    lower = ssic_desc.lower()
    for keyword, vertical in _SSIC_DESC_TO_VERTICAL:
        if keyword in lower:
            return vertical
    return None


class ProductService(BaseModel):
    """A product or service offered by the company."""

    name: str = Field(...)
    description: str = Field(...)
    category: str = Field(default="general")  # product, service, platform, tool
    target_audience: str | None = Field(default=None)
    pricing_model: str | None = Field(default=None)  # subscription, one-time, freemium


class TeamMember(BaseModel):
    """A key team member identified from the website."""

    name: str = Field(...)
    role: str = Field(...)
    linkedin_url: str | None = Field(default=None)


class FundingInfo(BaseModel):
    """Funding information if available."""

    stage: str | None = Field(default=None)  # seed, series-a, etc.
    amount: str | None = Field(default=None)
    investors: list[str] = Field(default_factory=list)
    date: str | None = Field(default=None)


class CompanyEnrichmentOutput(BaseModel):
    """Complete company enrichment output from website analysis."""

    # Basic Info
    company_name: str = Field(...)
    website: str = Field(...)
    tagline: str | None = Field(default=None)
    description: str = Field(...)

    # Industry & Market
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    sub_industry: str | None = Field(default=None)
    target_markets: list[str] = Field(default_factory=list)

    # Products & Services
    products: list[ProductService] = Field(default_factory=list)
    value_propositions: list[str] = Field(default_factory=list)

    # Technology
    tech_stack: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)

    # Team & Culture
    key_team_members: list[TeamMember] = Field(default_factory=list)
    company_size: str | None = Field(default=None)  # startup, smb, enterprise
    culture_keywords: list[str] = Field(default_factory=list)

    # Funding & Business
    funding: FundingInfo | None = Field(default=None)
    business_model: str | None = Field(default=None)  # b2b, b2c, b2b2c, marketplace

    # Competitive Positioning
    unique_selling_points: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    mentioned_competitors: list[str] = Field(default_factory=list)

    # Contact & Social
    contact_email: str | None = Field(default=None)
    social_links: dict[str, str] = Field(default_factory=dict)

    # Singapore Government Data
    acra_data: dict | None = Field(
        default=None,
        description=(
            "Government-sourced company facts from ACRA (Singapore company registry). "
            "Present when the company is found in the registry. "
            "Keys: uen, entity_name, entity_type, status, registration_date, "
            "ssic_code, ssic_description."
        ),
    )

    # Metadata
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources_analyzed: list[str] = Field(default_factory=list)

    # Private — NOT sent to LLM schema. Populated after structured completion
    # by the Perplexity path so run_analysis can persist website context.
    _raw_website_context: str | None = PrivateAttr(default=None)

    @property
    def raw_website_context(self) -> str | None:
        return self._raw_website_context

    @raw_website_context.setter
    def raw_website_context(self, value: str | None) -> None:
        self._raw_website_context = value


class CompanyEnricherAgent(BaseGTMAgent[CompanyEnrichmentOutput]):
    """Company Enricher Agent - First agent in the A2A flow.

    This agent analyzes the user's company website and publishes discoveries
    that other agents can react to:

    - COMPANY_PROFILE: Basic company info for all agents
    - COMPANY_PRODUCTS: Products/services for Campaign Architect
    - COMPANY_TECH_STACK: Tech stack for Lead Hunter (tech matching)
    - COMPETITOR_FOUND: Mentioned competitors for Competitor Analyst
    - ICP_SEGMENT: Inferred target audience for Customer Profiler
    """

    def __init__(
        self,
        agent_bus: AgentBus | None = None,
        analysis_id: UUID | None = None,
    ) -> None:
        super().__init__(
            name="company-enricher",
            description=(
                "Analyzes company websites to extract structured information "
                "about products, team, technology, and market positioning. "
                "Publishes discoveries for other agents to use."
            ),
            result_type=CompanyEnrichmentOutput,
            min_confidence=0.65,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="website-analysis",
                    description="Extract company information from website",
                ),
                AgentCapability(
                    name="product-extraction",
                    description="Identify products and services",
                ),
                AgentCapability(
                    name="tech-detection",
                    description="Detect technology stack",
                ),
                AgentCapability(
                    name="team-identification",
                    description="Identify key team members",
                ),
                AgentCapability(
                    name="discovery-publishing",
                    description="Publish discoveries for A2A collaboration",
                ),
            ],
        )

        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id = analysis_id
        self._perplexity = get_llm_manager().perplexity

    def set_analysis_id(self, analysis_id: UUID) -> None:
        """Set the current analysis ID for discovery publishing."""
        self._analysis_id = analysis_id

    def get_system_prompt(self) -> str:
        base = """You are the Company Enricher Agent, a specialist in extracting structured company information from websites.

Your role is to analyze company websites and extract:
1. Basic company information (name, description, tagline)
2. Products and services with descriptions
3. Target markets and audience
4. Technology stack and integrations
5. Key team members and company culture
6. Business model and funding information
7. Competitive positioning and differentiators

Focus on CONCRETE, SPECIFIC information - not generic descriptions.
Extract actual product names, real team member names, specific technologies.

When analyzing:
- Look for "About", "Products", "Team", "Careers" pages
- Check footer for social links
- Identify pricing/business model from pricing page
- Note any competitors mentioned or comparison pages
- Extract unique selling points from hero sections

Be specific. "AI-powered analytics platform" is better than "technology company"."""
        sg_hint = getattr(self, "_sg_hint", "")
        if sg_hint:
            return base + f"\n\n{sg_hint}"
        return base

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan website analysis."""
        context = context or {}

        website = context.get("website") or ""
        # Normalise website URL — add scheme if missing
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        company_name = context.get("company_name", "")

        plan = {
            "website": website or None,
            "company_name": company_name,
            "pages_to_analyze": ["home", "about", "products", "team", "pricing"],
            "use_perplexity": self._perplexity.is_configured,
        }

        return plan

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CompanyEnrichmentOutput:
        """Execute website analysis."""
        context = context or {}

        # Fetch Singapore market context for better vertical detection
        sg_verticals_hint = ""
        try:
            kmcp = get_knowledge_mcp()
            sg_raw = await kmcp.get_singapore_context()
            sectors = sg_raw.get("market_overview", {}).get("key_sectors", [])
            if isinstance(sectors, list) and sectors:
                vert_names = [str(s) for s in sectors[:8]]
                sg_verticals_hint = (
                    f"Singapore key sectors: {', '.join(vert_names)}. "
                    "For companies in these sectors, prioritise accurate vertical detection."
                )
        except Exception as e:
            self._logger.debug("company_enricher_sg_context_failed", error=str(e))
        self._sg_hint = sg_verticals_hint

        website = plan.get("website") or context.get("website")
        company_name = plan.get("company_name") or context.get("company_name", "Unknown")

        # Step 0: ACRA government lookup (Singapore company registry)
        acra_data = await self._lookup_acra(company_name)

        # If no website but document text available, extract directly from document
        if not website and context.get("additional_context"):
            result = await self._analyze_from_document(company_name, context)
        elif not website:
            # If no website and no document, use Perplexity to research the company
            result = await self._research_company_without_website(company_name, context)
        elif plan.get("use_perplexity"):
            result = await self._analyze_with_perplexity(website, company_name, context)
        else:
            result = await self._analyze_with_llm(website, company_name, context)

        # Merge ACRA data into result
        if acra_data:
            result.acra_data = acra_data
            # Patch in government-authoritative fields only when the LLM left them blank
            if not result.company_name or result.company_name == "Unknown":
                entity_name = acra_data.get("entity_name")
                if entity_name:
                    result.company_name = entity_name
            # Apply SSIC → vertical if the LLM defaulted to OTHER
            if result.industry == IndustryVertical.OTHER:
                ssic_desc = acra_data.get("ssic_description", "")
                inferred = _vertical_from_ssic_desc(ssic_desc)
                if inferred is not None:
                    result.industry = inferred
            # Record ACRA as an additional source
            if "acra_singapore" not in result.sources_analyzed:
                result.sources_analyzed.append("acra_singapore")

        return result

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Return a simple token-overlap similarity in [0, 1] between two strings.

        Used to select the best-matching ACRA record when the API returns
        multiple companies for a query (e.g. "Grab" matches "GrabCar Pte Ltd",
        "GrabFood Pte Ltd", "Grab Holdings Pte Ltd", …).  We want the record
        whose registered name most closely matches what the caller supplied.

        The metric is |query_tokens ∩ candidate_tokens| / |query_tokens| so
        that a query like "Grab" scores 1.0 against "Grab Holdings Pte Ltd"
        (all query tokens found) but also 1.0 against "GrabCar Pte Ltd"
        (same denominator).  Tiebreaking is handled by preferring longer
        candidate names, which are less likely to be wholly different entities.
        """
        stop = {"pte", "ltd", "llp", "co", "sdn", "bhd", "inc", "corp", "the", "and", "&"}
        a_tokens = {t for t in a.lower().split() if t not in stop and len(t) > 1}
        b_tokens = {t for t in b.lower().split() if t not in stop and len(t) > 1}
        if not a_tokens:
            return 0.0
        return len(a_tokens & b_tokens) / len(a_tokens)

    async def _lookup_acra(self, company_name: str) -> dict:
        """Query the ACRA MCP server for Singapore government company data.

        Returns a dict of extracted fields, or an empty dict if the company is
        not found, does not match well enough, or the API is unavailable.

        Name-matching safeguard
        -----------------------
        ACRA full-text search may return several companies whose names share a
        common word with *company_name* (e.g. querying "Grab" returns
        "GrabCar", "GrabFood", …).  We score each candidate entity against the
        query and only proceed if the best score meets a minimum threshold
        (0.5).  This also acts as a country guard: an overseas company that
        happens to share a keyword with a Singapore-registered entity will
        typically score below 0.5 against the full query name and be skipped.
        """
        _MIN_NAME_SCORE = 0.5

        try:
            from packages.mcp.src.servers.acra import ACRAMCPServer

            acra = ACRAMCPServer.create()
            search_result = await acra.search(company_name, limit=5)

            if not search_result.facts:
                return {}

            # --- Name-matching: pick the best-fitting entity ---
            # Group facts by the entity (UEN) they belong to so we can pick
            # the registration fact (COMPANY_INFO type, has "uen" key) for the
            # entity that best matches the query name.
            best_entity_name: str | None = None
            best_score: float = 0.0

            for entity in search_result.entities:
                score = self._name_similarity(company_name, entity.name)
                if score > best_score:
                    best_score = score
                    best_entity_name = entity.name

            if best_score < _MIN_NAME_SCORE:
                self._logger.info(
                    "acra_lookup_no_match",
                    company=company_name,
                    best_score=round(best_score, 2),
                    best_candidate=best_entity_name,
                )
                return {}

            # Find the registration fact (the COMPANY_INFO fact that carries
            # "uen") for the best-matching entity.
            registration_fact = None
            for fact in search_result.facts:
                ed = fact.extracted_data
                candidate_name = ed.get("company_name", "")
                if (
                    candidate_name
                    and self._name_similarity(company_name, candidate_name) >= _MIN_NAME_SCORE
                    and ed.get("uen")
                ):
                    registration_fact = fact
                    break

            if registration_fact is None:
                return {}

            acra_data: dict = dict(registration_fact.extracted_data)

            # Normalise key: the registration fact stores the name under
            # "company_name"; downstream code expects "entity_name".
            if not acra_data.get("entity_name"):
                acra_data["entity_name"] = acra_data.get("company_name", best_entity_name)

            # If we have a UEN, fetch full details and merge in SSIC description
            uen = acra_data.get("uen")
            if uen:
                detail_result = await acra.get_company_details(uen)
                for fact in detail_result.facts:
                    ed = fact.extracted_data
                    if ed.get("ssic_code"):
                        acra_data.setdefault("ssic_code", ed["ssic_code"])
                    if ed.get("ssic_description"):
                        acra_data.setdefault("ssic_description", ed["ssic_description"])
                    if ed.get("industry"):
                        acra_data.setdefault("industry_label", ed["industry"])
                    if ed.get("status"):
                        acra_data.setdefault("status", ed["status"])
                    if ed.get("is_active") is not None:
                        acra_data.setdefault("is_active", ed["is_active"])

            self._logger.info(
                "acra_lookup_success",
                company=company_name,
                matched_name=acra_data.get("entity_name"),
                match_score=round(best_score, 2),
                uen=acra_data.get("uen"),
                status=acra_data.get("status"),
            )
            return acra_data

        except Exception as exc:
            # ACRA offline or company not found — degrade gracefully
            self._logger.info("acra_lookup_skipped", company=company_name, reason=str(exc))
            return {}

    async def _analyze_from_document(
        self,
        company_name: str,
        context: dict[str, Any],
    ) -> CompanyEnrichmentOutput:
        """Extract company profile directly from uploaded document text."""
        self._logger.info("analyzing_company_from_document", company_name=company_name)
        doc_text = context["additional_context"]
        # Truncate to avoid blowing token budget (document already truncated upstream)
        doc_excerpt = doc_text[:8000] if len(doc_text) > 8000 else doc_text

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Extract structured company information from this uploaded document:

Company Name: {company_name}
Industry Hint: {context.get("industry", "Not specified")}

DOCUMENT TEXT:
{doc_excerpt}

Extract as much concrete information as possible: products, team, target markets, tech stack, competitors mentioned, differentiators, business model, and funding. Confidence should reflect the richness of the document.""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompanyEnrichmentOutput,
            messages=messages,
        )
        result.company_name = company_name
        result.website = ""
        result.sources_analyzed = ["uploaded_document"]
        return result

    async def _research_company_without_website(
        self,
        company_name: str,
        context: dict[str, Any],
    ) -> CompanyEnrichmentOutput:
        """Research company using just the name — tries Perplexity first, then LLM fallback."""
        self._logger.info("researching_company_without_website", company_name=company_name)

        # Try Perplexity for real-time web research first
        if self._perplexity.is_configured:
            try:
                research_query = (
                    f"Company information about {company_name}: "
                    f"what they do, products, target market, competitors, Singapore/APAC presence"
                )
                perplexity_response = await self._perplexity.search(
                    query=research_query,
                    focus="internet",
                )
                messages = [
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"""Based on this research about {company_name}:

{perplexity_response}

Industry Hint: {context.get("industry", "Not specified")}
Description Hint: {context.get("description", "Not specified")}

Extract structured company information. Confidence should reflect how much concrete data was found.""",
                    },
                ]
                result = await self._complete_structured(
                    response_model=CompanyEnrichmentOutput,
                    messages=messages,
                )
                result.company_name = company_name
                result.website = ""
                result.sources_analyzed = ["perplexity_web_search"]
                return result
            except Exception as e:
                self._logger.warning("perplexity_company_research_failed", error=str(e))

        # LLM-only fallback (confidence will be penalised in _check)
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Research and extract information about this company:

Company Name: {company_name}
Industry Hint: {context.get("industry", "Not specified")}
Description Hint: {context.get("description", "Not specified")}

Without a website or live data, use the company name and hints to infer:
1. What they likely do
2. Target markets
3. Potential competitors
4. Likely business model

Note: This is inference only — confidence should be low (0.2-0.4).""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompanyEnrichmentOutput,
            messages=messages,
        )

        result.company_name = company_name
        result.website = ""
        result.sources_analyzed = ["llm_inference_only"]

        return result

    async def _analyze_with_perplexity(
        self,
        website: str,
        company_name: str,
        context: dict[str, Any],
    ) -> CompanyEnrichmentOutput:
        """Analyze website using Perplexity for real-time web data."""
        self._logger.info("analyzing_website_with_perplexity", website=website)

        # Use Perplexity to get live website information
        try:
            research_query = f"""
            Analyze the company website {website} and extract detailed information about {company_name}:

            1. Company Overview:
               - Official description and tagline
               - Industry and sub-industry
               - Target markets and geographies

            2. Products & Services:
               - List all products/services with descriptions
               - Pricing model (subscription, one-time, freemium)
               - Key features and benefits

            3. Technology:
               - Technology stack mentioned
               - Integrations offered
               - API availability

            4. Team & Company:
               - Key executives and founders
               - Company size
               - Office locations
               - Culture and values

            5. Business Information:
               - Business model (B2B, B2C, etc.)
               - Funding information if public
               - Major customers or case studies

            6. Competitive Position:
               - Unique selling points
               - Key differentiators
               - Any competitors mentioned

            7. Contact & Social:
               - Contact email
               - Social media links

            Be specific and extract actual names, numbers, and details.
            """

            perplexity_response = await self._perplexity.search(
                query=research_query,
                focus="internet",
            )

            # Now use GPT-4 to structure the response
            doc_text = context.get("additional_context", "")
            doc_section = (
                f"\n\nUploaded Document (primary source — takes precedence over web research):\n{doc_text[:4000]}"
                if doc_text
                else ""
            )
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"""Based on this research about {company_name} ({website}):

{perplexity_response}

Additional context from user:
- Industry: {context.get("industry", "Not specified")}
- Description: {context.get("description", "Not specified")}{doc_section}

Extract and structure the company information.
Confidence should reflect how much concrete data was found.""",
                },
            ]

            result = await self._complete_structured(
                response_model=CompanyEnrichmentOutput,
                messages=messages,
            )

            result.company_name = company_name
            result.website = website
            result.sources_analyzed = ["perplexity_web_search", website]
            result.raw_website_context = perplexity_response

            return result

        except Exception as e:
            self._logger.warning("perplexity_analysis_failed", error=str(e))
            return await self._analyze_with_llm(website, company_name, context)

    async def _analyze_with_llm(
        self,
        website: str,
        company_name: str,
        context: dict[str, Any],
    ) -> CompanyEnrichmentOutput:
        """Analyze using LLM with context (fallback when Perplexity unavailable)."""
        self._logger.info("analyzing_website_with_llm_fallback", website=website)

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Analyze and extract information about this company:

Company Name: {company_name}
Website: {website}
Industry: {context.get("industry", "Not specified")}
User's Description: {context.get("description", "Not specified")}

Based on the company name, website domain, and provided description,
extract as much structured information as possible.

Note: No live data was fetched — this is domain/name inference only. Confidence should be low (0.3-0.5).""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompanyEnrichmentOutput,
            messages=messages,
        )

        result.company_name = company_name
        result.website = website
        result.sources_analyzed = ["llm_domain_inference"]

        return result

    async def _check(self, result: CompanyEnrichmentOutput) -> float:
        """Validate enrichment quality."""
        score = 0.2  # Base score — must earn via real data, not just LLM completion

        # Check basic info
        if result.description and len(result.description) > 50:
            score += 0.15

        # Check products
        if result.products:
            score += 0.1
            if len(result.products) >= 2:
                score += 0.05

        # Check value propositions
        if result.value_propositions:
            score += 0.1

        # Check industry identification
        if result.industry != IndustryVertical.OTHER:
            score += 0.05

        # Check target markets
        if result.target_markets:
            score += 0.05

        # Check tech stack
        if result.tech_stack:
            score += 0.05

        # Check unique selling points
        if result.unique_selling_points:
            score += 0.1

        # Check sources
        if result.sources_analyzed and len(result.sources_analyzed) >= 2:
            score += 0.05

        # Government-verified bonus: ACRA confirmed active Singapore company
        acra = result.acra_data or {}
        status = acra.get("status", "")
        is_live = acra.get("is_active") or any(
            s in status.lower() for s in ("live", "active", "registered", "existing")
        )
        if acra and is_live:
            score += 0.10

        return min(score, 1.0)

    async def _act(
        self, result: CompanyEnrichmentOutput, confidence: float
    ) -> CompanyEnrichmentOutput:
        """Publish discoveries to the AgentBus."""
        result.confidence = confidence

        # Publish discoveries for other agents
        await self._publish_discoveries(result)

        return result

    async def _publish_discoveries(self, result: CompanyEnrichmentOutput) -> None:
        """Publish discoveries to the AgentBus for other agents."""
        if not self._agent_bus:
            return

        # 1. Publish company profile (for all agents)
        await self._agent_bus.publish(
            from_agent=self.name,
            discovery_type=DiscoveryType.COMPANY_PROFILE,
            title=f"Company Profile: {result.company_name}",
            content={
                "company_name": result.company_name,
                "website": result.website,
                "description": result.description,
                "tagline": result.tagline,
                "industry": result.industry.value,
                "target_markets": result.target_markets,
                "business_model": result.business_model,
                "company_size": result.company_size,
                "value_propositions": result.value_propositions,
            },
            confidence=result.confidence,
            analysis_id=self._analysis_id,
        )

        # 2. Publish products (for Campaign Architect)
        if result.products:
            await self._agent_bus.publish(
                from_agent=self.name,
                discovery_type=DiscoveryType.COMPANY_PRODUCTS,
                title=f"Products: {len(result.products)} identified",
                content={
                    "products": [p.model_dump() for p in result.products],
                },
                confidence=result.confidence,
                analysis_id=self._analysis_id,
            )

        # 3. Publish tech stack (for Lead Hunter tech matching)
        if result.tech_stack:
            await self._agent_bus.publish(
                from_agent=self.name,
                discovery_type=DiscoveryType.COMPANY_TECH_STACK,
                title=f"Tech Stack: {len(result.tech_stack)} technologies",
                content={
                    "tech_stack": result.tech_stack,
                    "integrations": result.integrations,
                },
                confidence=result.confidence,
                analysis_id=self._analysis_id,
            )

        # 4. Publish mentioned competitors (for Competitor Analyst)
        if result.mentioned_competitors:
            for competitor in result.mentioned_competitors:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.COMPETITOR_FOUND,
                    title=f"Competitor mentioned: {competitor}",
                    content={
                        "name": competitor,              # matches signature spec
                        "competitor_name": competitor,   # kept for _on_competitor_discovered()
                        "source": "company_website",
                        "context": f"Mentioned on {result.website}",
                    },
                    confidence=0.7,  # Mentioned competitors are fairly reliable
                    analysis_id=self._analysis_id,
                )

        # 5. Publish inferred ICP segment (for Customer Profiler)
        if result.target_markets or result.products:
            target_audience = []
            for product in result.products:
                if product.target_audience:
                    target_audience.append(product.target_audience)

            await self._agent_bus.publish(
                from_agent=self.name,
                discovery_type=DiscoveryType.ICP_SEGMENT,
                title=f"Target Segment: {result.industry.value}",
                content={
                    "industry": result.industry.value,
                    "target_markets": result.target_markets,
                    "target_audience": target_audience,
                    "business_model": result.business_model,
                    "company_size_target": result.company_size,
                },
                confidence=result.confidence * 0.8,  # Inferred, so slightly lower confidence
                analysis_id=self._analysis_id,
            )

        discoveries_count = (
            1  # always: company_profile
            + (1 if result.products else 0)
            + (1 if result.tech_stack else 0)
            + (len(result.mentioned_competitors) if result.mentioned_competitors else 0)
            + (1 if result.target_markets or result.products else 0)
        )
        self._logger.info(
            "discoveries_published",
            company=result.company_name,
            discoveries_count=discoveries_count,
        )

    async def enrich_company(
        self,
        company_name: str,
        website: str | None = None,
        industry: IndustryVertical | None = None,
        description: str | None = None,
        additional_context: str | None = None,
        analysis_id: UUID | None = None,
    ) -> CompanyEnrichmentOutput:
        """Convenience method to enrich a company profile.

        Args:
            company_name: Company name
            website: Company website URL
            industry: Industry hint
            description: Description hint
            additional_context: Raw text from uploaded document (corporate profile, business plan)
            analysis_id: Analysis session ID for discovery publishing

        Returns:
            Enriched company profile
        """
        if analysis_id:
            self.set_analysis_id(analysis_id)

        context = {
            "company_name": company_name,
            "website": website,
            "industry": industry.value if industry else "other",
            "description": description or "",
            "additional_context": additional_context,
        }

        return await self.run(
            f"Enrich company profile for {company_name}",
            context=context,
        )
