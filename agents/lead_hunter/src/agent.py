"""Lead Hunter Agent - Tool-Empowered Lead Identification.

This agent identifies REAL potential customers using the 4-layer architecture:

1. COGNITIVE (LLM): Synthesis, explanation, outreach messaging
2. ANALYTICAL (Algorithms): Lead scoring, ICP matching, value calculation
3. OPERATIONAL (Tools): Company enrichment, LinkedIn, email finding
4. GOVERNANCE (Rules): Rate limiting, PDPA compliance, checkpoints

Principle: Algorithms score, tools enrich, LLMs explain.
"""

from __future__ import annotations

import asyncio
import re as _re
import socket
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agents.core.src import AgentCapability, ToolEmpoweredAgent
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.core.src.types import (
    IndustryVertical,
    LeadProfile,
    LeadStatus,
)
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.integrations.eodhd.src.client import EODHDClient
from packages.integrations.hunter.src import get_hunter_client
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.llm.src import get_llm_manager
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer
from packages.scoring.src.market_context import MarketContextScorer
from packages.tools.src import ToolAccess


def _guess_domain(name: str) -> str:
    """Derive a best-effort domain from a company name.

    Strips common legal suffixes, collapses non-alphanumeric characters into
    hyphens, and appends `.com`.  The result is intentionally marked as
    unverified — callers should treat it as a starting point for enrichment,
    not ground truth.
    """
    slug = name.lower()
    for suffix in [
        " pte ltd",
        " pte. ltd.",
        " ltd",
        " inc",
        " corp",
        " limited",
        " sdn bhd",
        " llc",
    ]:
        slug = slug.replace(suffix, "")
    slug = _re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    if not slug:
        return ""
    return f"{slug}.com"


class _CompanyList(BaseModel):
    """Structured output for LLM company extraction — defined at module level for schema reuse."""
    companies: list[dict[str, str]] = []


class LeadScoringCriteria(BaseModel):
    """Criteria for scoring leads."""

    ideal_company_size: str | None = Field(default=None)
    ideal_industries: list[IndustryVertical] = Field(default_factory=list)
    ideal_locations: list[str] = Field(default_factory=list)
    budget_indicators: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    ideal_roles: list[str] = Field(default_factory=list)
    your_acv: float = Field(default=30000)  # Your average contract value


