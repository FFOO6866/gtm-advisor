"""MCP Server Registry and Manager.

Centralized registry for all MCP servers, providing:
- Server registration and discovery
- Unified query interface
- Health monitoring
- Fact aggregation across sources
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from packages.mcp.src.base import BaseMCPServer
from packages.mcp.src.types import (
    EvidencedFact,
    MCPHealthStatus,
    MCPQueryResult,
    SourceType,
)

logger = structlog.get_logger()


class MCPRegistry:
    """Registry for MCP servers.

    Manages all MCP servers and provides a unified interface for:
    - Querying multiple servers in parallel
    - Aggregating facts from multiple sources
    - Health monitoring
    - Cross-source fact verification

    Example:
        registry = MCPRegistry()
        registry.register(ACRAMCPServer(config))
        registry.register(NewsAPIMCPServer(config))

        # Query all relevant servers
        result = await registry.search(
            query="TechCorp Singapore",
            source_types=[SourceType.ACRA, SourceType.NEWSAPI],
        )
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._servers: dict[str, BaseMCPServer] = {}
        self._servers_by_type: dict[SourceType, list[BaseMCPServer]] = {}
        self._logger = logger.bind(component="mcp_registry")

    def register(self, server: BaseMCPServer) -> None:
        """Register an MCP server.

        Args:
            server: The MCP server to register
        """
        if server.name in self._servers:
            self._logger.warning("server_already_registered", server=server.name)
            return

        self._servers[server.name] = server

        # Index by source type
        if server.source_type not in self._servers_by_type:
            self._servers_by_type[server.source_type] = []
        self._servers_by_type[server.source_type].append(server)

        self._logger.info(
            "server_registered",
            server=server.name,
            source_type=server.source_type.value,
        )

    def unregister(self, server_name: str) -> None:
        """Unregister an MCP server.

        Args:
            server_name: Name of server to unregister
        """
        if server_name not in self._servers:
            return

        server = self._servers.pop(server_name)

        # Remove from type index
        if server.source_type in self._servers_by_type:
            self._servers_by_type[server.source_type] = [
                s for s in self._servers_by_type[server.source_type] if s.name != server_name
            ]

        self._logger.info("server_unregistered", server=server_name)

    def get_server(self, name: str) -> BaseMCPServer | None:
        """Get a server by name.

        Args:
            name: Server name

        Returns:
            Server instance or None
        """
        return self._servers.get(name)

    def get_servers_by_type(self, source_type: SourceType) -> list[BaseMCPServer]:
        """Get all servers of a specific source type.

        Args:
            source_type: Source type to filter by

        Returns:
            List of servers
        """
        return self._servers_by_type.get(source_type, [])

    def get_all_servers(self) -> list[BaseMCPServer]:
        """Get all registered servers.

        Returns:
            List of all servers
        """
        return list(self._servers.values())

    def get_configured_servers(self) -> list[BaseMCPServer]:
        """Get all properly configured servers.

        Returns:
            List of configured servers
        """
        return [s for s in self._servers.values() if s.is_configured]

    async def search(
        self,
        query: str,
        source_types: list[SourceType] | None = None,
        server_names: list[str] | None = None,
        parallel: bool = True,
        **kwargs: Any,
    ) -> MCPQueryResult:
        """Search across multiple MCP servers.

        Args:
            query: Search query
            source_types: Filter to specific source types
            server_names: Filter to specific servers
            parallel: Execute queries in parallel
            **kwargs: Additional parameters passed to servers

        Returns:
            Aggregated query result
        """
        # Determine which servers to query
        servers_to_query = self._select_servers(source_types, server_names)

        if not servers_to_query:
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server="registry",
                warnings=["No configured servers available for query"],
            )

        self._logger.info(
            "search_started",
            query=query,
            servers=[s.name for s in servers_to_query],
        )

        # Execute queries
        if parallel:
            results = await self._query_parallel(query, servers_to_query, **kwargs)
        else:
            results = await self._query_sequential(query, servers_to_query, **kwargs)

        # Aggregate results
        return self._aggregate_results(query, results)

    def _select_servers(
        self,
        source_types: list[SourceType] | None,
        server_names: list[str] | None,
    ) -> list[BaseMCPServer]:
        """Select servers to query based on filters."""
        servers = []

        if server_names:
            # Query specific servers
            for name in server_names:
                server = self._servers.get(name)
                if server and server.is_configured:
                    servers.append(server)
        elif source_types:
            # Query by source type
            for st in source_types:
                for server in self._servers_by_type.get(st, []):
                    if server.is_configured:
                        servers.append(server)
        else:
            # Query all configured servers
            servers = self.get_configured_servers()

        return servers

    async def _query_parallel(
        self,
        query: str,
        servers: list[BaseMCPServer],
        **kwargs: Any,
    ) -> list[MCPQueryResult]:
        """Execute queries in parallel."""
        tasks = [server.execute_query(query, **kwargs) for server in servers]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _query_sequential(
        self,
        query: str,
        servers: list[BaseMCPServer],
        **kwargs: Any,
    ) -> list[MCPQueryResult]:
        """Execute queries sequentially."""
        results = []
        for server in servers:
            result = await server.execute_query(query, **kwargs)
            results.append(result)
        return results

    def _aggregate_results(
        self,
        query: str,
        results: list[MCPQueryResult],
    ) -> MCPQueryResult:
        """Aggregate results from multiple servers."""
        all_facts: list[EvidencedFact] = []
        all_entities = []
        all_errors = []
        all_warnings = []
        total_time = 0.0
        servers_queried = []

        for result in results:
            all_facts.extend(result.facts)
            all_entities.extend(result.entities)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            total_time += result.query_time_ms
            servers_queried.append(result.mcp_server)

        # Deduplicate and verify facts
        verified_facts = self._verify_and_dedupe_facts(all_facts)

        return MCPQueryResult(
            facts=verified_facts,
            entities=all_entities,
            query=query,
            mcp_server=f"registry:{','.join(servers_queried)}",
            query_time_ms=total_time,
            total_results=len(verified_facts),
            errors=all_errors,
            warnings=all_warnings,
        )

    def _verify_and_dedupe_facts(
        self,
        facts: list[EvidencedFact],
    ) -> list[EvidencedFact]:
        """Verify and deduplicate facts from multiple sources.

        Facts confirmed by multiple sources get higher confidence.
        """
        # Group facts by claim similarity
        fact_groups: dict[str, list[EvidencedFact]] = {}

        for fact in facts:
            # Simple claim normalization for grouping
            normalized = fact.claim.lower().strip()
            if normalized not in fact_groups:
                fact_groups[normalized] = []
            fact_groups[normalized].append(fact)

        # Process groups
        verified_facts = []
        for _claim, group in fact_groups.items():
            if len(group) == 1:
                verified_facts.append(group[0])
            else:
                # Multiple sources - boost confidence
                best_fact = max(group, key=lambda f: f.confidence)

                # Boost confidence for cross-source verification
                verification_count = len(group)
                confidence_boost = min(0.15, verification_count * 0.05)

                boosted_fact = EvidencedFact(
                    id=best_fact.id,
                    claim=best_fact.claim,
                    fact_type=best_fact.fact_type,
                    source_type=best_fact.source_type,
                    source_name=best_fact.source_name,
                    source_url=best_fact.source_url,
                    raw_excerpt=best_fact.raw_excerpt,
                    published_at=best_fact.published_at,
                    captured_at=best_fact.captured_at,
                    confidence=min(1.0, best_fact.confidence + confidence_boost),
                    verification_count=verification_count,
                    extracted_data=best_fact.extracted_data,
                    related_entities=best_fact.related_entities,
                    mcp_server=best_fact.mcp_server,
                )
                verified_facts.append(boosted_fact)

        # Sort by confidence
        verified_facts.sort(key=lambda f: f.confidence, reverse=True)

        return verified_facts

    async def health_check_all(self) -> list[MCPHealthStatus]:
        """Check health of all registered servers.

        Returns:
            List of health statuses
        """
        tasks = [server.health_check() for server in self._servers.values()]
        return await asyncio.gather(*tasks)

    async def get_server_status(self, name: str) -> MCPHealthStatus | None:
        """Get health status of a specific server.

        Args:
            name: Server name

        Returns:
            Health status or None
        """
        server = self._servers.get(name)
        if not server:
            return None
        return await server.health_check()


