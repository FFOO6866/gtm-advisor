# Cycle 2 — Core Workflow Completion + Two-Layer Defense: Red-Team Memo

**Date**: 2026-04-07
**Streams**: A (Core Workflows), D (Platform Hardening continuation), E partial (Brand)
**Branch**: `rc/v0.1.0`
**Entry state**: `60be519` (cycle-1-complete tag)

## Refinements applied from program-level review

1. **Backend two-layer defense** — `require_execution_enabled` dependency protects 5 execution-tier endpoints at the backend; matches frontend silent-redirect posture (returns 404 Not Found)
2. **Runtime safety check** — `_run_sequence_runner` re-checks `is_launch_mode_v1()` at call time, not just at job registration
3. **Doc-sync discipline** — governance rule added to `workstream-status.md`; this cycle updated `feature-flags.md`, `launch-package.md`, and `naming-conventions.md` in the same cycle as code changes
4. **TodayPage launch-critical ACs** — attribution fetch gated at `useEffect` level (no network request in launch mode), all hidden-surface links gated, cold-start welcome card uses Hi Meet AI branding
5. **No legacy-naming spread** — every touched launch-facing file had user-visible "GTM Advisor" strings corrected in the same cycle

## What was built

### Backend (Stream C partial + D)
- `services/gateway/src/auth/launch_mode.py` — `require_execution_enabled` FastAPI dependency + `is_launch_mode_v1()` helper
- `routers/approvals.py` — 3 endpoints protected (approve, reject, bulk-approve)
- `routers/sequences.py` — 1 endpoint protected (activate-playbook)
- `routers/workforce.py` — 1 endpoint protected (execute)
- `scheduler.py::_run_sequence_runner` — call-time safety check
- `tests/unit/test_launch_mode_deny.py` — 6 regression tests covering env states, case-insensitivity, reimport semantics, and endpoint inventory

### Frontend (Stream A)
- **TodayPage.tsx** (1,580+ lines): attribution fetch gated at `useEffect` via `Promise.resolve(null)` replacement; `PerformanceSummary` conditionally rendered on `FEATURES.todayAttributionKpis`; 3 `SectionHeader` actions to `/insights` gated via undefined callback; pending approvals block gated; urgent signal click gated; "Welcome to GTM Advisor" → "Welcome to Hi Meet AI"
- **CampaignsPage.tsx**: "Campaigns" → "Campaign Plans" (header, subtitle, empty state); "New Campaign" → "New Plan"; Activate/Pause CTAs gated; View Content CTA gated on `contentBeta`; subtitle "Plan and document your GTM campaigns"
- **LeadsPipeline.tsx**: "Lead Pipeline" → "Prospects" (header and count label); cold-start welcome card with Run Analysis CTA; docstring reference to Enroll removed; "Users" icon import added
- **ResultsPanel.tsx**: auth + unauth CTAs updated to briefing-room language
- **SettingsPage.tsx**: Integrations Status gated on `settingsApiKeys`; Danger Zone gated on `settingsDangerZone`; launch posture is Profile + Display Preferences only
- **index.html**: page title + meta description updated to Hi Meet AI

### Documentation (Stream D)
- `workstream-status.md` — Cycle 2 section added; governance rules 6, 7, 8 added (doc-sync, no-legacy-spread, two-layer defense)
- `feature-flags.md` — Two-Layer Defense section added; Protected Backend Endpoints table added
- `launch-package.md` — nav diagram updated with Cycle 2 renames
- `naming-conventions.md` — technical-debt section split into "Resolved in Cycle 2" and "Still deferred to Cycle 5"
- `cycle-2-redteam.md` (this file)

## Red-team 5-question audit

### 1. Completeness — What shipped incomplete?

- **TodayPage ACs all satisfied.** Verified: grep for hidden-route navigate calls returns only gated/safe results. Attribution not fetched (confirmed via code path inspection). No execution-implying CTAs. Cold-start card exists. Empty states present.
- **CampaignsPage Activate/Pause stripped.** Verified: `handleActivate`/`handlePause` functions still exist in code but their call sites are gated. (Dead code kept to avoid structural churn; will be removed in Cycle 5 or left for internal builds.)
- **SettingsPage strip** complete for Integrations + Danger Zone. Profile + Display Preferences remain.
- **Backend protection** applied to the 5 most dangerous endpoints. Pause/resume enrollment and webhooks deliberately unprotected (state-only transitions; advisory customers need them).

