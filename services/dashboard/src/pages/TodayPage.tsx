/**
 * TodayPage — Primary landing page for paid users.
 *
 * Shows a personalised greeting, an intelligence briefing (market signals +
 * insights with "what it means for you"), a 3-column action grid, a next-best-
 * action CTA, and a recent activity feed.
 *
 * All data is fetched in parallel. Failures are caught individually so a
 * single failing endpoint never breaks the whole page.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Bell,
  Radio,
  TrendingUp,
  ArrowRight,
  Rocket,
  CheckCircle,
  Zap,
  Users,
  Newspaper,
  Lightbulb,
  AlertTriangle,
  Shield,
  DollarSign,
  Crosshair,
  BarChart2,
  ExternalLink,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCompany, useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';

// ============================================================================
// Types
// ============================================================================

interface SignalEvent {
  id: string;
  signal_type: string;
  urgency: string;
  is_actioned: boolean;
  headline: string;
  summary: string | null;
  source: string | null;
  source_url: string | null;
  recommended_action: string | null;
  relevance_score: number;
  competitors_mentioned: string[];
  created_at: string;
}

interface MarketInsightItem {
  id: string;
  insight_type: string;
  category: string | null;
  title: string;
  summary: string | null;
  impact_level: string | null;
  recommended_actions: string[];
  relevance_score: number;
  source_name: string | null;
  created_at: string;
  expires_at: string | null;
}

interface InsightsSummary {
  recent_trends: MarketInsightItem[];
  top_opportunities: MarketInsightItem[];
}

interface Lead {
  id: string;
  status?: string;
  name: string;
  company_name?: string;
  created_at?: string;
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

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ============================================================================
// Intelligence Briefing
// ============================================================================

type BriefingKind = 'signal' | 'insight';

interface BriefingItem {
  id: string;
  kind: BriefingKind;
  typeKey: string;      // signal_type or insight_type
  headline: string;
  summary: string | null;
  recommendation: string | null;
  urgency?: string;
  source: string | null;
  sourceUrl: string | null;
  timestamp: string;
}

function signalIcon(type: string) {
  const cls = 'w-4 h-4';
  switch (type) {
    case 'competitor_move': return <Crosshair className={cls} />;
    case 'regulatory':      return <Shield className={cls} />;
    case 'funding':         return <DollarSign className={cls} />;
    case 'product_launch':  return <Rocket className={cls} />;
    case 'market_shift':    return <TrendingUp className={cls} />;
    default:                return <Radio className={cls} />;
  }
}

function insightIcon(type: string) {
  const cls = 'w-4 h-4';
  switch (type) {
    case 'opportunity': return <Lightbulb className={cls} />;
    case 'threat':      return <AlertTriangle className={cls} />;
    case 'trend':       return <BarChart2 className={cls} />;
    default:            return <Newspaper className={cls} />;
  }
}

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  competitor_move: 'Competitor',
  regulatory:      'Regulatory',
  funding:         'Funding',
  product_launch:  'Product Launch',
  market_shift:    'Market Shift',
  customer_signal: 'Customer Signal',
};

const INSIGHT_TYPE_COLORS: Record<string, string> = {
  opportunity: 'text-green-400  bg-green-500/10  border-green-500/20',
  threat:      'text-red-400    bg-red-500/10    border-red-500/20',
  trend:       'text-blue-400   bg-blue-500/10   border-blue-500/20',
  news:        'text-white/50   bg-white/5       border-white/10',
};

const URGENCY_COLORS: Record<string, string> = {
  immediate: 'text-red-400    bg-red-500/10  border-red-500/20',
  this_week: 'text-amber-400  bg-amber-500/10 border-amber-500/20',
  monitor:   'text-white/40   bg-white/5      border-white/10',
};

function BriefingRow({ item }: { item: BriefingItem }) {
  const isSignal = item.kind === 'signal';

  const badgeColor = isSignal
    ? (URGENCY_COLORS[item.urgency ?? 'monitor'] ?? URGENCY_COLORS.monitor)
    : (INSIGHT_TYPE_COLORS[item.typeKey] ?? INSIGHT_TYPE_COLORS.news);

  const badgeLabel = isSignal
    ? (SIGNAL_TYPE_LABELS[item.typeKey] ?? item.typeKey.replace(/_/g, ' '))
    : (item.typeKey.charAt(0).toUpperCase() + item.typeKey.slice(1));

  const icon = isSignal ? signalIcon(item.typeKey) : insightIcon(item.typeKey);

  return (
    <div className="flex gap-3 py-3.5 border-b border-white/5 last:border-0">
      {/* Icon */}
      <div className={`mt-0.5 p-2 rounded-lg flex-shrink-0 ${badgeColor.split(' ').slice(1).join(' ')}`}>
        <span className={badgeColor.split(' ')[0]}>{icon}</span>
      </div>

      {/* Body */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${badgeColor}`}>
            {badgeLabel}
          </span>
          {item.source && (
            <span className="text-[10px] text-white/30">{item.source}</span>
          )}
        </div>

        <p className="text-sm font-medium text-white leading-snug line-clamp-2">
          {item.headline}
        </p>

        {item.summary && (
          <p className="text-xs text-white/50 mt-0.5 leading-relaxed line-clamp-2">
            {item.summary}
          </p>
        )}

        {item.recommendation && (
          <p className="text-xs text-purple-400 mt-1 leading-snug">
            → {item.recommendation}
          </p>
        )}
      </div>

      {/* Right: time + external link */}
      <div className="flex flex-col items-end gap-1 flex-shrink-0">
        <span className="text-[10px] text-white/30">{timeAgo(item.timestamp)}</span>
        {item.sourceUrl && (
          <a
            href={item.sourceUrl}
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

function IntelligenceBriefing({ signals, insights }: {
  signals: SignalEvent[];
  insights: InsightsSummary | null;
}) {
  const navigate = useNavigate();

  // Recency gates:
  //   signals  — created within the last 7 days (covers "this_week" urgency)
  //   insights — not yet expired AND created within the last 30 days
  const now = Date.now();
  const sevenDaysAgo  = now - 7  * 24 * 60 * 60 * 1000;
  const thirtyDaysAgo = now - 30 * 24 * 60 * 60 * 1000;

  const isRecentSignal = (s: SignalEvent) =>
    new Date(s.created_at).getTime() >= sevenDaysAgo;

  const isValidInsight = (ins: MarketInsightItem) => {
    if (new Date(ins.created_at).getTime() < thirtyDaysAgo) return false;
    if (ins.expires_at && new Date(ins.expires_at).getTime() < now) return false;
    return true;
  };

  // Build unified briefing list: top urgent signals + top insights, sorted by urgency/recency
  const items: BriefingItem[] = [];

  // Urgent / this_week signals (not actioned, recent), up to 3
  const urgencyOrder: Record<string, number> = { immediate: 0, this_week: 1, monitor: 2 };
  signals
    .filter((s) => !s.is_actioned && s.urgency !== 'monitor' && isRecentSignal(s))
    .sort((a, b) => (urgencyOrder[a.urgency] ?? 2) - (urgencyOrder[b.urgency] ?? 2))
    .slice(0, 3)
    .forEach((s) =>
      items.push({
        id: `signal-${s.id}`,
        kind: 'signal',
        typeKey: s.signal_type,
        headline: s.headline,
        summary: s.summary,
        recommendation: s.recommended_action,
        urgency: s.urgency,
        source: s.source,
        sourceUrl: s.source_url,
        timestamp: s.created_at,
      })
    );

  // Top trend + top opportunity from insights — only if not stale
  const topTrend = insights?.recent_trends?.find(isValidInsight);
  const topOpp   = insights?.top_opportunities?.find(isValidInsight);

  [topOpp, topTrend].forEach((ins) => {
    if (!ins) return;
    items.push({
      id: `insight-${ins.id}`,
      kind: 'insight',
      typeKey: ins.insight_type,
      headline: ins.title,
      summary: ins.summary,
      recommendation: ins.recommended_actions?.[0] ?? null,
      source: ins.source_name,
      sourceUrl: null,
      timestamp: ins.created_at,
    });
  });

  if (items.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl border border-white/10"
    >
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
            What's happening
          </p>
          <h2 className="text-sm font-semibold text-white mt-0.5">
            Your market intelligence briefing
          </h2>
        </div>
        <button
          onClick={() => navigate('/insights')}
          className="text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
        >
          Full feed
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      <div className="px-5 pb-1">
        {items.map((item) => (
          <BriefingRow key={item.id} item={item} />
        ))}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Action Grid Card
// ============================================================================

interface ActionCardProps {
  label: string;
  count: number;
  subLabel: string;
  icon: React.ReactNode;
  accentClass: string;
  borderClass: string;
  href: string;
}

function ActionCard({
  label,
  count,
  subLabel,
  icon,
  accentClass,
  borderClass,
  href,
}: ActionCardProps) {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass-card p-5 rounded-xl border ${borderClass} cursor-pointer hover:bg-white/5 transition-colors`}
      onClick={() => navigate(href)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className={`text-4xl font-bold tabular-nums ${accentClass}`}>
            {count}
          </span>
          <span className="text-sm font-medium text-white">{label}</span>
          <span className="text-xs text-white/40">{subLabel}</span>
        </div>
        <div className={`p-2.5 rounded-xl bg-white/5 ${accentClass} flex-shrink-0`}>
          {icon}
        </div>
      </div>
      {count > 0 && (
        <div className="mt-4 flex items-center gap-1 text-xs text-white/40 hover:text-white/60 transition-colors">
          View all
          <ArrowRight className="w-3 h-3" />
        </div>
      )}
    </motion.div>
  );
}

