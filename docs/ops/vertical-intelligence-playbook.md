# Vertical Intelligence Playbook

> Step-by-step guide for building, operating, and maintaining vertical intelligence for any industry.

## Overview

The Vertical Intelligence Framework produces consulting-grade industry reports by combining:
- **Financial data** (EODHD) — revenue, margins, benchmarks
- **News & RSS** (NewsAPI, trade publications) — real-time signals
- **Deep research** (Perplexity) — company dossiers, thought leadership
- **Industry ecosystem** (curated JSON) — associations, awards, regulators, events
- **LLM synthesis** (GPT-4o) — narrative and GTM implications

## Building a New Vertical (SOP)

### Phase 1: Seed Companies (1-2 hours)

Create `scripts/seed_{vertical_slug}.py` following the pattern in `scripts/seed_marketing_comms.py`.

```python
# Structure
LISTED_COMPANIES = [
    {
        "ticker": "AAPL", "exchange": "US", "name": "Apple Inc",
        "currency": "USD", "website": "https://apple.com",
        "description": "...", "is_sg_incorporated": False,
    },
]

PRIVATE_COMPANIES = [
    {
        "ticker": "STARTUP-SG", "exchange": "PRIVATE", "name": "Startup Pte Ltd",
        "currency": "SGD", "website": "https://startup.sg",
        "description": "...", "is_sg_incorporated": True,
    },
]
```

**Checklist:**
- [ ] All major global holding companies / public players
- [ ] Top 20+ Singapore agencies/companies (private)
- [ ] Correct EODHD exchange codes (`US`, `LSE`, `PA`, `KO`, `AS`, `HK`, `SG`, `AU`)
- [ ] No duplicate ticker+exchange pairs
- [ ] IPO/M&A status current (comment out delisted companies)
- [ ] Run: `uv run python scripts/seed_{slug}.py`

### Phase 2: Sync Financial Data (10-30 min)

```bash
# Sync EODHD fundamentals for all listed companies in the vertical
uv run python scripts/sync_companies.py --phases 3 --limit 50

# Compute benchmarks for the vertical
uv run python << 'EOF'
import asyncio
from dotenv import load_dotenv; load_dotenv(".env")

async def main():
    from packages.database.src.session import async_session_factory, close_db, init_db
    from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync
    await init_db()
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        for period in ["2024", "2023", "2025-Q3", "2024-Q3"]:
            ok = await sync.compute_and_store_benchmarks("YOUR_SLUG", period)
            print(f"  {period}: {'OK' if ok else 'SKIP'}")
            await db.commit()
    await close_db()

asyncio.run(main())
EOF
```

### Phase 3: Create Ecosystem Definition (1-2 hours)

Create `data/intel/{slug}/_ecosystem.json` using this template:

```json
{
  "vertical_slug": "your_slug",
  "vertical_name": "Human-Readable Vertical Name",
  "generated_at": "2026-03-17",
  "description": "Industry ecosystem reference for ...",

  "associations": [
    {
      "name": "Key Industry Body",
      "abbr": "KIB",
      "website": "https://...",
      "description": "What this body does.",
      "sg_relevance": "critical",
      "sg_notes": "Singapore-specific context."
    }
  ],
  "publications": [],
  "awards_bodies": [],
  "research_firms": [],
  "regulators": [],
  "certification_bodies": [],

  "events": [
    {
      "name": "Industry Conference",
      "frequency": "annual",
      "typical_month": "June",
      "location": "Singapore",
      "website": "https://...",
      "description": "Premier industry gathering.",
      "sg_relevance": "high"
    }
  ],

  "rss_feeds": [
    {
      "url": "https://example.com/feed",
      "name": "Trade Publication",
      "category": "trade_publication",
      "priority": "high"
    }
  ],

  "influencers": [],
  "research_angles": [],

  "sg_summary": {
    "primary_trade_body": "...",
    "key_regulator": "...",
    "premier_award": "...",
    "key_publications": ["...", "..."]
  }
}
```

**Relevance tiers:** `critical` (mandatory for SG operations) > `high` (major influence) > `medium` (relevant) > `low` (peripheral)

**Also update the static registries** in `packages/intelligence/src/vertical_ecosystem.py`:
- `VERTICAL_RSS_FEEDS` — add trade publication feeds
- `VERTICAL_RESEARCH_ANGLES` — add Perplexity query angles

### Phase 4: Gather Deep Intelligence (2-8 hours depending on company count)

```bash
# Gather dossiers for all companies in the vertical
uv run python scripts/intel_vertical.py --vertical your_slug

# Or limit to a test batch
uv run python scripts/intel_vertical.py --vertical your_slug --limit 5

# Options
--listed-only     # Only listed companies
--private-only    # Only private companies
--ticker WPP      # Single company
--force           # Re-gather even if cached (<7 days)
```

Each company gets 3-4 Perplexity queries + website scrape + NewsAPI search.
Output: `data/intel/{slug}/{ticker}_{exchange}.json`

### Phase 5: Generate Intelligence Report

