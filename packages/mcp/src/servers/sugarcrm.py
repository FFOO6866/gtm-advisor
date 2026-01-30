"""SugarCRM MCP Server - CRM data integration.

Provides evidence-backed facts from SugarCRM:
- Account information
- Contact details
- Lead data
- Opportunity pipeline

API Documentation: https://support.sugarcrm.com/documentation/sugar_developer/sugar_developer_guide/
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


class SugarCRMMCPServer(APIBasedMCPServer):
    """MCP Server for SugarCRM.

    Connects to SugarCRM REST API to extract:
    - Account data (name, industry, revenue)
    - Contact details (email, phone, title)
    - Lead information (status, source)
    - Opportunity pipeline (stage, amount)

    Requires environment variables:
        - SUGARCRM_URL: SugarCRM instance URL
        - SUGARCRM_USERNAME: API username
        - SUGARCRM_PASSWORD: API password

    Example:
        server = SugarCRMMCPServer.from_env()
        result = await server.search("Acme", module="Accounts")
    """

    def __init__(self, config: MCPServerConfig, credentials: dict[str, str]) -> None:
        """Initialize SugarCRM server.

        Args:
            config: Server configuration
            credentials: OAuth credentials
        """
        super().__init__(config)
        self._credentials = credentials
        self._base_url = credentials.get("url", "").rstrip("/")
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    @classmethod
    def from_env(cls) -> SugarCRMMCPServer:
        """Create server from environment variables."""
        credentials = {
            "url": os.getenv("SUGARCRM_URL", ""),
            "username": os.getenv("SUGARCRM_USERNAME", ""),
            "password": os.getenv("SUGARCRM_PASSWORD", ""),
        }

        config = MCPServerConfig(
            name="SugarCRM",
            source_type=SourceType.SUGARCRM,
            description="SugarCRM - accounts, contacts, leads, opportunities",
            api_key=credentials.get("username"),
            requires_api_key=True,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            cache_ttl_seconds=1800,
        )
        return cls(config, credentials)

    @property
    def is_configured(self) -> bool:
        """Check if all credentials are configured."""
        return all([
            self._credentials.get("url"),
            self._credentials.get("username"),
            self._credentials.get("password"),
        ])

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token."""
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return True

        # Try refresh token first
        if self._refresh_token:
            if await self._refresh_auth():
                return True

        return await self._authenticate()

    async def _authenticate(self) -> bool:
        """Authenticate with SugarCRM OAuth."""
        try:
            response = await self._client.post(
                f"{self._base_url}/rest/v11_12/oauth2/token",
                json={
                    "grant_type": "password",
                    "client_id": "sugar",
                    "client_secret": "",
                    "username": self._credentials.get("username"),
                    "password": self._credentials.get("password"),
                    "platform": "api",
                },
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                self._refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                self._logger.info("sugarcrm_authenticated", url=self._base_url)
                return True
            else:
                self._logger.error(
                    "sugarcrm_auth_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return False

        except Exception as e:
            self._logger.error("sugarcrm_auth_error", error=str(e))
            return False

    async def _refresh_auth(self) -> bool:
        """Refresh the access token."""
        try:
            response = await self._client.post(
                f"{self._base_url}/rest/v11_12/oauth2/token",
                json={
                    "grant_type": "refresh_token",
                    "client_id": "sugar",
                    "client_secret": "",
                    "refresh_token": self._refresh_token,
                    "platform": "api",
                },
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                self._refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                return True
            else:
                return False

        except Exception:
            return False

    async def _health_check_impl(self) -> bool:
        """Verify SugarCRM API accessibility."""
        if not await self._ensure_authenticated():
            return False

        try:
            response = await self._client.get(
                f"{self._base_url}/rest/v11_12/me",
                headers={"OAuth-Token": self._access_token},
            )
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("sugarcrm_health_check_failed", error=str(e))
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search SugarCRM modules.

        Args:
            query: Search term
            **kwargs:
                - module: "Accounts", "Contacts", "Leads", or "Opportunities"
                - limit: Max results (default: 20)

        Returns:
            Query result with SugarCRM facts
        """
        module = kwargs.get("module", "Accounts")
        limit = min(kwargs.get("limit", 20), 100)

        cache_key = f"sugarcrm:{module}:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        if not await self._ensure_authenticated():
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=["SugarCRM authentication failed"],
            )

        try:
            if module == "Accounts":
                result = await self._search_accounts(query, limit)
            elif module == "Contacts":
                result = await self._search_contacts(query, limit)
            elif module == "Leads":
                result = await self._search_leads(query, limit)
            elif module == "Opportunities":
                result = await self._search_opportunities(query, limit)
            else:
                result = await self._search_accounts(query, limit)

            if result.facts:
                self._set_cached(cache_key, result)

            self._logger.info(
                "sugarcrm_search_success",
                query=query,
                module=module,
                facts_found=len(result.facts),
            )
            return result

        except Exception as e:
            self._logger.error("sugarcrm_search_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"SugarCRM search failed: {str(e)}"],
            )

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        """Make an authenticated API request."""
        url = f"{self._base_url}/rest/v11_12/{endpoint}"
        headers = {"OAuth-Token": self._access_token}

        if method.upper() == "GET":
            response = await self._client.get(url, params=params, headers=headers)
        elif method.upper() == "POST":
            response = await self._client.post(url, json=json_data, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.status_code != 200:
            raise Exception(f"SugarCRM API error: {response.status_code}")

        return response.json()

    async def _search_accounts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Accounts."""
        facts = []
        entities = []

        try:
            data = await self._api_request(
                "GET",
                "Accounts",
                params={
                    "filter[0][$or][0][name][$contains]": query,
                    "filter[0][$or][1][website][$contains]": query,
                    "max_num": limit,
                    "fields": "id,name,industry,website,phone_office,billing_address_city,billing_address_country,employees,annual_revenue",
                },
            )

            for record in data.get("records", []):
                account_facts, entity = self._parse_account(record)
                facts.extend(account_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("sugarcrm_account_search_failed", error=str(e))
            return MCPQueryResult(facts=[], query=query, mcp_server=self.name, errors=[str(e)])

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_account(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert SugarCRM Account to EvidencedFacts."""
        facts = []
        sugar_id = record.get("id", "")
        name = record.get("name") or "Unknown Account"

        source_url = f"{self._base_url}/#Accounts/{sugar_id}"

        extracted_data = {
            "sugarcrm_id": sugar_id,
            "name": name,
            "industry": record.get("industry"),
            "website": record.get("website"),
            "phone": record.get("phone_office"),
            "city": record.get("billing_address_city"),
            "country": record.get("billing_address_country"),
            "employee_count": record.get("employees"),
            "annual_revenue": record.get("annual_revenue"),
        }

        facts.append(
            self.create_fact(
                claim=f"{name} is tracked in SugarCRM",
                fact_type=FactType.COMPANY_INFO.value,
                source_name="SugarCRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name],
            )
        )

        if record.get("industry"):
            facts.append(
                self.create_fact(
                    claim=f"{name} operates in {record.get('industry')}",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="SugarCRM",
                    source_url=source_url,
                    confidence=0.90,
                    extracted_data={"industry": record.get("industry")},
                    related_entities=[name],
                )
            )

        if record.get("employees"):
            facts.append(
                self.create_fact(
                    claim=f"{name} has {record.get('employees')} employees",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="SugarCRM",
                    source_url=source_url,
                    confidence=0.85,
                    extracted_data={"employee_count": record.get("employees")},
                    related_entities=[name],
                )
            )

        entity = EntityReference(
            entity_type=EntityType.COMPANY,
            name=name,
            canonical_name=name.upper(),
            website=record.get("website"),
            external_ids={"sugarcrm_id": sugar_id},
        )

        return facts, entity

    async def _search_contacts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Contacts."""
        facts = []
        entities = []

        try:
            data = await self._api_request(
                "GET",
                "Contacts",
                params={
                    "filter[0][$or][0][first_name][$contains]": query,
                    "filter[0][$or][1][last_name][$contains]": query,
                    "filter[0][$or][2][email1][$contains]": query,
                    "max_num": limit,
                    "fields": "id,first_name,last_name,title,email1,phone_work,account_name",
                },
            )

            for record in data.get("records", []):
                contact_facts, entity = self._parse_contact(record)
                facts.extend(contact_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("sugarcrm_contact_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_contact(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert SugarCRM Contact to EvidencedFacts."""
        facts = []
        sugar_id = record.get("id", "")
        first_name = record.get("first_name") or ""
        last_name = record.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or "Unknown Contact"
        email = record.get("email1") or ""
        account_name = record.get("account_name") or ""

        source_url = f"{self._base_url}/#Contacts/{sugar_id}"

        extracted_data = {
            "sugarcrm_id": sugar_id,
            "first_name": first_name,
            "last_name": last_name,
            "title": record.get("title"),
            "email": email,
            "phone": record.get("phone_work"),
            "account_name": account_name,
        }

        claim_parts = [f"{name}"]
        if record.get("title"):
            claim_parts.append(f"({record.get('title')})")
        if account_name:
            claim_parts.append(f"at {account_name}")
        claim_parts.append("is a contact in SugarCRM")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="SugarCRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name, account_name] if account_name else [name],
            )
        )

        if email:
            facts.append(
                self.create_fact(
                    claim=f"{name} can be reached at {email}",
                    fact_type=FactType.CONTACT_INFO.value,
                    source_name="SugarCRM",
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
            external_ids={"sugarcrm_id": sugar_id, "email": email} if email else {"sugarcrm_id": sugar_id},
        )

        return facts, entity

    async def _search_leads(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Leads."""
        facts = []
        entities = []

        try:
            data = await self._api_request(
                "GET",
                "Leads",
                params={
                    "filter[0][$or][0][first_name][$contains]": query,
                    "filter[0][$or][1][last_name][$contains]": query,
                    "filter[0][$or][2][account_name][$contains]": query,
                    "max_num": limit,
                    "fields": "id,first_name,last_name,title,email1,phone_work,account_name,status,lead_source",
                },
            )

            for record in data.get("records", []):
                lead_facts, entity = self._parse_lead(record)
                facts.extend(lead_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("sugarcrm_lead_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_lead(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert SugarCRM Lead to EvidencedFacts."""
        facts = []
        sugar_id = record.get("id", "")
        first_name = record.get("first_name") or ""
        last_name = record.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or "Unknown Lead"
        account_name = record.get("account_name") or ""

        source_url = f"{self._base_url}/#Leads/{sugar_id}"

        extracted_data = {
            "sugarcrm_id": sugar_id,
            "first_name": first_name,
            "last_name": last_name,
            "title": record.get("title"),
            "email": record.get("email1"),
            "phone": record.get("phone_work"),
            "account_name": account_name,
            "status": record.get("status"),
            "lead_source": record.get("lead_source"),
        }

        claim_parts = [f"{name}"]
        if record.get("title"):
            claim_parts.append(f"({record.get('title')})")
        if account_name:
            claim_parts.append(f"at {account_name}")
        status = record.get("status", "Unknown")
        claim_parts.append(f"is a lead in SugarCRM (Status: {status})")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="SugarCRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name, account_name] if account_name else [name],
            )
        )

        entity = EntityReference(
            entity_type=EntityType.PERSON,
            name=name,
            canonical_name=name.upper(),
            external_ids={"sugarcrm_id": sugar_id},
        )

        return facts, entity

    async def _search_opportunities(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Opportunities."""
        facts = []

        try:
            data = await self._api_request(
                "GET",
                "Opportunities",
                params={
                    "filter[0][name][$contains]": query,
                    "max_num": limit,
                    "fields": "id,name,amount,sales_stage,date_closed,account_name,probability",
                },
            )

            for record in data.get("records", []):
                opp_facts = self._parse_opportunity(record)
                facts.extend(opp_facts)

        except Exception as e:
            self._logger.warning("sugarcrm_opportunity_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_opportunity(self, record: dict) -> list:
        """Convert SugarCRM Opportunity to EvidencedFacts."""
        facts = []
        sugar_id = record.get("id", "")
        name = record.get("name") or "Unknown Opportunity"
        account_name = record.get("account_name") or ""

        source_url = f"{self._base_url}/#Opportunities/{sugar_id}"

        extracted_data = {
            "sugarcrm_id": sugar_id,
            "name": name,
            "amount": record.get("amount"),
            "stage": record.get("sales_stage"),
            "close_date": record.get("date_closed"),
            "account_name": account_name,
            "probability": record.get("probability"),
        }

        claim_parts = [f"Opportunity '{name}'"]
        if record.get("amount"):
            claim_parts.append(f"worth ${float(record.get('amount')):,.0f}")
        if account_name:
            claim_parts.append(f"with {account_name}")
        if record.get("sales_stage"):
            claim_parts.append(f"is at stage '{record.get('sales_stage')}'")
        claim_parts.append("in SugarCRM")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.DEAL_INFO.value,
                source_name="SugarCRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[account_name] if account_name else [],
            )
        )

        return facts

    async def create_lead(self, lead_data: dict[str, Any]) -> str | None:
        """Create a new Lead in SugarCRM."""
        if not await self._ensure_authenticated():
            return None

        try:
            data = await self._api_request("POST", "Leads", json_data=lead_data)
            lead_id = data.get("id")
            self._logger.info("sugarcrm_lead_created", lead_id=lead_id)
            return lead_id

        except Exception as e:
            self._logger.error("sugarcrm_lead_create_error", error=str(e))
            return None

    async def create_account(self, account_data: dict[str, Any]) -> str | None:
        """Create a new Account in SugarCRM."""
        if not await self._ensure_authenticated():
            return None

        try:
            data = await self._api_request("POST", "Accounts", json_data=account_data)
            account_id = data.get("id")
            self._logger.info("sugarcrm_account_created", account_id=account_id)
            return account_id

        except Exception as e:
            self._logger.error("sugarcrm_account_create_error", error=str(e))
            return None

    async def close(self) -> None:
        """Close HTTP client and logout."""
        try:
            if self._access_token:
                await self._client.post(
                    f"{self._base_url}/rest/v11_12/oauth2/logout",
                    headers={"OAuth-Token": self._access_token},
                )
        except Exception:
            pass
        finally:
            await self._client.aclose()
