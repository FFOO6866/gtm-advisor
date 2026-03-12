"""Market Intelligence Agent - Real market research and trend analysis.

This agent provides genuine market insights by combining:
- Perplexity AI for real-time web search
- NewsAPI for industry news
- EODHD for economic indicators

NOT generic LLM advice - actual data-driven insights.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, DiscoveryType, get_agent_bus
from packages.core.src.types import IndustryVertical, MarketInsight
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.integrations.eodhd.src import get_eodhd_client
from packages.integrations.newsapi.src import get_newsapi_client
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.knowledge.src.research_persist import persist_research
from packages.llm.src import get_llm_manager
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer


class MarketTrend(BaseModel):
    """A market trend with supporting data."""

    name: str = Field(...)
    description: str = Field(...)
    relevance: str = Field(...)  # How it affects the user's business
    evidence: list[str] = Field(default_factory=list)  # Sources/data points
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)


class MarketOpportunity(BaseModel):
    """Market opportunity identified."""

    title: str = Field(...)
    description: str = Field(...)
    market_size_estimate: str | None = Field(default=None)
    growth_rate: str | None = Field(default=None)
    competitive_intensity: str = Field(default="medium")  # low, medium, high
    time_sensitivity: str = Field(default="medium")  # low, medium, high
    recommended_action: str = Field(...)


class MarketIntelligenceOutput(BaseModel):
    """Complete market intelligence report."""

    industry: IndustryVertical = Field(...)
    region: str = Field(default="Singapore")

    # Market Overview
    market_summary: str = Field(...)
    market_size: str | None = Field(default=None)
    growth_outlook: str | None = Field(default=None)

    # Trends
    key_trends: list[MarketTrend] = Field(default_factory=list)

    # Opportunities & Threats
    opportunities: list[MarketOpportunity] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)

    # Economic Context
    economic_indicators: list[dict[str, Any]] = Field(default_factory=list)

    # News & Events
    recent_news: list[dict[str, str]] = Field(default_factory=list)

    # Recommendations
    implications_for_gtm: list[str] = Field(default_factory=list)

    # DB-backed MCP enrichment (optional — absent when DB is unavailable)
    vertical_landscape: dict[str, Any] | None = Field(default=None)
    vertical_benchmarks: dict[str, Any] | None = Field(default=None)
    stored_articles: list[dict[str, Any]] | None = Field(default=None)

    # Structured insights (e.g. competitive landscape, deep-dives)
    insights: list[MarketInsight] = Field(default_factory=list)

    # Metadata
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_freshness: str = Field(default="real-time")
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=False)  # True only if >=1 real API succeeded


class MarketIntelligenceAgent(BaseGTMAgent[MarketIntelligenceOutput]):
    """Market Intelligence Agent - Real data-driven market research.

    This agent goes beyond generic LLM responses by:
    1. Using Perplexity for real-time web search
    2. Pulling actual news from NewsAPI
    3. Incorporating economic indicators from EODHD
    4. Synthesizing data into actionable insights

    Focus: Singapore and APAC markets
    """

    def __init__(self, agent_bus: AgentBus | None = None) -> None:
        super().__init__(
            name="market-intelligence",
            description=(
                "Provides real-time market intelligence using live data sources. "
                "Analyzes market trends, opportunities, and threats specific to "
                "Singapore/APAC markets with actual news and economic data."
            ),
            result_type=MarketIntelligenceOutput,
            min_confidence=0.70,  # LLM-only (no external APIs) can reach 0.75; add margin
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="market-research",
                    description="Research market trends and dynamics",
                ),
                AgentCapability(
                    name="trend-analysis",
                    description="Identify and analyze market trends",
                ),
                AgentCapability(
                    name="opportunity-identification",
                    description="Spot market opportunities",
                ),
                AgentCapability(
                    name="economic-analysis",
                    description="Incorporate economic indicators",
                ),
            ],
        )

        # Initialize data source clients
        self._newsapi = get_newsapi_client()
        self._eodhd = get_eodhd_client()
        self._perplexity = get_llm_manager().perplexity
        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id: Any = None
        self._company_profile: dict | None = None

    def _detect_vertical(self, task: str) -> str | None:
        """Detect a Singapore market vertical slug from free-text task description.

        Returns one of the 12 registered vertical slugs, or None when no
        keyword match is found. Delegates to the shared utility so the
        keyword table is maintained in a single place.
        """
        return detect_vertical_slug(task)

    def get_system_prompt(self) -> str:
        return """You are the Market Intelligence Agent, a specialist in APAC market research with deep expertise in Singapore's business landscape.

