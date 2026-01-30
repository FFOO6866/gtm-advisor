"""ICP and Persona API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PersonaCreate(BaseModel):
    """Schema for creating a buyer persona."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Persona name (e.g., 'Marketing Michelle')"
    )
    role: str = Field(..., min_length=1, max_length=100, description="Job title/role")
    avatar: str | None = Field(default=None, max_length=10, description="Emoji or icon")

    # Demographics
    age_range: str | None = Field(
        default=None, max_length=20, description="Age range (e.g., '30-40')"
    )
    experience_years: str | None = Field(
        default=None, max_length=20, description="Years of experience"
    )
    education: str | None = Field(default=None, max_length=100, description="Education level")

    # Psychographics
    goals: list[str] = Field(default_factory=list, description="Professional goals")
    challenges: list[str] = Field(default_factory=list, description="Key challenges")
    objections: list[str] = Field(default_factory=list, description="Common objections")

    # Engagement
    preferred_channels: list[str] = Field(
        default_factory=list, description="Preferred communication channels"
    )
    messaging_hooks: list[str] = Field(default_factory=list, description="Messaging that resonates")
    content_preferences: list[str] = Field(
        default_factory=list, description="Preferred content types"
    )


class PersonaUpdate(BaseModel):
    """Schema for updating a persona."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=100)
    avatar: str | None = Field(default=None, max_length=10)
    age_range: str | None = None
    experience_years: str | None = None
    education: str | None = None
    goals: list[str] | None = None
    challenges: list[str] | None = None
    objections: list[str] | None = None
    preferred_channels: list[str] | None = None
    messaging_hooks: list[str] | None = None
    content_preferences: list[str] | None = None
    is_active: bool | None = None


class PersonaResponse(BaseModel):
    """Schema for persona response."""

    id: UUID
    icp_id: UUID
    name: str
    role: str
    avatar: str | None
    age_range: str | None
    experience_years: str | None
    education: str | None
    goals: list[str]
    challenges: list[str]
    objections: list[str]
    preferred_channels: list[str]
    messaging_hooks: list[str]
    content_preferences: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ICPCreate(BaseModel):
    """Schema for creating an Ideal Customer Profile."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="ICP name (e.g., 'Growth-Stage SaaS')"
    )
    description: str | None = Field(default=None, description="Description of this ICP")
    fit_score: int = Field(default=0, ge=0, le=100, description="Fit score 0-100")

    # Characteristics
    company_size: str | None = Field(
        default=None, max_length=100, description="Target company size"
    )
    revenue_range: str | None = Field(default=None, max_length=100, description="Revenue range")
    industry: str | None = Field(default=None, max_length=100, description="Target industry")
    tech_stack: str | None = Field(
        default=None, max_length=200, description="Tech stack preference"
    )
    buying_triggers: list[str] = Field(
        default_factory=list, description="Events that trigger buying"
    )

    # Pain points
    pain_points: list[str] = Field(default_factory=list, description="Key pain points")
    needs: list[str] = Field(default_factory=list, description="Key needs")


class ICPUpdate(BaseModel):
    """Schema for updating an ICP."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    fit_score: int | None = Field(default=None, ge=0, le=100)
    company_size: str | None = None
    revenue_range: str | None = None
    industry: str | None = None
    tech_stack: str | None = None
    buying_triggers: list[str] | None = None
    pain_points: list[str] | None = None
    needs: list[str] | None = None
    is_active: bool | None = None


class ICPResponse(BaseModel):
    """Schema for ICP response."""

    id: UUID
    company_id: UUID
    name: str
    description: str | None
    fit_score: int
    company_size: str | None
    revenue_range: str | None
    industry: str | None
    tech_stack: str | None
    buying_triggers: list[str]
    pain_points: list[str]
    needs: list[str]
    matching_companies_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    # Nested personas
    personas: list[PersonaResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ICPListResponse(BaseModel):
    """Schema for list of ICPs."""

    icps: list[ICPResponse]
    total: int
    active_count: int
    total_personas: int
