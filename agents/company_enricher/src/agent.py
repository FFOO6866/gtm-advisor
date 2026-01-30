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

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import (
    AgentBus,
    DiscoveryType,
    get_agent_bus,
)
from packages.core.src.types import IndustryVertical
from packages.llm.src import get_llm_manager


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

    # Metadata
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources_analyzed: list[str] = Field(default_factory=list)


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
        return """You are the Company Enricher Agent, a specialist in extracting structured company information from websites.

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

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan website analysis."""
        context = context or {}

        website = context.get("website")
        company_name = context.get("company_name", "")

        plan = {
            "website": website,
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
        website = plan.get("website") or context.get("website")
        company_name = plan.get("company_name") or context.get("company_name", "Unknown")

        # If no website, use Perplexity to research the company
        if not website:
            return await self._research_company_without_website(company_name, context)

        # Analyze website using Perplexity
        if plan.get("use_perplexity"):
            return await self._analyze_with_perplexity(website, company_name, context)
        else:
            return await self._analyze_with_llm(website, company_name, context)

    async def _research_company_without_website(
        self,
        company_name: str,
        context: dict[str, Any],
    ) -> CompanyEnrichmentOutput:
        """Research company using just the name (no website provided)."""
        self._logger.info("researching_company_without_website", company_name=company_name)

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Research and extract information about this company:

Company Name: {company_name}
Industry Hint: {context.get("industry", "Not specified")}
Description Hint: {context.get("description", "Not specified")}

Without a website, use the company name and hints to:
1. Try to identify what they do
2. Infer target markets
3. Identify potential competitors
4. Determine likely business model

Note: Without a website, confidence should be lower (0.4-0.6).""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompanyEnrichmentOutput,
            messages=messages,
        )

        result.company_name = company_name
        result.website = ""
        result.sources_analyzed = ["company_name_inference"]

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
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"""Based on this research about {company_name} ({website}):

{perplexity_response}

Additional context from user:
- Industry: {context.get("industry", "Not specified")}
- Description: {context.get("description", "Not specified")}

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

Note: This is inference-based analysis, so confidence should be moderate (0.5-0.7).""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompanyEnrichmentOutput,
            messages=messages,
        )

        result.company_name = company_name
        result.website = website
        result.sources_analyzed = ["user_provided_context"]

        return result

    async def _check(self, result: CompanyEnrichmentOutput) -> float:
        """Validate enrichment quality."""
        score = 0.3  # Base score for completing

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
                        "competitor_name": competitor,
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

        self._logger.info(
            "discoveries_published",
            company=result.company_name,
            discoveries_count=5 if result.mentioned_competitors else 4,
        )

    async def enrich_company(
        self,
        company_name: str,
        website: str | None = None,
        industry: IndustryVertical | None = None,
        description: str | None = None,
        analysis_id: UUID | None = None,
    ) -> CompanyEnrichmentOutput:
        """Convenience method to enrich a company profile.

        Args:
            company_name: Company name
            website: Company website URL
            industry: Industry hint
            description: Description hint
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
        }

        return await self.run(
            f"Enrich company profile for {company_name}",
            context=context,
        )
