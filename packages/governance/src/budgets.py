"""Budget and Cost Control.

Manages:
- LLM token budgets per agent
- API call limits
- Overall cost tracking
- Alerts when approaching limits

Principle: No unlimited spending.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class BudgetPeriod(Enum):
    """Budget reset periods."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class BudgetLimit:
    """A budget limit configuration."""

    id: str
    name: str
    limit_type: str  # "tokens", "api_calls", "dollars"
    limit_value: float
    period: BudgetPeriod
    agent_id: str | None = None  # None = applies to all
    tool_name: str | None = None  # None = applies to all
    alert_threshold: float = 0.8  # Alert at 80% usage
    hard_limit: bool = True  # If True, block when exceeded

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "limit_type": self.limit_type,
            "limit_value": self.limit_value,
            "period": self.period.value,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "alert_threshold": self.alert_threshold,
            "hard_limit": self.hard_limit,
        }


@dataclass
class UsageRecord:
    """A usage record."""

    timestamp: datetime
    agent_id: str | None
    tool_name: str | None
    usage_type: str  # tokens, api_calls, dollars
    amount: float
    metadata: dict[str, Any] = field(default_factory=dict)


class UsageTracker:
    """Tracks usage by agent, tool, and type."""

    def __init__(self):
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()

    def record(
        self,
        usage_type: str,
        amount: float,
        agent_id: str | None = None,
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record usage."""
        record = UsageRecord(
            timestamp=datetime.utcnow(),
            agent_id=agent_id,
            tool_name=tool_name,
            usage_type=usage_type,
            amount=amount,
            metadata=metadata or {},
        )
        with self._lock:
            self._records.append(record)

    def get_usage(
        self,
        usage_type: str,
        period: BudgetPeriod,
        agent_id: str | None = None,
        tool_name: str | None = None,
    ) -> float:
        """Get total usage for a period."""
        now = datetime.utcnow()

        # Calculate period start
        if period == BudgetPeriod.HOURLY:
            period_start = now - timedelta(hours=1)
        elif period == BudgetPeriod.DAILY:
            period_start = now - timedelta(days=1)
        elif period == BudgetPeriod.WEEKLY:
            period_start = now - timedelta(weeks=1)
        elif period == BudgetPeriod.MONTHLY:
            period_start = now - timedelta(days=30)
        else:
            period_start = now - timedelta(days=1)

        total = 0.0
        with self._lock:
            for record in self._records:
                if record.timestamp < period_start:
                    continue
                if record.usage_type != usage_type:
                    continue
                if agent_id and record.agent_id != agent_id:
                    continue
                if tool_name and record.tool_name != tool_name:
                    continue
                total += record.amount

        return total

    def get_usage_by_agent(
        self,
        usage_type: str,
        period: BudgetPeriod,
    ) -> dict[str, float]:
        """Get usage breakdown by agent."""
        now = datetime.utcnow()

        if period == BudgetPeriod.HOURLY:
            period_start = now - timedelta(hours=1)
        elif period == BudgetPeriod.DAILY:
            period_start = now - timedelta(days=1)
        elif period == BudgetPeriod.WEEKLY:
            period_start = now - timedelta(weeks=1)
        else:
            period_start = now - timedelta(days=30)

        by_agent: dict[str, float] = {}
        with self._lock:
            for record in self._records:
                if record.timestamp < period_start:
                    continue
                if record.usage_type != usage_type:
                    continue
                agent = record.agent_id or "unknown"
                by_agent[agent] = by_agent.get(agent, 0) + record.amount

        return by_agent

    def clear_old_records(self, older_than_days: int = 30) -> int:
        """Clear records older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        with self._lock:
            original_count = len(self._records)
            self._records = [r for r in self._records if r.timestamp >= cutoff]
            return original_count - len(self._records)


class BudgetManager:
    """Manages budgets and enforces limits.

    Example:
        budget = BudgetManager()

        # Set limits
        budget.add_limit(BudgetLimit(
            id="daily_tokens",
            name="Daily Token Limit",
            limit_type="tokens",
            limit_value=1_000_000,
            period=BudgetPeriod.DAILY,
            alert_threshold=0.8,
        ))

        budget.add_limit(BudgetLimit(
            id="lead_hunter_api",
            name="Lead Hunter API Calls",
            limit_type="api_calls",
            limit_value=100,
            period=BudgetPeriod.HOURLY,
            agent_id="lead_hunter",
        ))

        # Check before operation
        if budget.can_spend("tokens", 5000, agent_id="lead_hunter"):
            # proceed
            budget.spend("tokens", 5000, agent_id="lead_hunter")
    """

    def __init__(self):
        self._limits: dict[str, BudgetLimit] = {}
        self._tracker = UsageTracker()
        self._alert_callbacks: list[callable] = []

    @property
    def tracker(self) -> UsageTracker:
        """Get the usage tracker."""
        return self._tracker

    def add_limit(self, limit: BudgetLimit) -> None:
        """Add a budget limit."""
        self._limits[limit.id] = limit

    def remove_limit(self, limit_id: str) -> bool:
        """Remove a budget limit."""
        if limit_id in self._limits:
            del self._limits[limit_id]
            return True
        return False

    def get_limit(self, limit_id: str) -> BudgetLimit | None:
        """Get a limit by ID."""
        return self._limits.get(limit_id)

    def on_alert(self, callback: callable) -> None:
        """Register callback for budget alerts."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(
        self,
        limit: BudgetLimit,
        current_usage: float,
        usage_percent: float,
    ) -> None:
        """Trigger alert callbacks."""
        alert_data = {
            "limit_id": limit.id,
            "limit_name": limit.name,
            "limit_value": limit.limit_value,
            "current_usage": current_usage,
            "usage_percent": usage_percent,
            "agent_id": limit.agent_id,
            "tool_name": limit.tool_name,
        }
        for callback in self._alert_callbacks:
            try:
                callback(alert_data)
            except Exception:
                pass

    def can_spend(
        self,
        usage_type: str,
        amount: float,
        agent_id: str | None = None,
        tool_name: str | None = None,
    ) -> bool:
        """Check if spending is allowed under all applicable limits."""
        for limit in self._limits.values():
            if limit.limit_type != usage_type:
                continue

            # Check if limit applies
            if limit.agent_id and limit.agent_id != agent_id:
                continue
            if limit.tool_name and limit.tool_name != tool_name:
                continue

            # Get current usage
            current = self._tracker.get_usage(
                usage_type=usage_type,
                period=limit.period,
                agent_id=limit.agent_id,
                tool_name=limit.tool_name,
            )

            # Check if would exceed
            if current + amount > limit.limit_value:
                if limit.hard_limit:
                    return False

            # Check alert threshold
            usage_percent = (current + amount) / limit.limit_value
            if usage_percent >= limit.alert_threshold:
                self._trigger_alert(limit, current + amount, usage_percent)

        return True

    def spend(
        self,
        usage_type: str,
        amount: float,
        agent_id: str | None = None,
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Record spending and enforce limits.

        Returns True if spending was allowed, False if blocked.
        """
        if not self.can_spend(usage_type, amount, agent_id, tool_name):
            return False

        self._tracker.record(
            usage_type=usage_type,
            amount=amount,
            agent_id=agent_id,
            tool_name=tool_name,
            metadata=metadata,
        )
        return True

    def get_budget_status(
        self,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get status of all applicable budget limits."""
        status = []

        for limit in self._limits.values():
            # Filter by agent if specified
            if agent_id and limit.agent_id and limit.agent_id != agent_id:
                continue

            current = self._tracker.get_usage(
                usage_type=limit.limit_type,
                period=limit.period,
                agent_id=limit.agent_id,
                tool_name=limit.tool_name,
            )

            usage_percent = current / limit.limit_value if limit.limit_value > 0 else 0

            status.append(
                {
                    "limit_id": limit.id,
                    "limit_name": limit.name,
                    "limit_type": limit.limit_type,
                    "limit_value": limit.limit_value,
                    "period": limit.period.value,
                    "current_usage": round(current, 2),
                    "remaining": round(limit.limit_value - current, 2),
                    "usage_percent": round(usage_percent * 100, 1),
                    "at_alert_threshold": usage_percent >= limit.alert_threshold,
                    "exceeded": current >= limit.limit_value,
                }
            )

        return status

    def get_cost_summary(
        self,
        period: BudgetPeriod = BudgetPeriod.DAILY,
    ) -> dict[str, Any]:
        """Get cost summary for the period."""
        tokens = self._tracker.get_usage("tokens", period)
        api_calls = self._tracker.get_usage("api_calls", period)
        dollars = self._tracker.get_usage("dollars", period)

        by_agent_tokens = self._tracker.get_usage_by_agent("tokens", period)
        by_agent_calls = self._tracker.get_usage_by_agent("api_calls", period)

        return {
            "period": period.value,
            "total_tokens": tokens,
            "total_api_calls": api_calls,
            "total_dollars": round(dollars, 2),
            "tokens_by_agent": by_agent_tokens,
            "api_calls_by_agent": by_agent_calls,
            "estimated_cost_usd": round(self._estimate_cost(tokens, api_calls), 2),
        }

    def _estimate_cost(self, tokens: float, api_calls: float) -> float:
        """Estimate cost in USD.

        Uses approximate pricing:
        - GPT-4: $0.03/1K input, $0.06/1K output (assuming 50/50 split)
        - Enrichment APIs: ~$0.05 per call
        """
        # Rough estimate: $0.045 per 1K tokens average
        token_cost = (tokens / 1000) * 0.045

        # API calls: ~$0.05 each on average
        api_cost = api_calls * 0.05

        return token_cost + api_cost


# Pre-configured limits for GTM Advisor
def create_gtm_budget_limits() -> list[BudgetLimit]:
    """Create default budget limits."""
    return [
        # Global limits
        BudgetLimit(
            id="daily_tokens_global",
            name="Daily Token Limit (All Agents)",
            limit_type="tokens",
            limit_value=2_000_000,  # 2M tokens/day
            period=BudgetPeriod.DAILY,
            alert_threshold=0.8,
        ),
        BudgetLimit(
            id="daily_dollars_global",
            name="Daily Spend Limit",
            limit_type="dollars",
            limit_value=100,  # $100/day
            period=BudgetPeriod.DAILY,
            alert_threshold=0.9,
            hard_limit=True,
        ),
        # Per-agent limits
        BudgetLimit(
            id="lead_hunter_hourly",
            name="Lead Hunter Hourly API Calls",
            limit_type="api_calls",
            limit_value=50,
            period=BudgetPeriod.HOURLY,
            agent_id="lead_hunter",
        ),
        BudgetLimit(
            id="market_intel_daily",
            name="Market Intelligence Daily Tokens",
            limit_type="tokens",
            limit_value=500_000,
            period=BudgetPeriod.DAILY,
            agent_id="market_intelligence",
        ),
        # Tool-specific limits
        BudgetLimit(
            id="enrichment_daily",
            name="Enrichment API Daily Calls",
            limit_type="api_calls",
            limit_value=200,
            period=BudgetPeriod.DAILY,
            tool_name="company_enrichment",
        ),
        BudgetLimit(
            id="scraping_hourly",
            name="Web Scraping Hourly Limit",
            limit_type="api_calls",
            limit_value=30,
            period=BudgetPeriod.HOURLY,
            tool_name="web_scraper",
        ),
    ]
