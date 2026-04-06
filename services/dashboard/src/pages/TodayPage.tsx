/**
 * TodayPage — Executive Intelligence Brief
 *
 * One-screen layout a CEO reads in 30 seconds:
 *   1. Action bar — what needs deciding right now (top, prominent)
 *   2. Market pulse — one visual card, one insight
 *   3. Top opportunities — 3 insight rows, each one line + action
 *   4. Pipeline + performance — funnel bar + conversion chain
 *
 * Design: visual indicators first (bars, dots, arrows, numbers),
 * text only as annotation. No scrolling needed on desktop.
 */

import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  Bell,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';
import {
  fetchVerticalIntelligence,
  type VerticalIntelligenceData,
} from '../api/verticalIntelligence';
import { SegmentedBar } from '../components/common/MiniCharts';

// ============================================================================
// Types
// ============================================================================

interface PercentileData {
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p90: number | null;
}

interface BenchmarkPeriod {
  period_label: string;
  period_type: string;
  company_count: number;
  revenue_growth_yoy: PercentileData | null;
  gross_margin: PercentileData | null;
  ebitda_margin: PercentileData | null;
  net_margin: PercentileData | null;
  sga_to_revenue: PercentileData | null;
  rnd_to_revenue: PercentileData | null;
  operating_margin: PercentileData | null;
}

interface LeaderLaggard {
  ticker: string;
  name: string;
  exchange: string | null;
  revenue_growth_yoy: number | null;
  gross_margin: number | null;
}

interface VerticalSummary {
  vertical_slug: string | null;
  vertical_name: string | null;
  industry_category: string | null;
  listed_companies_count: number;
  market_cap_total_sgd: number | null;
  benchmarks: BenchmarkPeriod[];
  leaders: LeaderLaggard[];
  laggards: LeaderLaggard[];
}

interface MarketSignal {
  id: string;
  signal_type: string;
  urgency: string;
  headline: string;
  summary: string | null;
  source: string | null;
  source_url: string | null;
  relevance_score: number;
  recommended_action: string | null;
  published_at: string | null;
  created_at: string;
}

interface MarketArticle {
  id: string;
  title: string;
  source_name: string | null;
  signal_type: string | null;
  published_at: string | null;
  source_url: string | null;
}

interface IndustrySignalsData {
  signals: MarketSignal[];
  articles: MarketArticle[];
}

interface PipelineStatusCount {
  status: string;
  count: number;
}

interface RecentLead {
  id: string;
  lead_company_name: string | null;
  contact_name: string | null;
  contact_title: string | null;
  fit_score: number;
  overall_score: number;
  status: string;
  created_at: string | null;
  pain_points: string[];
  trigger_events: string[];
  recommended_approach: string | null;
}

interface PipelineSummaryData {
  total_leads: number;
  by_status: PipelineStatusCount[];
  avg_fit_score: number | null;
  avg_overall_score: number | null;
  recent_leads: RecentLead[];
}

interface AttributionSummary {
  period_days: number;
  emails_sent: number;
  replies: number;
  reply_rate_pct: number;
  meetings_booked: number;
  pipeline_value_sgd: number;
  meeting_to_email_ratio: number;
  breakdown: Record<string, { count: number; pipeline_sgd: number }>;
}

interface BriefingStatus {
  has_completed_analysis: boolean;
  last_analysis_at: string | null;
}

// ============================================================================
// Helpers
// ============================================================================

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  if (diff < 0) return 'just now';
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const URGENCY_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  immediate: { dot: 'bg-red-400', bg: 'bg-red-500/10', text: 'text-red-400' },
  this_week: { dot: 'bg-amber-400', bg: 'bg-amber-500/10', text: 'text-amber-400' },
  this_month: { dot: 'bg-blue-400', bg: 'bg-blue-500/10', text: 'text-blue-400' },
  monitor: { dot: 'bg-white/30', bg: 'bg-white/5', text: 'text-white/50' },
};

const PRIORITY_DOT: Record<string, string> = {
  high: 'bg-red-400',
  medium: 'bg-amber-400',
  low: 'bg-blue-400',
};

// ============================================================================
// 1. ACTION BAR — Decisions needed, always on top
// ============================================================================

