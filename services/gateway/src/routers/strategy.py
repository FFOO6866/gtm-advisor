"""Strategy management API endpoints.

Provides endpoints for:
- Strategy dashboard data
- Recommendations management
- Running strategy analysis
"""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import (
    AgentActivity as AgentActivityModel,
)
from packages.database.src.models import (
    Company,
    PhaseStatus,
    RecommendationPriority,
    RecommendationStatus,
    StrategyRun,
)
from packages.database.src.models import (
    StrategyPhase as StrategyPhaseModel,
)
from packages.database.src.models import (
    StrategyRecommendation as StrategyRecommendationModel,
)
from packages.database.src.session import get_db_session

from ..agents_registry import AGENT_METADATA, TOTAL_AGENTS, get_agent_class
from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User
from ..utils import verify_company_exists

logger = structlog.get_logger()
router = APIRouter()


# ============================================================================
# Constants
# ============================================================================

MAX_RECOMMENDATIONS_PER_COMPANY = 10
MAX_RECENT_ACTIVITIES = 10

# Phases map to logical stages, not 1:1 with agents
STRATEGY_PHASES = [
    {
        "key": "discovery",
        "name": "Discovery",
        "icon": "🔍",
        "description": "Gathering market and company data",
    },
    {
        "key": "analysis",
        "name": "Analysis",
        "icon": "📊",
        "description": "Analyzing competitors and customers",
    },
    {
        "key": "synthesis",
        "name": "Synthesis",
        "icon": "🎯",
        "description": "Synthesizing insights into strategy",
    },
    {
        "key": "recommendations",
        "name": "Recommendations",
        "icon": "💡",
        "description": "Generating actionable recommendations",
    },
    {"key": "complete", "name": "Complete", "icon": "✅", "description": "Analysis complete"},
]


# ============================================================================
# Schemas (matching frontend types exactly)
# ============================================================================


class StrategyPhaseResponse(BaseModel):
    """Strategy phase information - matches frontend StrategyPhase interface."""

    id: str
    name: str
    status: str  # 'pending', 'in_progress', 'complete'
    icon: str
    started_at: str | None = None
    completed_at: str | None = None


class StrategyMetricsResponse(BaseModel):
    """Strategy metrics."""

    agents_active: int = 0
    agents_total: int = TOTAL_AGENTS
    tasks_completed: int = 0
    avg_confidence: float = 0.0
    avg_execution_time_ms: float = 0.0


class AgentActivityResponse(BaseModel):
    """Recent agent activity - matches frontend AgentActivity interface."""

    id: str
    agent_id: str
    agent_name: str
    action: str
    icon: str
    created_at: str


class StrategyRecommendationResponse(BaseModel):
    """Strategy recommendation - matches frontend StrategyRecommendation interface."""

    id: str
    company_id: str
    priority: str  # 'high', 'medium', 'low'
    title: str
    description: str
    source_agents: list[str]
    impact: str
    confidence: float
    status: str  # 'pending', 'in_progress', 'completed', 'dismissed'
    created_at: str
    updated_at: str | None = None


class StrategyDashboardResponse(BaseModel):
    """Strategy dashboard response - matches frontend StrategyDashboard interface."""

    phases: list[StrategyPhaseResponse]
    recommendations: list[StrategyRecommendationResponse]
    recent_activity: list[AgentActivityResponse]
    metrics: StrategyMetricsResponse
    last_run_at: str | None = None


class StrategyRunResponse(BaseModel):
    """Response from running strategy analysis."""

    analysis_id: str
    status: str


class RecommendationStatusUpdate(BaseModel):
    """Update recommendation status."""

    status: str = Field(..., pattern="^(in_progress|completed|dismissed)$")


# ============================================================================
# Helper Functions
# ============================================================================


def phase_to_response(phase: StrategyPhaseModel) -> StrategyPhaseResponse:
    """Convert database phase to response."""
    return StrategyPhaseResponse(
        id=phase.phase_key,
        name=phase.name,
        status=phase.status.value if phase.status else "pending",
        icon=phase.icon or "📋",
        started_at=phase.started_at.isoformat() if phase.started_at else None,
        completed_at=phase.completed_at.isoformat() if phase.completed_at else None,
    )


