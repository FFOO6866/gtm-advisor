"""Company management endpoints with database persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import Company
from packages.database.src.session import get_db_session

from ..auth.dependencies import get_optional_user
from ..auth.models import User
from ..middleware.rate_limit import dynamic_limit

logger = structlog.get_logger()
router = APIRouter()


def validate_website_url(url: str | None) -> str | None:
    """Validate and normalize website URL.

    Uses permissive validation - allows any syntactically valid URL.
    Does not restrict TLDs since new ones are created regularly.

    Args:
        url: The URL to validate

    Returns:
        Normalized URL or None if input was None/empty

    Raises:
        ValueError: If URL is invalid
    """
    if url is None:
        return None

    url = url.strip()
    if not url:
        return None

    # Add https:// if no scheme provided
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Parse and validate URL structure
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Invalid URL format")

    # Validate scheme
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https protocol")

    # Validate netloc (domain)
    if not parsed.netloc:
        raise ValueError("URL must include a valid domain")

    # Extract domain parts
    domain = parsed.netloc.lower()

    # Remove port if present
    if ":" in domain:
        domain, port_str = domain.rsplit(":", 1)
        # Validate port is numeric
        if not port_str.isdigit():
            raise ValueError("Invalid port number in URL")

    # Basic domain validation
    if not domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Invalid domain format")

    # Check domain has at least one dot (TLD required)
    if "." not in domain:
        raise ValueError("Domain must include a TLD (e.g., .com, .sg)")

    # Check for valid characters in domain (RFC 1035)
    for char in domain:
        if char not in "abcdefghijklmnopqrstuvwxyz0123456789.-":
            raise ValueError(
                "Domain contains invalid character. "
                "Only letters, numbers, dots, and hyphens are allowed."
            )

    # Validate domain parts
    parts = domain.split(".")
    for part in parts:
        if not part:
            raise ValueError("Domain cannot have consecutive dots")
        if part.startswith("-") or part.endswith("-"):
            raise ValueError("Domain parts cannot start or end with hyphens")
        if len(part) > 63:
            raise ValueError("Domain label too long (max 63 characters)")

    # TLD must be at least 2 characters
    if len(parts[-1]) < 2:
        raise ValueError("TLD must be at least 2 characters")

    return url


# ============================================================================
# Schemas
# ============================================================================


class CompanyCreateRequest(BaseModel):
    """Request to create a company profile."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=100)
    funding_stage: str | None = Field(default=None, max_length=100)
    headquarters: str | None = Field(default=None, max_length=200)
    employee_count: str | None = Field(default=None, max_length=50)
    products: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    value_proposition: str | None = Field(default=None)
    challenges: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        """Validate and normalize website URL."""
        return validate_website_url(v)


class CompanyUpdateRequest(BaseModel):
    """Request to update a company profile.

    All fields are optional. Set a field to None explicitly to clear it.
    Omit a field entirely to leave it unchanged.
    """

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=100)
    funding_stage: str | None = Field(default=None, max_length=100)
    headquarters: str | None = Field(default=None, max_length=200)
    employee_count: str | None = Field(default=None, max_length=50)
    products: list[str] | None = Field(default=None)
    target_markets: list[str] | None = Field(default=None)
    value_proposition: str | None = Field(default=None)
    challenges: list[str] | None = Field(default=None)
    goals: list[str] | None = Field(default=None)
    competitors: list[str] | None = Field(default=None)
    # Special flag to clear optional fields
    clear_fields: list[str] | None = Field(
        default=None,
        description="List of field names to clear (set to NULL)",
    )

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        """Validate and normalize website URL."""
        return validate_website_url(v)


class CompanyResponse(BaseModel):
    """Company profile response."""

    id: UUID
    owner_id: UUID | None = None
    name: str
    description: str | None = None
    website: str | None = None
    industry: str | None = None
    funding_stage: str | None = None
    headquarters: str | None = None
    employee_count: str | None = None
    founded_year: str | None = None
    products: list[str] = []
    target_markets: list[str] = []
    value_proposition: str | None = None
    challenges: list[str] = []
    goals: list[str] = []
    competitors: list[str] = []
    tech_stack: list[str] = []
    enrichment_confidence: float = 0.0
    last_enriched_at: str | None = None
    created_at: str
    updated_at: str | None = None


class CompanyListResponse(BaseModel):
    """Response for listing companies with pagination."""

    companies: list[CompanyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# Helpers
# ============================================================================


def company_to_response(company: Company) -> CompanyResponse:
    """Convert database model to response schema."""
    return CompanyResponse(
        id=company.id,
        owner_id=company.owner_id,
        name=company.name,
        description=company.description,
        website=company.website,
        industry=company.industry,
        funding_stage=company.funding_stage,
        headquarters=company.headquarters,
        employee_count=company.employee_count,
        founded_year=company.founded_year,
        products=company.products or [],
        target_markets=company.target_markets or [],
        value_proposition=company.value_proposition,
        challenges=company.challenges or [],
        goals=company.goals or [],
        competitors=company.competitors or [],
        tech_stack=company.tech_stack or [],
        enrichment_confidence=company.enrichment_confidence or 0.0,
        last_enriched_at=company.last_enriched_at.isoformat() if company.last_enriched_at else None,
        created_at=company.created_at.isoformat()
        if company.created_at
        else datetime.now(UTC).isoformat(),
        updated_at=company.updated_at.isoformat() if company.updated_at else None,
    )


def check_company_access(
    company: Company,
    user: User | None,
) -> None:
    """Check if user has access to the company.

    Access rules:
    - Unowned companies (owner_id=None) are public and can be viewed/modified by anyone (MVP mode)
    - Owned companies require the owner to view/modify

    Args:
        company: The company to check access for
        user: The current user (may be None for unauthenticated)

    Raises:
        HTTPException: If access is denied
    """
    # Unowned companies are public (MVP mode) - anyone can view/modify
    if company.owner_id is None:
        return

    # Company has owner - require authentication
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access this company",
        )

    # Check ownership
    if company.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this company",
        )