function ActionBar({
  pendingApprovals,
  urgentSignalCount,
  topSignal,
}: {
  pendingApprovals: number;
  urgentSignalCount: number;
  topSignal: MarketSignal | null;
}) {
  const navigate = useNavigate();

  if (pendingApprovals === 0 && urgentSignalCount === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-wrap gap-2"
    >
      {pendingApprovals > 0 && (
        <button
          onClick={() => navigate('/approvals')}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 transition-all group"
        >
          <Bell className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-medium text-amber-400">
            {pendingApprovals} email{pendingApprovals !== 1 ? 's' : ''} to approve
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-amber-400/50 group-hover:translate-x-0.5 transition-transform" />
        </button>
      )}
      {topSignal && (
        <button
          onClick={() =>
            navigate(`/campaigns?signal=${topSignal.id}&playbook=signal_triggered&headline=${encodeURIComponent(topSignal.headline)}`)
          }
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 transition-all group"
        >
          <Zap className="w-4 h-4 text-red-400" />
          <span className="text-sm font-medium text-red-400 truncate max-w-[260px]">
            {topSignal.headline}
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-red-400/50 group-hover:translate-x-0.5 transition-transform" />
        </button>
      )}
    </motion.div>
  );
}

// ============================================================================
// 2. MARKET PULSE — One card, visual bar + insight sentence
// ============================================================================

