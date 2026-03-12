"""Sequences router — manage outreach sequence templates and enrollments."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import SequenceEnrollment
from packages.database.src.session import get_db_session

from ..services.playbook_service import PlaybookService
from ..services.sequence_engine import SequenceEngine

router = APIRouter()

class EnrollRequest(BaseModel):
    lead_id: str
    template_id: str
    trigger_signal_id: str | None = None
    start_immediately: bool = True

class EnrollmentResponse(BaseModel):
    id: str
    lead_id: str
    template_id: str
    status: str
    current_step: int
    next_step_due: str | None
    enrolled_at: str
    emails_sent: int

class PlaybookActivateRequest(BaseModel):
    playbook_type: str
    lead_ids: list[str]
    custom_name: str | None = None

@router.get("/{company_id}/sequences/templates", response_model=list[dict])
async def list_templates(_company_id: UUID, db: AsyncSession = Depends(get_db_session)):
    svc = PlaybookService(db)
    playbooks = await svc.get_all_playbooks()
    return [{"id": str(pb.id), "playbook_type": pb.playbook_type, "name": pb.name, "description": pb.description, "steps_count": pb.steps_count, "duration_days": pb.duration_days, "success_rate_benchmark": pb.success_rate_benchmark, "is_singapore_specific": pb.is_singapore_specific, "best_for": pb.best_for} for pb in playbooks]

@router.post("/{company_id}/sequences/activate-playbook")
async def activate_playbook(
    company_id: UUID,
    body: PlaybookActivateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Activate a playbook for a list of leads — creates template + enrolls all leads."""
    svc = PlaybookService(db)
    engine = SequenceEngine(db)
    template = await svc.create_sequence_from_playbook(body.playbook_type, company_id, body.custom_name)
    enrolled = 0
    skipped = 0
    for lead_id_str in body.lead_ids:
        try:
            await engine.enroll(UUID(lead_id_str), template.id, company_id)
            enrolled += 1
        except ValueError:
            skipped += 1
    return {"template_id": str(template.id), "enrolled": enrolled, "skipped_already_active": skipped}

@router.get("/{company_id}/sequences/enrollments", response_model=list[EnrollmentResponse])
async def list_enrollments(
    company_id: UUID,
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(SequenceEnrollment).where(SequenceEnrollment.company_id == company_id).order_by(desc(SequenceEnrollment.enrolled_at)).limit(limit)
    if status:
        stmt = stmt.where(SequenceEnrollment.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [EnrollmentResponse(id=str(r.id), lead_id=str(r.lead_id), template_id=str(r.template_id), status=r.status.value, current_step=r.current_step, next_step_due=r.next_step_due.isoformat() if r.next_step_due else None, enrolled_at=r.enrolled_at.isoformat(), emails_sent=r.emails_sent) for r in rows]

@router.post("/{company_id}/sequences/enrollments/{enrollment_id}/pause")
async def pause_enrollment(_company_id: UUID, enrollment_id: UUID, db: AsyncSession = Depends(get_db_session)):
    engine = SequenceEngine(db)
    await engine.pause(enrollment_id, reason="manual")
    return {"status": "paused"}

@router.post("/{company_id}/sequences/enrollments/{enrollment_id}/resume")
async def resume_enrollment(_company_id: UUID, enrollment_id: UUID, db: AsyncSession = Depends(get_db_session)):
    engine = SequenceEngine(db)
    await engine.resume(enrollment_id)
    return {"status": "resumed"}
