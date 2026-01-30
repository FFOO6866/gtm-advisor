"""GTM Advisor Gateway - FastAPI Application.

Main entry point for the GTM Advisor API.
Provides endpoints for:
- Agent interaction
- Company profile management
- Analysis and lead generation
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env file BEFORE any other imports that might need env vars
from dotenv import load_dotenv

# Find and load .env from project root
_project_root = Path(__file__).parent.parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Try current working directory
    load_dotenv()

# These imports must come AFTER load_dotenv() to ensure env vars are available
from typing import Any  # noqa: E402

import structlog  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from packages.core.src.config import get_config  # noqa: E402
from packages.database.src.session import close_db, init_db  # noqa: E402

from .cache import close_cache, init_cache  # noqa: E402
from .errors import register_error_handlers  # noqa: E402
from .middleware.auth import AuthMiddleware  # noqa: E402
from .middleware.rate_limit import limiter  # noqa: E402
from .routers import (  # noqa: E402
    agents,
    analysis,
    auth,
    campaigns,
    companies,
    company_agents,
    competitors,
    exports,
    health,
    icps,
    insights,
    leads,
    settings,
    strategy,
    websocket,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("gtm_advisor_starting", version="0.1.0")
    config = get_config()
    logger.info(
        "config_loaded",
        environment=config.environment.value,
        governance_enabled=config.enable_governance,
    )

    # Validate production requirements
    production_errors = config.validate_production_requirements()
    if production_errors:
        for error in production_errors:
            logger.error("production_config_error", error=error)
        if config.is_production:
            raise RuntimeError(f"Production configuration errors: {'; '.join(production_errors)}")

    # Initialize database tables
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise

    # Initialize cache (Redis or in-memory)
    try:
        await init_cache()
        logger.info("cache_initialized")
    except Exception as e:
        logger.error("cache_initialization_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("gtm_advisor_stopping")
    await close_cache()
    logger.info("cache_closed")
    await close_db()
    logger.info("database_connections_closed")


app = FastAPI(
    title="GTM Advisor API",
    description=(
        "Self-Service Agentic AI Platform for Go-To-Market Advisory. "
        "Empowers Singapore SMEs with AI-driven GTM strategies and lead generation."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication middleware (sets request.state.user)
app.add_middleware(AuthMiddleware)

# Register all error handlers for consistent error responses
register_error_handlers(app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

# Workspace data routers
app.include_router(competitors.router, prefix="/api/v1/companies", tags=["Competitors"])
app.include_router(icps.router, prefix="/api/v1/companies", tags=["ICPs & Personas"])
app.include_router(leads.router, prefix="/api/v1/companies", tags=["Leads"])
app.include_router(campaigns.router, prefix="/api/v1/companies", tags=["Campaigns"])
app.include_router(insights.router, prefix="/api/v1/companies", tags=["Market Insights"])
app.include_router(strategy.router, prefix="/api/v1/companies", tags=["Strategy"])
app.include_router(company_agents.router, prefix="/api/v1/companies", tags=["Company Agents"])
app.include_router(exports.router, prefix="/api/v1/exports", tags=["Exports"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "GTM Advisor API",
        "version": "0.1.0",
        "description": "AI-powered Go-To-Market Advisory Platform",
        "docs": "/docs",
        "health": "/health",
    }


def run() -> None:
    """Run the gateway service."""
    import uvicorn

    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", "8000"))

    uvicorn.run(
        "services.gateway.src.main:app",
        host=host,
        port=port,
        reload=config.is_development,
    )


if __name__ == "__main__":
    run()
