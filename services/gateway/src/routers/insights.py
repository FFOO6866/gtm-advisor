"""Market Insights API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import MarketInsight, Company
from packages.database.src.session import get_db_session

from ..schemas.insights import (
    MarketInsightResponse,
    MarketInsightListResponse,
    InsightMarkRead,
    InsightArchive,
)

logger = structlog.get_logger()
router = APIRouter()


def insight_to_response(insight: MarketInsight) -> MarketInsightResponse:
    """Convert database model to response schema."""
    return MarketInsightResponse(
        id=insight.id,
        company_id=insight.company_id,
        insight_type=insight.insight_type,
        category=insight.category,
        title=insight.title,
        summary=insight.summary,
        full_content=insight.full_content,
        impact_level=insight.impact_level,
        relevance_score=insight.relevance_score or 0.0,
        source_name=insight.source_name,
        source_url=insight.source_url,
        published_at=insight.published_at,
        recommended_actions=insight.recommended_actions or [],
        related_agents=insight.related_agents or [],
        is_read=insight.is_read,
        is_archived=insight.is_archived,
        created_at=insight.created_at,
        expires_at=insight.expires_at,
    )


@router.get("/{company_id}/insights", response_model=MarketInsightListResponse)
async def list_insights(
    company_id: UUID,
    insight_type: Optional[str] = Query(default=None, pattern="^(trend|opportunity|threat|news)$"),
    impact_level: Optional[str] = Query(default=None, pattern="^(low|medium|high)$"),
    unread_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> MarketInsightListResponse:
    """List market insights for a company."""
    # Build query
    query = select(MarketInsight).where(MarketInsight.company_id == company_id)

    if not include_archived:
        query = query.where(MarketInsight.is_archived == False)
    if unread_only:
        query = query.where(MarketInsight.is_read == False)
    if insight_type:
        query = query.where(MarketInsight.insight_type == insight_type)
    if impact_level:
        query = query.where(MarketInsight.impact_level == impact_level)

    # Order by relevance and recency
    query = query.order_by(MarketInsight.relevance_score.desc(), MarketInsight.created_at.desc())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    insights = result.scalars().all()

    # Get total count
    count_query = select(func.count(MarketInsight.id)).where(
        MarketInsight.company_id == company_id,
        MarketInsight.is_archived == False,
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Get unread count
    unread_query = select(func.count(MarketInsight.id)).where(
        MarketInsight.company_id == company_id,
        MarketInsight.is_read == False,
        MarketInsight.is_archived == False,
    )
    unread_count = (await db.execute(unread_query)).scalar() or 0

    # Get counts by type
    type_query = (
        select(MarketInsight.insight_type, func.count(MarketInsight.id))
        .where(MarketInsight.company_id == company_id, MarketInsight.is_archived == False)
        .group_by(MarketInsight.insight_type)
    )
    type_result = await db.execute(type_query)
    by_type = {row.insight_type: row[1] for row in type_result}

    # Get counts by impact
    impact_query = (
        select(MarketInsight.impact_level, func.count(MarketInsight.id))
        .where(
            MarketInsight.company_id == company_id,
            MarketInsight.is_archived == False,
            MarketInsight.impact_level.isnot(None),
        )
        .group_by(MarketInsight.impact_level)
    )
    impact_result = await db.execute(impact_query)
    by_impact = {row.impact_level: row[1] for row in impact_result}

    # Get recent high-impact insights
    high_impact_query = (
        select(MarketInsight)
        .where(
            MarketInsight.company_id == company_id,
            MarketInsight.impact_level == "high",
            MarketInsight.is_archived == False,
        )
        .order_by(MarketInsight.created_at.desc())
        .limit(5)
    )
    high_impact_result = await db.execute(high_impact_query)
    recent_high_impact = [insight_to_response(i) for i in high_impact_result.scalars().all()]

    return MarketInsightListResponse(
        insights=[insight_to_response(i) for i in insights],
        total=total,
        unread_count=unread_count,
        by_type=by_type,
        by_impact=by_impact,
        recent_high_impact=recent_high_impact,
    )


@router.get("/{company_id}/insights/{insight_id}", response_model=MarketInsightResponse)
async def get_insight(
    company_id: UUID,
    insight_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MarketInsightResponse:
    """Get a specific market insight."""
    insight = await db.get(MarketInsight, insight_id)
    if not insight or insight.company_id != company_id:
        raise HTTPException(status_code=404, detail="Insight not found")

    # Mark as read
    if not insight.is_read:
        insight.is_read = True
        await db.flush()

    return insight_to_response(insight)


@router.post("/{company_id}/insights/mark-read", status_code=204)
async def mark_insights_read(
    company_id: UUID,
    data: InsightMarkRead,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Mark multiple insights as read."""
    for insight_id in data.insight_ids:
        insight = await db.get(MarketInsight, insight_id)
        if insight and insight.company_id == company_id:
            insight.is_read = True

    await db.flush()
    logger.info("insights_marked_read", count=len(data.insight_ids))


@router.post("/{company_id}/insights/archive", status_code=204)
async def archive_insights(
    company_id: UUID,
    data: InsightArchive,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Archive multiple insights."""
    for insight_id in data.insight_ids:
        insight = await db.get(MarketInsight, insight_id)
        if insight and insight.company_id == company_id:
            insight.is_archived = True

    await db.flush()
    logger.info("insights_archived", count=len(data.insight_ids))


@router.post("/{company_id}/insights/{insight_id}/unarchive", response_model=MarketInsightResponse)
async def unarchive_insight(
    company_id: UUID,
    insight_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MarketInsightResponse:
    """Unarchive an insight."""
    insight = await db.get(MarketInsight, insight_id)
    if not insight or insight.company_id != company_id:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_archived = False
    await db.flush()

    return insight_to_response(insight)


@router.get("/{company_id}/insights/summary")
async def get_insights_summary(
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get a summary of market insights for the company."""
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get counts
    base_query = select(func.count(MarketInsight.id)).where(
        MarketInsight.company_id == company_id,
        MarketInsight.is_archived == False,
    )

    total = (await db.execute(base_query)).scalar() or 0
    unread = (await db.execute(base_query.where(MarketInsight.is_read == False))).scalar() or 0
    high_impact = (await db.execute(base_query.where(MarketInsight.impact_level == "high"))).scalar() or 0

    # Get recent trends
    trends_query = (
        select(MarketInsight)
        .where(
            MarketInsight.company_id == company_id,
            MarketInsight.insight_type == "trend",
            MarketInsight.is_archived == False,
        )
        .order_by(MarketInsight.created_at.desc())
        .limit(3)
    )
    trends = (await db.execute(trends_query)).scalars().all()

    # Get opportunities
    opportunities_query = (
        select(MarketInsight)
        .where(
            MarketInsight.company_id == company_id,
            MarketInsight.insight_type == "opportunity",
            MarketInsight.is_archived == False,
        )
        .order_by(MarketInsight.relevance_score.desc())
        .limit(3)
    )
    opportunities = (await db.execute(opportunities_query)).scalars().all()

    return {
        "total_insights": total,
        "unread_insights": unread,
        "high_impact_count": high_impact,
        "recent_trends": [insight_to_response(t) for t in trends],
        "top_opportunities": [insight_to_response(o) for o in opportunities],
    }
