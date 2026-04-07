# Cycle 4 — Execution Layer Verification

**Date**: 2026-04-07
**Scope**: Stream C (Execution Layer) — sequences, approvals, outreach, CRM sync, webhook handling, workforce execution, campaign activation.
**Mode**: Verification and boundary audit. Not enablement.
**Constraints in force**: see `cycle-4-incorporation-plan.md`.

This document contains:
1. The execution verification plan (what is being traced and why).
2. The policy-to-endpoint coverage matrix.
3. Findings from tracing the code paths.
4. A separate scheduler-level coverage matrix (because the execution layer has two surfaces: HTTP and the APScheduler).

The red-team review and sign-off are in `cycle-4-redteam.md`.

---

## A. Verification plan

### Goal

Confirm that every execution-layer code path — HTTP or background — is gated such that in `GTM_LAUNCH_MODE=v1` production, **no route, no scheduler job, no cascading state transition, and no webhook handler can cause an outbound email, an outbound CRM write, or a scheduled future send**.

### Non-goals

- Not enabling execution features that are currently gated.
- Not widening the launch surface.
- Not promoting any hidden flag.
- Not writing new endpoints or new scheduler jobs.

### Method

For each area, follow the actual code from HTTP edge (or scheduler tick) to the outermost side effect and note where each gate lives.

1. **Sequences** — from `POST /sequences/activate-playbook` and the daily sequence runner, trace through `SequenceEngine.enroll`, `run_due_steps`, `_process_enrollment_step` to the `ApprovalQueueItem` table. Confirm there is no path that skips approval.
2. **Approvals** — from `POST /approvals/{id}/approve` and `/bulk-approve`, trace to `_send_approved_email`, and from there to `SendGridMCPServer.send_email`. Confirm the approve endpoints are behind `require_execution_enabled` and the background task is only reachable from protected endpoints.
3. **Outreach (SendGrid send)** — confirm that `SendGridMCPServer.send_email` is only invoked from `_send_approved_email` (which is only reachable from protected endpoints) and nowhere else. Grep for other call sites.
4. **CRM Sync (HubSpot)** — locate `HubSpotMCPServer.create_or_update_contact` call sites. Confirm each is either (a) inside a protected endpoint handler or (b) inside a gated scheduler job or (c) nowhere reachable in launch mode.
5. **Webhook handling** — `POST /api/v1/webhooks/sendgrid`. Confirm it can only pause, record, and log — never send. Confirm it is intentionally unprotected and the policy clause for inbound webhooks is clear.
6. **Workforce execution** — from `POST /workforce/{id}/execute` (protected) trace through `run_execution` → `OutreachExecutorAgent`. Confirm the pre-protected endpoint is the only entry point to `run_execution`.
7. **Campaign activation (watch item)** — re-audit `POST /campaigns/{id}/activate` to confirm it remains state-only and no new consumer of `CampaignStatus.ACTIVE` has been introduced.
8. **Scheduler jobs** — inventory all 18 jobs, classify each by what cascading effect it produces, and confirm the three execution-tier jobs are gated at both registration and call time.

### Gates at issue (three layers)

| Layer | Primitive | Who it stops |
|---|---|---|
| Frontend | `<FeatureGate>` + `FEATURES[flag]` | Normal customers via the UI |
| Backend HTTP | `Depends(require_execution_enabled)` | Anyone hitting the route directly (curl, API client) |
| Backend runtime | `is_launch_mode_v1()` checks in scheduler jobs | Background automation that bypasses HTTP |

The verification must find gaps where any layer is missing. **Findings below confirm one gap** — scheduler auto-enrollment — which is fixed in the same cycle.

---

## B. Policy-to-endpoint coverage matrix (HTTP)

Every execution-capable or externally-effectful HTTP endpoint in the execution layer. Classified against `dangerous-action-policy.md`.

**Legend**:
- ✅ **Protected** — has `Depends(require_execution_enabled)`; returns 404 in v1
- 🟢 **Exempt** — no external effect per policy; intentionally unprotected
- 🟡 **Watch** — currently safe, flagged for re-audit if downstream behavior changes
- ❌ **Inconsistent** — classification disagrees with current protection (must be fixed in-cycle)

