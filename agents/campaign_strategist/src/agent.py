"""Campaign Strategist Agent — AI marketing director that produces phased GTM roadmaps.

This is the strategic layer above the Campaign Architect. While the Architect
produces tactical campaign plans (messaging, templates, sequences), the Strategist
produces a 12-month GTM roadmap: maturity diagnosis, motion selection, phased
campaign calendar, and framework attribution.

Pulls from the AgentBus:
- PERSONA_DEFINED  → Customer Profiler output (ICP, persona detail)
- COMPETITOR_WEAKNESS → Competitor Analyst findings
- MARKET_TREND     → Market Intelligence signals
- LEAD_FOUND       → Lead Hunter prospects (volume = market size signal)
- CAMPAIGN_READY   → Prior Campaign Architect output (if any)

Publishes:
- ROADMAP_READY    → Full GTM roadmap summary for downstream agents and UI
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
    CAMPAIGN_BRIEF_TEMPLATE,
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


class ProposedCampaign(BaseModel):
    """A campaign proposed by the AI strategist."""

    name: str = Field(...)
    phase: str = Field(...)  # immediate, short_term, mid_term, long_term
    priority_rank: int = Field(default=1)
    objective: str = Field(...)
    objective_type: str = Field(default="lead_gen")  # awareness, lead_gen, conversion, retention
    channels: list[str] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)
    # e.g. "RACE:Reach + Cialdini:Social Proof — build credibility before outreach"
    framework_rationale: str = Field(default="")
    # e.g. "Digital Marketing Strategy (Kingsnorth), RACE Ch.4"
    knowledge_source: str = Field(default="")
    target_persona: str = Field(default="")
    kpis: list[str] = Field(default_factory=list)
    estimated_duration_days: int = Field(default=30)
    estimated_budget_sgd: float = Field(default=0.0)
    depends_on: str | None = Field(default=None)  # Name of prerequisite campaign
    quick_win: bool = Field(default=False)
    strategy_track: str = Field(default="")  # Track name: "Digital Presence", "Outbound Sales", etc.


class StrategyTrack(BaseModel):
    """A strategic track grouping related campaigns."""

    name: str = Field(...)                          # "Digital Presence", "Outbound Sales"
    insight_source: str = Field(default="")          # Which insight triggered this track
    rationale: str = Field(default="")               # Why this track matters
    framework: str = Field(default="")               # RACE stage or principle driving it
    campaigns: list[ProposedCampaign] = Field(default_factory=list)
    expected_outcome: str = Field(default="")
    success_metric: str = Field(default="")


class _TrackExpansion(BaseModel):
    """Second-pass: expand a strategy track into granular executable tasks."""

    tasks: list[ProposedCampaign] = Field(default_factory=list)


class GTMRoadmapOutput(BaseModel):
    """Complete GTM roadmap with phased campaigns."""

    title: str = Field(...)
    executive_summary: str = Field(...)
    gtm_motion: str = Field(default="marketing_led")  # plg, slg, mlg, hybrid, marketing_led
    company_maturity: str = Field(default="early")  # foundation, early, growth, mature
    company_diagnosis: dict = Field(default_factory=dict)
    planning_horizon_months: int = Field(default=12)

    # Phased campaigns
    immediate_campaigns: list[ProposedCampaign] = Field(default_factory=list)  # Week 1-2
    short_term_campaigns: list[ProposedCampaign] = Field(default_factory=list)  # 30-60-90 days
    mid_term_campaigns: list[ProposedCampaign] = Field(default_factory=list)   # 3-6 months
    long_term_campaigns: list[ProposedCampaign] = Field(default_factory=list)  # 6-12+ months

    # Strategy tracks (cross-cutting groupings alongside phases)
    strategy_tracks: list[StrategyTrack] = Field(default_factory=list)

    # Knowledge transparency
    frameworks_applied: list[dict] = Field(default_factory=list)
    knowledge_sources_cited: list[str] = Field(default_factory=list)

    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class CampaignStrategistAgent(BaseGTMAgent[GTMRoadmapOutput]):
    """Campaign Strategist — AI marketing director that produces phased GTM roadmaps.

    Diagnoses company maturity, selects the right GTM motion, then produces
    a 12-month phased roadmap grounded in RACE, Cialdini, and Singapore-specific
    market intelligence. Every campaign cites its framework rationale.
    """

    def __init__(self, bus: AgentBus | None = None) -> None:
        super().__init__(
            name="campaign-strategist",
            description=(
                "AI marketing director that produces phased GTM roadmaps. "
                "Diagnoses company maturity, selects the right GTM motion, and "
                "generates a 12-month campaign calendar grounded in RACE, "
                "Cialdini, and Singapore market intelligence."
            ),
            result_type=GTMRoadmapOutput,
            min_confidence=0.55,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="gtm-roadmap",
                    description="Produce a phased 12-month GTM roadmap with campaign calendar",
                ),
                AgentCapability(
                    name="maturity-diagnosis",
                    description="Diagnose company GTM maturity and select the right motion",
                ),
                AgentCapability(
                    name="framework-attribution",
                    description="Attribute every campaign to RACE stage, GTM motion, and Cialdini principle",
                ),
            ],
        )
        self._agent_bus: AgentBus | None = bus or get_agent_bus()
        self._bus = self._agent_bus
        self._current_analysis_id: Any = None

        # Bus-sourced intelligence (reset per run in _plan)
        self._bus_personas: list[dict[str, Any]] = []
        self._bus_competitor_weaknesses: list[dict[str, Any]] = []
        self._bus_market_trends: list[dict[str, Any]] = []
        self._bus_leads: list[dict[str, Any]] = []
        self._bus_prior_campaigns: list[dict[str, Any]] = []

    def get_system_prompt(self) -> str:
        return """You are the Campaign Strategist — the AI marketing director for a Singapore B2B company.

