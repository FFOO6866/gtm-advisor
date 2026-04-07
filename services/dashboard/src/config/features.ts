/**
 * Hi Meet AI — Feature Flag Registry
 *
 * Single source of truth for launch exposure.
 *
 * Build completeness and launch exposure are separate concerns:
 *   - Code for hidden features lives in the repo and is testable.
 *   - Launch exposure is controlled by this file at build time.
 *
 * Internal QA and advisory-mode access: set VITE_LAUNCH_MODE=internal
 * to flip all gated flags to true in a local/dev build.
 *
 * Production builds (no env var set, or anything other than "internal")
 * get the conservative launch package: 6 nav items, no execution surfaces,
 * no outreach UI, no agent workspaces.
 *
 * Governance:
 *   - Adding a new flag REQUIRES updating docs/launch/feature-flags.md
 *   - Promoting a flag from gated → launch REQUIRES a cycle red-team sign-off
 *   - This file is the only place that decides visibility. Components and
 *     routes should import from here, never hardcode flags.
 */

const INTERNAL = import.meta.env.VITE_LAUNCH_MODE === 'internal';

export const FEATURES = {
  // --------------------------------------------------------------------
  // LAUNCH SURFACES — always visible in production
  // --------------------------------------------------------------------
  /** /today — daily briefing (vertical benchmarks, prospects, signals preview) */
  today: true,
  /** / — analysis flow (OnboardingModal + AgentNetwork + ResultsPanel) */
  analysis: true,
  /** /campaigns — Campaign Plans (renamed in Cycle 2) */
  campaignPlans: true,
  /** /prospects — Lead pipeline Kanban */
  prospects: true,
  /** /settings — stripped Settings (profile + display prefs) */
  settings: true,
  /** /why-us — static differentiator page */
  whyUs: true,
  /** Auth pages */
  login: true,
  register: true,

  // --------------------------------------------------------------------
  // GATED SURFACES — hidden in production, visible only in INTERNAL builds
  // --------------------------------------------------------------------
  /** /content — Content Studio. Launch-day QA gate required. Default HIDDEN. */
  contentBeta: INTERNAL,
  /** /insights — standalone Signals Feed. Preview lives on /today instead. */
  signalsFeed: INTERNAL,
  /** /playbooks — browse playbook library. Hidden until activation flow is built. */
  playbooks: INTERNAL,
  /** /approvals — advisory-only surface for outreach approval. Hidden at launch. */
  approvals: INTERNAL,
  /** /sequences — advisory-only sequence management. Hidden at launch. */
  sequences: INTERNAL,
  /** /workforce — Digital Workforce designer. Hidden until execution is proven. */
  workforce: INTERNAL,
  /** /results — ROI attribution page. Hidden until outreach has data. */
  attributionResults: INTERNAL,
  /** /dashboard — internal ops metrics. Duplicate of /today with worse UX. */
  dashboardOps: INTERNAL,
  /** /agent/* — 8 per-agent workspace pages. Power-user feature. */
  agentWorkspaces: INTERNAL,
  /** /strategy or similar deferred surfaces */
  strategyWorkspace: INTERNAL,

  // --------------------------------------------------------------------
  // WITHIN-PAGE GATES — control CTAs and sections inside otherwise-launch pages
  // --------------------------------------------------------------------
  /** Campaign activation/pause buttons (execution-implying CTAs) */
  campaignActivation: INTERNAL,
  /** "Enroll in sequence" action on lead cards */
  leadSequenceEnroll: INTERNAL,
  /** "Send email" button inside Content Studio email tab */
  contentEmailSend: INTERNAL,
  /** API-key management section on SettingsPage */
  settingsApiKeys: INTERNAL,
  /** Danger-zone (clear all data) section on SettingsPage */
  settingsDangerZone: INTERNAL,
  /** Attribution KPIs section inside TodayPage */
  todayAttributionKpis: INTERNAL,
} as const;

export type FeatureFlag = keyof typeof FEATURES;

/**
 * Runtime check whether the app is running in internal mode.
 * Use sparingly — prefer FEATURES[flag] for individual surfaces.
 */
export const IS_INTERNAL_BUILD = INTERNAL;
