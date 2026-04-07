# Cycle 4 — Execution Layer Verification: Red-Team Memo

**Date**: 2026-04-07
**Streams**: C (Execution Layer)
**Branch**: `rc/v0.1.0`
**Entry state**: `ea091f5` (cycle-3-complete)

## Constraints in force

The program-level review at the start of Cycle 4 added three constraints that shaped the whole cycle. They are recorded in `cycle-4-incorporation-plan.md` and referenced here for red-team visibility.

1. **Verification-first** — fix what is necessary for safety/correctness/policy alignment only. Do not widen launch behavior. Tracing is not a pretext for feature work.
2. **Policy-to-endpoint coverage matrix** — every execution-capable HTTP route and scheduler job is inventoried and classified.
3. **Qualitative override on numeric gates** — 57/57 is a floor, not a ceiling. No rubric replaces the differentiation judgment.

The red-team audit below measures the cycle's work against these constraints in addition to the standard 5-question red-team.

---

## What was built

**Docs (new)**:
- `docs/launch/cycle-4-incorporation-plan.md`
- `docs/launch/execution-verification.md` (verification plan + coverage matrix + findings)
- `docs/launch/cycle-4-redteam.md` (this file)

**Docs (updated)**:
- `docs/launch/dangerous-action-policy.md` — scheduler coverage section + Cycle 4 watch-list re-audit
- `docs/launch/feature-flags.md` — runtime gates table adds the auto-enroll gate
- `docs/launch/content-studio-qa.md` — "Qualitative override" section
- `docs/launch/workstream-status.md` — Cycle 4 history + LD-10, LD-11 added; LD-9 re-audited

**Code (one safety fix)**:
- `services/gateway/src/scheduler.py` — F-1 fix: gate `auto_enroll_from_signals` call inside `_run_signal_monitor_all_active` on `is_launch_mode_v1()`. Signal monitor itself continues to run.
- `services/gateway/src/auth/launch_mode.py` — docstring cites the new scheduler gate and references `execution-verification.md`.

**Tests (regression)**:
- `tests/unit/test_launch_mode_deny.py::TestSchedulerAutoEnrollGate` — two tests:
  - `test_auto_enroll_call_is_guarded_by_launch_mode_check`: asserts the `is_launch_mode_v1()` guard appears before the `engine.auto_enroll_from_signals(...)` call site in `scheduler.py`. A future edit that removes the guard fails this test.
  - `test_auto_enroll_skip_log_event_exists`: asserts the `auto_enroll_from_signals_skipped` structured log key exists so operators have prod visibility into the gate firing.

## Red-team 5-question audit

### 1. Completeness — What shipped incomplete?

- **Coverage matrix is complete for the named scopes**: sequences, approvals, outreach, CRM sync, webhook handling, workforce execution, campaign activation. Every HTTP route in these areas has a row. The scheduler matrix also covers all 18 jobs, including 14 non-execution ones explicitly classified as "not gated (correct)" rather than omitted.
- **Fix for F-1 landed with a test**. Doc + code + test synchronized in a single cycle — the doc-sync discipline from Cycle 2 is intact.
- **F-3 and F-4 are deferred, not forgotten**. Both are on the launch debt register as LD-10 and LD-11 with explicit owning cycles and re-audit triggers. The alternative — applying them in Cycle 4 — would have violated Constraint 1 (verification-first) by drifting into polish work.
- **Not done by design**:
  - No Content Studio QA gate execution (stays hidden).
  - No flag promotions.
  - No frontend work.
  - No new endpoints or new scheduler jobs.

### 2. Overexposure — Is anything visible that shouldn't be?

- **Zero dashboard changes**. Verified by `git diff services/dashboard` after the cycle's work.
- **Zero new HTTP endpoints**. Verified by reviewing the cycle's diff.
- **Zero flag changes**. `services/dashboard/src/config/features.ts` is untouched.
- **No nav changes**. SidebarNav untouched.
- **The only runtime behavior change**: in launch mode, the signal monitor no longer creates enrollments. This is a strict *reduction* in state mutation — not an exposure.

