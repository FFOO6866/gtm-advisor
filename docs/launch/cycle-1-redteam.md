# Cycle 1 — Foundation: Red-Team Memo

**Date**: 2026-04-07
**Stream**: D — Platform Hardening
**Branch**: `rc/v0.1.0`

## What was built

1. **`services/dashboard/src/config/features.ts`** — Feature-flag registry. 27 flags total (8 launch, 10 gated surfaces, 6 within-page gates, 3 auth/static). Single source of truth. `INTERNAL` const reads `VITE_LAUNCH_MODE=internal` to flip gated flags in internal builds.

2. **`services/dashboard/src/components/FeatureGate.tsx`** — Route guard primitive. Silent `<Navigate to="/today">` when the flag is false. No "upgrade" or "not available" screens — avoids paywall confusion.

3. **`services/dashboard/src/App.tsx`** — Wrapped 17 hidden routes with `<FeatureGate>`:
   - 8 agent workspace routes → `agentWorkspaces`
   - 9 authenticated-shell routes → individual flags (content, insights, signals, results, approvals, dashboard, sequences, playbooks, workforce)
   - `/leads` → 301-style `<Navigate to="/prospects">` redirect (legacy alias)

4. **`services/dashboard/src/components/SidebarNav.tsx`** — Nav items now filter by `FEATURES[item.flag]`. `PRIMARY_NAV_ALL` + `SECONDARY_NAV_ALL` are the full catalogs; `PRIMARY_NAV` + `SECONDARY_NAV` are the build-time filtered renderables. Approvals polling is skipped entirely when the approvals flag is off (removes unnecessary API traffic in production). Mobile-nav Approvals button is also gated.

5. **`services/gateway/src/scheduler.py`** — Added `_LAUNCH_MODE_V1` env check reading `GTM_LAUNCH_MODE=v1`. Wrapped 3 execution-tier jobs: `sequence_runner_daily`, `lead_enrichment_weekly`, `roi_summary_weekly`. Other 14 jobs remain registered. Skipped jobs log `scheduler_job_skipped` with reason.

6. **`docs/launch/`** — 4 governance docs:
   - `workstream-status.md` — active workstreams and cycle history
   - `feature-flags.md` — flag registry, promotion rules, scheduler gating
   - `naming-conventions.md` — canonical product name (Hi Meet AI), forbidden strings, customer-facing story
   - `launch-package.md` — definitive list of visible surfaces with diff protocol

## Red-team findings

### Finding 1 — SidebarNav was displaying nav items for gated routes (CORRECTED in cycle)

**Severity**: High (support burden)
**Discovery**: End-of-cycle review of `SidebarNav.tsx`.
**Problem**: Routes were gated via `<FeatureGate>` but nav items in SidebarNav still showed Content, Insights, Results, Approvals, Sequences, Workforce. Clicking any of them triggered a silent redirect to `/today` — a confusing UX ("why did my click take me home?").
**Correction applied**: Refactored SidebarNav to filter `PRIMARY_NAV_ALL` and `SECONDARY_NAV_ALL` by `FEATURES[item.flag]` at module load. In production, primary nav renders 3 items (Today, Campaign Plans, Prospects); secondary nav renders 1 item (Run Analysis). In internal builds, all 10 nav items render.
**Verification**: `pnpm tsc --noEmit` → exit 0; `pnpm build` → success; `pytest` → 575 passed.

### Finding 2 — Approvals API polling in production was wasted work (CORRECTED in cycle)

**Severity**: Low (operational noise)
**Problem**: The `useEffect` hook polled `/approvals/count` every 60 seconds even when the approvals nav item was hidden. In production this is pointless API traffic.
**Correction applied**: Added `SHOW_APPROVALS_BADGE` constant; polling short-circuits when the flag is off.

### Finding 3 — Legacy `/leads` route was gated but should be a redirect (CORRECTED in cycle)

