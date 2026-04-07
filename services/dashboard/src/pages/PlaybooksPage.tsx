/**
 * PlaybooksPage — Hi Meet AI's GTM methodology library.
 *
 * Methodology mode (Cycle 3): read-only documentation of the playbooks
 * Hi Meet AI's analysis can adapt for your business. No Activate CTAs
 * — activation is part of the advisory-mode setup, not a self-serve
 * surface in v1.
 *
 * The page is gated by FEATURES.playbooks (default: hidden in production).
 * When promoted, it serves as educational content describing the playbook
 * library, not as an interactive activation tool.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Zap, Clock, TrendingUp, Users, CheckCircle, BookOpen } from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';

interface Playbook {
  id: string;
  playbook_type: string;
  name: string;
  description: string;
  best_for: string;
  steps_count: number;
  duration_days: number;
  success_rate_benchmark?: string;
  is_singapore_specific: boolean;
}

const BUILTIN_PLAYBOOKS: Playbook[] = [
  {
    id: 'cold-outreach-blitz',
    playbook_type: 'cold_outreach',
    name: 'Cold Outreach Blitz',
    description: 'High-velocity cold prospecting sequence using multi-channel touchpoints to generate pipeline quickly from net-new accounts.',
    best_for: 'Early-stage pipeline building with limited existing relationships',
    steps_count: 8,
    duration_days: 14,
    success_rate_benchmark: '3–6% reply rate',
    is_singapore_specific: false,
  },
  {
    id: 'warm-up-campaign',
    playbook_type: 'warm_up',
    name: 'Warm Up Campaign',
    description: 'Gradual nurture sequence that builds brand familiarity and trust before a direct sales ask, ideal for longer buying cycles.',
    best_for: 'Mid-market accounts and enterprise prospects with long evaluation cycles',
    steps_count: 6,
    duration_days: 21,
    success_rate_benchmark: '8–12% conversion to meeting',
    is_singapore_specific: false,
  },
  {
    id: 'competitor-displacement',
    playbook_type: 'competitor_displacement',
    name: 'Competitor Displacement',
    description: 'Targeted sequence designed to win over accounts currently using a competitor by highlighting superior differentiation and ROI.',
    best_for: 'Prospects locked into a competitor contract expiring within 90 days',
    steps_count: 7,
    duration_days: 18,
    success_rate_benchmark: '10–15% switch rate',
    is_singapore_specific: false,
  },
  {
    id: 'signal-triggered-outreach',
    playbook_type: 'signal_triggered',
    name: 'Signal-Triggered Outreach',
    description: 'Automated, intent-driven sequences that activate when a buying signal is detected — funding rounds, job postings, or tech stack changes.',
    best_for: 'Accounts showing active buying intent signals in the past 30 days',
    steps_count: 5,
    duration_days: 10,
    success_rate_benchmark: '12–18% reply rate',
    is_singapore_specific: false,
  },
  {
    id: 'psg-grant-opportunity',
    playbook_type: 'psg_grant',
    name: 'PSG Grant Opportunity',
    description: 'Singapore-specific sequence that leads with PSG grant eligibility to reduce cost objections and accelerate purchase decisions for qualifying SMEs.',
    best_for: 'Singapore SMEs eligible for IMDA Productivity Solutions Grant funding',
    steps_count: 6,
    duration_days: 12,
    success_rate_benchmark: '15–22% conversion rate',
    is_singapore_specific: true,
  },
  {
    id: 'market-entry-play',
    playbook_type: 'market_entry',
    name: 'Market Entry Play',
    description: 'Strategic outreach playbook for entering a new vertical or geography, combining education-led content with direct prospecting.',
    best_for: 'Expanding into APAC markets using Singapore as a regional launchpad',
    steps_count: 9,
    duration_days: 30,
    success_rate_benchmark: '5–9% pipeline conversion',
    is_singapore_specific: true,
  },
];

const PLAYBOOK_TYPE_ICONS: Record<string, React.ReactNode> = {
  cold_outreach: <Zap className="w-4 h-4 text-purple-400" />,
  warm_up: <Users className="w-4 h-4 text-cyan-400" />,
  competitor_displacement: <TrendingUp className="w-4 h-4 text-red-400" />,
  signal_triggered: <Zap className="w-4 h-4 text-yellow-400" />,
  psg_grant: <CheckCircle className="w-4 h-4 text-green-400" />,
  market_entry: <TrendingUp className="w-4 h-4 text-purple-400" />,
};

function PlaybookCard({ playbook }: { playbook: Playbook }) {
  const icon = PLAYBOOK_TYPE_ICONS[playbook.playbook_type] ?? <Zap className="w-4 h-4 text-purple-400" />;

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 rounded-xl border border-white/10 flex flex-col gap-3"
    >
      {/* Card header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0">{icon}</span>
          <h3 className="text-sm font-bold text-white leading-snug truncate">{playbook.name}</h3>
        </div>
        {playbook.is_singapore_specific && (
          <span className="flex-shrink-0 flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-500/15 text-yellow-400 text-[10px] font-medium border border-yellow-500/20">
            🇸🇬 SG-Specific
          </span>
        )}
      </div>

      {/* Description */}
      <p className="text-xs text-white/60 leading-relaxed">{playbook.description}</p>

      {/* Best for */}
      <p className="text-xs text-white/50 italic">
        <span className="not-italic text-white/40 font-medium">Best for:</span>{' '}
        {playbook.best_for}
      </p>

      {/* Stats row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-xs text-white/60">
          <CheckCircle className="w-3 h-3 text-purple-400" />
          {playbook.steps_count} steps
        </span>
        <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-xs text-white/60">
          <Clock className="w-3 h-3 text-cyan-400" />
          {playbook.duration_days} days
        </span>
      </div>

      {/* Success benchmark */}
      {playbook.success_rate_benchmark && (
        <p className="text-xs text-green-400">
          Benchmark: {playbook.success_rate_benchmark}
        </p>
      )}

      {/* Methodology footer — read-only, no activation in v1 */}
      <div className="mt-auto pt-2 border-t border-white/5">
        <p className="text-[10px] text-white/30 italic">
          Available through guided onboarding.
        </p>
      </div>
    </motion.div>
  );
}