Your role is to provide DATA-DRIVEN market intelligence, not generic advice. You:
1. Use real news and data to identify trends
2. Analyze economic indicators for context
3. Identify specific opportunities and threats
4. Provide actionable insights with evidence

Key focus areas for Singapore:
- Strong government support for startups (PSG grants, etc.)
- High digital adoption rates
- Regional hub for fintech, SaaS
- Growing SME ecosystem
- ASEAN expansion gateway

When analyzing markets:
- Cite specific sources and data points
- Quantify market sizes when possible
- Identify timing and urgency
- Connect trends to GTM implications

Be specific and data-driven. Generic statements like "the market is growing" are not helpful without supporting data."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan market intelligence gathering."""
        context = context or {}

        # Load domain knowledge pack — injected into _do() synthesis prompt.
        kmcp = get_knowledge_mcp()
        self._knowledge_pack = await kmcp.get_agent_knowledge_pack(
            agent_name="market-intelligence",
            task_context=task,
        )

        # Capture analysis_id for bus publishing scope
        self._analysis_id = context.get("analysis_id")

        # Determine industry and region
        industry = context.get("industry", "technology")
        region = context.get("region", "Singapore")
        company_name = context.get("company_name", "")

        description = context.get("description", "")
        value_proposition = context.get("value_proposition", "")

        plan = {
            "industry": industry,
            "region": region,
            "company_name": company_name,
            "description": description,
            "value_proposition": value_proposition,
            "data_sources": [],
            "queries": [],
        }

        # Plan Perplexity queries — use current year to avoid stale-biased searches
        current_year = datetime.now().year
        # Build company-specific queries when we have product context; fall back to
        # generic industry queries when context is sparse.
        _raw_context = (value_proposition or description or "")
        # Truncate at word boundary to avoid mid-word cuts in search queries
        product_context = _raw_context[:150].rsplit(" ", 1)[0] if len(_raw_context) > 150 else _raw_context
        _short_ctx = _raw_context[:80].rsplit(" ", 1)[0] if len(_raw_context) > 80 else _raw_context
        if product_context and company_name:
            plan["queries"] = [
                f"{company_name}: {product_context} market opportunities Singapore APAC {current_year}",
                f"{company_name} target customers competitors alternatives Singapore {current_year}",
                f"{industry} {_short_ctx} Singapore SME adoption trends {current_year}",
            ]
        else:
            plan["queries"] = [
                f"{industry} market trends Singapore {current_year - 1} {current_year}",
                f"{industry} startup ecosystem APAC growth",
                f"{industry} Singapore SME challenges opportunities",
            ]

        # Plan data sources to use
        if self._newsapi.is_configured:
            plan["data_sources"].append("newsapi")
        if self._eodhd.is_configured:
            plan["data_sources"].append("eodhd")
        if self._perplexity.is_configured:
            plan["data_sources"].append("perplexity")

        # ── A2A backfill: pull enriched company profile published by GTM Strategist ──
        if self._agent_bus is not None:
            try:
                profile_msgs = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.COMPANY_PROFILE,
                    limit=1,
                )
                self._company_profile = profile_msgs[0].content if profile_msgs else None
            except Exception as e:
                self._logger.debug("bus_backfill_company_profile_failed", error=str(e))

        return plan

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MarketIntelligenceOutput:
        """Execute market intelligence gathering."""
        context = context or {}
        industry = plan.get("industry", "technology")
        region = plan.get("region", "Singapore")
        task = plan.get("queries", [""])[0]  # representative text for vertical detection

        # Enrich industry/vertical from bus-sourced company profile when available
        if self._company_profile:
            profile_industry = self._company_profile.get("industry") or self._company_profile.get(
                "vertical"
            )
            if profile_industry and not plan.get("industry"):
                industry = profile_industry

        # ------------------------------------------------------------------
        # Phase 1: DB-backed MCP enrichment (MarketIntelMCPServer)
        # Runs first so the synthesizer can incorporate structured benchmarks
        # and stored articles alongside the live API data.
        # Wrapped in a broad except so a missing DB never blocks the agent.
        # ------------------------------------------------------------------
        mcp_landscape: dict[str, Any] = {}
        mcp_benchmarks: dict[str, Any] = {}
        mcp_articles: list[dict[str, Any]] = []

        vertical_slug = self._detect_vertical(f"{industry} {task}")
        if vertical_slug:
            try:
                # SQLAlchemy AsyncSession is NOT safe for concurrent access —
                # "not safe for use in concurrent tasks" (SQLAlchemy 2.0 docs).
                # Run the three MCP calls sequentially on the shared session.
                async with async_session_factory() as db:
                    mcp = MarketIntelMCPServer(session=db)
                    mcp_landscape = await mcp.get_vertical_landscape(vertical_slug)
                    mcp_benchmarks = await mcp.get_vertical_benchmarks(vertical_slug)
                    mcp_search = await mcp.search_market_intelligence(
                        query=f"{industry} market Singapore",
                        vertical_slug=vertical_slug,
                        limit=10,
                    )
                    mcp_articles = mcp_search if isinstance(mcp_search, list) else []
            except Exception as e:
                self._logger.warning(
                    "market_intel_mcp_fetch_failed",
                    vertical=vertical_slug,
                    error=str(e),
                )

        # ------------------------------------------------------------------
        # Phase 1.5: KnowledgeMCPServer — analytical frameworks from books
        # PORTER_FIVE_FORCES guides competitive analysis structure;
        # RACE_FRAMEWORK guides GTM implications output.
        # ------------------------------------------------------------------
        kb_framework_guidance = ""
        try:
            kmcp = get_knowledge_mcp()
            porter_fw = await kmcp.get_framework("PORTER_FIVE_FORCES")
            race_fw = await kmcp.get_framework("RACE_FRAMEWORK")
            porter_forces = list(
                ((porter_fw.get("content") or {}).get("forces") or {}).keys()
            )
            race_stages = list(
                ((race_fw.get("content") or {}).get("stages") or {}).keys()
            )
            parts: list[str] = []
            if porter_forces:
                parts.append(f"Porter's 5 Forces to assess: {', '.join(porter_forces[:5])}")
            if race_stages:
                parts.append(f"RACE framework stages for GTM implications: {', '.join(race_stages[:4])}")
            if parts:
                kb_framework_guidance = " | ".join(parts)
        except Exception as e:
            self._logger.debug("knowledge_mcp_porter_failed", error=str(e))

        self._has_kb_framework = bool(kb_framework_guidance)

        # ------------------------------------------------------------------
        # Phase 2: Live external API data (NewsAPI, EODHD, Perplexity)
        # ------------------------------------------------------------------

        # Gather data from all sources concurrently (they are fully independent)
        gathered_data: dict[str, Any] = {
            "news": [],
            "economic": [],
            "research": [],
            "mcp_landscape": mcp_landscape,
            "mcp_benchmarks": mcp_benchmarks,
            "mcp_articles": mcp_articles,
            "kb_framework_guidance": kb_framework_guidance,
        }
        data_sources = plan.get("data_sources", [])

        async def _fetch_news() -> list[dict[str, Any]]:
            if "newsapi" not in data_sources:
                return []
            try:
                async with asyncio.timeout(25):
                    news_result = await self._newsapi.search_market_news(
                        industry=industry, region=region, days_back=14
                    )
                return [
                    {
                        "title": article.title,
                        "description": article.description or "",
                        "source": article.source_name,
                        "url": article.url,
                        "date": article.published_at.isoformat(),
                    }
                    for article in news_result.articles[:10]
                ]
            except TimeoutError:
                self._logger.warning("api_timeout", source="news", industry=industry)
                return []
            except Exception as e:
                self._logger.warning("newsapi_fetch_failed", error=str(e))
                return []

        async def _fetch_economic() -> list[dict[str, Any]]:
            if "eodhd" not in data_sources:
                return []
            try:
                async with asyncio.timeout(25):
                    indicators = await self._eodhd.get_economic_indicators("SGP")
                return [
                    {
                        "indicator": ind.indicator,
                        "value": ind.value,
                        "period": ind.period,
                        "previous_value": ind.previous_value,
                        "change": ind.change,
                    }
                    for ind in indicators[:20]
                    if abs(ind.value) < 1_000  # Keep rate/% indicators; exclude raw GDP (>1B)
                       and ind.indicator.lower() != "unknown"
                ][:5]
            except TimeoutError:
                self._logger.warning("api_timeout", source="eodhd", region="SGP")
                return []
            except Exception as e:
                self._logger.warning("eodhd_fetch_failed", error=str(e))
                return []

        async def _fetch_research() -> tuple[Any, list[str]]:
            if "perplexity" not in data_sources:
                return [], []
            try:
                async with asyncio.timeout(25):
                    _company = plan.get("company_name", "")
                    _desc = plan.get("value_proposition", "") or plan.get("description", "")
                    if _company and _desc:
                        _topic = f"{_company}: {_desc[:200]}"
                    elif _company:
                        _topic = f"{_company} market"
                    else:
                        _topic = f"{industry} market"
                    result = await self._perplexity.research_market_with_citations(
                        topic=_topic, region=region
                    )
                return result.text, result.citations
            except TimeoutError:
                self._logger.warning("api_timeout", source="perplexity", industry=industry)
                return [], []
            except Exception as e:
                self._logger.warning("perplexity_fetch_failed", error=str(e))
                return [], []

        news, economic, (research, research_citations) = await asyncio.gather(
            _fetch_news(), _fetch_economic(), _fetch_research()
        )
        gathered_data["news"] = news
        gathered_data["economic"] = economic
        gathered_data["research"] = research
        gathered_data["research_citations"] = research_citations

        # Fetch structured competitive landscape (runs in parallel with data gather above)
        competitive_landscape = await self._fetch_competitive_landscape(
            company_name=plan.get("company_name", ""),
            product_context=(plan.get("value_proposition", "") or plan.get("description", "") or "")[:300],
            industry=industry,
            region=region,
        )
        gathered_data["competitive_landscape"] = competitive_landscape

        # Merge bus-sourced company profile into context so the synthesizer can reference it
        synthesis_context = dict(context)
        if self._company_profile:
            # Bus profile takes precedence for company-level fields
            synthesis_context = {**synthesis_context, **self._company_profile}

        # Synthesize with LLM
        return await self._synthesize_intelligence(
            industry=industry,
            region=region,
            gathered_data=gathered_data,
            context=synthesis_context,
        )

    async def _derive_service_label(self, company_name: str, raw_description: str) -> str:
        """Translate raw marketing copy into a plain service-category label.

        Prevents Perplexity from returning cloud/AI infrastructure vendors
        (AWS, Google Cloud, OpenAI) when the client is a services business.
        Returns e.g. "marketing strategy and GTM consulting services for brands".
        """
        if not raw_description:
            return "professional services"
        prompt = (
            f"In 10-15 words, describe the SERVICE this company delivers to its clients "
            f"(not the technology it uses internally).\n\n"
            f"Company: {company_name}\nDescription: {raw_description[:400]}\n\n"
            f"Focus on: what does the client receive? (e.g. 'marketing strategy consulting', "
            f"'payroll management software', 'outsourced sales operations')\n"
            f"'AI-powered' is acceptable ONLY if it IS the core differentiator. "
            f"NEVER use: 'multi-agent', 'platform', 'LLM', 'neural network', or the company name.\n"
            f"Return only the label."
        )
        try:
            messages = [
                {"role": "system", "content": "Return only the service label, nothing else."},
                {"role": "user", "content": prompt},
            ]
            label = await self._complete(messages, temperature=0, max_tokens=50)
            label = (label or "").strip().strip('"').strip("'")
            if label and len(label) > 8:
                return label
        except Exception:
            pass
        return "professional services"

    async def _fetch_competitive_landscape(
        self,
        company_name: str,
        product_context: str,
        industry: str,
        region: str,
    ) -> list[dict[str, Any]]:
        """Fetch a structured ranked competitive landscape via Perplexity.

        Produces a ranked list of top competitors similar to a market research
        report (e.g. "Top 20 Global Advertising Agencies") but specific to the
        client's product category. Each entry has: rank, name, HQ, size_signal,
        strategic_focus, key_weakness, relevance_to_client.

        This is the "intelligence" differentiator vs a generic ChatGPT summary.
        """
        if not self._perplexity.is_configured or not product_context:
            return []

        # Derive service category label before querying.
        # Raw product_context is often tech-focused marketing copy which causes Perplexity
        # to return cloud providers (AWS, Google Cloud) instead of actual service competitors.
        service_label = await self._derive_service_label(company_name, product_context)

        query = (
            f"List the top 15 companies that provide '{service_label}' in Singapore and APAC. "
            f"Focus on direct competitors and close alternatives (NOT infrastructure/cloud providers "
            f"unless they directly offer this service). "
            f"For each company provide: rank (1-15), company name, headquarters country, "
            f"approximate employee count or revenue size, their main strategic focus/positioning, "
            f"one key weakness or gap, and whether they are a direct competitor, adjacent player, "
            f"or potential customer/partner of '{company_name}'. "
            f"Format: numbered list with structured entries."
        )
        try:
            async with asyncio.timeout(30):
                result = await self._perplexity.research_market_with_citations(
                    topic=query,
                    region=region,
                )
            if not result or not result.text:
                return []

            # Parse the ranked list into structured entries using LLM
            parse_prompt = f"""Extract companies from this competitive landscape text and return a JSON array.

Text:
{result.text[:3000]}

Return a JSON array of objects, each with:
- "rank": integer (1-based)
- "name": company name
- "hq": headquarters country/city
- "size_signal": revenue or employee count as string (e.g. "$2B revenue", "500 employees")
- "strategic_focus": one sentence on their main positioning
- "key_weakness": one sentence on their main gap or weakness
- "relevance": "competitor" | "adjacent" | "potential_customer"

Return only the JSON array, no markdown."""

            messages = [
                {"role": "system", "content": "Return only valid JSON array. No markdown."},
                {"role": "user", "content": parse_prompt},
            ]
            import json
            import re as _re_local
            raw = await self._complete(messages, temperature=0, max_tokens=2000)
            cleaned = _re_local.sub(r"```[a-zA-Z]*\n?", "", raw or "").strip()
            entries = json.loads(cleaned)
            if isinstance(entries, list):
                return entries[:15]
        except Exception as e:
            self._logger.debug("competitive_landscape_fetch_failed", error=str(e))
        return []

    async def _synthesize_intelligence(
        self,
        industry: str,
        region: str,
        gathered_data: dict[str, Any],
        context: dict[str, Any],
    ) -> MarketIntelligenceOutput:
        """Synthesize gathered data into market intelligence."""
        # Build synthesis prompt with real data
        data_summary = []

        # Enriched company profile from bus (injected via synthesis_context by _do())
        if self._company_profile:
            profile_lines = [
                f"- Company: {self._company_profile.get('company_name', 'N/A')}",
                f"- Industry: {self._company_profile.get('industry', '')}",
                f"- Vertical: {self._company_profile.get('vertical', '')}",
                f"- Target market: {self._company_profile.get('target_market', '')}",
                f"- Geography: {self._company_profile.get('geography', '')}",
            ]
            data_summary.append(
                "A2A Company Profile (from GTM Strategist):\n"
                + "\n".join(
                    line for line in profile_lines if line.split(": ", 1)[-1].strip()
                )
            )

        # MCP vertical landscape (DB-backed structured data)
        mcp_landscape: dict[str, Any] = gathered_data.get("mcp_landscape") or {}
        mcp_benchmarks: dict[str, Any] = gathered_data.get("mcp_benchmarks") or {}
        mcp_articles: list[dict[str, Any]] = gathered_data.get("mcp_articles") or []

        if mcp_landscape:
            landscape_lines = [
                f"- Listed companies: {mcp_landscape.get('listed_companies_count', 'N/A')}",
                f"- Total market cap (SGD): {mcp_landscape.get('market_cap_total_sgd', 'N/A')}",
            ]
            top_signals = mcp_landscape.get("top_signals", [])
            if top_signals:
                landscape_lines.append(
                    "- Recent signals: " + "; ".join(str(s) for s in top_signals[:3])
                )
            data_summary.append(
                "DB Vertical Landscape:\n" + "\n".join(landscape_lines)
            )

        if mcp_benchmarks:
            data_summary.append(
                f"DB Vertical Benchmarks (percentile distributions):\n{mcp_benchmarks}"
            )

        if mcp_articles:
            article_lines = []
            for art in mcp_articles[:5]:
                if isinstance(art, dict):
                    title = art.get("title") or art.get("headline") or str(art)
                    article_lines.append(f"- {title}")
            if article_lines:
                data_summary.append(
                    "DB Stored Articles (semantic search):\n" + "\n".join(article_lines)
                )

        if gathered_data.get("news"):
            news_lines = []
            for n in gathered_data["news"][:5]:
                line = f"- {n['title']}"
                if n.get("description"):
                    line += f": {n['description']}"
                line += f" ({n['source']}, {n.get('date', '')[:10]})"
                news_lines.append(line)
            data_summary.append("Recent News:\n" + "\n".join(news_lines))

        if gathered_data.get("economic"):
            econ_lines = []
            for e in gathered_data["economic"]:
                line = f"- {e['indicator']}: {e['value']} ({e['period']})"
                if e.get("change") is not None:
                    direction = "▲" if e["change"] >= 0 else "▼"
                    line += f" {direction}{abs(e['change']):.2f} vs prior"
                econ_lines.append(line)
            data_summary.append("Economic Indicators:\n" + "\n".join(econ_lines))

        if gathered_data.get("research"):
            data_summary.append(f"Research Insights:\n{gathered_data['research']}")

        kb_framework_guidance: str = gathered_data.get("kb_framework_guidance", "")

        framework_suffix = (
            f"\n\nAnalytical framework: {kb_framework_guidance}"
            if kb_framework_guidance
            else ""
        )

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""{_knowledge_header}Synthesize this real market data into a comprehensive intelligence report:

