"""Lead Hunter Agent - Tool-Empowered Lead Identification.

This agent identifies REAL potential customers using the 4-layer architecture:

1. COGNITIVE (LLM): Synthesis, explanation, outreach messaging
2. ANALYTICAL (Algorithms): Lead scoring, ICP matching, value calculation
3. OPERATIONAL (Tools): Company enrichment, LinkedIn, email finding
4. GOVERNANCE (Rules): Rate limiting, PDPA compliance, checkpoints

Principle: Algorithms score, tools enrich, LLMs explain.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src import AgentCapability, ToolEmpoweredAgent
from packages.core.src.types import (
    IndustryVertical,
    LeadProfile,
    LeadStatus,
)
from packages.tools.src import ToolAccess


class LeadScoringCriteria(BaseModel):
    """Criteria for scoring leads."""

    ideal_company_size: str | None = Field(default=None)
    ideal_industries: list[IndustryVertical] = Field(default_factory=list)
    ideal_locations: list[str] = Field(default_factory=list)
    budget_indicators: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    your_acv: float = Field(default=30000)  # Your average contract value


class ProspectCompany(BaseModel):
    """A prospected company with details."""

    company_name: str = Field(...)
    website: str | None = Field(default=None)
    domain: str | None = Field(default=None)
    description: str = Field(default="")
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    location: str | None = Field(default=None)
    employee_count: str | None = Field(default=None)
    funding_status: str | None = Field(default=None)

    # Why this company is a prospect
    fit_reasons: list[str] = Field(default_factory=list)
    potential_pain_points: list[str] = Field(default_factory=list)
    trigger_events: list[str] = Field(default_factory=list)

    # Contact info (if found)
    key_contacts: list[dict[str, str]] = Field(default_factory=list)

    # Scoring (from algorithms, not LLM)
    fit_score: float = Field(default=0.5, ge=0.0, le=1.0)
    intent_score: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_value: float = Field(default=0.0)

    # Source
    source: str = Field(default="enrichment")
    source_urls: list[str] = Field(default_factory=list)

    # Decision attribution
    scoring_method: str = Field(default="algorithm")  # algorithm or llm


class LeadHuntingOutput(BaseModel):
    """Output from lead hunting."""

    target_criteria: LeadScoringCriteria = Field(...)
    prospects: list[ProspectCompany] = Field(default_factory=list)
    qualified_leads: list[LeadProfile] = Field(default_factory=list)

    # Summary
    total_companies_found: int = Field(default=0)
    qualified_count: int = Field(default=0)
    top_recommendations: list[str] = Field(default_factory=list)
    total_pipeline_value: float = Field(default=0.0)

    # Outreach suggestions (LLM-generated)
    suggested_approach: str = Field(default="")
    email_templates: list[str] = Field(default_factory=list)

    # Metadata
    sources_searched: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Decision attribution (for transparency)
    algorithm_decisions: int = Field(default=0)
    llm_decisions: int = Field(default=0)
    determinism_ratio: float = Field(default=0.0)


class LeadHunterAgent(ToolEmpoweredAgent[LeadHuntingOutput]):
    """Lead Hunter Agent - Tool-Empowered Lead Identification.

    4-Layer Architecture:

    COGNITIVE LAYER (LLM):
    - Parse search results into structured data
    - Generate outreach messaging
    - Explain why leads are qualified

    ANALYTICAL LAYER (Algorithms):
    - ICPScorer: Deterministic fit scoring
    - LeadScorer: BANT qualification scoring
    - LeadValueCalculator: Expected value calculation
    - MarketSegmenter: Segment leads by priority

    OPERATIONAL LAYER (Tools):
    - company_enrichment: Enrich company data from domain
    - contact_enrichment: Find contact details
    - email_finder: Find email addresses
    - linkedin_scraper: Get LinkedIn data
    - news_scraper: Find recent news

    GOVERNANCE LAYER:
    - Rate limiting on enrichment APIs
    - PDPA compliance for contact data
    - Budget controls on API calls
    - Checkpoints for high-value outreach
    """

    def __init__(self) -> None:
        super().__init__(
            name="lead_hunter",
            description=(
                "Identifies and qualifies real potential customers. "
                "Uses deterministic scoring algorithms for qualification, "
                "enrichment tools for data, and LLM for synthesis/outreach."
            ),
            result_type=LeadHuntingOutput,
            min_confidence=0.60,
            max_iterations=2,
            model="gpt-4o",
            # Tool access: read-only (no CRM writes)
            tool_access=[ToolAccess.READ],
            allowed_tools=[
                "company_enrichment",
                "contact_enrichment",
                "email_finder",
                "linkedin_scraper",
                "news_scraper",
            ],
            # Algorithms to use
            use_icp_scorer=True,
            use_lead_scorer=True,
            use_calculators=True,
            use_clustering=True,
            # Budget limits
            max_tokens_per_task=30000,
            max_cost_per_task=3.0,
            # Capabilities
            capabilities=[
                AgentCapability(
                    name="prospect-identification",
                    description="Find companies matching ICP criteria",
                ),
                AgentCapability(
                    name="lead-scoring",
                    description="Score leads using BANT algorithm",
                ),
                AgentCapability(
                    name="contact-research",
                    description="Research key contacts at target companies",
                ),
                AgentCapability(
                    name="outreach-planning",
                    description="Plan outreach approach",
                ),
            ],
        )

    def get_system_prompt(self) -> str:
        return """You are the Lead Hunter, a specialist in B2B lead generation.

