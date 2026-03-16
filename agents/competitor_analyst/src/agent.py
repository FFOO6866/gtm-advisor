"""Competitor Analyst Agent - Real competitive intelligence.

Uses Perplexity for real-time competitor research and EODHD for financial data.
Subscribes to COMPETITOR_FOUND discoveries from other agents for dynamic analysis.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from agents.core.src.mcp_integration import AgentMCPClient
from packages.core.src.agent_bus import (
    AgentBus,
    AgentMessage,
    DiscoveryType,
    get_agent_bus,
)
from packages.core.src.types import CompetitorAnalysis
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.integrations.eodhd.src import get_eodhd_client
from packages.integrations.newsapi.src import get_newsapi_client
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.knowledge.src.research_persist import persist_research
from packages.llm.src import get_llm_manager
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer

# Stop-words stripped before building ACRA search terms from the service category.
# Filters both English stop-words and marketing/tech buzzwords that don't appear
# in Singapore SSIC industry descriptions.
_ACRA_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "as", "at", "by", "for", "in", "of", "or", "the",
        "to", "with",
        # tech / marketing buzzwords that won't match SSIC text
        "ai", "ai-powered", "ai-driven", "cloud", "cloud-based", "digital",
        "innovative", "integrated", "intelligent", "smart", "platform",
        "solutions", "service", "services", "powered", "driven", "based",
    }
)

# Generic company-name suffixes stripped when comparing EODHD search results.
# Prevents the name-similarity guard from being vacuously false when query or
# result names consist entirely of generic words (e.g. "Group Holdings Pte Ltd").
_EODHD_GENERIC_WORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "of", "and", "inc", "pte", "ltd", "limited",
        "group", "holdings", "corp", "co", "llc", "plc", "sa", "ag",
        "bv", "nv", "gmbh", "sdn", "bhd",
    }
)


class CompetitivePositioning(BaseModel):
    """Your positioning vs competitors."""

    your_differentiators: list[str] = Field(default_factory=list)
    competitor_advantages: list[str] = Field(default_factory=list)
    market_gaps: list[str] = Field(default_factory=list)
    recommended_positioning: str = Field(default="")


class CompetitorIntelOutput(BaseModel):
    """Complete competitor intelligence report."""

    competitors: list[CompetitorAnalysis] = Field(default_factory=list)
    market_landscape: str = Field(default="")
    competitive_positioning: CompetitivePositioning = Field(default_factory=CompetitivePositioning)
    strategic_recommendations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=False)  # True only if Perplexity OR EODHD returned data


class CompetitorAnalystAgent(BaseGTMAgent[CompetitorIntelOutput]):
    """Competitor Analyst - Real competitive intelligence.

    Researches actual competitors using:
    - Perplexity for real-time company research
    - EODHD for public company financials
    - Web research for product/pricing info

    A2A Integration:
    - Subscribes to COMPETITOR_FOUND discoveries from CompanyEnricher
    - Dynamically adds discovered competitors to analysis
    - Publishes COMPETITOR_WEAKNESS discoveries for other agents
    """

    def __init__(
        self,
        agent_bus: AgentBus | None = None,
        analysis_id: UUID | None = None,
    ) -> None:
        super().__init__(
            name="competitor-analyst",
            description=(
                "Provides real competitive intelligence using live data. "
                "Analyzes competitor strengths, weaknesses, and positioning "
                "to help you differentiate effectively."
            ),
            result_type=CompetitorIntelOutput,
            min_confidence=0.50,  # LLM-only path (no MCP data) peaks at 0.65; real-data path can reach 0.95
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="competitor-research",
                    description="Research competitor companies",
                ),
                AgentCapability(
                    name="swot-analysis",
                    description="SWOT analysis of competitors",
                ),
                AgentCapability(
                    name="positioning-analysis",
                    description="Analyze market positioning",
                ),
                AgentCapability(
                    name="a2a-discovery",
                    description="React to competitor discoveries from other agents",
                ),
            ],
        )

        self._perplexity = get_llm_manager().perplexity
        self._eodhd = get_eodhd_client()
        self._newsapi = get_newsapi_client()
        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id = analysis_id
        self._discovered_competitors: list[str] = []
        self._mcp = AgentMCPClient()
        # Tracks which competitors had real MCP facts fetched (set during _do)
        self._competitors_with_real_data: set[str] = set()
        # Porter's Five Forces framework from KB (populated during _do)
        self._porter_framework: dict | None = None
        # Vertical slug resolved during _do() and forwarded to persist_research()
        self._vertical_slug: str = ""

        # Subscribe to competitor discoveries
        self._subscribe_to_discoveries()

    def _subscribe_to_discoveries(self) -> None:
        """Subscribe to relevant discovery types from other agents."""
        self._agent_bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.COMPETITOR_FOUND,
            handler=self._on_competitor_discovered,
        )

        # Also subscribe to company profile for context
        self._agent_bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.COMPANY_PROFILE,
            handler=self._on_company_profile,
        )

    async def _on_competitor_discovered(self, message: AgentMessage) -> None:
        """Handle competitor discovery from another agent."""
        # Scope to current analysis to prevent cross-analysis contamination
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        competitor_name = message.content.get("competitor_name")
        if competitor_name and competitor_name not in self._discovered_competitors:
            self._discovered_competitors.append(competitor_name)
            self._logger.info(
                "competitor_discovered_via_a2a",
                competitor=competitor_name,
                from_agent=message.from_agent,
            )

    async def _on_company_profile(self, message: AgentMessage) -> None:
        """Handle company profile discovery for context enrichment."""
        self._logger.debug(
            "company_profile_received",
            company=message.content.get("company_name"),
            from_agent=message.from_agent,
        )

    def set_analysis_id(self, analysis_id: UUID) -> None:
        """Set the current analysis ID."""
        self._analysis_id = analysis_id

    def get_discovered_competitors(self) -> list[str]:
        """Get competitors discovered via A2A communication."""
        return self._discovered_competitors.copy()

    def clear_discovered_competitors(self) -> None:
        """Clear discovered competitors (call between analyses)."""
        self._discovered_competitors.clear()

    def get_system_prompt(self) -> str:
        return """You are the Competitor Analyst, specializing in competitive intelligence for Singapore/APAC markets.

