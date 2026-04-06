"""Webhooks router — inbound webhooks from SendGrid.

Handles SendGrid Event Webhook (tracking events) and Inbound Parse Webhook (replies).

When a lead replies to a sequence email, the enrollment is automatically paused
so they are not contacted again without human review.

Endpoint: POST /api/v1/webhooks/sendgrid
Auth: Optional SENDGRID_WEBHOOK_SECRET header (set SENDGRID_WEBHOOK_SECRET env var)
"""

from __future__ import annotations

import os
import re

import structlog
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from packages.database.src.models import AttributionEvent, CreativeAsset, EngagementEvent, Lead
from packages.database.src.session import async_session_factory
from services.gateway.src.services.sequence_engine import SequenceEngine

logger = structlog.get_logger()

router = APIRouter()

# Regex to extract bare email from "Name <email@domain.com>" or plain "email@domain.com"
_EMAIL_RE = re.compile(r"<([^>]+)>|([^\s<>]+@[^\s<>]+)")


def _extract_email(raw: str) -> str:
    """Extract bare email address from RFC 5322 formatted header value."""
    m = _EMAIL_RE.search(raw)
    if m:
        return (m.group(1) or m.group(2)).lower().strip()
    return raw.lower().strip()

# Event types that indicate a lead replied or opted out and should pause their enrollment
_PAUSE_EVENT_TYPES = frozenset({
    "inbound",          # SendGrid Inbound Parse — actual reply email
    "group_unsubscribe",  # Unsubscribed from a group
    "unsubscribe",        # Global unsubscribe
    "spamreport",         # Marked as spam — must stop immediately
})

# Engagement events mapped to AttributionEvent.event_type values
_ENGAGEMENT_EVENT_MAP: dict[str, str] = {
    "open": "email_opened",
    "click": "email_clicked",
    "inbound": "reply_received",
}

# Delivery failure events — logged but not stored (no lead-level consequence yet)
_BOUNCE_EVENT_TYPES = frozenset({"bounce", "deferred", "dropped"})

# SendGrid event → EngagementEvent.event_type (Phase 4 granular tracking)
_ENGAGEMENT_EVENT_TYPE_MAP: dict[str, str] = {
    "open": "email_open",
    "click": "email_click",
    "bounce": "email_bounce",
    "unsubscribe": "email_unsubscribe",
    "group_unsubscribe": "email_unsubscribe",
    "spamreport": "email_spam",
    "spam_report": "email_spam",
}


@router.post("/webhooks/sendgrid")
async def sendgrid_webhook(request: Request) -> dict:
    """Process SendGrid webhook events.

    SendGrid sends a JSON array of events. Each event may have:
    - event: str — the event type
    - email: str — the recipient's email address
    - lead_id: str — from custom_args set when email was sent
    - from: str — sender email (inbound parse events)

    On inbound/unsubscribe events, pauses the lead's active enrollments.
    """
    # Optional webhook secret validation
    secret = os.getenv("SENDGRID_WEBHOOK_SECRET", "")
    if secret:
        provided = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
        if not provided:
            # SendGrid's older format uses a custom header
            provided = request.headers.get("X-SendGrid-Webhook-Secret", "")
        if provided != secret:
            raise HTTPException(403, "Invalid webhook secret")

    try:
        body = await request.json()
    except Exception:
        # SendGrid inbound parse uses multipart/form-data
        form = await request.form()
        # Treat inbound parse as a reply event
        sender_email = str(form.get("from", "")).strip()
        if sender_email:
            await _handle_inbound_reply(sender_email)
        return {"processed": 1}

    if not isinstance(body, list):
        body = [body]

    paused = 0
    engagement_recorded = 0
    for event in body:
        if not isinstance(event, dict):
            continue

        event_type = event.get("event", "")

        # Extract lead identity fields used by both pause and engagement paths
        lead_id_str: str | None = (
            event.get("lead_id")
            or (event.get("unique_args") or {}).get("lead_id")
        )
        raw_email: str | None = event.get("email") or event.get("from")

        try:
            if event_type in _PAUSE_EVENT_TYPES:
                if lead_id_str:
                    count = await _pause_by_lead_id(lead_id_str)
                    paused += count
                    logger.info(
                        "sendgrid_webhook_pause_by_id",
                        event=event_type,
                        lead_id=lead_id_str,
                        enrollments_paused=count,
                    )
                elif raw_email:
                    count = await _pause_by_email(raw_email)
                    paused += count
                    logger.info(
                        "sendgrid_webhook_pause_by_email",
                        event=event_type,
                        email=raw_email,
                        enrollments_paused=count,
                    )

            elif event_type in _ENGAGEMENT_EVENT_MAP:
                attribution_type = _ENGAGEMENT_EVENT_MAP[event_type]
                recorded = await _record_engagement_event(
                    lead_id_str, raw_email, attribution_type,
                    metadata={"url": event.get("url", ""), "timestamp": event.get("timestamp")},
                )
                engagement_recorded += recorded
                if recorded:
                    logger.info(
                        "sendgrid_webhook_engagement",
                        event=event_type,
                        attribution_type=attribution_type,
                    )

            elif event_type in _BOUNCE_EVENT_TYPES:
                # Log bounces for deliverability tracking; no DB write yet
                logger.warning(
                    "sendgrid_webhook_bounce",
                    event=event_type,
                    email=raw_email or "",
                    reason=event.get("reason", ""),
                )

            # Phase 4: write a granular EngagementEvent row for all trackable event types
            if event_type in _ENGAGEMENT_EVENT_TYPE_MAP:
                custom_args: dict = event.get("custom_args") or {}
                await _write_engagement_event(
                    sg_event_type=event_type,
                    sg_message_id=event.get("sg_message_id") or event.get("sg_event_id"),
                    email=raw_email,
                    lead_id_str=lead_id_str or custom_args.get("lead_id"),
                    company_id_str=custom_args.get("company_id"),
                    campaign_id_str=custom_args.get("campaign_id"),
                    asset_id_str=custom_args.get("asset_id"),
                    url_clicked=event.get("url"),
                    timestamp=event.get("timestamp"),
                )

        except Exception as e:
            logger.error("sendgrid_webhook_event_failed", event=event_type, error=str(e))

    return {
        "processed": len(body),
        "enrollments_paused": paused,
        "engagement_recorded": engagement_recorded,
    }


