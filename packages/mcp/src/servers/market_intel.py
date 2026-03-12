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


class MarketIntelMCPServer:
    """MCP server providing Singapore Market Intelligence tools to GTM agents.

    Tools:
      get_vertical_landscape        — overview of a vertical (companies, market cap, benchmarks)
      get_listed_company            — full profile for a listed company
      benchmark_company             — how a company ranks vs its vertical peers
      search_market_intelligence    — semantic search over annual reports + news
      get_executive_intelligence    — executive profiles and news monitoring
      get_vertical_benchmarks       — full benchmark distributions
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
                vertical_slug=vb.vertical.slug if vb.vertical else "",
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
                dpu_yield=company.dividend_yield,
                gearing_ratio=company.gearing_ratio,
            )

            metric_ranks = self._benchmark_engine.rank_company(company_metrics, benchmark_result)
            description = self._benchmark_engine.describe_position(metric_ranks)

            # Fetch vertical name for display
            vertical_stmt = select(MarketVertical).where(
                MarketVertical.id == company.vertical_id
            )
            vertical: MarketVertical | None = await self._session.scalar(vertical_stmt)

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
                like_pattern = f"%{query}%"
                article_stmt = (
                    select(MarketArticle)
                    .where(MarketArticle.title.ilike(like_pattern))
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
                    .where(DocumentChunk.chunk_text.like(like_pattern))
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
            name_pattern = f"%{executive_name}%"
            exec_stmt = (
                select(CompanyExecutive)
                .where(CompanyExecutive.name.ilike(name_pattern))
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
