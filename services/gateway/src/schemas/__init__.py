"""API Schemas for GTM Advisor."""

from .competitors import (
    CompetitorCreate,
    CompetitorUpdate,
    CompetitorResponse,
    CompetitorAlertResponse,
    CompetitorListResponse,
    BattleCardResponse,
)
from .icps import (
    ICPCreate,
    ICPUpdate,
    ICPResponse,
    ICPListResponse,
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
)
from .leads import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadScoreUpdate,
)
from .campaigns import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    EmailTemplateSchema,
    ContentAssetSchema,
)
from .insights import (
    MarketInsightResponse,
    MarketInsightListResponse,
)
from .settings import (
    UserPreferences,
    UserSettingsUpdate,
    UserSettingsResponse,
)
from .common import (
    PaginationParams,
    PaginatedResponse,
    SearchParams,
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
