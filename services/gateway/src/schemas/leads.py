"""Lead API schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


class LeadCreate(BaseModel):
    """Schema for creating a lead."""

    # Lead company info
    lead_company_name: str = Field(..., min_length=1, max_length=200, description="Lead's company name")
    lead_company_website: Optional[str] = Field(default=None, max_length=255, description="Company website")
    lead_company_industry: Optional[str] = Field(default=None, max_length=100, description="Industry")
    lead_company_size: Optional[str] = Field(default=None, max_length=50, description="Company size")
    lead_company_description: Optional[str] = Field(default=None, description="Company description")

    # Contact info (optional)
    contact_name: Optional[str] = Field(default=None, max_length=100, description="Contact person name")
    contact_title: Optional[str] = Field(default=None, max_length=100, description="Job title")
    contact_email: Optional[EmailStr] = Field(default=None, description="Contact email")
    contact_linkedin: Optional[str] = Field(default=None, max_length=255, description="LinkedIn URL")

    # Scoring
    fit_score: int = Field(default=0, ge=0, le=100, description="ICP fit score")
    intent_score: int = Field(default=0, ge=0, le=100, description="Buying intent score")

    # Source
    source: Optional[str] = Field(default=None, max_length=100, description="Lead source")
    source_url: Optional[str] = Field(default=None, max_length=500, description="Source URL")

    # ICP association
    icp_id: Optional[UUID] = Field(default=None, description="Associated ICP")

    # Qualification
    qualification_reasons: list[str] = Field(default_factory=list, description="Why this is a good lead")

    # Engagement
    notes: Optional[str] = Field(default=None, description="Notes about the lead")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""

    lead_company_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    lead_company_website: Optional[str] = None
    lead_company_industry: Optional[str] = None
    lead_company_size: Optional[str] = None
    lead_company_description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_linkedin: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(new|qualified|contacted|converted|lost)$")
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    qualification_reasons: Optional[list[str]] = None
    disqualification_reasons: Optional[list[str]] = None


class LeadScoreUpdate(BaseModel):
    """Schema for updating lead scores."""

    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    intent_score: Optional[int] = Field(default=None, ge=0, le=100)


class LeadResponse(BaseModel):
    """Schema for lead response."""

    id: UUID
    company_id: UUID
    icp_id: Optional[UUID]

    # Lead company info
    lead_company_name: str
    lead_company_website: Optional[str]
    lead_company_industry: Optional[str]
    lead_company_size: Optional[str]
    lead_company_description: Optional[str]

    # Contact info
    contact_name: Optional[str]
    contact_title: Optional[str]
    contact_email: Optional[str]
    contact_linkedin: Optional[str]

    # Scoring
    fit_score: int
    intent_score: int
    overall_score: int

    # Status
    status: str
    qualification_reasons: list[str]
    disqualification_reasons: list[str]

    # Source
    source: Optional[str]
    source_url: Optional[str]

    # Engagement
    notes: Optional[str]
    tags: list[str]

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime]
    contacted_at: Optional[datetime]
    converted_at: Optional[datetime]

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
