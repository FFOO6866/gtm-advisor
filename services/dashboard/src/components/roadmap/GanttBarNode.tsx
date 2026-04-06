/**
 * GanttBarNode — a draggable horizontal bar on the Gantt timeline.
 *
 * Features:
 * - Draggable along X (reschedule) and Y (move between tracks)
 * - Progress bar showing KPI attainment from agent monitor data
 * - Click to select → opens CampaignDetailPanel for editing
 * - Visual status (draft/active/paused/completed)
 * - Strategy track color coding
 *
 * All content from Campaign Strategist + Campaign Monitor agents.
 */
import { memo, useCallback, useState } from 'react';
import { Handle, Position, NodeResizer, type NodeProps } from '@xyflow/react';
import { Pencil, GripHorizontal } from 'lucide-react';
import type { RoadmapCampaign } from '../../api/roadmap';

const STATUS_COLORS: Record<string, { border: string; text: string; dot: string }> = {
  draft: { border: 'border-white/10', text: 'text-white/60', dot: 'bg-white/20' },
  active: { border: 'border-blue-400/30', text: 'text-blue-300', dot: 'bg-blue-400 animate-pulse' },
  paused: { border: 'border-amber-400/30', text: 'text-amber-300', dot: 'bg-amber-400' },
  completed: { border: 'border-emerald-400/30', text: 'text-emerald-300', dot: 'bg-emerald-400' },
};

const TRACK_GRADIENTS: string[] = [
  'from-blue-500/20 to-blue-600/5',
  'from-purple-500/20 to-purple-600/5',
  'from-amber-500/20 to-amber-600/5',
  'from-emerald-500/20 to-emerald-600/5',
  'from-rose-500/20 to-rose-600/5',
];

export interface GanttBarData {
  campaign: RoadmapCampaign;
  width: number;
  height: number;
  isPast?: boolean;  // True if task's time window has passed — greyed out
  onSelect?: (campaignId: string) => void;
}

/**
 * Compute progress % from agent-generated metrics.
 * The Campaign Monitor agent populates campaign.metrics with KPI data.
 */
function computeProgress(campaign: RoadmapCampaign): number {
  if (campaign.status === 'completed') return 100;
  if (campaign.status === 'draft') return 0;

  const metrics = campaign.metrics || {};
  const kpis = (metrics.kpis as string[]) || [];

  // If monitor agent has run, use its data
  const totalImpressions = (metrics.total_impressions as number) || 0;
  const totalClicks = (metrics.total_clicks as number) || 0;

  if (totalImpressions > 0 || totalClicks > 0) {
    // Simple heuristic: progress based on having engagement data
    // Real progress would compare against KPI targets
    const signals = [
      totalImpressions > 0 ? 25 : 0,
      totalClicks > 0 ? 25 : 0,
      kpis.length > 0 ? 15 : 0,
      campaign.status === 'active' ? 20 : 0,
    ];
    return Math.min(signals.reduce((a, b) => a + b, 0), 95);
  }

  // Active but no engagement data yet
  if (campaign.status === 'active') return 15;
  return 0;
}