async def _write_engagement_event(
    sg_event_type: str,
    sg_message_id: str | None,
    email: str | None,
    lead_id_str: str | None,
    company_id_str: str | None,
    campaign_id_str: str | None,
    asset_id_str: str | None,
    url_clicked: str | None,
    timestamp: int | float | None,
) -> None:
    """Create an EngagementEvent row and update CreativeAsset counters if applicable.

    company_id is required — if it cannot be resolved the event is dropped.
    All other FK fields are optional and silently skipped if the UUID is invalid.
    """
    from datetime import datetime
    from uuid import UUID

    engagement_event_type = _ENGAGEMENT_EVENT_TYPE_MAP.get(sg_event_type)
    if not engagement_event_type:
        return

    # company_id is mandatory for EngagementEvent
    if not company_id_str:
        logger.debug(
            "sendgrid_webhook_engagement_event_skipped_no_company",
            sg_event_type=sg_event_type,
            email=email or "",
        )
        return

    def _parse_uuid(value: str | None) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(value)
        except (ValueError, AttributeError):
            return None

    company_id = _parse_uuid(company_id_str)
    if company_id is None:
        return

    campaign_id = _parse_uuid(campaign_id_str)
    asset_id = _parse_uuid(asset_id_str)
    lead_id = _parse_uuid(lead_id_str)

    occurred_at: datetime | None = None
    if timestamp is not None:
        try:
            occurred_at = datetime.utcfromtimestamp(float(timestamp))
        except (ValueError, OSError, OverflowError):
            occurred_at = None

    async with async_session_factory() as db:
        ev = EngagementEvent(
            company_id=company_id,
            campaign_id=campaign_id,
            asset_id=asset_id,
            lead_id=lead_id,
            event_type=engagement_event_type,
            channel="email",
            source_message_id=sg_message_id,
            url_clicked=url_clicked if sg_event_type == "click" else None,
            metadata_json={"email": email or "", "sg_event_type": sg_event_type},
        )
        if occurred_at is not None:
            ev.occurred_at = occurred_at
        db.add(ev)

        # Increment CreativeAsset performance counters when asset_id is present
        if asset_id is not None:
            asset: CreativeAsset | None = await db.get(CreativeAsset, asset_id)
            if asset is not None:
                if sg_event_type == "open":
                    asset.impressions += 1
                elif sg_event_type == "click":
                    asset.clicks += 1

        await db.commit()
        logger.info(
            "sendgrid_webhook_engagement_event_written",
            event_type=engagement_event_type,
            company_id=str(company_id),
            asset_id=str(asset_id) if asset_id else None,
        )


async def _record_engagement_event(
    lead_id_str: str | None,
    raw_email: str | None,
    attribution_type: str,
    metadata: dict | None = None,
) -> int:
    """Record an email_opened or email_clicked AttributionEvent.

    Returns 1 on success, 0 if lead could not be resolved.
    """
    from uuid import UUID

    async with async_session_factory() as db:
        lead: Lead | None = None

        if lead_id_str:
            try:
                lead = await db.get(Lead, UUID(lead_id_str))
            except (ValueError, Exception):
                pass

        if lead is None and raw_email:
            email = _extract_email(raw_email)
            if email:
                result = await db.execute(
                    select(Lead).where(Lead.contact_email == email)
                )
                lead = result.scalars().first()

        if lead is None:
            return 0

        event = AttributionEvent(
            company_id=lead.company_id,
            lead_id=lead.id,
            event_type=attribution_type,
            recorded_by="system",
            metadata_json=metadata or {},
        )
        db.add(event)
        await db.commit()
        return 1


async def _pause_by_lead_id(lead_id_str: str) -> int:
    """Pause all active enrollments for a lead by their UUID."""
    from uuid import UUID
    try:
        lead_id = UUID(lead_id_str)
    except ValueError:
        return 0

    async with async_session_factory() as db:
        engine = SequenceEngine(db)
        return await engine.pause_on_reply(lead_id)


async def _pause_by_email(raw_email: str) -> int:
    """Find a lead by contact_email and pause all their active enrollments.

    Handles RFC 5322 "Name <email>" format from SendGrid inbound parse.
    Uses .first() to be resilient if duplicate emails exist in the database.
    """
    email = _extract_email(raw_email)
    if not email:
        return 0
    async with async_session_factory() as db:
        result = await db.execute(
            select(Lead).where(Lead.contact_email == email)
        )
        lead = result.scalars().first()
        if not lead:
            logger.warning("sendgrid_webhook_lead_not_found", email=email)
            return 0

        engine = SequenceEngine(db)
        return await engine.pause_on_reply(lead.id)


async def _handle_inbound_reply(raw_from: str) -> None:
    """Handle inbound parse (multipart form) reply.

    raw_from may be "Name <email@domain.com>" — _pause_by_email calls _extract_email.
    Also records a reply_received AttributionEvent for attribution tracking.
    """
    await _pause_by_email(raw_from)
    # Record reply attribution event
    email = _extract_email(raw_from)
    if email:
        await _record_engagement_event(None, email, "reply_received")
