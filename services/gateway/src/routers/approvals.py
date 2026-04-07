"""Approvals router — human approval gate for outreach queue."""
from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import ApprovalQueueItem, ApprovalStatus, AttributionEvent
from packages.database.src.session import get_db_session
from services.gateway.src.auth.launch_mode import require_execution_enabled

router = APIRouter()

class ApprovalItemResponse(BaseModel):
    id: str
    lead_id: str
    to_email: str
    to_name: str | None
    sequence_name: str | None
    step_number: int
    proposed_subject: str
    proposed_body: str
    status: str
    created_at: str
    expires_at: str | None

class ApproveRequest(BaseModel):
    edited_subject: str | None = None
    edited_body: str | None = None
    approved_by: str = "user"

class BulkApproveRequest(BaseModel):
    item_ids: list[str]
    approved_by: str = "user"

@router.get("/{company_id}/approvals", response_model=list[ApprovalItemResponse])
async def list_pending(
    company_id: UUID,
    status: str = Query("pending"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(ApprovalQueueItem)
        .where(
            ApprovalQueueItem.company_id == company_id,
            ApprovalQueueItem.status == status,
        )
        .order_by(ApprovalQueueItem.created_at)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]

@router.get("/{company_id}/approvals/count")
async def pending_count(company_id: UUID, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(
        select(func.count()).where(
            ApprovalQueueItem.company_id == company_id,
            ApprovalQueueItem.status == ApprovalStatus.PENDING,
        )
    )
    return {"pending": result.scalar_one()}

@router.post(
    "/{company_id}/approvals/{item_id}/approve",
    dependencies=[Depends(require_execution_enabled)],
)
async def approve_item(
    company_id: UUID,
    item_id: UUID,
    body: ApproveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
):
    """Approve an outreach item and send the email."""
    item = await db.get(ApprovalQueueItem, item_id)
    if not item or item.company_id != company_id:
        raise HTTPException(404, "Approval item not found")
    if item.status != ApprovalStatus.PENDING:
        raise HTTPException(400, f"Item is not pending (status: {item.status.value})")

    if body.edited_subject or body.edited_body:
        item.status = ApprovalStatus.EDITED_APPROVED
        item.final_subject = body.edited_subject or item.proposed_subject
        item.final_body = body.edited_body or item.proposed_body
    else:
        item.status = ApprovalStatus.APPROVED
        item.final_subject = item.proposed_subject
        item.final_body = item.proposed_body

    item.approved_by = body.approved_by
    item.reviewed_at = datetime.now(UTC)
    item.scheduled_send_at = datetime.now(UTC)

    # Record attribution event
    attr = AttributionEvent(
        company_id=company_id,
        lead_id=item.lead_id,
        approval_item_id=item.id,
        event_type="email_approved",
        recorded_by=body.approved_by,
    )
    db.add(attr)
    await db.commit()

    # Send in background using the approved (possibly edited) content
    background_tasks.add_task(
        _send_approved_email,
        item_id=item.id,
        to_email=item.to_email,
        to_name=item.to_name,
        subject=item.final_subject,
        body=item.final_body,
        lead_id=str(item.lead_id),
    )
    return {"status": "approved", "id": str(item.id)}

@router.post(
    "/{company_id}/approvals/{item_id}/reject",
    dependencies=[Depends(require_execution_enabled)],
)
async def reject_item(
    company_id: UUID,
    item_id: UUID,
    reason: str = Body(default="", embed=True),
    db: AsyncSession = Depends(get_db_session),
):
    item = await db.get(ApprovalQueueItem, item_id)
    if not item or item.company_id != company_id:
        raise HTTPException(404, "Approval item not found")
    item.status = ApprovalStatus.REJECTED
    item.rejection_reason = reason
    item.reviewed_at = datetime.now(UTC)
    attr = AttributionEvent(
        company_id=company_id,
        lead_id=item.lead_id,
        approval_item_id=item.id,
        event_type="email_rejected",
        recorded_by="system",
    )
    db.add(attr)
    await db.commit()
    return {"status": "rejected"}

@router.post(
    "/{company_id}/approvals/bulk-approve",
    dependencies=[Depends(require_execution_enabled)],
)
async def bulk_approve(
    company_id: UUID,
    body: BulkApproveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
):
    """Approve multiple items at once and send them."""
    approved = 0
    to_send = []
    for id_str in body.item_ids:
        try:
            item = await db.get(ApprovalQueueItem, UUID(id_str))
            if item and item.company_id == company_id and item.status == ApprovalStatus.PENDING:
                item.status = ApprovalStatus.APPROVED
                item.final_subject = item.proposed_subject
                item.final_body = item.proposed_body
                item.approved_by = body.approved_by
                item.reviewed_at = datetime.now(UTC)
                item.scheduled_send_at = datetime.now(UTC)
                db.add(AttributionEvent(
                    company_id=company_id,
                    lead_id=item.lead_id,
                    approval_item_id=item.id,
                    event_type="email_approved",
                    recorded_by=body.approved_by,
                ))
                to_send.append((item.id, item.to_email, item.to_name, item.final_subject, item.final_body, str(item.lead_id)))
                approved += 1
        except Exception:
            continue
    await db.commit()
    for item_id, to_email, to_name, subject, body_text, lead_id in to_send:
        background_tasks.add_task(_send_approved_email, item_id=item_id, to_email=to_email, to_name=to_name, subject=subject, body=body_text, lead_id=lead_id)
    return {"approved": approved}


async def _send_approved_email(
    item_id: object,
    to_email: str,
    _to_name: str | None,
    subject: str,
    body: str,
    lead_id: str,
) -> None:
    """Background: send the approved email via SendGrid and record sent_at."""
    import structlog as _log

    from packages.database.src.models import ApprovalQueueItem, AttributionEvent
    from packages.database.src.session import async_session_factory
    from packages.mcp.src.servers.sendgrid import SendGridMCPServer

    _logger = _log.get_logger()
    from_email = os.getenv("WORKFORCE_OUTREACH_FROM_EMAIL", "")
    if not from_email:
        _logger.warning("outreach_send_skipped_no_from_email", item_id=str(item_id))
        return

    sendgrid = SendGridMCPServer.from_env()
    message_id: str | None = None
    sent = False
    if sendgrid.is_configured:
        message_id = await sendgrid.send_email(
            to=to_email,
            subject=subject or "(no subject)",
            body=body or "",
            from_email=from_email,
            from_name=os.getenv("WORKFORCE_OUTREACH_FROM_NAME", "GTM Advisor"),
            categories=["sequence-outreach"],
            custom_args={"lead_id": lead_id},
        )
        sent = message_id is not None
    else:
        _logger.warning("outreach_send_skipped_no_sendgrid", item_id=str(item_id))

    async with async_session_factory() as db:
        item = await db.get(ApprovalQueueItem, item_id)
        if not item:
            _logger.error("outreach_approval_item_missing", item_id=str(item_id))
            return
        if sent:
            from datetime import UTC as _UTC
            from datetime import datetime as _dt
            item.sent_at = _dt.now(_UTC)
            item.message_id = message_id
        db.add(AttributionEvent(
            company_id=item.company_id,
            lead_id=item.lead_id,
            approval_item_id=item.id,
            event_type="email_sent" if sent else "email_send_skipped",
            recorded_by="system",
            metadata_json={"message_id": message_id} if message_id else {},
        ))
        await db.commit()


def _to_response(item: ApprovalQueueItem) -> ApprovalItemResponse:
    return ApprovalItemResponse(
        id=str(item.id),
        lead_id=str(item.lead_id),
        to_email=item.to_email,
        to_name=item.to_name,
        sequence_name=item.sequence_name,
        step_number=item.step_number,
        proposed_subject=item.proposed_subject,
        proposed_body=item.proposed_body,
        status=item.status.value,
        created_at=item.created_at.isoformat(),
        expires_at=item.expires_at.isoformat() if item.expires_at else None,
    )
