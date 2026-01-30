"""MCP Server implementations.

Each server collects evidence-backed facts from a specific data source.
"""

from packages.mcp.src.servers.acra import ACRAMCPServer
from packages.mcp.src.servers.eodhd import EODHDMCPServer
from packages.mcp.src.servers.news import NewsAggregatorMCPServer
from packages.mcp.src.servers.web_scraper import WebScraperMCPServer

__all__ = [
    "ACRAMCPServer",
    "EODHDMCPServer",
    "NewsAggregatorMCPServer",
    "WebScraperMCPServer",
]
