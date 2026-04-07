# Promise-Scope Audit

**Purpose**: Track the gap (if any) between *what users see* (visibility scope) and *what users are led to believe the product does* (promise scope).

This is a discipline added in Cycle 3 because Cycles 1 and 2 focused on visibility (which routes/CTAs/sections are shown) without explicitly tracking the promises those surfaces make. A surface can be perfectly hidden where it should be hidden and still mislead users about what the visible parts deliver.

**Rule**: For every launch surface, the explicit and implicit promises must match the actual behavior. If they drift, the surface is corrected (not the behavior).

---

## Two scopes defined

| Scope | Definition | Examples |
|---|---|---|
| **Visibility scope** | What the user can see, click, navigate to | Nav items, page sections, buttons, CTAs |
| **Promise scope** | What the user is led to believe the product does, based on the visible surface | Header copy, subtitle, button verbs, animations, marketing language, brand positioning |

**Visibility drift** = something is shown that shouldn't be (Cycle 1–2 caught most of these)
**Promise drift** = something is implied that the product doesn't actually do

Both can mislead. Promise drift is harder to detect because it lives in word choice and visual signals, not in code structure.

---

## Audit by surface

### Surface 1: Onboarding Modal (`/`, OnboardingModal.tsx)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Title | "Tell us about your business" | One-time setup | Yes — one analysis per submission | None |
| Doc upload | "Upload PDF/DOCX/TXT" | We extract structured data | Yes — GPT-4o-mini parses | None |
| Submit CTA | "Run analysis" | Triggers analysis once | Yes | None |
| AgentNetwork visualization (post-submit) | Six animated agent nodes "thinking" and "completing" | "AI agents work for you" | Agents run during one analysis run only; nothing happens between runs | **Latent drift — see "Onboarding Drift" below** |

**Onboarding Drift**: The orbital agent visualization is the most evocative element of the experience. A first-time customer could reasonably infer that "AI agents are working continuously on my behalf." In reality, agents run only during an active analysis. Mitigation: the visualization is anchored to a real WebSocket-streamed analysis run, so the customer sees the activity stop when the analysis completes. This anchors the promise to a discrete event. **Current status: acceptable** but watch for marketing copy that might amplify the drift.

---

### Surface 2: TodayPage (`/today`)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Page title | "Today" | A daily briefing that updates | Yes — updates daily via scheduler | None |
| Cold-start title | "Welcome to Hi Meet AI" | First-time user welcome | Yes | None |
| Cold-start subtitle | "Get your first briefing in two minutes" | A briefing is produced quickly | True — analysis takes ~2 min | None |
| Cold-start CTA | "Run Your First Analysis" | One click to start | Yes | None |
| Industry & Market section | "Industry & Market" header | Real-time market intelligence | Yes — populated from Signal Monitor agent + RSS ingestion | None |
| Pipeline section | Lead cards | These are real leads matched to ICP | Yes | None |
| Strategic Intelligence section | "Deep dive" action (gated in launch) | Drill-down available | Action is hidden in launch — no implication remains | None |
| (Removed in Cycle 2) Attribution KPIs | "Emails sent / Reply rate / Meetings booked / Pipeline value" | "We track your outreach" | Removed in launch mode — no implication remains | None (resolved) |

**TodayPage status: clean.** No visible promise drift after Cycle 2 corrections.

---

### Surface 3: Run Analysis Flow (`/`, Dashboard component)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Header during analysis | Company name | This analysis is for THIS company | Yes | None |
| AgentNetwork orbital | Animated agents in motion | Each agent does specific work | Yes — each agent's status reflects its real PDCA state | None |
| ConversationPanel messages | "Market Intelligence is researching..." | Real-time progress | Yes | None |
| ResultsPanel CTAs | "Save to Your Daily Briefing" / "Open Today's Briefing" | A briefing exists post-analysis | Yes — TodayPage shows the persisted briefing | None |
| Export CTA | "Download Report (JSON)" | A complete report can be exported | Yes | None |

**Run Analysis status: clean.**

---

### Surface 4: Campaign Plans (`/campaigns`)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Page title | "Campaign Plans" | Plans, not running campaigns | True — planning posture explicit | None |
| Subtitle (empty state) | "Plan and document your GTM campaigns" | Documentation tool, not execution | True | None |
| New CTA | "New Plan" | Creates a draft plan | Yes — creates DB record | None |
| Status pill | "Draft" only (Active hidden in launch) | All plans are drafts | True | None |
| 3-step wizard | Objective → Channels → Review | A structured planning flow | Yes | None |
| (Removed in launch) Activate button | n/a | n/a | Hidden | None (resolved) |

**Campaign Plans status: clean.** Renamed in Cycle 2 to make planning posture explicit.

---

### Surface 5: Prospects (`/prospects`, LeadsPipeline.tsx)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Page title | "Prospects" | Qualified prospects from analysis | Yes | None |
| Subtitle | "Qualified prospects matched to your ICP" | ICP-matched, not random | Yes — fit_score from Lead Hunter agent | None |
| Kanban stages | New → Qualified → Contacted → Won/Lost | Sales pipeline progression | Yes — manual transitions | None |
| Quick actions | Qualify, Contact, Won, Lost | Manual status changes | Yes — pure state transitions | None |
| Cold-start CTA | "Run Analysis" | Prospects come from analysis | Yes | None |
| Email verified badge | Green check / red alert | We verify email deliverability | Yes — DNS MX validation in Lead Enrichment agent (when enabled) | **Latent drift — see "Prospects Drift" below** |

