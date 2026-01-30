"""Lead management API endpoints."""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import Company, Lead, LeadStatus
from packages.database.src.session import get_db_session

from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User
from ..schemas.leads import (
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    LeadScoreUpdate,
    LeadUpdate,
)

logger = structlog.get_logger()
router = APIRouter()


def lead_to_response(lead: Lead) -> LeadResponse:
    """Convert database model to response schema."""
    return LeadResponse(
        id=lead.id,
        company_id=lead.company_id,
        icp_id=lead.icp_id,
        lead_company_name=lead.lead_company_name,
        lead_company_website=lead.lead_company_website,
        lead_company_industry=lead.lead_company_industry,
        lead_company_size=lead.lead_company_size,
        lead_company_description=lead.lead_company_description,
        contact_name=lead.contact_name,
        contact_title=lead.contact_title,
        contact_email=lead.contact_email,
        contact_linkedin=lead.contact_linkedin,
        fit_score=lead.fit_score or 0,
        intent_score=lead.intent_score or 0,
        overall_score=lead.overall_score or 0,
        status=lead.status.value if lead.status else "new",
        qualification_reasons=lead.qualification_reasons or [],
        disqualification_reasons=lead.disqualification_reasons or [],
        source=lead.source,
        source_url=lead.source_url,
        notes=lead.notes,
        tags=lead.tags or [],
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        contacted_at=lead.contacted_at,
        converted_at=lead.converted_at,
    )


@router.get("/{company_id}/leads", response_model=LeadListResponse)
async def list_leads(
    company_id: UUID,
    status: str | None = Query(default=None, pattern="^(new|qualified|contacted|converted|lost)$"),
    min_score: int = Query(default=0, ge=0, le=100),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(
        default="overall_score", pattern="^(overall_score|created_at|fit_score|intent_score)$"
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadListResponse:
    """List leads for a company with filtering and pagination."""
    await validate_company_access(company_id, current_user, db)

    # Build base query
    query = select(Lead).where(Lead.company_id == company_id)

    # Apply filters
    if status:
        query = query.where(Lead.status == LeadStatus(status))
    if min_score > 0:
        query = query.where(Lead.overall_score >= min_score)
    if search:
        query = query.where(Lead.lead_company_name.ilike(f"%{search}%"))

    # Apply sorting
    sort_column = getattr(Lead, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    leads = result.scalars().all()

    # Get total count
    count_query = select(func.count(Lead.id)).where(Lead.company_id == company_id)
    total = (await db.execute(count_query)).scalar() or 0

    # Get counts by status
    status_counts_query = (
        select(Lead.status, func.count(Lead.id))
        .where(Lead.company_id == company_id)
        .group_by(Lead.status)
    )
    status_result = await db.execute(status_counts_query)
    by_status = {row.status.value: row[1] for row in status_result}

    # Calculate averages
    avg_query = select(
        func.avg(Lead.fit_score).label("avg_fit"),
        func.avg(Lead.intent_score).label("avg_intent"),
        func.count(Lead.id).filter(Lead.overall_score > 80).label("high_score"),
    ).where(Lead.company_id == company_id)
    avg_result = await db.execute(avg_query)
    avg_row = avg_result.first()

    return LeadListResponse(
        leads=[lead_to_response(lead) for lead in leads],
        total=total,
        by_status=by_status,
        avg_fit_score=float(avg_row.avg_fit or 0),
        avg_intent_score=float(avg_row.avg_intent or 0),
        high_score_count=avg_row.high_score or 0,
    )


@router.post("/{company_id}/leads", response_model=LeadResponse, status_code=201)
async def create_lead(
    company_id: UUID,
    data: LeadCreate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Create a new lead."""
    await validate_company_access(company_id, current_user, db)

    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Calculate overall score
    overall_score = int((data.fit_score * 0.6) + (data.intent_score * 0.4))

    lead = Lead(
        company_id=company_id,
        icp_id=data.icp_id,
        lead_company_name=data.lead_company_name,
        lead_company_website=data.lead_company_website,
        lead_company_industry=data.lead_company_industry,
        lead_company_size=data.lead_company_size,
        lead_company_description=data.lead_company_description,
        contact_name=data.contact_name,
        contact_title=data.contact_title,
        contact_email=data.contact_email,
        contact_linkedin=data.contact_linkedin,
        fit_score=data.fit_score,
        intent_score=data.intent_score,
        overall_score=overall_score,
        source=data.source,
        source_url=data.source_url,
        qualification_reasons=data.qualification_reasons,
        notes=data.notes,
        tags=data.tags,
    )

    db.add(lead)
    await db.flush()

    logger.info("lead_created", lead_id=str(lead.id), company_name=lead.lead_company_name)
    return lead_to_response(lead)


@router.get("/{company_id}/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    company_id: UUID,
    lead_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Get a specific lead."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    return lead_to_response(lead)


@router.patch("/{company_id}/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    company_id: UUID,
    lead_id: UUID,
    data: LeadUpdate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Update a lead."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle status conversion
    if "status" in update_data:
        new_status = LeadStatus(update_data["status"])
        update_data["status"] = new_status

        # Track status changes
        if new_status == LeadStatus.CONTACTED and not lead.contacted_at:
            lead.contacted_at = datetime.utcnow()
        elif new_status == LeadStatus.CONVERTED and not lead.converted_at:
            lead.converted_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(lead, field, value)

    await db.flush()

    logger.info("lead_updated", lead_id=str(lead_id))
    return lead_to_response(lead)


@router.patch("/{company_id}/leads/{lead_id}/score", response_model=LeadResponse)
async def update_lead_score(
    company_id: UUID,
    lead_id: UUID,
    data: LeadScoreUpdate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Update lead scores."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    if data.fit_score is not None:
        lead.fit_score = data.fit_score
    if data.intent_score is not None:
        lead.intent_score = data.intent_score

    # Recalculate overall score
    lead.overall_score = int((lead.fit_score * 0.6) + (lead.intent_score * 0.4))

    await db.flush()

    logger.info("lead_score_updated", lead_id=str(lead_id), overall_score=lead.overall_score)
    return lead_to_response(lead)


@router.delete("/{company_id}/leads/{lead_id}", status_code=204)
async def delete_lead(
    company_id: UUID,
    lead_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a lead permanently."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    await db.delete(lead)
    await db.flush()

    logger.info("lead_deleted", lead_id=str(lead_id))


@router.post("/{company_id}/leads/{lead_id}/qualify", response_model=LeadResponse)
async def qualify_lead(
    company_id: UUID,
    lead_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Mark a lead as qualified."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = LeadStatus.QUALIFIED
    await db.flush()

    logger.info("lead_qualified", lead_id=str(lead_id))
    return lead_to_response(lead)


@router.post("/{company_id}/leads/{lead_id}/contact", response_model=LeadResponse)
async def mark_lead_contacted(
    company_id: UUID,
    lead_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Mark a lead as contacted."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = LeadStatus.CONTACTED
    lead.contacted_at = datetime.utcnow()
    await db.flush()

    logger.info("lead_contacted", lead_id=str(lead_id))
    return lead_to_response(lead)


@router.post("/{company_id}/leads/{lead_id}/convert", response_model=LeadResponse)
async def convert_lead(
    company_id: UUID,
    lead_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Mark a lead as converted (won)."""
    await validate_company_access(company_id, current_user, db)

    lead = await db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = LeadStatus.CONVERTED
    lead.converted_at = datetime.utcnow()
    await db.flush()

    logger.info("lead_converted", lead_id=str(lead_id))
    return lead_to_response(lead)
