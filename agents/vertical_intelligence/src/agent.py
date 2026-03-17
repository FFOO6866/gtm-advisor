"""Vertical Intelligence Agent — deep industry expertise for GTM advisory.

Produces comprehensive vertical intelligence by combining:
- VerticalIntelligenceReport (weekly synthesized data)
- VerticalBenchmark percentile distributions (financial, GTM spend, R&D)
- Company trajectories (leaders, movers, laggards)
- GTM profiles (SG&A intensity, ESG, analyst consensus)
- Live market signals and news
- Regulatory/grant environment from SG knowledge base
- LLM synthesis for narrative and actionable implications

The agent is the single authority on "what's happening in this industry"
for the rest of the GTM advisory team.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, DiscoveryType, get_agent_bus
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.integrations.newsapi.src import get_newsapi_client
from packages.intelligence.src.vertical_ecosystem import get_vertical_ecosystem
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.llm.src import get_llm_manager
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer

# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


class IndustryDriver(BaseModel):
    """A key driver or headwind shaping the industry."""

    name: str = Field(..., description="Driver name (e.g. 'AI adoption wave')")
    direction: str = Field(..., description="'tailwind' or 'headwind'")
    magnitude: str = Field(..., description="'strong', 'moderate', or 'emerging'")
    description: str = Field(..., description="Evidence-backed explanation")
    gtm_implication: str = Field(..., description="What this means for selling into the vertical")


class CompetitorProfile(BaseModel):
    """A notable player in the vertical."""

    name: str = Field(...)
    ticker: str | None = Field(default=None)
    role: str = Field(..., description="'leader', 'challenger', 'new_entrant', 'laggard', 'niche'")
    market_cap_sgd: float | None = Field(default=None)
    revenue_growth_yoy: float | None = Field(default=None)
    sga_to_revenue: float | None = Field(default=None)
    trajectory: str | None = Field(default=None, description="'accelerating', 'stable', 'decelerating'")
    notable: str = Field(..., description="What makes this player worth watching")


class FinancialBenchmarkSummary(BaseModel):
    """Summarised benchmark distributions for the vertical."""

    period: str = Field(...)
    company_count: int = Field(default=0)
    revenue_growth_median: float | None = Field(default=None)
    gross_margin_median: float | None = Field(default=None)
    sga_to_revenue_median: float | None = Field(default=None)
    rnd_to_revenue_median: float | None = Field(default=None)
    operating_margin_median: float | None = Field(default=None)
    capex_to_revenue_median: float | None = Field(default=None)


class MarketForces(BaseModel):
    """Porter's Five Forces assessment for the vertical."""

    buyer_power: str = Field(..., description="Assessment with evidence")
    supplier_power: str = Field(...)
    threat_of_new_entrants: str = Field(...)
    threat_of_substitutes: str = Field(...)
    competitive_rivalry: str = Field(...)