### Sequences

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `GET /companies/{id}/sequences/templates` | `list_templates` | None — read-only | 🟢 Exempt | Read; lists playbook templates |
| `POST /companies/{id}/sequences/activate-playbook` | `activate_playbook` | Clause 3: creates template + enrollments → cascades to future sends | ✅ Protected | `dependencies=[Depends(require_execution_enabled)]` verified at `sequences.py:49` |
| `GET /companies/{id}/sequences/enrollments` | `list_enrollments` | None — read-only | 🟢 Exempt | Read |
| `POST /companies/{id}/sequences/enrollments/{id}/pause` | `pause_enrollment` | None — state-only halt | 🟢 Exempt | Per policy "Pauses or halts an existing flow without sending anything new" |
| `POST /companies/{id}/sequences/enrollments/{id}/resume` | `resume_enrollment` | Resumes a scheduled enrollment: sets `status=ACTIVE` and `next_step_due=NOW`. Would cause the next step to be processed on the next sequence-runner tick — but the runner is gated in launch mode, so no send fires. | 🟢 Exempt + 🟡 Watch | Safe **only because the sequence runner gate exists at both registration and runtime**. This is a conditional classification: if the runner gate is ever weakened (e.g., a new endpoint triggers `run_due_steps` directly, or the call-time check is removed), `/resume` becomes a cascade trigger and must be added to `require_execution_enabled`. Cycle 4 self-challenge Challenge 1 flagged the dependency for explicit annotation. |

### Approvals

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `GET /companies/{id}/approvals` | `list_pending` | None | 🟢 Exempt | Read |
| `GET /companies/{id}/approvals/count` | `pending_count` | None | 🟢 Exempt | Read |
| `POST /companies/{id}/approvals/{id}/approve` | `approve_item` | Clause 1: triggers `_send_approved_email` background task → SendGrid | ✅ Protected | `approvals.py:72` |
| `POST /companies/{id}/approvals/bulk-approve` | `bulk_approve` | Clause 1: triggers batch SendGrid sends | ✅ Protected | `approvals.py:155` |
| `POST /companies/{id}/approvals/{id}/reject` | `reject_item` | None — sets `REJECTED` + writes internal `email_rejected` attribution event | 🟢 Exempt | Cycle 3 alignment; documented with in-line comment at `approvals.py:124-128` |

### Outreach / Send

No HTTP endpoint directly triggers a send. `SendGridMCPServer.send_email` is called exclusively from `_send_approved_email` in `approvals.py`, which is only scheduled as a background task from the two protected approve endpoints. Grep confirmation:

```
$ grep -rn "sendgrid.send_email\|\.send_email(" services/ agents/
```

Result: `_send_approved_email` is the only downstream invoker in the HTTP path. The `OutreachExecutorAgent` (used by workforce execution) also calls SendGrid, but its entry point is `run_execution` which is only reachable from the protected `POST /workforce/{id}/execute`.

| Call path | Gate | Status |
|---|---|---|
| `POST /approvals/{id}/approve` → `_send_approved_email` → `SendGridMCPServer.send_email` | `require_execution_enabled` on the approve endpoint | ✅ |
| `POST /approvals/bulk-approve` → `_send_approved_email` → `SendGridMCPServer.send_email` | Same | ✅ |
| `POST /workforce/{id}/execute` → `_run_execution_background` → `run_execution` → `OutreachExecutorAgent` → `SendGridMCPServer.send_email` | `require_execution_enabled` on the execute endpoint | ✅ |

### CRM Sync (HubSpot)

| Call path | Gate | Status |
|---|---|---|
| Workforce execution → `CRMSyncAgent` → `HubSpotMCPServer.create_or_update_contact` | `require_execution_enabled` on `/workforce/{id}/execute` | ✅ |

There is no HTTP endpoint that directly calls CRM sync outside of workforce execution. Verified by grep for `HubSpotMCPServer`:

```
$ grep -rln "HubSpotMCPServer\|create_or_update_contact" services/ agents/
```

