"""Analysis orchestration endpoints with database persistence.

Features A2A (Agent-to-Agent) communication for dynamic collaboration:
1. CompanyEnricherAgent runs FIRST to analyze user's company website
2. It publishes discoveries to the AgentBus
3. Other agents subscribe and react to these discoveries
4. Agents can publish their own discoveries for cross-agent insights
"""

from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import agents
from agents.campaign_architect.src import CampaignArchitectAgent
from agents.company_enricher.src import CompanyEnricherAgent
from agents.competitor_analyst.src import CompetitorAnalystAgent
from agents.customer_profiler.src import CustomerProfilerAgent
from agents.lead_hunter.src import LeadHunterAgent
from agents.market_intelligence.src import MarketIntelligenceAgent
from packages.core.src.agent_bus import (
    AgentMessage,
    DiscoveryType,
    get_agent_bus,
)
from packages.core.src.errors import AgentError, MaxIterationsExceededError
from packages.core.src.types import (
    CampaignBrief,
    CompetitorAnalysis,
    CustomerPersona,
    GTMAnalysisResult,
    IndustryVertical,
    LeadProfile,
    MarketInsight,
)
from packages.database.src.models import (
    Analysis,
    CampaignStatus,
    Company,
    Lead,
    SignalEvent,
    SignalType,
    SignalUrgency,
)
from packages.database.src.models import AnalysisStatus as DBAnalysisStatus
from packages.database.src.models import (
    Campaign as DBCampaign,
)
from packages.database.src.models import MarketInsight as DBMarketInsight
from packages.database.src.session import async_session_factory, get_db_session

from ..auth.dependencies import get_optional_user
from ..auth.models import User
from ..middleware.rate_limit import analysis_limit
from ..services import (
    ClarificationResponse,
    GTMClarificationService,
    TaskDecompositionService,
)
from .websocket import send_agent_update

router = APIRouter()
logger = structlog.get_logger()


def _build_context_string(context_sources: list[dict] | None) -> str:
    """Join all company context sources into a single additional_context string for agents."""
    if not context_sources:
        return ""
    parts = []
    for src in context_sources:
        label = src.get("name") or src.get("type", "source")
        parts.append(f"=== {label} ===\n{src.get('text', '')}")
    return "\n\n".join(parts)


def _make_source_entry(source_type: str, name: str, text: str) -> dict:
    """Create a context_sources entry."""
    from datetime import UTC, datetime
    return {
        "type": source_type,
        "name": name,
        "text": text,
        "chars": len(text),
        "added_at": datetime.now(UTC).isoformat(),
    }


class AnalysisRequest(BaseModel):
    """Request for GTM analysis."""

    company_name: str = Field(..., min_length=1)
    website: str | None = Field(default=None, description="Company website URL for enrichment")
    description: str = Field(default="")
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    goals: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    value_proposition: str | None = Field(default=None)
    # Analysis options
    include_market_research: bool = Field(default=True)
    include_competitor_analysis: bool = Field(default=True)
    include_customer_profiling: bool = Field(default=True)
    include_lead_generation: bool = Field(default=True)
    include_campaign_planning: bool = Field(default=True)
    lead_count: int = Field(default=25, ge=1, le=100)
    # Optional: link to existing company
    company_id: UUID | None = Field(default=None)
    # Optional: clarification responses to enrich context
    clarification_responses: list[ClarificationResponse] = Field(default_factory=list)
    # Optional: raw document text from uploaded corporate profile / business plan
    additional_context: str | None = Field(default=None, description="Raw text from uploaded document for agent context")


class ClarifyRequest(BaseModel):
    """Request to generate clarifying questions."""

    company_name: str = Field(..., min_length=1)
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    goals: list[str] = Field(default_factory=list)
    existing_context: dict = Field(default_factory=dict)


class DecomposeRequest(BaseModel):
    """Request to decompose analysis into a task dependency graph."""

    include_market_research: bool = Field(default=True)
    include_competitor_analysis: bool = Field(default=True)
    include_customer_profiling: bool = Field(default=True)
    include_lead_generation: bool = Field(default=True)
    include_campaign_planning: bool = Field(default=True)
    include_enrichment: bool = Field(default=True)
    clarification_responses: list[ClarificationResponse] = Field(default_factory=list)


class AnalysisStatusResponse(BaseModel):
    """Status of an analysis."""

    analysis_id: UUID
    company_id: UUID | None = None
    status: str  # pending, running, completed, failed
    progress: float = 0.0  # 0-1
    current_agent: str | None = None
    completed_agents: list[str] = []
    error: str | None = None


class AnalysisResponse(BaseModel):
    """Response from completed analysis."""

    analysis_id: UUID
    status: str
    result: GTMAnalysisResult | None = None
    processing_time_seconds: float = 0.0


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/clarify")
async def generate_clarifications(
    request: ClarifyRequest,
) -> dict:
    """Generate clarifying questions before starting analysis.

    Call this first to get tailored questions, then submit answers with the
    /start request as clarification_responses.
    """
    svc = GTMClarificationService()
    session = svc.generate_questions(
        company_name=request.company_name,
        industry=request.industry,
        goals=request.goals,
        existing_context=request.existing_context,
    )
    return {
        "company_name": session.company_name,
        "industry": session.industry.value,
        "readiness_score": session.readiness_score,
        "questions": [q.model_dump() for q in session.questions],
        "total_questions": len(session.questions),
        "required_count": sum(1 for q in session.questions if q.required),
    }


@router.post("/decompose")
async def decompose_analysis(
    request: DecomposeRequest,
) -> dict:
    """Decompose analysis into a dependency graph of agent tasks.

    Returns execution waves showing which agents run in parallel and which
    must wait for others. Useful for UI progress visualization.
    """
    clarification_context = {}
    if request.clarification_responses:
        svc = GTMClarificationService()
        clarification_context = svc.responses_to_context(request.clarification_responses)

    decomp_svc = TaskDecompositionService()
    graph = decomp_svc.decompose(
        include_enrichment=request.include_enrichment,
        include_market=request.include_market_research,
        include_competitor=request.include_competitor_analysis,
        include_profiling=request.include_customer_profiling,
        include_leads=request.include_lead_generation,
        include_campaign=request.include_campaign_planning,
        clarification_context=clarification_context,
    )
    return graph.to_dict()