class VerticalIntelligenceOutput(BaseModel):
    """Comprehensive vertical intelligence report."""

    vertical_slug: str = Field(...)
    vertical_name: str = Field(...)
    report_period: str = Field(default="")

    # Executive summary
    executive_summary: str = Field(..., description="2-3 paragraph industry overview")

    # Market structure
    total_companies_tracked: int = Field(default=0)
    total_market_cap_sgd: float = Field(default=0)

    # Key drivers and headwinds
    drivers: list[IndustryDriver] = Field(default_factory=list)

    # Financial performance
    benchmarks: FinancialBenchmarkSummary | None = Field(default=None)
    benchmark_history: list[FinancialBenchmarkSummary] = Field(
        default_factory=list, description="All available benchmark periods for trend analysis"
    )
    trend_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Pre-computed YoY trends from multi-period data"
    )
    performance_narrative: str = Field(default="", description="Plain-English interpretation of benchmarks")

    # Competitive landscape
    leaders: list[CompetitorProfile] = Field(default_factory=list)
    challengers: list[CompetitorProfile] = Field(default_factory=list)
    new_entrants: list[CompetitorProfile] = Field(default_factory=list)
    laggards: list[CompetitorProfile] = Field(default_factory=list)

    # Market forces
    market_forces: MarketForces | None = Field(default=None)

    # Trends and signals
    trends: list[dict[str, Any]] = Field(default_factory=list)
    recent_signals: list[dict[str, Any]] = Field(default_factory=list)

    # Executive movements
    executive_movements: list[dict[str, Any]] = Field(default_factory=list)

    # Industry structure (SG-specific)
    holding_group_map: dict[str, Any] = Field(
        default_factory=dict, description="Holding group → subsidiary agencies mapping"
    )
    sg_agency_landscape: list[dict[str, Any]] = Field(
        default_factory=list, description="SG agencies with parent group, services, awards"
    )
    award_leaderboard: list[dict[str, Any]] = Field(
        default_factory=list, description="Agencies ranked by award wins"
    )
    service_line_distribution: dict[str, Any] = Field(
        default_factory=dict, description="Service line → agency count and list"
    )

    # Regulatory and grant environment
    regulatory_environment: list[dict[str, Any]] = Field(default_factory=list)

    # GTM implications — the money section
    gtm_implications: list[dict[str, str]] = Field(default_factory=list)

    # Metadata
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class VerticalIntelligenceAgent(BaseGTMAgent[VerticalIntelligenceOutput]):
    """Deep industry intelligence agent.

    Knows the inside-out of each vertical: key drivers, performance
    benchmarks, competitive landscape (leaders, laggards, new entrants,
    movers), market forces, trends, regulatory environment, and
    GTM implications.
    """

    def __init__(self, agent_bus: AgentBus | None = None) -> None:
        super().__init__(
            name="vertical-intelligence",
            description=(
                "Provides deep industry intelligence by synthesising financial "
                "benchmarks, company trajectories, competitive dynamics, market "
                "signals, and regulatory data into actionable vertical insights."
            ),
            result_type=VerticalIntelligenceOutput,
            min_confidence=0.70,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="industry-analysis",
                    description="Deep analysis of industry structure and dynamics",
                ),
                AgentCapability(
                    name="competitive-landscape",
                    description="Map leaders, challengers, new entrants, laggards",
                ),
                AgentCapability(
                    name="benchmark-interpretation",
                    description="Interpret financial benchmarks for GTM strategy",
                ),
                AgentCapability(
                    name="market-forces",
                    description="Porter's Five Forces industry assessment",
                ),
            ],
        )
        self._newsapi = get_newsapi_client()
        self._perplexity = get_llm_manager().perplexity
        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id: Any = None
        self._vertical_slug: str = ""

        # Data quality flags for _check()
        self._has_vertical_intel = False
        self._has_benchmarks = False
        self._has_trajectories = False
        self._has_multi_period = False
        self._has_live_news = False
        self._has_research = False
        self._has_kb_framework = False

    def get_system_prompt(self) -> str:
        return """You are the Vertical Intelligence Agent — producing consulting-grade industry analysis comparable to Gartner, Forrester, McKinsey, and BCG industry reports.

Your mission: produce a comprehensive, data-driven intelligence report that enables the sales team to walk into any meeting with prospects in this vertical and demonstrate deep industry knowledge. The output must be specific enough that a senior industry analyst would recognise it as accurate and actionable.

You must cover:
1. EXECUTIVE SUMMARY — Open with market size and structure. State the headline performance metric and its YoY direction. Identify the dominant cycle (growth, efficiency, or transformation). Name specific companies with specific numbers.
2. KEY DRIVERS (minimum 5) — Forces shaping the vertical. Each MUST be specific to THIS industry with data evidence (not generic "digital transformation" that applies to every vertical). Cite numbers.
3. PERFORMANCE BENCHMARKS — Interpret multi-period financial data. Show YoY trends: "Revenue growth shifted from X% (2023) to Y% (2024)". Explain what SG&A trends, margin compression/expansion, and R&D intensity signal about industry spending behaviour.
4. COMPETITIVE LANDSCAPE — Classify ALL companies from the data. For each, cite specific financials and explain WHY they matter for GTM strategy (not just "large market cap").
5. MARKET FORCES — Porter's Five Forces grounded in the data. Each force must cite at least 2 data points (e.g., "Buyer power is HIGH — 69 companies compete on thin margins (P50 operating margin 18.6%), P25-P75 spread of only 8pp indicates commoditised pricing").
6. TRENDS & SIGNALS — What's emerging from key_trends, signal_digest, and news? What signals should the sales team watch?
7. GTM IMPLICATIONS (minimum 5) — The most important section. Each must be data-backed, name a specific buyer persona or budget line, and include a concrete tactic.

Quality standards:
- NEVER make up financial data. Use only the numbers provided in the data context.
- Every claim must be traceable to a specific number in the data context.
- Interpret percentiles: P50 is median, P75 is top quartile, P25 is bottom quartile. P25-P75 spread indicates industry dispersion.
- SG&A is a proxy for GTM investment intensity. Rising SG&A = companies investing in growth. Falling SG&A = cost-cutting cycle.
- R&D intensity > 10% signals IP-heavy model (sell IP protection, compliance, licensing tools). < 3% signals commoditised/service delivery (sell efficiency and automation).
- When margin is compressing while SG&A rises: companies are buying growth (TAM expansion). When margin compresses while SG&A falls: defensive (price war or cost-cutting).
- Revenue growth > 15% median = high-growth vertical. < 0% = declining. 0-15% = moderate.
- When margins are compressing, companies need efficiency tools (pain-based selling).
- Always connect analysis back to actionable GTM strategy with specific tactics.
- For Singapore context: reference specific regulators (MAS, IMDA, HSA, EMA, ASAS, PDPC) not just generic PDPA. Reference specific grants (PSG, EDG, MRA) with eligibility criteria.
- Distinguish between segments within the vertical (e.g., in marketing_comms: creative agencies vs media agencies vs PR firms vs digital performance vs experiential; in fintech: digital payments vs wealth tech vs insurtech vs digital banking).

Data sparsity rules:
- If a benchmark has < 10 companies, state: "Caution: Limited sample (N=X). Insights are directional, not conclusive."
- If only 1 benchmark period exists, say "Single-period snapshot — YoY trends unavailable" rather than extrapolating.
- If SG agency landscape data is present, ALWAYS include a dedicated section on SG competitive positioning.
- If ecosystem data mentions industry events/conferences, reference them for campaign timing.

Industry structure requirements:
- If a Holding Group Ownership Map is present, your executive summary MUST reference the top holding groups by name (e.g. "WPP, Omnicom, Publicis, Dentsu dominate with N subsidiaries..."). This is critical industry context.
- If an Award Leaderboard is present, name the award-winning agencies and their parent groups.
- If a Service Line Distribution is present, describe the competitive landscape in terms of service specializations (e.g. "75 agencies compete in creative, 37 in PR, 28 in social").
- The holding_group_map, sg_agency_landscape, award_leaderboard, and service_line_distribution fields MUST be populated from the data context — these are deterministic, not LLM-generated.

Buyer cycle guidance:
- For each GTM implication, identify: the budget owner (CFO for cost-savings, CTO for innovation, CMO for brand, GC for compliance), approximate buy cycle length, and budget reset trigger.
- Reference industry events (Cannes Lions in June, Spikes Asia in March, Campaign AOY in December) as campaign timing signals."""

    # ------------------------------------------------------------------
    # PDCA: Plan
    # ------------------------------------------------------------------

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan vertical intelligence gathering."""
        context = context or {}

        # Load domain knowledge pack
        kmcp = get_knowledge_mcp()
        self._knowledge_pack = await kmcp.get_agent_knowledge_pack(
            agent_name="vertical-intelligence",
            task_context=task,
        )

        self._analysis_id = context.get("analysis_id")

        # Determine vertical slug — from explicit context or auto-detect
        vertical_slug = context.get("vertical_slug") or detect_vertical_slug(task) or "ict_saas"
        self._vertical_slug = vertical_slug

        # Load vertical ecosystem (associations, publications, events, etc.)
        self._ecosystem = get_vertical_ecosystem(vertical_slug)

        industry = context.get("industry", vertical_slug)
        region = context.get("region", "Singapore")

        data_sources = ["mcp", "newsapi", "perplexity"]
        if self._ecosystem:
            data_sources.append("ecosystem")

        return {
            "vertical_slug": vertical_slug,
            "industry": industry,
            "region": region,
            "data_sources": data_sources,
            "has_ecosystem": self._ecosystem is not None,
        }

    # ------------------------------------------------------------------
    # PDCA: Do
    # ------------------------------------------------------------------

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> VerticalIntelligenceOutput:
        """Execute deep vertical intelligence gathering."""
        context = context or {}
        vertical_slug = plan["vertical_slug"]
        industry = plan.get("industry", vertical_slug)
        region = plan.get("region", "Singapore")

        # -- Phase 1: DB-backed MCP data (sequential on shared session) --
        mcp_data = await self._fetch_mcp_data(vertical_slug)

        # -- Phase 2: Live external data (parallel — independent APIs) --
        live_data = await self._fetch_live_data(industry, region)

        # -- Phase 3: Knowledge frameworks --
        kb_framework = await self._fetch_frameworks()

        # -- Phase 4: LLM synthesis --
        return await self._synthesize(
            vertical_slug, mcp_data, live_data, kb_framework
        )

    # Benchmark periods available in DB (annual + quarterly)
    _BENCHMARK_PERIODS = ["2024", "2023", "2025-Q3", "2024-Q3"]

    async def _fetch_mcp_data(self, vertical_slug: str) -> dict[str, Any]:
        """Fetch all structured data from MarketIntelMCPServer.

        Key design decisions for consulting-grade output:
        1. Fetch ALL benchmark periods for YoY trend analysis (not just latest)
        2. Use competitive_dynamics from vertical_intel for company selection
           (market-cap leaders, not growth-sorted landscape leaders)
        3. Profile up to 20 companies across all competitive roles
        """
        data: dict[str, Any] = {
            "landscape": {},
            "benchmark_history": [],  # all periods for trend analysis
            "vertical_intel": {},
            "company_profiles": {},   # keyed by role: leaders/movers_up/movers_down/gtm_investors
            "company_trajectories": {},
        }

        try:
            async with async_session_factory() as db:
                mcp = MarketIntelMCPServer(session=db)

                # Core vertical data
                data["landscape"] = await mcp.get_vertical_landscape(vertical_slug)
                data["vertical_intel"] = await mcp.get_vertical_intelligence(vertical_slug)

                # Fetch ALL benchmark periods for YoY trend analysis
                for period in self._BENCHMARK_PERIODS:
                    bm = await mcp.get_vertical_benchmarks(vertical_slug, period_label=period)
                    if bm:
                        data["benchmark_history"].append(bm)

                # If no period-specific benchmarks found, fall back to latest
                if not data["benchmark_history"]:
                    bm = await mcp.get_vertical_benchmarks(vertical_slug)
                    if bm:
                        data["benchmark_history"].append(bm)

                # Extract competitive dynamics from vertical_intel report
                # (market-cap-ranked, not growth-ranked like landscape.leaders)
                vi = data["vertical_intel"]
                comp_dyn = vi.get("competitive_dynamics") or {}
                role_lists = {
                    "leaders": comp_dyn.get("leaders") or [],
                    "movers_up": comp_dyn.get("movers_up") or [],
                    "movers_down": comp_dyn.get("movers_down") or [],
                    "gtm_investors": comp_dyn.get("gtm_investors") or [],
                }

                # If competitive_dynamics is empty, fall back to landscape leaders
                total_cd = sum(len(v) for v in role_lists.values())
                if total_cd == 0:
                    ls_leaders = data["landscape"].get("leaders") or []
                    role_lists["leaders"] = ls_leaders[:5]

                # Profile companies across all roles (up to 20)
                seen_tickers: set[str] = set()
                for role, companies in role_lists.items():
                    data["company_profiles"][role] = []
                    data["company_trajectories"][role] = []
                    for company in companies[:5]:
                        ticker = company.get("ticker")
                        if not ticker or ticker in seen_tickers:
                            continue
                        seen_tickers.add(ticker)
                        for exchange in ("SG", "US"):
                            try:
                                profile = await mcp.get_company_gtm_profile(ticker, exchange)
                                if profile and not profile.get("error"):
                                    profile["company_name"] = company.get("name", ticker)
                                    profile["competitive_role"] = role
                                    data["company_profiles"][role].append(profile)

                                    traj = await mcp.get_company_trajectory(ticker, exchange)
                                    if traj and not traj.get("error"):
                                        traj["company_name"] = company.get("name", ticker)
                                        data["company_trajectories"][role].append(traj)
                                    break
                            except Exception:
                                self._logger.debug(
                                    "company_profile_failed",
                                    ticker=ticker,
                                    exchange=exchange,
                                    role=role,
                                )

        except Exception as e:
            self._logger.warning("mcp_fetch_failed", vertical=vertical_slug, error=str(e))

        self._has_vertical_intel = bool(data["vertical_intel"])
        self._has_benchmarks = bool(data["benchmark_history"])
        self._has_trajectories = any(
            bool(v) for v in data.get("company_trajectories", {}).values()
        )
        self._has_multi_period = len(data["benchmark_history"]) >= 2
        return data

    async def _fetch_live_data(self, industry: str, region: str) -> dict[str, Any]:
        """Fetch live data from external APIs (parallel)."""
        data: dict[str, Any] = {"news": [], "research": ""}

        async def _news() -> list[dict]:
            if not self._newsapi.is_configured:
                return []
            try:
                async with asyncio.timeout(20):
                    result = await self._newsapi.search_market_news(
                        industry=industry, region=region, days_back=14
                    )
                    return [
                        {
                            "title": a.title,
                            "description": a.description or "",
                            "source": a.source_name,
                            "date": a.published_at.isoformat(),
                        }
                        for a in result.articles[:10]
                    ]
            except Exception as e:
                self._logger.debug("newsapi_failed", error=str(e))
                return []

        async def _research() -> str:
            if not self._perplexity.is_configured:
                return ""
            try:
                year = datetime.now().year
                async with asyncio.timeout(25):
                    resp = await self._perplexity.research_market_with_citations(
                        topic=f"{industry} industry analysis Singapore APAC {year}",
                        region=region,
                    )
                    return resp.text if resp else ""
            except Exception as e:
                self._logger.debug("perplexity_failed", error=str(e))
                return ""

        news_result, research_result = await asyncio.gather(_news(), _research())
        data["news"] = news_result
        data["research"] = research_result

        self._has_live_news = bool(news_result)
        self._has_research = bool(research_result)
        return data

    async def _fetch_frameworks(self) -> str:
        """Load analytical frameworks from knowledge base."""
        try:
            kmcp = get_knowledge_mcp()
            porter = await kmcp.get_framework("PORTER_FIVE_FORCES")
            forces = list(((porter.get("content") or {}).get("forces") or {}).keys())
            if forces:
                self._has_kb_framework = True
                return f"Apply Porter's Five Forces: {', '.join(forces[:5])}"
        except Exception:
            pass
        return ""

    def _build_benchmark_summary(self, bm: dict[str, Any]) -> FinancialBenchmarkSummary:
        """Build a FinancialBenchmarkSummary from raw MCP benchmark data."""
        dist = bm.get("distributions") or {}
        return FinancialBenchmarkSummary(
            period=bm.get("period_label", ""),
            company_count=bm.get("company_count", 0),
            revenue_growth_median=(dist.get("revenue_growth_yoy") or {}).get("p50"),
            gross_margin_median=(dist.get("gross_margin") or {}).get("p50"),
            sga_to_revenue_median=(dist.get("sga_to_revenue") or {}).get("p50"),
            rnd_to_revenue_median=(dist.get("rnd_to_revenue") or {}).get("p50"),
            operating_margin_median=(dist.get("operating_margin") or {}).get("p50"),
            capex_to_revenue_median=(dist.get("capex_to_revenue") or {}).get("p50"),
        )

    def _compute_trend_analysis(
        self,
        benchmark_history: list[dict[str, Any]],
        financial_pulse: dict[str, Any],
    ) -> dict[str, Any]:
        """Pre-compute YoY trends from multi-period benchmarks + financial_pulse.

        Returns a structured dict the LLM can reference for trend narrative.
        """
        trends: dict[str, Any] = {}

        # Financial pulse trends (from vertical_intel report)
        if financial_pulse:
            trends["sga_trend"] = financial_pulse.get("sga_trend", "")
            trends["sga_trend_pct"] = financial_pulse.get("sga_trend_pct")
            trends["margin_trend"] = financial_pulse.get("margin_trend", "")
            trends["revenue_growth_trend"] = financial_pulse.get("revenue_growth_trend", "")

        # Compute YoY benchmark deltas from multi-period data
        # Sort by period: annual descending, quarterly descending
        annuals = sorted(
            [b for b in benchmark_history if b.get("period_type") == "annual"],
            key=lambda b: b.get("period_label", ""),
            reverse=True,
        )
        quarterlies = sorted(
            [b for b in benchmark_history if b.get("period_type") == "quarterly"],
            key=lambda b: b.get("period_label", ""),
            reverse=True,
        )

        metrics = [
            "revenue_growth_yoy", "gross_margin", "sga_to_revenue",
            "rnd_to_revenue", "operating_margin",
        ]

        def _extract_medians(bm_list: list[dict]) -> list[dict]:
            result = []
            for bm in bm_list:
                dist = bm.get("distributions") or {}
                row = {"period": bm.get("period_label", "")}
                for m in metrics:
                    row[m] = (dist.get(m) or {}).get("p50")
                result.append(row)
            return result

        if len(annuals) >= 2:
            trends["annual_medians"] = _extract_medians(annuals)
            # Compute deltas between most recent and prior year
            latest, prior = annuals[0], annuals[1]
            deltas = {}
            latest_dist = latest.get("distributions") or {}
            prior_dist = prior.get("distributions") or {}
            for m in metrics:
                lv = (latest_dist.get(m) or {}).get("p50")
                pv = (prior_dist.get(m) or {}).get("p50")
                if lv is not None and pv is not None:
                    deltas[m] = round(lv - pv, 4)
            trends["annual_yoy_deltas"] = deltas
            trends["annual_periods_compared"] = f"{latest.get('period_label')} vs {prior.get('period_label')}"

        if len(quarterlies) >= 2:
            trends["quarterly_medians"] = _extract_medians(quarterlies)
            latest_q, prior_q = quarterlies[0], quarterlies[1]
            qdeltas = {}
            latest_qd = latest_q.get("distributions") or {}
            prior_qd = prior_q.get("distributions") or {}
            for m in metrics:
                lv = (latest_qd.get(m) or {}).get("p50")
                pv = (prior_qd.get(m) or {}).get("p50")
                if lv is not None and pv is not None:
                    qdeltas[m] = round(lv - pv, 4)
            trends["quarterly_qoq_deltas"] = qdeltas
            trends["quarterly_periods_compared"] = f"{latest_q.get('period_label')} vs {prior_q.get('period_label')}"

        return trends

    def _compact_benchmarks(self, bm_history: list[dict[str, Any]]) -> str:
        """Build a compact benchmark table from multi-period data (token-efficient)."""
        if not bm_history:
            return ""
        metrics = [
            ("revenue_growth_yoy", "Rev Growth"),
            ("gross_margin", "Gross Margin"),
            ("operating_margin", "Op Margin"),
            ("sga_to_revenue", "SG&A/Rev"),
            ("rnd_to_revenue", "R&D/Rev"),
            ("capex_to_revenue", "CapEx/Rev"),
        ]
        header = "| Period | N |"
        for _, label in metrics:
            header += f" {label} P50 |"
        lines = [header, "|" + "---|" * (len(metrics) + 2)]
        for bm in bm_history:
            dist = bm.get("distributions") or {}
            row = f"| {bm.get('period_label', '?')} | {bm.get('company_count', 0)} |"
            for key, _ in metrics:
                val = (dist.get(key) or {}).get("p50")
                row += f" {val:.1%} |" if val is not None else " — |"
            lines.append(row)
        return "\n".join(lines)

    def _compact_company_table(
        self, profiles: dict[str, list], trajectories: dict[str, list]
    ) -> str:
        """Build compact company profiles grouped by competitive role."""
        traj_map: dict[str, str] = {}
        for role_trajs in trajectories.values():
            for t in role_trajs:
                traj_map[t.get("company_name", "")] = t.get("trajectory_class", "?")

        lines = [
            "| Role | Company | Ticker | Rev Growth | SG&A/Rev | Op Margin | Trajectory | Signals |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for role, role_profiles in profiles.items():
            for p in role_profiles:
                name = p.get("company_name", "?")
                ticker = (p.get("company") or {}).get("ticker", "?")
                spend = p.get("gtm_spend") or {}
                sga = spend.get("sga_to_revenue")
                opm = spend.get("operating_margin")
                # revenue_growth is in trend[0], not top-level gtm_spend
                trend_list = spend.get("trend") or []
                rg = trend_list[0].get("revenue_growth_yoy") if trend_list else None
                sga_s = f"{sga:.1%}" if sga is not None else "—"
                opm_s = f"{opm:.1%}" if opm is not None else "—"
                rg_s = f"{rg:.1%}" if rg is not None else "—"
                traj = traj_map.get(name, "?")
                sigs = len(p.get("gtm_signals") or [])
                lines.append(
                    f"| {role} | {name} | {ticker} | {rg_s} | {sga_s} | {opm_s} | {traj} | {sigs} |"
                )
        return "\n".join(lines)

    async def _synthesize(
        self,
        vertical_slug: str,
        mcp_data: dict[str, Any],
        live_data: dict[str, Any],
        kb_framework: str,
    ) -> VerticalIntelligenceOutput:
        """Synthesize all data into a comprehensive intelligence report via LLM."""

        # Build data context for the LLM — COMPACT format to stay under token limits
        data_sections: list[str] = []

        # Vertical intel report — extract key sections, skip redundant raw data
        vi = mcp_data.get("vertical_intel") or {}
        if vi:
            # Market overview (text)
            mo = vi.get("market_overview") or {}
            if mo:
                data_sections.append(f"## Market Overview\n{json.dumps(mo, default=str)}")

            # Key trends (compact)
            kt = vi.get("key_trends") or []
            if kt:
                data_sections.append(f"## Key Industry Trends\n{json.dumps(kt, default=str)}")

            # Signal digest (recent high-impact signals)
            sd = vi.get("signal_digest") or []
            if sd:
                data_sections.append(f"## Recent Signals ({len(sd)} items)\n{json.dumps(sd, default=str)}")

            # Executive movements
            em = vi.get("executive_movements") or []
            if em:
                data_sections.append(f"## Executive Movements\n{json.dumps(em, default=str)}")

            # Financial pulse (critical for trend analysis)
            fp = vi.get("financial_pulse") or {}
            if fp:
                data_sections.append(f"## Financial Pulse (Trend Data)\n{json.dumps(fp, default=str)}")

            # Competitive dynamics summary (names + roles only — detail comes from profiles)
            cd = vi.get("competitive_dynamics") or {}
            if cd:
                cd_summary = {}
                for role in ("leaders", "movers_up", "movers_down", "gtm_investors"):
                    companies = cd.get(role) or []
                    cd_summary[role] = [
                        {"name": c.get("name"), "ticker": c.get("ticker"),
                         "market_cap_sgd": c.get("market_cap_sgd"),
                         "revenue_growth_yoy": c.get("revenue_growth_yoy")}
                        for c in companies
                    ]
                data_sections.append(f"## Competitive Dynamics\n{json.dumps(cd_summary, default=str)}")

                # SG agency landscape (private companies invisible in DB-based dynamics)
                sg_agencies = cd.get("sg_agency_landscape") or []
                if sg_agencies:
                    # Compact table: name, segment, parent group, hiring, awards
                    sg_lines = [
                        "| Agency | Parent Group | Segment | Hiring | Awards |",
                        "|---|---|---|---|---|",
                    ]
                    for a in sg_agencies[:40]:
                        hiring = a.get("hiring_openings", 0)
                        awards_list = a.get("awards_won", [])
                        awards_str = ", ".join(awards_list[:3]) if awards_list else "—"
                        sg_lines.append(
                            f"| {a.get('name', '?')} | {a.get('parent_group', 'Independent')} "
                            f"| {a.get('segment', '?')} "
                            f"| {hiring or '—'} | {awards_str} |"
                        )
                    data_sections.append(f"## SG Agency Landscape ({len(sg_agencies)} agencies)\n" + "\n".join(sg_lines))

                # Holding group ownership map
                hg_map = cd.get("holding_group_map") or {}
                if hg_map:
                    hg_lines = []
                    for grp, info in list(hg_map.items())[:15]:
                        agencies_str = ", ".join(info.get("agencies", [])[:8])
                        hg_lines.append(f"- **{grp}** ({info.get('subsidiary_count', 0)} agencies): {agencies_str}")
                    data_sections.append("## Holding Group Ownership Map\n" + "\n".join(hg_lines))

                # Award leaderboard
                award_lb = cd.get("award_leaderboard") or []
                if award_lb:
                    al_lines = [f"- {a['name']} ({a.get('parent_group', '?')}): {', '.join(a.get('awards', []))}" for a in award_lb[:15]]
                    data_sections.append(f"## Award Leaderboard ({len(award_lb)} agencies with awards)\n" + "\n".join(al_lines))

                # Service line matrix
                svc_matrix = cd.get("service_line_matrix") or {}
                if svc_matrix:
                    svc_lines = [f"- **{svc}** ({info['count']} agencies): {', '.join(info['agencies'][:6])}" for svc, info in svc_matrix.items()]
                    data_sections.append("## Service Line Distribution\n" + "\n".join(svc_lines))

                # Segment breakdown
                seg_breakdown = cd.get("segment_breakdown") or {}
                if seg_breakdown:
                    data_sections.append(f"## Segment Breakdown\n{json.dumps(seg_breakdown, default=str)}")

                # SG market pulse (hiring velocity, award density)
                sg_pulse = cd.get("sg_market_pulse") or {}
                if sg_pulse:
                    data_sections.append(f"## SG Market Pulse\n{json.dumps(sg_pulse, indent=2, default=str)}")

            # GTM implications from pre-synth
            gi = vi.get("gtm_implications") or []
            if gi:
                data_sections.append(f"## Pre-Computed GTM Implications\n{json.dumps(gi, default=str)}")

            # Regulatory
            reg = vi.get("regulatory_environment") or []
            if reg:
                data_sections.append(f"## Regulatory Environment\n{json.dumps(reg, default=str)}")

        # Multi-period benchmarks — COMPACT table format
        bm_history = mcp_data.get("benchmark_history") or []
        if bm_history:
            bm_table = self._compact_benchmarks(bm_history)
            data_sections.append(f"## Financial Benchmarks — {len(bm_history)} Periods\n{bm_table}")

        # Pre-computed trend analysis (already compact)
        financial_pulse = vi.get("financial_pulse") or {}
        trend_analysis = self._compute_trend_analysis(bm_history, financial_pulse)
        if trend_analysis:
            data_sections.append(
                f"## YoY Trend Deltas\n{json.dumps(trend_analysis, indent=2, default=str)}"
            )

        # Landscape summary (just structure, not full company list)
        ls = mcp_data.get("landscape") or {}
        if ls:
            ls_summary = {
                "companies_tracked": ls.get("listed_companies_count"),
                "market_cap_total_sgd": ls.get("market_cap_total_sgd"),
                "vertical": ls.get("vertical"),
            }
            data_sections.append(f"## Vertical Structure\n{json.dumps(ls_summary, default=str)}")

        # Company profiles + trajectories — COMPACT table
        profiles = mcp_data.get("company_profiles") or {}
        trajectories = mcp_data.get("company_trajectories") or {}
        total_profiles = sum(len(v) for v in profiles.values())
        if total_profiles:
            company_table = self._compact_company_table(profiles, trajectories)
            data_sections.append(f"## Company GTM Profiles ({total_profiles} companies)\n{company_table}")

        # Trajectory narratives (compact: name + class + CAGR + narrative)
        total_trajs = sum(len(v) for v in trajectories.values())
        if total_trajs:
            traj_lines = []
            for _role, role_trajs in trajectories.items():
                for t in role_trajs:
                    name = t.get("company_name", "?")
                    tc = t.get("trajectory_class", "?")
                    cagr = t.get("revenue_cagr")
                    narrative = t.get("narrative", "")
                    cagr_s = f"{cagr:.1%}" if cagr is not None else "—"
                    traj_lines.append(f"- **{name}** ({tc}, CAGR {cagr_s}): {narrative[:120]}")
            if traj_lines:
                data_sections.append("## Company Trajectories\n" + "\n".join(traj_lines[:15]))

        # Live news
        if live_data.get("news"):
            data_sections.append(
                f"## Recent News (last 14 days)\n{json.dumps(live_data['news'], indent=2, default=str)}"
            )

        # Live research
        if live_data.get("research"):
            data_sections.append(f"## Perplexity Research\n{live_data['research'][:3000]}")

        # Ecosystem context (associations, publications, events, awards)
        ecosystem = getattr(self, "_ecosystem", None)
        if ecosystem:
            eco_text = ecosystem.format_for_llm(max_orgs=12, include_feeds=False)
            data_sections.append(eco_text)

        data_context = "\n\n".join(data_sections)

        # Build explicit data gaps so LLM knows what's unavailable
        gaps: list[str] = []
        if not bm_history:
            gaps.append("No financial benchmarks available — do NOT reference benchmark percentiles")
        elif len(bm_history) == 1:
            gaps.append("Single benchmark period only — state 'single-period snapshot' instead of citing YoY trends")
        if not (vi.get("key_trends") or []):
            gaps.append("No industry trends from DB — use dossier-derived trends if present in data context")
        if not (vi.get("signal_digest") or []):
            gaps.append("No recent market signals from DB — use dossier-derived signals if present")
        if not (vi.get("executive_movements") or []):
            gaps.append("No executive movements from DB — use dossier-derived movements if present")
        if not total_profiles:
            gaps.append("No company GTM profiles available — competitive landscape based on landscape data only")
        if not total_trajs:
            gaps.append("No company trajectory data — do NOT cite acceleration or deceleration trends")
        if not live_data.get("news"):
            gaps.append("No live news available — do NOT reference recent news events")
        if not live_data.get("research"):
            gaps.append("No Perplexity research available — do NOT cite real-time market analysis")

        gaps_section = ""
        if gaps:
            gaps_section = "\n\n## DATA GAPS — do NOT fabricate data for these:\n" + "\n".join(f"- {g}" for g in gaps)

        # Knowledge pack injection
        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""

        # Framework guidance
        fw_section = f"\n\nAnalytical Framework: {kb_framework}" if kb_framework else ""

        prompt = f"""{_knowledge_header}Produce a comprehensive Vertical Intelligence Report for the **{vertical_slug}** vertical.

