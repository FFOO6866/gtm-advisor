# Hi Meet AI — Feature Flag Registry

**Source of truth**: `services/dashboard/src/config/features.ts`
**Gate primitive**: `services/dashboard/src/components/FeatureGate.tsx`
**Backend gate**: `GTM_LAUNCH_MODE=v1` env var (scheduler execution jobs)

## Launch posture by build

| Build | Env | Visible flags |
|-------|-----|--------------|
| **Production** | `VITE_LAUNCH_MODE` unset or != `internal` | Launch surfaces only (8 flags true) |
| **Internal** | `VITE_LAUNCH_MODE=internal` | All flags true |

## Flag inventory

### Launch surfaces (always true)

| Flag | Route | Nav label | Notes |
|------|-------|-----------|-------|
| `today` | `/today` | Today | Daily briefing (vertical benchmarks, prospects, signals preview) |
| `analysis` | `/` | Run Analysis | Core analysis flow (OnboardingModal → AgentNetwork → ResultsPanel) |
| `campaignPlans` | `/campaigns` | Campaign Plans | **To be renamed in Cycle 2** (currently "Campaigns") |
| `prospects` | `/prospects` | Prospects | Lead Kanban |
| `settings` | `/settings` | Settings | **To be stripped in Cycle 3** (hide API keys, danger zone) |
| `whyUs` | `/why-us` | Why Us | Static differentiator content |
| `login` | `/login` | — | Public auth |
| `register` | `/register` | — | Public auth |

**Total: 8 launch flags. 6 nav items (login/register not in SidebarNav).**

### Gated surfaces (false by default; true in INTERNAL)

| Flag | Route | Gating reason | Promotion path |
|------|-------|--------------|---------------|
| `contentBeta` | `/content` | Output quality is the product; must pass 3-vertical QA | Cycle 3 QA gate |
| `signalsFeed` | `/insights`, `/signals` | Cold-start empty; preview exists on TodayPage | Reopen post-launch when data freshness is guaranteed |
| `playbooks` | `/playbooks` | Browse-only with disabled Activate is a dead-end | Reopen when activation flow is built (v1.1) |
| `approvals` | `/approvals` | Advisory-only; requires SendGrid + sequences | Advisory-mode only |
| `sequences` | `/sequences` | Advisory-only; PDPA compliance requires interview | Advisory-mode only |
| `workforce` | `/workforce` | Abstract concept; hard to support | Defer until execution is proven for 3+ customers |
| `attributionResults` | `/results` | Zero KPIs without outreach data | Reopen when outreach has ≥ 30 days of data |
| `dashboardOps` | `/dashboard` | Duplicate of `/today` | Permanently hidden (internal ops view only) |
| `agentWorkspaces` | `/agent/*` (8 routes) | 8 mini-apps; support burden | Power-user feature, v1.2+ |
| `strategyWorkspace` | (reserved) | Separate deferred feature | Post-launch branch |

### Within-page gates

| Flag | Effect |
|------|--------|
| `campaignActivation` | Hides "Activate" / "Pause" buttons on Campaign Plans page |
| `leadSequenceEnroll` | Hides "Enroll in Sequence" action on lead cards |
| `contentEmailSend` | Hides "Send" button in Content Studio email tab |
| `settingsApiKeys` | Hides API key section on SettingsPage |
| `settingsDangerZone` | Hides "Clear all data" button on SettingsPage |
| `todayAttributionKpis` | Hides Attribution KPIs section on TodayPage |

## Rules for adding / changing flags

1. **Any new flag requires an entry in this file** — PR is blocked otherwise
2. **Promotion from gated → launch** requires:
   - Red-team sign-off in the cycle memo
   - All user-visible copy says "Hi Meet AI"
   - Empty states exist for every data condition
   - Support team has a response for the first likely ticket
3. **Removal of a flag** requires documenting it in the cycle memo as "feature retired"
4. **No runtime toggling**: flags are compile-time constants. Changing a flag requires a rebuild.

## Backend scheduler gating

`GTM_LAUNCH_MODE=v1` disables 3 execution-tier scheduler jobs:

| Job ID | Schedule | Disabled in v1 | Reason |
|--------|---------|---------------|--------|
| `sequence_runner_daily` | 08:00 SGT daily | ✅ | No outreach UI at launch |
| `lead_enrichment_weekly` | Sun 02:00 SGT | ✅ | No re-enrichment pipeline exposed |
| `roi_summary_weekly` | Mon 07:00 SGT | ✅ | No attribution data yet |

**14 other scheduler jobs remain enabled** (RSS ingestion, financial sync, vertical benchmarks, signal monitor, article intelligence, etc.).

## Emergency kill switch

If a launch surface goes wrong in production and we need to hide it **without a frontend rebuild**, the options are:
- Rely on the backend to return a 503 or empty data (frontend shows empty state)
- Hotfix: flip the flag and redeploy (no runtime toggle exists)

**Decision for v1**: no runtime kill switch. A rebuild is required. This keeps the flag system simple and the launch posture explicit.
