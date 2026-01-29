"""Competitor management API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import Competitor, CompetitorAlert, Company, ThreatLevel
from packages.database.src.session import get_db_session

from ..schemas.competitors import (
    CompetitorCreate,
    CompetitorUpdate,
    CompetitorResponse,
    CompetitorAlertResponse,
    CompetitorListResponse,
    BattleCardResponse,
)

logger = structlog.get_logger()
router = APIRouter()


def competitor_to_response(competitor: Competitor, alert_count: int = 0) -> CompetitorResponse:
    """Convert database model to response schema."""
    return CompetitorResponse(
        id=competitor.id,
        company_id=competitor.company_id,
        name=competitor.name,
        website=competitor.website,
        description=competitor.description,
        threat_level=competitor.threat_level.value if competitor.threat_level else "medium",
        positioning=competitor.positioning,
        strengths=competitor.strengths or [],
        weaknesses=competitor.weaknesses or [],
        opportunities=competitor.opportunities or [],
        threats=competitor.threats or [],
        our_advantages=competitor.our_advantages or [],
        their_advantages=competitor.their_advantages or [],
        key_objection_handlers=competitor.key_objection_handlers or [],
        pricing_info=competitor.pricing_info,
        is_active=competitor.is_active,
        last_updated=competitor.last_updated or competitor.updated_at or competitor.created_at,
        created_at=competitor.created_at,
        updated_at=competitor.updated_at,
        alert_count=alert_count,
    )


@router.get("/{company_id}/competitors", response_model=CompetitorListResponse)
async def list_competitors(
    company_id: UUID,
    threat_level: Optional[str] = Query(default=None, pattern="^(low|medium|high)$"),
    is_active: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
) -> CompetitorListResponse:
    """List all competitors for a company."""
    # Build query
    query = select(Competitor).where(
        Competitor.company_id == company_id,
        Competitor.is_active == is_active,
    )

    if threat_level:
        query = query.where(Competitor.threat_level == ThreatLevel(threat_level))

    query = query.order_by(Competitor.threat_level.desc(), Competitor.name)

    result = await db.execute(query)
    competitors = result.scalars().all()

    # Get alert counts for each competitor
    alert_query = (
        select(CompetitorAlert.competitor_id, func.count(CompetitorAlert.id).label("count"))
        .where(
            CompetitorAlert.competitor_id.in_([c.id for c in competitors]),
            CompetitorAlert.is_read == False,
            CompetitorAlert.is_dismissed == False,
        )
        .group_by(CompetitorAlert.competitor_id)
    )
    alert_result = await db.execute(alert_query)
    alert_counts = {row.competitor_id: row.count for row in alert_result}

    # Count by threat level
    high_count = sum(1 for c in competitors if c.threat_level == ThreatLevel.HIGH)
    medium_count = sum(1 for c in competitors if c.threat_level == ThreatLevel.MEDIUM)
    low_count = sum(1 for c in competitors if c.threat_level == ThreatLevel.LOW)
    total_alerts = sum(alert_counts.values())

    return CompetitorListResponse(
        competitors=[competitor_to_response(c, alert_counts.get(c.id, 0)) for c in competitors],
        total=len(competitors),
        high_threat_count=high_count,
        medium_threat_count=medium_count,
        low_threat_count=low_count,
        unread_alerts_count=total_alerts,
    )


@router.post("/{company_id}/competitors", response_model=CompetitorResponse, status_code=201)
async def create_competitor(
    company_id: UUID,
    data: CompetitorCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CompetitorResponse:
    """Create a new competitor."""
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    competitor = Competitor(
        company_id=company_id,
        name=data.name,
        website=data.website,
        description=data.description,
        threat_level=ThreatLevel(data.threat_level),
        positioning=data.positioning,
        strengths=data.strengths,
        weaknesses=data.weaknesses,
        opportunities=data.opportunities,
        threats=data.threats,
        our_advantages=data.our_advantages,
        their_advantages=data.their_advantages,
        key_objection_handlers=data.key_objection_handlers,
        pricing_info=data.pricing_info,
    )

    db.add(competitor)
    await db.flush()

    logger.info("competitor_created", competitor_id=str(competitor.id), name=competitor.name)
    return competitor_to_response(competitor)


@router.get("/{company_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    company_id: UUID,
    competitor_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CompetitorResponse:
    """Get a specific competitor."""
    competitor = await db.get(Competitor, competitor_id)
    if not competitor or competitor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Get alert count
    alert_query = select(func.count(CompetitorAlert.id)).where(
        CompetitorAlert.competitor_id == competitor_id,
        CompetitorAlert.is_read == False,
        CompetitorAlert.is_dismissed == False,
    )
    alert_count = (await db.execute(alert_query)).scalar() or 0

    return competitor_to_response(competitor, alert_count)


@router.patch("/{company_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    company_id: UUID,
    competitor_id: UUID,
    data: CompetitorUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> CompetitorResponse:
    """Update a competitor."""
    competitor = await db.get(Competitor, competitor_id)
    if not competitor or competitor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Competitor not found")

    update_data = data.model_dump(exclude_unset=True)
    if "threat_level" in update_data:
        update_data["threat_level"] = ThreatLevel(update_data["threat_level"])

    for field, value in update_data.items():
        setattr(competitor, field, value)

    competitor.last_updated = datetime.utcnow()
    await db.flush()

    logger.info("competitor_updated", competitor_id=str(competitor_id))
    return competitor_to_response(competitor)


@router.delete("/{company_id}/competitors/{competitor_id}", status_code=204)
async def delete_competitor(
    company_id: UUID,
    competitor_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a competitor (soft delete by setting is_active=False)."""
    competitor = await db.get(Competitor, competitor_id)
    if not competitor or competitor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Competitor not found")

    competitor.is_active = False
    await db.flush()

    logger.info("competitor_deleted", competitor_id=str(competitor_id))


