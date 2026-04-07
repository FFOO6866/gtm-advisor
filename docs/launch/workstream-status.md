# Hi Meet AI — v1 Workstream Status

**Branch**: `rc/v0.1.0` (v1 development trunk)
**Last updated**: Cycle 1 (Foundation)

## Workstream overview

| Stream | Focus | Status |
|--------|-------|--------|
| **A — Core Workflows** | Onboarding, Analysis, Results, TodayPage, Prospects, Campaign Plans | Not started (Cycle 2) |
| **B — Feature Completion** | Content Studio, Signals, Playbooks, Settings strip, Battlecards, Exports | Not started (Cycle 3) |
| **C — Execution Layer** | Sequences, Approvals, Outreach, CRM Sync, Webhooks, Workforce, Attribution | Not started (Cycle 4) |
| **D — Platform Hardening** | Feature flags, Route guards, Tests, CI/CD, Logging, Deployment, Runbooks | **In progress** (Cycle 1) |
| **E — Brand & UX Coherence** | Hi Meet AI rename, CTA language, empty states, launch story | Not started (Cycle 5) |

## Cycle history

### Cycle 1 — Foundation (Stream D)
- Created `services/dashboard/src/config/features.ts` — feature-flag registry
- Created `services/dashboard/src/components/FeatureGate.tsx` — route guard primitive
- Wrapped 14 hidden routes in `App.tsx` with `<FeatureGate>`
- Added `GTM_LAUNCH_MODE` env gate in `scheduler.py` for 3 execution-tier jobs
- Created `docs/launch/` governance skeleton (this file, feature-flags.md, naming-conventions.md, launch-package.md)

**Outcome**: Build-vs-expose separation is now enforced. Internal builds see everything; production builds see the 6-surface launch package.

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
