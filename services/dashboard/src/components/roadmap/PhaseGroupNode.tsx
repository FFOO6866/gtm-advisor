/**
 * PhaseGroupNode — a phase container on the GTM Roadmap canvas.
 * Groups campaigns by time horizon. All content is agent-generated.
 */
import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { Zap, Clock, TrendingUp, Target } from 'lucide-react';

const PHASE_CONFIG: Record<string, { icon: typeof Zap; color: string; border: string; label: string; timeline: string }> = {
  immediate: { icon: Zap, color: 'text-blue-400', border: 'border-blue-500/20', label: 'Immediate', timeline: 'Week 1-2' },
  short_term: { icon: Clock, color: 'text-purple-400', border: 'border-purple-500/20', label: 'Short Term', timeline: '30-60-90 Days' },
  mid_term: { icon: TrendingUp, color: 'text-amber-400', border: 'border-amber-500/20', label: 'Mid Term', timeline: '3-6 Months' },
  long_term: { icon: Target, color: 'text-emerald-400', border: 'border-emerald-500/20', label: 'Long Term', timeline: '6-12 Months' },
};

export interface PhaseGroupData {
  phase: string;
  campaignCount: number;
  completedCount: number;
  activeCount: number;
}

function PhaseGroupNodeComponent({ data }: NodeProps & { data: PhaseGroupData }) {
  const config = PHASE_CONFIG[data.phase] || PHASE_CONFIG.immediate;
  const Icon = config.icon;

  return (
    <div className={`rounded-2xl border ${config.border} bg-white/[0.02] backdrop-blur-sm min-w-[320px]`}
      style={{ padding: '0' }}
    >
      {/* Phase header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
        <Icon className={`w-4 h-4 ${config.color}`} />
        <div>
          <span className={`text-sm font-semibold ${config.color}`}>{config.label}</span>
          <span className="text-[10px] text-white/30 ml-2">{config.timeline}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {data.completedCount > 0 && (
            <span className="text-[10px] text-emerald-400">
              {data.completedCount}/{data.campaignCount} done
            </span>
          )}
          {data.activeCount > 0 && (
            <span className="text-[10px] text-blue-400">
              {data.activeCount} running
            </span>
          )}
        </div>
      </div>
      {/* Children (campaign nodes) are rendered inside by React Flow via parentId */}
    </div>
  );
}

export const PhaseGroupNode = memo(PhaseGroupNodeComponent);