**Verdict**: Cycle 4 made no production exposure changes. The launch package is pixel-identical to cycle-3-complete.

### 3. Fragility — What breaks under failure conditions?

- **The F-1 fix uses the same pattern as `_run_sequence_runner`**: import `is_launch_mode_v1` at call time, check it, skip with a structured log. The pattern is already in production and has been regression-tested since Cycle 2. The new site is tested by `TestSchedulerAutoEnrollGate`.
- **Failure mode if the fix is bypassed**: the ORIGINAL defense — sequence runner registration gate + call-time check — still holds. Enrollments would accumulate, but sends would not fire. F-1 is defense in depth, not a single point of failure.
- **Failure mode if `is_launch_mode_v1()` is unreliable**: the function reads `_LAUNCH_MODE_V1` which is set at import time from the env var. If the env var changes after import, the function returns stale data. This is documented in the module docstring and matches the frontend's compile-time posture. Cycle 2 introduced the call-time re-read pattern for `_run_sequence_runner`; Cycle 4 adopts the same pattern, so the fix inherits the same robustness (and the same caveat).
- **Regression test fragility**: `test_auto_enroll_call_is_guarded_by_launch_mode_check` uses source-text inspection (`inspect.getsource`) to verify the gate position. If someone refactors the gate into a helper function named differently, the test would fail even though the intent was preserved. **Mitigation**: the test checks for both the `is_launch_mode_v1()` substring and the position relative to the call site — a refactor that preserves the gate name will still pass. A refactor that renames the gate would be flagged by the test, which is the desired behavior (name consistency aids auditing).

### 4. Support drag — What's the first likely ticket?

- **Internal / advisory user**: "Why are no enrollments being created from signals in prod?" **Answer**: Launch mode gates the auto-enrollment cascade by design. Operators can verify by grepping production logs for `auto_enroll_from_signals_skipped` — the structured log is emitted every hour per company. Pointer: `execution-verification.md` finding F-1.
- **Hostile API explorer**: "Your launch-mode docs say you disable 3 execution jobs, but `_run_signal_monitor_all_active` still runs hourly — isn't that an execution job that leaked through?" **Answer**: The signal monitor is benign research (NewsAPI + EODHD + Perplexity reads + internal `SignalEvent` rows). Its *only* execution-tier step was the embedded `auto_enroll_from_signals` call, which Cycle 4 gated. The `feature-flags.md` table now documents both layers of scheduler gating explicitly.
- **Future-cycle engineer**: "I want to add the outreach-executor agent to the registry so we can invoke it from `/agents/outreach-executor/run` for internal testing." **Answer**: That creates a bypass around `require_execution_enabled`. Add explicit protection at the route or don't expose the agent via the generic run endpoints. See Finding F-4 in `execution-verification.md`.

### 5. Coherence — Does the product still feel like one thing?

- **The two-layer defense now has three layers**: frontend hiding, backend HTTP deny, backend scheduler runtime deny. The three layers are each appropriate for a different attack surface (customer discovery, direct API invocation, background automation). The dangerous-action policy now explicitly covers all three.
- **The coverage matrix closes an audit gap**: before Cycle 4, the claim "we protect dangerous actions" was supported by a list of 4 protected endpoints plus trust that we hadn't missed any. After Cycle 4, it is supported by an exhaustive matrix that names every execution-adjacent route and justifies each classification against the policy. The claim is now falsifiable.
- **Scheduler gates are no longer a footnote**: Cycles 1-3 treated scheduler gating as a sidebar ("additionally, `_run_sequence_runner` has a runtime check"). Cycle 4 pulled it into the same matrix as HTTP gating, so future red-teams can compare both surfaces side by side.
- **The qualitative-override principle extends Cycle 3's content gate philosophy**: Cycle 3 added the differentiation criterion to the rubric. Cycle 4 says the rubric alone is not sufficient. These compound: the rubric filters out obvious failures early; the qualitative questions filter out rubric-passing mediocrity.

