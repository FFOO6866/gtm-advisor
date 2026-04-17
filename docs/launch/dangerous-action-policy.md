# Dangerous-Action Policy

**Purpose**: Define which backend actions are protected when `GTM_LAUNCH_MODE=v1`, and the rule that determines protection.

**Source of truth for protection**: `services/gateway/src/auth/launch_mode.py::require_execution_enabled`

**Source of truth for policy**: this document.

---

## The Policy

An action is **dangerous** (and therefore protected in launch mode) if its invocation produces **any** of:

1. **External communication**
   Sends an email, SMS, push notification, webhook delivery, or any other message to a third party.
2. **External-facing record creation or mutation**
   Creates or modifies a record visible to non-internal parties: a CRM contact, a CRM deal, a calendar invite, a social post, an audience segment.
3. **Cascading state transition**
   Transitions an entity into a state whose downstream automation produces external effects later (e.g., enrolling a lead → scheduling sends → triggering emails on the next scheduler tick).
4. **Third-party API call with billing or notification consequences**
   Invokes a third-party API that bills the customer's account, sends a message, or notifies a person.
5. **Mutation of state visible to non-internal parties**
   Changes any persisted state that the customer's customers, leads, or partners can observe.

An action is **NOT dangerous** if it:

- Changes only internal state (an internal status, an internal flag, an internal log entry)
- Records audit data without external effect
- Reads data
- Pauses or halts an existing flow without sending anything new
- Renders, transforms, or exports data the customer already has

---

## Dangerous vs destructive (orthogonal concerns)

> Permanent policy language. Originally surfaced in Cycle 4 self-challenge Challenge 2; promoted out of the cycle memo into standing policy in Cycle 5 setup so future cycles cannot lose the distinction.

**"Dangerous"** and **"destructive"** are not the same. They are orthogonal: an action can be one, the other, both, or neither. The dangerous-action policy in this document covers *dangerous* actions only. Destructive actions are governed separately.

| | Not destructive | Destructive |
|---|---|---|
| **Not dangerous** | Read, list, internal-status flip, pause, export | Delete a draft campaign, clear local cache, reset a session |
| **Dangerous** | Send email, enroll lead, create CRM contact, schedule outreach | (rare) An action that both deletes internal state AND triggers an outbound message — handle as both |

**Definitions**:

- **Dangerous**: produces an *external effect* — communicates with a third party, mutates a record visible outside our system, or transitions an entity into a state whose downstream automation will produce one of these later (the 5 clauses above). The blast radius escapes our system boundary.
- **Destructive**: *destroys internal state* without external effect — deletes a row, clears a table, wipes a cache, resets a configuration. The blast radius is contained inside our system but the action is hard or impossible to reverse.

**Concrete examples** (each listed under exactly the right column):

| Action | Dangerous? | Destructive? | Where it is governed |
|---|---|---|---|
| `POST /approvals/{id}/approve` → SendGrid send | ✅ | ❌ | This policy (`require_execution_enabled`) |
| `POST /sequences/activate-playbook` → cascading enrollments | ✅ | ❌ | This policy (cascading state, clause 3) |
| `DELETE /companies/{id}/campaigns/{id}` (deletes a draft) | ❌ | ✅ | Frontend `settingsDangerZone` flag and similar UI gating; **not** in this policy |
| Settings "Clear all data" wipe | ❌ | ✅ | Frontend `settingsDangerZone` flag |
| `POST /companies/{id}/leads/{id}/qualify` (status flip) | ❌ | ❌ | Neither — not gated |
| Hypothetical "delete contact AND send goodbye email" | ✅ | ✅ | Both: must satisfy this policy AND destructive-UX gating |

**Why this matters**:

1. **Symmetry confusion** — without the distinction, a reviewer sees `DELETE /campaigns/{id}` and asks "should this be in `require_execution_enabled`?" The answer is no — destructive operations are handled by frontend gating because the blast radius is internal. Putting them in the dangerous-action gate would either dilute the signal (fewer reviewers would understand what `require_execution_enabled` means) or under-protect them (the 404 response is the wrong UX for a destructive action; the user needs a confirmation, not a silent disappearance).
2. **Aesthetic protection drift** — Cycle 3 removed `reject_item` from `require_execution_enabled` because it was state-only (neither dangerous nor destructive). If "destructive" were folded into "dangerous", a future reviewer could re-add it on the wrong basis. The two columns must stay separate.
3. **Coverage matrix integrity** — the execution-verification coverage matrix only enumerates dangerous actions. If destructive operations were included, the matrix would either bloat or become inconsistent. Cycle 4 finding F-7's exemption note already calls this out; promoting it to standing policy makes the distinction non-negotiable for future cycles.

