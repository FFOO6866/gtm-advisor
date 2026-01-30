"""Lead API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    """Schema for creating a lead."""

    # Lead company info
    lead_company_name: str = Field(
        ..., min_length=1, max_length=200, description="Lead's company name"
    )
    lead_company_website: str | None = Field(
        default=None, max_length=255, description="Company website"
    )
    lead_company_industry: str | None = Field(default=None, max_length=100, description="Industry")
    lead_company_size: str | None = Field(default=None, max_length=50, description="Company size")
    lead_company_description: str | None = Field(default=None, description="Company description")

    # Contact info (optional)
    contact_name: str | None = Field(
        default=None, max_length=100, description="Contact person name"
    )
    contact_title: str | None = Field(default=None, max_length=100, description="Job title")
    contact_email: EmailStr | None = Field(default=None, description="Contact email")
    contact_linkedin: str | None = Field(default=None, max_length=255, description="LinkedIn URL")

    # Scoring
    fit_score: int = Field(default=0, ge=0, le=100, description="ICP fit score")
    intent_score: int = Field(default=0, ge=0, le=100, description="Buying intent score")

    # Source
    source: str | None = Field(default=None, max_length=100, description="Lead source")
    source_url: str | None = Field(default=None, max_length=500, description="Source URL")

    # ICP association
    icp_id: UUID | None = Field(default=None, description="Associated ICP")

    # Qualification
    qualification_reasons: list[str] = Field(
        default_factory=list, description="Why this is a good lead"
    )

    # Engagement
    notes: str | None = Field(default=None, description="Notes about the lead")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""

    lead_company_name: str | None = Field(default=None, min_length=1, max_length=200)
    lead_company_website: str | None = None
    lead_company_industry: str | None = None
    lead_company_size: str | None = None
    lead_company_description: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    contact_email: EmailStr | None = None
    contact_linkedin: str | None = None
    status: str | None = Field(default=None, pattern="^(new|qualified|contacted|converted|lost)$")
    notes: str | None = None
    tags: list[str] | None = None
    qualification_reasons: list[str] | None = None
    disqualification_reasons: list[str] | None = None


class LeadScoreUpdate(BaseModel):
    """Schema for updating lead scores."""

    fit_score: int | None = Field(default=None, ge=0, le=100)
    intent_score: int | None = Field(default=None, ge=0, le=100)


class LeadResponse(BaseModel):
    """Schema for lead response."""

    id: UUID
    company_id: UUID
    icp_id: UUID | None

    # Lead company info
    lead_company_name: str
    lead_company_website: str | None
    lead_company_industry: str | None
    lead_company_size: str | None
    lead_company_description: str | None

    # Contact info
    contact_name: str | None
    contact_title: str | None
    contact_email: str | None
    contact_linkedin: str | None

    # Scoring
    fit_score: int
    intent_score: int
    overall_score: int

    # Status
    status: str
    qualification_reasons: list[str]
    disqualification_reasons: list[str]

    # Source
    source: str | None
    source_url: str | None

    # Engagement
    notes: str | None
    tags: list[str]

    # Timestamps
    created_at: datetime
    updated_at: datetime | None
    contacted_at: datetime | None
    converted_at: datetime | None

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Schema for list of leads with stats."""

    leads: list[LeadResponse]
    total: int
    by_status: dict[str, int]  # Count by status
    avg_fit_score: float
    avg_intent_score: float
    high_score_count: int  # Leads with overall_score > 80
