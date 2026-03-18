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
# Default signatures for all GTM agents
# ---------------------------------------------------------------------------

def _register_default_signatures() -> None:
    # ── Analysis tier: first-mover agents ─────────────────────────────────

    # company-enricher: first agent in the flow — scrapes/enriches company
    # profile and seeds the bus with everything downstream agents consume.
    register_signature(AgentSignature(
        agent_name="company-enricher",
        emits_discovery_types=[
            DiscoveryType.COMPANY_PROFILE,
            DiscoveryType.COMPANY_PRODUCTS,
            DiscoveryType.COMPANY_TECH_STACK,
            DiscoveryType.COMPETITOR_FOUND,
            DiscoveryType.ICP_SEGMENT,
        ],
        consumes_discovery_types=[],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.COMPANY_PROFILE.value: {"company_name": "str"},
            DiscoveryType.COMPETITOR_FOUND.value: {"name": "str"},
        },
    ))

    # gtm-strategist: orchestrator — publishes COMPANY_PROFILE + MARKET_TREND
    # (market sizing/sales motion); backfills CAMPAIGN_READY, LEAD_FOUND,
    # PERSONA_DEFINED to synthesise specialist results into the final output.
    register_signature(AgentSignature(
        agent_name="gtm-strategist",
        emits_discovery_types=[
            DiscoveryType.COMPANY_PROFILE,
            DiscoveryType.MARKET_TREND,
        ],
        consumes_discovery_types=[
            DiscoveryType.CAMPAIGN_READY,
            DiscoveryType.LEAD_FOUND,
            DiscoveryType.PERSONA_DEFINED,
        ],
        required_context_keys=["company_name", "industry"],
        payload_schemas={
            DiscoveryType.COMPANY_PROFILE.value: {"company_name": "str"},
        },
    ))

    # market-intelligence: publishes trends and opportunities; backfills the
    # enriched COMPANY_PROFILE from the orchestrator for grounding.
    register_signature(AgentSignature(
        agent_name="market-intelligence",
        emits_discovery_types=[
            DiscoveryType.MARKET_TREND,
            DiscoveryType.MARKET_OPPORTUNITY,
        ],
        consumes_discovery_types=[DiscoveryType.COMPANY_PROFILE],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.MARKET_TREND.value: {"name": "str"},
            DiscoveryType.MARKET_OPPORTUNITY.value: {"title": "str"},
        },
    ))

    # competitor-analyst: discovers new competitors and publishes their
    # weaknesses; subscribes to COMPETITOR_FOUND (from company-enricher /
    # other agents) and COMPANY_PROFILE for context.
    register_signature(AgentSignature(
        agent_name="competitor-analyst",
        emits_discovery_types=[
            DiscoveryType.COMPETITOR_FOUND,
            DiscoveryType.COMPETITOR_WEAKNESS,
        ],
        consumes_discovery_types=[
            DiscoveryType.COMPETITOR_FOUND,
            DiscoveryType.COMPANY_PROFILE,
        ],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.COMPETITOR_FOUND.value: {"name": "str"},
            DiscoveryType.COMPETITOR_WEAKNESS.value: {"competitor_name": "str"},
        },
    ))

    # customer-profiler: emits one PERSONA_DEFINED per buyer persona;
    # consumes market and competitor signals to ground ICP firmographics.
    register_signature(AgentSignature(
        agent_name="customer-profiler",
        emits_discovery_types=[
            DiscoveryType.PERSONA_DEFINED,
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

    # lead-hunter: emits one LEAD_FOUND per qualified prospect;
    # consumes personas, market opportunities, and competitor weaknesses for
    # ICP refinement and lead prioritisation.
    register_signature(AgentSignature(
        agent_name="lead-hunter",
        emits_discovery_types=[
            DiscoveryType.LEAD_FOUND,
        ],
        consumes_discovery_types=[
            DiscoveryType.PERSONA_DEFINED,
            DiscoveryType.MARKET_OPPORTUNITY,
            DiscoveryType.COMPETITOR_WEAKNESS,
        ],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.LEAD_FOUND.value: {"company_name": "str"},
        },
    ))

    # campaign-architect: builds campaigns from personas, leads, and
    # competitor weaknesses; emits CAMPAIGN_READY so execution agents fire.
    register_signature(AgentSignature(
        agent_name="campaign-architect",
        emits_discovery_types=[
            DiscoveryType.CAMPAIGN_READY,
        ],
        consumes_discovery_types=[
            DiscoveryType.PERSONA_DEFINED,
            DiscoveryType.LEAD_FOUND,
            DiscoveryType.COMPETITOR_WEAKNESS,
        ],
        required_context_keys=["company_name", "value_proposition"],
        payload_schemas={
            DiscoveryType.CAMPAIGN_READY.value: {"content_pieces_count": "int"},
        },
    ))

    # ── Execution tier: Phase 2 agents ────────────────────────────────────

    # workforce-architect: designs the AI agent roster from completed GTM
    # analysis; consumes campaign and persona context to right-size the team.
    register_signature(AgentSignature(
        agent_name="workforce-architect",
        emits_discovery_types=[
            DiscoveryType.WORKFORCE_READY,
        ],
        consumes_discovery_types=[
            DiscoveryType.CAMPAIGN_READY,
            DiscoveryType.PERSONA_DEFINED,
            DiscoveryType.LEAD_FOUND,
        ],
        required_context_keys=["company_name"],
        payload_schemas={
            DiscoveryType.WORKFORCE_READY.value: {"agent_count": "int"},
        },
    ))

    # outreach-executor: sends personalised emails via SendGrid; gates on
    # WORKFORCE_READY (approved roster check) and LEAD_ENRICHED (email
    # deliverability); emits MESSAGE_CRAFTED on successful send.
    register_signature(AgentSignature(
        agent_name="outreach-executor",
        emits_discovery_types=[
            DiscoveryType.MESSAGE_CRAFTED,
        ],
        consumes_discovery_types=[
            DiscoveryType.WORKFORCE_READY,
            DiscoveryType.CAMPAIGN_READY,
            DiscoveryType.LEAD_ENRICHED,
        ],
        required_context_keys=["lead_id", "lead_email"],
        payload_schemas={
            DiscoveryType.MESSAGE_CRAFTED.value: {"lead_id": "str", "status": "str"},
        },
    ))

    # crm-sync: upserts HubSpot contacts; consumes WORKFORCE_READY for
    # workforce metadata, LEAD_FOUND for batch CRM population, and
    # LEAD_ENRICHED for email-verification fields; emits LEAD_QUALIFIED
    # once a contact is confirmed in the CRM.
    register_signature(AgentSignature(
        agent_name="crm-sync",
        emits_discovery_types=[
            DiscoveryType.LEAD_QUALIFIED,
        ],
        consumes_discovery_types=[
            DiscoveryType.WORKFORCE_READY,
            DiscoveryType.LEAD_FOUND,
            DiscoveryType.LEAD_ENRICHED,
        ],
        required_context_keys=["lead_id"],
        payload_schemas={
            DiscoveryType.LEAD_QUALIFIED.value: {"lead_id": "str", "crm_platform": "str"},
        },
    ))

    # ── Operational tier: Phase 2.1 agents ────────────────────────────────

    # signal-monitor: scheduled surveillance agent; subscribes to
    # COMPETITOR_FOUND to keep its watchlist current; emits SIGNAL_DETECTED
    # for every actionable (relevance >= 0.50) market signal.
    register_signature(AgentSignature(
        agent_name="signal-monitor",
        emits_discovery_types=[
            DiscoveryType.SIGNAL_DETECTED,
        ],
        consumes_discovery_types=[
            DiscoveryType.COMPETITOR_FOUND,
        ],
        required_context_keys=["company_id", "industry"],
        payload_schemas={
            DiscoveryType.SIGNAL_DETECTED.value: {
                "signal_text": "str",
                "relevance_score": "float",
            },
        },
    ))

    # lead-enrichment: validates emails (DNS MX + Hunter.io), ACRA registry
    # lookup, and financial data enrichment; subscribes to LEAD_FOUND to
    # auto-enrich on discovery; emits LEAD_ENRICHED with quality gate result.
    register_signature(AgentSignature(
        agent_name="lead-enrichment",
        emits_discovery_types=[
            DiscoveryType.LEAD_ENRICHED,
        ],
        consumes_discovery_types=[
            DiscoveryType.LEAD_FOUND,
        ],
        required_context_keys=["company_id"],
        payload_schemas={
            DiscoveryType.LEAD_ENRICHED.value: {
                "lead_id": "str",
                "email_valid": "bool",
                "qualifies_for_sequence": "bool",
            },
        },
    ))


# Register defaults on module import
_register_default_signatures()
