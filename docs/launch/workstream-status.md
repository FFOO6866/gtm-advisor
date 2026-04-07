# Hi Meet AI — v1 Workstream Status

**Branch**: `rc/v0.1.0` (v1 development trunk)
**Last updated**: Cycle 4 (Execution Layer Verification)

## Workstream overview

| Stream | Focus | Status |
|--------|-------|--------|
| **A — Core Workflows** | Onboarding, Analysis, Results, TodayPage, Prospects, Campaign Plans, Settings | Complete for launch surfaces (Cycle 2); LD-1 fragility resolved (Cycle 3) |
| **B — Feature Completion** | Content Studio, Signals, Playbooks, Battlecards, Exports | **Polish complete** (Cycle 3); QA gate doc written; Content Studio stays Hidden by default pending 57/57 gate execution |
| **C — Execution Layer** | Sequences, Approvals, Outreach, CRM Sync, Webhooks, Workforce, Attribution | Verified Cycle 4 (policy-to-endpoint + scheduler coverage matrix, 1 defense-in-depth fix landed, 4 watch items + 2 debt items catalogued) |
| **D — Platform Hardening** | Feature flags, Route guards, Tests, CI/CD, Logging, Deployment, Runbooks | Cycle 1 foundation complete; dangerous-action policy formalized (Cycle 3); ongoing |
| **E — Brand & UX Coherence** | Hi Meet AI rename, CTA language, empty states, launch story | Partial passes in Cycle 2 + 3 (touched files); full sweep in Cycle 5 |

## Cycle history

### Cycle 1 — Foundation (Stream D)
- Created `services/dashboard/src/config/features.ts` — feature-flag registry
- Created `services/dashboard/src/components/FeatureGate.tsx` — route guard primitive
- Wrapped 17 hidden routes in `App.tsx` with `<FeatureGate>`
- Added `GTM_LAUNCH_MODE` env gate in `scheduler.py` for 3 execution-tier jobs
- Created `docs/launch/` governance skeleton (this file, feature-flags.md, naming-conventions.md, launch-package.md)

**Outcome**: Build-vs-expose separation is now enforced. Internal builds see everything; production builds see the 6-surface launch package.

### Cycle 2 — Core Workflow Completion + Two-Layer Defense (Streams A, D, E partial)
- **Backend deny dependency** (`services/gateway/src/auth/launch_mode.py`): 404s 5 execution-tier endpoints when `GTM_LAUNCH_MODE=v1`
  - `POST /companies/{id}/approvals/{id}/approve`
  - `POST /companies/{id}/approvals/{id}/reject`
  - `POST /companies/{id}/approvals/bulk-approve`
  - `POST /companies/{id}/sequences/activate-playbook`
  - `POST /companies/{id}/workforce/{id}/execute`
- **Runtime safety in sequence_runner**: call-time `is_launch_mode_v1()` check prevents accidental execution even if job is registered
- **TodayPage launch-critical ACs**: attribution fetch gated at `useEffect` (no network request in launch mode); all SectionHeader actions to `/insights` gated; pending approvals block gated; "Welcome to GTM Advisor" → "Welcome to Hi Meet AI"
- **CampaignsPage**: renamed "Campaigns" → "Campaign Plans"; "New Campaign" → "New Plan"; Activate/Pause CTAs gated behind `campaignActivation`; "View Content" gated behind `contentBeta`; subtitle "Plan and document your GTM campaigns"
- **LeadsPipeline**: renamed "Lead Pipeline" → "Prospects"; cold-start empty state with "Run Analysis" CTA; docstring corrected (no more reference to Enroll action)
- **ResultsPanel**: "Unlock Full Dashboard" → "Save to Your Daily Briefing"; "Go to Dashboard" → "Open Today's Briefing"
- **SettingsPage**: Integrations Status section gated behind `settingsApiKeys`; Danger Zone gated behind `settingsDangerZone`; launch posture is Profile + Display Preferences only
- **`index.html`**: page title "GTM Advisor" → "Hi Meet AI — AI Briefing Room for GTM"; meta description updated
- **Test coverage**: 6 new tests in `tests/unit/test_launch_mode_deny.py` verifying the backend dependency (env=unset/dev/v1/V1/case-insensitive/re-import semantics)

