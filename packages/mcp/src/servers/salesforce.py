"""Salesforce MCP Server - CRM data integration.

Provides evidence-backed facts from Salesforce CRM:
- Account information
- Lead and contact data
- Opportunity pipeline
- Activity history

API Documentation: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/
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


class SalesforceMCPServer(APIBasedMCPServer):
    """MCP Server for Salesforce CRM data.

    Connects to Salesforce REST API to extract:
    - Account data (name, industry, revenue, employees)
    - Lead information (status, source, rating)
    - Contact details (email, phone, title)
    - Opportunity pipeline (stage, amount, close date)

    Requires environment variables:
        - SALESFORCE_CLIENT_ID: Connected App Consumer Key
        - SALESFORCE_CLIENT_SECRET: Connected App Consumer Secret
        - SALESFORCE_USERNAME: Salesforce username
        - SALESFORCE_PASSWORD: Salesforce password + security token
        - SALESFORCE_DOMAIN: login.salesforce.com or test.salesforce.com

    Example:
        server = SalesforceMCPServer.from_env()
        result = await server.search("Acme", object_type="Account")
    """

    API_VERSION = "v59.0"

    def __init__(self, config: MCPServerConfig, credentials: dict[str, str]) -> None:
        """Initialize Salesforce server.

        Args:
            config: Server configuration
            credentials: OAuth credentials dict
        """
        super().__init__(config)
        self._credentials = credentials
        self._access_token: str | None = None
        self._instance_url: str | None = None
        self._token_expires_at: datetime | None = None
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    @classmethod
    def from_env(cls) -> SalesforceMCPServer:
        """Create server from environment variables."""
        credentials = {
            "client_id": os.getenv("SALESFORCE_CLIENT_ID", ""),
            "client_secret": os.getenv("SALESFORCE_CLIENT_SECRET", ""),
            "username": os.getenv("SALESFORCE_USERNAME", ""),
            "password": os.getenv("SALESFORCE_PASSWORD", ""),
            "domain": os.getenv("SALESFORCE_DOMAIN", "login.salesforce.com"),
        }

        config = MCPServerConfig(
            name="Salesforce CRM",
            source_type=SourceType.SALESFORCE,
            description="Salesforce CRM - accounts, leads, contacts, opportunities",
            api_key=credentials.get("client_id"),  # For is_configured check
            requires_api_key=True,
            rate_limit_per_hour=1000,
            rate_limit_per_day=15000,
            cache_ttl_seconds=1800,  # 30 minutes
        )
        return cls(config, credentials)

    @property
    def is_configured(self) -> bool:
        """Check if all credentials are configured."""
        return all([
            self._credentials.get("client_id"),
            self._credentials.get("client_secret"),
            self._credentials.get("username"),
            self._credentials.get("password"),
        ])

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token."""
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return True

        return await self._authenticate()

    async def _authenticate(self) -> bool:
        """Authenticate with Salesforce OAuth."""
        try:
            domain = self._credentials.get("domain", "login.salesforce.com")
            token_url = f"https://{domain}/services/oauth2/token"

            response = await self._client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": self._credentials.get("client_id"),
                    "client_secret": self._credentials.get("client_secret"),
                    "username": self._credentials.get("username"),
                    "password": self._credentials.get("password"),
                },
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                self._instance_url = data.get("instance_url")
                # Tokens typically last 2 hours
                self._token_expires_at = datetime.utcnow() + timedelta(hours=2)

                self._logger.info(
                    "salesforce_authenticated",
                    instance_url=self._instance_url,
                )
                return True
            else:
                self._logger.error(
                    "salesforce_auth_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return False

        except Exception as e:
            self._logger.error("salesforce_auth_error", error=str(e))
            return False

    async def _health_check_impl(self) -> bool:
        """Verify Salesforce API accessibility."""
        if not await self._ensure_authenticated():
            return False

        try:
            response = await self._client.get(
                f"{self._instance_url}/services/data/{self.API_VERSION}/limits",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("salesforce_health_check_failed", error=str(e))
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search Salesforce objects.

        Args:
            query: Search term
            **kwargs:
                - object_type: "Account", "Lead", "Contact", or "Opportunity"
                - limit: Max results (default: 20)

        Returns:
            Query result with Salesforce facts
        """
        object_type = kwargs.get("object_type", "Account")
        limit = min(kwargs.get("limit", 20), 200)

        # Check cache
        cache_key = f"salesforce:{object_type}:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        if not await self._ensure_authenticated():
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=["Salesforce authentication failed"],
            )

        try:
            if object_type == "Account":
                result = await self._search_accounts(query, limit)
            elif object_type == "Lead":
                result = await self._search_leads(query, limit)
            elif object_type == "Contact":
                result = await self._search_contacts(query, limit)
            elif object_type == "Opportunity":
                result = await self._search_opportunities(query, limit)
            else:
                result = await self._search_accounts(query, limit)

            if result.facts:
                self._set_cached(cache_key, result)

            self._logger.info(
                "salesforce_search_success",
                query=query,
                object_type=object_type,
                facts_found=len(result.facts),
            )
            return result

        except Exception as e:
            self._logger.error("salesforce_search_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"Salesforce search failed: {str(e)}"],
            )

    async def _soql_query(self, soql: str) -> list[dict]:
        """Execute a SOQL query."""
        response = await self._client.get(
            f"{self._instance_url}/services/data/{self.API_VERSION}/query",
            params={"q": soql},
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

        if response.status_code != 200:
            raise Exception(f"SOQL query failed: {response.status_code}")

        data = response.json()
        return data.get("records", [])

    async def _search_accounts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Accounts by name."""
        facts = []
        entities = []

        try:
            # SOQL query for accounts
            soql = f"""
                SELECT Id, Name, Industry, Type, Website, Phone,
                       BillingCity, BillingCountry, NumberOfEmployees,
                       AnnualRevenue, Description, OwnerId
                FROM Account
                WHERE Name LIKE '%{query}%'
                LIMIT {limit}
            """

            records = await self._soql_query(soql)

            for record in records:
                account_facts, entity = self._parse_account(record)
                facts.extend(account_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("salesforce_account_search_failed", error=str(e))
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

    def _parse_account(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert Salesforce Account to EvidencedFacts."""
        facts = []
        sf_id = record.get("Id", "")
        name = record.get("Name") or "Unknown Account"

        source_url = f"{self._instance_url}/{sf_id}" if self._instance_url else None

        extracted_data = {
            "salesforce_id": sf_id,
            "name": name,
            "industry": record.get("Industry"),
            "type": record.get("Type"),
            "website": record.get("Website"),
            "phone": record.get("Phone"),
            "city": record.get("BillingCity"),
            "country": record.get("BillingCountry"),
            "employee_count": record.get("NumberOfEmployees"),
            "annual_revenue": record.get("AnnualRevenue"),
        }

        # Fact 1: Account exists in CRM
        facts.append(
            self.create_fact(
                claim=f"{name} is tracked in Salesforce CRM",
                fact_type=FactType.COMPANY_INFO.value,
                source_name="Salesforce CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name],
            )
        )

        # Fact 2: Industry
        if record.get("Industry"):
            facts.append(
                self.create_fact(
                    claim=f"{name} operates in {record.get('Industry')}",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="Salesforce CRM",
                    source_url=source_url,
                    confidence=0.90,
                    extracted_data={"industry": record.get("Industry")},
                    related_entities=[name],
                )
            )

        # Fact 3: Employee count
        if record.get("NumberOfEmployees"):
            facts.append(
                self.create_fact(
                    claim=f"{name} has {record.get('NumberOfEmployees')} employees",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="Salesforce CRM",
                    source_url=source_url,
                    confidence=0.85,
                    extracted_data={"employee_count": record.get("NumberOfEmployees")},
                    related_entities=[name],
                )
            )

        # Fact 4: Revenue
        if record.get("AnnualRevenue"):
            facts.append(
                self.create_fact(
                    claim=f"{name} has annual revenue of ${record.get('AnnualRevenue'):,.0f}",
                    fact_type=FactType.FINANCIAL.value,
                    source_name="Salesforce CRM",
                    source_url=source_url,
                    confidence=0.80,
                    extracted_data={"annual_revenue": record.get("AnnualRevenue")},
                    related_entities=[name],
                )
            )

        # Entity reference
        entity = EntityReference(
            entity_type=EntityType.COMPANY,
            name=name,
            canonical_name=name.upper(),
            website=record.get("Website"),
            external_ids={"salesforce_id": sf_id},
        )

        return facts, entity

    async def _search_leads(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Leads."""
        facts = []
        entities = []

        try:
            soql = f"""
                SELECT Id, Name, Company, Title, Email, Phone, Status,
                       LeadSource, Rating, Industry, AnnualRevenue,
                       NumberOfEmployees, City, Country
                FROM Lead
                WHERE Name LIKE '%{query}%' OR Company LIKE '%{query}%'
                LIMIT {limit}
            """

            records = await self._soql_query(soql)

            for record in records:
                lead_facts, entity = self._parse_lead(record)
                facts.extend(lead_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("salesforce_lead_search_failed", error=str(e))
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

    def _parse_lead(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert Salesforce Lead to EvidencedFacts."""
        facts = []
        sf_id = record.get("Id", "")
        name = record.get("Name") or "Unknown Lead"
        company = record.get("Company") or ""

        source_url = f"{self._instance_url}/{sf_id}" if self._instance_url else None

        extracted_data = {
            "salesforce_id": sf_id,
            "name": name,
            "company": company,
            "title": record.get("Title"),
            "email": record.get("Email"),
            "phone": record.get("Phone"),
            "status": record.get("Status"),
            "source": record.get("LeadSource"),
            "rating": record.get("Rating"),
        }

        # Fact 1: Lead info
        claim_parts = [f"{name}"]
        if record.get("Title"):
            claim_parts.append(f"({record.get('Title')})")
        if company:
            claim_parts.append(f"at {company}")
        claim_parts.append(f"is a lead in Salesforce (Status: {record.get('Status', 'Unknown')})")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="Salesforce CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name, company] if company else [name],
            )
        )

        # Fact 2: Contact available
        if record.get("Email"):
            facts.append(
                self.create_fact(
                    claim=f"{name} can be reached at {record.get('Email')}",
                    fact_type=FactType.CONTACT_INFO.value,
                    source_name="Salesforce CRM",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={"email": record.get("Email")},
                    related_entities=[name],
                )
            )

        # Entity reference
        entity = EntityReference(
            entity_type=EntityType.PERSON,
            name=name,
            canonical_name=name.upper(),
            external_ids={"salesforce_id": sf_id, "email": record.get("Email", "")},
        )

        return facts, entity

    async def _search_contacts(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Contacts."""
        facts = []
        entities = []

        try:
            soql = f"""
                SELECT Id, Name, Title, Email, Phone, AccountId,
                       Account.Name, MailingCity, MailingCountry
                FROM Contact
                WHERE Name LIKE '%{query}%' OR Email LIKE '%{query}%'
                LIMIT {limit}
            """

            records = await self._soql_query(soql)

            for record in records:
                contact_facts, entity = self._parse_contact(record)
                facts.extend(contact_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            self._logger.warning("salesforce_contact_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_contact(self, record: dict) -> tuple[list, EntityReference | None]:
        """Convert Salesforce Contact to EvidencedFacts."""
        facts = []
        sf_id = record.get("Id", "")
        name = record.get("Name") or "Unknown Contact"
        account = record.get("Account", {}) or {}
        account_name = account.get("Name", "")

        source_url = f"{self._instance_url}/{sf_id}" if self._instance_url else None

        extracted_data = {
            "salesforce_id": sf_id,
            "name": name,
            "title": record.get("Title"),
            "email": record.get("Email"),
            "phone": record.get("Phone"),
            "account_id": record.get("AccountId"),
            "account_name": account_name,
        }

        # Fact 1: Contact info
        claim_parts = [f"{name}"]
        if record.get("Title"):
            claim_parts.append(f"({record.get('Title')})")
        if account_name:
            claim_parts.append(f"at {account_name}")
        claim_parts.append("is a contact in Salesforce")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.CONTACT_INFO.value,
                source_name="Salesforce CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[name, account_name] if account_name else [name],
            )
        )

        # Entity reference
        entity = EntityReference(
            entity_type=EntityType.PERSON,
            name=name,
            canonical_name=name.upper(),
            external_ids={"salesforce_id": sf_id},
        )

        return facts, entity

    async def _search_opportunities(self, query: str, limit: int) -> MCPQueryResult:
        """Search for Opportunities."""
        facts = []

        try:
            soql = f"""
                SELECT Id, Name, Amount, StageName, CloseDate, Probability,
                       AccountId, Account.Name, Type, LeadSource
                FROM Opportunity
                WHERE Name LIKE '%{query}%' OR Account.Name LIKE '%{query}%'
                LIMIT {limit}
            """

            records = await self._soql_query(soql)

            for record in records:
                opp_facts = self._parse_opportunity(record)
                facts.extend(opp_facts)

        except Exception as e:
            self._logger.warning("salesforce_opportunity_search_failed", error=str(e))

        return MCPQueryResult(
            facts=facts,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
        )

    def _parse_opportunity(self, record: dict) -> list:
        """Convert Salesforce Opportunity to EvidencedFacts."""
        facts = []
        sf_id = record.get("Id", "")
        name = record.get("Name") or "Unknown Opportunity"
        account = record.get("Account", {}) or {}
        account_name = account.get("Name", "")

        source_url = f"{self._instance_url}/{sf_id}" if self._instance_url else None

        extracted_data = {
            "salesforce_id": sf_id,
            "name": name,
            "amount": record.get("Amount"),
            "stage": record.get("StageName"),
            "close_date": record.get("CloseDate"),
            "probability": record.get("Probability"),
            "account_name": account_name,
        }

        # Fact: Opportunity info
        claim_parts = [f"Opportunity '{name}'"]
        if record.get("Amount"):
            claim_parts.append(f"worth ${record.get('Amount'):,.0f}")
        if account_name:
            claim_parts.append(f"with {account_name}")
        claim_parts.append(f"is at stage '{record.get('StageName', 'Unknown')}'")
        if record.get("Probability"):
            claim_parts.append(f"({record.get('Probability')}% probability)")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.DEAL_INFO.value,
                source_name="Salesforce CRM",
                source_url=source_url,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[account_name] if account_name else [],
            )
        )

        return facts

    # Write operations

    async def create_lead(self, lead_data: dict[str, Any]) -> str | None:
        """Create a new Lead in Salesforce.

        Args:
            lead_data: Lead fields (LastName required, Company required)

        Returns:
            Salesforce Lead ID if successful
        """
        if not await self._ensure_authenticated():
            return None

        try:
            response = await self._client.post(
                f"{self._instance_url}/services/data/{self.API_VERSION}/sobjects/Lead",
                json=lead_data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 201:
                data = response.json()
                lead_id = data.get("id")
                self._logger.info("salesforce_lead_created", lead_id=lead_id)
                return lead_id
            else:
                self._logger.warning(
                    "salesforce_lead_create_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return None

        except Exception as e:
            self._logger.error("salesforce_lead_create_error", error=str(e))
            return None

    async def create_account(self, account_data: dict[str, Any]) -> str | None:
        """Create a new Account in Salesforce.

        Args:
            account_data: Account fields (Name required)

        Returns:
            Salesforce Account ID if successful
        """
        if not await self._ensure_authenticated():
            return None

        try:
            response = await self._client.post(
                f"{self._instance_url}/services/data/{self.API_VERSION}/sobjects/Account",
                json=account_data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 201:
                data = response.json()
                account_id = data.get("id")
                self._logger.info("salesforce_account_created", account_id=account_id)
                return account_id
            else:
                self._logger.warning("salesforce_account_create_failed", status=response.status_code)
                return None

        except Exception as e:
            self._logger.error("salesforce_account_create_error", error=str(e))
            return None

    async def update_lead(self, lead_id: str, data: dict[str, Any]) -> bool:
        """Update an existing Lead.

        Args:
            lead_id: Salesforce Lead ID
            data: Fields to update

        Returns:
            True if successful
        """
        if not await self._ensure_authenticated():
            return False

        try:
            response = await self._client.patch(
                f"{self._instance_url}/services/data/{self.API_VERSION}/sobjects/Lead/{lead_id}",
                json=data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 204:
                self._logger.info("salesforce_lead_updated", lead_id=lead_id)
                return True
            else:
                self._logger.warning("salesforce_lead_update_failed", status=response.status_code)
                return False

        except Exception as e:
            self._logger.error("salesforce_lead_update_error", error=str(e))
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
