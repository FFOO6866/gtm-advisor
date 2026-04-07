# Cycle 4 — Constraint Incorporation Plan

**Date**: 2026-04-07
**Streams**: C (Execution Layer), D partial (Platform Hardening)
**Branch**: `rc/v0.1.0`
**Entry state**: `ea091f5` (cycle-3-complete)

Three constraints were handed down from the program-level review at the start of Cycle 4. This document records how each is absorbed into the cycle's working rules, so they apply to every downstream deliverable in this cycle and carry forward.

---

## Constraint 1 — Verification-first rule

> Cycle 4 is primarily an execution-layer verification and boundary-audit cycle. Do not let it drift into broad execution-feature expansion. If you discover defects, fix what is necessary for safety, correctness, or policy alignment — but do not treat tracing as a pretext to widen launch-visible or launch-operational behavior.

### Incorporation

- **Default action on any finding: narrow, not widen.** If a trace surfaces a gap in the deny layer, the fix must be a gate (close a path), not an unlock (open a path). Any change that adds a new surface, new CTA, new job registration, new endpoint, or new scheduler behavior is out of scope and must be deferred to a later cycle.
- **Scope boundary**: Cycle 4 changes are allowed to touch these files only if the change is a safety fix, a runtime gate, a doc update, or a regression test:
  - `services/gateway/src/auth/launch_mode.py`
  - `services/gateway/src/scheduler.py` (runtime gating only)
  - `services/gateway/src/routers/*.py` (adding `Depends(require_execution_enabled)` only; no new endpoints)
  - `tests/unit/test_launch_mode_deny.py`
  - `docs/launch/*`
- **Frontend changes are out of scope** unless a surface is inadvertently exposing an execution action that slipped through Cycle 1-3 (none was found; verified by visible-nav diff).
- **Red-team self-challenge question** (added to the Cycle 4 red-team memo): "Did any change in this cycle enable execution behavior instead of verifying and securing it?" Any "yes" or "uncertain" answer requires reverting the change.

### Acceptance

No file in `services/dashboard/src/` is modified in this cycle. No new endpoint is added. No flag is promoted. Verification output and safety fixes are the only deliverables.

---

## Constraint 2 — Policy-to-endpoint coverage matrix

> The dangerous-action policy now exists, but I want explicit route-level coverage. Inventory all execution-capable or externally effectful endpoints/surfaces involved in: sequences, approvals, outreach/send, CRM sync, webhook handling, workforce execution, campaign activation/watch items. For each, classify: protected by launch deny | intentionally exempt by policy | watch item / needs follow-up | inconsistent with policy. Include rationale and any recommended correction.

### Incorporation

- **Primary deliverable**: `docs/launch/execution-verification.md` — contains the full coverage matrix, the trace notes, and the findings.
- **Scope**: every HTTP route that could plausibly produce or cascade to an external effect is inventoried. Not just the currently-protected ones. The matrix must enumerate ALL execution-adjacent endpoints and explicitly say why each one is where it is.
- **Also covered**: scheduler jobs. The policy so far has been expressed in terms of HTTP endpoints, but scheduler jobs are the second surface of the execution layer. The matrix extends to include them.
- **Correction rule**: when a row is classified as "inconsistent with policy," the fix is applied in the same cycle and the row is re-classified. A cycle cannot exit with any row in "inconsistent" state.
- **Watch items** remain open across cycles but must have an explicit owning cycle and a re-audit trigger.
- **Source of truth ordering**: if the matrix and `dangerous-action-policy.md` disagree, the policy wins and the matrix is brought into compliance. If the matrix and actual code disagree, the code wins (reality is the source of truth for what the routes actually do) and the matrix is corrected.

### Acceptance

The coverage matrix exists, covers every execution-adjacent route in the named areas, and has zero rows in the "inconsistent with policy" state at cycle end.

---

## Constraint 3 — Numeric gates do not create false confidence

> For Content Studio and similar surfaces, a rubric score is not by itself sufficient. Keep the principle explicit: qualitative strategic differentiation overrides score completion. If any future promotion recommendation appears, it must answer: is this meaningfully better than generic prompting? does it reflect Hi Meet AI workflow context and positioning? is it coherent across multiple verticals?

### Incorporation

- **Reaffirmation**: The `content-studio-qa.md` 7-criterion gate is preserved as-is. 57/57 is a floor, not a ceiling. Reaching 57/57 does not imply promotion; it implies the surface has cleared the minimum bar and the qualitative judgment call is now *unblocked*, not *decided*.
- **Added to the QA gate's sign-off rule**: Even with 57/57, any reviewer may veto promotion with a qualitative justification tied to one of the three questions above. A veto does not need to be reconciled — one veto = stay hidden.
- **Applies to other rubric-based gates too**: if Cycle 5 or later introduces a promotion rubric for any other hidden surface (Playbooks, Signals, Workforce), the same principle applies: the rubric is a floor, the qualitative judgment is binding.
- **Cycle 4 scope**: no promotion decisions are made in Cycle 4. This constraint is recorded now so it carries forward.
- **Documentation update**: `content-studio-qa.md` gets a new "Qualitative override" section that captures this explicitly.

### Acceptance

`docs/launch/content-studio-qa.md` reflects the qualitative-override principle. No surface is promoted in this cycle. The constraint is recorded so it applies in Cycle 5 and the launch-readiness review in Cycle 6.

---

## Summary

| Constraint | Primary artifact | Acceptance check |
|---|---|---|
| Verification-first | This file + Cycle 4 red-team self-challenge | No dashboard changes; no new endpoints; no flag promotions |
| Coverage matrix | `execution-verification.md` | Zero "inconsistent" rows at cycle end |
| Numeric-gate qualitative override | `content-studio-qa.md` amendment | Section added; no surface promoted |

All three constraints are in force for every other Cycle 4 deliverable (verification plan, coverage matrix, findings, safety fixes, red-team memo).
