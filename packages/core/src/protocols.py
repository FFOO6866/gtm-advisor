"""GTM Advisor Protocols - Interface definitions for agents and integrations."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol, TypeVar, runtime_checkable

from .types import AgentStatus, ExecutionMode, PDCAState, TaskStatus

T = TypeVar("T")


@runtime_checkable
class AgentProtocol(Protocol[T]):
    """Protocol for all GTM Advisor agents.

    All agents must implement PDCA methods for self-correcting execution.
    """

    @property
    def name(self) -> str:
        """Agent name (kebab-case)."""
        ...

    @property
    def description(self) -> str:
        """Agent description."""
        ...

    @property
    def status(self) -> AgentStatus:
        """Current agent status."""
        ...

    @property
    def min_confidence(self) -> float:
        """Minimum confidence threshold to accept result."""
        ...

    @property
    def max_iterations(self) -> int:
        """Maximum PDCA iterations before giving up."""
        ...

    async def run(self, task: str, **kwargs: Any) -> T:
        """Execute agent with full PDCA cycle.

        Args:
            task: Task description
            **kwargs: Additional context

        Returns:
            Typed result based on agent's result_type
        """
        ...

    async def fast_execute(
        self,
        context: dict[str, Any],
        mode: ExecutionMode = ExecutionMode.FAST,
    ) -> T:
        """Execute agent in fast mode (single LLM call or rule-based).

        Args:
            context: Execution context
            mode: Execution mode (FAST or ULTRA_FAST)

        Returns:
            Typed result
        """
        ...

    @abstractmethod
    async def _plan(self, task: str) -> dict[str, Any]:
        """PLAN phase: Analyze task and create execution plan.

        Args:
            task: Task description

        Returns:
            Execution plan dictionary
        """
        ...

    @abstractmethod
    async def _do(self, plan: dict[str, Any]) -> T:
        """DO phase: Execute the plan.

        Args:
            plan: Execution plan from _plan()

        Returns:
            Initial result
        """
        ...

    @abstractmethod
    async def _check(self, result: T) -> float:
        """CHECK phase: Validate result and return confidence score.

        Args:
            result: Result from _do()

        Returns:
            Confidence score 0.0-1.0
        """
        ...

    @abstractmethod
    async def _act(self, result: T, confidence: float) -> T:
        """ACT phase: Accept, adjust, or escalate based on confidence.

        Args:
            result: Result from _do()
            confidence: Confidence score from _check()

        Returns:
            Final or adjusted result
        """
        ...


@runtime_checkable
class TaskProtocol(Protocol):
    """Protocol for task objects."""

    @property
    def id(self) -> str:
        """Unique task identifier."""
        ...

    @property
    def task_type(self) -> str:
        """Type of task."""
        ...

    @property
    def status(self) -> TaskStatus:
        """Current task status."""
        ...

    @property
    def input_data(self) -> dict[str, Any]:
        """Input data for the task."""
        ...

    @property
    def result(self) -> dict[str, Any] | None:
        """Task result if completed."""
        ...


@runtime_checkable
class IntegrationProtocol(Protocol):
    """Protocol for external data source integrations."""

    @property
    def name(self) -> str:
        """Integration name."""
        ...

    @property
    def is_configured(self) -> bool:
        """Check if integration is properly configured (API key set, etc.)."""
        ...

    async def health_check(self) -> bool:
        """Check if integration is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        ...

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search the data source.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of results
        """
        ...


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Protocol for LLM providers."""

    @property
    def provider_name(self) -> str:
        """Provider name (openai, anthropic, perplexity)."""
        ...

    @property
    def is_configured(self) -> bool:
        """Check if provider is configured."""
        ...

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Get completion from LLM.

        Args:
            messages: Chat messages
            model: Model name override
            **kwargs: Additional parameters

        Returns:
            Completion text
        """
        ...

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Get structured completion using Instructor.

        Args:
            messages: Chat messages
            response_model: Pydantic model for response
            model: Model name override
            **kwargs: Additional parameters

        Returns:
            Structured response
        """
        ...


@runtime_checkable
class GovernancePolicyProtocol(Protocol):
    """Protocol for governance policies."""

    @property
    def name(self) -> str:
        """Policy name."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether policy is enabled."""
        ...

    async def evaluate(
        self,
        context: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Evaluate policy against context.

        Args:
            context: Evaluation context

        Returns:
            Tuple of (allowed, reason if denied)
        """
        ...


@runtime_checkable
class StateStoreProtocol(Protocol):
    """Protocol for PDCA state persistence."""

    async def save_state(self, agent_id: str, task_id: str, state: PDCAState) -> None:
        """Save PDCA state.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier
            state: PDCA state to save
        """
        ...

    async def load_state(self, agent_id: str, task_id: str) -> PDCAState | None:
        """Load PDCA state.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier

        Returns:
            Saved state or None if not found
        """
        ...

    async def delete_state(self, agent_id: str, task_id: str) -> None:
        """Delete PDCA state.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier
        """
        ...


@runtime_checkable
class ObservabilityProtocol(Protocol):
    """Protocol for observability (tracing, metrics, logging)."""

    def start_span(self, name: str, **attributes: Any) -> Any:
        """Start a new trace span.

        Args:
            name: Span name
            **attributes: Span attributes

        Returns:
            Span context manager
        """
        ...

    def record_metric(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
        """
        ...

    def log(
        self,
        level: str,
        message: str,
        **context: Any,
    ) -> None:
        """Log a message with context.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **context: Additional context
        """
        ...
