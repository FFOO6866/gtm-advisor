# Cycle 5 — Constraint Incorporation Plan

**Date**: 2026-04-07
**Streams**: E (Brand & UX Coherence — primary), C + D (refinements before main work)
**Branch**: `rc/v0.1.0`
**Entry state**: `745febd` (cycle-4-complete)

Three program-level refinements were handed down at the end of Cycle 4. They are absorbed into Cycle 5 setup *before* the main Brand & UX coherence work begins, so that the execution-boundary discipline established in Cycle 4 remains durable as parallel feature work continues. This document records how each refinement is absorbed and what the acceptance check looks like.

The pattern mirrors `cycle-4-incorporation-plan.md`. The constraints recorded here apply to every Cycle 5 deliverable.

---

## Refinement 1 — Close LD-11 early (registry-lock regression test)

> The latent bypass risk on `/api/v1/agents/{name}/run` and `/companies/{id}/agents/{id}/run` should not remain dependent on tribal knowledge that the registry is narrow. Add the smallest robust protection: a registry-lock regression test, and/or an explicit assertion that only approved analysis agents can be exposed in launch mode. Keep this lightweight.

### Incorporation

- **Closed in setup, not deferred to mid-cycle.** LD-11 was previously scheduled for "Cycle 5 or 6" as a future-proofing item. The Cycle 4 red-team flagged it as a *latent* risk — safe today, fragile tomorrow. The user instruction is to close it before Cycle 5's main work begins so brand/UX changes (which can touch many files) cannot accidentally re-open the bypass.
- **Smallest robust protection: a regression test plus a contract comment at the source.** The test asserts the registry contents in three independent ways so a single rename or a partial edit cannot evade it:
  1. **Exact-set lock** on `AGENT_METADATA` — the registered IDs must equal exactly the 6 approved analysis agent IDs. Any addition, removal, or rename fails the test.
  2. **Class/metadata drift check** — `get_all_agent_classes()` and `AGENT_METADATA` must agree on the set, so an editor cannot add an agent in one place and forget the other.
  3. **Explicit deny list** for the 5 known execution-tier agents (`outreach-executor`, `crm-sync`, `workforce-architect`, `signal-monitor`, `lead-enrichment`). The test fails with an informative message naming the leaked agent if any of these passes `is_valid_agent()`.
- **Source-level documentation**: a launch-mode contract block is added to the `agents_registry.py` module docstring that explains the implicit gate and tells future editors exactly what the choices are when adding a new agent. This means the constraint is visible at the place where it would be violated, not just in a test file.
- **Failure-message UX**: each test's `assert` message includes the remediation steps. A failing CI run tells the editor the two valid responses (confirm no external effect AND update the test allow-list, OR add `Depends(require_execution_enabled)` to the run endpoints AND update the policy doc). There is no third option.
- **No widening of launch behavior.** No new endpoint, no new flag, no new gate added at the route level. The route protection is unchanged; the test merely codifies the registry's current contents as the contract that makes the existing route-level posture safe.

### Acceptance

- `tests/unit/test_launch_mode_deny.py::TestAgentRegistryLock` exists with three test methods and all pass.
- `agents_registry.py` module docstring documents the launch-mode contract and references the regression test.
- LD-11 is marked ✅ Resolved Cycle 5 setup in the launch debt register.
- `dangerous-action-policy.md` Watch list reflects LD-11 as closed.

---

## Refinement 2 — Formalize watchlist discipline

> For each watch item (including LD-9, LD-10, LD-11), add: owner or responsible workstream; why it is safe today; what future change would make it dangerous; what the required response would be. This should live in the launch debt / verification discipline, not just as prose in one cycle memo.

### Incorporation

- **Schema lives in `workstream-status.md`, not in a one-off cycle memo.** A new top-level subsection "Watch-item discipline" is added under the Launch Debt Register. It defines the four required fields (Owner / Why safe today / Danger trigger / Required response) and the rule that any watch item that cannot fill all four fields concretely is *not* a watch item — it is either an undocumented assumption (must be analyzed in-cycle) or a blocker (must be fixed in-cycle).
- **Each existing watch item is migrated to the schema in Cycle 5 setup.** LD-9 (`/campaigns/{id}/activate`), LD-10 (scheduler runtime gates), and LD-11 (now closed) each get a dedicated formalized record in the same section. The launch debt register table remains as the index; the formalized records are the source of truth for the safety argument.
- **`dangerous-action-policy.md` Watch list is reformatted** as an index pointing to the formalized records. Two short-form items (`workforce/design` and `workforce/approve`) remain in-line because their safety argument is one line and stable. Anything contested or longer than one line must be promoted to a formalized record.
- **Re-audit procedure is documented.** "Adding a new watch item" and "Re-auditing a watch item" are both written as numbered steps so future cycles cannot drift from the discipline. A re-audit must re-derive "Why safe today" from current code (grep or trace), not trust the prior cycle's claim.
- **No silent watch items.** Watch items that lack the four fields cannot exist at cycle exit. This forces the question "is the safety argument falsifiable?" to be answered for every item.

