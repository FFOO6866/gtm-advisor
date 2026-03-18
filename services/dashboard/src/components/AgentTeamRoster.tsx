/**
 * AgentTeamRoster — compact horizontal strip showing the strategic bench.
 *
 * Paid-tier alternative to the teaser AgentNetwork orbital animation.
 * Aesthetic team identity component — communicates "you have a strategic team
 * working for you" via agent cards with live status indicators.
 *
 * Each card: avatar + name + status text. Click navigates to relevant page.
 * During analysis: idle cards pulse; active/complete/error keep their own state.
 */

import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AGENTS, AgentActivity } from '../types';

interface AgentTeamRosterProps {
  activities: AgentActivity[];
  isAnalyzing: boolean;
}

/** Map agent IDs to dashboard navigation targets. */
const AGENT_NAV: Record<string, string> = {
  'gtm-strategist': '/',
  'company-enricher': '/insights',
  'market-intelligence': '/insights',
  'competitor-analyst': '/insights',
  'customer-profiler': '/prospects',
  'lead-hunter': '/prospects',
  'campaign-architect': '/campaigns',
};

/** Idle status text per agent — what they do when not actively running. */
const IDLE_STATUS: Record<string, string> = {
  'gtm-strategist': 'Orchestrating',
  'company-enricher': 'Enriching',
  'market-intelligence': 'Scanning',
  'competitor-analyst': 'Monitoring',
  'customer-profiler': 'Profiling',
  'lead-hunter': 'Hunting',
  'campaign-architect': 'Drafting',
};

function getStatusText(agentId: string, activity?: AgentActivity): string {
  if (!activity || activity.status === 'idle') return IDLE_STATUS[agentId] || 'Ready';
  if (activity.status === 'thinking') return 'Analyzing';
  if (activity.status === 'active') return activity.currentTask || 'Executing';
  if (activity.status === 'complete') return 'Complete';
  if (activity.status === 'error') return 'Interrupted';
  return 'Ready';
}

function getStatusColor(status?: AgentActivity['status']): string {
  if (!status || status === 'idle') return 'bg-white/20';
  if (status === 'thinking' || status === 'active') return 'bg-amber-400';
  if (status === 'complete') return 'bg-emerald-400';
  if (status === 'error') return 'bg-red-400';
  return 'bg-white/20';
}

export function AgentTeamRoster({ activities, isAnalyzing }: AgentTeamRosterProps) {
  const navigate = useNavigate();
  const activityMap = useMemo(
    () => new Map(activities.map(a => [a.agentId, a])),
    [activities],
  );

  return (
    <div className="flex-shrink-0" role="group" aria-label="Your Strategic Bench">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/30 mb-2">
        Your Strategic Bench
      </p>
      <div className="flex flex-wrap gap-2">
        {AGENTS.map((agent, i) => {
          const activity = activityMap.get(agent.id);
          const isActive = activity?.status === 'thinking' || activity?.status === 'active';
          const shouldPulse = isActive || (isAnalyzing && !activity);
          const statusText = getStatusText(agent.id, activity);
          const statusColor = getStatusColor(activity?.status);

          return (
            <motion.button
              key={agent.id}
              onClick={() => navigate(AGENT_NAV[agent.id] || '/today')}
              aria-label={`${agent.name} — ${statusText}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.2 }}
              whileHover={{ scale: 1.02, y: -1 }}
              className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/5 border border-white/8 hover:bg-white/8 hover:border-white/15 transition-colors min-w-0 group focus-visible:ring-1 focus-visible:ring-white/30 focus-visible:outline-none"
            >
              {/* Avatar */}
              <span className="text-base flex-shrink-0" aria-hidden="true">{agent.avatar}</span>

              {/* Name + status */}
              <div className="min-w-0 text-left">
                <p className="text-xs font-medium text-white/70 group-hover:text-white/90 truncate transition-colors">
                  {agent.name}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusColor} ${shouldPulse ? 'animate-pulse' : ''}`}
                    aria-hidden="true"
                  />
                  <span className="text-[10px] text-white/40 truncate">
                    {statusText}
                  </span>
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