def recommendation_to_response(rec: StrategyRecommendationModel) -> StrategyRecommendationResponse:
    """Convert database recommendation to response."""
    return StrategyRecommendationResponse(
        id=str(rec.id),
        company_id=str(rec.company_id),
        priority=rec.priority.value if rec.priority else "medium",
        title=rec.title,
        description=rec.description or "",
        source_agents=rec.source_agents or [],
        impact=rec.impact or "",
        confidence=rec.confidence or 0.0,
        status=rec.status.value if rec.status else "pending",
        created_at=rec.created_at.isoformat() if rec.created_at else datetime.utcnow().isoformat(),
        updated_at=rec.updated_at.isoformat() if rec.updated_at else None,
    )


def activity_to_response(activity: AgentActivityModel) -> AgentActivityResponse:
    """Convert database activity to response."""
    return AgentActivityResponse(
        id=str(activity.id),
        agent_id=activity.agent_id,
        agent_name=activity.agent_name,
        action=activity.action,
        icon=activity.icon or "💡",
        created_at=activity.created_at.isoformat()
        if activity.created_at
        else datetime.utcnow().isoformat(),
    )


def get_default_phase_responses() -> list[StrategyPhaseResponse]:
    """Get default phases when no run exists."""
    return [
        StrategyPhaseResponse(
            id=phase["key"],
            name=phase["name"],
            status="pending",
            icon=phase["icon"],
            started_at=None,
            completed_at=None,
        )
        for phase in STRATEGY_PHASES
    ]


def extract_recommendations_from_results(
    company_id: UUID,
    strategy_run_id: UUID,
    agent_results: dict[str, dict],
) -> list[StrategyRecommendationModel]:
    """Extract recommendations from actual agent output structures.

    Uses the real field names from each agent's output model:
    - MarketIntelligenceOutput: opportunities (list[MarketOpportunity])
    - CompetitorIntelOutput: competitive_positioning.market_gaps, strategic_recommendations
    - CustomerProfileOutput: personas, targeting_recommendations
    - LeadHuntingOutput: qualified_count, prospects, total_pipeline_value
    - CampaignPlanOutput: content_pieces, timeline_recommendations
    """
    recommendations = []
    now = datetime.utcnow()

    # Extract from Market Intelligence results (MarketIntelligenceOutput)
    market_result = agent_results.get("market-intelligence", {})
    if market_result:
        # opportunities is list[MarketOpportunity] with: title, description, recommended_action
        opportunities = market_result.get("opportunities", [])
        confidence = market_result.get("confidence", 0.7)

        for i, opp in enumerate(opportunities[:2]):  # Max 2 from market intel
            title = opp.get("title") if isinstance(opp, dict) else getattr(opp, "title", None)
            desc = (
                opp.get("description")
                if isinstance(opp, dict)
                else getattr(opp, "description", None)
            )
            action = (
                opp.get("recommended_action")
                if isinstance(opp, dict)
                else getattr(opp, "recommended_action", None)
            )

            if title:
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.HIGH
                        if i == 0
                        else RecommendationPriority.MEDIUM,
                        title=title,
                        description=f"{desc or ''} {action or ''}".strip()
                        or "Market opportunity identified.",
                        source_agents=["market-intelligence"],
                        impact="Revenue Growth",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

        # Also extract from implications_for_gtm
        gtm_implications = market_result.get("implications_for_gtm", [])
        for impl in gtm_implications[:1]:
            if impl and isinstance(impl, str):
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.MEDIUM,
                        title="GTM Strategy Insight",
                        description=impl,
                        source_agents=["market-intelligence"],
                        impact="Strategic Direction",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

    # Extract from Competitor Analysis results (CompetitorIntelOutput)
    competitor_result = agent_results.get("competitor-analyst", {})
    if competitor_result:
        confidence = competitor_result.get("confidence", 0.7)

        # competitive_positioning.market_gaps is list[str]
        positioning = competitor_result.get("competitive_positioning", {})
        market_gaps = positioning.get("market_gaps", []) if isinstance(positioning, dict) else []

        for gap in market_gaps[:1]:
            if gap and isinstance(gap, str):
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.HIGH,
                        title="Market Gap Opportunity",
                        description=gap,
                        source_agents=["competitor-analyst"],
                        impact="Competitive Advantage",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

        # strategic_recommendations is list[str]
        strategic_recs = competitor_result.get("strategic_recommendations", [])
        for rec in strategic_recs[:1]:
            if rec and isinstance(rec, str):
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.MEDIUM,
                        title="Competitive Strategy",
                        description=rec,
                        source_agents=["competitor-analyst"],
                        impact="Market Positioning",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

    # Extract from Customer Profiler results (CustomerProfileOutput)
    customer_result = agent_results.get("customer-profiler", {})
    if customer_result:
        confidence = customer_result.get("confidence", 0.7)

        # personas is list[CustomerPersona] with title, description, etc.
        personas = customer_result.get("personas", [])
        if personas:
            persona = personas[0]
            persona_title = (
                persona.get("title")
                if isinstance(persona, dict)
                else getattr(persona, "title", None)
            )
            if persona_title:
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.HIGH,
                        title=f"Target: {persona_title}",
                        description="Focus sales and marketing efforts on this high-value persona.",
                        source_agents=["customer-profiler"],
                        impact="Customer Acquisition",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

        # targeting_recommendations is list[str]
        targeting_recs = customer_result.get("targeting_recommendations", [])
        for rec in targeting_recs[:1]:
            if rec and isinstance(rec, str):
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.MEDIUM,
                        title="Targeting Strategy",
                        description=rec,
                        source_agents=["customer-profiler"],
                        impact="Lead Quality",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

    # Extract from Lead Hunter results (LeadHuntingOutput)
    lead_result = agent_results.get("lead-hunter", {})
    if lead_result:
        confidence = lead_result.get("confidence", 0.7)

        # qualified_count and total_pipeline_value are direct fields
        qualified_count = lead_result.get("qualified_count", 0)
        pipeline_value = lead_result.get("total_pipeline_value", 0)

        if qualified_count > 0:
            value_str = f" (est. ${pipeline_value:,.0f} pipeline)" if pipeline_value > 0 else ""
            recommendations.append(
                StrategyRecommendationModel(
                    company_id=company_id,
                    strategy_run_id=strategy_run_id,
                    priority=RecommendationPriority.HIGH,
                    title=f"Pursue {qualified_count} Qualified Leads",
                    description=f"Lead analysis identified {qualified_count} prospects matching your ICP{value_str}.",
                    source_agents=["lead-hunter"],
                    impact="Pipeline Growth",
                    confidence=confidence,
                    status=RecommendationStatus.PENDING,
                    created_at=now,
                )
            )

        # top_recommendations is list[str]
        top_recs = lead_result.get("top_recommendations", [])
        for rec in top_recs[:1]:
            if rec and isinstance(rec, str):
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.MEDIUM,
                        title="Lead Generation Strategy",
                        description=rec,
                        source_agents=["lead-hunter"],
                        impact="Sales Efficiency",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

    # Extract from Campaign Architect results (CampaignPlanOutput)
    campaign_result = agent_results.get("campaign-architect", {})
    if campaign_result:
        confidence = campaign_result.get("confidence", 0.7)

        # content_pieces is list[ContentPiece] with type, title, content
        content_pieces = campaign_result.get("content_pieces", [])
        if content_pieces:
            piece_types = set()
            for piece in content_pieces:
                piece_type = (
                    piece.get("type") if isinstance(piece, dict) else getattr(piece, "type", None)
                )
                if piece_type:
                    piece_types.add(piece_type)

            if piece_types:
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.MEDIUM,
                        title=f"Launch Campaign: {', '.join(sorted(piece_types))}",
                        description=f"Campaign plan includes {len(content_pieces)} ready-to-use content pieces.",
                        source_agents=["campaign-architect"],
                        impact="Brand Awareness",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

        # timeline_recommendations is list[str]
        timeline_recs = campaign_result.get("timeline_recommendations", [])
        for rec in timeline_recs[:1]:
            if rec and isinstance(rec, str):
                recommendations.append(
                    StrategyRecommendationModel(
                        company_id=company_id,
                        strategy_run_id=strategy_run_id,
                        priority=RecommendationPriority.LOW,
                        title="Campaign Timeline",
                        description=rec,
                        source_agents=["campaign-architect"],
                        impact="Execution Planning",
                        confidence=confidence,
                        status=RecommendationStatus.PENDING,
                        created_at=now,
                    )
                )

    # If no recommendations were generated, create a summary recommendation
    if not recommendations:
        avg_confidence = sum(r.get("confidence", 0) for r in agent_results.values()) / max(
            len(agent_results), 1
        )

        recommendations.append(
            StrategyRecommendationModel(
                company_id=company_id,
                strategy_run_id=strategy_run_id,
                priority=RecommendationPriority.MEDIUM,
                title="Analysis Complete",
                description="Strategy analysis finished. Review individual agent outputs for detailed insights.",
                source_agents=list(agent_results.keys()),
                impact="Strategic Clarity",
                confidence=avg_confidence,
                status=RecommendationStatus.PENDING,
                created_at=now,
            )
        )

    return recommendations[:MAX_RECOMMENDATIONS_PER_COMPANY]