@router.post("/start")
@analysis_limit()  # Tier-based limits: FREE=3/day, TIER1=20/day, TIER2=100/day
async def start_analysis(
    request: Request,
    analysis_request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    _current_user: User | None = Depends(get_optional_user),
) -> AnalysisStatusResponse:
    """Start a new GTM analysis (runs in background)."""
    # Get user from auth middleware (may be None for unauthenticated)
    user = getattr(request.state, "user", None)
    user_id = user.id if user else None

    # Create or get company — deduplicate by name + owner
    company_id = analysis_request.company_id
    if not company_id:
        # Check for existing company with same name (owned by same user or unowned)
        _dedup_filters = [Company.name == analysis_request.company_name]
        if user_id:
            _dedup_filters.append(Company.owner_id == user_id)
        else:
            _dedup_filters.append(Company.owner_id.is_(None))
        _existing_co = await db.scalar(
            select(Company).where(*_dedup_filters).order_by(Company.created_at.desc()).limit(1)
        )
        if _existing_co:
            company_id = _existing_co.id
            # Update fields with latest input
            _existing_co.description = analysis_request.description or _existing_co.description
            _existing_co.industry = analysis_request.industry.value
            _existing_co.website = analysis_request.website or _existing_co.website
            _existing_co.goals = analysis_request.goals or _existing_co.goals
            _existing_co.challenges = analysis_request.challenges or _existing_co.challenges
            _existing_co.competitors = analysis_request.competitors or _existing_co.competitors
            _existing_co.target_markets = analysis_request.target_markets or _existing_co.target_markets
            _existing_co.value_proposition = analysis_request.value_proposition or _existing_co.value_proposition
            if analysis_request.additional_context:
                sources: list[dict] = list(_existing_co.context_sources or [])
                new_entry = _make_source_entry("document", "uploaded_document", analysis_request.additional_context)
                sources = [s for s in sources if not (s.get("type") == "document" and s.get("name") == "uploaded_document")]
                sources.append(new_entry)
                _existing_co.context_sources = sources
            await db.flush()

    if not company_id:
        company = Company(
            name=analysis_request.company_name,
            website=analysis_request.website,
            description=analysis_request.description,
            industry=analysis_request.industry.value,
            goals=analysis_request.goals,
            challenges=analysis_request.challenges,
            competitors=analysis_request.competitors,
            target_markets=analysis_request.target_markets,
            value_proposition=analysis_request.value_proposition,
            owner_id=user_id,
            context_sources=(
                [_make_source_entry("document", "uploaded_document", analysis_request.additional_context)]
                if analysis_request.additional_context else []
            ),
        )
        db.add(company)
        await db.flush()
        company_id = company.id
    elif analysis_request.additional_context:
        # Existing company — append new document source if a new document was uploaded
        existing = await db.get(Company, company_id)
        if existing:
            sources: list[dict] = list(existing.context_sources or [])
            # Replace any existing "document" entry with the same name, or append
            new_entry = _make_source_entry("document", "uploaded_document", analysis_request.additional_context)
            sources = [s for s in sources if not (s.get("type") == "document" and s.get("name") == "uploaded_document")]
            sources.append(new_entry)
            existing.context_sources = sources

    # Create analysis record with user_id if authenticated
    analysis = Analysis(
        company_id=company_id,
        user_id=user_id,  # Set user_id if authenticated, None otherwise
        status=DBAnalysisStatus.PENDING,
        progress=0,
        completed_agents=[],
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    # Start background task
    background_tasks.add_task(run_analysis, analysis.id, analysis_request)

    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        company_id=company_id,
        status="pending",
        progress=0.0,
    )


@router.get("/{analysis_id}/status")
async def get_analysis_status(
    analysis_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    _current_user: User | None = Depends(get_optional_user),
) -> AnalysisStatusResponse:
    """Get the status of an analysis."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check ownership: user can only access their own analyses or public (no user_id) analyses
    user = getattr(request.state, "user", None)
    if analysis.user_id is not None:
        # This analysis has an owner
        if user is None:
            raise HTTPException(
                status_code=403, detail="Authentication required to access this analysis"
            )
        if analysis.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

    return AnalysisStatusResponse(
        analysis_id=analysis_id,
        status=analysis.status.value if analysis.status else "pending",
        progress=analysis.progress / 100.0 if analysis.progress else 0.0,
        current_agent=analysis.current_agent,
        completed_agents=analysis.completed_agents or [],
        error=analysis.error,
    )


@router.get("/{analysis_id}/result")
async def get_analysis_result(
    analysis_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    _current_user: User | None = Depends(get_optional_user),
) -> AnalysisResponse:
    """Get the result of a completed analysis."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check ownership: user can only access their own analyses or public (no user_id) analyses
    user = getattr(request.state, "user", None)
    if analysis.user_id is not None:
        if user is None:
            raise HTTPException(
                status_code=403, detail="Authentication required to access this analysis"
            )
        if analysis.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

    if analysis.status != DBAnalysisStatus.COMPLETED:
        return AnalysisResponse(
            analysis_id=analysis_id,
            status=analysis.status.value if analysis.status else "pending",
            result=None,
        )

    # Reconstruct GTMAnalysisResult from database fields
    result = GTMAnalysisResult(
        id=analysis_id,
        company_id=analysis.company_id,
        executive_summary=analysis.executive_summary or "",
        key_recommendations=analysis.key_recommendations or [],
        market_insights=[MarketInsight(**m) for m in (analysis.market_insights or [])],
        competitor_analysis=[
            CompetitorAnalysis(**c) if isinstance(c, dict) else c
            for c in (analysis.competitor_analysis or [])
        ],
        customer_personas=[
            CustomerPersona(**p) if isinstance(p, dict) else p
            for p in (analysis.customer_personas or [])
        ],
        leads=[LeadProfile(**lead) for lead in (analysis.leads or [])],
        campaign_brief=CampaignBrief(**analysis.campaign_brief) if isinstance(analysis.campaign_brief, dict) else analysis.campaign_brief,
        outreach_sequences=analysis.outreach_sequences or [],
        market_sizing=getattr(analysis, "market_sizing", None),
        agents_used=analysis.agents_used or [],
        total_confidence=analysis.total_confidence or 0.0,
        processing_time_seconds=analysis.processing_time_seconds or 0.0,
    )

    return AnalysisResponse(
        analysis_id=analysis_id,
        status="completed",
        result=result,
        processing_time_seconds=analysis.processing_time_seconds or 0.0,
    )


@router.post("/quick")
@analysis_limit()  # Uses same tier-based limits as full analysis
async def quick_analysis(
    request: Request,
    analysis_request: AnalysisRequest,
    db: AsyncSession = Depends(get_db_session),
    _current_user: User | None = Depends(get_optional_user),
) -> AnalysisResponse:
    """Run a quick synchronous analysis (for testing/demo)."""
    # Get user from auth middleware (may be None for unauthenticated)
    user = getattr(request.state, "user", None)
    user_id = user.id if user else None

    analysis_id = uuid4()
    start_time = time.time()

    try:
        result = await run_analysis_sync(analysis_request)
        processing_time = time.time() - start_time

        # Save to database
        company = Company(
            name=analysis_request.company_name,
            website=analysis_request.website,
            description=analysis_request.description,
            industry=analysis_request.industry.value,
            owner_id=user_id,
            context_sources=(
                [_make_source_entry("document", "uploaded_document", analysis_request.additional_context)]
                if analysis_request.additional_context else []
            ),
        )
        db.add(company)
        await db.flush()

        analysis = Analysis(
            id=analysis_id,
            company_id=company.id,
            user_id=user_id,  # Set user_id if authenticated
            status=DBAnalysisStatus.COMPLETED,
            progress=100,
            completed_agents=result.agents_used,
            executive_summary=result.executive_summary,
            leads=[lead.model_dump(mode="json") for lead in result.leads] if result.leads else [],
            total_confidence=result.total_confidence,
            processing_time_seconds=processing_time,
        )
        db.add(analysis)
        await db.commit()

        return AnalysisResponse(
            analysis_id=analysis_id,
            status="completed",
            result=result,
            processing_time_seconds=processing_time,
        )

    except Exception as e:
        logger.error("analysis_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again.")


