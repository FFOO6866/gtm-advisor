# Getting Started with GTM Advisor

This guide walks you through your first GTM analysis, from setup to results.

## Prerequisites

Before starting, ensure you have:

- **Python 3.12+** installed
- **Node.js 18+** installed
- **uv** Python package manager (`pip install uv`)
- **pnpm** Node package manager (`npm install -g pnpm`)
- API keys for at least one LLM provider

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/gtm-advisor.git
cd gtm-advisor
```

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Install Dashboard Dependencies

```bash
cd services/dashboard
pnpm install
cd ../..
```

### 4. Configure Environment

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Required: At least one LLM provider
OPENAI_API_KEY=sk-your-openai-key

# Recommended: For real-time market data
NEWSAPI_API_KEY=your-newsapi-key
EODHD_API_KEY=your-eodhd-key

# Optional: Alternative LLM providers
PERPLEXITY_API_KEY=pplx-your-perplexity-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Optional: Data enrichment (enhances lead quality)
CLEARBIT_API_KEY=your-clearbit-key
APOLLO_API_KEY=your-apollo-key
```

## Running GTM Advisor

### Start the Backend

```bash
# Terminal 1
uv run uvicorn services.gateway.src.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started reloader process
```

### Start the Dashboard

```bash
# Terminal 2
cd services/dashboard
pnpm dev
```

You should see:
```
VITE v6.x.x ready in XXX ms
➜  Local:   http://localhost:3000/
```

### Access the Dashboard

Open **http://localhost:3000** in your browser.

## Your First Analysis

### Step 1: Enter Company Information

When the dashboard loads, you'll see the onboarding modal:

1. **Company Name**: Enter your company name (e.g., "TechStartup SG")
2. **Industry**: Select your industry (e.g., "SaaS")
3. Click **Continue**

### Step 2: Describe Your Business

1. **Description**: Describe what your company does
   - Example: "We provide HR automation software for Singapore SMEs"
2. **Value Proposition** (optional): Your unique selling point
   - Example: "Reduce HR admin time by 50%"
3. **Competitors** (optional): Known competitors
   - Example: "HRCloud, PayrollPro"
4. **Target Markets**: Select your target markets (default: Singapore)

Click **Start Analysis**

### Step 3: Watch the Analysis

The dashboard shows real-time progress as agents work:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Network                                │
│                                                                  │
│   🎯 GTM Strategist (coordinating)                              │
│        │                                                         │
│        ├─→ 📊 Market Intelligence (researching fintech...)      │
│        │       [████████░░] 80%                                 │
│        │                                                         │
│        ├─→ 🔍 Competitor Analyst (analyzing CompetitorA...)     │
│        │       [██████░░░░] 60%                                 │
│        │                                                         │
│        └─→ 👥 Customer Profiler (creating personas...)          │
│                [████░░░░░░] 40%                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Step 4: Review Results

When analysis completes, the Results Panel shows:

#### Decision Attribution
Shows how decisions were made:
- **Algorithm decisions**: Deterministic scoring (ICP, BANT, value)
- **LLM decisions**: Synthesis and generation
- **Determinism ratio**: Higher = more repeatable

#### Qualified Leads
Each lead shows:
- Company name and industry
- Employee count
- **Fit score** (how well they match your ICP)
- **Scoring method** badge (ALGO = algorithm, LLM = generated)
- **Expected value** (estimated deal size)

#### Market Insights
Key findings from market research with sources.

#### Campaign Templates
Ready-to-use outreach materials:
- Email sequences
- LinkedIn posts

## Understanding the Analysis

### Agent Workflow

The analysis follows this sequence:

```
1. GTM Strategist
   │
   │ "I'll coordinate the analysis"
   │
   ├──→ 2. Market Intelligence
   │       "Researching fintech market trends..."
   │       - Calls NewsAPI for recent news
   │       - Analyzes market size and growth
   │       - Identifies opportunities and threats
   │
   ├──→ 3. Competitor Analyst
   │       "Analyzing your competitors..."
   │       - SWOT analysis for each competitor
   │       - Positioning recommendations
   │       - Differentiation opportunities
   │
   ├──→ 4. Customer Profiler
   │       "Creating ideal customer profiles..."
   │       - Buyer personas with pain points
   │       - Decision criteria
   │       - Preferred channels
   │
   ├──→ 5. Lead Hunter
   │       "Finding qualified leads..."
   │       - Company enrichment (real data)
   │       - ICP scoring (algorithm)
   │       - BANT scoring (algorithm)
   │       - Lead value calculation
   │
   └──→ 6. Campaign Architect
           "Creating outreach campaigns..."
           - Email templates
           - LinkedIn content
           - Messaging framework
```

### Four-Layer Decision Making

GTM Advisor uses four layers for decisions:

| Layer | What It Does | Example |
|-------|--------------|---------|
| **Cognitive (LLM)** | Synthesis, explanation | "This company is a good fit because..." |
| **Analytical (Algorithm)** | Scoring, calculations | ICP score = 0.85 |
| **Operational (Tools)** | Data acquisition | Company employee count: 50 |
| **Governance (Rules)** | Compliance, access | PDPA data check passed |

### Interpreting Fit Scores

| Score | Meaning | Action |
|-------|---------|--------|
| 0.80+ | Excellent fit | Prioritize outreach |
| 0.60-0.79 | Good fit | Include in campaigns |
| 0.40-0.59 | Moderate fit | Consider for nurture |
| <0.40 | Poor fit | Skip for now |

## Next Steps

### Export Results

Click **Export Full Report** to download:
- PDF summary
- CSV of leads
- Campaign materials

### Refine Analysis

Run another analysis with:
- Different competitors
- Adjusted target markets
- More specific value proposition

### Follow Up

Use the campaign templates to:
1. Send personalized outreach to top leads
2. Post thought leadership content
3. Track responses in your CRM

## Troubleshooting

### Backend Not Available

If you see "Backend Not Available":

1. Check the gateway is running on port 8000
2. Verify API keys are configured in `.env`
3. Check terminal for error messages

### Analysis Failed

If analysis fails:

1. Check LLM API quota hasn't been exceeded
2. Verify internet connectivity for data sources
3. Review gateway logs for specific errors

### No Leads Found

If no leads are returned:

1. Broaden your industry selection
2. Check if enrichment APIs are configured
3. Review ICP criteria (may be too strict)

## Configuration Options

### Adjust Lead Count

In the onboarding form, you can request 1-50 leads. More leads take longer but provide more options.

### Industry Selection

Available industries:
- Fintech
- SaaS
- E-commerce
- Healthtech
- Edtech
- Proptech
- Logistics
- Manufacturing
- Professional Services
- Other

### Target Markets

Select multiple markets to expand your search:
- Singapore (default)
- Malaysia
- Indonesia
- Thailand
- Vietnam
- Philippines

## Related Documentation

- [Understanding Results](understanding-results.md)
- [Agent Development](agent-development.md)
- [API Reference](../api/gateway.md)
- [Architecture Overview](architecture-overview.md)
