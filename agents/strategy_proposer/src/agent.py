"""Strategy Proposer Agent — reads insights and proposes high-level strategies for user approval.

Sits between the insight-gathering agents (Market Intelligence, Competitor Analyst,
Customer Profiler, Lead Hunter) and the execution layer (Campaign Strategist,
Campaign Architect, Outreach Executor).

The flow is:
  Insights → STRATEGY PROPOSER (user approves) → Campaigns → Execute → Monitor

Pulls from the AgentBus:
- MARKET_TREND      → Market Intelligence signals
- MARKET_OPPORTUNITY → Identified market openings
- MARKET_THREAT      → Risks from Market Intelligence
- COMPETITOR_WEAKNESS → Competitor Analyst findings
- COMPETITOR_FOUND    → Known competitors (context for positioning)
- PERSONA_DEFINED     → Customer Profiler output (ICP, persona detail)
- PAIN_POINT          → Customer pain points from profiling
- LEAD_FOUND          → Lead Hunter prospects (volume = market receptivity signal)
- CAMPAIGN_READY      → Prior campaign plans if analysis has been run before

Publishes:
- STRATEGY_PROPOSED → Full strategy proposal for user review/approval
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, DiscoveryType, get_agent_bus
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.knowledge.src.frameworks import (
    CIALDINI_PRINCIPLES,
    GTM_FRAMEWORKS,
    RACE_FRAMEWORK,
    SINGAPORE_SME_CONTEXT,
)
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class ProposedStrategy(BaseModel):
    """A high-level strategy proposed by AI from analysis insights."""

    name: str = Field(...)
    description: str = Field(...)
    insight_sources: list[str] = Field(default_factory=list)
    rationale: str = Field(...)
    expected_outcome: str = Field(default="")
    success_metrics: list[dict] = Field(default_factory=list)
    priority: str = Field(default="medium")
    estimated_timeline: str = Field(default="")
    target_segment: str = Field(default="")
    category: str = Field(default="")


class StrategyProposalOutput(BaseModel):
    """Complete set of proposed strategies from insight analysis."""

    company_summary: str = Field(default="")
    market_context: str = Field(default="")
    strategies: list[ProposedStrategy] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class StrategyProposerAgent(BaseGTMAgent[StrategyProposalOutput]):
    """Strategy Proposer — reads gathered insights and proposes high-level strategies.

    This generic agent works for any company and any industry. It synthesises
    intelligence from all insight-gathering agents into 4-7 actionable strategies.
    The user approves or rejects each strategy; only approved ones flow into
    detailed campaign planning.

    Strategies are derived from SPECIFIC insights on the bus — not from thin air.
    """

    def __init__(self, bus: AgentBus | None = None) -> None:
        super().__init__(
            name="strategy-proposer",
            description=(
                "Reads insights from all analysis agents and proposes 4-7 high-level "
                "strategies for user review. Only approved strategies proceed to "
                "campaign planning and execution."
            ),
            result_type=StrategyProposalOutput,
            min_confidence=0.50,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="strategy-proposal",
                    description="Synthesise agent insights into 4-7 actionable strategies",
                ),
                AgentCapability(
                    name="insight-synthesis",
                    description="Read and consolidate findings from Market Intel, Competitor, Persona, and Lead agents",
                ),
                AgentCapability(
                    name="priority-ranking",
                    description="Rank strategies by impact vs effort for a specific company context",
                ),
            ],
        )
        self._agent_bus: AgentBus | None = bus or get_agent_bus()
        self._bus = self._agent_bus
        self._current_analysis_id: Any = None

        # Bus-sourced intelligence (reset per run in _plan)
        self._bus_personas: list[dict[str, Any]] = []
        self._bus_pain_points: list[dict[str, Any]] = []
        self._bus_competitor_weaknesses: list[dict[str, Any]] = []
        self._bus_competitors_found: list[dict[str, Any]] = []
        self._bus_market_trends: list[dict[str, Any]] = []
        self._bus_market_opportunities: list[dict[str, Any]] = []
        self._bus_market_threats: list[dict[str, Any]] = []
        self._bus_leads: list[dict[str, Any]] = []
        self._bus_prior_campaigns: list[dict[str, Any]] = []

    def get_system_prompt(self) -> str:
        return """You are a strategic advisor reviewing analysis findings and proposing high-level strategies.