Confirmed: only the `CRMSyncAgent` consumes HubSpot, and it is only invoked from `workforce_executor.run_execution`.

### Webhook handling

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `POST /api/v1/webhooks/sendgrid` | `sendgrid_webhook` | Clause test: does it cause external effect? No — it processes events that already happened. | 🟢 Exempt (documented) | Inbound events: (a) pauses enrollments via `pause_on_reply` (state-only halt); (b) records open/click `AttributionEvent` rows (internal log); (c) logs bounces (stdout). No send, no external API call. Advisory customers depend on it for delivery tracking. |

### Workforce

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `POST /companies/{id}/workforce/design` | `design_workforce` | None — kicks off background `WorkforceArchitectAgent` which produces a DRAFT config record only | 🟢 Exempt | Agent uses LLM provider (platform-billed, not customer-billed) so clause 4 does not apply. No external communication. |
| `GET /companies/{id}/workforce` | `get_workforce_config` | None | 🟢 Exempt | Read |
| `GET /companies/{id}/workforce/{id}` | `get_workforce_config_by_id` | None | 🟢 Exempt | Read |
| `PATCH /companies/{id}/workforce/{id}/approve` | `approve_workforce` | State-only: DRAFT → ACTIVE. BUT: an ACTIVE workforce is picked up by `_run_signal_monitor_all_active` (hourly) which then calls `auto_enroll_from_signals` → creates `SequenceEnrollment` rows. Per policy clause 3, this is a *cascading* state transition. | 🟡 Watch | Safe today because the cascade terminates at a gated scheduler job (sequence runner). **New gate added this cycle in scheduler** to prevent the enrollment creation itself in launch mode. See Finding F-1 below. After the fix, the cascade is broken at the auto-enroll call site, not just the sequence runner. No HTTP protection change needed. |
| `POST /companies/{id}/workforce/{id}/execute` | `trigger_execution` | Clause 3: cascades to outreach + CRM writes | ✅ Protected | `workforce.py:246` |
| `GET /companies/{id}/workforce/runs/list` | `list_execution_runs` | None | 🟢 Exempt | Read |
| `GET /companies/{id}/workforce/runs/{id}` | `get_execution_run` | None | 🟢 Exempt | Read |
| `GET /companies/{id}/workforce/metrics` | `get_workforce_metrics` | None | 🟢 Exempt | Read |

### Campaign activation / watch items

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `GET /companies/{id}/campaigns` | `list_campaigns` | None | 🟢 Exempt | Read |
| `POST /companies/{id}/campaigns` | `create_campaign` | None — creates a draft record | 🟢 Exempt | Internal artifact only |
| `PATCH /companies/{id}/campaigns/{id}` | `update_campaign` | None | 🟢 Exempt | Internal state |
| `DELETE /companies/{id}/campaigns/{id}` | `delete_campaign` | None | 🟢 Exempt | Internal state (destructive but not externally effectful). **Policy note**: "destructive" (destroys internal state) and "dangerous" (causes external effect) are orthogonal concerns. Destructive operations are governed by separate frontend gating (`settingsDangerZone` and similar) and do not belong in the dangerous-action matrix. |
| `POST /companies/{id}/campaigns/{id}/activate` | `activate_campaign` | None currently — sets `status=ACTIVE`, sets `start_date`. No scheduler job or downstream consumer acts on `CampaignStatus.ACTIVE`. | 🟢 Exempt + 🟡 Watch (LD-9) | Cycle 4 re-audit confirms the watch item is unchanged: grep for `CampaignStatus.ACTIVE` returns exactly one reference (the setter itself in `campaigns.py:228`). No consumers. Safe. Watch item remains for any future cycle that wires this up. |
| `POST /companies/{id}/campaigns/{id}/pause` | `pause_campaign` | None | 🟢 Exempt | Internal state |
| `POST /companies/{id}/campaigns/{id}/complete` | `complete_campaign` | None | 🟢 Exempt | Internal state |
| `POST /companies/{id}/campaigns/{id}/duplicate` | `duplicate_campaign` | None | 🟢 Exempt | Internal artifact |
| `POST /companies/{id}/campaigns/generate-content` | `generate_content` | Runs `CampaignArchitectAgent` via LLM provider, persists `GeneratedContent` rows. No outbound message. LLM cost is platform-billed. | 🟢 Exempt | Covered by clause-4 reading (billing is platform, not customer) and no external communication. |

### Attribution

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `POST /companies/{id}/attribution/events` | `record_event` | None — writes internal `AttributionEvent` row | 🟢 Exempt | Internal log; customer-recorded outcomes |
| `GET /companies/{id}/attribution/summary` | `attribution_summary` | None | 🟢 Exempt | Read |

### Signals

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `GET /companies/{id}/signals` | `list_signals` | None | 🟢 Exempt | Read |
| `POST /companies/{id}/signals/{id}/action` | `mark_actioned` | None — sets `is_actioned=True` | 🟢 Exempt | Internal state |

### Leads (status transitions)

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `POST /companies/{id}/leads/{id}/qualify` | `qualify_lead` | None — status change | 🟢 Exempt | Internal state |
| `POST /companies/{id}/leads/{id}/contact` | `mark_lead_contacted` | None — status change + timestamp | 🟢 Exempt | Internal state. Does *not* actually contact the lead — it records that a human has reached out. |
| `POST /companies/{id}/leads/{id}/convert` | `convert_lead` | None — status change | 🟢 Exempt | Internal state |

### Generic agent run endpoints

| Route | Handler | External effect | Classification | Rationale |
|---|---|---|---|---|
| `POST /api/v1/agents/{agent_name}/run` | `run_agent` | Depends on which agent. Current registry = 6 analysis agents only. | 🟢 Exempt (implicit) + 🟡 Watch | The registry at `agents_registry.py:65-72` narrows to: gtm-strategist, market-intelligence, competitor-analyst, customer-profiler, lead-hunter, campaign-architect. The `outreach-executor`, `crm-sync`, `workforce-architect`, `signal-monitor`, and `lead-enrichment` agents are NOT in the registry and cannot be invoked by name. **Implicit gate, not explicit.** Watch item: if anyone adds execution agents to the registry, this route becomes a bypass. |
| `POST /api/v1/companies/{id}/agents/{agent_id}/run` | `trigger_agent` | Same implicit narrowing via `validate_agent_id → is_valid_agent` | 🟢 Exempt (implicit) + 🟡 Watch | Same rationale |

**Coverage summary**:

| Classification | Count |
|---|---|
| ✅ Protected | 4 |
| 🟢 Exempt | ~30 |
| 🟡 Watch | 5 (LD-9, sequences/resume, workforce/approve (pre-fix), agents/run × 2) |
| ❌ Inconsistent | 0 (after Cycle 4 scheduler fix) |

---

## C. Policy-to-scheduler coverage matrix

The execution layer has a second surface: background jobs in `services/gateway/src/scheduler.py`. The dangerous-action policy has been stated in terms of HTTP endpoints — Cycle 4 extends it to scheduler jobs.

**Scheduler jobs inventory (18 total)**:

