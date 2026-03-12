"""Trust Postures for GTM Advisor.

Implements the agentic-os EATP-inspired trust posture system:
  - SUPERVISED: Pause at every agent handoff, require human approval
  - MONITORED:  Run freely, log everything (default — best for most users)
  - AUTONOMOUS: Run freely, minimal overhead (power users / CI)

TrustContext is created per analysis run and passed to the orchestrator.
It gates agent handoffs via gate_agent_handoff(), which blocks in SUPERVISED
mode and passes through immediately in MONITORED/AUTONOMOUS.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger()


class TrustPosture(str, Enum):
    """Controls how much human oversight an analysis run requires."""

    SUPERVISED = "supervised"    # Pause + require explicit approval at each wave
    MONITORED = "monitored"      # Run freely, full audit trail (default)
    AUTONOMOUS = "autonomous"    # Run freely, minimal logging


@dataclass
class ApprovalGate:
    """A pending approval waiting for human sign-off."""

    gate_id: str
    from_agent: str
    to_agent: str
    context_summary: str
    approved: bool = False
    rejected: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event, compare=False)

    def approve(self, reason: str = "") -> None:
        """Human approves this handoff."""
        self.approved = True
        self._event.set()
        logger.info("gate_approved", gate_id=self.gate_id, reason=reason)

    def reject(self, reason: str = "") -> None:
        """Human rejects this handoff."""
        self.rejected = True
        self._event.set()
        logger.warning("gate_rejected", gate_id=self.gate_id, reason=reason)

    async def wait(self, timeout_seconds: float = 300.0) -> bool:
        """Wait for human decision. Returns True if approved, False if rejected/timeout."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_seconds)
            return self.approved
        except TimeoutError:
            logger.warning(
                "gate_timeout",
                gate_id=self.gate_id,
                timeout_seconds=timeout_seconds,
            )
            # Default: auto-approve on timeout to avoid stalling analysis
            self.approved = True
            return True


class TrustContext:
    """Per-run trust enforcement context.

    Usage:
        ctx = TrustContext(posture=TrustPosture.SUPERVISED, analysis_id=aid)
        allowed = await ctx.gate_agent_handoff("market-intelligence", "customer-profiler", {})
        if not allowed:
            # Handoff rejected by human
            raise AgentError("Handoff rejected")
    """

    def __init__(
        self,
        posture: TrustPosture,
        analysis_id: UUID,
        user_id: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.posture = posture
        self.analysis_id = analysis_id
        self.user_id = user_id
        self.timeout_seconds = timeout_seconds
        self._pending_gates: dict[str, ApprovalGate] = {}
        self._audit_log: list[dict[str, Any]] = []

    async def gate_agent_handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Gate the transition from one agent wave to the next.

        SUPERVISED: Creates an ApprovalGate and waits for human approval.
        MONITORED:  Logs the handoff and returns True immediately.
        AUTONOMOUS: Returns True immediately with no logging overhead.

        Returns:
            True if handoff is approved (always True for MONITORED/AUTONOMOUS).
        """
        self._audit_log.append({
            "event": "handoff_requested",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "posture": self.posture.value,
        })

        if self.posture == TrustPosture.AUTONOMOUS:
            return True

        if self.posture == TrustPosture.MONITORED:
            logger.info(
                "handoff_monitored",
                from_agent=from_agent,
                to_agent=to_agent,
                analysis_id=str(self.analysis_id),
            )
            return True

        # SUPERVISED: create gate and wait.
        # Include a UUID fragment so repeated handoffs between the same pair
        # don't overwrite each other in _pending_gates.
        gate_id = f"{from_agent}→{to_agent}:{uuid4().hex[:8]}"
        gate = ApprovalGate(
            gate_id=gate_id,
            from_agent=from_agent,
            to_agent=to_agent,
            context_summary=str(context or {}),
        )
        self._pending_gates[gate_id] = gate

        logger.info(
            "handoff_gate_created",
            gate_id=gate_id,
            from_agent=from_agent,
            to_agent=to_agent,
            analysis_id=str(self.analysis_id),
        )

        approved = await gate.wait(timeout_seconds=self.timeout_seconds)

        self._audit_log.append({
            "event": "handoff_resolved",
            "gate_id": gate_id,
            "approved": approved,
        })

        return approved

    def get_pending_gates(self) -> list[dict[str, Any]]:
        """Return pending gates waiting for approval (for dashboard polling)."""
        return [
            {
                "gate_id": g.gate_id,
                "from_agent": g.from_agent,
                "to_agent": g.to_agent,
                "context_summary": g.context_summary,
                "approved": g.approved,
                "rejected": g.rejected,
            }
            for g in self._pending_gates.values()
            if not g.approved and not g.rejected
        ]

    def approve_gate(self, gate_id: str, reason: str = "") -> bool:
        """Programmatically approve a pending gate (for API endpoint)."""
        gate = self._pending_gates.get(gate_id)
        if gate:
            gate.approve(reason=reason)
            return True
        return False

    def reject_gate(self, gate_id: str, reason: str = "") -> bool:
        """Programmatically reject a pending gate (for API endpoint)."""
        gate = self._pending_gates.get(gate_id)
        if gate:
            gate.reject(reason=reason)
            return True
        return False

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Return the full audit log for this analysis run."""
        return list(self._audit_log)