// ============================================================================
// Next Best Action Card
// ============================================================================

interface NextActionProps {
  pendingApprovals: number;
  urgentSignals: number;
  unqualifiedLeads: number;
}

function NextBestAction({ pendingApprovals, urgentSignals, unqualifiedLeads }: NextActionProps) {
  const navigate = useNavigate();

  let icon = <Rocket className="w-5 h-5" />;
  let title = '';
  let description = '';
  let buttonLabel = '';
  let buttonHref = '/campaigns';
  let accentClass = 'text-purple-400';
  let buttonClass =
    'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border border-purple-500/30';

  if (pendingApprovals > 0) {
    icon = <Bell className="w-5 h-5" />;
    title = `${pendingApprovals} ${pendingApprovals === 1 ? 'email' : 'emails'} waiting for your approval`;
    description =
      'Your outreach is queued — review and approve these emails before they expire.';
    buttonLabel = 'Go to Approvals';
    buttonHref = '/approvals';
    accentClass = 'text-amber-400';
    buttonClass =
      'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30';
  } else if (urgentSignals > 0) {
    icon = <Radio className="w-5 h-5" />;
    title = `${urgentSignals} urgent market ${urgentSignals === 1 ? 'signal' : 'signals'} detected`;
    description =
      'New funding, competitor moves or regulatory changes relevant to your prospects.';
    buttonLabel = 'View Signals';
    buttonHref = '/insights';
    accentClass = 'text-yellow-400';
    buttonClass =
      'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 border border-yellow-500/30';
  } else if (unqualifiedLeads > 0) {
    icon = <Users className="w-5 h-5" />;
    title = `${unqualifiedLeads} new ${unqualifiedLeads === 1 ? 'lead' : 'leads'} need qualifying`;
    description = 'Fresh leads are in the pipeline — review them and start outreach.';
    buttonLabel = 'View Prospects';
    buttonHref = '/prospects';
    accentClass = 'text-green-400';
    buttonClass =
      'bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30';
  } else {
    icon = <Rocket className="w-5 h-5" />;
    title = 'Your pipeline is clear';
    description = 'No pending actions today. A great time to launch a new campaign.';
    buttonLabel = 'Launch a Campaign';
    buttonHref = '/campaigns';
    accentClass = 'text-purple-400';
    buttonClass =
      'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border border-purple-500/30';
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 rounded-xl border border-white/10"
    >
      <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-3">
        Your next best action
      </p>
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-xl bg-white/5 ${accentClass} flex-shrink-0`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-base font-semibold ${accentClass} leading-snug`}>{title}</p>
          <p className="text-sm text-white/50 mt-1 leading-relaxed">{description}</p>
        </div>
        <button
          onClick={() => navigate(buttonHref)}
          className={`flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors self-center ${buttonClass}`}
        >
          {buttonLabel}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
}

