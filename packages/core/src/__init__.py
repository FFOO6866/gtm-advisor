"""GTM Advisor Core Package - Types, Config, Errors, and Protocols."""

# SubscriptionTier - single source of truth from database models
from packages.database.src.models import SubscriptionTier

from .agent_bus import (
    AgentBus,
    AgentMessage,
    DiscoveryType,
    get_agent_bus,
    reset_agent_bus,
)
from .config import GTMConfig, get_config
from .errors import (
    AgentError,
    BudgetExceededError,
    GovernanceError,
    GTMError,
    IntegrationError,
    MaxIterationsExceededError,
    RateLimitExceededError,
    ValidationError,
)
from .protocols import (
    AgentProtocol,
    IntegrationProtocol,
    TaskProtocol,
)
from .signatures import (
    AgentSignature,
    get_signature,
    list_signatures,
    register_signature,
    reset_signature_registry,
    validate_publish,
)
from .types import (
    AgentStatus,
    CampaignBrief,
    # Domain Types
    CompanyProfile,
    CompetitorAnalysis,
    CompetitorFundingRound,
    CompetitorPricing,
    ConfidenceLevel,
    CustomerPersona,
    # Enums
    ExecutionMode,
    # Fast Path
    FastPathConfig,
    FastPathRule,
    LeadProfile,
    MarketInsight,
    PDCAPhase,
    # PDCA Types
    PDCAState,
    TaskStatus,
)
from .vertical import detect_vertical_slug

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
    "CompetitorPricing",
    "CompetitorFundingRound",
    "CustomerPersona",
    # Protocols
    "AgentProtocol",
    "TaskProtocol",
    "IntegrationProtocol",
    # A2A Communication
    "AgentBus",
    "AgentMessage",
    "DiscoveryType",
    "get_agent_bus",
    "reset_agent_bus",
    # Agent Signatures
    "AgentSignature",
    "register_signature",
    "get_signature",
    "list_signatures",
    "validate_publish",
    "reset_signature_registry",
    # Vertical Detection
    "detect_vertical_slug",
]