Industry: {industry}
Region: {region}
Company Context: {context.get("company_name", "Not specified")}

GATHERED DATA:
{chr(10).join(data_summary) if data_summary else "[No live data retrieved — all configured data sources were unavailable or returned no results. Note this limitation explicitly in your analysis rather than filling gaps with assumptions.]"}

Create a MarketIntelligenceOutput with:
1. Market summary: include size estimate (SGD) and CAGR ONLY if the gathered data contains these figures — otherwise write "Market size data not available from current sources"
2. Key trends: extract as many as evidenced by the gathered data (aim for 3 if data allows); each MUST cite a specific headline or indicator from above — do NOT invent trends
3. Opportunities: identify what the data explicitly suggests (aim for 2 if data allows); market_size_estimate and growth_rate fields should be "N/A - no data" if not in the gathered data
4. Threats: extract from gathered data; aim for 2 concrete threats (regulatory, competitive, macro) — note if data is insufficient
5. GTM implications: 3-5 specific actions within 90 days, each citing a specific data point from the GATHERED DATA above. If the gathered data contains no actionable signals, write a single item: "Insufficient market data to recommend GTM actions — ensure NewsAPI, Perplexity, and EODHD are configured." Do NOT invent implications from general industry knowledge.
6. Economic context: reference the indicator data with directional commentary (▲/▼ vs prior period where available)

