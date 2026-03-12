"""Unit tests for AgentSignature I/O contract validation."""

from __future__ import annotations

import pytest

from packages.core.src.agent_bus import DiscoveryType
from packages.core.src.signatures import (
    AgentSignature,
    get_signature,
    list_signatures,
    register_signature,
    reset_signature_registry,
    validate_publish,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolated_registry():
    """Reset registry before each test to avoid cross-test pollution."""
    reset_signature_registry()
    yield
    reset_signature_registry()


# =============================================================================
# validate_payload tests
# =============================================================================


@pytest.mark.unit
class TestValidatePayload:
    def _make_sig(self, schema: dict) -> AgentSignature:
        return AgentSignature(
            agent_name="test-agent",
            emits_discovery_types=None,
            payload_schemas={DiscoveryType.MARKET_TREND.value: schema},
        )

    def test_valid_payload_returns_no_errors(self):
        sig = self._make_sig({"trend": "str", "confidence": "float"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"trend": "AI boom", "confidence": 0.9})
        assert errors == []

    def test_missing_required_field_returns_error(self):
        sig = self._make_sig({"trend": "str", "confidence": "float"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"trend": "AI boom"})
        assert any("confidence" in e for e in errors)

    def test_wrong_type_returns_error(self):
        sig = self._make_sig({"trend": "str"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"trend": 123})
        assert any("trend" in e for e in errors)

    def test_bool_rejected_for_int_field(self):
        """bool is a subclass of int in Python — must be explicitly rejected."""
        sig = self._make_sig({"count": "int"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"count": True})
        assert any("count" in e for e in errors), "True must not pass int schema check"

    def test_bool_rejected_for_float_field(self):
        sig = self._make_sig({"score": "float"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"score": False})
        assert any("score" in e for e in errors), "False must not pass float schema check"

    def test_int_accepted_for_float_field(self):
        """Integers are valid for float fields (numeric coercion)."""
        sig = self._make_sig({"score": "float"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"score": 1})
        assert errors == []

    def test_no_schema_registered_allows_anything(self):
        sig = AgentSignature(agent_name="test-agent")
        # No schema registered → any content passes
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"garbage": object()})
        assert errors == []

    def test_list_field_accepted(self):
        sig = self._make_sig({"tags": "list"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"tags": ["a", "b"]})
        assert errors == []

    def test_dict_field_accepted(self):
        sig = self._make_sig({"meta": "dict"})
        errors = sig.validate_payload(DiscoveryType.MARKET_TREND, {"meta": {"key": "val"}})
        assert errors == []


# =============================================================================
# validate_publish tests
# =============================================================================


@pytest.mark.unit
class TestValidatePublish:
    def test_allowed_emission_returns_no_errors(self):
        register_signature(AgentSignature(
            agent_name="market-intelligence",
            emits_discovery_types=[DiscoveryType.MARKET_TREND],
        ))
        errors = validate_publish("market-intelligence", DiscoveryType.MARKET_TREND, {"trend": "AI"})
        assert errors == []

    def test_disallowed_emission_returns_error(self):
        register_signature(AgentSignature(
            agent_name="market-intelligence",
            emits_discovery_types=[DiscoveryType.MARKET_TREND],
        ))
        errors = validate_publish("market-intelligence", DiscoveryType.LEAD_FOUND, {"company_name": "Acme"})
        assert any("LEAD_FOUND" in e or "lead_found" in e.lower() for e in errors)

    def test_empty_emit_list_blocks_all(self):
        """emits_discovery_types=[] means no emissions allowed."""
        register_signature(AgentSignature(
            agent_name="restricted-agent",
            emits_discovery_types=[],
        ))
        errors = validate_publish("restricted-agent", DiscoveryType.MARKET_TREND, {})
        assert len(errors) > 0

    def test_unconstrained_agent_allows_any_type(self):
        """emits_discovery_types=None means unconstrained."""
        register_signature(AgentSignature(
            agent_name="free-agent",
            emits_discovery_types=None,
        ))
        errors = validate_publish("free-agent", DiscoveryType.LEAD_FOUND, {})
        assert errors == []

    def test_unknown_agent_always_passes(self):
        """Agents without registered signatures pass all checks."""
        errors = validate_publish("ghost-agent", DiscoveryType.MARKET_TREND, {})
        assert errors == []

    def test_payload_schema_checked_on_allowed_emission(self):
        register_signature(AgentSignature(
            agent_name="market-intelligence",
            emits_discovery_types=[DiscoveryType.MARKET_TREND],
            payload_schemas={DiscoveryType.MARKET_TREND.value: {"trend": "str"}},
        ))
        # Missing required "trend" field
        errors = validate_publish("market-intelligence", DiscoveryType.MARKET_TREND, {})
        assert any("trend" in e for e in errors)


# =============================================================================
# validate_context tests
# =============================================================================


@pytest.mark.unit
class TestValidateContext:
    def test_all_required_keys_present(self):
        sig = AgentSignature(
            agent_name="test-agent",
            required_context_keys=["company_name", "industry"],
        )
        missing = sig.validate_context({"company_name": "Acme", "industry": "saas"})
        assert missing == []

    def test_missing_context_key_returned(self):
        sig = AgentSignature(
            agent_name="test-agent",
            required_context_keys=["company_name", "industry"],
        )
        missing = sig.validate_context({"company_name": "Acme"})
        assert "industry" in missing

    def test_extra_context_keys_allowed(self):
        sig = AgentSignature(
            agent_name="test-agent",
            required_context_keys=["company_name"],
        )
        missing = sig.validate_context({"company_name": "Acme", "extra": "data"})
        assert missing == []

    def test_empty_required_keys_always_passes(self):
        sig = AgentSignature(agent_name="test-agent")
        missing = sig.validate_context({})
        assert missing == []


# =============================================================================
# Registry tests
# =============================================================================


@pytest.mark.unit
class TestSignatureRegistry:
    def test_register_and_get(self):
        sig = AgentSignature(agent_name="my-agent")
        register_signature(sig)
        retrieved = get_signature("my-agent")
        assert retrieved is sig

    def test_get_unknown_returns_none(self):
        assert get_signature("does-not-exist") is None

    def test_later_registration_overwrites(self):
        sig1 = AgentSignature(agent_name="my-agent", required_context_keys=["a"])
        sig2 = AgentSignature(agent_name="my-agent", required_context_keys=["b"])
        register_signature(sig1)
        register_signature(sig2)
        assert get_signature("my-agent").required_context_keys == ["b"]

    def test_reset_restores_6_defaults(self):
        reset_signature_registry()
        sigs = list_signatures()
        names = {s.agent_name for s in sigs}
        expected = {
            "market-intelligence", "competitor-analyst", "customer-profiler",
            "lead-hunter", "campaign-architect", "gtm-strategist",
        }
        assert names == expected

    def test_list_signatures_returns_all(self):
        reset_signature_registry()
        assert len(list_signatures()) == 6

    def test_lead_hunter_emits_lead_found(self):
        """lead-hunter must declare LEAD_FOUND in its emit list."""
        sig = get_signature("lead-hunter")
        assert sig is not None
        assert DiscoveryType.LEAD_FOUND in (sig.emits_discovery_types or [])
