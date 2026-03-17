/**
 * TodayPage — Daily Strategic Briefing
 *
 * The digital equivalent of a chief of staff presenting the morning intelligence
 * report. Every element follows the three-layer Intelligence Framework:
 *   1. Intelligence — the observed signal or data point
 *   2. Strategic Implication — what it means for the client's business
 *   3. Recommended Action — what the bench is doing or what needs approval
 *
 * All data is fetched in parallel. Each section handles its own empty state.
 * Failures are caught individually so a single failing endpoint never breaks
 * the whole page.
 */

import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  BarChart3,
  Bell,
  Crosshair,
  DollarSign,
  ExternalLink,
  Globe,
  Mail,
  MessageSquare,
  Radio,
  Rocket,
  Shield,
  Target,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCompany, useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';
import { AgentTeamRoster } from '../components/AgentTeamRoster';

// ============================================================================
// Types — aligned with backend response schemas
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

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function getUserFirstName(): string | null {
  const fullName = localStorage.getItem('gtm_user_name');
  if (!fullName) return null;
  const first = fullName.trim().split(' ')[0];
  return first || null;
}

function titleCase(name: string): string {
  return name
    .split(' ')
    .map((word) => {
      if (word.length <= 3 && word === word.toUpperCase()) return word;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}

// ============================================================================
// Constants
// ============================================================================

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  competitor_news: 'Competitor',
  acquisition: 'Acquisition',
  product_launch: 'Product Launch',
  partnership: 'Partnership',
  funding: 'Funding',
  market_trend: 'Market Trend',
  regulation: 'Regulatory',
  expansion: 'Expansion',
  general_news: 'Industry',
  hiring: 'Hiring',
  layoff: 'Restructuring',
};

const URGENCY_BADGE: Record<string, string> = {
  immediate: 'text-red-400 bg-red-500/10 border-red-500/20',
  this_week: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  this_month: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  monitor: 'text-white/40 bg-white/5 border-white/10',
};

const PIPELINE_STATUSES = ['new', 'qualified', 'contacted', 'converted', 'lost'] as const;

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-blue-500',
  qualified: 'bg-emerald-500',
  contacted: 'bg-amber-500',
  converted: 'bg-purple-500',
  lost: 'bg-white/20',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  qualified: 'Qualified',
  contacted: 'Contacted',
  converted: 'Converted',
  lost: 'Lost',
};

// ============================================================================
// Section Header
// ============================================================================