Use ONLY the structured data below — do not fabricate financial figures.{fw_section}{gaps_section}

--- DATA CONTEXT ---
{data_context}
--- END DATA ---

Respond with a JSON object matching the VerticalIntelligenceOutput schema.

## CRITICAL REQUIREMENTS (consulting-grade depth):

### 1. Executive Summary (2-3 paragraphs)
- Open with the vertical's market size (total_market_cap_sgd) and company count
- State the headline performance metric (median revenue growth) and its YoY direction
- Identify the dominant narrative: growth cycle, efficiency cycle, or transformation
- Name specific companies and cite their numbers
- If a Holding Group Ownership Map is in the data, your SECOND paragraph MUST name the top holding groups and their subsidiary counts (e.g. "The market is dominated by global holding groups: WPP (6 SG subsidiaries), Omnicom (11), Publicis (6), and Dentsu (3), alongside 36 independents")
- If an Award Leaderboard is in the data, name the top 3 award-winning agencies

### 2. Drivers — MINIMUM 5 (not 3)
Each driver MUST be specific to THIS vertical with data evidence:
- BAD: "Digital Transformation" (generic, applies to every industry)
- GOOD: "Embedded finance adoption — 3 of 5 leaders investing >25% SG&A" (specific, data-backed)
- Each driver must cite at least one number from the data context
- Include at least 2 tailwinds and 2 headwinds
- Each gtm_implication must be actionable and specific (name a buying persona or budget line)

