"""Strategy lifecycle API endpoints.

The Strategy layer is the human gate between Insights and Campaigns:
  Insights → Strategy (propose → human approval) → Campaigns → Execute → Monitor

Endpoints:
  GET  /{company_id}/strategies               — list strategies (filter by status)
  GET  /{company_id}/strategies/{id}          — single strategy
  POST /{company_id}/strategies/{id}/approve  — approve (sets status + approved_at)
  POST /{company_id}/strategies/{id}/reject   — reject with optional reason
  PATCH /{company_id}/strategies/{id}         — edit user_notes / name / description
  POST /{company_id}/strategies/generate      — propose strategies from insights (background)
  POST /{company_id}/strategies/generate-campaigns — take APPROVED strategies → Campaign Strategist
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    Campaign,
    CampaignStatus,
    Company,
    RoadmapPhase,
    RoadmapStatus,
    Strategy,
    StrategyPriority,
    StrategyStatus,
)
from packages.database.src.session import async_session_factory, get_db_session

from ..agents_registry import get_agent_class
from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User
from ..utils import verify_company_exists

logger = structlog.get_logger()
router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class StrategyResponse(BaseModel):
    """Strategy as returned by the API."""

    id: str
    company_id: str
    roadmap_id: str | None
    name: str
    description: str
    insight_sources: list
    rationale: str
    expected_outcome: str
    success_metrics: list
    priority: str
    estimated_timeline: str | None
    target_segment: str | None
    status: str
    user_notes: str | None
    approved_at: str | None
    approved_by: str | None
    created_at: str
    updated_at: str | None


class StrategyListResponse(BaseModel):
    """Paginated list of strategies."""

    strategies: list[StrategyResponse]
    total: int
    by_status: dict[str, int]


class ApproveStrategyRequest(BaseModel):
    """Approve a strategy, optionally record who approved it."""

    approved_by: str = "user"


class RejectStrategyRequest(BaseModel):
    """Reject a strategy with an optional reason stored in user_notes."""

    reason: str | None = None


class PatchStrategyRequest(BaseModel):
    """Editable fields — all optional; only provided fields are updated."""

    name: str | None = None
    description: str | None = None
    user_notes: str | None = None
    priority: str | None = Field(default=None, pattern="^(high|medium|low)$")


class GenerateStrategiesRequest(BaseModel):
    """Kick off the Strategy Proposer agent."""

    analysis_id: str | None = None  # Link to a completed analysis for richer context
    max_strategies: int = Field(default=5, ge=1, le=10)


class GenerateCampaignsRequest(BaseModel):
    """Generate roadmap campaigns from all APPROVED strategies."""

    planning_horizon_months: int = 12


# ============================================================================
# Helpers
# ============================================================================


def _strategy_to_response(s: Strategy) -> StrategyResponse:
    return StrategyResponse(
        id=str(s.id),
        company_id=str(s.company_id),
        roadmap_id=str(s.roadmap_id) if s.roadmap_id else None,
        name=s.name,
        description=s.description,
        insight_sources=s.insight_sources or [],
        rationale=s.rationale,
        expected_outcome=s.expected_outcome,
        success_metrics=s.success_metrics or [],
        priority=s.priority.value if s.priority else "medium",
        estimated_timeline=s.estimated_timeline,
        target_segment=s.target_segment,
        status=s.status.value if s.status else "proposed",
        user_notes=s.user_notes,
        approved_at=s.approved_at.isoformat() if s.approved_at else None,
        approved_by=s.approved_by,
        created_at=s.created_at.isoformat() if s.created_at else datetime.now(UTC).isoformat(),
        updated_at=s.updated_at.isoformat() if s.updated_at else None,
    )


def _count_by_status(strategies: list[Strategy]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in strategies:
        key = s.status.value if s.status else "proposed"
        counts[key] = counts.get(key, 0) + 1
    return counts


# ============================================================================
# Background tasks
# ============================================================================


async def _run_strategy_proposer(
    company_id: UUID,
    company: Company,
    analysis_id: str | None,
    max_strategies: int,
) -> None:
    """Background task: call Strategy Proposer agent and persist Strategy rows."""
    try:
        agent_class = get_agent_class("strategy-proposer")
        if not agent_class:
            logger.warning("strategy_proposer_agent_not_found", company_id=str(company_id))
            return

        agent = agent_class()
        context: dict = {
            "company_id": str(company_id),
            "company_name": company.name,
            "industry": company.industry or "",
            "description": company.description or "",
            "goals": company.goals or [],
            "challenges": company.challenges or [],
            "target_markets": company.target_markets or ["Singapore"],
            "max_strategies": max_strategies,
        }
        if analysis_id:
            context["analysis_id"] = analysis_id

        result = await agent.run(
            task=f"Propose strategic initiatives for {company.name}",
            context=context,
        )
        if not result:
            logger.warning("strategy_proposer_no_result", company_id=str(company_id))
            return

        # Persist each proposed strategy
        async with async_session_factory() as db:
            now = datetime.now(UTC)
            strategies_to_add = getattr(result, "strategies", []) or []
            for s in strategies_to_add:
                # Support both dict and object payloads from the agent
                def _get(obj: object, key: str, default=None):  # noqa: ANN001
                    if isinstance(obj, dict):
                        return obj.get(key, default)
                    return getattr(obj, key, default)

                priority_raw = _get(s, "priority", "medium")
                try:
                    priority = StrategyPriority(priority_raw)
                except ValueError:
                    priority = StrategyPriority.MEDIUM

                db.add(
                    Strategy(
                        company_id=company_id,
                        name=_get(s, "name", "Untitled Strategy"),
                        description=_get(s, "description", ""),
                        insight_sources=_get(s, "insight_sources", []),
                        rationale=_get(s, "rationale", ""),
                        expected_outcome=_get(s, "expected_outcome", ""),
                        success_metrics=_get(s, "success_metrics", []),
                        priority=priority,
                        estimated_timeline=_get(s, "estimated_timeline"),
                        target_segment=_get(s, "target_segment"),
                        status=StrategyStatus.PROPOSED,
                        created_at=now,
                    )
                )
            await db.commit()

            logger.info(
                "strategies_proposed",
                company_id=str(company_id),
                count=len(strategies_to_add),
            )

    except Exception as e:
        logger.error(
            "strategy_proposer_failed",
            company_id=str(company_id),
            error=str(e),
        )


async def _run_campaign_generator_from_strategies(
    company_id: UUID,
    company: Company,
    strategy_ids: list[UUID],
    planning_horizon_months: int,
) -> None:
    """Background task: feed APPROVED strategies to Campaign Strategist, persist campaigns."""
    try:
        agent_class = get_agent_class("campaign-strategist")
        if not agent_class:
            logger.warning("campaign_strategist_not_found", company_id=str(company_id))
            return

        # Fetch the approved strategy rows to pass as rich context
        async with async_session_factory() as db:
            stmt = select(Strategy).where(Strategy.id.in_(strategy_ids))
            result = await db.execute(stmt)
            strategies = result.scalars().all()

        if not strategies:
            logger.warning("no_approved_strategies_found", company_id=str(company_id))
            return

        strategy_context = [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "rationale": s.rationale,
                "expected_outcome": s.expected_outcome,
                "priority": s.priority.value if s.priority else "medium",
                "target_segment": s.target_segment,
                "estimated_timeline": s.estimated_timeline,
                "success_metrics": s.success_metrics or [],
            }
            for s in strategies
        ]

        agent = agent_class()
        context: dict = {
            "company_id": str(company_id),
            "company_name": company.name,
            "industry": company.industry or "",
            "description": company.description or "",
            "products": company.products or [],
            "target_markets": company.target_markets or ["Singapore"],
            "planning_horizon_months": planning_horizon_months,
            "approved_strategies": strategy_context,
        }

        result = await agent.run(
            task=(
                f"Create a {planning_horizon_months}-month GTM roadmap for {company.name} "
                f"based on {len(strategies)} approved strategic initiatives"
            ),
            context=context,
        )

        if not result:
            logger.warning("campaign_strategist_no_result", company_id=str(company_id))
            return

        # Persist roadmap + campaigns (same pattern as roadmap.py)
        from packages.database.src.models import GTMRoadmap

        async with async_session_factory() as db:
            roadmap = GTMRoadmap(
                company_id=company_id,
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
            await db.flush()

            # Map each campaign phase to RoadmapPhase and link to a strategy where possible
            all_campaigns = [
                (RoadmapPhase.IMMEDIATE, result.immediate_campaigns),
                (RoadmapPhase.SHORT_TERM, result.short_term_campaigns),
                (RoadmapPhase.MID_TERM, result.mid_term_campaigns),
                (RoadmapPhase.LONG_TERM, result.long_term_campaigns),
            ]

            # Build a name→strategy_id lookup for optional linkage
            name_to_strategy: dict[str, UUID] = {}
            for s in strategies:
                name_to_strategy[s.name.lower()] = s.id

            for phase, campaigns in all_campaigns:
                for camp in campaigns:
                    # Try to match campaign to a strategy by name similarity
                    matched_strategy_id: UUID | None = None
                    camp_name_lower = camp.name.lower()
                    for strat_name, strat_id in name_to_strategy.items():
                        if strat_name[:20] in camp_name_lower or camp_name_lower[:20] in strat_name:
                            matched_strategy_id = strat_id
                            break

                    db.add(
                        Campaign(
                            company_id=company_id,
                            roadmap_id=roadmap.id,
                            strategy_id=matched_strategy_id,
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
                    )

            await db.commit()

            logger.info(
                "strategy_campaigns_persisted",
                company_id=str(company_id),
                roadmap_id=str(roadmap.id),
                strategy_count=len(strategies),
                campaign_count=sum(len(c) for _, c in all_campaigns),
            )

    except Exception as e:
        logger.error(
            "strategy_campaign_generation_failed",
            company_id=str(company_id),
            error=str(e),
        )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/{company_id}/strategies", response_model=StrategyListResponse)
async def list_strategies(
    company_id: UUID,
    status: str | None = Query(default=None, description="Filter by status (proposed, approved, rejected, in_progress, completed, revised)"),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyListResponse:
    """List all strategies for a company, optionally filtered by status."""
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)

    stmt = select(Strategy).where(Strategy.company_id == company_id)
    if status:
        try:
            status_enum = StrategyStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status!r}")
        stmt = stmt.where(Strategy.status == status_enum)
    stmt = stmt.order_by(Strategy.created_at.desc())

    result = await db.execute(stmt)
    strategies = result.scalars().all()

    return StrategyListResponse(
        strategies=[_strategy_to_response(s) for s in strategies],
        total=len(strategies),
        by_status=_count_by_status(list(strategies)),
    )


@router.get("/{company_id}/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    company_id: UUID,
    strategy_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """Fetch a single strategy by ID."""
    await validate_company_access(company_id, current_user, db)

    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Strategy not found")

    return _strategy_to_response(strategy)


@router.post("/{company_id}/strategies/{strategy_id}/approve", response_model=StrategyResponse)
async def approve_strategy(
    company_id: UUID,
    strategy_id: UUID,
    body: ApproveStrategyRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """Approve a strategy — transitions it to APPROVED with timestamp."""
    await validate_company_access(company_id, current_user, db)

    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if strategy.status not in (StrategyStatus.PROPOSED, StrategyStatus.REVISED):
        raise HTTPException(
            status_code=400,
            detail=f"Strategy cannot be approved from status: {strategy.status.value}",
        )

    strategy.status = StrategyStatus.APPROVED
    strategy.approved_at = datetime.now(UTC)
    strategy.approved_by = body.approved_by

    await db.commit()
    await db.refresh(strategy)

    logger.info("strategy_approved", strategy_id=str(strategy_id), approved_by=body.approved_by)
    return _strategy_to_response(strategy)


@router.post("/{company_id}/strategies/{strategy_id}/reject", response_model=StrategyResponse)
async def reject_strategy(
    company_id: UUID,
    strategy_id: UUID,
    body: RejectStrategyRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """Reject a strategy, optionally recording the reason in user_notes."""
    await validate_company_access(company_id, current_user, db)

    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if strategy.status == StrategyStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot reject a completed strategy")

    strategy.status = StrategyStatus.REJECTED
    if body.reason:
        strategy.user_notes = body.reason

    await db.commit()
    await db.refresh(strategy)

    logger.info("strategy_rejected", strategy_id=str(strategy_id))
    return _strategy_to_response(strategy)


@router.patch("/{company_id}/strategies/{strategy_id}", response_model=StrategyResponse)
async def patch_strategy(
    company_id: UUID,
    strategy_id: UUID,
    body: PatchStrategyRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """Edit user-editable fields on a strategy (name, description, user_notes, priority)."""
    await validate_company_access(company_id, current_user, db)

    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if body.name is not None:
        strategy.name = body.name
    if body.description is not None:
        strategy.description = body.description
    if body.user_notes is not None:
        strategy.user_notes = body.user_notes
    if body.priority is not None:
        strategy.priority = StrategyPriority(body.priority)

    await db.commit()
    await db.refresh(strategy)

    logger.info("strategy_patched", strategy_id=str(strategy_id))
    return _strategy_to_response(strategy)


@router.post("/{company_id}/strategies/generate")
async def generate_strategies(
    company_id: UUID,
    request: GenerateStrategiesRequest,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Trigger the Strategy Proposer agent to propose new strategic initiatives.

    Runs in background — the agent reads all available insights (SignalEvents,
    bus history, analysis results) for this company and persists Strategy rows
    with status=PROPOSED.

    Poll GET /{company_id}/strategies?status=proposed to see results.
    """
    await validate_company_access(company_id, current_user, db)
    company = await verify_company_exists(db, company_id)

    logger.info(
        "strategy_generation_requested",
        company_id=str(company_id),
        max_strategies=request.max_strategies,
    )

    background_tasks.add_task(
        _run_strategy_proposer,
        company_id=company_id,
        company=company,
        analysis_id=request.analysis_id,
        max_strategies=request.max_strategies,
    )

    return {
        "status": "generating",
        "company_id": str(company_id),
        "message": (
            "Strategy Proposer is analysing insights and will propose up to "
            f"{request.max_strategies} strategic initiatives. "
            "Poll GET /strategies?status=proposed for results."
        ),
    }


