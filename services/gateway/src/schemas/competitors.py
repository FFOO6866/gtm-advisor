"""Competitor-related API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CompetitorCreate(BaseModel):
    """Schema for creating a competitor."""

    name: str = Field(..., min_length=1, max_length=200, description="Competitor company name")
    website: str | None = Field(default=None, max_length=255, description="Competitor website URL")
    description: str | None = Field(default=None, description="Brief description of the competitor")
    threat_level: str = Field(
        default="medium", pattern="^(low|medium|high)$", description="Threat assessment level"
    )
    positioning: str | None = Field(default=None, description="Their market positioning")

    # SWOT Analysis (can be populated later)
    strengths: list[str] = Field(default_factory=list, description="Competitor strengths")
    weaknesses: list[str] = Field(default_factory=list, description="Competitor weaknesses")
    opportunities: list[str] = Field(
        default_factory=list, description="Our opportunities against them"
    )
    threats: list[str] = Field(default_factory=list, description="Threats they pose")

    # Battle card data
    our_advantages: list[str] = Field(default_factory=list, description="Our advantages over them")
    their_advantages: list[str] = Field(
        default_factory=list, description="Their advantages over us"
    )
    key_objection_handlers: list[str] = Field(
        default_factory=list, description="How to handle objections"
    )

    # Pricing
    pricing_info: dict | None = Field(default=None, description="Known pricing information")


class CompetitorUpdate(BaseModel):
    """Schema for updating a competitor."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None
    threat_level: str | None = Field(default=None, pattern="^(low|medium|high)$")
    positioning: str | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    opportunities: list[str] | None = None
    threats: list[str] | None = None
    our_advantages: list[str] | None = None
    their_advantages: list[str] | None = None
    key_objection_handlers: list[str] | None = None
    pricing_info: dict | None = None
    is_active: bool | None = None


class CompetitorResponse(BaseModel):
    """Schema for competitor response."""

    id: UUID
    company_id: UUID
    name: str
    website: str | None
    description: str | None
    threat_level: str
    positioning: str | None
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]
    our_advantages: list[str]
    their_advantages: list[str]
    key_objection_handlers: list[str]
    pricing_info: dict | None
    is_active: bool
    last_updated: datetime
    created_at: datetime
    updated_at: datetime | None

    # Computed fields
    alert_count: int = Field(default=0, description="Number of unread alerts")

    class Config:
        from_attributes = True


class CompetitorAlertResponse(BaseModel):
    """Schema for competitor alert response."""

    id: UUID
    competitor_id: UUID
    alert_type: str
    severity: str
    title: str
    description: str | None
    source_url: str | None
    is_read: bool
    is_dismissed: bool
    detected_at: datetime
    read_at: datetime | None

    class Config:
        from_attributes = True


class CompetitorListResponse(BaseModel):
    """Schema for list of competitors with summary stats."""

    competitors: list[CompetitorResponse]
    total: int
    high_threat_count: int
    medium_threat_count: int
    low_threat_count: int
    unread_alerts_count: int


class BattleCardResponse(BaseModel):
    """Battle card for sales enablement."""

    competitor_id: UUID
    competitor_name: str
    our_advantages: list[str]
    their_advantages: list[str]
    key_objection_handlers: list[str]
    positioning: str | None
    pricing_comparison: dict | None
    win_strategies: list[str]
    generated_at: datetime
