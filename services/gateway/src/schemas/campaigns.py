"""Campaign API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmailTemplateSchema(BaseModel):
    """Schema for email template."""

    id: str | None = Field(default=None, description="Template ID")
    name: str = Field(..., description="Template name")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body (HTML or plain text)")
    type: str = Field(default="cold_outreach", description="Template type")
    variables: list[str] = Field(default_factory=list, description="Variables used in template")


class ContentAssetSchema(BaseModel):
    """Schema for content asset (LinkedIn post, ad copy, etc.)."""

    id: str | None = Field(default=None, description="Asset ID")
    type: str = Field(..., description="Asset type (linkedin_post, ad_copy, blog_outline)")
    title: str | None = Field(default=None, description="Asset title")
    content: str = Field(..., description="Asset content")
    channel: str | None = Field(default=None, description="Target channel")
    target_persona: str | None = Field(default=None, description="Target persona ID")


class CampaignCreate(BaseModel):
    """Schema for creating a campaign."""

    name: str = Field(..., min_length=1, max_length=200, description="Campaign name")
    description: str | None = Field(default=None, description="Campaign description")
    objective: str = Field(
        default="lead_gen",
        pattern="^(awareness|lead_gen|conversion|retention)$",
        description="Campaign objective",
    )

    # Target audience
    icp_id: UUID | None = Field(default=None, description="Target ICP")
    target_personas: list[str] = Field(default_factory=list, description="Target persona IDs")
    target_industries: list[str] = Field(default_factory=list, description="Target industries")
    target_company_sizes: list[str] = Field(
        default_factory=list, description="Target company sizes"
    )

    # Messaging
    key_messages: list[str] = Field(default_factory=list, description="Key messages")
    value_propositions: list[str] = Field(default_factory=list, description="Value propositions")
    call_to_action: str | None = Field(default=None, max_length=200, description="CTA")

    # Channels
    channels: list[str] = Field(default_factory=list, description="Marketing channels")

    # Budget and timeline
    budget: float | None = Field(default=None, ge=0, description="Campaign budget")
    currency: str = Field(default="SGD", max_length=3, description="Currency code")
    start_date: datetime | None = Field(default=None, description="Campaign start date")
    end_date: datetime | None = Field(default=None, description="Campaign end date")


class CampaignUpdate(BaseModel):
    """Schema for updating a campaign."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    objective: str | None = Field(
        default=None, pattern="^(awareness|lead_gen|conversion|retention)$"
    )
    status: str | None = Field(default=None, pattern="^(draft|active|paused|completed)$")
    target_personas: list[str] | None = None
    target_industries: list[str] | None = None
    target_company_sizes: list[str] | None = None
    key_messages: list[str] | None = None
    value_propositions: list[str] | None = None
    call_to_action: str | None = None
    channels: list[str] | None = None
    budget: float | None = None
    currency: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Content assets (can be updated individually or all at once)
    email_templates: list[EmailTemplateSchema] | None = None
    linkedin_posts: list[ContentAssetSchema] | None = None
    ad_copy: list[ContentAssetSchema] | None = None
    landing_page_copy: dict | None = None
    blog_outlines: list[ContentAssetSchema] | None = None


class CampaignResponse(BaseModel):
    """Schema for campaign response."""

    id: UUID
    company_id: UUID
    icp_id: UUID | None
    name: str
    description: str | None
    objective: str
    status: str

    # Target audience
    target_personas: list[str]
    target_industries: list[str]
    target_company_sizes: list[str]

    # Messaging
    key_messages: list[str]
    value_propositions: list[str]
    call_to_action: str | None

    # Channels
    channels: list[str]

    # Content assets
    email_templates: list[dict]
    linkedin_posts: list[dict]
    ad_copy: list[dict]
    landing_page_copy: dict | None
    blog_outlines: list[dict]

    # Budget and timeline
    budget: float | None
    currency: str
    start_date: datetime | None
    end_date: datetime | None

    # Metrics
    metrics: dict

    # Timestamps
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Schema for list of campaigns."""

    campaigns: list[CampaignResponse]
    total: int
    by_status: dict[str, int]
    by_objective: dict[str, int]
    total_budget: float