@router.get("/")
async def list_analyses(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    limit: int = 20,
    _current_user: User | None = Depends(get_optional_user),
) -> list[AnalysisStatusResponse]:
    """List recent analyses.

    Returns only analyses owned by the current user or public (no user_id) analyses.
    """
    user = getattr(request.state, "user", None)

    # Build query with ownership filter
    from sqlalchemy import or_

    if user:
        # Authenticated: show user's analyses and public analyses
        query = select(Analysis).where(or_(Analysis.user_id == user.id, Analysis.user_id.is_(None)))
    else:
        # Unauthenticated: only show public analyses
        query = select(Analysis).where(Analysis.user_id.is_(None))

    result = await db.execute(query.order_by(Analysis.created_at.desc()).limit(limit))
    analyses = result.scalars().all()

    return [
        AnalysisStatusResponse(
            analysis_id=a.id,
            status=a.status.value if a.status else "pending",
            progress=a.progress / 100.0 if a.progress else 0.0,
            current_agent=a.current_agent,
            completed_agents=a.completed_agents or [],
            error=a.error,
        )
        for a in analyses
    ]


# ============================================================================
# Background Task
# ============================================================================


async def run_analysis(analysis_id: UUID, request: AnalysisRequest) -> None:
    """Run the full GTM analysis (background task) with database persistence.

    A2A Flow:
    1. CompanyEnricherAgent runs first (if website provided) to enrich company data
    2. Discoveries are published to AgentBus
    3. Other agents subscribe and use these discoveries
    4. Cross-agent collaboration happens via the bus
    """
    async with async_session_factory() as db:
        analysis = await db.get(Analysis, analysis_id)
        if not analysis:
            logger.error("analysis_not_found", analysis_id=str(analysis_id))
            return

        analysis.status = DBAnalysisStatus.RUNNING
        await db.commit()

        # Wait briefly so the browser has time to establish the WebSocket before
        # we start firing events. BackgroundTasks run almost immediately after the
        # HTTP response is sent; the WS handshake needs ~100-500 ms.
        await asyncio.sleep(1.5)

        start_time = time.time()

        # Initialize AgentBus for this analysis
        agent_bus = get_agent_bus()
        agent_bus.clear_history(analysis_id)

        # Set up WebSocket broadcast for A2A messages
        async def broadcast_a2a_message(message: AgentMessage) -> None:
            await send_agent_update(
                analysis_id=analysis_id,
                update_type="a2a_message",
                agent_id=message.from_agent,
                message=message.title,
                result={
                    "discovery_type": message.discovery_type.value,
                    "to_agent": message.to_agent,
                    "content_keys": list(message.content.keys()),
                    "confidence": message.confidence,
                },
            )

        agent_bus.set_ws_broadcast(broadcast_a2a_message)

        try:
            # Build additional_context from persistent context_sources on the company.
            # If the request includes a new document, merge it into context_sources first.
            _company_for_ctx: Company | None = None
            if analysis.company_id:
                _company_for_ctx = await db.get(Company, analysis.company_id)

            if _company_for_ctx is not None and request.additional_context:
                # Merge new document into company's context_sources
                sources: list[dict] = list(_company_for_ctx.context_sources or [])
                new_entry = _make_source_entry("document", "uploaded_document", request.additional_context)
                sources = [s for s in sources if not (s.get("type") == "document" and s.get("name") == "uploaded_document")]
                sources.append(new_entry)
                _company_for_ctx.context_sources = sources
                await db.commit()

            additional_context = _build_context_string(
                _company_for_ctx.context_sources if _company_for_ctx else None
            ) or request.additional_context

            # Build context
            context = {
                "analysis_id": analysis_id,
                "company_name": request.company_name,
                "website": request.website,
                "description": request.description,
                "industry": request.industry.value,
                "goals": request.goals,
                "current_challenges": request.challenges,
                "known_competitors": request.competitors,
                "target_markets": request.target_markets or ["Singapore"],
                "value_proposition": request.value_proposition,
                "additional_context": additional_context,
            }

            # ── Pre-flight: ensure vertical intelligence report exists ──
            # Agents query VerticalIntelligenceReport via MCP during their runs.
            # If no report exists for this vertical, synthesize one now (fast,
            # deterministic — no LLM calls, just DB aggregation).
            try:
                from packages.core.src.vertical import detect_vertical_slug
                from packages.intelligence.src.vertical_synthesizer import (
                    VerticalIntelligenceSynthesizer,
                )

                _vi_text = f"{request.industry.value} {request.description} {request.value_proposition or ''}"
                _vi_slug = detect_vertical_slug(_vi_text)
                if _vi_slug:
                    async with async_session_factory() as _vi_db:
                        from packages.database.src.models import (
                            MarketVertical,
                            VerticalIntelligenceReport,
                        )
                        _vi_vert = await _vi_db.scalar(
                            select(MarketVertical).where(MarketVertical.slug == _vi_slug)
                        )
                        if _vi_vert:
                            _vi_report = await _vi_db.scalar(
                                select(VerticalIntelligenceReport).where(
                                    VerticalIntelligenceReport.vertical_id == _vi_vert.id,
                                    VerticalIntelligenceReport.is_current.is_(True),
                                )
                            )
                            if not _vi_report:
                                logger.info(
                                    "vi_preflight_synthesizing",
                                    vertical=_vi_slug,
                                    reason="no current report in DB",
                                )
                                synth = VerticalIntelligenceSynthesizer(_vi_db)
                                await synth.synthesize_vertical(_vi_slug)
                                await _vi_db.commit()
                    context["_detected_vertical"] = _vi_slug
                    # Override the generic industry with the more specific vertical
                    # so all agents detect the right vertical from their context.
                    # E.g., "professional_services" → "marketing_comms" when the
                    # description mentions marketing campaigns and GTM.
                    if _vi_slug != request.industry.value:
                        context["industry"] = _vi_slug
                        logger.info(
                            "vi_vertical_override",
                            original=request.industry.value,
                            detected=_vi_slug,
                        )
            except Exception as _vi_err:
                logger.debug("vi_preflight_failed", error=str(_vi_err))

            result = GTMAnalysisResult(
                id=analysis_id,
                company_id=analysis.company_id,
            )

            # Track decision attribution
            decision_attribution = {
                "algorithm_decisions": 0,
                "llm_decisions": 0,
                "tool_calls": 0,
            }

            # Calculate total steps
            include_company_enrichment = bool(request.website or additional_context)
            total_steps = sum(
                [
                    include_company_enrichment,
                    request.include_market_research,
                    request.include_competitor_analysis,
                    request.include_customer_profiling,
                    request.include_lead_generation,
                    request.include_campaign_planning,
                ]
            )
            step = 0
            completed_agents: list[str] = []

            # Send analysis started
            await send_agent_update(
                analysis_id=analysis_id,
                update_type="analysis_started",
                message=f"Starting GTM analysis for {request.company_name}",
            )

            # Helper to update progress
            async def update_progress(agent_id: str, progress_pct: int) -> None:
                analysis.current_agent = agent_id
                analysis.progress = progress_pct
                # Use list() copy — SQLAlchemy JSON column may not detect dirty
                # when the same list object is re-assigned after in-place mutations.
                analysis.completed_agents = list(completed_agents)
                try:
                    await db.commit()
                except Exception as _commit_err:
                    # Non-fatal: progress update failed, but the analysis continues.
                    # The final commit will persist the completed state.
                    logger.warning("progress_commit_failed", agent=agent_id, error=str(_commit_err))
                    await db.rollback()

            # =====================================================================
            # STEP 0: Company Enrichment
            # =====================================================================
            if include_company_enrichment:
                agent_id = "company-enricher"
                await update_progress(agent_id, int((step / total_steps) * 100))

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id=agent_id,
                    agent_name="Company Enricher",
                    status="thinking",
                    message=f"Analyzing {request.website or 'uploaded document'}...",
                )

                enricher = CompanyEnricherAgent(agent_bus=agent_bus, analysis_id=analysis_id)
                enrichment_result = None
                try:
                    async with asyncio.timeout(90):
                        enrichment_result = await enricher.enrich_company(
                            company_name=request.company_name,
                            website=request.website,
                            industry=request.industry,
                            description=request.description,
                            additional_context=additional_context,
                            analysis_id=analysis_id,
                        )
                except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
                    logger.warning(
                        "agent_failed",
                        agent=agent_id,
                        error=str(e),
                        analysis_id=str(analysis_id),
                    )

                # Update context with enriched data
                if enrichment_result:
                    if enrichment_result.description:
                        context["description"] = enrichment_result.description
                    if enrichment_result.value_propositions:
                        context["value_proposition"] = "; ".join(
                            enrichment_result.value_propositions
                        )
                    if enrichment_result.mentioned_competitors:
                        existing = set(context.get("known_competitors", []))
                        existing.update(enrichment_result.mentioned_competitors)
                        context["known_competitors"] = list(existing)
                    if enrichment_result.target_markets:
                        context["target_markets"] = enrichment_result.target_markets

                    # Persist website scrape to context_sources so future re-runs have it
                    if enrichment_result.raw_website_context and _company_for_ctx is not None:
                        async with async_session_factory() as persist_db:
                            company_to_update = await persist_db.get(Company, analysis.company_id)
                            if company_to_update is not None:
                                sources = list(company_to_update.context_sources or [])
                                website_name = request.website or "website_scrape"
                                sources = [s for s in sources if not (s.get("type") == "website" and s.get("name") == website_name)]
                                sources.append(_make_source_entry("website", website_name, enrichment_result.raw_website_context))
                                company_to_update.context_sources = sources
                                await persist_db.commit()
                        # Rebuild additional_context with website scrape now included
                        _company_for_ctx.context_sources = [s for s in (_company_for_ctx.context_sources or []) if s.get("type") != "website"]
                        _company_for_ctx.context_sources = (_company_for_ctx.context_sources or []) + [_make_source_entry("website", request.website or "website_scrape", enrichment_result.raw_website_context)]
                        additional_context = _build_context_string(_company_for_ctx.context_sources)
                        context["additional_context"] = additional_context

                completed_agents.append(agent_id)
                step += 1

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
                    agent_name="Company Enricher",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Enriched profile with {len(enrichment_result.products) if enrichment_result else 0} products",
                    result={
                        "products_count": len(enrichment_result.products) if enrichment_result else 0,
                        "competitors_discovered": len(enrichment_result.mentioned_competitors) if enrichment_result else 0,
                    },
                )

                await asyncio.sleep(0.1)

            # =====================================================================
            # WAVE 2: Market Intelligence + Competitor Analysis (truly independent)
            # CustomerProfiler is moved to WAVE 3 so it can read market/competitor
            # bus publications in its _plan() step (A2A data flow).
            # =====================================================================

            async def _run_market_intel() -> Any:
                if not request.include_market_research:
                    return None
                _mi = MarketIntelligenceAgent(agent_bus=agent_bus)
                try:
                    async with asyncio.timeout(90):
                        return await _mi.run(
                            f"Research {request.industry.value} market in Singapore for: {request.company_name}. {request.description}",
                            context=context,
                        )
                except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
                    logger.warning(
                        "agent_failed",
                        agent="market-intelligence",
                        error=str(e),
                        analysis_id=str(analysis_id),
                    )
                    return None

            async def _run_competitor_analyst() -> Any:
                if not request.include_competitor_analysis:
                    return None
                _competitors = context.get("known_competitors", [])[:5]
                _ca = CompetitorAnalystAgent(agent_bus=agent_bus, analysis_id=analysis_id)
                try:
                    async with asyncio.timeout(180):
                        return await _ca.run(
                            f"Analyze competitors for {request.company_name} in {request.industry.value}: {', '.join(_competitors)}",
                            context=context,
                        )
                except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
                    logger.warning(
                        "agent_failed",
                        agent="competitor-analyst",
                        error=str(e),
                        analysis_id=str(analysis_id),
                    )
                    return None

            async def _run_customer_profiler() -> Any:
                if not request.include_customer_profiling:
                    return None
                _cp = CustomerProfilerAgent(bus=agent_bus)
                try:
                    async with asyncio.timeout(90):
                        return await _cp.run(
                            f"Create ideal customer profiles for {request.company_name}",
                            context=context,
                        )
                except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
                    logger.warning(
                        "agent_failed",
                        agent="customer-profiler",
                        error=str(e),
                        analysis_id=str(analysis_id),
                    )
                    return None

            if any([
                request.include_market_research,
                request.include_competitor_analysis,
            ]):
                await update_progress("wave-2", int((step / total_steps) * 100))

            # Send agent_started updates sequentially BEFORE the parallel gather
            # so concurrent coroutines never write to the WebSocket simultaneously.
            if request.include_market_research:
                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id="market-intelligence",
                    agent_name="Market Intelligence",
                    status="thinking",
                    message=f"Researching {request.industry.value} market in Singapore...",
                )
            if request.include_competitor_analysis:
                _wave2_competitors = context.get("known_competitors", [])[:5]
                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id="competitor-analyst",
                    agent_name="Competitor Analyst",
                    status="thinking",
                    message=f"Analyzing {len(_wave2_competitors)} competitors...",
                )

            market_result, competitor_result = await asyncio.gather(
                _run_market_intel(),
                _run_competitor_analyst(),
            )

            # --- Process market_result ---
            if request.include_market_research:
                if market_result is None:
                    result.market_insights = []
                else:
                    # Build structured MarketInsight entries from the full agent output.
                    # The agent returns MarketIntelligenceOutput with rich fields;
                    # we must convert these into MarketInsight objects for the response model.
                    insights: list[MarketInsight] = []

                    # Always include any structured insights the agent produced
                    if hasattr(market_result, "insights"):
                        insights.extend(market_result.insights)

                    # Convert the full market analysis into a primary insight entry
                    key_findings: list[str] = []
                    implications: list[str] = []
                    recommendations: list[str] = []

                    if hasattr(market_result, "key_trends"):
                        for trend in market_result.key_trends[:5]:
                            evidence_str = f" (evidence: {', '.join(trend.evidence[:2])})" if trend.evidence else ""
                            key_findings.append(f"{trend.name}: {trend.description}{evidence_str}")

                    if hasattr(market_result, "opportunities"):
                        for opp in market_result.opportunities[:3]:
                            size_info = f" [{opp.market_size_estimate}]" if opp.market_size_estimate else ""
                            key_findings.append(f"Opportunity: {opp.title}{size_info} — {opp.description}")
                            recommendations.append(opp.recommended_action)

                    if hasattr(market_result, "implications_for_gtm"):
                        implications = market_result.implications_for_gtm[:5]

                    if hasattr(market_result, "threats"):
                        for threat in market_result.threats[:3]:
                            key_findings.append(f"Threat: {threat}")

                    # Add economic indicators as findings
                    if hasattr(market_result, "economic_indicators") and market_result.economic_indicators:
                        for ind in market_result.economic_indicators[:3]:
                            indicator = ind.get("indicator", "")
                            value = ind.get("value", "")
                            change = ind.get("change")
                            direction = ""
                            if change is not None:
                                direction = f" ({'▲' if change >= 0 else '▼'}{abs(change):.2f} vs prior)"
                            key_findings.append(f"Economic: {indicator} = {value}{direction}")

                    if key_findings or implications:
                        primary_insight = MarketInsight(
                            title=f"{request.industry.value.title()} Market Analysis — {request.company_name}",
                            summary=getattr(market_result, "market_summary", "Market analysis completed."),
                            category="market_analysis",
                            key_findings=key_findings,
                            implications=implications,
                            recommendations=recommendations,
                            sources=getattr(market_result, "sources", []),
                            confidence=getattr(market_result, "confidence", 0.5),
                            relevant_to_company=True,
                        )
                        insights.insert(0, primary_insight)

                    result.market_insights = insights

                    # Store the full raw market output for workspace pages that need it
                    if hasattr(market_result, "model_dump"):
                        result.market_sizing = {
                            "market_summary": getattr(market_result, "market_summary", ""),
                            "market_size": getattr(market_result, "market_size", None),
                            "growth_outlook": getattr(market_result, "growth_outlook", None),
                            "vertical_landscape": getattr(market_result, "vertical_landscape", None),
                            "vertical_benchmarks": getattr(market_result, "vertical_benchmarks", None),
                            "recent_news": getattr(market_result, "recent_news", []),
                            "economic_indicators": getattr(market_result, "economic_indicators", []),
                            "data_sources_used": getattr(market_result, "data_sources_used", []),
                            "is_live_data": getattr(market_result, "is_live_data", False),
                            "confidence": getattr(market_result, "confidence", 0.0),
                        }

                completed_agents.append("market-intelligence")
                step += 1
                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id="market-intelligence",
                    agent_name="Market Intelligence",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Found {len(result.market_insights)} market insights",
                    result={"insights_count": len(result.market_insights)},
                )
                decision_attribution["llm_decisions"] += 1

            # --- Process competitor_result ---
            if request.include_competitor_analysis:
                if hasattr(competitor_result, "competitors"):
                    result.competitor_analysis = competitor_result.competitors
                else:
                    result.competitor_analysis = []

                completed_agents.append("competitor-analyst")
                step += 1
                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id="competitor-analyst",
                    agent_name="Competitor Analyst",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Analyzed {len(result.competitor_analysis)} competitors",
                    result={"competitors_count": len(result.competitor_analysis)},
                )
                decision_attribution["llm_decisions"] += 1
                decision_attribution["tool_calls"] += 2

            # =====================================================================
            # WAVE 3: Customer Profiling
            # Runs AFTER wave-2 so _plan() can read market_result and
            # competitor_result bus publications (true A2A data flow).
            # =====================================================================
            profile_result: object = None  # default if wave-3 is skipped
            if request.include_customer_profiling:
                await update_progress("customer-profiler", int((step / total_steps) * 100))
                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id="customer-profiler",
                    agent_name="Customer Profiler",
                    status="thinking",
                    message="Developing ideal customer profiles from market intel...",
                )

                profile_result = await _run_customer_profiler()

                if hasattr(profile_result, "personas"):
                    result.customer_personas = profile_result.personas
                else:
                    result.customer_personas = []

                completed_agents.append("customer-profiler")
                step += 1
                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id="customer-profiler",
                    agent_name="Customer Profiler",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Created {len(result.customer_personas)} customer personas",
                    result={"personas_count": len(result.customer_personas)},
                )
                decision_attribution["llm_decisions"] += 1

            # =====================================================================
            # STEP 4: Lead Generation
            # =====================================================================
            lead_result: object = None
            campaign_result: object = None

            if request.include_lead_generation:
                agent_id = "lead-hunter"
                await update_progress(agent_id, int((step / total_steps) * 100))

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id=agent_id,
                    agent_name="Lead Hunter",
                    status="thinking",
                    message=f"Finding {request.lead_count} qualified leads...",
                )

                agent = LeadHunterAgent()
                # Harvest pain_points from CustomerProfiler personas so LeadHunter
                # can target companies experiencing those specific problems.
                persona_pain_points: list[str] = []
                for persona in result.customer_personas[:2]:
                    if hasattr(persona, "pain_points"):
                        persona_pain_points.extend(persona.pain_points[:3])
                lead_context = {
                    **context,
                    "target_industries": [request.industry.value],
                    "target_count": request.lead_count,
                    "target_locations": request.target_markets or ["Singapore"],
                    "pain_points": list(dict.fromkeys(persona_pain_points)),  # deduped
                    "personas": [p.model_dump(mode="json") for p in result.customer_personas[:2]]
                    if result.customer_personas
                    else [],
                }
                try:
                    # 3 min: 5 parallel Perplexity calls + enrichment of 25 companies
                    async with asyncio.timeout(180):
                        lead_result = await agent.run(
                            f"Find {request.lead_count} qualified leads for {request.company_name} in {request.industry.value}",
                            context=lead_context,
                        )
                except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
                    logger.warning("agent_failed", agent=agent_id, error=str(e), analysis_id=str(analysis_id))
                    lead_result = None

                if hasattr(lead_result, "qualified_leads"):
                    result.leads = lead_result.qualified_leads
                else:
                    result.leads = []

                if hasattr(lead_result, "algorithm_decisions"):
                    decision_attribution["algorithm_decisions"] += lead_result.algorithm_decisions
                if hasattr(lead_result, "llm_decisions"):
                    decision_attribution["llm_decisions"] += lead_result.llm_decisions

                completed_agents.append(agent_id)
                step += 1

                total_pipeline = sum(lead.overall_score * 15000 for lead in result.leads)

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
                    agent_name="Lead Hunter",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Found {len(result.leads)} qualified leads (SGD {total_pipeline:,.0f} pipeline)",
                    result={
                        "leads_count": len(result.leads),
                        "pipeline_value": total_pipeline,
                    },
                )

            # =====================================================================
            # STEP 5: Campaign Planning
            # =====================================================================
            if request.include_campaign_planning:
                agent_id = "campaign-architect"
                await update_progress(agent_id, int((step / total_steps) * 100))

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id=agent_id,
                    agent_name="Campaign Architect",
                    status="thinking",
                    message="Creating outreach campaigns...",
                )

                agent = CampaignArchitectAgent(bus=agent_bus)
                campaign_context = {
                    **context,
                    "leads": [lead.model_dump(mode="json") for lead in result.leads[:3]]
                    if result.leads
                    else [],
                    "personas": [p.model_dump(mode="json") for p in result.customer_personas[:2]]
                    if result.customer_personas
                    else [],
                    # company_name, description, value_proposition etc. already in context
                    # via **context spread above — no separate company_profile needed.
                }
                try:
                    async with asyncio.timeout(90):
                        campaign_result = await agent.run(
                            f"Create outreach campaign for {request.company_name}",
                            context=campaign_context,
                        )
                except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
                    logger.warning("agent_failed", agent=agent_id, error=str(e), analysis_id=str(analysis_id))
                    campaign_result = None

                if hasattr(campaign_result, "campaign_brief"):
                    result.campaign_brief = campaign_result.campaign_brief
                elif hasattr(campaign_result, "brief"):
                    result.campaign_brief = campaign_result.brief

                if campaign_result:
                    result.outreach_sequences = [
                        seq.model_dump() for seq in (campaign_result.outreach_sequences or [])
                    ]
                    result.success_metrics = campaign_result.success_metrics or []
                    result.compliance_flags = getattr(campaign_result, "compliance_flags", []) or []

                    # Enrich campaign_brief.email_templates with actual content from content_pieces
                    _content_pieces = getattr(campaign_result, "content_pieces", []) or []
                    if _content_pieces and result.campaign_brief:
                        _real_emails = [
                            f"Subject: {cp.title}\n\n{cp.content}"
                            for cp in _content_pieces
                            if cp.type == "email" and cp.content and len(cp.content) > 50
                        ]
                        if _real_emails:
                            result.campaign_brief.email_templates = _real_emails
                        _real_linkedin = [
                            cp.content
                            for cp in _content_pieces
                            if cp.type in ("linkedin", "linkedin_post") and cp.content
                        ]
                        if _real_linkedin:
                            result.campaign_brief.linkedin_posts = _real_linkedin

                completed_agents.append(agent_id)
                step += 1

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
                    agent_name="Campaign Architect",
                    status="complete",
                    progress=step / total_steps,
                    message="Created campaign templates and messaging",
                    result={"campaign_ready": result.campaign_brief is not None},
                )

                decision_attribution["llm_decisions"] += 1

            # =====================================================================
            # Pull GTM Strategist market sizing + sales motion from bus history
            # (published via MARKET_TREND discovery by GTMStrategistAgent._act())
            # =====================================================================
            market_trend_msgs = agent_bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.MARKET_TREND,
                limit=1,
            )
            if market_trend_msgs:
                mt = market_trend_msgs[0].content
                tam = mt.get("tam_sgd_estimate")
                sam = mt.get("sam_sgd_estimate")
                som = mt.get("som_sgd_estimate")
                primary_motion = mt.get("primary_motion")
                deal_size = mt.get("deal_size_sgd")
                if any([tam, sam, som]):
                    result.market_sizing = {
                        "tam_sgd_estimate": tam,
                        "sam_sgd_estimate": sam,
                        "som_sgd_estimate": som,
                        "tam_description": mt.get("tam_description", ""),
                        "sam_description": mt.get("sam_description", ""),
                        "som_description": mt.get("som_description", ""),
                        "assumptions": mt.get("assumptions", []),
                    }
                if any([primary_motion, deal_size]):
                    result.sales_motion = {
                        "primary_motion": primary_motion or "",
                        "deal_size_sgd": deal_size or "",
                        "sales_cycle_days": mt.get("sales_cycle_days"),
                        "key_objections": mt.get("key_objections", []),
                        "win_themes": mt.get("win_themes", []),
                        "recommended_first_90_days": mt.get("recommended_first_90_days", []),
                    }

            # =====================================================================
            # Finalize Results
            # =====================================================================
            result.agents_used = completed_agents
            result.processing_time_seconds = time.time() - start_time

            # Derive confidence from actual per-agent outcomes
            agent_scores: list[float] = []
            if market_result is not None and hasattr(market_result, "confidence"):
                agent_scores.append(market_result.confidence)
            elif request.include_market_research:
                agent_scores.append(0.0)  # agent failed

            if competitor_result is not None and hasattr(competitor_result, "confidence"):
                agent_scores.append(competitor_result.confidence)
            elif request.include_competitor_analysis:
                agent_scores.append(0.0)

            if profile_result is not None and hasattr(profile_result, "confidence"):
                agent_scores.append(profile_result.confidence)
            elif request.include_customer_profiling:
                agent_scores.append(0.0)

            if lead_result is not None and hasattr(lead_result, "confidence"):
                agent_scores.append(lead_result.confidence)
            elif request.include_lead_generation:
                agent_scores.append(0.0)

            if campaign_result is not None and hasattr(campaign_result, "confidence"):
                agent_scores.append(campaign_result.confidence)
            elif request.include_campaign_planning:
                agent_scores.append(0.0)

            result.total_confidence = sum(agent_scores) / len(agent_scores) if agent_scores else 0.0

            # ── Rich, data-driven executive summary ──────────────────────────────
            top_lead = max(result.leads, key=lambda lead: lead.overall_score) if result.leads else None
            top_insight = result.market_insights[0] if result.market_insights else None
            top_competitor = result.competitor_analysis[0] if result.competitor_analysis else None

            summary_parts: list[str] = []
            sector_label = request.industry.value.replace('_', ' ')
            if top_lead:
                if top_lead.contact_name:
                    title_part = f", {top_lead.contact_title}" if top_lead.contact_title else ""
                    contact_str = f" Contact: {top_lead.contact_name}{title_part}."
                else:
                    contact_str = ""
                summary_parts.append(
                    f"GTM analysis for {request.company_name} ({sector_label} sector):"
                    f" Identified {len(result.leads)} qualified leads — best fit is "
                    f"{top_lead.company_name} ({top_lead.overall_score:.0%} match).{contact_str}"
                )
            else:
                summary_parts.append(
                    f"GTM analysis for {request.company_name} in Singapore's {sector_label} sector complete."
                )
            if top_insight and top_insight.summary:
                summary_parts.append(top_insight.summary[:220].rstrip(".") + ".")
            if top_competitor and top_competitor.weaknesses:
                weakness_short = top_competitor.weaknesses[0][:120].rstrip(".")
                summary_parts.append(
                    f"Key competitive gap vs {top_competitor.competitor_name}: {weakness_short}."
                )
            result.executive_summary = " ".join(summary_parts)

            # ── Actionable key recommendations ───────────────────────────────────
            # Consistent ACV across all revenue displays (pipeline card uses same figure)
            avg_acv_sgd = 15_000
            key_recommendations: list[str] = []

            # #1 Action first — this gets highlighted in the UI (index 0)
            if top_lead:
                trigger_str = ""
                if hasattr(top_lead, "trigger_events") and top_lead.trigger_events:
                    trigger_str = f" Trigger: {top_lead.trigger_events[0]}."
                contact_str = ""
                if top_lead.contact_name and top_lead.contact_email:
                    contact_str = f" Email {top_lead.contact_name} at {top_lead.contact_email} today."
                elif top_lead.contact_name:
                    contact_str = f" Key contact: {top_lead.contact_name} ({top_lead.contact_title or 'decision maker'})."
                key_recommendations.append(
                    f"#1 Action: Reach out to {top_lead.company_name} — {top_lead.overall_score:.0%} ICP fit.{trigger_str}{contact_str}"
                )
            else:
                key_recommendations.append(
                    "No leads auto-discovered — add a website URL or known competitors to improve lead generation"
                )

            # Revenue projection — consistent ACV matches pipeline card in UI
            if result.leads:
                total_pipeline = sum(lead.overall_score * avg_acv_sgd for lead in result.leads)
                key_recommendations.append(
                    f"Pipeline value: {len(result.leads)} scored leads × SGD {avg_acv_sgd:,} ACV = SGD {total_pipeline:,.0f} weighted pipeline"
                )

            # Competitor positioning
            if result.competitor_analysis:
                weakness_str = ""
                if top_competitor and top_competitor.weaknesses:
                    weakness_str = f" Lead with: {top_competitor.weaknesses[0][:120]}."
                key_recommendations.append(
                    f"Differentiate against {len(result.competitor_analysis)} competitors identified.{weakness_str}"
                )
            else:
                key_recommendations.append(
                    "Provide known competitors to enable SWOT analysis and positioning recommendations"
                )

            # Market insight action
            if top_insight and top_insight.recommendations:
                _first_rec = top_insight.recommendations[0]
                if _first_rec:
                    key_recommendations.append(
                        f"Market action: {_first_rec[:200]}"
                    )
            elif top_insight:
                key_recommendations.append(
                    f"Market signal: {top_insight.summary[:200]}"
                )

            # Campaign action
            if result.campaign_brief and result.campaign_brief.email_templates:
                key_recommendations.append(
                    f"Campaign ready: use the '{result.campaign_brief.name}' email sequence — first template ready to personalise and send"
                )

            result.key_recommendations = key_recommendations

            # Save to database
            analysis.status = DBAnalysisStatus.COMPLETED
            analysis.progress = 100
            analysis.current_agent = None
            analysis.completed_agents = list(completed_agents)
            analysis.executive_summary = result.executive_summary
            analysis.key_recommendations = result.key_recommendations
            analysis.market_insights = (
                [m.model_dump(mode="json") for m in result.market_insights] if result.market_insights else []
            )
            analysis.competitor_analysis = (
                [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in result.competitor_analysis]
                if result.competitor_analysis
                else []
            )
            analysis.customer_personas = (
                [p.model_dump(mode="json") for p in result.customer_personas]
                if result.customer_personas
                else []
            )
            analysis.leads = [lead.model_dump(mode="json") for lead in result.leads] if result.leads else []

            # Persist leads to the Lead table so workspace pages can read them
            for lead_profile in result.leads:
                db.add(Lead(
                    company_id=analysis.company_id,
                    lead_company_name=lead_profile.company_name,
                    lead_company_website=lead_profile.website,
                    lead_company_industry=lead_profile.industry.value if hasattr(lead_profile.industry, "value") else str(lead_profile.industry),
                    lead_company_description=lead_profile.recommended_approach,
                    contact_name=lead_profile.contact_name,
                    contact_title=lead_profile.contact_title,
                    contact_email=lead_profile.contact_email,
                    contact_linkedin=lead_profile.contact_linkedin,
                    fit_score=int(lead_profile.fit_score * 100),
                    intent_score=int(lead_profile.intent_score * 100),
                    overall_score=int(lead_profile.overall_score * 100),
                    pain_points=lead_profile.pain_points or [],
                    trigger_events=lead_profile.trigger_events or [],
                    recommended_approach=lead_profile.recommended_approach,
                ))

            # Materialize market insights → MarketInsight table (powers /insights page)
            for insight in result.market_insights:
                confidence = insight.confidence or 0.0
                impact = "high" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "low"
                db.add(DBMarketInsight(
                    company_id=analysis.company_id,
                    insight_type=insight.category or "trend",
                    category=insight.category or "market",
                    title=insight.title,
                    summary=insight.summary,
                    full_content="\n".join(
                        (insight.key_findings or []) + (insight.implications or [])
                    ),
                    relevance_score=confidence,
                    impact_level=impact,
                    recommended_actions=insight.recommendations or [],
                    source_name=insight.sources[0] if insight.sources else None,
                    related_agents=["market-intelligence"],
                ))

            # Materialize campaign brief → Campaign table (powers /campaigns page)
            if result.campaign_brief:
                cb = result.campaign_brief
                db.add(DBCampaign(
                    company_id=analysis.company_id,
                    name=cb.name,
                    description=cb.objective,
                    objective=cb.objective,
                    status=CampaignStatus.DRAFT,
                    target_personas=[cb.target_persona] if cb.target_persona else [],
                    target_industries=[
                        i.value if hasattr(i, "value") else str(i)
                        for i in (cb.target_industries or [])
                    ],
                    key_messages=cb.key_messages or [],
                    value_propositions=cb.value_propositions or [],
                    call_to_action=cb.call_to_action,
                    channels=cb.channels or [],
                    email_templates=[{"body": t} for t in (cb.email_templates or [])],
                    linkedin_posts=[{"content": p} for p in (cb.linkedin_posts or [])],
                    budget=cb.budget_sgd,
                    currency="SGD",
                ))

            analysis.campaign_brief = (
                result.campaign_brief.model_dump(mode="json")
                if hasattr(result.campaign_brief, "model_dump")
                else result.campaign_brief
            )
            analysis.outreach_sequences = (
                [seq.model_dump(mode="json") if hasattr(seq, "model_dump") else seq for seq in result.outreach_sequences]
                if result.outreach_sequences else []
            )
            # content_pieces from CampaignPlanOutput
            if campaign_result and hasattr(campaign_result, "content_pieces"):
                analysis.content_pieces = [
                    cp.model_dump(mode="json") if hasattr(cp, "model_dump") else cp
                    for cp in (campaign_result.content_pieces or [])
                ]
            analysis.market_sizing = result.market_sizing
            analysis.total_confidence = result.total_confidence
            analysis.processing_time_seconds = result.processing_time_seconds
            analysis.agents_used = result.agents_used

            # Bridge: materialize analysis results → SignalEvent rows so TodayPage
            # can display intelligence immediately (before scheduler runs).
            # Clear previous analysis-generated signals to avoid duplicates on re-run.
            await db.execute(
                SignalEvent.__table__.delete().where(
                    SignalEvent.company_id == analysis.company_id,
                    SignalEvent.source == "analysis",
                )
            )
            _INSIGHT_CATEGORY_MAP: dict[str, SignalType] = {
                "trend": SignalType.MARKET_TREND,
                "opportunity": SignalType.MARKET_TREND,
                "threat": SignalType.COMPETITOR_NEWS,
                "regulation": SignalType.REGULATION,
                "news": SignalType.GENERAL_NEWS,
                "market": SignalType.MARKET_TREND,
                "general": SignalType.GENERAL_NEWS,
            }
            for insight in result.market_insights:
                sig_type = _INSIGHT_CATEGORY_MAP.get(
                    (insight.category or "general").lower(), SignalType.GENERAL_NEWS
                )
                confidence = insight.confidence or 0.0
                urgency = (
                    SignalUrgency.THIS_WEEK if confidence >= 0.7
                    else SignalUrgency.THIS_MONTH if confidence >= 0.4
                    else SignalUrgency.MONITOR
                )
                summary_parts = []
                if insight.key_findings:
                    summary_parts.extend(f for f in insight.key_findings[:3] if f)
                if insight.implications:
                    summary_parts.extend(i for i in insight.implications[:2] if i)
                db.add(SignalEvent(
                    company_id=analysis.company_id,
                    signal_type=sig_type,
                    urgency=urgency,
                    headline=insight.title,
                    summary=insight.summary + ("\n" + " | ".join(summary_parts) if summary_parts else ""),
                    source="analysis",
                    relevance_score=confidence,
                    recommended_action="; ".join(r for r in insight.recommendations[:2] if r) if insight.recommendations else None,
                ))

            for comp in result.competitor_analysis:
                # Create a signal per competitor with their key intelligence
                headline_parts = [comp.competitor_name]
                if comp.strategic_moves:
                    headline_parts.append(comp.strategic_moves[0])
                elif comp.recent_news:
                    headline_parts.append(comp.recent_news[0])
                else:
                    headline_parts.append(comp.positioning or comp.description[:100] if comp.description else "competitor identified")

                summary_lines = []
                if comp.strengths:
                    summary_lines.append(f"Strengths: {', '.join(comp.strengths[:3])}")
                if comp.weaknesses:
                    summary_lines.append(f"Gaps: {', '.join(comp.weaknesses[:3])}")
                if comp.key_differentiators:
                    summary_lines.append(f"Differentiators: {', '.join(comp.key_differentiators[:3])}")

                db.add(SignalEvent(
                    company_id=analysis.company_id,
                    signal_type=SignalType.COMPETITOR_NEWS,
                    urgency=SignalUrgency.THIS_WEEK if comp.confidence >= 0.7 else SignalUrgency.THIS_MONTH,
                    headline=" — ".join(headline_parts),
                    summary="\n".join(summary_lines) if summary_lines else comp.description,
                    source="analysis",
                    relevance_score=comp.confidence,
                    competitors_mentioned=[comp.competitor_name],
                    recommended_action=f"Review {comp.competitor_name}'s positioning and adjust your differentiation strategy.",
                ))

            await db.commit()

            # Mark GTM Strategist as complete before broadcasting analysis_completed
            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id="gtm-strategist",
                agent_name="GTM Strategist",
                status="complete",
                progress=1.0,
                message=f"Strategy complete — {len(result.leads)} leads, {len(result.competitor_analysis)} competitors analysed",
            )

            # Send final completion
            await send_agent_update(
                analysis_id=analysis_id,
                update_type="analysis_completed",
                message=f"Analysis complete for {request.company_name}",
                result={
                    "leads_count": len(result.leads),
                    "insights_count": len(result.market_insights),
                    "competitors_count": len(result.competitor_analysis),
                    "personas_count": len(result.customer_personas),
                    "has_campaign": result.campaign_brief is not None,
                    "processing_time_seconds": result.processing_time_seconds,
                    "confidence": result.total_confidence,
                },
            )

            logger.info(
                "analysis_completed",
                analysis_id=str(analysis_id),
                company=request.company_name,
                leads=len(result.leads),
                processing_time=result.processing_time_seconds,
            )

        except Exception as e:
            full_tb = traceback.format_exc()
            logger.error(
                "analysis_failed",
                analysis_id=str(analysis_id),
                error=str(e),
                traceback=full_tb,
            )
            # Always rollback first — the session may be in a broken state if the
            # main try block's db.commit() was what raised. Without rollback, any
            # subsequent commit raises InvalidRequestError and the analysis is
            # permanently stuck as RUNNING.
            try:
                await db.rollback()
            except Exception:
                pass
            analysis.status = DBAnalysisStatus.FAILED
            analysis.error = full_tb
            analysis.current_agent = None
            try:
                await db.commit()
            except Exception as commit_err:
                logger.error("failed_status_commit_failed", error=str(commit_err))

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="error",
                error=str(e),
                message=f"Analysis failed: {str(e)}",
            )