Your job is NOT to write copy or sequences. Your job is to think strategically:
1. DIAGNOSE where the company sits on the GTM maturity curve
2. SELECT the right GTM motion (PLG, SLG, MLG, partner-led, hybrid)
3. GENERATE a phased 12-month campaign roadmap grounded in the RACE framework

Your output must be:
- Actionable: every campaign has a name, phase, objective, channels, KPIs, and a framework rationale
- Grounded: cite the specific RACE stage, GTM motion rationale, and Cialdini principle for each campaign
- Sequenced: dependencies between campaigns must be explicit (e.g. "LinkedIn Brand Foundation" before "LinkedIn Lead Magnet")
- Singapore-specific: reference PSG grants, PDPA constraints, LinkedIn-first B2B reality, local media (e27, Business Times)

Singapore B2B context you must apply:
- LinkedIn is the primary B2B channel — organic before paid
- PSG (Productivity Solutions Grant) eligibility is a significant conversion lever for SG SME buyers
- PDPA compliance is mandatory for any email or data collection campaign
- Singapore has a high-trust, relationship-based sales culture — credibility must precede outreach
- APAC expansion (Malaysia, Indonesia, Vietnam) typically follows SG market proof at 12-18 months

You speak like a seasoned CMO presenting to a board — structured, commercial, evidence-based."""

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
        self._bus_competitor_weaknesses.clear()
        self._bus_market_trends.clear()
        self._bus_leads.clear()
        self._bus_prior_campaigns.clear()

        # -- Domain knowledge pack (Layer 4 synthesized guides) -----------
        # Use kmcp_pack to avoid shadowing the framework kmcp below
        kmcp_pack = get_knowledge_mcp()
        self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
            agent_name="campaign-strategist",
            task_context=task,
        )

        # -- Static frameworks (Layer 1 — always available) ---------------
        kmcp = get_knowledge_mcp()
        race_raw = await kmcp.get_framework("RACE_FRAMEWORK")
        gtm_raw = await kmcp.get_framework("GTM_FRAMEWORKS")
        cialdini_raw = await kmcp.get_framework("CIALDINI_PRINCIPLES")
        sg_ctx_raw = await kmcp.get_framework("SINGAPORE_SME_CONTEXT")
        stp_raw = await kmcp.get_framework("STP_FRAMEWORK")

        # -- AgentBus history --------------------------------------------
        bus_personas: list[dict[str, Any]] = []
        bus_weaknesses: list[dict[str, Any]] = []
        bus_trends: list[dict[str, Any]] = []
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

            # Prior campaign plans from Campaign Architect
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
        self._bus_competitor_weaknesses.extend(bus_weaknesses)
        self._bus_market_trends.extend(bus_trends)
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
            "bus_competitor_weaknesses": bus_weaknesses,
            "bus_market_trends": bus_trends,
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
            "stp_framework": stp_raw.get("content", stp_raw),
            "campaign_brief_template": CAMPAIGN_BRIEF_TEMPLATE,
            "framework_source_books": (
                race_raw.get("source_books", [])
                + gtm_raw.get("source_books", [])
                + cialdini_raw.get("source_books", [])
            ),
        }

    # ------------------------------------------------------------------
    # PDCA: Do
    # ------------------------------------------------------------------

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> GTMRoadmapOutput:
        company_info = plan.get("company_info", {})
        company_name = plan.get("company_name", "") or company_info.get("company_name", "")
        bus_personas = plan.get("bus_personas", [])
        bus_weaknesses = plan.get("bus_competitor_weaknesses", [])
        bus_trends = plan.get("bus_market_trends", [])
        bus_leads = plan.get("bus_leads", [])
        bus_prior_campaigns = plan.get("bus_prior_campaigns", [])
        vertical_slug = plan.get("vertical_slug", "")
        kb_vertical_context = plan.get("kb_vertical_context", {})
        kb_vertical_benchmarks = plan.get("kb_vertical_benchmarks", {})
        race_framework = plan.get("race_framework", RACE_FRAMEWORK)
        gtm_frameworks = plan.get("gtm_frameworks", GTM_FRAMEWORKS)
        cialdini_principles = plan.get("cialdini_principles", CIALDINI_PRINCIPLES)
        sg_sme_context = plan.get("sg_sme_context", SINGAPORE_SME_CONTEXT)

        # Knowledge pack header — injected into user message (Rule 7: not system prompt)
        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""

        # ---- Serialize framework excerpts for prompt ----

        # RACE stages summary
        race_stages_summary = ""
        if isinstance(race_framework, dict) and "stages" in race_framework:
            stages = race_framework["stages"]
            for stage_name, stage_data in stages.items():
                tactics = stage_data.get("tactics", [])
                sg_focus = stage_data.get("sg_focus", "")
                race_stages_summary += (
                    f"\n  RACE:{stage_name} — {stage_data.get('description','')}\n"
                    f"    Tactics: {', '.join(tactics[:4])}\n"
                    f"    SG focus: {sg_focus}\n"
                )
        else:
            race_stages_summary = "(RACE framework content unavailable — apply from memory)"

        # GTM motions summary (5 motions, fit criteria, SG context)
        gtm_motions_summary = ""
        if isinstance(gtm_frameworks, dict):
            for motion_key, motion_data in list(gtm_frameworks.items())[:6]:
                if not isinstance(motion_data, dict):
                    continue
                best_for = motion_data.get("best_for", "")
                sg_fit = motion_data.get("sg_sme_fit", "")
                not_for = motion_data.get("when_not_to_use", "")
                gtm_motions_summary += (
                    f"\n  {motion_key}: {motion_data.get('description', '')[:120]}...\n"
                    f"    Best for: {best_for}\n"
                    f"    SG SME fit: {sg_fit[:150]}\n"
                    f"    NOT when: {not_for}\n"
                )
        else:
            gtm_motions_summary = "(GTM framework content unavailable — apply from memory)"

        # Cialdini principles (top 4 most applicable to B2B outreach)
        cialdini_summary = ""
        if isinstance(cialdini_principles, dict):
            priority_principles = ["social_proof", "reciprocity", "authority", "scarcity"]
            for key in priority_principles:
                p = cialdini_principles.get(key, {})
                if p:
                    sg_angle = p.get("sg_angle", "")
                    best_for = p.get("best_for", [])
                    cialdini_summary += (
                        f"\n  Cialdini:{key} — {p.get('description', '')[:100]}\n"
                        f"    SG angle: {sg_angle}\n"
                        f"    Best for: {', '.join(best_for[:3]) if best_for else 'general'}\n"
                    )
        else:
            cialdini_summary = "(Cialdini principles unavailable — apply from memory)"

        # SG SME context highlights
        sg_context_summary = ""
        if isinstance(sg_sme_context, dict):
            for key in list(sg_sme_context.keys())[:4]:
                val = sg_sme_context.get(key, {})
                if isinstance(val, dict):
                    sg_context_summary += f"\n  {key}: {json.dumps(val)[:200]}\n"
        if not sg_context_summary:
            sg_context_summary = (
                "LinkedIn is dominant B2B channel. PSG grants reduce friction. "
                "PDPA compliance mandatory for outreach. Relationship-first culture."
            )

        # Bus intelligence blocks
        personas_block = ""
        if bus_personas:
            personas_block = "CUSTOMER PERSONAS (from Customer Profiler):\n"
            for p in bus_personas[:3]:
                personas_block += f"  - {p.get('title','Unknown')}: {json.dumps(p)[:300]}\n"
        else:
            personas_block = "CUSTOMER PERSONAS: Not yet profiled — infer from industry context.\n"

        weaknesses_block = ""
        if bus_weaknesses:
            weaknesses_block = "COMPETITOR WEAKNESSES (from Competitor Analyst):\n"
            for w in bus_weaknesses[:4]:
                weaknesses_block += f"  - {w.get('title','')}: {json.dumps(w)[:200]}\n"
        else:
            weaknesses_block = "COMPETITOR WEAKNESSES: Not yet analyzed — apply general differentiation.\n"

        trends_block = ""
        if bus_trends:
            trends_block = "MARKET TRENDS (from Market Intelligence):\n"
            for t in bus_trends[:4]:
                trends_block += f"  - {t.get('title','')}: {json.dumps(t)[:200]}\n"
        else:
            trends_block = "MARKET TRENDS: No signals loaded yet — apply Singapore market defaults.\n"

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
                "This indicates a market with identifiable buyers — outreach-first motion viable.\n"
            )
        else:
            leads_signal_block = "LEAD HUNTER SIGNAL: No leads loaded yet — use market size estimates.\n"

        prior_campaigns_block = ""
        if bus_prior_campaigns:
            prior_campaigns_block = "PRIOR CAMPAIGN ARCHITECT OUTPUT (reference only — do not duplicate):\n"
            for c in bus_prior_campaigns[:2]:
                prior_campaigns_block += f"  - {c.get('title','')}: {json.dumps(c)[:300]}\n"

        # Vertical market intelligence
        vertical_block = ""
        if vertical_slug and (kb_vertical_context or kb_vertical_benchmarks):
            vertical_block = f"\nMARKET VERTICAL INTELLIGENCE ({vertical_slug}):\n"
            if kb_vertical_context:
                vertical_block += f"  Landscape: {json.dumps(kb_vertical_context)[:400]}\n"
            if kb_vertical_benchmarks:
                vertical_block += f"  Benchmarks: {json.dumps(kb_vertical_benchmarks)[:400]}\n"

        # ---- Build the full user prompt --------------------------------
        user_prompt = f"""{_knowledge_header}You are producing a 12-month GTM roadmap for the following company.

