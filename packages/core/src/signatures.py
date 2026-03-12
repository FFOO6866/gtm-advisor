"""Agent Signature I/O Contracts.

Declarative contracts that each agent registers to describe:
- Which DiscoveryTypes it emits to the bus
- Which DiscoveryTypes it consumes from the bus
- Which context keys it requires to run

Used by AgentBus.publish() to validate payload schema at runtime,
and by test harnesses / the orchestrator to detect wiring mismatches
before execution starts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.core.src.agent_bus import DiscoveryType


@dataclass
class AgentSignature:
    """Declarative I/O contract for an agent.

    Example::

        sig = AgentSignature(
            agent_name="market-intelligence",
            emits_discovery_types=[DiscoveryType.MARKET_TREND, DiscoveryType.MARKET_OPPORTUNITY],
            consumes_discovery_types=[DiscoveryType.COMPANY_PROFILE],
            required_context_keys=["company_name", "industry"],
        )
        register_signature(sig)
    """

    agent_name: str
    # None = unconstrained (no emit check). [] = no emissions allowed (strictest).
    emits_discovery_types: list[DiscoveryType] | None = field(default=None)
    consumes_discovery_types: list[DiscoveryType] = field(default_factory=list)
    required_context_keys: list[str] = field(default_factory=list)
    # Optional schema per DiscoveryType: {DiscoveryType: {field: type_name}}
    payload_schemas: dict[str, dict[str, str]] = field(default_factory=dict)

    def validate_payload(
        self,
        discovery_type: DiscoveryType,
        content: dict[str, Any],
    ) -> list[str]:
        """Return list of validation errors for a payload (empty = valid).

        Checks required fields declared in payload_schemas.
        """
        schema = self.payload_schemas.get(discovery_type.value)
        if not schema:
            return []  # No schema registered → allow anything

        safe_content: dict[str, Any] = content if content is not None else {}
        errors: list[str] = []
        _type_checks: dict[str, tuple] = {
            "str": (str,),
            "list": (list,),
            "float": (int, float),
            "int": (int,),
            "bool": (bool,),
            "dict": (dict,),
        }
        for field_name, type_name in schema.items():
            if field_name not in safe_content:
                errors.append(
                    f"[{self.agent_name}] Missing required field '{field_name}' "
                    f"in {discovery_type.value} payload"
                )
            elif type_name in _type_checks:
                expected = _type_checks[type_name]
                actual = safe_content[field_name]
                # bool is a subclass of int in Python; reject bool for int/float fields
                bool_reject = type_name in ("int", "float") and isinstance(actual, bool)
                if bool_reject or not isinstance(actual, expected):
                    errors.append(
                        f"[{self.agent_name}] Field '{field_name}' must be {type_name}"
                    )
        return errors

    def validate_context(self, context: dict[str, Any]) -> list[str]:
        """Return list of missing required context keys."""
        return [k for k in self.required_context_keys if k not in context]


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

_SIGNATURE_REGISTRY: dict[str, AgentSignature] = {}


def register_signature(sig: AgentSignature) -> None:
    """Register an agent's I/O contract.

    Safe to call multiple times — later registration overwrites earlier.
    """
    _SIGNATURE_REGISTRY[sig.agent_name] = sig


def get_signature(agent_name: str) -> AgentSignature | None:
    """Retrieve a registered signature or None if not registered."""
    return _SIGNATURE_REGISTRY.get(agent_name)


def list_signatures() -> list[AgentSignature]:
    """Return all registered signatures."""
    return list(_SIGNATURE_REGISTRY.values())


def reset_signature_registry() -> None:
    """Clear the registry and re-register defaults (for test isolation)."""
    _SIGNATURE_REGISTRY.clear()
    _register_default_signatures()


def validate_publish(
    from_agent: str,
    discovery_type: DiscoveryType,
    content: dict[str, Any],
) -> list[str]:
    """Validate a publish call against the agent's registered signature.

    Returns a list of validation errors (empty list = valid).
    Agents without registered signatures always pass.
    """
    sig = _SIGNATURE_REGISTRY.get(from_agent)
    if sig is None:
        return []

    errors: list[str] = []

    # Check the agent is allowed to emit this type.
    # emits_discovery_types=None → unconstrained (no check).
    # emits_discovery_types=[]   → no emissions allowed (strictest).
    if sig.emits_discovery_types is not None and discovery_type not in sig.emits_discovery_types:
        errors.append(
            f"[{from_agent}] Not declared to emit {discovery_type.value}. "
            f"Declared: {[d.value for d in sig.emits_discovery_types]}"
        )

    # Validate payload schema (content=None is treated as empty dict)
    errors.extend(sig.validate_payload(discovery_type, content))

    return errors


# ---------------------------------------------------------------------------
# Default signatures for the 6 GTM agents
# ---------------------------------------------------------------------------

def _register_default_signatures() -> None:
    register_signature(AgentSignature(
        agent_name="market-intelligence",
        emits_discovery_types=[
            DiscoveryType.MARKET_TREND,
            DiscoveryType.MARKET_OPPORTUNITY,
            DiscoveryType.MARKET_THREAT,
        ],
        consumes_discovery_types=[DiscoveryType.COMPANY_PROFILE],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.MARKET_TREND.value: {"trend": "str", "confidence": "float"},
        },
    ))

    register_signature(AgentSignature(
        agent_name="competitor-analyst",
        emits_discovery_types=[
            DiscoveryType.COMPETITOR_FOUND,
            DiscoveryType.COMPETITOR_WEAKNESS,
            DiscoveryType.COMPETITOR_SIGNAL,
        ],
        consumes_discovery_types=[DiscoveryType.COMPANY_PROFILE],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.COMPETITOR_FOUND.value: {"name": "str"},
        },
    ))

    register_signature(AgentSignature(
        agent_name="customer-profiler",
        emits_discovery_types=[
            DiscoveryType.ICP_SEGMENT,
            DiscoveryType.PERSONA_DEFINED,
            DiscoveryType.PAIN_POINT,
        ],
        consumes_discovery_types=[
            DiscoveryType.MARKET_TREND,
            DiscoveryType.COMPETITOR_FOUND,
            DiscoveryType.COMPANY_PROFILE,
        ],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.PERSONA_DEFINED.value: {"name": "str", "role": "str"},
        },
    ))

    register_signature(AgentSignature(
        agent_name="lead-hunter",
        emits_discovery_types=[
            DiscoveryType.LEAD_FOUND,
            DiscoveryType.LEAD_QUALIFIED,
            DiscoveryType.LEAD_ENRICHED,
        ],
        consumes_discovery_types=[
            DiscoveryType.ICP_SEGMENT,
            DiscoveryType.PERSONA_DEFINED,
        ],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.LEAD_FOUND.value: {"company_name": "str"},
        },
    ))

    register_signature(AgentSignature(
        agent_name="campaign-architect",
        emits_discovery_types=[
            DiscoveryType.CHANNEL_RECOMMENDED,
            DiscoveryType.MESSAGE_CRAFTED,
        ],
        consumes_discovery_types=[
            DiscoveryType.LEAD_FOUND,
            DiscoveryType.PERSONA_DEFINED,
        ],
        required_context_keys=["company_name", "value_proposition"],
    ))

    register_signature(AgentSignature(
        agent_name="gtm-strategist",
        emits_discovery_types=[DiscoveryType.INSIGHT],
        consumes_discovery_types=[],
        required_context_keys=["company_name", "industry"],
    ))


# Register defaults on module import
_register_default_signatures()
