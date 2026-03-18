/**
 * Vertical Intelligence API — the canonical source of industry data.
 *
 * Single endpoint returns the full VerticalIntelligenceReport for the
 * company's vertical.  Frontend pages consume whichever sections they need.
 */

import { apiClient } from './client';

// ---------------------------------------------------------------------------
// Response types — aligned with backend VerticalIntelligenceResponse
// ---------------------------------------------------------------------------

export interface GTMImplication {
  insight: string;
  evidence: string | null;
  recommended_action: string | null;
  priority: string | null;
}

export interface FinancialPulse {
  sga_median: number | null;
  sga_trend: string | null;
  rnd_median: number | null;
  rnd_trend: string | null;
  margin_compression_or_expansion: string | null;
  capex_intensity: number | null;
  top_spenders: Array<{
    ticker?: string;
    name?: string;
    sga_to_revenue?: number;
  }>;
}

export interface CompetitiveDynamics {
  leaders: Array<Record<string, unknown>>;
  challengers: Array<Record<string, unknown>>;
  movers: Array<Record<string, unknown>>;
  new_entrants: Array<Record<string, unknown>>;
  exits: Array<Record<string, unknown>>;
}

export interface SignalDigestItem {
  headline: string;
  signal_type: string | null;
  source: string | null;
  published_at: string | null;
  companies_mentioned: string[];
}

export interface ExecutiveMovement {
  company: string | null;
  name: string | null;
  old_title: string | null;
  new_title: string | null;
  change_type: string | null;
  date: string | null;
}

export interface RegulatoryItem {
  title: string;
  summary: string | null;
  source: string | null;
  impact: string | null;
}

export interface KeyTrend {
  trend: string;
  evidence: string | null;
  impact: string | null;
  source_count: number | null;
}

export interface VerticalIntelligenceData {
  id: string;
  vertical_slug: string | null;
  vertical_name: string | null;
  report_period: string;
  computed_at: string | null;
  market_overview: Record<string, unknown>;
  key_trends: KeyTrend[];
  competitive_dynamics: CompetitiveDynamics;
  financial_pulse: FinancialPulse;
  signal_digest: SignalDigestItem[];
  executive_movements: ExecutiveMovement[];
  regulatory_environment: RegulatoryItem[];
  gtm_implications: GTMImplication[];
  data_sources: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

export async function fetchVerticalIntelligence(
  companyId: string,
): Promise<VerticalIntelligenceData | null> {
  return apiClient
    .get<VerticalIntelligenceData>(
      `/companies/${companyId}/market-data/vertical-intelligence`,
    )
    .catch(() => null);
}