# ============================================================================
# Background Task for Strategy Analysis
# ============================================================================


async def run_strategy_analysis_task(
    company_id: UUID,
    strategy_run_id: UUID,
):
    """Background task to run the actual strategy analysis.

    Executes agents sequentially, updates phases, stores results,
    and generates recommendations from actual agent outputs.
    """
    from packages.database.src.session import async_session_factory

    async with async_session_factory() as db:
        try:
            strategy_run = await db.get(StrategyRun, strategy_run_id)
            if not strategy_run:
                logger.error("strategy_run_not_found", run_id=str(strategy_run_id))
                return

            # Get company for context
            company = await db.get(Company, company_id)
            if not company:
                logger.error("company_not_found", company_id=str(company_id))
                strategy_run.status = "failed"
                await db.commit()
                return

            start_time = datetime.utcnow()
            agent_results: dict[str, dict] = {}
            completed_agents: list[str] = []
            total_confidence = 0.0

            # Define agent execution order and phase mapping
            agent_phases = [
                ("discovery", ["market-intelligence"]),
                ("analysis", ["competitor-analyst", "customer-profiler"]),
                ("synthesis", ["lead-hunter"]),
                ("recommendations", ["campaign-architect"]),
            ]

            # Get phases
            phases_result = await db.execute(
                select(StrategyPhaseModel).where(
                    StrategyPhaseModel.strategy_run_id == strategy_run_id
                )
            )
            phases_dict = {p.phase_key: p for p in phases_result.scalars().all()}

            for phase_key, agent_ids in agent_phases:
                phase = phases_dict.get(phase_key)
                if phase:
                    phase.status = PhaseStatus.IN_PROGRESS
                    phase.started_at = datetime.utcnow()
                    await db.commit()

                # Update running count
                strategy_run.agents_active = len(agent_ids)
                await db.commit()

                for agent_id in agent_ids:
                    try:
                        agent_class = get_agent_class(agent_id)
                        if not agent_class:
                            logger.warning("agent_class_not_found", agent_id=agent_id)
                            continue

                        agent = agent_class()
                        metadata = AGENT_METADATA.get(agent_id, {})

                        # Build context with company data
                        context = {
                            "company_id": str(company_id),
                            "company_name": company.name,
                            "industry": company.industry,
                            "description": company.description,
                            "goals": company.goals or [],
                            "challenges": company.challenges or [],
                            "target_markets": company.target_markets or [],
                        }

                        task = metadata.get("task_description", f"Execute {agent_id}")
                        result = await agent.run(task, context=context)

                        # Extract result data
                        confidence = getattr(result, "confidence", 0.7)
                        total_confidence += confidence
                        completed_agents.append(agent_id)

                        # Store result for recommendation generation
                        if hasattr(result, "model_dump"):
                            agent_results[agent_id] = result.model_dump()
                        elif hasattr(result, "__dict__"):
                            agent_results[agent_id] = {
                                k: v for k, v in result.__dict__.items() if not k.startswith("_")
                            }
                        else:
                            agent_results[agent_id] = {"raw": str(result)}

                        agent_results[agent_id]["confidence"] = confidence

                        # Log activity
                        activity = AgentActivityModel(
                            strategy_run_id=strategy_run_id,
                            company_id=company_id,
                            agent_id=agent_id,
                            agent_name=metadata.get("title", agent_id),
                            action=f"Completed: {confidence * 100:.0f}% confidence",
                            icon=metadata.get("avatar", "🤖"),
                        )
                        db.add(activity)
                        await db.commit()

                        logger.info(
                            "agent_completed",
                            agent_id=agent_id,
                            confidence=confidence,
                            company_id=str(company_id),
                        )

                    except Exception as e:
                        logger.error(
                            "agent_execution_failed",
                            agent_id=agent_id,
                            error=str(e),
                            company_id=str(company_id),
                        )
                        # Log failure activity
                        activity = AgentActivityModel(
                            strategy_run_id=strategy_run_id,
                            company_id=company_id,
                            agent_id=agent_id,
                            agent_name=AGENT_METADATA.get(agent_id, {}).get("title", agent_id),
                            action="Failed - continuing with other agents",
                            icon="⚠️",
                        )
                        db.add(activity)
                        await db.commit()

                # Mark phase complete
                if phase:
                    phase.status = PhaseStatus.COMPLETE
                    phase.completed_at = datetime.utcnow()
                    await db.commit()

            # Mark final phase complete
            complete_phase = phases_dict.get("complete")
            if complete_phase:
                complete_phase.status = PhaseStatus.COMPLETE
                complete_phase.started_at = datetime.utcnow()
                complete_phase.completed_at = datetime.utcnow()
                await db.commit()

            # Generate recommendations from actual results
            recommendations = extract_recommendations_from_results(
                company_id, strategy_run_id, agent_results
            )

            for rec in recommendations:
                db.add(rec)

            # Update strategy run with final metrics
            end_time = datetime.utcnow()
            strategy_run.status = "completed"
            strategy_run.completed_at = end_time
            strategy_run.agents_active = 0
            strategy_run.tasks_completed = len(completed_agents)
            strategy_run.avg_confidence = total_confidence / max(len(completed_agents), 1)
            strategy_run.execution_time_ms = (end_time - start_time).total_seconds() * 1000

            await db.commit()

            logger.info(
                "strategy_analysis_completed",
                company_id=str(company_id),
                run_id=str(strategy_run_id),
                agents_completed=len(completed_agents),
                recommendations_generated=len(recommendations),
                execution_time_ms=strategy_run.execution_time_ms,
            )

        except Exception as e:
            logger.error("strategy_analysis_failed", error=str(e), company_id=str(company_id))
            try:
                if strategy_run:
                    strategy_run.status = "failed"
                    strategy_run.agents_active = 0
                    await db.commit()
            except Exception:
                pass


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/{company_id}/strategy/dashboard", response_model=StrategyDashboardResponse)
async def get_strategy_dashboard(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyDashboardResponse:
    """Get strategy dashboard for a company."""
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)

    # Get the latest strategy run
    latest_run_result = await db.execute(
        select(StrategyRun)
        .where(StrategyRun.company_id == company_id)
        .options(
            selectinload(StrategyRun.phases),
            selectinload(StrategyRun.activities),
        )
        .order_by(desc(StrategyRun.started_at))
        .limit(1)
    )
    latest_run = latest_run_result.scalar_one_or_none()

    # Get recommendations for company
    recommendations_result = await db.execute(
        select(StrategyRecommendationModel)
        .where(StrategyRecommendationModel.company_id == company_id)
        .where(StrategyRecommendationModel.status != RecommendationStatus.DISMISSED)
        .order_by(desc(StrategyRecommendationModel.created_at))
        .limit(MAX_RECOMMENDATIONS_PER_COMPANY)
    )
    recommendations = recommendations_result.scalars().all()

    # Get recent activities
    activities_result = await db.execute(
        select(AgentActivityModel)
        .where(AgentActivityModel.company_id == company_id)
        .order_by(desc(AgentActivityModel.created_at))
        .limit(MAX_RECENT_ACTIVITIES)
    )
    activities = activities_result.scalars().all()

    if latest_run:
        phases = [
            phase_to_response(p) for p in sorted(latest_run.phases, key=lambda x: x.phase_key)
        ]
        metrics = StrategyMetricsResponse(
            agents_active=latest_run.agents_active or 0,
            agents_total=latest_run.agents_total or TOTAL_AGENTS,
            tasks_completed=latest_run.tasks_completed or 0,
            avg_confidence=latest_run.avg_confidence or 0.0,
            avg_execution_time_ms=latest_run.execution_time_ms or 0.0,
        )
        last_run_at = latest_run.started_at.isoformat() if latest_run.started_at else None
    else:
        phases = get_default_phase_responses()
        metrics = StrategyMetricsResponse()
        last_run_at = None

    return StrategyDashboardResponse(
        phases=phases,
        recommendations=[recommendation_to_response(r) for r in recommendations],
        recent_activity=[activity_to_response(a) for a in activities],
        metrics=metrics,
        last_run_at=last_run_at,
    )


