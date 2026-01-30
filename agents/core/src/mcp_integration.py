"""MCP Integration for GTM Agents.

Provides agents with access to the Knowledge Web via MCP servers.
This enables evidence-backed fact gathering from multiple data sources.

Usage:
    from agents.core.src.mcp_integration import AgentMCPClient

    class MyAgent(BaseGTMAgent[MyOutput]):
        def __init__(self):
            super().__init__(...)
            self._mcp = AgentMCPClient()

        async def _do(self, plan, context):
            # Get facts from MCP servers
            facts = await self._mcp.research_topic("Singapore fintech market")
            # Process facts into agent output
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from packages.mcp.src.registry import MCPRegistry
from packages.mcp.src.servers.acra import ACRAMCPServer
from packages.mcp.src.servers.eodhd import EODHDMCPServer
from packages.mcp.src.servers.news import NewsAggregatorMCPServer
from packages.mcp.src.servers.web_scraper import WebScraperMCPServer
# CRM integrations
from packages.mcp.src.servers.hubspot import HubSpotMCPServer
from packages.mcp.src.servers.salesforce import SalesforceMCPServer
from packages.mcp.src.servers.dynamics import DynamicsMCPServer
from packages.mcp.src.servers.sugarcrm import SugarCRMMCPServer
# Email services
from packages.mcp.src.servers.mailgun import MailgunMCPServer
from packages.mcp.src.servers.sendgrid import SendGridMCPServer
from packages.mcp.src.types import (
    EvidencedFact,
    FactType,
    MCPServerConfig,
    SourceType,
)

logger = structlog.get_logger()


class AgentMCPClient:
    """MCP client for agents to access the Knowledge Web.

    Provides a simplified interface for agents to:
    - Search across multiple data sources
    - Get company information
    - Research market topics
    - Find news and signals

    All results are EvidencedFacts with full provenance.

    Example:
        mcp = AgentMCPClient()
        facts = await mcp.research_topic("Singapore SaaS market")

        for fact in facts:
            print(f"- {fact.claim}")
            print(f"  Source: {fact.source_name} ({fact.source_url})")
            print(f"  Confidence: {fact.confidence}")
    """

    def __init__(self, auto_register: bool = True) -> None:
        """Initialize the MCP client.

        Args:
            auto_register: Automatically register available servers
        """
        self._registry = MCPRegistry()
        self._logger = logger.bind(component="agent_mcp_client")

        if auto_register:
            self._register_default_servers()

    def _register_default_servers(self) -> None:
        """Register all available MCP servers based on configuration."""
        # ACRA (data.gov.sg) - always available, no API key needed
        try:
            acra_config = MCPServerConfig(
                name="ACRA Singapore",
                source_type=SourceType.GOVERNMENT,
                description="Singapore company registry via data.gov.sg",
                timeout_seconds=30,
            )
            self._registry.register(ACRAMCPServer(acra_config))
            self._logger.info("registered_server", server="acra")
        except Exception as e:
            self._logger.warning("server_registration_failed", server="acra", error=str(e))

        # NewsAPI - requires API key
        newsapi_key = os.getenv("NEWSAPI_API_KEY")
        if newsapi_key:
            try:
                news_config = MCPServerConfig(
                    name="News Aggregator",
                    source_type=SourceType.NEWSAPI,
                    description="News from NewsAPI and Singapore RSS feeds",
                    api_key=newsapi_key,
                    timeout_seconds=30,
                )
                self._registry.register(NewsAggregatorMCPServer(news_config))
                self._logger.info("registered_server", server="news")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="news", error=str(e))

        # EODHD - requires API key
        eodhd_key = os.getenv("EODHD_API_KEY")
        if eodhd_key:
            try:
                eodhd_config = MCPServerConfig(
                    name="EODHD Financial",
                    source_type=SourceType.EODHD,
                    description="Financial data and economic indicators",
                    api_key=eodhd_key,
                    timeout_seconds=30,
                )
                self._registry.register(EODHDMCPServer(eodhd_config))
                self._logger.info("registered_server", server="eodhd")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="eodhd", error=str(e))

        # Web Scraper - always available
        try:
            scraper_config = MCPServerConfig(
                name="Web Scraper",
                source_type=SourceType.WEB_SCRAPE,
                description="Website scraping for company data and tech stack",
                timeout_seconds=30,
            )
            self._registry.register(WebScraperMCPServer(scraper_config))
            self._logger.info("registered_server", server="web_scraper")
        except Exception as e:
            self._logger.warning("server_registration_failed", server="web_scraper", error=str(e))

        # === CRM Integrations ===

        # HubSpot CRM
        if os.getenv("HUBSPOT_API_KEY"):
            try:
                self._registry.register(HubSpotMCPServer.from_env())
                self._logger.info("registered_server", server="hubspot")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="hubspot", error=str(e))

        # Salesforce CRM
        if os.getenv("SALESFORCE_CLIENT_ID"):
            try:
                self._registry.register(SalesforceMCPServer.from_env())
                self._logger.info("registered_server", server="salesforce")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="salesforce", error=str(e))

        # Microsoft Dynamics 365
        if os.getenv("DYNAMICS_CLIENT_ID"):
            try:
                self._registry.register(DynamicsMCPServer.from_env())
                self._logger.info("registered_server", server="dynamics")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="dynamics", error=str(e))

        # SugarCRM
        if os.getenv("SUGARCRM_URL"):
            try:
                self._registry.register(SugarCRMMCPServer.from_env())
                self._logger.info("registered_server", server="sugarcrm")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="sugarcrm", error=str(e))

        # === Email Services ===

        # Mailgun
        if os.getenv("MAILGUN_API_KEY") and os.getenv("MAILGUN_DOMAIN"):
            try:
                self._registry.register(MailgunMCPServer.from_env())
                self._logger.info("registered_server", server="mailgun")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="mailgun", error=str(e))

        # SendGrid
        if os.getenv("SENDGRID_API_KEY"):
            try:
                self._registry.register(SendGridMCPServer.from_env())
                self._logger.info("registered_server", server="sendgrid")
            except Exception as e:
                self._logger.warning("server_registration_failed", server="sendgrid", error=str(e))

    @property
    def registry(self) -> MCPRegistry:
        """Get the underlying registry."""
        return self._registry

    async def search(
        self,
        query: str,
        source_types: list[SourceType] | None = None,
        limit: int = 20,
    ) -> list[EvidencedFact]:
        """Search across all registered MCP servers.

        Args:
            query: Search query
            source_types: Optional filter by source types
            limit: Maximum results per server

        Returns:
            List of evidenced facts from all sources
        """
        result = await self._registry.search(
            query=query,
            source_types=source_types,
        )
        return result.facts[:limit] if result.facts else []

    async def research_topic(
        self,
        topic: str,
        industry: str | None = None,
        region: str = "Singapore",
        limit: int = 30,
    ) -> list[EvidencedFact]:
        """Research a topic using multiple data sources.

        Combines results from news, government data, and web search.

        Args:
            topic: Research topic
            industry: Industry vertical
            region: Geographic focus
            limit: Maximum results

        Returns:
            Curated list of relevant facts
        """
        # Build comprehensive search query
        query_parts = [topic]
        if industry:
            query_parts.append(industry)
        if region:
            query_parts.append(region)

        query = " ".join(query_parts)

        # Search across all sources
        facts = await self.search(query, limit=limit * 2)

        # Sort by confidence and return top results
        facts.sort(key=lambda f: f.confidence, reverse=True)
        return facts[:limit]

    async def get_company_info(
        self,
        company_name: str,
        uen: str | None = None,
        website: str | None = None,
    ) -> list[EvidencedFact]:
        """Get information about a company.

        Searches ACRA, news, and optionally scrapes website.

        Args:
            company_name: Company name
            uen: Singapore UEN if known
            website: Company website to scrape

        Returns:
            Facts about the company
        """
        facts: list[EvidencedFact] = []

        # Search ACRA if available
        acra_server = self._registry.get_server("ACRA Singapore")
        if acra_server:
            try:
                search_term = uen or company_name
                result = await acra_server.search(search_term, limit=5)
                facts.extend(result.facts)
            except Exception as e:
                self._logger.warning("acra_search_failed", error=str(e))

        # Search news
        news_server = self._registry.get_server("News Aggregator")
        if news_server:
            try:
                result = await news_server.search(company_name, limit=10)
                facts.extend(result.facts)
            except Exception as e:
                self._logger.warning("news_search_failed", error=str(e))

        # Scrape website if provided
        if website:
            scraper = self._registry.get_server("Web Scraper")
            if scraper:
                try:
                    result = await scraper.search(website)
                    facts.extend(result.facts)
                except Exception as e:
                    self._logger.warning("scrape_failed", error=str(e))

        return facts

    async def find_market_news(
        self,
        industry: str,
        region: str = "Singapore",
        limit: int = 20,
    ) -> list[EvidencedFact]:
        """Find market news for an industry.

        Args:
            industry: Industry to search
            region: Geographic focus
            limit: Maximum results

        Returns:
            News facts sorted by recency
        """
        news_server = self._registry.get_server("News Aggregator")
        if not news_server:
            return []

        try:
            query = f"{industry} {region}"
            result = await news_server.search(query, limit=limit)
            return result.facts
        except Exception as e:
            self._logger.warning("news_search_failed", error=str(e))
            return []

    async def find_funding_news(
        self,
        industry: str | None = None,
        region: str = "Singapore",
        limit: int = 10,
    ) -> list[EvidencedFact]:
        """Find recent funding announcements.

        Args:
            industry: Optional industry filter
            region: Geographic focus
            limit: Maximum results

        Returns:
            Funding-related facts
        """
        query_parts = ["funding startup raised investment"]
        if industry:
            query_parts.append(industry)
        query_parts.append(region)

        query = " ".join(query_parts)

        facts = await self.search(query, limit=limit * 2)

        # Filter to funding-related facts
        funding_facts = [
            f for f in facts
            if f.fact_type in (FactType.FUNDING, FactType.ACQUISITION)
        ]

        return funding_facts[:limit]

    async def find_hiring_signals(
        self,
        company_name: str | None = None,
        industry: str | None = None,
        limit: int = 10,
    ) -> list[EvidencedFact]:
        """Find hiring signals.

        Args:
            company_name: Optional company filter
            industry: Optional industry filter
            limit: Maximum results

        Returns:
            Hiring-related facts
        """
        query_parts = ["hiring jobs careers growing"]
        if company_name:
            query_parts.append(company_name)
        if industry:
            query_parts.append(industry)

        query = " ".join(query_parts)

        facts = await self.search(query, limit=limit * 2)

        # Filter to hiring-related facts
        hiring_facts = [
            f for f in facts
            if f.fact_type == FactType.HIRING
        ]

        return hiring_facts[:limit]

    def facts_to_context(self, facts: list[EvidencedFact]) -> dict[str, Any]:
        """Convert facts to a context dict for LLM prompts.

        Args:
            facts: List of evidenced facts

        Returns:
            Context dictionary with structured fact data
        """
        context: dict[str, Any] = {
            "evidence": [],
            "sources": set(),
        }

        for fact in facts:
            context["evidence"].append({
                "claim": fact.claim,
                "source": fact.source_name,
                "url": fact.source_url,
                "confidence": fact.confidence,
                "type": fact.fact_type.value,
            })
            context["sources"].add(fact.source_name)

        context["sources"] = list(context["sources"])
        context["fact_count"] = len(facts)

        return context

    def summarize_facts(self, facts: list[EvidencedFact]) -> str:
        """Create a text summary of facts for LLM prompts.

        Args:
            facts: List of evidenced facts

        Returns:
            Formatted text summary
        """
        if not facts:
            return "No facts available."

        lines = [f"Evidence from {len(facts)} sources:"]

        for i, fact in enumerate(facts[:20], 1):  # Limit to 20 for context size
            lines.append(f"{i}. [{fact.source_name}] {fact.claim}")
            if fact.source_url:
                lines.append(f"   Source: {fact.source_url}")
            lines.append(f"   Confidence: {fact.confidence:.0%}")

        return "\n".join(lines)

    # === CRM Integration Methods ===

    async def sync_lead_to_crm(
        self,
        lead_data: dict[str, Any],
        crm_type: str = "hubspot",
    ) -> str | None:
        """Push a qualified lead to CRM.

        Args:
            lead_data: Lead data (email, name, company, etc.)
            crm_type: CRM to sync to ("hubspot", "salesforce", "dynamics", "sugarcrm")

        Returns:
            CRM record ID if successful, None otherwise
        """
        server_names = {
            "hubspot": "HubSpot CRM",
            "salesforce": "Salesforce CRM",
            "dynamics": "Microsoft Dynamics 365",
            "sugarcrm": "SugarCRM",
        }

        server_name = server_names.get(crm_type)
        if not server_name:
            self._logger.warning("unknown_crm_type", crm_type=crm_type)
            return None

        server = self._registry.get_server(server_name)
        if not server:
            self._logger.warning("crm_server_not_configured", crm_type=crm_type)
            return None

        try:
            if crm_type == "hubspot":
                return await server.create_contact(lead_data)
            elif crm_type == "salesforce":
                return await server.create_lead(lead_data)
            elif crm_type == "dynamics":
                return await server.create_lead(lead_data)
            elif crm_type == "sugarcrm":
                return await server.create_lead(lead_data)
        except Exception as e:
            self._logger.error("crm_sync_failed", crm_type=crm_type, error=str(e))
            return None

        return None

    async def get_crm_company(
        self,
        company_name: str,
        domain: str | None = None,
    ) -> list[EvidencedFact]:
        """Get company info from connected CRMs.

        Args:
            company_name: Company name to search
            domain: Optional company domain

        Returns:
            Facts from CRM about the company
        """
        facts: list[EvidencedFact] = []
        query = domain or company_name

        crm_servers = [
            "HubSpot CRM",
            "Salesforce CRM",
            "Microsoft Dynamics 365",
            "SugarCRM",
        ]

        for server_name in crm_servers:
            server = self._registry.get_server(server_name)
            if server:
                try:
                    result = await server.search(query, search_type="company", limit=5)
                    facts.extend(result.facts)
                except Exception as e:
                    self._logger.warning("crm_search_failed", server=server_name, error=str(e))

        return facts

    # === Email Integration Methods ===

    async def send_outreach_email(
        self,
        to: str,
        subject: str,
        body: str,
        template_id: str | None = None,
        template_data: dict[str, Any] | None = None,
        provider: str = "mailgun",
        tags: list[str] | None = None,
    ) -> str | None:
        """Send email via configured provider.

        Args:
            to: Recipient email
            subject: Email subject
            body: Plain text body
            template_id: Optional template ID
            template_data: Optional template variables
            provider: Email provider ("mailgun" or "sendgrid")
            tags: Optional tags for tracking

        Returns:
            Message ID if successful, None otherwise
        """
        server_names = {
            "mailgun": "Mailgun Email",
            "sendgrid": "SendGrid Email",
        }

        server_name = server_names.get(provider)
        if not server_name:
            self._logger.warning("unknown_email_provider", provider=provider)
            return None

        server = self._registry.get_server(server_name)
        if not server:
            self._logger.warning("email_server_not_configured", provider=provider)
            return None

        try:
            if template_id and template_data:
                return await server.send_template(
                    to=to,
                    template_id=template_id,
                    variables=template_data if provider == "mailgun" else template_data,
                    tags=tags,
                )
            else:
                return await server.send_email(
                    to=to,
                    subject=subject,
                    body=body,
                    tags=tags,
                )
        except Exception as e:
            self._logger.error("email_send_failed", provider=provider, error=str(e))
            return None

    async def get_email_engagement(
        self,
        message_id: str | None = None,
        recipient: str | None = None,
        provider: str = "mailgun",
    ) -> list[EvidencedFact]:
        """Get email engagement signals.

        Args:
            message_id: Optional message ID to filter
            recipient: Optional recipient email to filter
            provider: Email provider ("mailgun" or "sendgrid")

        Returns:
            Facts about email engagement (opens, clicks, etc.)
        """
        server_names = {
            "mailgun": "Mailgun Email",
            "sendgrid": "SendGrid Email",
        }

        server_name = server_names.get(provider)
        if not server_name:
            return []

        server = self._registry.get_server(server_name)
        if not server:
            return []

        try:
            query = message_id or recipient or ""
            if not query:
                return []

            result = await server.search(query, limit=50)
            return result.facts
        except Exception as e:
            self._logger.warning("email_engagement_fetch_failed", error=str(e))
            return []
