/**
 * SignalsFeed — Real-time market signal stream.
 *
 * Shows signals detected by the Signal Monitor Agent:
 * competitor news, market trends, regulatory changes, financial signals.
 *
 * Each signal has: urgency badge, relevance score, recommended action,
 * and a "Deploy Playbook" CTA for high-relevance signals.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Radio, Zap, ExternalLink, CheckCircle } from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { signalsApi, SignalEvent } from '../api/signals';
import { useNavigate } from 'react-router-dom';

const SIGNAL_ICONS: Record<string, string> = {
  funding: '💰', acquisition: '🤝', product_launch: '🚀',
  regulation: '⚖️', expansion: '🌏', hiring: '👥', layoff: '📉',
  partnership: '🔗', market_trend: '📈', competitor_news: '🔍', general_news: '📰',
};

const URGENCY_STYLES: Record<string, string> = {
  immediate: 'bg-red-500/20 text-red-400 border-red-500/30',
  this_week: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  this_month: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  monitor: 'bg-white/10 text-white/40 border-white/10',
};

const URGENCY_LABELS: Record<string, string> = {
  immediate: 'Act Now',
  this_week: 'This Week',
  this_month: 'This Month',
  monitor: 'Monitor',
};

function SignalCard({ signal, onAction }: { signal: SignalEvent; onAction: (id: string) => void }) {
  const navigate = useNavigate();
  const relevancePct = Math.round(signal.relevance_score * 100);
  const icon = SIGNAL_ICONS[signal.signal_type] || '📡';

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass-card p-4 rounded-xl border transition-colors ${signal.is_actioned ? 'opacity-50 border-white/5' : 'border-white/10'}`}
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0 mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${URGENCY_STYLES[signal.urgency] || URGENCY_STYLES.monitor}`}>
              {URGENCY_LABELS[signal.urgency]}
            </span>
            <span className="text-xs text-white/30">{signal.source}</span>
            <span className={`ml-auto text-xs font-bold ${relevancePct >= 70 ? 'text-green-400' : relevancePct >= 50 ? 'text-yellow-400' : 'text-white/30'}`}>
              {relevancePct}% relevant
            </span>
          </div>

          <p className="text-sm font-medium text-white leading-snug">{signal.headline}</p>

          {signal.competitors_mentioned.length > 0 && (
            <div className="flex items-center gap-1 mt-1.5">
              <span className="text-[10px] text-white/30">Mentions:</span>
              {signal.competitors_mentioned.map(c => (
                <span key={c} className="px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 text-[10px]">{c}</span>
              ))}
            </div>
          )}

          {signal.recommended_action && (
            <p className="text-xs text-white/50 mt-2 italic">{signal.recommended_action}</p>
          )}

          <div className="flex items-center gap-2 mt-3">
            {!signal.is_actioned && signal.relevance_score >= 0.50 && (
              <button
                onClick={() => navigate(
                  `/campaigns?signal=${encodeURIComponent(signal.id)}&playbook=signal_triggered&headline=${encodeURIComponent(signal.headline)}`
                )}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/20 text-purple-300 text-xs font-medium hover:bg-purple-500/30 transition-colors"
              >
                <Zap className="w-3 h-3" />
                Deploy Playbook
              </button>
            )}
            {signal.source_url && (
              <a href={signal.source_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition-colors">
                <ExternalLink className="w-3 h-3" />
                Source
              </a>
            )}
            {!signal.is_actioned && (
              <button
                onClick={() => onAction(signal.id)}
                className="ml-auto flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition-colors"
              >
                <CheckCircle className="w-3 h-3" />
                Mark actioned
              </button>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function SignalsFeed() {
  const companyId = useCompanyId() ?? '';
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  const load = () => {
    if (!companyId) return;
    signalsApi.list(companyId, filter === 'all' ? undefined : filter)
      .then(data => { setSignals(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { setLoading(true); load(); }, [companyId, filter]);

  const handleAction = async (signalId: string) => {
    await signalsApi.markActioned(companyId, signalId);
    setSignals(prev => prev.map(s => s.id === signalId ? { ...s, is_actioned: true } : s));
  };

  const urgentCount = signals.filter(s => s.urgency === 'immediate' && !s.is_actioned).length;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white flex items-center gap-2">
              <Radio className="w-5 h-5 text-yellow-400" />
              Market Signals
            </h1>
            <p className="text-xs text-white/40">
              {urgentCount > 0 ? (
                <span className="text-red-400">{urgentCount} urgent signals require action</span>
              ) : (
                'Monitored by Signal Monitor Agent · runs hourly'
              )}
            </p>
          </div>
          <div className="flex gap-1">
            {['all', 'immediate', 'this_week'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${filter === f ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'}`}
              >
                {f === 'all' ? 'All' : f === 'immediate' ? '🔴 Urgent' : '🟡 This Week'}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : signals.length === 0 ? (
          <div className="text-center py-16">
            <Radio className="w-12 h-12 text-white/10 mx-auto mb-3" />
            <p className="text-white/50">No signals detected yet</p>
            <p className="text-white/30 text-sm mt-1">The Signal Monitor Agent runs hourly and will populate this feed.</p>
          </div>
        ) : (
          signals.map(signal => (
            <SignalCard key={signal.id} signal={signal} onAction={handleAction} />
          ))
        )}
      </div>
    </div>
  );
}
