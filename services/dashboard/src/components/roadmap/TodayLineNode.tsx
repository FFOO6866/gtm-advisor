/**
 * TodayLineNode — a vertical "today" marker line on the Gantt chart.
 */
import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';

export interface TodayLineData {
  height: number;
  label: string;
}

function TodayLineNodeComponent({ data }: NodeProps & { data: TodayLineData }) {
  return (
    <div style={{ width: 2, height: data.height }} className="relative">
      {/* The line */}
      <div className="absolute inset-0 bg-purple-400/60" />
      {/* "Today" label at top */}
      <div className="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-[9px] font-semibold text-purple-300 bg-purple-500/20 px-1.5 py-0.5 rounded">
          {data.label}
        </span>
      </div>
    </div>
  );
}

export const TodayLineNode = memo(TodayLineNodeComponent);
