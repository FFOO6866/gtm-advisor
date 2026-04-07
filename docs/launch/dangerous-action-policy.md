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

## Watch list (potential dangerous actions to review in Cycle 4)

These endpoints **may become dangerous** as the execution layer evolves. Cycle 4 (Execution Layer Verification) will re-audit:

- `POST /companies/{id}/campaigns/{id}/activate` — currently safe, but if it ever triggers a sequence runner or sends, it becomes dangerous
- `POST /companies/{id}/workforce/design` — currently creates a config record only, but if it ever auto-executes the design, it becomes dangerous
- Any new agent endpoint that posts to social media, books meetings, or calls external APIs

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