function MarketPulseCard({
  verticalData,
  intelligence,
}: {
  verticalData: VerticalSummary | null;
  intelligence: VerticalIntelligenceData | null;
}) {
  const navigate = useNavigate();
  const fp = intelligence?.financial_pulse;
  const annualBenchmark = verticalData?.benchmarks.find((b) => b.period_type === 'annual');
  const verticalName = verticalData?.vertical_name ?? intelligence?.vertical_name;

  if (!fp && !annualBenchmark && !verticalName) return null;

  const sgaPct = fp?.sga_median != null ? fp.sga_median * 100 : null;
  const growth = annualBenchmark?.revenue_growth_yoy?.p50;
  const marginDir = fp?.margin_compression_or_expansion;

  // One-sentence headline
  let headline = '';
  if (sgaPct != null) {
    const trend = fp?.sga_trend === 'increasing' ? 'rising' : fp?.sga_trend === 'decreasing' ? 'falling' : 'steady';
    headline = `Clients spend ${sgaPct.toFixed(0)}% on GTM — ${trend}`;
  } else if (growth != null) {
    headline = `Sector growing at ${growth.toFixed(1)}% YoY`;
  }

  // Sub-indicators
  const indicators: { label: string; value: string; trend?: 'up' | 'down' | 'neutral' }[] = [];

  if (growth != null) {
    indicators.push({
      label: 'Growth',
      value: `${growth >= 0 ? '+' : ''}${growth.toFixed(1)}%`,
      trend: growth > 0 ? 'up' : growth < 0 ? 'down' : 'neutral',
    });
  }
  if (sgaPct != null) {
    indicators.push({
      label: 'GTM spend',
      value: `${sgaPct.toFixed(0)}%`,
      trend: fp?.sga_trend === 'increasing' ? 'up' : fp?.sga_trend === 'decreasing' ? 'down' : 'neutral',
    });
  }
  if (marginDir) {
    indicators.push({
      label: 'Margins',
      value: marginDir === 'compressing' ? 'Compressing' : 'Expanding',
      trend: marginDir === 'expanding' ? 'up' : 'down',
    });
  }

  const companyCount = verticalData?.listed_companies_count ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className="glass-card rounded-xl border border-white/10 p-5 cursor-pointer hover:border-white/15 transition-colors"
      onClick={() => navigate('/insights?tab=industry')}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
          {verticalName ?? 'Market Pulse'}
          {companyCount > 0 && <span className="text-white/15 ml-2">{companyCount} companies</span>}
        </p>
        <ArrowRight className="w-3 h-3 text-white/20" />
      </div>

      {/* Headline */}
      {headline && (
        <p className="text-base font-medium text-white mb-3">{headline}</p>
      )}

      {/* Visual indicator bars */}
      {indicators.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {indicators.map((ind) => (
            <div key={ind.label}>
              <div className="flex items-center gap-1.5 mb-1">
                {ind.trend === 'up' && <TrendingUp className="w-3 h-3 text-emerald-400" />}
                {ind.trend === 'down' && <TrendingDown className="w-3 h-3 text-red-400" />}
                <span className={`text-sm font-semibold tabular-nums ${
                  ind.trend === 'up' ? 'text-emerald-400' : ind.trend === 'down' ? 'text-red-400' : 'text-white'
                }`}>
                  {ind.value}
                </span>
              </div>
              <p className="text-[10px] text-white/30">{ind.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* SGA visual bar — how much clients spend on GTM */}
      {sgaPct != null && (
        <div className="mt-3 pt-3 border-t border-white/5">
          <div className="h-2 rounded-full bg-white/5 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-purple-500/60 to-purple-400/80 transition-all duration-700"
              style={{ width: `${Math.min(sgaPct * 2.5, 100)}%` }}
            />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-white/20">0%</span>
            <span className="text-[10px] text-white/20">40% of revenue</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ============================================================================
// 3. TOP OPPORTUNITIES — Max 4 rows, visual priority, one line each
// ============================================================================

function OpportunitiesCard({
  intelligence,
  industrySignals,
  competitorSignals,
}: {
  intelligence: VerticalIntelligenceData | null;
  industrySignals: MarketSignal[];
  competitorSignals: MarketSignal[];
}) {
  const navigate = useNavigate();
  const implications = intelligence?.gtm_implications ?? [];
  const regulations = intelligence?.regulatory_environment ?? [];

  // Merge all opportunities into a single ranked list
  type OpportunityRow = {
    id: string;
    dot: string;
    text: string;
    action?: string;
    actionUrl?: string;
    time?: string;
    sourceUrl?: string;
  };

  const rows: OpportunityRow[] = [];

  // GTM implications (high priority first)
  const sorted = implications.slice().sort((a, b) => {
    const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
    return (order[a.priority ?? 'medium'] ?? 1) - (order[b.priority ?? 'medium'] ?? 1);
  });
  sorted.slice(0, 2).forEach((impl, i) => {
    rows.push({
      id: `impl-${i}`,
      dot: PRIORITY_DOT[impl.priority ?? 'medium'] ?? PRIORITY_DOT.medium,
      text: impl.insight,
      action: impl.recommended_action ?? undefined,
    });
  });

  // Top competitor signal
  if (competitorSignals.length > 0) {
    const s = competitorSignals[0];
    rows.push({
      id: `comp-${s.id}`,
      dot: URGENCY_COLORS[s.urgency]?.dot ?? 'bg-white/30',
      text: s.headline,
      action: s.recommended_action ?? undefined,
      time: timeAgo(s.created_at),
      sourceUrl: s.source_url ?? undefined,
    });
  }

  // Top industry signal (if different from implications)
  if (industrySignals.length > 0 && rows.length < 4) {
    const s = industrySignals[0];
    rows.push({
      id: `ind-${s.id}`,
      dot: URGENCY_COLORS[s.urgency]?.dot ?? 'bg-white/30',
      text: s.headline,
      action: s.recommended_action ?? undefined,
      time: timeAgo(s.created_at),
      sourceUrl: s.source_url ?? undefined,
    });
  }

  // PSG grant / regulation (if any)
  const grant = regulations.find(
    (r) => r.source?.toLowerCase().includes('psg') || r.title.toLowerCase().includes('grant'),
  );
  if (grant && rows.length < 5) {
    rows.push({
      id: 'grant',
      dot: 'bg-emerald-400',
      text: grant.title,
      action: grant.impact ?? undefined,
    });
  }

  if (rows.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
          Opportunities
        </p>
        <button
          onClick={() => navigate('/insights')}
          className="text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
        >
          All signals <ArrowRight className="w-3 h-3" />
        </button>
      </div>
      <div className="px-5 pb-4">
        {rows.map((row) => (
          <OpportunityRow key={row.id} row={row} />
        ))}
      </div>
    </motion.div>
  );
}

function OpportunityRow({ row }: {
  row: {
    id: string;
    dot: string;
    text: string;
    action?: string;
    time?: string;
    sourceUrl?: string;
  };
}) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = !!row.action;

  return (
    <div className="border-b border-white/5 last:border-0">
      <div
        className={`flex items-start gap-2.5 py-3 ${hasDetail ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${row.dot}`} />
        <p className="text-sm text-white/80 leading-snug flex-1">{row.text}</p>
        {row.sourceUrl && (
          <a
            href={row.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-white/20 hover:text-white/50 transition-colors flex-shrink-0 mt-0.5"
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
        {row.time && (
          <span className="text-[10px] text-white/20 flex-shrink-0 mt-0.5">{row.time}</span>
        )}
        {hasDetail && (
          expanded
            ? <ChevronUp className="w-3.5 h-3.5 text-white/20 flex-shrink-0 mt-0.5" />
            : <ChevronDown className="w-3.5 h-3.5 text-white/20 flex-shrink-0 mt-0.5" />
        )}
      </div>
      <AnimatePresence>
        {expanded && row.action && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <p className="text-xs text-purple-400 pl-[18px] pb-3">&rarr; {row.action}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================================================
// 4. PIPELINE + PERFORMANCE — Funnel bar + conversion chain
// ============================================================================

function PipelineCard({
  pipelineData,
  attribution,
}: {
  pipelineData: PipelineSummaryData | null;
  attribution: AttributionSummary | null;
}) {
  const navigate = useNavigate();

  const hasAttribution = attribution != null && attribution.emails_sent > 0;
  const hasPipeline = pipelineData != null && pipelineData.total_leads > 0;

  if (!hasPipeline && !hasAttribution) return null;

  const statusMap = hasPipeline
    ? new Map(pipelineData.by_status.map((s) => [s.status, s.count]))
    : new Map<string, number>();
  const newCount = statusMap.get('new') ?? 0;
  const qualifiedCount = statusMap.get('qualified') ?? 0;
  const contactedCount = statusMap.get('contacted') ?? 0;
  const convertedCount = statusMap.get('converted') ?? 0;

  const topLeads = hasPipeline
    ? pipelineData.recent_leads.filter((l) => l.fit_score >= 40).slice(0, 3)
    : [];

  const benchmarkRate = 8;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30">Pipeline & Performance</p>
        <button
          onClick={() => navigate('/prospects')}
          className="text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
        >
          All prospects <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      <div className="px-5 pb-5">
        {/* Segmented pipeline bar */}
        {hasPipeline && (
          <div className="pt-3">
            <SegmentedBar
              segments={[
                { value: newCount, color: '#3b82f6', label: 'new' },
                { value: qualifiedCount, color: '#10b981', label: 'qualified' },
                { value: contactedCount, color: '#f59e0b', label: 'contacted' },
                { value: convertedCount, color: '#8b5cf6', label: 'converted' },
              ]}
              height={10}
            />
            <div className="flex items-center gap-3 mt-2 text-xs">
              <span className="text-white font-medium">{pipelineData.total_leads} leads</span>
              {pipelineData.avg_fit_score != null && (
                <span className="text-white/40">{pipelineData.avg_fit_score.toFixed(0)}% avg fit</span>
              )}
              <div className="flex-1" />
              <span className="flex items-center gap-1 text-[10px] text-white/30">
                <span className="w-2 h-2 rounded-sm bg-blue-500" />{newCount}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-white/30">
                <span className="w-2 h-2 rounded-sm bg-emerald-500" />{qualifiedCount}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-white/30">
                <span className="w-2 h-2 rounded-sm bg-amber-500" />{contactedCount}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-white/30">
                <span className="w-2 h-2 rounded-sm bg-purple-500" />{convertedCount}
              </span>
            </div>
          </div>
        )}

        {/* Conversion chain — visual funnel */}
        {hasAttribution && attribution && (
          <div className={hasPipeline ? 'mt-4 pt-4 border-t border-white/5' : 'pt-3'}>
            <div className="flex items-center">
              <FunnelStep value={attribution.emails_sent} label="sent" />
              <FunnelArrow />
              <FunnelStep value={attribution.replies} label="replies" color="text-emerald-400" />
              <FunnelArrow />
              <FunnelStep value={attribution.meetings_booked} label="meetings" color="text-purple-400" />
              {attribution.pipeline_value_sgd > 0 && (
                <>
                  <FunnelArrow />
                  <FunnelStep
                    value={`$${(attribution.pipeline_value_sgd / 1000).toFixed(0)}K`}
                    label="pipeline"
                    color="text-amber-400"
                  />
                </>
              )}
            </div>

            {/* Reply rate benchmark bar */}
            {attribution.reply_rate_pct > 0 && (
              <div className="mt-3">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-white/30 w-14">Reply rate</span>
                  <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden relative">
                    {/* Benchmark tick */}
                    <div
                      className="absolute top-0 bottom-0 w-px bg-white/30"
                      style={{ left: `${Math.min((benchmarkRate / 30) * 100, 100)}%` }}
                    />
                    {/* Actual rate */}
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        attribution.reply_rate_pct > benchmarkRate
                          ? 'bg-gradient-to-r from-emerald-500/60 to-emerald-400'
                          : 'bg-gradient-to-r from-amber-500/60 to-amber-400'
                      }`}
                      style={{ width: `${Math.min((attribution.reply_rate_pct / 30) * 100, 100)}%` }}
                    />
                  </div>
                  <span className={`text-xs font-medium tabular-nums ${
                    attribution.reply_rate_pct > benchmarkRate ? 'text-emerald-400' : 'text-amber-400'
                  }`}>
                    {attribution.reply_rate_pct}%
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-0.5 ml-16">
                  <span className="text-[10px] text-white/20">
                    Benchmark: {benchmarkRate}%
                    {attribution.reply_rate_pct > benchmarkRate && (
                      <span className="text-emerald-400/70 ml-1">
                        {(attribution.reply_rate_pct / benchmarkRate).toFixed(1)}x above
                      </span>
                    )}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top 3 prospects — compact row, not cards */}
        {topLeads.length > 0 && (
          <div className={hasAttribution || hasPipeline ? 'mt-4 pt-4 border-t border-white/5' : 'pt-3'}>
            <p className="text-[10px] uppercase tracking-widest text-white/20 mb-2">Top prospects</p>
            {topLeads.map((lead) => (
              <div
                key={lead.id}
                className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0 cursor-pointer hover:bg-white/5 rounded-lg px-2 -mx-2 transition-colors"
                onClick={() => navigate('/prospects')}
              >
                {/* Fit score badge */}
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold flex-shrink-0 ${
                  lead.fit_score >= 70 ? 'text-emerald-400 bg-emerald-500/10'
                    : lead.fit_score >= 50 ? 'text-blue-400 bg-blue-500/10'
                    : 'text-amber-400 bg-amber-500/10'
                }`}>
                  {lead.fit_score}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white/80 font-medium truncate">
                    {lead.contact_name ?? lead.lead_company_name ?? 'Unknown'}
                  </p>
                  <p className="text-[10px] text-white/30 truncate">
                    {lead.contact_title ? `${lead.contact_title} · ` : ''}{lead.lead_company_name ?? ''}
                  </p>
                </div>
                {/* Why now — trigger event */}
                {lead.trigger_events[0] && (
                  <span className="text-[10px] text-purple-400/60 max-w-[140px] truncate hidden sm:block flex-shrink-0">
                    {lead.trigger_events[0]}
                  </span>
                )}
                <ArrowRight className="w-3 h-3 text-white/15 flex-shrink-0" />
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function FunnelStep({ value, label, color }: { value: number | string; label: string; color?: string }) {
  return (
    <div className="flex-1 text-center">
      <p className={`text-lg font-semibold tabular-nums ${color ?? 'text-white'}`}>{value}</p>
      <p className="text-[10px] text-white/30">{label}</p>
    </div>
  );
}

function FunnelArrow() {
  return <ArrowRight className="w-3 h-3 text-white/10 flex-shrink-0 mx-1" />;
}

// ============================================================================
// Empty / No Company States
// ============================================================================

function EmptyState() {
  const navigate = useNavigate();
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center text-center max-w-sm mx-auto py-16"
    >
      <div className="w-14 h-14 bg-purple-500/10 rounded-2xl flex items-center justify-center mb-5">
        <Zap className="w-7 h-7 text-purple-400" />
      </div>
      <h2 className="text-lg font-semibold text-white">Run your first analysis</h2>
      <p className="text-sm text-white/40 mt-1">6 agents, one click.</p>
      <button
        onClick={() => navigate('/')}
        className="mt-5 flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-500/20 text-purple-400 text-sm font-medium hover:bg-purple-500/30 border border-purple-500/30 transition-colors"
      >
        Start Analysis
      </button>
    </motion.div>
  );
}

function NoCompanyState() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <h1 className="text-lg font-semibold text-white">Today</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center text-center"
        >
          <div className="w-14 h-14 bg-purple-500/10 rounded-2xl flex items-center justify-center mb-5">
            <Zap className="w-7 h-7 text-purple-400" />
          </div>
          <h2 className="text-lg font-semibold text-white">Welcome to Hi Meet.AI</h2>
          <button
            onClick={() => navigate('/analyze')}
            className="mt-5 flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-500/20 text-purple-400 text-sm font-medium hover:bg-purple-500/30 border border-purple-500/30 transition-colors"
          >
            <Zap className="w-4 h-4" /> Run Your First Analysis
          </button>
        </motion.div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export function TodayPage() {
  const companyId = useCompanyId();

  const [loading, setLoading] = useState(true);
  const [verticalData, setVerticalData] = useState<VerticalSummary | null>(null);
  const [industryData, setIndustryData] = useState<IndustrySignalsData | null>(null);
  const [competitorSignals, setCompetitorSignals] = useState<MarketSignal[]>([]);
  const [pipelineData, setPipelineData] = useState<PipelineSummaryData | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [attribution, setAttribution] = useState<AttributionSummary | null>(null);
  const [briefingStatus, setBriefingStatus] = useState<BriefingStatus | null>(null);
  const [intelligence, setIntelligence] = useState<VerticalIntelligenceData | null>(null);

  useEffect(() => {
    if (!companyId) {
      setLoading(false);
      return;
    }

    setLoading(true);

    Promise.all([
      apiClient.get<VerticalSummary>(`/companies/${companyId}/market-data/vertical-summary`).catch(() => null),
      apiClient.get<IndustrySignalsData>(`/companies/${companyId}/market-data/industry-signals`).catch(() => null),
      apiClient.get<MarketSignal[]>(`/companies/${companyId}/market-data/competitor-signals`).catch(() => []),
      apiClient.get<PipelineSummaryData>(`/companies/${companyId}/market-data/pipeline-summary`).catch(() => null),
      apiClient.get<{ pending: number }>(`/companies/${companyId}/approvals/count`).catch(() => ({ pending: 0 })),
      apiClient.get<AttributionSummary>(`/companies/${companyId}/attribution/summary?days=7`).catch(() => null),
      apiClient.get<BriefingStatus>(`/companies/${companyId}/market-data/briefing-status`).catch(() => null),
      fetchVerticalIntelligence(companyId),
    ]).then(
      ([vertical, industry, competitors, pipeline, approvals, attr, briefing, intel]) => {
        setVerticalData(vertical);
        setIndustryData(industry);
        setCompetitorSignals(competitors);
        setPipelineData(pipeline);
        setPendingApprovals(approvals.pending ?? 0);
        setAttribution(attr);
        setBriefingStatus(briefing);
        setIntelligence(intel);
      },
    ).finally(() => setLoading(false));
  }, [companyId]);

  const urgentSignals = useMemo(
    () => [
      ...(industryData?.signals ?? []),
      ...competitorSignals,
    ].filter((s) => s.urgency === 'immediate' || s.urgency === 'this_week'),
    [industryData, competitorSignals],
  );

  const hasAnyIntel =
    (industryData?.signals.length ?? 0) > 0 ||
    (industryData?.articles.length ?? 0) > 0 ||
    competitorSignals.length > 0 ||
    (pipelineData?.total_leads ?? 0) > 0 ||
    (intelligence?.id ? true : false);

  const isFirstRun =
    !hasAnyIntel &&
    briefingStatus != null &&
    !briefingStatus.has_completed_analysis;

  if (!companyId) return <NoCompanyState />;

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
          <h1 className="text-lg font-semibold text-white">Today</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {isFirstRun ? (
          <EmptyState />
        ) : (
          <>
            {/* 1. ACTIONS — What needs deciding right now */}
            <ActionBar
              pendingApprovals={pendingApprovals}
              urgentSignalCount={urgentSignals.length}
              topSignal={urgentSignals[0] ?? null}
            />

            {/* 2. MARKET PULSE — One card, visual indicators */}
            <MarketPulseCard
              verticalData={verticalData}
              intelligence={intelligence}
            />

            {/* 3. OPPORTUNITIES — Ranked list, visual priority dots */}
            <OpportunitiesCard
              intelligence={intelligence}
              industrySignals={industryData?.signals ?? []}
              competitorSignals={competitorSignals}
            />

            {/* 4. PIPELINE + PERFORMANCE — Funnel bar, conversion chain, top prospects */}
            <PipelineCard
              pipelineData={pipelineData}
              attribution={attribution}
            />
          </>
        )}
      </div>
    </div>
  );
}
