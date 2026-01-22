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
    Permission,
    Role,
    AgentPermissions,
)
from .checkpoints import (
    Checkpoint,
    CheckpointType,
    CheckpointManager,
    ApprovalRequest,
    ApprovalStatus,
)
from .audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
)
from .budgets import (
    BudgetManager,
    BudgetLimit,
    UsageTracker,
)
from .compliance import (
    PDPAChecker,
    DataCategory,
    ConsentStatus,
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
