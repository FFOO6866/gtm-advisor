"""GTM Advisor Core Package - Types, Config, Errors, and Protocols."""

from .config import GTMConfig, get_config
from .errors import (
    GTMError,
    AgentError,
    ValidationError,
    GovernanceError,
    IntegrationError,
    MaxIterationsExceededError,
    RateLimitExceededError,
    BudgetExceededError,
)
from .types import (
    # Enums
    ExecutionMode,
    AgentStatus,
    TaskStatus,
    ConfidenceLevel,
    SubscriptionTier,
    # PDCA Types
    PDCAState,
    PDCAPhase,
    # Fast Path
    FastPathConfig,
    FastPathRule,
    # Domain Types
    CompanyProfile,
    LeadProfile,
    CampaignBrief,
    MarketInsight,
    CompetitorAnalysis,
    CustomerPersona,
)
from .protocols import (
    AgentProtocol,
    TaskProtocol,
    IntegrationProtocol,
)

__all__ = [
    # Config
    "GTMConfig",
    "get_config",
    # Errors
    "GTMError",
    "AgentError",
    "ValidationError",
    "GovernanceError",
    "IntegrationError",
    "MaxIterationsExceededError",
    "RateLimitExceededError",
    "BudgetExceededError",
    # Enums
    "ExecutionMode",
    "AgentStatus",
    "TaskStatus",
    "ConfidenceLevel",
    "SubscriptionTier",
    # PDCA
    "PDCAState",
    "PDCAPhase",
    # Fast Path
    "FastPathConfig",
    "FastPathRule",
    # Domain Types
    "CompanyProfile",
    "LeadProfile",
    "CampaignBrief",
    "MarketInsight",
    "CompetitorAnalysis",
    "CustomerPersona",
    # Protocols
    "AgentProtocol",
    "TaskProtocol",
    "IntegrationProtocol",
]
