"""Unit tests for BaseGTMAgent PDCA loop, run(), and fast_execute()."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.core.src.base_agent import BaseGTMAgent
from packages.core.src.errors import AgentError, MaxIterationsExceededError
from packages.core.src.types import (
    AgentStatus,
    ExecutionMode,
    FastPathConfig,
    FastPathRule,
)

# =============================================================================
# Concrete mock agent for testing
# =============================================================================


class MockGTMAgent(BaseGTMAgent[dict]):
    """Concrete subclass of BaseGTMAgent with configurable confidence sequence."""

    def __init__(self, confidence_sequence=None, llm_manager=None):
        super().__init__(
            name="mock-agent",
            description="Test agent",
            result_type=dict,
            llm_manager=llm_manager or AsyncMock(),
        )
        self._confidence_sequence = confidence_sequence or [0.9]
        self._call_count = 0

    async def _plan(self, task, context=None, **kwargs):
        return {"strategy": "test"}

    async def _do(self, plan, context=None, **kwargs):
        return {"data": "result", "call": self._call_count}

    async def _check(self, result):
        conf = self._confidence_sequence[self._call_count % len(self._confidence_sequence)]
        self._call_count += 1
        return conf

    async def _act(self, result, confidence):
        return result


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pdca_completes_on_first_try():
    """Agent with high confidence should return on iteration 0 without retries."""
    agent = MockGTMAgent(confidence_sequence=[0.9])

    result = await agent.run("Test task")

    assert result == {"data": "result", "call": 0}
    assert agent._call_count == 1
    assert agent.status == AgentStatus.COMPLETED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retries_when_confidence_below_threshold():
    """Agent should retry when first confidence is below threshold, succeed on second."""
    # default min_confidence is 0.85; first call returns 0.5 (retry), second 0.9 (accept)
    agent = MockGTMAgent(confidence_sequence=[0.5, 0.9])

    result = await agent.run("Test task")

    # _call_count is incremented inside _check, so 2 means two check calls
    assert agent._call_count == 2
    assert result["data"] == "result"
    assert agent.status == AgentStatus.COMPLETED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_raises_max_iterations_exceeded():
    """Agent should raise MaxIterationsExceededError after exhausting all iterations."""
    agent = MockGTMAgent(confidence_sequence=[0.3, 0.3, 0.3])
    agent.max_iterations = 3

    with pytest.raises(MaxIterationsExceededError) as exc_info:
        await agent.run("Test task")

    error = exc_info.value
    assert error.details["agent_name"] == "mock-agent"
    assert error.details["iterations"] == 3
    assert error.details["final_confidence"] == pytest.approx(0.3)
    assert agent.status == AgentStatus.FAILED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_status_transitions_are_correct_sequence():
    """Status should flow PLANNING -> EXECUTING -> CHECKING -> ADJUSTING -> COMPLETED."""
    observed_statuses: list[AgentStatus] = []

    class StatusTrackingAgent(MockGTMAgent):
        async def _plan(self, task, context=None, **kwargs):
            observed_statuses.append(self.status)  # should be PLANNING
            return await super()._plan(task, context, **kwargs)

        async def _do(self, plan, context=None, **kwargs):
            observed_statuses.append(self.status)  # should be EXECUTING
            return await super()._do(plan, context, **kwargs)

        async def _check(self, result):
            observed_statuses.append(self.status)  # should be CHECKING
            return await super()._check(result)

        async def _act(self, result, confidence):
            observed_statuses.append(self.status)  # should be ADJUSTING
            return await super()._act(result, confidence)

    agent = StatusTrackingAgent(confidence_sequence=[0.9])
    await agent.run("Test task")

    assert observed_statuses[0] == AgentStatus.PLANNING
    assert observed_statuses[1] == AgentStatus.EXECUTING
    assert observed_statuses[2] == AgentStatus.CHECKING
    assert observed_statuses[3] == AgentStatus.ADJUSTING
    assert agent.status == AgentStatus.COMPLETED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_wraps_unexpected_exception():
    """An unexpected exception inside _do should be wrapped in AgentError."""
    agent = MockGTMAgent(confidence_sequence=[0.9])

    async def exploding_do(_plan, _context=None, **_kwargs):
        raise ValueError("something went wrong internally")

    agent._do = exploding_do

    with pytest.raises(AgentError) as exc_info:
        await agent.run("Test task")

    assert "mock-agent" in str(exc_info.value)
    assert agent.status == AgentStatus.FAILED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fast_execute_calls_plan_and_do():
    """fast_execute() in FAST mode should call _plan and _do exactly once, skip _check."""
    agent = MockGTMAgent(confidence_sequence=[0.9])

    plan_mock = AsyncMock(return_value={"strategy": "fast"})
    do_mock = AsyncMock(return_value={"data": "fast_result"})
    check_mock = AsyncMock(return_value=0.9)

    agent._plan = plan_mock
    agent._do = do_mock
    agent._check = check_mock

    result = await agent.fast_execute({"task": "quick task"}, mode=ExecutionMode.FAST)

    plan_mock.assert_awaited_once()
    do_mock.assert_awaited_once()
    check_mock.assert_not_awaited()
    assert result == {"data": "fast_result"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ultra_fast_uses_rules():
    """fast_execute() in ULTRA_FAST mode should return rule output without LLM calls."""

    class RuleBasedResult(dict):
        """dict subclass that supports model_validate for ultra-fast path."""

        @classmethod
        def model_validate(cls, data):
            return cls(data)

    class RuleAgent(BaseGTMAgent[RuleBasedResult]):
        def __init__(self):
            fp_config = FastPathConfig(
                enabled=True,
                rules=[
                    FastPathRule(
                        name="small-company-rule",
                        conditions={"company_size": "small"},
                        output={"tier": "starter", "recommended_channels": ["email", "linkedin"]},
                        priority=10,
                    )
                ],
                fallback_to_standard=False,
            )
            super().__init__(
                name="rule-agent",
                description="Rule-based test agent",
                result_type=RuleBasedResult,
                fast_path_config=fp_config,
                llm_manager=AsyncMock(),
            )

        async def _plan(self, task, context=None, **kwargs):
            return {}

        async def _do(self, plan, context=None, **kwargs):
            return RuleBasedResult({"data": "llm_result"})

        async def _check(self, result):
            return 0.9

    agent = RuleAgent()
    context = {"company_size": "small", "task": "fast analysis"}

    result = await agent.fast_execute(context, mode=ExecutionMode.ULTRA_FAST)

    assert result["tier"] == "starter"
    assert "email" in result["recommended_channels"]