Cite specific headlines, indicators, or data points from GATHERED DATA as evidence for each claim.
CRITICAL: Do NOT fabricate statistics, market sizes, or growth rates not present in the gathered data.
Where relevant, reference MAS regulations, PSG/EDG grants, or SGX dynamics.{framework_suffix}""",
            },
        ]

        result = await self._complete_structured(
            response_model=MarketIntelligenceOutput,
            messages=messages,
        )

        # Add news to result
        result.recent_news = gathered_data.get("news", [])[:5]
        result.economic_indicators = gathered_data.get("economic", [])

        # Attach MCP-sourced structured data
        result.vertical_landscape = mcp_landscape or None
        result.vertical_benchmarks = mcp_benchmarks or None
        result.stored_articles = mcp_articles or None

        # Add sources — use actual citation URLs when available, fall back to provider name
        sources = []
        if mcp_landscape or mcp_benchmarks or mcp_articles:
            sources.append("MarketIntel DB")
        if gathered_data.get("news"):
            sources.append("NewsAPI")
        if gathered_data.get("economic"):
            sources.append("EODHD")
        research_citations: list[str] = gathered_data.get("research_citations") or []
        if gathered_data.get("research"):
            sources.extend(research_citations if research_citations else ["Perplexity AI"])
        result.sources = sources

        # Populate data provenance fields
        result.data_sources_used = [s for s in sources if not s.startswith("http")]
        # is_live_data: only real-time APIs count (NewsAPI/EODHD/Perplexity < 24h freshness).
        # KB data (mcp_landscape, mcp_benchmarks, mcp_articles) is daily-synced — not live.
        result.is_live_data = bool(
            gathered_data.get("news")
            or gathered_data.get("economic")
            or gathered_data.get("research")
        )

        # Produce a structured competitive landscape MarketInsight
        landscape = gathered_data.get("competitive_landscape", [])
        if landscape:
            # Format ranked entries like a market research report
            formatted_entries = []
            for entry in landscape[:15]:
                rank = entry.get("rank", "?")
                name = entry.get("name", "Unknown")
                hq = entry.get("hq", "")
                size = entry.get("size_signal", "")
                focus = entry.get("strategic_focus", "")
                weakness = entry.get("key_weakness", "")
                relevance = entry.get("relevance", "")
                line = f"{rank}. {name}"
                if hq:
                    line += f" ({hq})"
                if size:
                    line += f" — {size}"
                if focus:
                    line += f". Strategy: {focus}"
                if weakness:
                    line += f" Gap: {weakness}"
                if relevance:
                    line += f" [{relevance}]"
                formatted_entries.append(line)

            competitors_count = len([e for e in landscape if e.get("relevance") == "competitor"])
            adjacent_count = len([e for e in landscape if e.get("relevance") == "adjacent"])
            customers_count = len([e for e in landscape if e.get("relevance") == "potential_customer"])

            landscape_insight = MarketInsight(
                title=f"Competitive Landscape — Top {len(landscape)} Players",
                summary=(
                    f"Ranked market map: {competitors_count} direct competitors, "
                    f"{adjacent_count} adjacent players, {customers_count} potential customers identified. "
                    f"Top player: {landscape[0].get('name', 'N/A')} ({landscape[0].get('hq', '')})."
                ),
                category="competitive_landscape",
                key_findings=formatted_entries,
                implications=[
                    f"Direct competitors to differentiate from: {', '.join(e.get('name','') for e in landscape if e.get('relevance')=='competitor')[:200]}",
                    f"Potential customers to target: {', '.join(e.get('name','') for e in landscape if e.get('relevance')=='potential_customer')[:200]}",
                ] if landscape else [],
                recommendations=[
                    f"Focus differentiation on gaps vs {landscape[0].get('name', 'top competitor')}: {landscape[0].get('key_weakness', 'N/A')}"
                ] if landscape else [],
                sources=["Perplexity Research"],
                confidence=0.75,
                relevant_to_company=True,
            )
            # Insert at position 0 so it appears first in the results
            result.insights.insert(0, landscape_insight)

        return result

    async def _check(self, result: MarketIntelligenceOutput) -> float:
        """Validate market intelligence quality."""
        score = 0.0

        # Check data presence
        if result.market_summary and len(result.market_summary) > 100:
            score += 0.2

        # Check trends
        if result.key_trends:
            score += 0.15
            # Quality check - trends should have evidence
            with_evidence = sum(1 for t in result.key_trends if t.evidence)
            if with_evidence >= 2:
                score += 0.1

        # Check opportunities
        if result.opportunities:
            score += 0.15
            # Quality check - opportunities should have recommendations
            with_recs = sum(1 for o in result.opportunities if o.recommended_action)
            if with_recs >= 2:
                score += 0.1

        # Check GTM implications
        if result.implications_for_gtm:
            score += 0.15

        # Check data sources
        if result.sources:
            score += 0.05 * len(result.sources)

        # Check news and economic data
        if result.recent_news:
            score += 0.05
        if result.economic_indicators:
            score += 0.05

        # MCP DB enrichment bonus (+0.05 per non-empty MCP result, capped together at +0.10)
        mcp_boost = 0.0
        if result.vertical_landscape:
            mcp_boost += 0.05
        if result.vertical_benchmarks:
            mcp_boost += 0.05
        if result.stored_articles:
            mcp_boost += 0.05
        score += min(mcp_boost, 0.10)

        # Knowledge MCP framework guidance bonus (+0.03 when Porter/RACE frameworks were loaded)
        if getattr(self, "_has_kb_framework", False):
            score += 0.03

        return min(score, 0.95)

    async def _act(
        self, result: MarketIntelligenceOutput, confidence: float
    ) -> MarketIntelligenceOutput:
        """Stamp confidence and publish trends/opportunities to AgentBus."""
        result.confidence = confidence

        # Persist market trends as public research (market-level, not company-specific)
        if result.key_trends:
            for trend in result.key_trends[:5]:
                title = trend.name
                if title:
                    asyncio.create_task(persist_research(
                        source="market_intelligence",
                        query=f"Singapore market trend: {title[:200]}",
                        content=str(trend.model_dump()),
                        vertical_slug=getattr(self, "_vertical_slug", None),
                        analysis_id=self._analysis_id,
                        is_public=True,  # Market trends are generic, not company-specific
                    ))

        if self._agent_bus is None:
            return result

        # Publish each key trend so CustomerProfiler and CampaignArchitect can consume it
        for trend in result.key_trends:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.MARKET_TREND,
                    title=trend.name,
                    content={
                        "name": trend.name,
                        "description": trend.description,
                        "relevance": trend.relevance,
                        "evidence": trend.evidence,
                        "impact_score": trend.impact_score,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.warning("bus_publish_trend_failed", trend=trend.name, error=str(e))

        # Publish each opportunity so downstream agents can act on high-value openings
        for opp in result.opportunities:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.MARKET_OPPORTUNITY,
                    title=opp.title,
                    content={
                        "title": opp.title,
                        "description": opp.description,
                        "market_size_estimate": opp.market_size_estimate,
                        "growth_rate": opp.growth_rate,
                        "competitive_intensity": opp.competitive_intensity,
                        "time_sensitivity": opp.time_sensitivity,
                        "recommended_action": opp.recommended_action,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.warning(
                    "bus_publish_opportunity_failed", opportunity=opp.title, error=str(e)
                )

        self._logger.info(
            "market_intel_published_to_bus",
            trends=len(result.key_trends),
            opportunities=len(result.opportunities),
            analysis_id=str(self._analysis_id),
        )
        return result

    async def research_industry(
        self,
        industry: IndustryVertical,
        region: str = "Singapore",
        focus_areas: list[str] | None = None,
    ) -> MarketIntelligenceOutput:
        """Research a specific industry.

        Convenience method for direct industry research.

        Args:
            industry: Industry to research
            region: Geographic region
            focus_areas: Specific areas to focus on

        Returns:
            Market intelligence report
        """
        task = f"Research {industry.value} market in {region}"
        context = {
            "industry": industry.value,
            "region": region,
            "focus_areas": focus_areas or [],
        }
        return await self.run(task, context=context)
