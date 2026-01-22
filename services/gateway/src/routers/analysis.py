"""Analysis orchestration endpoints."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from packages.core.src.types import (
    CompanyProfile,
    GTMAnalysisResult,
    IndustryVertical,
)

# Import agents
from agents.campaign_architect.src import CampaignArchitectAgent
from agents.competitor_analyst.src import CompetitorAnalystAgent
from agents.customer_profiler.src import CustomerProfilerAgent
from agents.gtm_strategist.src import GTMStrategistAgent
from agents.lead_hunter.src import LeadHunterAgent
from agents.market_intelligence.src import MarketIntelligenceAgent

router = APIRouter()

# In-memory store for analysis results
_analyses: dict[UUID, dict[str, Any]] = {}


class AnalysisRequest(BaseModel):
    """Request for GTM analysis."""

    company_name: str = Field(..., min_length=1)
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
    """Run the full GTM analysis (background task)."""
    data = _analyses[analysis_id]
    data["status"] = "running"
    start_time = time.time()

    try:
        # Build context
        context = {
            "company_name": request.company_name,
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
            company_id=uuid4(),  # Would be real company ID
        )

        total_steps = sum([
            request.include_market_research,
            request.include_competitor_analysis,
            request.include_customer_profiling,
            request.include_lead_generation,
            request.include_campaign_planning,
        ])
        step = 0

        # 1. Market Intelligence
        if request.include_market_research:
            data["current_agent"] = "market-intelligence"
            agent = MarketIntelligenceAgent()
            market_result = await agent.run(
                f"Research {request.industry.value} market in Singapore",
                context=context,
            )
            result.market_insights = [market_result]  # Simplified
            data["completed_agents"].append("market-intelligence")
            step += 1
            data["progress"] = step / total_steps

        # 2. Competitor Analysis
        if request.include_competitor_analysis and request.competitors:
            data["current_agent"] = "competitor-analyst"
            agent = CompetitorAnalystAgent()
            competitor_result = await agent.run(
                f"Analyze competitors: {', '.join(request.competitors[:3])}",
                context=context,
            )
            result.competitor_analysis = competitor_result.competitors
            data["completed_agents"].append("competitor-analyst")
            step += 1
            data["progress"] = step / total_steps

        # 3. Customer Profiling
        if request.include_customer_profiling:
            data["current_agent"] = "customer-profiler"
            agent = CustomerProfilerAgent()
            profile_result = await agent.run(
                "Create customer profiles",
                context=context,
            )
            result.customer_personas = profile_result.personas
            data["completed_agents"].append("customer-profiler")
            step += 1
            data["progress"] = step / total_steps

        # 4. Lead Generation
        if request.include_lead_generation:
            data["current_agent"] = "lead-hunter"
            agent = LeadHunterAgent()
            lead_context = {
                **context,
                "target_industries": [request.industry.value],
                "target_count": request.lead_count,
            }
            lead_result = await agent.run(
                f"Find {request.lead_count} qualified leads",
                context=lead_context,
            )
            result.leads = lead_result.qualified_leads
            data["completed_agents"].append("lead-hunter")
            step += 1
            data["progress"] = step / total_steps

        # 5. Campaign Planning
        if request.include_campaign_planning:
            data["current_agent"] = "campaign-architect"
            agent = CampaignArchitectAgent()
            campaign_context = {
                **context,
                "leads": [l.model_dump() for l in result.leads[:3]],
            }
            campaign_result = await agent.run(
                "Create outreach campaign",
                context=campaign_context,
            )
            result.campaign_brief = campaign_result.campaign_brief
            data["completed_agents"].append("campaign-architect")
            step += 1
            data["progress"] = step / total_steps

        # Set summary
        result.agents_used = data["completed_agents"]
        result.processing_time_seconds = time.time() - start_time
        result.total_confidence = 0.75  # Simplified

        # Generate executive summary
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

        data["result"] = result
        data["status"] = "completed"
        data["processing_time"] = time.time() - start_time
        data["current_agent"] = None
        data["progress"] = 1.0

    except Exception as e:
        data["status"] = "failed"
        data["error"] = str(e)
        data["current_agent"] = None


async def run_analysis_sync(request: AnalysisRequest) -> GTMAnalysisResult:
    """Run analysis synchronously (simplified for quick endpoint)."""
    # Build context
    context = {
        "company_name": request.company_name,
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