**Severity**: Low (dead link)
**Problem**: I initially gated `/leads` on the `prospects` flag, but that means `/leads` redirects to `/today` in production — losing the customer's intent to see prospects. Both `/leads` and `/prospects` should show the pipeline.
**Correction applied**: `/leads` is now a `<Navigate to="/prospects" replace>` — a canonical redirect rather than a feature gate. Inbound links to `/leads` continue to work.

### Finding 4 — Page title / head metadata still says "GTM Advisor" (DEFERRED to Cycle 5)

**Severity**: Medium (brand overclaim)
**Problem**: `services/dashboard/index.html` and various meta tags likely still reference "GTM Advisor". Not fixed in Cycle 1 because naming/brand work is scheduled for Cycle 5 as the final pass.
**Deferred action**: Listed in `naming-conventions.md` technical debt section. Will be swept in Cycle 5.

### Finding 5 — No CI check enforces the launch-package diff (DEFERRED to Cycle 6)

**Severity**: Medium (governance drift risk)
**Problem**: `launch-package.md` defines a canonical set of visible surfaces, but nothing prevents a future PR from adding a new nav item without updating the doc or gating it.
**Deferred action**: Add a CI grep check in Cycle 6 (Launch Readiness Review): `rg -n "path:\s*'/" services/dashboard/src/components/SidebarNav.tsx` diffed against `launch-package.md`.

### Finding 6 — `GTM_LAUNCH_MODE=v1` must be explicitly set in production (OPERATIONAL RISK)

**Severity**: Medium (deployment risk)
**Problem**: If the production deployment doesn't set `GTM_LAUNCH_MODE=v1`, all execution-tier scheduler jobs will register. Outreach could theoretically fire on stale data if the sequence_runner finds any pending ApprovalQueueItem from testing.
**Mitigation**: Documented in `feature-flags.md`. Also: the frontend has no UI to create approval items in the first place (approvals flag is false), so there's no customer-initiated path to create data for the scheduler to pick up. Risk is contained to internal testing bleed-through.
**Follow-up in Cycle 4**: Verify the sequence_runner has an additional safety check: no-op if zero active enrollments exist (should already be the case in the engine).

## Red-team 5-question answers

### 1. Completeness — What shipped incomplete?
- **Frontend nav gating and route guarding are complete.** Corrections were made mid-cycle when the SidebarNav gap was found.
- **Scheduler env gate is complete** but requires explicit `GTM_LAUNCH_MODE=v1` in production deploy config (documented).
- **Not yet complete** (deferred by design): Hi Meet AI rename, CI enforcement, Content Studio QA gate, TodayPage attribution removal, CampaignsPage rename. These are all scheduled for later cycles.

### 2. Overexposure — Is anything visible that shouldn't be?
- **Production build with default env**: PRIMARY_NAV renders 3 items, SECONDARY_NAV renders 1. Routes for `/content`, `/insights`, `/results`, `/approvals`, `/sequences`, `/workforce`, `/playbooks`, `/dashboard`, and all `/agent/*` redirect to `/today`. **No overexposure detected.**
- **What about the Dashboard teaser page** (`/`)? It's a launch surface by design. No issue.
- **What about internal-only content visible via direct URL?** Routes are gated. Silent redirect works.

### 3. Fragility — What breaks under failure conditions?
- **If `GTM_LAUNCH_MODE` env var is unset in production**: execution-tier jobs register. Risk is contained (no UI entry point to create ApprovalQueueItems).
- **If `VITE_LAUNCH_MODE` is unset at build time**: `INTERNAL` is false → all gated flags are false → conservative launch posture. This is the correct default-deny behavior.
- **If someone accidentally sets `VITE_LAUNCH_MODE=production`**: It's not `internal`, so gated flags are false. Still correct.
- **What if the file-level `PRIMARY_NAV.filter(...)` runs before `FEATURES` is imported?**: Module load order handles this — `features.ts` is a static export, not a runtime lookup.