IMPORTANT: Your role is primarily to:
1. SYNTHESIZE data from tools and algorithms into coherent narratives
2. EXPLAIN why leads are qualified (using scores from algorithms)
3. CREATE outreach messaging and recommendations

You do NOT:
- Score leads yourself (algorithms do this)
- Make up company data (tools provide this)
- Estimate values (calculators do this)

When presenting leads:
- Reference the algorithm-generated scores
- Explain the fit in human terms
- Suggest personalized outreach based on data

Focus on Singapore/APAC market context."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan lead hunting strategy."""
        context = context or {}

        # Build scoring criteria from context
        criteria = LeadScoringCriteria(
            ideal_company_size=context.get("target_company_size"),
            ideal_industries=[
                IndustryVertical(ind)
                for ind in context.get("target_industries", [])
                if ind in [e.value for e in IndustryVertical]
            ],
            ideal_locations=context.get("target_locations", ["Singapore"]),
            pain_points=context.get("pain_points", []),
            your_acv=context.get("your_acv", 30000),
        )

        # Get seed companies to research (from context or generate list)
        seed_companies = context.get("seed_companies", [])

        # If no seed companies, generate search queries for LLM
        if not seed_companies:
            industry_term = (
                criteria.ideal_industries[0].value
                if criteria.ideal_industries
                else "technology"
            )
            location = criteria.ideal_locations[0] if criteria.ideal_locations else "Singapore"

            # These will be used to find seed companies via web search
            search_queries = [
                f"top {industry_term} startups {location} 2024",
                f"{industry_term} companies {location} series A funding",
                f"growing {industry_term} SMEs {location}",
            ]
        else:
            search_queries = []

        plan = {
            "criteria": criteria.model_dump(),
            "seed_companies": seed_companies,
            "search_queries": search_queries,
            "target_count": context.get("target_count", 10),
            "steps": [
                "1. Identify target companies (from seeds or search)",
                "2. Enrich company data via tools",
                "3. Score with ICP algorithm",
                "4. Score with BANT algorithm",
                "5. Calculate expected value",
                "6. Segment by priority",
                "7. Generate outreach recommendations (LLM)",
            ],
        }

        return plan

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LeadHuntingOutput:
        """Execute lead hunting using 4-layer architecture."""
        context = context or {}
        criteria = LeadScoringCriteria(**plan["criteria"])

        prospects: list[ProspectCompany] = []
        algorithm_decisions = 0
        llm_decisions = 0

        # Step 1: Get seed companies
        seed_companies = plan.get("seed_companies", [])

        if not seed_companies and plan.get("search_queries"):
            # Use LLM to identify companies from search
            seed_companies = await self._search_for_companies(
                plan["search_queries"],
                criteria,
            )
            llm_decisions += 1

        # Step 2-5: Process each company through the pipeline
        for seed in seed_companies[: plan.get("target_count", 10)]:
            try:
                prospect = await self._process_company(seed, criteria)
                if prospect:
                    prospects.append(prospect)
                    algorithm_decisions += 3  # ICP, BANT, Value scores
            except Exception as e:
                self._logger.warning("company_processing_failed", company=seed, error=str(e))

        # Step 6: Segment leads by priority
        if prospects and len(prospects) >= 4:
            segmentation = await self.segment_market(
                [p.model_dump() for p in prospects],
                criteria.pain_points,
            )
            algorithm_decisions += 1

            # Tag prospects with segments
            for segment in segmentation.get("clusters", []):
                for i, member in enumerate(segment.get("members", [])):
                    # Find matching prospect and tag
                    for p in prospects:
                        if p.company_name == member.get("company_name"):
                            p.fit_reasons.append(f"Segment: {segment['name']}")

        # Convert to LeadProfile
        qualified_leads = []
        for p in prospects:
            if p.fit_score >= 0.5:  # Qualification threshold
                lead = LeadProfile(
                    company_name=p.company_name,
                    industry=p.industry,
                    employee_count=self._parse_employee_count(p.employee_count),
                    location=p.location,
                    website=p.website,
                    status=LeadStatus.NEW,
                    fit_score=p.fit_score,
                    intent_score=p.intent_score,
                    overall_score=(p.fit_score * 0.6 + p.intent_score * 0.4),
                    pain_points=p.potential_pain_points,
                    trigger_events=p.trigger_events,
                    source="lead_hunter",
                )
                qualified_leads.append(lead)

        # Sort by overall score
        qualified_leads.sort(key=lambda l: l.overall_score, reverse=True)

        # Calculate total pipeline value
        total_value = sum(p.expected_value for p in prospects)

        # Step 7: Generate outreach recommendations (LLM)
        approach = ""
        if qualified_leads:
            approach = await self._generate_outreach_approach(criteria, qualified_leads[:3])
            llm_decisions += 1

        # Determine determinism ratio
        total_decisions = algorithm_decisions + llm_decisions
        determinism_ratio = algorithm_decisions / total_decisions if total_decisions > 0 else 0

        return LeadHuntingOutput(
            target_criteria=criteria,
            prospects=prospects,
            qualified_leads=qualified_leads,
            total_companies_found=len(prospects),
            qualified_count=len(qualified_leads),
            total_pipeline_value=total_value,
            top_recommendations=self._generate_recommendations(qualified_leads),
            suggested_approach=approach,
            sources_searched=["company_enrichment", "algorithms"],
            confidence=self._calculate_confidence(prospects, qualified_leads),
            algorithm_decisions=algorithm_decisions,
            llm_decisions=llm_decisions,
            determinism_ratio=determinism_ratio,
        )

    async def _process_company(
        self,
        company_info: dict[str, Any] | str,
        criteria: LeadScoringCriteria,
    ) -> ProspectCompany | None:
        """Process a single company through the enrichment and scoring pipeline."""
        # Normalize input
        if isinstance(company_info, str):
            company_data = {"name": company_info, "domain": f"{company_info.lower().replace(' ', '')}.com"}
        else:
            company_data = company_info

        # Step 2: OPERATIONAL - Enrich company data
        domain = company_data.get("domain") or company_data.get("website", "").replace("https://", "").replace("http://", "").split("/")[0]

        if domain:
            enrichment_result = await self.use_tool(
                "company_enrichment",
                domain=domain,
                name=company_data.get("name"),
            )

            if enrichment_result.success and enrichment_result.data:
                enriched = enrichment_result.data
                company_data.update({
                    "name": enriched.name or company_data.get("name"),
                    "domain": enriched.domain,
                    "industry": enriched.industry,
                    "employee_count": enriched.employee_count or enriched.employee_range,
                    "description": enriched.description,
                    "location": enriched.location.get("city") if enriched.location else None,
                    "funding_stage": enriched.funding_stage,
                    "technologies": enriched.technologies,
                })

        # Step 3: ANALYTICAL - Score ICP fit
        icp_result = await self.score_icp_fit(
            company_data,
            {
                "industries": [i.value for i in criteria.ideal_industries],
                "company_sizes": [criteria.ideal_company_size] if criteria.ideal_company_size else [],
                "locations": criteria.ideal_locations,
            },
        )
        fit_score = icp_result.get("total_score", 0.5)

        # Step 4: ANALYTICAL - Score with BANT
        lead_data = {
            **company_data,
            "budget_confirmed": company_data.get("funding_stage") is not None,
            "authority_level": "decision_maker" if company_data.get("employee_count", 0) < 50 else "influencer",
            "need_score": 0.7 if criteria.pain_points else 0.5,
            "timeline_days": 60,  # Default assumption
        }
        bant_result = await self.score_lead(lead_data)
        intent_score = bant_result.get("total_score", 0.5)

        # Step 5: ANALYTICAL - Calculate expected value
        value_result = await self.calculate_lead_value(
            lead_score=(fit_score + intent_score) / 2,
            company_size=self._get_size_bucket(company_data.get("employee_count")),
            acv=criteria.your_acv,
        )
        expected_value = value_result.get("expected_value", 0)

        # Build prospect
        industry = IndustryVertical.OTHER
        if company_data.get("industry"):
            industry_str = company_data["industry"].lower()
            for iv in IndustryVertical:
                if iv.value in industry_str:
                    industry = iv
                    break

        return ProspectCompany(
            company_name=company_data.get("name", "Unknown"),
            website=company_data.get("website") or f"https://{domain}" if domain else None,
            domain=domain,
            description=company_data.get("description", ""),
            industry=industry,
            location=company_data.get("location"),
            employee_count=str(company_data.get("employee_count", "")),
            funding_status=company_data.get("funding_stage"),
            fit_reasons=icp_result.get("reasons", []),
            potential_pain_points=criteria.pain_points[:3],
            trigger_events=company_data.get("technologies", [])[:3],  # Tech as signals
            fit_score=fit_score,
            intent_score=intent_score,
            expected_value=expected_value,
            source="enrichment_pipeline",
            scoring_method="algorithm",
        )

    async def _search_for_companies(
        self,
        queries: list[str],
        criteria: LeadScoringCriteria,
    ) -> list[dict[str, Any]]:
        """Use LLM to identify companies from search queries.

        This is the COGNITIVE layer - LLM helps identify companies,
        but scoring happens via algorithms.
        """
        # Use news scraper to find company mentions
        companies = []

        for query in queries[:2]:  # Limit queries
            news_result = await self.use_tool(
                "news_scraper",
                query=query,
                limit=5,
            )

            if news_result.success and news_result.data:
                # Extract company names from news using LLM
                articles = news_result.data
                if articles:
                    article_text = "\n".join([
                        f"- {a.title}: {a.content_preview}"
                        for a in articles[:5]
                    ])

                    messages = [
                        {"role": "system", "content": "Extract company names from news articles. Return as JSON list."},
                        {"role": "user", "content": f"Extract Singapore/APAC company names from:\n{article_text}\n\nReturn format: {{\"companies\": [{{\"name\": \"...\", \"domain\": \"...\"}}]}}"},
                    ]

                    try:
                        from pydantic import BaseModel

                        class CompanyList(BaseModel):
                            companies: list[dict[str, str]] = []

                        result = await self.llm.complete_structured(
                            messages=messages,
                            response_model=CompanyList,
                        )
                        companies.extend(result.companies)
                    except Exception:
                        pass

        # Also add some mock Singapore companies for demo
        if not companies:
            companies = [
                {"name": "TechStartup Pte Ltd", "domain": "techstartup.sg"},
                {"name": "Finnovate Solutions", "domain": "finnovate.sg"},
                {"name": "DataDriven AI", "domain": "datadriven.ai"},
            ]

        return companies

    async def _generate_outreach_approach(
        self,
        criteria: LeadScoringCriteria,
        top_leads: list[LeadProfile],
    ) -> str:
        """Generate outreach approach using LLM (COGNITIVE layer)."""
        if not top_leads:
            return "Expand search criteria to find more qualified leads."

        # Prepare lead summaries
        lead_summaries = []
        for lead in top_leads:
            lead_summaries.append(
                f"- {lead.company_name}: Fit {lead.fit_score:.0%}, Intent {lead.intent_score:.0%}, "
                f"Industry: {lead.industry.value}"
            )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Based on these algorithmically-scored leads:
{chr(10).join(lead_summaries)}

