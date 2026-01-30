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
    get_agent_bus,
)
from packages.core.src.types import (
    GTMAnalysisResult,
    IndustryVertical,
    LeadProfile,
    MarketInsight,
)
from packages.database.src.models import Analysis, Company
from packages.database.src.models import AnalysisStatus as DBAnalysisStatus
from packages.database.src.session import async_session_factory, get_db_session

from ..auth.dependencies import get_optional_user
from ..auth.models import User
from ..middleware.rate_limit import analysis_limit
from .websocket import send_agent_update

router = APIRouter()
logger = structlog.get_logger()


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
    lead_count: int = Field(default=10, ge=1, le=50)
    # Optional: link to existing company
    company_id: UUID | None = Field(default=None)


class AnalysisStatusResponse(BaseModel):
    """Status of an analysis."""

    analysis_id: UUID
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

    # Create or get company
    company_id = analysis_request.company_id
    if not company_id:
        # Create a new company record for this analysis
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
            owner_id=user_id,  # Set owner if authenticated
        )
        db.add(company)
        await db.flush()
        company_id = company.id

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
        competitor_analysis=analysis.competitor_analysis or [],
        customer_personas=analysis.customer_personas or [],
        leads=[LeadProfile(**lead) for lead in (analysis.leads or [])],
        campaign_brief=analysis.campaign_brief,
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
            leads=[lead.model_dump() for lead in result.leads] if result.leads else [],
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
        raise HTTPException(status_code=500, detail=str(e))


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
            # Build context
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
            include_company_enrichment = bool(request.website)
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
                analysis.completed_agents = completed_agents
                await db.commit()

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
                    message=f"Analyzing company website: {request.website}...",
                )

                enricher = CompanyEnricherAgent(agent_bus=agent_bus, analysis_id=analysis_id)
                enrichment_result = await enricher.enrich_company(
                    company_name=request.company_name,
                    website=request.website,
                    industry=request.industry,
                    description=request.description,
                    analysis_id=analysis_id,
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

                completed_agents.append(agent_id)
                step += 1

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
                    agent_name="Company Enricher",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Enriched profile with {len(enrichment_result.products)} products",
                    result={
                        "products_count": len(enrichment_result.products),
                        "competitors_discovered": len(enrichment_result.mentioned_competitors),
                    },
                )

                await asyncio.sleep(0.1)

            # =====================================================================
            # STEP 1: Market Intelligence
            # =====================================================================
            if request.include_market_research:
                agent_id = "market-intelligence"
                await update_progress(agent_id, int((step / total_steps) * 100))

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id=agent_id,
                    agent_name="Market Intelligence",
                    status="thinking",
                    message=f"Researching {request.industry.value} market in Singapore...",
                )

                agent = MarketIntelligenceAgent()
                market_result = await agent.run(
                    f"Research {request.industry.value} market in Singapore for: {request.company_name}. {request.description}",
                    context=context,
                )

                # Convert to MarketInsight format
                if hasattr(market_result, "insights"):
                    result.market_insights = market_result.insights
                else:
                    key_findings = []
                    implications = []
                    recommendations = []

                    if hasattr(market_result, "key_trends"):
                        for trend in market_result.key_trends[:3]:
                            key_findings.append(f"{trend.name}: {trend.description}")

                    if hasattr(market_result, "opportunities"):
                        for opp in market_result.opportunities[:3]:
                            key_findings.append(f"Opportunity: {opp.title}")
                            recommendations.append(opp.recommended_action)

                    if hasattr(market_result, "implications_for_gtm"):
                        implications = market_result.implications_for_gtm[:5]

                    if hasattr(market_result, "threats"):
                        for threat in market_result.threats[:3]:
                            key_findings.append(f"Threat: {threat}")

                    result.market_insights = [
                        MarketInsight(
                            title=f"{request.industry.value.title()} Market Analysis",
                            summary=market_result.market_summary
                            if hasattr(market_result, "market_summary")
                            else "Market analysis completed.",
                            category="trend",
                            key_findings=key_findings or ["Market data gathered successfully"],
                            implications=implications,
                            recommendations=recommendations,
                            sources=market_result.sources
                            if hasattr(market_result, "sources")
                            else [],
                            confidence=market_result.confidence
                            if hasattr(market_result, "confidence")
                            else 0.7,
                        )
                    ]

                completed_agents.append(agent_id)
                step += 1

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
                    agent_name="Market Intelligence",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Found {len(result.market_insights)} market insights",
                    result={"insights_count": len(result.market_insights)},
                )

                decision_attribution["llm_decisions"] += 1

            # =====================================================================
            # STEP 2: Competitor Analysis
            # =====================================================================
            if request.include_competitor_analysis:
                agent_id = "competitor-analyst"
                await update_progress(agent_id, int((step / total_steps) * 100))

                all_competitors = context.get("known_competitors", [])
                competitors_to_analyze = (
                    all_competitors[:5] if all_competitors else ["market leaders"]
                )

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id=agent_id,
                    agent_name="Competitor Analyst",
                    status="thinking",
                    message=f"Analyzing {len(competitors_to_analyze)} competitors...",
                )

                agent = CompetitorAnalystAgent(agent_bus=agent_bus, analysis_id=analysis_id)
                competitor_result = await agent.run(
                    f"Analyze competitors for {request.company_name} in {request.industry.value}: {', '.join(competitors_to_analyze)}",
                    context=context,
                )

                if hasattr(competitor_result, "competitors"):
                    result.competitor_analysis = competitor_result.competitors
                else:
                    result.competitor_analysis = []

                completed_agents.append(agent_id)
                step += 1

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
                    agent_name="Competitor Analyst",
                    status="complete",
                    progress=step / total_steps,
                    message=f"Analyzed {len(result.competitor_analysis)} competitors",
                    result={"competitors_count": len(result.competitor_analysis)},
                )

                decision_attribution["llm_decisions"] += 1
                decision_attribution["tool_calls"] += 2

            # =====================================================================
            # STEP 3: Customer Profiling
            # =====================================================================
            if request.include_customer_profiling:
                agent_id = "customer-profiler"
                await update_progress(agent_id, int((step / total_steps) * 100))

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_started",
                    agent_id=agent_id,
                    agent_name="Customer Profiler",
                    status="thinking",
                    message="Developing ideal customer profiles...",
                )

                agent = CustomerProfilerAgent()
                profile_result = await agent.run(
                    f"Create ideal customer profiles for {request.company_name}",
                    context=context,
                )

                if hasattr(profile_result, "personas"):
                    result.customer_personas = profile_result.personas
                else:
                    result.customer_personas = []

                completed_agents.append(agent_id)
                step += 1

                await send_agent_update(
                    analysis_id=analysis_id,
                    update_type="agent_completed",
                    agent_id=agent_id,
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
                lead_context = {
                    **context,
                    "target_industries": [request.industry.value],
                    "target_count": request.lead_count,
                }
                lead_result = await agent.run(
                    f"Find {request.lead_count} qualified leads for {request.company_name} in {request.industry.value}",
                    context=lead_context,
                )

                if hasattr(lead_result, "qualified_leads"):
                    result.leads = lead_result.qualified_leads
                else:
                    result.leads = []

                if hasattr(lead_result, "algorithm_decisions"):
                    decision_attribution["algorithm_decisions"] += lead_result.algorithm_decisions
                if hasattr(lead_result, "llm_decisions"):
                    decision_attribution["llm_decisions"] += lead_result.llm_decisions
                if hasattr(lead_result, "tool_calls"):
                    decision_attribution["tool_calls"] += lead_result.tool_calls

                completed_agents.append(agent_id)
                step += 1

                total_pipeline = sum(lead.overall_score * 50000 for lead in result.leads)

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

                agent = CampaignArchitectAgent()
                campaign_context = {
                    **context,
                    "leads": [lead.model_dump() for lead in result.leads[:3]]
                    if result.leads
                    else [],
                    "personas": [p.model_dump() for p in result.customer_personas[:2]]
                    if result.customer_personas
                    else [],
                }
                campaign_result = await agent.run(
                    f"Create outreach campaign for {request.company_name}",
                    context=campaign_context,
                )

                if hasattr(campaign_result, "campaign_brief"):
                    result.campaign_brief = campaign_result.campaign_brief
                elif hasattr(campaign_result, "brief"):
                    result.campaign_brief = campaign_result.brief

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
            # Finalize Results
            # =====================================================================
            total_decisions = (
                decision_attribution["algorithm_decisions"] + decision_attribution["llm_decisions"]
            )
            determinism_ratio = (
                decision_attribution["algorithm_decisions"] / total_decisions
                if total_decisions > 0
                else 0.5
            )

            result.agents_used = completed_agents
            result.processing_time_seconds = time.time() - start_time
            result.total_confidence = 0.75 + (determinism_ratio * 0.15)

            result.executive_summary = (
                f"GTM analysis completed for {request.company_name}. "
                f"Found {len(result.leads)} qualified leads, "
                f"analyzed {len(result.competitor_analysis)} competitors, "
                f"and created {len(result.customer_personas)} customer personas."
            )

            result.key_recommendations = [
                "Focus on the identified high-fit leads for immediate outreach",
                "Use the campaign templates provided for initial contact",
                "Monitor market trends identified for ongoing opportunities",
            ]

            # Save to database
            analysis.status = DBAnalysisStatus.COMPLETED
            analysis.progress = 100
            analysis.current_agent = None
            analysis.completed_agents = completed_agents
            analysis.executive_summary = result.executive_summary
            analysis.key_recommendations = result.key_recommendations
            analysis.market_insights = (
                [m.model_dump() for m in result.market_insights] if result.market_insights else []
            )
            analysis.competitor_analysis = result.competitor_analysis
            analysis.customer_personas = (
                [p.model_dump() for p in result.customer_personas]
                if result.customer_personas
                else []
            )
            analysis.leads = [lead.model_dump() for lead in result.leads] if result.leads else []
            analysis.campaign_brief = (
                result.campaign_brief.model_dump()
                if hasattr(result.campaign_brief, "model_dump")
                else result.campaign_brief
            )
            analysis.total_confidence = result.total_confidence
            analysis.processing_time_seconds = result.processing_time_seconds
            analysis.agents_used = result.agents_used
            await db.commit()

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
            logger.error(
                "analysis_failed",
                analysis_id=str(analysis_id),
                error=str(e),
            )
            analysis.status = DBAnalysisStatus.FAILED
            analysis.error = str(e)
            analysis.current_agent = None
            await db.commit()

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
            "target_industries": [request.industry.value],
            "target_count": min(request.lead_count, 5),
        }
        lead_result = await agent.run(
            f"Find qualified leads in {request.industry.value}",
            context=lead_context,
        )
        result.leads = lead_result.qualified_leads

    result.agents_used = ["lead-hunter"]
    result.total_confidence = 0.7
    result.executive_summary = f"Quick analysis for {request.company_name}"

    return result
