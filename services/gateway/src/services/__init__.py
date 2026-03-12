"""Gateway service layer for GTM Advisor.

Services encapsulate complex business logic that spans multiple agents or
database operations. Routers should delegate to services, not contain logic.
"""

from .clarification import ClarificationQuestion, ClarificationResponse, GTMClarificationService
from .journey import JourneyCheckpoint, JourneyOrchestrator
from .task_decomposition import (
    AgentTaskNode,
    TaskDecompositionService,
    TaskDependencyGraph,
)

__all__ = [
    "GTMClarificationService",
    "ClarificationQuestion",
    "ClarificationResponse",
    "TaskDecompositionService",
    "TaskDependencyGraph",
    "AgentTaskNode",
    "JourneyOrchestrator",
    "JourneyCheckpoint",
]
