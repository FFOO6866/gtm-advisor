"""Signal Monitor Agent — Always-on market intelligence surveillance.

Runs on a schedule (hourly/daily) to monitor:
- Perplexity: Real-time web signals about competitors, market, regulations
- NewsAPI: Industry and competitor news (last 24 hours)
- EODHD: Financial signals — funding rounds, M&A, Singapore market data

For each signal found, applies SignalRelevanceScorer to score actionability.
High-relevance signals (>= 0.50) are stored in the SignalEvent table and
published to AgentBus to trigger downstream agents.

Why this is not ChatGPT:
- Runs continuously on a schedule — no human prompt required
- Uses LIVE data from three real APIs
- Applies deterministic relevance scoring to filter noise from signal
- Stores and tracks signals over time — gives context to trends
- Can trigger other agents automatically (e.g. Competitor Displacement playbook)
"""

from __future__ import annotations

import asyncio
import uuid as _uuid_module
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.models import SignalEvent, SignalType, SignalUrgency
from packages.database.src.session import async_session_factory
from packages.integrations.eodhd.src.client import EODHDClient
from packages.integrations.newsapi.src.client import NewsAPIClient
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.llm.src import get_llm_manager
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer
from packages.scoring.src.market_context import MarketContextScorer
from packages.scoring.src.signal_relevance import SIGNAL_TYPES, ScoredSignal, SignalRelevanceScorer

logger = structlog.get_logger()


class DetectedSignal(BaseModel):
    headline: str = Field(...)
    signal_type: str = Field(...)
    source: str = Field(...)
    source_url: str | None = Field(default=None)
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_content: str | None = Field(default=None)


class AccountSignalSummary(BaseModel):
    """Aggregated signal intelligence for a specific company/account."""

    company_name: str = Field(...)
    signals_30d: int = Field(default=0)
    latest_signal_date: str | None = Field(default=None)
    signal_types_seen: list[str] = Field(default_factory=list)
    deal_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    deal_probability_rationale: str = Field(default="")
    recommended_action: str = Field(default="")
    urgency_level: str = Field(default="monitor")


class SignalMonitorResult(BaseModel):
    """Result of one Signal Monitor run."""
    company_id: str = Field(...)
    scan_period_hours: int = Field(default=24)
    signals_found: int = Field(default=0)
    signals_actionable: int = Field(default=0)  # relevance >= 0.50
    signals_urgent: int = Field(default=0)       # urgency == "immediate"
    scored_signals: list[dict[str, Any]] = Field(default_factory=list)
    data_sources_queried: list[str] = Field(default_factory=list)
    account_summaries: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_live_data: bool = Field(default=False)  # True if data_sources_queried is non-empty


