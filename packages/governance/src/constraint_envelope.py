"""Per-run constraint enforcement with FAIL-CLOSED semantics.

Unlike BudgetManager (aggregate tracking), ConstraintEnvelope + RuntimeBudgetTracker
enforce hard limits on a single agent run().
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from packages.core.src.errors import BudgetExceededError

if TYPE_CHECKING:
    from packages.database.src.models import SubscriptionTier


# Per-tier limits
# max_llm_calls is set to floor(max_dollars / COST_PER_LLM_CALL_USD) so both
# limits are reachable independently. Dollar limit fires first for expensive
# models; call limit fires first for cheaper models (mini, haiku, etc.).
TIER_LIMITS = {
    "FREE":  {"max_dollars": 0.50, "max_llm_calls": 8,   "max_duration_seconds": 60.0},
    "TIER1": {"max_dollars": 2.00, "max_llm_calls": 33,  "max_duration_seconds": 180.0},
    "TIER2": {"max_dollars": 10.00, "max_llm_calls": 166, "max_duration_seconds": 600.0},
}

# Approximate USD cost per LLM call (gpt-4o ~2K tokens avg)
COST_PER_LLM_CALL_USD = 0.06


@dataclass
class ConstraintEnvelope:
    """Defines the budget constraints for a single analysis run."""

    tier_name: str
    max_dollars: float
    max_llm_calls: int
    max_duration_seconds: float

    @classmethod
    def for_tier(cls, tier: SubscriptionTier) -> ConstraintEnvelope:
        """Create envelope from a SubscriptionTier enum value."""
        limits = TIER_LIMITS.get(tier.name, TIER_LIMITS["FREE"])
        return cls(
            tier_name=tier.name,
            max_dollars=limits["max_dollars"],
            max_llm_calls=limits["max_llm_calls"],
            max_duration_seconds=limits["max_duration_seconds"],
        )

    @classmethod
    def for_tier_name(cls, tier_name: str) -> ConstraintEnvelope:
        """Create envelope from tier name string (for testing)."""
        limits = TIER_LIMITS.get(tier_name, TIER_LIMITS["FREE"])
        return cls(
            tier_name=tier_name,
            max_dollars=limits["max_dollars"],
            max_llm_calls=limits["max_llm_calls"],
            max_duration_seconds=limits["max_duration_seconds"],
        )


@dataclass
class RuntimeBudgetTracker:
    """Tracks spend for a single agent run(). Created fresh per run().

    Raises BudgetExceededError immediately when any limit is crossed.
    """

    envelope: ConstraintEnvelope
    agent_name: str = "unknown"
    _dollars_spent: float = field(default=0.0, init=False)
    _llm_calls: int = field(default=0, init=False)
    _start_time: float = field(default_factory=time.monotonic, init=False)

    def charge(self, llm_calls: int = 1, dollars: float | None = None) -> None:
        """Record LLM usage. Raises BudgetExceededError if over limit.

        Args:
            llm_calls: Number of LLM calls made (default 1)
            dollars: Explicit dollar cost. If None, estimated from llm_calls.
        """
        cost = dollars if dollars is not None else llm_calls * COST_PER_LLM_CALL_USD

        # Compute tentative new totals BEFORE mutating state.
        # Only commit if all checks pass so counters stay accurate after a caught exception.
        new_llm_calls = self._llm_calls + llm_calls
        new_dollars_spent = self._dollars_spent + cost

        # Check duration (does not depend on tentative totals)
        elapsed = time.monotonic() - self._start_time
        if elapsed > self.envelope.max_duration_seconds:
            raise BudgetExceededError(
                user_id=self.agent_name,
                budget=self.envelope.max_duration_seconds,
                spent=elapsed,
                currency="seconds",
            )

        # Check dollar limit
        if new_dollars_spent > self.envelope.max_dollars:
            raise BudgetExceededError(
                user_id=self.agent_name,
                budget=self.envelope.max_dollars,
                spent=new_dollars_spent,
                currency="USD",
            )

        # Check call limit
        if new_llm_calls > self.envelope.max_llm_calls:
            raise BudgetExceededError(
                user_id=self.agent_name,
                budget=float(self.envelope.max_llm_calls),
                spent=float(new_llm_calls),
                currency="llm_calls",
            )

        # All checks passed — commit
        self._llm_calls = new_llm_calls
        self._dollars_spent = new_dollars_spent

    @property
    def dollars_spent(self) -> float:
        return round(self._dollars_spent, 4)

    @property
    def llm_calls(self) -> int:
        return self._llm_calls

    @property
    def elapsed_seconds(self) -> float:
        return round(time.monotonic() - self._start_time, 2)

    @property
    def remaining_dollars(self) -> float:
        return round(max(0.0, self.envelope.max_dollars - self._dollars_spent), 4)

    def is_within_budget(self) -> bool:
        """Returns True if capacity remains on all limits (next call may succeed).

        Uses direct state comparison with >= so that hitting a limit exactly
        (e.g. _llm_calls == max_llm_calls) is correctly reported as exhausted.
        The probe-via-charge(0) approach missed this boundary because charge()
        uses strict > and adding 0 never crosses it.
        """
        elapsed = time.monotonic() - self._start_time
        return (
            elapsed < self.envelope.max_duration_seconds
            and self._dollars_spent < self.envelope.max_dollars
            and self._llm_calls < self.envelope.max_llm_calls
        )

    def summary(self) -> dict:
        return {
            "tier": self.envelope.tier_name,
            "dollars_spent": self.dollars_spent,
            "dollars_budget": self.envelope.max_dollars,
            "llm_calls": self.llm_calls,
            "llm_calls_budget": self.envelope.max_llm_calls,
            "elapsed_seconds": self.elapsed_seconds,
            "duration_budget": self.envelope.max_duration_seconds,
        }
