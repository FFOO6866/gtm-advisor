# Cycle 3 — Tier-2 Surface Polish + Program Refinements: Red-Team Memo

**Date**: 2026-04-07
**Streams**: B (Feature Completion), D (Platform Hardening), E partial (Brand)
**Branch**: `rc/v0.1.0`
**Entry state**: `45cb3d4` (cycle-2-complete tag)

## Refinements applied from program-level review

1. **Formal dangerous-action policy** — `dangerous-action-policy.md` defines what qualifies as "dangerous"; audit found `reject_item` was inconsistently protected; unprotected to align
2. **Launch debt register** — TodayPage Promise.all fragility now tracked as LD-1; resolved in Cycle 3 setup; 8 other debt items classified
3. **Visibility vs promise scope** — `promise-scope-audit.md` tracks both scopes per surface; 4 latent drift items identified
4. **Content Studio gate philosophy** — strengthened to 7 criteria including differentiation, brand fidelity, vertical coherence; default outcome is "stay hidden"

## What was built

### Setup phase (refinements)
- `docs/launch/dangerous-action-policy.md` — 5-clause policy + endpoint audit
- `services/gateway/src/routers/approvals.py` — `reject_item` unprotected (policy alignment)
- `services/gateway/src/auth/launch_mode.py` — docstring updated
- `tests/unit/test_launch_mode_deny.py` — `PROTECTED_ENDPOINTS` list updated (4 entries, was 5)
- `services/dashboard/src/pages/TodayPage.tsx` — `Promise.all` refactored to named-key `fetches` object
- `docs/launch/workstream-status.md` — Launch Debt Register section + Cycle 3 history
- `docs/launch/promise-scope-audit.md` — per-surface promise audit
- `docs/launch/content-studio-qa.md` — strengthened 7-criterion gate
- `docs/launch/launch-package.md` — Promise-scope reference + nav diagram unchanged
- `docs/launch/feature-flags.md` — Protected Endpoints table aligned with policy

### Tier-2 surface work
- `services/dashboard/src/pages/ContentPage.tsx` — Beta badge in header + disclaimer subtitle
- `services/dashboard/src/pages/PlaybooksPage.tsx` — Methodology mode (no Activate, BookOpen icon, "Available through guided onboarding")
- `services/dashboard/src/pages/SignalsFeed.tsx` — "Deploy Playbook" → "Plan Campaign from Signal"
- Exports + Battlecards — verification only, no code changes needed

## Red-team 5-question audit

### 1. Completeness — What shipped incomplete?

