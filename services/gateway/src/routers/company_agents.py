"""Company-scoped agent API endpoints.

Provides company-scoped endpoints for:
- Running agents in company context
- Getting agent status
"""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    AgentRun,
    AgentRunStatus,
    Company,
)
from packages.database.src.session import get_db_session

from ..agents_registry import (
    get_agent_class,
    get_task_description,
    is_valid_agent,
)
from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User
from ..utils import verify_company_exists

logger = structlog.get_logger()
router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class AgentRunResponse(BaseModel):
    """Response from triggering an agent."""

    task_id: str
    status: str


class AgentStatusResponse(BaseModel):
    """Response for agent status."""

    status: str  # 'idle', 'running', 'completed', 'error'
    last_run_at: str | None = None
    current_task_id: str | None = None
    error_message: str | None = None


# ============================================================================
# Helper Functions
# ============================================================================


def validate_agent_id(agent_id: str) -> None:
    """Validate that the agent ID exists."""
    if not is_valid_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


# ============================================================================
# Background Task for Agent Execution
# ============================================================================


async def run_agent_task(
    company_id: UUID,
    agent_id: str,
    agent_run_id: UUID,
):
    """Background task to run the agent."""
    from packages.database.src.session import async_session_factory

    async with async_session_factory() as db:
        agent_run = await db.get(AgentRun, agent_run_id)
        if not agent_run:
            logger.error("agent_run_not_found", run_id=str(agent_run_id))
            return

        try:
            # Get company for context
            company = await db.get(Company, company_id)
            if not company:
                agent_run.status = AgentRunStatus.ERROR
                agent_run.error_message = "Company not found"
                agent_run.completed_at = datetime.utcnow()
                await db.commit()
                return

            # Get the agent class
            agent_class = get_agent_class(agent_id)
            if not agent_class:
                agent_run.status = AgentRunStatus.ERROR
                agent_run.error_message = "Agent not available"
                agent_run.completed_at = datetime.utcnow()
                await db.commit()
                return

            # Create agent instance and run
            agent = agent_class()
            task = get_task_description(agent_id)

            # Build rich context from company data
            context = {
                "company_id": str(company_id),
                "company_name": company.name,
                "industry": company.industry,
                "description": company.description,
                "goals": company.goals or [],
                "challenges": company.challenges or [],
                "target_markets": company.target_markets or [],
                "triggered_at": datetime.utcnow().isoformat(),
            }

            result = await agent.run(task, context=context)

            # Update with success
            agent_run.status = AgentRunStatus.COMPLETED
            agent_run.completed_at = datetime.utcnow()
            agent_run.confidence = getattr(result, "confidence", None)

            # Store summary of result
            if hasattr(result, "model_dump"):
                result_data = result.model_dump()
                agent_run.result_summary = str(result_data)[:500]
            else:
                agent_run.result_summary = str(result)[:500] if result else None

            await db.commit()

            logger.info(
                "agent_completed",
                company_id=str(company_id),
                agent_id=agent_id,
                task_id=str(agent_run.task_id),
                confidence=agent_run.confidence,
            )

        except Exception as e:
            logger.error(
                "agent_execution_failed",
                company_id=str(company_id),
                agent_id=agent_id,
                error=str(e),
            )

            # Update with error - don't expose internal details to users
            agent_run.status = AgentRunStatus.ERROR
            agent_run.completed_at = datetime.utcnow()
            agent_run.error_message = "Agent execution failed. Please try again."
            await db.commit()


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/{company_id}/agents/{agent_id}/run", response_model=AgentRunResponse)
async def trigger_agent(
    company_id: UUID,
    agent_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> AgentRunResponse:
    """Trigger an agent run for a specific company.

    The agent runs in the background and the status can be polled via the status endpoint.
    Only one run per agent per company at a time.
    """
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)
    validate_agent_id(agent_id)

    # Check for existing running agent (prevent concurrent runs)
    existing_run = await db.execute(
        select(AgentRun)
        .where(AgentRun.company_id == company_id)
        .where(AgentRun.agent_id == agent_id)
        .where(AgentRun.status == AgentRunStatus.RUNNING)
        .limit(1)
    )
    if existing_run.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail=f"Agent '{agent_id}' is already running for this company"
        )

    now = datetime.utcnow()

    # Create agent run record
    agent_run = AgentRun(
        company_id=company_id,
        agent_id=agent_id,
        status=AgentRunStatus.RUNNING,
        started_at=now,
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(agent_run)

    # Schedule background task
    background_tasks.add_task(run_agent_task, company_id, agent_id, agent_run.id)

    logger.info(
        "agent_triggered",
        company_id=str(company_id),
        agent_id=agent_id,
        task_id=str(agent_run.task_id),
    )

    return AgentRunResponse(
        task_id=str(agent_run.task_id),
        status="running",
    )


@router.get("/{company_id}/agents/{agent_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(
    company_id: UUID,
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> AgentStatusResponse:
    """Get the status of an agent for a specific company."""
    await validate_company_access(company_id, current_user, db)
    await verify_company_exists(db, company_id)
    validate_agent_id(agent_id)

    # Get the latest run for this agent and company
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.company_id == company_id)
        .where(AgentRun.agent_id == agent_id)
        .order_by(desc(AgentRun.started_at))
        .limit(1)
    )
    latest_run = result.scalar_one_or_none()

    if not latest_run:
        return AgentStatusResponse(
            status="idle",
            last_run_at=None,
            current_task_id=None,
            error_message=None,
        )

    return AgentStatusResponse(
        status=latest_run.status.value if latest_run.status else "idle",
        last_run_at=latest_run.started_at.isoformat() if latest_run.started_at else None,
        current_task_id=str(latest_run.task_id) if latest_run.task_id else None,
        error_message=latest_run.error_message
        if latest_run.status == AgentRunStatus.ERROR
        else None,
    )
