"""Regression tests for the backend launch-mode deny dependency.

These verify that the frontend FeatureGate + backend require_execution_enabled
form a two-layer defense: frontend hides visibility, backend denies direct
invocation of dangerous actions (sending email, enrolling in sequences,
triggering execution runs).

The protected endpoints are documented in
services/gateway/src/auth/launch_mode.py.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException


class TestLaunchModeDependency:
    """Tests the require_execution_enabled FastAPI dependency directly."""

    def test_dependency_passes_when_launch_mode_unset(self, monkeypatch):
        """With no GTM_LAUNCH_MODE env var, execution is enabled."""
        monkeypatch.delenv("GTM_LAUNCH_MODE", raising=False)
        # Reimport to re-read env
        import importlib

        from services.gateway.src.auth import launch_mode

        importlib.reload(launch_mode)
        assert launch_mode.is_launch_mode_v1() is False
        # Should not raise
        launch_mode.require_execution_enabled()

    def test_dependency_passes_when_mode_is_dev(self, monkeypatch):
        """With GTM_LAUNCH_MODE=dev, execution is enabled."""
        monkeypatch.setenv("GTM_LAUNCH_MODE", "dev")
        import importlib

        from services.gateway.src.auth import launch_mode

        importlib.reload(launch_mode)
        assert launch_mode.is_launch_mode_v1() is False
        launch_mode.require_execution_enabled()

    def test_dependency_denies_when_mode_is_v1(self, monkeypatch):
        """With GTM_LAUNCH_MODE=v1, execution is denied with 404."""
        monkeypatch.setenv("GTM_LAUNCH_MODE", "v1")
        import importlib

        from services.gateway.src.auth import launch_mode

        importlib.reload(launch_mode)
        assert launch_mode.is_launch_mode_v1() is True
        with pytest.raises(HTTPException) as exc_info:
            launch_mode.require_execution_enabled()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not Found"

    def test_dependency_denies_when_mode_is_v1_uppercase(self, monkeypatch):
        """Env var match is case-insensitive (V1 works the same as v1)."""
        monkeypatch.setenv("GTM_LAUNCH_MODE", "V1")
        import importlib

        from services.gateway.src.auth import launch_mode

        importlib.reload(launch_mode)
        assert launch_mode.is_launch_mode_v1() is True
        with pytest.raises(HTTPException):
            launch_mode.require_execution_enabled()

    def test_module_reimport_resets_state(self, monkeypatch):
        """After env flip + reimport, behavior reflects new env state.

        This documents the compile-time posture: flipping the env requires
        a process restart (or in tests, an importlib.reload).
        """
        import importlib

        from services.gateway.src.auth import launch_mode

        monkeypatch.setenv("GTM_LAUNCH_MODE", "v1")
        importlib.reload(launch_mode)
        assert launch_mode.is_launch_mode_v1() is True

        monkeypatch.delenv("GTM_LAUNCH_MODE", raising=False)
        importlib.reload(launch_mode)
        assert launch_mode.is_launch_mode_v1() is False


class TestProtectedEndpointsList:
    """Documents which endpoints are protected. If this list changes, the
    corresponding decorator in the router file must also change, and vice
    versa.
    """

    # Per docs/launch/dangerous-action-policy.md — protected endpoints have
    # external effects (send email, cascade to sends). reject_item is NOT
    # in this list because it is state-only (status change + internal log).
    PROTECTED_ENDPOINTS = [
        ("POST", "/api/v1/companies/{company_id}/approvals/{item_id}/approve"),
        ("POST", "/api/v1/companies/{company_id}/approvals/bulk-approve"),
        ("POST", "/api/v1/companies/{company_id}/sequences/activate-playbook"),
        ("POST", "/api/v1/companies/{company_id}/workforce/{config_id}/execute"),
    ]

    def test_inventory_matches_module_docstring(self):
        """The protected endpoint list in launch_mode.py should match this test."""
        import importlib

        from services.gateway.src.auth import launch_mode

        importlib.reload(launch_mode)
        docstring = launch_mode.require_execution_enabled.__doc__ or ""
        # Each endpoint fragment should appear in the docstring
        for _method, path in self.PROTECTED_ENDPOINTS:
            # Strip /api/v1 prefix and check last segment + action
            fragment = path.split("/")[-1]
            # "approve" should appear, "reject" should appear, etc.
            assert fragment in docstring, f"Endpoint {path} not documented in launch_mode.py"


class TestSchedulerAutoEnrollGate:
    """Regression tests for Cycle 4 Finding F-1.

    `_run_signal_monitor_all_active` in scheduler.py calls
    `engine.auto_enroll_from_signals(...)` which creates SequenceEnrollment
    rows — a cascading state transition per the dangerous-action policy.

    In launch mode, the call must be skipped so that no enrollments are
    created, even though the signal monitor itself continues to run.

    These tests exercise only the text of the scheduler module to confirm
    the gate is in place and the expected log event exists. We intentionally
    do not spin up the full scheduler + DB just to verify a code-path gate.
    """

    def _read_scheduler_source(self) -> str:
        import inspect

        from services.gateway.src import scheduler

        return inspect.getsource(scheduler)

    def test_auto_enroll_call_is_guarded_by_launch_mode_check(self):
        """The auto_enroll_from_signals call must be inside an `if
        is_launch_mode_v1()` guard that skips it in v1.
        """
        source = self._read_scheduler_source()

        # Both the gate import and the auto_enroll call must be present.
        assert "is_launch_mode_v1" in source
        assert "auto_enroll_from_signals" in source

        # The gate must precede the call site (inside the signal monitor job).
        gate_index = source.find("is_launch_mode_v1()")
        call_index = source.find("engine.auto_enroll_from_signals(")
        assert gate_index != -1, "launch-mode gate missing from scheduler"
        assert call_index != -1, "auto_enroll_from_signals call missing"
        assert gate_index < call_index, (
            "is_launch_mode_v1() check must appear before auto_enroll call; "
            "Cycle 4 finding F-1 would regress without it"
        )

    def test_auto_enroll_skip_log_event_exists(self):
        """The skip log event 'auto_enroll_from_signals_skipped' must be
        emitted so operators can see in prod that the gate is active.
        """
        source = self._read_scheduler_source()
        assert "auto_enroll_from_signals_skipped" in source, (
            "skip log event missing — operators need visibility into the gate"
        )


class TestAgentRegistryLock:
    """Regression tests for Cycle 4 Finding F-4 / LD-11 (closed Cycle 5 setup).

    The /api/v1/agents/{agent_name}/run and
    /api/v1/companies/{company_id}/agents/{agent_id}/run endpoints execute any
    agent whose ID passes is_valid_agent(). The launch-mode deny dependency
    does NOT cover these routes — they are implicitly safe only because the
    agent registry narrows the set to the 6 approved analysis agents.

    These tests lock that registry. If anyone adds an execution agent
    (outreach-executor, crm-sync, workforce-architect, signal-monitor,
    lead-enrichment) — or any other agent that has external effect — to the
    registry, the run endpoints become a launch-mode bypass into the
    execution layer. These tests fail in that case so the bypass cannot land
    silently.

    See:
      - docs/launch/dangerous-action-policy.md (Watch list)
      - docs/launch/execution-verification.md (Finding F-4)
      - docs/launch/cycle-5-incorporation-plan.md (Refinement 1)
    """

    # The exact set of agents that may be exposed via /agents/{name}/run.
    # Every entry must be a pure analysis agent — no external effects.
    APPROVED_ANALYSIS_AGENTS = frozenset(
        {
            "gtm-strategist",
            "market-intelligence",
            "competitor-analyst",
            "customer-profiler",
            "lead-hunter",
            "campaign-architect",
        }
    )

    # Explicit deny list for known execution-tier agents. Listed by name so
    # the failure message is informative when one slips through. This is in
    # addition to (not a replacement for) the exact-set assertion above.
    KNOWN_EXECUTION_AGENTS = frozenset(
        {
            "outreach-executor",
            "crm-sync",
            "workforce-architect",
            "signal-monitor",
            "lead-enrichment",
        }
    )

    def test_registry_metadata_contains_only_approved_analysis_agents(self):
        """AGENT_METADATA must equal exactly the approved analysis agent set.

        Any deviation (addition, rename, removal) must be reviewed against
        the dangerous-action policy before this assertion is updated.
        """
        from services.gateway.src.agents_registry import AGENT_METADATA

        registered = set(AGENT_METADATA.keys())
        assert registered == set(self.APPROVED_ANALYSIS_AGENTS), (
            f"Agent registry must contain exactly the 6 approved analysis "
            f"agents. Found: {sorted(registered)}. "
            f"Expected: {sorted(self.APPROVED_ANALYSIS_AGENTS)}. "
            f"If you intentionally added a new agent, you must either "
            f"(a) confirm it has no external effect AND update "
            f"APPROVED_ANALYSIS_AGENTS in this test, or "
            f"(b) gate /api/v1/agents/{{name}}/run and "
            f"/companies/{{id}}/agents/{{id}}/run with require_execution_enabled "
            f"and update docs/launch/dangerous-action-policy.md."
        )

    def test_registry_classes_match_metadata(self):
        """get_all_agent_classes() and AGENT_METADATA must agree on the set.

        Drift between these two would create a state where an agent is
        validated by is_valid_agent() but cannot be instantiated, or vice
        versa.
        """
        from services.gateway.src.agents_registry import (
            AGENT_METADATA,
            get_all_agent_classes,
        )

        classes = set(get_all_agent_classes().keys())
        metadata = set(AGENT_METADATA.keys())
        assert classes == metadata, (
            f"Drift between agent class registry and metadata. "
            f"Classes only: {sorted(classes - metadata)}. "
            f"Metadata only: {sorted(metadata - classes)}."
        )

    def test_known_execution_agents_are_not_in_registry(self):
        """No known execution-tier agent ID may pass is_valid_agent() or
        appear in AGENT_METADATA / get_all_agent_classes().

        This is the explicit deny-list complement to the exact-set assertion.
        Failure here is a launch-mode bypass: the run endpoints would
        instantiate and execute an agent that produces external effects
        without any require_execution_enabled gate.
        """
        from services.gateway.src.agents_registry import (
            AGENT_METADATA,
            get_all_agent_classes,
            is_valid_agent,
        )

        all_classes = get_all_agent_classes()
        leaked = set()
        for agent_id in self.KNOWN_EXECUTION_AGENTS:
            if is_valid_agent(agent_id):
                leaked.add(agent_id)
            if agent_id in AGENT_METADATA:
                leaked.add(agent_id)
            if agent_id in all_classes:
                leaked.add(agent_id)

        assert not leaked, (
            f"Execution agents {sorted(leaked)} are exposed via the agent "
            f"registry. They are reachable through "
            f"/api/v1/agents/{{name}}/run and "
            f"/api/v1/companies/{{id}}/agents/{{id}}/run, which are NOT "
            f"protected by require_execution_enabled. This is a launch-mode "
            f"bypass into the execution layer. Either remove them from the "
            f"registry or add an explicit gate on the run endpoints "
            f"(see docs/launch/dangerous-action-policy.md)."
        )
