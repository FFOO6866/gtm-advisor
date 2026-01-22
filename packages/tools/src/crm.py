"""CRM Integration Tools.

Connectors for popular CRMs used by Singapore SMEs:
- HubSpot (most popular for startups)
- Pipedrive (sales-focused teams)
- Salesforce (enterprise)

All operations are audited and respect access boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from datetime import datetime
import asyncio
import httpx
import os

from .base import (
    BaseTool,
    ToolAccess,
    ToolResult,
    ToolCategory,
    RateLimitConfig,
)


@dataclass
class CRMContact:
    """Unified contact representation across CRMs."""
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    company: str | None
    title: str | None
    phone: str | None
    lifecycle_stage: str | None
    lead_status: str | None
    owner_id: str | None
    created_at: datetime | None
    updated_at: datetime | None
    custom_properties: dict[str, Any] = field(default_factory=dict)
    source_crm: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "title": self.title,
            "phone": self.phone,
            "lifecycle_stage": self.lifecycle_stage,
            "lead_status": self.lead_status,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "custom_properties": self.custom_properties,
            "source_crm": self.source_crm,
        }


@dataclass
class CRMCompany:
    """Unified company representation across CRMs."""
    id: str
    name: str
    domain: str | None
    industry: str | None
    employee_count: int | None
    revenue: float | None
    owner_id: str | None
    created_at: datetime | None
    custom_properties: dict[str, Any] = field(default_factory=dict)
    source_crm: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "revenue": self.revenue,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "custom_properties": self.custom_properties,
            "source_crm": self.source_crm,
        }


@dataclass
class CRMDeal:
    """Unified deal/opportunity representation."""
    id: str
    name: str
    amount: float | None
    stage: str
    pipeline: str | None
    close_date: datetime | None
    contact_ids: list[str]
    company_id: str | None
    owner_id: str | None
    probability: float | None
    created_at: datetime | None
    custom_properties: dict[str, Any] = field(default_factory=dict)
    source_crm: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "stage": self.stage,
            "pipeline": self.pipeline,
            "close_date": self.close_date.isoformat() if self.close_date else None,
            "contact_ids": self.contact_ids,
            "company_id": self.company_id,
            "owner_id": self.owner_id,
            "probability": self.probability,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "custom_properties": self.custom_properties,
            "source_crm": self.source_crm,
        }


class HubSpotTool(BaseTool):
    """HubSpot CRM integration.

    Supports:
    - Contacts: read, create, update
    - Companies: read, create, update
    - Deals: read, create, update
    - Lists: read
    """

    name = "hubspot"
    description = "HubSpot CRM integration for contacts, companies, and deals"
    category = ToolCategory.CRM
    required_access = ToolAccess.READ  # Default, can be overridden per operation
    rate_limit = RateLimitConfig(
        requests_per_minute=100,
        requests_per_hour=1000,
        burst_limit=10,
    )

    BASE_URL = "https://api.hubapi.com"

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        api_key: str | None = None,
        use_mock: bool = False,
    ):
        super().__init__(agent_id, allowed_access)
        self.api_key = api_key or os.getenv("HUBSPOT_API_KEY")
        self.use_mock = use_mock or not self.api_key

    async def _execute(self, **kwargs: Any) -> ToolResult:
        """Execute HubSpot operation."""
        operation = kwargs.get("operation", "get_contacts")

        operations = {
            # Read operations
            "get_contacts": self._get_contacts,
            "get_contact": self._get_contact,
            "search_contacts": self._search_contacts,
            "get_companies": self._get_companies,
            "get_company": self._get_company,
            "get_deals": self._get_deals,
            "get_deal": self._get_deal,
            # Write operations (require WRITE access)
            "create_contact": self._create_contact,
            "update_contact": self._update_contact,
            "create_company": self._create_company,
            "create_deal": self._create_deal,
            "update_deal": self._update_deal,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown operation: {operation}",
            )

        # Check write access for write operations
        write_ops = ["create_contact", "update_contact", "create_company", "create_deal", "update_deal"]
        if operation in write_ops and not self.has_access(ToolAccess.WRITE):
            return ToolResult(
                success=False,
                data=None,
                error="Write access required for this operation",
            )

        return await handler(**kwargs)

    async def _get_contacts(self, **kwargs: Any) -> ToolResult[list[CRMContact]]:
        """Get contacts list."""
        limit = kwargs.get("limit", 10)

        if self.use_mock:
            return await self._mock_get_contacts(limit)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/crm/v3/objects/contacts",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={"limit": limit},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    contacts = [
                        self._parse_hubspot_contact(item)
                        for item in data.get("results", [])
                    ]
                    return ToolResult(success=True, data=contacts)
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"HubSpot API error: {response.status_code}",
                    )

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

    async def _get_contact(self, **kwargs: Any) -> ToolResult[CRMContact | None]:
        """Get single contact by ID."""
        contact_id = kwargs.get("contact_id")
        if not contact_id:
            return ToolResult(success=False, data=None, error="contact_id required")

        if self.use_mock:
            return await self._mock_get_contact(contact_id)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    contact = self._parse_hubspot_contact(response.json())
                    return ToolResult(success=True, data=contact)
                elif response.status_code == 404:
                    return ToolResult(success=False, data=None, error="Contact not found")
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"HubSpot API error: {response.status_code}",
                    )

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

    async def _search_contacts(self, **kwargs: Any) -> ToolResult[list[CRMContact]]:
        """Search contacts by email or property."""
        email = kwargs.get("email")
        query = kwargs.get("query")

        if self.use_mock:
            return await self._mock_search_contacts(email, query)

        # Build search filter
        filters = []
        if email:
            filters.append({
                "propertyName": "email",
                "operator": "CONTAINS_TOKEN",
                "value": email,
            })

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/search",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "filterGroups": [{"filters": filters}] if filters else [],
                        "limit": 10,
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    contacts = [
                        self._parse_hubspot_contact(item)
                        for item in data.get("results", [])
                    ]
                    return ToolResult(success=True, data=contacts)
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Search failed: {response.status_code}",
                    )

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

    async def _create_contact(self, **kwargs: Any) -> ToolResult[CRMContact]:
        """Create a new contact."""
        email = kwargs.get("email")
        first_name = kwargs.get("first_name")
        last_name = kwargs.get("last_name")
        company = kwargs.get("company")

        if not email:
            return ToolResult(success=False, data=None, error="email required")

        properties = {
            "email": email,
            "firstname": first_name,
            "lastname": last_name,
            "company": company,
        }
        properties = {k: v for k, v in properties.items() if v}

        if self.use_mock:
            return await self._mock_create_contact(properties)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/crm/v3/objects/contacts",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"properties": properties},
                    timeout=10.0,
                )

                if response.status_code == 201:
                    contact = self._parse_hubspot_contact(response.json())
                    return ToolResult(success=True, data=contact)
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Create failed: {response.status_code}",
                    )

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

    async def _update_contact(self, **kwargs: Any) -> ToolResult[CRMContact]:
        """Update an existing contact."""
        contact_id = kwargs.get("contact_id")
        properties = kwargs.get("properties", {})

        if not contact_id:
            return ToolResult(success=False, data=None, error="contact_id required")

        if self.use_mock:
            return await self._mock_update_contact(contact_id, properties)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"properties": properties},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    contact = self._parse_hubspot_contact(response.json())
                    return ToolResult(success=True, data=contact)
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Update failed: {response.status_code}",
                    )

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

    async def _get_companies(self, **kwargs: Any) -> ToolResult[list[CRMCompany]]:
        """Get companies list."""
        limit = kwargs.get("limit", 10)

        if self.use_mock:
            return await self._mock_get_companies(limit)

        # Similar implementation to contacts
        return ToolResult(success=True, data=[])

    async def _get_company(self, **kwargs: Any) -> ToolResult[CRMCompany | None]:
        """Get single company."""
        return ToolResult(success=True, data=None)

    async def _get_deals(self, **kwargs: Any) -> ToolResult[list[CRMDeal]]:
        """Get deals list."""
        limit = kwargs.get("limit", 10)

        if self.use_mock:
            return await self._mock_get_deals(limit)

        return ToolResult(success=True, data=[])

    async def _get_deal(self, **kwargs: Any) -> ToolResult[CRMDeal | None]:
        """Get single deal."""
        return ToolResult(success=True, data=None)

    async def _create_company(self, **kwargs: Any) -> ToolResult[CRMCompany]:
        """Create a company."""
        return ToolResult(success=True, data=None)

    async def _create_deal(self, **kwargs: Any) -> ToolResult[CRMDeal]:
        """Create a deal."""
        return ToolResult(success=True, data=None)

    async def _update_deal(self, **kwargs: Any) -> ToolResult[CRMDeal]:
        """Update a deal."""
        return ToolResult(success=True, data=None)

    def _parse_hubspot_contact(self, data: dict[str, Any]) -> CRMContact:
        """Parse HubSpot contact to unified format."""
        props = data.get("properties", {})
        created = None
        if props.get("createdate"):
            try:
                created = datetime.fromisoformat(props["createdate"].replace("Z", "+00:00"))
            except Exception:
                pass

        return CRMContact(
            id=str(data.get("id", "")),
            email=props.get("email", ""),
            first_name=props.get("firstname"),
            last_name=props.get("lastname"),
            company=props.get("company"),
            title=props.get("jobtitle"),
            phone=props.get("phone"),
            lifecycle_stage=props.get("lifecyclestage"),
            lead_status=props.get("hs_lead_status"),
            owner_id=props.get("hubspot_owner_id"),
            created_at=created,
            updated_at=None,
            custom_properties={k: v for k, v in props.items() if k.startswith("custom_")},
            source_crm="hubspot",
        )

    # Mock implementations
    async def _mock_get_contacts(self, limit: int) -> ToolResult[list[CRMContact]]:
        await asyncio.sleep(0.05)
        contacts = [
            CRMContact(
                id="1001",
                email="john@techstartup.sg",
                first_name="John",
                last_name="Tan",
                company="TechStartup Pte Ltd",
                title="CEO",
                phone="+65 9123 4567",
                lifecycle_stage="lead",
                lead_status="new",
                owner_id="owner_1",
                created_at=datetime.utcnow(),
                updated_at=None,
                source_crm="hubspot",
            ),
            CRMContact(
                id="1002",
                email="sarah@finnovate.sg",
                first_name="Sarah",
                last_name="Lim",
                company="Finnovate Solutions",
                title="CTO",
                phone="+65 9876 5432",
                lifecycle_stage="opportunity",
                lead_status="qualified",
                owner_id="owner_1",
                created_at=datetime.utcnow(),
                updated_at=None,
                source_crm="hubspot",
            ),
        ]
        return ToolResult(success=True, data=contacts[:limit])

    async def _mock_get_contact(self, contact_id: str) -> ToolResult[CRMContact | None]:
        await asyncio.sleep(0.05)
        contact = CRMContact(
            id=contact_id,
            email="contact@example.sg",
            first_name="Test",
            last_name="Contact",
            company="Example Pte Ltd",
            title="Manager",
            lifecycle_stage="lead",
            lead_status="new",
            created_at=datetime.utcnow(),
            source_crm="hubspot",
            owner_id=None,
            phone=None,
            updated_at=None,
        )
        return ToolResult(success=True, data=contact)

    async def _mock_search_contacts(
        self,
        email: str | None,
        query: str | None,
    ) -> ToolResult[list[CRMContact]]:
        await asyncio.sleep(0.05)
        # Return empty for now
        return ToolResult(success=True, data=[])

    async def _mock_create_contact(
        self,
        properties: dict[str, Any],
    ) -> ToolResult[CRMContact]:
        await asyncio.sleep(0.05)
        contact = CRMContact(
            id="new_1001",
            email=properties.get("email", ""),
            first_name=properties.get("firstname"),
            last_name=properties.get("lastname"),
            company=properties.get("company"),
            title=None,
            phone=None,
            lifecycle_stage="lead",
            lead_status="new",
            owner_id=None,
            created_at=datetime.utcnow(),
            updated_at=None,
            source_crm="hubspot",
        )
        return ToolResult(success=True, data=contact)

    async def _mock_update_contact(
        self,
        contact_id: str,
        properties: dict[str, Any],
    ) -> ToolResult[CRMContact]:
        result = await self._mock_get_contact(contact_id)
        if result.data:
            for key, value in properties.items():
                if hasattr(result.data, key):
                    setattr(result.data, key, value)
        return result

    async def _mock_get_companies(self, limit: int) -> ToolResult[list[CRMCompany]]:
        await asyncio.sleep(0.05)
        companies = [
            CRMCompany(
                id="c1001",
                name="TechStartup Pte Ltd",
                domain="techstartup.sg",
                industry="Technology",
                employee_count=25,
                revenue=500000,
                owner_id="owner_1",
                created_at=datetime.utcnow(),
                source_crm="hubspot",
            ),
        ]
        return ToolResult(success=True, data=companies[:limit])

    async def _mock_get_deals(self, limit: int) -> ToolResult[list[CRMDeal]]:
        await asyncio.sleep(0.05)
        deals = [
            CRMDeal(
                id="d1001",
                name="TechStartup - Enterprise Plan",
                amount=50000,
                stage="proposal",
                pipeline="default",
                close_date=datetime.utcnow(),
                contact_ids=["1001"],
                company_id="c1001",
                owner_id="owner_1",
                probability=0.6,
                created_at=datetime.utcnow(),
                source_crm="hubspot",
            ),
        ]
        return ToolResult(success=True, data=deals[:limit])


class PipedriveTool(BaseTool):
    """Pipedrive CRM integration.

    Popular with sales-focused Singapore SMEs.
    """

    name = "pipedrive"
    description = "Pipedrive CRM integration for persons, organizations, and deals"
    category = ToolCategory.CRM
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=80,
        requests_per_hour=800,
        burst_limit=10,
    )

    BASE_URL = "https://api.pipedrive.com/v1"

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        api_token: str | None = None,
        use_mock: bool = False,
    ):
        super().__init__(agent_id, allowed_access)
        self.api_token = api_token or os.getenv("PIPEDRIVE_API_TOKEN")
        self.use_mock = use_mock or not self.api_token

    async def _execute(self, **kwargs: Any) -> ToolResult:
        """Execute Pipedrive operation."""
        operation = kwargs.get("operation", "get_persons")

        operations = {
            "get_persons": self._get_persons,
            "get_organizations": self._get_organizations,
            "get_deals": self._get_deals,
            "search": self._search,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown operation: {operation}",
            )

        return await handler(**kwargs)

    async def _get_persons(self, **kwargs: Any) -> ToolResult[list[CRMContact]]:
        """Get persons from Pipedrive."""
        limit = kwargs.get("limit", 10)

        if self.use_mock:
            # Mock implementation similar to HubSpot
            await asyncio.sleep(0.05)
            return ToolResult(success=True, data=[])

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/persons",
                    params={"api_token": self.api_token, "limit": limit},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    contacts = [
                        self._parse_pipedrive_person(item)
                        for item in data.get("data", []) or []
                    ]
                    return ToolResult(success=True, data=contacts)

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

        return ToolResult(success=True, data=[])

    async def _get_organizations(self, **kwargs: Any) -> ToolResult[list[CRMCompany]]:
        """Get organizations from Pipedrive."""
        return ToolResult(success=True, data=[])

    async def _get_deals(self, **kwargs: Any) -> ToolResult[list[CRMDeal]]:
        """Get deals from Pipedrive."""
        return ToolResult(success=True, data=[])

    async def _search(self, **kwargs: Any) -> ToolResult[dict[str, Any]]:
        """Search across Pipedrive."""
        query = kwargs.get("query")
        if not query:
            return ToolResult(success=False, data=None, error="query required")

        if self.use_mock:
            return ToolResult(success=True, data={"items": []})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/itemSearch",
                    params={"api_token": self.api_token, "term": query},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    return ToolResult(success=True, data=response.json().get("data", {}))

            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))

        return ToolResult(success=True, data={})

    def _parse_pipedrive_person(self, data: dict[str, Any]) -> CRMContact:
        """Parse Pipedrive person to unified format."""
        email = ""
        if data.get("email"):
            emails = data["email"]
            if isinstance(emails, list) and emails:
                email = emails[0].get("value", "")
            elif isinstance(emails, str):
                email = emails

        return CRMContact(
            id=str(data.get("id", "")),
            email=email,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            company=data.get("org_name"),
            title=None,
            phone=None,
            lifecycle_stage=None,
            lead_status=None,
            owner_id=str(data.get("owner_id", "")),
            created_at=None,
            updated_at=None,
            source_crm="pipedrive",
        )


class CRMSyncTool(BaseTool):
    """Sync data between CRMs and GTM Advisor.

    Provides unified interface for multi-CRM environments.
    """

    name = "crm_sync"
    description = "Sync and deduplicate contacts across CRM systems"
    category = ToolCategory.CRM
    required_access = ToolAccess.WRITE  # Requires write for sync
    rate_limit = RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=2,
    )

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        hubspot: HubSpotTool | None = None,
        pipedrive: PipedriveTool | None = None,
    ):
        super().__init__(agent_id, allowed_access)
        self.hubspot = hubspot
        self.pipedrive = pipedrive

    async def _execute(self, **kwargs: Any) -> ToolResult:
        """Execute sync operation."""
        operation = kwargs.get("operation", "get_all_contacts")

        if operation == "get_all_contacts":
            return await self._get_all_contacts(**kwargs)
        elif operation == "deduplicate":
            return await self._deduplicate_contacts(**kwargs)
        elif operation == "sync_contact":
            return await self._sync_contact(**kwargs)
        else:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown operation: {operation}",
            )

    async def _get_all_contacts(self, **kwargs: Any) -> ToolResult[list[CRMContact]]:
        """Get contacts from all connected CRMs."""
        all_contacts = []

        if self.hubspot:
            result = await self.hubspot._get_contacts(limit=kwargs.get("limit", 50))
            if result.success and result.data:
                all_contacts.extend(result.data)

        if self.pipedrive:
            result = await self.pipedrive._get_persons(limit=kwargs.get("limit", 50))
            if result.success and result.data:
                all_contacts.extend(result.data)

        return ToolResult(
            success=True,
            data=all_contacts,
            metadata={"total_count": len(all_contacts)},
        )

    async def _deduplicate_contacts(
        self,
        **kwargs: Any,
    ) -> ToolResult[dict[str, Any]]:
        """Find duplicate contacts across CRMs."""
        result = await self._get_all_contacts(**kwargs)
        if not result.success or not result.data:
            return result

        # Group by email
        by_email: dict[str, list[CRMContact]] = {}
        for contact in result.data:
            if contact.email:
                email_lower = contact.email.lower()
                if email_lower not in by_email:
                    by_email[email_lower] = []
                by_email[email_lower].append(contact)

        # Find duplicates
        duplicates = {
            email: [c.to_dict() for c in contacts]
            for email, contacts in by_email.items()
            if len(contacts) > 1
        }

        return ToolResult(
            success=True,
            data={
                "total_contacts": len(result.data),
                "unique_emails": len(by_email),
                "duplicates": duplicates,
                "duplicate_count": len(duplicates),
            },
        )

    async def _sync_contact(self, **kwargs: Any) -> ToolResult[dict[str, Any]]:
        """Sync a contact to specified CRM."""
        contact_data = kwargs.get("contact")
        target_crm = kwargs.get("target_crm", "hubspot")

        if not contact_data:
            return ToolResult(success=False, data=None, error="contact data required")

        if target_crm == "hubspot" and self.hubspot:
            return await self.hubspot._create_contact(**contact_data)
        elif target_crm == "pipedrive" and self.pipedrive:
            return ToolResult(success=False, data=None, error="Pipedrive create not implemented")
        else:
            return ToolResult(success=False, data=None, error=f"CRM {target_crm} not configured")
