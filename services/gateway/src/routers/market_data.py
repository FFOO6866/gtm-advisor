"""Market Data router — exposes KB intelligence to the frontend.

Endpoints:
  GET /{company_id}/market-data/vertical-summary    — vertical benchmarks + landscape
  GET /{company_id}/market-data/competitor-signals   — competitor move signals
  GET /{company_id}/market-data/industry-signals     — market/industry signals
  GET /{company_id}/market-data/pipeline-summary     — lead pipeline stats
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.models import (
    Analysis,
    Company,
    Lead,
    ListedCompany,
    MarketArticle,
    MarketVertical,
    SignalEvent,
    SignalType,
    VerticalBenchmark,
)
from packages.database.src.models import AnalysisStatus as DBAnalysisStatus
from packages.database.src.session import get_db_session

from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PercentileResponse(BaseModel):
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None


class BenchmarkPeriodResponse(BaseModel):
    period_label: str
    period_type: str
    company_count: int
    revenue_growth_yoy: PercentileResponse | None = None
    gross_margin: PercentileResponse | None = None
    ebitda_margin: PercentileResponse | None = None
    net_margin: PercentileResponse | None = None
    roe: PercentileResponse | None = None
    sga_to_revenue: PercentileResponse | None = None
    rnd_to_revenue: PercentileResponse | None = None
    operating_margin: PercentileResponse | None = None
    computed_at: str | None = None


class LeaderLaggardResponse(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None
    revenue_growth_yoy: float | None = None
    gross_margin: float | None = None
    sga_to_revenue: float | None = None
    rnd_to_revenue: float | None = None


class VerticalSummaryResponse(BaseModel):
    vertical_slug: str | None = None
    vertical_name: str | None = None
    listed_companies_count: int = 0
    market_cap_total_sgd: float | None = None
    benchmarks: list[BenchmarkPeriodResponse] = []
    leaders: list[LeaderLaggardResponse] = []
    laggards: list[LeaderLaggardResponse] = []


class MarketSignalResponse(BaseModel):
    id: str
    signal_type: str
    urgency: str
    headline: str
    summary: str | None = None
    source: str | None = None
    source_url: str | None = None
    relevance_score: float = 0.0
    recommended_action: str | None = None
    published_at: str | None = None
    created_at: str


class MarketArticleResponse(BaseModel):
    id: str
    title: str
    source_name: str | None = None
    signal_type: str | None = None
    published_at: str | None = None
    source_url: str | None = None


class IndustrySignalsResponse(BaseModel):
    signals: list[MarketSignalResponse] = []
    articles: list[MarketArticleResponse] = []


class PipelineStatusCount(BaseModel):
    status: str
    count: int


class RecentLeadResponse(BaseModel):
    id: str
    lead_company_name: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    fit_score: int = 0
    overall_score: int = 0
    status: str = "new"
    created_at: str | None = None
    # Intelligence fields — why this lead, what's the angle
    pain_points: list[str] = []
    trigger_events: list[str] = []
    recommended_approach: str | None = None


class PipelineSummaryResponse(BaseModel):
    total_leads: int = 0
    by_status: list[PipelineStatusCount] = []
    avg_fit_score: float | None = None
    avg_overall_score: float | None = None
    recent_leads: list[RecentLeadResponse] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile_from_json(data: dict | list | None) -> PercentileResponse | None:
    """Safely parse a JSON percentile distribution."""
    if not data or not isinstance(data, dict):
        return None
    return PercentileResponse(
        p25=data.get("p25"),
        p50=data.get("p50"),
        p75=data.get("p75"),
        p90=data.get("p90"),
    )


async def _resolve_vertical(
    industry: str | None, db: AsyncSession
) -> MarketVertical | None:
    """Resolve a company industry string to its MarketVertical."""
    if not industry:
        return None
    slug = detect_vertical_slug(industry)
    if not slug:
        return None
    stmt = select(MarketVertical).where(MarketVertical.slug == slug)
    return await db.scalar(stmt)


def _leader_from_dict(item: dict) -> LeaderLaggardResponse:
    """Convert a benchmark leader/laggard snapshot dict to response."""
    return LeaderLaggardResponse(
        ticker=item.get("ticker", ""),
        name=item.get("name", ""),
        exchange=item.get("exchange"),
        revenue_growth_yoy=item.get("revenue_growth_yoy"),
        gross_margin=item.get("gross_margin"),
        sga_to_revenue=item.get("sga_to_revenue"),
        rnd_to_revenue=item.get("rnd_to_revenue"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/market-data/vertical-summary",
    response_model=VerticalSummaryResponse,
)
async def vertical_summary(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> VerticalSummaryResponse:
    """Vertical benchmarks, company count, leaders/laggards for the user's industry."""
    await validate_company_access(company_id, current_user, db)

    # Fetch company to get industry (identity map caches the db.get from validate_company_access)
    company = await db.get(Company, company_id)
    vertical = await _resolve_vertical(company.industry if company else None, db)
    if not vertical:
        return VerticalSummaryResponse()

    # Aggregate stats
    agg_stmt = (
        select(
            func.count(ListedCompany.id).label("cnt"),
            func.sum(ListedCompany.market_cap_sgd).label("mcap"),
        )
        .where(
            ListedCompany.vertical_id == vertical.id,
            ListedCompany.is_active.is_(True),
        )
    )
    agg = (await db.execute(agg_stmt)).one()

    # Latest benchmarks (up to 4: annual + quarterly × 2 periods)
    bench_stmt = (
        select(VerticalBenchmark)
        .where(VerticalBenchmark.vertical_id == vertical.id)
        .order_by(desc(VerticalBenchmark.computed_at))
        .limit(4)
    )
    benchmarks_rows = (await db.execute(bench_stmt)).scalars().all()

    benchmarks: list[BenchmarkPeriodResponse] = []
    leaders: list[LeaderLaggardResponse] = []
    laggards: list[LeaderLaggardResponse] = []

    for b in benchmarks_rows:
        benchmarks.append(
            BenchmarkPeriodResponse(
                period_label=b.period_label,
                period_type=b.period_type.value if b.period_type else "annual",
                company_count=b.company_count or 0,
                revenue_growth_yoy=_percentile_from_json(b.revenue_growth_yoy),
                gross_margin=_percentile_from_json(b.gross_margin),
                ebitda_margin=_percentile_from_json(b.ebitda_margin),
                net_margin=_percentile_from_json(b.net_margin),
                roe=_percentile_from_json(b.roe),
                sga_to_revenue=_percentile_from_json(b.sga_to_revenue),
                rnd_to_revenue=_percentile_from_json(b.rnd_to_revenue),
                operating_margin=_percentile_from_json(b.operating_margin_dist),
                computed_at=b.computed_at.isoformat() if b.computed_at else None,
            )
        )
        # Leaders/laggards from the first (latest) benchmark only
        if not leaders:
            leaders = [_leader_from_dict(item) for item in (b.leaders or [])]
            laggards = [_leader_from_dict(item) for item in (b.laggards or [])]

    return VerticalSummaryResponse(
        vertical_slug=vertical.slug,
        vertical_name=vertical.name,
        listed_companies_count=agg.cnt or 0,
        market_cap_total_sgd=agg.mcap,
        benchmarks=benchmarks,
        leaders=leaders,
        laggards=laggards,
    )