### 3. Performance Narrative
- MUST reference YoY trend data: "Revenue growth median shifted from X% (2023) to Y% (2024)"
- MUST address SG&A trend direction and what it signals about industry buying appetite
- MUST address margin compression/expansion and what it means for urgency
- Use the Pre-Computed Trend Analysis section for precise deltas

### 4. Competitive Landscape
- Classify ALL companies from the data (leaders, challengers, new_entrants, laggards)
- For each company: cite specific financials (revenue_growth_yoy, sga_to_revenue, trajectory)
- 'notable' field must explain WHY this company matters for GTM strategy (not just "large market cap")

### 5. Market Forces (Porter's Five Forces) — DATA-GROUNDED
- BAD: "High buyer power due to availability of multiple solutions" (MBA 101 generic)
- GOOD: "Buyer power is HIGH — 69 tracked companies compete on margin (P50 operating margin only 18.6%), creating price sensitivity. The top 5 leaders hold 60% market cap but only 30% of revenue, indicating fragmented mid-market"
- Each force must cite at least 2 data points from the benchmarks or landscape

### 6. GTM Implications — MINIMUM 5
- Each must have: insight (data-backed), recommended_action (specific tactic), priority (high/medium/low)
- At least 2 must reference specific benchmark trends
- Include implications for: pricing strategy, buyer personas, competitive positioning, timing

