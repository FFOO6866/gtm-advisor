/**
 * WhyUsPanel — Embedded "Why GTM Advisor vs ChatGPT" differentiator.
 *
 * Shown in the onboarding flow and accessible from the dashboard.
 * Answers the #1 SME objection: "Can't I just use ChatGPT for this?"
 */

import { motion } from 'framer-motion';
import { Database, Clock, Zap, Shield, TrendingUp, Globe } from 'lucide-react';

const COMPARISONS = [
  {
    icon: Database,
    dimension: 'Data Sources',
    us: 'Live EODHD + NewsAPI + Perplexity + ACRA',
    them: 'Knowledge cutoff — can\'t access data from this week',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
  },
  {
    icon: Zap,
    dimension: 'Execution',
    us: 'Sends emails, updates CRM, manages sequences',
    them: 'Outputs text only — cannot take any action',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
  },
  {
    icon: Clock,
    dimension: 'Always-On',
    us: 'Monitors signals & runs sequences 24/7 while you sleep',
    them: 'Requires you to prompt it every time',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
  },
  {
    icon: TrendingUp,
    dimension: 'ROI Proof',
    us: 'Tracks outreach → reply → meeting → pipeline value',
    them: 'Cannot prove it generated a single dollar of revenue',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
  },
  {
    icon: Shield,
    dimension: 'Compliance',
    us: 'PDPA consent tracking, audit trail, unsubscribe management',
    them: 'No compliance layer, no PDPA awareness',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
  },
  {
    icon: Globe,
    dimension: 'Singapore Context',
    us: 'PSG grant plays, ACRA company data, MAS regulatory signals',
    them: 'Generic global knowledge — no ACRA, no PSG grants',
    color: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
  },
];

interface WhyUsPanelProps {
  compact?: boolean;
}

export function WhyUsPanel({ compact = false }: WhyUsPanelProps) {
  return (
    <div className={`space-y-${compact ? '2' : '3'}`}>
      {!compact && (
        <div className="text-center mb-4">
          <h3 className="text-lg font-semibold text-white">Why GTM Advisor?</h3>
          <p className="text-sm text-white/50 mt-1">Not a chatbot. An always-on AI workforce.</p>
        </div>
      )}
      {COMPARISONS.map(({ icon: Icon, dimension, us, them, color, bg }) => (
        <motion.div
          key={dimension}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="glass-card p-3 rounded-xl"
        >
          <div className="flex items-start gap-3">
            <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center flex-shrink-0`}>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-white/80 mb-1">{dimension}</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-[10px] text-green-400 font-medium mb-0.5">GTM Advisor</p>
                  <p className="text-xs text-white/70">{us}</p>
                </div>
                <div>
                  <p className="text-[10px] text-white/30 font-medium mb-0.5">ChatGPT / Claude</p>
                  <p className="text-xs text-white/40">{them}</p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      ))}
      {!compact && (
        <div className="glass-card p-4 rounded-xl border border-purple-500/20 mt-4">
          <p className="text-sm text-purple-300 font-medium text-center">
            "GTM Advisor doesn't give you advice. It takes action."
          </p>
        </div>
      )}
    </div>
  );
}