You provide DATA-DRIVEN competitor analysis, not generic SWOT templates. You:
1. Research real competitors with actual data
2. Identify specific strengths and weaknesses
3. Analyze pricing and positioning
4. Find actionable differentiation opportunities

Be specific - cite real products, features, pricing, recent news.
Focus on Singapore/APAC competitors when relevant."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}

        # Load domain knowledge pack — injected into _do() synthesis prompt.
        kmcp_pack = get_knowledge_mcp()
        self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
            agent_name="competitor-analyst",
            task_context=task,
        )

        # Update analysis_id from context to gate A2A subscription filtering
        if context.get("analysis_id"):
            self._analysis_id = context["analysis_id"]
        # Snapshot A2A competitors that arrived before _plan() (from this analysis via callbacks),
        # then clear the list so the next iteration starts fresh without cross-analysis bleed.
        a2a_snapshot = list(self._discovered_competitors)
        self._discovered_competitors.clear()

        competitors = context.get("known_competitors", [])
        industry = context.get("industry", "technology")

        # Merge in competitors discovered via A2A communication
        all_competitors = list(set(competitors + a2a_snapshot))

        self._logger.info(
            "planning_competitor_analysis",
            known_competitors=len(competitors),
            discovered_competitors=len(a2a_snapshot),
            total_competitors=len(all_competitors),
        )

        description = context.get("description", "")
        value_proposition = context.get("value_proposition", "")
        company_name = context.get("company_name", "")
        raw_context = (value_proposition or description or "")[:500]

        # Derive a service-category label FROM THE CLIENT'S PERSPECTIVE.
        # Raw value_proposition is often technology-focused marketing copy
        # ("AI-native multi-agent platform for strategic empowerment") which
        # makes Perplexity return cloud providers (AWS, Google Cloud) instead
        # of real service competitors (marketing agencies, GTM consultancies).
        # The label must describe WHAT is delivered to clients, not HOW.
        service_category = await self._derive_service_category(
            company_name=company_name,
            raw_description=raw_context,
            industry=industry,
        )

        return {
            "known_competitors": all_competitors,
            "industry": industry,
            "company_name": company_name,
            "product_context": raw_context[:150],
            "service_category": service_category,
            "research_queries": [
                f"{comp} company analysis products pricing" for comp in all_competitors[:5]
            ]
            + [f"top {industry} competitors Singapore"],
            "discovered_via_a2a": a2a_snapshot,
        }

    async def _derive_service_category(
        self,
        company_name: str,
        raw_description: str,
        industry: str,
    ) -> str:
        """Return a concise service-category label for competitor search.

        Transforms technology-laden marketing copy into a plain description of
        WHAT the company delivers to clients, e.g.:
          "AI-powered marketing and GTM consulting services for brands and SMEs"
        rather than:
          "AI-native multi-agent platform for strategic empowerment"

        This prevents Perplexity from returning cloud/AI tool vendors (AWS,
        Google Cloud, OpenAI) when the client is a services company.
        """
        if not raw_description:
            return industry.replace("_", " ")

        prompt = (
            f"You are a business analyst. Based on the description below, write a single "
            f"sentence (max 20 words) describing WHAT this company does FROM THE CLIENT'S "
            f"PERSPECTIVE — the service they receive, not the internal technology used.\n\n"
            f"Company: {company_name}\n"
            f"Description: {raw_description[:400]}\n\n"
            f"Rules:\n"
            f"- Describe the CLIENT-FACING SERVICE (e.g. 'marketing strategy consulting', "
            f"'payroll management software', 'digital transformation advisory')\n"
            f"- 'AI-powered' is acceptable ONLY if it IS the core product differentiator. "
            f"Do NOT use it just because the company uses AI internally.\n"
            f"- NEVER use architecture terms: 'multi-agent', 'LLM', 'neural network', 'platform'\n"
            f"- Do NOT mention the company name\n"
            f"- Start with the service noun\n\n"
            f"Return only the sentence, nothing else."
        )
        try:
            messages = [
                {"role": "system", "content": "Return only the service description sentence."},
                {"role": "user", "content": prompt},
            ]
            label = await self._complete(messages, temperature=0, max_tokens=60)
            label = (label or "").strip().strip('"').strip("'")
            if label and len(label) > 10:
                self._logger.info("service_category_derived", label=label)
                return label
        except Exception as e:
            self._logger.debug("service_category_derivation_failed", error=str(e))
        return industry.replace("_", " ")

    async def _fetch_competitor_mcp(
        self,
        competitor: str,
    ) -> tuple[str, list[Any]]:
        """Fetch MCP facts for one competitor concurrently."""
        async def _safe(coro: Any) -> list[Any]:
            try:
                async with asyncio.timeout(10):
                    return await coro
            except Exception:
                return []

        results = await asyncio.gather(
            _safe(self._mcp.search(competitor)),
            _safe(self._mcp.get_company_info(competitor)),
        )
        facts: list[Any] = []
        for r in results:
            facts.extend(r)
        return competitor, facts

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CompetitorIntelOutput:
        context = context or {}
        competitors_data: list[CompetitorAnalysis] = []
        real_data: dict[str, Any] = {}
        sources: set[str] = set()

        # Reset tracking for this run
        self._competitors_with_real_data = set()
        self._porter_framework = None
        self._kb_financial_benchmarks: dict[str, dict] = {}

        known = plan.get("known_competitors", [])[:5]

        # --- Phase 0a: KnowledgeMCPServer — Porter's Five Forces framework ---
        # Fetch before any external calls so the framework can ground the LLM analysis.
        try:
            kmcp = get_knowledge_mcp()
            porter_fw = await kmcp.get_framework("PORTER_FIVE_FORCES")
            if not porter_fw.get("error"):
                self._porter_framework = porter_fw
        except Exception as _e:
            self._logger.debug("knowledge_mcp_porter_failed", error=str(_e))

        # --- Phase 0: KB-first — query Market Intelligence DB for listed competitors ---
        # Uses the vertical landscape to surface SGX-listed companies in the same
        # vertical and stored articles for each competitor. Runs before any external
        # API calls so the KB data can ground subsequent Perplexity research.
        kb_competitor_articles: dict[str, list[dict]] = {}  # name → article list
        kb_sources: set[str] = set()
        try:
            industry = plan.get("industry", "")
            # Map industry keyword to vertical slug via shared utility (best-effort; "" on no match)
            vertical_slug = detect_vertical_slug(f"{industry} {context.get('description', '')}") or ""
            # Store for persist_research() in _act()
            self._vertical_slug = vertical_slug
            async with async_session_factory() as db:
                mcp = MarketIntelMCPServer(session=db)

                # Get vertical landscape — leaders/laggards are KB-verified competitors
                if vertical_slug:
                    landscape = await mcp.get_vertical_landscape(vertical_slug)
                    if landscape:
                        kb_sources.add("MarketIntel DB")
                        kb_names = [
                            c.get("name", "") for c in (
                                landscape.get("leaders", []) + landscape.get("laggards", [])
                            ) if c.get("name")
                        ]
                        # Merge KB names into known, cap at 8 total to stay manageable
                        all_names = list(dict.fromkeys(known + kb_names))
                        known = all_names[:8]

                # Pull stored articles for each known competitor
                for comp_name in known[:5]:
                    articles = await mcp.search_market_intelligence(
                        query=comp_name, vertical_slug=vertical_slug or None
                    )
                    if articles:
                        kb_competitor_articles[comp_name] = articles
                        kb_sources.add("MarketIntel DB")
        except Exception as e:
            self._logger.debug("kb_phase0_failed", error=str(e))

        # --- Step 1: If no named competitors, discover via Perplexity using service category ---
        if not known:
            industry = plan.get("industry", "technology")
            # Use the LLM-derived service category (not raw marketing copy, not company name).
            # service_category = "Marketing strategy and GTM execution services for brands"
            # → finds marketing agencies, GTM consultancies, growth firms (correct!)
            # raw product_context = "AI-native multi-agent platform for strategic empowerment"
            # → finds AWS, Google Cloud, OpenAI (wrong!)
            service_category = plan.get("service_category") or industry
            discovery_topic = (
                f"top Singapore companies that provide {service_category}. "
                f"List their names, focus, and key differentiators."
            )
            try:
                discovery_research = await self._perplexity.research_market(
                    topic=discovery_topic, region="Singapore"
                )
                # Extract competitor names by parsing the discovery text with LLM.
                # Be explicit that we want COMPETITORS/ALTERNATIVES, not tangentially
                # mentioned companies (avoids picking up investors, clients, tools, etc.).
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Extract up to 5 DIRECT COMPETITOR or CLOSE ALTERNATIVE company names "
                            "from this market research text. Only include companies that offer "
                            "similar products or services — not investors, clients, or unrelated "
                            "tool vendors. Return only a JSON array of company name strings."
                        ),
                    },
                    {"role": "user", "content": discovery_research[:2000] if isinstance(discovery_research, str) else str(discovery_research)[:2000]},
                ]
                try:
                    raw = await self._complete(messages, temperature=0, max_tokens=200)
                    # Strip markdown code fences the model sometimes wraps around JSON
                    cleaned = re.sub(r"```[a-zA-Z]*\n?", "", raw).strip() if isinstance(raw, str) else ""
                    names = json.loads(cleaned) if cleaned else []
                    if isinstance(names, list):
                        known = [str(n) for n in names[:5] if n]
                        self._logger.info("discovered_competitors", count=len(known), names=known)
                except Exception as e:
                    self._logger.warning("competitor_discovery_parse_failed", error=str(e))
            except Exception as e:
                self._logger.warning("competitor_discovery_failed", error=str(e))

        # --- Step 1b: ACRA discovery — locally registered Singapore competitors ---
        # Always runs (not just when Perplexity returned nothing) to supplement
        # with government-verified registrations in the same service category.
        # Extract content words from service_category to build the ACRA query;
        # stops words and tech buzzwords are stripped so SSIC descriptions match.
        _svc = plan.get("service_category") or plan.get("industry", "")
        _acra_words = [
            w for w in _svc.lower().split() if w not in _ACRA_STOP_WORDS and len(w) > 2
        ]
        _acra_keyword = " ".join(_acra_words[:4])  # first 4 meaningful words
        if _acra_keyword:
            try:
                async with asyncio.timeout(15):
                    acra_names = await self._mcp.discover_local_companies(
                        keyword=_acra_keyword,
                        exclude_name=plan.get("company_name", ""),
                        limit=6,
                    )
                known_lower = {k.lower() for k in known}
                added = 0
                for name in acra_names:
                    if name.lower() not in known_lower and len(known) < 8:
                        known.append(name)
                        known_lower.add(name.lower())
                        added += 1
                if added:
                    sources.add("ACRA")
                    self._logger.info(
                        "acra_discovery_added",
                        keyword=_acra_keyword,
                        added=added,
                        total_known=len(known),
                    )
            except Exception as _e:
                self._logger.debug("acra_discovery_failed", error=str(_e))

        # --- Step 1c: Publish COMPETITOR_FOUND for newly-discovered competitors ---
        # "New" = not in the original plan input list; discovered via Perplexity or KB.
        original_known: set[str] = {c.lower() for c in plan.get("known_competitors", [])}
        industry = plan.get("industry", "")
        for competitor_name in known:
            if competitor_name.lower() not in original_known:
                try:
                    await self._agent_bus.publish(
                        from_agent=self.name,
                        discovery_type=DiscoveryType.COMPETITOR_FOUND,
                        title=f"Competitor discovered: {competitor_name}",
                        content={
                            "name": competitor_name,          # matches signature spec
                            "competitor_name": competitor_name,  # kept for _on_competitor_discovered()
                            "domain": None,
                            "industry": industry,
                            "discovery_source": "perplexity_or_acra_or_market_intel_mcp",
                            "analysis_id": str(self._analysis_id) if self._analysis_id else None,
                        },
                        confidence=0.75,
                        analysis_id=self._analysis_id,
                    )
                except Exception as _publish_err:
                    self._logger.debug(
                        "competitor_found_publish_failed",
                        competitor=competitor_name,
                        error=str(_publish_err),
                    )

        # --- Steps 2 + 3: MCP and Perplexity run in parallel (both only need `known`) ---
        mcp_tasks = [self._fetch_competitor_mcp(c) for c in known]
        perplexity_tasks = [self._perplexity.research_company_with_citations(c) for c in known]

        (mcp_results, perplexity_results) = await asyncio.gather(
            asyncio.gather(*mcp_tasks, return_exceptions=True),
            asyncio.gather(*perplexity_tasks, return_exceptions=True),
        )

        for res in mcp_results:
            if isinstance(res, Exception):
                continue
            competitor, facts = res
            if facts:
                self._competitors_with_real_data.add(competitor)
                real_data[competitor] = self._mcp.summarize_facts(facts)
                for fact in facts:
                    if getattr(fact, "source_name", None):
                        sources.add(fact.source_name)

        # Filter to successful results, then parse all concurrently; log any Perplexity failures
        # valid_pairs: (competitor_name, research_text, citation_urls)
        valid_pairs: list[tuple[str, str, list[str]]] = []
        all_perplexity_citations: list[str] = []
        for competitor, research in zip(known, perplexity_results, strict=True):
            if isinstance(research, Exception):
                self._logger.warning(
                    "perplexity_research_failed", competitor=competitor, error=str(research)
                )
            else:
                valid_pairs.append((competitor, research.text, research.citations or []))
                all_perplexity_citations.extend(research.citations or [])
        if valid_pairs:
            parse_results = await asyncio.gather(*[
                self._parse_competitor(c, r, context) for c, r, _ in valid_pairs
            ], return_exceptions=True)
            for (competitor, _, citations), result in zip(valid_pairs, parse_results, strict=True):
                if isinstance(result, Exception):
                    self._logger.warning("competitor_parse_failed", competitor=competitor, error=str(result))
                elif result is not None:
                    result.sources = citations  # Per-competitor citation URLs
                    competitors_data.append(result)

        # --- Step 3b: EODHD enrichment — local (SGX) + major global exchanges ---
        # Try exchanges in priority order: Singapore first, then US, HK, AU, London.
        # Stop at the first exchange where the company is found to avoid false
        # positives from unrelated companies sharing a similar name.
        _EODHD_EXCHANGES = ["SG", "US", "HKEX", "AU", "LSE"]

        eodhd_enrichments: dict[str, dict] = {}  # comp_name → non-None financial fields
        if self._eodhd.is_configured and known:
            async def _enrich_one_eodhd(comp_name: str) -> tuple[str, dict]:
                """Search SG then major global exchanges; return first match."""
                # Strip generic suffixes from query so "DBS Group" → {"dbs"}.
                # Guard is skipped when either side has no meaningful words.
                query_meaningful = set(comp_name.lower().split()) - _EODHD_GENERIC_WORDS
                for exchange in _EODHD_EXCHANGES:
                    try:
                        hits = await self._eodhd.search_companies(
                            query=comp_name, exchange=exchange, limit=2
                        )
                        if not hits:
                            continue
                        hit = hits[0]
                        ticker = hit.get("Code") or hit.get("code") or ""
                        if not ticker:
                            continue
                        # Light name-similarity guard: at least one meaningful word
                        # from the query must appear in the result name, to prevent
                        # matching "Ogilvy" to an unrelated "Ogilvy Roofing Inc" on
                        # a different exchange.  Guard is skipped when either the
                        # query or the result name contains no meaningful words
                        # (avoids rejecting companies with purely generic names).
                        result_name = (hit.get("Name") or "").lower()
                        result_meaningful = set(result_name.split()) - _EODHD_GENERIC_WORDS
                        if query_meaningful and result_meaningful and not (
                            query_meaningful & result_meaningful
                        ):
                            continue
                        fundamentals = await self._eodhd.get_company_fundamentals(
                            ticker, exchange=exchange
                        )
                        if fundamentals is None:
                            continue
                        enrichment: dict = {}
                        if fundamentals.revenue is not None:
                            enrichment["revenue"] = fundamentals.revenue
                        if fundamentals.employees is not None:
                            enrichment["employees"] = fundamentals.employees
                        if fundamentals.market_cap is not None:
                            enrichment["market_cap"] = fundamentals.market_cap
                        if enrichment:
                            enrichment["ticker"] = ticker
                            enrichment["exchange"] = exchange
                        return comp_name, enrichment
                    except Exception as exc:
                        self._logger.debug(
                            "eodhd_enrichment_failed",
                            competitor=comp_name,
                            exchange=exchange,
                            error=str(exc),
                        )
                return comp_name, {}

            eodhd_tasks = [_enrich_one_eodhd(c) for c in known[:5]]
            eodhd_raw_results = await asyncio.gather(*eodhd_tasks, return_exceptions=True)
            for item in eodhd_raw_results:
                if isinstance(item, Exception):
                    self._logger.debug("eodhd_gather_exception", error=str(item))
                    continue
                comp_name, enrichment = item
                if enrichment:
                    eodhd_enrichments[comp_name] = enrichment

            if eodhd_enrichments:
                sources.add("EODHD")

        # --- Step 3c: NewsAPI — recent news per competitor (last 14 days) ---
        competitor_news: dict[str, list[str]] = {}  # comp_name → list of recent headlines
        if self._newsapi.is_configured and known:
            async def _fetch_competitor_news(comp_name: str) -> tuple[str, list[str]]:
                try:
                    async with asyncio.timeout(10):
                        result = await self._newsapi.search_market_news(
                            industry=comp_name,  # use company name as query
                            region="Singapore",
                            days_back=14,
                        )
                        articles = getattr(result, "articles", []) or []
                        headlines = [a.title for a in articles[:3] if getattr(a, "title", None)]
                        return comp_name, headlines
                except Exception as e:
                    self._logger.debug("newsapi_competitor_failed", competitor=comp_name, error=str(e))
                    return comp_name, []

            news_tasks = [_fetch_competitor_news(c) for c in known[:5]]
            news_results = await asyncio.gather(*news_tasks, return_exceptions=True)
            for res in news_results:
                if isinstance(res, Exception):
                    continue
                comp_name, headlines = res
                if headlines:
                    competitor_news[comp_name] = headlines
                    sources.add("NewsAPI")

        # --- Step 3d: KB financial benchmarks — benchmark each competitor against vertical peers ---
        kb_financial_benchmarks: dict[str, dict] = {}  # comp_name → benchmark dict
        if known:
            try:
                industry_3d = plan.get("industry", "")
                vertical_slug_3d = (
                    detect_vertical_slug(f"{industry_3d} {context.get('description', '')}") or None
                )
                async with async_session_factory() as db:
                    mcp_bench = MarketIntelMCPServer(session=db)
                    for comp_name in known[:5]:
                        try:
                            bench_result = await mcp_bench.find_and_benchmark_company_by_name(
                                name=comp_name,
                                vertical_slug=vertical_slug_3d,
                            )
                            if bench_result.get("found"):
                                kb_financial_benchmarks[comp_name] = bench_result
                        except Exception as _bench_err:
                            self._logger.debug(
                                "kb_benchmark_failed",
                                competitor=comp_name,
                                error=str(_bench_err),
                            )
            except Exception as _bench_outer_err:
                self._logger.debug("kb_benchmark_outer_failed", error=str(_bench_outer_err))

        self._kb_financial_benchmarks = kb_financial_benchmarks

        # --- Step 3e: Trajectory + GTM profile + executive intelligence ---
        # These MCP tools access EODHD time-series data that no LLM has.
        kb_trajectories: dict[str, dict] = {}  # comp_name → trajectory dict
        kb_gtm_profiles: dict[str, dict] = {}  # comp_name → GTM profile dict
        if known:
            try:
                async with async_session_factory() as db:
                    mcp_deep = MarketIntelMCPServer(session=db)
                    for comp_name in known[:5]:
                        bench = kb_financial_benchmarks.get(comp_name, {})
                        co = bench.get("company", {})
                        _ticker = co.get("ticker")
                        _exchange = co.get("exchange", "SG")
                        if _ticker:
                            try:
                                traj = await mcp_deep.get_company_trajectory(_ticker, _exchange)
                                if traj:
                                    kb_trajectories[comp_name] = traj
                            except Exception as _exc:
                                self._logger.debug("trajectory_fetch_failed", competitor=comp_name, error=str(_exc))
                            try:
                                gtm_prof = await mcp_deep.get_company_gtm_profile(_ticker, _exchange)
                                if gtm_prof:
                                    kb_gtm_profiles[comp_name] = gtm_prof
                            except Exception as _exc:
                                self._logger.debug("gtm_profile_fetch_failed", competitor=comp_name, error=str(_exc))
            except Exception as _deep_err:
                self._logger.debug("kb_deep_intel_failed", error=str(_deep_err))

        self._kb_trajectories = kb_trajectories
        self._kb_gtm_profiles = kb_gtm_profiles

        # --- Step 4: Build grounding context from real MCP data + KB articles ---

        def _format_kb_benchmark(comp_name: str) -> str:
            """Return a formatted KB financial benchmark block, or '' if not found."""
            bench = kb_financial_benchmarks.get(comp_name)
            if not bench:
                return ""
            company_info = bench.get("company", {})
            financials = bench.get("financials", {})
            benchmark_meta = bench.get("benchmark", {})
            ticker = company_info.get("ticker", "")
            metric_ranks: dict = benchmark_meta.get("metric_ranks", {})
            description: str = benchmark_meta.get("description", "")

            def _rank_label(rank: float | None) -> str:
                if rank is None:
                    return "n/a"
                pct = rank * 100
                if pct >= 90:
                    return f"P{pct:.0f} — fast-growing threat"
                if pct >= 75:
                    return f"P{pct:.0f} — above median"
                if pct >= 50:
                    return f"P{pct:.0f} — average"
                if pct >= 25:
                    return f"P{pct:.0f} — below median"
                return f"P{pct:.0f} — laggard"

            lines: list[str] = [f"KB Financial Benchmark ({ticker}):"]
            metric_display = {
                "gross_margin": "Gross margin",
                "revenue_growth_yoy": "Revenue growth YoY",
                "net_margin": "Net margin",
                "ebitda_margin": "EBITDA margin",
                "roe": "ROE",
            }
            fin_vals = {
                "gross_margin": financials.get("gross_margin"),
                "revenue_growth_yoy": financials.get("revenue_growth_yoy"),
                "net_margin": financials.get("net_margin"),
                "ebitda_margin": financials.get("ebitda_margin"),
                "roe": financials.get("roe"),
            }
            for key, label in metric_display.items():
                val = fin_vals.get(key)
                rank = metric_ranks.get(key)
                if val is not None:
                    lines.append(
                        f"- {label}: {val * 100:.1f}% ({_rank_label(rank)})"
                    )
            if description:
                lines.append(f"- Position: {description}")
            return "\n".join(lines) if len(lines) > 1 else ""

        def _format_deep_intel(comp_name: str) -> str:
            """Return trajectory + GTM profile + exec intel block, or '' if not found."""
            parts: list[str] = []
            traj = kb_trajectories.get(comp_name)
            if traj:
                tclass = traj.get("trajectory_class", "")
                narrative = traj.get("narrative", "")
                cagr = traj.get("revenue_cagr_3y")
                sga = traj.get("sga_efficiency_trend", "")
                line = f"Trajectory: {tclass}"
                if cagr is not None:
                    line += f" (3Y CAGR: {cagr*100:.1f}%)"
                if sga:
                    line += f", SG&A efficiency: {sga}"
                parts.append(line)
                if narrative:
                    parts.append(f"  {narrative[:300]}")

            gtm = kb_gtm_profiles.get(comp_name)
            if gtm and not gtm.get("error"):
                profile_parts = []
                gtm_spend = gtm.get("gtm_spend") or {}
                sga = gtm_spend.get("sga_to_revenue")
                if isinstance(sga, (int, float)):
                    profile_parts.append(f"SG&A/Rev: {sga*100:.1f}%")
                rnd = gtm_spend.get("rnd_to_revenue")
                if isinstance(rnd, (int, float)):
                    profile_parts.append(f"R&D/Rev: {rnd*100:.1f}%")
                # SG&A trend from time-series
                trend_data = gtm_spend.get("trend") or []
                if len(trend_data) >= 2:
                    curr_sga = (trend_data[0] or {}).get("sga_to_revenue")
                    prev_sga = (trend_data[1] or {}).get("sga_to_revenue")
                    if isinstance(curr_sga, (int, float)) and isinstance(prev_sga, (int, float)) and prev_sga > 0:
                        direction = "increasing" if curr_sga > prev_sga else "decreasing"
                        profile_parts.append(f"SG&A trend: {direction}")
                esg_score = (gtm.get("esg") or {}).get("total_score")
                if isinstance(esg_score, (int, float)):
                    profile_parts.append(f"ESG: {esg_score:.0f}")
                analyst_rating = (gtm.get("analyst_consensus") or {}).get("rating")
                if analyst_rating:
                    profile_parts.append(f"Analyst: {analyst_rating}")
                if profile_parts:
                    parts.append(f"GTM Profile: {', '.join(profile_parts)}")

            return "\n".join(parts) if parts else ""

        real_data_sections: list[str] = []
        for competitor, facts_summary in real_data.items():
            section = f"### {competitor} (real data from MCP sources)\n{facts_summary}"
            # Append KB stored articles if available
            kb_articles = kb_competitor_articles.get(competitor, [])
            if kb_articles:
                article_lines = "\n".join(
                    f"- [{a.get('source', '')}] {a.get('title', '')}"
                    for a in kb_articles[:3]
                )
                section += f"\n\nKB Stored Articles:\n{article_lines}"
            # Append EODHD financial data if available for this competitor
            eodhd_data = eodhd_enrichments.get(competitor)
            if eodhd_data:
                eodhd_parts = []
                if "revenue" in eodhd_data:
                    eodhd_parts.append(f"revenue={eodhd_data['revenue']:.0f}")
                if "employees" in eodhd_data:
                    eodhd_parts.append(f"employees={eodhd_data['employees']}")
                if "market_cap" in eodhd_data:
                    eodhd_parts.append(f"market_cap={eodhd_data['market_cap']:.0f}")
                if eodhd_parts:
                    _exch = eodhd_data.get("exchange", "SG")
                    section += f"\n\nEODHD Fundamentals ({_exch}:{eodhd_data.get('ticker', '')}): " + ", ".join(eodhd_parts)
            news_headlines = competitor_news.get(competitor, [])
            if news_headlines:
                section += "\n\nRecent News (last 14 days):\n" + "\n".join(f"- {h}" for h in news_headlines)
            kb_bench_block = _format_kb_benchmark(competitor)
            if kb_bench_block:
                section += f"\n\n{kb_bench_block}"
            deep_intel_block = _format_deep_intel(competitor)
            if deep_intel_block:
                section += f"\n\n{deep_intel_block}"
            real_data_sections.append(section)

        # For competitors with KB articles but no MCP facts, add a KB-only section
        for competitor, articles in kb_competitor_articles.items():
            if competitor not in real_data and articles:
                article_lines = "\n".join(
                    f"- [{a.get('source', '')}] {a.get('title', '')}"
                    for a in articles[:3]
                )
                section = f"### {competitor} (from KB stored articles)\n{article_lines}"
                # Append EODHD data even for KB-only competitors
                eodhd_data = eodhd_enrichments.get(competitor)
                if eodhd_data:
                    eodhd_parts = []
                    if "revenue" in eodhd_data:
                        eodhd_parts.append(f"revenue={eodhd_data['revenue']:.0f}")
                    if "employees" in eodhd_data:
                        eodhd_parts.append(f"employees={eodhd_data['employees']}")
                    if "market_cap" in eodhd_data:
                        eodhd_parts.append(f"market_cap={eodhd_data['market_cap']:.0f}")
                    if eodhd_parts:
                        _exch = eodhd_data.get("exchange", "SG")
                        section += f"\n\nEODHD Fundamentals ({_exch}:{eodhd_data.get('ticker', '')}): " + ", ".join(eodhd_parts)
                news_headlines = competitor_news.get(competitor, [])
                if news_headlines:
                    section += "\n\nRecent News (last 14 days):\n" + "\n".join(f"- {h}" for h in news_headlines)
                kb_bench_block = _format_kb_benchmark(competitor)
                if kb_bench_block:
                    section += f"\n\n{kb_bench_block}"
                deep_intel_block = _format_deep_intel(competitor)
                if deep_intel_block:
                    section += f"\n\n{deep_intel_block}"
                real_data_sections.append(section)

        # For competitors with EODHD data but neither MCP nor KB coverage, add a standalone section
        for competitor, eodhd_data in eodhd_enrichments.items():
            if competitor not in real_data and competitor not in kb_competitor_articles:
                eodhd_parts = []
                if "revenue" in eodhd_data:
                    eodhd_parts.append(f"revenue={eodhd_data['revenue']:.0f}")
                if "employees" in eodhd_data:
                    eodhd_parts.append(f"employees={eodhd_data['employees']}")
                if "market_cap" in eodhd_data:
                    eodhd_parts.append(f"market_cap={eodhd_data['market_cap']:.0f}")
                if eodhd_parts:
                    _exch = eodhd_data.get("exchange", "SG")
                    eodhd_section = (
                        f"### {competitor} (EODHD {_exch}:{eodhd_data.get('ticker', '')})\n"
                        + "EODHD Fundamentals: " + ", ".join(eodhd_parts)
                    )
                    kb_bench_block = _format_kb_benchmark(competitor)
                    if kb_bench_block:
                        eodhd_section += f"\n\n{kb_bench_block}"
                    deep_intel_block = _format_deep_intel(competitor)
                    if deep_intel_block:
                        eodhd_section += f"\n\n{deep_intel_block}"
                    real_data_sections.append(eodhd_section)

        # Competitors with only news data
        for competitor, headlines in competitor_news.items():
            if competitor not in real_data and competitor not in kb_competitor_articles and competitor not in eodhd_enrichments:
                section = f"### {competitor} (recent news only)\n" + "\n".join(f"- {h}" for h in headlines)
                kb_bench_block = _format_kb_benchmark(competitor)
                if kb_bench_block:
                    section += f"\n\n{kb_bench_block}"
                deep_intel_block = _format_deep_intel(competitor)
                if deep_intel_block:
                    section += f"\n\n{deep_intel_block}"
                real_data_sections.append(section)

        # Competitors with only KB financial benchmark data (no other coverage)
        covered = (
            set(real_data)
            | set(kb_competitor_articles)
            | set(eodhd_enrichments)
            | set(competitor_news)
        )
        for competitor, bench in kb_financial_benchmarks.items():
            if competitor not in covered and bench.get("found"):
                kb_bench_block = _format_kb_benchmark(competitor)
                if kb_bench_block:
                    bench_section = f"### {competitor}\n{kb_bench_block}"
                    deep_intel_block = _format_deep_intel(competitor)
                    if deep_intel_block:
                        bench_section += f"\n\n{deep_intel_block}"
                    real_data_sections.append(bench_section)

        grounding_context = (
            "\n\n".join(real_data_sections)
            if real_data_sections
            else "No real data fetched from MCP sources — analysis is LLM-generated only."
        )

        # --- Step 4b: Build Porter's Five Forces section if KB framework available ---
        porter_section = ""
        if self._porter_framework:
            porter_content = self._porter_framework.get("content") or {}
            forces = list((porter_content.get("forces") or {}).keys())
            if forces:
                porter_section = (
                    "\n\n## Porter's Five Forces Framework\n"
                    f"Assess the following forces: {', '.join(forces[:5])}.\n"
                    "Apply this framework to evaluate competitive dynamics in the market."
                )

        # --- Step 5: Synthesize positioning with LLM, grounded in real data ---
        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""{_knowledge_header}You have the following REAL data fetched from live sources (ACRA, news, web). \