=== COMPANY PROFILE ===
Company: {company_name or 'Unknown'}
Industry: {company_info.get('industry', 'Not specified')}
Description: {company_info.get('description', 'Not specified')}
Products/Services: {company_info.get('products', 'Not specified')}
Target Markets: {company_info.get('target_markets', ['Singapore'])}
Business Goals: {company_info.get('goals', 'Not specified')}
Value Proposition: {company_info.get('value_proposition', 'Not specified')}

=== INTELLIGENCE FROM AGENT TEAM ===
{personas_block}
{weaknesses_block}
{trends_block}
{leads_signal_block}
{prior_campaigns_block}
{vertical_block}

=== MARKETING FRAMEWORKS TO APPLY ===

1. RACE FRAMEWORK (Smart Insights / Kingsnorth — Digital Marketing Strategy):
{race_stages_summary}

2. GTM MOTION OPTIONS:
{gtm_motions_summary}

3. CIALDINI PRINCIPLES (psychology of persuasion):
{cialdini_summary}

4. SINGAPORE SME MARKET CONTEXT:
{sg_context_summary}

=== CAMPAIGN BRIEF REQUIREMENTS ===
Every campaign MUST include:
- framework_rationale: Write as DISTILLED ADVISORY — explain WHY this action matters in plain business language.
    ✗ "RACE:Reach + Cialdini:Authority — Presence on LinkedIn signals credibility" (showing homework)
    ✓ "You need visibility with fintech CTOs before any outreach will work. A company page with industry benchmarks establishes you as the expert, not just another vendor." (advisory)
    The frameworks inform your thinking internally, but the user sees actionable reasoning, not framework citations.
