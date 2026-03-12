# Skill: Add a New Data Integration

## When to use
When adding a new external data source (API, database, scraper) to GTM Advisor.

## Locations
- MCP server integrations: `packages/mcp/src/servers/{integration_name}_server.py`
- Direct API integrations: `packages/integrations/{integration_name}/src/client.py`
- LLM providers: `packages/llm/src/{provider}_provider.py`

## Step-by-step

### 1. Choose the integration type
| Type | Use when | Location |
|------|----------|----------|
| MCP server | External data source with structured output | `packages/mcp/src/servers/` |
| Direct API | Simple REST API with Python SDK | `packages/integrations/` |
| LLM provider | AI model provider | `packages/llm/src/` |

### 2. Create the client
```python
"""
{IntegrationName} integration client.
"""
import structlog
from packages.core.src.errors import APIError

logger = structlog.get_logger()

class {IntegrationName}Client:
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def search(self, query: str) -> list[dict]:
        """Search for data."""
        try:
            # API call here
            ...
        except Exception as e:
            raise APIError("{integration_name}", message=str(e)) from e
```

### 3. Add environment variable
Add to `.env.example`:
```bash
{INTEGRATION_NAME}_API_KEY=your-key-here
```

Add to `packages/core/src/config.py`:
```python
{integration_name}_api_key: str | None = Field(default=None, alias="{INTEGRATION_NAME}_API_KEY")
```

### 4. Register in MCP registry (if MCP server)
In `packages/mcp/src/registry.py`, add:
```python
if config.{integration_name}_api_key:
    registry.register({IntegrationName}MCPServer(api_key=config.{integration_name}_api_key))
```

### 5. Test with a unit test (mocked) + integration test (real API)
```python
@pytest.mark.unit
async def test_{integration_name}_client_handles_api_error():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        with pytest.raises(APIError):
            await client.search("test")
```
