# GTM Advisor

> AI-Powered Go-To-Market Advisory Platform for Singapore SMEs

<div align="center">

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-purple)

**Transform your GTM strategy with a team of AI agents**

[Live Demo](#) · [Documentation](#architecture) · [Quick Start](#quick-start)

</div>

---

## 🎯 Overview

GTM Advisor is a self-service platform that empowers Singapore-based SMEs and startups with AI-driven go-to-market strategies and lead generation. Instead of expensive consultants, you get a team of 6 specialized AI agents working together to analyze your market, identify opportunities, and generate actionable leads.

### ✨ Key Features

- **🤖 6 Specialized AI Agents** - Each expert in their domain, collaborating via A2A protocol
- **📊 Real Data Integration** - Perplexity AI, NewsAPI, EODHD for actual market intelligence
- **🎯 Qualified Lead Generation** - Real prospects, not generic suggestions
- **📣 Ready-to-Use Campaigns** - Email templates, LinkedIn content, and messaging
- **🔒 PDPA Compliant** - Built for Singapore's data protection requirements
- **💰 PSG Eligible** - Designed for Productivity Solutions Grant consideration

---

## 🧠 The Agent Team

| Agent | Role | Data Sources |
|-------|------|--------------|
| **🎯 GTM Strategist** | Orchestrates strategy, gathers requirements | User context |
| **📊 Market Intelligence** | Market trends, opportunities, threats | Perplexity, NewsAPI, EODHD |
| **🔍 Competitor Analyst** | SWOT analysis, competitive positioning | Perplexity, EODHD |
| **👥 Customer Profiler** | ICP development, buyer personas | Market analysis |
| **🎣 Lead Hunter** | Real prospect identification, scoring | Perplexity, databases |
| **📣 Campaign Architect** | Messaging, content, outreach templates | All insights |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+ (for dashboard)
- API Keys: OpenAI, Perplexity, NewsAPI, EODHD

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/gtm-advisor.git
cd gtm-advisor

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### 2. Install Dependencies

```bash
# Python (using uv)
uv sync

# Dashboard
cd services/dashboard
pnpm install
```

### 3. Run Locally

```bash
# Terminal 1: Backend
uv run uvicorn services.gateway.src.main:app --reload

# Terminal 2: Dashboard
cd services/dashboard
pnpm dev
```

### 4. Or Use Docker

```bash
cd deployment/docker
docker compose up
```

Access the dashboard at `http://localhost:3000`

---

## 🏗 Architecture

GTM Advisor is built on the **Grace Framework** patterns:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Dashboard (React)                         │
│              Aurora UI · Agent Network · Results                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Gateway (FastAPI)                            │
│           Auth · Governance · Rate Limiting · CORS               │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │   GTM   │ │ Market  │ │Competitor│ │Customer │ │  Lead   │
   │Strategist│ │  Intel  │ │ Analyst │ │Profiler │ │ Hunter  │
   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
               ┌─────────┐ ┌─────────┐ ┌─────────┐
               │Perplexity│ │ NewsAPI │ │  EODHD  │
               └─────────┘ └─────────┘ └─────────┘
```

### Four-Layer Architecture

Each agent operates across four layers for reliable, auditable decisions:

| Layer | Purpose | Examples |
|-------|---------|----------|
| **Cognitive (LLM)** | Synthesis, explanation, generation | Market summaries, outreach messages |
| **Analytical (Algorithms)** | Deterministic scoring, calculations | ICP scoring, BANT scoring, lead value |
| **Operational (Tools)** | Data acquisition from external sources | Company enrichment, news search |
| **Governance (Rules)** | Compliance, access control, audit | PDPA checks, rate limiting |

**Why this matters:**
- **Repeatability**: Algorithmic scores are deterministic (same input = same output)
- **Explainability**: Every decision can be traced to its source
- **Cost efficiency**: Algorithms are free; LLM calls only where needed
- **Auditability**: Complete decision trail for compliance

### Core Patterns

- **PDCA Agents** - Self-correcting with confidence thresholds
- **A2A Protocol** - Agents communicate and collaborate
- **Schema-First** - All data models defined as JSON Schema
- **Governance-First** - PDPA compliance at service boundaries
- **Real-Time Updates** - WebSocket for live agent progress

---

## 📁 Project Structure

```
gtm-advisor/
├── packages/
│   ├── core/                 # Types, config, errors
│   ├── llm/                  # LLM provider abstraction
│   ├── governance/           # Rate limiting, PDPA
│   ├── observability/        # Tracing, metrics
│   └── integrations/         # NewsAPI, EODHD, Perplexity
├── agents/
│   ├── core/                 # BaseGTMAgent (PDCA pattern)
│   ├── gtm_strategist/       # Orchestrator agent
│   ├── market_intelligence/  # Market research
│   ├── competitor_analyst/   # Competitive intel
│   ├── customer_profiler/    # ICP & personas
│   ├── lead_hunter/          # Prospect identification
│   └── campaign_architect/   # Messaging & campaigns
├── services/
│   ├── gateway/              # FastAPI backend
│   └── dashboard/            # React frontend
├── schemas/                  # JSON Schema definitions
├── deployment/               # Docker, Kubernetes
├── tests/                    # Test suite
└── docs/                     # Documentation
```

---

## 🔑 Environment Variables

Create a `.env` file with:

```bash
# Required - LLM Providers
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...

# Required - Data Sources
NEWSAPI_API_KEY=...
EODHD_API_KEY=...

# Optional
ANTHROPIC_API_KEY=sk-ant-...
GTM_ENVIRONMENT=development
GTM_ENABLE_GOVERNANCE=true
```

---

## 📖 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agents` | GET | List all agents |
| `/api/v1/agents/{name}/run` | POST | Run specific agent |
| `/api/v1/companies` | POST | Create company profile |
| `/api/v1/analysis/start` | POST | Start full GTM analysis |
| `/api/v1/analysis/{id}/status` | GET | Check analysis status |
| `/api/v1/analysis/{id}/result` | GET | Get analysis results |

---

## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [Getting Started](docs/guides/getting-started.md) | First analysis walkthrough |
| [Agent Development](docs/guides/agent-development.md) | Building new agents |
| [Tool Development](docs/guides/tool-development.md) | Creating external integrations |
| [Gateway API](docs/api/gateway.md) | REST API reference |
| [Agent API](docs/api/agents.md) | Agent interfaces |
| [ADR-0001: Four-Layer Architecture](docs/adr/0001-four-layer-architecture.md) | Architecture decision |

---

## 🛠 Development

```bash
# Run tests
pytest tests/

# Lint
ruff check .
ruff format .

# Type check
mypy packages/ agents/
```

---

## 🎨 Dashboard Features

The dashboard provides a **"Neural Command Center"** experience:

- **Aurora Background** - Animated gradient background
- **Agent Network** - Real-time visualization of agent collaboration
- **Connection Pulses** - See when agents communicate (A2A)
- **Glassmorphic Cards** - Modern, premium UI components
- **Live Status** - Thinking indicators, progress rings
- **Results Panel** - Leads, insights, and campaign templates

---

## 📜 License

MIT License - see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

Built on the [Grace Framework](https://github.com/yourorg/grace) patterns.

UI inspired by [Linear](https://linear.app), [Vercel](https://vercel.com), and [Raycast](https://raycast.com).

---

<div align="center">

**Made with 💜 for Singapore SMEs**

[Report Bug](https://github.com/yourorg/gtm-advisor/issues) · [Request Feature](https://github.com/yourorg/gtm-advisor/issues)

</div>
