"""Workforce router — Digital Workforce design, approval, execution, and monitoring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    Analysis,
    AnalysisStatus,
    ExecutionMetric,
    ExecutionRun,
    ExecutionRunStatus,
    WorkforceConfig,
    WorkforceStatus,
)
from packages.database.src.session import get_db_session

router = APIRouter()
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class WorkforceConfigResponse(BaseModel):
    id: str
    company_id: str
    analysis_id: str | None
    status: str
    definition: dict
    approved_agents: list[str]
    executive_summary: str | None
    estimated_weekly_hours_saved: float
    estimated_monthly_revenue_impact_sgd: float
    agent_count: int
    created_at: str
    updated_at: str | None


class ExecutionRunResponse(BaseModel):
    id: str
    workforce_config_id: str
    company_id: str
    status: str
    trigger: str
    steps_total: int
    steps_completed: int
    steps_failed: int
    emails_sent: int
    crm_records_updated: int
    leads_contacted: int
    started_at: str
    completed_at: str | None


class ExecutionRunDetailResponse(ExecutionRunResponse):
    execution_log: list[dict]
    metrics: list[dict]


class MetricPoint(BaseModel):
    date: str
    value: float
    unit: str


class MetricSeriesResponse(BaseModel):
    metric_name: str
    source: str
    points: list[MetricPoint]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_to_response(c: WorkforceConfig) -> WorkforceConfigResponse:
    return WorkforceConfigResponse(
        id=str(c.id),
        company_id=str(c.company_id),
        analysis_id=str(c.analysis_id) if c.analysis_id else None,
        status=c.status.value,
        definition=c.definition or {},
        approved_agents=c.approved_agents or [],
        executive_summary=c.executive_summary,
        estimated_weekly_hours_saved=c.estimated_weekly_hours_saved or 0.0,
        estimated_monthly_revenue_impact_sgd=c.estimated_monthly_revenue_impact_sgd or 0.0,
        agent_count=c.agent_count or 0,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


def _run_to_response(r: ExecutionRun) -> ExecutionRunResponse:
    return ExecutionRunResponse(
        id=str(r.id),
        workforce_config_id=str(r.workforce_config_id),
        company_id=str(r.company_id),
        status=r.status.value,
        trigger=r.trigger or "manual",
        steps_total=r.steps_total or 0,
        steps_completed=r.steps_completed or 0,
        steps_failed=r.steps_failed or 0,
        emails_sent=r.emails_sent or 0,
        crm_records_updated=r.crm_records_updated or 0,
        leads_contacted=r.leads_contacted or 0,
        started_at=r.started_at.isoformat(),
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


# ---------------------------------------------------------------------------
# Design & Configuration
# ---------------------------------------------------------------------------

@router.post("/{company_id}/workforce/design")
async def design_workforce(
    company_id: UUID,
    analysis_id: UUID = Body(..., embed=True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Trigger WorkforceArchitectAgent to design a Digital Workforce.

    Reads the completed analysis and generates an agent roster, value chain,
    and KPIs. Returns immediately with workforce_config_id — runs in background.
    """
    # Load analysis to extract context
    analysis = await db.get(Analysis, analysis_id)
    if not analysis or str(analysis.company_id) != str(company_id):
        raise HTTPException(status_code=404, detail="Analysis not found")

    if analysis.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Analysis must be completed before designing a workforce",
        )

    # Create draft config record
    config = WorkforceConfig(
        company_id=company_id,
        analysis_id=analysis_id,
        status=WorkforceStatus.DRAFT,
        definition={},
        approved_agents=[],
    )
    db.add(config)
    await db.flush()
    config_id = config.id
    await db.commit()

    background_tasks.add_task(
        _run_workforce_design,
        config_id=config_id,
        analysis_id=analysis_id,
        company_id=company_id,
    )

    logger.info("workforce_design_started", company_id=str(company_id), config_id=str(config_id))
    return {"workforce_config_id": str(config_id), "status": "designing"}


