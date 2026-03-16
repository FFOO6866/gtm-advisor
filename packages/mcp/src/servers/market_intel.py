"""Market Intelligence MCP Server — Singapore Market Intelligence Database.

Exposes structured market data, benchmarks, and executive intelligence to GTM
agents via tool calls.  All tools return empty dict/list on any exception and
never propagate exceptions to callers.

Tools:
  get_vertical_landscape        — overview of a vertical (companies, market cap, benchmarks)
  get_listed_company            — full profile for a listed company
  benchmark_company             — how a company ranks vs its vertical peers
  search_market_intelligence    — semantic search over annual reports and news
  get_executive_intelligence    — executive profiles and news monitoring
  get_vertical_benchmarks       — full benchmark distributions
  get_company_gtm_profile       — GTM-focused profile (SG&A, R&D, ESG, peer rank, signals)
  get_company_trajectory        — growth trajectory analysis from financial time-series
  get_gtm_intelligence          — extracted GTM insights from annual reports
  get_vertical_intelligence     — synthesized per-vertical intelligence report
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    CompanyDocument,
    CompanyExecutive,
    CompanyFinancialSnapshot,
    DocumentChunk,
    FinancialPeriodType,
    ListedCompany,
    MarketArticle,
    MarketVertical,
    SignalEvent,
    VerticalBenchmark,
)
from packages.documents.src.embeddings import get_embedding_service
from packages.integrations.sgx.src.executive_intel import ExecutiveIntelligenceService
from packages.scoring.src.financial_benchmarks import (
    BenchmarkResult,
    CompanyMetrics,
    FinancialBenchmarkEngine,
    PercentileDistribution,
)
from packages.vector_store.src import cosine_similarity_fallback, get_qdrant_store

logger = structlog.get_logger(__name__)


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters (% and _) in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MarketIntelMCPServer:
    """MCP server providing Singapore Market Intelligence tools to GTM agents.

    Tools:
      get_vertical_landscape        — overview of a vertical (companies, market cap, benchmarks)
      get_listed_company            — full profile for a listed company
      benchmark_company             — how a company ranks vs its vertical peers
      search_market_intelligence    — semantic search over annual reports + news
      get_executive_intelligence    — executive profiles and news monitoring
      get_vertical_benchmarks       — full benchmark distributions
      get_company_gtm_profile       — GTM-focused profile (SG&A, R&D, ESG, peer rank, signals)
      get_company_trajectory        — growth trajectory analysis from financial time-series
      get_gtm_intelligence          — extracted GTM insights from annual reports
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._benchmark_engine = FinancialBenchmarkEngine()

    async def _get_query_vector(self, query: str) -> list[float] | None:
        """Embed *query* and return the float vector, or None when unavailable.

        The embedding service returns a JSON string on success and None when the
        OpenAI key is absent or the call fails.  We parse that JSON here so the
        rest of the search logic can work with a plain ``list[float]``.
        """
        try:
            embedding_svc = get_embedding_service()
            query_vector_json = await embedding_svc.embed_text(query)
            if query_vector_json is None:
                return None
            return json.loads(query_vector_json)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Tool 1: get_vertical_landscape
    # ------------------------------------------------------------------

    async def get_vertical_landscape(self, vertical_slug: str) -> dict[str, Any]:
        """Return an overview of a Singapore market vertical.

        Includes listed-company count, total market cap, latest benchmark
        percentiles, recent news signals, and leader/laggard snapshots.

        Args:
            vertical_slug: e.g. "fintech", "reit-industrial"

        Returns:
            {vertical, listed_companies_count, market_cap_total_sgd,
             benchmark_latest, top_signals, leaders, laggards}
            or {} on any error.
        """
        try:
            # Fetch vertical row
            vertical_stmt = select(MarketVertical).where(MarketVertical.slug == vertical_slug)
            vertical: MarketVertical | None = await self._session.scalar(vertical_stmt)
            if vertical is None:
                logger.warning("market_intel.get_vertical_landscape.not_found", slug=vertical_slug)
                return {}

            # Count listed companies and sum market cap
            agg_stmt = (
                select(
                    func.count(ListedCompany.id).label("count"),
                    func.sum(ListedCompany.market_cap_sgd).label("total_market_cap"),
                )
                .where(
                    ListedCompany.vertical_id == vertical.id,
                    ListedCompany.is_active.is_(True),
                )
            )
            agg_result = await self._session.execute(agg_stmt)
            agg_row = agg_result.one()
            listed_companies_count: int = agg_row.count or 0
            market_cap_total_sgd: float | None = agg_row.total_market_cap

            # Latest VerticalBenchmark for this vertical
            benchmark_stmt = (
                select(VerticalBenchmark)
                .where(VerticalBenchmark.vertical_id == vertical.id)
                .order_by(desc(VerticalBenchmark.computed_at))
                .limit(1)
            )
            benchmark: VerticalBenchmark | None = await self._session.scalar(benchmark_stmt)

            benchmark_latest: dict[str, Any] = {}
            leaders: list[dict] = []
            laggards: list[dict] = []
            if benchmark is not None:
                benchmark_latest = {
                    "period_label": benchmark.period_label,
                    "period_type": benchmark.period_type.value if benchmark.period_type else None,
                    "company_count": benchmark.company_count,
                    "revenue_growth_yoy": benchmark.revenue_growth_yoy,
                    "gross_margin": benchmark.gross_margin,
                    "ebitda_margin": benchmark.ebitda_margin,
                    "net_margin": benchmark.net_margin,
                    "roe": benchmark.roe,
                    "net_debt_ebitda": benchmark.net_debt_ebitda,
                    "sga_to_revenue": benchmark.sga_to_revenue,
                    "rnd_to_revenue": benchmark.rnd_to_revenue,
                    "operating_margin": benchmark.operating_margin_dist,
                    "capex_to_revenue": benchmark.capex_to_revenue,
                    "computed_at": (
                        benchmark.computed_at.isoformat() if benchmark.computed_at else None
                    ),
                }
                leaders = benchmark.leaders or []
                laggards = benchmark.laggards or []

            # Recent MarketArticle signals for this vertical (last 7 days, limit 5)
            cutoff = datetime.now(UTC) - timedelta(days=7)
            signals_stmt = (
                select(MarketArticle)
                .where(
                    MarketArticle.vertical_slug == vertical_slug,
                    MarketArticle.published_at >= cutoff,
                )
                .order_by(desc(MarketArticle.published_at))
                .limit(5)
            )
            signals_result = await self._session.execute(signals_stmt)
            signal_articles: list[MarketArticle] = list(signals_result.scalars().all())

            top_signals = [
                {
                    "title": article.title,
                    "source": article.source_name,
                    "signal_type": article.signal_type,
                    "published_at": (
                        article.published_at.isoformat() if article.published_at else None
                    ),
                    "url": article.source_url,
                }
                for article in signal_articles
            ]

            logger.info(
                "market_intel.get_vertical_landscape.ok",
                slug=vertical_slug,
                companies=listed_companies_count,
            )
            return {
                "vertical": {
                    "slug": vertical.slug,
                    "name": vertical.name,
                    "description": vertical.description,
                    "is_reit_vertical": vertical.is_reit_vertical,
                    "ssic_sections": vertical.ssic_sections,
                },
                "listed_companies_count": listed_companies_count,
                "market_cap_total_sgd": market_cap_total_sgd,
                "benchmark_latest": benchmark_latest,
                "top_signals": top_signals,
                "leaders": leaders,
                "laggards": laggards,
            }

        except Exception as exc:
            logger.warning(
                "market_intel.get_vertical_landscape.error",
                slug=vertical_slug,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Tool 2: get_listed_company
    # ------------------------------------------------------------------

    async def get_listed_company(
        self, ticker: str, exchange: str = "SG"
    ) -> dict[str, Any]:
        """Return a full company profile including financials and executives.

        Args:
            ticker:   SGX stock code, e.g. "D05" (DBS), "Z74" (SingTel).
            exchange: Exchange identifier, default "SG".

        Returns:
            Full company profile dict, or {} when not found / on error.
        """
        try:
            company_stmt = (
                select(ListedCompany)
                .where(
                    ListedCompany.ticker == ticker,
                    ListedCompany.exchange == exchange,
                )
            )
            company: ListedCompany | None = await self._session.scalar(company_stmt)
            if company is None:
                logger.warning(
                    "market_intel.get_listed_company.not_found",
                    ticker=ticker,
                    exchange=exchange,
                )
                return {}

            # Latest annual financial snapshot
            snapshot_stmt = (
                select(CompanyFinancialSnapshot)
                .where(
                    CompanyFinancialSnapshot.company_id == company.id,
                    CompanyFinancialSnapshot.period_type == FinancialPeriodType.ANNUAL,
                )
                .order_by(desc(CompanyFinancialSnapshot.period_end_date))
                .limit(1)
            )
            snapshot: CompanyFinancialSnapshot | None = await self._session.scalar(snapshot_stmt)

            financials: dict[str, Any] = {}
            if snapshot is not None:
                financials = {
                    "period_end_date": snapshot.period_end_date,
                    "period_type": snapshot.period_type.value,
                    "revenue": snapshot.revenue,
                    "gross_profit": snapshot.gross_profit,
                    "ebitda": snapshot.ebitda,
                    "net_income": snapshot.net_income,
                    "gross_margin": snapshot.gross_margin,
                    "ebitda_margin": snapshot.ebitda_margin,
                    "net_margin": snapshot.net_margin,
                    "revenue_growth_yoy": snapshot.revenue_growth_yoy,
                    "total_assets": snapshot.total_assets,
                    "total_equity": snapshot.total_equity,
                    "total_debt": snapshot.total_debt,
                    "net_debt": snapshot.net_debt,
                    "roe": snapshot.roe,
                    "net_debt_ebitda": snapshot.net_debt_ebitda,
                    "operating_cash_flow": snapshot.operating_cash_flow,
                    "free_cash_flow": snapshot.free_cash_flow,
                    "cost_of_revenue": snapshot.cost_of_revenue,
                    "selling_general_administrative": snapshot.selling_general_administrative,
                    "research_development": snapshot.research_development,
                    "operating_income": snapshot.operating_income,
                    "sga_to_revenue": snapshot.sga_to_revenue,
                    "rnd_to_revenue": snapshot.rnd_to_revenue,
                    "operating_margin": snapshot.operating_margin,
                    "capex": snapshot.capex,
                    "capex_to_revenue": (
                        abs(snapshot.capex) / snapshot.revenue
                        if snapshot.capex is not None and snapshot.revenue and snapshot.revenue > 0
                        else None
                    ),
                }

            # Active executives
            exec_stmt = (
                select(CompanyExecutive)
                .where(
                    CompanyExecutive.listed_company_id == company.id,
                    CompanyExecutive.is_active.is_(True),
                )
                .order_by(CompanyExecutive.is_ceo.desc(), CompanyExecutive.name)
            )
            exec_result = await self._session.execute(exec_stmt)
            executives_rows: list[CompanyExecutive] = list(exec_result.scalars().all())

            executives = [
                {
                    "name": ex.name,
                    "title": ex.title,
                    "is_ceo": ex.is_ceo,
                    "is_cfo": ex.is_cfo,
                    "is_chair": ex.is_chair,
                    "since_date": ex.since_date,
                    "age": ex.age,
                }
                for ex in executives_rows
            ]

            logger.info(
                "market_intel.get_listed_company.ok",
                ticker=ticker,
                exchange=exchange,
            )
            return {
                "ticker": company.ticker,
                "exchange": company.exchange,
                "isin": company.isin,
                "name": company.name,
                "description": company.description,
                "website": company.website,
                "employees": company.employees,
                "address": company.address,
                "gics_sector": company.gics_sector,
                "gics_industry": company.gics_industry,
                "listing_type": company.listing_type.value if company.listing_type else None,
                "currency": company.currency,
                "market_cap_sgd": company.market_cap_sgd,
                "pe_ratio": company.pe_ratio,
                "ev_ebitda": company.ev_ebitda,
                "revenue_ttm_sgd": company.revenue_ttm_sgd,
                "gross_margin": company.gross_margin,
                "profit_margin": company.profit_margin,
                "roe": company.roe,
                "dividend_yield": company.dividend_yield,
                "is_reit": company.listing_type.value == "reit" if company.listing_type else False,
                "nav_per_unit": company.nav_per_unit,
                "dpu_ttm": company.dpu_ttm,
                "gearing_ratio": company.gearing_ratio,
                "last_synced_at": (
                    company.last_synced_at.isoformat() if company.last_synced_at else None
                ),
                "financials": financials,
                "executives": executives,
            }

        except Exception as exc:
            logger.warning(
                "market_intel.get_listed_company.error",
                ticker=ticker,
                exchange=exchange,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Tool 3: benchmark_company
    # ------------------------------------------------------------------

    async def benchmark_company(
        self, ticker: str, exchange: str = "SG"
    ) -> dict[str, Any]:
        """Return how a company ranks vs its vertical peers.

        Fetches the company's latest annual snapshot and the corresponding
        VerticalBenchmark, then uses FinancialBenchmarkEngine to compute
        per-metric percentile ranks.

        Args:
            ticker:   SGX stock code.
            exchange: Exchange identifier, default "SG".

        Returns:
            {company, vertical, period, metric_ranks, description, leaders, laggards}
            or {} when data is insufficient / on error.
        """
        try:
            # Fetch company
            company_stmt = (
                select(ListedCompany)
                .where(
                    ListedCompany.ticker == ticker,
                    ListedCompany.exchange == exchange,
                )
            )
            company: ListedCompany | None = await self._session.scalar(company_stmt)
            if company is None:
                logger.warning(
                    "market_intel.benchmark_company.no_company",
                    ticker=ticker,
                    exchange=exchange,
                )
                return {}

            if company.vertical_id is None:
                logger.warning(
                    "market_intel.benchmark_company.no_vertical",
                    ticker=ticker,
                )
                return {}

            # Fetch latest annual snapshot for this company
            snapshot_stmt = (
                select(CompanyFinancialSnapshot)
                .where(
                    CompanyFinancialSnapshot.company_id == company.id,
                    CompanyFinancialSnapshot.period_type == FinancialPeriodType.ANNUAL,
                )
                .order_by(desc(CompanyFinancialSnapshot.period_end_date))
                .limit(1)
            )
            snapshot: CompanyFinancialSnapshot | None = await self._session.scalar(snapshot_stmt)
            if snapshot is None:
                logger.warning(
                    "market_intel.benchmark_company.no_snapshot",
                    ticker=ticker,
                )
                return {}

            # Derive period_label from period_end_date (first 4 chars = fiscal year)
            period_label = snapshot.period_end_date[:4] if snapshot.period_end_date else ""

            # Fetch VerticalBenchmark for same vertical + period
            benchmark_stmt = (
                select(VerticalBenchmark)
                .where(
                    VerticalBenchmark.vertical_id == company.vertical_id,
                    VerticalBenchmark.period_type == FinancialPeriodType.ANNUAL,
                    VerticalBenchmark.period_label == period_label,
                )
                .order_by(desc(VerticalBenchmark.computed_at))
                .limit(1)
            )
            vb: VerticalBenchmark | None = await self._session.scalar(benchmark_stmt)

            if vb is None:
                # Fall back to the latest available benchmark for this vertical
                vb_latest_stmt = (
                    select(VerticalBenchmark)
                    .where(VerticalBenchmark.vertical_id == company.vertical_id)
                    .order_by(desc(VerticalBenchmark.computed_at))
                    .limit(1)
                )
                vb = await self._session.scalar(vb_latest_stmt)

            if vb is None:
                logger.warning(
                    "market_intel.benchmark_company.no_benchmark",
                    ticker=ticker,
                    period_label=period_label,
                )
                return {}

            # Fetch vertical eagerly (avoids lazy-load greenlet issue)
            vertical_stmt = select(MarketVertical).where(
                MarketVertical.id == company.vertical_id
            )
            vertical: MarketVertical | None = await self._session.scalar(vertical_stmt)

            # Reconstruct BenchmarkResult from the stored JSON distributions
            def _dist_from_dict(d: dict) -> PercentileDistribution:
                return PercentileDistribution(
                    p25=d.get("p25"),
                    p50=d.get("p50"),
                    p75=d.get("p75"),
                    p90=d.get("p90"),
                    mean=d.get("mean"),
                    sample_size=d.get("n", 0),
                )

            benchmark_result = BenchmarkResult(
                vertical_slug=vertical.slug if vertical else "",
                period_label=vb.period_label,
                period_type=vb.period_type.value,
                company_count=vb.company_count,
                revenue_growth_yoy=_dist_from_dict(vb.revenue_growth_yoy or {}),
                gross_margin=_dist_from_dict(vb.gross_margin or {}),
                ebitda_margin=_dist_from_dict(vb.ebitda_margin or {}),
                net_margin=_dist_from_dict(vb.net_margin or {}),
                roe=_dist_from_dict(vb.roe or {}),
                net_debt_ebitda=_dist_from_dict(vb.net_debt_ebitda or {}),
                revenue_ttm_sgd=_dist_from_dict(vb.revenue_ttm_sgd or {}),
                sga_to_revenue=_dist_from_dict(vb.sga_to_revenue or {}),
                rnd_to_revenue=_dist_from_dict(vb.rnd_to_revenue or {}),
                operating_margin=_dist_from_dict(vb.operating_margin_dist or {}),
                capex_to_revenue=_dist_from_dict(vb.capex_to_revenue or {}),
                leaders=vb.leaders or [],
                laggards=vb.laggards or [],
            )

            # Build CompanyMetrics from snapshot
            is_reit = (
                company.listing_type.value == "reit" if company.listing_type else False
            )
            company_metrics = CompanyMetrics(
                ticker=company.ticker,
                name=company.name,
                is_reit=is_reit,
                revenue_growth_yoy=snapshot.revenue_growth_yoy,
                gross_margin=snapshot.gross_margin,
                ebitda_margin=snapshot.ebitda_margin,
                net_margin=snapshot.net_margin,
                roe=snapshot.roe,
                net_debt_ebitda=snapshot.net_debt_ebitda,
                revenue_ttm_sgd=snapshot.revenue,
                sga_to_revenue=snapshot.sga_to_revenue,
                rnd_to_revenue=snapshot.rnd_to_revenue,
                operating_margin=snapshot.operating_margin,
                capex_to_revenue=(
                    abs(snapshot.capex) / snapshot.revenue
                    if snapshot.capex is not None and snapshot.revenue and snapshot.revenue > 0
                    else None
                ),
                dpu_yield=company.dividend_yield,
                gearing_ratio=company.gearing_ratio,
            )

            metric_ranks = self._benchmark_engine.rank_company(company_metrics, benchmark_result)
            description = self._benchmark_engine.describe_position(metric_ranks)

            logger.info(
                "market_intel.benchmark_company.ok",
                ticker=ticker,
                period=vb.period_label,
                metrics_ranked=len(metric_ranks),
            )
            return {
                "company": {
                    "ticker": company.ticker,
                    "exchange": company.exchange,
                    "name": company.name,
                },
                "vertical": {
                    "slug": vertical.slug if vertical else "",
                    "name": vertical.name if vertical else "",
                },
                "period": vb.period_label,
                "period_type": vb.period_type.value,
                "metric_ranks": metric_ranks,
                "description": description,
                "leaders": vb.leaders or [],
                "laggards": vb.laggards or [],
            }

        except Exception as exc:
            logger.warning(
                "market_intel.benchmark_company.error",
                ticker=ticker,
                exchange=exchange,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Name → benchmark helper (Competitor/Lead/Profiler agents)
    # ------------------------------------------------------------------

    async def find_and_benchmark_company_by_name(
        self, name: str, vertical_slug: str | None = None,
    ) -> dict[str, Any]:
        """Find a listed company by name and benchmark against its vertical.

        Strips common corporate suffixes, performs ILIKE search, fetches latest
        annual snapshot, and delegates to ``benchmark_company()``.

        Returns ``{"found": True, "company": {}, "financials": {}, "benchmark": {}}``
        or ``{"found": False}``.
        """
        try:
            import re as _re  # noqa: PLC0415

            stripped = _re.sub(
                r"\s*(Pte\.?\s*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|Co\.?\s*Ltd\.?|"
                r"Group|Holdings|Bhd\.?|Plc\.?|Limited|Corporation|PLC)\s*$",
                "", name.strip(), flags=_re.IGNORECASE,
            ).strip()
            if len(stripped) < 2:
                return {"found": False}

            stmt = (
                select(ListedCompany)
                .where(ListedCompany.is_active.is_(True), ListedCompany.name.ilike(f"%{_escape_like(stripped)}%", escape="\\"))
                .limit(5)
            )
            if vertical_slug:
                vert_id = await self._session.scalar(
                    select(MarketVertical.id).where(MarketVertical.slug == vertical_slug)
                )
                if vert_id:
                    stmt = stmt.where(ListedCompany.vertical_id == vert_id)

            candidates = list((await self._session.execute(stmt)).scalars().all())
            if not candidates:
                return {"found": False}

            company = min(candidates, key=lambda c: len(c.name))

            snapshot: CompanyFinancialSnapshot | None = await self._session.scalar(
                select(CompanyFinancialSnapshot)
                .where(
                    CompanyFinancialSnapshot.company_id == company.id,
                    CompanyFinancialSnapshot.period_type == FinancialPeriodType.ANNUAL,
                )
                .order_by(desc(CompanyFinancialSnapshot.period_end_date))
                .limit(1)
            )

            financials: dict[str, Any] = {}
            if snapshot:
                financials = {
                    "revenue": snapshot.revenue,
                    "gross_margin": snapshot.gross_margin,
                    "ebitda_margin": snapshot.ebitda_margin,
                    "net_margin": snapshot.net_margin,
                    "revenue_growth_yoy": snapshot.revenue_growth_yoy,
                    "roe": snapshot.roe,
                    "period_end_date": snapshot.period_end_date,
                }

            company_info = {
                "ticker": company.ticker, "exchange": company.exchange,
                "name": company.name, "employees": company.employees,
                "market_cap_sgd": company.market_cap_sgd,
            }

            benchmark: dict[str, Any] = {}
            if company.ticker and company.exchange:
                benchmark = await self.benchmark_company(company.ticker, company.exchange)

            return {"found": True, "company": company_info, "financials": financials, "benchmark": benchmark}

        except Exception as exc:
            logger.warning("market_intel.find_and_benchmark_by_name.error", name=name, error=str(exc))
            return {"found": False}

    # ------------------------------------------------------------------
    # Tool 4: search_market_intelligence
    # ------------------------------------------------------------------

    async def search_market_intelligence(
        self,
        query: str,
        vertical_slug: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search over market articles and corporate document chunks.

        Uses a three-tier search strategy, falling back gracefully:

          1. Qdrant ANN search (articles then chunks) — fastest, when configured
          2. Python cosine similarity — when embeddings available but Qdrant absent
          3. SQL LIKE text search — final fallback when no embeddings configured

        Args:
            query:        Natural language search string.
            vertical_slug: Restrict to a specific vertical (optional).
            limit:        Maximum results to return (default 10).

        Returns:
            List of {source, title, text_snippet, published_at, relevance_score}
            sorted by relevance_score descending.  Empty list on error.
        """
        try:
            results: list[dict[str, Any]] = []
            seen_keys: set[str] = set()

            query_vector = await self._get_query_vector(query)

            if query_vector is not None:
                qdrant = get_qdrant_store()

                if qdrant._enabled:
                    # --------------------------------------------------
                    # Tier 1a: Qdrant ANN — market articles
                    # --------------------------------------------------
                    article_hits = await qdrant.search_articles(
                        query_vector,
                        vertical_slug=vertical_slug,
                        limit=limit,
                    )
                    if article_hits:
                        article_ids = [
                            uuid.UUID(r.id) for r in article_hits if r.id
                        ]
                        if article_ids:
                            db_stmt = select(MarketArticle).where(
                                MarketArticle.id.in_(article_ids)
                            )
                            db_result = await self._session.execute(db_stmt)
                            db_articles = db_result.scalars().all()
                            score_by_id = {r.id: r.score for r in article_hits}
                            for a in db_articles:
                                key = a.title.lower()
                                if key in seen_keys:
                                    continue
                                seen_keys.add(key)
                                results.append(
                                    {
                                        "source": a.source_name,
                                        "title": a.title,
                                        "text_snippet": (a.summary or "")[:400],
                                        "section": None,
                                        "published_at": (
                                            a.published_at.isoformat()
                                            if a.published_at
                                            else None
                                        ),
                                        "relevance_score": score_by_id.get(
                                            str(a.id), 0.0
                                        ),
                                    }
                                )

                    # --------------------------------------------------
                    # Tier 1b: Qdrant ANN — document chunks
                    # --------------------------------------------------
                    chunk_hits = await qdrant.search_chunks(
                        query_vector,
                        limit=limit,
                    )
                    if chunk_hits:
                        chunk_ids = [
                            uuid.UUID(r.id) for r in chunk_hits if r.id
                        ]
                        if chunk_ids:
                            chunk_stmt = (
                                select(DocumentChunk, CompanyDocument, ListedCompany)
                                .join(
                                    CompanyDocument,
                                    DocumentChunk.document_id == CompanyDocument.id,
                                )
                                .join(
                                    ListedCompany,
                                    CompanyDocument.listed_company_id == ListedCompany.id,
                                )
                                .where(DocumentChunk.id.in_(chunk_ids))
                            )
                            chunk_result = await self._session.execute(chunk_stmt)
                            chunk_rows = chunk_result.all()
                            chunk_score_by_id = {r.id: r.score for r in chunk_hits}
                            for chunk, doc, company in chunk_rows:
                                key = doc.title.lower()
                                if key in seen_keys:
                                    continue
                                seen_keys.add(key)
                                results.append(
                                    {
                                        "source": company.name,
                                        "title": doc.title,
                                        "text_snippet": chunk.chunk_text[:400],
                                        "section": chunk.section_name,
                                        "published_at": None,
                                        "relevance_score": chunk_score_by_id.get(
                                            str(chunk.id), 0.0
                                        ),
                                    }
                                )

                else:
                    # --------------------------------------------------
                    # Tier 2a: Python cosine — market articles
                    # --------------------------------------------------
                    art_stmt = select(MarketArticle).where(
                        MarketArticle.embedding.isnot(None)
                    )
                    if vertical_slug is not None:
                        art_stmt = art_stmt.where(
                            MarketArticle.vertical_slug == vertical_slug
                        )
                    art_stmt = art_stmt.limit(500)
                    art_result = await self._session.execute(art_stmt)
                    candidate_articles = list(art_result.scalars().all())

                    article_candidates = [
                        (
                            str(a.id),
                            json.loads(a.embedding),
                            {
                                "source_name": a.source_name,
                                "title": a.title,
                                "summary": a.summary,
                                "published_at": (
                                    a.published_at.isoformat()
                                    if a.published_at
                                    else None
                                ),
                            },
                        )
                        for a in candidate_articles
                        if a.embedding
                    ]
                    art_sim_results = cosine_similarity_fallback(
                        query_vector, article_candidates, limit=limit
                    )
                    art_lookup = {str(a.id): a for a in candidate_articles}
                    for sr in art_sim_results:
                        a = art_lookup.get(sr.id)
                        if a is None:
                            continue
                        key = a.title.lower()
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        results.append(
                            {
                                "source": a.source_name,
                                "title": a.title,
                                "text_snippet": (a.summary or "")[:400],
                                "section": None,
                                "published_at": sr.payload.get("published_at"),
                                "relevance_score": sr.score,
                            }
                        )

                    # --------------------------------------------------
                    # Tier 2b: Python cosine — document chunks
                    # --------------------------------------------------
                    chunk_base_stmt = (
                        select(DocumentChunk, CompanyDocument, ListedCompany)
                        .join(
                            CompanyDocument,
                            DocumentChunk.document_id == CompanyDocument.id,
                        )
                        .join(
                            ListedCompany,
                            CompanyDocument.listed_company_id == ListedCompany.id,
                        )
                        .where(DocumentChunk.embedding.isnot(None))
                        .limit(500)
                    )
                    if vertical_slug is not None:
                        chunk_base_stmt = chunk_base_stmt.join(
                            MarketVertical,
                            ListedCompany.vertical_id == MarketVertical.id,
                        ).where(MarketVertical.slug == vertical_slug)
                    chunk_base_result = await self._session.execute(chunk_base_stmt)
                    chunk_base_rows = chunk_base_result.all()

                    chunk_candidates = [
                        (
                            str(chunk.id),
                            json.loads(chunk.embedding),
                            {
                                "document_title": doc.title,
                                "company_name": company.name,
                                "section_name": chunk.section_name,
                                "chunk_text": chunk.chunk_text,
                            },
                        )
                        for chunk, doc, company in chunk_base_rows
                        if chunk.embedding
                    ]
                    chunk_sim_results = cosine_similarity_fallback(
                        query_vector, chunk_candidates, limit=limit
                    )
                    chunk_meta = {
                        str(chunk.id): (chunk, doc, company)
                        for chunk, doc, company in chunk_base_rows
                    }
                    for sr in chunk_sim_results:
                        row = chunk_meta.get(sr.id)
                        if row is None:
                            continue
                        chunk, doc, company = row
                        key = doc.title.lower()
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        results.append(
                            {
                                "source": company.name,
                                "title": doc.title,
                                "text_snippet": chunk.chunk_text[:400],
                                "section": chunk.section_name,
                                "published_at": None,
                                "relevance_score": sr.score,
                            }
                        )

            if not results:
                # ----------------------------------------------------------
                # Tier 3: SQL LIKE fallback — articles
                # ----------------------------------------------------------
                like_pattern = f"%{_escape_like(query)}%"
                article_stmt = (
                    select(MarketArticle)
                    .where(MarketArticle.title.ilike(like_pattern, escape="\\"))
                    .order_by(desc(MarketArticle.published_at))
                    .limit(limit)
                )
                if vertical_slug is not None:
                    article_stmt = article_stmt.where(
                        MarketArticle.vertical_slug == vertical_slug
                    )
                article_result = await self._session.execute(article_stmt)
                like_articles: list[MarketArticle] = list(article_result.scalars().all())

                for article in like_articles:
                    key = article.title.lower()
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    results.append(
                        {
                            "source": article.source_name,
                            "title": article.title,
                            "text_snippet": (article.summary or "")[:400],
                            "section": None,
                            "published_at": (
                                article.published_at.isoformat()
                                if article.published_at
                                else None
                            ),
                            "relevance_score": 0.5,
                        }
                    )

                # SQL LIKE fallback — document chunks
                chunk_like_stmt = (
                    select(DocumentChunk, CompanyDocument, ListedCompany)
                    .join(
                        CompanyDocument,
                        DocumentChunk.document_id == CompanyDocument.id,
                    )
                    .join(
                        ListedCompany,
                        CompanyDocument.listed_company_id == ListedCompany.id,
                    )
                    .where(DocumentChunk.chunk_text.like(like_pattern, escape="\\"))
                    .limit(limit)
                )
                if vertical_slug is not None:
                    chunk_like_stmt = chunk_like_stmt.join(
                        MarketVertical,
                        ListedCompany.vertical_id == MarketVertical.id,
                    ).where(MarketVertical.slug == vertical_slug)
                chunk_like_result = await self._session.execute(chunk_like_stmt)
                for chunk, doc, company in chunk_like_result.all():
                    key = doc.title.lower()
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    results.append(
                        {
                            "source": company.name,
                            "title": doc.title,
                            "text_snippet": chunk.chunk_text[:400],
                            "section": chunk.section_name,
                            "published_at": None,
                            "relevance_score": 0.4,
                        }
                    )

            results.sort(key=lambda r: r["relevance_score"], reverse=True)

            logger.info(
                "market_intel.search_market_intelligence.ok",
                query=query[:80],
                results=len(results),
                used_qdrant=query_vector is not None and get_qdrant_store()._enabled,
            )
            return results

        except Exception as exc:
            logger.warning(
                "market_intel.search_market_intelligence.error",
                query=query[:80],
                error=str(exc),
            )
            return []

    # ------------------------------------------------------------------
    # Tool 5: get_executive_intelligence
    # ------------------------------------------------------------------

    async def get_executive_intelligence(
        self,
        executive_name: str,
        company_name: str | None = None,
    ) -> dict[str, Any]:
        """Return news mentions and profile for a named executive.

        Combines a live NewsAPI search (via ExecutiveIntelligenceService) with
        a DB profile lookup from CompanyExecutive.

        Args:
            executive_name: Full name, e.g. "Piyush Gupta".
            company_name:   Optional company name to narrow news search.

        Returns:
            {name, title, company, recent_news}  or {} on error.
        """
        try:
            # 1. DB profile lookup (ILIKE on name)
            name_pattern = f"%{_escape_like(executive_name)}%"
            exec_stmt = (
                select(CompanyExecutive)
                .where(CompanyExecutive.name.ilike(name_pattern, escape="\\"))
                .where(CompanyExecutive.is_active.is_(True))
                .limit(1)
            )
            exec_row: CompanyExecutive | None = await self._session.scalar(exec_stmt)

            profile: dict[str, Any] = {}
            if exec_row is not None:
                # Fetch associated company name via a second query (avoid lazy load)
                listed_stmt = select(ListedCompany).where(
                    ListedCompany.id == exec_row.listed_company_id
                )
                listed: ListedCompany | None = await self._session.scalar(listed_stmt)
                profile = {
                    "name": exec_row.name,
                    "title": exec_row.title,
                    "company": listed.name if listed else None,
                    "ticker": listed.ticker if listed else None,
                    "exchange": listed.exchange if listed else None,
                    "is_ceo": exec_row.is_ceo,
                    "is_cfo": exec_row.is_cfo,
                    "is_chair": exec_row.is_chair,
                    "since_date": exec_row.since_date,
                    "age": exec_row.age,
                    "bio": exec_row.bio[:300] if exec_row.bio else None,
                }
                # Use matched company_name from DB for news search if none provided
                if company_name is None and listed is not None:
                    company_name = listed.name

            # 2. Live news search
            intel_service = ExecutiveIntelligenceService(self._session)
            recent_news = await intel_service.search_executive_news(
                executive_name=executive_name,
                company_name=company_name,
            )

            logger.info(
                "market_intel.get_executive_intelligence.ok",
                name=executive_name,
                news_count=len(recent_news),
                has_profile=bool(profile),
            )
            return {
                "name": profile.get("name", executive_name),
                "title": profile.get("title"),
                "company": profile.get("company"),
                "ticker": profile.get("ticker"),
                "is_ceo": profile.get("is_ceo"),
                "is_cfo": profile.get("is_cfo"),
                "since_date": profile.get("since_date"),
                "age": profile.get("age"),
                "bio": profile.get("bio"),
                "recent_news": recent_news,
            }

        except Exception as exc:
            logger.warning(
                "market_intel.get_executive_intelligence.error",
                name=executive_name,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Tool 6: get_vertical_benchmarks
    # ------------------------------------------------------------------

    async def get_vertical_benchmarks(
        self,
        vertical_slug: str,
        period_label: str | None = None,
    ) -> dict[str, Any]:
        """Return full benchmark distributions for a vertical.

        Args:
            vertical_slug: e.g. "fintech", "logistics".
            period_label:  Exact label e.g. "2024".  When omitted, returns
                           the most recently computed benchmark.

        Returns:
            Full benchmark dict with all percentile distributions,
            or {} when not found / on error.
        """
        try:
            # Resolve vertical
            vertical_stmt = select(MarketVertical).where(
                MarketVertical.slug == vertical_slug
            )
            vertical: MarketVertical | None = await self._session.scalar(vertical_stmt)
            if vertical is None:
                logger.warning(
                    "market_intel.get_vertical_benchmarks.no_vertical",
                    slug=vertical_slug,
                )
                return {}

            # Build benchmark query
            benchmark_stmt = select(VerticalBenchmark).where(
                VerticalBenchmark.vertical_id == vertical.id
            )
            if period_label is not None:
                benchmark_stmt = benchmark_stmt.where(
                    VerticalBenchmark.period_label == period_label
                )
            benchmark_stmt = benchmark_stmt.order_by(desc(VerticalBenchmark.computed_at)).limit(1)

            vb: VerticalBenchmark | None = await self._session.scalar(benchmark_stmt)
            if vb is None:
                logger.warning(
                    "market_intel.get_vertical_benchmarks.no_benchmark",
                    slug=vertical_slug,
                    period_label=period_label,
                )
                return {}

            logger.info(
                "market_intel.get_vertical_benchmarks.ok",
                slug=vertical_slug,
                period=vb.period_label,
            )
            return {
                "vertical": {
                    "slug": vertical.slug,
                    "name": vertical.name,
                    "is_reit_vertical": vertical.is_reit_vertical,
                },
                "period_label": vb.period_label,
                "period_type": vb.period_type.value if vb.period_type else None,
                "company_count": vb.company_count,
                "computed_at": vb.computed_at.isoformat() if vb.computed_at else None,
                "distributions": {
                    "revenue_growth_yoy": vb.revenue_growth_yoy,
                    "gross_margin": vb.gross_margin,
                    "ebitda_margin": vb.ebitda_margin,
                    "net_margin": vb.net_margin,
                    "roe": vb.roe,
                    "net_debt_ebitda": vb.net_debt_ebitda,
                    "revenue_ttm_sgd": vb.revenue_ttm_sgd,
                    "sga_to_revenue": vb.sga_to_revenue,
                    "rnd_to_revenue": vb.rnd_to_revenue,
                    "operating_margin": vb.operating_margin_dist,
                    "capex_to_revenue": vb.capex_to_revenue or {},
                },
                "leaders": vb.leaders or [],
                "laggards": vb.laggards or [],
            }

        except Exception as exc:
            logger.warning(
                "market_intel.get_vertical_benchmarks.error",
                slug=vertical_slug,
                period_label=period_label,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Tool 7: get_company_gtm_profile
    # ------------------------------------------------------------------

    async def get_company_gtm_profile(
        self, ticker: str, exchange: str = "SG"
    ) -> dict[str, Any]:
        """Return a GTM-focused intelligence profile for a listed company.

        Combines financial spend analysis (SG&A, R&D, operating margin),
        ESG scores, analyst consensus, and peer benchmarking into a single
        profile designed for GTM advisory use.

        Args:
            ticker:   Stock code, e.g. "D05" (DBS), "AAPL" (Apple).
            exchange: Exchange identifier, default "SG".

        Returns:
            {company, gtm_spend, esg, analyst_consensus, peer_comparison,
             gtm_signals}
            or {} when not found / on error.
        """
        try:
            company_stmt = select(ListedCompany).where(
                ListedCompany.ticker == ticker,
                ListedCompany.exchange == exchange,
            )
            company: ListedCompany | None = await self._session.scalar(company_stmt)
            if company is None:
                logger.warning(
                    "market_intel.get_company_gtm_profile.not_found",
                    ticker=ticker,
                    exchange=exchange,
                )
                return {}

            # Fetch last 3 annual snapshots for trend analysis
            snapshots_stmt = (
                select(CompanyFinancialSnapshot)
                .where(
                    CompanyFinancialSnapshot.company_id == company.id,
                    CompanyFinancialSnapshot.period_type == FinancialPeriodType.ANNUAL,
                )
                .order_by(desc(CompanyFinancialSnapshot.period_end_date))
                .limit(3)
            )
            snap_result = await self._session.execute(snapshots_stmt)
            snapshots: list[CompanyFinancialSnapshot] = list(snap_result.scalars().all())

            if not snapshots:
                return {
                    "company": {"ticker": ticker, "exchange": exchange, "name": company.name},
                    "error": "no_financial_data",
                }

            latest = snapshots[0]

            # GTM spend analysis
            gtm_spend: dict[str, Any] = {
                "period": latest.period_end_date,
                "revenue_sgd": latest.revenue,
                "sga_sgd": latest.selling_general_administrative,
                "sga_to_revenue": latest.sga_to_revenue,
                "rnd_sgd": latest.research_development,
                "rnd_to_revenue": latest.rnd_to_revenue,
                "operating_margin": latest.operating_margin,
                "cost_of_revenue_sgd": latest.cost_of_revenue,
                "operating_income_sgd": latest.operating_income,
            }

            # Trend: SG&A and R&D intensity over available years
            trend: list[dict[str, Any]] = []
            for snap in snapshots:
                trend.append({
                    "period": snap.period_end_date,
                    "sga_to_revenue": snap.sga_to_revenue,
                    "rnd_to_revenue": snap.rnd_to_revenue,
                    "operating_margin": snap.operating_margin,
                    "revenue_growth_yoy": snap.revenue_growth_yoy,
                    "gross_margin": snap.gross_margin,
                })
            gtm_spend["trend"] = trend

            # ESG scores
            esg: dict[str, Any] = {
                "total_score": company.esg_score,
                "environment": company.esg_environment,
                "social": company.esg_social,
                "governance": company.esg_governance,
            }

            # Analyst consensus
            analyst: dict[str, Any] = {
                "rating": company.analyst_rating,
                "target_price": company.analyst_target_price,
                "analyst_count": company.analyst_count,
            }

            # Peer comparison — rank against vertical benchmark
            peer_comparison: dict[str, Any] = {}
            if company.vertical_id is not None:
                benchmark_stmt = (
                    select(VerticalBenchmark)
                    .where(
                        VerticalBenchmark.vertical_id == company.vertical_id,
                        VerticalBenchmark.period_type == FinancialPeriodType.ANNUAL,
                    )
                    .order_by(desc(VerticalBenchmark.computed_at))
                    .limit(1)
                )
                vb: VerticalBenchmark | None = await self._session.scalar(benchmark_stmt)

                if vb is not None:
                    # Fetch vertical explicitly (avoids lazy-load greenlet issue)
                    vert_stmt = select(MarketVertical).where(
                        MarketVertical.id == company.vertical_id
                    )
                    vertical: MarketVertical | None = await self._session.scalar(vert_stmt)
                    vert_slug = vertical.slug if vertical else ""
                    vert_name = vertical.name if vertical else ""

                    def _dist(d: dict) -> PercentileDistribution:
                        return PercentileDistribution(
                            p25=d.get("p25"), p50=d.get("p50"),
                            p75=d.get("p75"), p90=d.get("p90"),
                            mean=d.get("mean"), sample_size=d.get("n", 0),
                        )

                    is_reit = (
                        company.listing_type.value == "reit" if company.listing_type else False
                    )
                    company_metrics = CompanyMetrics(
                        ticker=company.ticker,
                        name=company.name,
                        is_reit=is_reit,
                        revenue_growth_yoy=latest.revenue_growth_yoy,
                        gross_margin=latest.gross_margin,
                        ebitda_margin=latest.ebitda_margin,
                        net_margin=latest.net_margin,
                        roe=latest.roe,
                        net_debt_ebitda=latest.net_debt_ebitda,
                        revenue_ttm_sgd=latest.revenue,
                        sga_to_revenue=latest.sga_to_revenue,
                        rnd_to_revenue=latest.rnd_to_revenue,
                        operating_margin=latest.operating_margin,
                        capex_to_revenue=(
                            abs(latest.capex) / latest.revenue
                            if latest.capex is not None and latest.revenue and latest.revenue > 0
                            else None
                        ),
                        dpu_yield=company.dividend_yield,
                        gearing_ratio=company.gearing_ratio,
                    )

                    benchmark_result = BenchmarkResult(
                        vertical_slug=vert_slug,
                        period_label=vb.period_label,
                        period_type=vb.period_type.value,
                        company_count=vb.company_count,
                        revenue_growth_yoy=_dist(vb.revenue_growth_yoy or {}),
                        gross_margin=_dist(vb.gross_margin or {}),
                        ebitda_margin=_dist(vb.ebitda_margin or {}),
                        net_margin=_dist(vb.net_margin or {}),
                        roe=_dist(vb.roe or {}),
                        net_debt_ebitda=_dist(vb.net_debt_ebitda or {}),
                        revenue_ttm_sgd=_dist(vb.revenue_ttm_sgd or {}),
                        sga_to_revenue=_dist(vb.sga_to_revenue or {}),
                        rnd_to_revenue=_dist(vb.rnd_to_revenue or {}),
                        operating_margin=_dist(vb.operating_margin_dist or {}),
                        capex_to_revenue=_dist(vb.capex_to_revenue or {}),
                        leaders=vb.leaders or [],
                        laggards=vb.laggards or [],
                    )

                    ranks = self._benchmark_engine.rank_company(company_metrics, benchmark_result)
                    peer_comparison = {
                        "vertical_slug": vert_slug,
                        "vertical_name": vert_name,
                        "period": vb.period_label,
                        "peer_count": vb.company_count,
                        "metric_ranks": ranks,
                        "description": self._benchmark_engine.describe_position(ranks),
                    }

            # GTM signals — derive actionable insights from the data
            gtm_signals: list[str] = []
            if latest.sga_to_revenue is not None:
                if latest.sga_to_revenue > 0.40:
                    gtm_signals.append(
                        f"High SG&A intensity ({latest.sga_to_revenue:.0%}) — "
                        "aggressive market investment; may be receptive to efficiency tools."
                    )
                elif latest.sga_to_revenue < 0.15:
                    gtm_signals.append(
                        f"Low SG&A intensity ({latest.sga_to_revenue:.0%}) — "
                        "lean operation; may need help scaling GTM."
                    )
            if latest.rnd_to_revenue is not None and latest.rnd_to_revenue > 0.15:
                gtm_signals.append(
                    f"R&D-intensive ({latest.rnd_to_revenue:.0%} of revenue) — "
                    "product-led growth; position technical solutions."
                )
            if company.esg_score is not None and company.esg_score > 70:
                gtm_signals.append(
                    f"Strong ESG profile (score: {company.esg_score:.0f}) — "
                    "sustainability messaging resonates."
                )
            if len(snapshots) >= 2:
                prev = snapshots[1]
                if (
                    latest.sga_to_revenue is not None
                    and prev.sga_to_revenue is not None
                    and latest.sga_to_revenue > prev.sga_to_revenue * 1.15
                ):
                    gtm_signals.append(
                        "SG&A spending accelerating YoY (>15% increase) — "
                        "company is investing in growth."
                    )
                elif (
                    latest.sga_to_revenue is not None
                    and prev.sga_to_revenue is not None
                    and latest.sga_to_revenue < prev.sga_to_revenue * 0.85
                ):
                    gtm_signals.append(
                        "SG&A spending contracting YoY (>15% decrease) — "
                        "cost-cutting mode; position ROI-focused solutions."
                    )

            logger.info(
                "market_intel.get_company_gtm_profile.ok",
                ticker=ticker,
                exchange=exchange,
                signals=len(gtm_signals),
            )
            return {
                "company": {
                    "ticker": company.ticker,
                    "exchange": company.exchange,
                    "name": company.name,
                    "description": company.description,
                    "employees": company.employees,
                    "market_cap_sgd": company.market_cap_sgd,
                },
                "gtm_spend": gtm_spend,
                "esg": esg,
                "analyst_consensus": analyst,
                "peer_comparison": peer_comparison,
                "gtm_signals": gtm_signals,
            }

        except Exception as exc:
            logger.warning(
                "market_intel.get_company_gtm_profile.error",
                ticker=ticker,
                exchange=exchange,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Tool 8: get_company_trajectory
    # ------------------------------------------------------------------

    async def get_company_trajectory(
        self, ticker: str, exchange: str = "SG"
    ) -> dict[str, Any]:
        """Return growth trajectory analysis for a listed company.

        Loads the last 5 years of CompanyFinancialSnapshot (annual) and
        computes trajectory metrics using TrajectoryEngine: CAGR, margin
        trends, SG&A efficiency, acceleration classification, and a
        deterministic narrative.

        Args:
            ticker:   Stock code, e.g. "D05" (DBS), "AAPL".
            exchange: Exchange identifier, default "SG".

        Returns:
            TrajectoryReport as dict, or {} on error / insufficient data.
        """
        try:
            from packages.scoring.src.trajectory import TrajectoryEngine

            company_stmt = select(ListedCompany).where(
                ListedCompany.ticker == ticker,
                ListedCompany.exchange == exchange,
            )
            company: ListedCompany | None = await self._session.scalar(company_stmt)
            if company is None:
                return {}

            # Load last 5 years of annual snapshots, oldest first
            snapshots_stmt = (
                select(CompanyFinancialSnapshot)
                .where(
                    CompanyFinancialSnapshot.company_id == company.id,
                    CompanyFinancialSnapshot.period_type == FinancialPeriodType.ANNUAL,
                )
                .order_by(CompanyFinancialSnapshot.period_end_date.asc())
                .limit(5)
            )
            snap_result = await self._session.execute(snapshots_stmt)
            snapshots: list[CompanyFinancialSnapshot] = list(snap_result.scalars().all())

            if not snapshots:
                return {"company": {"ticker": ticker, "name": company.name}, "error": "no_financial_data"}

            # Convert ORM objects to dicts for the engine
            snapshot_dicts = [
                {
                    "ticker": company.ticker,
                    "name": company.name,
                    "revenue": s.revenue,
                    "gross_margin": s.gross_margin,
                    "operating_margin": s.operating_margin,
                    "net_margin": s.net_margin,
                    "sga_to_revenue": s.sga_to_revenue,
                    "rnd_to_revenue": s.rnd_to_revenue,
                    "free_cash_flow": s.free_cash_flow,
                    "revenue_growth_yoy": s.revenue_growth_yoy,
                    "period_end_date": s.period_end_date,
                }
                for s in snapshots
            ]

            engine = TrajectoryEngine()
            report = engine.compute(snapshot_dicts)

            logger.info(
                "market_intel.get_company_trajectory.ok",
                ticker=ticker,
                periods=report.periods_analyzed,
                trajectory=report.trajectory_class,
            )
            return report.to_dict()

        except Exception as exc:
            logger.warning(
                "market_intel.get_company_trajectory.error",
                ticker=ticker,
                exchange=exchange,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Tool 9: get_gtm_intelligence
    # ------------------------------------------------------------------

    async def get_gtm_intelligence(
        self, ticker: str, exchange: str = "SG"
    ) -> list[dict[str, Any]]:
        """Return extracted GTM intelligence signals for a company.

        Queries SignalEvent rows where source starts with 'GTMIntel' and
        the linked company matches the given ticker/exchange.

        Args:
            ticker:   Stock code.
            exchange: Exchange identifier, default "SG".

        Returns:
            List of GTM signal dicts, or [] on error.
        """
        try:
            company_stmt = select(ListedCompany).where(
                ListedCompany.ticker == ticker,
                ListedCompany.exchange == exchange,
            )
            company: ListedCompany | None = await self._session.scalar(company_stmt)
            if company is None:
                return []

            # GTM intel signals are stored with source LIKE 'GTMIntel%',
            # source_url LIKE 'gtm_intel:%', and headline starts with
            # "GTM Profile: {ticker}".  Filter by headline prefix for
            # accurate per-company results.
            headline_prefix = f"GTM Profile: {_escape_like(ticker)} %"
            signals_stmt = (
                select(SignalEvent)
                .where(
                    SignalEvent.source.like("GTMIntel%"),
                    SignalEvent.source_url.like("gtm_intel:%"),
                    SignalEvent.headline.like(headline_prefix, escape="\\"),
                )
                .order_by(desc(SignalEvent.created_at))
                .limit(20)
            )
            result = await self._session.execute(signals_stmt)
            signals: list[SignalEvent] = list(result.scalars().all())

            if not signals:
                return []

            logger.info(
                "market_intel.get_gtm_intelligence.ok",
                ticker=ticker,
                signals_found=len(signals),
            )

            results: list[dict[str, Any]] = []
            for s in signals:
                entry: dict[str, Any] = {
                    "headline": s.headline,
                    "summary": s.summary,
                    "source": s.source,
                    "relevance_score": s.relevance_score,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                # Parse structured metadata from recommended_action JSON
                if s.recommended_action:
                    try:
                        entry["metadata"] = json.loads(s.recommended_action)
                    except (json.JSONDecodeError, TypeError):
                        pass
                results.append(entry)

            return results

        except Exception as exc:
            logger.warning(
                "market_intel.get_gtm_intelligence.error",
                ticker=ticker,
                exchange=exchange,
                error=str(exc),
            )
            return []

    # ------------------------------------------------------------------
    # Tool 10: get_vertical_intelligence
    # ------------------------------------------------------------------

    async def get_vertical_intelligence(
        self, vertical_slug: str
    ) -> dict[str, Any]:
        """Return the current synthesized intelligence report for a vertical.

        This is the primary tool for agents needing deep industry knowledge.
        Returns the latest VerticalIntelligenceReport which includes market
        overview, key trends, competitive dynamics, financial pulse (SG&A/R&D
        trends), signal digest, executive movements, and actionable GTM
        implications.

        Args:
            vertical_slug: e.g. "fintech", "ict_saas", "biomedical"

        Returns:
            Full intelligence report dict, or {} when no report is available.
        """
        try:
            from packages.database.src.models import VerticalIntelligenceReport

            # Find the current report for this vertical
            vert_stmt = select(MarketVertical).where(
                MarketVertical.slug == vertical_slug
            )
            vertical: MarketVertical | None = await self._session.scalar(vert_stmt)
            if vertical is None:
                logger.warning(
                    "market_intel.get_vertical_intelligence.no_vertical",
                    slug=vertical_slug,
                )
                return {}

            report_stmt = (
                select(VerticalIntelligenceReport)
                .where(
                    VerticalIntelligenceReport.vertical_id == vertical.id,
                    VerticalIntelligenceReport.is_current.is_(True),
                )
                .order_by(desc(VerticalIntelligenceReport.computed_at))
                .limit(1)
            )
            report: VerticalIntelligenceReport | None = await self._session.scalar(report_stmt)

            if report is None:
                logger.warning(
                    "market_intel.get_vertical_intelligence.no_report",
                    slug=vertical_slug,
                )
                return {}

            logger.info(
                "market_intel.get_vertical_intelligence.ok",
                slug=vertical_slug,
                period=report.report_period,
            )
            return {
                "vertical": {
                    "slug": vertical.slug,
                    "name": vertical.name,
                },
                "report_period": report.report_period,
                "computed_at": report.computed_at.isoformat() if report.computed_at else None,
                "market_overview": report.market_overview,
                "key_trends": report.key_trends,
                "competitive_dynamics": report.competitive_dynamics,
                "financial_pulse": report.financial_pulse,
                "signal_digest": report.signal_digest,
                "executive_movements": report.executive_movements,
                "regulatory_environment": report.regulatory_environment,
                "gtm_implications": report.gtm_implications,
                "data_sources": report.data_sources,
            }

        except Exception as exc:
            logger.warning(
                "market_intel.get_vertical_intelligence.error",
                slug=vertical_slug,
                error=str(exc),
            )
            return {}
