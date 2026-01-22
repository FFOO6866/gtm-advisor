"""Rule Engine for Deterministic Decision Making.

Provides a declarative rule system for:
- Lead routing and prioritization
- Alert triggers
- Workflow automation
- Policy enforcement

Rules execute in priority order and can chain together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum
import operator
import re


class Operator(Enum):
    """Comparison operators for rule conditions."""
    EQ = "eq"  # equals
    NE = "ne"  # not equals
    GT = "gt"  # greater than
    GE = "ge"  # greater or equal
    LT = "lt"  # less than
    LE = "le"  # less or equal
    IN = "in"  # value in list
    NOT_IN = "not_in"  # value not in list
    CONTAINS = "contains"  # string contains
    MATCHES = "matches"  # regex match
    EXISTS = "exists"  # field exists
    NOT_EXISTS = "not_exists"  # field doesn't exist


class Action(Enum):
    """Actions that rules can trigger."""
    ASSIGN = "assign"  # Assign a value
    INCREMENT = "increment"  # Increment a counter
    NOTIFY = "notify"  # Trigger notification
    ROUTE = "route"  # Route to destination
    FLAG = "flag"  # Add a flag
    ESCALATE = "escalate"  # Escalate for review
    BLOCK = "block"  # Block processing
    LOG = "log"  # Log event


@dataclass
class Condition:
    """A single condition in a rule."""
    field: str
    operator: Operator
    value: Any

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        # Handle nested field access (e.g., "company.industry")
        field_value = self._get_nested_value(context, self.field)

        # Handle existence checks
        if self.operator == Operator.EXISTS:
            return field_value is not None
        if self.operator == Operator.NOT_EXISTS:
            return field_value is None

        # If field doesn't exist and we're not checking existence, condition fails
        if field_value is None:
            return False

        # Comparison operators
        ops = {
            Operator.EQ: operator.eq,
            Operator.NE: operator.ne,
            Operator.GT: operator.gt,
            Operator.GE: operator.ge,
            Operator.LT: operator.lt,
            Operator.LE: operator.le,
        }

        if self.operator in ops:
            try:
                return ops[self.operator](field_value, self.value)
            except TypeError:
                return False

        # Collection operators
        if self.operator == Operator.IN:
            return field_value in self.value
        if self.operator == Operator.NOT_IN:
            return field_value not in self.value

        # String operators
        if self.operator == Operator.CONTAINS:
            return str(self.value).lower() in str(field_value).lower()
        if self.operator == Operator.MATCHES:
            return bool(re.search(self.value, str(field_value), re.IGNORECASE))

        return False

    def _get_nested_value(self, data: dict[str, Any], field: str) -> Any:
        """Get value from nested dict using dot notation."""
        parts = field.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
        }


@dataclass
class RuleAction:
    """An action to execute when rule matches."""
    action: Action
    target: str  # What to act on
    value: Any = None  # Value for the action
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "target": self.target,
            "value": self.value,
            "metadata": self.metadata,
        }


@dataclass
class RuleResult:
    """Result of rule evaluation."""
    rule_id: str
    rule_name: str
    matched: bool
    actions_triggered: list[RuleAction]
    context_modifications: dict[str, Any]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "matched": self.matched,
            "actions_triggered": [a.to_dict() for a in self.actions_triggered],
            "context_modifications": self.context_modifications,
            "explanation": self.explanation,
        }


@dataclass
class Rule:
    """A business rule with conditions and actions."""
    id: str
    name: str
    description: str
    conditions: list[Condition]
    actions: list[RuleAction]
    priority: int = 0  # Higher = executes first
    enabled: bool = True
    stop_on_match: bool = False  # If True, stop processing further rules
    tags: list[str] = field(default_factory=list)

    def evaluate(self, context: dict[str, Any]) -> RuleResult:
        """Evaluate rule against context."""
        if not self.enabled:
            return RuleResult(
                rule_id=self.id,
                rule_name=self.name,
                matched=False,
                actions_triggered=[],
                context_modifications={},
                explanation="Rule is disabled",
            )

        # All conditions must match (AND logic)
        all_match = all(cond.evaluate(context) for cond in self.conditions)

        if all_match:
            # Execute actions and collect modifications
            modifications = {}
            for action in self.actions:
                if action.action == Action.ASSIGN:
                    modifications[action.target] = action.value
                elif action.action == Action.INCREMENT:
                    current = context.get(action.target, 0)
                    modifications[action.target] = current + (action.value or 1)
                elif action.action == Action.FLAG:
                    flags = context.get("_flags", [])
                    modifications["_flags"] = flags + [action.target]

            return RuleResult(
                rule_id=self.id,
                rule_name=self.name,
                matched=True,
                actions_triggered=self.actions,
                context_modifications=modifications,
                explanation=f"Rule matched: {self.description}",
            )
        else:
            return RuleResult(
                rule_id=self.id,
                rule_name=self.name,
                matched=False,
                actions_triggered=[],
                context_modifications={},
                explanation="Conditions not met",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": [a.to_dict() for a in self.actions],
            "priority": self.priority,
            "enabled": self.enabled,
            "stop_on_match": self.stop_on_match,
            "tags": self.tags,
        }


class RuleEngine:
    """Execute rules against data with full audit trail.

    Example usage:
        engine = RuleEngine()

        # Add lead routing rules
        engine.add_rule(Rule(
            id="high_value_lead",
            name="High Value Lead Routing",
            description="Route high-value leads to senior sales",
            conditions=[
                Condition("lead_score", Operator.GE, 80),
                Condition("company.employee_count", Operator.GE, 100),
            ],
            actions=[
                RuleAction(Action.ROUTE, "senior_sales"),
                RuleAction(Action.FLAG, "high_priority"),
            ],
            priority=100,
        ))

        # Execute
        results = engine.execute(lead_context)
    """

    def __init__(self):
        self.rules: list[Rule] = []
        self._execution_log: list[dict[str, Any]] = []

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules.append(rule)
        # Keep sorted by priority (descending)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rules(self, rules: list[Rule]) -> None:
        """Add multiple rules."""
        for rule in rules:
            self.add_rule(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                del self.rules[i]
                return True
        return False

    def get_rule(self, rule_id: str) -> Rule | None:
        """Get a rule by ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def execute(
        self,
        context: dict[str, Any],
        tags: list[str] | None = None,
    ) -> list[RuleResult]:
        """Execute all matching rules against context.

        Args:
            context: Data to evaluate against rules
            tags: Optional filter - only run rules with these tags

        Returns:
            List of rule results (matched and unmatched)
        """
        results = []
        working_context = context.copy()

        for rule in self.rules:
            # Filter by tags if specified
            if tags and not any(t in rule.tags for t in tags):
                continue

            # Evaluate rule
            result = rule.evaluate(working_context)
            results.append(result)

            # Apply context modifications
            if result.matched:
                working_context.update(result.context_modifications)

                # Stop processing if rule says so
                if rule.stop_on_match:
                    break

        # Log execution
        self._execution_log.append({
            "input_context": context,
            "results": [r.to_dict() for r in results],
            "final_context": working_context,
        })

        return results

    def execute_until_match(
        self,
        context: dict[str, Any],
        tags: list[str] | None = None,
    ) -> RuleResult | None:
        """Execute rules until first match.

        Useful for routing decisions where you want the first matching rule.
        """
        for rule in self.rules:
            if tags and not any(t in rule.tags for t in tags):
                continue

            result = rule.evaluate(context)
            if result.matched:
                return result

        return None

    def get_matching_rules(
        self,
        context: dict[str, Any],
        tags: list[str] | None = None,
    ) -> list[Rule]:
        """Get all rules that would match the context."""
        matching = []
        for rule in self.rules:
            if tags and not any(t in rule.tags for t in tags):
                continue
            if rule.evaluate(context).matched:
                matching.append(rule)
        return matching

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Get audit log of all executions."""
        return self._execution_log.copy()

    def clear_execution_log(self) -> None:
        """Clear the execution log."""
        self._execution_log = []

    def to_dict(self) -> dict[str, Any]:
        """Export engine configuration."""
        return {
            "rules": [r.to_dict() for r in self.rules],
            "rule_count": len(self.rules),
        }


# Pre-built rule sets for common GTM scenarios

def create_lead_routing_rules() -> list[Rule]:
    """Create standard lead routing rules."""
    return [
        Rule(
            id="enterprise_lead",
            name="Enterprise Lead Routing",
            description="Route enterprise leads to enterprise sales team",
            conditions=[
                Condition("company.employee_count", Operator.GE, 500),
            ],
            actions=[
                RuleAction(Action.ROUTE, "enterprise_sales"),
                RuleAction(Action.ASSIGN, "lead_tier", "enterprise"),
                RuleAction(Action.FLAG, "high_touch"),
            ],
            priority=100,
            tags=["routing", "lead"],
        ),
        Rule(
            id="mid_market_lead",
            name="Mid-Market Lead Routing",
            description="Route mid-market leads to commercial team",
            conditions=[
                Condition("company.employee_count", Operator.GE, 50),
                Condition("company.employee_count", Operator.LT, 500),
            ],
            actions=[
                RuleAction(Action.ROUTE, "commercial_sales"),
                RuleAction(Action.ASSIGN, "lead_tier", "mid_market"),
            ],
            priority=90,
            tags=["routing", "lead"],
        ),
        Rule(
            id="smb_lead",
            name="SMB Lead Routing",
            description="Route SMB leads to inside sales",
            conditions=[
                Condition("company.employee_count", Operator.LT, 50),
            ],
            actions=[
                RuleAction(Action.ROUTE, "inside_sales"),
                RuleAction(Action.ASSIGN, "lead_tier", "smb"),
            ],
            priority=80,
            tags=["routing", "lead"],
        ),
        Rule(
            id="hot_lead_escalation",
            name="Hot Lead Escalation",
            description="Escalate hot leads for immediate follow-up",
            conditions=[
                Condition("lead_score", Operator.GE, 85),
                Condition("engagement.demo_requested", Operator.EQ, True),
            ],
            actions=[
                RuleAction(Action.ESCALATE, "sales_manager"),
                RuleAction(Action.FLAG, "hot_lead"),
                RuleAction(Action.NOTIFY, "slack", {"channel": "#hot-leads"}),
            ],
            priority=150,
            tags=["escalation", "lead"],
        ),
    ]


def create_alert_rules() -> list[Rule]:
    """Create standard alert/notification rules."""
    return [
        Rule(
            id="competitor_mention",
            name="Competitor Mention Alert",
            description="Alert when competitor is mentioned in conversation",
            conditions=[
                Condition("transcript", Operator.MATCHES, r"\b(competitor1|competitor2)\b"),
            ],
            actions=[
                RuleAction(Action.FLAG, "competitor_mentioned"),
                RuleAction(Action.LOG, "competitor_analysis", {"source": "conversation"}),
            ],
            priority=50,
            tags=["alert", "competitive"],
        ),
        Rule(
            id="budget_signal",
            name="Budget Signal Detection",
            description="Flag when budget discussion detected",
            conditions=[
                Condition("transcript", Operator.MATCHES, r"budget|pricing|cost|invest"),
            ],
            actions=[
                RuleAction(Action.FLAG, "budget_discussed"),
                RuleAction(Action.ASSIGN, "buying_signal", True),
            ],
            priority=60,
            tags=["alert", "buying_signal"],
        ),
        Rule(
            id="churn_risk",
            name="Churn Risk Alert",
            description="Alert on churn risk indicators",
            conditions=[
                Condition("health_score", Operator.LT, 50),
                Condition("days_since_login", Operator.GT, 14),
            ],
            actions=[
                RuleAction(Action.ESCALATE, "customer_success"),
                RuleAction(Action.FLAG, "churn_risk"),
                RuleAction(Action.NOTIFY, "email", {"template": "churn_intervention"}),
            ],
            priority=100,
            tags=["alert", "churn"],
        ),
    ]


def create_qualification_rules() -> list[Rule]:
    """Create lead qualification rules (BANT-based)."""
    return [
        Rule(
            id="bant_qualified",
            name="BANT Qualified Lead",
            description="Lead meets all BANT criteria",
            conditions=[
                Condition("budget_confirmed", Operator.EQ, True),
                Condition("authority_level", Operator.IN, ["decision_maker", "economic_buyer"]),
                Condition("need_score", Operator.GE, 70),
                Condition("timeline_days", Operator.LE, 90),
            ],
            actions=[
                RuleAction(Action.ASSIGN, "qualification_status", "qualified"),
                RuleAction(Action.ASSIGN, "mql_status", True),
                RuleAction(Action.FLAG, "bant_qualified"),
            ],
            priority=100,
            tags=["qualification"],
        ),
        Rule(
            id="needs_nurture",
            name="Needs Nurturing",
            description="Lead needs more nurturing before sales ready",
            conditions=[
                Condition("need_score", Operator.LT, 50),
            ],
            actions=[
                RuleAction(Action.ASSIGN, "qualification_status", "nurture"),
                RuleAction(Action.ROUTE, "marketing_nurture"),
            ],
            priority=50,
            tags=["qualification"],
        ),
    ]