**Prospects Drift**: The "email verified" badge is shown for ALL leads, but the verification happens via the Lead Enrichment agent, which is gated by `GTM_LAUNCH_MODE=v1` (its scheduler job is disabled in launch mode). So in launch mode, lead emails may show "needs verification" indefinitely without ever being checked. **Mitigation**: this is honest — needs-verification is an accurate state for unverified leads. Not a drift, but a known cold-start condition.

---

### Surface 6: Settings (`/settings`)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Page title | "Settings" | User-controllable settings | Yes — minimal at launch | None |
| Profile section | Read-only company info | Profile is informational | Yes | None |
| Display Preferences | Compact mode + timezone | Persistent UI prefs | Yes — localStorage | None |
| (Removed in launch) Integrations | n/a | n/a | Hidden | None (resolved) |
| (Removed in launch) Danger Zone | n/a | n/a | Hidden | None (resolved) |

**Settings status: clean.**

---

### Surface 7: ResultsPanel (component used during analysis)

| Aspect | What it says | What it implies | Actual behavior | Drift? |
|---|---|---|---|---|
| Executive summary | "Here's what we found" | A coherent summary of the analysis | Yes — generated by GTM Strategist | None |
| Leads section | "Qualified prospects" | These are real, vetted leads | Yes — fit-scored, source-tracked | None |
| Competitors section | "Competitive intelligence" | Real competitor analysis | Yes — Competitor Analyst output | None |
| Market signals | "Market trends" | Real-time market intelligence | Yes — Market Intelligence agent | None |
| Campaign templates | "Campaign ideas" | Pre-built templates customized to your business | Yes — Campaign Architect output | None |
| "Save to Your Daily Briefing" CTA | "Save and continue" | Persists this analysis | Yes — to /today | None |
| Export CTA | "Download Report (JSON)" | Full report available | Yes | None |

**ResultsPanel status: clean** after Cycle 2 CTA renames.

---

### Surface 8: Why Us (`/why-us`)

Static marketing content. Promise scope = whatever the page copy says. **Action item**: review the WhyUsPanel.tsx copy in Cycle 5 brand sweep. Defer until then because no Cycle 1–2 changes touched it.

---

### Surface 9: Marketing / Customer-Facing Story (canonical, in `naming-conventions.md`)

The canonical message is:

> **Hi Meet AI is the AI briefing room for your next GTM move.**
>
> Six AI specialists — market intelligence, competitors, customers, leads, campaigns, and a dedicated strategist — analyze your business using live data from EODHD financials, NewsAPI, Perplexity, and the Singapore company registry (ACRA). No generic AI guesses.
>
> A daily Today briefing built on real data — vertical benchmarks, qualified prospects matched to your ICP, and live market signals — refreshed continuously by our research pipeline.
>
> Artifacts you can act on — qualified prospects with fit scores, competitor battlecards, campaign plans, and an exportable GTM report. Outreach execution is available through our guided onboarding service when you're ready.
>
> **Get your first briefing in two minutes.**

Promise check:
- "AI specialists analyze your business using live data" — ✅ true
- "A daily Today briefing built on real data" — ✅ true (TodayPage delivers this)
- "Refreshed continuously by our research pipeline" — ⚠️ **partial drift**: the scheduler does run continuously, but the customer's own data only refreshes when they re-run an analysis. The market data (signals, benchmarks, articles) does refresh continuously. **Mitigation**: the wording is technically accurate (the research *pipeline* runs continuously) but ambiguous. Fix candidate: "Refreshed by our research pipeline daily" — no drift.
- "Artifacts you can act on" — ✅ true
- "Outreach execution is available through our guided onboarding service when you're ready" — ✅ true and explicit; sets expectations correctly

**Action**: queue the "refreshed continuously" wording for review in Cycle 5 brand sweep.

---

## Findings summary

| ID | Surface | Drift type | Severity | Status |
|---|---|---|---|---|
| PD-1 | Onboarding agent visualization | Latent — could imply autonomous work | Low | Acceptable; monitor marketing copy |
| PD-2 | Prospects "email verified" badge in cold start | Latent — verification depends on disabled scheduler job | Low | Honest by design (needs-verification = accurate state) |
| PD-3 | Marketing story "refreshed continuously" wording | Subtle ambiguity | Low | Cycle 5 brand sweep correction candidate |
| PD-4 | Why Us page copy not yet audited | Unknown | Unknown | Cycle 5 review |

**No high-severity promise drift found.** Cycle 2's discipline (CampaignsPage rename, attribution removal, briefing-room CTA language) closed the most significant drift candidates.

---

## How to use this document

1. **Before promoting a hidden surface to launch**: do a promise-scope audit row for it. If drift exists, fix the surface OR fix the doc (whichever matches reality better).
2. **Before adding a new launch surface**: write its row first. Make the promise explicit. Then build the surface to match.
3. **In each cycle's red-team**: re-read the audit. Look for drift introduced by changed copy or new affordances.
4. **Before launch**: every entry in the "Findings summary" must be either resolved or accepted as a known cold-start condition with a documented support response.
