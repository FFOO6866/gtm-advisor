"""Analysis orchestration endpoints.

Features A2A (Agent-to-Agent) communication for dynamic collaboration:
1. CompanyEnricherAgent runs FIRST to analyze user's company website
2. It publishes discoveries to the AgentBus
3. Other agents subscribe and react to these discoveries
4. Agents can publish their own discoveries for cross-agent insights
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from packages.core.src.types import (
    CompanyProfile,
    GTMAnalysisResult,
    IndustryVertical,
    LeadProfile,
    MarketInsight,
)
from packages.core.src.agent_bus import (
    AgentBus,
    AgentMessage,
    get_agent_bus,
    reset_agent_bus,
)

# Import agents
from agents.campaign_architect.src import CampaignArchitectAgent
from agents.company_enricher.src import CompanyEnricherAgent
from agents.competitor_analyst.src import CompetitorAnalystAgent
from agents.customer_profiler.src import CustomerProfilerAgent
from agents.gtm_strategist.src import GTMStrategistAgent
from agents.lead_hunter.src import LeadHunterAgent
from agents.market_intelligence.src import MarketIntelligenceAgent

from .websocket import send_agent_update

router = APIRouter()
logger = structlog.get_logger()

# In-memory store for analysis results
_analyses: dict[UUID, dict[str, Any]] = {}


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


class AnalysisStatus(BaseModel):
    """Status of an analysis."""

    analysis_id: UUID = Field(...)
    status: str = Field(...)  # pending, running, completed, failed
    progress: float = Field(default=0.0)  # 0-1
    current_agent: str | None = Field(default=None)
    completed_agents: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None)


class AnalysisResponse(BaseModel):
    """Response from completed analysis."""

    analysis_id: UUID = Field(...)
    status: str = Field(...)
    result: GTMAnalysisResult | None = Field(default=None)
    processing_time_seconds: float = Field(default=0.0)


@router.post("/start")
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisStatus:
    """Start a new GTM analysis (runs in background)."""
    analysis_id = uuid4()

    # Initialize status
    _analyses[analysis_id] = {
        "status": "pending",
        "progress": 0.0,
        "current_agent": None,
        "completed_agents": [],
        "request": request.model_dump(),
        "result": None,
        "error": None,
        "started_at": time.time(),
    }

    # Start background task
    background_tasks.add_task(run_analysis, analysis_id, request)

    return AnalysisStatus(
        analysis_id=analysis_id,
        status="pending",
        progress=0.0,
    )


@router.get("/{analysis_id}/status")
async def get_analysis_status(analysis_id: UUID) -> AnalysisStatus:
    """Get the status of an analysis."""
    if analysis_id not in _analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    data = _analyses[analysis_id]
    return AnalysisStatus(
        analysis_id=analysis_id,
        status=data["status"],
        progress=data["progress"],
        current_agent=data["current_agent"],
        completed_agents=data["completed_agents"],
        error=data["error"],
    )


@router.get("/{analysis_id}/result")
async def get_analysis_result(analysis_id: UUID) -> AnalysisResponse:
    """Get the result of a completed analysis."""
    if analysis_id not in _analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    data = _analyses[analysis_id]

    if data["status"] != "completed":
        return AnalysisResponse(
            analysis_id=analysis_id,
            status=data["status"],
            result=None,
        )

    return AnalysisResponse(
        analysis_id=analysis_id,
        status="completed",
        result=data["result"],
        processing_time_seconds=data.get("processing_time", 0),
    )


@router.post("/quick")
async def quick_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Run a quick synchronous analysis (for testing/demo)."""
    analysis_id = uuid4()
    start_time = time.time()

    try:
        result = await run_analysis_sync(request)

        return AnalysisResponse(
            analysis_id=analysis_id,
            status="completed",
            result=result,
            processing_time_seconds=time.time() - start_time,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_analysis(analysis_id: UUID, request: AnalysisRequest) -> None:
    """Run the full GTM analysis (background task) with real-time WebSocket updates.

    A2A Flow:
    1. CompanyEnricherAgent runs first (if website provided) to enrich company data
    2. Discoveries are published to AgentBus
    3. Other agents subscribe and use these discoveries
    4. Cross-agent collaboration happens via the bus
    """
    data = _analyses[analysis_id]
    data["status"] = "running"
    start_time = time.time()

    # Initialize AgentBus for this analysis
    agent_bus = get_agent_bus()
    agent_bus.clear_history(analysis_id)

    # Set up WebSocket broadcast for A2A messages
    async def broadcast_a2a_message(message: AgentMessage) -> None:
        """Broadcast A2A messages to frontend."""
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
            company_id=uuid4(),
        )

        # Track decision attribution
        decision_attribution = {
            "algorithm_decisions": 0,
            "llm_decisions": 0,
            "tool_calls": 0,
            "breakdown": [],
        }

        # Calculate total steps (including company enrichment if website provided)
        include_company_enrichment = bool(request.website)
        total_steps = sum([
            include_company_enrichment,
            request.include_market_research,
            request.include_competitor_analysis,
            request.include_customer_profiling,
            request.include_lead_generation,
            request.include_campaign_planning,
        ])
        step = 0

        # Send analysis started
        await send_agent_update(
            analysis_id=analysis_id,
            update_type="analysis_started",
            message=f"Starting GTM analysis for {request.company_name}",
        )

        # =====================================================================
        # STEP 0: Company Enrichment (A2A First Step)
        # This runs FIRST to provide context for other agents
        # =====================================================================
        if include_company_enrichment:
            agent_id = "company-enricher"
            data["current_agent"] = agent_id

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
                    context["value_proposition"] = "; ".join(enrichment_result.value_propositions)
                if enrichment_result.mentioned_competitors:
                    # Add discovered competitors to the list
                    existing = set(context.get("known_competitors", []))
                    existing.update(enrichment_result.mentioned_competitors)
                    context["known_competitors"] = list(existing)
                if enrichment_result.target_markets:
                    context["target_markets"] = enrichment_result.target_markets

            data["completed_agents"] = data.get("completed_agents", [])
            data["completed_agents"].append(agent_id)
            step += 1
            data["progress"] = step / total_steps

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id=agent_id,
                agent_name="Company Enricher",
                status="complete",
                progress=data["progress"],
                message=f"Enriched profile with {len(enrichment_result.products)} products, {len(enrichment_result.mentioned_competitors)} competitors discovered",
                result={
                    "products_count": len(enrichment_result.products),
                    "competitors_discovered": len(enrichment_result.mentioned_competitors),
                    "tech_stack": len(enrichment_result.tech_stack),
                },
            )

            # Small delay to allow A2A messages to propagate
            await asyncio.sleep(0.1)

        # 1. Market Intelligence
        if request.include_market_research:
            agent_id = "market-intelligence"
            data["current_agent"] = agent_id

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
                f"Research {request.industry.value} market in Singapore for a company: {request.company_name}. {request.description}",
                context=context,
            )

            # Convert MarketIntelligenceOutput to MarketInsight format
            if hasattr(market_result, "insights"):
                result.market_insights = market_result.insights
            else:
                # Extract key findings from trends and opportunities
                key_findings = []
                implications = []
                recommendations = []

                # Extract from trends
                if hasattr(market_result, "key_trends"):
                    for trend in market_result.key_trends[:3]:
                        key_findings.append(f"{trend.name}: {trend.description}")

                # Extract from opportunities
                if hasattr(market_result, "opportunities"):
                    for opp in market_result.opportunities[:3]:
                        key_findings.append(f"Opportunity: {opp.title}")
                        recommendations.append(opp.recommended_action)

                # Extract implications
                if hasattr(market_result, "implications_for_gtm"):
                    implications = market_result.implications_for_gtm[:5]

                # Extract threats
                if hasattr(market_result, "threats"):
                    for threat in market_result.threats[:3]:
                        key_findings.append(f"Threat: {threat}")

                result.market_insights = [
                    MarketInsight(
                        title=f"{request.industry.value.title()} Market Analysis - {market_result.region if hasattr(market_result, 'region') else 'Singapore'}",
                        summary=market_result.market_summary if hasattr(market_result, "market_summary") else "Market analysis completed.",
                        category="trend",
                        key_findings=key_findings or ["Market data gathered successfully"],
                        implications=implications,
                        recommendations=recommendations,
                        sources=market_result.sources if hasattr(market_result, "sources") else [],
                        confidence=market_result.confidence if hasattr(market_result, "confidence") else 0.7,
                    )
                ]

            data["completed_agents"].append(agent_id)
            step += 1
            data["progress"] = step / total_steps

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id=agent_id,
                agent_name="Market Intelligence",
                status="complete",
                progress=data["progress"],
                message=f"Found {len(result.market_insights)} market insights",
                result={"insights_count": len(result.market_insights)},
            )

            decision_attribution["llm_decisions"] += 1

        # 2. Competitor Analysis (A2A-enabled)
        if request.include_competitor_analysis:
            agent_id = "competitor-analyst"
            data["current_agent"] = agent_id

            # Competitors may include A2A-discovered ones from CompanyEnricher
            all_competitors = context.get("known_competitors", [])
            competitors_to_analyze = all_competitors[:5] if all_competitors else ["market leaders"]

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_started",
                agent_id=agent_id,
                agent_name="Competitor Analyst",
                status="thinking",
                message=f"Analyzing {len(competitors_to_analyze)} competitors (incl. A2A discoveries)...",
            )

            # Use A2A-enabled agent with bus subscription
            agent = CompetitorAnalystAgent(agent_bus=agent_bus, analysis_id=analysis_id)
            competitor_result = await agent.run(
                f"Analyze competitors for {request.company_name} in {request.industry.value}: {', '.join(competitors_to_analyze)}",
                context=context,
            )

            if hasattr(competitor_result, "competitors"):
                result.competitor_analysis = competitor_result.competitors
            else:
                result.competitor_analysis = []

            data["completed_agents"].append(agent_id)
            step += 1
            data["progress"] = step / total_steps

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id=agent_id,
                agent_name="Competitor Analyst",
                status="complete",
                progress=data["progress"],
                message=f"Analyzed {len(result.competitor_analysis)} competitors",
                result={"competitors_count": len(result.competitor_analysis)},
            )

            decision_attribution["llm_decisions"] += 1
            decision_attribution["tool_calls"] += 2  # Web search, news

        # 3. Customer Profiling
        if request.include_customer_profiling:
            agent_id = "customer-profiler"
            data["current_agent"] = agent_id

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

            data["completed_agents"].append(agent_id)
            step += 1
            data["progress"] = step / total_steps

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id=agent_id,
                agent_name="Customer Profiler",
                status="complete",
                progress=data["progress"],
                message=f"Created {len(result.customer_personas)} customer personas",
                result={"personas_count": len(result.customer_personas)},
            )

            decision_attribution["llm_decisions"] += 1

        # 4. Lead Generation
        if request.include_lead_generation:
            agent_id = "lead-hunter"
            data["current_agent"] = agent_id

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

            # Track lead hunter's decision attribution
            if hasattr(lead_result, "algorithm_decisions"):
                decision_attribution["algorithm_decisions"] += lead_result.algorithm_decisions
            if hasattr(lead_result, "llm_decisions"):
                decision_attribution["llm_decisions"] += lead_result.llm_decisions
            if hasattr(lead_result, "tool_calls"):
                decision_attribution["tool_calls"] += lead_result.tool_calls

            data["completed_agents"].append(agent_id)
            step += 1
            data["progress"] = step / total_steps

            # Calculate total pipeline value
            total_pipeline = sum(
                lead.overall_score * 50000  # Estimated deal value based on score
                for lead in result.leads
            )

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id=agent_id,
                agent_name="Lead Hunter",
                status="complete",
                progress=data["progress"],
                message=f"Found {len(result.leads)} qualified leads (SGD {total_pipeline:,.0f} pipeline)",
                result={
                    "leads_count": len(result.leads),
                    "pipeline_value": total_pipeline,
                },
            )

        # 5. Campaign Planning
        if request.include_campaign_planning:
            agent_id = "campaign-architect"
            data["current_agent"] = agent_id

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
                "leads": [l.model_dump() for l in result.leads[:3]] if result.leads else [],
                "personas": [p.model_dump() for p in result.customer_personas[:2]] if result.customer_personas else [],
            }
            campaign_result = await agent.run(
                f"Create outreach campaign for {request.company_name}",
                context=campaign_context,
            )

            if hasattr(campaign_result, "campaign_brief"):
                result.campaign_brief = campaign_result.campaign_brief
            elif hasattr(campaign_result, "brief"):
                result.campaign_brief = campaign_result.brief

            data["completed_agents"].append(agent_id)
            step += 1
            data["progress"] = step / total_steps

            await send_agent_update(
                analysis_id=analysis_id,
                update_type="agent_completed",
                agent_id=agent_id,
                agent_name="Campaign Architect",
                status="complete",
                progress=data["progress"],
                message="Created campaign templates and messaging",
                result={"campaign_ready": result.campaign_brief is not None},
            )

            decision_attribution["llm_decisions"] += 1

        # Calculate final metrics
        total_decisions = (
            decision_attribution["algorithm_decisions"]
            + decision_attribution["llm_decisions"]
        )
        determinism_ratio = (
            decision_attribution["algorithm_decisions"] / total_decisions
            if total_decisions > 0
            else 0.5
        )

        # Set summary
        result.agents_used = data["completed_agents"]
        result.processing_time_seconds = time.time() - start_time
        result.total_confidence = 0.75 + (determinism_ratio * 0.15)  # Higher confidence with more algorithmic decisions

        # Generate executive summary
        result.executive_summary = (
            f"GTM analysis completed for {request.company_name}. "
            f"Found {len(result.leads)} qualified leads, "
            f"analyzed {len(result.competitor_analysis)} competitors, "
            f"and created {len(result.customer_personas)} customer personas. "
            f"Analysis used {decision_attribution['algorithm_decisions']} algorithmic decisions "
            f"and {decision_attribution['llm_decisions']} LLM-based decisions "
            f"({determinism_ratio:.0%} determinism ratio)."
        )

        result.key_recommendations = [
            "Focus on the identified high-fit leads for immediate outreach",
            "Use the campaign templates provided for initial contact",
            "Monitor market trends identified for ongoing opportunities",
        ]

        data["result"] = result
        data["decision_attribution"] = decision_attribution
        data["determinism_ratio"] = determinism_ratio
        data["status"] = "completed"
        data["processing_time"] = time.time() - start_time
        data["current_agent"] = None
        data["progress"] = 1.0

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
                "determinism_ratio": determinism_ratio,
                "algorithm_decisions": decision_attribution["algorithm_decisions"],
                "llm_decisions": decision_attribution["llm_decisions"],
                "tool_calls": decision_attribution["tool_calls"],
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
        data["status"] = "failed"
        data["error"] = str(e)
        data["current_agent"] = None

        await send_agent_update(
            analysis_id=analysis_id,
            update_type="error",
            error=str(e),
            message=f"Analysis failed: {str(e)}",
        )


async def run_analysis_sync(request: AnalysisRequest) -> GTMAnalysisResult:
    """Run analysis synchronously (simplified for quick endpoint)."""
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
        id=uuid4(),
        company_id=uuid4(),
    )

    # Run lead hunter only for quick analysis
    if request.include_lead_generation:
        agent = LeadHunterAgent()
        lead_context = {
            **context,
            "target_industries": [request.industry.value],
            "target_count": min(request.lead_count, 5),  # Limit for quick
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
