# GTM Advisor Documentation

> AI-Powered Go-To-Market Advisory Platform for Singapore SMEs

**Version**: 0.1.0 | **Status**: Production MVP | **Python**: >=3.12

## Overview

GTM Advisor is a self-service AI platform that helps Singapore SMEs develop effective go-to-market strategies. It uses 6 specialized AI agents that collaborate to deliver:

- Market research and intelligence
- Competitor analysis (SWOT)
- Customer profiling (ICP development)
- Qualified lead generation
- Campaign planning and messaging

## Architecture

GTM Advisor is built on the **Grace Framework** with a four-layer architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                              │
│                   React Dashboard + WebSocket                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GATEWAY API                                 │
│              FastAPI + Agent Orchestration                       │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   COGNITIVE   │     │  ANALYTICAL   │     │  OPERATIONAL  │
│    (LLM)      │     │ (Algorithms)  │     │   (Tools)     │
│               │     │               │     │               │
│ • Synthesis   │     │ • ICP Scoring │     │ • Enrichment  │
│ • Explanation │     │ • BANT Scoring│     │ • Web Scraping│
│ • Generation  │     │ • Clustering  │     │ • CRM Sync    │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GOVERNANCE                                  │
│        RBAC • Audit • Compliance • Budget Controls               │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### Multi-Agent Collaboration
Six specialized AI agents work together using the PDCA (Plan-Do-Check-Act) methodology:

| Agent | Role | Layer |
|-------|------|-------|
| GTM Strategist | Orchestrates analysis, coordinates team | Cognitive |
| Market Intelligence | Researches market trends and opportunities | Cognitive + Operational |
| Competitor Analyst | Performs SWOT analysis | Cognitive + Operational |
| Customer Profiler | Develops ICPs and buyer personas | Cognitive |
| Lead Hunter | Finds and scores qualified leads | Analytical + Operational |
| Campaign Architect | Creates messaging and campaigns | Cognitive |

### Deterministic Scoring
Lead scoring uses algorithms (not just LLM) for:
- **Repeatability**: Same inputs produce same outputs
- **Explainability**: Clear reasoning for every score
- **Auditability**: Full decision trail

### Real-Time Updates
WebSocket integration provides live progress updates as agents work.

### Governance Built-In
- PDPA compliance checking
- Role-based access control
- Complete audit logging
- Budget controls per agent

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- uv (Python package manager)
- pnpm (Node package manager)

### Installation

```bash
# Clone repository
cd gtm-advisor

# Install Python dependencies
uv sync

# Install dashboard dependencies
cd services/dashboard && pnpm install && cd ../..

# Set environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Required API Keys

```bash
# LLM Providers (at least one required)
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...

# Data Sources
NEWSAPI_API_KEY=...
EODHD_API_KEY=...
```

### Running

```bash
# Terminal 1: Start gateway API
uv run uvicorn services.gateway.src.main:app --reload --port 8000

# Terminal 2: Start dashboard
cd services/dashboard && pnpm dev
```

Open http://localhost:3000 to access the dashboard.

## Documentation Structure

| Section | Description |
|---------|-------------|
| [Guides](guides/) | How-to documentation for developers |
| [API Reference](api/) | Detailed API documentation |
| [Architecture Decisions](adr/) | ADRs explaining key decisions |
| [References](references/) | Standards and specifications |

## Guides

### For Users
- [Getting Started](guides/getting-started.md) - First analysis walkthrough
- [Understanding Results](guides/understanding-results.md) - How to interpret analysis

### For Developers
- [Agent Development](guides/agent-development.md) - Building new agents
- [Tool Development](guides/tool-development.md) - Creating new tools
- [API Integration](guides/api-integration.md) - Connecting external systems

### For Operators
- [Deployment](guides/deployment.md) - Production deployment guide
- [Monitoring](guides/monitoring.md) - Observability and alerts

## API Reference

- [Gateway API](api/gateway.md) - REST API endpoints
- [WebSocket API](api/websocket.md) - Real-time updates
- [Agent API](api/agents.md) - Agent interfaces
- [Types](api/types.md) - Data models

## Architecture Decisions

- [ADR-0001: Four-Layer Architecture](adr/0001-four-layer-architecture.md)
- [ADR-0002: PDCA Pattern for Agents](adr/0002-pdca-pattern.md)
- [ADR-0003: Deterministic Lead Scoring](adr/0003-deterministic-scoring.md)
- [ADR-0004: WebSocket for Real-Time Updates](adr/0004-websocket-updates.md)

## Support

- Issues: https://github.com/your-org/gtm-advisor/issues
- Documentation: This site

## License

Copyright 2024. All rights reserved.