| Job ID | Schedule | External effect? | Launch-mode gating | Classification | Rationale |
|---|---|---|---|---|---|
| `signal_monitor_hourly` | every 1h | **Cascade**: calls `auto_enroll_from_signals` which creates `SequenceEnrollment` rows — a cascading state transition per policy clause 3 | ❌ **Ungated at call site** (fixed this cycle) | **Finding F-1** — see below | Signal monitoring itself is research (NewsAPI + EODHD + Perplexity reads); creating `SignalEvent` rows is internal. The dangerous step is the embedded `auto_enroll_from_signals` call at `scheduler.py:390`. |
| `sequence_runner_daily` | daily 08:00 SGT | Clause 1 + 3: processes due steps, creates approval queue items for eventual sending | ✅ Gated at registration + runtime | Correctly protected | `scheduler.py:93,428` |
| `lead_enrichment_weekly` | Sun 02:00 SGT | None currently — DNS MX validation + metadata enrichment; no outbound message | ✅ Gated at registration (not runtime) | Correctly gated; could add belt-and-suspenders runtime check for consistency but not required by policy | LeadEnrichmentAgent validates emails and enriches metadata. No send. |
| `roi_summary_weekly` | Mon 07:00 SGT | None currently — queries DB and logs. There is a TODO comment at `scheduler.py:537` to "send summary email" but no implementation. | ✅ Gated at registration (not runtime) | Correctly gated; monitor the TODO — if implemented, the job will become clause-1 dangerous and the runtime gate must be added | |
| `rss_ingestion` | every 2h | None — reads public RSS feeds, writes `MarketArticle` rows | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `sgx_discovery_daily` | 06:00 SGT | None — reads SGX API, writes announcement records | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `document_processing_daily` | 03:00 SGT | None — downloads corporate PDFs, extracts, embeds | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `financial_sync_daily` | 02:00 SGT | None — EODHD API reads, writes `CompanyFinancialSnapshot` | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `sgx_roster_weekly` | Sat 01:00 SGT | None — EODHD API reads | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `article_pipeline_bihourly` | every 2h at :30 | None — classifies + embeds articles | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `qdrant_catchup_daily` | 05:00 SGT | None — embeds document chunks | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `vertical_benchmarks_daily` | 04:00 SGT | None — computes percentile benchmarks | Not gated (correct) | 🟢 Exempt | Analytics pipeline |
| `document_intelligence_daily` | 04:15 SGT | None — extracts business signals from document chunks | Not gated (correct) | 🟢 Exempt | Analytics pipeline |
| `research_embedder_bihourly` | every 2h at :45 | None — embeds public research cache rows | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `sg_reference_weekly` | Sun 04:00 SGT | None — scrapes PSG/PDPC/MAS public pages | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `guide_resynthesis_weekly` | Sat 03:00 SGT | None — re-synthesizes domain guides | Not gated (correct) | 🟢 Exempt | Research pipeline |
| `gtm_financial_extraction_daily` | 04:30 SGT | None — extracts GTM insights from annual reports | Not gated (correct) | 🟢 Exempt | Analytics pipeline |
| `vertical_intelligence_weekly` | Sun 05:00 SGT | None — synthesizes vertical reports | Not gated (correct) | 🟢 Exempt | Analytics pipeline |

---

## D. Findings

### F-1 — Scheduler `auto_enroll_from_signals` is ungated in launch mode (fixed this cycle)

**Severity**: Medium (defense-in-depth gap; no customer-visible effect today because of downstream gates, but a single gate failure would expose the cascade).

**Location**: `services/gateway/src/scheduler.py:386-405` inside `_run_signal_monitor_all_active`.

**What it does**: After running the `SignalMonitorAgent` for each company with an `ACTIVE` `WorkforceConfig`, the job calls:

```python
engine = SequenceEngine(db)
enrollments = await engine.auto_enroll_from_signals(
    company_id=str(company.id),
    db=db,
)
```

`auto_enroll_from_signals` (sequence_engine.py:312) creates new `SequenceEnrollment` rows with `status=ACTIVE` and `next_step_due=NOW`. These rows are the cascading state that the daily `sequence_runner_daily` job would then process into `ApprovalQueueItem` rows, which an approver would then turn into SendGrid emails.

