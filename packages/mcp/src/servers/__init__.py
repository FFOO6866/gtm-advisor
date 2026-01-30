"""MCP Server implementations.

Each server collects evidence-backed facts from a specific data source.
"""

# Data providers
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

__all__ = [
    # Data providers
    "ACRAMCPServer",
    "EODHDMCPServer",
    "NewsAggregatorMCPServer",
    "WebScraperMCPServer",
    # CRM integrations
    "HubSpotMCPServer",
    "SalesforceMCPServer",
    "DynamicsMCPServer",
    "SugarCRMMCPServer",
    # Email services
    "MailgunMCPServer",
    "SendGridMCPServer",
]