Your job is to synthesise intelligence from multiple sources into clear, prioritised strategies that a business owner can understand and approve.

You operate between the insight layer and the execution layer:
  Market research + Competitor analysis + Customer personas + Lead intelligence
  → YOUR STRATEGIES (approved by user)
  → Detailed campaign plans

Your output must be:
- INSIGHT-GROUNDED: every strategy must cite which specific finding triggered it
- ADVISORY: plain business language — no framework jargon, no acronym soup
- ACTIONABLE: a clear description of what the company should do
- MEASURABLE: each strategy has concrete success metrics
- PRIORITISED: ranked by business impact relative to effort

You think like an experienced commercial advisor — not an academic consultant.
Your language is direct, commercial, and specific to the company in front of you."""

    # ------------------------------------------------------------------
    # PDCA: Plan
    # ------------------------------------------------------------------

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        analysis_id = context.get("analysis_id")
        self._current_analysis_id = analysis_id

        # Reset per-run accumulation to prevent cross-analysis contamination
        self._bus_personas.clear()
        self._bus_pain_points.clear()
        self._bus_competitor_weaknesses.clear()
        self._bus_competitors_found.clear()
        self._bus_market_trends.clear()
        self._bus_market_opportunities.clear()
        self._bus_market_threats.clear()
        self._bus_leads.clear()
        self._bus_prior_campaigns.clear()

        # -- Domain knowledge pack (Layer 4 synthesized guides) -----------
        # Use kmcp_pack to avoid shadowing the framework kmcp variable below
        kmcp_pack = get_knowledge_mcp()
        self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
            agent_name="strategy-proposer",
            task_context=task,
        )

        # -- Static frameworks (Layer 1 — always available) ---------------
        kmcp = get_knowledge_mcp()
        race_raw = await kmcp.get_framework("RACE_FRAMEWORK")
        gtm_raw = await kmcp.get_framework("GTM_FRAMEWORKS")
        cialdini_raw = await kmcp.get_framework("CIALDINI_PRINCIPLES")
        sg_ctx_raw = await kmcp.get_framework("SINGAPORE_SME_CONTEXT")

        # -- AgentBus history --------------------------------------------
        bus_personas: list[dict[str, Any]] = []
        bus_pain_points: list[dict[str, Any]] = []
        bus_weaknesses: list[dict[str, Any]] = []
        bus_competitors: list[dict[str, Any]] = []
        bus_trends: list[dict[str, Any]] = []
        bus_opportunities: list[dict[str, Any]] = []
        bus_threats: list[dict[str, Any]] = []
        bus_leads: list[dict[str, Any]] = []
        bus_prior_campaigns: list[dict[str, Any]] = []

        if self._bus is not None:
            # Personas from Customer Profiler
            seen_persona_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.PERSONA_DEFINED,
                limit=5,
            ):
                if msg.title not in seen_persona_keys:
                    seen_persona_keys.add(msg.title)
                    bus_personas.append({"title": msg.title, **msg.content})

            # Pain points from Customer Profiler
            seen_pain_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.PAIN_POINT,
                limit=10,
            ):
                if msg.title not in seen_pain_keys:
                    seen_pain_keys.add(msg.title)
                    bus_pain_points.append({"title": msg.title, **msg.content})

            # Competitor weaknesses from Competitor Analyst
            seen_weakness_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.COMPETITOR_WEAKNESS,
                limit=10,
            ):
                if msg.title not in seen_weakness_keys:
                    seen_weakness_keys.add(msg.title)
                    bus_weaknesses.append({"title": msg.title, **msg.content})

            # Competitors found
            seen_competitor_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.COMPETITOR_FOUND,
                limit=8,
            ):
                if msg.title not in seen_competitor_keys:
                    seen_competitor_keys.add(msg.title)
                    bus_competitors.append({"title": msg.title, **msg.content})

            # Market trends from Market Intelligence
            seen_trend_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.MARKET_TREND,
                limit=10,
            ):
                if msg.title not in seen_trend_keys:
                    seen_trend_keys.add(msg.title)
                    bus_trends.append({"title": msg.title, **msg.content})

            # Market opportunities
            seen_opp_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.MARKET_OPPORTUNITY,
                limit=8,
            ):
                if msg.title not in seen_opp_keys:
                    seen_opp_keys.add(msg.title)
                    bus_opportunities.append({"title": msg.title, **msg.content})

            # Market threats
            seen_threat_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.MARKET_THREAT,
                limit=8,
            ):
                if msg.title not in seen_threat_keys:
                    seen_threat_keys.add(msg.title)
                    bus_threats.append({"title": msg.title, **msg.content})

            # Leads from Lead Hunter (volume = market receptivity signal)
            seen_lead_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.LEAD_FOUND,
                limit=20,
            ):
                if msg.title not in seen_lead_keys:
                    seen_lead_keys.add(msg.title)
                    bus_leads.append({"title": msg.title, **msg.content})

            # Prior campaign plans from Campaign Architect (if re-analysis)
            seen_campaign_keys: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.CAMPAIGN_READY,
                limit=3,
            ):
                if msg.title not in seen_campaign_keys:
                    seen_campaign_keys.add(msg.title)
                    bus_prior_campaigns.append({"title": msg.title, **msg.content})

        # Populate instance lists for use in _check()
        self._bus_personas.extend(bus_personas)
        self._bus_pain_points.extend(bus_pain_points)
        self._bus_competitor_weaknesses.extend(bus_weaknesses)
        self._bus_competitors_found.extend(bus_competitors)
        self._bus_market_trends.extend(bus_trends)
        self._bus_market_opportunities.extend(bus_opportunities)
        self._bus_market_threats.extend(bus_threats)
        self._bus_leads.extend(bus_leads)
        self._bus_prior_campaigns.extend(bus_prior_campaigns)

        # -- Market vertical intelligence (DB / MarketIntelMCPServer) ----
        kb_vertical_context: dict[str, Any] = {}
        kb_vertical_benchmarks: dict[str, Any] = {}
        industry_text = context.get("industry", "") or context.get("description", "")
        vertical_slug = detect_vertical_slug(industry_text)
        if vertical_slug:
            try:
                async with async_session_factory() as db:
                    mcp_server = MarketIntelMCPServer(session=db)
                    kb_vertical_context = await mcp_server.get_vertical_landscape(vertical_slug) or {}
                    kb_vertical_benchmarks = await mcp_server.get_vertical_benchmarks(vertical_slug) or {}
            except Exception as exc:
                self._logger.debug("vertical_intel_failed", error=str(exc))

        return {
            "task": task,
            "company_info": context.get("company_profile") or {
                "company_name": context.get("company_name", ""),
                "description": context.get("description", ""),
                "industry": context.get("industry", ""),
                "target_markets": context.get("target_markets", []),
                "products": context.get("products", []),
                "goals": context.get("goals", ""),
                "value_proposition": context.get("value_proposition", ""),
            },
            "company_name": context.get("company_name", ""),
            # AgentBus intelligence
            "bus_personas": bus_personas,
            "bus_pain_points": bus_pain_points,
            "bus_competitor_weaknesses": bus_weaknesses,
            "bus_competitors_found": bus_competitors,
            "bus_market_trends": bus_trends,
            "bus_market_opportunities": bus_opportunities,
            "bus_market_threats": bus_threats,
            "bus_leads": bus_leads,
            "bus_prior_campaigns": bus_prior_campaigns,
            # Market vertical DB data
            "vertical_slug": vertical_slug,
            "kb_vertical_context": kb_vertical_context,
            "kb_vertical_benchmarks": kb_vertical_benchmarks,
            # Framework content (for prompt injection)
            "race_framework": race_raw.get("content", RACE_FRAMEWORK),
            "gtm_frameworks": gtm_raw.get("content", GTM_FRAMEWORKS),
            "cialdini_principles": cialdini_raw.get("content", CIALDINI_PRINCIPLES),
            "sg_sme_context": sg_ctx_raw.get("content", SINGAPORE_SME_CONTEXT),
        }

    # ------------------------------------------------------------------
    # PDCA: Do
    # ------------------------------------------------------------------

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> StrategyProposalOutput:
        company_info = plan.get("company_info", {})
        company_name = plan.get("company_name", "") or company_info.get("company_name", "")
        bus_personas = plan.get("bus_personas", [])
        bus_pain_points = plan.get("bus_pain_points", [])
        bus_weaknesses = plan.get("bus_competitor_weaknesses", [])
        bus_competitors = plan.get("bus_competitors_found", [])
        bus_trends = plan.get("bus_market_trends", [])
        bus_opportunities = plan.get("bus_market_opportunities", [])
        bus_threats = plan.get("bus_market_threats", [])
        bus_leads = plan.get("bus_leads", [])
        bus_prior_campaigns = plan.get("bus_prior_campaigns", [])
        vertical_slug = plan.get("vertical_slug", "")
        kb_vertical_context = plan.get("kb_vertical_context", {})
        kb_vertical_benchmarks = plan.get("kb_vertical_benchmarks", {})
        gtm_frameworks = plan.get("gtm_frameworks", GTM_FRAMEWORKS)
        cialdini_principles = plan.get("cialdini_principles", CIALDINI_PRINCIPLES)
        sg_sme_context = plan.get("sg_sme_context", SINGAPORE_SME_CONTEXT)

        # Knowledge pack header — injected into user message (Rule 7: not system prompt)
        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""

        # ---- Serialize framework excerpts for prompt ----

        # GTM motion fit criteria (condensed — for internal reasoning only)
        gtm_fit_summary = ""
        if isinstance(gtm_frameworks, dict):
            for motion_key, motion_data in list(gtm_frameworks.items())[:5]:
                if not isinstance(motion_data, dict):
                    continue
                best_for = motion_data.get("best_for", "")
                sg_fit = motion_data.get("sg_sme_fit", "")
                gtm_fit_summary += (
                    f"  {motion_key}: {best_for[:120]}\n"
                    f"    SG fit: {sg_fit[:120]}\n"
                )
        if not gtm_fit_summary:
            gtm_fit_summary = "(GTM motion context unavailable — apply from knowledge)"

        # Cialdini influence mechanisms (condensed — for internal reasoning only)
        cialdini_summary = ""
        if isinstance(cialdini_principles, dict):
            priority_principles = ["social_proof", "reciprocity", "authority", "scarcity"]
            for key in priority_principles:
                p = cialdini_principles.get(key, {})
                if p:
                    cialdini_summary += (
                        f"  {key}: {p.get('description', '')[:100]}\n"
                    )
        if not cialdini_summary:
            cialdini_summary = "(Influence principles unavailable — apply from knowledge)"

        # SG SME context highlights
        sg_context_summary = ""
        if isinstance(sg_sme_context, dict):
            for key in list(sg_sme_context.keys())[:4]:
                val = sg_sme_context.get(key, {})
                if isinstance(val, dict):
                    sg_context_summary += f"  {key}: {json.dumps(val)[:200]}\n"
        if not sg_context_summary:
            sg_context_summary = (
                "LinkedIn is dominant B2B channel. PSG grants reduce friction. "
                "PDPA compliance mandatory for outreach. Relationship-first culture."
            )

        # ---- Build intelligence blocks from bus data ----

        personas_block = ""
        if bus_personas:
            personas_block = "CUSTOMER PERSONAS (from Customer Profiler):\n"
            for p in bus_personas[:4]:
                personas_block += f"  - {p.get('title', 'Unknown')}: {json.dumps(p)[:300]}\n"
        else:
            personas_block = "CUSTOMER PERSONAS: Not yet profiled — infer from industry and company context.\n"

        pain_points_block = ""
        if bus_pain_points:
            pain_points_block = "CUSTOMER PAIN POINTS (from Customer Profiler):\n"
            for pp in bus_pain_points[:6]:
                pain_points_block += f"  - {pp.get('title', '')}: {json.dumps(pp)[:200]}\n"

        weaknesses_block = ""
        if bus_weaknesses:
            weaknesses_block = "COMPETITOR WEAKNESSES (from Competitor Analyst):\n"
            for w in bus_weaknesses[:5]:
                weaknesses_block += f"  - {w.get('title', '')}: {json.dumps(w)[:200]}\n"
        else:
            weaknesses_block = "COMPETITOR WEAKNESSES: Not yet analyzed — apply general differentiation reasoning.\n"

        competitors_block = ""
        if bus_competitors:
            competitors_block = "KNOWN COMPETITORS (from Competitor Analyst):\n"
            for c in bus_competitors[:5]:
                competitors_block += f"  - {c.get('title', '')}: {json.dumps(c)[:150]}\n"

        trends_block = ""
        if bus_trends:
            trends_block = "MARKET TRENDS (from Market Intelligence):\n"
            for t in bus_trends[:5]:
                trends_block += f"  - {t.get('title', '')}: {json.dumps(t)[:200]}\n"
        else:
            trends_block = "MARKET TRENDS: No signals loaded — apply Singapore market defaults.\n"

        opportunities_block = ""
        if bus_opportunities:
            opportunities_block = "MARKET OPPORTUNITIES (from Market Intelligence):\n"
            for o in bus_opportunities[:4]:
                opportunities_block += f"  - {o.get('title', '')}: {json.dumps(o)[:200]}\n"

        threats_block = ""
        if bus_threats:
            threats_block = "MARKET THREATS (from Market Intelligence):\n"
            for t in bus_threats[:4]:
                threats_block += f"  - {t.get('title', '')}: {json.dumps(t)[:200]}\n"

        leads_signal_block = ""
        if bus_leads:
            lead_verticals = list({
                lead.get("industry", lead.get("vertical", ""))
                for lead in bus_leads
                if lead.get("industry") or lead.get("vertical")
            })
            leads_signal_block = (
                f"LEAD HUNTER SIGNAL: {len(bus_leads)} prospects identified. "
                f"Verticals present: {', '.join(lead_verticals[:5]) or 'mixed'}. "
                "This indicates a market with identifiable buyers — direct outreach motion is viable.\n"
            )
        else:
            leads_signal_block = "LEAD HUNTER SIGNAL: No leads loaded — use market size estimates.\n"

        prior_campaigns_block = ""
        if bus_prior_campaigns:
            prior_campaigns_block = "PRIOR CAMPAIGN PLANS (reference — do not simply repeat):\n"
            for c in bus_prior_campaigns[:2]:
                prior_campaigns_block += f"  - {c.get('title', '')}: {json.dumps(c)[:300]}\n"

        # Vertical market intelligence
        vertical_block = ""
        if vertical_slug and (kb_vertical_context or kb_vertical_benchmarks):
            vertical_block = f"\nMARKET VERTICAL INTELLIGENCE ({vertical_slug}):\n"
            if kb_vertical_context:
                vertical_block += f"  Landscape: {json.dumps(kb_vertical_context)[:400]}\n"
            if kb_vertical_benchmarks:
                vertical_block += f"  Benchmarks: {json.dumps(kb_vertical_benchmarks)[:400]}\n"

        # ---- Build the full user prompt --------------------------------
        user_prompt = f"""{_knowledge_header}You are a strategic advisor analyzing {company_name or 'this company'} in the {company_info.get('industry', 'technology')} sector.