```bash
# Step 1: Synthesize (deterministic, no LLM)
# Step 2: Agent synthesis (GPT-4o)
# Use the two-step pipeline script:
uv run python scripts/run_vertical_intel_marketing_comms.py

# Or create a similar script for your vertical
```

Output: `data/intel/{slug}/_vertical_intelligence_report.json`

### Phase 6: Verify & Validate

```bash
# List available ecosystems
uv run python scripts/intel_vertical.py --list-verticals

# Count dossiers
ls data/intel/{slug}/*.json | wc -l

# Check report quality
python -c "
import json
r = json.load(open('data/intel/{slug}/_vertical_intelligence_report.json'))
print(f'Confidence: {r[\"confidence\"]}')
print(f'Companies: {r[\"total_companies_tracked\"]}')
print(f'Drivers: {len(r[\"drivers\"])}')
print(f'Leaders: {len(r[\"leaders\"])}')
print(f'Benchmark periods: {len(r[\"benchmark_history\"])}')
print(f'Data sources: {r[\"data_sources_used\"]}')
"
```

**Quality gates:**
- [ ] Confidence >= 0.70
- [ ] >= 3 drivers with GTM implications
- [ ] Leaders/challengers correctly classified
- [ ] Benchmark data from >= 2 periods
- [ ] No empty arrays that should have data (trends, signals, exec movements)
- [ ] Executive summary references real data, not hallucinations

## Daily Operations (Automatic)

Once the gateway is running, these jobs keep the vertical fresh:

| Frequency | What Happens |
|-----------|-------------|
| Every 2h | Vertical RSS feeds ingested (Campaign Asia, etc.) |
| Every 2h | Articles classified, embedded, pushed to Qdrant |
| Daily 02:00 | Financial data synced from EODHD |
| Daily 04:00 | Benchmarks recomputed (current quarter) |
| Daily 05:00 | VerticalIntelligenceReport re-synthesized |
| Daily 06:30 | Market signal scan (industry-level: awards, events, exec moves) |
| Wed 01:00 | Stale dossiers re-gathered (>14 days old, max 20/run) |
| Sat 03:00 | Domain guides re-synthesized with new research |

**No manual intervention needed** after Phase 6.

## Troubleshooting

### "No ecosystem file for vertical X"
Expected for new verticals. Create `data/intel/{slug}/_ecosystem.json`. The pipeline works without it but produces generic (less accurate) analysis.

### "marketing_comms vertical not found"
Run the seed script first: `uv run python scripts/seed_{slug}.py`

### Benchmarks show 0 companies
Financial sync hasn't run for this vertical's companies. Run:
```bash
uv run python scripts/sync_companies.py --phases 3
```

### Confidence below 0.70
Check which data sources are missing:
- No benchmarks → run benchmark computation
- No live data → check PERPLEXITY_API_KEY and NEWSAPI_API_KEY
- No ecosystem → create ecosystem JSON
- Few companies → add more companies to seed

### Stale dossiers not refreshing
Deep Intel Refresh (Job 21) only runs on Wednesdays. Check:
- Are dossiers >14 days old? (`ls -la data/intel/{slug}/`)
- Is the gateway running? (scheduler only runs in-process)
- Force refresh: `uv run python scripts/intel_vertical.py --vertical {slug} --force`

## Current Vertical Coverage

| Vertical | Companies | Listed | Dossiers | Ecosystem | Benchmarks | Status |
|----------|-----------|--------|----------|-----------|------------|--------|
| marketing_comms | 110 | 32 | 112 | 67 orgs | 4 periods | Production |
| fintech | ~80 | ~30 | 0 | Static angles | 4 periods | Needs ecosystem |
| ict_saas | ~60 | ~25 | 0 | Static angles | 4 periods | Needs ecosystem |
| biomedical | ~40 | ~15 | 0 | Static angles | 4 periods | Needs ecosystem |
| maritime | ~15 | ~12 | 0 | Static angles | 4 periods | Needs ecosystem |
| Others | Varies | Varies | 0 | None | 4 periods | Needs full build |

## File Inventory per Vertical

```
data/intel/{slug}/
  _ecosystem.json                     # Industry ecosystem definition
  _vertical_intelligence_report.json  # Latest consulting-grade report
  {TICKER}_{EXCHANGE}.json            # Per-company dossier (Perplexity + scrape + news)
```

## Key Code Locations

| Component | File |
|-----------|------|
| Ecosystem registry | `packages/intelligence/src/vertical_ecosystem.py` |
| Synthesizer (deterministic) | `packages/intelligence/src/vertical_synthesizer.py` |
| Agent (LLM synthesis) | `agents/vertical_intelligence/src/agent.py` |
| Intel gathering script | `scripts/intel_vertical.py` |
| Scheduler (21 jobs) | `services/gateway/src/scheduler.py` |
| Signal types & models | `packages/database/src/models.py` (SignalType, SignalSourceType, SignalEvent) |
| Vertical seeds | `packages/database/src/vertical_seeds.py` |
| MCP server | `packages/mcp/src/servers/market_intel.py` |
