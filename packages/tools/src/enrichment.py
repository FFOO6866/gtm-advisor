"""Enrichment Tools for Company and Contact Data.

Integrates with external APIs to enrich lead and company data.
All tools have rate limiting and caching built-in.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from .base import (
    BaseTool,
    RateLimitConfig,
    ToolAccess,
    ToolCategory,
    ToolResult,
)


@dataclass
class CompanyData:
    """Enriched company data."""

    name: str
    domain: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    employee_range: str | None = None
    founded_year: int | None = None
    revenue_range: str | None = None
    funding_total: float | None = None
    funding_stage: str | None = None
    description: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    location: dict[str, str] = field(default_factory=dict)
    technologies: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "employee_range": self.employee_range,
            "founded_year": self.founded_year,
            "revenue_range": self.revenue_range,
            "funding_total": self.funding_total,
            "funding_stage": self.funding_stage,
            "description": self.description,
            "linkedin_url": self.linkedin_url,
            "twitter_url": self.twitter_url,
            "location": self.location,
            "technologies": self.technologies,
            "keywords": self.keywords,
        }


@dataclass
class ContactData:
    """Enriched contact data."""

    name: str
    email: str | None = None
    email_verified: bool = False
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    location: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "email_verified": self.email_verified,
            "title": self.title,
            "seniority": self.seniority,
            "department": self.department,
            "linkedin_url": self.linkedin_url,
            "phone": self.phone,
            "company_name": self.company_name,
            "company_domain": self.company_domain,
            "location": self.location,
        }


class CompanyEnrichmentTool(BaseTool):
    """Enrich company data from domain or name.

    Sources: Clearbit, Apollo, LinkedIn API (configurable)
    """

    name = "company_enrichment"
    description = "Enrich company data from domain, name, or LinkedIn URL"
    category = ToolCategory.ENRICHMENT
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        burst_limit=5,
    )

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        api_key: str | None = None,
        provider: str = "mock",  # mock, clearbit, apollo
    ):
        super().__init__(agent_id, allowed_access)
        self.api_key = api_key or os.getenv("ENRICHMENT_API_KEY")
        self.provider = provider
        self._cache: dict[str, CompanyData] = {}

    async def _execute(self, **kwargs: Any) -> ToolResult[CompanyData]:
        """Enrich company by domain or name."""
        domain = kwargs.get("domain")
        name = kwargs.get("name")
        linkedin_url = kwargs.get("linkedin_url")

        if not any([domain, name, linkedin_url]):
            return ToolResult(
                success=False,
                data=None,
                error="Must provide domain, name, or linkedin_url",
            )

        # Check cache
        cache_key = domain or name or linkedin_url
        if cache_key in self._cache:
            return ToolResult(
                success=True,
                data=self._cache[cache_key],
                cached=True,
            )

        # Route to provider
        if self.provider == "mock":
            data = await self._mock_enrich(domain, name)
        elif self.provider == "clearbit":
            data = await self._clearbit_enrich(domain)
        elif self.provider == "apollo":
            data = await self._apollo_enrich(domain, name)
        else:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown provider: {self.provider}",
            )

        if data:
            self._cache[cache_key] = data

        return ToolResult(
            success=data is not None,
            data=data,
            error=None if data else "Company not found",
        )

    async def _mock_enrich(
        self,
        domain: str | None,
        name: str | None,
    ) -> CompanyData | None:
        """Mock enrichment for testing/demo."""
        # Simulate API latency
        await asyncio.sleep(0.1)

        # Singapore company mock data
        mock_companies = {
            "grab.com": CompanyData(
                name="Grab Holdings",
                domain="grab.com",
                industry="Transportation/Technology",
                employee_count=8000,
                employee_range="5001-10000",
                founded_year=2012,
                revenue_range="$1B+",
                funding_total=10_000_000_000,
                funding_stage="Public",
                description="Southeast Asia's leading superapp",
                linkedin_url="https://linkedin.com/company/grab",
                location={"city": "Singapore", "country": "Singapore"},
                technologies=["React", "Go", "Kubernetes", "AWS"],
            ),
            "shopee.sg": CompanyData(
                name="Shopee Singapore",
                domain="shopee.sg",
                industry="E-commerce",
                employee_count=15000,
                employee_range="10001+",
                founded_year=2015,
                revenue_range="$5B+",
                funding_stage="Public (SEA Limited)",
                description="Leading e-commerce platform in Southeast Asia",
                linkedin_url="https://linkedin.com/company/shopee",
                location={"city": "Singapore", "country": "Singapore"},
                technologies=["Java", "React", "MySQL", "Redis"],
            ),
        }

        if domain and domain.lower() in mock_companies:
            return mock_companies[domain.lower()]

        # Generate mock data for unknown domains
        if domain:
            return CompanyData(
                name=name or domain.split(".")[0].title(),
                domain=domain,
                industry="Technology",
                employee_count=50,
                employee_range="11-50",
                description=f"Company at {domain}",
                location={"city": "Singapore", "country": "Singapore"},
            )

        return None

    async def _clearbit_enrich(self, domain: str | None) -> CompanyData | None:
        """Enrich via Clearbit API."""
        if not domain or not self.api_key:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://company.clearbit.com/v2/companies/find",
                    params={"domain": domain},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return CompanyData(
                        name=data.get("name", ""),
                        domain=data.get("domain"),
                        industry=data.get("category", {}).get("industry"),
                        employee_count=data.get("metrics", {}).get("employees"),
                        employee_range=data.get("metrics", {}).get("employeesRange"),
                        founded_year=data.get("foundedYear"),
                        description=data.get("description"),
                        linkedin_url=data.get("linkedin", {}).get("handle"),
                        twitter_url=data.get("twitter", {}).get("handle"),
                        location={
                            "city": data.get("geo", {}).get("city"),
                            "country": data.get("geo", {}).get("country"),
                        },
                        technologies=data.get("tech", []),
                        raw_data=data,
                    )
            except Exception:
                pass

        return None

    async def _apollo_enrich(
        self,
        domain: str | None,
        name: str | None,
    ) -> CompanyData | None:
        """Enrich via Apollo API."""
        if not self.api_key:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.apollo.io/v1/organizations/enrich",
                    headers={"Content-Type": "application/json"},
                    json={
                        "api_key": self.api_key,
                        "domain": domain,
                        "name": name,
                    },
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json().get("organization", {})
                    return CompanyData(
                        name=data.get("name", ""),
                        domain=data.get("primary_domain"),
                        industry=data.get("industry"),
                        employee_count=data.get("estimated_num_employees"),
                        founded_year=data.get("founded_year"),
                        funding_total=data.get("total_funding"),
                        linkedin_url=data.get("linkedin_url"),
                        location={
                            "city": data.get("city"),
                            "country": data.get("country"),
                        },
                        technologies=data.get("technologies", []),
                        keywords=data.get("keywords", []),
                        raw_data=data,
                    )
            except Exception:
                pass

        return None


class ContactEnrichmentTool(BaseTool):
    """Enrich contact/person data.

    Sources: Apollo, Clearbit, Hunter.io
    """

    name = "contact_enrichment"
    description = "Enrich contact data from email or LinkedIn URL"
    category = ToolCategory.ENRICHMENT
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=300,
        burst_limit=3,
    )

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        api_key: str | None = None,
        provider: str = "mock",
    ):
        super().__init__(agent_id, allowed_access)
        self.api_key = api_key or os.getenv("CONTACT_API_KEY")
        self.provider = provider
        self._cache: dict[str, ContactData] = {}

    async def _execute(self, **kwargs: Any) -> ToolResult[ContactData]:
        """Enrich contact by email or LinkedIn."""
        email = kwargs.get("email")
        linkedin_url = kwargs.get("linkedin_url")
        name = kwargs.get("name")
        company_domain = kwargs.get("company_domain")

        if not any([email, linkedin_url, (name and company_domain)]):
            return ToolResult(
                success=False,
                data=None,
                error="Must provide email, linkedin_url, or name+company_domain",
            )

        cache_key = email or linkedin_url or f"{name}@{company_domain}"
        if cache_key in self._cache:
            return ToolResult(
                success=True,
                data=self._cache[cache_key],
                cached=True,
            )

        if self.provider == "mock":
            data = await self._mock_enrich(email, name, company_domain)
        else:
            data = await self._api_enrich(email, linkedin_url, name, company_domain)

        if data:
            self._cache[cache_key] = data

        return ToolResult(
            success=data is not None,
            data=data,
            error=None if data else "Contact not found",
        )

    async def _mock_enrich(
        self,
        email: str | None,
        name: str | None,
        company_domain: str | None,
    ) -> ContactData | None:
        """Mock enrichment for testing."""
        await asyncio.sleep(0.05)

        if email:
            parts = email.split("@")
            name_part = parts[0].replace(".", " ").title()
            domain = parts[1] if len(parts) > 1 else None

            return ContactData(
                name=name_part,
                email=email,
                email_verified=True,
                title="Manager",
                seniority="mid",
                department="Business",
                company_domain=domain,
                location={"country": "Singapore"},
            )

        if name and company_domain:
            return ContactData(
                name=name,
                email=f"{name.lower().replace(' ', '.')}@{company_domain}",
                email_verified=False,
                company_domain=company_domain,
                location={"country": "Singapore"},
            )

        return None

    async def _api_enrich(
        self,
        email: str | None,
        linkedin_url: str | None,
        name: str | None,
        company_domain: str | None,
    ) -> ContactData | None:
        """Enrich via API provider."""
        # Implementation would call actual API
        return None


class EmailFinderTool(BaseTool):
    """Find email addresses for contacts.

    Uses pattern matching and verification.
    """

    name = "email_finder"
    description = "Find and verify email addresses for contacts"
    category = ToolCategory.ENRICHMENT
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=2,
    )

    # Common email patterns
    PATTERNS = [
        "{first}.{last}@{domain}",
        "{first}@{domain}",
        "{first}{last}@{domain}",
        "{f}{last}@{domain}",
        "{first}_{last}@{domain}",
    ]

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        api_key: str | None = None,
        verify_emails: bool = True,
    ):
        super().__init__(agent_id, allowed_access)
        self.api_key = api_key
        self.verify_emails = verify_emails
        self._verified_patterns: dict[str, str] = {}  # domain -> pattern

    async def _execute(self, **kwargs: Any) -> ToolResult[dict[str, Any]]:
        """Find email for a contact."""
        first_name = kwargs.get("first_name", "").lower()
        last_name = kwargs.get("last_name", "").lower()
        domain = kwargs.get("domain", "")

        if not all([first_name, last_name, domain]):
            return ToolResult(
                success=False,
                data=None,
                error="Must provide first_name, last_name, and domain",
            )

        # Check if we know the pattern for this domain
        if domain in self._verified_patterns:
            pattern = self._verified_patterns[domain]
            email = self._apply_pattern(pattern, first_name, last_name, domain)
            return ToolResult(
                success=True,
                data={
                    "email": email,
                    "pattern": pattern,
                    "confidence": 0.9,
                    "verified": False,
                },
            )

        # Generate candidates
        candidates = self._generate_candidates(first_name, last_name, domain)

        # In production, we'd verify these
        best_candidate = candidates[0] if candidates else None

        return ToolResult(
            success=bool(best_candidate),
            data={
                "email": best_candidate,
                "candidates": candidates[:5],
                "confidence": 0.6,
                "verified": False,
            }
            if best_candidate
            else None,
        )

    def _generate_candidates(
        self,
        first: str,
        last: str,
        domain: str,
    ) -> list[str]:
        """Generate email candidates from patterns."""
        candidates = []
        for pattern in self.PATTERNS:
            email = self._apply_pattern(pattern, first, last, domain)
            candidates.append(email)
        return candidates

    def _apply_pattern(
        self,
        pattern: str,
        first: str,
        last: str,
        domain: str,
    ) -> str:
        """Apply pattern to generate email."""
        return pattern.format(
            first=first,
            last=last,
            f=first[0] if first else "",
            l=last[0] if last else "",
            domain=domain,
        )

    async def verify_email(self, email: str) -> bool:
        """Verify if email exists (simplified)."""
        # In production, this would do SMTP verification
        # or use a verification service
        return True
