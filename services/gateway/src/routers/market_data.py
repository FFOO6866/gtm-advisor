"""Market Data router — exposes KB intelligence to the frontend.

Endpoints:
  GET /{company_id}/market-data/vertical-summary          — vertical benchmarks + landscape
  GET /{company_id}/market-data/competitor-signals         — competitor move signals
  GET /{company_id}/market-data/industry-signals           — market/industry signals
  GET /{company_id}/market-data/pipeline-summary           — lead pipeline stats
  GET /{company_id}/market-data/vertical-intelligence      — full vertical intelligence report
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
    VerticalIntelligenceReport,
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


class GTMImplicationResponse(BaseModel):
    insight: str
    evidence: str | None = None
    recommended_action: str | None = None
    priority: str | None = None


class FinancialPulseResponse(BaseModel):
    sga_median: float | None = None
    sga_trend: str | None = None
    rnd_median: float | None = None
    rnd_trend: str | None = None
    margin_compression_or_expansion: str | None = None
    capex_intensity: float | None = None
    top_spenders: list[dict] = []


class CompetitiveDynamicsResponse(BaseModel):
    leaders: list[dict] = []
    challengers: list[dict] = []
    movers: list[dict] = []
    new_entrants: list[dict] = []
    exits: list[dict] = []


class SignalDigestItem(BaseModel):
    headline: str
    signal_type: str | None = None
    source: str | None = None
    published_at: str | None = None
    companies_mentioned: list[str] = []


class ExecutiveMovementResponse(BaseModel):
    company: str | None = None
    name: str | None = None
    old_title: str | None = None
    new_title: str | None = None
    change_type: str | None = None
    date: str | None = None


class RegulatoryItemResponse(BaseModel):
    title: str
    summary: str | None = None
    source: str | None = None
    impact: str | None = None


class KeyTrendResponse(BaseModel):
    trend: str
    evidence: str | None = None
    impact: str | None = None
    source_count: int | None = None


class VerticalIntelligenceResponse(BaseModel):
    id: str
    vertical_slug: str | None = None
    vertical_name: str | None = None
    report_period: str
    computed_at: str | None = None
    market_overview: dict = {}
    key_trends: list[KeyTrendResponse] = []
    competitive_dynamics: CompetitiveDynamicsResponse = CompetitiveDynamicsResponse()
    financial_pulse: FinancialPulseResponse = FinancialPulseResponse()
    signal_digest: list[SignalDigestItem] = []
    executive_movements: list[ExecutiveMovementResponse] = []
    regulatory_environment: list[RegulatoryItemResponse] = []
    gtm_implications: list[GTMImplicationResponse] = []
    data_sources: dict = {}


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


@router.get(
    "/{company_id}/market-data/vertical-intelligence",
    response_model=VerticalIntelligenceResponse,
)
async def vertical_intelligence(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> VerticalIntelligenceResponse:
    """Full vertical intelligence report — the canonical source of industry data.

    Returns the current (``is_current=True``) ``VerticalIntelligenceReport`` for
    the company's vertical.  Used by TodayPage (GTM implications + financial
    pulse), SignalsFeed (trends + landscape), CampaignsPage (market context),
    and other pages that need industry intelligence.
    """
    await validate_company_access(company_id, current_user, db)

    company = await db.get(Company, company_id)
    vertical = await _resolve_vertical(company.industry if company else None, db)
    if not vertical:
        return VerticalIntelligenceResponse(
            id="", report_period="", vertical_slug=None, vertical_name=None,
        )

    stmt = (
        select(VerticalIntelligenceReport)
        .where(
            VerticalIntelligenceReport.vertical_id == vertical.id,
            VerticalIntelligenceReport.is_current.is_(True),
        )
        .order_by(desc(VerticalIntelligenceReport.computed_at))
        .limit(1)
    )
    report = await db.scalar(stmt)
    if not report:
        return VerticalIntelligenceResponse(
            id="", report_period="",
            vertical_slug=vertical.slug, vertical_name=vertical.name,
        )

    return _report_to_response(report, vertical)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _report_to_response(
    report: VerticalIntelligenceReport,
    vertical: MarketVertical,
) -> VerticalIntelligenceResponse:
    """Convert a DB VerticalIntelligenceReport to API response."""
    # Parse JSON sections with safe defaults
    key_trends_raw = report.key_trends or []
    key_trends = [
        KeyTrendResponse(
            trend=t.get("trend", "") if isinstance(t, dict) else str(t),
            evidence=t.get("evidence") if isinstance(t, dict) else None,
            impact=t.get("impact") if isinstance(t, dict) else None,
            source_count=t.get("source_count") if isinstance(t, dict) else None,
        )
        for t in key_trends_raw
    ]

    comp_dyn = report.competitive_dynamics or {}
    competitive = CompetitiveDynamicsResponse(
        leaders=comp_dyn.get("leaders", []),
        challengers=comp_dyn.get("challengers", []),
        movers=comp_dyn.get("movers", []),
        new_entrants=comp_dyn.get("new_entrants", []),
        exits=comp_dyn.get("exits", []),
    )

    fp = report.financial_pulse or {}
    financial_pulse = FinancialPulseResponse(
        sga_median=fp.get("sga_median"),
        sga_trend=fp.get("sga_trend"),
        rnd_median=fp.get("rnd_median"),
        rnd_trend=fp.get("rnd_trend"),
        margin_compression_or_expansion=fp.get("margin_compression_or_expansion"),
        capex_intensity=fp.get("capex_intensity"),
        top_spenders=fp.get("top_spenders", []),
    )

    signal_digest = [
        SignalDigestItem(
            headline=s.get("headline", "") if isinstance(s, dict) else str(s),
            signal_type=s.get("signal_type") if isinstance(s, dict) else None,
            source=s.get("source") if isinstance(s, dict) else None,
            published_at=s.get("published_at") if isinstance(s, dict) else None,
            companies_mentioned=s.get("companies_mentioned", []) if isinstance(s, dict) else [],
        )
        for s in (report.signal_digest or [])
    ]

    exec_moves = [
        ExecutiveMovementResponse(
            company=e.get("company") if isinstance(e, dict) else None,
            name=e.get("name") if isinstance(e, dict) else None,
            old_title=e.get("old_title") if isinstance(e, dict) else None,
            new_title=e.get("new_title") if isinstance(e, dict) else None,
            change_type=e.get("change_type") if isinstance(e, dict) else None,
            date=e.get("date") if isinstance(e, dict) else None,
        )
        for e in (report.executive_movements or [])
    ]

    regulatory = [
        RegulatoryItemResponse(
            title=r.get("title", "") if isinstance(r, dict) else str(r),
            summary=r.get("summary") if isinstance(r, dict) else None,
            source=r.get("source") if isinstance(r, dict) else None,
            impact=r.get("impact") if isinstance(r, dict) else None,
        )
        for r in (report.regulatory_environment or [])
    ]

    gtm_impl = [
        GTMImplicationResponse(
            insight=g.get("insight", "") if isinstance(g, dict) else str(g),
            evidence=g.get("evidence") if isinstance(g, dict) else None,
            recommended_action=g.get("recommended_action") if isinstance(g, dict) else None,
            priority=g.get("priority") if isinstance(g, dict) else None,
        )
        for g in (report.gtm_implications or [])
    ]

    return VerticalIntelligenceResponse(
        id=str(report.id),
        vertical_slug=vertical.slug,
        vertical_name=vertical.name,
        report_period=report.report_period,
        computed_at=report.computed_at.isoformat() if report.computed_at else None,
        market_overview=report.market_overview or {},
        key_trends=key_trends,
        competitive_dynamics=competitive,
        financial_pulse=financial_pulse,
        signal_digest=signal_digest,
        executive_movements=exec_moves,
        regulatory_environment=regulatory,
        gtm_implications=gtm_impl,
        data_sources=report.data_sources or {},
    )


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