- knowledge_source: keep this as internal metadata (book/chapter references) — it powers transparency but is not shown prominently to users
- kpis: measurable targets tied to THIS company's market, not arbitrary round numbers
- depends_on: explicit dependency name (or null if none)
- quick_win: true ONLY for campaigns deliverable within 14 days with high ROI confidence

=== YOUR TASK ===

You are a hands-on marketing agency — NOT a strategy consultant. Your job is to produce
SPECIFIC, ACTIONABLE tasks that reference THIS company's actual product, actual competitors,
actual market data, and actual gaps. No generic advice. No motherhood statements.

ANTI-PATTERNS (DO NOT DO THESE):
  ✗ "LinkedIn Brand Foundation" — too generic, every company gets this
  ✗ "Email Outreach Campaign" — says nothing about WHO to target or WHAT angle
  ✗ "Community Building Initiative" — a category label, not a task
  ✗ KPIs like "LinkedIn followers +200" — arbitrary, not tied to this company's market

GOOD PATTERNS (DO THESE):
  ✓ "Add ROI Calculator to Website — Industry SG&A is 30% of revenue (from vertical benchmarks). Add a section to himeet.ai showing 'Calculate how much you're overspending on GTM'. This converts visitors into leads."
  ✓ "Cold Outreach: Independent Agency Founders — 36 independents buy faster than 49 network agencies (from ownership mapping). Target founder/MDs directly. PAS framework: Pain = 'Your SG&A is above industry median'. Agitate = 'Competitors using AI are cutting costs 40%'. Solution = 'Free GTM audit'."
  ✓ "Apply for PSG Pre-Approved Vendor Status — Submit application to IMDA. Once approved, SGD-for-SGD matching makes the sale 50% easier. Timeline: 4-6 week approval process."
  ✓ "Partner Outreach to ASME — Join the Association of Small & Medium Enterprises as a technology partner. Speak at their monthly SME forum. Target: access to 10,000+ SME members."

