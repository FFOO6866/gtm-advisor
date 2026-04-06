/**
 * StrategyPage — AI-proposed strategies for user approval.
 *
 * ALL content comes from the backend (Strategy Proposer agent).
 * This page is GENERIC — it works for any company on the platform.
 *
 * States:
 *   1. No company selected → prompt to select
 *   2. No strategies yet → prompt to run analysis
 *   3. Strategies exist → cards grouped by priority (high / medium / low)
 *   4. Some approved → show "Generate Campaign Plan" CTA
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Compass,
  CheckCircle,
  XCircle,
  Pencil,
  Loader2,
  Sparkles,
  Clock,
  Target,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  AlertTriangle,
  Tag,
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCompanyId } from '../context/CompanyContext';
import { strategiesApi, type Strategy, type StrategiesResponse } from '../api/strategies';

// ============================================================================
// Priority config
// ============================================================================

const PRIORITY_CONFIG: Record<string, { label: string; border: string; bg: string; text: string }> = {
  high: { label: 'High Priority', border: 'border-l-red-500', bg: 'bg-red-500/10', text: 'text-red-400' },
  medium: { label: 'Medium Priority', border: 'border-l-amber-500', bg: 'bg-amber-500/10', text: 'text-amber-400' },
  low: { label: 'Low Priority', border: 'border-l-slate-500', bg: 'bg-slate-500/10', text: 'text-slate-400' },
};

const STATUS_COLORS: Record<string, string> = {
  proposed: 'text-blue-400',
  approved: 'text-emerald-400',
  rejected: 'text-red-400',
  in_progress: 'text-amber-400',
  completed: 'text-green-400',
  revised: 'text-purple-400',
};

// ============================================================================
// Strategy Card
// ============================================================================

interface StrategyCardProps {
  strategy: Strategy;
  onApprove: (id: string, notes?: string) => void;
  onReject: (id: string, reason?: string) => void;
  onEdit: (id: string, data: Partial<Strategy>) => void;
  isActioning: boolean;
}

function StrategyCard({ strategy, onApprove, onReject, onEdit, isActioning }: StrategyCardProps) {
  const [expanded, setExpanded] = useState(strategy.status !== 'rejected');
  const [editing, setEditing] = useState(false);
  const [userNotes, setUserNotes] = useState(strategy.user_notes || '');

  const isRejected = strategy.status === 'rejected';
  const isApproved = strategy.status === 'approved' || strategy.status === 'in_progress' || strategy.status === 'completed';
  const priorityCfg = PRIORITY_CONFIG[strategy.priority] || PRIORITY_CONFIG.low;

  const handleSaveNotes = useCallback(() => {
    onEdit(strategy.id, { user_notes: userNotes });
    setEditing(false);
  }, [onEdit, strategy.id, userNotes]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: isRejected ? 0.5 : 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.25 }}
      className={`relative bg-surface/80 backdrop-blur-md border border-white/10 rounded-2xl overflow-hidden border-l-4 ${priorityCfg.border} ${isRejected ? 'opacity-60' : ''}`}
    >
      {/* Approved overlay */}
      {isApproved && (
        <div className="absolute top-3 right-3 z-10">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
        </div>
      )}

      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full text-left px-5 py-4 flex items-start gap-3"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="text-white font-semibold text-sm leading-tight">{strategy.name}</h3>
            <span className={`text-[10px] font-medium uppercase tracking-wider ${STATUS_COLORS[strategy.status] || 'text-white/40'}`}>
              {strategy.status.replace('_', ' ')}
            </span>
          </div>
          <p className="text-white/50 text-xs line-clamp-2">{strategy.description}</p>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-white/30 flex-shrink-0 mt-1" />
        ) : (
          <ChevronDown className="w-4 h-4 text-white/30 flex-shrink-0 mt-1" />
        )}
      </button>

      {/* Expanded body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4">
              {/* Rationale */}
              <div>
                <p className="text-[10px] uppercase tracking-wider text-white/30 mb-1">Rationale</p>
                <p className="text-white/70 text-xs leading-relaxed">{strategy.rationale}</p>
              </div>

              {/* Insight sources */}
              {strategy.insight_sources.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">Insight Sources</p>
                  <div className="flex flex-wrap gap-1.5">
                    {strategy.insight_sources.map((source) => (
                      <span
                        key={source}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/60 text-[10px]"
                      >
                        <Tag className="w-2.5 h-2.5" />
                        {source}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Expected outcome */}
              <div>
                <p className="text-[10px] uppercase tracking-wider text-white/30 mb-1">Expected Outcome</p>
                <p className="text-white/70 text-xs">{strategy.expected_outcome}</p>
              </div>

              {/* Success metrics */}
              {strategy.success_metrics.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">Success Metrics</p>
                  <div className="space-y-1">
                    {strategy.success_metrics.map((m, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <BarChart3 className="w-3 h-3 text-white/30 flex-shrink-0" />
                        <span className="text-white/60">{m.metric}:</span>
                        <span className="text-white/80 font-medium">{m.target}</span>
                        {m.current && (
                          <span className="text-white/40">(current: {m.current})</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Meta row */}
              <div className="flex items-center gap-4 text-[10px] text-white/40 pt-1">
                {strategy.estimated_timeline && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {strategy.estimated_timeline}
                  </span>
                )}
                {strategy.target_segment && (
                  <span className="flex items-center gap-1">
                    <Target className="w-3 h-3" />
                    {strategy.target_segment}
                  </span>
                )}
              </div>

              {/* User notes (edit mode) */}
              {editing && (
                <div className="space-y-2">
                  <textarea
                    value={userNotes}
                    onChange={(e) => setUserNotes(e.target.value)}
                    placeholder="Add your notes or adjustments..."
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white/80 text-xs placeholder-white/20 resize-none focus:outline-none focus:border-white/20"
                    rows={3}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveNotes}
                      disabled={isActioning}
                      className="px-3 py-1.5 rounded-lg bg-indigo-500/20 text-indigo-300 text-xs font-medium hover:bg-indigo-500/30 transition-colors disabled:opacity-50"
                    >
                      Save Notes
                    </button>
                    <button
                      onClick={() => setEditing(false)}
                      className="px-3 py-1.5 rounded-lg bg-white/5 text-white/50 text-xs hover:bg-white/10 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Display saved notes */}
              {!editing && strategy.user_notes && (
                <div className="bg-white/5 rounded-lg px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-white/30 mb-0.5">Your Notes</p>
                  <p className="text-white/60 text-xs">{strategy.user_notes}</p>
                </div>
              )}

              {/* Action buttons */}
              {strategy.status === 'proposed' && (
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => onApprove(strategy.id, userNotes || undefined)}
                    disabled={isActioning}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-500/20 text-emerald-300 text-xs font-medium hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
                  >
                    {isActioning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                    Approve
                  </button>
                  <button
                    onClick={() => setEditing(true)}
                    disabled={isActioning}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/5 text-white/60 text-xs font-medium hover:bg-white/10 transition-colors disabled:opacity-50"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    Edit
                  </button>
                  <button
                    onClick={() => onReject(strategy.id)}
                    disabled={isActioning}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/5 text-white/40 text-xs font-medium hover:bg-red-500/10 hover:text-red-300 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Skip
                  </button>
                </div>
              )}

              {strategy.status === 'revised' && (
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => onApprove(strategy.id, userNotes || undefined)}
                    disabled={isActioning}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-500/20 text-emerald-300 text-xs font-medium hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
                  >
                    {isActioning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                    Approve Revision
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ============================================================================
// StrategyPage
// ============================================================================

export function StrategyPage() {
  const companyId = useCompanyId();
  const navigate = useNavigate();

  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [total, setTotal] = useState(0);
  const [byStatus, setByStatus] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generatingCampaigns, setGeneratingCampaigns] = useState(false);

  // ---- Fetch strategies ----
  const fetchStrategies = useCallback(async () => {
    if (!companyId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data: StrategiesResponse = await strategiesApi.list(companyId);
      setStrategies(data.strategies);
      setTotal(data.total);
      setByStatus(data.by_status);
    } catch (err) {
      console.error('Failed to fetch strategies:', err);
      setError('Unable to load strategies. The backend may not have this endpoint yet.');
      setStrategies([]);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  // ---- Actions ----
  const handleApprove = useCallback(async (strategyId: string, notes?: string) => {
    if (!companyId) return;
    setActioningId(strategyId);
    try {
      const updated = await strategiesApi.approve(companyId, strategyId, notes);
      setStrategies(prev => prev.map(s => s.id === strategyId ? updated : s));
      setByStatus(prev => ({
        ...prev,
        proposed: Math.max(0, (prev.proposed || 0) - 1),
        approved: (prev.approved || 0) + 1,
      }));
    } catch (err) {
      console.error('Failed to approve strategy:', err);
    } finally {
      setActioningId(null);
    }
  }, [companyId]);

  const handleReject = useCallback(async (strategyId: string, reason?: string) => {
    if (!companyId) return;
    setActioningId(strategyId);
    try {
      await strategiesApi.reject(companyId, strategyId, reason);
      setStrategies(prev => prev.map(s => s.id === strategyId ? { ...s, status: 'rejected' as const } : s));
      setByStatus(prev => ({
        ...prev,
        proposed: Math.max(0, (prev.proposed || 0) - 1),
        rejected: (prev.rejected || 0) + 1,
      }));
    } catch (err) {
      console.error('Failed to reject strategy:', err);
    } finally {
      setActioningId(null);
    }
  }, [companyId]);

  const handleEdit = useCallback(async (strategyId: string, data: Partial<Strategy>) => {
    if (!companyId) return;
    setActioningId(strategyId);
    try {
      const updated = await strategiesApi.update(companyId, strategyId, data);
      setStrategies(prev => prev.map(s => s.id === strategyId ? updated : s));
    } catch (err) {
      console.error('Failed to update strategy:', err);
    } finally {
      setActioningId(null);
    }
  }, [companyId]);

  const handleGenerate = useCallback(async () => {
    if (!companyId) return;
    setGenerating(true);
    try {
      await strategiesApi.generate(companyId);
      // Refetch after a short delay to allow backend processing
      setTimeout(() => {
        fetchStrategies();
        setGenerating(false);
      }, 3000);
    } catch (err) {
      console.error('Failed to generate strategies:', err);
      setGenerating(false);
    }
  }, [companyId, fetchStrategies]);

  const handleGenerateCampaigns = useCallback(async () => {
    if (!companyId) return;
    setGeneratingCampaigns(true);
    try {
      await strategiesApi.generateCampaigns(companyId);
      navigate('/campaigns');
    } catch (err) {
      console.error('Failed to generate campaigns:', err);
      setGeneratingCampaigns(false);
    }
  }, [companyId, navigate]);

  // ---- Group strategies by priority ----
  const grouped = {
    high: strategies.filter(s => s.priority === 'high'),
    medium: strategies.filter(s => s.priority === 'medium'),
    low: strategies.filter(s => s.priority === 'low'),
  };

  const approvedCount = strategies.filter(s => s.status === 'approved' || s.status === 'in_progress').length;
  const hasApproved = approvedCount > 0;

  // ---- Render states ----

  // No company
  if (!companyId) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <Compass className="w-12 h-12 text-white/20 mx-auto mb-4" />
          <h2 className="text-white/80 text-lg font-semibold mb-2">Select a Company</h2>
          <p className="text-white/40 text-sm">
            Run an analysis first to generate AI-proposed strategies for your company.
          </p>
        </div>
      </div>
    );
  }

  // Loading
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto mb-3" />
          <p className="text-white/50 text-sm">Loading strategies...</p>
        </div>
      </div>
    );
  }

  // Error
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-10 h-10 text-amber-400/60 mx-auto mb-3" />
          <h2 className="text-white/80 text-sm font-semibold mb-2">Could not load strategies</h2>
          <p className="text-white/40 text-xs mb-4">{error}</p>
          <button
            onClick={fetchStrategies}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/5 text-white/60 text-xs font-medium hover:bg-white/10 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // No strategies
  if (strategies.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <Compass className="w-12 h-12 text-indigo-400/40 mx-auto mb-4" />
          <h2 className="text-white/80 text-lg font-semibold mb-2">Your strategies are being prepared</h2>
          <p className="text-white/40 text-sm mb-6">
            Once your analysis completes, AI-proposed strategies will appear here for your review and approval.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-indigo-500/20 text-indigo-300 text-sm font-medium hover:bg-indigo-500/30 transition-colors disabled:opacity-50"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Generate Strategies
            </button>
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-white/5 text-white/50 text-sm font-medium hover:bg-white/10 transition-colors"
            >
              Run Analysis
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Main view: strategies grouped by priority ----
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
        {/* Page header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-white text-xl font-bold flex items-center gap-2">
              <Compass className="w-5 h-5 text-indigo-400" />
              Strategy
            </h1>
            <p className="text-white/40 text-xs mt-1">
              {total} {total === 1 ? 'strategy' : 'strategies'} proposed
              {approvedCount > 0 && (
                <span className="text-emerald-400 ml-1">
                  &middot; {approvedCount} approved
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchStrategies}
              className="p-2 rounded-lg bg-white/5 text-white/40 hover:text-white/60 hover:bg-white/10 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-500/20 text-indigo-300 text-xs font-medium hover:bg-indigo-500/30 transition-colors disabled:opacity-50"
            >
              {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Regenerate
            </button>
          </div>
        </div>

        {/* Status summary bar */}
        {Object.keys(byStatus).length > 0 && (
          <div className="flex items-center gap-3 flex-wrap">
            {Object.entries(byStatus).map(([status, count]) => (
              <span
                key={status}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/5 text-[10px] font-medium ${STATUS_COLORS[status] || 'text-white/40'}`}
              >
                {status.replace('_', ' ')} ({count})
              </span>
            ))}
          </div>
        )}

        {/* Priority groups */}
        {(['high', 'medium', 'low'] as const).map(priority => {
          const items = grouped[priority];
          if (items.length === 0) return null;
          const cfg = PRIORITY_CONFIG[priority];
          return (
            <motion.section
              key={priority}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="flex items-center gap-2 mb-3">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider ${cfg.bg} ${cfg.text}`}>
                  {cfg.label}
                </span>
                <span className="text-white/20 text-[10px]">{items.length}</span>
              </div>
              <div className="space-y-3">
                {items.map(strategy => (
                  <StrategyCard
                    key={strategy.id}
                    strategy={strategy}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    onEdit={handleEdit}
                    isActioning={actioningId === strategy.id}
                  />
                ))}
              </div>
            </motion.section>
          );
        })}

        {/* Generate Campaign Plan CTA */}
        {hasApproved && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.3 }}
            className="bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 border border-white/10 rounded-2xl p-5"
          >
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-white font-semibold text-sm">
                  {approvedCount} {approvedCount === 1 ? 'strategy' : 'strategies'} approved
                </h3>
                <p className="text-white/40 text-xs mt-0.5">
                  Generate a campaign plan from your approved strategies to start execution.
                </p>
              </div>
              <button
                onClick={handleGenerateCampaigns}
                disabled={generatingCampaigns}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors disabled:opacity-50 flex-shrink-0"
              >
                {generatingCampaigns ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4" />
                )}
                Generate Campaign Plan
              </button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
