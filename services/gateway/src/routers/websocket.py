"""WebSocket endpoints for real-time updates."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from packages.database.src.models import Analysis
from packages.database.src.session import async_session_factory

from ..auth.dependencies import db_user_to_api_user, get_user_by_id, validate_company_access
from ..auth.utils import decode_token

logger = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        # Map analysis_id -> list of connected websockets
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        # Map websocket -> analysis_id for cleanup
        self.websocket_to_analysis: dict[WebSocket, UUID] = {}
        # Per-analysis send lock — prevents concurrent ws.send_json() calls
        # from parallel agent coroutines from interleaving frames.
        self._send_locks: dict[UUID, asyncio.Lock] = {}

    async def connect(self, websocket: WebSocket, analysis_id: UUID) -> None:
        """Accept connection and track it."""
        if analysis_id in self.active_connections and len(self.active_connections[analysis_id]) >= 10:
            logger.warning(
                "websocket_connection_limit_reached",
                analysis_id=str(analysis_id),
                total_connections=len(self.active_connections[analysis_id]),
            )
            await websocket.close(code=1008)
            return
        await websocket.accept()
        if analysis_id not in self.active_connections:
            self.active_connections[analysis_id] = []
        self.active_connections[analysis_id].append(websocket)
        self.websocket_to_analysis[websocket] = analysis_id
        logger.info(
            "websocket_connected",
            analysis_id=str(analysis_id),
            total_connections=len(self.active_connections[analysis_id]),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection from tracking."""
        analysis_id = self.websocket_to_analysis.get(websocket)
        if analysis_id and analysis_id in self.active_connections:
            if websocket in self.active_connections[analysis_id]:
                self.active_connections[analysis_id].remove(websocket)
            if not self.active_connections[analysis_id]:
                self.active_connections.pop(analysis_id, None)
        self.websocket_to_analysis.pop(websocket, None)
        logger.info("websocket_disconnected", analysis_id=str(analysis_id))

    async def broadcast_to_analysis(self, analysis_id: UUID, message: dict[str, Any]) -> None:
        """Send message to all connections watching an analysis.

        Serialises writes per analysis_id — concurrent coroutines (parallel
        wave-2 agents, A2A bus broadcasts) must not interleave WebSocket frames
        on the same connection.
        """
        if analysis_id not in self.active_connections:
            return

        if analysis_id not in self._send_locks:
            self._send_locks[analysis_id] = asyncio.Lock()

        async with self._send_locks[analysis_id]:
            disconnected = []
            for websocket in self.active_connections[analysis_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(websocket)

            # Clean up disconnected
            for ws in disconnected:
                self.disconnect(ws)


# Global connection manager
manager = ConnectionManager()


class AgentUpdateMessage(BaseModel):
    """Message format for agent updates."""

    type: str = Field(
        ...
    )  # agent_started, agent_progress, agent_completed, analysis_completed, error
    agent_id: str | None = Field(default=None)
    agent_name: str | None = Field(default=None)
    status: str | None = Field(default=None)
    progress: float | None = Field(default=None)
    message: str | None = Field(default=None)
    result: dict[str, Any] | None = Field(default=None)
    error: str | None = Field(default=None)
    timestamp: str | None = Field(default=None)


@router.websocket("/analysis/{analysis_id}")
async def websocket_analysis(
    websocket: WebSocket,
    analysis_id: UUID,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for real-time analysis updates.

    Authentication is handled via token query parameter since WebSocket
    doesn't support standard HTTP headers in the same way.

    For MVP mode (unowned companies), connections are allowed without a token.
    For owned companies, a valid JWT token is required.
    """
    # Validate authentication and authorization
    async with async_session_factory() as db:
        # Get the analysis to find its company
        analysis = await db.get(Analysis, analysis_id)
        if not analysis:
            await websocket.close(code=4004, reason="Analysis not found")
            return

        # Validate user access to the analysis's company
        user = None
        if token:
            token_data = decode_token(token, token_type="access")
            if token_data:
                db_user = await get_user_by_id(str(token_data.user_id), db)
                if db_user and db_user.is_active:
                    user = db_user_to_api_user(db_user)

        # Check company access
        try:
            await validate_company_access(analysis.company_id, user, db)
        except Exception as e:
            logger.warning(
                "websocket_auth_failed",
                analysis_id=str(analysis_id),
                error=str(e),
            )
            await websocket.close(code=4003, reason="Access denied")
            return

    # Authorization passed - establish connection
    await manager.connect(websocket, analysis_id)
    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            # Client can send ping/pong or other messages
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("websocket_error", error=str(e), analysis_id=str(analysis_id))
        manager.disconnect(websocket)


async def send_agent_update(
    analysis_id: UUID,
    update_type: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Send an agent update to all connected clients."""
    from datetime import UTC, datetime

    update = {
        "type": update_type,
        "agentId": agent_id,
        "agentName": agent_name,
        "status": status,
        "progress": progress,
        "message": message,
        "result": result,
        "error": error,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    await manager.broadcast_to_analysis(analysis_id, update)


def get_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager
