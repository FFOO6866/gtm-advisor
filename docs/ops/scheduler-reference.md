# Scheduler Reference — 21 Always-On Jobs

> GTM Advisor runs 21 scheduled jobs that keep intelligence fresh without manual intervention.
> All jobs run inside the FastAPI process via APScheduler (no external queue needed).

## Daily Intelligence Cycle (Asia/Singapore timezone)

```
02:00  Financial Sync ──────────┐
03:00  Document Processing      │  Data collection
04:00  Benchmarks (12 verticals)│  & computation
04:15  Document Intelligence    │
04:30  GTM Financial Extraction ┘

05:00  Vertical Intelligence Synthesis ──── Daily report generation

06:00  SGX Announcements ───────┐
06:30  Market Signal Scan       │  Signal detection
       (hourly) Signal Monitor  ┘

08:00  Sequence Runner ──── Outreach execution
```

## Job Reference

### Data Collection (5 jobs)

| # | Job | Schedule | Function | What It Does |
|---|-----|----------|----------|-------------|
| 8 | Financial Sync | Daily 02:00 | `_sync_financial_snapshots` | EODHD income stmt, balance sheet, CF for top 200 companies by market cap |
| 7 | Document Processing | Daily 03:00 | `_process_pending_documents` | Download + extract + embed corporate PDFs (annual reports, sustainability). Batch=5 |
| 6 | SGX Announcements | Daily 06:00 | `_discover_sgx_announcements` | Board changes, corporate actions from SGX RegNet (2-day lookback) |
| 9 | SGX Roster Sync | Sat 01:00 | `_sync_sgx_roster` | Full SGX symbol list refresh from EODHD |
| 15 | SG Reference Scraper | Sun 04:00 | `_run_sg_reference_scraper` | PSG/PDPA/MAS/EnterpriseSG public pages → SgKnowledgeArticle rows |

### News & RSS Ingestion (3 jobs)

| # | Job | Schedule | Function | What It Does |
|---|-----|----------|----------|-------------|
| 5 | RSS Feeds (generic) | Every 2h :00 | `_ingest_rss_feeds` | Business Times, e27, CNA, Vulcan Post, Fintech News SG, SBR (11 feeds) |
| 19 | **Vertical RSS Feeds** | Every 2h :15 | `_ingest_vertical_rss_feeds` | Trade publications per vertical: Campaign Asia, Ad Age, TechCrunch, etc. (21 feeds across 8 verticals). Pre-sets `vertical_slug` on ingestion |
| 10 | Article Pipeline | Every 2h :30 | `_run_article_pipeline` | LLM classification (vertical, signal_type, sentiment) + OpenAI embedding + Qdrant upsert. Batch=200 |

### Signal Detection (3 jobs)

| # | Job | Schedule | Function | What It Does |
|---|-----|----------|----------|-------------|
| 1 | Signal Monitor | Every 1h | `_run_signal_monitor_all_active` | NewsAPI + EODHD + Perplexity scan for companies with **active WorkforceConfig**. Persists SignalEvent rows. Auto-enrolls leads |
| 20 | **Market Signal Scan** | Daily 06:30 | `_run_market_signal_scan` | **Market-level** signal scan for ALL verticals with ecosystem definitions. Uses ecosystem research angles + NewsAPI. Detects: awards, conferences, exec moves, thought leadership |
| 13 | Document Intelligence | Daily 04:15 | `_run_document_intelligence` | Extract business signals from processed document chunks |

### Computation & Synthesis (5 jobs)

| # | Job | Schedule | Function | What It Does |
|---|-----|----------|----------|-------------|
| 12 | Benchmarks | Daily 04:00 | `_compute_vertical_benchmarks` | P25/P50/P75/P90 percentile benchmarks for all 12 verticals (current quarter) |
| 17 | GTM Financial Extraction | Daily 04:30 | `_run_gtm_financial_extraction` | Extract GTM channels, initiatives, segments from annual report chunks |
| 18 | **Vertical Intelligence** | **Daily 05:00** | `_run_vertical_intelligence_synthesis` | Synthesize VerticalIntelligenceReport for ALL verticals (deterministic, no LLM). Changed from weekly → daily |
| 11 | Qdrant Catchup | Daily 05:00 | `_run_qdrant_catchup` | Embed unembedded document chunks → Qdrant. Batch=500 |
| 14 | Research Embedder | Every 2h :45 | `_run_research_embedder` | Embed ResearchCache rows → Qdrant `research_cache_sg` collection |

