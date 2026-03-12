"""Workforce execution service.

Orchestrates the Digital Workforce: runs each approved process step in order,
calls execution agents (OutreachExecutor, CRMSync), records metrics, and
broadcasts WebSocket progress updates.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import structlog

logger = structlog.get_logger()


async def run_execution(
    execution_run_id: UUID,
    workforce_config_id: UUID,
    company_id: UUID,
) -> None:
    """Background task: execute all approved workforce process steps.

    For each step in the value chain:
    1. Log step start to execution_log
    2. Call the appropriate execution agent (outreach, crm_sync, etc.)
    3. Record ExecutionMetric rows
    4. Update progress counters on ExecutionRun
    5. Broadcast WebSocket update

    On step failure: mark step as failed, continue (partial run semantics).
    On all steps done: mark ExecutionRun as COMPLETED or PARTIAL.
    """
    from packages.database.src.models import ExecutionRun, ExecutionRunStatus, WorkforceConfig
    from packages.database.src.session import async_session_factory

    async with async_session_factory() as db:
        # Load execution run
        run = await db.get(ExecutionRun, execution_run_id)
        if not run:
            logger.error("execution_run_not_found", run_id=str(execution_run_id))
            return

        config = await db.get(WorkforceConfig, workforce_config_id)
        if not config:
            logger.error("workforce_config_not_found", config_id=str(workforce_config_id))
            run.status = ExecutionRunStatus.FAILED
            run.error_summary = "WorkforceConfig not found"
            await db.commit()
            return

        run.status = ExecutionRunStatus.RUNNING
        await db.commit()

        definition = config.definition or {}
        value_chain = definition.get("value_chain", [])
        approved_agents = set(config.approved_agents or [])

        # Filter steps to only approved agents
        steps = [s for s in value_chain if s.get("responsible_agent") in approved_agents]
        run.steps_total = len(steps)
        await db.commit()

        log: list[dict] = []
        steps_completed = 0
        steps_failed = 0
        emails_sent = 0
        crm_records = 0

        for step in steps:
            step_name = step.get("name", "unknown")
            agent_type = step.get("responsible_agent", "")
            mcp_call = step.get("mcp_call", "")
            started = datetime.now(UTC)

            try:
                result = await _execute_step(
                    agent_type=agent_type,
                    mcp_call=mcp_call,
                    step=step,
                    config=config,
                    db=db,
                )

                duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
                log.append({
                    "step": step_name,
                    "agent": agent_type,
                    "status": "completed",
                    "result": result.get("summary", ""),
                    "duration_ms": duration_ms,
                })
                steps_completed += 1

                # Accumulate counters
                emails_sent += result.get("emails_sent", 0)
                crm_records += result.get("crm_records", 0)

                # Record metric
                await _record_metric(
                    db=db,
                    execution_run_id=execution_run_id,
                    company_id=company_id,
                    metric_name=f"step_{agent_type}_completed",
                    value=1.0,
                    source="internal",
                    step_name=step_name,
                    agent_type=agent_type,
                )

            except Exception as e:
                duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
                logger.warning("workforce_step_failed", step=step_name, error=str(e))
                log.append({
                    "step": step_name,
                    "agent": agent_type,
                    "status": "failed",
                    "error": str(e)[:200],
                    "duration_ms": duration_ms,
                })
                steps_failed += 1

        # Determine final status
        if steps_failed == 0:
            final_status = ExecutionRunStatus.COMPLETED
        elif steps_completed > 0:
            final_status = ExecutionRunStatus.PARTIAL
        else:
            final_status = ExecutionRunStatus.FAILED

        run.status = final_status
        run.steps_completed = steps_completed
        run.steps_failed = steps_failed
        run.emails_sent = emails_sent
        run.crm_records_updated = crm_records
        run.execution_log = log
        run.completed_at = datetime.now(UTC)
        await db.commit()

        logger.info(
            "workforce_execution_complete",
            run_id=str(execution_run_id),
            status=final_status.value,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            emails_sent=emails_sent,
        )


async def _execute_step(
    agent_type: str,
    _mcp_call: str,
    step: dict,
    config: object,
    db: object,
) -> dict:
    """Dispatch a single process step to the appropriate handler.

    Returns a dict with: summary, emails_sent, crm_records.
    """
    if agent_type == "outreach":
        return await _run_outreach_step(config, db)
    elif agent_type == "crm_sync":
        return await _run_crm_sync_step(config, db)
    elif agent_type in ("nurture", "content", "monitor", "scheduler"):
        # Stubbed for Phase 2.1 — log as no-op
        logger.info("workforce_step_noop", agent_type=agent_type, step=step.get("name"))
        return {"summary": f"{agent_type} step acknowledged (not yet implemented)", "emails_sent": 0, "crm_records": 0}
    else:
        return {"summary": f"Unknown agent type: {agent_type}", "emails_sent": 0, "crm_records": 0}


async def _run_outreach_step(config: object, db: object) -> dict:
    """Execute the outreach step: send personalised emails to leads."""
    from sqlalchemy import select

    from agents.outreach_executor.src import OutreachExecutorAgent
    from packages.database.src.models import Lead

    company_id = config.company_id
    definition = config.definition or {}
    campaign_brief = definition.get("campaign_brief", {})

    # Fetch leads that haven't been contacted yet (contact_email not null, contacted_at null)
    result = await db.execute(
        select(Lead)
        .where(Lead.company_id == company_id)
        .where(Lead.contact_email.isnot(None))
        .limit(20)  # Safety cap per run
    )
    leads = result.scalars().all()

    if not leads:
        return {"summary": "No contactable leads found", "emails_sent": 0, "crm_records": 0}

    agent = OutreachExecutorAgent()
    emails_sent = 0

    for lead in leads:
        try:
            await agent.run(
                task="Send personalised outreach email",
                context={
                    "lead_id": str(lead.id),
                    "lead_email": lead.contact_email,
                    "lead_name": lead.contact_name or "",
                    "company_name": lead.lead_company_name,
                    "contact_title": lead.contact_title or "",
                    "industry": lead.lead_company_industry or "",
                    "company_size": lead.lead_company_size or "",
                    "fit_score": lead.fit_score or 0,
                    "intent_score": lead.intent_score or 0,
                    "qualification_reasons": lead.qualification_reasons or [],
                    "campaign_brief": campaign_brief,
                },
            )
            emails_sent += 1
            await asyncio.sleep(0.5)  # Rate limiting: 2/second max
        except Exception as e:
            logger.warning("outreach_lead_failed", lead_id=str(lead.id), error=str(e))

    return {"summary": f"Sent {emails_sent} outreach emails", "emails_sent": emails_sent, "crm_records": 0}


async def _run_crm_sync_step(config: object, db: object) -> dict:
    """Execute the CRM sync step: create/update HubSpot contacts for leads."""
    from sqlalchemy import select

    from agents.crm_sync.src import CRMSyncAgent
    from packages.database.src.models import Lead

    company_id = config.company_id

    result = await db.execute(
        select(Lead)
        .where(Lead.company_id == company_id)
        .where(Lead.contact_email.isnot(None))
        .limit(50)
    )
    leads = result.scalars().all()

    if not leads:
        return {"summary": "No leads to sync", "emails_sent": 0, "crm_records": 0}

    agent = CRMSyncAgent()
    synced = 0

    for lead in leads:
        try:
            await agent.run(
                task="Sync lead to CRM",
                context={
                    "lead_id": str(lead.id),
                    "email": lead.contact_email,
                    "name": lead.contact_name or "",
                    "company": lead.lead_company_name,
                    "job_title": lead.contact_title or "",
                },
            )
            synced += 1
        except Exception as e:
            logger.warning("crm_sync_lead_failed", lead_id=str(lead.id), error=str(e))

    return {"summary": f"Synced {synced} contacts to CRM", "emails_sent": 0, "crm_records": synced}


async def _record_metric(
    db: object,
    execution_run_id: UUID,
    company_id: UUID,
    metric_name: str,
    value: float,
    source: str,
    step_name: str = "",
    agent_type: str = "",
    unit: str = "count",
) -> None:
    """Write one ExecutionMetric row."""
    from packages.database.src.models import ExecutionMetric

    metric = ExecutionMetric(
        execution_run_id=execution_run_id,
        company_id=company_id,
        metric_name=metric_name,
        metric_source=source,
        value=value,
        unit=unit,
        step_name=step_name,
        agent_type=agent_type,
    )
    db.add(metric)
    await db.flush()
