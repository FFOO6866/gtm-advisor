"""ICP and Persona management API endpoints."""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import ICP, Persona, Company
from packages.database.src.session import get_db_session

from ..schemas.icps import (
    ICPCreate,
    ICPUpdate,
    ICPResponse,
    ICPListResponse,
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
)

logger = structlog.get_logger()
router = APIRouter()


def persona_to_response(persona: Persona) -> PersonaResponse:
    """Convert database model to response schema."""
    return PersonaResponse(
        id=persona.id,
        icp_id=persona.icp_id,
        name=persona.name,
        role=persona.role,
        avatar=persona.avatar,
        age_range=persona.age_range,
        experience_years=persona.experience_years,
        education=persona.education,
        goals=persona.goals or [],
        challenges=persona.challenges or [],
        objections=persona.objections or [],
        preferred_channels=persona.preferred_channels or [],
        messaging_hooks=persona.messaging_hooks or [],
        content_preferences=persona.content_preferences or [],
        is_active=persona.is_active,
        created_at=persona.created_at,
        updated_at=persona.updated_at,
    )


def icp_to_response(icp: ICP, personas: list[Persona] = None) -> ICPResponse:
    """Convert database model to response schema."""
    return ICPResponse(
        id=icp.id,
        company_id=icp.company_id,
        name=icp.name,
        description=icp.description,
        fit_score=icp.fit_score or 0,
        company_size=icp.company_size,
        revenue_range=icp.revenue_range,
        industry=icp.industry,
        tech_stack=icp.tech_stack,
        buying_triggers=icp.buying_triggers or [],
        pain_points=icp.pain_points or [],
        needs=icp.needs or [],
        matching_companies_count=icp.matching_companies_count or 0,
        is_active=icp.is_active,
        created_at=icp.created_at,
        updated_at=icp.updated_at,
        personas=[persona_to_response(p) for p in (personas or [])],
    )


@router.get("/{company_id}/icps", response_model=ICPListResponse)
async def list_icps(
    company_id: UUID,
    is_active: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
) -> ICPListResponse:
    """List all ICPs for a company."""
    query = (
        select(ICP)
        .options(selectinload(ICP.personas))
        .where(ICP.company_id == company_id, ICP.is_active == is_active)
        .order_by(ICP.fit_score.desc(), ICP.name)
    )

    result = await db.execute(query)
    icps = result.scalars().unique().all()

    # Calculate stats
    total_personas = sum(len([p for p in icp.personas if p.is_active]) for icp in icps)

    return ICPListResponse(
        icps=[icp_to_response(icp, [p for p in icp.personas if p.is_active]) for icp in icps],
        total=len(icps),
        active_count=sum(1 for icp in icps if icp.is_active),
        total_personas=total_personas,
    )


@router.post("/{company_id}/icps", response_model=ICPResponse, status_code=201)
async def create_icp(
    company_id: UUID,
    data: ICPCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ICPResponse:
    """Create a new ICP."""
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    icp = ICP(
        company_id=company_id,
        name=data.name,
        description=data.description,
        fit_score=data.fit_score,
        company_size=data.company_size,
        revenue_range=data.revenue_range,
        industry=data.industry,
        tech_stack=data.tech_stack,
        buying_triggers=data.buying_triggers,
        pain_points=data.pain_points,
        needs=data.needs,
    )

    db.add(icp)
    await db.flush()

    logger.info("icp_created", icp_id=str(icp.id), name=icp.name)
    return icp_to_response(icp, [])


@router.get("/{company_id}/icps/{icp_id}", response_model=ICPResponse)
async def get_icp(
    company_id: UUID,
    icp_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ICPResponse:
    """Get a specific ICP."""
    query = select(ICP).options(selectinload(ICP.personas)).where(ICP.id == icp_id)
    result = await db.execute(query)
    icp = result.scalars().first()

    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    return icp_to_response(icp, [p for p in icp.personas if p.is_active])


@router.patch("/{company_id}/icps/{icp_id}", response_model=ICPResponse)
async def update_icp(
    company_id: UUID,
    icp_id: UUID,
    data: ICPUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ICPResponse:
    """Update an ICP."""
    query = select(ICP).options(selectinload(ICP.personas)).where(ICP.id == icp_id)
    result = await db.execute(query)
    icp = result.scalars().first()

    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(icp, field, value)

    await db.flush()

    logger.info("icp_updated", icp_id=str(icp_id))
    return icp_to_response(icp, [p for p in icp.personas if p.is_active])


@router.delete("/{company_id}/icps/{icp_id}", status_code=204)
async def delete_icp(
    company_id: UUID,
    icp_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an ICP (soft delete)."""
    icp = await db.get(ICP, icp_id)
    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    icp.is_active = False
    await db.flush()

    logger.info("icp_deleted", icp_id=str(icp_id))


# Persona endpoints (nested under ICPs)


@router.post("/{company_id}/icps/{icp_id}/personas", response_model=PersonaResponse, status_code=201)
async def create_persona(
    company_id: UUID,
    icp_id: UUID,
    data: PersonaCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PersonaResponse:
    """Create a new persona for an ICP."""
    icp = await db.get(ICP, icp_id)
    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    persona = Persona(
        icp_id=icp_id,
        name=data.name,
        role=data.role,
        avatar=data.avatar,
        age_range=data.age_range,
        experience_years=data.experience_years,
        education=data.education,
        goals=data.goals,
        challenges=data.challenges,
        objections=data.objections,
        preferred_channels=data.preferred_channels,
        messaging_hooks=data.messaging_hooks,
        content_preferences=data.content_preferences,
    )

    db.add(persona)
    await db.flush()

    logger.info("persona_created", persona_id=str(persona.id), name=persona.name)
    return persona_to_response(persona)


@router.get("/{company_id}/icps/{icp_id}/personas/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    company_id: UUID,
    icp_id: UUID,
    persona_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PersonaResponse:
    """Get a specific persona."""
    persona = await db.get(Persona, persona_id)
    if not persona or persona.icp_id != icp_id:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Verify company ownership via ICP
    icp = await db.get(ICP, icp_id)
    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    return persona_to_response(persona)


@router.patch("/{company_id}/icps/{icp_id}/personas/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    company_id: UUID,
    icp_id: UUID,
    persona_id: UUID,
    data: PersonaUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> PersonaResponse:
    """Update a persona."""
    persona = await db.get(Persona, persona_id)
    if not persona or persona.icp_id != icp_id:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Verify company ownership
    icp = await db.get(ICP, icp_id)
    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(persona, field, value)

    await db.flush()

    logger.info("persona_updated", persona_id=str(persona_id))
    return persona_to_response(persona)


@router.delete("/{company_id}/icps/{icp_id}/personas/{persona_id}", status_code=204)
async def delete_persona(
    company_id: UUID,
    icp_id: UUID,
    persona_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a persona (soft delete)."""
    persona = await db.get(Persona, persona_id)
    if not persona or persona.icp_id != icp_id:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Verify company ownership
    icp = await db.get(ICP, icp_id)
    if not icp or icp.company_id != company_id:
        raise HTTPException(status_code=404, detail="ICP not found")

    persona.is_active = False
    await db.flush()

    logger.info("persona_deleted", persona_id=str(persona_id))
