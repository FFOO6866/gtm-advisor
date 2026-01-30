"""MCP (Model Context Protocol) package.

Provides the data collection layer for the Knowledge Web:
- Base classes for MCP servers
- Registry for managing servers
- Types for evidence-backed facts

MCP Servers are responsible for collecting evidence-backed facts from
various data sources (APIs, web scraping, databases). Every fact must
have full provenance: source URL, timestamp, and confidence score.

Example usage:
    from packages.mcp.src import (
        get_mcp_registry,
        get_mcp_manager,
        EvidencedFact,
        SourceType,
        FactType,
    )

    # Register servers
    registry = get_mcp_registry()
    registry.register(ACRAMCPServer(config))
    registry.register(NewsAPIMCPServer(config))

    # Use manager for high-level operations
    manager = get_mcp_manager()
    result = await manager.research_company("TechCorp Singapore")

    for fact in result.facts:
        print(f"[{fact.confidence:.0%}] {fact.claim}")
        print(f"  Source: {fact.source_name} ({fact.source_url})")
"""

from packages.mcp.src.base import (
    APIBasedMCPServer,
    BaseMCPServer,
    MCPConfigurationError,
    MCPRateLimitError,
    MCPServerError,
    WebScrapingMCPServer,
)
from packages.mcp.src.registry import (
    MCPManager,
    MCPRegistry,
    get_mcp_manager,
    get_mcp_registry,
    reset_mcp_registry,
)
from packages.mcp.src.types import (
    CompetitorAlert,
    EntityReference,
    EntityType,
    EvidencedFact,
    FactType,
    LeadSignal,
    MCPHealthStatus,
    MCPQueryResult,
    MCPServerConfig,
    SignalCategory,
    SourceType,
)

__all__ = [
    # Base classes
    "BaseMCPServer",
    "APIBasedMCPServer",
    "WebScrapingMCPServer",
    # Registry
    "MCPRegistry",
    "MCPManager",
    "get_mcp_registry",
    "get_mcp_manager",
    "reset_mcp_registry",
    # Types
    "EvidencedFact",
    "EntityReference",
    "EntityType",
    "FactType",
    "SourceType",
    "MCPQueryResult",
    "MCPHealthStatus",
    "MCPServerConfig",
    "SignalCategory",
    "LeadSignal",
    "CompetitorAlert",
    # Errors
    "MCPServerError",
    "MCPConfigurationError",
    "MCPRateLimitError",
]
