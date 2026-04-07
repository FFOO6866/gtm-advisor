# Hi Meet AI — v1 Workstream Status

**Branch**: `rc/v0.1.0` (v1 development trunk)
**Last updated**: Cycle 2 (Core Workflow Completion + Backend Two-Layer Defense)

## Workstream overview

| Stream | Focus | Status |
|--------|-------|--------|
| **A — Core Workflows** | Onboarding, Analysis, Results, TodayPage, Prospects, Campaign Plans, Settings | **Complete for launch surfaces** (Cycle 2) |
| **B — Feature Completion** | Content Studio, Signals, Playbooks, Battlecards, Exports | Not started (Cycle 3) |
| **C — Execution Layer** | Sequences, Approvals, Outreach, CRM Sync, Webhooks, Workforce, Attribution | Backend deny dependency in place (Cycle 2); verification in Cycle 4 |
| **D — Platform Hardening** | Feature flags, Route guards, Tests, CI/CD, Logging, Deployment, Runbooks | Cycle 1 foundation complete; ongoing |
| **E — Brand & UX Coherence** | Hi Meet AI rename, CTA language, empty states, launch story | Partial pass in Cycle 2 (touched files); full sweep in Cycle 5 |

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

## Cycle plan

| # | Name | Streams | Goal |
|---|------|---------|------|
| 1 | Foundation | D | Feature-flag spine, route guards, docs skeleton |
| 2 | Core Workflow Completion | A + E(partial) | Lock the 6 launch surfaces end-to-end |
| 3 | Tier-2 Surface Completion | B | Gate Content Studio, Signals, Playbooks, Settings internals |
| 4 | Execution Layer Verification | C | Trace sequence → approval → outreach → attribution |
| 5 | Brand & UX Coherence | E (full) | Hi Meet AI rename, launch-story alignment |
| 6 | Launch Readiness Review | — | Hostile reviewer simulation, final go/no-go |

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