Use it as ground truth — do not invent details that contradict it.

REAL COMPETITOR DATA:
{grounding_context}
{porter_section}
---
Based on the above real data and competitor research:
{[c.model_dump() for c in competitors_data]}

Your company: {context.get("company_name", "Not specified")}
Industry: {plan.get("industry")}

Create a complete CompetitorIntelOutput with:
1. Market landscape summary (cite real data where available)
2. Competitive positioning analysis
3. Strategic recommendations
""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompetitorIntelOutput,
            messages=messages,
        )
        result.competitors = competitors_data
        # Deduplicate citations (same URL may appear across multiple competitor lookups)
        unique_citations = list(dict.fromkeys(all_perplexity_citations))
        all_sources = list(sources | kb_sources) + (
            unique_citations if unique_citations
            else (["Perplexity AI"] if competitors_data else [])
        )
        result.sources = all_sources

        # Populate data provenance fields
        named_sources = list(sources | kb_sources) + (
            ["Perplexity AI"] if competitors_data else []
        )
        if kb_financial_benchmarks:
            named_sources.append("Market Intel DB (financial benchmarks)")
        result.data_sources_used = named_sources
        # is_live_data: only count real-time sources (Perplexity, MCP live queries, EODHD, NewsAPI).
        # kb_sources are from daily-synced DB snapshots — not live data.
        result.is_live_data = bool(
            self._competitors_with_real_data  # MCP returned data
            or valid_pairs  # Perplexity returned data for at least one competitor
            or eodhd_enrichments  # EODHD financial data
            or competitor_news  # NewsAPI recent news
        )
        return result

    async def _parse_competitor(
        self,
        name: str,
        research: str,
        context: dict[str, Any],
    ) -> CompetitorAnalysis | None:
        """Parse research into structured competitor analysis."""
        company_name = context.get("company_name", "our company")
        industry = context.get("industry", "technology")
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Extract a detailed CompetitorAnalysis for "{name}" from this research.