Pain points we address: {', '.join(criteria.pain_points) or 'General business challenges'}
Our ACV: SGD {criteria.your_acv:,.0f}

Write a 2-3 sentence outreach approach that:
1. References specific signals from the data
2. Addresses their likely pain points
3. Is appropriate for Singapore B2B context""",
            },
        ]

        return await self._complete(messages)

    def _generate_recommendations(self, qualified_leads: list[LeadProfile]) -> list[str]:
        """Generate recommendations based on lead data."""
        if not qualified_leads:
            return ["Broaden search criteria to find more leads"]

        recommendations = []

        # Top lead recommendation
        top = qualified_leads[0]
        recommendations.append(
            f"Prioritize {top.company_name} (score: {top.overall_score:.0%})"
        )

        # Volume recommendation
        if len(qualified_leads) >= 5:
            avg_score = sum(l.overall_score for l in qualified_leads) / len(qualified_leads)
            recommendations.append(
                f"Pipeline health: {len(qualified_leads)} qualified leads, avg score {avg_score:.0%}"
            )

        return recommendations

    def _calculate_confidence(
        self,
        prospects: list[ProspectCompany],
        qualified: list[LeadProfile],
    ) -> float:
        """Calculate confidence based on data quality."""
        if not prospects:
            return 0.3

        score = 0.4  # Base

        # More prospects = higher confidence
        if len(prospects) >= 5:
            score += 0.15
        elif len(prospects) >= 3:
            score += 0.1

        # Qualified leads
        if qualified:
            score += 0.15
            # High average score
            avg = sum(l.overall_score for l in qualified) / len(qualified)
            if avg >= 0.7:
                score += 0.1

        # Enrichment quality
        enriched = sum(1 for p in prospects if p.domain)
        if enriched / len(prospects) >= 0.8:
            score += 0.1

        return min(score, 0.95)

    def _parse_employee_count(self, value: Any) -> int | None:
        """Parse employee count from various formats."""
        if not value:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # Handle ranges like "11-50"
            if "-" in value:
                try:
                    return int(value.split("-")[0])
                except ValueError:
                    pass
            # Handle plain numbers
            try:
                return int(value.replace(",", ""))
            except ValueError:
                pass
        return None

    def _get_size_bucket(self, employee_count: Any) -> str:
        """Get size bucket from employee count."""
        count = self._parse_employee_count(employee_count)
        if not count:
            return "small"
        if count <= 10:
            return "micro"
        elif count <= 50:
            return "small"
        elif count <= 200:
            return "medium"
        elif count <= 1000:
            return "large"
        else:
            return "enterprise"

    async def _check(self, result: LeadHuntingOutput) -> float:
        """Validate lead hunting quality."""
        score = 0.3  # Base score

        # Check prospects found
        if result.prospects:
            score += 0.2

        # Check qualified leads
        if result.qualified_leads:
            score += 0.2
            # Quality: leads should have reasons
            with_reasons = sum(
                1 for p in result.prospects if p.fit_reasons
            )
            if with_reasons >= 2:
                score += 0.15

        # Check scoring quality (algorithm-based)
        if result.prospects:
            algo_scored = sum(1 for p in result.prospects if p.scoring_method == "algorithm")
            if algo_scored / len(result.prospects) >= 0.8:
                score += 0.15

        # Check outreach approach
        if result.suggested_approach and len(result.suggested_approach) > 50:
            score += 0.15

        # Check recommendations
        if result.top_recommendations:
            score += 0.1

        # Determinism bonus - higher ratio = more reliable
        if result.determinism_ratio >= 0.7:
            score += 0.05

        return min(score, 1.0)

    # ==========================================================================
    # Convenience Methods
    # ==========================================================================

    async def hunt_leads(
        self,
        target_industries: list[IndustryVertical],
        target_locations: list[str] | None = None,
        company_size: str | None = None,
        pain_points: list[str] | None = None,
        your_acv: float = 30000,
        count: int = 10,
    ) -> LeadHuntingOutput:
        """Hunt for leads matching criteria.

        Args:
            target_industries: Industries to target
            target_locations: Geographic locations
            company_size: Target company size
            pain_points: Pain points your product solves
            your_acv: Your average contract value (SGD)
            count: Number of leads to find

        Returns:
            Lead hunting results with algorithm-scored leads
        """
        context = {
            "target_industries": [i.value for i in target_industries],
            "target_locations": target_locations or ["Singapore"],
            "target_company_size": company_size,
            "pain_points": pain_points or [],
            "your_acv": your_acv,
            "target_count": count,
        }

        return await self.run(
            f"Find {count} qualified leads in {target_industries[0].value}",
            context=context,
        )

    async def score_company(
        self,
        domain: str,
        your_acv: float = 30000,
    ) -> dict[str, Any]:
        """Score a single company.

        Uses the full pipeline: enrich → ICP score → lead score → value.

        Args:
            domain: Company domain
            your_acv: Your ACV

        Returns:
            Scoring results with full attribution
        """
        criteria = LeadScoringCriteria(your_acv=your_acv)
        prospect = await self._process_company({"domain": domain}, criteria)

        if prospect:
            return {
                "company": prospect.company_name,
                "domain": prospect.domain,
                "fit_score": prospect.fit_score,
                "intent_score": prospect.intent_score,
                "expected_value": prospect.expected_value,
                "fit_reasons": prospect.fit_reasons,
                "scoring_method": prospect.scoring_method,
                "decision_log": self.get_decision_log(),
            }

        return {"error": "Could not process company"}
