"""Agent API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..agents_registry import (
    AGENT_METADATA,
    get_agent_class,
    get_all_agent_classes,
    is_valid_agent,
)
from ..auth.dependencies import get_optional_user
from ..auth.models import User

logger = structlog.get_logger()
router = APIRouter()


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
async def list_agents(
    _current_user: User | None = Depends(get_optional_user),
) -> list[AgentCard]:
    """List all available agents with their cards."""
    cards = []
    agents = get_all_agent_classes()

    for name, agent_class in agents.items():
        agent = agent_class()
        metadata = AGENT_METADATA.get(name, {})

        cards.append(
            AgentCard(
                name=agent.name,
                title=metadata.get("title", agent.name.replace("-", " ").title()),
                description=agent.description,
                status=agent.status.value,
                capabilities=[
                    {"name": c.name, "description": c.description} for c in agent.capabilities
                ],
                avatar=metadata.get("avatar"),
                color=metadata.get("color", "#3B82F6"),
            )
        )

    return cards


@router.get("/{agent_name}")
async def get_agent(
    agent_name: str,
    _current_user: User | None = Depends(get_optional_user),
) -> AgentCard:
    """Get a specific agent's card."""
    if not is_valid_agent(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent_class = get_agent_class(agent_name)
    if not agent_class:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = agent_class()
    metadata = AGENT_METADATA.get(agent_name, {})

    return AgentCard(
        name=agent.name,
        title=metadata.get("title", agent.name.replace("-", " ").title()),
        description=agent.description,
        status=agent.status.value,
        capabilities=[{"name": c.name, "description": c.description} for c in agent.capabilities],
        avatar=metadata.get("avatar"),
        color=metadata.get("color", "#3B82F6"),
    )


@router.post("/{agent_name}/run")
async def run_agent(
    agent_name: str,
    request: AgentRunRequest,
    _current_user: User | None = Depends(get_optional_user),
) -> AgentRunResponse:
    """Run a specific agent with a task.

    Note: For company-scoped agent runs with persistence, use the
    /api/v1/companies/{company_id}/agents/{agent_id}/run endpoint instead.
    """
    if not is_valid_agent(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent_class = get_agent_class(agent_name)
    if not agent_class:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = agent_class()

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
        # Log the actual error for debugging
        logger.error("agent_run_failed", agent_name=agent_name, error=str(e))
        # Return a generic error to the client (don't expose internal details)
        raise HTTPException(
            status_code=500, detail="Agent execution failed. Please try again or contact support."
        )
