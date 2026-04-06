/**
 * InsightsPage — Analyst Report
 *
 * Tabbed analyst report replacing the old SignalsFeed at /insights.
 * Follows the "So What -> Do What -> Are We Doing" three-layer framework.
 *
 * Tabs:
 *   industry    — Industry Intelligence (financial pulse, trends, regulatory)
 *   market      — Market Signals (signal digest, executive movements)
 *   competitors — Competitive Landscape (dynamics, competitor signals)
 *   opportunities — Growth Opportunities (pipeline, playbooks)
 *
 * All data is fetched in parallel. Each section handles its own empty state.
 * Failures are caught individually so a single failing endpoint never breaks
 * the whole page.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle,
  Crosshair,
  DollarSign,
  ExternalLink,
  Globe,
  Radio,
  Rocket,
  Shield,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';
import {
  fetchVerticalIntelligence,
  type VerticalIntelligenceData,
  type GTMImplication,
  type FinancialPulse,
  // CompetitiveDynamics type is too narrow — we read the raw Record instead
  type SignalDigestItem,
  type ExecutiveMovement,
  type RegulatoryItem,
  type KeyTrend,
} from '../api/verticalIntelligence';

// ============================================================================
// Local types
// ============================================================================

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
  recommended_approach: string | null;
}

interface PipelineSummaryData {
  total_leads: number;
  by_status: PipelineStatusCount[];
  avg_fit_score: number | null;
  recent_leads: RecentLead[];
}

// ============================================================================
// Tab config
// ============================================================================

type TabId = 'industry' | 'market' | 'competitors' | 'opportunities';

interface TabConfig {
  id: TabId;
  label: string;
}

const TABS: TabConfig[] = [
  { id: 'industry', label: 'Industry' },
  { id: 'market', label: 'Market' },
  { id: 'competitors', label: 'Competitors' },
  { id: 'opportunities', label: 'Opportunities' },
];

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

const URGENCY_LABELS: Record<string, string> = {
  immediate: 'Immediate',
  this_week: 'This Week',
  this_month: 'This Month',
  monitor: 'Monitor',
};

const PRIORITY_BADGE: Record<string, string> = {
  high: 'text-red-400 bg-red-500/10 border-red-500/20',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  low: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
};

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

const PIPELINE_STATUSES = ['new', 'qualified', 'contacted', 'converted'] as const;

// ============================================================================
// Helpers
// ============================================================================

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

function trendArrow(trend: string | null): { icon: React.ReactNode; label: string; color: string } {
  if (!trend) return { icon: null, label: '', color: 'text-white/30' };
  const t = trend.toLowerCase();
  if (t === 'rising' || t === 'increasing' || t === 'growing') {
    return { icon: <TrendingUp className="w-3 h-3" />, label: trend, color: 'text-emerald-400' };
  }
  if (t === 'declining' || t === 'decreasing' || t === 'falling') {
    return { icon: <TrendingDown className="w-3 h-3" />, label: trend, color: 'text-red-400' };
  }
  return { icon: null, label: trend, color: 'text-white/40' };
}

function labelForSignalType(type: string): string {
  return (
    SIGNAL_TYPE_LABELS[type] ??
    type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function signalIcon(type: string): React.ReactNode {
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

// ============================================================================
// Shared sub-components
// ============================================================================

function LayerHeader({ label, action, onAction }: { label: string; action?: string; onAction?: () => void }) {
  return (
    <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/5 mb-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30">{label}</p>
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

function EmptyState({ icon, text, subtext }: { icon: React.ReactNode; text: string; subtext?: string }) {
  return (
    <div className="py-8 text-center">
      <div className="flex justify-center mb-2 text-white/20">{icon}</div>
      <p className="text-sm text-white/40">{text}</p>
      {subtext && <p className="text-xs text-white/25 mt-1">{subtext}</p>}
    </div>
  );
}

function SignalRow({ signal, onDeploy }: { signal: MarketSignal; onDeploy?: (signal: MarketSignal) => void }) {
  const badgeColor = URGENCY_BADGE[signal.urgency] ?? URGENCY_BADGE.monitor;
  const typeLabel = labelForSignalType(signal.signal_type);
  const iconBg = badgeColor.split(' ').slice(1).join(' ');
  const iconColor = badgeColor.split(' ')[0];

  return (
    <div className="flex gap-3 py-3.5 border-b border-white/5 last:border-0">
      <div className={`mt-0.5 p-2 rounded-lg flex-shrink-0 ${iconBg}`}>
        <span className={iconColor}>{signalIcon(signal.signal_type)}</span>
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${badgeColor}`}>
            {typeLabel}
          </span>
          {signal.source && (
            <span className="text-[10px] text-white/30">{signal.source}</span>
          )}
          <span className="text-[10px] text-white/20 tabular-nums">
            {Math.round(signal.relevance_score * 100)}% relevant
          </span>
        </div>
        <p className="text-sm font-medium text-white leading-snug line-clamp-2">{signal.headline}</p>
        {signal.summary && (
          <p className="text-xs text-white/50 mt-0.5 leading-relaxed line-clamp-2">{signal.summary}</p>
        )}
        {signal.recommended_action && (
          <p className="text-xs text-purple-400 mt-1 leading-snug">
            &rarr; {signal.recommended_action}
          </p>
        )}
        {onDeploy && (signal.urgency === 'immediate' || signal.urgency === 'this_week') && (
          <button
            onClick={() => onDeploy(signal)}
            className="mt-2 text-xs px-2.5 py-1 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
          >
            <Zap className="w-3 h-3" />
            Deploy Playbook
          </button>
        )}
      </div>

      <div className="flex flex-col items-end gap-1 flex-shrink-0">
        <span className="text-[10px] text-white/30">{timeAgo(signal.created_at)}</span>
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

function GTMImplicationCard({ item, onCreateCampaign }: { item: GTMImplication; onCreateCampaign?: (insight: string) => void }) {
  const priority = (item.priority ?? 'low').toLowerCase();
  const badgeColor = PRIORITY_BADGE[priority] ?? PRIORITY_BADGE.low;

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm font-medium text-white leading-snug">{item.insight}</p>
        <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border flex-shrink-0 ${badgeColor}`}>
          {priority}
        </span>
      </div>
      {item.evidence && (
        <div className="mb-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
          <p className="text-[10px] uppercase tracking-wider text-white/25 mb-1">Evidence</p>
          <p className="text-xs text-white/50 leading-relaxed">{item.evidence}</p>
        </div>
      )}
      {item.recommended_action && (
        <p className="text-xs text-purple-400 leading-snug mb-2">
          &rarr; {item.recommended_action}
        </p>
      )}
      {onCreateCampaign && (
        <button
          onClick={() => onCreateCampaign(item.insight)}
          className="text-xs px-2.5 py-1 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
        >
          <Zap className="w-3 h-3" />
          Create Campaign
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Tab 1: Industry Intelligence
// ============================================================================

function IndustryTab({
  vi,
  campaignCount,
}: {
  vi: VerticalIntelligenceData | null;
  campaignCount: number;
}) {
  const navigate = useNavigate();

  const financialPulse: FinancialPulse | null = vi?.financial_pulse ?? null;
  // Filter out garbage key_trends: signal_type labels, too-short text, or concatenated headlines
  const keyTrends: KeyTrend[] = (vi?.key_trends ?? []).filter(
    (t) =>
      t.trend &&
      t.trend.length > 20 &&
      !['general', 'market_trend', 'competitor_news', 'regulation', 'funding', 'hiring'].includes(t.trend.trim().toLowerCase()) &&
      // Skip entries where "trend" is just comma-separated headlines
      (t.trend.match(/,/g) || []).length < 3,
  );
  const regulatory: RegulatoryItem[] = vi?.regulatory_environment ?? [];
  const implications: GTMImplication[] = vi?.gtm_implications ?? [];

  const hasSoWhat = financialPulse != null || keyTrends.length > 0 || regulatory.length > 0;
  const hasDoWhat = implications.length > 0;

  const handleCreateCampaign = (insight: string) => {
    navigate(`/campaigns?playbook=strategy&headline=${encodeURIComponent(insight)}`);
  };

  const sgaTrend = trendArrow(financialPulse?.sga_trend ?? null);
  const rndTrend = trendArrow(financialPulse?.rnd_trend ?? null);
  const marginStatus = financialPulse?.margin_compression_or_expansion;

  const trendInterpretation = (trend: string | null, metric: string): string => {
    if (!trend) return '';
    const t = trend.toLowerCase();
    if (metric === 'sga') {
      if (t === 'declining' || t === 'decreasing') return 'Cost optimization cycle';
      if (t === 'rising' || t === 'increasing') return 'Ramp-up in sales investment';
    }
    if (metric === 'rnd') {
      if (t === 'rising' || t === 'increasing') return 'Innovation race intensifying';
      if (t === 'declining' || t === 'decreasing') return 'R&D consolidation';
    }
    return trend;
  };

  const marginInterpretation = (status: string | null): { label: string; color: string } => {
    if (!status) return { label: '', color: 'text-white/40' };
    const s = status.toLowerCase();
    if (s.includes('expand')) return { label: 'Growth phase', color: 'text-emerald-400' };
    if (s.includes('compress')) return { label: 'Margin pressure', color: 'text-red-400' };
    return { label: status, color: 'text-white/40' };
  };

  const margin = marginInterpretation(marginStatus ?? null);

  return (
    <div className="space-y-6">
      {/* SO WHAT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="So What?" />
        <div className="px-5 pb-4">
          {!hasSoWhat ? (
            <EmptyState
              icon={<BarChart3 className="w-5 h-5" />}
              text="No industry data yet — run your first analysis to populate this section."
            />
          ) : (
            <>
              {/* Financial pulse */}
              {financialPulse && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Financial pulse — {vi?.vertical_name ?? 'your vertical'}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {/* SG&A */}
                    {financialPulse.sga_median != null && (
                      <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-xs text-white/40">SG&A median</span>
                          {sgaTrend.icon && (
                            <span className={sgaTrend.color}>{sgaTrend.icon}</span>
                          )}
                        </div>
                        <p className="text-lg font-semibold text-white tabular-nums">
                          {(financialPulse.sga_median < 1 ? financialPulse.sga_median * 100 : financialPulse.sga_median).toFixed(1)}%
                        </p>
                        <p className="text-[10px] text-white/30 mt-0.5">
                          {trendInterpretation(financialPulse.sga_trend, 'sga') || (sgaTrend.label || 'Stable')}
                        </p>
                      </div>
                    )}
                    {/* R&D */}
                    {financialPulse.rnd_median != null && (
                      <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-xs text-white/40">R&D intensity</span>
                          {rndTrend.icon && (
                            <span className={rndTrend.color}>{rndTrend.icon}</span>
                          )}
                        </div>
                        <p className="text-lg font-semibold text-white tabular-nums">
                          {(financialPulse.rnd_median < 1 ? financialPulse.rnd_median * 100 : financialPulse.rnd_median).toFixed(1)}%
                        </p>
                        <p className="text-[10px] text-white/30 mt-0.5">
                          {trendInterpretation(financialPulse.rnd_trend, 'rnd') || (rndTrend.label || 'Stable')}
                        </p>
                      </div>
                    )}
                    {/* Margin status */}
                    {marginStatus && (
                      <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3">
                        <p className="text-xs text-white/40 mb-1">Margins</p>
                        <p className={`text-sm font-semibold capitalize ${margin.color}`}>
                          {marginStatus}
                        </p>
                        <p className="text-[10px] text-white/30 mt-0.5">{margin.label}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Key trends */}
              {keyTrends.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Key trends</p>
                  <div className="space-y-2">
                    {keyTrends.map((t, i) => (
                      <div key={i} className="rounded-lg border border-white/8 bg-white/[0.02] p-3">
                        <p className="text-sm font-medium text-white">{t.trend}</p>
                        {t.evidence && (
                          <p className="text-xs text-white/50 mt-0.5">{t.evidence}</p>
                        )}
                        {t.impact && (
                          <p className="text-xs text-amber-400 mt-1">&rarr; {t.impact}</p>
                        )}
                        {t.source_count != null && t.source_count > 0 && (
                          <span className="text-[10px] text-white/20 mt-1 inline-block">
                            {t.source_count} {t.source_count === 1 ? 'source' : 'sources'}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Regulatory */}
              {regulatory.length > 0 && (
                <div>
                  <p className="text-xs text-white/40 mb-2">Regulatory environment</p>
                  <div className="space-y-2">
                    {regulatory.map((r, i) => (
                      <div key={i} className="flex gap-2.5 py-2 border-b border-white/5 last:border-0">
                        <Shield className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white">{r.title}</p>
                          {r.summary && (
                            <p className="text-xs text-white/50 mt-0.5 line-clamp-2">{r.summary}</p>
                          )}
                          {r.impact && (
                            <p className="text-xs text-blue-400 mt-1">&rarr; {r.impact}</p>
                          )}
                          {r.source && (
                            <span className="text-[10px] text-white/25">{r.source}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* DO WHAT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="What Should We Do?" />
        <div className="px-5 pb-4">
          {!hasDoWhat ? (
            <EmptyState
              icon={<Target className="w-5 h-5" />}
              text="Growth implications will appear after your first analysis."
            />
          ) : (
            <div className="space-y-3">
              {implications
                .slice()
                .sort((a, b) => {
                  const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
                  return (order[(a.priority ?? 'low').toLowerCase()] ?? 2) - (order[(b.priority ?? 'low').toLowerCase()] ?? 2);
                })
                .map((item, i) => (
                  <GTMImplicationCard key={i} item={item} onCreateCampaign={handleCreateCampaign} />
                ))}
            </div>
          )}
        </div>
      </div>

      {/* ARE WE DOING IT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="Are We Doing It?" />
        <div className="px-5 pb-4">
          {campaignCount > 0 ? (
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-white">
                  {campaignCount} {campaignCount === 1 ? 'campaign' : 'campaigns'} in progress
                </span>
              </div>
              <button
                onClick={() => navigate('/campaigns')}
                className="text-xs text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
              >
                Manage campaigns
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <div className="py-4">
              <p className="text-sm text-white/50 leading-relaxed">
                Strategic recommendations above are ready for campaign planning. The Campaign Manager will translate these into targeted outreach with AI-generated content.
              </p>
              <button
                onClick={() => navigate('/campaigns')}
                className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
              >
                <Rocket className="w-3 h-3" />
                Plan Campaigns
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Tab 2: Market Signals
// ============================================================================

function MarketTab({
  vi,
  industrySignals,
  campaignCount,
}: {
  vi: VerticalIntelligenceData | null;
  industrySignals: IndustrySignalsData | null;
  campaignCount: number;
}) {
  const navigate = useNavigate();

  // Filter out dossier fragments (not real signals) and entries with no headline
  const signalDigest: SignalDigestItem[] = (vi?.signal_digest ?? []).filter(
    (item) =>
      item.headline &&
      item.headline.length > 20 &&
      !(item.source ?? '').startsWith('dossier:') &&
      !item.headline.includes('##') &&
      // Skip fragments that start mid-sentence (lowercase first char)
      /^[A-Z0-9"']/.test(item.headline.trim()),
  );
  // Filter out executive movements with no name — no useful data to show
  const execMovements: ExecutiveMovement[] = (vi?.executive_movements ?? []).filter(
    (m) => m.name != null && m.name.trim() !== '',
  );
  const signals: MarketSignal[] = (industrySignals?.signals ?? []).slice().sort((a, b) => {
    const urgencyOrder: Record<string, number> = { immediate: 0, this_week: 1, this_month: 2, monitor: 3 };
    return (urgencyOrder[a.urgency] ?? 3) - (urgencyOrder[b.urgency] ?? 3);
  });
  const articles: MarketArticle[] = industrySignals?.articles ?? [];

  // Deduplicate strategy recommendations from signals
  const strategyCards = (() => {
    const seen = new Set<string>();
    const cards: { strategy: string; headline: string; urgency: string; signalId: string }[] = [];
    for (const s of signals) {
      if (s.recommended_action && !seen.has(s.recommended_action)) {
        seen.add(s.recommended_action);
        cards.push({
          strategy: s.recommended_action,
          headline: s.headline,
          urgency: s.urgency,
          signalId: s.id,
        });
      }
    }
    return cards;
  })();

  const handleDeployPlaybook = (signal: MarketSignal) => {
    const headline = encodeURIComponent(signal.headline);
    navigate(`/campaigns?signal=${signal.id}&playbook=signal_triggered&headline=${headline}`);
  };

  const hasSoWhat = signalDigest.length > 0 || signals.length > 0 || articles.length > 0 || execMovements.length > 0;

  return (
    <div className="space-y-6">
      {/* SO WHAT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="So What?" />
        <div className="px-5 pb-4">
          {!hasSoWhat ? (
            <EmptyState
              icon={<Radio className="w-5 h-5" />}
              text="Market Intelligence scans 142 sources daily."
              subtext="Your first briefing arrives with your initial analysis."
            />
          ) : (
            <>
              {/* Signal digest from VI */}
              {signalDigest.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Vertical signal digest</p>
                  <div className="space-y-2">
                    {signalDigest.map((item, i) => (
                      <div key={i} className="rounded-lg border border-white/8 bg-white/[0.02] p-3">
                        <div className="flex items-center gap-2 mb-1">
                          {item.signal_type && (
                            <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border text-white/50 bg-white/5 border-white/10">
                              {labelForSignalType(item.signal_type)}
                            </span>
                          )}
                          {item.published_at && (
                            <span className="text-[10px] text-white/25">{timeAgo(item.published_at)}</span>
                          )}
                          {item.companies_mentioned.length > 0 && (
                            <span className="text-[10px] text-white/25">
                              {item.companies_mentioned.slice(0, 2).join(', ')}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-white">{item.headline}</p>
                        {item.source && (
                          <span className="text-[10px] text-white/25 mt-0.5 inline-block">{item.source}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Industry signals from endpoint */}
              {signals.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Live market signals</p>
                  {signals.map((s) => (
                    <SignalRow key={s.id} signal={s} onDeploy={handleDeployPlaybook} />
                  ))}
                </div>
              )}

              {/* Market articles */}
              {articles.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Market coverage</p>
                  <div className="space-y-2">
                    {articles.map((a) => (
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

              {/* Executive movements */}
              {execMovements.length > 0 && (
                <div>
                  <p className="text-xs text-white/40 mb-2">Executive movements</p>
                  <div className="space-y-2">
                    {execMovements.map((m, i) => (
                      <div key={i} className="flex gap-2.5 py-2 border-b border-white/5 last:border-0">
                        <Users className="w-4 h-4 text-white/30 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white">
                            {m.name ?? 'Unknown'}
                            {m.company ? <span className="text-white/50"> at {m.company}</span> : null}
                          </p>
                          <p className="text-xs text-white/40">
                            {m.old_title && m.new_title
                              ? `${m.old_title} \u2192 ${m.new_title}`
                              : m.new_title ?? m.old_title ?? m.change_type ?? ''}
                          </p>
                          {m.date && (
                            <span className="text-[10px] text-white/20">{timeAgo(m.date)}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* DO WHAT — synthesized strategies from signal recommendations */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="What Should We Do?" />
        <div className="px-5 pb-4">
          {strategyCards.length === 0 ? (
            <EmptyState
              icon={<Target className="w-5 h-5" />}
              text="Market signals are being monitored."
              subtext="Strategic responses will appear as patterns emerge."
            />
          ) : (
            <div className="space-y-3">
              {strategyCards.map((card, i) => {
                const badgeColor = URGENCY_BADGE[card.urgency] ?? URGENCY_BADGE.monitor;
                return (
                  <div key={i} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start gap-2 mb-2">
                      <Target className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm font-medium text-white leading-snug">{card.strategy}</p>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${badgeColor}`}>
                        {URGENCY_LABELS[card.urgency] ?? card.urgency}
                      </span>
                      <span className="text-xs text-white/40 line-clamp-1">{card.headline}</span>
                    </div>
                    <button
                      onClick={() => {
                        const headline = encodeURIComponent(card.headline);
                        navigate(`/campaigns?signal=${card.signalId}&playbook=signal_triggered&headline=${headline}`);
                      }}
                      className="text-xs px-2.5 py-1 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
                    >
                      <Zap className="w-3 h-3" />
                      Deploy Campaign
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ARE WE DOING IT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="Are We Doing It?" />
        <div className="px-5 pb-4">
          {campaignCount > 0 ? (
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-white">
                  {campaignCount} {campaignCount === 1 ? 'campaign' : 'campaigns'} responding to market signals
                </span>
              </div>
              <button
                onClick={() => navigate('/campaigns')}
                className="text-xs text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
              >
                View campaigns
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <div className="py-4">
              <p className="text-sm text-white/50">No campaigns deployed from market signals yet.</p>
              <button
                onClick={() => navigate('/campaigns')}
                className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
              >
                <Rocket className="w-3 h-3" />
                View Campaign Manager
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Tab 3: Competitive Landscape
// ============================================================================

// The competitive_dynamics JSON from the VI backend uses vertical-specific keys.
// For marketing_comms: leaders, movers_up, movers_down, gtm_investors,
// sg_agency_landscape (85 agencies), holding_group_map (23 groups),
// segment_breakdown, service_line_matrix, award_leaderboard, sg_market_pulse.
// For other verticals: leaders, challengers, movers, new_entrants.
// We read the actual keys present in the data.

interface AgencyLandscapeEntry {
  name?: string;
  segment?: string;
  parent_group?: string;
  service_lines?: string[];
}

interface HoldingGroupEntry {
  agencies: string[];
  subsidiary_count: number;
}

function CompetitorsTab({
  vi,
  competitorSignals,
  sequenceCount,
  campaignCount,
}: {
  vi: VerticalIntelligenceData | null;
  competitorSignals: MarketSignal[];
  sequenceCount: number;
  campaignCount: number;
}) {
  const navigate = useNavigate();

  // Read competitive_dynamics as raw Record to access all keys
  const dynamics = (vi?.competitive_dynamics ?? {}) as Record<string, unknown>;

  // Listed company dynamics (works for all verticals)
  const leaders = (dynamics.leaders ?? []) as Array<Record<string, unknown>>;
  const moversUp = (dynamics.movers_up ?? dynamics.movers ?? []) as Array<Record<string, unknown>>;
  const moversDown = (dynamics.movers_down ?? []) as Array<Record<string, unknown>>;
  // Agency landscape (marketing_comms-specific but safely optional)
  const agencyLandscape = (dynamics.sg_agency_landscape ?? []) as AgencyLandscapeEntry[];
  const holdingGroupMap = (dynamics.holding_group_map ?? {}) as Record<string, HoldingGroupEntry>;
  const segmentBreakdown = (dynamics.segment_breakdown ?? {}) as Record<string, number>;
  const serviceLineMatrix = (dynamics.service_line_matrix ?? {}) as Record<string, { count: number; agencies?: string[] }>;
  const marketPulse = dynamics.sg_market_pulse as { hiring_velocity?: { agencies_hiring?: number; total_openings?: number; signal?: string }; award_density?: { award_winning_agencies?: number; pct_with_major_awards?: number } } | undefined;
  const totalTracked = dynamics.total_tracked as number | undefined;

  const hasAgencyLandscape = agencyLandscape.length > 0;
  const hasListedDynamics = leaders.length > 0 || moversUp.length > 0;
  const hasDynamics = hasAgencyLandscape || hasListedDynamics;
  const holdingGroups = Object.entries(holdingGroupMap).sort((a, b) => b[1].subsidiary_count - a[1].subsidiary_count);
  const segmentEntries = Object.entries(segmentBreakdown).sort((a, b) => b[1] - a[1]);
  const serviceLines = Object.entries(serviceLineMatrix).sort((a, b) => b[1].count - a[1].count);

  // Filter gtm_implications where evidence mentions competitive keywords
  const competitivePattern = /\b(competitor|competitive|ownership|agency|agencies|service\s+line|holding\s+group|market\s+share|displacement)\b/i;
  const competitiveImplications = (vi?.gtm_implications ?? []).filter((imp) => {
    const text = `${imp.evidence ?? ''} ${imp.insight ?? ''}`;
    return competitivePattern.test(text);
  });

  const handleDeployPlaybook = (signal: MarketSignal) => {
    const headline = encodeURIComponent(signal.headline);
    navigate(`/campaigns?signal=${signal.id}&playbook=signal_triggered&headline=${headline}`);
  };

  const handleCreateCampaign = (insight: string) => {
    navigate(`/campaigns?playbook=strategy&headline=${encodeURIComponent(insight)}`);
  };

  function DynamicsRow({ entry, label, color }: { entry: Record<string, unknown>; label: string; color: string }) {
    const name = (entry.name as string | undefined) ?? (entry.ticker as string | undefined) ?? 'Unknown';
    const ticker = entry.ticker as string | undefined;
    const growth = entry.revenue_growth_yoy as number | undefined;
    return (
      <div className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
        <span className="text-sm text-white font-medium flex-1 min-w-0 truncate">{name}</span>
        {ticker && <span className="text-[10px] text-white/25 font-mono flex-shrink-0">{ticker}</span>}
        {growth != null && (
          <span className={`text-xs tabular-nums flex-shrink-0 ${growth >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {growth >= 0 ? '+' : ''}{(growth * 100).toFixed(1)}%
          </span>
        )}
        <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border flex-shrink-0 ${color}`}>
          {label}
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* SO WHAT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="So What?" />
        <div className="px-5 pb-4">
          {!hasDynamics && competitorSignals.length === 0 ? (
            <EmptyState
              icon={<Crosshair className="w-5 h-5" />}
              text="Competitor Analyst monitors your competitive landscape."
              subtext="Run your first analysis to identify and track key competitors."
            />
          ) : (
            <>
              {/* Market pulse summary — hiring + awards */}
              {marketPulse && (
                <div className="mb-4 flex flex-wrap gap-3">
                  {marketPulse.hiring_velocity?.agencies_hiring != null && (
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 flex-1 min-w-[140px]">
                      <p className="text-xs text-white/40 mb-1">Hiring activity</p>
                      <p className="text-lg font-semibold text-white tabular-nums">
                        {marketPulse.hiring_velocity.agencies_hiring} agencies
                      </p>
                      <p className="text-[10px] text-white/30">
                        {marketPulse.hiring_velocity.total_openings?.toLocaleString()} total openings
                      </p>
                    </div>
                  )}
                  {totalTracked != null && (
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 flex-1 min-w-[140px]">
                      <p className="text-xs text-white/40 mb-1">Tracked companies</p>
                      <p className="text-lg font-semibold text-white tabular-nums">{totalTracked}</p>
                      <p className="text-[10px] text-white/30">Listed in your vertical</p>
                    </div>
                  )}
                  {agencyLandscape.length > 0 && (
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 flex-1 min-w-[140px]">
                      <p className="text-xs text-white/40 mb-1">SG agency landscape</p>
                      <p className="text-lg font-semibold text-white tabular-nums">{agencyLandscape.length}</p>
                      <p className="text-[10px] text-white/30">
                        Mapped across {holdingGroups.length} groups
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Segment breakdown — who competes where */}
              {segmentEntries.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Market segments</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {segmentEntries.map(([segment, count]) => {
                      const maxSeg = segmentEntries[0]?.[1] ?? 1;
                      const pct = (count / maxSeg) * 100;
                      return (
                        <div key={segment} className="rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-white/60 truncate">{segment}</span>
                            <span className="text-xs font-medium text-white/70 tabular-nums ml-2">{count}</span>
                          </div>
                          <div className="h-1 rounded-full bg-white/5 overflow-hidden">
                            <div className="h-full rounded-full bg-purple-500/40" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Holding groups — network vs independent */}
              {holdingGroups.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Holding groups</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {holdingGroups.slice(0, 9).map(([group, data]) => (
                      <div key={group} className="rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
                        <p className="text-xs text-white font-medium truncate">{group}</p>
                        <p className="text-[10px] text-white/30">
                          {data.subsidiary_count} {data.subsidiary_count === 1 ? 'agency' : 'agencies'}
                        </p>
                      </div>
                    ))}
                  </div>
                  {holdingGroups.length > 9 && (
                    <p className="text-[10px] text-white/20 mt-2">+{holdingGroups.length - 9} more groups</p>
                  )}
                </div>
              )}

              {/* Service line matrix */}
              {serviceLines.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Service line density</p>
                  <div className="flex flex-wrap gap-2">
                    {serviceLines.map(([line, data]) => (
                      <span key={line} className="text-xs px-2.5 py-1 rounded-lg border border-white/8 bg-white/[0.02] text-white/60">
                        {line} <span className="text-white/30 font-medium tabular-nums">({data.count})</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Listed company dynamics — leaders + movers */}
              {hasListedDynamics && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Listed company dynamics</p>
                  {leaders.slice(0, 5).map((e, i) => (
                    <DynamicsRow key={`l-${i}`} entry={e} label="Leader" color="text-emerald-400 border-emerald-500/20 bg-emerald-500/10" />
                  ))}
                  {moversUp.slice(0, 3).map((e, i) => (
                    <DynamicsRow key={`mu-${i}`} entry={e} label="Rising" color="text-blue-400 border-blue-500/20 bg-blue-500/10" />
                  ))}
                  {moversDown.slice(0, 3).map((e, i) => (
                    <DynamicsRow key={`md-${i}`} entry={e} label="Declining" color="text-amber-400 border-amber-500/20 bg-amber-500/10" />
                  ))}
                </div>
              )}

              {/* Competitor signals */}
              {competitorSignals.length > 0 && (
                <div>
                  <p className="text-xs text-white/40 mb-2">Competitor signals</p>
                  {competitorSignals.slice(0, 6).map((s) => (
                    <SignalRow key={s.id} signal={s} onDeploy={handleDeployPlaybook} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* DO WHAT — competitive implications (strategic) + per-signal responses (tactical) */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="What Should We Do?" />
        <div className="px-5 pb-4">
          {competitiveImplications.length === 0 && competitorSignals.filter((s) => s.recommended_action).length === 0 ? (
            <EmptyState
              icon={<Target className="w-5 h-5" />}
              text="Competitor response recommendations will appear here."
            />
          ) : (
            <div className="space-y-3">
              {/* Strategic implications first */}
              {competitiveImplications.length > 0 && (
                <>
                  <p className="text-xs text-white/40">Strategic competitive implications</p>
                  {competitiveImplications.map((item, i) => (
                    <GTMImplicationCard key={`ci-${i}`} item={item} onCreateCampaign={handleCreateCampaign} />
                  ))}
                </>
              )}

              {/* Tactical per-signal responses */}
              {competitorSignals.filter((s) => s.recommended_action).length > 0 && (
                <>
                  <p className="text-xs text-white/40 mt-2">Tactical signal responses</p>
                  {competitorSignals
                    .filter((s) => s.recommended_action)
                    .map((s) => {
                      const badgeColor = URGENCY_BADGE[s.urgency] ?? URGENCY_BADGE.monitor;
                      const urgencyLabel = URGENCY_LABELS[s.urgency] ?? s.urgency;
                      return (
                        <div key={s.id} className="rounded-lg border border-white/8 bg-white/[0.02] p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${badgeColor}`}>
                              {urgencyLabel}
                            </span>
                            <span className="text-xs text-white/50 line-clamp-1 flex-1">{s.headline}</span>
                          </div>
                          <p className="text-xs text-purple-400 mb-2">&rarr; {s.recommended_action}</p>
                          <button
                            onClick={() => handleCreateCampaign(s.headline)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
                          >
                            <Zap className="w-3 h-3" />
                            Create Campaign
                          </button>
                        </div>
                      );
                    })}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ARE WE DOING IT */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="Are We Doing It?" />
        <div className="px-5 pb-4">
          {sequenceCount > 0 || campaignCount > 0 ? (
            <div className="py-2 space-y-2">
              {campaignCount > 0 && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-white">
                      {campaignCount} {campaignCount === 1 ? 'campaign' : 'campaigns'} in progress
                    </span>
                  </div>
                  <button
                    onClick={() => navigate('/campaigns')}
                    className="text-xs text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
                  >
                    View campaigns
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              )}
              {sequenceCount > 0 && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-white">
                      {sequenceCount} active {sequenceCount === 1 ? 'sequence' : 'sequences'}
                    </span>
                  </div>
                  <button
                    onClick={() => navigate('/sequences')}
                    className="text-xs text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
                  >
                    View sequences
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="py-4">
              <p className="text-sm text-white/50">Competitive response strategies are ready for campaign planning.</p>
              <button
                onClick={() => navigate('/campaigns')}
                className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
              >
                <Rocket className="w-3 h-3" />
                Plan Campaigns
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Tab 4: Growth Opportunities
// ============================================================================

function OpportunitiesTab({
  vi,
  pipelineData,
  campaignCount,
}: {
  vi: VerticalIntelligenceData | null;
  pipelineData: PipelineSummaryData | null;
  campaignCount: number;
}) {
  const navigate = useNavigate();

  // Strategic opportunity data from VI
  const dynamics = (vi?.competitive_dynamics ?? {}) as Record<string, unknown>;
  const moversUp = (dynamics.movers_up ?? dynamics.movers ?? []) as Array<Record<string, unknown>>;
  const moversDown = (dynamics.movers_down ?? []) as Array<Record<string, unknown>>;
  const keyTrends = (vi?.key_trends ?? []).filter(
    (t) =>
      t.trend &&
      t.trend.length > 20 &&
      !['general', 'market_trend', 'competitor_news', 'regulation', 'funding', 'hiring'].includes(t.trend.trim().toLowerCase()) &&
      (t.trend.match(/,/g) || []).length < 3,
  );
  const marketOverview = (vi?.market_overview ?? {}) as Record<string, unknown>;
  const marketSummary = (marketOverview.summary as string | undefined) ?? null;

  // Service line & segment gap analysis
  const serviceLineMatrix = (dynamics.service_line_matrix ?? {}) as Record<string, { count: number }>;
  const segmentBreakdown = (dynamics.segment_breakdown ?? {}) as Record<string, number>;
  const serviceLines = Object.entries(serviceLineMatrix).sort((a, b) => a[1].count - b[1].count);
  const underservedLines = serviceLines.filter(([, d]) => d.count <= 5).slice(0, 4);
  const segments = Object.entries(segmentBreakdown).sort((a, b) => a[1] - b[1]);
  const underservedSegments = segments.filter(([, count]) => count <= 5).slice(0, 4);

  // Only high-priority implications that have a clear action (avoid duplicating Industry tab)
  const highImplications = (vi?.gtm_implications ?? [])
    .filter((i) => (i.priority ?? '').toLowerCase() === 'high' && i.recommended_action);

  const statusMap = new Map((pipelineData?.by_status ?? []).map((s) => [s.status, s.count]));
  const maxCount = Math.max(...(pipelineData?.by_status ?? []).map((s) => s.count), 1);
  const topLeads = [...(pipelineData?.recent_leads ?? [])]
    .sort((a, b) => b.fit_score - a.fit_score)
    .slice(0, 4);
  const newLeads = statusMap.get('new') ?? 0;
  const qualifiedLeads = statusMap.get('qualified') ?? 0;

  const avgFit = pipelineData?.avg_fit_score ?? null;
  const isLowQuality = avgFit != null && avgFit < 30;
  const fitScoreColor = avgFit == null ? 'text-white/30' : avgFit >= 50 ? 'text-emerald-400' : avgFit >= 30 ? 'text-amber-400' : 'text-red-400';

  const handleCreateCampaign = (insight: string) => {
    navigate(`/campaigns?playbook=strategy&headline=${encodeURIComponent(insight)}`);
  };

  const hasStrategicData = keyTrends.length > 0 || moversDown.length > 0 || underservedLines.length > 0 || underservedSegments.length > 0;

  return (
    <div className="space-y-6">
      {/* SO WHAT — strategic opportunity analysis */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="So What?" />
        <div className="px-5 pb-4">
          {!hasStrategicData && !pipelineData ? (
            <EmptyState
              icon={<Rocket className="w-5 h-5" />}
              text="Growth opportunities will appear after your first analysis."
            />
          ) : (
            <>
              {/* Market overview */}
              {marketSummary && (
                <p className="text-sm text-white/60 leading-relaxed mb-4">{marketSummary}</p>
              )}

              {/* Key trends creating demand — WHERE to hunt */}
              {keyTrends.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Trends creating demand</p>
                  <div className="space-y-2">
                    {keyTrends.slice(0, 4).map((t, i) => (
                      <div key={i} className="rounded-lg border border-white/8 bg-white/[0.02] p-3">
                        <div className="flex items-start gap-2">
                          <TrendingUp className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white">{t.trend}</p>
                            {t.impact && (
                              <p className="text-xs text-purple-400 mt-0.5">&rarr; {t.impact}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Underserved areas — gaps in market coverage */}
              {(underservedLines.length > 0 || underservedSegments.length > 0) && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Market gaps — low competition areas</p>
                  <div className="flex flex-wrap gap-2">
                    {underservedLines.map(([line, data]) => (
                      <span key={line} className="text-xs px-2.5 py-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-emerald-400">
                        {line} <span className="text-emerald-400/50">({data.count} providers)</span>
                      </span>
                    ))}
                    {underservedSegments.map(([seg, count]) => (
                      <span key={seg} className="text-xs px-2.5 py-1.5 rounded-lg border border-blue-500/20 bg-blue-500/5 text-blue-400">
                        {seg} <span className="text-blue-400/50">({count} companies)</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Declining competitors — displacement targets */}
              {moversDown.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Weakening competitors — their clients need alternatives</p>
                  <div className="space-y-2">
                    {moversDown.map((entry, i) => {
                      const name = (entry.name as string | undefined) ?? 'Unknown';
                      const growth = entry.revenue_growth_yoy as number | undefined;
                      return (
                        <div key={i} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                          <span className="text-sm text-white flex-1 min-w-0 truncate">{name}</span>
                          {growth != null && (
                            <span className="text-xs text-red-400 tabular-nums flex-shrink-0">
                              {(growth * 100).toFixed(1)}% YoY
                            </span>
                          )}
                          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border text-red-400 border-red-500/20 bg-red-500/10 flex-shrink-0">
                            Declining
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Rising challengers — watch or partner */}
              {moversUp.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Rising challengers — watch or partner</p>
                  <div className="space-y-2">
                    {moversUp.slice(0, 3).map((entry, i) => {
                      const name = (entry.name as string | undefined) ?? 'Unknown';
                      const growth = entry.revenue_growth_yoy as number | undefined;
                      return (
                        <div key={i} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                          <span className="text-sm text-white flex-1 min-w-0 truncate">{name}</span>
                          {growth != null && (
                            <span className="text-xs text-emerald-400 tabular-nums flex-shrink-0">
                              +{(growth * 100).toFixed(1)}% YoY
                            </span>
                          )}
                          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border text-emerald-400 border-emerald-500/20 bg-emerald-500/10 flex-shrink-0">
                            Rising
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Pipeline reality check — moved to bottom as context */}
              {pipelineData && (
                <div className="pt-3 border-t border-white/5">
                  <p className="text-xs text-white/40 mb-2">Current pipeline</p>
                  <div className="flex flex-wrap gap-3">
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 flex-1 min-w-[100px]">
                      <p className="text-lg font-semibold text-white tabular-nums">{pipelineData.total_leads}</p>
                      <p className="text-[10px] text-white/40">total leads</p>
                    </div>
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 flex-1 min-w-[100px]">
                      <p className="text-lg font-semibold text-blue-400 tabular-nums">{newLeads}</p>
                      <p className="text-[10px] text-white/40">uncontacted</p>
                    </div>
                    {avgFit != null && (
                      <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 flex-1 min-w-[100px]">
                        <p className={`text-lg font-semibold tabular-nums ${fitScoreColor}`}>{Math.round(avgFit)}%</p>
                        <p className="text-[10px] text-white/40">avg fit</p>
                      </div>
                    )}
                  </div>
                  {isLowQuality && (
                    <p className="text-xs text-amber-400/70 mt-2">Pipeline quality is low — strategic campaigns will improve targeting.</p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* DO WHAT — high-priority actions with quality gate */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="What Should We Do?" />
        <div className="px-5 pb-4">
          {highImplications.length === 0 && newLeads === 0 ? (
            <EmptyState
              icon={<BookOpen className="w-5 h-5" />}
              text="Actionable recommendations will appear after your first analysis."
            />
          ) : (
            <div className="space-y-3">
              {/* Quality gate warning when avg fit is low */}
              {isLowQuality && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
                  <div className="flex items-start gap-2 mb-2">
                    <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm font-medium text-amber-300 leading-snug">
                      Pipeline quality needs attention — avg fit score is {Math.round(avgFit!)}%
                    </p>
                  </div>
                  <p className="text-xs text-white/50 mb-3">
                    Current leads are early-stage and may not convert well. Launch a targeted campaign to build higher-quality pipeline.
                  </p>
                  <button
                    onClick={() => navigate('/campaigns')}
                    className="text-xs px-3 py-1.5 rounded-lg border border-amber-500/30 text-amber-400 hover:bg-amber-500/10 transition-colors flex items-center gap-1"
                  >
                    <Target className="w-3 h-3" />
                    Build Targeted Campaign
                  </button>
                </div>
              )}

              {/* Uncontacted leads call to action */}
              {newLeads > 0 && (
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4">
                  <div className="flex items-start gap-2 mb-2">
                    <Target className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm font-medium text-white leading-snug">
                      {newLeads} potential {newLeads === 1 ? 'lead has' : 'leads have'} not been contacted yet
                    </p>
                  </div>
                  <p className="text-xs text-white/50 mb-3">
                    {qualifiedLeads > 0 ? `${qualifiedLeads} qualified, ready for outreach. ` : ''}
                    {isLowQuality ? 'Review leads before outreach — fit scores are low.' : 'Deploy a playbook to start automated sequencing.'}
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => navigate('/prospects')}
                      className="text-xs px-3 py-1.5 rounded-lg border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-colors"
                    >
                      Review leads
                    </button>
                    {!isLowQuality && (
                      <button
                        onClick={() => navigate('/campaigns')}
                        className="text-xs px-3 py-1.5 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1"
                      >
                        <Zap className="w-3 h-3" />
                        Deploy outreach
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* High-priority implication CTAs */}
              {highImplications.map((item, i) => (
                <GTMImplicationCard key={i} item={item} onCreateCampaign={handleCreateCampaign} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ARE WE DOING IT — execution status */}
      <div className="glass-card rounded-xl border border-white/10">
        <LayerHeader label="Are We Doing It?" action="View pipeline" onAction={() => navigate('/prospects')} />
        <div className="px-5 pb-4">
          {!pipelineData && campaignCount === 0 ? (
            <EmptyState
              icon={<Users className="w-5 h-5" />}
              text="Lead Hunter identifies qualified prospects from verified databases."
              subtext="Your pipeline populates after your first analysis."
            />
          ) : (
            <>
              {/* Campaign + lead stats */}
              <div className="flex flex-wrap gap-3 py-3">
                <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 flex-1 min-w-[120px]">
                  <p className="text-xs text-white/40 mb-1">Campaigns</p>
                  <p className={`text-2xl font-semibold tabular-nums ${campaignCount > 0 ? 'text-emerald-400' : 'text-white/30'}`}>{campaignCount}</p>
                </div>
                {pipelineData && (
                  <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 flex-1 min-w-[120px]">
                    <p className="text-xs text-white/40 mb-1">Total leads</p>
                    <p className="text-2xl font-semibold text-white tabular-nums">{pipelineData.total_leads}</p>
                  </div>
                )}
                {avgFit != null && (
                  <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 flex-1 min-w-[120px]">
                    <p className="text-xs text-white/40 mb-1">Avg fit score</p>
                    <p className={`text-2xl font-semibold tabular-nums ${fitScoreColor}`}>
                      {Math.round(avgFit)}%
                    </p>
                  </div>
                )}
              </div>

              {/* Status bar */}
              {pipelineData && pipelineData.by_status.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-white/40 mb-2">Pipeline by status</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {PIPELINE_STATUSES.map((status) => {
                      const count = statusMap.get(status) ?? 0;
                      const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                      return (
                        <div key={status}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-white/50">{STATUS_LABELS[status]}</span>
                            <span className="text-xs font-medium text-white tabular-nums">{count}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${STATUS_COLORS[status] ?? 'bg-white/30'} transition-all duration-500`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Top leads */}
              {topLeads.length > 0 && (
                <div>
                  <p className="text-xs text-white/40 mb-2">Top prospects by fit score</p>
                  <div className="space-y-2">
                    {topLeads.map((lead) => {
                      const leadFitColor = lead.fit_score >= 50 ? 'text-emerald-400' : lead.fit_score >= 30 ? 'text-amber-400' : 'text-red-400';
                      return (
                        <div key={lead.id} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-white font-medium truncate">
                              {lead.lead_company_name ?? 'Unknown company'}
                            </p>
                            {lead.contact_name && (
                              <p className="text-xs text-white/50 truncate">
                                {lead.contact_name}
                                {lead.contact_title ? ` \u00b7 ${lead.contact_title}` : ''}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className={`text-xs font-medium tabular-nums ${leadFitColor}`}>
                              {Math.round(lead.fit_score)}%
                            </span>
                            <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${
                              lead.status === 'new'
                                ? 'text-blue-400 bg-blue-500/10 border-blue-500/20'
                                : lead.status === 'qualified'
                                ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                                : 'text-white/40 bg-white/5 border-white/10'
                            }`}>
                              {STATUS_LABELS[lead.status] ?? lead.status}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Pipeline quality footer */}
              {isLowQuality && (
                <p className="text-xs text-amber-400/70 mt-3 pt-3 border-t border-white/5">
                  Pipeline quality needs improvement — campaign targeting will help.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Page
// ============================================================================

export function InsightsPage() {
  const companyId = useCompanyId();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const rawTab = searchParams.get('tab') as TabId | null;
  const activeTab: TabId =
    rawTab && TABS.some((t) => t.id === rawTab) ? rawTab : 'industry';

  // State
  const [vi, setVi] = useState<VerticalIntelligenceData | null>(null);
  const [industrySignals, setIndustrySignals] = useState<IndustrySignalsData | null>(null);
  const [competitorSignals, setCompetitorSignals] = useState<MarketSignal[]>([]);
  const [pipelineData, setPipelineData] = useState<PipelineSummaryData | null>(null);
  const [campaignCount, setCampaignCount] = useState(0);
  const [sequenceCount, setSequenceCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) {
      setLoading(false);
      return;
    }

    setLoading(true);

    Promise.all([
      fetchVerticalIntelligence(companyId).catch(() => null),
      apiClient
        .get<IndustrySignalsData>(`/companies/${companyId}/market-data/industry-signals`)
        .catch(() => null),
      apiClient
        .get<MarketSignal[]>(`/companies/${companyId}/market-data/competitor-signals?limit=20`)
        .catch(() => []),
      apiClient
        .get<PipelineSummaryData>(`/companies/${companyId}/market-data/pipeline-summary`)
        .catch(() => null),
      apiClient
        .get<{ campaigns: unknown[] }>(`/companies/${companyId}/campaigns`)
        .then((r) => r.campaigns?.length ?? 0)
        .catch(() => 0),
      apiClient
        .get<unknown[]>(`/companies/${companyId}/sequences/enrollments`)
        .then((r) => (Array.isArray(r) ? r.length : 0))
        .catch(() => 0),
    ]).then(([viData, indSignals, compSignals, pipeline, campaigns, sequences]) => {
      setVi(viData);
      setIndustrySignals(indSignals);
      setCompetitorSignals(compSignals ?? []);
      setPipelineData(pipeline);
      setCampaignCount(campaigns);
      setSequenceCount(sequences);
    }).finally(() => {
      setLoading(false);
    });
  }, [companyId]);

  function setTab(tab: TabId) {
    setSearchParams({ tab }, { replace: true });
  }

  const tabTitles: Record<TabId, { title: string; subtitle: string }> = {
    industry: {
      title: 'Industry Intelligence',
      subtitle: 'What\'s happening in our industry and what does it mean for us?',
    },
    market: {
      title: 'Market Signals',
      subtitle: 'What signals are we picking up and which ones matter?',
    },
    competitors: {
      title: 'Competitive Landscape',
      subtitle: 'What are our competitors doing and how should we respond?',
    },
    opportunities: {
      title: 'Growth Opportunities',
      subtitle: 'Where should we focus next and what\'s the pipeline?',
    },
  };

  const current = tabTitles[activeTab];

  return (
    <div className="flex flex-col h-full">
      {/* Sticky header + tabs */}
      <div className="flex-shrink-0 px-6 pt-4 pb-0 border-b border-white/10">
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-3"
        >
          <h1 className="text-lg font-semibold text-white">{current.title}</h1>
          <p className="text-xs text-white/40 mt-0.5">{current.subtitle}</p>
        </motion.div>

        {/* Tab bar */}
        <div className="flex gap-1 p-1 rounded-xl bg-white/5 border border-white/8 overflow-x-auto mb-4">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setTab(tab.id)}
              className={`flex-1 min-w-max text-sm px-3 py-1.5 rounded-lg transition-all font-medium whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-white/10 text-white shadow-sm'
                  : 'text-white/40 hover:text-white/60'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* No company guard */}
        {!companyId && (
          <div className="glass-card rounded-xl border border-white/10 py-12 text-center">
            <Radio className="w-6 h-6 text-white/20 mx-auto mb-3" />
            <p className="text-sm text-white/40">Run your first analysis to see insights here.</p>
            <button
              onClick={() => navigate('/')}
              className="mt-4 text-xs px-4 py-2 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors"
            >
              Start analysis
            </button>
          </div>
        )}

        {/* Loading skeleton */}
        {companyId && loading && (
          <div className="space-y-4">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="glass-card rounded-xl border border-white/10 h-32 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Tab content */}
        {companyId && !loading && (
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'industry' && (
              <IndustryTab vi={vi} campaignCount={campaignCount} />
            )}
            {activeTab === 'market' && (
              <MarketTab vi={vi} industrySignals={industrySignals} campaignCount={campaignCount} />
            )}
            {activeTab === 'competitors' && (
              <CompetitorsTab
                vi={vi}
                competitorSignals={competitorSignals}
                sequenceCount={sequenceCount}
                campaignCount={campaignCount}
              />
            )}
            {activeTab === 'opportunities' && (
              <OpportunitiesTab vi={vi} pipelineData={pipelineData} campaignCount={campaignCount} />
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
