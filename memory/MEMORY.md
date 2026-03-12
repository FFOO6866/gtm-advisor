# GTM Advisor - Session Memory

## Project Summary
AI-powered GTM advisory platform for Singapore SMEs. Python 3.12+, FastAPI backend, React dashboard.
PDCA agent framework, A2A via AgentBus pub/sub, MCP Knowledge Web (10+ servers).

## Key Files
- Base agent: `agents/core/src/base_agent.py`
- MCP integration: `agents/core/src/mcp_integration.py`
- Agent bus: `packages/core/src/agent_bus.py`
- Gateway: `services/gateway/src/main.py`

## Frontend Architecture
Full docs in `memory/frontend.md` — covers free/paid tier boundary, routing, localStorage keys, hydration, auth endpoints, demo seed data.

**Quick ref — auth endpoints** (correct):
- `POST /api/v1/auth/login` → `{access_token, refresh_token}`
- `POST /api/v1/auth/register` → `{access_token, refresh_token}`

## Gap Analysis (2026-03-10)
Full gap analysis vs kailash-coc and agentic-os in: `memory/gap_analysis.md`

## Known Gaps
- No database persistence (analysis results in memory)
- Governance is skeleton (auto-approves in demo mode)
- No constraint envelopes / hard budget enforcement
- No observation/anomaly detection for agent runs
- No 3-tier testing strategy
- No structured clarification workflow (ObjectiveClarificationService)
- No COC development tooling (.claude/agents, hooks, skills)