=== COMPANY PROFILE ===
Company: {company_name or 'Unknown'}
Industry: {company_info.get('industry', 'Not specified')}
Description: {company_info.get('description', 'Not specified')}
Products/Services: {company_info.get('products', 'Not specified')}
Target Markets: {company_info.get('target_markets', ['Singapore'])}
Business Goals: {company_info.get('goals', 'Not specified')}
Value Proposition: {company_info.get('value_proposition', 'Not specified')}

=== INTELLIGENCE FROM ANALYSIS AGENTS ===
{personas_block}
{pain_points_block}
{weaknesses_block}
{competitors_block}
{trends_block}
{opportunities_block}
{threats_block}
{leads_signal_block}
{prior_campaigns_block}
{vertical_block}

=== STRATEGIC CONTEXT (internal use — do not surface to user) ===

GTM motion fit reference:
{gtm_fit_summary}

Influence mechanisms reference:
{cialdini_summary}

Singapore market context:
{sg_context_summary}

=== YOUR TASK ===

Based on the intelligence gathered by our analysis team, propose 4-7 high-level strategies for {company_name or 'this company'}.

Each strategy must:
1. Be derived from a SPECIFIC insight above — cite exactly which finding triggered it in insight_sources
2. Have a clear expected_outcome with measurable success_metrics ([{{metric, target}}])
3. Be written as advisory — plain business language, not framework jargon
4. Be actionable — something the company can execute in a defined timeframe
5. Include a priority (high/medium/low) based on impact vs effort for THIS company
6. Specify which target_segment it addresses (customers, partners, channels, internal capability)
7. Assign a category: acquisition, retention, expansion, foundation, or partnership

