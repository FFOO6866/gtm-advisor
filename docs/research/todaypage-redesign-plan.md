# TodayPage Strategic Redesign — Implementation Plan

## Design Principle

The TodayPage is not a dashboard. It is a **Daily Strategic Briefing** — the
digital equivalent of a chief of staff presenting the morning intelligence
report. Every element follows the three-layer Intelligence Framework:

| Layer | Purpose | Example |
|-------|---------|---------|
| **Intelligence** | The observed signal or data point | "MAS issued digital payment guidelines" |
| **Strategic Implication** | What it means for the client's business | "40% of your target accounts must comply within 90 days" |
| **Recommended Action** | What the bench is doing or what needs approval | "Campaign Architect drafted compliance thought-leadership piece" |

---

## Architecture Overview

```
TodayPage
├── Greeting Header (user name, not company name)
├── Strategic Bench (compact AgentNetwork — digital team roster)
├── Market Intelligence Briefing
│   ├── Section: Industry & Market
│   ├── Section: Competitive Landscape
│   ├── Section: Pipeline & Prospects
│   └── Section: Strategic Actions
├── Weekly Performance Summary
└── Empty State (first-run: auto-trigger analysis)
```

---

## Phase 1: Data Foundation

### Task 1.1 — User Context in Frontend

**Problem:** Greeting says "Good afternoon, hi meet ai" — uses company name
(lowercase) instead of user's name.

**Changes:**
- `LoginPage.tsx`: After successful login, fetch `GET /auth/me`, store
  `full_name` in `localStorage.gtm_user_name`.
- `RegisterPage.tsx`: Same pattern after registration.
- `TodayPage.tsx`: Read `gtm_user_name` from localStorage, extract first
  name (`full_name.split(' ')[0]`).
- `Header.tsx`: Show company name (title-cased) on the left for authenticated
  users instead of empty `<div />`.

**Acceptance criteria:**
- Greeting: "Good afternoon, Sarah" (first name).
- Header: shows "Hi Meet AI" with green live indicator.
- Sidebar: company name title-cased.

**Files:** `LoginPage.tsx`, `RegisterPage.tsx`, `TodayPage.tsx`, `Header.tsx`,
`SidebarNav.tsx`.

---

### Task 1.2 — Market Data REST Endpoints

**Problem:** Vertical benchmarks, financial snapshots, and market intelligence
exist only in the MCP server (agent-accessible). The frontend has no way to
fetch KB intelligence data.

**Changes:**
- New router: `services/gateway/src/routers/market_data.py`
- Endpoints:
  - `GET /companies/{id}/market-data/vertical-summary` — Returns the user's
    vertical benchmarks (P25/P50/P75/P90 for key metrics), vertical name,
    company count, and latest period.
  - `GET /companies/{id}/market-data/competitor-signals` — Returns signals
    filtered to `competitor_move`, `product_launch` types.
  - `GET /companies/{id}/market-data/industry-signals` — Returns signals
    filtered to `market_shift`, `regulatory`, `funding`, `market_trend`.
  - `GET /companies/{id}/market-data/pipeline-summary` — Returns lead counts
    by status, recent leads, buying-signal leads.
- Wire router in `main.py`.

**Implementation notes:**
- Vertical resolution: company industry → `detect_vertical_slug()` → query
  `VerticalBenchmark` for that slug.
- Benchmark data: return latest annual + latest quarterly periods.
- Reuse existing DB queries from MCP server where possible.

**Acceptance criteria:**
- Each endpoint returns JSON with real KB data.
- Graceful empty response when no data exists for the vertical.
- Authenticated access only (Bearer token required).

**Files:** New `market_data.py`, `main.py` (router mount).

---

### Task 1.3 — Title-Case Display Helper

**Problem:** Company names stored as-is from user input. "hi meet ai"
displays as lowercase throughout the app.

**Changes:**
- Add `titleCase(name: string): string` utility in a shared helpers file.
- Apply in: `SidebarNav.tsx` (workspace header), `Header.tsx` (company
  display), `TodayPage.tsx` (anywhere company name appears).

**Rules:**
- Capitalise first letter of each word.
- Preserve existing capitalisation for known patterns (AI, SaaS, etc.) —
  simple heuristic: if a word is ≤3 chars and all caps, keep it.

**Acceptance criteria:**
- "hi meet ai" → "Hi Meet AI" everywhere.
- "himeetai" → "Himeetai" (no word breaks to infer).

**Files:** New `src/utils/format.ts`, `SidebarNav.tsx`, `Header.tsx`,
`TodayPage.tsx`.

---

## Phase 2: Strategic Briefing Redesign

### Task 2.1 — Section: Industry & Market Intelligence

**Purpose:** Answer "What's happening in our industry?" with strategic
implications and bench response.

**Data source:** `GET /companies/{id}/signals` filtered by type +
`GET /companies/{id}/insights/summary` + (new) vertical summary endpoint.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  INDUSTRY & MARKET                        View all →    │
│                                                         │
│  ⚡ Regulatory  •  MAS digital payment guidelines       │
│     Impact: 40% of fintech targets must comply by Q3.   │
│     → Campaign Architect drafting compliance brief.     │
│                                                         │
│  📈 Funding  •  SEA fintech funding up 23% YoY          │
│     Impact: More competitors entering your space.       │
│     → Lead Hunter accelerating outreach to early-stage. │
│                                                         │
│  Your vertical (SaaS): median revenue growth 12.3%      │
│  Top quartile threshold: 24.7% — [View Benchmarks]      │
└─────────────────────────────────────────────────────────┘
```

**Three-layer pattern per signal:**
1. **Intelligence:** Signal type badge + headline + source.
2. **Strategic Implication:** `summary` field, or generated implication from
   signal type + context.
3. **Recommended Action:** `recommended_action` field, prefixed with agent
   name where applicable.

**Empty state:** "Market Intelligence agent scans 142 sources daily. Your
first briefing arrives with your initial analysis."

**Files:** `TodayPage.tsx` (new `IndustrySection` component).

---

### Task 2.2 — Section: Competitive Landscape

**Purpose:** Answer "What are our competitors doing?" with strategic
implications.

**Data source:** `GET /companies/{id}/signals?type=competitor_move,product_launch`
+ `GET /companies/{id}/competitors` (existing battlecards endpoint).

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  COMPETITIVE LANDSCAPE                    View all →    │
│                                                         │
│  🎯 Competitor Move  •  Acme Corp raised $5M Series A   │
│     Impact: Likely +30% sales headcount within 6 months.│
│     → 8 shared-target accounts prioritised for outreach.│
│                                                         │
│  🚀 Product Launch  •  Beta Inc launched APAC offering   │
│     Impact: No PSG certification — your advantage.      │
│     → Competitor Analyst updating battlecard.            │
│                                                         │
│  Tracking 23 competitors  •  Last updated: 2h ago       │
└─────────────────────────────────────────────────────────┘
```

**Empty state:** "Competitor Analyst monitors your competitive landscape.
Run your first analysis to identify and track key competitors."

**Files:** `TodayPage.tsx` (new `CompetitorSection` component).

---

### Task 2.3 — Section: Pipeline & Prospects

**Purpose:** Answer "Where are our customers?" with lead quality metrics and
buying signals.

**Data source:** `GET /companies/{id}/leads` (existing endpoint with status
filter + fit_score).

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  PIPELINE & PROSPECTS                     View all →    │
│                                                         │
│  New  ████████░░░░  8    Qualified ████░░░░░░░░ 3       │
│  Contacted ██░░░░░░░░░░ 2   Converted █░░░░░░░░░░░ 1   │
│                                                         │
│  🟢 3 prospects showing buying signals                  │
│     These accounts engaged with your content this week. │
│     Historical conversion: 60% when contacted within    │
│     48 hours of signal.                                 │
│     → 2 personalised emails pending your approval.      │
│                                                         │
│  Recent: Jane Doe (VP Eng, Acme) — fit 87% — new       │
│          Mark Tan (CTO, FinCo) — fit 72% — qualified    │
└─────────────────────────────────────────────────────────┘
```

**Key design choice:** Show fit score as quality indicator, not quantity.
Align with SG SME pain point: "lead quality over vanity metrics."

**Empty state:** "Lead Hunter identifies qualified prospects from verified
databases. Your pipeline populates after your first analysis."

**Files:** `TodayPage.tsx` (new `PipelineSection` component).

---

### Task 2.4 — Section: Strategic Actions

**Purpose:** Answer "What needs my decision?" — the only section requiring
user input.

**Data source:** `GET /companies/{id}/approvals/count` (existing) +
urgent signals needing action.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  STRATEGIC ACTIONS                                      │
│                                                         │
│  ⚡ 4 outreach emails awaiting approval                  │
│     Delay beyond 24 hours reduces response rates.       │
│     [Review & Approve]                                  │
│                                                         │
│  📡 2 urgent market signals require your input           │
│     Competitor funding round + regulatory change.       │
│     [Review Signals]                                    │
│                                                         │
│  ✅ Pipeline clear?                                      │
│     Your bench recommends launching a new campaign to   │
│     maintain pipeline momentum.                         │
│     [Launch Campaign]                                   │
└─────────────────────────────────────────────────────────┘
```

**Logic:** Priority ordering: pending approvals → urgent signals →
unqualified leads → all clear (recommend campaign launch).

**Empty state:** "No actions required. Your bench is running autonomously."

**Files:** `TodayPage.tsx` (new `ActionsSection` component).

---

### Task 2.5 — Weekly Performance Summary

**Purpose:** Prove ongoing value. Answer "What has my bench accomplished?"
Directly addresses the SG SME pain point of ROI opacity.

**Data source:** `GET /companies/{id}/attribution/summary?days=7` (existing
endpoint, just change `days` parameter).

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  THIS WEEK'S PERFORMANCE                                │
│                                                         │
│  24 emails sent  •  6 replies (25%)  •  2 meetings      │
│  Reply rate 3x above industry benchmark (8%)            │
│                                                         │
│  12 market signals processed  •  3 competitor moves     │
│  5 leads enriched  •  1 new prospect identified         │
│                                                         │
│  [View Full Attribution Report →]                       │
└─────────────────────────────────────────────────────────┘
```

**Key design choice:** Show real metrics from real database queries. Never
fabricate numbers. If no outreach has occurred, show intelligence activity
only (signals processed, leads enriched).

**Files:** `TodayPage.tsx` (new `PerformanceSummary` component).

---

## Phase 3: Agent Presence in Paid Tier

### Task 3.1 — Compact Agent Team Roster

**Purpose:** Communicate "you have a strategic team working for you" — the
digital org chart that augments the physical team.

**Design intent:** Aesthetic, not functional. Communicates identity and
presence, not system health. Equivalent to a "Meet Your Team" section on an
agency website.

**Layout (horizontal strip at top of TodayPage):**
```
┌─────────────────────────────────────────────────────────┐
│  YOUR STRATEGIC BENCH                                   │
│                                                         │
│  [🎯 GTM         ] [📊 Market    ] [🔍 Competitor ]    │
│  [ Strategist    ] [ Intelligence] [ Analyst      ]    │
│  [ Orchestrating ] [ Scanning    ] [ Monitoring   ]    │
│                                                         │
│  [👥 Customer    ] [🔎 Lead      ] [📢 Campaign   ]    │
│  [ Profiler      ] [ Hunter      ] [ Architect    ]    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Behaviour:**
- Each agent card shows: icon + name + current status (text, not dot colour).
- Status text: "Orchestrating", "Scanning", "Monitoring", "Ready", "Drafting".
- Click any agent → navigate to relevant page (e.g., Lead Hunter → /prospects).
- During active analysis: cards animate with subtle pulse, status updates
  stream via existing WebSocket.

**Teaser vs. Paid:**
- Teaser: Full AgentNetwork SVG orbital animation (existing). Aesthetic demo.
- Paid: Compact horizontal roster (new). Functional — click to navigate.
  More elaborated — shows status text and recent output count.

**Files:** New `src/components/AgentTeamRoster.tsx`, `TodayPage.tsx`.

---

### Task 3.2 — Agent Activity Feed

**Purpose:** Show that the bench is actively working. Address the trust gap:
"Are you actually doing work?" (SG SME transparency requirement).

**Data source:** Compose from existing data:
- Recent signals created (agent: Signal Monitor).
- Recent leads enriched (agent: Lead Enrichment).
- Recent campaigns drafted (agent: Campaign Architect).
- Approval items created (agent: Outreach Executor).

**Layout (within Recent Activity section):**
```
  ● Market Intelligence scanned 3 RSS feeds           2h ago
  ● Lead Hunter enriched 5 prospect profiles           6h ago
  ● Signal Monitor detected regulatory change          1d ago
  ● Campaign Architect drafted email sequence           1d ago
```

**Key design choice:** Attribute activity to agent names, not system events.
This reinforces the "team" metaphor and justifies the premium positioning.

**Files:** `TodayPage.tsx` (update existing `ActivityRow` component).

---

## Phase 4: First-Run Experience

### Task 4.1 — Auto-Trigger Analysis on First Login

**Problem:** Paid users land on an empty dashboard. Current TTFV: infinite.
Target TTFV: <10 minutes.

**Trigger conditions:**
- `companyId` exists (company created during teaser or registration).
- No analysis exists for this company (check via `GET /analysis/` list).
- No signals, no leads, no insights (all counters zero).

**Behaviour:**
1. TodayPage detects first-run state.
2. Displays the Agent Team Roster in "deploying" state.
3. Auto-calls `POST /analysis/start` with company context from CompanyContext.
4. WebSocket streams agent progress.
5. As each agent completes, the corresponding TodayPage section populates.
6. Full briefing ready in ~5–10 minutes.

**Fallback:** If auto-trigger fails (missing required fields), show a guided
prompt: "Complete your company profile to activate your strategic bench."
Links to OnboardingModal.

**Files:** `TodayPage.tsx` (first-run detection + auto-trigger logic).

---

### Task 4.2 — Progressive Briefing Population

**Problem:** Current TodayPage fetches all data once on mount. During first
analysis, all data is zero.

**Changes:**
- After auto-trigger, poll `GET /analysis/{id}/status` every 5 seconds.
- As `completed_agents` array grows, re-fetch the corresponding section:
  - `market-intelligence` complete → re-fetch industry signals + insights.
  - `competitor-analyst` complete → re-fetch competitor signals.
  - `lead-hunter` complete → re-fetch pipeline summary.
  - `campaign-architect` complete → re-fetch campaign data.
- Each section transitions from "Agent working..." to populated state with
  animation (fade in).

**Key UX principle:** User watches the briefing build in real-time. This IS
the "aha moment" — seeing intelligence arrive that their agency would have
taken 3 months to compile.

**Files:** `TodayPage.tsx` (polling + progressive section rendering).

---

### Task 4.3 — First-Run Empty State (Pre-Analysis)

**Current:** "Your GTM engine is ready" + "Launch Campaign" button.

**New design:** Briefing-style empty state that communicates the bench is
preparing to deploy.

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  [Agent Team Roster — all showing "Standby"]            │
│                                                         │
│  Your Strategic Bench is ready to deploy.               │
│                                                         │
│  6 specialised agents will map your competitive         │
│  landscape, identify qualified prospects, and prepare   │
│  your first campaign brief — all within minutes.        │
│                                                         │
│  [Start Market Analysis]                                │
│                                                         │
│  What happens next:                                     │
│  1. Market Intelligence scans 142 data sources          │
│  2. Competitor Analyst profiles your competitive space   │
│  3. Customer Profiler defines your ideal buyer          │
│  4. Lead Hunter surfaces qualified prospects            │
│  5. Campaign Architect drafts your first outreach       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**CTA:** "Start Market Analysis" (not "Launch Campaign" — campaigns need
data first; analysis is the value chain entry point).

**Files:** `TodayPage.tsx` (replace existing `EmptyState` component).