function SectionHeader({
  title,
  action,
  onAction,
}: {
  title: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
        {title}
      </p>
      {action && onAction && (
        <button
          onClick={onAction}
          className="text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
        >
          {action}
          <ArrowRight className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Signal Row — three-layer intelligence pattern
// ============================================================================

function signalIcon(type: string) {
  const cls = 'w-4 h-4';
  switch (type) {
    case 'competitor_news':
    case 'acquisition':
      return <Crosshair className={cls} />;
    case 'regulation':
      return <Shield className={cls} />;
    case 'funding':
      return <DollarSign className={cls} />;
    case 'product_launch':
      return <Rocket className={cls} />;
    case 'market_trend':
    case 'expansion':
      return <TrendingUp className={cls} />;
    case 'partnership':
      return <Globe className={cls} />;
    default:
      return <Radio className={cls} />;
  }
}

function SignalRow({ signal }: { signal: MarketSignal }) {
  const badgeColor =
    URGENCY_BADGE[signal.urgency] ?? URGENCY_BADGE.monitor;
  const typeLabel =
    SIGNAL_TYPE_LABELS[signal.signal_type] ??
    signal.signal_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="flex gap-3 py-3.5 border-b border-white/5 last:border-0">
      {/* Icon */}
      <div
        className={`mt-0.5 p-2 rounded-lg flex-shrink-0 ${badgeColor
          .split(' ')
          .slice(1)
          .join(' ')}`}
      >
        <span className={badgeColor.split(' ')[0]}>
          {signalIcon(signal.signal_type)}
        </span>
      </div>

      {/* Body — three layers */}
      <div className="flex-1 min-w-0">
        {/* Layer 1: Intelligence */}
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span
            className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${badgeColor}`}
          >
            {typeLabel}
          </span>
          {signal.source && (
            <span className="text-[10px] text-white/30">{signal.source}</span>
          )}
        </div>
        <p className="text-sm font-medium text-white leading-snug line-clamp-2">
          {signal.headline}
        </p>

        {/* Layer 2: Strategic Implication */}
        {signal.summary && (
          <p className="text-xs text-white/50 mt-0.5 leading-relaxed line-clamp-2">
            {signal.summary}
          </p>
        )}

        {/* Layer 3: Recommended Action */}
        {signal.recommended_action && (
          <p className="text-xs text-purple-400 mt-1 leading-snug">
            &rarr; {signal.recommended_action}
          </p>
        )}
      </div>

      {/* Right: time + external link */}
      <div className="flex flex-col items-end gap-1 flex-shrink-0">
        <span className="text-[10px] text-white/30">
          {timeAgo(signal.created_at)}
        </span>
        {signal.source_url && (
          <a
            href={signal.source_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-white/20 hover:text-white/50 transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Section: Industry & Market Intelligence
// ============================================================================

function IndustrySection({
  industryData,
  verticalData,
}: {
  industryData: IndustrySignalsData | null;
  verticalData: VerticalSummary | null;
}) {
  const navigate = useNavigate();
  const signals = industryData?.signals ?? [];
  const articles = industryData?.articles ?? [];

  // Find latest annual benchmark for vertical stats
  const annualBenchmark = verticalData?.benchmarks.find(
    (b) => b.period_type === 'annual'
  );

  const isEmpty = signals.length === 0 && articles.length === 0 && !annualBenchmark;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <SectionHeader
        title="Industry & Market"
        action="View all"
        onAction={() => navigate('/insights')}
      />
      <div className="px-5 pb-4">
        {isEmpty ? (
          <div className="py-6 text-center">
            <Radio className="w-5 h-5 text-white/20 mx-auto mb-2" />
            <p className="text-sm text-white/40">
              Market Intelligence scans 142 sources daily.
            </p>
            <p className="text-xs text-white/25 mt-1">
              Your first briefing arrives with your initial analysis.
            </p>
          </div>
        ) : (
          <>
            {/* Signals */}
            {signals.slice(0, 4).map((s) => (
              <SignalRow key={s.id} signal={s} />
            ))}

            {/* Market articles */}
            {articles.length > 0 && (
              <div className="mt-3 pt-3 border-t border-white/5">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/20 mb-2">
                  Recent coverage
                </p>
                <div className="space-y-2">
                  {articles.slice(0, 3).map((a) => (
                    <div key={a.id} className="flex items-start gap-2">
                      <span className="w-1 h-1 rounded-full bg-white/20 mt-2 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        {a.source_url ? (
                          <a
                            href={a.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-white/60 hover:text-white/80 transition-colors line-clamp-1"
                          >
                            {a.title}
                          </a>
                        ) : (
                          <p className="text-xs text-white/60 line-clamp-1">{a.title}</p>
                        )}
                        <span className="text-[10px] text-white/25">
                          {a.source_name ?? 'Market article'}
                          {a.published_at ? ` \u00b7 ${timeAgo(a.published_at)}` : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Vertical benchmark */}
            {annualBenchmark && verticalData?.vertical_name && (
              <div className="mt-3 pt-3 border-t border-white/5">
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="text-xs text-white/40">
                    Your vertical ({verticalData.vertical_name}):
                  </span>
                  {annualBenchmark.revenue_growth_yoy?.p50 != null && (
                    <span className="text-xs">
                      <span className="text-white/50">Median revenue growth</span>{' '}
                      <span className="text-emerald-400 font-medium">
                        {formatPct(annualBenchmark.revenue_growth_yoy.p50)}
                      </span>
                    </span>
                  )}
                  {annualBenchmark.sga_to_revenue?.p50 != null && (
                    <span className="text-xs">
                      <span className="text-white/50">SG&A ratio</span>{' '}
                      <span className="text-white/70 font-medium">
                        {annualBenchmark.sga_to_revenue.p50.toFixed(1)}%
                      </span>
                    </span>
                  )}
                  {annualBenchmark.revenue_growth_yoy?.p75 != null && (
                    <span className="text-xs text-white/30">
                      Top quartile: {formatPct(annualBenchmark.revenue_growth_yoy.p75)}
                    </span>
                  )}
                </div>
                {verticalData.listed_companies_count > 0 && (
                  <span className="text-[10px] text-white/20 mt-1 inline-block">
                    Based on {verticalData.listed_companies_count} listed companies
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Section: Competitive Landscape
// ============================================================================

function CompetitorSection({
  competitorSignals,
}: {
  competitorSignals: MarketSignal[];
}) {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <SectionHeader
        title="Competitive Landscape"
        action="View all"
        onAction={() => navigate('/insights')}
      />
      <div className="px-5 pb-4">
        {competitorSignals.length === 0 ? (
          <div className="py-6 text-center">
            <Crosshair className="w-5 h-5 text-white/20 mx-auto mb-2" />
            <p className="text-sm text-white/40">
              Competitor Analyst monitors your competitive landscape.
            </p>
            <p className="text-xs text-white/25 mt-1">
              Run your first analysis to identify and track key competitors.
            </p>
          </div>
        ) : (
          <>
            {competitorSignals.slice(0, 4).map((s) => (
              <SignalRow key={s.id} signal={s} />
            ))}

            {/* Footer — tracking count */}
            <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-2">
              <span className="text-[10px] text-white/20">
                Tracking {competitorSignals.length} competitor{' '}
                {competitorSignals.length === 1 ? 'signal' : 'signals'}
              </span>
              {competitorSignals[0]?.created_at && (
                <span className="text-[10px] text-white/15">
                  Last updated: {timeAgo(competitorSignals[0].created_at)}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Section: Pipeline & Prospects
// ============================================================================

function PipelineSection({
  pipelineData,
}: {
  pipelineData: PipelineSummaryData | null;
}) {
  const navigate = useNavigate();

  if (!pipelineData) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card rounded-xl border border-white/10"
      >
        <SectionHeader title="Pipeline & Prospects" />
        <div className="px-5 pb-4 py-6 text-center">
          <Users className="w-5 h-5 text-white/20 mx-auto mb-2" />
          <p className="text-sm text-white/40">
            Lead Hunter identifies qualified prospects from verified databases.
          </p>
          <p className="text-xs text-white/25 mt-1">
            Your pipeline populates after your first analysis.
          </p>
        </div>
      </motion.div>
    );
  }

  const statusMap = new Map(pipelineData.by_status.map((s) => [s.status, s.count]));
  const maxCount = Math.max(...pipelineData.by_status.map((s) => s.count), 1);
  const buyingSignalLeads = pipelineData.recent_leads.filter(
    (l) => l.trigger_events.length > 0
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <SectionHeader
        title="Pipeline & Prospects"
        action="View all"
        onAction={() => navigate('/prospects')}
      />
      <div className="px-5 pb-4">
        {/* Status bars */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-3">
          {PIPELINE_STATUSES.filter((s) => s !== 'lost').map((status) => {
            const count = statusMap.get(status) ?? 0;
            const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
            return (
              <div key={status}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-white/50">
                    {STATUS_LABELS[status]}
                  </span>
                  <span className="text-xs font-medium text-white/70 tabular-nums">
                    {count}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${STATUS_COLORS[status]} transition-all duration-500`}
                    style={{ width: `${Math.max(pct, count > 0 ? 8 : 0)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Buying signal callout */}
        {buyingSignalLeads.length > 0 && (
          <div className="mt-2 py-3 border-t border-white/5">
            <div className="flex items-start gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-white">
                  {buyingSignalLeads.length}{' '}
                  {buyingSignalLeads.length === 1 ? 'prospect' : 'prospects'} showing
                  buying signals
                </p>
                <p className="text-xs text-white/40 mt-0.5">
                  These accounts have active trigger events. Historical conversion is
                  highest when contacted within 48 hours of signal.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Top leads */}
        {pipelineData.recent_leads.length > 0 && (
          <div className="mt-2 pt-3 border-t border-white/5 space-y-2.5">
            {pipelineData.recent_leads.slice(0, 4).map((lead) => (
              <div
                key={lead.id}
                className="flex items-start gap-3 group cursor-pointer hover:bg-white/5 rounded-lg px-2 py-1.5 -mx-2 transition-colors"
                onClick={() => navigate('/prospects')}
              >
                {/* Fit score badge */}
                <div
                  className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold ${
                    lead.fit_score >= 80
                      ? 'bg-emerald-500/15 text-emerald-400'
                      : lead.fit_score >= 60
                        ? 'bg-blue-500/15 text-blue-400'
                        : 'bg-white/5 text-white/40'
                  }`}
                >
                  {lead.fit_score}%
                </div>

                {/* Lead info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white/80 truncate">
                      {lead.contact_name ?? lead.lead_company_name ?? 'Unknown'}
                    </span>
                    {lead.contact_title && (
                      <span className="text-[10px] text-white/30 truncate hidden sm:inline">
                        {lead.contact_title}
                      </span>
                    )}
                  </div>
                  {lead.lead_company_name && lead.contact_name && (
                    <span className="text-xs text-white/40">{lead.lead_company_name}</span>
                  )}
                  {lead.pain_points.length > 0 && (
                    <p className="text-[11px] text-white/30 mt-0.5 line-clamp-1">
                      {lead.pain_points[0]}
                    </p>
                  )}
                </div>

                {/* Status */}
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded border border-white/10 text-white/40 flex-shrink-0`}
                >
                  {STATUS_LABELS[lead.status] ?? lead.status}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Average fit score */}
        {pipelineData.avg_fit_score != null && pipelineData.total_leads > 0 && (
          <div className="mt-3 pt-3 border-t border-white/5">
            <span className="text-[10px] text-white/20">
              {pipelineData.total_leads} total leads &middot; avg fit score{' '}
              {pipelineData.avg_fit_score.toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Section: Strategic Actions
// ============================================================================

function ActionsSection({
  pendingApprovals,
  urgentSignals,
  pipelineData,
}: {
  pendingApprovals: number;
  urgentSignals: MarketSignal[];
  pipelineData: PipelineSummaryData | null;
}) {
  const navigate = useNavigate();
  const urgentCount = urgentSignals.length;
  const newLeads =
    pipelineData?.by_status.find((s) => s.status === 'new')?.count ?? 0;

  const hasActions = pendingApprovals > 0 || urgentCount > 0 || newLeads > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <SectionHeader title="Strategic Actions" />
      <div className="px-5 pb-4">
        {!hasActions ? (
          <div className="py-5 text-center">
            <p className="text-sm text-white/50">
              No actions required. Your bench is running autonomously.
            </p>
            <button
              onClick={() => navigate('/campaigns')}
              className="mt-3 text-xs text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1 mx-auto"
            >
              Launch a new campaign to maintain pipeline momentum
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <div className="space-y-3 py-2">
            {/* Pending approvals */}
            {pendingApprovals > 0 && (
              <div
                className="flex items-start gap-3 cursor-pointer hover:bg-white/5 rounded-lg px-2 py-2 -mx-2 transition-colors"
                onClick={() => navigate('/approvals')}
              >
                <div className="p-2 rounded-lg bg-amber-500/10 flex-shrink-0">
                  <Bell className="w-4 h-4 text-amber-400" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-amber-400">
                    {pendingApprovals} outreach{' '}
                    {pendingApprovals === 1 ? 'email' : 'emails'} awaiting approval
                  </p>
                  <p className="text-xs text-white/40 mt-0.5">
                    Delay beyond 24 hours reduces response rates.
                  </p>
                </div>
                <button className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 text-amber-400 text-xs font-medium hover:bg-amber-500/25 border border-amber-500/20 transition-colors self-center">
                  Review & Approve
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* Urgent signals */}
            {urgentCount > 0 && (
              <div
                className="flex items-start gap-3 cursor-pointer hover:bg-white/5 rounded-lg px-2 py-2 -mx-2 transition-colors"
                onClick={() => navigate('/insights')}
              >
                <div className="p-2 rounded-lg bg-yellow-500/10 flex-shrink-0">
                  <Radio className="w-4 h-4 text-yellow-400" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-yellow-400">
                    {urgentCount} urgent market{' '}
                    {urgentCount === 1 ? 'signal requires' : 'signals require'} your
                    input
                  </p>
                  <p className="text-xs text-white/40 mt-0.5">
                    {urgentSignals
                      .slice(0, 2)
                      .map(
                        (s) =>
                          SIGNAL_TYPE_LABELS[s.signal_type] ??
                          s.signal_type.replace(/_/g, ' ')
                      )
                      .join(' + ')}
                    .
                  </p>
                </div>
                <button className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-yellow-500/15 text-yellow-400 text-xs font-medium hover:bg-yellow-500/25 border border-yellow-500/20 transition-colors self-center">
                  Review Signals
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* Unqualified leads */}
            {newLeads > 0 && pendingApprovals === 0 && urgentCount === 0 && (
              <div
                className="flex items-start gap-3 cursor-pointer hover:bg-white/5 rounded-lg px-2 py-2 -mx-2 transition-colors"
                onClick={() => navigate('/prospects')}
              >
                <div className="p-2 rounded-lg bg-green-500/10 flex-shrink-0">
                  <Target className="w-4 h-4 text-green-400" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-green-400">
                    {newLeads} new {newLeads === 1 ? 'lead needs' : 'leads need'}{' '}
                    qualifying
                  </p>
                  <p className="text-xs text-white/40 mt-0.5">
                    Fresh prospects in your pipeline. Review and advance to outreach.
                  </p>
                </div>
                <button className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/15 text-green-400 text-xs font-medium hover:bg-green-500/25 border border-green-500/20 transition-colors self-center">
                  View Prospects
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* All clear — recommend campaign */}
            {pendingApprovals === 0 && urgentCount === 0 && newLeads === 0 && (
              <div
                className="flex items-start gap-3 cursor-pointer hover:bg-white/5 rounded-lg px-2 py-2 -mx-2 transition-colors"
                onClick={() => navigate('/campaigns')}
              >
                <div className="p-2 rounded-lg bg-purple-500/10 flex-shrink-0">
                  <Rocket className="w-4 h-4 text-purple-400" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-purple-400">Pipeline clear</p>
                  <p className="text-xs text-white/40 mt-0.5">
                    Your bench recommends launching a new campaign to maintain pipeline
                    momentum.
                  </p>
                </div>
                <button className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/15 text-purple-400 text-xs font-medium hover:bg-purple-500/25 border border-purple-500/20 transition-colors self-center">
                  Launch Campaign
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Weekly Performance Summary
// ============================================================================

function PerformanceSummary({
  attribution,
}: {
  attribution: AttributionSummary | null;
}) {
  const navigate = useNavigate();

  if (!attribution) return null;

  const hasOutreach =
    attribution.emails_sent > 0 || attribution.replies > 0 || attribution.meetings_booked > 0;
  const hasPipeline = attribution.pipeline_value_sgd > 0;

  if (!hasOutreach && !hasPipeline) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <SectionHeader
        title="This Week's Performance"
        action="Full report"
        onAction={() => navigate('/results')}
      />
      <div className="px-5 pb-4 pt-3">
        {/* Outreach metrics row */}
        {hasOutreach && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {attribution.emails_sent > 0 && (
              <div className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-white/30" />
                <span className="text-sm text-white/70">
                  <span className="font-medium text-white tabular-nums">
                    {attribution.emails_sent}
                  </span>{' '}
                  emails sent
                </span>
              </div>
            )}
            {attribution.replies > 0 && (
              <div className="flex items-center gap-2">
                <MessageSquare className="w-3.5 h-3.5 text-white/30" />
                <span className="text-sm text-white/70">
                  <span className="font-medium text-white tabular-nums">
                    {attribution.replies}
                  </span>{' '}
                  replies ({attribution.reply_rate_pct}%)
                </span>
              </div>
            )}
            {attribution.meetings_booked > 0 && (
              <div className="flex items-center gap-2">
                <Users className="w-3.5 h-3.5 text-white/30" />
                <span className="text-sm text-white/70">
                  <span className="font-medium text-white tabular-nums">
                    {attribution.meetings_booked}
                  </span>{' '}
                  meetings
                </span>
              </div>
            )}
          </div>
        )}

        {/* Reply rate benchmark */}
        {attribution.reply_rate_pct > 0 && (
          <p className="text-xs text-emerald-400/80 mt-2">
            Reply rate {attribution.reply_rate_pct > 8 ? `${(attribution.reply_rate_pct / 8).toFixed(1)}x above` : 'tracking against'} industry benchmark (8%)
          </p>
        )}

        {/* Pipeline value */}
        {hasPipeline && (
          <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5 text-white/30" />
            <span className="text-sm text-white/70">
              SGD{' '}
              <span className="font-medium text-white tabular-nums">
                {attribution.pipeline_value_sgd.toLocaleString('en-SG', {
                  maximumFractionDigits: 0,
                })}
              </span>{' '}
              pipeline generated
            </span>
          </div>
        )}

        {/* View full report */}
        <button
          onClick={() => navigate('/results')}
          className="mt-3 text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
        >
          View full attribution report
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </motion.div>
  );
}

// ============================================================================
// Agent Activity Feed
// ============================================================================

interface ActivityItem {
  id: string;
  agentName: string;
  description: string;
  timestamp: string;
  icon: React.ReactNode;
  dotColor: string;
}

function buildActivityFeed(
  industrySignals: MarketSignal[],
  competitorSignals: MarketSignal[],
  pipelineData: PipelineSummaryData | null,
  pendingApprovals: number,
): ActivityItem[] {
  const items: ActivityItem[] = [];

  // Signal Monitor detections
  const allSignals = [...industrySignals, ...competitorSignals]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 3);

  allSignals.forEach((s) => {
    const typeLabel =
      SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type.replace(/_/g, ' ');
    items.push({
      id: `sig-${s.id}`,
      agentName: 'Signal Monitor',
      description: `detected ${typeLabel.toLowerCase()}: ${s.headline}`,
      timestamp: s.created_at,
      icon: <Radio className="w-3.5 h-3.5 text-yellow-400" />,
      dotColor: 'bg-yellow-400',
    });
  });

  // Lead Hunter identifications
  if (pipelineData && pipelineData.recent_leads.length > 0) {
    const count = pipelineData.recent_leads.length;
    const mostRecent = pipelineData.recent_leads[0];
    items.push({
      id: 'lead-activity',
      agentName: 'Lead Hunter',
      description: `identified ${count} qualified ${count === 1 ? 'prospect' : 'prospects'}${mostRecent.contact_name ? ` including ${mostRecent.contact_name}` : ''}`,
      timestamp: mostRecent.created_at ?? new Date().toISOString(),
      icon: <Target className="w-3.5 h-3.5 text-green-400" />,
      dotColor: 'bg-green-400',
    });
  }

  // Outreach Executor queued items
  if (pendingApprovals > 0) {
    items.push({
      id: 'approval-activity',
      agentName: 'Outreach Executor',
      description: `queued ${pendingApprovals} personalised ${pendingApprovals === 1 ? 'email' : 'emails'} for approval`,
      timestamp: new Date().toISOString(),
      icon: <Mail className="w-3.5 h-3.5 text-amber-400" />,
      dotColor: 'bg-amber-400',
    });
  }

  return items
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 6);
}

function ActivityFeed({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <SectionHeader title="Bench Activity" />
      <div className="px-5 pb-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-3 py-2.5 border-b border-white/5 last:border-0"
          >
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${item.dotColor}`}
            />
            <div className="flex-shrink-0">{item.icon}</div>
            <div className="flex-1 min-w-0">
              <span className="text-sm text-white/70">
                <span className="font-medium text-white/80">{item.agentName}</span>{' '}
                {item.description}
              </span>
            </div>
            <span className="text-[10px] text-white/30 flex-shrink-0">
              {timeAgo(item.timestamp)}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Empty State — first-run experience
// ============================================================================

function EmptyState() {
  const navigate = useNavigate();

  const steps = [
    {
      agent: 'Market Intelligence',
      action: 'scans 142 data sources for market signals',
    },
    {
      agent: 'Competitor Analyst',
      action: 'profiles your competitive landscape',
    },
    {
      agent: 'Customer Profiler',
      action: 'defines your ideal buyer persona',
    },
    {
      agent: 'Lead Hunter',
      action: 'surfaces qualified prospects with verified contacts',
    },
    {
      agent: 'Campaign Architect',
      action: 'drafts your first personalised outreach',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-8 sm:p-10 rounded-xl border border-white/10 flex flex-col items-center text-center max-w-lg mx-auto"
    >
      <div className="w-14 h-14 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-5">
        <Zap className="w-7 h-7 text-purple-400" />
      </div>

      <h2 className="text-lg font-semibold text-white">
        Your Strategic Bench is ready to deploy
      </h2>
      <p className="text-sm text-white/50 mt-2 max-w-sm leading-relaxed">
        6 specialised agents will map your competitive landscape, identify
        qualified prospects, and prepare your first campaign brief — all within
        minutes.
      </p>

      <button
        onClick={() => navigate('/')}
        className="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-xl bg-purple-500/20 text-purple-400 text-sm font-medium hover:bg-purple-500/30 border border-purple-500/30 transition-colors"
      >
        <BarChart3 className="w-4 h-4" />
        Start Market Analysis
      </button>

      <div className="mt-8 w-full space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/20">
          What happens next
        </p>
        {steps.map(({ agent, action }, i) => (
          <div key={agent} className="flex items-center gap-3 text-left">
            <span className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[10px] font-bold text-white/40 flex-shrink-0">
              {i + 1}
            </span>
            <div>
              <span className="text-sm font-medium text-white/70">{agent}</span>
              <span className="text-xs text-white/30 ml-1.5">{action}</span>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ============================================================================
// No Company State
// ============================================================================

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
          className="glass-card p-10 rounded-xl border border-white/10 flex flex-col items-center text-center max-w-md"
        >
          <div className="w-14 h-14 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-4">
            <Zap className="w-7 h-7 text-purple-400" />
          </div>
          <h2 className="text-lg font-semibold text-white">
            Welcome to GTM Advisor
          </h2>
          <p className="text-sm text-white/50 mt-2 leading-relaxed">
            Start by running an AI analysis of your company. Your 6-agent bench
            will map the market, profile competitors, identify qualified
            prospects, and draft your first campaign — then you manage the
            entire GTM process from here.
          </p>
          <button
            onClick={() => navigate('/')}
            className="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-xl bg-purple-500/20 text-purple-400 text-sm font-medium hover:bg-purple-500/30 border border-purple-500/30 transition-colors"
          >
            <Zap className="w-4 h-4" />
            Run Your First Analysis
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
  const { company } = useCompany();
  const companyId = useCompanyId();

  // Data states
  const [loading, setLoading] = useState(true);
  const [verticalData, setVerticalData] = useState<VerticalSummary | null>(null);
  const [industryData, setIndustryData] = useState<IndustrySignalsData | null>(null);
  const [competitorSignals, setCompetitorSignals] = useState<MarketSignal[]>([]);
  const [pipelineData, setPipelineData] = useState<PipelineSummaryData | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [attribution, setAttribution] = useState<AttributionSummary | null>(null);
  const [briefingStatus, setBriefingStatus] = useState<BriefingStatus | null>(null);

  useEffect(() => {
    if (!companyId) {
      setLoading(false);
      return;
    }

    setLoading(true);

    Promise.all([
      apiClient
        .get<VerticalSummary>(`/companies/${companyId}/market-data/vertical-summary`)
        .catch(() => null),
      apiClient
        .get<IndustrySignalsData>(`/companies/${companyId}/market-data/industry-signals`)
        .catch(() => null),
      apiClient
        .get<MarketSignal[]>(`/companies/${companyId}/market-data/competitor-signals`)
        .catch(() => []),
      apiClient
        .get<PipelineSummaryData>(`/companies/${companyId}/market-data/pipeline-summary`)
        .catch(() => null),
      apiClient
        .get<{ pending: number }>(`/companies/${companyId}/approvals/count`)
        .catch(() => ({ pending: 0 })),
      apiClient
        .get<AttributionSummary>(`/companies/${companyId}/attribution/summary?days=7`)
        .catch(() => null),
      apiClient
        .get<BriefingStatus>(`/companies/${companyId}/market-data/briefing-status`)
        .catch(() => null),
    ]).then(
      ([
        vertical,
        industry,
        competitors,
        pipeline,
        approvals,
        attr,
        briefing,
      ]) => {
        setVerticalData(vertical);
        setIndustryData(industry);
        setCompetitorSignals(competitors);
        setPipelineData(pipeline);
        setPendingApprovals(approvals.pending ?? 0);
        setAttribution(attr);
        setBriefingStatus(briefing);
      }
    ).finally(() => setLoading(false));
  }, [companyId]);

  // Compute urgent signals — match backend SignalUrgency enum values
  const urgentCompetitorSignals = useMemo(
    () => competitorSignals.filter((s) => s.urgency === 'immediate' || s.urgency === 'this_week'),
    [competitorSignals]
  );
  const urgentIndustrySignals = useMemo(
    () =>
      (industryData?.signals ?? []).filter(
        (s) => s.urgency === 'immediate' || s.urgency === 'this_week'
      ),
    [industryData]
  );
  const allUrgentSignals = useMemo(
    () => [...urgentIndustrySignals, ...urgentCompetitorSignals],
    [urgentIndustrySignals, urgentCompetitorSignals]
  );

  // Activity feed
  const activityItems = useMemo(
    () =>
      buildActivityFeed(
        industryData?.signals ?? [],
        competitorSignals,
        pipelineData,
        pendingApprovals
      ),
    [industryData, competitorSignals, pipelineData, pendingApprovals]
  );

  // Determine if this is a first-run (empty) state.
  // Show the briefing even if no analysis was run — signals and articles from
  // the intelligence pipeline (RSS, curated intel) are always available.
  const hasAnyIntel =
    (industryData?.signals.length ?? 0) > 0 ||
    (industryData?.articles.length ?? 0) > 0 ||
    competitorSignals.length > 0 ||
    (pipelineData?.total_leads ?? 0) > 0;
  const isFirstRun =
    !hasAnyIntel &&
    briefingStatus != null &&
    !briefingStatus.has_completed_analysis;

  // ---- No company selected ----
  if (!companyId) {
    return <NoCompanyState />;
  }

  // ---- Loading ----
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

  // ---- Greeting ----
  const firstName = getUserFirstName();
  const displayName = firstName
    ? firstName
    : company?.name
      ? titleCase(company.name)
      : null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <h1 className="text-lg font-semibold text-white">
          {getGreeting()}
          {displayName ? `, ${displayName}` : ''}
        </h1>
        <p className="text-xs text-white/40 mt-0.5">Your daily strategic briefing</p>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Strategic Bench */}
        <AgentTeamRoster activities={[]} isAnalyzing={false} />

        {isFirstRun ? (
          <EmptyState />
        ) : (
          <>
            {/* Market Intelligence Briefing */}
            <IndustrySection
              industryData={industryData}
              verticalData={verticalData}
            />

            <CompetitorSection competitorSignals={competitorSignals} />

            <PipelineSection pipelineData={pipelineData} />

            <ActionsSection
              pendingApprovals={pendingApprovals}
              urgentSignals={allUrgentSignals}
              pipelineData={pipelineData}
            />

            {/* Weekly Performance */}
            <PerformanceSummary attribution={attribution} />

            {/* Agent Activity Feed */}
            <ActivityFeed items={activityItems} />
          </>
        )}
      </div>
    </div>
  );
}