- **All 4 program refinements landed** with code AND doc changes in the same cycle (per the doc-sync discipline rule from Cycle 2).
- **All 4 Tier-2 surfaces touched**. ContentPage banner, PlaybooksPage methodology mode, SignalsFeed CTA rename. Exports verified stable without code changes.
- **Not yet complete by design**:
  - Content Studio QA gate **execution** — gate is documented but not run. Decision deferred to launch week (gate requires actual side-by-side comparison work that's better done with fresh eyes near launch). Default remains: hidden.
  - Cycle 4 (execution layer verification) hasn't started.
  - Cycle 5 (full brand sweep + naming-debt closure).

### 2. Overexposure — Is anything visible that shouldn't be?

- **Production build with default env (verified by Vite build)**: 3 primary nav + 1 secondary + 2 bottom = 6 items. Unchanged from Cycle 2.
- **PlaybooksPage** is now a methodology library, but it remains gated behind `FEATURES.playbooks` (hidden in production). The methodology refactor is for the day it's eventually re-exposed. **No production exposure change.**
- **ContentPage Beta badge** is only visible if `FEATURES.contentBeta` is true. Default: false in production. **No production exposure change.**
- **SignalsFeed CTA rename** is invisible in production (page is gated). **No production exposure change.**

**Verdict**: Cycle 3 made no production exposure changes. All work was either internal-build polish or documentation. This is consistent with the discipline of "build broad, expose selectively."

### 3. Fragility — What breaks under failure conditions?

- **`require_execution_enabled` policy alignment** — `reject_item` is now unprotected. Risk: if a customer somehow reaches `/approvals` (they can't in launch mode because the page is hidden) and rejects an item, the rejection records an internal `email_rejected` AttributionEvent. **No external effect**, per the policy. Safe.
- **TodayPage refactor** — `Promise.all(Object.values(fetches))` parallelizes correctly; subsequent `await fetches.x` is instant since each promise is already settled. Works with TypeScript. Failure mode: if someone adds a new fetch to the `fetches` object but forgets to add a setter, TypeScript won't catch it (the new fetch just runs and is discarded). **Mitigation**: comment in the code documents the 2-place edit pattern. Acceptable risk.
- **Content Studio QA gate is documentation, not enforcement** — nothing in code prevents someone from flipping `FEATURES.contentBeta = true` without running the gate. **Mitigation**: the flag flip is a PR with required review, and `cycle-3-redteam.md` (this file) documents the protocol. The next cycle's red-team would catch a flag flip without QA results.

### 4. Support drag — What's the first likely ticket?

- **From an internal-build user (advisory mode)**: "Why doesn't the playbook activate button work anymore?" **Answer**: PlaybooksPage is now methodology mode. Activation happens via direct enrollment (advisory path), not from the page. This is correct behavior for v1.
- **From a hostile API explorer**: "Your `POST /approvals/{id}/reject` returns 200 even though the rest of approvals returns 404." **Answer**: Per the dangerous-action policy (`docs/launch/dangerous-action-policy.md`), reject is state-only and not dangerous. The policy is the source of truth, and it's documented.
- **From a customer who saw a Content Studio screenshot**: "Where's the AI content generator?" **Answer**: Content Studio is in private beta. Will be available after our QA gate completes. (Honest, with a clear next step.)

### 5. Coherence — Does the product still feel like one thing?

- **Stronger than Cycle 2.** Reasons:
  - The dangerous-action policy gives the protection layer a *justification*, not just a list. Future PRs will be evaluated against the policy.
  - The promise-scope audit gives launch surfaces a *contract* with the customer that we can verify.
  - The launch debt register makes "deferred" items concrete and trackable instead of casual notes.
  - PlaybooksPage methodology mode is qualitatively different from "browse with disabled Activate" — it has a coherent purpose even when the underlying activation is gated.
- **Still missing for full coherence**:
  - Cycle 4 hasn't traced the execution layer end-to-end yet
  - Cycle 5 hasn't done the full brand sweep
  - Content Studio gate hasn't been executed

## Doc-sync check (Cycle 2 discipline)

| Code change | Doc updated? | File |
|---|---|---|
| `reject_item` unprotected | ✅ | `dangerous-action-policy.md`, `feature-flags.md`, `launch_mode.py` docstring, test PROTECTED_ENDPOINTS |
| TodayPage `Promise.all` refactor | ✅ | `workstream-status.md` (LD-1 marked resolved) |
| ContentPage Beta badge | ✅ | (no doc change needed; gated by existing flag) |
| PlaybooksPage methodology mode | ✅ | `workstream-status.md` (Cycle 3 history) |
| SignalsFeed CTA rename | ✅ | `workstream-status.md` (Cycle 3 history) |
| Promise-scope audit (new doc) | ✅ | `launch-package.md` references it |
| Dangerous-action policy (new doc) | ✅ | `feature-flags.md` references it |
| Content Studio gate (new doc) | ✅ | (will be referenced from `cycle-3-redteam.md` and the gate-execution memo when run) |
| Launch Debt Register (new section) | ✅ | `workstream-status.md` |

**All doc-sync items verified. No drift introduced.**

## Integration check

| Concern | Status |
|---|---|
| Shared contracts (API types) | ✅ No type contracts changed |
| Route/nav consistency | ✅ Unchanged from Cycle 2 |
| Naming consistency on launch surfaces | ✅ ContentPage gets Beta language, PlaybooksPage gets methodology language, SignalsFeed gets planning language — all match the launch story |
| Feature-flag discipline | ✅ Zero new hardcoded flag checks |
| Backend protection matches policy | ✅ 4 endpoints protected (was 5; reject removed for policy alignment) |
| Cross-stream regression risk | ✅ 581 Python tests pass, ruff clean, TypeScript clean, Vite production build successful |
| Bundle size trend | ✅ 642.99KB (~unchanged; minor variance from Cycle 2's 642.20KB) |

## Launch debt register update

- **LD-1** (TodayPage Promise.all) — ✅ **Closed in Cycle 3 setup** (refactored to named-key access)
- **LD-2** through **LD-8** — unchanged
- **LD-9** (campaigns activate watch item) — added in setup

## Does this still feel like one product?

Yes. Cycle 3 made the product *more* coherent without adding visible surfaces. The work was structural: policy formalization, debt tracking, drift detection, gate strengthening. These investments make Cycle 4 and 5 cheaper because the rules are now explicit.

## What would a hostile launch reviewer attack first?

"Your dangerous-action policy says external effect = protected, but you have a `POST /companies/{id}/campaigns/{id}/activate` endpoint that's unprotected — couldn't that trigger execution?"

**Response**: Currently `campaigns/{id}/activate` only flips an internal status flag in the DB. There is no execution wired to it in v1. This is documented in `dangerous-action-policy.md` as a watch item for Cycle 4. If Cycle 4 wires activation to actual execution, it gets added to `require_execution_enabled` and the policy table updated. Verification: grep `services/gateway/src/routers/campaigns.py` for any background task or external API call inside the activate handler — there are none.

## What should still remain hidden even if technically complete?

No changes from Cycle 2. The hidden/gated list is stable. Content Studio is the only surface with a defined promotion path (the QA gate); the others stay hidden by default until v1.1+.

## Recommended next cycle

**Cycle 4 — Execution Layer Verification (Stream C)**

Goal: trace the execution path end-to-end with real verification, ensuring the two-layer defense actually works.

Scope:
1. **Sequence engine → Approval queue → SendGrid** trace
   - Set `GTM_LAUNCH_MODE=` (unset) in a local dev env
   - Manually create a sequence enrollment via API
   - Verify approval queue receives the item
   - Verify approval API returns 200 (not 404, since unset env)
   - Verify SendGrid mock receives the call (or real SendGrid if sandbox key present)
   - Then set `GTM_LAUNCH_MODE=v1` and verify all 5 protected endpoints return 404
2. **CRM Sync (HubSpot)** trace
   - Verify HubSpotMCPServer connects with API key
   - Verify `create_or_update_contact` works
   - Verify gating: in launch mode, no UI surface reaches CRM Sync
3. **Webhook handler** trace
   - Verify `POST /webhooks/sendgrid` accepts an event
   - Verify it correctly updates `Lead`, `AttributionEvent`, `SequenceEnrollment`
   - Verify the endpoint is NOT gated (per policy — inbound webhooks needed for advisory)
4. **Workforce execute** trace
   - Verify `WorkforceExecutor` runs end-to-end on a test config
   - Verify gating: `POST /workforce/{id}/execute` returns 404 in launch mode
5. **Watch item from policy**: re-audit `campaigns/{id}/activate` — does it still only flip a status flag, or has Cycle 2-3 work added side effects?

**Red-team focus for Cycle 4**:
- Does any execution endpoint produce an external effect that bypasses the deny dependency?
- Does the sequence runner job actually skip when `GTM_LAUNCH_MODE=v1`?
- Are PDPA audit trails (consent recording) functioning correctly?
- Are there any new "watch item" endpoints to add to the protected list?

**Go criteria for Cycle 4 start**: Cycle 3 is complete with all 4 program refinements landed, all Tier-2 polish applied, and doc-sync verified. ✅ Ready to proceed.