**Why it is a gap**:
- The policy's clause 3 (cascading state transition) applies: creating these rows transitions the lead into a state "whose downstream automation produces external effects later."
- The signal monitor job itself is NOT gated by launch mode (correctly — its research calls are harmless and used by non-execution surfaces like `/today`'s signal preview).
- The enrollment creation is invisible to HTTP clients but is a cascading step the policy cares about.
- Today the cascade is terminated by (a) the sequence runner being registration-gated + call-time-gated, and (b) the workforce HTTP route `/execute` being protected. So in current production, no send actually fires.
- But the invariant relies on **two other gates** to hold. If either gate is weakened in a future cycle (e.g., someone adds a new scheduler job that processes enrollments, or someone adds a new endpoint that triggers `run_due_steps`), this call becomes an active cascading step with no local check.

**What reality looks like without the fix**: In `GTM_LAUNCH_MODE=v1`, every hour the signal monitor runs for every company that has an ACTIVE `WorkforceConfig`. For each such company with recent high-relevance signals, the enrollment rows accumulate in the database. They never process because the sequence runner is off. The DB grows with orphan enrollments. On the day launch mode flips off, the accumulated backlog of enrollments would begin processing on the next sequence-runner tick — a sudden burst of approval-queue items from signals that are by that time possibly stale.

**Fix (applied this cycle)**: Add a call-time `is_launch_mode_v1()` check in `_run_signal_monitor_all_active` around the auto-enrollment call. The signal monitoring itself still runs (benign research + `SignalEvent` rows). Only the enrollment creation is gated.

**Why this is not "widening launch behavior"**: the fix *narrows* behavior. The current behavior creates enrollments; after the fix, in launch mode, it does not. No surface is exposed, no flag is promoted, no new endpoint is added.

**Acceptance**: Both runtime enforcement and a regression test exist so a future edit to `scheduler.py` that removes the gate is caught by CI.

### F-2 — Workforce `/approve` transition is cascading-adjacent but does not need HTTP protection after F-1 fix

**Severity**: Low (observation).

**Location**: `services/gateway/src/routers/workforce.py:205-237`.

**Observation**: The `PATCH /workforce/{id}/approve` endpoint transitions `WorkforceConfig` from DRAFT to ACTIVE. An ACTIVE `WorkforceConfig` is the selector used by `_run_signal_monitor_all_active` to know which companies to monitor. Before the F-1 fix, an ACTIVE workforce implicitly enabled the auto-enrollment cascade.

**Why this is not a finding that requires HTTP protection**: After F-1, the cascade is broken at the scheduler call site in launch mode. The `/approve` endpoint itself has no external effect — it sets two internal fields (`status` and `approved_agents`) and one timestamp. Per policy, that is state-only.

**Why leave it as a watch item rather than protect it**: protecting `/approve` would be an aesthetic fix (symmetry with `/execute`) not a policy-aligned fix. Cycle 3 removed an aesthetic protection (`reject_item`) to honor the "protect what is dangerous, leave the rest alone" discipline. Adding a new aesthetic protection here would be a regression of that discipline. The correct gate is at the cascade's actual exit point in the scheduler, which is exactly where F-1 placed it.

### F-3 — `lead_enrichment_weekly` and `roi_summary_weekly` lack belt-and-suspenders runtime gate

**Severity**: Low (consistency observation, not a safety gap).

**Location**: `scheduler.py:450,500`.

**Observation**: `_run_sequence_runner` has a call-time `is_launch_mode_v1()` check as a belt-and-suspenders defense against the env var being unset at scheduler startup but set later. The other two execution-tier jobs (`_run_lead_enrichment_all`, `_run_weekly_roi_summary`) do not have the same check.

**Why this is not fixed in Cycle 4**:
- Neither of these jobs currently has any external effect (lead enrichment validates emails and enriches metadata; ROI summary queries the DB and logs).
- They are already gated at registration time (`if not _LAUNCH_MODE_V1`).
- Adding a call-time check would be consistent with `_run_sequence_runner` but is not required by the policy and would not prevent anything that can happen today.
- Cycle 4's constraint is "verification first, enablement second, no widening" — adding the checks is a polish item, not a safety fix.
- **Added to launch debt register as LD-10** (new) for Cycle 5 polish sweep.

**Watch trigger**: the TODO at `scheduler.py:537` ("send summary email") would make `_run_weekly_roi_summary` clause-1 dangerous. If that TODO is implemented, the runtime gate is required at the same time.

### F-4 — `/agents/{name}/run` endpoints are implicitly gated by the narrow registry

**Severity**: Low (latent risk, not a current gap).

**Location**: `services/gateway/src/agents_registry.py:56-73` and consumers at `routers/agents.py:109` and `routers/company_agents.py:167`.

**Observation**: The two `/agents/{name}/run` endpoints (global and company-scoped) will execute any agent whose ID passes `is_valid_agent()`. The registry narrows this to the 6 analysis agents. Execution agents (`outreach-executor`, `crm-sync`, `workforce-architect`, `signal-monitor`, `lead-enrichment`) are NOT in the registry, so they cannot be invoked by name through these routes.

**Why it is a latent risk**: If someone adds an execution agent to the registry in the future, these two endpoints become unprotected bypasses into the execution layer. There is no test that would catch this.

**Proposed mitigation (not applied in Cycle 4)**: add a unit test that asserts the `AGENT_METADATA` dict contains *only* the 6 analysis agent IDs and fails if an execution agent is added without explicit protection. This would be a single-line assertion test and is a genuine safety fix.

**Decision**: added to launch debt register as **LD-11** for Cycle 5 or 6. Not applied in Cycle 4 because:
1. The current state is safe.
2. Adding the test requires weighing whether to assert an exact list or a deny list.
3. Cycle 4's scope is verification and finding-driven fixes; this is a future-proofing item.

### F-5 — Webhook handler is correctly unprotected; no send path exists

**Severity**: None (verification-pass).

**Location**: `services/gateway/src/routers/webhooks.py`.

**Verified**: the webhook only (a) pauses enrollments via `pause_on_reply`, (b) records `email_opened`/`email_clicked` attribution events, (c) logs bounces. No `SendGridMCPServer.send_email` call. No HubSpot write. No cascading state. The intentional exemption in `dangerous-action-policy.md` is correct and no change is needed.

### F-6 — `/campaigns/{id}/activate` watch item (LD-9) re-audit

**Severity**: None (watch pass).

**Re-audit result**: `grep -r CampaignStatus.ACTIVE services/ agents/` returns exactly **one** hit — the setter itself in `campaigns.py:228`. No scheduler job, no agent, no other router acts on `CampaignStatus.ACTIVE`. The activate endpoint remains state-only and correctly exempt. LD-9 stays on the watch list for any future cycle that wires activation to actual execution.

### F-7 — Content generation route is correctly exempt

**Severity**: None (verification-pass).

**Verified**: `POST /campaigns/generate-content` calls `CampaignArchitectAgent` which uses the LLM provider. LLM API calls are billed to the platform, not the customer. No external communication is produced. The generated content is stored as `GeneratedContent` rows. Classification: 🟢 Exempt. Not a dangerous action under any policy clause.

---

## E. Required safety / correctness fixes

One fix, for F-1. The other findings are observations, watch items, or debt register entries.

**File**: `services/gateway/src/scheduler.py`
**Change**: in `_run_signal_monitor_all_active`, skip the `auto_enroll_from_signals` call when `is_launch_mode_v1()` returns true. Log the skip with a clear reason. Leave the signal monitoring itself running.
**Tests**: regression test in `tests/unit/test_launch_mode_deny.py` that patches `_LAUNCH_MODE_V1` and confirms the auto-enroll call is skipped.

---

## F. What is NOT done this cycle (by design)

These were explicitly scoped out by the Cycle 4 verification-first rule:

- No new protected endpoints beyond the existing 4. (F-2 explicitly argues against adding one.)
- No new scheduler jobs.
- No frontend changes.
- No content-studio QA gate execution.
- No flag promotions.
- LD-10 (belt-and-suspenders runtime gates for non-dangerous scheduled jobs): deferred.
- LD-11 (registry assertion test): deferred.
- LD-9 (campaigns/activate watch item): re-audited as safe, stays on watch list.

---

## G. Promotion / launch-exposure delta

**Has launch exposure changed this cycle?** No. Zero dashboard changes. Zero nav changes. Zero new endpoints. Zero flag promotions.

**Has launch behavior changed this cycle?** Yes, narrowed only: in `GTM_LAUNCH_MODE=v1`, the signal monitor no longer creates `SequenceEnrollment` rows. Before: enrollments accumulated in DB; after: they do not. This is a strict reduction of state mutation in launch mode.

**Has launch promise changed this cycle?** No. The customer-facing story is unchanged; the surfaces covered by `promise-scope-audit.md` are unchanged.

**What a hostile reviewer would still attack**: see the red-team memo (`cycle-4-redteam.md`).