Research data:
{research[:3000]}

Extract SPECIFICALLY:
- strengths: 3-5 concrete strengths (product features, market position, pricing, support, brand)
- weaknesses: 3-5 concrete weaknesses exploitable by {company_name} in the {industry} space
- opportunities: 2-3 gaps in their offering that create opportunities for {company_name}
- threats: 2-3 ways they could harm {company_name}'s growth
- pricing_model: their actual pricing structure if discoverable (e.g. "S$X/seat/month", "enterprise contract")
- pricing_tiers: list of structured pricing tiers, each with:
    tier_name (e.g. "Starter", "Professional", "Enterprise", "Usage-based"),
    price_usd (monthly USD float, e.g. 99.0 — do NOT include currency symbols or text, return null if undisclosed or unknown),
    price_sgd (monthly SGD float, e.g. 135.0 — do NOT include currency symbols or text, return null if undisclosed or unknown),
    frequency ("monthly" | "annual" | "usage" | "custom"),
    features_summary (key features at this tier),
    source (where this pricing was found, e.g. "company website", "G2", "Perplexity")
- latest_funding: most recent funding round with:
    round_type (e.g. "Series B", "Seed", "IPO", "Bootstrapped"),
    amount_usd (float in USD, e.g. 5000000.0 — do NOT include currency symbols, commas, or text like "M"/"million", return null if undisclosed or unknown),
    announced_date (ISO date string or null),
    investors (list of fund/investor names),
    use_of_funds (stated purpose, e.g. "APAC expansion")
    Set latest_funding to null if no funding data is available.