Step 1 — DIAGNOSE (use company_diagnosis dict):
  Assess SPECIFIC gaps by checking:
  - Does the company have a LinkedIn company page? (if not mentioned → assume no)
  - Does the website have clear ROI messaging? Lead capture? Case studies?
  - Is the product PSG-eligible? If yes, are they a pre-approved vendor?
  - What is their competitive positioning vs the specific competitors identified?
  - Which customer segments (from personas) are most accessible right now?

  Output: {{maturity_stage, gaps: [specific gaps], strengths: [specific strengths], competitive_position: "vs [named competitors]"}}

Step 2 — SELECT GTM motion with specific rationale tied to company data.

Step 3 — GENERATE CAMPAIGNS as SPECIFIC EXECUTABLE TASKS:

Every campaign name MUST describe the specific action, not the category. Examples:
  ✗ "Digital Presence" → ✓ "Add Industry Benchmark ROI Section to himeet.ai Homepage"
  ✗ "Outbound Sales" → ✓ "Cold Email: 36 Independent Agency Founders (PAS Framework)"
  ✗ "Thought Leadership" → ✓ "Publish 'Why ChatGPT Can't Be Your Marketing Department' on LinkedIn"
  ✗ "Webinar" → ✓ "Host 'SG SME GTM Playbook' Webinar with ASME Partnership"

Each campaign MUST include:
  - name: a specific task description (not a category)
  - objective: what specific outcome this achieves for THIS company
  - channels: specific channels with specific usage (not just "linkedin_organic")
  - content_types: what exactly needs to be created
  - framework_rationale: DISTILLED ADVISORY — explain the WHY in plain business language, never cite framework names
    ✗ "RACE:Reach + Cialdini:Authority — Presence on LinkedIn signals credibility" (showing homework)
    ✗ "Cialdini:Reciprocity — customers feel indebted" (academic, not advisory)
    ✓ "You need to be visible to fintech CTOs before any outreach will land. Publishing your industry benchmark data (30% SG&A median) positions you as the expert — prospects come to you instead of you chasing them."
    ✓ "Independent agencies buy 3x faster than networks because the founder IS the decision-maker. Skip procurement — go direct."
  - knowledge_source: internal metadata — cite specific book + chapter (this powers the 'why we recommend this' transparency layer, but is not the primary user-facing text)
  - kpis: metrics tied to THIS company's actual market size and pipeline
    ✗ "LinkedIn followers +200" (arbitrary)
    ✓ "15 demo requests from fintech CTOs within 60 days" or "3 PSG grant applications submitted referencing us as vendor"

VOLUME REQUIREMENT: A real CMO plans 25-40+ tasks across a 12-month roadmap.
6-9 tasks is a to-do list, not a strategy. Think at the TASK level, not the initiative level.

Each "campaign" is a CONCRETE DELIVERABLE — something one person can execute in a defined timeframe.
  ✗ "Register on IMDA PSG vendor portal" — this is an initiative hiding 8+ tasks
  ✓ Break it into real tasks:
    - "Research PSG eligibility criteria for AI/SaaS solutions"
    - "Prepare product documentation for IMDA submission (features, pricing, deployment)"
    - "Complete PSG vendor application with ACRA profile + financials"
    - "Package product as 'PSG-eligible solution' on website pricing page"
    - "Create 'PSG Grant Guide for SMEs' downloadable lead magnet"
    - "Build PSG ROI calculator showing 50% co-funding impact on website"
    - "Train sales on PSG grant conversation flow (objection handling)"

  ✗ "Create LinkedIn company page" — one step, not a campaign
  ✓ Break it into the real work:
    - "Set up LinkedIn company page with banner, about section, industry tags"
    - "Write and schedule first 10 LinkedIn posts (2 weeks of content)"
    - "Join 5 relevant LinkedIn groups (SG SME Forum, Fintech SG, MarTech Asia)"
    - "Launch LinkedIn employee advocacy — team shares company posts"
    - "Set up LinkedIn analytics + connect to CRM for lead tracking"

