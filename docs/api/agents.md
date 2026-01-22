# Agent API Reference

This document provides complete API reference for all GTM Advisor agents.

## Agent Overview

| Agent | Purpose | Min Confidence | Layers Used |
|-------|---------|----------------|-------------|
| GTM Strategist | Orchestrates analysis | 0.80 | Cognitive |
| Market Intelligence | Market research | 0.75 | Cognitive, Operational |
| Competitor Analyst | SWOT analysis | 0.75 | Cognitive, Operational |
| Customer Profiler | ICP development | 0.75 | Cognitive |
| Lead Hunter | Lead scoring | 0.70 | All four layers |
| Campaign Architect | Campaign planning | 0.75 | Cognitive |

---

## GTM Strategist Agent

**Module**: `agents.gtm_strategist.src`

The orchestrator agent that coordinates analysis and communicates with users.

### Class: `GTMStrategistAgent`

```python
from agents.gtm_strategist.src import GTMStrategistAgent

agent = GTMStrategistAgent(min_confidence=0.80)
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_confidence` | `float` | `0.80` | Minimum confidence threshold for results |

#### Methods

##### `run(task: str, context: dict) -> StrategyResult`

Execute the strategist agent.

**Parameters:**
- `task` (str): Task description (e.g., "Develop GTM strategy")
- `context` (dict): Context including:
  - `company_name` (str): Company name
  - `industry` (str): Industry vertical
  - `description` (str): Company description
  - `goals` (list[str]): Business goals
  - `competitors` (list[str]): Known competitors

**Returns:** `StrategyResult`

**Example:**
```python
result = await agent.run(
    "Develop GTM strategy for B2B SaaS launch",
    context={
        "company_name": "TechCorp SG",
        "industry": "saas",
        "description": "HR automation platform for SMEs",
        "goals": ["10 enterprise customers in Q1"],
    }
)
```

#### Result Type: `StrategyResult`

| Field | Type | Description |
|-------|------|-------------|
| `executive_summary` | `str` | High-level strategy summary |
| `key_recommendations` | `list[str]` | Top actionable recommendations |
| `next_steps` | `list[str]` | Immediate next actions |
| `confidence` | `float` | Result confidence (0-1) |

---

## Market Intelligence Agent

**Module**: `agents.market_intelligence.src`

Researches market trends, opportunities, and threats using real data sources.

### Class: `MarketIntelligenceAgent`

```python
from agents.market_intelligence.src import MarketIntelligenceAgent

agent = MarketIntelligenceAgent(min_confidence=0.75)
```

#### Data Sources

- **NewsAPI**: Recent market news and trends
- **EODHD**: Economic indicators
- **Perplexity AI**: Search-augmented research

#### Methods

##### `run(task: str, context: dict) -> MarketIntelligenceResult`

Execute market research.

**Parameters:**
- `task` (str): Research task
- `context` (dict): Context including company and industry info

**Returns:** `MarketIntelligenceResult`

**Example:**
```python
result = await agent.run(
    "Research fintech market trends in Singapore",
    context={
        "company_name": "PayTech SG",
        "industry": "fintech",
        "target_markets": ["Singapore", "Malaysia"],
    }
)
```

#### Result Type: `MarketIntelligenceResult`

| Field | Type | Description |
|-------|------|-------------|
| `summary` | `str` | Market research summary |
| `insights` | `list[MarketInsight]` | Detailed market insights |
| `trends` | `list[str]` | Identified market trends |
| `opportunities` | `list[str]` | Market opportunities |
| `threats` | `list[str]` | Market threats |
| `sources` | `list[str]` | Data sources used |
| `confidence` | `float` | Result confidence (0-1) |

---

## Competitor Analyst Agent

**Module**: `agents.competitor_analyst.src`

Performs competitive analysis including SWOT framework.

### Class: `CompetitorAnalystAgent`

```python
from agents.competitor_analyst.src import CompetitorAnalystAgent

agent = CompetitorAnalystAgent(min_confidence=0.75)
```

#### Methods

##### `run(task: str, context: dict) -> CompetitorAnalysisResult`

Execute competitor analysis.

**Parameters:**
- `task` (str): Analysis task
- `context` (dict): Context including:
  - `known_competitors` (list[str]): Competitor names to analyze

**Returns:** `CompetitorAnalysisResult`