@router.get("/{company_id}/workforce")
async def get_workforce_config(
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> WorkforceConfigResponse:
    """Return the latest WorkforceConfig for this company."""
    result = await db.execute(
        select(WorkforceConfig)
        .where(WorkforceConfig.company_id == company_id)
        .order_by(desc(WorkforceConfig.created_at))
        .limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No workforce configuration found")
    return _config_to_response(config)


@router.get("/{company_id}/workforce/{config_id}")
async def get_workforce_config_by_id(
    company_id: UUID,
    config_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> WorkforceConfigResponse:
    """Return a specific WorkforceConfig by ID."""
    config = await db.get(WorkforceConfig, config_id)
    if not config or str(config.company_id) != str(company_id):
        raise HTTPException(status_code=404, detail="Workforce config not found")
    return _config_to_response(config)


@router.patch("/{company_id}/workforce/{config_id}/approve")
async def approve_workforce(
    company_id: UUID,
    config_id: UUID,
    approved_agents: list[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db_session),
) -> WorkforceConfigResponse:
    """Approve a workforce design and select which agents to activate.

    Sets status to ACTIVE. The client chooses which agent types from the
    roster they want to run (e.g. ["outreach", "crm_sync"]).
    """
    config = await db.get(WorkforceConfig, config_id)
    if not config or str(config.company_id) != str(company_id):
        raise HTTPException(status_code=404, detail="Workforce config not found")

    if config.status == WorkforceStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Cannot approve an archived workforce")

    if config.status == WorkforceStatus.FAILED:
        raise HTTPException(status_code=400, detail="Cannot approve a failed workforce design — please retry")

    config.approved_agents = approved_agents
    config.status = WorkforceStatus.ACTIVE
    config.updated_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "workforce_approved",
        config_id=str(config_id),
        approved_agents=approved_agents,
    )
    return _config_to_response(config)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@router.post("/{company_id}/workforce/{config_id}/execute")
async def trigger_execution(
    company_id: UUID,
    config_id: UUID,
    trigger: str = Body(default="manual", embed=True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Start a new execution run for the active workforce.

    Returns immediately with execution_run_id. Execution happens in background.
    """
    config = await db.get(WorkforceConfig, config_id)
    if not config or str(config.company_id) != str(company_id):
        raise HTTPException(status_code=404, detail="Workforce config not found")

    if config.status != WorkforceStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Workforce must be approved (status=active) before executing",
        )

    run = ExecutionRun(
        workforce_config_id=config_id,
        company_id=company_id,
        status=ExecutionRunStatus.PENDING,
        trigger=trigger,
    )
    db.add(run)
    await db.flush()
    run_id = run.id
    await db.commit()

    background_tasks.add_task(
        _run_execution_background,
        execution_run_id=run_id,
        workforce_config_id=config_id,
        company_id=company_id,
    )

    logger.info("workforce_execution_triggered", run_id=str(run_id), trigger=trigger)
    return {"execution_run_id": str(run_id), "status": "pending"}


@router.get("/{company_id}/workforce/runs/list")
async def list_execution_runs(
    company_id: UUID,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> list[ExecutionRunResponse]:
    """List recent execution runs for a company."""
    result = await db.execute(
        select(ExecutionRun)
        .where(ExecutionRun.company_id == company_id)
        .order_by(desc(ExecutionRun.started_at))
        .limit(limit)
    )
    runs = result.scalars().all()
    return [_run_to_response(r) for r in runs]


@router.get("/{company_id}/workforce/runs/{run_id}")
async def get_execution_run(
    company_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ExecutionRunDetailResponse:
    """Get full detail of one execution run including step log and metrics."""
    run = await db.get(ExecutionRun, run_id)
    if not run or str(run.company_id) != str(company_id):
        raise HTTPException(status_code=404, detail="Execution run not found")

    # Load metrics
    metrics_result = await db.execute(
        select(ExecutionMetric)
        .where(ExecutionMetric.execution_run_id == run_id)
        .order_by(ExecutionMetric.captured_at)
    )
    metrics = metrics_result.scalars().all()
    metrics_data = [
        {
            "metric_name": m.metric_name,
            "value": m.value,
            "unit": m.unit,
            "source": m.metric_source,
            "step_name": m.step_name,
            "captured_at": m.captured_at.isoformat(),
        }
        for m in metrics
    ]

    base = _run_to_response(run)
    return ExecutionRunDetailResponse(
        **base.model_dump(),
        execution_log=run.execution_log or [],
        metrics=metrics_data,
    )


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

@router.get("/{company_id}/workforce/metrics")
async def get_workforce_metrics(
    company_id: UUID,
    metric_name: str | None = Query(default=None),
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_db_session),
) -> list[MetricSeriesResponse]:
    """Return time-series KPI data for charting. Aggregated by day."""
    since = datetime.now(UTC) - timedelta(days=days)

    query = (
        select(ExecutionMetric)
        .where(ExecutionMetric.company_id == company_id)
        .where(ExecutionMetric.captured_at >= since)
        .order_by(ExecutionMetric.captured_at)
    )
    if metric_name:
        query = query.where(ExecutionMetric.metric_name == metric_name)

    result = await db.execute(query)
    metrics = result.scalars().all()

    # Group by metric_name
    series: dict[str, list] = {}
    sources: dict[str, str] = {}
    units: dict[str, str] = {}
    for m in metrics:
        series.setdefault(m.metric_name, []).append(m)
        sources[m.metric_name] = m.metric_source
        units[m.metric_name] = m.unit or "count"

    return [
        MetricSeriesResponse(
            metric_name=name,
            source=sources.get(name, "internal"),
            points=[
                MetricPoint(
                    date=m.captured_at.strftime("%Y-%m-%d"),
                    value=m.value,
                    unit=units.get(name, "count"),
                )
                for m in points
            ],
        )
        for name, points in series.items()
    ]


# ---------------------------------------------------------------------------
# Background task helpers
# ---------------------------------------------------------------------------

async def _run_workforce_design(
    config_id: UUID,
    analysis_id: UUID,
    _company_id: UUID,
) -> None:
    """Background: run WorkforceArchitectAgent and save result to DB."""
    from agents.workforce_architect.src import WorkforceArchitectAgent
    from packages.database.src.models import Analysis
    from packages.database.src.session import async_session_factory

    async with async_session_factory() as db:
        config = await db.get(WorkforceConfig, config_id)
        analysis = await db.get(Analysis, analysis_id)
        if not config or not analysis:
            return

        try:
            agent = WorkforceArchitectAgent()
            result = await agent.run(
                task="Design a Digital Workforce for this company",
                context={
                    "company_name": analysis.executive_summary[:100] if analysis.executive_summary else "",
                    "key_recommendations": analysis.key_recommendations or [],
                    "customer_personas": analysis.customer_personas or [],
                    "leads": analysis.leads or [],
                    "campaign_brief": analysis.campaign_brief or {},
                },
            )

            definition = result.model_dump() if hasattr(result, "model_dump") else {}
            config.definition = definition
            config.executive_summary = definition.get("executive_summary", "")
            config.estimated_weekly_hours_saved = definition.get("estimated_weekly_hours_saved", 0.0)
            config.estimated_monthly_revenue_impact_sgd = definition.get("estimated_monthly_revenue_impact_sgd", 0.0)
            config.agent_count = len(definition.get("agent_roster", []))
            config.updated_at = datetime.now(UTC)
            await db.commit()

            logger.info("workforce_design_complete", config_id=str(config_id))

        except Exception as e:
            logger.error("workforce_design_failed", config_id=str(config_id), error=str(e))
            config.definition = {"error": str(e)}
            config.status = WorkforceStatus.FAILED
            config.updated_at = datetime.now(UTC)
            await db.commit()


async def _run_execution_background(
    execution_run_id: UUID,
    workforce_config_id: UUID,
    company_id: UUID,
) -> None:
    """Wrapper to call the executor service from background task."""
    from services.gateway.src.services.workforce_executor import run_execution
    await run_execution(
        execution_run_id=execution_run_id,
        workforce_config_id=workforce_config_id,
        company_id=company_id,
    )
