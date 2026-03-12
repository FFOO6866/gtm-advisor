"""Attribution router — ROI tracking from outreach to pipeline."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import AttributionEvent
from packages.database.src.session import get_db_session

router = APIRouter()

class RecordEventRequest(BaseModel):
    lead_id: str
    event_type: str  # meeting_booked, meeting_held, proposal_sent, deal_closed
    pipeline_value_sgd: float | None = None
    notes: str | None = None
    approval_item_id: str | None = None

@router.post("/{company_id}/attribution/events")
async def record_event(
    company_id: UUID,
    body: RecordEventRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Manually record a business outcome (meeting, deal) attributed to GTM Advisor."""
    event = AttributionEvent(
        company_id=company_id,
        lead_id=UUID(body.lead_id),
        approval_item_id=UUID(body.approval_item_id) if body.approval_item_id else None,
        event_type=body.event_type,
        pipeline_value_sgd=body.pipeline_value_sgd,
        notes=body.notes,
        recorded_by="user",
    )
    db.add(event)
    await db.commit()
    return {"status": "recorded", "id": str(event.id)}

@router.get("/{company_id}/attribution/summary")
async def attribution_summary(
    company_id: UUID,
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db_session),
):
    """Get ROI summary — the 'prove your value' dashboard."""
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(AttributionEvent.event_type, func.count().label("count"), func.sum(AttributionEvent.pipeline_value_sgd).label("pipeline_sgd"))
        .where(AttributionEvent.company_id == company_id, AttributionEvent.occurred_at >= since)
        .group_by(AttributionEvent.event_type)
    )
    rows = (await db.execute(stmt)).all()
    summary = {}
    for row in rows:
        summary[row.event_type] = {"count": row.count, "pipeline_sgd": float(row.pipeline_sgd or 0)}

    emails_sent = summary.get("email_sent", {}).get("count", 0) or summary.get("email_approved", {}).get("count", 0)
    meetings = summary.get("meeting_booked", {}).get("count", 0)
    pipeline = sum(v.get("pipeline_sgd", 0) for v in summary.values())
    reply_rate = round((summary.get("reply_received", {}).get("count", 0) / emails_sent * 100), 1) if emails_sent else 0

    return {
        "period_days": days,
        "emails_sent": emails_sent,
        "replies": summary.get("reply_received", {}).get("count", 0),
        "reply_rate_pct": reply_rate,
        "meetings_booked": meetings,
        "pipeline_value_sgd": pipeline,
        "meeting_to_email_ratio": round(meetings / emails_sent * 100, 1) if emails_sent else 0,
        "breakdown": summary,
        "why_us_proof": f"GTM Advisor generated {meetings} meetings and SGD {pipeline:,.0f} pipeline in {days} days.",
    }
