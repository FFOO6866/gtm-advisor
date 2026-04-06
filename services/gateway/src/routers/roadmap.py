"""GTM Roadmap API — strategic campaign planning endpoints.

The Campaign Strategist agent produces phased GTM roadmaps grounded in
14 marketing reference books and 18 domain guides. This router exposes
the roadmap lifecycle: generate → review → approve → execute → revise.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    Campaign,
    CampaignStatus,
    Company,
    RoadmapPhase,
    RoadmapStatus,
)
from packages.database.src.session import async_session_factory, get_db_session

from ..agents_registry import get_agent_class
from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User
from ..utils import verify_company_exists

logger = structlog.get_logger()
router = APIRouter()


class GenerateRoadmapRequest(BaseModel):
    """Request to generate a GTM roadmap."""

    planning_horizon_months: int = 12
    focus_areas: list[str] | None = None  # Optional: ["awareness", "lead_gen", "expansion"]
    analysis_id: str | None = None  # Link to a completed analysis for context


class ApproveRoadmapRequest(BaseModel):
    """Request to approve a roadmap (optionally with edits)."""

    approved_by: str = "user"
    approved_campaigns: list[str] | None = None  # Campaign names to approve (None = all)


@router.get("/{company_id}/roadmap")
async def get_roadmap(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get the current GTM roadmap for a company.

    Returns the roadmap with campaigns grouped by phase.
    """
    await validate_company_access(company_id, current_user, db)

    # Import here to avoid circular — GTMRoadmap may not exist until migration runs
    from packages.database.src.models import GTMRoadmap

    stmt = (
        select(GTMRoadmap)
        .where(GTMRoadmap.company_id == company_id)
        .order_by(GTMRoadmap.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    roadmap = result.scalar_one_or_none()

    if not roadmap:
        return {
            "has_roadmap": False,
            "message": "No GTM roadmap yet. Generate one with POST /roadmap/generate.",
        }

    # Fetch campaigns linked to this roadmap, grouped by phase
    campaigns_stmt = (
        select(Campaign)
        .where(Campaign.roadmap_id == roadmap.id)
        .order_by(Campaign.priority_rank.asc().nulls_last(), Campaign.created_at.asc())
    )
    campaigns = (await db.execute(campaigns_stmt)).scalars().all()

    # Group by phase
    phase_groups: dict[str, list[dict]] = {
        "immediate": [],
        "short_term": [],
        "mid_term": [],
        "long_term": [],
        "unphased": [],
    }

    active_count = 0
    completed_count = 0
    track_groups: dict[str, list[dict]] = {}

    for c in campaigns:
        phase_key = c.phase.value if c.phase else "unphased"
        campaign_dict = {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "objective": c.objective,
            "status": c.status.value if c.status else "draft",
            "phase": phase_key,
            "priority_rank": c.priority_rank,
            "framework_rationale": c.framework_rationale,
            "knowledge_source": c.knowledge_source,
            "channels": c.channels or [],
            "content_types_needed": c.content_types_needed or [],
            "strategy_track": c.strategy_track,
            "estimated_impact": c.estimated_impact,
            "recommended_by_ai": c.recommended_by_ai,
            "budget": c.budget,
            "metrics": c.metrics or {},
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        phase_groups.get(phase_key, phase_groups["unphased"]).append(campaign_dict)

        # Group by strategy track
        track = c.strategy_track or "Unassigned"
        if track not in track_groups:
            track_groups[track] = []
        track_groups[track].append(campaign_dict)

        if c.status == CampaignStatus.ACTIVE:
            active_count += 1
        elif c.status == CampaignStatus.COMPLETED:
            completed_count += 1

    return {
        "has_roadmap": True,
        "roadmap": {
            "id": str(roadmap.id),
            "company_id": str(roadmap.company_id),
            "title": roadmap.title,
            "executive_summary": roadmap.executive_summary,
            "gtm_motion": roadmap.gtm_motion,
            "status": roadmap.status.value if roadmap.status else "proposed",
            "planning_horizon_months": roadmap.planning_horizon_months,
            "company_diagnosis": roadmap.company_diagnosis or {},
            "frameworks_applied": roadmap.frameworks_applied or [],
            "knowledge_sources": roadmap.knowledge_sources or [],
            "confidence": roadmap.confidence,
            "created_at": roadmap.created_at.isoformat() if roadmap.created_at else None,
            "approved_at": roadmap.approved_at.isoformat() if roadmap.approved_at else None,
        },
        "phases": phase_groups,
        "strategy_tracks": track_groups,
        "summary": {
            "total_campaigns": len(campaigns),
            "active_campaigns": active_count,
            "completed_campaigns": completed_count,
        },
    }


@router.post("/{company_id}/roadmap/generate")
async def generate_roadmap(
    company_id: UUID,
    request: GenerateRoadmapRequest,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Generate a GTM roadmap using the Campaign Strategist agent.

    Runs in background — poll GET /roadmap for results.
    """
    await validate_company_access(company_id, current_user, db)
    company = await verify_company_exists(db, company_id)

    logger.info(
        "roadmap_generation_requested",
        company_id=str(company_id),
        horizon_months=request.planning_horizon_months,
    )

    background_tasks.add_task(
        _run_roadmap_generator,
        company_id=company_id,
        company=company,
        analysis_id=request.analysis_id,
        planning_horizon_months=request.planning_horizon_months,
        focus_areas=request.focus_areas,
    )

    return {
        "status": "generating",
        "company_id": str(company_id),
        "message": "Campaign Strategist is building your GTM roadmap. Poll GET /roadmap for results.",
    }


@router.post("/{company_id}/roadmap/{roadmap_id}/approve")
async def approve_roadmap(
    company_id: UUID,
    roadmap_id: UUID,
    body: ApproveRoadmapRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Approve a roadmap — sets status to IN_PROGRESS and marks campaigns as planned."""
    await validate_company_access(company_id, current_user, db)

    from packages.database.src.models import GTMRoadmap

    roadmap = await db.get(GTMRoadmap, roadmap_id)
    if not roadmap or roadmap.company_id != company_id:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    if roadmap.status not in (RoadmapStatus.PROPOSED, RoadmapStatus.REVISED):
        raise HTTPException(status_code=400, detail=f"Roadmap cannot be approved (status: {roadmap.status.value})")

    roadmap.status = RoadmapStatus.IN_PROGRESS
    roadmap.approved_at = datetime.now(UTC)

    await db.commit()

    logger.info("roadmap_approved", roadmap_id=str(roadmap_id), approved_by=body.approved_by)
    return {"status": "approved", "roadmap_id": str(roadmap_id)}


@router.post("/{company_id}/roadmap/{roadmap_id}/revise")
async def revise_roadmap(
    company_id: UUID,
    roadmap_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Re-generate the roadmap with latest data (signals, performance)."""
    await validate_company_access(company_id, current_user, db)

    from packages.database.src.models import GTMRoadmap

    roadmap = await db.get(GTMRoadmap, roadmap_id)
    if not roadmap or roadmap.company_id != company_id:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Mark old roadmap as revised
    roadmap.status = RoadmapStatus.REVISED

    await db.commit()

    # Generate new roadmap
    background_tasks.add_task(
        _run_roadmap_generator,
        company_id=company_id,
        company=company,
        analysis_id=str(roadmap.analysis_id) if roadmap.analysis_id else None,
        planning_horizon_months=roadmap.planning_horizon_months,
        focus_areas=None,
    )

    logger.info("roadmap_revision_requested", roadmap_id=str(roadmap_id))
    return {
        "status": "revising",
        "old_roadmap_id": str(roadmap_id),
        "message": "Campaign Strategist is regenerating your roadmap with latest data.",
    }


async def _run_roadmap_generator(
    company_id: UUID,
    company: Company,
    analysis_id: str | None,
    planning_horizon_months: int,
    focus_areas: list[str] | None,
) -> None:
    """Background task: run Campaign Strategist agent and persist roadmap + campaigns."""
    from packages.database.src.models import GTMRoadmap

    try:
        agent_class = get_agent_class("campaign-strategist")
        if not agent_class:
            logger.warning("campaign_strategist_not_found")
            return

        agent = agent_class()
        context = {
            "company_id": str(company_id),
            "company_name": company.name,
            "industry": company.industry or "",
            "description": company.description or "",
            "products": company.products or [],
            "target_markets": company.target_markets or ["Singapore"],
            "planning_horizon_months": planning_horizon_months,
        }
        if analysis_id:
            context["analysis_id"] = analysis_id
        if focus_areas:
            context["focus_areas"] = focus_areas

        result = await agent.run(
            task=f"Create a {planning_horizon_months}-month GTM roadmap for {company.name}",
            context=context,
        )

        if not result:
            logger.warning("campaign_strategist_no_result", company_id=str(company_id))
            return

        # Persist roadmap
        async with async_session_factory() as db:
            roadmap = GTMRoadmap(
                company_id=company_id,
                analysis_id=UUID(analysis_id) if analysis_id else None,
                title=result.title,
                executive_summary=result.executive_summary,
                gtm_motion=result.gtm_motion,
                status=RoadmapStatus.PROPOSED,
                planning_horizon_months=result.planning_horizon_months,
                company_diagnosis=result.company_diagnosis,
                frameworks_applied=result.frameworks_applied,
                knowledge_sources=result.knowledge_sources_cited,
                confidence=result.confidence,
            )
            db.add(roadmap)
            await db.flush()  # Get roadmap.id

            # Persist campaigns for each phase
            all_campaigns = [
                (RoadmapPhase.IMMEDIATE, result.immediate_campaigns),
                (RoadmapPhase.SHORT_TERM, result.short_term_campaigns),
                (RoadmapPhase.MID_TERM, result.mid_term_campaigns),
                (RoadmapPhase.LONG_TERM, result.long_term_campaigns),
            ]

            for phase, campaigns in all_campaigns:
                for camp in campaigns:
                    db_campaign = Campaign(
                        company_id=company_id,
                        roadmap_id=roadmap.id,
                        name=camp.name,
                        description=camp.objective,
                        objective=camp.objective_type,
                        status=CampaignStatus.DRAFT,
                        phase=phase,
                        priority_rank=camp.priority_rank,
                        framework_rationale=camp.framework_rationale,
                        knowledge_source=camp.knowledge_source,
                        channels=camp.channels,
                        content_types_needed=camp.content_types,
                        strategy_track=getattr(camp, "strategy_track", None) or None,
                        target_personas=[camp.target_persona] if camp.target_persona else [],
                        budget=camp.estimated_budget_sgd if camp.estimated_budget_sgd > 0 else None,
                        recommended_by_ai=True,
                        estimated_impact="high" if camp.quick_win else "medium",
                        key_messages=[],
                        value_propositions=[],
                        metrics={"kpis": camp.kpis},
                    )
                    db.add(db_campaign)

            await db.commit()

            logger.info(
                "roadmap_persisted",
                company_id=str(company_id),
                roadmap_id=str(roadmap.id),
                campaigns_count=sum(len(c) for _, c in all_campaigns),
            )

    except Exception as e:
        logger.error(
            "roadmap_generation_failed",
            company_id=str(company_id),
            error=str(e),
        )