**Outcome**: The 6 launch surfaces work end-to-end with no hidden-surface links, no execution-implying CTAs, and honest empty states. Backend + frontend now form a two-layer defense for dangerous actions. Touched launch-facing files carry "Hi Meet AI" branding. Full suite: 581 pytest pass, TypeScript clean, Vite production build successful (642KB bundle, down 3KB from Cycle 1 via dead-code elimination on gated branches).

### Cycle 3 — Tier-2 Surface Polish + Program Refinements (Streams B + D + E partial)

**Program refinements applied (4)**:
1. **Dangerous-action policy formalized** — `docs/launch/dangerous-action-policy.md` defines the 5-clause rule. Audit found `reject_item` was inconsistently protected. Unprotected to align with policy.
2. **TodayPage `Promise.all` fragility resolved** — refactored from positional destructuring to named-key `fetches` object. Adding new fetches now requires editing exactly 2 places. LD-1 closed.
3. **Promise-scope audit** — `docs/launch/promise-scope-audit.md` tracks visibility scope vs. promise scope per surface. 4 latent drift items identified, all classified as low severity or already resolved.
4. **Content Studio QA gate strengthened** — `docs/launch/content-studio-qa.md` defines the 7-criterion gate (specificity, market grounding, ready-to-use, tone fidelity, **differentiation**, **brand fidelity**, **vertical coherence**). Sign-off requires 57/57 across 9 outputs in 3 verticals + 2 reviewers. Default outcome: stay Hidden.

**Tier-2 surface work**:
- **ContentPage**: Beta badge added to header + disclaimer subtitle ("Beta — AI drafts. Review and edit before sending or posting.")
- **PlaybooksPage**: Converted from "playbook browse with disabled Activate" to read-only **methodology library**. Header renamed "GTM Playbooks" → "GTM Methodology"; Activate button replaced with "Available through guided onboarding" footer text; navigate import removed; icon updated to BookOpen.
- **SignalsFeed**: "Deploy Playbook" → "Plan Campaign from Signal" (removes execution implication; navigation target unchanged at `/campaigns?signal=...`)
- **Exports + battlecards**: verified stable — endpoints handle empty-data conditions gracefully; no code changes needed

**Launch debt register added**: 9 items classified by risk/severity/cycle. LD-1 closed in this cycle; LD-9 (campaigns activate watch item) added.

**Governance docs created/updated**:
- NEW: `dangerous-action-policy.md`, `promise-scope-audit.md`, `content-studio-qa.md`
- UPDATED: `feature-flags.md` (Protected Endpoints table refined per policy), `launch-package.md` (Promise Scope reference added), `naming-conventions.md` (no changes needed), `workstream-status.md` (Cycle 3 history + Launch Debt Register)

**Verification**: 581 pytest pass (no new tests added in Cycle 3 — refinements were doc + existing-feature changes), ruff clean on touched files, TypeScript --noEmit clean, Vite production build 642.99KB.

### Cycle 4 — Execution Layer Verification (Stream C)

**Three program constraints incorporated** (`cycle-4-incorporation-plan.md`):
1. **Verification-first rule** — no dashboard changes, no new endpoints, no flag promotions. Only safety fixes, runtime gates, doc updates, and regression tests allowed.
2. **Policy-to-endpoint coverage matrix** — every execution-capable HTTP route AND scheduler job inventoried and classified (protected / exempt / watch / inconsistent).
3. **Qualitative override on numeric gates** — Content Studio QA gate strengthened: 57/57 is a floor, not a ceiling; any reviewer may veto on qualitative grounds.

**Deliverables**:
- NEW `docs/launch/cycle-4-incorporation-plan.md` — how the 3 constraints are absorbed
- NEW `docs/launch/execution-verification.md` — verification plan + HTTP coverage matrix (~40 routes) + scheduler coverage matrix (18 jobs) + findings
- NEW `docs/launch/cycle-4-redteam.md` — red-team memo with self-challenge revision
- UPDATED `docs/launch/dangerous-action-policy.md` — scheduler coverage section + Cycle 4 watch-list re-audit
- UPDATED `docs/launch/feature-flags.md` — scheduler gating table adds the auto-enroll runtime gate
- UPDATED `docs/launch/content-studio-qa.md` — "Qualitative override" section (Constraint 3)
- UPDATED `services/gateway/src/scheduler.py` — Finding F-1 fix (see below)
- UPDATED `services/gateway/src/auth/launch_mode.py` — docstring cites scheduler gates + execution-verification.md
- UPDATED `tests/unit/test_launch_mode_deny.py` — `TestSchedulerAutoEnrollGate` regression tests