### 2. Overexposure — Is anything visible that shouldn't be?

- **Regression scan**: production build (default env) renders 3 primary + 1 secondary nav items, matches the launch package.
- **TodayPage**: verified no hidden-surface navigation remains at run-time. "Deploy Playbook" from signals doesn't exist in TodayPage (it's in SignalsFeed, which is gated).
- **CampaignsPage**: the "View Content" button would have leaked into `/content` (hidden). Now gated.
- **Finding (corrected in cycle)**: `/leads` was gated on `prospects` flag in Cycle 1; that meant production `/leads` would redirect to `/today`. I caught this in Cycle 1 red-team and converted to a canonical `<Navigate to="/prospects">`. Verified still correct after Cycle 2.

### 3. Fragility — What breaks under failure conditions?

- **Backend deny dependency**: if `GTM_LAUNCH_MODE` is unset in production, all endpoints are callable. This is documented as an operational risk in `feature-flags.md`. Mitigated by: (a) `GTM_LAUNCH_MODE=v1` is required in the production deployment script, (b) frontend has no UI to reach these endpoints anyway.
- **Test import-reload semantics**: the `test_launch_mode_deny.py` tests use `importlib.reload(launch_mode)` to force re-evaluation of the env var. This works but is a fragile pattern — any test-order dependency could see stale state. Mitigation: each test reloads before asserting. Not a fragility for production.
- **TodayPage Promise.all destructuring**: the attribution and approvals entries are in fixed positions. If any parallel fetch is added/removed, the destructuring breaks. This is a latent fragility in TodayPage's code style, not introduced by Cycle 2 but not fixed either. Deferred.

### 4. Support drag — What's the first likely ticket?

- **"My Campaign Plans page doesn't have an Activate button."** — Answer: Campaign Plans is a planning tool in v1. Execution is available through guided onboarding. Documented in `naming-conventions.md` launch story.
- **"Why is the Settings page so short?"** — Answer: Profile and Display Preferences are the primary v1 settings. API key management is handled server-side.
- **"Where are my attribution KPIs?"** — Answer: Attribution dashboards activate once outreach is enabled via advisory onboarding.
- **"Can I bulk approve outreach via the API?"** — Answer: 404. Execution surfaces are not available in v1. This is the CORRECT support answer — the 404 is intentional.

### 5. Coherence — Does the product still feel like one thing?

- **Yes, more than Cycle 1.** Launch surfaces now share:
  - Hi Meet AI branding in customer-visible entry points (TodayPage cold-start, index.html title)
  - Briefing-room language in ResultsPanel CTAs
  - Planning posture on Campaign Plans (no execution, no Activate)
  - Honest empty states on Prospects
  - Consistent launch exposure across frontend (FeatureGate) and backend (require_execution_enabled)
