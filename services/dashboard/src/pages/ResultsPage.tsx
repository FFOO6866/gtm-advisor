/**
 * ResultsPage — ROI attribution, pipeline value, and GTM performance metrics.
 *
 * Data source: GET /api/v1/companies/{id}/attribution/summary?days=30
 * Record outcomes: POST /api/v1/companies/{id}/attribution/events
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  Mail,
  MessageSquare,
  Calendar,
  DollarSign,
  ArrowUpRight,
  Award,
  Share2,
  ChevronDown,
  ChevronUp,
  Check,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';

// ============================================================================
// Types
// ============================================================================

interface AttributionSummary {
  period_days: number;
  emails_sent: number;
  replies: number;
  reply_rate_pct: number;
  meetings_booked: number;
  pipeline_value_sgd: number;
  meeting_to_email_ratio: number;
  breakdown: Record<string, { count: number; pipeline_sgd: number }>;
  why_us_proof: string;
}

type OutcomeEventType =
  | 'meeting_booked'
  | 'meeting_held'
  | 'proposal_sent'
  | 'deal_closed';

interface RecordOutcomePayload {
  lead_id?: string;
  event_type: OutcomeEventType;
  pipeline_value_sgd?: number;
  notes?: string;
}

// ============================================================================
// Constants
// ============================================================================

const ZERO_SUMMARY: AttributionSummary = {
  period_days: 30,
  emails_sent: 0,
  replies: 0,
  reply_rate_pct: 0,
  meetings_booked: 0,
  pipeline_value_sgd: 0,
  meeting_to_email_ratio: 0,
  breakdown: {},
  why_us_proof: '',
};

const EVENT_TYPE_OPTIONS: { value: OutcomeEventType; label: string }[] = [
  { value: 'meeting_booked', label: 'Meeting Booked' },
  { value: 'meeting_held', label: 'Meeting Held' },
  { value: 'proposal_sent', label: 'Proposal Sent' },
  { value: 'deal_closed', label: 'Deal Closed' },
];

// ============================================================================
// Animation variants
// ============================================================================

const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.35, ease: 'easeOut' },
  }),
};

// ============================================================================
// KPI Card
// ============================================================================

interface KpiCardProps {
  index: number;
  label: string;
  value: string | number;
  icon: React.ReactNode;
  accentClass: string;
  badge?: React.ReactNode;
}

function KpiCard({ index, label, value, icon, accentClass, badge }: KpiCardProps) {
  return (
    <motion.div
      custom={index}
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      className="glass-card p-5 rounded-2xl flex flex-col gap-3"
    >
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${accentClass}`}>
        {icon}
      </div>
      <div>
        <p className="text-3xl font-bold text-white leading-none">{value}</p>
        {badge && <div className="mt-1.5">{badge}</div>}
        <p className="text-sm text-white/50 mt-2">{label}</p>
      </div>
    </motion.div>
  );
}

// ============================================================================
// Funnel Bar
// ============================================================================

interface FunnelBarProps {
  label: string;
  count: number;
  widthPct: number;
  colorClass: string;
  index: number;
}

function FunnelBar({ label, count, widthPct, colorClass, index }: FunnelBarProps) {
  return (
    <motion.div
      custom={index}
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      className="flex items-center gap-4"
    >
      <span className="w-24 text-xs text-white/50 text-right flex-shrink-0">{label}</span>
      <div className="flex-1 h-9 bg-white/5 rounded-lg overflow-hidden relative">
        <motion.div
          className={`h-full rounded-lg flex items-center px-3 ${colorClass}`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(widthPct, 0)}%` }}
          transition={{ delay: index * 0.1 + 0.2, duration: 0.5, ease: 'easeOut' }}
        >
          <span className="text-xs font-semibold text-white whitespace-nowrap">{count}</span>
        </motion.div>
      </div>
      <span className="w-12 text-xs text-white/30 text-right flex-shrink-0">
        {widthPct > 0 ? `${Math.round(widthPct)}%` : '—'}
      </span>
    </motion.div>
  );
}

// ============================================================================
// Record Outcome Form
// ============================================================================

interface RecordOutcomeFormProps {
  companyId: string;
  onSuccess: () => void;
}

function RecordOutcomeForm({ companyId, onSuccess }: RecordOutcomeFormProps) {
  const [leadId, setLeadId] = useState('');
  const [eventType, setEventType] = useState<OutcomeEventType>('meeting_booked');
  const [pipelineValue, setPipelineValue] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    const payload: RecordOutcomePayload = {
      event_type: eventType,
    };
    if (leadId.trim()) payload.lead_id = leadId.trim();
    if (pipelineValue.trim()) {
      const val = parseFloat(pipelineValue);
      if (!isNaN(val)) payload.pipeline_value_sgd = val;
    }
    if (notes.trim()) payload.notes = notes.trim();

    try {
      await apiClient.post(`/companies/${companyId}/attribution/events`, payload);
      setLeadId('');
      setEventType('meeting_booked');
      setPipelineValue('');
      setNotes('');
      onSuccess();
    } catch {
      setError('Failed to record outcome. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 pt-4 border-t border-white/10">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-white/50 font-medium">Lead (optional)</label>
          <input
            type="text"
            placeholder="Lead ID or search…"
            value={leadId}
            onChange={e => setLeadId(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-white/50 font-medium">Event Type</label>
          <select
            value={eventType}
            onChange={e => setEventType(e.target.value as OutcomeEventType)}
            className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/50"
          >
            {EVENT_TYPE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} className="bg-gray-900">
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-white/50 font-medium">Pipeline Value (SGD, optional)</label>
          <input
            type="number"
            min="0"
            step="100"
            placeholder="e.g. 10000"
            value={pipelineValue}
            onChange={e => setPipelineValue(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-white/50 font-medium">Notes (optional)</label>
          <input
            type="text"
            placeholder="e.g. Meeting with John from Acme"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <motion.button
        type="submit"
        disabled={submitting}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500/20 text-cyan-300 text-sm font-medium hover:bg-cyan-500/30 transition-colors border border-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <span className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        ) : (
          <Check className="w-4 h-4" />
        )}
        {submitting ? 'Recording…' : 'Record'}
      </motion.button>
    </form>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export function ResultsPage() {
  const companyId = useCompanyId();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<AttributionSummary>(ZERO_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchSummary = useCallback(async () => {
    if (!companyId) {
      setLoading(false);
      return;
    }
    try {
      const data = await apiClient.get<AttributionSummary>(
        `/companies/${companyId}/attribution/summary?days=30`
      );
      setSummary(data ?? ZERO_SUMMARY);
    } catch {
      setSummary(ZERO_SUMMARY);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // ── Derived funnel values ─────────────────────────────────────────────────

  const emailsSent =
    summary.breakdown['email_sent']?.count ?? summary.emails_sent;
  const dealsCount = summary.breakdown['deal_closed']?.count ?? 0;

  const funnelStages = [
    {
      label: 'Emails Sent',
      count: emailsSent,
      colorClass: 'bg-cyan-500/40',
    },
    {
      label: 'Replies',
      count: summary.replies,
      colorClass: 'bg-green-500/40',
    },
    {
      label: 'Meetings',
      count: summary.meetings_booked,
      colorClass: 'bg-purple-500/40',
    },
    {
      label: 'Deals',
      count: dealsCount,
      colorClass: 'bg-emerald-500/40',
    },
  ];

  const toWidthPct = (count: number) =>
    emailsSent > 0 ? Math.round((count / emailsSent) * 100) : 0;

  // ── Clipboard ─────────────────────────────────────────────────────────────

  const handleCopyProof = () => {
    navigator.clipboard.writeText(summary.why_us_proof).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  // ── Loading spinner ───────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Empty state ───────────────────────────────────────────────────────────

  if (summary.emails_sent === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-10 rounded-2xl text-center max-w-md"
        >
          <TrendingUp className="w-14 h-14 text-white/10 mx-auto mb-5" />
          <p className="text-white font-semibold mb-2">No outreach activity yet.</p>
          <p className="text-white/40 text-sm mb-7 leading-relaxed">
            Launch a campaign and start reaching out to see your pipeline here.
          </p>
          <motion.button
            onClick={() => navigate('/campaigns')}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500/20 text-cyan-300 text-sm font-medium hover:bg-cyan-500/30 transition-colors border border-cyan-500/20"
          >
            <ArrowUpRight className="w-4 h-4" />
            Launch Campaign
          </motion.button>
        </motion.div>
      </div>
    );
  }

  // ── Main render ───────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex-shrink-0 px-6 py-5 border-b border-white/10"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
              <Award className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Results</h1>
              <p className="text-xs text-white/40">ROI attribution and growth performance</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
            <Calendar className="w-4 h-4 text-white/30" />
            <span className="text-sm text-white/50">Last 30 days</span>
          </div>
        </div>
      </motion.div>

      <div className="flex-1 p-6 space-y-8">
        {/* KPI Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            index={0}
            label="Emails Sent"
            value={summary.emails_sent.toLocaleString()}
            icon={<Mail className="w-5 h-5 text-cyan-400" />}
            accentClass="bg-cyan-500/20"
          />
          <KpiCard
            index={1}
            label="Replies Received"
            value={summary.replies.toLocaleString()}
            icon={<MessageSquare className="w-5 h-5 text-green-400" />}
            accentClass="bg-green-500/20"
            badge={
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 text-[11px] font-medium border border-green-500/20">
                <ArrowUpRight className="w-3 h-3" />
                {summary.reply_rate_pct.toFixed(1)}% reply rate
              </span>
            }
          />
          <KpiCard
            index={2}
            label="Meetings Booked"
            value={summary.meetings_booked.toLocaleString()}
            icon={<Calendar className="w-5 h-5 text-purple-400" />}
            accentClass="bg-purple-500/20"
            badge={
              summary.emails_sent > 0 ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 text-[11px] font-medium border border-purple-500/20">
                  {summary.meeting_to_email_ratio.toFixed(1)}% of emails
                </span>
              ) : undefined
            }
          />
          <KpiCard
            index={3}
            label="Pipeline Value"
            value={`SGD ${summary.pipeline_value_sgd.toLocaleString()}`}
            icon={<DollarSign className="w-5 h-5 text-yellow-400" />}
            accentClass="bg-yellow-500/20"
          />
        </div>

        {/* Conversion Funnel */}
        <motion.div
          custom={4}
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          className="glass-card p-6 rounded-2xl"
        >
          <div className="flex items-center gap-2 mb-5">
            <TrendingUp className="w-5 h-5 text-white/50" />
            <h2 className="text-sm font-semibold text-white/70 uppercase tracking-wider">
              Conversion Funnel
            </h2>
          </div>
          <div className="space-y-3">
            {funnelStages.map((stage, i) => (
              <FunnelBar
                key={stage.label}
                index={i}
                label={stage.label}
                count={stage.count}
                widthPct={i === 0 ? 100 : toWidthPct(stage.count)}
                colorClass={stage.colorClass}
              />
            ))}
          </div>
        </motion.div>

        {/* Why Us proof card */}
        {summary.why_us_proof && (
          <motion.div
            custom={5}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
            className="glass-card p-6 rounded-2xl border border-green-500/30"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Award className="w-4 h-4 text-green-400" />
                </div>
                <p className="text-sm text-green-300 leading-relaxed">
                  {summary.why_us_proof}
                </p>
              </div>
              <motion.button
                onClick={handleCopyProof}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                title="Copy to clipboard"
                className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-400" />
                ) : (
                  <Share2 className="w-4 h-4 text-white/40" />
                )}
              </motion.button>
            </div>
          </motion.div>
        )}

        {/* Record Outcome section */}
        <motion.div
          custom={6}
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          className="glass-card p-6 rounded-2xl"
        >
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-2 text-sm font-semibold text-white/70 hover:text-white transition-colors w-full text-left"
          >
            {showForm ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
            Record Outcome +
          </button>

          <AnimatePresence>
            {showForm && companyId && (
              <motion.div
                key="form"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <RecordOutcomeForm
                  companyId={companyId}
                  onSuccess={() => {
                    setShowForm(false);
                    fetchSummary();
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
