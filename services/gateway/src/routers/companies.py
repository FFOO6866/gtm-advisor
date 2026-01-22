"""Company management endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.core.src.types import (
    CompanyProfile,
    CompanyStage,
    IndustryVertical,
)

router = APIRouter()

# In-memory store for MVP (would be replaced with database)
_companies: dict[UUID, CompanyProfile] = {}


class CompanyCreateRequest(BaseModel):
    """Request to create a company profile."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    website: str | None = Field(default=None)
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    stage: CompanyStage = Field(default=CompanyStage.SEED)
    country: str = Field(default="Singapore")
    city: str | None = Field(default=None)
    products: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    value_proposition: str | None = Field(default=None)
    current_challenges: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)


class CompanyUpdateRequest(BaseModel):
    """Request to update a company profile."""

    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    website: str | None = Field(default=None)
    industry: IndustryVertical | None = Field(default=None)
    stage: CompanyStage | None = Field(default=None)
    products: list[str] | None = Field(default=None)
    target_markets: list[str] | None = Field(default=None)
    value_proposition: str | None = Field(default=None)
    current_challenges: list[str] | None = Field(default=None)
    goals: list[str] | None = Field(default=None)
    competitors: list[str] | None = Field(default=None)


@router.post("/", response_model=CompanyProfile)
async def create_company(request: CompanyCreateRequest) -> CompanyProfile:
    """Create a new company profile."""
    company = CompanyProfile(
        id=uuid4(),
        name=request.name,
        description=request.description,
        website=request.website,
        industry=request.industry,
        stage=request.stage,
        country=request.country,
        city=request.city,
        products=request.products,
        target_markets=request.target_markets,
        value_proposition=request.value_proposition,
        current_challenges=request.current_challenges,
        goals=request.goals,
        competitors=request.competitors,
    )

    _companies[company.id] = company
    return company


@router.get("/", response_model=list[CompanyProfile])
async def list_companies() -> list[CompanyProfile]:
    """List all company profiles."""
    return list(_companies.values())


@router.get("/{company_id}", response_model=CompanyProfile)
async def get_company(company_id: UUID) -> CompanyProfile:
    """Get a specific company profile."""
    if company_id not in _companies:
        raise HTTPException(status_code=404, detail="Company not found")
    return _companies[company_id]


@router.patch("/{company_id}", response_model=CompanyProfile)
async def update_company(
    company_id: UUID,
    request: CompanyUpdateRequest,
) -> CompanyProfile:
    """Update a company profile."""
    if company_id not in _companies:
        raise HTTPException(status_code=404, detail="Company not found")

    company = _companies[company_id]

    # Update fields that are provided
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(company, field, value)

    _companies[company_id] = company
    return company


@router.delete("/{company_id}")
async def delete_company(company_id: UUID) -> dict[str, str]:
    """Delete a company profile."""
    if company_id not in _companies:
        raise HTTPException(status_code=404, detail="Company not found")

    del _companies[company_id]
    return {"status": "deleted", "company_id": str(company_id)}
