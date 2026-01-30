"""Health check endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from packages.core.src.config import get_config
from packages.llm.src import get_llm_manager

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "gtm-advisor-gateway",
        "version": "0.1.0",
    }


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Detailed health check including dependencies."""
    config = get_config()
    llm_manager = get_llm_manager()

    # Check LLM providers
    llm_status = await llm_manager.health_check()

    return {
        "status": "healthy",
        "service": "gtm-advisor-gateway",
        "version": "0.1.0",
        "environment": config.environment.value,
        "dependencies": {
            "llm_providers": llm_status,
            "governance_enabled": config.enable_governance,
            "observability_enabled": config.enable_observability,
        },
    }


@router.get("/health/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check for Kubernetes."""
    # Check if at least one LLM provider is configured
    llm_manager = get_llm_manager()
    providers = llm_manager.list_configured_providers()

    if not providers:
        return {
            "status": "not_ready",
            "reason": "No LLM providers configured",
        }

    return {
        "status": "ready",
        "configured_providers": providers,
    }