def get_user_context(user: User | None) -> str:
    """Get user context string for logging."""
    if user is None:
        return "anonymous"
    return str(user.id)[:8]


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/", response_model=CompanyResponse, status_code=201)
@dynamic_limit()
async def create_company(
    request: Request,  # noqa: ARG001 - Required by rate limiter decorator
    request_data: CompanyCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> CompanyResponse:
    """Create a new company profile.

    If authenticated, the company will be owned by the current user.
    If unauthenticated (MVP mode), the company will have no owner.
    """
    company = Company(
        name=request_data.name,
        description=request_data.description,
        website=request_data.website,
        industry=request_data.industry,
        funding_stage=request_data.funding_stage,
        headquarters=request_data.headquarters,
        employee_count=request_data.employee_count,
        products=request_data.products,
        target_markets=request_data.target_markets,
        value_proposition=request_data.value_proposition,
        challenges=request_data.challenges,
        goals=request_data.goals,
        competitors=request_data.competitors,
        owner_id=current_user.id if current_user else None,
        created_at=datetime.now(UTC),
    )

    db.add(company)
    await db.flush()
    await db.refresh(company)

    logger.info(
        "company_created",
        company_id=str(company.id),
        name=company.name,
        owner_id=str(company.owner_id) if company.owner_id else None,
        user=get_user_context(current_user),
    )

    return company_to_response(company)


@router.get("/", response_model=CompanyListResponse)
@dynamic_limit()
async def list_companies(
    request: Request,  # noqa: ARG001 - Required by rate limiter decorator
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> CompanyListResponse:
    """List company profiles with pagination.

    Returns companies owned by the current user plus unowned companies.
    If unauthenticated, only returns unowned companies.
    """
    # Build query for accessible companies
    if current_user:
        # User can see their own companies and unowned companies
        query = select(Company).where(
            (Company.owner_id == current_user.id) | (Company.owner_id.is_(None))
        )
        count_query = select(func.count(Company.id)).where(
            (Company.owner_id == current_user.id) | (Company.owner_id.is_(None))
        )
    else:
        # Unauthenticated can only see unowned companies
        query = select(Company).where(Company.owner_id.is_(None))
        count_query = select(func.count(Company.id)).where(Company.owner_id.is_(None))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    offset = (page - 1) * page_size

    # Execute paginated query
    result = await db.execute(
        query.order_by(Company.created_at.desc()).offset(offset).limit(page_size)
    )
    companies = result.scalars().all()

    return CompanyListResponse(
        companies=[company_to_response(c) for c in companies],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
@dynamic_limit()
async def get_company(
    request: Request,  # noqa: ARG001 - Required by rate limiter decorator
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> CompanyResponse:
    """Get a specific company profile."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check access (view only)
    check_company_access(company, current_user)

    return company_to_response(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
@dynamic_limit()
async def update_company(
    request: Request,  # noqa: ARG001 - Required by rate limiter decorator
    company_id: UUID,
    request_data: CompanyUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> CompanyResponse:
    """Update a company profile.

    Set fields to new values to update them.
    Use clear_fields to explicitly set fields to NULL.
    """
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check access (modification requires ownership for owned companies)
    check_company_access(company, current_user)

    # Handle explicit field clearing
    clearable_fields = {
        "description",
        "website",
        "industry",
        "funding_stage",
        "headquarters",
        "employee_count",
        "value_proposition",
    }

    if request_data.clear_fields:
        for field_name in request_data.clear_fields:
            if field_name in clearable_fields:
                setattr(company, field_name, None)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Field '{field_name}' cannot be cleared",
                )

    # Update fields that are provided (excluding clear_fields and None values)
    update_data = request_data.model_dump(exclude_unset=True, exclude={"clear_fields"})
    for field, value in update_data.items():
        if value is not None:
            setattr(company, field, value)

    company.updated_at = datetime.now(UTC)
    await db.flush()

    logger.info(
        "company_updated",
        company_id=str(company_id),
        user=get_user_context(current_user),
    )

    return company_to_response(company)


@router.delete("/{company_id}", status_code=204)
@dynamic_limit()
async def delete_company(
    request: Request,  # noqa: ARG001 - Required by rate limiter decorator
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> None:
    """Delete a company profile.

    For owned companies, only the owner can delete.
    Unowned companies can be deleted by anyone (MVP mode).
    """
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check access (deletion requires ownership for owned companies)
    check_company_access(company, current_user)

    await db.delete(company)
    await db.flush()

    logger.info(
        "company_deleted",
        company_id=str(company_id),
        user=get_user_context(current_user),
    )
