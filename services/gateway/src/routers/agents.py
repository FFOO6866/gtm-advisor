"""Agent API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import agents
from agents.campaign_architect.src import CampaignArchitectAgent
from agents.competitor_analyst.src import CompetitorAnalystAgent
from agents.customer_profiler.src import CustomerProfilerAgent
from agents.gtm_strategist.src import GTMStrategistAgent
from agents.lead_hunter.src import LeadHunterAgent
from agents.market_intelligence.src import MarketIntelligenceAgent

router = APIRouter()


# Agent registry
AGENTS = {
    "gtm-strategist": GTMStrategistAgent,
    "market-intelligence": MarketIntelligenceAgent,
    "competitor-analyst": CompetitorAnalystAgent,
    "customer-profiler": CustomerProfilerAgent,
    "lead-hunter": LeadHunterAgent,
    "campaign-architect": CampaignArchitectAgent,
}


class AgentCard(BaseModel):
    """Agent card for dashboard display."""

    name: str = Field(...)
    title: str = Field(...)
    description: str = Field(...)
    status: str = Field(default="idle")
    capabilities: list[dict[str, str]] = Field(default_factory=list)
    avatar: str | None = Field(default=None)
    color: str = Field(default="#3B82F6")  # Default blue


class AgentRunRequest(BaseModel):
    """Request to run an agent."""

    task: str = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    """Response from agent execution."""

    agent_name: str = Field(...)
    status: str = Field(...)
    result: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0)
    iterations: int = Field(default=0)


@router.get("/")
async def list_agents() -> list[AgentCard]:
    """List all available agents with their cards."""
    cards = []

    # Agent metadata for UI
    agent_metadata = {
        "gtm-strategist": {
            "title": "GTM Strategist",
            "color": "#8B5CF6",  # Purple
            "avatar": "🎯",
        },
        "market-intelligence": {
            "title": "Market Intelligence",
            "color": "#10B981",  # Green
            "avatar": "📊",
        },
        "competitor-analyst": {
            "title": "Competitor Analyst",
            "color": "#F59E0B",  # Amber
            "avatar": "🔍",
        },
        "customer-profiler": {
            "title": "Customer Profiler",
            "color": "#EC4899",  # Pink
            "avatar": "👥",
        },
        "lead-hunter": {
            "title": "Lead Hunter",
            "color": "#3B82F6",  # Blue
            "avatar": "🎣",
        },
        "campaign-architect": {
            "title": "Campaign Architect",
            "color": "#EF4444",  # Red
            "avatar": "📣",
        },
    }

    for name, agent_class in AGENTS.items():
        agent = agent_class()
        metadata = agent_metadata.get(name, {})

        cards.append(
            AgentCard(
                name=agent.name,
                title=metadata.get("title", agent.name.replace("-", " ").title()),
                description=agent.description,
                status=agent.status.value,
                capabilities=[
                    {"name": c.name, "description": c.description}
                    for c in agent.capabilities
                ],
                avatar=metadata.get("avatar"),
                color=metadata.get("color", "#3B82F6"),
            )
        )

    return cards


@router.get("/{agent_name}")
async def get_agent(agent_name: str) -> AgentCard:
    """Get a specific agent's card."""
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = AGENTS[agent_name]()
    return AgentCard(
        name=agent.name,
        title=agent.name.replace("-", " ").title(),
        description=agent.description,
        status=agent.status.value,
        capabilities=[
            {"name": c.name, "description": c.description}
            for c in agent.capabilities
        ],
    )


@router.post("/{agent_name}/run")
async def run_agent(agent_name: str, request: AgentRunRequest) -> AgentRunResponse:
    """Run a specific agent with a task."""
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = AGENTS[agent_name]()

    try:
        result = await agent.run(request.task, context=request.context)

        return AgentRunResponse(
            agent_name=agent_name,
            status="completed",
            result=result.model_dump() if hasattr(result, "model_dump") else {},
            confidence=result.confidence if hasattr(result, "confidence") else 0.0,
            iterations=agent._current_state.iteration + 1 if agent._current_state else 0,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