### 7. Trends and Signals
- Use key_trends and signal_digest from the vertical intelligence report
- If the report has financial_pulse data, interpret what SG&A/margin trends mean for GTM timing

### 8. Regulatory Environment
- Go beyond generic PDPA/PSG — cite industry-specific regulations from the data
- If the vertical has specific regulators (MAS for fintech, HSA for biomedical), name them"""

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        # Track data sources
        sources: list[str] = []
        if mcp_data.get("vertical_intel"):
            sources.append("vertical_intelligence_report")
        if bm_history:
            sources.append("vertical_benchmarks")
            if len(bm_history) >= 2:
                sources.append("multi_period_trends")
        if mcp_data.get("landscape"):
            sources.append("vertical_landscape")
        total_profiles = sum(
            len(v) for v in (mcp_data.get("company_profiles") or {}).values()
        )
        if total_profiles:
            sources.append("company_gtm_profiles")
        total_trajs = sum(
            len(v) for v in (mcp_data.get("company_trajectories") or {}).values()
        )
        if total_trajs:
            sources.append("company_trajectories")
        if live_data.get("news"):
            sources.append("newsapi")
        if live_data.get("research"):
            sources.append("perplexity")

        result = await self._complete_structured(
            response_model=VerticalIntelligenceOutput,
            messages=messages,
        )

        # Overlay metadata that the LLM might not set correctly
        result.vertical_slug = vertical_slug
        result.data_sources_used = sources
        result.is_live_data = self._has_live_news or self._has_research

        # Overlay structured data from synthesizer (prefer synthesizer when non-empty,
        # otherwise keep LLM-generated content)
        vi_data = mcp_data.get("vertical_intel") or {}
        vi_signals = vi_data.get("signal_digest") or []
        vi_movements = vi_data.get("executive_movements") or []
        vi_regulatory = vi_data.get("regulatory_environment") or []
        vi_trends = vi_data.get("key_trends") or []
        vi_gtm = vi_data.get("gtm_implications") or []

        # Merge synthesizer data WITH LLM output (synthesizer first, then unique LLM items)
        result.recent_signals = self._merge_list_sections(
            vi_signals, result.recent_signals, key_field="headline", max_items=15,
        )
        result.executive_movements = self._merge_list_sections(
            vi_movements, result.executive_movements, key_field="company", max_items=12,
        )
        result.regulatory_environment = self._merge_list_sections(
            vi_regulatory, result.regulatory_environment, key_field="title", max_items=12,
        )
        if vi_trends:
            result.trends = vi_trends  # Trends: synthesizer is authoritative (structured extraction)

        # Merge synthesizer GTM implications into LLM output (dedup by insight text)
        if vi_gtm and result.gtm_implications:
            existing_insights = {
                (g.get("insight") or "").lower() for g in result.gtm_implications
            }
            for g in vi_gtm:
                key = (g.get("insight") or "").lower()
                if key and key not in existing_insights:
                    result.gtm_implications.append(g)
                    existing_insights.add(key)
        elif vi_gtm and not result.gtm_implications:
            result.gtm_implications = vi_gtm
        result.total_companies_tracked = (
            (mcp_data.get("landscape") or {}).get("listed_companies_count") or 0
        )
        result.total_market_cap_sgd = (
            (mcp_data.get("landscape") or {}).get("market_cap_total_sgd") or 0
        )

        # Build benchmark summaries from all periods
        result.benchmark_history = [self._build_benchmark_summary(bm) for bm in bm_history]
        if result.benchmark_history:
            # Latest period as the primary benchmark
            result.benchmarks = result.benchmark_history[0]

        # Store pre-computed trend analysis
        result.trend_analysis = trend_analysis

        # Overlay industry structure data from synthesizer (not LLM-generated)
        vi_cd = vi_data.get("competitive_dynamics") or {}
        if vi_cd.get("holding_group_map"):
            result.holding_group_map = vi_cd["holding_group_map"]
        if vi_cd.get("sg_agency_landscape"):
            result.sg_agency_landscape = vi_cd["sg_agency_landscape"]
        if vi_cd.get("award_leaderboard"):
            result.award_leaderboard = vi_cd["award_leaderboard"]
        if vi_cd.get("service_line_matrix"):
            result.service_line_distribution = vi_cd["service_line_matrix"]

        # Include SG agency count in total companies tracked
        sg_agency_count = len(result.sg_agency_landscape)
        if sg_agency_count > 0:
            listed_count = result.total_companies_tracked
            result.total_companies_tracked = listed_count + sg_agency_count

        return result

    @staticmethod
    def _merge_list_sections(
        authoritative: list[dict], secondary: list[dict],
        *, key_field: str, max_items: int = 15,
    ) -> list[dict]:
        """Merge two list sections, deduplicating by key_field.

        Authoritative items come first; secondary items added only if
        their key_field value hasn't been seen.  Returns at most max_items.
        """
        if not authoritative and not secondary:
            return []
        if not authoritative:
            return secondary[:max_items]
        if not secondary:
            return authoritative[:max_items]

        merged = list(authoritative)
        seen_keys: set[str] = set()
        for item in authoritative:
            key = str(item.get(key_field, "")).lower()[:100]
            if key:
                seen_keys.add(key)

        for item in secondary:
            if len(merged) >= max_items:
                break
            key = str(item.get(key_field, "")).lower()[:100]
            if key and key not in seen_keys:
                merged.append(item)
                seen_keys.add(key)

        return merged[:max_items]

    # ------------------------------------------------------------------
    # PDCA: Check
    # ------------------------------------------------------------------

    async def _check(self, result: VerticalIntelligenceOutput) -> float:
        """Derive confidence from data quality. Base is 0.2.

        Rewards data richness AND penalises empty critical sections
        so that confidence reflects actual output quality, not just
        input availability.
        """
        score = 0.2

        # Executive summary depth
        if result.executive_summary and len(result.executive_summary) > 200:
            score += 0.12
        elif result.executive_summary and len(result.executive_summary) > 50:
            score += 0.05

        # Drivers identified (5+ for consulting-grade)
        if len(result.drivers) >= 5:
            score += 0.10
        elif len(result.drivers) >= 3:
            score += 0.07
        elif result.drivers:
            score += 0.03

        # Competitive landscape populated
        total_players = len(result.leaders) + len(result.challengers) + len(result.laggards)
        if total_players >= 5:
            score += 0.08
        elif total_players >= 2:
            score += 0.04

        # Market forces analysis
        if result.market_forces:
            score += 0.05

        # MCP data enrichment
        if self._has_vertical_intel:
            score += 0.08
        if self._has_benchmarks:
            score += 0.05
        if self._has_trajectories:
            score += 0.05

        # Multi-period trend analysis (consulting-grade differentiator)
        if self._has_multi_period:
            score += 0.05

        # Live data
        if self._has_live_news:
            score += 0.04
        if self._has_research:
            score += 0.04

        # Knowledge framework usage
        if self._has_kb_framework:
            score += 0.02

        # Ecosystem context enrichment
        if getattr(self, "_ecosystem", None) is not None:
            score += 0.03

        # GTM implications (5+ for consulting-grade)
        if len(result.gtm_implications) >= 5:
            score += 0.07
        elif len(result.gtm_implications) >= 3:
            score += 0.05

        # ----- Penalties for empty critical sections -----
        # These sections are expected in a consulting-grade report.
        # Empty = data pipeline issue or synthesis failure.
        if not result.trends:
            score -= 0.06
        if not result.recent_signals:
            score -= 0.04
        if not result.executive_movements:
            score -= 0.03
        if not result.gtm_implications:
            score -= 0.08
        if not result.regulatory_environment:
            score -= 0.03

        # Penalty for insufficient depth (system prompt requires MINIMUM 5)
        if 0 < len(result.drivers) < 5:
            score -= 0.04
        if 0 < len(result.gtm_implications) < 5:
            score -= 0.04

        # Penalty for sparse benchmarks (< 10 companies is statistically weak)
        if result.benchmarks and hasattr(result.benchmarks, "company_count"):
            if result.benchmarks.company_count < 10:
                score -= 0.04

        # Penalty for single-period benchmarks (cannot show YoY trends)
        if self._has_benchmarks and not self._has_multi_period:
            score -= 0.04

        # Penalty for sparse competitive landscape
        if 0 < total_players < 5:
            score -= 0.03

        return min(max(score, 0.10), 0.95)

    # ------------------------------------------------------------------
    # PDCA: Act
    # ------------------------------------------------------------------

    async def _act(
        self,
        result: VerticalIntelligenceOutput,
        confidence: float,
    ) -> VerticalIntelligenceOutput:
        """Publish findings to the agent bus."""
        result.confidence = confidence

        if self._agent_bus:
            # Publish market overview
            await self._agent_bus.publish(
                from_agent=self.name,
                discovery_type=DiscoveryType.MARKET_TREND,
                title=f"Vertical Intelligence: {result.vertical_name}",
                content={
                    "vertical_slug": result.vertical_slug,
                    "executive_summary": result.executive_summary,
                    "drivers": [d.model_dump() for d in result.drivers],
                    "gtm_implications": result.gtm_implications,
                    "benchmarks": result.benchmarks.model_dump() if result.benchmarks else None,
                },
                confidence=confidence,
                analysis_id=self._analysis_id,
            )

            # Publish each driver as an individual discovery
            for driver in result.drivers:
                dtype = (
                    DiscoveryType.MARKET_OPPORTUNITY
                    if driver.direction == "tailwind"
                    else DiscoveryType.MARKET_TREND
                )
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=dtype,
                    title=f"[{result.vertical_slug}] {driver.name}",
                    content={
                        "direction": driver.direction,
                        "magnitude": driver.magnitude,
                        "description": driver.description,
                        "gtm_implication": driver.gtm_implication,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )

        return result
