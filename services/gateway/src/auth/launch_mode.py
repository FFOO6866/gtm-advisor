"""Launch-mode deny dependency for dangerous actions.

This is the BACKEND complement to the frontend FeatureGate component.
Together they form a two-layer defense: frontend hides visibility,
backend denies execution of dangerous actions.

"Dangerous" means actions that create real-world side effects — sending
email, enrolling leads into sequences, starting execution runs. These
cannot be allowed to run in v1 launch mode even if someone discovers
the endpoint directly (leaked URL, curl, API client).

Design notes:
  - We return 404 Not Found, not 403 Forbidden, to match the silent-redirect
    posture of the frontend. No paywall language, no "access denied" — the
    resource simply does not exist in this deployment.
  - Single env var: GTM_LAUNCH_MODE=v1 in production disables the endpoints.
  - No RBAC, no user tiers, no per-customer flags. The simplest possible
    kill switch that works.
  - Stateless dependency: safe to import and use everywhere, no setup needed.

Governance:
  - See docs/launch/feature-flags.md for the canonical feature-flag policy.
  - Adding a new protected endpoint requires updating this module's
    "protected endpoints" comment and docs/launch/feature-flags.md.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, status

# Evaluated once at module import. Env flips require a process restart,
# matching the frontend's compile-time flag posture.
_LAUNCH_MODE_V1 = os.getenv("GTM_LAUNCH_MODE", "").lower() == "v1"


def is_launch_mode_v1() -> bool:
    """Return True if the backend is running in v1 launch mode.

    Prefer the `require_execution_enabled` dependency for endpoint gating.
    This function is exposed for scheduler jobs and other non-HTTP code that
    needs to short-circuit at call time.
    """
    return _LAUNCH_MODE_V1


def require_execution_enabled() -> None:
    """FastAPI dependency: deny execution-tier actions in v1 launch mode.

    Apply as a dependency on endpoints whose invocation creates real-world
    side effects (sending email, enrolling in sequences, starting execution
    runs, triggering external sync).

    Protected endpoints (v1 launch — actions with external effect):
      - POST /companies/{id}/approvals/{id}/approve   (sends email)
      - POST /companies/{id}/approvals/bulk-approve   (sends emails)
      - POST /companies/{id}/sequences/activate-playbook   (cascades to sends)
      - POST /companies/{id}/workforce/{id}/execute   (cascades to sends)

    Intentionally NOT protected (state-only, no external effect):
      - POST /companies/{id}/approvals/{id}/reject   (status change + internal log)
      - POST /sequences/enrollments/{id}/pause       (state-only)
      - POST /sequences/enrollments/{id}/resume      (state-only)

    Scheduler runtime gates (Cycle 2 + Cycle 4):
      - _run_sequence_runner: call-time is_launch_mode_v1() skip (Cycle 2)
      - _run_signal_monitor_all_active: call-time is_launch_mode_v1() skip
        around auto_enroll_from_signals (Cycle 4, finding F-1)

    See docs/launch/dangerous-action-policy.md for the full audit, the rule
    for what qualifies as "dangerous", and docs/launch/execution-verification.md
    for the Cycle 4 policy-to-endpoint + scheduler coverage matrix.

    Usage:
        from services.gateway.src.auth.launch_mode import require_execution_enabled

        @router.post(
            "/{company_id}/approvals/{item_id}/approve",
            dependencies=[Depends(require_execution_enabled)],
        )
        async def approve_item(...):
            ...

    Raises:
        HTTPException: 404 Not Found when launch mode is v1.
    """
    if _LAUNCH_MODE_V1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )
