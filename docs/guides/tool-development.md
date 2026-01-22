# Tool Development Guide

This guide explains how to develop tools for the GTM Advisor operational layer.

## Overview

Tools in GTM Advisor provide the **Operational Layer** - they interface with external systems to acquire real data. Unlike LLM-generated content, tool outputs come from actual data sources.

## Tool Architecture

### Base Class

All tools inherit from `BaseTool`:

```python
from packages.tools.src.base import BaseTool, ToolCategory, ToolAccess, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    category = ToolCategory.ENRICHMENT  # or SCRAPING, CRM, ANALYTICS
    required_access = ToolAccess.READ   # or WRITE, DELETE, ADMIN

    async def _execute(self, **kwargs) -> ToolResult:
        # Implementation
        pass
```

### Tool Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| `ENRICHMENT` | Data enrichment | Company info, contact data |
| `SCRAPING` | Web data extraction | News, company websites |
| `CRM` | CRM integration | HubSpot, Salesforce |
| `ANALYTICS` | Data analysis | Clustering, scoring |
| `COMMUNICATION` | Outreach | Email, LinkedIn |

### Access Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| `READ` | Read-only access | Data retrieval |
| `WRITE` | Create/update | CRM sync, lead creation |
| `DELETE` | Remove data | Lead cleanup |
| `ADMIN` | Full access | System administration |

## Available Tools

### Enrichment Tools

#### CompanyEnrichmentTool

Enriches company data from external sources.

```python
from packages.tools.src.enrichment import CompanyEnrichmentTool

tool = CompanyEnrichmentTool()
result = await tool.execute(
    company_name="TechCorp SG",
    country="Singapore"
)

# Result
{
    "company_name": "TechCorp SG",
    "industry": "saas",
    "employee_count": 50,
    "founded_year": 2020,
    "website": "https://techcorp.sg",
    "linkedin_url": "https://linkedin.com/company/techcorp-sg",
    "description": "B2B SaaS platform...",
    "headquarters": "Singapore",
    "funding_stage": "Series A"
}
```

**Supported Providers:**
- Clearbit (default)
- Apollo
- Mock (for testing)

**Configuration:**
```python
tool = CompanyEnrichmentTool(
    provider="clearbit",  # or "apollo", "mock"
    api_key=os.getenv("CLEARBIT_API_KEY")
)
```

#### ContactEnrichmentTool

Finds contact information for leads.

```python
from packages.tools.src.enrichment import ContactEnrichmentTool

tool = ContactEnrichmentTool()
result = await tool.execute(
    company_name="TechCorp SG",
    role="CEO"
)

# Result
{
    "name": "John Doe",
    "title": "Chief Executive Officer",
    "email": "john@techcorp.sg",
    "linkedin_url": "https://linkedin.com/in/johndoe",
    "phone": "+65 9123 4567"
}
```

#### EmailFinderTool

Finds and validates email addresses.

```python
from packages.tools.src.enrichment import EmailFinderTool

tool = EmailFinderTool()
result = await tool.execute(
    first_name="John",
    last_name="Doe",
    company_domain="techcorp.sg"
)

# Result
{
    "email": "john.doe@techcorp.sg",
    "confidence": 0.95,
    "verification_status": "valid"
}
```

### Scraping Tools

#### WebScraperTool

Extracts structured data from websites.

```python
from packages.tools.src.scraping import WebScraperTool

tool = WebScraperTool()
result = await tool.execute(
    url="https://techcorp.sg/about",
    extract=["company_description", "team_size", "locations"]
)

# Result
{
    "company_description": "TechCorp is a leading...",
    "team_size": "50-100 employees",
    "locations": ["Singapore", "Malaysia"]
}
```

**Features:**
- Respects `robots.txt`
- Rate limited (10 requests/minute default)
- Caches responses
- Handles JavaScript rendering (optional)

#### NewsScraperTool

Gathers recent news about companies.

```python
from packages.tools.src.scraping import NewsScraperTool

tool = NewsScraperTool()
result = await tool.execute(
    query="TechCorp SG funding",
    max_results=5,
    days_back=30
)

# Result
{
    "articles": [
        {
            "title": "TechCorp SG Raises $10M Series A",
            "source": "Tech in Asia",
            "date": "2024-01-10",
            "url": "https://...",
            "summary": "Singapore-based TechCorp..."
        }
    ],
    "total_found": 3
}
```

**Data Sources:**
- NewsAPI (primary)
- Google News (fallback)

#### LinkedInScraperTool

Extracts public LinkedIn data.

```python
from packages.tools.src.scraping import LinkedInScraperTool

tool = LinkedInScraperTool()
result = await tool.execute(
    company_url="https://linkedin.com/company/techcorp-sg"
)

# Result
{
    "name": "TechCorp SG",
    "followers": 5000,
    "employee_count": "51-200",
    "industry": "Software Development",
    "headquarters": "Singapore",
    "recent_posts": [...]
}
```

> **Note**: LinkedIn scraping must comply with terms of service. Use responsibly.

### CRM Tools

#### HubSpotTool

Integrates with HubSpot CRM.

```python
from packages.tools.src.crm import HubSpotTool

tool = HubSpotTool()

# Search for contacts
result = await tool.execute(
    operation="search_contacts",
    query={"company": "TechCorp SG"}
)

# Create a contact
result = await tool.execute(
    operation="create_contact",
    data={
        "email": "john@techcorp.sg",
        "firstname": "John",
        "lastname": "Doe",
        "company": "TechCorp SG"
    }
)

# Create a deal
result = await tool.execute(
    operation="create_deal",
    data={
        "dealname": "TechCorp SG - Enterprise",
        "amount": 50000,
        "pipeline": "default",
        "dealstage": "appointmentscheduled"
    }
)
```

**Supported Operations:**
- `search_contacts`
- `get_contact`
- `create_contact`
- `update_contact`
- `search_companies`
- `create_company`
- `create_deal`
- `update_deal`

#### PipedriveTool

Integrates with Pipedrive CRM.

```python
from packages.tools.src.crm import PipedriveTool

tool = PipedriveTool()

# Search persons
result = await tool.execute(
    operation="search_persons",
    query="john@techcorp.sg"
)

# Create a person
result = await tool.execute(
    operation="create_person",
    data={
        "name": "John Doe",
        "email": "john@techcorp.sg",
        "org_id": 12345
    }
)
```

#### CRMSyncTool

Unified CRM interface (abstracts HubSpot/Pipedrive/Salesforce).

```python
from packages.tools.src.crm import CRMSyncTool

tool = CRMSyncTool(provider="hubspot")  # or "pipedrive", "salesforce"

# Sync a lead
result = await tool.execute(
    operation="sync_lead",
    lead={
        "company_name": "TechCorp SG",
        "contact_name": "John Doe",
        "email": "john@techcorp.sg",
        "fit_score": 0.85
    }
)
```

## Creating a New Tool

### Step 1: Define the Tool

```python
# packages/tools/src/my_tool.py

from typing import Any
from .base import BaseTool, ToolCategory, ToolAccess, ToolResult, RateLimitConfig

class MyCustomTool(BaseTool):
    """Custom tool for X integration.

    This tool provides Y functionality for Z use case.

    Example:
        ```python
        tool = MyCustomTool(api_key="...")
        result = await tool.execute(param1="value1")
        print(result.result)
        ```
    """

    name = "my_custom_tool"
    description = "Provides X functionality"
    category = ToolCategory.ENRICHMENT
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_limit=10,
    )

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self._api_key = api_key or os.getenv("MY_TOOL_API_KEY")
        if not self._api_key:
            raise ValueError("API key required for MyCustomTool")

    async def _execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool operation.

        Args:
            param1: Description of param1
            param2: Description of param2

        Returns:
            ToolResult with operation outcome
        """
        param1 = kwargs.get("param1")
        if not param1:
            return ToolResult(
                success=False,
                error="param1 is required",
            )

        try:
            # Call external API
            response = await self._call_api(param1)

            return ToolResult(
                success=True,
                result=response,
                metadata={
                    "source": "my_api",
                    "version": "v1",
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    async def _call_api(self, param: str) -> dict:
        """Call the external API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.example.com/v1/resource/{param}",
                headers={"Authorization": f"Bearer {self._api_key}"}
            )
            response.raise_for_status()
            return response.json()
```

### Step 2: Register the Tool

```python
# packages/tools/src/__init__.py

from .my_tool import MyCustomTool

__all__ = [
    # ... existing exports
    "MyCustomTool",
]
```

### Step 3: Use in Agent

```python
# In your agent
class MyAgent(ToolEmpoweredAgent[MyResult]):
    def __init__(self):
        super().__init__(...)
        self._register_tool(MyCustomTool())

    async def _do(self, plan: dict) -> MyResult:
        # Use the tool
        result = await self.use_tool("my_custom_tool", param1="value")

        if not result.success:
            self._log("Tool failed", error=result.error)
            # Handle gracefully

        return MyResult(data=result.result)
```

## Testing Tools

### Unit Tests

```python
# tests/unit/tools/test_my_tool.py

import pytest
from packages.tools.src.my_tool import MyCustomTool

@pytest.fixture
def tool():
    return MyCustomTool(api_key="test-key")

class TestMyCustomTool:
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mocker):
        # Mock external API
        mocker.patch.object(
            tool,
            "_call_api",
            return_value={"data": "result"}
        )

        result = await tool.execute(param1="test")

        assert result.success
        assert result.result == {"data": "result"}

    @pytest.mark.asyncio
    async def test_execute_missing_param(self, tool):
        result = await tool.execute()

        assert not result.success
        assert "param1 is required" in result.error

    @pytest.mark.asyncio
    async def test_execute_api_error(self, tool, mocker):
        mocker.patch.object(
            tool,
            "_call_api",
            side_effect=Exception("API Error")
        )

        result = await tool.execute(param1="test")

        assert not result.success
        assert "API Error" in result.error
```

### Integration Tests

```python
# tests/integration/tools/test_my_tool_integration.py

import pytest
import os

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("MY_TOOL_API_KEY"),
    reason="API key not configured"
)
class TestMyCustomToolIntegration:
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        tool = MyCustomTool()
        result = await tool.execute(param1="real-value")

        assert result.success
        assert result.result is not None
```

## Best Practices

### 1. Always Return ToolResult

```python
async def _execute(self, **kwargs) -> ToolResult:
    # Good: Always return ToolResult
    if not input_valid:
        return ToolResult(success=False, error="Invalid input")

    result = await self._do_work()
    return ToolResult(success=True, result=result)

    # Bad: Raising exceptions
    # raise ValueError("Invalid input")  # Don't do this
```

### 2. Implement Rate Limiting

```python
class MyTool(BaseTool):
    rate_limit = RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_limit=10,
    )
```

### 3. Handle Failures Gracefully

```python
async def _execute(self, **kwargs) -> ToolResult:
    try:
        result = await self._call_api()
        return ToolResult(success=True, result=result)
    except httpx.HTTPStatusError as e:
        return ToolResult(
            success=False,
            error=f"API returned {e.response.status_code}",
            metadata={"status_code": e.response.status_code}
        )
    except httpx.TimeoutException:
        return ToolResult(
            success=False,
            error="Request timed out",
            metadata={"timeout": True}
        )
```

### 4. Log for Observability

```python
async def _execute(self, **kwargs) -> ToolResult:
    self._log("Starting API call", params=kwargs)

    start = time.time()
    result = await self._call_api()
    elapsed = time.time() - start

    self._log(
        "API call completed",
        elapsed_ms=elapsed * 1000,
        result_size=len(result)
    )

    return ToolResult(success=True, result=result)
```

### 5. Validate Inputs

```python
async def _execute(self, **kwargs) -> ToolResult:
    # Validate required parameters
    company_name = kwargs.get("company_name")
    if not company_name:
        return ToolResult(
            success=False,
            error="company_name is required"
        )

    # Validate format
    if len(company_name) > 200:
        return ToolResult(
            success=False,
            error="company_name exceeds maximum length"
        )

    # Proceed with execution
    ...
```

### 6. Use Caching When Appropriate

```python
from functools import lru_cache

class MyTool(BaseTool):
    @lru_cache(maxsize=100)
    async def _cached_api_call(self, param: str) -> dict:
        """Cache expensive API calls."""
        return await self._call_api(param)
```

## Configuration

### Environment Variables

```bash
# Enrichment
CLEARBIT_API_KEY=...
APOLLO_API_KEY=...

# CRM
HUBSPOT_API_KEY=...
PIPEDRIVE_API_KEY=...

# News
NEWSAPI_API_KEY=...

# Rate Limits (optional overrides)
TOOL_RATE_LIMIT_PER_MINUTE=60
TOOL_RATE_LIMIT_PER_HOUR=1000
```

### Runtime Configuration

```python
tool = MyTool(
    api_key="custom-key",
    timeout=30,
    max_retries=3,
)
```

## Related Documentation

- [Agent Development Guide](agent-development.md)
- [Algorithm API Reference](../api/algorithms.md)
- [Governance Guide](governance.md)
- [ADR-0001: Four-Layer Architecture](../adr/0001-four-layer-architecture.md)
