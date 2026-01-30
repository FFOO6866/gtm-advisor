"""GTM Advisor Governance Package.

Enterprise governance layer providing:
- Access Control: RBAC for agents and tools
- Checkpoints: Human-in-the-loop for critical decisions
- Audit Trail: Complete logging of all operations
- Budgets: Token and API cost controls
- PDPA Compliance: Singapore data protection

Principle: No agent operates without governance oversight.
"""

from .access import (
    AccessControl,
    AgentPermissions,
    Permission,
    Role,
)
from .audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
)
from .budgets import (
    BudgetLimit,
    BudgetManager,
    UsageTracker,
)
from .checkpoints import (
    ApprovalRequest,
    ApprovalStatus,
    Checkpoint,
    CheckpointManager,
    CheckpointType,
)
from .compliance import (
    ConsentStatus,
    DataCategory,
    PDPAChecker,
)

__all__ = [
    # Access Control
    "AccessControl",
    "Permission",
    "Role",
    "AgentPermissions",
    # Checkpoints
    "Checkpoint",
    "CheckpointType",
    "CheckpointManager",
    "ApprovalRequest",
    "ApprovalStatus",
    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    # Budgets
    "BudgetManager",
    "BudgetLimit",
    "UsageTracker",
    # Compliance
    "PDPAChecker",
    "DataCategory",
    "ConsentStatus",
]
