# Gateway API Reference

The Gateway API provides REST endpoints for interacting with GTM Advisor.

**Base URL**: `http://localhost:8000`

## Authentication

Currently, the API does not require authentication for development. Production deployments should implement JWT authentication.

## Endpoints

### Health Check

#### `GET /health`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

### Root

#### `GET /`

Get API information.

**Response:**
```json
{
  "name": "GTM Advisor API",
  "version": "0.1.0",
  "description": "AI-powered Go-To-Market Advisory Platform",
  "docs": "/docs",
  "health": "/health"
}
```

---

## Agents

### List Agents

#### `GET /api/v1/agents`

List all available agents with their capabilities.

**Response:**
```json
[
  {
    "name": "gtm-strategist",
    "title": "GTM Strategist",
    "description": "Orchestrates your GTM strategy and coordinates the team",
    "status": "idle",
    "capabilities": [
      {"name": "Discovery", "description": "Discovers business context"},
      {"name": "Strategy", "description": "Develops GTM strategy"},
      {"name": "Coordination", "description": "Coordinates other agents"}
    ],
    "avatar": "🎯",
    "color": "#8B5CF6"
  }
]
```

### Get Agent

#### `GET /api/v1/agents/{agent_name}`

Get a specific agent's information.

**Path Parameters:**
- `agent_name` (string): Agent identifier (e.g., `lead-hunter`)

**Response:**
```json
{
  "name": "lead-hunter",
  "title": "Lead Hunter",
  "description": "Finds and qualifies real prospects",
  "status": "idle",
  "capabilities": [
    {"name": "Prospecting", "description": "Finds potential leads"},
    {"name": "Lead Scoring", "description": "Scores leads using algorithms"},
    {"name": "Contact Research", "description": "Enriches contact data"}
  ],
  "avatar": "🎣",
  "color": "#3B82F6"
}
```

### Run Agent

#### `POST /api/v1/agents/{agent_name}/run`

Execute a specific agent with a task.

**Path Parameters:**
- `agent_name` (string): Agent identifier

**Request Body:**
```json
{
  "task": "Find 10 qualified leads in fintech",
  "context": {
    "company_name": "TechCorp SG",
    "industry": "saas",
    "target_industries": ["fintech", "saas"],
    "target_count": 10
  }
}
```

**Response:**
```json
{
  "agent_name": "lead-hunter",
  "status": "completed",
  "result": {
    "qualified_leads": [...],
    "total_found": 15,
    "total_qualified": 10,
    "algorithm_decisions": 30,
    "llm_decisions": 5,
    "determinism_ratio": 0.86
  },
  "confidence": 0.82,
  "iterations": 1
}
```

---

## Analysis

### Start Analysis

#### `POST /api/v1/analysis/start`

Start a full GTM analysis (runs in background).

**Request Body:**
```json
{
  "company_name": "TechCorp SG",
  "description": "B2B SaaS platform for HR automation",
  "industry": "saas",
  "goals": ["10 enterprise customers in Q1", "SGD 500K ARR"],
  "challenges": ["Long sales cycles", "Competition from incumbents"],
  "competitors": ["CompetitorA", "CompetitorB"],
  "target_markets": ["Singapore", "Malaysia"],
  "value_proposition": "Reduce HR admin time by 50%",
  "include_market_research": true,
  "include_competitor_analysis": true,
  "include_customer_profiling": true,
  "include_lead_generation": true,
  "include_campaign_planning": true,
  "lead_count": 10
}
```

**Request Body Schema:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | - | Company name |
| `description` | string | No | "" | Company description |
| `industry` | string | No | "other" | Industry vertical |
| `goals` | string[] | No | [] | Business goals |
| `challenges` | string[] | No | [] | Current challenges |
| `competitors` | string[] | No | [] | Known competitors |
| `target_markets` | string[] | No | ["Singapore"] | Target markets |
| `value_proposition` | string | No | null | Value proposition |
| `include_market_research` | boolean | No | true | Include market research |
| `include_competitor_analysis` | boolean | No | true | Include competitor analysis |
| `include_customer_profiling` | boolean | No | true | Include customer profiling |
| `include_lead_generation` | boolean | No | true | Include lead generation |
| `include_campaign_planning` | boolean | No | true | Include campaign planning |
| `lead_count` | integer | No | 10 | Number of leads to find (1-50) |

**Industry Values:**
- `fintech`
- `saas`
- `ecommerce`
- `healthtech`
- `edtech`
- `proptech`
- `logistics`
- `manufacturing`
- `professional_services`
- `other`

**Response:**
```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "progress": 0.0
}
```

### Get Analysis Status

#### `GET /api/v1/analysis/{analysis_id}/status`

Check the status of a running analysis.

**Path Parameters:**
- `analysis_id` (UUID): Analysis identifier

**Response:**
```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 0.4,
  "current_agent": "customer-profiler",
  "completed_agents": ["market-intelligence", "competitor-analyst"],
  "error": null
}
```

**Status Values:**
- `pending`: Analysis queued
- `running`: Analysis in progress
- `completed`: Analysis finished successfully
- `failed`: Analysis encountered an error

### Get Analysis Result

#### `GET /api/v1/analysis/{analysis_id}/result`

Get the result of a completed analysis.

