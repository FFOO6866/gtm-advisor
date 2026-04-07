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
