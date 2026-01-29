"""ICP and Persona API schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PersonaCreate(BaseModel):
    """Schema for creating a buyer persona."""

    name: str = Field(..., min_length=1, max_length=100, description="Persona name (e.g., 'Marketing Michelle')")
    role: str = Field(..., min_length=1, max_length=100, description="Job title/role")
    avatar: Optional[str] = Field(default=None, max_length=10, description="Emoji or icon")

    # Demographics
    age_range: Optional[str] = Field(default=None, max_length=20, description="Age range (e.g., '30-40')")
    experience_years: Optional[str] = Field(default=None, max_length=20, description="Years of experience")
    education: Optional[str] = Field(default=None, max_length=100, description="Education level")

    # Psychographics
    goals: list[str] = Field(default_factory=list, description="Professional goals")
    challenges: list[str] = Field(default_factory=list, description="Key challenges")
    objections: list[str] = Field(default_factory=list, description="Common objections")

    # Engagement
    preferred_channels: list[str] = Field(default_factory=list, description="Preferred communication channels")
    messaging_hooks: list[str] = Field(default_factory=list, description="Messaging that resonates")
    content_preferences: list[str] = Field(default_factory=list, description="Preferred content types")


class PersonaUpdate(BaseModel):
    """Schema for updating a persona."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, min_length=1, max_length=100)
    avatar: Optional[str] = Field(default=None, max_length=10)
    age_range: Optional[str] = None
    experience_years: Optional[str] = None
    education: Optional[str] = None
    goals: Optional[list[str]] = None
    challenges: Optional[list[str]] = None
    objections: Optional[list[str]] = None
    preferred_channels: Optional[list[str]] = None
    messaging_hooks: Optional[list[str]] = None
    content_preferences: Optional[list[str]] = None
    is_active: Optional[bool] = None


class PersonaResponse(BaseModel):
    """Schema for persona response."""

    id: UUID
    icp_id: UUID
    name: str
    role: str
    avatar: Optional[str]
    age_range: Optional[str]
    experience_years: Optional[str]
    education: Optional[str]
    goals: list[str]
    challenges: list[str]
    objections: list[str]
    preferred_channels: list[str]
    messaging_hooks: list[str]
    content_preferences: list[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ICPCreate(BaseModel):
    """Schema for creating an Ideal Customer Profile."""

    name: str = Field(..., min_length=1, max_length=200, description="ICP name (e.g., 'Growth-Stage SaaS')")
    description: Optional[str] = Field(default=None, description="Description of this ICP")
    fit_score: int = Field(default=0, ge=0, le=100, description="Fit score 0-100")

    # Characteristics
    company_size: Optional[str] = Field(default=None, max_length=100, description="Target company size")
    revenue_range: Optional[str] = Field(default=None, max_length=100, description="Revenue range")
    industry: Optional[str] = Field(default=None, max_length=100, description="Target industry")
    tech_stack: Optional[str] = Field(default=None, max_length=200, description="Tech stack preference")
    buying_triggers: list[str] = Field(default_factory=list, description="Events that trigger buying")

    # Pain points
    pain_points: list[str] = Field(default_factory=list, description="Key pain points")
    needs: list[str] = Field(default_factory=list, description="Key needs")


class ICPUpdate(BaseModel):
    """Schema for updating an ICP."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    company_size: Optional[str] = None
    revenue_range: Optional[str] = None
    industry: Optional[str] = None
    tech_stack: Optional[str] = None
    buying_triggers: Optional[list[str]] = None
    pain_points: Optional[list[str]] = None
    needs: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ICPResponse(BaseModel):
    """Schema for ICP response."""

    id: UUID
    company_id: UUID
    name: str
    description: Optional[str]
    fit_score: int
    company_size: Optional[str]
    revenue_range: Optional[str]
    industry: Optional[str]
    tech_stack: Optional[str]
    buying_triggers: list[str]
    pain_points: list[str]
    needs: list[str]
    matching_companies_count: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

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