@router.get("/{company_id}/competitors/{competitor_id}/alerts", response_model=list[CompetitorAlertResponse])
async def list_competitor_alerts(
    company_id: UUID,
    competitor_id: UUID,
    unread_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db_session),
) -> list[CompetitorAlertResponse]:
    """List alerts for a competitor."""
    competitor = await db.get(Competitor, competitor_id)
    if not competitor or competitor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Competitor not found")

    query = (
        select(CompetitorAlert)
        .where(CompetitorAlert.competitor_id == competitor_id, CompetitorAlert.is_dismissed == False)
        .order_by(CompetitorAlert.detected_at.desc())
    )

    if unread_only:
        query = query.where(CompetitorAlert.is_read == False)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [CompetitorAlertResponse.model_validate(a) for a in alerts]


@router.post("/{company_id}/competitors/{competitor_id}/alerts/{alert_id}/read", status_code=204)
async def mark_alert_read(
    company_id: UUID,
    competitor_id: UUID,
    alert_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Mark an alert as read."""
    alert = await db.get(CompetitorAlert, alert_id)
    if not alert or alert.competitor_id != competitor_id:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_read = True
    alert.read_at = datetime.utcnow()
    await db.flush()


@router.get("/{company_id}/competitors/{competitor_id}/battlecard", response_model=BattleCardResponse)
async def get_battle_card(
    company_id: UUID,
    competitor_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> BattleCardResponse:
    """Get battle card for a competitor."""
    competitor = await db.get(Competitor, competitor_id)
    if not competitor or competitor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Generate win strategies based on weaknesses and our advantages
    win_strategies = []
    for weakness in (competitor.weaknesses or [])[:3]:
        win_strategies.append(f"Leverage their weakness: {weakness}")
    for advantage in (competitor.our_advantages or [])[:2]:
        win_strategies.append(f"Emphasize our strength: {advantage}")

    return BattleCardResponse(
        competitor_id=competitor.id,
        competitor_name=competitor.name,
        our_advantages=competitor.our_advantages or [],
        their_advantages=competitor.their_advantages or [],
        key_objection_handlers=competitor.key_objection_handlers or [],
        positioning=competitor.positioning,
        pricing_comparison=competitor.pricing_info,
        win_strategies=win_strategies,
        generated_at=datetime.utcnow(),
    )