@router.post("/{company_id}/strategies/generate-campaigns")
async def generate_campaigns_from_strategies(
    company_id: UUID,
    request: GenerateCampaignsRequest,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Generate a Gantt-style campaign roadmap from all APPROVED strategies.

    Only APPROVED strategies are passed to the Campaign Strategist.
    The resulting campaigns are linked back to their source strategy via
    the strategy_id FK on the campaigns table.

    Runs in background — poll GET /{company_id}/roadmap for results.
    """
    await validate_company_access(company_id, current_user, db)
    company = await verify_company_exists(db, company_id)

    # Fetch all approved strategies for this company
    stmt = select(Strategy).where(
        Strategy.company_id == company_id,
        Strategy.status == StrategyStatus.APPROVED,
    )
    result = await db.execute(stmt)
    approved = result.scalars().all()

    if not approved:
        raise HTTPException(
            status_code=400,
            detail="No approved strategies found. Approve at least one strategy before generating campaigns.",
        )

    strategy_ids = [s.id for s in approved]

    logger.info(
        "strategy_campaign_generation_requested",
        company_id=str(company_id),
        approved_strategies=len(strategy_ids),
    )

    background_tasks.add_task(
        _run_campaign_generator_from_strategies,
        company_id=company_id,
        company=company,
        strategy_ids=strategy_ids,
        planning_horizon_months=request.planning_horizon_months,
    )

    return {
        "status": "generating",
        "company_id": str(company_id),
        "approved_strategies": len(strategy_ids),
        "message": (
            f"Campaign Strategist is building a {request.planning_horizon_months}-month roadmap "
            f"from {len(strategy_ids)} approved strategies. "
            "Poll GET /roadmap for results."
        ),
    }