- employee_count_estimate: numeric headcount estimate from LinkedIn/Crunchbase/press (null if unknown)
- hiring_velocity: one of "growing fast" (many open roles), "stable", or "contracting" (layoffs/freeze)
- recent_executive_moves: list of notable CXO/VP hires or departures with approximate date
    (e.g. "New CTO hired from Stripe, March 2025"). Empty list if none found.
- market_share_estimate: estimated market position (e.g. "market leader", "challenger", "niche player")
- key_differentiators: what makes them distinctive vs generic options

Be specific — cite product names, pricing tiers, customer segments, or recent moves if mentioned.
Do not use generic phrases like "strong brand" without supporting detail.""",
            },
        ]
        try:
            return await self._complete_structured(
                response_model=CompetitorAnalysis,
                messages=messages,
            )
        except Exception:
            return None

    async def _check(self, result: CompetitorIntelOutput) -> float:
        total_competitors = len(result.competitors)
        competitors_with_data = len(self._competitors_with_real_data)

        if total_competitors > 0 and competitors_with_data > 0:
            # Named competitors analysed with real MCP data — highest quality path
            data_coverage = competitors_with_data / total_competitors
            base_score = 0.3 + 0.2 * data_coverage  # 0.3–0.5
            cap = 1.0
        elif total_competitors > 0 and competitors_with_data == 0:
            # Competitors found but MCP data unavailable (first-cut / unconfigured).
            # A well-structured LLM analysis should still pass — penalise but don't block.
            # Max with all bonuses: 0.20+0.15+0.10+0.10+0.10+0.05 = 0.70 → capped 0.65
            base_score = 0.20
            cap = 0.65
        else:
            # No named competitors at all — valid state, no data failure
            base_score = 0.35
            cap = 1.0

        score = base_score

        if result.competitors:
            score += 0.15
            for c in result.competitors:
                if c.strengths and c.weaknesses:
                    score += 0.1
                    break

        if result.competitive_positioning.your_differentiators:
            score += 0.1
        if result.strategic_recommendations:
            score += 0.1
        if result.market_landscape:
            score += 0.05

        # Structured pricing/funding intelligence bonus — rewards extracting deep signal
        if result.competitors:
            has_pricing_tiers = any(c.pricing_tiers for c in result.competitors)
            has_funding = any(c.latest_funding is not None for c in result.competitors)
            if has_pricing_tiers:
                score += 0.05
            if has_funding:
                score += 0.05

        # Knowledge MCP framework bonus (+0.03 when Porter's Five Forces was loaded)
        if self._porter_framework is not None:
            score += 0.03

        # KB financial benchmark bonus (+0.05 when at least one competitor was benchmarked)
        if getattr(self, "_kb_financial_benchmarks", {}):
            score += 0.05

        # Deep intelligence bonuses (trajectory + GTM profile)
        if getattr(self, "_kb_trajectories", {}):
            score += 0.03
        if getattr(self, "_kb_gtm_profiles", {}):
            score += 0.02

        return min(score, cap)

    async def _act(self, result: CompetitorIntelOutput, confidence: float) -> CompetitorIntelOutput:
        """Publish discovered weaknesses to the AgentBus."""
        result.confidence = confidence

        # Persist competitor landscape data — company-specific, so is_public=False
        if result.competitors:
            for comp in result.competitors[:3]:
                comp_name = comp.competitor_name
                asyncio.create_task(persist_research(
                    source="competitor_analyst",
                    query=f"Competitor analysis: {comp_name}",
                    content=str(comp.model_dump()),
                    vertical_slug=getattr(self, "_vertical_slug", None),
                    analysis_id=self._analysis_id,
                    is_public=False,  # Company-specific competitor data
                ))

        # Publish competitor weaknesses for Campaign Architect to exploit
        if self._agent_bus and result.competitors:
            for competitor in result.competitors:
                if competitor.weaknesses:
                    try:
                        await self._agent_bus.publish(
                            from_agent=self.name,
                            discovery_type=DiscoveryType.COMPETITOR_WEAKNESS,
                            title=f"Weaknesses: {competitor.competitor_name}",
                            content={
                                "competitor_name": competitor.competitor_name,
                                "weaknesses": competitor.weaknesses,
                                "opportunities": competitor.opportunities,
                            },
                            confidence=confidence,
                            analysis_id=self._analysis_id,
                        )
                    except Exception as e:
                        self._logger.warning(
                            "competitor_weakness_publish_failed",
                            competitor=competitor.competitor_name,
                            error=str(e),
                        )

        return result