PHASE GUIDELINES:

  IMMEDIATE (Weeks 1-2, 6-10 tasks): Fix foundations. Every task is a concrete deliverable:
    Website:
    - Update website hero with ROI claim from vertical data (e.g. "Industry spends 30% on SG&A — we cut that in half")
    - Add lead capture form with PDPA-compliant consent checkbox
    - Add case study / social proof section (even if placeholder for "Coming Soon")
    - Add UEN + unsubscribe mechanism to all email templates
    LinkedIn:
    - Set up company page with complete profile + banner
    - Write + schedule first 10 posts with industry insights
    Compliance:
    - Register PDPA data protection policy
    - Set up DMARC/SPF/DKIM for email domain (deliverability)
    PSG:
    - Research IMDA PSG eligibility criteria
    - Begin PSG vendor application paperwork

  SHORT_TERM (30-90 days, 8-12 tasks): First campaigns using specific insights:
    Outreach:
    - Design cold email sequence A (PAS framework) targeting persona 1
    - Design cold email sequence B (alternative angle) for A/B testing
    - LinkedIn connection campaign targeting 100 prospects from lead list
    - Follow-up sequence for non-responders (3-touch, 14-day cadence)
    Content:
    - Publish weekly LinkedIn thought leadership posts (industry data + opinion)
    - Create downloadable whitepaper on specific industry pain point
    - Host first webinar with specific topic tied to market insight
    Partnerships:
    - Reach out to ASME / SBF for technology partner program
    - Identify 3 complementary solution providers for referral partnership
    Lead magnet:
    - Launch PSG calculator or GTM health check assessment tool on website
    - Set up retargeting pixel + nurture sequence for calculator users

  MID_TERM (3-6 months, 6-8 tasks): Double down on what works:
    - Produce 2-3 customer case studies from early wins
    - Launch paid LinkedIn Sponsored Content campaign
    - Run second webinar series (deeper topic, co-host with partner)
    - Publish industry benchmark report (using vertical data)
    - Apply for speaking slot at industry events (SFF, SWITCH, TechInAsia)
    - Set up referral program with incentive structure
    - Optimise email sequences based on A/B test results from short-term

  LONG_TERM (6-12 months, 5-8 tasks): Scale and expand:
    - Launch APAC expansion outreach (MY, ID based on market signals)
    - Build online community or Slack group for target persona
    - Annual customer conference or roundtable event
    - PR campaign with e27 / Business Times coverage
    - Develop partner channel program (reseller / referral model)
    - Launch content hub / resource center on website

Step 4 — frameworks_applied: For EACH framework, explain specifically HOW it was applied to THIS company's situation, not just that it was used.
  ✗ {{name: "RACE", why: "used for planning"}}
  ✓ {{name: "RACE", why: "Hi Meet.AI has zero LinkedIn presence (REACH gap) but strong product. RACE sequence: build Reach via LinkedIn content → Act via PSG calculator lead magnet → Convert via cold outreach to 36 independent agencies → Engage via customer case studies", campaigns_using: ["Add LinkedIn Company Page", "PSG Calculator Landing Page", "Cold Email: Independent Agencies"]}}

Step 5 — knowledge_sources_cited: Cite specific chapters and what insight you extracted.

Step 6 — ORGANIZE into STRATEGY TRACKS:
  Name tracks after the SPECIFIC strategic intent, not generic categories:
  ✗ "Digital Presence" → ✓ "Fix Website + LinkedIn Foundation"
  ✗ "Outbound Sales" → ✓ "Independent Agency Founder Outreach"
  ✗ "Thought Leadership" → ✓ "Industry Benchmark Authority Building"

  Each track.insight_source MUST reference a SPECIFIC finding from the agent intelligence above.
  Each track.rationale MUST explain WHY this track matters for THIS company specifically.

