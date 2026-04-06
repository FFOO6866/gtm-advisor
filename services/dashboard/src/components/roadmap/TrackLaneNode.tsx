/**
 * TrackLaneNode — swim lane for a strategy track on the Gantt chart.
 * Larger, more visible labels with track color coding.
 */
import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';

const TRACK_STYLES = [
  { bg: 'bg-blue-500/10', border: 'border-blue-500/15', text: 'text-blue-300', badge: 'bg-blue-500/20 text-blue-400' },
  { bg: 'bg-purple-500/10', border: 'border-purple-500/15', text: 'text-purple-300', badge: 'bg-purple-500/20 text-purple-400' },
  { bg: 'bg-amber-500/10', border: 'border-amber-500/15', text: 'text-amber-300', badge: 'bg-amber-500/20 text-amber-400' },
  { bg: 'bg-emerald-500/10', border: 'border-emerald-500/15', text: 'text-emerald-300', badge: 'bg-emerald-500/20 text-emerald-400' },
  { bg: 'bg-rose-500/10', border: 'border-rose-500/15', text: 'text-rose-300', badge: 'bg-rose-500/20 text-rose-400' },
  { bg: 'bg-cyan-500/10', border: 'border-cyan-500/15', text: 'text-cyan-300', badge: 'bg-cyan-500/20 text-cyan-400' },
];

export interface TrackLaneData {
  name: string;
  campaignCount: number;
  activeCount: number;
  completedCount: number;
  height: number;
  width: number;
}

function TrackLaneNodeComponent({ data }: NodeProps & { data: TrackLaneData }) {
  const nameHash = data.name.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const style = TRACK_STYLES[nameHash % TRACK_STYLES.length];

  return (
    <div style={{ width: data.width, height: data.height }} className="relative">
      {/* Full-width band background */}
      <div className={`absolute inset-0 rounded-xl border ${style.border} ${style.bg}`} />

      {/* Track label (left column) */}
      <div className="absolute left-0 top-0 w-[220px] h-full flex items-start pt-2.5 px-3 z-10">
        <div className="flex items-center gap-2.5">
          {/* Color badge */}
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${style.badge}`}>
            {data.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className={`text-xs font-semibold leading-tight ${style.text}`}>
              {data.name}
            </p>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[10px] text-white/30">
                {data.campaignCount} task{data.campaignCount !== 1 ? 's' : ''}
              </span>
              {data.activeCount > 0 && (
                <span className="text-[10px] text-blue-400 flex items-center gap-0.5">
                  <span className="w-1 h-1 rounded-full bg-blue-400 animate-pulse" />
                  {data.activeCount}
                </span>
              )}
              {data.completedCount > 0 && (
                <span className="text-[10px] text-emerald-400">
                  {data.completedCount} done
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export const TrackLaneNode = memo(TrackLaneNodeComponent);