class ContactInfo(BaseModel):
    """Best-effort contact information for outreach."""

    guessed_email: str | None = Field(default=None)
    email_mx_valid: bool = Field(default=False)
    linkedin_company_url: str | None = Field(default=None)
    estimated_decision_maker_title: str = Field(default="")
    estimated_decision_maker_name: str = Field(default="")
    contact_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


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
    contact_info: ContactInfo = Field(default_factory=ContactInfo)

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
    is_live_data: bool = Field(default=False)  # True if any prospect found via tool enrichment

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
            name="lead-hunter",
            description=(
                "Identifies and qualifies real potential customers. "
                "Uses deterministic scoring algorithms for qualification, "
                "enrichment tools for data, and LLM for synthesis/outreach."
            ),
            result_type=LeadHuntingOutput,
            min_confidence=0.50,
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
        self._agent_bus: AgentBus | None = get_agent_bus()
        self._analysis_id: Any = None
        self._eodhd = EODHDClient()
        self._perplexity = get_llm_manager().perplexity
        self._market_scorer = MarketContextScorer()
        self._icp_personas: list[dict[str, Any]] = []  # Populated by PERSONA_DEFINED bus events
        self._buyer_archetypes: list[dict[str, Any]] = []
        self._opportunity_window = None
        # KB qualification frameworks (populated during _do)
        self._kb_qualification: dict | None = None
        # Count of prospects enriched with KB financial benchmarks (reset each _do run)
        self._kb_benchmarked_count: int = 0
        # Market opportunities from MarketIntelligenceAgent (via bus)
        self._market_opportunities: list[dict] = []
        # Competitor weaknesses from CompetitorAnalyst (via bus)
        self._competitor_weaknesses: list[dict] = []
        if self._agent_bus is not None:
            self._agent_bus.subscribe(
                agent_id=self.name,
                discovery_type=DiscoveryType.PERSONA_DEFINED,
                handler=self._on_persona_defined,
            )
            self._agent_bus.subscribe(
                agent_id=self.name,
                discovery_type=DiscoveryType.MARKET_OPPORTUNITY,
                handler=self._on_market_opportunity,
            )
            self._agent_bus.subscribe(
                agent_id=self.name,
                discovery_type=DiscoveryType.COMPETITOR_WEAKNESS,
                handler=self._on_competitor_weakness,
            )

    async def _on_persona_defined(self, message: AgentMessage) -> None:
        """Cache persona definitions from Customer Profiler for ICP refinement."""
        # Scope to current analysis
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        persona = message.content
        if persona and persona not in self._icp_personas:
            self._icp_personas.append(persona)
            self._logger.debug("persona_received_for_icp", persona=persona.get("name", ""))

    async def _on_market_opportunity(self, message: AgentMessage) -> None:
        """Cache market opportunities from Market Intelligence for lead prioritization."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        if message.content and message.content not in self._market_opportunities:
            self._market_opportunities.append(message.content)
            self._logger.debug(
                "market_opportunity_received",
                title=message.title,
                from_agent=message.from_agent,
            )

    async def _on_competitor_weakness(self, message: AgentMessage) -> None:
        """Cache competitor weaknesses from Competitor Analyst for lead approach tailoring."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        if message.content and message.content not in self._competitor_weaknesses:
            self._competitor_weaknesses.append(message.content)
            self._logger.debug(
                "competitor_weakness_received",
                competitor=message.content.get("competitor_name", ""),
                from_agent=message.from_agent,
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
        self._analysis_id = context.get("analysis_id")

        # Load domain knowledge pack — injected into outreach approach synthesis.
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="lead-hunter",
                task_context=task,
            )
        except Exception as _e:
            self._logger.debug("knowledge_pack_load_failed", error=str(_e))

        # Pull personas from bus history (for cases where PERSONA_DEFINED was published before this agent ran)
        if self._agent_bus is not None:
            for msg in self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.PERSONA_DEFINED,
                limit=5,
            ):
                persona = msg.content
                if persona and persona not in self._icp_personas:
                    self._icp_personas.append(persona)

            # Backfill market opportunities
            try:
                opp_history = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.MARKET_OPPORTUNITY,
                    limit=5,
                )
                for msg in opp_history:
                    if msg.content and msg.content not in self._market_opportunities:
                        self._market_opportunities.append(msg.content)
            except Exception as _e:
                self._logger.debug("market_opportunity_history_failed", error=str(_e))

            # Backfill competitor weaknesses
            try:
                weakness_history = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.COMPETITOR_WEAKNESS,
                    limit=10,
                )
                for msg in weakness_history:
                    if msg.content and msg.content not in self._competitor_weaknesses:
                        self._competitor_weaknesses.append(msg.content)
            except Exception as _e:
                self._logger.debug("competitor_weakness_history_failed", error=str(_e))

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
                criteria.ideal_industries[0].value if criteria.ideal_industries else "technology"
            )
            location = criteria.ideal_locations[0] if criteria.ideal_locations else "Singapore"
            current_year = datetime.now().year

            # Pre-compute buyer_signal / pain_signal for elif fallback branches
            value_prop = (context.get("value_proposition", "") or "").strip()
            description = (context.get("description", "") or "").strip()
            pain_points = criteria.pain_points or []
            buyer_signal = (value_prop or description or "")[:100]
            pain_signal = pain_points[0] if pain_points else ""

            # Derive USP-driven buyer archetypes for multi-vertical search
            # Each archetype = a distinct buyer TYPE that would purchase this product
            archetypes = await self._derive_buyer_archetypes(context)
            self._buyer_archetypes = archetypes  # store for _do()

            if archetypes:
                # Build 2 queries per archetype (up to 5 archetypes = up to 10 queries)
                search_queries = []
                for archetype in archetypes[:5]:
                    search_queries.extend(archetype.get("queries", [])[:2])
                self._logger.info(
                    "buyer_archetypes_derived",
                    count=len(archetypes),
                    verticals=[a.get("vertical", "") for a in archetypes],
                    queries=len(search_queries),
                )
            elif buyer_signal:
                search_queries = [
                    f"Singapore companies needing {buyer_signal} {current_year}",
                    f"Singapore SMEs adopting {industry_term} software digital transformation {current_year}",
                    f"growing companies {location} {pain_signal or industry_term} technology buyers {current_year}",
                    f"top {industry_term} firms {location} digital tools {current_year}",
                    f"{industry_term} companies {location} growth stage {current_year}",
                ]
            else:
                search_queries = [
                    f"top {industry_term} startups {location} {current_year}",
                    f"{industry_term} companies {location} series A funding",
                    f"growing {industry_term} SMEs {location}",
                ]
        else:
            search_queries = []

        # Detect vertical slug from industry terms so _process_company() can pass it
        # to KB search — stored as instance attribute for easy access in the pipeline.
        industry_text = " ".join(
            ind.value for ind in criteria.ideal_industries
        ) if criteria.ideal_industries else task
        self._current_vertical_slug = detect_vertical_slug(industry_text)

        plan = {
            "criteria": criteria.model_dump(),
            "seed_companies": seed_companies,
            "search_queries": search_queries,
            "target_count": context.get("target_count", 10),
            "company_name": context.get("company_name", ""),
            "value_proposition": context.get("value_proposition", ""),
            "description": context.get("description", ""),
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
        self._kb_benchmarked_count = 0  # reset per-run counter

        # --- KB Phase: Pull BANT (via SALES_QUALIFICATION) and ICP qualification frameworks ---
        self._kb_qualification = None
        try:
            kmcp = get_knowledge_mcp()
            bant_framework = await kmcp.get_framework("SALES_QUALIFICATION")
            icp_framework = await kmcp.get_framework("ICP_FRAMEWORK")
            # Only store if both returned without error
            if not bant_framework.get("error") and not icp_framework.get("error"):
                self._kb_qualification = {
                    "bant": bant_framework,
                    "icp": icp_framework,
                }
        except Exception as _e:
            self._logger.debug("knowledge_mcp_qualification_failed", error=str(_e))

        # Enrich criteria with bus personas if available
        bus_personas = self._icp_personas[:]  # snapshot
        if bus_personas:
            persona_roles = [p.get("role", "") for p in bus_personas if p.get("role")]
            persona_pain_points = [
                pp for p in bus_personas for pp in (p.get("pain_points") or [])
            ]
            if persona_roles and not criteria.ideal_roles:
                criteria.ideal_roles = persona_roles[:3]
            if persona_pain_points:
                existing = set(criteria.pain_points)
                criteria.pain_points = list(existing | set(persona_pain_points[:5]))

        prospects: list[ProspectCompany] = []
        algorithm_decisions = 0
        llm_decisions = 0

        # Step 1: Get seed companies
        seed_companies = plan.get("seed_companies", [])

        if not seed_companies and plan.get("search_queries"):
            # Boost search queries with market opportunity segments when available
            base_queries: list[str] = list(plan["search_queries"])
            if self._market_opportunities:
                opp_keywords = [
                    opp.get("opportunity", opp.get("title", ""))
                    for opp in self._market_opportunities[:3]
                    if opp.get("opportunity") or opp.get("title")
                ]
                for kw in opp_keywords:
                    if kw:
                        base_queries.append(f"Singapore companies in {kw} segment")
            # Use news_scraper tool to find companies from search (single pass for speed)
            seed_companies = await self._search_for_companies(
                base_queries[:3],  # first 3 queries via tool
                criteria,
            )
            llm_decisions += 1

        # Perplexity multi-archetype tier: runs ALWAYS (not just fallback)
        # Each archetype query finds a different buyer type → 5× more coverage
        _perplexity_used = False
        if getattr(self._perplexity, "is_configured", False):
            archetypes = getattr(self, "_buyer_archetypes", [])
            if archetypes:
                # Run one Perplexity search per archetype in parallel (5 concurrent)
                archetype_queries = [
                    {
                        **plan,
                        "value_proposition": archetype.get("pain_point", plan.get("value_proposition", "")),
                        "description": f"Companies needing: {archetype.get('pain_point', '')}. Size: {archetype.get('company_size', '')}. Trigger: {archetype.get('buying_trigger', '')}",
                        "search_queries": archetype.get("queries", []),
                    }
                    for archetype in archetypes[:5]
                ]
                perplexity_rounds = await asyncio.gather(
                    *[self._discover_companies_via_perplexity(aq, criteria) for aq in archetype_queries],
                    return_exceptions=True,
                )
                perplexity_companies: list[dict[str, Any]] = []
                for round_result in perplexity_rounds:
                    if isinstance(round_result, list):
                        perplexity_companies.extend(round_result)
                # Deduplicate by name (case-insensitive)
                seen_names: set[str] = {c.get("name", "").lower() for c in seed_companies}
                for c in perplexity_companies:
                    name_key = c.get("name", "").lower()
                    if name_key and name_key not in seen_names:
                        seen_names.add(name_key)
                        seed_companies.append(c)
                _perplexity_used = bool(perplexity_companies)
                self._logger.info(
                    "multi_archetype_perplexity_complete",
                    archetypes=len(archetypes),
                    companies_found=len(perplexity_companies),
                    total_unique=len(seed_companies),
                )
            elif not seed_companies:
                # Fallback: single Perplexity pass if no archetypes derived
                self._logger.info("tools_returned_nothing_trying_perplexity")
                seed_companies = await self._discover_companies_via_perplexity(plan, criteria)
                _perplexity_used = bool(seed_companies)

        # Fallback: if tools returned nothing, ask LLM to generate plausible prospects
        if not seed_companies:
            self._logger.info("tools_returned_no_companies_using_llm_fallback")
            seed_companies = await self._discover_companies_via_llm(plan, criteria)
            llm_decisions += 1

        # Step 2-5: Process each company through the pipeline (parallel enrichment)
        batch = seed_companies[: min(plan.get("target_count", 25), 50)]
        raw_results = await asyncio.gather(
            *[self._process_company(seed, criteria) for seed in batch],
            return_exceptions=True,
        )
        for seed, res in zip(batch, raw_results, strict=True):
            if isinstance(res, Exception):
                self._logger.warning("company_processing_failed", company=seed, error=str(res))
            elif res is not None:
                prospects.append(res)
                algorithm_decisions += 3  # ICP, BANT, Value scores

        # Step 6: Segment leads by priority
        if prospects and len(prospects) >= 4:
            segmentation = await self.segment_market(
                [p.model_dump() for p in prospects],
                criteria.pain_points,
            )
            algorithm_decisions += 1

            # Tag prospects with segments
            for segment in segmentation.get("clusters", []):
                for _, member in enumerate(segment.get("members", [])):
                    # Find matching prospect and tag
                    for p in prospects:
                        if p.company_name == member.get("company_name"):
                            p.fit_reasons.append(f"Segment: {segment['name']}")

        # Convert to LeadProfile
        # Lower threshold when all prospects came from LLM fallback (no tool enrichment)
        tool_enriched = any(p.scoring_method == "algorithm" for p in prospects)
        _qualification_threshold = 0.5 if tool_enriched else 0.3
        qualified_leads = []
        for p in prospects:
            if p.fit_score >= _qualification_threshold:
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
                    # Map contact_info fields built by _build_contact_info()
                    contact_name=p.contact_info.estimated_decision_maker_name or None,
                    contact_title=p.contact_info.estimated_decision_maker_title or None,
                    contact_email=p.contact_info.guessed_email or None,
                    contact_linkedin=p.contact_info.linkedin_company_url or None,
                )
                qualified_leads.append(lead)

        # Sort by overall score
        qualified_leads.sort(key=lambda lead: lead.overall_score, reverse=True)

        # Calculate total pipeline value
        total_value = sum(p.expected_value for p in prospects)

        # Market context scoring — check if this is a good time to outreach
        opportunity_window = None
        if prospects:
            industry_str = (
                criteria.ideal_industries[0].value if criteria.ideal_industries else "technology"
            )
            try:
                async with asyncio.timeout(15):
                    opportunity_window = await self._market_scorer.score(
                        industry=industry_str, target_region="Singapore"
                    )
                self._logger.info(
                    "market_context_scored",
                    rating=opportunity_window.rating.value,
                    score=opportunity_window.score,
                )
            except Exception as e:
                self._logger.debug("market_context_score_failed", error=str(e))
        self._opportunity_window = opportunity_window

        # Step 7: Generate outreach recommendations (LLM) + attach per-lead approaches
        approach = ""
        if qualified_leads:
            approach = await self._generate_outreach_approach(
                criteria,
                qualified_leads[:3],
                competitor_weaknesses=self._competitor_weaknesses,
                kb_qualification=self._kb_qualification,
            )
            llm_decisions += 1
            # Attach a short data-driven approach hint to each qualified lead
            top_prospect_map = {p.company_name: p for p in prospects}
            for lead in qualified_leads[:5]:
                prospect = top_prospect_map.get(lead.company_name)
                if prospect and not lead.recommended_approach:
                    hints: list[str] = []
                    if prospect.trigger_events:
                        hints.append(f"tech signals: {', '.join(prospect.trigger_events[:2])}")
                    if prospect.potential_pain_points:
                        hints.append(f"pain: {prospect.potential_pain_points[0]}")
                    if hints:
                        lead.recommended_approach = "; ".join(hints).capitalize() + "."

        # Determine determinism ratio
        total_decisions = algorithm_decisions + llm_decisions
        # No decisions = nothing to evaluate; report 1.0 (fully deterministic) rather than 0
        determinism_ratio = algorithm_decisions / total_decisions if total_decisions > 0 else 1.0

        # is_live_data: True if any prospect was enriched via tool pipeline (algorithm-scored)
        tool_enriched = any(p.scoring_method == "algorithm" for p in prospects)

        sources_searched = (
            ["company_enrichment", "algorithms"]
            + (["Perplexity"] if _perplexity_used else [])
            + (
                ["eodhd"]
                if any(
                    "SGX-listed" in str(event)
                    for p in prospects
                    for event in p.trigger_events
                )
                else []
            )
            + (
                [f"MarketContext:{opportunity_window.rating.value}"]
                if opportunity_window is not None
                else []
            )
            + (["Market Intel DB"] if self._kb_benchmarked_count > 0 else [])
        )

        return LeadHuntingOutput(
            target_criteria=criteria,
            prospects=prospects,
            qualified_leads=qualified_leads,
            total_companies_found=len(prospects),
            qualified_count=len(qualified_leads),
            total_pipeline_value=total_value,
            top_recommendations=self._generate_recommendations(qualified_leads),
            suggested_approach=approach,
            sources_searched=sources_searched,
            confidence=self._calculate_confidence(prospects, qualified_leads),
            is_live_data=tool_enriched,
            algorithm_decisions=algorithm_decisions,
            llm_decisions=llm_decisions,
            determinism_ratio=determinism_ratio,
        )

    async def _fetch_kb_context(
        self, company_name: str, vertical_slug: str | None = None
    ) -> list[str]:
        """Return stored article headlines for a company from the Market Intelligence DB.

        Used as additional trigger event signals when the company appears in the
        KB (e.g. funding rounds, expansion news stored by the ingestion pipeline).
        Passing vertical_slug narrows the semantic search to the relevant vertical.
        Returns empty list when DB is unavailable or company is not found.
        """
        try:
            async with async_session_factory() as db:
                mcp = MarketIntelMCPServer(session=db)
                articles = await mcp.search_market_intelligence(
                    query=company_name, vertical_slug=vertical_slug
                )
                return [a.get("title", "") for a in (articles or [])[:3] if a.get("title")]
        except Exception as e:
            self._logger.debug("kb_context_fetch_failed", company=company_name, error=str(e))
            return []

    async def _enrich_with_eodhd(self, company_name: str) -> dict[str, Any]:
        """Enrich a company with EODHD financial data if it is SGX-listed.

        Returns additional fields to merge into company_data, or an empty dict
        when the company is not found / EODHD is not configured.

        Fields returned (when available):
            employee_count   — from FullTimeEmployees
            budget_confirmed — True if revenue data found (public company)
            revenue_sgd      — latest annual revenue
            market_cap       — market capitalisation
        """
        if not self._eodhd.is_configured:
            return {}
        try:
            results = await self._eodhd.search_companies(
                query=company_name, exchange="SG", limit=5
            )
            ticker = next(
                (r.get("Code") for r in results if r.get("Exchange") == "SG" and r.get("Code")),
                None,
            )
            if not ticker:
                return {}

            fundamentals = await self._eodhd.get_company_fundamentals(ticker, exchange="SG")
            if not fundamentals:
                return {}

            enrichment: dict[str, Any] = {}
            if fundamentals.employees:
                enrichment["employee_count"] = fundamentals.employees
            if fundamentals.revenue:
                enrichment["budget_confirmed"] = True
                enrichment["revenue_sgd"] = fundamentals.revenue
            if fundamentals.market_cap:
                enrichment["market_cap"] = fundamentals.market_cap
            if enrichment:
                enrichment["ticker"] = ticker
                enrichment["exchange"] = "SG"
            return enrichment

        except Exception as e:
            self._logger.debug("eodhd_enrichment_failed", company=company_name, error=str(e))
            return {}

    async def _check_domain_mx(self, domain: str) -> bool:
        """Check DNS reachability for the domain (mirrors lead_enrichment MX check).

        Uses asyncio.to_thread to avoid blocking the event loop.
        """
        try:
            await asyncio.to_thread(socket.getaddrinfo, domain, None, socket.AF_INET)
            return True
        except (socket.gaierror, OSError):
            return False

    async def _build_contact_info(
        self,
        domain: str,
        company_data: dict[str, Any],
        criteria: LeadScoringCriteria,
        enrichment_result: Any,
    ) -> ContactInfo:
        """Derive best-effort contact info from enrichment data and DNS checks.

        Phase 0: Hunter.io domain search (when configured) — surfaces real
        professional contacts, avoiding the generic contact@ fallback.
        Subsequent phases fill in gaps when Hunter is unconfigured or returns
        nothing useful.
        """
        contact_info = ContactInfo()

        if not domain:
            self._logger.debug(
                "contact_info_skipped_no_domain",
                company=company_data.get("name", ""),
            )
            return contact_info

        # Phase 0: Hunter.io domain search — only call when no email has been
        # found yet (conservative: free tier limits 25 searches/month)
        hunter_found_email = False
        hunter_client = get_hunter_client()
        if hunter_client.is_configured:
            hunter_contacts = await hunter_client.domain_search(domain, limit=3)
            if hunter_contacts:
                # Prefer contacts with a known position (professional), else take first
                best = next(
                    (c for c in hunter_contacts if c.position),
                    hunter_contacts[0],
                )
                contact_info.guessed_email = best.email
                contact_info.contact_confidence = min(best.confidence / 100.0, 0.95)
                # Hunter has already verified the domain — mark MX valid
                contact_info.email_mx_valid = True
                hunter_found_email = True
                if best.first_name and best.last_name:
                    contact_info.estimated_decision_maker_name = (
                        f"{best.first_name} {best.last_name}"
                    )
                if best.position:
                    contact_info.estimated_decision_maker_title = best.position

        # Phase 1: Generic email fallback (when Hunter found nothing)
        if not hunter_found_email:
            contact_info.guessed_email = f"contact@{domain}"

            # DNS MX/A record check — async, does not block event loop
            contact_info.email_mx_valid = await self._check_domain_mx(domain)

            # Confidence: MX valid lifts to 0.5
            if contact_info.email_mx_valid:
                contact_info.contact_confidence = 0.5

        # Phase 2: LinkedIn company URL estimation from company name slug
        company_name = company_data.get("name", "")
        if company_name:
            slug = _re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
            contact_info.linkedin_company_url = f"https://linkedin.com/company/{slug}"

        # Phase 3: Decision maker title from ICP ideal_roles (fallback when
        # Hunter did not return a position)
        if not contact_info.estimated_decision_maker_title and criteria.ideal_roles:
            contact_info.estimated_decision_maker_title = criteria.ideal_roles[0]

        # Phase 4: Tool enrichment key_contacts override (highest fidelity)
        if enrichment_result is not None and enrichment_result.success and enrichment_result.data:
            enriched = enrichment_result.data
            key_contacts = getattr(enriched, "key_contacts", None) or []
            for c in key_contacts[:1]:
                name = c.get("name", "")
                title = c.get("title", "")
                if name:
                    contact_info.estimated_decision_maker_name = name
                if title:
                    contact_info.estimated_decision_maker_title = title
                contact_info.contact_confidence = 0.8

        return contact_info

    async def _process_company(
        self,
        company_info: dict[str, Any] | str,
        criteria: LeadScoringCriteria,
    ) -> ProspectCompany | None:
        """Process a single company through the enrichment and scoring pipeline."""
        # Normalize input
        if isinstance(company_info, str):
            company_data = {
                "name": company_info,
                # _guess_domain strips legal suffixes and handles spaces/punctuation;
                # flagged unverified so enrichment may replace it.
                "domain": _guess_domain(company_info),
                "domain_verified": False,
            }
        else:
            company_data = company_info

        # Step 2: OPERATIONAL - Enrich company data
        domain = (
            company_data.get("domain")
            or company_data.get("website", "")
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )

        enrichment_result = None
        if domain:
            # Step 1: KB context (local DB — fast, no external API cost)
            kb_headlines = await self._fetch_kb_context(
                company_data.get("name", ""),
                vertical_slug=getattr(self, "_current_vertical_slug", None),
            )

            # Step 2: External enrichment (parallel — only after KB context gathered)
            enrichment_result, eodhd_data = await asyncio.gather(
                self.use_tool("company_enrichment", domain=domain, name=company_data.get("name")),
                self._enrich_with_eodhd(company_data.get("name", "")),
            )

            if enrichment_result.success and enrichment_result.data:
                enriched = enrichment_result.data
                company_data.update(
                    {
                        "name": enriched.name or company_data.get("name"),
                        "domain": enriched.domain,
                        "industry": enriched.industry,
                        "employee_count": enriched.employee_count or enriched.employee_range,
                        "description": enriched.description,
                        "location": enriched.location.get("city") if enriched.location else None,
                        "funding_stage": enriched.funding_stage,
                        "technologies": enriched.technologies,
                    }
                )

            # EODHD overrides: employee count from stock filings is more accurate than enrichment
            if eodhd_data:
                company_data.update(eodhd_data)

            # KB financial benchmark lookup — queries the Market Intel DB for this
            # company and derives financial health signals from percentile ranks.
            # Runs after EODHD so KB can fill gaps and add richer context.
            # Step 2b trajectory analysis reuses the same session to avoid
            # opening a second concurrent connection per prospect.
            _benchmark_result: dict = {}
            try:
                async with async_session_factory() as _db:
                    _mcp = MarketIntelMCPServer(session=_db)
                    _benchmark_result = await _mcp.find_and_benchmark_company_by_name(
                        name=company_data.get("name", ""),
                        vertical_slug=getattr(self, "_current_vertical_slug", None),
                    )
                    if _benchmark_result.get("found"):
                        _co = _benchmark_result.get("company", {})
                        _fin = _benchmark_result.get("financials", {})
                        _bench = _benchmark_result.get("benchmark", {})
                        _metric_ranks: dict[str, float] = _bench.get("metric_ranks", {})

                        # Override employee count only when KB has a non-zero value
                        # (more reliable than tool enrichment for listed companies)
                        if _co.get("employees"):
                            company_data["employee_count"] = _co["employees"]

                        # Mark budget as confirmed — public company with known revenue
                        company_data["budget_confirmed"] = True
                        if _fin.get("revenue"):
                            company_data["revenue_sgd"] = _fin["revenue"]
                        if _co.get("market_cap_sgd"):
                            company_data["market_cap"] = _co["market_cap_sgd"]

                        # Derive financial health signals from percentile ranks
                        _fh_signals: list[str] = []
                        _growth_rank = _metric_ranks.get("revenue_growth_yoy")
                        _margin_rank = _metric_ranks.get("gross_margin")
                        if _growth_rank is not None:
                            pct = int(_growth_rank * 100)
                            if _growth_rank >= 0.75:
                                _fh_signals.append(f"High-growth (P{pct} revenue growth)")
                            elif _growth_rank < 0.25:
                                _fh_signals.append(f"Slow growth (P{pct}) — may seek new channels")
                        if _margin_rank is not None and _margin_rank >= 0.75:
                            pct = int(_margin_rank * 100)
                            _fh_signals.append(f"Strong margins (P{pct} gross margin)")

                        company_data["_financial_health_signals"] = _fh_signals
                        self._kb_benchmarked_count += 1
                        self._logger.debug(
                            "kb_financial_benchmark_applied",
                            company=company_data.get("name", ""),
                            signals=_fh_signals,
                        )

                    # Step 2b: Trajectory analysis — identifies accelerating companies
                    # (high-intent buyers). Reuses _mcp / _db from the benchmark block
                    # above to avoid opening a second session per prospect.
                    try:
                        # Use ticker from benchmark result if found, otherwise try EODHD search
                        _traj_ticker = None
                        _traj_exchange = "SG"
                        if _benchmark_result.get("found"):
                            _traj_ticker = _benchmark_result.get("company", {}).get("ticker")
                            _traj_exchange = _benchmark_result.get("company", {}).get("exchange", "SG")
                        elif eodhd_data.get("ticker"):
                            _traj_ticker = eodhd_data.get("ticker")
                            _traj_exchange = eodhd_data.get("exchange", "SG")
                        if _traj_ticker:
                            _traj = await _mcp.get_company_trajectory(_traj_ticker, _traj_exchange)
                            if _traj and not _traj.get("error"):
                                _traj_class = _traj.get("trajectory_class", "")
                                _traj_signals: list[str] = []
                                if _traj_class == "ACCELERATING":
                                    _traj_signals.append("Revenue accelerating — high-growth buyer")
                                elif _traj_class == "DECELERATING":
                                    _traj_signals.append("Revenue decelerating — may seek efficiency tools")
                                elif _traj_class == "TURNAROUND":
                                    _traj_signals.append("Turnaround in progress — actively investing")
                                _sga_eff = _traj.get("sga_efficiency_trend", "")
                                if _sga_eff == "improving":
                                    _traj_signals.append("SG&A efficiency improving — GTM-optimizing buyer")
                                elif _sga_eff == "declining":
                                    _traj_signals.append("SG&A efficiency declining — needs GTM optimization")
                                _cagr = _traj.get("revenue_cagr_3y")
                                if _cagr is not None:
                                    _traj_signals.append(f"3Y revenue CAGR: {_cagr*100:.1f}%")
                                if _traj_signals:
                                    existing_fh = company_data.get("_financial_health_signals", [])
                                    company_data["_financial_health_signals"] = existing_fh + _traj_signals
                                    company_data["_trajectory_class"] = _traj_class
                    except Exception as _traj_exc:
                        self._logger.debug(
                            "trajectory_enrichment_failed",
                            company=company_data.get("name", ""),
                            error=str(_traj_exc),
                        )
            except Exception as _bench_exc:
                self._logger.debug(
                    "kb_financial_benchmark_failed",
                    company=company_data.get("name", ""),
                    error=str(_bench_exc),
                )
        else:
            eodhd_data = {}
            kb_headlines = []

        # Step 3: ANALYTICAL - Score ICP fit
        icp_result = await self.score_icp_fit(
            company_data,
            {
                "industries": [i.value for i in criteria.ideal_industries],
                "company_sizes": [criteria.ideal_company_size]
                if criteria.ideal_company_size
                else [],
                "locations": criteria.ideal_locations,
            },
        )
        fit_score = icp_result.get("total_score", 0.5)

        # Step 4: ANALYTICAL - Score with BANT
        # budget_confirmed: True if public company revenue data exists (EODHD)
        # OR if funding stage is known from enrichment
        budget_confirmed = company_data.get("budget_confirmed", False) or (
            company_data.get("funding_stage") is not None
        )
        # Parse employee count to int for numeric comparison (tool may return strings like "11-50")
        employee_count_int = self._parse_employee_count(company_data.get("employee_count")) or 0
        # Bug 1a fix: SMEs (<200 employees) typically have decision-makers as main
        # contacts; larger organisations route to influencers.  Unknown/zero size
        # defaults to "influencer" (conservative).
        if employee_count_int and employee_count_int < 200:
            authority_level = "decision_maker"
        else:
            authority_level = "influencer"

        # Bug 1b fix: score need proportionally by how many of the ICP pain points
        # actually appear in the company's trigger events or description, rather
        # than a binary 0.5/0.7 that ignores all evidence.
        matched = sum(
            1
            for pp in (criteria.pain_points or [])
            if any(
                pp.lower() in str(ev).lower()
                for ev in (
                    company_data.get("trigger_events", [])
                    + [company_data.get("description", "")]
                )
            )
        )
        total_pp = len(criteria.pain_points) if criteria.pain_points else 1
        need_score = 0.3 + 0.5 * (matched / total_pp)  # range 0.3–0.8

        # Bug 1c fix: tier timeline by funding stage, then by company size.
        description_lower = str(company_data.get("description", "")).lower()
        if any(
            w in description_lower for w in ["series a", "series b", "funded", "raised"]
        ):
            timeline_days = 30  # funded companies move fast
        elif employee_count_int and employee_count_int > 100:
            timeline_days = 90  # larger companies have longer cycles
        else:
            timeline_days = 60  # default SME

        lead_data = {
            **company_data,
            "budget_confirmed": budget_confirmed,
            "authority_level": authority_level,
            "need_score": need_score,
            "timeline_days": timeline_days,
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

        # Step 6: Contact enrichment — best-effort, does not block scoring
        contact_info = await self._build_contact_info(
            domain=domain,
            company_data=company_data,
            criteria=criteria,
            enrichment_result=enrichment_result,
        )

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
            trigger_events=(
                company_data.get("technologies", [])[:3]
                + (["SGX-listed public company"] if company_data.get("market_cap") else [])
                + kb_headlines  # Stored news/events from KB ingestion pipeline
                + company_data.get("_financial_health_signals", [])  # KB financial benchmark signals
            )[:5],
            fit_score=fit_score,
            intent_score=intent_score,
            expected_value=expected_value,
            source="enrichment_pipeline",
            scoring_method="algorithm",
            contact_info=contact_info,
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
        # Use news scraper to find company mentions — run queries in parallel
        async def _fetch_one_query(query: str) -> list[dict[str, Any]]:
            news_result = await self.use_tool("news_scraper", query=query, limit=5)
            if not (news_result.success and news_result.data):
                return []
            articles = news_result.data
            if not articles:
                return []
            article_text = "\n".join(
                [f"- {a.title}: {a.content_preview}" for a in articles[:5]]
            )
            # Build a buyer description from ICP criteria so the extraction
            # prompt works for any client — a client selling TO tech companies
            # should not have SaaS/tech firms excluded.
            industry_labels = (
                ", ".join(i.value for i in criteria.ideal_industries[:3])
                if criteria.ideal_industries
                else "business"
            )
            pain_labels = (
                "; ".join(criteria.pain_points[:2])
                if criteria.pain_points
                else "operational or growth challenges"
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You extract POTENTIAL BUYER company names from news articles. "
                        f"Target companies in: {industry_labels}. "
                        f"These buyers typically face: {pain_labels}. "
                        f"Extract companies that would benefit from buying a relevant product/service. "
                        f"Exclude the companies that MADE or SELL the products mentioned. Return as JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Extract Singapore/APAC BUYER company names from these articles:\n{article_text}\n\n"
                        f'Return format: {{"companies": [{{"name": "...", "domain": "..."}}]}}'
                    ),
                },
            ]
            try:
                result = await self.llm.complete_structured(
                    messages=messages,
                    response_model=_CompanyList,
                )
                return result.companies
            except Exception as e:
                self._logger.warning(
                    "company_list_extraction_failed", query=query, error=str(e)
                )
                return []

        batches = await asyncio.gather(*[_fetch_one_query(q) for q in queries[:2]])
        companies: list[dict[str, Any]] = [c for batch in batches for c in batch]

        if not companies:
            self._logger.warning(
                "no_companies_found: queries=%s, search_queries_tried=%d",
                queries,
                len(queries),
            )

        return companies

    async def _derive_buyer_archetypes(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Derive 3-5 buyer archetypes from the company's USP.

        For each archetype, we identify WHICH types of companies would buy this
        product (not just companies in the same industry). This is the USP sweet-spot
        mapping step that makes lead discovery accurate for any client.

        Returns a list of archetype dicts, each with:
          - vertical: industry vertical label (e.g. "advertising agencies")
          - company_size: target headcount range (e.g. "50-500 employees")
          - pain_point: the specific pain this product solves for them
          - buying_trigger: signal that they're in market now
          - queries: list[str] of 2 Perplexity search queries targeting buyers
        """
        value_prop = (context.get("value_proposition", "") or "").strip()
        description = (context.get("description", "") or "").strip()
        company_name = (context.get("company_name", "") or "").strip()
        location = (context.get("target_markets") or ["Singapore"])[0]

        product_context = (value_prop or description or "")[:300]
        if not product_context:
            return []

        prompt = f"""You are a B2B sales strategist. A company called "{company_name}" offers:

{product_context}

Identify 5 DISTINCT buyer archetypes — types of companies that would PURCHASE this product.
For each archetype, think about WHO has the pain that this product solves.

Return a JSON array of 5 objects, each with:
- "vertical": specific industry vertical (e.g. "advertising agencies", "management consulting", "fintech SaaS", "law firms")
- "company_size": headcount sweet spot (e.g. "50-500 employees")
- "pain_point": one-sentence specific pain this product solves for them
- "buying_trigger": one signal that shows they are in-market now (e.g. "recent funding", "hiring surge", "digital transformation initiative")
- "queries": array of 2 search strings to find these buyers in {location}, e.g. ["top advertising agencies Singapore 2026 hiring", "Singapore creative agencies 50-200 staff digital tools"]

Only include archetypes where the product genuinely solves a real problem. Be specific — not generic industry names."""

        messages = [
            {"role": "system", "content": "Return only valid JSON. No markdown. No explanation."},
            {"role": "user", "content": prompt},
        ]
        try:
            import json
            raw = await self._complete(messages, temperature=0, max_tokens=1200)
            cleaned = _re.sub(r"```[a-zA-Z]*\n?", "", raw or "").strip()
            archetypes = json.loads(cleaned)
            if isinstance(archetypes, list):
                return archetypes[:5]
        except Exception as e:
            self._logger.debug("archetype_derivation_failed", error=str(e))
        return []

    async def _discover_companies_via_llm(
        self,
        plan: dict[str, Any],
        criteria: LeadScoringCriteria,
    ) -> list[dict[str, Any]]:
        """Generate prospect companies using LLM when tools are unavailable.

        This is the COGNITIVE layer fallback. Companies are LLM-generated based on
        industry knowledge — they get the same algorithmic scoring as tool-sourced
        companies, so the output is still deterministic where it matters.
        """
        industry = (
            criteria.ideal_industries[0].value
            if criteria.ideal_industries
            else "technology"
        )
        location = criteria.ideal_locations[0] if criteria.ideal_locations else "Singapore"
        target_count = plan.get("target_count", 10)
        pain_points = criteria.pain_points[:3]

        value_prop = (plan.get("value_proposition", "") or "").strip()
        description_text = (plan.get("description", "") or "").strip()
        company_name_local = (plan.get("company_name", "") or "").strip()
        buyer_context = (value_prop or description_text or "")[:200]

        if buyer_context:
            buyer_desc = (
                f"List {min(target_count, 8)} real companies in {location} that are potential BUYERS of "
                f"a product like '{company_name_local}' which offers: {buyer_context}.\n\n"
                f"These are companies with these challenges: {', '.join(pain_points) or 'digital transformation, growth'}.\n\n"
                f"Focus on SMEs (10-500 employees) across any industry that would benefit from this solution. "
                f"Include Singapore-registered or well-known regional companies.\n\n"
                f'Return JSON: {{"companies": [{{"name": "...", "domain": "..."}}]}}'
            )
        else:
            buyer_desc = (
                f"List {min(target_count, 8)} real {industry} companies based in or operating in {location} "
                f"that are likely experiencing these challenges: {', '.join(pain_points) or 'digital transformation, growth'}.\n\n"
                f"Focus on SMEs (10-500 employees). Include Singapore-listed or well-known regional companies.\n\n"
                f'Return JSON: {{"companies": [{{"name": "...", "domain": "..."}}]}}'
            )

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"{_knowledge_header}{buyer_desc}",
            },
        ]
        try:
            result = await self.llm.complete_structured(
                messages=messages,
                response_model=_CompanyList,
            )
            return result.companies
        except Exception as e:
            self._logger.warning("llm_company_discovery_failed", error=str(e))
            return []

    async def _discover_companies_via_perplexity(
        self,
        plan: dict[str, Any],
        criteria: LeadScoringCriteria,
    ) -> list[dict[str, Any]]:
        """Discover prospect companies using Perplexity's search-augmented research.

        Sits between the news_scraper tool tier (fast, structured) and the pure
        LLM fallback (no external data).  Perplexity performs live web searches,
        so results reference real companies rather than hallucinated names, while
        still avoiding the latency of per-company enrichment calls.

        Returns a list of company dicts (max 8) on success, or [] on any error.
        """
        if not self._perplexity.is_configured:
            return []

        value_prop = (plan.get("value_proposition", "") or "").strip()
        description_text = (plan.get("description", "") or "").strip()
        industry = (
            criteria.ideal_industries[0].value
            if criteria.ideal_industries
            else "technology"
        )
        current_year = datetime.now().year

        # Use the first specific search query from the plan if available (archetype queries
        # provide targeted queries like "Singapore e-commerce companies needing AI marketing").
        # Fall back to constructing a topic from value_proposition / description.
        specific_queries: list[str] = plan.get("search_queries") or []  # type: ignore[assignment]
        if specific_queries and isinstance(specific_queries, list):
            first_query = specific_queries[0]
            # Avoid appending "Singapore" if already present in the query
            if "singapore" not in first_query.lower():
                topic = f"{first_query} Singapore {current_year}"[:200]
            else:
                topic = f"{first_query} {current_year}"[:200]
        else:
            buyer_signal = (value_prop or description_text or industry)[:120]
            topic = f"Singapore companies that need {buyer_signal} {current_year}"[:200]

        try:
            async with asyncio.timeout(30):
                market_text = await self._perplexity.research_market(
                    topic=topic,
                    region="Singapore",
                )
        except Exception as e:
            self._logger.debug("perplexity_research_failed", topic=topic, error=str(e))
            return []

        if not market_text:
            return []

        company_name = plan.get("company_name") or "our client"
        # Build a generic buyer description from value_prop so the prompt works
        # for ANY client type (not just marketing/GTM companies).
        buyer_context = (
            f"companies that are potential buyers or clients of {company_name}"
            + (f", which offers: {value_prop[:200]}" if value_prop else "")
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"You extract POTENTIAL CUSTOMER company names from market research text. "
                    f"Extract {buyer_context}. "
                    f"These should be real businesses that are actively growing and would "
                    f"purchase this type of product or service. "
                    f"Return at most 10 companies. Return as JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Extract Singapore/APAC company names that are potential customers "
                    f"from this market research:\n{market_text[:4000]}\n\n"
                    f'Return format: {{"companies": [{{"name": "...", "domain": "..."}}]}}'
                ),
            },
        ]
        try:
            result = await self.llm.complete_structured(
                messages=messages,
                response_model=_CompanyList,
            )
            return result.companies[:10]
        except Exception as e:
            self._logger.debug("perplexity_company_extraction_failed", error=str(e))
            return []

    async def _generate_outreach_approach(
        self,
        criteria: LeadScoringCriteria,
        top_leads: list[LeadProfile],
        competitor_weaknesses: list[dict] | None = None,
        kb_qualification: dict | None = None,
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

        # Build competitor weakness context when available
        weakness_section = ""
        if competitor_weaknesses:
            weakness_lines = []
            for w in competitor_weaknesses[:3]:
                comp = w.get("competitor_name", "Competitor")
                weaknesses = w.get("weaknesses", [])
                if weaknesses:
                    weakness_lines.append(f"- {comp}: {', '.join(weaknesses[:2])}")
            if weakness_lines:
                weakness_section = (
                    "\n\nKnown competitor weaknesses (tailor recommended_approach to exploit):\n"
                    + "\n".join(weakness_lines)
                )

        # Build KB qualification guidance when available
        kb_section = ""
        if kb_qualification:
            bant = kb_qualification.get("bant", {})
            icp = kb_qualification.get("icp", {})
            bant_name = bant.get("framework_name", "SALES_QUALIFICATION")
            icp_name = icp.get("framework_name", "ICP_FRAMEWORK")
            kb_section = (
                f"\n\nQualification frameworks in use: {bant_name} (BANT/SPIN criteria), {icp_name}. "
                "Scores are derived from these frameworks — reference them when explaining lead fit."
            )

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""{_knowledge_header}Based on these algorithmically-scored leads:
{chr(10).join(lead_summaries)}

Pain points we address: {", ".join(criteria.pain_points) or "General business challenges"}
Our ACV: SGD {criteria.your_acv:,.0f}{weakness_section}{kb_section}

Write a 2-3 sentence outreach approach that:
1. References specific signals from the data
2. Addresses their likely pain points
3. Is appropriate for {", ".join(criteria.ideal_locations[:2]) if criteria.ideal_locations else "Singapore"} context""",
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
        recommendations.append(f"Prioritize {top.company_name} (score: {top.overall_score:.0%})")

        # Volume recommendation
        if len(qualified_leads) >= 5:
            avg_score = sum(lead.overall_score for lead in qualified_leads) / len(qualified_leads)
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
            avg = sum(lead.overall_score for lead in qualified) / len(qualified)
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
        if not result.prospects:
            # Nothing found even after LLM fallback — cap at just below threshold
            # so we don't waste a retry iteration that would return the same empty result.
            return 0.35

        score = 0.3  # Base score

        # Check prospects found
        score += 0.2

        # Check qualified leads
        if result.qualified_leads:
            score += 0.2
            # Quality: leads should have reasons
            with_reasons = sum(1 for p in result.prospects if p.fit_reasons)
            if with_reasons >= 2:
                score += 0.15

        # Check scoring quality (algorithm-based)
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

        # Market context bonus — GREEN window gets a confidence boost; RED gets a penalty
        ow = getattr(self, "_opportunity_window", None)
        if ow is not None:
            from packages.scoring.src.market_context import OpportunityRating  # noqa: PLC0415
            if ow.rating == OpportunityRating.GREEN:
                score += 0.05
            elif ow.rating == OpportunityRating.RED:
                score = max(0.0, score - 0.05)  # Deduct — bad timing, lower confidence in pipeline

        # Knowledge MCP qualification framework bonus (+0.03 when BANT/ICP frameworks loaded)
        if self._kb_qualification is not None:
            score += 0.03

        # KB financial benchmark bonus (+0.05 when at least one prospect was benchmarked)
        if getattr(self, "_kb_benchmarked_count", 0) > 0:
            score += 0.05

        # Trajectory enrichment bonus (+0.03 when at least one prospect has trajectory signals)
        # Trajectory signals are appended to _financial_health_signals, which lands in trigger_events.
        trajectory_enriched = sum(
            1
            for p in result.prospects
            if any(
                kw in ev
                for ev in (p.trigger_events or [])
                for kw in ("accelerating", "decelerating", "Turnaround", "CAGR", "SG&A efficiency")
            )
        )
        if trajectory_enriched > 0:
            score += 0.03

        return min(score, 1.0)

    async def _act(self, result: LeadHuntingOutput, confidence: float) -> LeadHuntingOutput:
        """Stamp confidence and publish qualified leads to AgentBus for CampaignArchitect."""
        result.confidence = confidence

        if self._agent_bus is None:
            return result

        # Build a lookup so we can attach contact_info to bus messages
        prospect_map = {p.company_name: p for p in result.prospects}

        published = 0
        for lead in result.qualified_leads[:10]:
            try:
                prospect = prospect_map.get(lead.company_name)
                contact_info_dict: dict[str, Any] = {}
                if prospect is not None:
                    contact_info_dict = prospect.contact_info.model_dump()
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.LEAD_FOUND,
                    title=lead.company_name,
                    content={
                        "company_name": lead.company_name,
                        "industry": lead.industry.value if lead.industry else "",
                        "location": lead.location or "",
                        "website": lead.website or "",
                        "contact_name": lead.contact_name or "",
                        "contact_title": lead.contact_title or "",
                        "contact_email": lead.contact_email or "",
                        "fit_score": lead.fit_score,
                        "intent_score": lead.intent_score,
                        "overall_score": lead.overall_score,
                        "pain_points": lead.pain_points,
                        "trigger_events": lead.trigger_events,
                        "recommended_approach": lead.recommended_approach or "",
                        "contact_info": contact_info_dict,
                    },
                    confidence=lead.overall_score,
                    analysis_id=self._analysis_id,
                )
                published += 1
            except Exception as e:
                self._logger.warning("bus_publish_lead_failed", lead=lead.company_name, error=str(e))

        self._logger.info(
            "leads_published_to_bus",
            published=published,
            total_qualified=len(result.qualified_leads),
        )
        return result

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