@router.get(
    "/{company_id}/market-data/competitor-signals",
    response_model=list[MarketSignalResponse],
)
async def competitor_signals(
    company_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[MarketSignalResponse]:
    """Competitor-related signals: acquisitions, product launches, funding, partnerships."""
    await validate_company_access(company_id, current_user, db)
    competitor_types = {
        SignalType.COMPETITOR_NEWS,
        SignalType.ACQUISITION,
        SignalType.PRODUCT_LAUNCH,
        SignalType.PARTNERSHIP,
        SignalType.FUNDING,
    }
    stmt = (
        select(SignalEvent)
        .where(
            SignalEvent.company_id == company_id,
            SignalEvent.signal_type.in_(competitor_types),
        )
        .order_by(desc(SignalEvent.created_at))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_market_signal(s) for s in rows]


@router.get(
    "/{company_id}/market-data/industry-signals",
    response_model=IndustrySignalsResponse,
)
async def industry_signals(
    company_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> IndustrySignalsResponse:
    """Industry/market signals plus recent market articles for the vertical."""
    await validate_company_access(company_id, current_user, db)

    # SignalEvent rows for industry types
    industry_types = {
        SignalType.MARKET_TREND,
        SignalType.REGULATION,
        SignalType.EXPANSION,
        SignalType.GENERAL_NEWS,
        SignalType.HIRING,
        SignalType.LAYOFF,
    }
    sig_stmt = (
        select(SignalEvent)
        .where(
            SignalEvent.company_id == company_id,
            SignalEvent.signal_type.in_(industry_types),
        )
        .order_by(desc(SignalEvent.created_at))
        .limit(limit)
    )
    sig_rows = (await db.execute(sig_stmt)).scalars().all()

    # MarketArticle rows for the vertical (recent 7 days)
    company = await db.get(Company, company_id)
    vertical = await _resolve_vertical(company.industry if company else None, db)
    articles: list[MarketArticleResponse] = []
    if vertical:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
        art_stmt = (
            select(MarketArticle)
            .where(
                MarketArticle.vertical_slug == vertical.slug,
                MarketArticle.published_at >= cutoff,
            )
            .order_by(desc(MarketArticle.published_at))
            .limit(limit)
        )
        art_rows = (await db.execute(art_stmt)).scalars().all()
        articles = [
            MarketArticleResponse(
                id=str(a.id),
                title=a.title,
                source_name=a.source_name,
                signal_type=a.signal_type,
                published_at=a.published_at.isoformat() if a.published_at else None,
                source_url=a.source_url,
            )
            for a in art_rows
        ]

    return IndustrySignalsResponse(
        signals=[_to_market_signal(s) for s in sig_rows],
        articles=articles,
    )


@router.get(
    "/{company_id}/market-data/pipeline-summary",
    response_model=PipelineSummaryResponse,
)
async def pipeline_summary(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> PipelineSummaryResponse:
    """Lead pipeline stats: counts by status, averages, recent leads."""
    await validate_company_access(company_id, current_user, db)

    # Counts by status
    status_stmt = (
        select(
            Lead.status,
            func.count(Lead.id).label("cnt"),
        )
        .where(Lead.company_id == company_id)
        .group_by(Lead.status)
    )
    status_rows = (await db.execute(status_stmt)).all()
    by_status = [
        PipelineStatusCount(
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            count=row.cnt,
        )
        for row in status_rows
    ]
    total = sum(s.count for s in by_status)

    # Averages
    avg_stmt = (
        select(
            func.avg(Lead.fit_score).label("avg_fit"),
            func.avg(Lead.overall_score).label("avg_overall"),
        )
        .where(Lead.company_id == company_id)
    )
    avg_row = (await db.execute(avg_stmt)).one()

    # Recent 5 leads — surface the BEST leads (highest fit_score), not the most
    # recently created ones.  Minimum quality threshold of 40 (out of 100) prevents
    # low-quality bulk-generated leads from flooding the TodayPage pipeline card.
    _MIN_FIT_SCORE = 40
    recent_stmt = (
        select(Lead)
        .where(
            Lead.company_id == company_id,
            Lead.fit_score >= _MIN_FIT_SCORE,
        )
        .order_by(desc(Lead.fit_score), desc(Lead.created_at))
        .limit(5)
    )
    recent_rows = (await db.execute(recent_stmt)).scalars().all()

    # Fallback: if no leads meet the quality bar, return the top 5 by fit_score
    # with a capped display so the section renders something rather than nothing.
    if not recent_rows:
        fallback_stmt = (
            select(Lead)
            .where(Lead.company_id == company_id)
            .order_by(desc(Lead.fit_score), desc(Lead.created_at))
            .limit(5)
        )
        recent_rows = (await db.execute(fallback_stmt)).scalars().all()

    # Normalise trigger_events: strip entries that look like generic news headlines
    # (contains "CFO", "tariff", "layoff") rather than company-specific buying signals.
    _GENERIC_TRIGGER_SUBSTRINGS = {"CFO", "tariff", "layoff", "earnings", "stock"}

    def _is_relevant_trigger(event: str) -> bool:
        ev_lower = event.lower()
        return not any(s.lower() in ev_lower for s in _GENERIC_TRIGGER_SUBSTRINGS)

    recent_leads = [
        RecentLeadResponse(
            id=str(r.id),
            lead_company_name=r.lead_company_name,
            contact_name=r.contact_name,
            contact_title=r.contact_title,
            fit_score=r.fit_score or 0,
            overall_score=r.overall_score or 0,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            created_at=r.created_at.isoformat() if r.created_at else None,
            pain_points=r.pain_points or [],
            trigger_events=[e for e in (r.trigger_events or []) if _is_relevant_trigger(e)],
            recommended_approach=r.recommended_approach,
        )
        for r in recent_rows
    ]

    return PipelineSummaryResponse(
        total_leads=total,
        by_status=by_status,
        avg_fit_score=round(avg_row.avg_fit, 1) if avg_row.avg_fit is not None else None,
        avg_overall_score=round(avg_row.avg_overall, 1) if avg_row.avg_overall is not None else None,
        recent_leads=recent_leads,
    )


# ---------------------------------------------------------------------------
# Briefing Status (lightweight check for TodayPage auto-trigger)
# ---------------------------------------------------------------------------


class BriefingStatusResponse(BaseModel):
    has_completed_analysis: bool = False
    last_analysis_at: str | None = None


@router.get(
    "/{company_id}/market-data/briefing-status",
    response_model=BriefingStatusResponse,
)
async def briefing_status(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> BriefingStatusResponse:
    """Check if this company has ever had a completed analysis."""
    await validate_company_access(company_id, current_user, db)

    stmt = (
        select(Analysis.created_at)
        .where(Analysis.company_id == company_id, Analysis.status == DBAnalysisStatus.COMPLETED)
        .order_by(desc(Analysis.created_at))
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return BriefingStatusResponse(
        has_completed_analysis=row is not None,
        last_analysis_at=row.isoformat() if row else None,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_market_signal(s: SignalEvent) -> MarketSignalResponse:
    return MarketSignalResponse(
        id=str(s.id),
        signal_type=s.signal_type.value if hasattr(s.signal_type, "value") else str(s.signal_type),
        urgency=s.urgency.value if hasattr(s.urgency, "value") else str(s.urgency),
        headline=s.headline,
        summary=s.summary,
        source=s.source,
        source_url=s.source_url,
        relevance_score=s.relevance_score or 0.0,
        recommended_action=s.recommended_action,
        published_at=s.published_at.isoformat() if s.published_at else None,
        created_at=s.created_at.isoformat() if s.created_at else "",
    )
