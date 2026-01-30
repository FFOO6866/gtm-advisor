"""API Schemas for GTM Advisor."""

from .campaigns import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdate,
    ContentAssetSchema,
    EmailTemplateSchema,
)
from .common import (
    PaginatedResponse,
    PaginationParams,
    SearchParams,
)
from .competitors import (
    BattleCardResponse,
    CompetitorAlertResponse,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorResponse,
    CompetitorUpdate,
)
from .icps import (
    ICPCreate,
    ICPListResponse,
    ICPResponse,
    ICPUpdate,
    PersonaCreate,
    PersonaResponse,
    PersonaUpdate,
)
from .insights import (
    MarketInsightListResponse,
    MarketInsightResponse,
)
from .leads import (
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    LeadScoreUpdate,
    LeadUpdate,
)
from .settings import (
    UserPreferences,
    UserSettingsResponse,
    UserSettingsUpdate,
)

__all__ = [
    # Competitors
    "CompetitorCreate",
    "CompetitorUpdate",
    "CompetitorResponse",
    "CompetitorAlertResponse",
    "CompetitorListResponse",
    "BattleCardResponse",
    # ICPs
    "ICPCreate",
    "ICPUpdate",
    "ICPResponse",
    "ICPListResponse",
    "PersonaCreate",
    "PersonaUpdate",
    "PersonaResponse",
    # Leads
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
    "LeadScoreUpdate",
    # Campaigns
    "CampaignCreate",
    "CampaignUpdate",
    "CampaignResponse",
    "CampaignListResponse",
    "EmailTemplateSchema",
    "ContentAssetSchema",
    # Insights
    "MarketInsightResponse",
    "MarketInsightListResponse",
    # Settings
    "UserPreferences",
    "UserSettingsUpdate",
    "UserSettingsResponse",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "SearchParams",
]
