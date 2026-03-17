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
    approvals,
    attribution,
    auth,
    campaigns,
    companies,
    company_agents,
    competitors,
    documents,
    exports,
    health,
    icps,
    insights,
    leads,
    market_data,
    playbooks,
    sequences,
    settings,
    signals,
    strategy,
    webhooks,
    websocket,
    workforce,
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

    # Seed built-in playbook templates
    try:
        from packages.database.src.session import async_session_factory
        from services.gateway.src.services.playbook_service import PlaybookService
        async with async_session_factory() as seed_db:
            await PlaybookService(seed_db).seed_built_in_playbooks()
        logger.info("playbooks_seeded")
    except Exception as e:
        logger.error("playbook_seed_failed", error=str(e))
        # Non-fatal — playbooks can be seeded later

    # Seed market verticals (idempotent)
    try:
        from packages.database.src.session import async_session_factory
        from packages.database.src.vertical_seeds import seed_verticals
        async with async_session_factory() as db:
            count = await seed_verticals(db)
            await db.commit()
            if count:
                logger.info("verticals_seeded", count=count)
    except Exception as e:
        logger.error("vertical_seed_failed", error=str(e))
        # Non-fatal — verticals can be seeded later

    # Recover any analyses orphaned by a previous server crash/reload.
    # Any analysis still in RUNNING state has no active background task — mark FAILED.
    # Retry up to 3 times with a short delay to handle SQLite WAL lock from prior process.
    try:
        import asyncio as _asyncio

        from sqlalchemy import update

        from packages.database.src.models import Analysis
        from packages.database.src.models import AnalysisStatus as DBAnalysisStatus
        from packages.database.src.session import async_session_factory
        for _attempt in range(3):
            try:
                async with async_session_factory() as db:
                    result = await db.execute(
                        update(Analysis)
                        .where(Analysis.status == DBAnalysisStatus.RUNNING)
                        .values(
                            status=DBAnalysisStatus.FAILED,
                            error="Server restarted while analysis was in progress. Please try again.",
                            current_agent=None,
                        )
                    )
                    await db.commit()
                    if result.rowcount > 0:
                        logger.warning("orphaned_analyses_recovered", count=result.rowcount)
                break
            except Exception as _e:
                if _attempt < 2:
                    await _asyncio.sleep(1.0)
                else:
                    raise _e
    except Exception as e:
        logger.error("orphan_recovery_failed", error=str(e))
        # Non-fatal — app continues

    # Start background scheduler (signal monitor, sequence runner, enrichment)
    from .scheduler import start_scheduler
    try:
        await start_scheduler()
        logger.info("scheduler_started")
    except Exception as e:
        logger.error("scheduler_start_failed", error=str(e))
        # Non-fatal — app continues without scheduler

    yield

    # Stop scheduler
    from .scheduler import stop_scheduler
    await stop_scheduler()

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

# Authentication middleware (sets request.state.user)
# Added FIRST so it is innermost — CORS headers are added on all responses,
# including 401s, because CORSMiddleware runs as the outermost layer.
app.add_middleware(AuthMiddleware)

# CORS must be added LAST (outermost) so it wraps AuthMiddleware and adds
# Access-Control-Allow-Origin headers even when auth rejects a request.
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(workforce.router, prefix="/api/v1/companies", tags=["Workforce"])
app.include_router(signals.router, prefix="/api/v1/companies", tags=["Signals"])
app.include_router(sequences.router, prefix="/api/v1/companies", tags=["Sequences"])
app.include_router(approvals.router, prefix="/api/v1/companies", tags=["Approvals"])
app.include_router(playbooks.router, prefix="/api/v1/companies", tags=["Playbooks"])
app.include_router(attribution.router, prefix="/api/v1/companies", tags=["Attribution"])
app.include_router(market_data.router, prefix="/api/v1/companies", tags=["Market Data"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(documents.router, tags=["Documents"])


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