@router.get(
    "/{company_id}/strategy/recommendations", response_model=list[StrategyRecommendationResponse]
)
async def get_strategy_recommendations(
    company_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[StrategyRecommendationResponse]:
    """Get all recommendations for a company."""
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)

    result = await db.execute(
        select(StrategyRecommendationModel)
        .where(StrategyRecommendationModel.company_id == company_id)
        .order_by(desc(StrategyRecommendationModel.created_at))
    )
    recommendations = result.scalars().all()

    return [recommendation_to_response(r) for r in recommendations]


@router.post("/{company_id}/strategy/run", response_model=StrategyRunResponse)
async def run_strategy_analysis(
    company_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyRunResponse:
    """Run strategy analysis for a company.

    Only one analysis can run at a time per company.
    """
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)

    # Check for existing running analysis (prevent concurrent runs)
    existing_run = await db.execute(
        select(StrategyRun)
        .where(StrategyRun.company_id == company_id)
        .where(StrategyRun.status == "running")
        .limit(1)
    )
    if existing_run.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="Strategy analysis already running for this company"
        )

    now = datetime.utcnow()

    # Create strategy run
    strategy_run = StrategyRun(
        company_id=company_id,
        status="running",
        agents_active=TOTAL_AGENTS,
        agents_total=TOTAL_AGENTS,
        started_at=now,
    )
    db.add(strategy_run)
    await db.flush()

    # Create phases
    for phase_def in STRATEGY_PHASES:
        phase = StrategyPhaseModel(
            strategy_run_id=strategy_run.id,
            phase_key=phase_def["key"],
            name=phase_def["name"],
            icon=phase_def["icon"],
            status=PhaseStatus.PENDING,
        )
        db.add(phase)

    await db.commit()

    # Schedule background task
    background_tasks.add_task(run_strategy_analysis_task, company_id, strategy_run.id)

    logger.info(
        "strategy_analysis_started", company_id=str(company_id), run_id=str(strategy_run.id)
    )

    return StrategyRunResponse(
        analysis_id=str(strategy_run.id),
        status="running",
    )


@router.patch(
    "/{company_id}/strategy/recommendations/{recommendation_id}",
    response_model=StrategyRecommendationResponse,
)
async def update_recommendation_status(
    company_id: UUID,
    recommendation_id: UUID,
    data: RecommendationStatusUpdate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyRecommendationResponse:
    """Update recommendation status."""
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)

    rec = await db.get(StrategyRecommendationModel, recommendation_id)
    if not rec or rec.company_id != company_id:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    status_map = {
        "in_progress": RecommendationStatus.IN_PROGRESS,
        "completed": RecommendationStatus.COMPLETED,
        "dismissed": RecommendationStatus.DISMISSED,
    }
    rec.status = status_map.get(data.status, RecommendationStatus.PENDING)
    rec.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(rec)

    logger.info(
        "recommendation_updated", recommendation_id=str(recommendation_id), status=data.status
    )

    return recommendation_to_response(rec)
