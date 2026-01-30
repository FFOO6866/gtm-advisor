"""User settings API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationPreferences(BaseModel):
    """Notification preference settings."""

    email_alerts: bool = Field(default=True, description="Receive email alerts")
    competitor_alerts: bool = Field(default=True, description="Alerts for competitor changes")
    lead_alerts: bool = Field(default=True, description="Alerts for new high-quality leads")
    insight_alerts: bool = Field(default=True, description="Alerts for market insights")
    weekly_digest: bool = Field(default=True, description="Weekly summary email")


class DisplayPreferences(BaseModel):
    """UI display preferences."""

    theme: str = Field(default="dark", pattern="^(dark|light|auto)$")
    dashboard_layout: str = Field(default="default", pattern="^(default|compact|expanded)$")
    default_tab: str = Field(default="overview", description="Default tab when opening workspaces")
    show_confidence_scores: bool = Field(default=True, description="Show AI confidence scores")


class APIKeySettings(BaseModel):
    """API key management."""

    openai_configured: bool = Field(default=False)
    perplexity_configured: bool = Field(default=False)
    newsapi_configured: bool = Field(default=False)
    eodhd_configured: bool = Field(default=False)

    # These are write-only - never returned in responses
    openai_api_key: str | None = Field(default=None, description="OpenAI API key (write-only)")
    perplexity_api_key: str | None = Field(
        default=None, description="Perplexity API key (write-only)"
    )
    newsapi_api_key: str | None = Field(default=None, description="NewsAPI key (write-only)")
    eodhd_api_key: str | None = Field(default=None, description="EODHD API key (write-only)")


class AgentPreferences(BaseModel):
    """Agent execution preferences."""

    auto_run_enrichment: bool = Field(
        default=True, description="Auto-run company enricher on new companies"
    )
    confidence_threshold: float = Field(
        default=0.7, ge=0, le=1, description="Minimum confidence for recommendations"
    )
    max_leads_per_run: int = Field(
        default=10, ge=1, le=50, description="Maximum leads to generate per run"
    )
    enable_a2a_sharing: bool = Field(
        default=True, description="Enable agent-to-agent discovery sharing"
    )
    parallel_execution: bool = Field(default=True, description="Enable parallel agent execution")


class UserPreferences(BaseModel):
    """Combined user preferences."""

    notifications: NotificationPreferences = Field(default_factory=NotificationPreferences)
    display: DisplayPreferences = Field(default_factory=DisplayPreferences)
    agents: AgentPreferences = Field(default_factory=AgentPreferences)


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings."""

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    preferences: UserPreferences | None = None

    # API keys (write-only, never returned)
    api_keys: APIKeySettings | None = None


class UserSettingsResponse(BaseModel):
    """Schema for user settings response."""

    id: UUID
    email: str
    full_name: str
    company_name: str | None

    # Subscription
    tier: str
    tier_display_name: str
    tier_limits: dict

    # Usage
    daily_requests: int
    daily_limit: int
    usage_percentage: float

    # Preferences
    preferences: UserPreferences

    # API key status (never returns actual keys)
    api_keys_configured: APIKeySettings

    # Timestamps
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class SubscriptionInfo(BaseModel):
    """Subscription tier information."""

    tier: str
    display_name: str
    price_monthly: float
    currency: str
    features: list[str]
    limits: dict
    is_current: bool


class SubscriptionTiersResponse(BaseModel):
    """All available subscription tiers."""

    tiers: list[SubscriptionInfo]
    current_tier: str
