"""Human-in-the-Loop Checkpoints.

Implements approval workflows for critical decisions:
- High-value lead outreach
- CRM data modifications
- Email campaigns
- Budget allocations
- Sensitive data access

Principle: Humans approve, agents execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable
import uuid
import asyncio


class CheckpointType(Enum):
    """Types of checkpoints."""
    APPROVAL = "approval"  # Yes/No decision
    REVIEW = "review"  # Review before proceeding
    SELECTION = "selection"  # Choose from options
    INPUT = "input"  # Provide additional input
    CONFIRMATION = "confirmation"  # Confirm action


class ApprovalStatus(Enum):
    """Status of approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ESCALATED = "escalated"


@dataclass
class ApprovalRequest:
    """A request for human approval."""
    id: str
    checkpoint_id: str
    agent_id: str
    checkpoint_type: CheckpointType
    title: str
    description: str
    context: dict[str, Any]
    options: list[str] | None = None  # For SELECTION type
    urgency: str = "normal"  # low, normal, high, critical
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision: str | None = None  # The actual decision/input
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "checkpoint_id": self.checkpoint_id,
            "agent_id": self.agent_id,
            "checkpoint_type": self.checkpoint_type.value,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "options": self.options,
            "urgency": self.urgency,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "decision": self.decision,
            "notes": self.notes,
        }

    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False

    @property
    def is_pending(self) -> bool:
        """Check if still pending."""
        return self.status == ApprovalStatus.PENDING and not self.is_expired


@dataclass
class Checkpoint:
    """A checkpoint definition.

    Defines when and how human approval is required.
    """
    id: str
    name: str
    description: str
    checkpoint_type: CheckpointType
    trigger_condition: Callable[[dict[str, Any]], bool] | None = None
    auto_approve_after: timedelta | None = None  # Auto-approve if no response
    escalation_after: timedelta | None = None  # Escalate if pending too long
    required_approvers: list[str] = field(default_factory=list)  # Role/user IDs
    enabled: bool = True

    def should_trigger(self, context: dict[str, Any]) -> bool:
        """Check if checkpoint should trigger."""
        if not self.enabled:
            return False
        if self.trigger_condition:
            return self.trigger_condition(context)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "checkpoint_type": self.checkpoint_type.value,
            "auto_approve_after": str(self.auto_approve_after) if self.auto_approve_after else None,
            "escalation_after": str(self.escalation_after) if self.escalation_after else None,
            "required_approvers": self.required_approvers,
            "enabled": self.enabled,
        }