### Acceptance

- `workstream-status.md` contains the "Watch-item discipline" section with the schema and re-audit procedure.
- LD-9, LD-10, LD-11 each have a formalized record with all four fields filled in concretely.
- `dangerous-action-policy.md` Watch list section indexes the formalized records and uses the same schema for any short-form items it retains.
- The discipline is referenced from the Cycle 5 red-team memo as a sign-off check.

---

## Refinement 3 — "Dangerous vs destructive" as permanent policy language

> Fold that distinction into the standing dangerous-action policy so future cycles do not lose it. Keep the examples concrete.

### Incorporation

- **Promoted out of the Cycle 4 red-team memo into `dangerous-action-policy.md` as standing language.** The distinction was originally surfaced in Cycle 4 self-challenge Challenge 2 (the matrix observation about `DELETE /campaigns/{id}` being destructive but not dangerous). Leaving it in a cycle memo means a reviewer two cycles later would not see it and could re-introduce the symmetry confusion.
- **New section "Dangerous vs destructive (orthogonal concerns)"** added to `dangerous-action-policy.md`, placed immediately after "The Policy" so any reader who reaches the policy clauses also reaches this distinction. Includes:
  - A 2×2 grid (dangerous × destructive) with concrete cell examples.
  - Explicit definitions of both terms — "external effect" vs "destroys internal state".
  - A concrete examples table covering at least one entry in every cell, including the rare both-cells case.
  - Three justifications for why the distinction matters (symmetry confusion, aesthetic protection drift, coverage matrix integrity).
  - A rule of thumb: "if you cannot explain the action's blast radius without using the words 'external' or 'third party', it is destructive, not dangerous."
- **Cross-references preserved.** The new section names which gating mechanism governs each column (this policy + `require_execution_enabled` for dangerous; frontend `settingsDangerZone` and similar for destructive). This prevents a future reviewer from asking "why isn't `DELETE /campaigns/{id}` in `require_execution_enabled`?" without finding the answer in the same document.
- **No code change.** The policy update is documentation-only. No existing endpoint is reclassified.

### Acceptance

- `dangerous-action-policy.md` contains the "Dangerous vs destructive" subsection with the 2×2 grid, the definitions, the examples table, and the rule of thumb.
- The Cycle 5 red-team memo verifies the distinction is visible to a reader who only reads `dangerous-action-policy.md` (not the cycle memos).

---

## Constraints carried forward from Cycle 4

These remain in force for every Cycle 5 deliverable. They are not new; they are the operating posture.

1. **Verification-first** — fix what is necessary for safety/correctness/policy alignment only. Do not widen launch behavior. The Cycle 5 brand/UX work specifically must not introduce new CTAs, new routes, or new flag promotions; it is a *naming and copy* sweep.
2. **Coverage matrix discipline** — any change to a router or scheduler job that touches the execution layer must update `execution-verification.md` in the same cycle. The matrix must have zero "inconsistent" rows at cycle exit.
3. **Qualitative override** — 57/57 is a floor, not a ceiling. No promotion of any hidden surface in Cycle 5 unless the cycle's red-team explicitly endorses it on qualitative grounds. (Cycle 5 is not expected to promote any surface; this is a guardrail.)

---

## Summary

| Refinement | Primary artifact | Acceptance check |
|---|---|---|
| 1. Close LD-11 | `tests/unit/test_launch_mode_deny.py::TestAgentRegistryLock` + `agents_registry.py` contract docstring | 3 new tests pass; LD-11 marked ✅ |
| 2. Watch-item discipline | `workstream-status.md` § Watch-item discipline; `dangerous-action-policy.md` Watch list reformatted | All open watch items have Owner / Why safe / Trigger / Response |
| 3. Dangerous vs destructive | `dangerous-action-policy.md` § Dangerous vs destructive | 2×2 grid + examples + rule of thumb live in standing policy, not in a cycle memo |

All three refinements are absorbed in Cycle 5 *setup* — before the main Brand & UX coherence work begins — so the execution-boundary discipline established in Cycle 4 cannot be eroded by parallel naming/copy edits later in the cycle.

---

## Self-challenge

Per the standing red-team requirement, the Cycle 5 setup is challenged before being finalized.

### Q1: Am I leaving any safety rule dependent on undocumented assumptions?

**Walk-through**:

- *Was the launch-mode posture for `/agents/{name}/run` ever written down before this cycle?* Only in `execution-verification.md` finding F-4 — i.e., in a single cycle memo. After Refinement 1, it is enforced by a regression test that runs in CI and documented at the source in `agents_registry.py`. The assumption "the registry is narrow" is now mechanically falsifiable. ✅
- *Is the safety of `/sequences/enrollments/{id}/resume` still tribal knowledge?* The Cycle 4 red-team self-challenge Challenge 1 already tightened the matrix annotation: `/resume` is safe **only because** the sequence runner gate exists at both registration and call time. This dependency is now documented in `execution-verification.md` and survived into Cycle 5 unchanged. **However**, the dependency is currently a prose annotation in the matrix. There is no test that fails if the sequence runner gate is removed. *Is that a gap?* The sequence runner gate is itself protected by the earlier `TestLaunchModeDependency` and the call-time check is exercised by `_run_sequence_runner` integration paths. A test that explicitly asserts "if you remove the sequence runner gate, `/resume` becomes dangerous" would be valuable but is out of scope for Cycle 5 setup; it should be a Cycle 6 launch-readiness item. **Action**: add a watch-item-style note acknowledging this is a known gap to revisit in Cycle 6, not in Cycle 5 setup. (Doing it now would be scope creep.)
- *Is the dangerous-vs-destructive distinction now visible to a reviewer who only reads `dangerous-action-policy.md`?* Yes — it is the second section after "The Policy", before the audit table. A reviewer reaching the audit table cannot have skipped it. ✅

**Verdict on Q1**: one acknowledged gap (sequence runner gate dependency lacks a regression test), explicitly deferred to Cycle 6 launch-readiness with a note in workstream-status.md. All other safety rules are now mechanically enforced or visibly documented at their source. No remaining undocumented assumptions.

### Q2: Am I letting watch items exist without clear trigger conditions?

**Walk-through of every open watch item after Cycle 5 setup**:

- **LD-9** — Trigger is "any commit that introduces a *consumer* of `CampaignStatus.ACTIVE`". A reviewer can verify this with one grep. ✅
- **LD-10** — Trigger is two-pronged: (a) the ROI summary TODO at `scheduler.py:537` is implemented; (b) lead enrichment grows an outbound HTTP call. Both are concrete code changes that a reviewer can detect. ✅
- **LD-11** — Closed; the trigger is now mechanically enforced by the regression test. ✅
- **`workforce/design` (light-touch)** — Safety is "creates a config record only, no cascade"; trigger would be "design endpoint grows a side effect". This is a one-line stable argument and fits the light-touch class. ✅
- **`workforce/approve` (light-touch)** — Safety is "cascade is broken at the scheduler by Cycle 4 F-1"; trigger would be "F-1 gate is removed OR a new consumer of `WorkforceConfig.status==ACTIVE` is added that doesn't go through the gated cascade". Two triggers, both detectable by grep. ✅

**Verdict on Q2**: every open watch item has a falsifiable trigger condition. None rely on "trust me, it's fine".

### Q3: Am I treating current safety as durable when future feature additions could re-open risk?

**Walk-through**:

- *Cycle 5's main work is brand/UX coherence — naming sweep, copy edits, possibly nav cleanup.* Could naming changes touch the execution boundary? Only if a renamed CTA accidentally enables a previously hidden surface. The two-layer defense (frontend hide + backend deny) protects against this: even if a frontend label change accidentally exposes a hidden CTA, the backend `require_execution_enabled` 404 still fires.
- *Could a brand-sweep edit touch `agents_registry.py`?* Plausible — a rename of an agent display title (e.g., "GTM Strategist" → "Hi Meet AI Strategist") would touch `AGENT_METADATA["gtm-strategist"]["title"]`. The registry-lock test asserts on the *keys* of `AGENT_METADATA`, not the values, so a title rename does not break the test. But if an editor accidentally renames the *key* `gtm-strategist` to something else, the test fails. ✅
- *Could a brand-sweep edit touch `dangerous-action-policy.md`?* Plausible — copy edits to the doc are not protected by tests. **However**, the new "Dangerous vs destructive" section is concrete enough that a copy edit is unlikely to silently invert its meaning. If it does, the next cycle's red-team will catch it.
- *Could a brand-sweep edit touch the LD-11 contract docstring in `agents_registry.py`?* If someone reformats the docstring and removes the launch-mode contract block, the registry-lock test still passes (the contract is enforced at the test, not the docstring). **But the docstring is the in-source explanation that future editors see first.** This is a potential weak point: a docstring rewrite could lose the contract explanation while still passing CI. *Mitigation*: I will note in the workstream-status.md cycle-5-setup section that the docstring should be re-verified during the Cycle 5 final red-team. This is lightweight and fits the cycle's discipline.
- *Could a future flag promotion bypass the registry lock?* The registry lock is independent of flag state; it asserts on Python data structures regardless of `GTM_LAUNCH_MODE`. A flag promotion does not change the registry. ✅

**Verdict on Q3**: one potential weak point (the in-source contract docstring is not test-enforced) is acknowledged and assigned a re-verification step in the Cycle 5 final red-team. All other current safety holds against the Cycle 5 main work.

### Revision outcome

After self-challenge, two minor adjustments are made:

1. **Sequence runner gate dependency** — a note is added to `workstream-status.md` flagging it as a known gap for Cycle 6 launch-readiness review. Not a Cycle 5 deliverable.
2. **Registry-lock contract docstring re-verification** — added as an explicit Cycle 5 final red-team check item (see below).

Neither adjustment changes the three refinements above; both are guardrails recorded in `workstream-status.md`.
