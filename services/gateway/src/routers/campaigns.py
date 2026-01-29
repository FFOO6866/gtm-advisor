"""Campaign management API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import Campaign, Company, CampaignStatus
from packages.database.src.session import get_db_session

from ..schemas.campaigns import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
)

logger = structlog.get_logger()
router = APIRouter()


def campaign_to_response(campaign: Campaign) -> CampaignResponse:
    """Convert database model to response schema."""
    return CampaignResponse(
        id=campaign.id,
        company_id=campaign.company_id,
        icp_id=campaign.icp_id,
        name=campaign.name,
        description=campaign.description,
        objective=campaign.objective or "lead_gen",
        status=campaign.status.value if campaign.status else "draft",
        target_personas=campaign.target_personas or [],
        target_industries=campaign.target_industries or [],
        target_company_sizes=campaign.target_company_sizes or [],
        key_messages=campaign.key_messages or [],
        value_propositions=campaign.value_propositions or [],
        call_to_action=campaign.call_to_action,
        channels=campaign.channels or [],
        email_templates=campaign.email_templates or [],
        linkedin_posts=campaign.linkedin_posts or [],
        ad_copy=campaign.ad_copy or [],
        landing_page_copy=campaign.landing_page_copy,
        blog_outlines=campaign.blog_outlines or [],
        budget=campaign.budget,
        currency=campaign.currency or "SGD",
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        metrics=campaign.metrics or {},
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.get("/{company_id}/campaigns", response_model=CampaignListResponse)
async def list_campaigns(
    company_id: UUID,
    status: Optional[str] = Query(default=None, pattern="^(draft|active|paused|completed)$"),
    objective: Optional[str] = Query(default=None, pattern="^(awareness|lead_gen|conversion|retention)$"),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignListResponse:
    """List all campaigns for a company."""
    query = select(Campaign).where(Campaign.company_id == company_id)

    if status:
        query = query.where(Campaign.status == CampaignStatus(status))
    if objective:
        query = query.where(Campaign.objective == objective)

    query = query.order_by(Campaign.created_at.desc())

    result = await db.execute(query)
    campaigns = result.scalars().all()

    # Get counts
    by_status = {}
    by_objective = {}
    total_budget = 0.0

    for campaign in campaigns:
        status_val = campaign.status.value if campaign.status else "draft"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        obj_val = campaign.objective or "lead_gen"
        by_objective[obj_val] = by_objective.get(obj_val, 0) + 1

        if campaign.budget:
            total_budget += campaign.budget

    return CampaignListResponse(
        campaigns=[campaign_to_response(c) for c in campaigns],
        total=len(campaigns),
        by_status=by_status,
        by_objective=by_objective,
        total_budget=total_budget,
    )


@router.post("/{company_id}/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    company_id: UUID,
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Create a new campaign."""
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    campaign = Campaign(
        company_id=company_id,
        icp_id=data.icp_id,
        name=data.name,
        description=data.description,
        objective=data.objective,
        target_personas=data.target_personas,
        target_industries=data.target_industries,
        target_company_sizes=data.target_company_sizes,
        key_messages=data.key_messages,
        value_propositions=data.value_propositions,
        call_to_action=data.call_to_action,
        channels=data.channels,
        budget=data.budget,
        currency=data.currency,
        start_date=data.start_date,
        end_date=data.end_date,
    )

    db.add(campaign)
    await db.flush()

    logger.info("campaign_created", campaign_id=str(campaign.id), name=campaign.name)
    return campaign_to_response(campaign)


@router.get("/{company_id}/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Get a specific campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return campaign_to_response(campaign)


@router.patch("/{company_id}/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    company_id: UUID,
    campaign_id: UUID,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Update a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle status conversion
    if "status" in update_data:
        update_data["status"] = CampaignStatus(update_data["status"])

    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.flush()

    logger.info("campaign_updated", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.delete("/{company_id}/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await db.delete(campaign)
    await db.flush()

    logger.info("campaign_deleted", campaign_id=str(campaign_id))


@router.post("/{company_id}/campaigns/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Activate a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.ACTIVE
    if not campaign.start_date:
        campaign.start_date = datetime.utcnow()

    await db.flush()

    logger.info("campaign_activated", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.post("/{company_id}/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Pause a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.PAUSED
    await db.flush()

    logger.info("campaign_paused", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.post("/{company_id}/campaigns/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Mark a campaign as completed."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.COMPLETED
    if not campaign.end_date:
        campaign.end_date = datetime.utcnow()

    await db.flush()

    logger.info("campaign_completed", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.post("/{company_id}/campaigns/{campaign_id}/duplicate", response_model=CampaignResponse, status_code=201)
async def duplicate_campaign(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Duplicate a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    new_campaign = Campaign(
        company_id=company_id,
        icp_id=campaign.icp_id,
        name=f"{campaign.name} (Copy)",
        description=campaign.description,
        objective=campaign.objective,
        target_personas=campaign.target_personas,
        target_industries=campaign.target_industries,
        target_company_sizes=campaign.target_company_sizes,
        key_messages=campaign.key_messages,
        value_propositions=campaign.value_propositions,
        call_to_action=campaign.call_to_action,
        channels=campaign.channels,
        email_templates=campaign.email_templates,
        linkedin_posts=campaign.linkedin_posts,
        ad_copy=campaign.ad_copy,
        landing_page_copy=campaign.landing_page_copy,
        blog_outlines=campaign.blog_outlines,
        budget=campaign.budget,
        currency=campaign.currency,
        # Don't copy dates or metrics
    )

    db.add(new_campaign)
    await db.flush()

    logger.info("campaign_duplicated", original_id=str(campaign_id), new_id=str(new_campaign.id))
    return campaign_to_response(new_campaign)