Strategy categories to draw from:
- FOUNDATION: Fix what is broken before spending on growth (website, compliance, digital presence, PSG eligibility)
- ACQUISITION: Win new customers from specific segments identified in the intelligence
- RETENTION: Engage and grow existing customers
- EXPANSION: Enter new markets, segments, or geographies
- PARTNERSHIP: Build ecosystem — associations (ASME, SGTech, SBF), channel partners, co-marketing

Priority guidance:
- HIGH: High impact + low effort or fixes a critical gap blocking growth
- MEDIUM: Meaningful impact but requires sustained effort over 30-90 days
- LOW: Long-term positioning or nice-to-have given resource constraints

IMPORTANT RULES:
1. NEVER propose a strategy without tying it to a specific insight from the data above — use insight_sources to cite it
2. NEVER use generic strategy names that apply to every company — be specific to what the data shows
3. The rationale must explain WHY this matters for THIS company in plain business language — do not cite framework names (RACE, Cialdini, PLG, SLG etc.)
4. success_metrics must be concrete and tied to THIS company's market size, not arbitrary round numbers
5. DO NOT ignore the competitive landscape — strategies must account for the specific competitors named
6. The user will review each strategy and approve or reject it — write for a business owner, not a consultant
7. Only approved strategies will be turned into detailed campaign plans

