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

from packages.database.src.models import AttributionEvent, Lead
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
}

# Delivery failure events — logged but not stored (no lead-level consequence yet)
_BOUNCE_EVENT_TYPES = frozenset({"bounce", "deferred", "dropped"})


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

        except Exception as e:
            logger.error("sendgrid_webhook_event_failed", event=event_type, error=str(e))

    return {
        "processed": len(body),
        "enrollments_paused": paused,
        "engagement_recorded": engagement_recorded,
    }


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
    """
    await _pause_by_email(raw_from)