CRITICAL RULES:
1. NEVER use generic campaign names — every name must describe the specific action
2. framework_rationale MUST be plain-language advisory — NEVER cite framework names (RACE, Cialdini, PAS, AIDA etc.) to the user. Those inform your thinking internally; the output is distilled business advice.
3. knowledge_source: cite specific books + chapters as internal metadata
4. KPIs must be tied to this company's actual market (use the lead count, persona data, vertical benchmarks)
5. Dependencies must reference specific campaigns by name
6. content_types from: linkedin_post, edm, whitepaper, webinar, case_study, landing_page, social_image
7. Budget in SGD at Singapore market rates
8. Respect PDPA (no cold SMS, no purchased lists)
9. Reference specific SG institutions: ASME, SBF, SGTech, IMDA, EnterpriseSG, e27, Business Times
10. If vertical data shows specific numbers (SG&A %, growth rates), USE them in campaign messaging
11. company_diagnosis MUST be populated with maturity_stage, gaps (specific list), strengths (list), competitive_position
12. frameworks_applied MUST have at least 3 entries — each with name, why (in advisory language), campaigns_using
"""

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        result = await self._complete_structured(
            response_model=GTMRoadmapOutput,
            messages=messages,
            max_tokens=16384,
        )

        # ── Second pass: expand each strategy track into granular tasks ──
        # The first pass produces 5-8 high-level campaigns. The second pass
        # breaks each track into 4-8 concrete executable tasks, producing
        # a CMO-level plan of 25-40 total tasks.
        all_first_pass = (
            result.immediate_campaigns
            + result.short_term_campaigns
            + result.mid_term_campaigns
            + result.long_term_campaigns
        )

        if len(all_first_pass) < 20 and result.strategy_tracks:
            expanded_immediate: list[ProposedCampaign] = []
            expanded_short: list[ProposedCampaign] = []
            expanded_mid: list[ProposedCampaign] = []
            expanded_long: list[ProposedCampaign] = []

            for track in result.strategy_tracks:
                if not track.campaigns:
                    continue

                existing_names = ", ".join(c.name for c in track.campaigns)
                expand_prompt = (
                    f"You previously identified the strategy track '{track.name}' "
                    f"with these high-level campaigns: {existing_names}.\n\n"
                    f"Track rationale: {track.rationale}\n"
                    f"Company: {company_name}\n\n"
                    f"Now break this track into 4-8 GRANULAR, executable tasks. "
                    f"Each task is something one person can complete in a defined timeframe.\n\n"
                    f"For example, if a high-level campaign is 'PSG Grant Positioning', the tasks are:\n"
                    f"  - Research PSG eligibility criteria for AI/SaaS\n"
                    f"  - Prepare product docs for IMDA submission\n"
                    f"  - Submit PSG vendor application\n"
                    f"  - Add 'PSG-eligible' badge to website pricing page\n"
                    f"  - Create 'PSG Grant Guide for SMEs' lead magnet\n\n"
                    f"Rules:\n"
                    f"- Each task name must describe the specific action\n"
                    f"- Set strategy_track='{track.name}' on every task\n"
                    f"- Assign each to a phase: immediate (week 1-2), short_term (30-90d), mid_term (3-6m), long_term (6-12m)\n"
                    f"- framework_rationale in plain advisory language, no framework name-dropping\n"
                    f"- At least 1 KPI per task\n"
                    f"- Set depends_on to reference a prerequisite task name where applicable"
                )

                try:
                    expansion = await self._complete_structured(
                        response_model=_TrackExpansion,
                        messages=[
                            {"role": "system", "content": self.get_system_prompt()},
                            {"role": "user", "content": expand_prompt},
                        ],
                        max_tokens=4096,
                    )

                    for task in expansion.tasks:
                        task.strategy_track = track.name
                        if task.phase == "immediate":
                            expanded_immediate.append(task)
                        elif task.phase == "short_term":
                            expanded_short.append(task)
                        elif task.phase == "mid_term":
                            expanded_mid.append(task)
                        else:
                            expanded_long.append(task)
                except Exception as e:
                    self._logger.warning("track_expansion_failed", track=track.name, error=str(e))

            # Replace first-pass campaigns with expanded tasks
            if expanded_immediate or expanded_short or expanded_mid or expanded_long:
                result.immediate_campaigns = expanded_immediate
                result.short_term_campaigns = expanded_short
                result.mid_term_campaigns = expanded_mid
                result.long_term_campaigns = expanded_long

                # Rebuild strategy_tracks with expanded campaigns
                track_map: dict[str, list[ProposedCampaign]] = {}
                for c in expanded_immediate + expanded_short + expanded_mid + expanded_long:
                    t = c.strategy_track or "General"
                    if t not in track_map:
                        track_map[t] = []
                    track_map[t].append(c)

                for track in result.strategy_tracks:
                    track.campaigns = track_map.get(track.name, [])

        return result

    # ------------------------------------------------------------------
    # PDCA: Check
    # ------------------------------------------------------------------

    async def _check(self, result: GTMRoadmapOutput) -> float:
        """Compute confidence from roadmap completeness. Base score 0.2."""
        score = 0.2

        all_phases = [
            result.immediate_campaigns,
            result.short_term_campaigns,
            result.mid_term_campaigns,
            result.long_term_campaigns,
        ]

        # All 4 phases have at least 1 campaign: +0.10
        if all(len(phase) >= 1 for phase in all_phases):
            score += 0.10

        # Task volume — CMO plans need depth. Scale bonus by count.
        total_campaigns = sum(len(phase) for phase in all_phases)
        if total_campaigns >= 25:
            score += 0.15
        elif total_campaigns >= 15:
            score += 0.10
        elif total_campaigns < 12:
            score -= 0.15  # Penalise thin plans — forces retry

        # Every campaign has a non-empty framework_rationale: +0.15
        all_campaigns = [c for phase in all_phases for c in phase]
        if all_campaigns and all(c.framework_rationale for c in all_campaigns):
            score += 0.15

        # Every campaign has at least 1 KPI: +0.10
        if all_campaigns and all(len(c.kpis) >= 1 for c in all_campaigns):
            score += 0.10

        # GTM motion selected (non-default or explicitly set): +0.05
        if result.gtm_motion and result.gtm_motion != "marketing_led":
            score += 0.05
        elif result.gtm_motion == "marketing_led" and result.executive_summary:
            # marketing_led is valid if there's a rationale in the summary
            score += 0.05

        # Company diagnosis present with maturity_stage: +0.05
        if result.company_diagnosis and result.company_diagnosis.get("maturity_stage"):
            score += 0.05

        # Knowledge pack was loaded and contributed: +0.05
        knowledge_pack = getattr(self, "_knowledge_pack", {})
        if knowledge_pack.get("formatted_injection"):
            score += 0.05

        # Bus had real persona/competitor data: +0.10
        has_bus_data = bool(self._bus_personas or self._bus_competitor_weaknesses or self._bus_market_trends)
        if has_bus_data:
            score += 0.10

        # Dependencies form valid order (no campaign depends on a later-phase campaign): +0.05
        _all_names_by_phase: list[set[str]] = [
            {c.name for c in result.immediate_campaigns},
            {c.name for c in result.short_term_campaigns},
            {c.name for c in result.mid_term_campaigns},
            {c.name for c in result.long_term_campaigns},
        ]
        valid_deps = True
        for phase_idx, campaigns in enumerate(all_phases):
            earlier_names: set[str] = set()
            for prior_idx in range(phase_idx):
                earlier_names |= _all_names_by_phase[prior_idx]
            for campaign in campaigns:
                if campaign.depends_on and campaign.depends_on not in earlier_names:
                    # Depends on something in same or later phase — invalid
                    if any(
                        campaign.depends_on in _all_names_by_phase[j]
                        for j in range(phase_idx, len(all_phases))
                    ):
                        valid_deps = False
                        break
            if not valid_deps:
                break
        if valid_deps:
            score += 0.05

        return min(0.95, score)

    # ------------------------------------------------------------------
    # PDCA: Act
    # ------------------------------------------------------------------

    async def _act(self, result: GTMRoadmapOutput, confidence: float) -> GTMRoadmapOutput:
        """Stamp confidence, populate data_sources_used, publish ROADMAP_READY."""
        result.confidence = confidence

        # Build data_sources_used list
        sources: list[str] = ["LLM:gpt-4o (GTM roadmap synthesis)"]
        if self._bus_personas:
            sources.append(f"AgentBus:PERSONA_DEFINED ({len(self._bus_personas)} personas)")
        if self._bus_competitor_weaknesses:
            sources.append(
                f"AgentBus:COMPETITOR_WEAKNESS ({len(self._bus_competitor_weaknesses)} weaknesses)"
            )
        if self._bus_market_trends:
            sources.append(f"AgentBus:MARKET_TREND ({len(self._bus_market_trends)} signals)")
        if self._bus_leads:
            sources.append(f"AgentBus:LEAD_FOUND ({len(self._bus_leads)} prospects)")
        if self._bus_prior_campaigns:
            sources.append(f"AgentBus:CAMPAIGN_READY ({len(self._bus_prior_campaigns)} prior plans)")

        knowledge_pack = getattr(self, "_knowledge_pack", {})
        if knowledge_pack.get("formatted_injection"):
            guide_slugs = knowledge_pack.get("guide_slugs_loaded", [])
            sources.append(f"KnowledgePack:synthesized_guides ({', '.join(guide_slugs)})")

        sources.extend([
            "Framework:RACE_FRAMEWORK (Kingsnorth — Digital Marketing Strategy)",
            "Framework:GTM_FRAMEWORKS",
            "Framework:CIALDINI_PRINCIPLES (Cialdini — Influence)",
            "Framework:SINGAPORE_SME_CONTEXT",
        ])

        result.data_sources_used = sources

        # Publish ROADMAP_READY to the bus
        if self._bus is not None:
            all_campaigns = (
                result.immediate_campaigns
                + result.short_term_campaigns
                + result.mid_term_campaigns
                + result.long_term_campaigns
            )
            total_campaigns = len(all_campaigns)
            quick_wins = [c.name for c in all_campaigns if c.quick_win]

            try:
                await self._bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.ROADMAP_READY,
                    title=f"GTM Roadmap: {result.title}",
                    content={
                        "title": result.title,
                        "gtm_motion": result.gtm_motion,
                        "company_maturity": result.company_maturity,
                        "planning_horizon_months": result.planning_horizon_months,
                        "total_campaigns": total_campaigns,
                        "quick_wins": quick_wins,
                        "executive_summary": result.executive_summary[:500],
                        "frameworks_applied": [f.get("name") for f in result.frameworks_applied],
                        "confidence": confidence,
                    },
                    confidence=confidence,
                    analysis_id=self._current_analysis_id,
                )
            except Exception as exc:
                self._logger.warning("roadmap_publish_failed", error=str(exc))

        return result