---

## Constraint-specific audit

### Constraint 1 — Verification-first

| Check | Result |
|---|---|
| Any new HTTP endpoint in this cycle? | No |
| Any new scheduler job? | No |
| Any frontend file modified? | No |
| Any flag flipped from Hidden to Launch? | No |
| Any CTA enabled that was previously gated? | No |
| Code change count (excluding tests and docs) | 2 files (`scheduler.py`, `launch_mode.py`) |
| Nature of code changes | Narrowing gates + docstring update |

**Verdict**: verification-first discipline held. The one code change (F-1) narrows launch-mode behavior; the other (docstring) documents it.

### Constraint 2 — Coverage matrix

| Check | Result |
|---|---|
| All named HTTP areas covered? | ✅ sequences, approvals, outreach, CRM sync, webhooks, workforce, campaigns, attribution, signals, leads, generic agent run |
| Each row classified? | ✅ Legend: protected / exempt / watch / inconsistent |
| Any row left in "inconsistent" state at cycle end? | ❌ zero |
| Scheduler jobs covered? | ✅ all 18 |
| Rationale + recommended correction recorded? | ✅ per finding in `execution-verification.md` |

**Verdict**: coverage matrix is complete and actionable.

### Constraint 3 — Qualitative override

| Check | Result |
|---|---|
| `content-studio-qa.md` reflects the override principle? | ✅ new section "Qualitative override (added Cycle 4)" |
| Principle applies to future rubric gates too? | ✅ explicitly stated in the new section |
| Any surface promoted in this cycle? | ❌ none |
| Sign-off rule updated to recognize reviewer veto? | ✅ "one veto = stay Hidden; no reconciliation, no averaging" |

**Verdict**: Constraint 3 landed as a doc update and applies forward.

---

## Doc-sync check (Cycle 2 discipline, still enforced)

| Code change | Doc updated? | File |
|---|---|---|
| `scheduler.py` auto-enroll gate | ✅ | `execution-verification.md`, `dangerous-action-policy.md`, `feature-flags.md`, `launch_mode.py` docstring, `workstream-status.md` |
| `launch_mode.py` docstring | ✅ (self) | |
| `test_launch_mode_deny.py` regression test | ✅ | referenced from `feature-flags.md` scheduler section |
| Launch debt register LD-10 (new) | ✅ | `workstream-status.md` + `execution-verification.md` F-3 |
| Launch debt register LD-11 (new) | ✅ | `workstream-status.md` + `execution-verification.md` F-4 |
| Launch debt register LD-9 re-audit | ✅ | `workstream-status.md` + `execution-verification.md` F-6 |
| Constraint 3 qualitative override | ✅ | `content-studio-qa.md` + `cycle-4-incorporation-plan.md` |

**All doc-sync items verified. No drift introduced.**

---

## Integration check

| Concern | Status |
|---|---|
| Shared contracts (API types) | ✅ No contracts changed |
| Route/nav consistency | ✅ Unchanged from Cycle 3 |
| Naming consistency on launch surfaces | ✅ No user-visible strings changed |
| Feature-flag discipline | ✅ Zero flag changes |
| Backend protection matches policy | ✅ 4 HTTP endpoints + 2 scheduler runtime gates |
| Scheduler coverage matches policy | ✅ new scheduler coverage section in `dangerous-action-policy.md` |
| Cross-stream regression risk | See verification section below |

---

## Verification results

Ran after all Cycle 4 changes were staged.

