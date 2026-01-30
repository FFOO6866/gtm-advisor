"""Market Insight API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MarketInsightResponse(BaseModel):
    """Schema for market insight response."""

    id: UUID
    company_id: UUID

    # Insight details
    insight_type: str  # trend, opportunity, threat, news
    category: str | None  # market, competitor, technology, regulation
    title: str
    summary: str | None
    full_content: str | None

    # Impact assessment
    impact_level: str | None  # low, medium, high
    relevance_score: float

    # Source
    source_name: str | None
    source_url: str | None
    published_at: datetime | None

    # Actionability
    recommended_actions: list[str]
    related_agents: list[str]

    # Status
    is_read: bool
    is_archived: bool

    # Timestamps
    created_at: datetime
    expires_at: datetime | None

    class Config:
        from_attributes = True


class MarketInsightListResponse(BaseModel):
    """Schema for list of market insights."""

    insights: list[MarketInsightResponse]
    total: int
    unread_count: int
    by_type: dict[str, int]  # Count by insight type
    by_impact: dict[str, int]  # Count by impact level
    recent_high_impact: list[MarketInsightResponse]  # Most recent high-impact insights


class InsightMarkRead(BaseModel):
    """Schema for marking insights as read."""

    insight_ids: list[UUID] = Field(..., description="List of insight IDs to mark as read")


class InsightArchive(BaseModel):
    """Schema for archiving insights."""

    insight_ids: list[UUID] = Field(..., description="List of insight IDs to archive")