**Rule of thumb**: if you cannot explain the action's blast radius without using the words "external" or "third party", it is destructive, not dangerous.

---

## Why this distinction matters

Frontend hiding prevents customers from discovering execution surfaces in normal use. The backend deny dependency is the second layer: it denies direct API invocation by anyone who has discovered the endpoint via a leaked URL, a screenshot, a curl, or an API client.

Protecting actions that have **no external effect** does not improve safety. It only adds support burden and creates inconsistency that suggests other endpoints might be unprotected when they shouldn't be. The discipline is: protect what is dangerous; leave the rest alone.

---

## Audit of current protected set

| Endpoint | Action | External effect? | Verdict |
|---|---|---|---|
| `POST /companies/{id}/approvals/{id}/approve` | Sets ApprovalQueueItem.status to APPROVED, triggers `_send_approved_email` background task → SendGrid send | ✅ Outbound email | **Correctly protected** |
| `POST /companies/{id}/approvals/bulk-approve` | Iterates items, sets each to APPROVED, queues batch SendGrid sends | ✅ Outbound email (bulk) | **Correctly protected** |
| `POST /companies/{id}/approvals/{id}/reject` | Sets status to REJECTED, records "email_rejected" AttributionEvent | ❌ State-only (internal status + internal log) | **Inconsistent — should be unprotected** |
| `POST /companies/{id}/sequences/activate-playbook` | Calls `PlaybookService.create_sequence_from_playbook`, then `SequenceEngine.enroll` for each lead → enrollments → scheduled emails | ✅ Cascading (enrollment → schedule → send) | **Correctly protected** |
| `POST /companies/{id}/workforce/{id}/execute` | Creates ExecutionRun, kicks off background workforce orchestration | ✅ Cascading (orchestrates outreach) | **Correctly protected** |

**Inconsistency**: `reject_item` is currently protected with `Depends(require_execution_enabled)`. The Cycle 2 justification was "state symmetry with approve" — an aesthetic argument, not a policy-driven one. Per this policy, `reject_item` has no external effect and should NOT be protected.

**Action**: In Cycle 3 setup, unprotect `reject_item`. Update `launch_mode.py` docstring, `feature-flags.md` table, and the test inventory accordingly.

---

## Endpoints reviewed and intentionally NOT protected

These endpoints touch execution-related state but pass the policy test (no external effect):

| Endpoint | Why NOT protected |
|---|---|
| `POST /sequences/enrollments/{id}/pause` | State-only — pauses an existing enrollment, sends nothing |
| `POST /sequences/enrollments/{id}/resume` | State-only — resumes an existing enrollment, scheduler decides whether to send next time it runs |
| `GET /approvals` (list) | Read-only |
| `GET /approvals/count` | Read-only counter |
| `POST /webhooks/sendgrid` | Inbound webhook from SendGrid; processes events that already happened. Cannot be removed because advisory customers depend on it for delivery tracking. |
| `POST /companies/{id}/campaigns` | Creates a draft campaign — internal artifact, no external effect |
| `POST /companies/{id}/campaigns/{id}/activate` | Currently this only flips a status flag in the DB; no execution trigger exists. **Watch item**: if Cycle 4 wires activation to actual execution, this becomes dangerous and must be added to the protected list. |
| `POST /companies/{id}/leads/{id}/qualify` | Manual status transition |
| `POST /companies/{id}/leads/{id}/contact` | Logs a contact attempt — internal record only |
| `POST /companies/{id}/leads/{id}/convert` | Marks as converted — internal status |

---

## Watch list (potential dangerous actions, reviewed each cycle)

These endpoints **may become dangerous** as the execution layer evolves. They are governed by the **watch-item discipline** defined in `workstream-status.md` — every entry must declare Owner, Why safe today, Danger trigger, and Required response. The formalized records live there; this section is the index and the routing.

