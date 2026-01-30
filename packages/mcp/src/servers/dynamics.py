"""Microsoft Dynamics 365 MCP Server - CRM data integration.

Provides evidence-backed facts from Dynamics 365:
- Account information
- Contact details
- Lead data
- Opportunity pipeline

API Documentation: https://learn.microsoft.com/en-us/dynamics365/customerengagement/on-premises/developer/webapi/
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
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


class DynamicsMCPServer(APIBasedMCPServer):
    """MCP Server for Microsoft Dynamics 365 CRM.

    Connects to Dynamics 365 Web API to extract:
    - Account data (name, industry, revenue)
    - Contact details (email, phone, title)
    - Lead information (status, source)
    - Opportunity pipeline (stage, amount)

    Requires environment variables:
        - DYNAMICS_CLIENT_ID: Azure AD Application ID
        - DYNAMICS_CLIENT_SECRET: Azure AD Client Secret
        - DYNAMICS_TENANT_ID: Azure AD Tenant ID
        - DYNAMICS_ENVIRONMENT: Dynamics environment URL (e.g., org.crm.dynamics.com)

    Example:
        server = DynamicsMCPServer.from_env()
        result = await server.search("Acme", entity="account")
    """

    API_VERSION = "v9.2"

    def __init__(self, config: MCPServerConfig, credentials: dict[str, str]) -> None:
        """Initialize Dynamics server.

        Args:
            config: Server configuration
            credentials: Azure AD credentials
        """
        super().__init__(config)
        self._credentials = credentials
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._environment = credentials.get("environment", "")
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    @classmethod
    def from_env(cls) -> DynamicsMCPServer:
        """Create server from environment variables."""
        credentials = {
            "client_id": os.getenv("DYNAMICS_CLIENT_ID", ""),
            "client_secret": os.getenv("DYNAMICS_CLIENT_SECRET", ""),
            "tenant_id": os.getenv("DYNAMICS_TENANT_ID", ""),
            "environment": os.getenv("DYNAMICS_ENVIRONMENT", ""),
        }

        config = MCPServerConfig(
            name="Microsoft Dynamics 365",
            source_type=SourceType.DYNAMICS,
            description="Dynamics 365 CRM - accounts, contacts, leads, opportunities",
            api_key=credentials.get("client_id"),
            requires_api_key=True,
            rate_limit_per_hour=6000,
            rate_limit_per_day=60000,
            cache_ttl_seconds=1800,
        )
        return cls(config, credentials)

    @property
    def is_configured(self) -> bool:
        """Check if all credentials are configured."""
        return all([
            self._credentials.get("client_id"),
            self._credentials.get("client_secret"),
            self._credentials.get("tenant_id"),
            self._credentials.get("environment"),
        ])

    @property
    def _base_url(self) -> str:
        """Get Dynamics API base URL."""
        return f"https://{self._environment}/api/data/{self.API_VERSION}"

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token."""
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return True
        return await self._authenticate()

    async def _authenticate(self) -> bool:
        """Authenticate with Azure AD for Dynamics 365."""
        try:
            tenant_id = self._credentials.get("tenant_id")
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

            response = await self._client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._credentials.get("client_id"),
                    "client_secret": self._credentials.get("client_secret"),
                    "scope": f"https://{self._environment}/.default",
                },
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                self._logger.info("dynamics_authenticated", environment=self._environment)
                return True
            else:
                self._logger.error(
                    "dynamics_auth_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return False

        except Exception as e:
            self._logger.error("dynamics_auth_error", error=str(e))
            return False

    async def _health_check_impl(self) -> bool:
        """Verify Dynamics API accessibility."""
        if not await self._ensure_authenticated():
            return False

        try:
            response = await self._client.get(
                f"{self._base_url}/WhoAmI",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("dynamics_health_check_failed", error=str(e))
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search Dynamics 365 entities.

        Args:
            query: Search term
            **kwargs:
                - entity: "account", "contact", "lead", or "opportunity"
                - limit: Max results (default: 20)

        Returns:
            Query result with Dynamics facts
        """
        entity = kwargs.get("entity", "account")
        limit = min(kwargs.get("limit", 20), 100)

        cache_key = f"dynamics:{entity}:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        if not await self._ensure_authenticated():
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=["Dynamics authentication failed"],
            )

        try:
            if entity == "account":
                result = await self._search_accounts(query, limit)
            elif entity == "contact":
                result = await self._search_contacts(query, limit)
            elif entity == "lead":
                result = await self._search_leads(query, limit)
            elif entity == "opportunity":
                result = await self._search_opportunities(query, limit)
            else:
                result = await self._search_accounts(query, limit)

            if result.facts:
                self._set_cached(cache_key, result)

            self._logger.info(
                "dynamics_search_success",
                query=query,
                entity=entity,
                facts_found=len(result.facts),
            )
            return result

        except Exception as e:
            self._logger.error("dynamics_search_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"Dynamics search failed: {str(e)}"],
            )

    async def _odata_query(self, entity_set: str, filter_query: str, select: str, top: int) -> list[dict]:
        """Execute an OData query."""
        params = {
            "$filter": filter_query,
            "$select": select,
            "$top": top,
        }

        response = await self._client.get(
            f"{self._base_url}/{entity_set}",
            params=params,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
                "Accept": "application/json",
            },
        )

        if response.status_code != 200:
            raise Exception(f"OData query failed: {response.status_code}")

        data = response.json()
        return data.get("value", [])

    async def _search_accounts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Accounts."""
        facts = []
        entities = []

        try:
            records = await self._odata_query(
                "accounts",
                f"contains(name,'{query}')",
                "accountid,name,industrycode,websiteurl,telephone1,address1_city,address1_country,numberofemployees,revenue",
                limit,
            )

            for record in records:
                account_facts, entity = self._parse_account(record)
                facts.extend(account_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("dynamics_account_search_failed", error=str(e))
            return MCPQueryResult(facts=[], query=query, mcp_server=self.name, errors=[str(e)])

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_account(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert Dynamics Account to EvidencedFacts."""
        facts = []
        account_id = record.get("accountid", "")
        name = record.get("name") or "Unknown Account"

        source_url = f"https://{self._environment}/main.aspx?etn=account&id={account_id}"

        extracted_data = {
            "dynamics_id": account_id,
            "name": name,
            "industry_code": record.get("industrycode"),
            "website": record.get("websiteurl"),
            "phone": record.get("telephone1"),
            "city": record.get("address1_city"),
            "country": record.get("address1_country"),
            "employee_count": record.get("numberofemployees"),
            "revenue": record.get("revenue"),
        }

        facts.append(
            self.create_fact(
                claim=f"{name} is tracked in Microsoft Dynamics 365",
                fact_type=FactType.COMPANY_INFO.value,
                source_name="Microsoft Dynamics 365",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name],
            )
        )

        if record.get("numberofemployees"):
            facts.append(
                self.create_fact(
                    claim=f"{name} has {record.get('numberofemployees')} employees",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="Microsoft Dynamics 365",
                    source_url=source_url,
                    confidence=0.85,
                    extracted_data={"employee_count": record.get("numberofemployees")},
                    related_entities=[name],
                )
            )

        if record.get("revenue"):
            facts.append(
                self.create_fact(
                    claim=f"{name} has revenue of ${record.get('revenue'):,.0f}",
                    fact_type=FactType.FINANCIAL.value,
                    source_name="Microsoft Dynamics 365",
                    source_url=source_url,
                    confidence=0.80,
                    extracted_data={"revenue": record.get("revenue")},
                    related_entities=[name],
                )
            )

        entity = EntityReference(
            entity_type=EntityType.COMPANY,
            name=name,
            canonical_name=name.upper(),
            website=record.get("websiteurl"),
            external_ids={"dynamics_id": account_id},
        )

        return facts, entity

    async def _search_contacts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Contacts."""
        facts = []
        entities = []

        try:
            records = await self._odata_query(
                "contacts",
                f"contains(fullname,'{query}') or contains(emailaddress1,'{query}')",
                "contactid,fullname,jobtitle,emailaddress1,telephone1,_parentcustomerid_value",
                limit,
            )

            for record in records:
                contact_facts, entity = self._parse_contact(record)
                facts.extend(contact_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("dynamics_contact_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_contact(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert Dynamics Contact to EvidencedFacts."""
        facts = []
        contact_id = record.get("contactid", "")
        name = record.get("fullname") or "Unknown Contact"
        email = record.get("emailaddress1") or ""

        source_url = f"https://{self._environment}/main.aspx?etn=contact&id={contact_id}"

        extracted_data = {
            "dynamics_id": contact_id,
            "name": name,
            "job_title": record.get("jobtitle"),
            "email": email,
            "phone": record.get("telephone1"),
            "account_id": record.get("_parentcustomerid_value"),
        }

        claim_parts = [f"{name}"]
        if record.get("jobtitle"):
            claim_parts.append(f"({record.get('jobtitle')})")
        claim_parts.append("is a contact in Dynamics 365")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="Microsoft Dynamics 365",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name],
            )
        )

        if email:
            facts.append(
                self.create_fact(
                    claim=f"{name} can be reached at {email}",
                    fact_type=FactType.CONTACT_INFO.value,
                    source_name="Microsoft Dynamics 365",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={"email": email},
                    related_entities=[name],
                )
            )

        entity = EntityReference(
            entity_type=EntityType.PERSON,
            name=name,
            canonical_name=name.upper(),
            external_ids={"dynamics_id": contact_id, "email": email} if email else {"dynamics_id": contact_id},
        )

        return facts, entity

    async def _search_leads(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Leads."""
        facts = []
        entities = []

        try:
            records = await self._odata_query(
                "leads",
                f"contains(fullname,'{query}') or contains(companyname,'{query}')",
                "leadid,fullname,companyname,jobtitle,emailaddress1,telephone1,leadqualitycode,leadsourcecode",
                limit,
            )

            for record in records:
                lead_facts, entity = self._parse_lead(record)
                facts.extend(lead_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("dynamics_lead_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_lead(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert Dynamics Lead to EvidencedFacts."""
        facts = []
        lead_id = record.get("leadid", "")
        name = record.get("fullname") or "Unknown Lead"
        company = record.get("companyname") or ""

        source_url = f"https://{self._environment}/main.aspx?etn=lead&id={lead_id}"

        extracted_data = {
            "dynamics_id": lead_id,
            "name": name,
            "company": company,
            "job_title": record.get("jobtitle"),
            "email": record.get("emailaddress1"),
            "phone": record.get("telephone1"),
            "quality_code": record.get("leadqualitycode"),
            "source_code": record.get("leadsourcecode"),
        }

        claim_parts = [f"{name}"]
        if record.get("jobtitle"):
            claim_parts.append(f"({record.get('jobtitle')})")
        if company:
            claim_parts.append(f"at {company}")
        claim_parts.append("is a lead in Dynamics 365")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="Microsoft Dynamics 365",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name, company] if company else [name],
            )
        )

        entity = EntityReference(
            entity_type=EntityType.PERSON,
            name=name,
            canonical_name=name.upper(),
            external_ids={"dynamics_id": lead_id},
        )

        return facts, entity

    async def _search_opportunities(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Opportunities."""
        facts = []

        try:
            records = await self._odata_query(
                "opportunities",
                f"contains(name,'{query}')",
                "opportunityid,name,estimatedvalue,stepname,estimatedclosedate,_parentaccountid_value",
                limit,
            )

            for record in records:
                opp_facts = self._parse_opportunity(record)
                facts.extend(opp_facts)

        except Exception as e:
            self._logger.warning("dynamics_opportunity_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_opportunity(self, record: dict) -> list:
        """Convert Dynamics Opportunity to EvidencedFacts."""
        facts = []
        opp_id = record.get("opportunityid", "")
        name = record.get("name") or "Unknown Opportunity"

        source_url = f"https://{self._environment}/main.aspx?etn=opportunity&id={opp_id}"

        extracted_data = {
            "dynamics_id": opp_id,
            "name": name,
            "estimated_value": record.get("estimatedvalue"),
            "stage": record.get("stepname"),
            "estimated_close": record.get("estimatedclosedate"),
            "account_id": record.get("_parentaccountid_value"),
        }

        claim_parts = [f"Opportunity '{name}'"]
        if record.get("estimatedvalue"):
            claim_parts.append(f"worth ${record.get('estimatedvalue'):,.0f}")
        if record.get("stepname"):
            claim_parts.append(f"is at stage '{record.get('stepname')}'")
        claim_parts.append("in Dynamics 365")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.DEAL_INFO.value,
                source_name="Microsoft Dynamics 365",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
            )
        )

        return facts

    async def create_lead(self, lead_data: dict[str, Any]) -> str | None:
        """Create a new Lead in Dynamics 365."""
        if not await self._ensure_authenticated():
            return None

        try:
            response = await self._client.post(
                f"{self._base_url}/leads",
                json=lead_data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                    "OData-MaxVersion": "4.0",
                    "OData-Version": "4.0",
                },
            )

            if response.status_code == 204:
                odata_id = response.headers.get("OData-EntityId", "")
                lead_id = odata_id.split("(")[-1].rstrip(")") if odata_id else ""
                self._logger.info("dynamics_lead_created", lead_id=lead_id)
                return lead_id
            else:
                self._logger.warning("dynamics_lead_create_failed", status=response.status_code)
                return None

        except Exception as e:
            self._logger.error("dynamics_lead_create_error", error=str(e))
            return None

    async def create_account(self, account_data: dict[str, Any]) -> str | None:
        """Create a new Account in Dynamics 365."""
        if not await self._ensure_authenticated():
            return None

        try:
            response = await self._client.post(
                f"{self._base_url}/accounts",
                json=account_data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                    "OData-MaxVersion": "4.0",
                    "OData-Version": "4.0",
                },
            )

            if response.status_code == 204:
                odata_id = response.headers.get("OData-EntityId", "")
                account_id = odata_id.split("(")[-1].rstrip(")") if odata_id else ""
                self._logger.info("dynamics_account_created", account_id=account_id)
                return account_id
            else:
                self._logger.warning("dynamics_account_create_failed", status=response.status_code)
                return None

        except Exception as e:
            self._logger.error("dynamics_account_create_error", error=str(e))
            return None

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