function GanttBarNodeComponent({ data, selected, width: nodeWidth, height: nodeHeight }: NodeProps & { data: GanttBarData }) {
  const { campaign, width: initialWidth, height: initialHeight, isPast, onSelect } = data;
  // Use React Flow's tracked dimensions (updated during resize), fall back to initial
  const width = nodeWidth ?? initialWidth;
  const height = nodeHeight ?? initialHeight;
  const status = STATUS_COLORS[campaign.status] || STATUS_COLORS.draft;
  const [hovered, setHovered] = useState(false);

  const trackHash = (campaign.strategy_track || '').split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const gradient = TRACK_GRADIENTS[trackHash % TRACK_GRADIENTS.length];

  const progress = computeProgress(campaign);
  const kpis = (campaign.metrics?.kpis as string[]) || [];
  const barW = Math.max(width, 120);  // For conditional content visibility

  const handleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect?.(campaign.id);
  }, [onSelect, campaign.id]);

  return (
    <>
      {/* Horizontal resize handles — stretch bar to change duration */}
      <NodeResizer
        isVisible={selected || hovered}
        minWidth={100}
        minHeight={height}
        maxHeight={height}
        handleStyle={{
          width: 6,
          height: 20,
          borderRadius: 3,
          background: 'rgba(168,85,247,0.4)',
          border: 'none',
        }}
        lineStyle={{ borderColor: 'transparent' }}
      />

      <Handle type="target" position={Position.Left} className="!w-1.5 !h-1.5 !bg-white/20 !border-0" />

      <div
        onClick={handleClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{ width: '100%', height: '100%' }}
        className={`relative rounded-lg border cursor-grab active:cursor-grabbing transition-all group ${
          isPast
            ? 'border-white/5 opacity-40'
            : selected
              ? 'border-purple-400/60 shadow-lg shadow-purple-500/20 ring-1 ring-purple-400/30'
              : `${status.border} hover:border-white/25 hover:shadow-md hover:shadow-white/5`
        }`}
      >
        {/* Background gradient */}
        <div className={`absolute inset-0 bg-gradient-to-r ${gradient} rounded-lg`} />

        {/* Progress fill — shows KPI attainment from Campaign Monitor agent */}
        {progress > 0 && (
          <div
            className="absolute inset-y-0 left-0 rounded-lg bg-white/[0.06] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        )}

        {/* Drag handle (visible on hover) */}
        <div className={`absolute left-1 top-1/2 -translate-y-1/2 transition-opacity ${hovered ? 'opacity-40' : 'opacity-0'}`}>
          <GripHorizontal className="w-3 h-3 text-white" />
        </div>

        {/* Main content */}
        <div className="relative z-10 h-full flex flex-col justify-center px-3 py-1.5"
          style={{ paddingLeft: hovered ? '18px' : '12px' }}
        >
          {/* Row 1: Name + edit icon */}
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${status.dot}`} />
            <p className={`text-xs font-semibold truncate flex-1 ${status.text}`}>
              {campaign.name}
            </p>
            {hovered && (
              <Pencil className="w-3.5 h-3.5 text-white/40 flex-shrink-0" />
            )}
          </div>

          {/* Row 2: Framework rationale */}
          {barW > 180 && campaign.framework_rationale && (
            <p className="text-[9px] text-white/30 truncate mt-0.5 pl-3.5">
              {campaign.framework_rationale}
            </p>
          )}

          {/* Row 3: Progress bar + percentage */}
          {campaign.status !== 'draft' && (
            <div className="flex items-center gap-2 mt-1.5 pl-3">
              <div className="flex-1 h-1 rounded-full bg-white/5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    progress >= 75 ? 'bg-emerald-400/60' :
                    progress >= 40 ? 'bg-blue-400/60' :
                    progress > 0 ? 'bg-amber-400/60' : ''
                  }`}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-[8px] text-white/30 w-6 text-right">{progress}%</span>
            </div>
          )}

          {/* Row 4: KPI summary (wide bars only) */}
          {barW > 250 && kpis.length > 0 && (
            <p className="text-[7px] text-white/20 truncate mt-0.5 pl-3">
              {kpis[0]}
            </p>
          )}
        </div>

        {/* Channels strip (right edge, wide bars only) */}
        {barW > 300 && campaign.channels.length > 0 && (
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex flex-col gap-0.5">
            {campaign.channels.slice(0, 3).map((ch) => (
              <span key={ch} className="text-[7px] px-1 py-0.5 rounded bg-white/5 text-white/20 text-right">
                {ch}
              </span>
            ))}
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Right} className="!w-1.5 !h-1.5 !bg-white/20 !border-0" />
    </>
  );
}

export const GanttBarNode = memo(GanttBarNodeComponent);