**Example:**
```python
result = await agent.run(
    "Analyze top 3 competitors",
    context={
        "company_name": "TechCorp SG",
        "industry": "saas",
        "known_competitors": ["CompetitorA", "CompetitorB", "CompetitorC"],
    }
)
```

#### Result Type: `CompetitorAnalysisResult`

| Field | Type | Description |
|-------|------|-------------|
| `competitors` | `list[CompetitorAnalysis]` | Individual competitor analyses |
| `positioning_recommendations` | `list[str]` | Positioning suggestions |
| `competitive_advantages` | `list[str]` | Your advantages |
| `confidence` | `float` | Result confidence (0-1) |

#### Nested Type: `CompetitorAnalysis`

| Field | Type | Description |
|-------|------|-------------|
| `competitor_name` | `str` | Competitor name |
| `strengths` | `list[str]` | SWOT strengths |
| `weaknesses` | `list[str]` | SWOT weaknesses |
| `opportunities` | `list[str]` | SWOT opportunities |
| `threats` | `list[str]` | SWOT threats |
| `products` | `list[str]` | Product offerings |
| `positioning` | `str` | Market positioning |

---

## Customer Profiler Agent

**Module**: `agents.customer_profiler.src`

Develops Ideal Customer Profiles (ICPs) and buyer personas.

### Class: `CustomerProfilerAgent`

```python
from agents.customer_profiler.src import CustomerProfilerAgent

agent = CustomerProfilerAgent(min_confidence=0.75)
```

#### Methods

##### `run(task: str, context: dict) -> CustomerProfileResult`

Create customer profiles.

**Parameters:**
- `task` (str): Profiling task
- `context` (dict): Company and product information

**Returns:** `CustomerProfileResult`

**Example:**
```python
result = await agent.run(
    "Create ICPs for enterprise HR software",
    context={
        "company_name": "HRTech SG",
        "industry": "saas",
        "description": "HR automation for enterprises",
        "value_proposition": "Reduce HR admin time by 50%",
    }
)
```

#### Result Type: `CustomerProfileResult`

| Field | Type | Description |
|-------|------|-------------|
| `personas` | `list[CustomerPersona]` | Buyer personas |
| `icp_summary` | `str` | ICP summary |
| `targeting_recommendations` | `list[str]` | Targeting suggestions |
| `confidence` | `float` | Result confidence (0-1) |

#### Nested Type: `CustomerPersona`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Persona name (e.g., "Tech-Savvy CFO") |
| `role` | `str` | Job role |
| `company_size` | `str` | Target company size |
| `industries` | `list[str]` | Target industries |
| `goals` | `list[str]` | Business goals |
| `challenges` | `list[str]` | Key challenges |
| `pain_points` | `list[str]` | Pain points |
| `preferred_channels` | `list[str]` | Communication channels |

---

## Lead Hunter Agent

**Module**: `agents.lead_hunter.src`

Finds and scores qualified leads using the four-layer architecture.

### Class: `LeadHunterAgent`

```python
from agents.lead_hunter.src import LeadHunterAgent

agent = LeadHunterAgent(min_confidence=0.70)
```

#### Architecture Layers

1. **Cognitive (LLM)**: Lead explanation, outreach suggestions
2. **Analytical (Algorithms)**: ICP scoring, BANT scoring, value calculation
3. **Operational (Tools)**: Company enrichment, contact lookup
4. **Governance**: PDPA compliance, access control

#### Methods

##### `run(task: str, context: dict) -> LeadHunterResult`

Find and score leads.

**Parameters:**
- `task` (str): Lead generation task
- `context` (dict): Context including:
  - `target_industries` (list[str]): Industries to target
  - `target_count` (int): Number of leads to find
  - `icp_criteria` (dict): ICP matching criteria

**Returns:** `LeadHunterResult`

**Example:**
```python
result = await agent.run(
    "Find 10 qualified fintech leads in Singapore",
    context={
        "company_name": "TechCorp SG",
        "target_industries": ["fintech", "saas"],
        "target_count": 10,
        "value_proposition": "Reduce costs by 40%",
    }
)
```

#### Result Type: `LeadHunterResult`

| Field | Type | Description |
|-------|------|-------------|
| `qualified_leads` | `list[LeadProfile]` | Scored and qualified leads |
| `total_found` | `int` | Total leads found |
| `total_qualified` | `int` | Leads meeting threshold |
| `algorithm_decisions` | `int` | Algorithmic decisions made |
| `llm_decisions` | `int` | LLM decisions made |
| `tool_calls` | `int` | Tool calls made |
| `determinism_ratio` | `float` | Algorithm/total ratio |
| `confidence` | `float` | Result confidence (0-1) |

