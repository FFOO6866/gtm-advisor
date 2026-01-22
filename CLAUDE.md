# GTM Advisor

> AI-Powered Go-To-Market Advisory Platform for Singapore SMEs

**Version**: 0.1.0 | **Status**: MVP | **Python**: >=3.12

## Project Overview

GTM Advisor is a self-service agentic AI platform that provides go-to-market strategies and lead generation for Singapore SMEs. Built on Grace Framework patterns with 6 specialized AI agents that collaborate via A2A protocol.

## Architecture: Agent Team

```
User Input → GTM Strategist → [Market Intel, Competitor, Customer, Leads, Campaign] → Results
```

| Agent | Purpose | Data Sources |
|-------|---------|--------------|
| **GTM Strategist** | Orchestrates, gathers requirements | User context |
| **Market Intelligence** | Market trends, opportunities | Perplexity, NewsAPI, EODHD |
| **Competitor Analyst** | SWOT, positioning | Perplexity, EODHD |
| **Customer Profiler** | ICP, personas | Analysis synthesis |
| **Lead Hunter** | Real prospect identification | Perplexity, databases |
| **Campaign Architect** | Messaging, templates | All insights |

## Key Directories

| Directory | Purpose | When to Modify |
|-----------|---------|----------------|
| `packages/core/` | Types, config, errors | Adding new types |
| `packages/llm/` | LLM provider abstraction | Adding providers |
| `packages/integrations/` | External data sources | Adding data sources |
| `agents/core/` | BaseGTMAgent (PDCA) | Agent framework changes |
| `agents/*/` | Domain-specific agents | Agent capabilities |
| `services/gateway/` | FastAPI backend | API endpoints |
| `services/dashboard/` | React frontend | UI changes |
| `schemas/` | JSON Schema definitions | Data models |

## Agent Development

All agents MUST:
1. Inherit from `BaseGTMAgent`
2. Implement PDCA methods: `_plan()`, `_do()`, `_check()`, `_act()`
3. Use real data sources (not just LLM generation)
4. Include confidence scoring

```python
from agents.core.src.base_agent import BaseGTMAgent

class MyAgent(BaseGTMAgent[ResultType]):
    async def _plan(self, task: str, context: dict) -> dict:
        """Plan execution strategy."""
        pass

    async def _do(self, plan: dict, context: dict) -> ResultType:
        """Execute plan, use real data sources."""
        pass

    async def _check(self, result: ResultType) -> float:
        """Return confidence 0-1."""
        pass

    async def _act(self, result: ResultType, confidence: float) -> ResultType:
        """Adjust if needed, return final."""
        pass
```

## Naming Conventions

| Context | Convention | Example |
|---------|------------|---------|
| Python variables | snake_case | `lead_score` |
| Python classes | PascalCase | `LeadHunterAgent` |
| API fields | camelCase | `fitScore` |
| Agent names | kebab-case | `lead-hunter` |
| Directories | snake_case | `market_intelligence/` |

## Data Sources

| Source | Purpose | Package |
|--------|---------|---------|
| **Perplexity** | Real-time web research | `packages/llm/src/perplexity_provider.py` |
| **NewsAPI** | Market news, trends | `packages/integrations/newsapi/` |
| **EODHD** | Financial data, indicators | `packages/integrations/eodhd/` |
| **OpenAI** | General LLM, structured outputs | `packages/llm/src/openai_provider.py` |

## Common Commands

```bash
# Development
uv sync                              # Install Python dependencies
cd services/dashboard && pnpm install # Install Node dependencies

# Run locally
uv run uvicorn services.gateway.src.main:app --reload
cd services/dashboard && pnpm dev

# Docker
cd deployment/docker && docker compose up

# Testing
pytest tests/
ruff check . && ruff format .
```

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
NEWSAPI_API_KEY=...
EODHD_API_KEY=...

# Optional
ANTHROPIC_API_KEY=sk-ant-...
GTM_ENVIRONMENT=development
GTM_ENABLE_GOVERNANCE=true
```

## Dashboard UI

The dashboard uses:
- **React 18** with TypeScript
- **Framer Motion** for animations
- **Tailwind CSS** with custom theme
- **Glassmorphism** card design
- **Aurora background** gradient animation

Key components:
- `AgentNetwork.tsx` - A2A visualization
- `ConversationPanel.tsx` - Chat interface
- `ResultsPanel.tsx` - Analysis results
- `OnboardingModal.tsx` - Company input

## Pitfalls to Avoid

| Pitfall | Solution |
|---------|----------|
| Generic LLM responses | Use Perplexity/NewsAPI for real data |
| No confidence scoring | Always implement `_check()` properly |
| Missing PDPA compliance | Enable governance in production |
| Hardcoded company data | Use actual search/research |
| UI not showing agent activity | Check AgentNetwork connections |

## Singapore Market Context

When developing, remember:
- Target users are SMEs (10-200 employees)
- PSG grant eligibility is a selling point
- PDPA compliance is mandatory
- Focus on fintech, SaaS, and tech verticals
- Singapore as APAC hub for regional expansion
