# Hi Meet AI — Naming Conventions

**Canonical product name**: **Hi Meet AI**

## Canonical terms

| Context | Use | Don't use |
|---------|-----|-----------|
| Product name (customer-facing) | **Hi Meet AI** | GTM Advisor, Kairos, HiMeetAI, HiMeet.AI |
| Product positioning | "AI briefing room for your next GTM move" | "GTM intelligence platform", "AI sales automation" |
| Six analysis agents | "AI specialists" | "agents" (too technical), "bots" (too casual) |
| The process | "Briefing" or "Analysis" | "Workflow run", "Execution" (unless actually executing) |
| Campaign pages | "Campaign Plans" | "Campaigns" (implies running things) |
| Prospect pages | "Prospects" | "Leads" (legacy term; `/leads` now redirects to `/prospects`) |
| Market signal surfaces | "Signals" (internal) or "Industry updates" (customer-facing) | "Alerts", "Notifications" |
| Background automation | **Do not mention in v1 copy.** No "workforce", "automation", "autopilot" language. | "Digital workforce", "autonomous agents" |

## Branding rules

1. **Single brand voice**: every user-visible string says "Hi Meet AI" or nothing
2. **No mixed codenames**: codebase internals can say `gtm_*`, `GTMAdvisor*`, etc., but no customer-facing string may use these
3. **No execution overclaim**: copy MUST NOT imply autonomous outreach, automated sending, or "set and forget"
4. **Planning posture**: customer-facing CTAs describe what the user or the AI specialists do *to prepare*, not *to execute*

## Forbidden strings in customer-visible code

CI check (to add in Cycle 5): grep the following against `services/dashboard/src/**/*.{tsx,ts}` and fail if any are present in JSX strings or user-visible copy:

```
GTM Advisor
GTMAdvisor
HiMeetAI
HiMeet.AI
Kairos
autonomous
autopilot
workforce  (except in hidden/internal routes)
```

Internal code, import paths, environment variable names, database column names, and package identifiers are exempt — they don't reach the customer.

## Technical debt to resolve (Cycle 5)

| File | Current | Target |
|------|---------|--------|
| `services/dashboard/src/App.tsx:2` | "GTM Advisor Dashboard" | "Hi Meet AI Dashboard" (comment only) |
| `services/gateway/src/scheduler.py:3` | "GTM Advisor agents on a schedule" | "Hi Meet AI agents on a schedule" (comment only) |
| Page title (`<title>`) | Currently "GTM Advisor" (check index.html) | "Hi Meet AI" |
| App branding in Header | Current logo text | Hi Meet AI |
| Email from_name env var default | "GTM Advisor" (in routers/approvals.py) | Not customer-facing at v1 (execution-layer gated) — cosmetic fix in Cycle 5 |
| Content Studio disclaimer | (doesn't exist yet) | "Hi Meet AI — Beta. Review and edit before sending or posting." |
| Launch story docs | Mixed | Single canonical message in `docs/launch/customer-message-v1.md` |

## Customer-facing story (canonical)

Canonical v1 message (from Cycle 4 prior work):

> **Hi Meet AI is the AI briefing room for your next GTM move.**
>
> Six AI specialists — market intelligence, competitors, customers, leads, campaigns, and a dedicated strategist — analyze your business using live data from EODHD financials, NewsAPI, Perplexity, and the Singapore company registry (ACRA). No generic AI guesses.
>
> A daily Today briefing built on real data — vertical benchmarks, qualified prospects matched to your ICP, and live market signals — refreshed continuously by our research pipeline.
>
> Artifacts you can act on — qualified prospects with fit scores, competitor battlecards, campaign plans, and an exportable GTM report. Outreach execution is available through our guided onboarding service when you're ready.
>
> **Get your first briefing in two minutes.**

This is the version that ships to marketing, sales, and the dashboard empty-state copy. Any divergence from this story requires cycle review approval.
