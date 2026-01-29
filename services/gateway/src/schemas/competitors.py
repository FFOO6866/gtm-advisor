"""Competitor-related API schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class CompetitorCreate(BaseModel):
    """Schema for creating a competitor."""

    name: str = Field(..., min_length=1, max_length=200, description="Competitor company name")
    website: Optional[str] = Field(default=None, max_length=255, description="Competitor website URL")
    description: Optional[str] = Field(default=None, description="Brief description of the competitor")
    threat_level: str = Field(default="medium", pattern="^(low|medium|high)$", description="Threat assessment level")
    positioning: Optional[str] = Field(default=None, description="Their market positioning")

    # SWOT Analysis (can be populated later)
    strengths: list[str] = Field(default_factory=list, description="Competitor strengths")
    weaknesses: list[str] = Field(default_factory=list, description="Competitor weaknesses")
    opportunities: list[str] = Field(default_factory=list, description="Our opportunities against them")
    threats: list[str] = Field(default_factory=list, description="Threats they pose")

    # Battle card data
    our_advantages: list[str] = Field(default_factory=list, description="Our advantages over them")
    their_advantages: list[str] = Field(default_factory=list, description="Their advantages over us")
    key_objection_handlers: list[str] = Field(default_factory=list, description="How to handle objections")

    # Pricing
    pricing_info: Optional[dict] = Field(default=None, description="Known pricing information")


class CompetitorUpdate(BaseModel):
    """Schema for updating a competitor."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    website: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    threat_level: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")
    positioning: Optional[str] = None
    strengths: Optional[list[str]] = None
    weaknesses: Optional[list[str]] = None
    opportunities: Optional[list[str]] = None
    threats: Optional[list[str]] = None
    our_advantages: Optional[list[str]] = None
    their_advantages: Optional[list[str]] = None
    key_objection_handlers: Optional[list[str]] = None
    pricing_info: Optional[dict] = None
    is_active: Optional[bool] = None


class CompetitorResponse(BaseModel):
    """Schema for competitor response."""

    id: UUID
    company_id: UUID
    name: str
    website: Optional[str]
    description: Optional[str]
    threat_level: str
    positioning: Optional[str]
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]
    our_advantages: list[str]
    their_advantages: list[str]
    key_objection_handlers: list[str]
    pricing_info: Optional[dict]
    is_active: bool
    last_updated: datetime
    created_at: datetime
    updated_at: Optional[datetime]

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
    description: Optional[str]
    source_url: Optional[str]
    is_read: bool
    is_dismissed: bool
    detected_at: datetime
    read_at: Optional[datetime]

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
    positioning: Optional[str]
    pricing_comparison: Optional[dict]
    win_strategies: list[str]
    generated_at: datetime