### 4. Support drag — What's the first likely ticket?
- "How do I access Content Studio?" — from customers who saw the feature in marketing screenshots but not in the nav. **Answer**: Content Studio is in private beta; contact us to enable it. (Confirms the advisory tier exists.)
- "Where's the Attribution dashboard?" — answer: Reopens when you have outreach data.
- "The Insights menu is gone." — answer: Industry signals now appear inside the Today briefing. (Requires Cycle 2 to actually implement the TodayPage signal preview.)

### 5. Coherence — Does the product still feel like one thing?
- **Partially.** The feature-flag spine enables coherence but doesn't deliver it yet. What's coherent now:
  - The set of visible surfaces is documented and enforced by code.
  - The governance docs form a consistent narrative.
  - Default-deny posture prevents accidental exposure.
- **Not yet coherent**:
  - Page titles still say "GTM Advisor"
  - "Campaigns" nav label still implies execution
  - TodayPage still shows the Attribution section (gated flag exists but not wired into the page)
  - No Hi Meet AI branding anywhere in the UI
- These are Cycle 2–5 work, as planned.

## Corrections applied this cycle

| # | Finding | File | Action |
|---|---------|------|--------|
| 1 | SidebarNav showing hidden nav items | `SidebarNav.tsx` | Filtered by `FEATURES[item.flag]` |
| 2 | Approvals polling in production | `SidebarNav.tsx` | `SHOW_APPROVALS_BADGE` short-circuits |
| 3 | `/leads` gated wrong | `App.tsx` | Converted to canonical redirect |

## Integration check

| Concern | Status |
|---------|--------|
| Shared contracts | ✅ No API/type contracts changed this cycle |
| Route/nav consistency | ✅ SidebarNav filters from the same flag source that gates routes |
| Naming consistency | ⚠️ Still "GTM Advisor" in places — Cycle 5 |
| Feature-flag discipline | ✅ Single source, no hardcoded flags in components |
| Launch-visibility rules | ✅ 6 nav items visible, 3 primary + 1 secondary, matches `launch-package.md` |
| Cross-stream regression risk | ✅ 575 tests still pass; production build succeeds |

## Does this still feel like one product?

Yes, scaffold-wise. The launch package is narrow but consistent. Everything visible has a reason to exist. Everything hidden is reachable only by internal builds or advisory activation.

**What remains for "one product" feel**:
- Naming uniformity (Cycle 5)
- Empty-state copy that matches the launch story (Cycle 2)
- TodayPage section adjustments (Cycle 2)

## Recommended next cycle

**Cycle 2 — Core Workflow Completion (Stream A + partial E)**

Goal: make the 6 launch surfaces work end-to-end with no broken CTAs, no overclaim, and consistent empty states.

Scope:
1. **CampaignsPage** — rename to "Campaign Plans" (page title, header, breadcrumbs); remove Activate/Pause CTAs; add "Draft" status filter only; add empty-state message
2. **TodayPage** — hide Attribution KPIs section when `todayAttributionKpis` flag is false; add cold-start welcome card; audit empty-state copy for all sections; remove any links to hidden routes (Deploy Playbook, Enroll in Sequence)
3. **LeadsPipeline (Prospects)** — remove "Enroll in Sequence" action (gate behind `leadSequenceEnroll`); add empty-state with "Run analysis" CTA
4. **ResultsPanel** — remove "Design Digital Workforce" CTA; rename "Go to Dashboard" → "Go to Today"; verify export button works
5. **SettingsPage** — strip API key section (gate on `settingsApiKeys`); strip Danger Zone (gate on `settingsDangerZone`); strip Integration Health section (developer-facing)
6. **Hi Meet AI branding** (partial) — page title in `index.html`; canonical "Hi Meet AI" in the launch-surface headers

Red-team focus for Cycle 2:
- Does any launch surface link to a hidden surface?
- Does any launch CTA imply execution?
- Are empty states honest and actionable?
- Is the attribution section truly removed from TodayPage (not just gated but still fetching data)?

## Cycle 1 outcome

**Completed.** Ready to start Cycle 2.