// ============================================================================
// Activity Feed Item
// ============================================================================

type ActivityKind = 'approval' | 'signal' | 'lead';

interface ActivityItem {
  id: string;
  kind: ActivityKind;
  label: string;
  subLabel?: string;
  timestamp: string;
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const navigate = useNavigate();

  const iconMap: Record<ActivityKind, React.ReactNode> = {
    approval: <Bell className="w-3.5 h-3.5 text-amber-400" />,
    signal: <Radio className="w-3.5 h-3.5 text-yellow-400" />,
    lead: <Users className="w-3.5 h-3.5 text-green-400" />,
  };

  const dotMap: Record<ActivityKind, string> = {
    approval: 'bg-amber-400',
    signal: 'bg-yellow-400',
    lead: 'bg-green-400',
  };

  const handleClick = () => {
    if (item.kind === 'signal') {
      const signalId = item.id.startsWith('signal-') ? item.id.slice('signal-'.length) : item.id;
      navigate(`/insights?id=${signalId}`);
    }
  };

  const isClickable = item.kind === 'signal';

  return (
    <div
      className={`flex items-center gap-3 py-2.5 border-b border-white/5 last:border-0 ${isClickable ? 'cursor-pointer hover:bg-white/5 rounded-lg px-1 -mx-1 transition-colors' : ''}`}
      onClick={isClickable ? handleClick : undefined}
    >
      <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dotMap[item.kind]}`} />
      <div className="flex-shrink-0">{iconMap[item.kind]}</div>
      <div className="flex-1 min-w-0">
        <span className="text-sm text-white/70 leading-tight">{item.label}</span>
        {item.subLabel && (
          <span className="text-xs text-white/30 ml-1.5">{item.subLabel}</span>
        )}
      </div>
      <span className="text-xs text-white/30 flex-shrink-0">{timeAgo(item.timestamp)}</span>
    </div>
  );
}

// ============================================================================
// Empty State
// ============================================================================

function EmptyState() {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-10 rounded-xl border border-white/10 flex flex-col items-center text-center"
    >
      <div className="w-14 h-14 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-4">
        <Zap className="w-7 h-7 text-purple-400" />
      </div>
      <h2 className="text-lg font-semibold text-white">Your GTM engine is ready</h2>
      <p className="text-sm text-white/50 mt-2 max-w-sm leading-relaxed">
        Launch your first campaign to get started. The platform will surface signals, qualify
        leads, and queue outreach for your approval automatically.
      </p>
      <button
        onClick={() => navigate('/campaigns')}
        className="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-xl bg-purple-500/20 text-purple-400 text-sm font-medium hover:bg-purple-500/30 border border-purple-500/30 transition-colors"
      >
        <Rocket className="w-4 h-4" />
        Launch Campaign
      </button>
    </motion.div>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export function TodayPage() {
  const { company } = useCompany();
  const companyId = useCompanyId();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [urgentSignals, setUrgentSignals] = useState(0);
  const [unqualifiedLeads, setUnqualifiedLeads] = useState(0);
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [insightsSummary, setInsightsSummary] = useState<InsightsSummary | null>(null);
  const [activityItems, setActivityItems] = useState<ActivityItem[]>([]);

  useEffect(() => {
    if (!companyId) {
      setLoading(false);
      return;
    }

    setLoading(true);

    Promise.all([
      apiClient
        .get<{ pending: number }>(`/companies/${companyId}/approvals/count`)
        .catch(() => ({ pending: 0 })),
      apiClient
        .get<SignalEvent[]>(`/companies/${companyId}/signals`)
        .catch(() => [] as SignalEvent[]),
      apiClient
        .get<{ leads: Array<{ id: string; status: string | null; lead_company_name: string; contact_name: string | null; created_at: string }> }>(`/companies/${companyId}/leads`)
        .then((r) => r.leads.map((l) => ({
          id: l.id,
          status: l.status ?? 'new',
          name: l.contact_name || l.lead_company_name,
          company_name: l.lead_company_name,
          created_at: l.created_at,
        })))
        .catch(() => [] as Lead[]),
      apiClient
        .get<InsightsSummary>(`/companies/${companyId}/insights/summary`)
        .catch(() => null),
    ]).then(([approvals, fetchedSignals, leads, summary]) => {
      const pending = approvals.pending ?? 0;
      const urgent = fetchedSignals.filter(
        (s) => !s.is_actioned && (s.urgency === 'immediate' || s.urgency === 'this_week')
      );
      const newLeads = leads.filter((l) => l.status === 'new');

      setPendingApprovals(pending);
      setUrgentSignals(urgent.length);
      setUnqualifiedLeads(newLeads.length);
      setSignals(fetchedSignals);
      setInsightsSummary(summary);

      // Build a unified activity feed capped at 8 items, sorted newest first.
      const items: ActivityItem[] = [];

      fetchedSignals
        .slice(0, 4)
        .forEach((s) =>
          items.push({
            id: `signal-${s.id}`,
            kind: 'signal',
            label: s.headline,
            subLabel: s.urgency === 'immediate' ? 'Urgent' : undefined,
            timestamp: s.created_at,
          })
        );

      leads
        .filter((l) => l.status === 'new')
        .slice(0, 4)
        .forEach((l) =>
          items.push({
            id: `lead-${l.id}`,
            kind: 'lead',
            label: `New lead: ${l.name}${l.company_name ? ` · ${l.company_name}` : ''}`,
            timestamp: l.created_at ?? new Date().toISOString(),
          })
        );

      items.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setActivityItems(items.slice(0, 8));
    }).finally(() => setLoading(false));
  }, [companyId]);

  // ---- No company selected ----
  if (!companyId) {
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
            <h2 className="text-lg font-semibold text-white">Welcome to GTM Advisor</h2>
            <p className="text-sm text-white/50 mt-2 leading-relaxed">
              Start by running an AI analysis of your company. Our 6-agent team will map
              your market, identify competitors, profile your ideal customers, and surface
              real leads — then you manage the entire GTM process from here.
            </p>
            <div className="mt-6 w-full space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/20">
                Your value chain
              </p>
              {[
                { step: '1', label: 'Discover', desc: 'Market signals & competitor moves' },
                { step: '2', label: 'Target', desc: 'Qualified leads pipeline' },
                { step: '3', label: 'Engage', desc: 'Campaigns & personalised outreach' },
                { step: '4', label: 'Measure', desc: 'Revenue attribution & ROI' },
              ].map(({ step, label, desc }) => (
                <div key={step} className="flex items-center gap-3 text-left">
                  <span className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[10px] font-bold text-white/40 flex-shrink-0">
                    {step}
                  </span>
                  <div>
                    <span className="text-sm font-medium text-white/70">{label}</span>
                    <span className="text-xs text-white/30 ml-2">{desc}</span>
                  </div>
                </div>
              ))}
            </div>
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

  const allZero = pendingApprovals === 0 && urgentSignals === 0 && unqualifiedLeads === 0;
  const sevenDaysAgo  = Date.now() - 7  * 24 * 60 * 60 * 1000;
  const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const hasBriefing =
    signals.some(
      (s) => !s.is_actioned && s.urgency !== 'monitor' &&
             new Date(s.created_at).getTime() >= sevenDaysAgo
    ) ||
    (insightsSummary?.recent_trends ?? []).some(
      (i) => new Date(i.created_at).getTime() >= thirtyDaysAgo &&
             (!i.expires_at || new Date(i.expires_at).getTime() > Date.now())
    ) ||
    (insightsSummary?.top_opportunities ?? []).some(
      (i) => new Date(i.created_at).getTime() >= thirtyDaysAgo &&
             (!i.expires_at || new Date(i.expires_at).getTime() > Date.now())
    );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <h1 className="text-lg font-semibold text-white">
          {getGreeting()}{company?.name ? `, ${company.name}` : ''}
        </h1>
        <p className="text-xs text-white/40 mt-0.5">
          Here's what's happening in your market today
        </p>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {allZero && activityItems.length === 0 && !hasBriefing ? (
          <EmptyState />
        ) : (
          <>
            {/* Intelligence Briefing — market signals + insights with "what it means" */}
            {hasBriefing && (
              <IntelligenceBriefing signals={signals} insights={insightsSummary} />
            )}

            {/* 3-column action grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <ActionCard
                label="Needs Attention"
                count={pendingApprovals}
                subLabel="pending approvals"
                icon={<Bell className="w-5 h-5" />}
                accentClass={pendingApprovals > 0 ? 'text-amber-400' : 'text-white/30'}
                borderClass={pendingApprovals > 0 ? 'border-amber-500/30' : 'border-white/10'}
                href="/approvals"
              />
              <ActionCard
                label="Today's Signals"
                count={urgentSignals}
                subLabel="urgent market signals"
                icon={<Radio className="w-5 h-5" />}
                accentClass={urgentSignals > 0 ? 'text-yellow-400' : 'text-white/30'}
                borderClass={urgentSignals > 0 ? 'border-yellow-500/30' : 'border-white/10'}
                href="/insights"
              />
              <ActionCard
                label="Pipeline Updates"
                count={unqualifiedLeads}
                subLabel="new unqualified leads"
                icon={<TrendingUp className="w-5 h-5" />}
                accentClass={unqualifiedLeads > 0 ? 'text-green-400' : 'text-white/30'}
                borderClass={unqualifiedLeads > 0 ? 'border-green-500/30' : 'border-white/10'}
                href="/prospects"
              />
            </div>

            {/* Next best action */}
            <NextBestAction
              pendingApprovals={pendingApprovals}
              urgentSignals={urgentSignals}
              unqualifiedLeads={unqualifiedLeads}
            />

            {/* Recent activity feed */}
            {activityItems.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-card p-5 rounded-xl border border-white/10"
              >
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-white">Recent Activity</h2>
                  <button
                    onClick={() => navigate('/insights')}
                    className="text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
                  >
                    View all
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
                <div>
                  {activityItems.map((item) => (
                    <ActivityRow key={item.id} item={item} />
                  ))}
                </div>
              </motion.div>
            )}

            {/* All clear */}
            {allZero && activityItems.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-card p-5 rounded-xl border border-white/10 flex items-center gap-4"
              >
                <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">All caught up!</p>
                  <p className="text-xs text-white/40 mt-0.5">
                    No pending approvals or urgent signals.{' '}
                    <button
                      onClick={() => navigate('/campaigns')}
                      className="text-purple-400 hover:text-purple-300 transition-colors"
                    >
                      Launch a campaign
                    </button>{' '}
                    to keep momentum going.
                  </p>
                </div>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
