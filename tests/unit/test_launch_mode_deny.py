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
