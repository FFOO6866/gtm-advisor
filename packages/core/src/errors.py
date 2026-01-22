"""GTM Advisor Error Hierarchy.

All custom errors inherit from GTMError for consistent handling.
"""

from __future__ import annotations

from typing import Any


class GTMError(Exception):
    """Base exception for all GTM Advisor errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# Agent Errors
class AgentError(GTMError):
    """Error during agent execution."""

    pass


class MaxIterationsExceededError(AgentError):
    """Agent exceeded maximum PDCA iterations without reaching confidence threshold."""

    def __init__(
        self,
        agent_name: str,
        iterations: int,
        final_confidence: float,
        threshold: float,
    ) -> None:
        super().__init__(
            f"Agent '{agent_name}' exceeded {iterations} iterations. "
            f"Final confidence {final_confidence:.2f} < threshold {threshold:.2f}",
            code="MAX_ITERATIONS_EXCEEDED",
            details={
                "agent_name": agent_name,
                "iterations": iterations,
                "final_confidence": final_confidence,
                "threshold": threshold,
            },
        )


class AgentNotFoundError(AgentError):
    """Requested agent not found in registry."""

    def __init__(self, agent_name: str) -> None:
        super().__init__(
            f"Agent '{agent_name}' not found in registry",
            code="AGENT_NOT_FOUND",
            details={"agent_name": agent_name},
        )


# Validation Errors
class ValidationError(GTMError):
    """Data validation failed."""

    pass


class SchemaValidationError(ValidationError):
    """JSON Schema validation failed."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__(
            f"Schema validation failed with {len(errors)} error(s)",
            code="SCHEMA_VALIDATION_ERROR",
            details={"validation_errors": errors},
        )


# Governance Errors
class GovernanceError(GTMError):
    """Governance policy violation."""

    pass


class RateLimitExceededError(GovernanceError):
    """Rate limit exceeded for user/tenant."""

    def __init__(
        self,
        user_id: str,
        limit: int,
        window: str,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            f"Rate limit exceeded for user '{user_id}'. Limit: {limit}/{window}",
            code="RATE_LIMIT_EXCEEDED",
            details={
                "user_id": user_id,
                "limit": limit,
                "window": window,
                "retry_after": retry_after,
            },
        )
        self.retry_after = retry_after


class BudgetExceededError(GovernanceError):
    """LLM cost budget exceeded."""

    def __init__(
        self,
        user_id: str,
        budget: float,
        spent: float,
        currency: str = "SGD",
    ) -> None:
        super().__init__(
            f"Budget exceeded for user '{user_id}'. "
            f"Budget: {currency}{budget:.2f}, Spent: {currency}{spent:.2f}",
            code="BUDGET_EXCEEDED",
            details={
                "user_id": user_id,
                "budget": budget,
                "spent": spent,
                "currency": currency,
            },
        )


class PDPAViolationError(GovernanceError):
    """PDPA (Personal Data Protection Act) compliance violation."""

    def __init__(self, violation_type: str, field: str | None = None) -> None:
        super().__init__(
            f"PDPA violation: {violation_type}" + (f" in field '{field}'" if field else ""),
            code="PDPA_VIOLATION",
            details={"violation_type": violation_type, "field": field},
        )


class UnauthorizedError(GovernanceError):
    """User not authorized for this action."""

    def __init__(self, action: str, resource: str | None = None) -> None:
        super().__init__(
            f"Unauthorized: cannot {action}" + (f" on {resource}" if resource else ""),
            code="UNAUTHORIZED",
            details={"action": action, "resource": resource},
        )


# Integration Errors
class IntegrationError(GTMError):
    """External integration failed."""

    pass


class APIError(IntegrationError):
    """External API call failed."""

    def __init__(
        self,
        service: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(
            f"API error from {service}" + (f": {message}" if message else ""),
            code="API_ERROR",
            details={
                "service": service,
                "status_code": status_code,
            },
        )


class NewsAPIError(APIError):
    """NewsAPI integration error."""

    def __init__(self, message: str) -> None:
        super().__init__("NewsAPI", message=message)


class PerplexityError(APIError):
    """Perplexity API integration error."""

    def __init__(self, message: str) -> None:
        super().__init__("Perplexity", message=message)


class EODHDError(APIError):
    """EODHD API integration error."""

    def __init__(self, message: str) -> None:
        super().__init__("EODHD", message=message)


# Configuration Errors
class ConfigurationError(GTMError):
    """Configuration error."""

    pass


class MissingAPIKeyError(ConfigurationError):
    """Required API key not configured."""

    def __init__(self, key_name: str) -> None:
        super().__init__(
            f"Missing required API key: {key_name}. "
            "Please set it in your .env file or environment variables.",
            code="MISSING_API_KEY",
            details={"key_name": key_name},
        )