- **Still not fully coherent**:
  - SidebarNav workspace header still says "GTM Dashboard" subtitle — deferred to Cycle 5
  - Module-level docstrings in App.tsx and scheduler.py still say "GTM Advisor" — deferred to Cycle 5
  - Content Studio QA gate not yet defined — deferred to Cycle 3
  - Signals Feed hidden-mode preview inside TodayPage not yet styled as a preview (it's a full section) — Cycle 3 polish

## Corrections applied during Cycle 2

| # | Finding | Action |
|---|---------|--------|
| 1 | Test file had unused imports (`os`, `patch`) | Ruff auto-fix |
| 2 | Test file had unsorted local imports | Ruff auto-fix |
| 3 | Legacy "Enroll in sequence" docstring in LeadsPipeline | Corrected to describe the actual (manual status) actions |
| 4 | CampaignsPage's "View Content" CTA targeted `/content` (hidden) | Gated behind `FEATURES.contentBeta` |
| 5 | Pre-existing ruff error in `documents.py` (`B007`: unused `family` loop var) | **Not fixed** — pre-existing, unrelated to Cycle 2 scope. Logged for Cycle 5 sweep. |

## Doc-sync check (new Cycle 2 discipline)

| Change in code | Doc updated? | File |
|---------------|--------------|------|
| Backend deny dependency added | ✅ | `feature-flags.md` — Two-Layer Defense section, Protected Endpoints table |
| 5 endpoints newly protected | ✅ | `feature-flags.md` — Protected Endpoints table; `launch_mode.py` docstring |
| Frontend nav labels renamed (Campaigns→Plans, Lead→Prospects) | ✅ | `launch-package.md` — nav diagram |
| Hi Meet AI branding applied to 6 files | ✅ | `naming-conventions.md` — Resolved in Cycle 2 section |
| Governance rules 6, 7, 8 added (doc-sync, no-legacy-spread, two-layer defense) | ✅ | `workstream-status.md` — Governance rules section |

**All doc-sync items verified before cycle close.**

## Integration check

| Concern | Status |
|---------|--------|
| Shared contracts (API types) | ✅ No API/type contracts changed |
| Route/nav consistency | ✅ SidebarNav filters match App.tsx gating |
| Naming consistency on launch surfaces | ✅ All touched files use "Hi Meet AI" where user-visible |
| Feature-flag discipline | ✅ No hardcoded flag checks; all via `FEATURES[...]` |
| Backend protection matches frontend hiding | ✅ 5 execution endpoints 404 when launch mode; frontend hides the UI that would call them |
| Cross-stream regression risk | ✅ 581 Python tests pass; TypeScript clean; Vite production build succeeds |
| Bundle size | ✅ 642KB (down 3KB from Cycle 1 via dead-code elimination) |

## Does this still feel like one product?

**Closer to yes.** Launch surfaces now share a coherent voice: Hi Meet AI, briefing room, planning (not execution), honest empty states. The backend defends what the frontend hides. The feature-flag spine from Cycle 1 actually governs real behavior in Cycle 2.

Still missing for full coherence:
- Full brand sweep (Cycle 5)
- Content Studio QA gate decision (Cycle 3)
- End-to-end trace of the execution layer with protection verified (Cycle 4)

## What would a hostile launch reviewer attack first?

"Your backend still accepts POST /sequences/activate-playbook — I can create enrollments by hitting the API directly."
**Response**: In v1 launch mode (`GTM_LAUNCH_MODE=v1`), that endpoint returns `404 Not Found`. Verify: `curl -X POST https://api.himeet.ai/.../sequences/activate-playbook` returns 404.

"Your TodayPage is making a network request to `/attribution/summary` even though you claim attribution is hidden."
**Response**: The fetch is conditional on `FEATURES.todayAttributionKpis`. In production builds, the request is replaced with `Promise.resolve(null)` at the useEffect level. Verify: open DevTools Network tab on `/today` — no `/attribution/summary` call.

## What should still remain hidden even if technically complete?

No changes from Cycle 1. The hidden/gated list is stable.

## Recommended next cycle

**Cycle 3 — Tier-2 Surface Completion (Stream B)**

Scope:
1. **Content Studio QA gate** — define the 3-vertical 5-criteria promotion protocol in `docs/launch/content-studio-qa.md`; add Beta disclaimer banner to `ContentPage.tsx` (rendered when flag is true, which it is not by default); decision: execute the QA gate or leave hidden for v1
2. **Signals Feed polish** — when re-enabled, styling fixes, empty-state copy, "Deploy Playbook" CTA removal
3. **Playbooks methodology** — convert playbook browse to methodology documentation (read-only, no Activate CTA, clearly labeled as upcoming)
4. **Competitor Battlecards** — light hardening pass; currently functional but never stress-tested
5. **Exports** — verify JSON export payload is stable; add empty-state handling
6. **Backend** — no changes expected (all protection already in place from Cycle 2)

Red-team focus for Cycle 3:
- Does any Tier-2 surface leak into launch by accident?
- Is Content Studio output reliably better than a 2-minute ChatGPT prompt? (QA gate)
- Do exports include hidden-mode data that would confuse customers?

**Go criteria for Cycle 3 start**: Cycle 2 is complete with all ACs satisfied and doc-sync verified. ✅ Ready to proceed.
