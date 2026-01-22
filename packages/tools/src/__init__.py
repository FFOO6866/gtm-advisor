"""GTM Advisor Tools Package.

Operational tools for real-world data operations.
All tools have explicit access boundaries and audit logging.

Tool Categories:
- Enrichment: Company/contact data enrichment
- Scraping: Web data extraction
- CRM: HubSpot, Pipedrive, Salesforce connectors
- Communication: Email, Slack integrations
"""

from .base import (
    BaseTool,
    ToolAccess,
    ToolResult,
    ToolError,
    ToolRegistry,
)
from .enrichment import (
    CompanyEnrichmentTool,
    ContactEnrichmentTool,
    EmailFinderTool,
)
from .scraping import (
    WebScraperTool,
    LinkedInScraperTool,
    NewsScraperTool,
)
from .crm import (
    HubSpotTool,
    PipedriveTool,
    CRMSyncTool,
)

__all__ = [
    # Base
    "BaseTool",
    "ToolAccess",
    "ToolResult",
    "ToolError",
    "ToolRegistry",
    # Enrichment
    "CompanyEnrichmentTool",
    "ContactEnrichmentTool",
    "EmailFinderTool",
    # Scraping
    "WebScraperTool",
    "LinkedInScraperTool",
    "NewsScraperTool",
    # CRM
    "HubSpotTool",
    "PipedriveTool",
    "CRMSyncTool",
]
