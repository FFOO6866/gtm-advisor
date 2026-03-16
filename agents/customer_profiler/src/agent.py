"""Customer Profiler Agent - ICP and persona development.

Develops detailed ideal customer profiles and personas based on market research.
Uses real signals from AgentBus (market trends, competitor intel) to ground LLM synthesis.
"""

from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, DiscoveryType, get_agent_bus
from packages.core.src.types import CustomerPersona
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.models import ListedCompany, MarketVertical
from packages.database.src.session import async_session_factory
from packages.integrations.newsapi.src.client import NewsAPIClient
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer


class ICPDefinition(BaseModel):
    """Ideal Customer Profile definition."""

    company_characteristics: dict[str, Any] = Field(default_factory=dict)
    firmographics: dict[str, Any] = Field(default_factory=dict)
    technographics: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)
    disqualification_criteria: list[str] = Field(default_factory=list)


class CustomerProfileOutput(BaseModel):
    """Customer profiling output."""

    icp: ICPDefinition = Field(default_factory=ICPDefinition)
    personas: list[CustomerPersona] = Field(default_factory=list)
    segmentation_strategy: str = Field(default="")
    targeting_recommendations: list[str] = Field(default_factory=list)
    messaging_themes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=False)  # True if bus or KB returned real data


class CustomerProfilerAgent(BaseGTMAgent[CustomerProfileOutput]):
    """Customer Profiler - Develops ICP and personas.

    Creates detailed customer profiles based on:
    - Company characteristics and requirements
    - Market research insights
    - Competitor analysis
    """

    def __init__(self, bus: AgentBus | None = None) -> None:
        super().__init__(
            name="customer-profiler",
            description=(
                "Develops detailed Ideal Customer Profiles (ICP) and buyer personas. "
                "Identifies target segments and provides messaging recommendations."
            ),
            result_type=CustomerProfileOutput,
            min_confidence=0.60,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="icp-development", description="Define ideal customer profile"
                ),
                AgentCapability(name="persona-creation", description="Create buyer personas"),
                AgentCapability(name="segmentation", description="Market segmentation strategy"),
            ],
        )
        self._bus = bus or get_agent_bus()
        self._newsapi = NewsAPIClient()
        self._analysis_id: Any = None

    def get_system_prompt(self) -> str:
        return """You are the Customer Profiler, an expert in B2B customer segmentation for Singapore/APAC markets.

You create actionable ICPs and personas by:
1. Defining PRECISE firmographic criteria with numeric ranges (not vague labels)
2. Identifying buying signals and trigger events
3. Understanding decision-maker personas with specific job titles
4. Mapping the buying process and typical sales cycle length

Firmographic precision is mandatory. Always specify:
- employee_count: exact range (e.g. "10–50", "50–200", "200–1000")
- annual_revenue_sgd: exact range (e.g. "SGD 1M–10M", "SGD 10M–50M")
- funding_stage: specific (e.g. "bootstrapped", "seed", "Series A–B", "profitable SME")
- company_age: range in years (e.g. "2–5 years", "5–15 years")
- geography: specific (e.g. "Singapore HQ, ASEAN expansion", "Singapore-only")

For Singapore SMEs, consider:
- PSG grant eligibility: companies with ≤200 employees, ≤SGD 100M turnover
- EDG grant eligibility: companies wanting to internationalise
- EntrePass/EP holders at target companies signal tech-forward culture
- Regional expansion plans (ASEAN gateway use case)

Be specific - vague personas like "Tech Manager" are useless.
Each persona must have a SPECIFIC job title (e.g. "Head of Sales Operations, 3–5 person team, Series A SaaS startup")."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        analysis_id = context.get("analysis_id")
        self._analysis_id = analysis_id

        # Load domain knowledge pack — injected into _do() synthesis prompt.
        kmcp = get_knowledge_mcp()
        self._knowledge_pack = await kmcp.get_agent_knowledge_pack(
            agent_name="customer-profiler",
            task_context=task,
        )

        # Load live Singapore reference data (PSG eligibility, firmographic context)
        self._sg_reference = await kmcp.get_sg_reference(
            query=f"Singapore SME PSG eligibility ICP firmographics {task[:200]}",
            limit=3,
        )

        # Pull real signals from bus history if available
        market_signals: list[dict[str, Any]] = []
        competitor_signals: list[dict[str, Any]] = []
        company_data: dict[str, Any] = context.get("company_profile", {})

        if self._bus is not None:
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.MARKET_TREND,
                limit=10,
            ):
                market_signals.append({"title": msg.title, **msg.content})

            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.COMPETITOR_FOUND,
                limit=5,
            ):
                competitor_signals.append({"title": msg.title, **msg.content})

            # Merge richer company profile if published by enricher
            profile_msgs = self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.COMPANY_PROFILE,
                limit=1,
            )
            if profile_msgs:
                # Bus-sourced enriched data wins over raw user-provided context
                company_data = {**company_data, **profile_msgs[0].content}

        return {
            "company_info": company_data,
            "market_insights": context.get("market_insights", {}),
            "market_signals": market_signals,
            "competitor_signals": competitor_signals,
            "value_proposition": context.get("value_proposition", ""),
            "target_industries": context.get("target_industries", []),
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CustomerProfileOutput:
        market_signals = plan.get("market_signals", [])
        competitor_signals = plan.get("competitor_signals", [])

        # --- Phase 0: KB — Vertical landscape + ICP framework from knowledge library ---
        kb_landscape: dict[str, Any] = {}
        kb_benchmarks: dict[str, Any] = {}
        kb_vertical_intel: dict[str, Any] = {}
        target_industries = plan.get("target_industries", [])
        company_info = plan.get("company_info", {})
        industry_fallback = (
            company_info.get("industry", "") + " " + company_info.get("description", "")
            if isinstance(company_info, dict)
            else ""
        )
        industry_text = " ".join(target_industries) if target_industries else industry_fallback
        vertical_slug = detect_vertical_slug(industry_text)
        if vertical_slug:
            try:
                async with async_session_factory() as db:
                    mcp = MarketIntelMCPServer(session=db)
                    kb_landscape = await mcp.get_vertical_landscape(vertical_slug) or {}
                    kb_benchmarks = await mcp.get_vertical_benchmarks(vertical_slug) or {}
                    kb_vertical_intel = await mcp.get_vertical_intelligence(vertical_slug) or {}

                    # Query real employee distribution for this vertical
                    kb_employee_stats: dict[str, Any] = {}
                    vert_row = await db.scalar(
                        select(MarketVertical).where(MarketVertical.slug == vertical_slug)
                    )
                    if vert_row is not None:
                        emp_rows = await db.scalars(
                            select(ListedCompany.employees).where(
                                ListedCompany.vertical_id == vert_row.id,
                                ListedCompany.is_active.is_(True),
                                ListedCompany.employees.is_not(None),
                            )
                        )
                        emp_values = sorted(emp_rows.all())
                        if emp_values:
                            n = len(emp_values)
                            kb_employee_stats = {
                                "n": n,
                                "p25": emp_values[max(0, int(n * 0.25) - 1)],
                                "median": statistics.median(emp_values),
                                "p75": emp_values[min(n - 1, int(n * 0.75))],
                            }
                    self._kb_employee_stats = kb_employee_stats
                    self._kb_vertical_intel = kb_vertical_intel
            except Exception as e:
                self._logger.debug("kb_icp_enrichment_failed", error=str(e))

        self._kb_hit = bool(kb_landscape or kb_benchmarks)

        # --- Phase 1: Live news for this vertical/industry ---
        industry_news: list[str] = []
        if self._newsapi.is_configured:
            try:
                search_query = industry_text or "Singapore SME B2B technology"
                news_result = await self._newsapi.search_market_news(
                    industry=search_query,
                    region="Singapore",
                    days_back=14,
                )
                industry_news = [
                    a.title
                    for a in (news_result.articles if hasattr(news_result, "articles") else [])
                    if a.title
                ][:5]
            except Exception as e:
                self._logger.debug("customer_profiler_newsapi_failed", error=str(e))

        self._has_live_news = bool(industry_news)

        # Track data sources for provenance
        data_sources_used: list[str] = []
        if market_signals:
            data_sources_used.append("AgentBus (Market Signals)")
        if competitor_signals:
            data_sources_used.append("AgentBus (Competitor Intel)")
        if kb_landscape or kb_benchmarks:
            data_sources_used.append("Market Intel DB")
        if industry_news:
            data_sources_used.append("NewsAPI")
        if getattr(self, "_kb_vertical_intel", {}):
            data_sources_used.append("Vertical Intelligence Report")
        self._data_sources_used = data_sources_used
        self._has_live_data = bool(market_signals or kb_landscape or kb_benchmarks or industry_news)

        # Load ICP segmentation framework from knowledge library (static, always available)
        kb_icp_guidance = ""
        try:
            kmcp = get_knowledge_mcp()
            icp_fw = await kmcp.get_framework("ICP_FRAMEWORK")
            stp_fw = await kmcp.get_framework("STP_FRAMEWORK")
            icp_content = icp_fw.get("content") or {}
            stp_seg = (stp_fw.get("content") or {}).get("segmentation", {})
            bases = list((stp_seg.get("bases") or {}).keys())
            if bases:
                kb_icp_guidance = (
                    f"\nSegmentation bases to use when defining the ICP: {', '.join(bases)}. "
                    f"Always include firmographic + behavioural bases for B2B Singapore profiles."
                )
            qualifiers = icp_content.get("qualification_signals", {})
            if qualifiers:
                kb_icp_guidance += (
                    f"\nICP qualification signals to surface: {list(qualifiers.keys())[:5]}"
                )
        except Exception as e:
            self._logger.debug("knowledge_mcp_icp_failed", error=str(e))

        # Build KB firmographic context from landscape/benchmark data
        kb_firmographic_context = ""
        if kb_landscape or kb_benchmarks:
            lines = [f"\n\nKB Vertical Data ({vertical_slug}):"]
            if kb_landscape.get("companies_count"):
                lines.append(f"- {kb_landscape['companies_count']} listed companies in vertical")
            mkt_cap = kb_landscape.get("market_cap_sgd_total")
            if mkt_cap and isinstance(mkt_cap, int | float):
                lines.append(f"- Total market cap: SGD {mkt_cap:,.0f}M")
            if kb_landscape.get("leaders"):
                leaders = [c.get("name", "") for c in kb_landscape["leaders"][:3] if c.get("name")]
                lines.append(f"- Market leaders: {', '.join(leaders)}")

            # Real employee distribution from ListedCompany DB query
            emp_stats = getattr(self, "_kb_employee_stats", {})
            if emp_stats:
                lines.append(
                    f"- Employee distribution: P25={emp_stats['p25']:,}, "
                    f"median={int(emp_stats['median']):,}, "
                    f"P75={emp_stats['p75']:,} "
                    f"(n={emp_stats['n']})"
                )

            # Revenue distribution from VerticalBenchmark.distributions.revenue_ttm_sgd
            dist = (kb_benchmarks.get("distributions") or {})
            rev_dist = dist.get("revenue_ttm_sgd") or {}
            rev_p25 = rev_dist.get("p25")
            rev_p50 = rev_dist.get("p50")
            rev_p75 = rev_dist.get("p75")
            if rev_p50 is not None:
                parts = []
                if rev_p25 is not None:
                    parts.append(f"P25=SGD {rev_p25/1e6:.0f}M")
                if rev_p50 is not None:
                    parts.append(f"median=SGD {rev_p50/1e6:.0f}M")
                if rev_p75 is not None:
                    parts.append(f"P75=SGD {rev_p75/1e6:.0f}M")
                if parts:
                    lines.append(f"- Revenue distribution (TTM): {', '.join(parts)}")

            # Gross margin median
            gm_dist = dist.get("gross_margin") or {}
            gm_p50 = gm_dist.get("p50")
            if gm_p50 is not None:
                lines.append(f"- Median gross margin: {gm_p50 * 100:.1f}%")

            # Revenue growth median
            rg_dist = dist.get("revenue_growth_yoy") or {}
            rg_p50 = rg_dist.get("p50")
            if rg_p50 is not None:
                lines.append(f"- Median revenue growth: {rg_p50 * 100:.1f}% YoY")

            # Vertical intelligence — competitive dynamics and GTM spend patterns
            vi = getattr(self, "_kb_vertical_intel", {})
            if vi:
                comp_dyn = vi.get("competitive_dynamics") or {}
                gtm_investors = comp_dyn.get("gtm_investors", [])
                if gtm_investors:
                    investor_names = [
                        g.get("name", str(g)) if isinstance(g, dict) else str(g)
                        for g in gtm_investors[:3]
                    ]
                    lines.append(f"- Top GTM investors (highest SG&A spend): {', '.join(investor_names)}")
                fin_pulse = vi.get("financial_pulse") or {}
                sga_median = fin_pulse.get("sga_median")
                rnd_median = fin_pulse.get("rnd_median")
                if isinstance(sga_median, (int, float)) and sga_median > 0:
                    lines.append(f"- Median SG&A/Revenue: {sga_median*100:.1f}% (marketing intensity)")
                if isinstance(rnd_median, (int, float)) and rnd_median > 0:
                    lines.append(f"- Median R&D/Revenue: {rnd_median*100:.1f}% (innovation intensity)")
                # Movers up = companies gaining momentum (good ICP targets)
                movers = comp_dyn.get("movers_up", [])
                if movers:
                    mover_names = [
                        m.get("name", str(m)) if isinstance(m, dict) else str(m)
                        for m in movers[:3]
                    ]
                    lines.append(f"- Momentum companies (revenue accelerating): {', '.join(mover_names)}")
                # GTM implications for ICP refinement
                gtm_impl = vi.get("gtm_implications") or []
                if gtm_impl:
                    for impl in gtm_impl[:2]:
                        insight = impl.get("insight", str(impl)) if isinstance(impl, dict) else str(impl)
                        lines.append(f"- GTM insight: {insight[:200]}")

            kb_firmographic_context = "\n".join(lines)

        market_context = ""
        if market_signals:
            market_context = "\n\nLive Market Signals from bus:\n" + "\n".join(
                f"- {s.get('title') or s.get('headline', '')}" for s in market_signals[:5]
            )

        competitor_context = ""
        if competitor_signals:
            competitor_context = "\n\nCompetitor Intel:\n" + "\n".join(
                f"- {s.get('title') or s.get('headline', '')}" for s in competitor_signals[:3]
            )

        news_context = ""
        if industry_news:
            news_context = "\n\nRecent Industry News (last 14 days):\n" + "\n".join(
                f"- {title}" for title in industry_news[:5]
            )

        has_live_data = bool(market_signals or kb_landscape or kb_benchmarks or industry_news)
        data_quality_note = (
            ""
            if has_live_data
            else (
                "\n\nDATA WARNING: No live market data is available for this analysis "
                "(no market signals, KB landscape, or news). "
                "Derive firmographics logically from the company description only. "
                "Use wide ranges (e.g. '10–200 employees') and prefix each estimated value "
                "with 'est.' — do NOT invent precise numbers without data support."
            )
        )

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        _sg_ref = getattr(self, "_sg_reference", [])
        _sg_context = ""
        if _sg_ref:
            _sg_context = "\n\n--- LIVE SINGAPORE REFERENCE DATA ---\n" + "\n".join(
                f"• {r['title']}: {r.get('summary', '')[:300]}" for r in _sg_ref
            ) + "\n---"
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""{_knowledge_header}Create customer profiles based on:{data_quality_note}

Company/Product: {plan.get("company_info", "Not specified")}
Value Proposition: {plan.get("value_proposition", "Not specified")}
Target Industries: {plan.get("target_industries", [])}{market_context}{competitor_context}{news_context}{kb_firmographic_context}{kb_icp_guidance}

Create:
1. ICP firmographics — include the fields below ONLY when they can be derived from the
   gathered data or logically from the company description. Mark estimates with "est.":
   - "employee_count_range": target company size
   - "annual_revenue_range_sgd": target company revenue
   - "funding_stage": e.g. "bootstrapped", "seed/Series A", "profitable SME"
   - "geography": specific cities/regions
   - "psg_eligible": true/false if derivable from size criteria
   - "tech_stack_maturity": "basic", "intermediate", "advanced"
2. 2-3 buyer personas, each with:
   - Specific job title (not generic "Manager")
   - KPIs they are measured on
   - Tools they currently use (if inferable from industry/description)
   - Trigger events that cause them to evaluate solutions
3. Segmentation strategy with Tier 1/2/3 classification criteria
   - When GTM investor or momentum company data is provided above, reference it to identify
     companies actively investing in go-to-market (high SG&A) as Tier 1 targets
   - Use SG&A/Revenue median to estimate target company marketing budgets
4. Targeting recommendations with specific outreach priority order
5. Messaging themes per persona (hooks grounded in the market signals above where available)

Focus on Singapore/APAC B2B market.{_sg_context}""",
            },
        ]

        return await self._complete_structured(
            response_model=CustomerProfileOutput,
            messages=messages,
        )

    async def _check(self, result: CustomerProfileOutput) -> float:
        score = 0.2  # Base score — must earn via data quality, not just completion
        if result.icp.company_characteristics:
            score += 0.15
        if result.icp.buying_signals:
            score += 0.1
        if result.personas:
            score += 0.15
            if len(result.personas) >= 2:
                score += 0.1
        if result.targeting_recommendations:
            score += 0.1
        if result.messaging_themes:
            score += 0.1
        # KB grounding bonus — vertical landscape/benchmarks improve ICP accuracy
        if getattr(self, "_kb_hit", False):
            score += 0.10
        # Real employee distribution bonus — grounded firmographic size ranges
        if getattr(self, "_kb_employee_stats", {}):
            score += 0.05
        # Live news bonus — grounds ICP in current market dynamics
        if getattr(self, "_has_live_news", False):
            score += 0.05
        # Vertical intelligence bonus — real financial data grounds ICP
        if getattr(self, "_kb_vertical_intel", {}):
            score += 0.05
        # Hard cap: ICP is largely derived from LLM without real data — don't overstate confidence
        has_live_data = getattr(self, "_has_live_data", False)
        if not has_live_data:
            score = min(score, 0.45)
        return min(score, 1.0)

    async def _act(
        self, result: CustomerProfileOutput, confidence: float
    ) -> CustomerProfileOutput:
        """Stamp confidence, data provenance, and publish each persona as PERSONA_DEFINED to the bus.

        Publishing personas lets CampaignArchitect read them from bus history
        (via get_history(PERSONA_DEFINED)) rather than relying solely on direct
        context injection — enabling true A2A data flow.
        """
        result.confidence = confidence
        result.data_sources_used = getattr(self, "_data_sources_used", [])
        result.is_live_data = getattr(self, "_has_live_data", False)

        if self._bus is None:
            return result

        for persona in result.personas:
            try:
                await self._bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.PERSONA_DEFINED,
                    title=persona.name,
                    content={
                        "name": persona.name,
                        "role": persona.role,
                        "pain_points": persona.pain_points,
                        "goals": persona.goals,
                        "challenges": persona.challenges,
                        "preferred_channels": persona.preferred_channels,
                        "decision_criteria": persona.decision_criteria,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.warning(
                    "bus_publish_persona_failed",
                    persona=persona.name,
                    error=str(e),
                )

        self._logger.info(
            "personas_published_to_bus",
            count=len(result.personas),
            analysis_id=str(self._analysis_id),
        )
        return result
