"""Base GTM Agent with PDCA (Plan-Do-Check-Act) pattern.

All GTM Advisor agents inherit from this base class to ensure:
- Self-correcting execution with confidence thresholds
- Structured outputs via Instructor
- Observability hooks
- Consistent error handling
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import uuid4

import structlog

from packages.core.src.errors import AgentError, MaxIterationsExceededError
from packages.core.src.types import (
    AgentStatus,
    ConfidenceLevel,
    ExecutionMode,
    FastPathConfig,
    FastPathRule,
    PDCAPhase,
    PDCAState,
    confidence_to_level,
)
from packages.llm.src import LLMManager, get_llm_manager

T = TypeVar("T")

logger = structlog.get_logger()


class AgentCapability:
    """Describes a capability of an agent."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}


class BaseGTMAgent(ABC, Generic[T]):
    """Base class for all GTM Advisor agents.

    Implements the PDCA (Plan-Do-Check-Act) cycle for self-correcting execution.

    Type Parameters:
        T: The result type (Pydantic model) that this agent produces

    Example:
        ```python
        class MarketResearchAgent(BaseGTMAgent[MarketInsight]):
            def __init__(self):
                super().__init__(
                    name="market-research",
                    description="Researches market trends and insights",
                    result_type=MarketInsight,
                )

            async def _plan(self, task: str) -> dict:
                return {"sources": ["perplexity", "newsapi"], "focus": "singapore"}

            async def _do(self, plan: dict) -> MarketInsight:
                # Execute research
                return await self._complete_structured(MarketInsight, messages)

            async def _check(self, result: MarketInsight) -> float:
                return result.confidence

            async def _act(self, result: MarketInsight, confidence: float) -> MarketInsight:
                if confidence >= self.min_confidence:
                    return result
                # Adjust and retry
                return await self._refine(result)
        ```
    """

    def __init__(
        self,
        name: str,
        description: str,
        result_type: type[T],
        *,
        min_confidence: float = 0.85,
        max_iterations: int = 3,
        model: str = "gpt-4o",
        capabilities: list[AgentCapability] | None = None,
        fast_path_config: FastPathConfig | None = None,
        llm_manager: LLMManager | None = None,
    ) -> None:
        """Initialize agent.

        Args:
            name: Agent name (kebab-case)
            description: What this agent does
            result_type: Pydantic model for results
            min_confidence: Minimum confidence to accept result (0-1)
            max_iterations: Maximum PDCA iterations
            model: Default LLM model
            capabilities: List of agent capabilities
            fast_path_config: Configuration for fast execution
            llm_manager: Optional LLM manager instance
        """
        self.name = name
        self.description = description
        self.result_type = result_type
        self.min_confidence = min_confidence
        self.max_iterations = max_iterations
        self.model = model
        self.capabilities = capabilities or []
        self.fast_path_config = fast_path_config

        self._llm_manager = llm_manager or get_llm_manager()
        self._status = AgentStatus.IDLE
        self._current_state: PDCAState | None = None
        self._logger = logger.bind(agent=name)

    @property
    def status(self) -> AgentStatus:
        """Current agent status."""
        return self._status

    @property
    def llm(self) -> LLMManager:
        """Get LLM manager."""
        return self._llm_manager

    async def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute agent with full PDCA cycle.

        This is the main entry point for agent execution.

        Args:
            task: Task description
            context: Additional context for execution
            **kwargs: Additional parameters

        Returns:
            Typed result based on result_type

        Raises:
            MaxIterationsExceededError: If max iterations reached without confidence
            AgentError: If execution fails
        """
        task_id = str(uuid4())
        context = context or {}
        start_time = time.time()

        self._logger.info(
            "agent_started",
            task_id=task_id,
            task=task[:100],
        )

        # Initialize state
        self._current_state = PDCAState(
            phase=PDCAPhase.PLAN,
            iteration=0,
            started_at=datetime.utcnow(),
        )
        self._status = AgentStatus.PLANNING

        try:
            result: T | None = None
            confidence = 0.0

            for iteration in range(self.max_iterations):
                self._current_state.iteration = iteration

                # PLAN
                self._status = AgentStatus.PLANNING
                self._current_state.phase = PDCAPhase.PLAN
                plan = await self._plan(task, context, **kwargs)
                self._current_state.plan = plan

                self._logger.debug(
                    "plan_created",
                    iteration=iteration,
                    plan_keys=list(plan.keys()) if plan else [],
                )

                # DO
                self._status = AgentStatus.EXECUTING
                self._current_state.phase = PDCAPhase.DO
                result = await self._do(plan, context, **kwargs)
                self._current_state.result = (
                    result.model_dump() if hasattr(result, "model_dump") else {}
                )

                # CHECK
                self._status = AgentStatus.CHECKING
                self._current_state.phase = PDCAPhase.CHECK
                confidence = await self._check(result)
                self._current_state.confidence = confidence

                self._logger.info(
                    "check_completed",
                    iteration=iteration,
                    confidence=confidence,
                    level=confidence_to_level(confidence).value,
                )

                # ACT
                self._status = AgentStatus.ADJUSTING
                self._current_state.phase = PDCAPhase.ACT

                if confidence >= self.min_confidence:
                    # Accept result
                    result = await self._act(result, confidence)
                    self._status = AgentStatus.COMPLETED
                    self._current_state.completed_at = datetime.utcnow()

                    elapsed = time.time() - start_time
                    self._logger.info(
                        "agent_completed",
                        task_id=task_id,
                        iterations=iteration + 1,
                        confidence=confidence,
                        elapsed_seconds=elapsed,
                    )
                    return result

                # Need adjustment - continue loop
                adjustment = f"Iteration {iteration + 1}: confidence {confidence:.2f} < {self.min_confidence}"
                self._current_state.adjustments.append(adjustment)

                self._logger.info(
                    "adjusting",
                    iteration=iteration,
                    confidence=confidence,
                    threshold=self.min_confidence,
                )

            # Max iterations reached
            self._status = AgentStatus.FAILED
            raise MaxIterationsExceededError(
                agent_name=self.name,
                iterations=self.max_iterations,
                final_confidence=confidence,
                threshold=self.min_confidence,
            )

        except MaxIterationsExceededError:
            raise
        except Exception as e:
            self._status = AgentStatus.FAILED
            self._current_state.error = str(e) if self._current_state else None
            self._logger.error(
                "agent_failed",
                task_id=task_id,
                error=str(e),
            )
            raise AgentError(f"Agent {self.name} failed: {e}") from e

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
            Result of fast execution
        """
        if mode == ExecutionMode.ULTRA_FAST:
            return await self._ultra_fast_execute(context)
        else:
            return await self._fast_execute(context)

    async def _fast_execute(self, context: dict[str, Any]) -> T:
        """Single LLM call execution (no PDCA loop)."""
        # Subclasses should override for optimized fast path
        task = context.get("task", str(context))
        plan = await self._plan(task, context)
        return await self._do(plan, context)

    async def _ultra_fast_execute(self, context: dict[str, Any]) -> T:
        """Rule-based execution without LLM calls."""
        if not self.fast_path_config or not self.fast_path_config.enabled:
            if self.fast_path_config and self.fast_path_config.fallback_to_standard:
                return await self._fast_execute(context)
            raise AgentError(f"Fast path not configured for {self.name}")

        # Evaluate rules by priority
        sorted_rules = sorted(
            self.fast_path_config.rules,
            key=lambda r: r.priority,
            reverse=True,
        )

        for rule in sorted_rules:
            if self._evaluate_rule(rule, context):
                self._logger.debug(
                    "fast_path_rule_matched",
                    rule=rule.name,
                )
                # Convert rule output to result type
                return self.result_type.model_validate(rule.output)

        # No rules matched
        if self.fast_path_config.fallback_to_standard:
            return await self._fast_execute(context)

        raise AgentError(f"No matching fast path rules for {self.name}")

    def _evaluate_rule(self, rule: FastPathRule, context: dict[str, Any]) -> bool:
        """Evaluate if a rule matches the context."""
        for key, condition in rule.conditions.items():
            if key not in context:
                return False

            value = context[key]

            # Handle range conditions (tuple)
            if isinstance(condition, tuple) and len(condition) == 2:
                min_val, max_val = condition
                if not (min_val <= value <= max_val):
                    return False
            # Handle exact match
            elif value != condition:
                return False

        return True

    # ==========================================================================
    # PDCA Methods - Must be implemented by subclasses
    # ==========================================================================

    @abstractmethod
    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """PLAN phase: Analyze task and create execution plan.

        Args:
            task: Task description
            context: Additional context
            **kwargs: Additional parameters

        Returns:
            Execution plan dictionary
        """
        ...

    @abstractmethod
    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> T:
        """DO phase: Execute the plan.

        Args:
            plan: Execution plan from _plan()
            context: Additional context
            **kwargs: Additional parameters

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

    async def _act(self, result: T, confidence: float) -> T:
        """ACT phase: Accept, adjust, or escalate based on confidence.

        Default implementation just returns result.
        Override for custom adjustment logic.

        Args:
            result: Result from _do()
            confidence: Confidence score from _check()

        Returns:
            Final or adjusted result
        """
        return result

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    async def _complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Get completion from LLM.

        Args:
            messages: Chat messages
            model: Model override
            **kwargs: Additional parameters

        Returns:
            Completion text
        """
        return await self.llm.complete(
            messages=messages,
            model=model or self.model,
            **kwargs,
        )

    async def _complete_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Get structured completion using Instructor.

        Args:
            response_model: Pydantic model for response
            messages: Chat messages
            model: Model override
            **kwargs: Additional parameters

        Returns:
            Structured response
        """
        return await self.llm.complete_structured(
            messages=messages,
            response_model=response_model,
            model=model or self.model,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        """Get default system prompt for this agent.

        Override in subclasses for custom prompts.

        Returns:
            System prompt string
        """
        return f"""You are {self.name}, a specialized AI agent.

{self.description}

Guidelines:
- Provide accurate, actionable information
- Use data and sources when available
- Be specific and concrete, avoid generic advice
- Focus on the Singapore/APAC market context
- Maintain professional, consultant-like communication

When uncertain, clearly indicate confidence level."""

    def to_card(self) -> dict[str, Any]:
        """Convert agent to dashboard card format.

        Returns:
            Card data for UI display
        """
        return {
            "name": self.name,
            "title": self.name.replace("-", " ").title(),
            "description": self.description,
            "status": self.status.value,
            "capabilities": [
                {"name": c.name, "description": c.description}
                for c in self.capabilities
            ],
            "confidence_threshold": self.min_confidence,
            "model": self.model,
        }