ANTI-PATTERNS to avoid:
  ✗ "Improve digital presence" — applies to every company, means nothing
  ✗ "Build brand awareness" — not specific to any insight
  ✗ "Leverage social media" — no indication of which insight drove this or what outcome
  ✗ rationale: "Using RACE framework Reach stage..." — framework citation, not advisory language

GOOD PATTERNS to follow:
  ✓ "Target independent agency founders directly — 36 identifiable decision-makers buy faster than procurement-driven networks"
  ✓ "Fix PSG vendor eligibility before scaling outreach — it makes every sale 50% easier and no competitor has applied yet"
  ✓ "Publish industry benchmark data competitors are sitting on — your target buyers search for this every quarter"

Populate company_summary with a 1-2 sentence factual summary of the company's current situation.
Populate market_context with the 2-3 most important market dynamics affecting strategy choice.
"""

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        return await self._complete_structured(
            response_model=StrategyProposalOutput,
            messages=messages,
            max_tokens=8192,
        )

    # ------------------------------------------------------------------
    # PDCA: Check
    # ------------------------------------------------------------------

    async def _check(self, result: StrategyProposalOutput) -> float:
        """Compute confidence from proposal completeness. Base score 0.2."""
        score = 0.2

        strategies = result.strategies

        # 4+ strategies proposed: +0.15
        if len(strategies) >= 4:
            score += 0.15
        elif len(strategies) >= 2:
            score += 0.05

        # Every strategy has non-empty insight_sources: +0.15
        if strategies and all(len(s.insight_sources) > 0 for s in strategies):
            score += 0.15
        elif strategies and any(len(s.insight_sources) > 0 for s in strategies):
            score += 0.07

        # Every strategy has a substantive rationale (>30 chars): +0.10
        if strategies and all(len(s.rationale) > 30 for s in strategies):
            score += 0.10
        elif strategies and any(len(s.rationale) > 30 for s in strategies):
            score += 0.05

        # Every strategy has at least one success_metric: +0.10
        if strategies and all(len(s.success_metrics) >= 1 for s in strategies):
            score += 0.10
        elif strategies and any(len(s.success_metrics) >= 1 for s in strategies):
            score += 0.05

        # Mix of priorities (not all the same): +0.05
        if strategies:
            priority_values = {s.priority for s in strategies}
            if len(priority_values) >= 2:
                score += 0.05

        # Mix of categories (not all the same): +0.05
        if strategies:
            category_values = {s.category for s in strategies if s.category}
            if len(category_values) >= 2:
                score += 0.05

        # Bus had real persona/competitor/trend data: +0.10
        has_bus_data = bool(
            self._bus_personas
            or self._bus_competitor_weaknesses
            or self._bus_market_trends
            or self._bus_market_opportunities
        )
        if has_bus_data:
            score += 0.10

        # Knowledge pack was loaded and contributed: +0.05
        knowledge_pack = getattr(self, "_knowledge_pack", {})
        if knowledge_pack.get("formatted_injection"):
            score += 0.05

        return min(0.95, score)

    # ------------------------------------------------------------------
    # PDCA: Act
    # ------------------------------------------------------------------

    async def _act(
        self, result: StrategyProposalOutput, confidence: float
    ) -> StrategyProposalOutput:
        """Stamp confidence, populate data_sources_used, publish STRATEGY_PROPOSED."""
        result.confidence = confidence

        # Build data_sources_used list
        sources: list[str] = ["LLM:gpt-4o (strategy synthesis)"]
        if self._bus_personas:
            sources.append(f"AgentBus:PERSONA_DEFINED ({len(self._bus_personas)} personas)")
        if self._bus_pain_points:
            sources.append(f"AgentBus:PAIN_POINT ({len(self._bus_pain_points)} pain points)")
        if self._bus_competitor_weaknesses:
            sources.append(
                f"AgentBus:COMPETITOR_WEAKNESS ({len(self._bus_competitor_weaknesses)} weaknesses)"
            )
        if self._bus_competitors_found:
            sources.append(
                f"AgentBus:COMPETITOR_FOUND ({len(self._bus_competitors_found)} competitors)"
            )
        if self._bus_market_trends:
            sources.append(f"AgentBus:MARKET_TREND ({len(self._bus_market_trends)} signals)")
        if self._bus_market_opportunities:
            sources.append(
                f"AgentBus:MARKET_OPPORTUNITY ({len(self._bus_market_opportunities)} opportunities)"
            )
        if self._bus_market_threats:
            sources.append(f"AgentBus:MARKET_THREAT ({len(self._bus_market_threats)} threats)")
        if self._bus_leads:
            sources.append(f"AgentBus:LEAD_FOUND ({len(self._bus_leads)} prospects)")
        if self._bus_prior_campaigns:
            sources.append(f"AgentBus:CAMPAIGN_READY ({len(self._bus_prior_campaigns)} prior plans)")

        knowledge_pack = getattr(self, "_knowledge_pack", {})
        if knowledge_pack.get("formatted_injection"):
            guide_slugs = knowledge_pack.get("guide_slugs_loaded", [])
            sources.append(f"KnowledgePack:synthesized_guides ({', '.join(guide_slugs)})")

        sources.extend([
            "Framework:GTM_FRAMEWORKS",
            "Framework:CIALDINI_PRINCIPLES (Cialdini — Influence)",
            "Framework:SINGAPORE_SME_CONTEXT",
        ])

        result.data_sources_used = sources

        # Publish STRATEGY_PROPOSED to the bus
        if self._bus is not None:
            high_priority = [s.name for s in result.strategies if s.priority == "high"]
            strategy_names = [s.name for s in result.strategies]

            try:
                await self._bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.STRATEGY_PROPOSED,
                    title=f"Strategy Proposal: {len(result.strategies)} strategies for {result.company_summary[:60] or 'company'}",
                    content={
                        "strategy_count": len(result.strategies),
                        "strategy_names": strategy_names,
                        "high_priority_strategies": high_priority,
                        "categories_covered": list({s.category for s in result.strategies if s.category}),
                        "company_summary": result.company_summary[:300],
                        "market_context": result.market_context[:300],
                        "confidence": confidence,
                    },
                    confidence=confidence,
                    analysis_id=self._current_analysis_id,
                )
            except Exception as exc:
                self._logger.warning("strategy_publish_failed", error=str(exc))

        return result