#### Nested Type: `LeadProfile`

| Field | Type | Description |
|-------|------|-------------|
| `company_name` | `str` | Company name |
| `contact_name` | `str | None` | Contact person name |
| `contact_title` | `str | None` | Contact job title |
| `contact_email` | `str | None` | Contact email |
| `industry` | `str` | Company industry |
| `employee_count` | `int | None` | Company size |
| `location` | `str | None` | Location |
| `website` | `str | None` | Company website |
| `fit_score` | `float` | ICP fit score (0-1) |
| `intent_score` | `float` | Buying intent score (0-1) |
| `overall_score` | `float` | Combined score (0-1) |
| `pain_points` | `list[str]` | Identified pain points |
| `trigger_events` | `list[str]` | Recent trigger events |
| `recommended_approach` | `str | None` | Suggested outreach |

---

## Campaign Architect Agent

**Module**: `agents.campaign_architect.src`

Creates marketing campaigns and messaging.

### Class: `CampaignArchitectAgent`

```python
from agents.campaign_architect.src import CampaignArchitectAgent

agent = CampaignArchitectAgent(min_confidence=0.75)
```

#### Methods

##### `run(task: str, context: dict) -> CampaignResult`

Create campaign materials.

**Parameters:**
- `task` (str): Campaign creation task
- `context` (dict): Context including:
  - `leads` (list[dict]): Target leads
  - `personas` (list[dict]): Target personas
  - `value_proposition` (str): Value proposition

**Returns:** `CampaignResult`

**Example:**
```python
result = await agent.run(
    "Create cold outreach campaign",
    context={
        "company_name": "TechCorp SG",
        "leads": [{"company_name": "Target Inc", "industry": "fintech"}],
        "personas": [{"name": "Tech CFO", "role": "CFO"}],
        "value_proposition": "Reduce costs by 40%",
    }
)
```

#### Result Type: `CampaignResult`

| Field | Type | Description |
|-------|------|-------------|
| `campaign_brief` | `CampaignBrief` | Full campaign brief |
| `email_templates` | `list[str]` | Email templates |
| `linkedin_posts` | `list[str]` | LinkedIn content |
| `messaging_framework` | `dict` | Key messages |
| `confidence` | `float` | Result confidence (0-1) |

#### Nested Type: `CampaignBrief`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Campaign name |
| `objective` | `str` | Campaign objective |
| `target_persona` | `str` | Primary persona |
| `key_messages` | `list[str]` | Core messages |
| `value_propositions` | `list[str]` | Value props |
| `call_to_action` | `str` | Primary CTA |
| `channels` | `list[str]` | Distribution channels |

---

## Common Patterns

### Running Agents Concurrently

```python
import asyncio

async def run_analysis():
    market_agent = MarketIntelligenceAgent()
    competitor_agent = CompetitorAnalystAgent()

    # Run in parallel
    market_result, competitor_result = await asyncio.gather(
        market_agent.run("Research market", context),
        competitor_agent.run("Analyze competitors", context),
    )

    return market_result, competitor_result
```

### Chaining Agents

```python
async def full_analysis(context: dict):
    # 1. Market research first
    market_agent = MarketIntelligenceAgent()
    market_result = await market_agent.run("Research market", context)

    # 2. Use market insights for profiling
    profiler = CustomerProfilerAgent()
    profile_result = await profiler.run(
        "Create profiles",
        {**context, "market_insights": market_result.insights}
    )

    # 3. Find leads matching profiles
    lead_hunter = LeadHunterAgent()
    leads = await lead_hunter.run(
        "Find leads",
        {**context, "personas": profile_result.personas}
    )

    return leads
```

### Error Handling

```python
from packages.core.src.errors import AgentError, LLMError

try:
    result = await agent.run(task, context)
except LLMError as e:
    logger.error("LLM call failed", error=str(e))
    # Handle gracefully
except AgentError as e:
    logger.error("Agent execution failed", error=str(e))
    raise
```

---

## Related Documentation

- [Agent Development Guide](../guides/agent-development.md)
- [Tool API Reference](tools.md)
- [Algorithm API Reference](algorithms.md)
- [Gateway API Reference](gateway.md)
