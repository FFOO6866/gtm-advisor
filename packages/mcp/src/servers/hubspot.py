"""HubSpot MCP Server - CRM contact and company data.

Provides evidence-backed facts from HubSpot CRM:
- Company information (industry, employee count, revenue)
- Contact details (email, phone, role, lifecycle stage)
- Deal information (stage, amount, expected close)
- Engagement signals (recent activity, email opens)

API Documentation: https://developers.hubspot.com/docs/api/overview
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx
import structlog

from packages.mcp.src.base import APIBasedMCPServer
from packages.mcp.src.types import (
    EntityReference,
    EntityType,
    FactType,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)

logger = structlog.get_logger()


class HubSpotMCPServer(APIBasedMCPServer):
    """MCP Server for HubSpot CRM data.

    Connects to HubSpot's CRM API to extract:
    - Company data (domain, industry, employee count)
    - Contact information (email, phone, title)
    - Deal pipeline data (stage, amount, close date)
    - Engagement signals (last activity, lifecycle stage)

    Requires: HUBSPOT_API_KEY environment variable (Private App token)

    Example:
        server = HubSpotMCPServer.from_env()
        result = await server.search("Acme Corp", search_type="company")
        for fact in result.facts:
            print(f"{fact.claim} (confidence: {fact.confidence})")
    """

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, config: MCPServerConfig) -> None:
        """Initialize HubSpot server.

        Args:
            config: Server configuration with API key
        """
        super().__init__(config)
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout_seconds,
        )
        self._portal_id: str | None = None

    @classmethod
    def from_env(cls) -> HubSpotMCPServer:
        """Create server from HUBSPOT_API_KEY environment variable."""
        api_key = os.getenv("HUBSPOT_API_KEY")
        config = MCPServerConfig(
            name="HubSpot CRM",
            source_type=SourceType.HUBSPOT,
            description="HubSpot CRM - companies, contacts, deals",
            api_key=api_key,
            requires_api_key=True,
            rate_limit_per_hour=500,
            rate_limit_per_day=10000,
            cache_ttl_seconds=1800,  # 30 minutes
        )
        return cls(config)

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self._config.api_key)

    async def _health_check_impl(self) -> bool:
        """Verify HubSpot API accessibility."""
        try:
            response = await self._client.get(
                "/crm/v3/objects/companies",
                params={"limit": 1},
            )
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("hubspot_health_check_failed", error=str(e))
            return False

    async def _get_portal_id(self) -> str:
        """Get HubSpot portal ID for building URLs."""
        if self._portal_id:
            return self._portal_id

        try:
            response = await self._client.get("/account-info/v3/details")
            if response.status_code == 200:
                data = response.json()
                self._portal_id = str(data.get("portalId", ""))
                return self._portal_id
        except Exception:
            pass

        return ""

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search HubSpot data.

        Args:
            query: Company name, contact email, or domain
            **kwargs:
                - search_type: "company", "contact", or "deal" (default: "company")
                - limit: Results per type (default: 10)

        Returns:
            Query result with HubSpot facts
        """
        search_type = kwargs.get("search_type", "company")
        limit = min(kwargs.get("limit", 10), 100)

        # Check cache
        cache_key = f"hubspot:{search_type}:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            self._logger.debug("hubspot_cache_hit", query=query)
            return cached

        try:
            if search_type == "company":
                result = await self._search_companies(query, limit)
            elif search_type == "contact":
                result = await self._search_contacts(query, limit)
            elif search_type == "deal":
                result = await self._search_deals(query, limit)
            else:
                result = await self._search_companies(query, limit)

            # Cache results
            if result.facts:
                self._set_cached(cache_key, result)

            self._logger.info(
                "hubspot_search_success",
                query=query,
                search_type=search_type,
                facts_found=len(result.facts),
            )
            return result

        except Exception as e:
            self._logger.error("hubspot_search_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"HubSpot search failed: {str(e)}"],
            )

    async def _search_companies(self, query: str, limit: int) -> MCPQueryResult:
        """Search for companies by name or domain."""
        facts = []
        entities = []

        try:
            # HubSpot company search
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "name",
                                "operator": "CONTAINS_TOKEN",
                                "value": query,
                            }
                        ]
                    },
                    {
                        "filters": [
                            {
                                "propertyName": "domain",
                                "operator": "CONTAINS_TOKEN",
                                "value": query,
                            }
                        ]
                    },
                ],
                "properties": [
                    "name",
                    "domain",
                    "industry",
                    "numberofemployees",
                    "annualrevenue",
                    "city",
                    "country",
                    "lifecyclestage",
                    "hs_lead_status",
                    "createdate",
                    "hs_lastmodifieddate",
                ],
                "limit": limit,
            }

            response = await self._client.post(
                "/crm/v3/objects/companies/search",
                json=search_body,
            )

            if response.status_code != 200:
                error_detail = response.text[:200] if response.text else "Unknown error"
                raise Exception(f"HubSpot API error {response.status_code}: {error_detail}")

            data = response.json()
            portal_id = await self._get_portal_id()

            for item in data.get("results", [])[:limit]:
                company_facts, entity = await self._parse_company(item, portal_id)
                facts.extend(company_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("hubspot_company_search_failed", error=str(e))
            return MCPQueryResult(
                facts=[],
                entities=[],
                query=query,
                mcp_server=self.name,
                errors=[str(e)],
            )

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    async def _parse_company(
        self, hubspot_company: dict, portal_id: str
    ) -> tuple[list, EntityReference | None]:
        """Convert HubSpot company object to EvidencedFacts."""
        facts = []
        props = hubspot_company.get("properties", {})
        hubspot_id = hubspot_company.get("id", "")

        company_name = props.get("name") or "Unknown Company"
        domain = props.get("domain") or ""
        source_url = f"https://app.hubspot.com/contacts/{portal_id}/company/{hubspot_id}" if portal_id else None

        # Fact 1: Company exists in CRM
        extracted_data = {
            "hubspot_id": hubspot_id,
            "company_name": company_name,
            "domain": domain,
            "industry": props.get("industry"),
            "employee_count": props.get("numberofemployees"),
            "annual_revenue": props.get("annualrevenue"),
            "city": props.get("city"),
            "country": props.get("country"),
            "lifecycle_stage": props.get("lifecyclestage"),
            "lead_status": props.get("hs_lead_status"),
        }

        facts.append(
            self.create_fact(
                claim=f"{company_name} is tracked in HubSpot CRM",
                fact_type=FactType.COMPANY_INFO.value,
                source_name="HubSpot CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[company_name],
            )
        )

        # Fact 2: Industry classification
        if props.get("industry"):
            facts.append(
                self.create_fact(
                    claim=f"{company_name} operates in {props.get('industry')}",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="HubSpot CRM",
                    source_url=source_url,
                    confidence=0.90,
                    extracted_data={"industry": props.get("industry")},
                    related_entities=[company_name],
                )
            )

        # Fact 3: Employee count
        if props.get("numberofemployees"):
            facts.append(
                self.create_fact(
                    claim=f"{company_name} has {props.get('numberofemployees')} employees",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="HubSpot CRM",
                    source_url=source_url,
                    confidence=0.85,
                    extracted_data={"employee_count": props.get("numberofemployees")},
                    related_entities=[company_name],
                )
            )

        # Fact 4: Revenue
        if props.get("annualrevenue"):
            facts.append(
                self.create_fact(
                    claim=f"{company_name} has annual revenue of ${props.get('annualrevenue')}",
                    fact_type=FactType.FINANCIAL.value,
                    source_name="HubSpot CRM",
                    source_url=source_url,
                    confidence=0.80,
                    extracted_data={"annual_revenue": props.get("annualrevenue")},
                    related_entities=[company_name],
                )
            )

        # Fact 5: Lifecycle stage (engagement signal)
        if props.get("lifecyclestage"):
            facts.append(
                self.create_fact(
                    claim=f"{company_name} is at lifecycle stage: {props.get('lifecyclestage')}",
                    fact_type=FactType.CRM_ACTIVITY.value,
                    source_name="HubSpot CRM",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={"lifecycle_stage": props.get("lifecyclestage")},
                    related_entities=[company_name],
                )
            )

        # Create entity reference
        entity = EntityReference(
            entity_type=EntityType.COMPANY,
            name=company_name,
            canonical_name=company_name.upper(),
            website=f"https://{domain}" if domain else None,
            external_ids={"hubspot_id": hubspot_id},
        )

        return facts, entity

    async def _search_contacts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for contacts by email or name."""
        facts = []
        entities = []

        try:
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "email",
                                "operator": "CONTAINS_TOKEN",
                                "value": query,
                            }
                        ]
                    },
                    {
                        "filters": [
                            {
                                "propertyName": "firstname",
                                "operator": "CONTAINS_TOKEN",
                                "value": query,
                            }
                        ]
                    },
                    {
                        "filters": [
                            {
                                "propertyName": "lastname",
                                "operator": "CONTAINS_TOKEN",
                                "value": query,
                            }
                        ]
                    },
                ],
                "properties": [
                    "email",
                    "firstname",
                    "lastname",
                    "jobtitle",
                    "phone",
                    "company",
                    "lifecyclestage",
                    "hs_lead_status",
                    "lastmodifieddate",
                ],
                "limit": limit,
            }

            response = await self._client.post(
                "/crm/v3/objects/contacts/search",
                json=search_body,
            )

            if response.status_code != 200:
                raise Exception(f"HubSpot API error {response.status_code}")

            data = response.json()
            portal_id = await self._get_portal_id()

            for item in data.get("results", [])[:limit]:
                contact_facts, entity = self._parse_contact(item, portal_id)
                facts.extend(contact_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("hubspot_contact_search_failed", error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[str(e)],
            )

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_contact(
        self, hubspot_contact: dict, portal_id: str
    ) -> tuple[list, EntityReference | None]:
        """Convert HubSpot contact to EvidencedFacts."""
        facts = []
        props = hubspot_contact.get("properties", {})
        hubspot_id = hubspot_contact.get("id", "")

        first_name = props.get("firstname") or ""
        last_name = props.get("lastname") or ""
        full_name = f"{first_name} {last_name}".strip() or "Unknown Contact"
        email = props.get("email") or ""
        source_url = f"https://app.hubspot.com/contacts/{portal_id}/contact/{hubspot_id}" if portal_id else None

        extracted_data = {
            "hubspot_id": hubspot_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "job_title": props.get("jobtitle"),
            "phone": props.get("phone"),
            "company": props.get("company"),
            "lifecycle_stage": props.get("lifecyclestage"),
        }

        # Fact 1: Contact info
        claim_parts = [f"{full_name}"]
        if props.get("jobtitle"):
            claim_parts.append(f"({props.get('jobtitle')})")
        if props.get("company"):
            claim_parts.append(f"at {props.get('company')}")
        claim_parts.append("is in HubSpot CRM")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="HubSpot CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[full_name, props.get("company")] if props.get("company") else [full_name],
            )
        )

        # Fact 2: Email available
        if email:
            facts.append(
                self.create_fact(
                    claim=f"{full_name} can be reached at {email}",
                    fact_type=FactType.CONTACT_INFO.value,
                    source_name="HubSpot CRM",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={"email": email},
                    related_entities=[full_name],
                )
            )

        # Create entity reference
        entity = EntityReference(
            entity_type=EntityType.PERSON,
            name=full_name,
            canonical_name=full_name.upper(),
            external_ids={"hubspot_id": hubspot_id, "email": email} if email else {"hubspot_id": hubspot_id},
        )

        return facts, entity

    async def _search_deals(self, query: str, limit: int) -> MCPQueryResult:
        """Search for deals by name or associated company."""
        facts = []

        try:
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "dealname",
                                "operator": "CONTAINS_TOKEN",
                                "value": query,
                            }
                        ]
                    }
                ],
                "properties": [
                    "dealname",
                    "amount",
                    "dealstage",
                    "closedate",
                    "pipeline",
                    "hs_lastmodifieddate",
                ],
                "limit": limit,
            }

            response = await self._client.post(
                "/crm/v3/objects/deals/search",
                json=search_body,
            )

            if response.status_code != 200:
                raise Exception(f"HubSpot API error {response.status_code}")

            data = response.json()
            portal_id = await self._get_portal_id()

            for item in data.get("results", [])[:limit]:
                deal_facts = self._parse_deal(item, portal_id)
                facts.extend(deal_facts)

        except Exception as e:
            self._logger.warning("hubspot_deal_search_failed", error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[str(e)],
            )

        return MCPQueryResult(
            facts=facts,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_deal(self, hubspot_deal: dict, portal_id: str) -> list:
        """Convert HubSpot deal to EvidencedFacts."""
        facts = []
        props = hubspot_deal.get("properties", {})
        hubspot_id = hubspot_deal.get("id", "")

        deal_name = props.get("dealname") or "Unknown Deal"
        amount = props.get("amount")
        stage = props.get("dealstage")
        close_date = props.get("closedate")
        source_url = f"https://app.hubspot.com/contacts/{portal_id}/deal/{hubspot_id}" if portal_id else None

        extracted_data = {
            "hubspot_id": hubspot_id,
            "deal_name": deal_name,
            "amount": amount,
            "stage": stage,
            "close_date": close_date,
            "pipeline": props.get("pipeline"),
        }

        # Fact 1: Deal exists
        claim_parts = [f"Deal '{deal_name}'"]
        if amount:
            claim_parts.append(f"worth ${amount}")
        if stage:
            claim_parts.append(f"is at stage '{stage}'")
        claim_parts.append("in HubSpot")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.DEAL_INFO.value,
                source_name="HubSpot CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[deal_name],
            )
        )

        return facts

    # Write operations for lead sync

    async def create_contact(self, contact_data: dict[str, Any]) -> str | None:
        """Create a new contact in HubSpot.

        Args:
            contact_data: Contact properties (email, firstname, lastname, etc.)

        Returns:
            HubSpot contact ID if successful, None otherwise
        """
        try:
            response = await self._client.post(
                "/crm/v3/objects/contacts",
                json={"properties": contact_data},
            )

            if response.status_code == 201:
                data = response.json()
                contact_id = data.get("id")
                self._logger.info("hubspot_contact_created", contact_id=contact_id)
                return contact_id
            else:
                self._logger.warning(
                    "hubspot_contact_create_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return None

        except Exception as e:
            self._logger.error("hubspot_contact_create_error", error=str(e))
            return None

    async def create_company(self, company_data: dict[str, Any]) -> str | None:
        """Create a new company in HubSpot.

        Args:
            company_data: Company properties (name, domain, industry, etc.)

        Returns:
            HubSpot company ID if successful, None otherwise
        """
        try:
            response = await self._client.post(
                "/crm/v3/objects/companies",
                json={"properties": company_data},
            )

            if response.status_code == 201:
                data = response.json()
                company_id = data.get("id")
                self._logger.info("hubspot_company_created", company_id=company_id)
                return company_id
            else:
                self._logger.warning(
                    "hubspot_company_create_failed",
                    status=response.status_code,
                )
                return None

        except Exception as e:
            self._logger.error("hubspot_company_create_error", error=str(e))
            return None

    async def create_deal(self, deal_data: dict[str, Any]) -> str | None:
        """Create a new deal in HubSpot.

        Args:
            deal_data: Deal properties (dealname, amount, dealstage, etc.)

        Returns:
            HubSpot deal ID if successful, None otherwise
        """
        try:
            response = await self._client.post(
                "/crm/v3/objects/deals",
                json={"properties": deal_data},
            )

            if response.status_code == 201:
                data = response.json()
                deal_id = data.get("id")
                self._logger.info("hubspot_deal_created", deal_id=deal_id)
                return deal_id
            else:
                self._logger.warning("hubspot_deal_create_failed", status=response.status_code)
                return None

        except Exception as e:
            self._logger.error("hubspot_deal_create_error", error=str(e))
            return None

    async def add_note(
        self,
        object_type: str,
        object_id: str,
        note_body: str,
    ) -> bool:
        """Add a note to a HubSpot object.

        Args:
            object_type: "contact", "company", or "deal"
            object_id: HubSpot object ID
            note_body: Note content

        Returns:
            True if successful
        """
        try:
            # Create engagement (note)
            note_data = {
                "properties": {
                    "hs_timestamp": datetime.utcnow().isoformat() + "Z",
                    "hs_note_body": note_body,
                },
                "associations": [
                    {
                        "to": {"id": object_id},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": self._get_association_type_id(object_type),
                            }
                        ],
                    }
                ],
            }

            response = await self._client.post(
                "/crm/v3/objects/notes",
                json=note_data,
            )

            if response.status_code == 201:
                self._logger.info("hubspot_note_added", object_type=object_type, object_id=object_id)
                return True
            else:
                self._logger.warning("hubspot_note_add_failed", status=response.status_code)
                return False

        except Exception as e:
            self._logger.error("hubspot_note_add_error", error=str(e))
            return False

    def _get_association_type_id(self, object_type: str) -> int:
        """Get HubSpot association type ID for notes."""
        # HubSpot defined association types for notes
        association_types = {
            "contact": 202,  # Note to Contact
            "company": 190,  # Note to Company
            "deal": 214,  # Note to Deal
        }
        return association_types.get(object_type, 202)

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