**Path Parameters:**
- `analysis_id` (UUID): Analysis identifier

**Response:**
```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "company_id": "...",
    "market_insights": [...],
    "competitor_analysis": [...],
    "customer_personas": [...],
    "leads": [...],
    "campaign_brief": {...},
    "executive_summary": "GTM analysis completed for TechCorp SG...",
    "key_recommendations": [...],
    "agents_used": ["market-intelligence", "competitor-analyst", "customer-profiler", "lead-hunter", "campaign-architect"],
    "total_confidence": 0.82,
    "processing_time_seconds": 45.3
  },
  "processing_time_seconds": 45.3
}
```

### Quick Analysis

#### `POST /api/v1/analysis/quick`

Run a synchronous quick analysis (for testing).

**Request Body:** Same as `POST /api/v1/analysis/start`

**Response:** Same as `GET /api/v1/analysis/{analysis_id}/result`

> **Note:** Quick analysis only runs lead generation and is limited to 5 leads. Use for testing only.

---

## Companies

### Create Company

#### `POST /api/v1/companies`

Create a new company profile.

**Request Body:**
```json
{
  "name": "TechCorp SG",
  "description": "B2B SaaS platform",
  "website": "https://techcorp.sg",
  "industry": "saas",
  "stage": "series_a",
  "country": "Singapore",
  "city": "Singapore",
  "products": ["HR Platform", "Payroll"],
  "target_markets": ["Singapore", "Malaysia"],
  "value_proposition": "Reduce HR admin by 50%",
  "current_challenges": ["Long sales cycles"],
  "goals": ["10 customers in Q1"],
  "competitors": ["CompetitorA"]
}
```

**Response:** Created company profile with `id`.

### List Companies

#### `GET /api/v1/companies`

List all company profiles.

**Response:**
```json
[
  {
    "id": "...",
    "name": "TechCorp SG",
    "industry": "saas",
    ...
  }
]
```

### Get Company

#### `GET /api/v1/companies/{company_id}`

Get a specific company profile.

### Update Company

#### `PATCH /api/v1/companies/{company_id}`

Update a company profile (partial update).

### Delete Company

#### `DELETE /api/v1/companies/{company_id}`

Delete a company profile.

---

## WebSocket API

### Analysis Updates

#### `WS /ws/analysis/{analysis_id}`

Connect to receive real-time analysis updates.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/analysis/{analysis_id}');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message);
};

// Keep alive
setInterval(() => ws.send('ping'), 30000);
```

**Message Types:**

##### `analysis_started`
```json
{
  "type": "analysis_started",
  "message": "Starting GTM analysis for TechCorp SG",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

##### `agent_started`
```json
{
  "type": "agent_started",
  "agentId": "market-intelligence",
  "agentName": "Market Intelligence",
  "status": "thinking",
  "message": "Researching fintech market in Singapore...",
  "timestamp": "2024-01-15T10:30:01Z"
}
```

##### `agent_completed`
```json
{
  "type": "agent_completed",
  "agentId": "market-intelligence",
  "agentName": "Market Intelligence",
  "status": "complete",
  "progress": 0.2,
  "message": "Found 5 market insights",
  "result": {
    "insights_count": 5
  },
  "timestamp": "2024-01-15T10:30:15Z"
}
```

##### `analysis_completed`
```json
{
  "type": "analysis_completed",
  "message": "Analysis complete for TechCorp SG",
  "result": {
    "leads_count": 10,
    "insights_count": 5,
    "competitors_count": 3,
    "personas_count": 2,
    "has_campaign": true,
    "processing_time_seconds": 45.3,
    "confidence": 0.82,
    "determinism_ratio": 0.75,
    "algorithm_decisions": 30,
    "llm_decisions": 10,
    "tool_calls": 15
  },
  "timestamp": "2024-01-15T10:31:00Z"
}
```

##### `error`
```json
{
  "type": "error",
  "error": "LLM API rate limit exceeded",
  "message": "Analysis failed: LLM API rate limit exceeded",
  "timestamp": "2024-01-15T10:30:30Z"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "detail": "Additional details (optional)"
}
```

### Common Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 400 | `ValidationError` | Invalid request body |
| 404 | `NotFound` | Resource not found |
| 422 | `UnprocessableEntity` | Invalid data format |
| 429 | `RateLimitExceeded` | Too many requests |
| 500 | `InternalServerError` | Server error |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Analysis start | 10/hour |
| Agent run | 60/minute |
| Status check | 120/minute |
| WebSocket | 10 connections |

---

## SDK Examples

### Python

```python
import httpx

async def start_analysis():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/analysis/start",
            json={
                "company_name": "TechCorp SG",
                "industry": "saas",
                "description": "B2B SaaS platform",
            }
        )
        return response.json()
```

### TypeScript

```typescript
const startAnalysis = async (request: AnalysisRequest) => {
  const response = await fetch('http://localhost:8000/api/v1/analysis/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return response.json();
};
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/analysis/start \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "TechCorp SG",
    "industry": "saas",
    "description": "B2B SaaS platform"
  }'
```

---

## Related Documentation

- [WebSocket API](websocket.md) - Detailed WebSocket documentation
- [Agent API](agents.md) - Agent interfaces
- [Types Reference](types.md) - Data models