| Watch item | Launch debt ID | Formalized record | Status |
|---|---|---|---|
| `POST /companies/{id}/campaigns/{id}/activate` | LD-9 | `workstream-status.md` § Watch-item discipline | Open — re-audited Cycle 4 as still safe (no consumers of `CampaignStatus.ACTIVE`) |
| `_run_lead_enrichment_all` and `_run_weekly_roi_summary` lack runtime gate | LD-10 | `workstream-status.md` § Watch-item discipline | Open — Cycle 5 polish target; required if ROI summary TODO ships |
| `POST /api/v1/agents/{name}/run` and `POST /api/v1/companies/{id}/agents/{id}/run` registry-lock | LD-11 | `workstream-status.md` § Watch-item discipline | ✅ Closed Cycle 5 setup — `tests/unit/test_launch_mode_deny.py::TestAgentRegistryLock` |
| `POST /companies/{id}/workforce/design` | — | This file (below) | Open — config record only; re-audited Cycle 4 as safe |
| `PATCH /companies/{id}/workforce/{id}/approve` | — | This file (below) | Open — DRAFT → ACTIVE; cascade broken by Cycle 4 F-1 fix at scheduler |

### Light-touch watch items (no formalized record yet)

These two are tracked here rather than in `workstream-status.md` because the safety argument is short and stable. If either becomes contested or the safety argument requires more than one line, promote to a formalized record.

- `POST /companies/{id}/workforce/design` — creates a config record only; no external effect, no cascade (the cascade was at the scheduler auto-enroll call, gated in Cycle 4 F-1).
- `PATCH /companies/{id}/workforce/{id}/approve` — transitions DRAFT → ACTIVE. Before Cycle 4's F-1 fix this implicitly enabled the scheduler cascade. Cycle 4 broke the cascade at the scheduler call site, so `/approve` does not need HTTP protection and remains exempt. See Cycle 4 finding F-2 in `execution-verification.md`.

### Open-ended watch class

- Any new agent endpoint that posts to social media, books meetings, or calls external APIs falls under this policy automatically and must be classified before merge.

## Scheduler coverage (added in Cycle 4)

The dangerous-action policy was originally expressed in terms of HTTP endpoints. Cycle 4 extended it to scheduler jobs, because background automation is the second surface of the execution layer.

**Gated execution-tier scheduler jobs** (registered only when `GTM_LAUNCH_MODE != v1`; `_run_sequence_runner` also has a call-time check):

| Job | Gate | Reason |
|---|---|---|
| `sequence_runner_daily` | Registration gate + call-time `is_launch_mode_v1()` | Clause 1 (processes due steps into approval queue, then SendGrid send) |
| `lead_enrichment_weekly` | Registration gate only | Currently no external effect; runtime gate is a polish item (LD-10) |
| `roi_summary_weekly` | Registration gate only | Currently no external effect; TODO at `scheduler.py:537` would flip this to clause-1 dangerous — runtime gate is a watch item |

**Embedded cascade gated at the call site** (Cycle 4):

| Job | Gate | Reason |
|---|---|---|
| `_run_signal_monitor_all_active` — `auto_enroll_from_signals` call | Call-time `is_launch_mode_v1()` skip around the enrollment call only; signal monitor itself continues to run | Clause 3 (cascading state transition): creating `SequenceEnrollment` rows is the cascade's dangerous step. See Cycle 4 finding F-1. |

**Non-execution scheduler jobs** (research, analytics, embedding — 14 jobs): not gated. None produce external effects. Full enumeration in `execution-verification.md` section C.

---

## Adding a new protected endpoint

When adding a new endpoint to `require_execution_enabled`:

1. **Justify against the policy** — write the justification in the PR description, citing which of the 5 policy clauses applies
2. **Add the dependency** — `dependencies=[Depends(require_execution_enabled)]` on the route
3. **Update `launch_mode.py` docstring** — add the endpoint to the "Protected endpoints" list
4. **Update `feature-flags.md`** — Protected Backend Endpoints table
5. **Update `tests/unit/test_launch_mode_deny.py::PROTECTED_ENDPOINTS`** — add the new endpoint
6. **Update this file** — move from Watch list to Audit table

If the action is state-only with no external effect, do **not** protect it. Document why in the audit table's "intentionally NOT protected" section.

---

## Removing protection from an endpoint

When removing protection (e.g., the endpoint is now state-only after a refactor):

1. Remove the `Depends(require_execution_enabled)` dependency
2. Update `launch_mode.py` docstring
3. Update `feature-flags.md` table
4. Update `tests/unit/test_launch_mode_deny.py::PROTECTED_ENDPOINTS`
5. Update this file's audit table with the rationale

The audit table should never lie. If the policy says an endpoint is dangerous, it must be protected. If the policy says it isn't, it must not be protected. **No "symmetry" or "aesthetic" justifications.**
