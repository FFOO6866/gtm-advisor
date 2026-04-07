# Hi Meet AI — v1 Launch Package

**What the customer sees on day 1.**

This document is the definitive list of user-visible surfaces at launch. It diffs against the actual application state in each cycle's end-of-cycle integration review. If this doc and the app disagree, this doc wins and the app is corrected.

## Visible nav items (in SidebarNav order)

```
Primary
├── Today              → /today
├── Run Analysis       → /
├── Campaign Plans     → /campaigns       (renamed from "Campaigns" in Cycle 2)
└── Prospects          → /prospects

Bottom
├── Why Us             → /why-us
└── Settings           → /settings
```

**6 nav items.** Everything else is hidden.

## Visible pages

| Route | Page | Launch status | Notes |
|-------|------|--------------|-------|
| `/login` | LoginPage | Launch | Public |
| `/register` | RegisterPage | Launch | Public |
| `/` | Dashboard (teaser + analysis flow) | Launch | OnboardingModal + AgentNetwork + ConversationPanel + ResultsPanel |
| `/today` | TodayPage | Launch | Post-login landing; 3 sections (benchmarks, prospects, signals preview) |
| `/campaigns` | CampaignsPage | Launch (as "Campaign Plans") | Planning posture; no Activate CTAs |
| `/prospects` | LeadsPipeline | Launch | Kanban view; no Enroll CTA |
| `/settings` | SettingsPage | Launch (stripped) | Profile + display prefs only |
| `/why-us` | WhyUsPage | Launch | Static |
| `/leads` | (redirects) | — | 301 → `/prospects` |

**11 routes, 8 pages (plus 1 alias redirect).**

## Hidden pages (code exists, routes guarded)

| Route | Gate flag | Cycle where it becomes visible (if ever) |
|-------|-----------|-------------------------------------------|
| `/content` | `contentBeta` | Cycle 3 QA gate; otherwise stays hidden |
| `/insights` | `signalsFeed` | v1.1 |
| `/signals` | `signalsFeed` | v1.1 |
| `/results` | `attributionResults` | When outreach has data |
| `/approvals` | `approvals` | Advisory-only, never public |
| `/sequences` | `sequences` | Advisory-only, never public |
| `/playbooks` | `playbooks` | v1.1 |
| `/workforce` | `workforce` | v1.2+ |
| `/dashboard` | `dashboardOps` | Internal only, never public |
| `/agent/market-intelligence` | `agentWorkspaces` | v1.2+ |
| `/agent/campaign-architect` | `agentWorkspaces` | v1.2+ |
| `/agent/lead-hunter` | `agentWorkspaces` | v1.2+ |
| `/agent/gtm-strategist` | `agentWorkspaces` | v1.2+ |
| `/agent/competitor-analyst` | `agentWorkspaces` | v1.2+ |
| `/agent/customer-profiler` | `agentWorkspaces` | v1.2+ |
| `/agent/company-enricher` | `agentWorkspaces` | v1.2+ |
| `/agent/:agentId` | `agentWorkspaces` | v1.2+ |

**17 hidden routes.** All redirect to `/today` via `FeatureGate` in production builds.

## Customer capabilities at launch

What a v1 customer can do, end-to-end:

1. **Register** with email + company name
2. **Log in** (30-min access token with refresh)
3. **Run an analysis**: upload a document or paste a URL, answer onboarding questions, watch the 6 AI specialists work in real time
4. **See results**: executive summary, prospects with fit scores, competitor intelligence, market trends, campaign ideas, full report export
5. **Check daily briefing** (`/today`): vertical benchmarks, recent prospects, live signals preview
6. **Manage prospects** (`/prospects`): Kanban workflow — New → Qualified → Contacted → Won/Lost; manual status transitions only
7. **Plan campaigns** (`/campaigns`): create campaign drafts from analysis insights; no execution
8. **Export** the full GTM report as JSON

What a v1 customer **cannot** do:

- ❌ Send outreach emails (execution layer hidden)
- ❌ Enroll leads in sequences (execution layer hidden)
- ❌ See attribution / ROI dashboards (no data yet)
- ❌ Sync to HubSpot or other CRMs (integration hidden)
- ❌ Access individual agent workspaces (power-user feature hidden)
- ❌ Activate playbooks (browse-only, and even browse is hidden at v1)

## Launch story

See `docs/launch/naming-conventions.md` for the canonical customer-facing message.

## Diff check protocol

At the end of every cycle, run this diff:

1. **Nav items** — `services/dashboard/src/components/SidebarNav.tsx` should list exactly the 6 items above. If it lists more, either (a) add them here and justify, or (b) remove them from SidebarNav.
2. **Routes** — `services/dashboard/src/App.tsx` should have: unguarded routes for the 11 above + `<FeatureGate>`-wrapped routes for the 17 hidden ones. Any unguarded hidden route is a regression.
3. **CTAs** — grep `services/dashboard/src/pages/` for button labels matching: "Activate", "Send", "Enroll", "Launch Campaign", "Design Workforce". Each hit must be either removed or gated.
4. **Story match** — user-visible copy (page titles, empty states, marketing headers) should not contradict the canonical launch story.

Cycle end is not complete until this diff is clean.
