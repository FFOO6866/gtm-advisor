"""Audit Logging for Full Traceability.

Every agent action, tool call, and decision is logged with:
- Who: Agent and user identity
- What: Action taken
- When: Timestamp
- Where: Context and source
- Why: Decision rationale (from LLM or algorithm)

Enables: Debugging, compliance, billing, improvement.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""

    # Agent events
    AGENT_START = "agent.start"
    AGENT_COMPLETE = "agent.complete"
    AGENT_ERROR = "agent.error"
    AGENT_INVOKE = "agent.invoke"

    # Tool events
    TOOL_CALL = "tool.call"
    TOOL_SUCCESS = "tool.success"
    TOOL_ERROR = "tool.error"
    TOOL_RATE_LIMITED = "tool.rate_limited"

    # Algorithm events
    ALGO_SCORE = "algo.score"
    ALGO_CLUSTER = "algo.cluster"
    ALGO_RULE = "algo.rule"

    # LLM events
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"

    # Checkpoint events
    CHECKPOINT_TRIGGERED = "checkpoint.triggered"
    CHECKPOINT_APPROVED = "checkpoint.approved"
    CHECKPOINT_REJECTED = "checkpoint.rejected"
    CHECKPOINT_EXPIRED = "checkpoint.expired"

    # Access events
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"

    # Data events
    DATA_READ = "data.read"
    DATA_WRITE = "data.write"
    DATA_EXPORT = "data.export"

    # Integration events
    CRM_SYNC = "integration.crm_sync"
    ENRICHMENT = "integration.enrichment"

    # User events
    USER_ACTION = "user.action"
    USER_FEEDBACK = "user.feedback"


@dataclass
class AuditEvent:
    """An audit log entry."""

    id: str
    event_type: AuditEventType
    timestamp: datetime
    agent_id: str | None
    user_id: str | None
    session_id: str | None
    action: str
    resource: str | None
    resource_id: str | None
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None
    success: bool = True
    error_message: str | None = None
    parent_event_id: str | None = None  # For tracing call chains

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "input_summary": self._summarize(self.input_data),
            "output_summary": self._summarize(self.output_data),
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message,
            "parent_event_id": self.parent_event_id,
        }

    def _summarize(self, data: dict[str, Any] | None, max_length: int = 500) -> str | None:
        """Summarize data for storage."""
        if not data:
            return None
        try:
            text = json.dumps(data, default=str)
            if len(text) > max_length:
                return text[:max_length] + "..."
            return text
        except Exception:
            return str(data)[:max_length]

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Central audit logging facility.

    Example:
        audit = AuditLogger()

        # Log agent start
        event_id = audit.log(
            event_type=AuditEventType.AGENT_START,
            agent_id="lead_hunter",
            action="process_lead",
            resource="lead",
            resource_id="lead_123",
            input_data={"company": "Acme Corp"},
        )

        # Log tool call (linked to parent)
        audit.log(
            event_type=AuditEventType.TOOL_CALL,
            agent_id="lead_hunter",
            action="company_enrichment",
            resource="tool",
            parent_event_id=event_id,
            input_data={"domain": "acme.com"},
        )
    """

    def __init__(
        self,
        storage_backend: str = "memory",  # memory, file, database
        file_path: str | None = None,
        max_memory_events: int = 10000,
    ):
        self.storage_backend = storage_backend
        self.file_path = file_path
        self.max_memory_events = max_memory_events
        self._events: list[AuditEvent] = []
        self._session_id: str | None = None

        if storage_backend == "file" and file_path:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    def set_session(self, session_id: str) -> None:
        """Set current session ID for all events."""
        self._session_id = session_id

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        agent_id: str | None = None,
        user_id: str | None = None,
        resource: str | None = None,
        resource_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        success: bool = True,
        error_message: str | None = None,
        parent_event_id: str | None = None,
    ) -> str:
        """Log an audit event."""
        event = AuditEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            agent_id=agent_id,
            user_id=user_id,
            session_id=self._session_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            input_data=input_data,
            output_data=output_data,
            metadata=metadata or {},
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            parent_event_id=parent_event_id,
        )

        self._store_event(event)
        return event.id

    def _store_event(self, event: AuditEvent) -> None:
        """Store event based on backend."""
        if self.storage_backend == "memory":
            self._events.append(event)
            # Trim if too many
            if len(self._events) > self.max_memory_events:
                self._events = self._events[-self.max_memory_events :]

        elif self.storage_backend == "file" and self.file_path:
            try:
                with open(self.file_path, "a") as f:
                    f.write(event.to_json() + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit event: {e}")

        # Always log to standard logger
        logger.info(
            f"AUDIT: {event.event_type.value} | "
            f"agent={event.agent_id} | "
            f"action={event.action} | "
            f"success={event.success}"
        )

    def query(
        self,
        event_type: AuditEventType | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        resource: str | None = None,
        success: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events."""
        results = self._events

        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if agent_id:
            results = [e for e in results if e.agent_id == agent_id]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if resource:
            results = [e for e in results if e.resource == resource]
        if success is not None:
            results = [e for e in results if e.success == success]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]

        # Sort by timestamp descending (most recent first)
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)

        return results[:limit]

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Get a specific event by ID."""
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    def get_event_chain(self, event_id: str) -> list[AuditEvent]:
        """Get an event and all its children (call chain)."""
        chain = []

        # Find the root event
        event = self.get_event(event_id)
        if event:
            chain.append(event)

        # Find all children
        def find_children(parent_id: str) -> list[AuditEvent]:
            children = [e for e in self._events if e.parent_event_id == parent_id]
            result = []
            for child in children:
                result.append(child)
                result.extend(find_children(child.id))
            return result

        chain.extend(find_children(event_id))
        return sorted(chain, key=lambda e: e.timestamp)

    def get_agent_summary(self, agent_id: str) -> dict[str, Any]:
        """Get summary statistics for an agent."""
        events = [e for e in self._events if e.agent_id == agent_id]

        if not events:
            return {"agent_id": agent_id, "total_events": 0}

        total = len(events)
        successful = sum(1 for e in events if e.success)
        failed = total - successful

        # Duration stats
        durations = [e.duration_ms for e in events if e.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Event type breakdown
        by_type: dict[str, int] = {}
        for event in events:
            key = event.event_type.value
            by_type[key] = by_type.get(key, 0) + 1

        return {
            "agent_id": agent_id,
            "total_events": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "by_type": by_type,
            "first_event": min(e.timestamp for e in events).isoformat(),
            "last_event": max(e.timestamp for e in events).isoformat(),
        }

    def export(
        self,
        format: str = "json",  # json, csv
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> str:
        """Export audit log."""
        events = self.query(since=since, until=until, limit=100000)

        if format == "json":
            return json.dumps([e.to_dict() for e in events], indent=2, default=str)

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(
                [
                    "id",
                    "event_type",
                    "timestamp",
                    "agent_id",
                    "user_id",
                    "action",
                    "resource",
                    "success",
                    "duration_ms",
                    "error_message",
                ]
            )

            # Rows
            for event in events:
                writer.writerow(
                    [
                        event.id,
                        event.event_type.value,
                        event.timestamp.isoformat(),
                        event.agent_id,
                        event.user_id,
                        event.action,
                        event.resource,
                        event.success,
                        event.duration_ms,
                        event.error_message,
                    ]
                )

            return output.getvalue()

        else:
            raise ValueError(f"Unknown format: {format}")

    def clear(self) -> None:
        """Clear in-memory events (for testing)."""
        self._events = []


# Convenience decorators
def audit_function(
    logger: AuditLogger,
    event_type: AuditEventType,
    agent_id: str | None = None,
):
    """Decorator to audit function calls."""

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            import time

            start = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000

                logger.log(
                    event_type=event_type,
                    action=func.__name__,
                    agent_id=agent_id,
                    input_data={"args": str(args)[:200], "kwargs": str(kwargs)[:200]},
                    output_data={"result": str(result)[:200]},
                    duration_ms=duration,
                    success=True,
                )
                return result

            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.log(
                    event_type=event_type,
                    action=func.__name__,
                    agent_id=agent_id,
                    input_data={"args": str(args)[:200], "kwargs": str(kwargs)[:200]},
                    duration_ms=duration,
                    success=False,
                    error_message=str(e),
                )
                raise

        def sync_wrapper(*args, **kwargs):
            import time

            start = time.time()

            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000

                logger.log(
                    event_type=event_type,
                    action=func.__name__,
                    agent_id=agent_id,
                    duration_ms=duration,
                    success=True,
                )
                return result

            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.log(
                    event_type=event_type,
                    action=func.__name__,
                    agent_id=agent_id,
                    duration_ms=duration,
                    success=False,
                    error_message=str(e),
                )
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
