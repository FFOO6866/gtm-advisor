"""Attribution router — ROI tracking from outreach to pipeline."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    AttributionEvent,
    Campaign,
    CreativeAsset,
    EngagementEvent,
)
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
    """Manually record a business outcome (meeting, deal) attributed to Kairos."""
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
        "why_us_proof": f"Kairos generated {meetings} meetings and SGD {pipeline:,.0f} pipeline in {days} days.",
    }


@router.get("/{company_id}/attribution/campaign/{campaign_id}")
async def campaign_attribution(
    company_id: UUID,
    campaign_id: UUID,
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Per-campaign performance breakdown with engagement metrics.

    Combines AttributionEvent (business outcomes) with EngagementEvent
    (email opens, clicks, social engagement) for a complete funnel view.
    """
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    since = datetime.now(UTC) - timedelta(days=days)

    # --- Engagement metrics (email + social) ---
    eng_stmt = (
        select(
            EngagementEvent.channel,
            EngagementEvent.event_type,
            func.count().label("count"),
        )
        .where(
            EngagementEvent.campaign_id == campaign_id,
            EngagementEvent.occurred_at >= since,
        )
        .group_by(EngagementEvent.channel, EngagementEvent.event_type)
    )
    eng_rows = (await db.execute(eng_stmt)).all()

    channel_metrics: dict[str, dict[str, int]] = {}
    for row in eng_rows:
        ch = row.channel or "unknown"
        if ch not in channel_metrics:
            channel_metrics[ch] = {}
        channel_metrics[ch][row.event_type] = row.count

    # Compute aggregate email metrics
    email_m = channel_metrics.get("email", {})
    email_opens = email_m.get("email_open", 0)
    email_clicks = email_m.get("email_click", 0)
    email_bounces = email_m.get("email_bounce", 0)
    email_unsubs = email_m.get("email_unsubscribe", 0)

    # --- Attribution events (business outcomes) ---
    attr_stmt = (
        select(
            AttributionEvent.event_type,
            func.count().label("count"),
            func.sum(AttributionEvent.pipeline_value_sgd).label("pipeline_sgd"),
        )
        .where(
            AttributionEvent.company_id == company_id,
            AttributionEvent.occurred_at >= since,
        )
        .group_by(AttributionEvent.event_type)
    )
    attr_rows = (await db.execute(attr_stmt)).all()
    attr_summary = {
        row.event_type: {"count": row.count, "pipeline_sgd": float(row.pipeline_sgd or 0)}
        for row in attr_rows
    }

    emails_sent = attr_summary.get("email_sent", {}).get("count", 0)
    meetings = attr_summary.get("meeting_booked", {}).get("count", 0)
    pipeline = sum(v.get("pipeline_sgd", 0) for v in attr_summary.values())

    # Compute rates
    open_rate = round(email_opens / emails_sent * 100, 1) if emails_sent else 0
    ctr = round(email_clicks / emails_sent * 100, 1) if emails_sent else 0

    # --- Top performing assets ---
    asset_stmt = (
        select(CreativeAsset)
        .where(CreativeAsset.campaign_id == campaign_id)
        .order_by(CreativeAsset.clicks.desc())
        .limit(5)
    )
    top_assets = (await db.execute(asset_stmt)).scalars().all()

    # --- Social totals ---
    social_impressions = 0
    social_clicks = 0
    social_engagements = 0
    for ch, metrics in channel_metrics.items():
        if ch != "email":
            social_impressions += metrics.get("social_impression", 0)
            social_clicks += metrics.get("social_click", 0)
            social_engagements += metrics.get("social_engagement", 0)

    return {
        "campaign_id": str(campaign_id),
        "campaign_name": campaign.name,
        "period_days": days,
        "status": campaign.status.value if campaign.status else "draft",
        # Email funnel
        "email": {
            "sent": emails_sent,
            "opens": email_opens,
            "clicks": email_clicks,
            "bounces": email_bounces,
            "unsubscribes": email_unsubs,
            "open_rate_pct": open_rate,
            "click_through_rate_pct": ctr,
        },
        # Social metrics
        "social": {
            "impressions": social_impressions,
            "clicks": social_clicks,
            "engagements": social_engagements,
        },
        # Business outcomes
        "outcomes": {
            "meetings_booked": meetings,
            "pipeline_value_sgd": pipeline,
            "breakdown": attr_summary,
        },
        # Channel breakdown
        "channel_breakdown": channel_metrics,
        # Top assets
        "top_assets": [
            {
                "id": str(a.id),
                "name": a.name,
                "platform": a.target_platform,
                "impressions": a.impressions,
                "clicks": a.clicks,
                "engagements": a.engagements,
                "ctr": round(a.clicks / a.impressions * 100, 1) if a.impressions else 0,
            }
            for a in top_assets
        ],
        # Campaign-level metrics (from Campaign.metrics JSON)
        "last_monitor_report": campaign.metrics or {},
    }


@router.get("/{company_id}/attribution/assets/top")
async def top_performing_assets(
    company_id: UUID,
    limit: int = Query(10, le=50),
    metric: str = Query("clicks", pattern="^(clicks|impressions|engagements|conversions)$"),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    """Top performing creative assets across all campaigns."""
    order_col = getattr(CreativeAsset, metric, CreativeAsset.clicks)
    stmt = (
        select(CreativeAsset)
        .where(CreativeAsset.company_id == company_id)
        .order_by(order_col.desc())
        .limit(limit)
    )
    assets = (await db.execute(stmt)).scalars().all()

    return [
        {
            "id": str(a.id),
            "campaign_id": str(a.campaign_id),
            "name": a.name,
            "asset_type": a.asset_type.value if a.asset_type else "",
            "platform": a.target_platform,
            "status": a.status.value if a.status else "draft",
            "impressions": a.impressions,
            "clicks": a.clicks,
            "engagements": a.engagements,
            "conversions": a.conversions,
            "ctr": round(a.clicks / a.impressions * 100, 1) if a.impressions else 0,
        }
        for a in assets
    ]