export function PlaybooksPage() {
  const companyId = useCompanyId() ?? '';
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) {
      setPlaybooks(BUILTIN_PLAYBOOKS);
      setLoading(false);
      return;
    }
    apiClient.get<Playbook[]>(`/companies/${companyId}/playbooks`)
      .then(data => {
        setPlaybooks(data && data.length > 0 ? data : BUILTIN_PLAYBOOKS);
        setLoading(false);
      })
      .catch(() => {
        // Fall back to built-in playbooks on error
        setPlaybooks(BUILTIN_PLAYBOOKS);
        setError(null);
        setLoading(false);
      });
  }, [companyId]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-purple-400" />
              GTM Methodology
            </h1>
            <p className="text-xs text-white/40">
              The playbooks Hi Meet AI's analysis can adapt for your business
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/30">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            <span>{playbooks.length} playbooks in library</span>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-16">
            <TrendingUp className="w-12 h-12 text-white/10 mx-auto mb-3" />
            <p className="text-white/50">Failed to load playbooks</p>
            <p className="text-white/30 text-sm mt-1">{error}</p>
          </div>
        ) : playbooks.length === 0 ? (
          <div className="text-center py-16">
            <TrendingUp className="w-12 h-12 text-white/10 mx-auto mb-3" />
            <p className="text-white/50">No playbooks available</p>
            <p className="text-white/30 text-sm mt-1">Playbooks will appear here once your company profile is set up.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {playbooks.map((playbook, index) => (
              <motion.div
                key={playbook.id}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <PlaybookCard playbook={playbook} />
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