**Findings** (full detail in `execution-verification.md`):
- **F-1 (Medium, fixed)** — `_run_signal_monitor_all_active` called `auto_enroll_from_signals` unconditionally every hour. Creating `SequenceEnrollment` rows is a cascading state transition per policy clause 3. Added call-time `is_launch_mode_v1()` gate around the embedded call only; signal monitor itself still runs. Regression test asserts the gate order.
- **F-2 (Low, no action)** — `PATCH /workforce/{id}/approve` is a state-only transition that enabled the F-1 cascade. After F-1, the cascade is broken at its source; `/approve` correctly remains exempt (protecting it would be an aesthetic fix, regressing Cycle 3's "protect what is dangerous, leave the rest alone" discipline).
- **F-3 (Low, deferred → LD-10)** — `_run_lead_enrichment_all` and `_run_weekly_roi_summary` have registration-only gating; adding belt-and-suspenders runtime checks is a Cycle 5 polish item. Neither has an external effect today.
- **F-4 (Low, deferred → LD-11)** — `/agents/{name}/run` is implicitly gated by the narrow agent registry (6 analysis agents only). Adding a registry-lock test prevents a future bypass if execution agents are added.
- **F-5 (Pass)** — Webhook handler `POST /api/v1/webhooks/sendgrid` verified to only pause, record, and log; no send path exists. Intentional exemption stands.
- **F-6 (Pass — LD-9 watch re-audit)** — `POST /campaigns/{id}/activate` re-verified as state-only. Grep for `CampaignStatus.ACTIVE` returns only the setter; no consumers. Watch item remains.
- **F-7 (Pass)** — `POST /campaigns/generate-content` uses LLM provider; platform-billed, no external communication.

**Launch-exposure delta**: none. No frontend changes. No new endpoints. No flag promotions.
**Launch-behavior delta**: strictly narrowed — in `GTM_LAUNCH_MODE=v1`, signal monitor no longer creates enrollments.
**Launch-promise delta**: none.

**Verification**: pytest + ruff + TypeScript + Vite build all pass (numbers recorded in `cycle-4-redteam.md`). No new tests touching frontend or product surfaces; the new tests live entirely in the launch-mode regression suite.

## Cycle plan

| # | Name | Streams | Goal |
|---|------|---------|------|
| 1 | Foundation | D | Feature-flag spine, route guards, docs skeleton |
| 2 | Core Workflow Completion | A + E(partial) | Lock the 6 launch surfaces end-to-end |
| 3 | Tier-2 Surface Completion | B | Gate Content Studio, Signals, Playbooks, Settings internals |
| 4 | Execution Layer Verification | C | Trace sequence → approval → outreach → attribution |
| 5 | Brand & UX Coherence | E (full) | Hi Meet AI rename, launch-story alignment |
| 6 | Launch Readiness Review | — | Hostile reviewer simulation, final go/no-go |

## Launch debt register

Tracked launch debt — items that are NOT blockers but carry future risk and must be classified, owned, and scheduled. Each entry has:

- **Risk**: blocker / non-blocker / latent
- **Severity**: high / medium / low
- **Cycle for fix**: which cycle owns the resolution

| ID | Item | Risk | Severity | Cycle | Notes |
|---|---|---|---|---|---|
| LD-1 | TodayPage `Promise.all` positional destructuring (8 fetches) | Non-blocker | Medium | **Cycle 3 setup** | ✅ **Resolved Cycle 3 setup**. Refactored to named `fetches` object; `Promise.all(Object.values(fetches))` parallelizes; setters await each by name. Adding a new fetch now requires editing exactly 2 places (the object + the setter block). |
| LD-2 | `documents.py:301` ruff B007 unused loop variable `family` | Non-blocker | Low | Cycle 5 | Pre-existing lint error unrelated to launch work. Sweep with full lint pass in Cycle 5. |
| LD-3 | `App.tsx` module docstring still says "GTM Advisor Dashboard" | Non-blocker | Low | Cycle 5 | Internal-only string (not customer-visible). Sweep with full naming pass. |
| LD-4 | `scheduler.py` module docstring still says "GTM Advisor agents on a schedule" | Non-blocker | Low | Cycle 5 | Internal-only string. Sweep with full naming pass. |
| LD-5 | `WORKFORCE_OUTREACH_FROM_NAME` env var default is "GTM Advisor" | Non-blocker | Low | Cycle 5 | Cosmetic; execution layer is gated so this never reaches a customer at v1. |
| LD-6 | SidebarNav workspace header subtitle reads "GTM Dashboard" | Non-blocker | Low | Cycle 5 | Customer-visible but minor; full sweep covers it. |
| LD-7 | Bundle size 642KB (Vite warns >500KB) | Non-blocker | Low | Post-launch | Code-splitting candidate. Not a launch blocker — gzip is 174KB. |
| LD-8 | TodayPage `attribution` state variable still declared even when feature is gated | Non-blocker | Low | Cycle 3 setup | Cosmetic — `setAttribution(null)` in launch mode is harmless but indicates dead state. Acceptable. |
| LD-9 | Backend `campaigns/{id}/activate` endpoint is unprotected (currently safe) | Latent | Medium | **Cycle 4 re-audit: still safe; carry forward** | Cycle 4 grep confirmed no consumers of `CampaignStatus.ACTIVE`. Still a watch item for any future wiring. See `execution-verification.md` finding F-6. |
| LD-10 | `_run_lead_enrichment_all` and `_run_weekly_roi_summary` lack belt-and-suspenders runtime `is_launch_mode_v1()` checks | Non-blocker | Low | Cycle 5 | Registration gate is sufficient today (neither job has external effect). Runtime gate would be consistency with `_run_sequence_runner`. Must be added if the ROI summary TODO at `scheduler.py:537` (send summary email) is ever implemented. See Cycle 4 finding F-3. |
| LD-11 | `/agents/{name}/run` and `/companies/{id}/agents/{id}/run` are implicitly gated by narrow registry; no test locks the registry | Latent | Medium | Cycle 5 or 6 | Current registry (`agents_registry.py`) exposes only the 6 analysis agents. A single-line test that asserts the exact registry contents would prevent a future bypass if execution agents are added. See Cycle 4 finding F-4. |

**Adding new debt**: when a cycle red-team identifies a deferred item, add it to this register with classification + target cycle. Do not let "deferred" items disappear into casual notes.

**Closing debt**: when an item is resolved, mark it ✅ and link to the cycle red-team where it closed. Do not delete entries — preserve the history.

## Governance rules (invariant across cycles)

1. **Default deny**: new surfaces are Hidden unless they pass the Launch gate
2. **No self-promotion**: classification is decided in red-team review, not by feature authors
3. **Single source of truth**: `docs/launch/feature-flags.md` is canonical for flag state
4. **Naming gate**: no surface is promoted until all user-visible copy says "Hi Meet AI"
5. **Red-team mandatory**: every cycle ends with a 5-question review (completeness, overexposure, fragility, support drag, coherence)
6. **Doc-sync discipline (added in Cycle 2)**: a cycle is not complete until the governance docs reflect the code state. Specifically:
   - If a cycle changes **feature flags**, `feature-flags.md` is updated in the same cycle
   - If a cycle changes **visible nav items or routes**, `launch-package.md` is updated in the same cycle
   - If a cycle changes **user-facing strings** on launch surfaces, `naming-conventions.md` technical-debt section is updated in the same cycle
   - If a cycle changes **backend protection** (new protected endpoints), the module docstring in `launch_mode.py` AND `feature-flags.md` are updated in the same cycle
   - The cycle red-team memo verifies this sync; failure to sync blocks cycle completion
7. **No legacy-naming spread (added in Cycle 2)**: any file touched in a cycle must not introduce new user-facing "GTM Advisor" strings on launch-visible surfaces. Existing strings in touched files should be corrected where they are user-visible. Full sweep remains in Cycle 5.
8. **Two-layer defense (added in Cycle 2)**: dangerous actions (sending email, enrolling in sequences, triggering execution runs) must be protected at the backend in addition to frontend hiding. Use `require_execution_enabled` dependency.