| Check | Command | Result |
|---|---|---|
| Python unit tests | `uv run pytest tests/unit/ -q` | **534 passed** |
| Python unit + integration | `uv run pytest tests/unit/ tests/integration/ -q` | **583 passed, 2 skipped** (up 2 from Cycle 3's 581 — the 2 new `TestSchedulerAutoEnrollGate` regression tests) |
| Ruff lint (touched files) | `uv run ruff check services/gateway/src/scheduler.py services/gateway/src/auth/launch_mode.py tests/unit/test_launch_mode_deny.py` | **All checks passed** |
| Ruff lint (services/gateway/src) | `uv run ruff check services/gateway/src/` | 1 pre-existing error (LD-2 — `documents.py:301` unused loop var, Cycle 5 sweep item; unrelated to Cycle 4) |
| Dashboard TypeScript | `cd services/dashboard && pnpm tsc --noEmit` | **Clean** (no frontend files touched) |
| Dashboard Vite build | `cd services/dashboard && pnpm build` | **Successful**; bundle 642.99KB / gzip 174.59KB — **identical to Cycle 3** (confirms zero frontend delta) |

---

## Launch debt register delta

- **LD-9** (campaigns activate watch item) — re-audited Cycle 4, still safe, stays on watch list with updated notes
- **LD-10** (belt-and-suspenders runtime gates for lead_enrichment + roi_summary) — **new**, Cycle 5 owner
- **LD-11** (registry-lock assertion test for `/agents/{name}/run` endpoints) — **new**, Cycle 5 or 6 owner

---

## Hostile launch reviewer — attack surface

**Q1 (what the user asked me to self-challenge):** "Did you start enabling execution behavior instead of just verifying and securing it?"

**Answer**: No. The cycle's only code changes are:
1. A runtime gate that *disables* a cascade in launch mode (F-1 fix).
2. A docstring update that documents gates.

Neither change enables any execution path. The F-1 fix strictly narrows launch-mode behavior. If a future cycle enables execution, it must come from explicit flag promotion and a promotion memo — not from Cycle 4's diffs.

**Q2:** "Are there endpoints whose real-world effect is larger than their name suggests?"

**Answer**: Yes, two — both now documented:
1. `PATCH /workforce/{id}/approve`: the name says "approve a design record," but the effect (before F-1) was "enable an hourly scheduler job to create enrollments for this company's leads." The gate at the scheduler side (F-1) is the correct place to break the cascade, because the approve endpoint itself has no external effect. Documented in `execution-verification.md` finding F-2.
2. `POST /api/v1/agents/{name}/run`: the name says "run any agent," but the narrow registry makes this "run any of 6 analysis agents" today. The gap between the name and the reality is an audit risk. Documented in finding F-4 with a deferred fix (LD-11) that locks the registry with a test.

**Q3:** "Am I treating documented policy as sufficient without checking actual route reality?"

**Answer**: This is the risk the coverage matrix was designed to eliminate. For every row in the matrix, I verified the current code, not the policy's assumption. Specifically:
- Confirmed the `reject_item` endpoint is not protected (matches Cycle 3's intentional removal).
- Confirmed the 4 protected endpoints have `Depends(require_execution_enabled)` by reading the decorator list in each router file.
- Traced `SendGridMCPServer.send_email` to its call sites in `_send_approved_email` (in `approvals.py`) and `OutreachExecutorAgent`, and confirmed no orphan call sites exist.
- Traced `HubSpotMCPServer.create_or_update_contact` to its only consumer, `CRMSyncAgent`, which runs only inside `workforce_executor.run_execution`.
- Grepped for `CampaignStatus.ACTIVE` to re-audit LD-9 and found only the setter itself.
- Re-read `_run_signal_monitor_all_active` line by line and **caught the F-1 cascade gap** — which was exactly what Q3's question was designed to catch. If I had trusted the policy doc's HTTP-only framing, I would have missed it.

The coverage matrix plus the scheduler inventory are the artifacts that make Q3 falsifiable in future cycles too.

---

## Self-challenge revision pass

Per the user's request: **before finalizing, challenge my own Cycle 4 work**.

### Challenge 1: Did I misclassify anything as "exempt" that should be protected?

Walking the matrix row by row, looking for classifications I'd be embarrassed to defend to a hostile reviewer:

- `POST /sequences/enrollments/{id}/resume` — I classified it 🟢 Exempt + 🟡 Watch. The resume action sets `status=ACTIVE` and `next_step_due=NOW`. If the sequence runner were running, this would cause the next step to be processed on the next tick. In launch mode the runner is off, so resume is harmless. The classification stands *conditionally on the runner gate*. If someone argues "you said exempt but it's really only safe because of another gate," they're right — and that's exactly what the 🟡 Watch annotation means. I'll leave the classification but tighten the language.
- `POST /approvals/{id}/reject` — exempt. Cycle 3 rationale holds: state-only + internal log. Not rechallengeable.
- `PATCH /workforce/{id}/approve` — exempt after the F-1 fix. Before F-1 this would have been inconsistent. I explicitly added finding F-2 to document why, after F-1, the correct fix is at the scheduler and not at the HTTP layer.
- `POST /campaigns/generate-content` — exempt. LLM cost is platform-billed. If I imagine a hostile reviewer saying "but LLM calls cost money, so clause 4 applies," my answer is: clause 4 says "bills the customer's account" — platform-billed does not meet that test. The analysis flow itself makes LLM calls and is unquestionably a launch surface, so protecting content generation on clause-4 grounds would be internally inconsistent.
- `POST /api/v1/webhooks/sendgrid` — verified unprotected is correct. No send path.

**Revision**: I will tighten the "Watch" annotation on `sequences/enrollments/{id}/resume` in the matrix to make the dependency explicit, so a future cycle can't accidentally weaken the sequence-runner gate without seeing this dependency. Applying now.

### Challenge 2: Did I under-scope the coverage matrix?

Areas I checked that could have been out-of-scope omissions:
- **Analysis router** (`analysis.py`): runs the 6 analysis agents. These are the normal launch flow; analysis itself is the product. No execution agents involved. Correctly not in the execution matrix.
- **Exports router** (`exports.py`): read-only, returns JSON. No external effect. Out-of-scope for execution coverage.
- **Documents router** (`documents.py`): uploads PDFs, extracts content. No send path. Out-of-scope.
- **Strategy, insights, competitors, ICPs routers**: all read-oriented or update-internal-state. No execution paths.
- **Market data, websocket, health**: none are execution-adjacent.

One thing I should add that I missed: a sentence in the matrix noting that the delete/destructive operations (`DELETE /companies/{id}/campaigns/{id}`) are destructive but not "dangerous" in the policy's sense — destructive means "destroys internal state," dangerous means "causes external effect." These are orthogonal. A data-wipe is a separate concern (the `settingsDangerZone` flag covers it on the frontend). Applying now.

### Challenge 3: Does the F-1 fix introduce any regression risk to the non-launch-mode code path?

When `is_launch_mode_v1()` returns `False` (i.e., dev or production-without-v1), the fix keeps the original behavior: import `SequenceEngine`, call `auto_enroll_from_signals`, log the count, catch exceptions. The only behavioral change when `False` is the insertion of an `is_launch_mode_v1()` call — which is a boolean check against a module-level constant. Cost: negligible. Behavior: identical to pre-fix.

**Revision**: no change needed. Documenting here so future cycles can see the cost analysis.

### Challenge 4: Does the Cycle 4 red-team answer the user's three self-challenge questions *directly*?

The user asked me to self-challenge on three questions. I answered them in the "Hostile launch reviewer" section above. Reading my answers back:
- Q1: Did I start enabling execution behavior? — Answered. Evidence-based. Good.
- Q2: Endpoints with larger real-world effect than their name suggests? — Answered with two concrete examples and pointers. Good.
- Q3: Treating policy as sufficient without checking actual route reality? — Answered with the trace evidence and the F-1 discovery as proof the coverage matrix method catches gaps the policy doc alone wouldn't. Good.

All three answers cite specific findings and files, not generic reassurance.

**Revision outcome**: two small documentation tightenings (Challenge 1 + Challenge 2), no code changes required. Applying below.