class CheckpointManager:
    """Manages checkpoints and approval workflows.

    Example:
        manager = CheckpointManager()

        # Define checkpoint
        manager.register_checkpoint(Checkpoint(
            id="high_value_outreach",
            name="High Value Lead Outreach",
            description="Approve outreach to leads with value > $50k",
            checkpoint_type=CheckpointType.APPROVAL,
            trigger_condition=lambda ctx: ctx.get("lead_value", 0) > 50000,
            auto_approve_after=timedelta(hours=4),
        ))

        # Request approval
        request = await manager.request_approval(
            checkpoint_id="high_value_outreach",
            agent_id="lead_hunter",
            title="Outreach to Enterprise Lead",
            description="Request to send outreach to Acme Corp (est. value $120k)",
            context={"company": "Acme Corp", "lead_value": 120000},
        )

        # Wait for decision (or timeout)
        result = await manager.wait_for_decision(request.id, timeout=300)
    """

    def __init__(self):
        self._checkpoints: dict[str, Checkpoint] = {}
        self._pending_requests: dict[str, ApprovalRequest] = {}
        self._completed_requests: list[ApprovalRequest] = []
        self._callbacks: dict[str, list[Callable]] = {}

    def register_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Register a checkpoint definition."""
        self._checkpoints[checkpoint.id] = checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Get checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)

    def on_decision(self, checkpoint_id: str, callback: Callable) -> None:
        """Register callback for when decision is made."""
        if checkpoint_id not in self._callbacks:
            self._callbacks[checkpoint_id] = []
        self._callbacks[checkpoint_id].append(callback)

    async def request_approval(
        self,
        checkpoint_id: str,
        agent_id: str,
        title: str,
        description: str,
        context: dict[str, Any],
        options: list[str] | None = None,
        urgency: str = "normal",
    ) -> ApprovalRequest:
        """Create an approval request."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Unknown checkpoint: {checkpoint_id}")

        # Check if should trigger
        if not checkpoint.should_trigger(context):
            # Auto-approve if condition not met
            return ApprovalRequest(
                id=str(uuid.uuid4()),
                checkpoint_id=checkpoint_id,
                agent_id=agent_id,
                checkpoint_type=checkpoint.checkpoint_type,
                title=title,
                description=description,
                context=context,
                status=ApprovalStatus.APPROVED,
                decision="auto_approved_condition_not_met",
            )

        # Calculate expiry
        expires_at = None
        if checkpoint.auto_approve_after:
            expires_at = datetime.utcnow() + checkpoint.auto_approve_after

        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            checkpoint_id=checkpoint_id,
            agent_id=agent_id,
            checkpoint_type=checkpoint.checkpoint_type,
            title=title,
            description=description,
            context=context,
            options=options or checkpoint.to_dict().get("options"),
            urgency=urgency,
            expires_at=expires_at,
        )

        self._pending_requests[request.id] = request
        return request

    async def decide(
        self,
        request_id: str,
        approved: bool,
        decided_by: str,
        decision: str | None = None,
        notes: str | None = None,
    ) -> ApprovalRequest:
        """Make a decision on a request."""
        request = self._pending_requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        if not request.is_pending:
            raise ValueError(f"Request is not pending: {request.status.value}")

        request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        request.decided_at = datetime.utcnow()
        request.decided_by = decided_by
        request.decision = decision or ("approved" if approved else "rejected")
        request.notes = notes

        # Move to completed
        del self._pending_requests[request_id]
        self._completed_requests.append(request)

        # Trigger callbacks
        callbacks = self._callbacks.get(request.checkpoint_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(request)
                else:
                    callback(request)
            except Exception:
                pass  # Don't let callback errors break the flow

        return request

    async def wait_for_decision(
        self,
        request_id: str,
        timeout: float = 300,  # 5 minutes default
        poll_interval: float = 1.0,
    ) -> ApprovalRequest:
        """Wait for a decision on a request.

        Returns the request when decided or expired.
        """
        elapsed = 0.0
        while elapsed < timeout:
            request = self._pending_requests.get(request_id)

            if not request:
                # Check completed
                for completed in self._completed_requests:
                    if completed.id == request_id:
                        return completed
                raise ValueError(f"Request not found: {request_id}")

            if not request.is_pending:
                return request

            if request.is_expired:
                # Handle expiry
                checkpoint = self._checkpoints.get(request.checkpoint_id)
                if checkpoint and checkpoint.auto_approve_after:
                    # Auto-approve on expiry
                    return await self.decide(
                        request_id=request_id,
                        approved=True,
                        decided_by="system",
                        decision="auto_approved_on_timeout",
                        notes="Request auto-approved after timeout",
                    )
                else:
                    request.status = ApprovalStatus.EXPIRED
                    return request

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Final timeout check
        request = self._pending_requests.get(request_id)
        if request:
            request.status = ApprovalStatus.EXPIRED
            return request

        raise TimeoutError(f"Timeout waiting for decision on {request_id}")

    def get_pending_requests(
        self,
        agent_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> list[ApprovalRequest]:
        """Get pending approval requests."""
        requests = list(self._pending_requests.values())

        if agent_id:
            requests = [r for r in requests if r.agent_id == agent_id]
        if checkpoint_id:
            requests = [r for r in requests if r.checkpoint_id == checkpoint_id]

        return requests

    def get_completed_requests(
        self,
        limit: int = 100,
    ) -> list[ApprovalRequest]:
        """Get completed requests (most recent first)."""
        return sorted(
            self._completed_requests,
            key=lambda r: r.decided_at or r.created_at,
            reverse=True,
        )[:limit]


# Pre-defined checkpoints for GTM Advisor
def create_gtm_checkpoints() -> list[Checkpoint]:
    """Create default checkpoints for GTM Advisor."""
    return [
        Checkpoint(
            id="high_value_outreach",
            name="High Value Lead Outreach",
            description="Approve outreach to leads with estimated value > $50k",
            checkpoint_type=CheckpointType.APPROVAL,
            trigger_condition=lambda ctx: ctx.get("lead_value", 0) > 50000,
            auto_approve_after=timedelta(hours=4),
        ),
        Checkpoint(
            id="crm_bulk_update",
            name="CRM Bulk Update",
            description="Approve bulk updates to CRM records",
            checkpoint_type=CheckpointType.APPROVAL,
            trigger_condition=lambda ctx: ctx.get("record_count", 0) > 10,
            escalation_after=timedelta(hours=1),
        ),
        Checkpoint(
            id="email_campaign_launch",
            name="Email Campaign Launch",
            description="Review and approve email campaign before sending",
            checkpoint_type=CheckpointType.REVIEW,
            auto_approve_after=timedelta(hours=24),
        ),
        Checkpoint(
            id="competitor_response",
            name="Competitor Response Strategy",
            description="Choose response strategy for competitive situation",
            checkpoint_type=CheckpointType.SELECTION,
        ),
        Checkpoint(
            id="budget_allocation",
            name="Campaign Budget Allocation",
            description="Approve budget allocation above threshold",
            checkpoint_type=CheckpointType.APPROVAL,
            trigger_condition=lambda ctx: ctx.get("budget_amount", 0) > 5000,
        ),
        Checkpoint(
            id="sensitive_data_access",
            name="Sensitive Data Access",
            description="Approve access to sensitive customer data",
            checkpoint_type=CheckpointType.APPROVAL,
            trigger_condition=lambda ctx: ctx.get("data_category") == "sensitive",
        ),
    ]
