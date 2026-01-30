"""Base Tool Framework with Access Control.

All tools MUST:
1. Declare their access level (read/write/admin)
2. Implement rate limiting
3. Log all operations for audit
4. Handle errors gracefully
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ToolAccess(Enum):
    """Access levels for tools."""

    READ = "read"  # Read-only operations (fetching data)
    WRITE = "write"  # Create/update operations
    DELETE = "delete"  # Delete operations
    ADMIN = "admin"  # Administrative operations


class ToolCategory(Enum):
    """Categories of tools."""

    ENRICHMENT = "enrichment"
    SCRAPING = "scraping"
    CRM = "crm"
    COMMUNICATION = "communication"
    ANALYTICS = "analytics"
    STORAGE = "storage"


@dataclass
class ToolError(Exception):
    """Tool execution error with context."""

    tool_name: str
    operation: str
    message: str
    recoverable: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.tool_name}:{self.operation}] {self.message}"


@dataclass
class ToolResult(Generic[T]):
    """Result of a tool operation."""

    success: bool
    data: T | None
    error: str | None = None
    execution_time_ms: float = 0
    cached: bool = False
    rate_limited: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "cached": self.cached,
            "rate_limited": self.rate_limited,
            "metadata": self.metadata,
        }


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max concurrent requests


@dataclass
class AuditEntry:
    """Audit log entry for tool operations."""

    timestamp: datetime
    tool_name: str
    operation: str
    access_level: ToolAccess
    agent_id: str | None
    input_summary: str
    output_summary: str
    success: bool
    execution_time_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "operation": self.operation,
            "access_level": self.access_level.value,
            "agent_id": self.agent_id,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


class BaseTool(ABC):
    """Base class for all operational tools.

    Example:
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Does something useful"
            category = ToolCategory.ENRICHMENT
            required_access = ToolAccess.READ

            async def _execute(self, **kwargs) -> ToolResult:
                # Implementation
                pass
    """

    name: str = "base_tool"
    description: str = "Base tool"
    category: ToolCategory = ToolCategory.ANALYTICS
    required_access: ToolAccess = ToolAccess.READ
    rate_limit: RateLimitConfig = RateLimitConfig()

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
    ):
        self.agent_id = agent_id
        self.allowed_access = allowed_access or [ToolAccess.READ]
        self._request_times: list[float] = []
        self._audit_log: list[AuditEntry] = []
        self._semaphore = asyncio.Semaphore(self.rate_limit.burst_limit)

    def has_access(self, required: ToolAccess) -> bool:
        """Check if agent has required access level."""
        # Admin has all access
        if ToolAccess.ADMIN in self.allowed_access:
            return True

        # Specific access check
        return required in self.allowed_access

    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limits."""
        now = time.time()

        # Clean old entries
        minute_ago = now - 60
        hour_ago = now - 3600
        self._request_times = [t for t in self._request_times if t > hour_ago]

        # Check limits
        minute_requests = sum(1 for t in self._request_times if t > minute_ago)
        hour_requests = len(self._request_times)

        if minute_requests >= self.rate_limit.requests_per_minute:
            return False
        if hour_requests >= self.rate_limit.requests_per_hour:
            return False

        return True

    def _record_request(self) -> None:
        """Record a request for rate limiting."""
        self._request_times.append(time.time())

    def _log_audit(
        self,
        operation: str,
        input_summary: str,
        output_summary: str,
        success: bool,
        execution_time_ms: float,
        error: str | None = None,
    ) -> None:
        """Log operation for audit trail."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            tool_name=self.name,
            operation=operation,
            access_level=self.required_access,
            agent_id=self.agent_id,
            input_summary=input_summary[:500],  # Truncate for storage
            output_summary=output_summary[:500],
            success=success,
            execution_time_ms=execution_time_ms,
            error=error,
        )
        self._audit_log.append(entry)
        logger.info(f"Tool audit: {entry.to_dict()}")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute tool with access control, rate limiting, and audit logging."""
        start_time = time.time()
        operation = kwargs.get("operation", "execute")
        input_summary = str(kwargs)[:200]

        # Check access
        if not self.has_access(self.required_access):
            error_msg = f"Access denied: {self.required_access.value} required"
            self._log_audit(operation, input_summary, "", False, 0, error_msg)
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
                metadata={"access_denied": True},
            )

        # Check rate limit
        if not self._check_rate_limit():
            error_msg = "Rate limit exceeded"
            self._log_audit(operation, input_summary, "", False, 0, error_msg)
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
                rate_limited=True,
            )

        # Execute with semaphore for burst limiting
        try:
            async with self._semaphore:
                self._record_request()
                result = await self._execute(**kwargs)

            execution_time = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time

            output_summary = str(result.data)[:200] if result.data else ""
            self._log_audit(
                operation,
                input_summary,
                output_summary,
                result.success,
                execution_time,
                result.error,
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            self._log_audit(operation, input_summary, "", False, execution_time, error_msg)
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
                execution_time_ms=execution_time,
            )

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> ToolResult:
        """Implement tool-specific logic."""
        pass

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get audit log entries."""
        return [entry.to_dict() for entry in self._audit_log]

    def clear_audit_log(self) -> None:
        """Clear audit log (for testing)."""
        self._audit_log = []

    def to_dict(self) -> dict[str, Any]:
        """Export tool configuration."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "required_access": self.required_access.value,
            "rate_limit": {
                "requests_per_minute": self.rate_limit.requests_per_minute,
                "requests_per_hour": self.rate_limit.requests_per_hour,
                "burst_limit": self.rate_limit.burst_limit,
            },
        }


class ToolRegistry:
    """Registry for managing available tools with access control.

    Example:
        registry = ToolRegistry()
        registry.register(CompanyEnrichmentTool())
        registry.register(HubSpotTool())

        # Get tools for an agent with specific access
        tools = registry.get_tools_for_agent(
            agent_id="lead_hunter",
            allowed_access=[ToolAccess.READ, ToolAccess.WRITE],
            categories=[ToolCategory.ENRICHMENT, ToolCategory.CRM],
        )
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._agent_permissions: dict[str, list[ToolAccess]] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def set_agent_permissions(
        self,
        agent_id: str,
        permissions: list[ToolAccess],
    ) -> None:
        """Set permissions for an agent."""
        self._agent_permissions[agent_id] = permissions

    def get_tools_for_agent(
        self,
        agent_id: str,
        categories: list[ToolCategory] | None = None,
    ) -> list[BaseTool]:
        """Get tools available for an agent based on permissions."""
        permissions = self._agent_permissions.get(agent_id, [ToolAccess.READ])

        available = []
        for tool in self._tools.values():
            # Check category filter
            if categories and tool.category not in categories:
                continue

            # Check access
            if tool.required_access in permissions or ToolAccess.ADMIN in permissions:
                # Create tool instance with agent context
                tool_instance = tool.__class__(
                    agent_id=agent_id,
                    allowed_access=permissions,
                )
                available.append(tool_instance)

        return available

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return [tool.to_dict() for tool in self._tools.values()]

    def get_tools_by_category(self, category: ToolCategory) -> list[BaseTool]:
        """Get all tools in a category."""
        return [t for t in self._tools.values() if t.category == category]
