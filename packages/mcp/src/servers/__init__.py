"""MCP Server implementations.

Each server collects evidence-backed facts from a specific data source.
"""

# Data providers
from packages.mcp.src.servers.acra import ACRAMCPServer
from packages.mcp.src.servers.dynamics import DynamicsMCPServer
from packages.mcp.src.servers.eodhd import EODHDMCPServer

# CRM integrations
from packages.mcp.src.servers.hubspot import HubSpotMCPServer

# Email services
from packages.mcp.src.servers.mailgun import MailgunMCPServer
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer
from packages.mcp.src.servers.news import NewsAggregatorMCPServer
from packages.mcp.src.servers.salesforce import SalesforceMCPServer
from packages.mcp.src.servers.sendgrid import SendGridMCPServer
from packages.mcp.src.servers.sugarcrm import SugarCRMMCPServer
from packages.mcp.src.servers.web_scraper import WebScraperMCPServer

__all__ = [
    # Data providers
    "ACRAMCPServer",
    "EODHDMCPServer",
    "MarketIntelMCPServer",
    "NewsAggregatorMCPServer",
    "WebScraperMCPServer",
    # CRM integrations
    "DynamicsMCPServer",
    "HubSpotMCPServer",
    "SalesforceMCPServer",
    "SugarCRMMCPServer",
    # Email services
    "MailgunMCPServer",
    "SendGridMCPServer",
]