---

## Phase 5: Brand Voice & Copy

### Task 5.1 — Copy Audit and Rewrite

Review all user-facing copy against the Brand Personality document:
- Voice: "The High-Velocity Strategist" — direct, evidence-based, certain.
- Avoid: Arrogance, hype, vague promises, fluff, passive voice.
- Tempo: Fast-paced, rhythmic, efficient.
- Tone: Like a high-end, futuristic mission control — not a cheap AI tool.

**Key rewrites:**

| Location | Current | Revised |
|----------|---------|---------|
| Greeting subtitle | "Here's what's happening in your market today" | "Your daily strategic briefing" |
| Empty state title | "Your GTM engine is ready" | "Your Strategic Bench is ready to deploy" |
| Empty state CTA | "Launch Campaign" | "Start Market Analysis" |
| Section headers | Generic ("Today's Signals") | Professional ("Competitive Landscape") |
| Agent references | None | Named agents ("Lead Hunter surfaced 3 prospects") |
| Activity items | "New lead: Jane Doe" | "Lead Hunter identified: Jane Doe, VP Eng at Acme (87% fit)" |

**Principle:** Every piece of copy should sound like a briefing from a senior
strategist, not a SaaS tooltip.

**Files:** `TodayPage.tsx`, `SidebarNav.tsx`, `Header.tsx`, all section
components.

---

### Task 5.2 — Sidebar Navigation Refinements

**Current issues:**
- "Insights" label but shows `SignalsFeed` component → rename to "Signals"
  or keep "Insights" but ensure the page matches the label.
- "Analysis" navigates to `/` (teaser page) — breaks spatial model.
- 12 nav items visible on day one — cognitive overload.

**Changes:**
- Rename "Insights" → "Intelligence" (aligns with brand vocabulary).
- "Analysis" → "New Analysis" with distinct icon treatment (or move under
  a "+" action button).
- Consider: dim/disable nav items that have no data yet (e.g., "Sequences"
  shows as `text-white/20` until first sequence exists).

**Files:** `SidebarNav.tsx`.

---

## Execution Order

| # | Task | Phase | Effort | Dependencies |
|---|------|-------|--------|-------------|
| 1 | Task 1.1 — User Context | Foundation | S | None |
| 2 | Task 1.3 — Title-Case Helper | Foundation | XS | None |
| 3 | Task 1.2 — Market Data Endpoints | Foundation | L | None |
| 4 | Task 3.1 — Agent Team Roster | Agent Presence | M | None |
| 5 | Task 4.3 — First-Run Empty State | First-Run | M | Task 3.1 |
| 6 | Task 5.1 — Copy Rewrite | Brand Voice | M | None |
| 7 | Task 2.1 — Industry Section | Briefing | M | Task 1.2 |
| 8 | Task 2.2 — Competitor Section | Briefing | M | Task 1.2 |
| 9 | Task 2.3 — Pipeline Section | Briefing | M | None |
| 10 | Task 2.4 — Actions Section | Briefing | S | None |
| 11 | Task 2.5 — Performance Summary | Briefing | S | None |
| 12 | Task 3.2 — Agent Activity Feed | Agent Presence | S | None |
| 13 | Task 4.1 — Auto-Trigger Analysis | First-Run | M | Task 4.3 |
| 14 | Task 4.2 — Progressive Population | First-Run | L | Task 4.1 |
| 15 | Task 5.2 — Sidebar Refinements | Brand Voice | S | None |

**Red team checkpoint after each task.**

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Time to First Value (TTFV) | ∞ (empty dashboard) | < 10 minutes |
| Sections populated on first visit | 0 of 4 | 4 of 4 (post-analysis) |
| Intelligence items with implications | 0% | 100% (every signal has implication) |
| Intelligence items with actions | 0% | 80%+ (most signals have recommended action) |
| User greeted by name | No | Yes |
| Company name properly formatted | No | Yes |
| Agent presence visible in paid tier | No (only teaser) | Yes (team roster) |
| KB data surfaced on dashboard | 0 endpoints | 4 new endpoints |