async def run_analysis_sync(request: AnalysisRequest) -> GTMAnalysisResult:
    """Run analysis synchronously (simplified for quick endpoint)."""
    context = {
        "company_name": request.company_name,
        "website": request.website,
        "description": request.description,
        "industry": request.industry.value,
        "goals": request.goals,
        "current_challenges": request.challenges,
        "known_competitors": request.competitors,
        "target_markets": request.target_markets or ["Singapore"],
        "value_proposition": request.value_proposition,
    }

    result = GTMAnalysisResult(
        id=uuid4(),
        company_id=uuid4(),
    )

    # Run lead hunter only for quick analysis
    if request.include_lead_generation:
        agent = LeadHunterAgent()
        lead_context = {
            **context,
            "analysis_id": result.id,  # scope any bus operations to this analysis
            "target_industries": [request.industry.value],
            "target_count": min(request.lead_count, 5),
        }
        try:
            async with asyncio.timeout(60):
                lead_result = await agent.run(
                    f"Find qualified leads in {request.industry.value}",
                    context=lead_context,
                )
            result.leads = lead_result.qualified_leads
        except (TimeoutError, MaxIterationsExceededError, AgentError) as e:
            logger.warning("quick_analysis_lead_hunter_failed", error=str(e))
            result.leads = []

    result.agents_used = ["lead-hunter"]
    result.total_confidence = 0.7
    result.executive_summary = f"Quick analysis for {request.company_name}"

    return result
