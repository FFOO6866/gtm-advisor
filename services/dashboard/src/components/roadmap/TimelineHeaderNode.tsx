/**
 * TimelineHeaderNode — the horizontal timeline axis at the top of the Gantt chart.
 * Shows week/month/quarter markers with clear visual ticks.
 */
import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import type { TimelineScale } from './RoadmapCanvas';

export interface TimelineHeaderData {
  labels: string[];
  unitWidth: number;
  totalUnits: number;
  scale: TimelineScale;
}

function TimelineHeaderNodeComponent({ data }: NodeProps & { data: TimelineHeaderData }) {
  const { labels, unitWidth, totalUnits } = data;
  const totalWidth = totalUnits * unitWidth;

  return (
    <div
      style={{ width: totalWidth, height: 48 }}
      className="flex items-end select-none border-b border-white/10"
    >
      {labels.map((label, i) => {
        // Highlight current period
        const isFirst = i === 0;
        return (
          <div
            key={i}
            style={{ width: unitWidth }}
            className="flex-shrink-0 relative"
          >
            {/* Tick mark */}
            <div className={`absolute left-0 bottom-0 w-px h-3 ${isFirst ? 'bg-purple-400' : 'bg-white/15'}`} />

            {/* "Today" dot on first period */}
            {isFirst && (
              <div className="absolute left-0 bottom-3 w-1.5 h-1.5 rounded-full bg-purple-400 -translate-x-[2px]" />
            )}

            {/* Label */}
            <span className={`text-[10px] font-medium pl-2 pb-1.5 block ${
              isFirst ? 'text-purple-300' : 'text-white/35'
            }`}>
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export const TimelineHeaderNode = memo(TimelineHeaderNodeComponent);
