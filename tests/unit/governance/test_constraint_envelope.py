"""Unit tests for ConstraintEnvelope and RuntimeBudgetTracker."""

from __future__ import annotations

import pytest

from packages.core.src.errors import BudgetExceededError
from packages.governance.src.constraint_envelope import (
    TIER_LIMITS,
    ConstraintEnvelope,
    RuntimeBudgetTracker,
)

# =============================================================================
# ConstraintEnvelope tests
# =============================================================================


@pytest.mark.unit
class TestConstraintEnvelope:
    def test_for_tier_name_free(self):
        env = ConstraintEnvelope.for_tier_name("FREE")
        assert env.tier_name == "FREE"
        assert env.max_dollars == TIER_LIMITS["FREE"]["max_dollars"]
        assert env.max_llm_calls == TIER_LIMITS["FREE"]["max_llm_calls"]
        assert env.max_duration_seconds == TIER_LIMITS["FREE"]["max_duration_seconds"]

    def test_for_tier_name_tier1(self):
        env = ConstraintEnvelope.for_tier_name("TIER1")
        assert env.max_dollars == TIER_LIMITS["TIER1"]["max_dollars"]
        assert env.max_llm_calls == TIER_LIMITS["TIER1"]["max_llm_calls"]

    def test_for_tier_name_tier2(self):
        env = ConstraintEnvelope.for_tier_name("TIER2")
        assert env.max_dollars == TIER_LIMITS["TIER2"]["max_dollars"]
        assert env.max_llm_calls == TIER_LIMITS["TIER2"]["max_llm_calls"]

    def test_for_tier_name_invalid_defaults_to_free(self):
        env = ConstraintEnvelope.for_tier_name("UNKNOWN_TIER")
        assert env.max_dollars == TIER_LIMITS["FREE"]["max_dollars"]
        assert env.max_llm_calls == TIER_LIMITS["FREE"]["max_llm_calls"]

    def test_tier_limits_coherent(self):
        """Verify max_llm_calls is reachable within dollar budget."""
        from packages.governance.src.constraint_envelope import COST_PER_LLM_CALL_USD

        for tier_name, limits in TIER_LIMITS.items():
            max_calls_by_dollar = limits["max_dollars"] / COST_PER_LLM_CALL_USD
            # max_llm_calls should be <= floor(max_dollars / cost_per_call)
            # so the call limit is independently reachable
            assert limits["max_llm_calls"] <= max_calls_by_dollar + 1, (
                f"{tier_name}: max_llm_calls {limits['max_llm_calls']} exceeds "
                f"dollar capacity {max_calls_by_dollar:.1f}"
            )


# =============================================================================
# RuntimeBudgetTracker tests
# =============================================================================


@pytest.mark.unit
class TestRuntimeBudgetTracker:
    def _make_tracker(self, tier_name="FREE") -> RuntimeBudgetTracker:
        env = ConstraintEnvelope.for_tier_name(tier_name)
        return RuntimeBudgetTracker(envelope=env, agent_name="test-agent")

    def test_charge_success_commits_state(self):
        tracker = self._make_tracker()
        tracker.charge(llm_calls=1)
        assert tracker.llm_calls == 1

    def test_charge_explicit_dollars(self):
        tracker = self._make_tracker()
        tracker.charge(llm_calls=0, dollars=0.10)
        assert tracker.dollars_spent == pytest.approx(0.10, abs=1e-4)

    def test_charge_default_cost_estimated_from_calls(self):
        from packages.governance.src.constraint_envelope import COST_PER_LLM_CALL_USD

        tracker = self._make_tracker()
        tracker.charge(llm_calls=2)
        assert tracker.dollars_spent == pytest.approx(2 * COST_PER_LLM_CALL_USD, abs=1e-4)

    def test_charge_raises_on_dollar_limit(self):
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=0.10, max_llm_calls=100, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.charge(dollars=0.11)
        assert exc_info.value.details.get("currency") == "USD"

    def test_charge_raises_on_call_limit(self):
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=100.0, max_llm_calls=3, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        tracker.charge(llm_calls=3, dollars=0.0)
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.charge(llm_calls=1, dollars=0.0)
        assert exc_info.value.details.get("currency") == "llm_calls"

    def test_state_not_mutated_on_failed_charge(self):
        """FAIL-CLOSED: state must be unchanged when charge() raises."""
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=0.05, max_llm_calls=100, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        # First charge succeeds
        tracker.charge(llm_calls=0, dollars=0.04)
        assert tracker.dollars_spent == pytest.approx(0.04, abs=1e-4)
        # Second charge would exceed budget — should not mutate state
        with pytest.raises(BudgetExceededError):
            tracker.charge(llm_calls=0, dollars=0.02)
        # State must be unchanged
        assert tracker.dollars_spent == pytest.approx(0.04, abs=1e-4)
        assert tracker.llm_calls == 0

    def test_is_within_budget_fresh_tracker(self):
        tracker = self._make_tracker()
        assert tracker.is_within_budget() is True

    def test_is_within_budget_at_exact_call_limit(self):
        """Hitting max_llm_calls exactly should be reported as exhausted."""
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=100.0, max_llm_calls=3, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        tracker.charge(llm_calls=3, dollars=0.0)
        assert tracker.is_within_budget() is False

    def test_is_within_budget_at_exact_dollar_limit(self):
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=0.10, max_llm_calls=100, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        tracker.charge(llm_calls=0, dollars=0.10)
        assert tracker.is_within_budget() is False

    def test_remaining_dollars_decreases_on_charge(self):
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=1.00, max_llm_calls=100, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        tracker.charge(llm_calls=0, dollars=0.30)
        assert tracker.remaining_dollars == pytest.approx(0.70, abs=1e-4)

    def test_remaining_dollars_never_negative(self):
        env = ConstraintEnvelope(
            tier_name="TEST", max_dollars=0.10, max_llm_calls=100, max_duration_seconds=60.0
        )
        tracker = RuntimeBudgetTracker(envelope=env)
        tracker.charge(llm_calls=0, dollars=0.10)
        assert tracker.remaining_dollars == 0.0

    def test_summary_contains_all_fields(self):
        tracker = self._make_tracker()
        summary = tracker.summary()
        for key in ("tier", "dollars_spent", "dollars_budget", "llm_calls", "llm_calls_budget",
                    "elapsed_seconds", "duration_budget"):
            assert key in summary, f"Missing key: {key}"