class SignalMonitorAgent(BaseGTMAgent[SignalMonitorResult]):
    """Always-on market signal surveillance for a company workspace.

    Designed to run on an APScheduler schedule — not triggered by user.
    Monitors: NewsAPI (industry + competitor news) + EODHD (financial signals)
    + Perplexity (real-time web — if configured).
    """

    MIN_RELEVANCE_SCORE = 0.50  # Signals below this are discarded (matches actionable threshold)
    URGENT_RELEVANCE_SCORE = 0.65  # Above this = "immediate" urgency

    def __init__(self, agent_bus: AgentBus | None = None) -> None:
        super().__init__(
            name="signal-monitor",
            description=(
                "Continuously monitors market signals: competitor news, industry trends, "
                "regulatory changes, and financial data. Runs autonomously on a schedule."
            ),
            result_type=SignalMonitorResult,
            min_confidence=0.35,  # 1 source + 0 signals = 0.35 (valid "all clear" run)
            max_iterations=1,
            model="gpt-4o-mini",
            capabilities=[
                AgentCapability(
                    name="market-surveillance",
                    description="Monitor Perplexity, NewsAPI, and EODHD for market signals",
                ),
            ],
        )
        self._newsapi = NewsAPIClient()
        self._eodhd = EODHDClient()
        self._perplexity = get_llm_manager().perplexity
        self._scorer = SignalRelevanceScorer()
        self._market_scorer = MarketContextScorer()
        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id: Any = None
        self._known_competitors: list[str] = []

        # Subscribe to competitor discoveries so monitoring queries can include them
        self._agent_bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.COMPETITOR_FOUND,
            handler=self._on_competitor_found,
        )

    def get_system_prompt(self) -> str:
        return (
            "You are a market signal classifier. Given a news headline and content, "
            "classify it as one of: funding, acquisition, product_launch, regulation, "
            "expansion, hiring, layoff, partnership, market_trend, competitor_news, general_news. "
            "Respond with ONLY the classification word. No explanation."
        )

    async def _on_competitor_found(self, message: AgentMessage) -> None:
        """Handle competitor discovery from Competitor Analyst or other agents."""
        try:
            if (
                self._analysis_id
                and message.analysis_id
                and message.analysis_id != self._analysis_id
            ):
                return
            name = message.content.get("competitor_name", "")
            if name and name not in self._known_competitors:
                self._known_competitors.append(name)
                self._logger.debug(
                    "signal_monitor_competitor_added",
                    competitor=name,
                    from_agent=message.from_agent,
                )
        except Exception as e:
            self._logger.debug("on_competitor_found_failed", error=str(e))

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Query KB for vertical landscape to contextualise signal scoring
        kb_vertical_context: dict[str, Any] = {}
        vertical_slug = detect_vertical_slug(
            context.get("industry", "") + " " + context.get("description", "")
        )
        if vertical_slug:
            try:
                async with async_session_factory() as db:
                    mcp = MarketIntelMCPServer(session=db)
                    landscape = await mcp.get_vertical_landscape(vertical_slug)
                    if landscape:
                        kb_vertical_context = {
                            "vertical": vertical_slug,
                            "listed_companies": landscape.get("listed_companies_count", 0),
                            "market_leaders": [
                                c.get("name", "")
                                for c in landscape.get("leaders", [])[:5]
                                if c.get("name")
                            ],
                            "top_signals": landscape.get("top_signals", [])[:3],
                        }
            except Exception as e:
                logger.debug("signal_monitor_kb_failed", error=str(e))

        # Fetch Singapore SME context for signal classification grounding
        sg_context: dict[str, Any] = {}
        try:
            kmcp = get_knowledge_mcp()
            sg_raw = await kmcp.get_singapore_context()
            buying_triggers = sg_raw.get("key_buying_triggers", [])
            sg_context = {
                "buying_triggers": buying_triggers[:5],
                "regulatory_signals": [
                    cat for cat in sg_raw.get("psg_grant", {}).get("qualifying_categories", [])
                ][:3] if isinstance(sg_raw.get("psg_grant"), dict) else [],
            }
        except Exception as e:
            logger.debug("signal_monitor_sg_context_failed", error=str(e))

        # ── A2A backfill: seed known competitors from bus history ────────────
        if self._agent_bus is not None:
            try:
                competitor_msgs = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.COMPETITOR_FOUND,
                    limit=10,
                )
                for msg in competitor_msgs:
                    name = msg.content.get("competitor_name", "")
                    if name and name not in self._known_competitors:
                        self._known_competitors.append(name)
            except Exception as e:
                self._logger.debug("bus_backfill_competitors_failed", error=str(e))

        return {
            "company_id": context.get("company_id", ""),
            "industry": context.get("industry", "technology"),
            "competitors": context.get("competitors", []),
            "keywords": context.get("keywords", []),
            "target_region": context.get("target_region", "Singapore"),
            "scan_hours": context.get("scan_hours", 24),
            "kb_vertical_context": kb_vertical_context,
            "sg_context": sg_context,
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SignalMonitorResult:
        company_id = plan.get("company_id", "")
        industry = plan.get("industry", "technology")
        # Merge context-provided competitors with A2A-discovered competitors
        _plan_competitors: list[str] = plan.get("competitors", [])
        competitors = list(
            {c for c in (_plan_competitors + self._known_competitors) if c}
        )
        target_region = plan.get("target_region", "Singapore")
        scan_hours = plan.get("scan_hours", 24)
        kb_vertical_context: dict[str, Any] = plan.get("kb_vertical_context", {})
        sg_context: dict[str, Any] = plan.get("sg_context", {})

        raw_signals: list[DetectedSignal] = []
        data_sources: list[str] = []

        # Gather signals from all sources concurrently (each returns its own source list)
        results = await asyncio.gather(
            self._fetch_newsapi_signals(industry, target_region, scan_hours),
            self._fetch_competitor_news(competitors, scan_hours),
            self._fetch_eodhd_signals(industry),
            self._fetch_perplexity_signals(industry, competitors, target_region),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, tuple):
                signals, sources = result
                raw_signals.extend(signals)
                data_sources.extend(sources)

        # Track KB as a data source if vertical context was loaded
        if kb_vertical_context:
            data_sources.append("Market Intel DB")

        # Classify all signals in parallel then score
        capped = raw_signals[:30]
        signal_types = await asyncio.gather(
            *[self._classify_signal(raw.headline, kb_context=kb_vertical_context, sg_context=sg_context) for raw in capped],
            return_exceptions=True,
        )

        scored: list[ScoredSignal] = []
        for raw, sig_type in zip(capped, signal_types, strict=False):
            signal_type = sig_type if isinstance(sig_type, str) else "market_trend"
            scored_signal = self._scorer.score(
                signal_text=raw.headline + " " + (raw.raw_content or ""),
                signal_type=signal_type,
                signal_published_at=raw.published_at,
                client_industry=industry,
                client_competitors=competitors,
                source=raw.source,
            )
            if scored_signal.relevance_score >= self.MIN_RELEVANCE_SCORE:
                scored.append(scored_signal)

        # Sort by relevance descending
        scored.sort(key=lambda s: s.relevance_score, reverse=True)

        # Deduplicate against signals already stored in the last 7 days so hourly
        # runs don't re-surface the same headlines repeatedly.
        recent_headlines: frozenset[str] = frozenset()
        if company_id:
            try:
                cutoff = datetime.now(UTC) - timedelta(days=7)
                async with async_session_factory() as db:
                    stmt = select(SignalEvent.headline).where(
                        SignalEvent.company_id == _uuid_module.UUID(str(company_id)),
                        SignalEvent.created_at >= cutoff,
                    )
                    rows = (await db.execute(stmt)).scalars().all()
                    recent_headlines = frozenset(h.lower() for h in rows)
            except Exception as e:
                self._logger.debug("signal_dedup_query_failed", error=str(e))

        scored = [s for s in scored if s.signal_text.lower() not in recent_headlines]

        # Score market context once per run — used to calibrate signal urgency
        opportunity_window = None
        industry_str = context.get("industry", "") if context else ""
        if not industry_str:
            industry_str = industry
        if industry_str:
            try:
                async with asyncio.timeout(15):
                    opportunity_window = await self._market_scorer.score(
                        industry=industry_str, target_region="Singapore"
                    )
            except Exception as e:
                self._logger.debug("signal_market_context_failed", error=str(e))

        # Downgrade "immediate" urgency signals when market conditions are unfavourable
        if opportunity_window is not None:
            from packages.scoring.src.market_context import OpportunityRating  # noqa: PLC0415
            if opportunity_window.rating == OpportunityRating.RED:
                for signal in scored:
                    if signal.urgency == "immediate":
                        signal.urgency = "high"  # Downgrade during bad market conditions
                self._logger.info(
                    "signal_urgency_downgraded_red_market",
                    count=len([s for s in scored if s.urgency == "high"]),
                )

        actionable = [s for s in scored if s.relevance_score >= 0.50]
        urgent = [s for s in scored if s.urgency == "immediate"]

        account_summaries = self._compute_account_summaries(scored, company_id)

        if opportunity_window is not None:
            data_sources.append("MarketContext")
        unique_sources = list(set(data_sources))
        return SignalMonitorResult(
            company_id=company_id,
            scan_period_hours=scan_hours,
            signals_found=len(raw_signals),
            signals_actionable=len(actionable),
            signals_urgent=len(urgent),
            scored_signals=[s.to_dict() for s in scored[:10]],  # Top 10
            data_sources_queried=unique_sources,
            account_summaries=account_summaries,
            confidence=0.0,  # Set by _check
            is_live_data=bool(unique_sources),
        )

    def _compute_account_summaries(
        self,
        scored_signals: list[ScoredSignal],
        company_id: str,
    ) -> list[dict[str, Any]]:
        """Aggregate signals by company name and compute deal probability.

        Deal probability model:
        - funding signal = +0.25 (company actively spending)
        - acquisition signal = +0.15 (strategic shift = opportunity)
        - hiring signal = +0.10 (growth = budget available)
        - product_launch = +0.20 (competitive pressure on their customers)
        - regulation signal = +0.15 (compliance pressure = need for solutions)
        - urgency == "immediate" bonus = +0.10
        - Multiple signals for same company = +0.10 per additional signal (max +0.30)
        """
        from collections import defaultdict

        # Group signals by companies mentioned
        company_signals: dict[str, list[ScoredSignal]] = defaultdict(list)
        for signal in scored_signals:
            for comp in (signal.competitors_mentioned or []):
                if comp:
                    company_signals[comp.lower()].append(signal)
            # Signals with no specific company are bucketed under "market" (skipped below)
            if not signal.competitors_mentioned:
                company_signals["market"].append(signal)

        signal_type_weights: dict[str, float] = {
            "funding": 0.25,
            "acquisition": 0.15,
            "hiring": 0.10,
            "product_launch": 0.20,
            "regulation": 0.15,
            "layoff": -0.05,
            "market_trend": 0.05,
            "competitor_news": 0.10,
        }

        summaries = []
        for company_name, signals in company_signals.items():
            if company_name == "market" or not signals:
                continue

            base_prob = 0.20
            for signal in signals:
                base_prob += signal_type_weights.get(signal.signal_type, 0.05)
                if signal.urgency == "immediate":
                    base_prob += 0.10

            # Multi-signal bonus
            if len(signals) > 1:
                base_prob += min(0.10 * (len(signals) - 1), 0.30)

            deal_prob = min(max(base_prob, 0.05), 0.90)

            if deal_prob >= 0.65:
                action = "Immediate outreach — high buying signal"
                urgency = "immediate"
            elif deal_prob >= 0.40:
                action = "Schedule outreach this week"
                urgency = "this_week"
            else:
                action = "Monitor — no strong buying signal yet"
                urgency = "monitor"

            signal_types_seen = list({s.signal_type for s in signals})

            # ScoredSignal has no dedicated date field; check for optional attrs defensively.
            latest: datetime | None = None
            for s in signals:
                pub = getattr(s, "signal_published_at", None) or getattr(s, "published_at", None)
                if pub and (latest is None or pub > latest):
                    latest = pub
            latest_signal_date_str = latest.isoformat() if latest else None

            summaries.append(AccountSignalSummary(
                company_name=company_name,
                signals_30d=len(signals),
                latest_signal_date=latest_signal_date_str,
                signal_types_seen=signal_types_seen,
                deal_probability=round(deal_prob, 2),
                deal_probability_rationale=(
                    f"{len(signals)} signals: {', '.join(signal_types_seen)}"
                ),
                recommended_action=action,
                urgency_level=urgency,
            ).model_dump())

        return sorted(summaries, key=lambda x: x["deal_probability"], reverse=True)[:10]

    async def _check(self, result: SignalMonitorResult) -> float:
        score = 0.20  # Base
        if result.data_sources_queried:
            score += min(len(result.data_sources_queried) * 0.15, 0.45)
        if result.signals_actionable > 0:
            score += 0.20
        if result.signals_urgent > 0:
            score += 0.15
        return min(score, 1.0)

    async def _persist_signals(self, result: SignalMonitorResult) -> None:
        """Write scored signals to the SignalEvent table for trend tracking."""
        try:
            company_uuid = _uuid_module.UUID(str(result.company_id))
        except (ValueError, AttributeError):
            return

        rows: list[SignalEvent] = []
        for signal in result.scored_signals:
            try:
                signal_type = SignalType(signal.get("signal_type", "general_news"))
            except ValueError:
                signal_type = SignalType.GENERAL_NEWS

            try:
                urgency = SignalUrgency(signal.get("urgency", "monitor"))
            except ValueError:
                urgency = SignalUrgency.MONITOR

            rows.append(SignalEvent(
                company_id=company_uuid,
                signal_type=signal_type,
                urgency=urgency,
                headline=signal.get("signal_text", "")[:500],
                source=signal.get("source", ""),
                relevance_score=signal.get("relevance_score", 0.0),
                recommended_action=signal.get("recommended_action") or "",
                competitors_mentioned=signal.get("competitors_mentioned", []),
            ))

        if not rows:
            return
        try:
            async with async_session_factory() as db:
                for row in rows:
                    db.add(row)
                await db.commit()
            self._logger.info("signals_persisted", count=len(rows), company=str(company_uuid))
        except Exception as e:
            self._logger.warning("signal_persist_failed", error=str(e))

    async def _act(self, result: SignalMonitorResult, confidence: float) -> SignalMonitorResult:
        result.confidence = confidence

        # Persist new (already-deduplicated) signals to the SignalEvent table.
        if result.scored_signals and result.company_id:
            await self._persist_signals(result)

        if self._agent_bus is None:
            return result

        # Publish actionable signals (relevance >= 0.50) to the bus so downstream
        # agents (e.g. CampaignArchitect, SequenceEngine) can react automatically.
        published = 0
        for signal in result.scored_signals:
            if signal.get("relevance_score", 0) < 0.50:
                continue
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.SIGNAL_DETECTED,
                    title=(signal.get("signal_text") or "Signal Detected")[:120],
                    content={
                        "signal_text": signal.get("signal_text", ""),
                        "signal_type": signal.get("signal_type", "market_trend"),
                        "relevance_score": signal.get("relevance_score", 0),
                        "urgency": signal.get("urgency", "normal"),
                        "recommended_action": signal.get("recommended_action", ""),
                        "reasoning": signal.get("reasoning", ""),
                        "competitors_mentioned": signal.get("competitors_mentioned", []),
                        "industries_affected": signal.get("industries_affected", []),
                        "source": signal.get("source", ""),
                        "company_id": result.company_id,
                    },
                    confidence=signal.get("relevance_score", 0.0),
                    analysis_id=self._analysis_id,
                )
                published += 1
            except Exception as e:
                self._logger.warning(
                    "bus_publish_signal_failed",
                    signal=signal.get("signal_text", "")[:60],
                    error=str(e),
                )

        self._logger.info(
            "signals_published_to_bus",
            published=published,
            total_actionable=result.signals_actionable,
        )
        return result

    async def _fetch_newsapi_signals(
        self,
        industry: str,
        region: str,
        hours: int,
    ) -> tuple[list[DetectedSignal], list[str]]:
        if not self._newsapi.is_configured:
            return [], []
        try:
            news_result = await self._newsapi.search_market_news(
                industry=industry,
                region=region,
                days_back=max(1, hours // 24),
            )
            signals = []
            for article in news_result.articles[:15]:
                signals.append(DetectedSignal(
                    headline=article.title,
                    signal_type="market_trend",
                    source="NewsAPI",
                    source_url=article.url,
                    published_at=article.published_at,
                    raw_content=article.description,
                ))
            return signals, ["NewsAPI"]
        except Exception as e:
            logger.warning("newsapi_signals_failed", error=str(e))
            return [], []

    async def _fetch_competitor_news(
        self,
        competitors: list[str],
        hours: int,
    ) -> tuple[list[DetectedSignal], list[str]]:
        if not self._newsapi.is_configured or not competitors:
            return [], []
        signals = []
        sources: list[str] = []
        for competitor in competitors[:3]:  # Max 3 competitors
            try:
                result = await self._newsapi.search_competitor_news(
                    competitor_name=competitor,
                    days_back=max(1, hours // 24),
                )
                if result.articles:
                    sources.append(f"NewsAPI:{competitor}")
                for article in result.articles[:5]:
                    signals.append(DetectedSignal(
                        headline=article.title,
                        signal_type="competitor_news",
                        source="NewsAPI",
                        source_url=article.url,
                        published_at=article.published_at,
                        raw_content=article.description,
                    ))
            except Exception:
                continue
        return signals, sources

    async def _fetch_eodhd_signals(
        self,
        industry: str,
    ) -> tuple[list[DetectedSignal], list[str]]:
        if not self._eodhd.is_configured:
            return [], []
        try:
            news = await self._eodhd.get_financial_news(limit=10)
            sources = ["EODHD Financial News"] if news else []
            signals = []
            industry_keywords = [kw for kw in industry.lower().split() if len(kw) > 3]
            for item in news:
                # Only include if relevant to industry (keyword match — skip short words to reduce false positives)
                title_lower = item.title.lower()
                if any(kw in title_lower for kw in industry_keywords + ["singapore", "apac", "funding", "acquisition"]):
                    signal_type = "funding"
                    if any(kw in title_lower for kw in ["acqui", "merger", "takeover"]):
                        signal_type = "acquisition"
                    elif any(kw in title_lower for kw in ["launch", "release", "announce"]):
                        signal_type = "product_launch"
                    signals.append(DetectedSignal(
                        headline=item.title,
                        signal_type=signal_type,
                        source="EODHD",
                        source_url=item.link,
                        published_at=item.date,
                        raw_content=item.content,
                    ))
            return signals, sources
        except Exception as e:
            logger.warning("eodhd_signals_failed", error=str(e))
            return [], []

    async def _fetch_perplexity_signals(
        self,
        industry: str,
        competitors: list[str],
        target_region: str,
    ) -> tuple[list[DetectedSignal], list[str]]:
        """Fetch real-time market signals via Perplexity web search."""
        if not self._perplexity.is_configured:
            return [], []
        try:
            competitor_str = (
                f" and competitors ({', '.join(competitors[:3])})" if competitors else ""
            )
            query = (
                f"Latest market signals for {industry} sector in {target_region}{competitor_str}: "
                f"funding rounds, acquisitions, regulatory changes, product launches, hiring trends 2025"
            )
            response = await self._perplexity.search(query=query, focus="internet")
            if not response:
                return [], []
            # Perplexity returns a text blob — split into headline-sized signals
            lines = [line.strip() for line in str(response).split("\n") if len(line.strip()) > 30]
            signals = []
            now = datetime.now(UTC)
            for line in lines[:10]:
                signals.append(DetectedSignal(
                    headline=line[:200],
                    signal_type="market_trend",
                    source="Perplexity",
                    published_at=now,
                    raw_content=line,
                ))
            return signals, ["Perplexity"] if signals else []
        except Exception as e:
            logger.warning("perplexity_signals_failed", error=str(e))
            return [], []

    async def _classify_signal(
        self,
        headline: str,
        kb_context: dict[str, Any] | None = None,
        sg_context: dict[str, Any] | None = None,
    ) -> str:
        """Use LLM to classify signal type from headline."""
        try:
            user_content = f"Classify: {headline}"
            if kb_context and kb_context.get("market_leaders"):
                leaders_str = ", ".join(kb_context["market_leaders"])
                user_content += (
                    f"\nMarket leaders in this vertical: {leaders_str}"
                    " — signals about these companies have higher relevance."
                )
            if sg_context and sg_context.get("buying_triggers"):
                triggers_str = "; ".join(
                    t.get("trigger", str(t)) if isinstance(t, dict) else str(t)
                    for t in sg_context["buying_triggers"][:3]
                )
                user_content += (
                    f"\nSingapore buying triggers: {triggers_str}"
                    " — signals matching these indicate high purchase intent."
                )
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_content},
            ]
            raw = await self._complete(messages)
            result = (raw or "").strip().lower()
            # Validate against known types
            if result in SIGNAL_TYPES:
                return result
        except Exception:
            pass
        # Fallback: keyword-based classification
        hl = headline.lower()
        if any(w in hl for w in ["fund", "raise", "series", "invest"]):
            return "funding"
        if any(w in hl for w in ["acqui", "merger", "takeover", "buy"]):
            return "acquisition"
        if any(w in hl for w in ["launch", "release", "new product"]):
            return "product_launch"
        if any(w in hl for w in ["regulat", "compliance", "mas ", "law", "pdpa"]):
            return "regulation"
        if any(w in hl for w in ["hire", "hiring", "recruit", "headcount"]):
            return "hiring"
        if any(w in hl for w in ["layoff", "retrench", "cut", "fired"]):
            return "layoff"
        return "market_trend"
