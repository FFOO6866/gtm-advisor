"""Signals router — market signal events."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import SignalEvent
from packages.database.src.session import get_db_session

router = APIRouter()

class SignalEventResponse(BaseModel):
    id: str
    signal_type: str
    urgency: str
    headline: str
    summary: str | None
    source: str | None
    source_url: str | None
    relevance_score: float
    competitors_mentioned: list[str]
    recommended_action: str | None
    is_actioned: bool
    published_at: str | None
    created_at: str

@router.get("/{company_id}/signals", response_model=list[SignalEventResponse])
async def list_signals(
    company_id: UUID,
    urgency: str | None = Query(None),
    signal_type: str | None = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(SignalEvent).where(SignalEvent.company_id == company_id).order_by(desc(SignalEvent.created_at))
    if urgency:
        stmt = stmt.where(SignalEvent.urgency == urgency)
    if signal_type:
        stmt = stmt.where(SignalEvent.signal_type == signal_type)
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_signal_response(r) for r in rows]

@router.post("/{company_id}/signals/{signal_id}/action")
async def mark_actioned(company_id: UUID, signal_id: UUID, db: AsyncSession = Depends(get_db_session)):
    signal = await db.get(SignalEvent, signal_id)
    if not signal or signal.company_id != company_id:
        raise HTTPException(404, "Signal not found")
    from datetime import UTC, datetime
    signal.is_actioned = True
    signal.actioned_at = datetime.now(UTC)
    await db.commit()
    return {"status": "actioned"}

def _to_signal_response(s: SignalEvent) -> SignalEventResponse:
    return SignalEventResponse(
        id=str(s.id),
        signal_type=s.signal_type.value if hasattr(s.signal_type, "value") else str(s.signal_type),
        urgency=s.urgency.value if hasattr(s.urgency, "value") else str(s.urgency),
        headline=s.headline,
        summary=s.summary,
        source=s.source,
        source_url=s.source_url,
        relevance_score=s.relevance_score,
        competitors_mentioned=s.competitors_mentioned or [],
        recommended_action=s.recommended_action,
        is_actioned=s.is_actioned,
        published_at=s.published_at.isoformat() if s.published_at else None,
        created_at=s.created_at.isoformat(),
    )