class MCPManager:
    """High-level manager for MCP operations.

    Provides convenience methods for common operations:
    - Research a company across all sources
    - Monitor competitors
    - Find intent signals
    """

    def __init__(self, registry: MCPRegistry) -> None:
        """Initialize manager.

        Args:
            registry: MCP registry to use
        """
        self._registry = registry
        self._logger = logger.bind(component="mcp_manager")

    async def research_company(
        self,
        company_name: str,
        website: str | None = None,
        include_news: bool = True,
        include_financials: bool = True,
    ) -> MCPQueryResult:
        """Research a company across all available sources.

        Args:
            company_name: Company name
            website: Company website
            include_news: Include news sources
            include_financials: Include financial sources

        Returns:
            Aggregated research results
        """
        source_types = [SourceType.ACRA, SourceType.WEB_SCRAPE, SourceType.LINKEDIN]

        if include_news:
            source_types.extend([SourceType.NEWSAPI, SourceType.PERPLEXITY])

        if include_financials:
            source_types.extend([SourceType.EODHD])

        query = company_name
        if website:
            query = f"{company_name} site:{website}"

        return await self._registry.search(query, source_types=source_types)

    async def find_funding_news(
        self,
        company_name: str | None = None,
        industry: str | None = None,
        region: str = "Singapore",
    ) -> MCPQueryResult:
        """Find funding news and announcements.

        Args:
            company_name: Specific company to search
            industry: Industry to filter
            region: Geographic region

        Returns:
            Funding-related facts
        """
        query_parts = []
        if company_name:
            query_parts.append(company_name)
        query_parts.append("funding OR series OR raised OR investment")
        if industry:
            query_parts.append(industry)
        if region:
            query_parts.append(region)

        query = " ".join(query_parts)

        return await self._registry.search(
            query,
            source_types=[SourceType.NEWSAPI, SourceType.PERPLEXITY, SourceType.PRESS_RELEASE],
        )

    async def detect_hiring_signals(
        self,
        company_name: str,
    ) -> MCPQueryResult:
        """Detect hiring activity as intent signals.

        Args:
            company_name: Company to analyze

        Returns:
            Hiring-related facts
        """
        return await self._registry.search(
            f"{company_name} hiring OR jobs OR careers",
            source_types=[SourceType.JOB_BOARD, SourceType.LINKEDIN, SourceType.WEB_SCRAPE],
        )

    async def monitor_competitor(
        self,
        competitor_name: str,
        since: datetime | None = None,  # noqa: ARG002
    ) -> MCPQueryResult:
        """Monitor competitor for news and changes.

        Args:
            competitor_name: Competitor to monitor
            since: Only get news after this date

        Returns:
            Competitor-related facts
        """
        return await self._registry.search(
            competitor_name,
            source_types=[
                SourceType.NEWSAPI,
                SourceType.PERPLEXITY,
                SourceType.WEB_SCRAPE,
                SourceType.LINKEDIN,
            ],
        )


# Global singleton instances
_registry_instance: MCPRegistry | None = None
_manager_instance: MCPManager | None = None


def get_mcp_registry() -> MCPRegistry:
    """Get the global MCP registry singleton."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = MCPRegistry()
    return _registry_instance


def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager singleton."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MCPManager(get_mcp_registry())
    return _manager_instance


def reset_mcp_registry() -> None:
    """Reset the global MCP registry (for testing)."""
    global _registry_instance, _manager_instance
    _registry_instance = None
    _manager_instance = None
