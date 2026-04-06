/**
 * InsightNode — a market insight on the GTM Roadmap canvas.
 * Represents signals, competitor gaps, persona insights that
 * informed the AI strategist's campaign recommendations.
 * All content comes from agent analysis — never hardcoded.
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { TrendingUp, Users, Target, AlertTriangle, Lightbulb } from 'lucide-react';

const INSIGHT_ICONS: Record<string, typeof TrendingUp> = {
  market_trend: TrendingUp,
  persona: Users,
  competitor_gap: Target,
  signal: AlertTriangle,
  opportunity: Lightbulb,
};

export interface InsightNodeData {
  type: string;         // market_trend, persona, competitor_gap, signal
  title: string;        // Agent-generated insight title
  detail?: string;      // Short description
  source?: string;      // Which agent/data source produced this
  confidence?: number;
  feedsCount?: number;  // How many campaigns this insight feeds
}

function InsightNodeComponent({ data }: NodeProps & { data: InsightNodeData }) {
  const Icon = INSIGHT_ICONS[data.type] || Lightbulb;

  return (
    <>
      <div className="w-[220px] rounded-xl border border-white/10 bg-surface/60 backdrop-blur-sm p-3">
        <div className="flex items-start gap-2">
          <div className="p-1.5 rounded-lg bg-yellow-500/10">
            <Icon className="w-3.5 h-3.5 text-yellow-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white/80 leading-tight">{data.title}</p>
            {data.detail && (
              <p className="text-[10px] text-white/40 mt-1 line-clamp-2">{data.detail}</p>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
          {data.source && (
            <span className="text-[9px] text-white/30">{data.source}</span>
          )}
          {data.feedsCount && data.feedsCount > 0 && (
            <span className="text-[9px] text-yellow-400/60">
              feeds {data.feedsCount} campaign{data.feedsCount > 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-yellow-400/50" />
    </>
  );
}

export const InsightNode = memo(InsightNodeComponent);
