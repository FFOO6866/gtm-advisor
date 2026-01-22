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
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.core.src.config import get_config

from .routers import agents, analysis, companies, health, websocket

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("gtm_advisor_starting", version="0.1.0")
    config = get_config()
    logger.info(
        "config_loaded",
        environment=config.environment.value,
        governance_enabled=config.enable_governance,
    )
    yield
    # Shutdown
    logger.info("gtm_advisor_stopping")


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

# CORS configuration
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
        },
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])


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