### Knowledge & Intelligence Refresh (3 jobs)

| # | Job | Schedule | Function | What It Does |
|---|-----|----------|----------|-------------|
| 16 | Guide Resynthesis | Sat 03:00 | `_run_guide_resynthesis` | Re-synthesize domain guides with 3+ new research rows (GPT-4o). Saves `{slug}_live.json` |
| 21 | **Deep Intel Refresh** | Wed 01:00 | `_refresh_stale_intel_dossiers` | Re-gather Perplexity dossiers for companies with intel >14 days old. Max 20/run. Ecosystem-aware queries |
| 3 | Lead Enrichment | Sun 02:00 | `_run_lead_enrichment_all` | Re-enrich leads >30 days old: email verification, ACRA, EODHD. Max 200/run |

### Outreach & Reporting (2 jobs)

| # | Job | Schedule | Function | What It Does |
|---|-----|----------|----------|-------------|
| 2 | Sequence Runner | Daily 08:00 | `_run_sequence_runner` | Process due outreach steps (after human approval) |
| 4 | ROI Summary | Mon 07:00 | `_run_weekly_roi_summary` | Weekly attribution digest: emails sent, replies, meetings, pipeline value |

## Configuration

All jobs are registered in `services/gateway/src/scheduler.py`. The scheduler starts automatically with the gateway:

```bash
# Start gateway (scheduler starts in lifespan)
uv run uvicorn services.gateway.src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Key Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `timezone` | `Asia/Singapore` | All cron times are SGT |
| `max_instances` | 1 | Prevents concurrent runs of same job |
| `misfire_grace_time` | 300-7200s | How late a job can start after its scheduled time |
| `replace_existing` | True | Idempotent — restart doesn't duplicate jobs |

### Environment Variables Required

```bash
# Data collection
EODHD_API_KEY=...        # Financial data (Jobs 8, 9)
NEWSAPI_API_KEY=...       # News articles (Jobs 1, 5, 20)
PERPLEXITY_API_KEY=...    # Market research (Jobs 1, 20, 21)

# AI processing
OPENAI_API_KEY=...        # Embeddings, classification (Jobs 10, 11, 13, 14, 16, 17)

# Optional
HUNTER_API_KEY=...        # Lead enrichment (Job 3)
SENDGRID_API_KEY=...      # Outreach sequences (Job 2)
```

## Monitoring

Jobs log to structlog. Key log events:

```
scheduled_job_start       job={name}
scheduled_job_failed      job={name} error={msg}
{job}_complete            {metrics}
```

Failed jobs are logged but do NOT crash the gateway. Each job catches its own exceptions.

## Vertical RSS Feed Coverage

Defined in `packages/intelligence/src/vertical_ecosystem.py`:

| Vertical | Feeds | Key Publications |
|----------|-------|-----------------|
| marketing_comms | 6 | Campaign Asia, Marketing-Interactive, The Drum, Ad Age, Adweek, Mumbrella |
| fintech | 3 | Fintech News SG, Finextra, PYMNTS |
| biomedical | 2 | Fierce Biotech, BioPharma Dive |
| ict_saas | 2 | TechCrunch, Tech in Asia |
| maritime | 2 | Splash 247, Seatrade Maritime |
| clean_energy | 2 | CleanTechnica, GreenTech Media |
| logistics | 2 | Supply Chain Dive, The Loadstar |
| retail_ecommerce | 2 | Retail Dive, Modern Retail |

To add feeds for a new vertical, update `VERTICAL_RSS_FEEDS` in `vertical_ecosystem.py`.
