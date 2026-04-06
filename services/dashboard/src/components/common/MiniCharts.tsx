/**
 * MiniCharts — Pure SVG chart components for dashboard KPIs.
 * Zero dependencies beyond React. All colors via props or currentColor.
 */

import type { ReactNode } from 'react';

// ── Sparkline ────────────────────────────────────────────────────────

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}

export function Sparkline({
  data,
  width = 64,
  height = 32,
  color = '#a78bfa',
  className,
}: SparklineProps) {
  if (data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * w;
    const y = pad + h - ((v - min) / range) * h;
    return `${x},${y}`;
  });

  const gradientId = `spark-${data.length}-${data[0]}`;

  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon
        points={`${pad},${height - pad} ${points.join(' ')} ${width - pad},${height - pad}`}
        fill={`url(#${gradientId})`}
      />
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── MiniBarChart ─────────────────────────────────────────────────────

interface MiniBarChartProps {
  data: number[];
  height?: number;
  barColor?: string;
  activeIndex?: number;
  className?: string;
}

export function MiniBarChart({
  data,
  height = 32,
  barColor = 'rgba(255,255,255,0.15)',
  activeIndex,
  className,
}: MiniBarChartProps) {
  if (data.length === 0) return null;
  const max = Math.max(...data, 1);
  const barWidth = 5;
  const gap = 3;
  const width = data.length * barWidth + (data.length - 1) * gap;

  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`}>
      {data.map((v, i) => {
        const barH = Math.max((v / max) * (height - 2), 1);
        const x = i * (barWidth + gap);
        const y = height - barH;
        const isActive = activeIndex != null && i === activeIndex;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barWidth}
            height={barH}
            rx={1.5}
            fill={isActive ? '#a78bfa' : barColor}
          />
        );
      })}
    </svg>
  );
}

// ── DonutRing ────────────────────────────────────────────────────────

interface DonutRingProps {
  value: number; // 0-100
  size?: number;
  strokeWidth?: number;
  color?: string;
  label?: ReactNode;
  className?: string;
}

export function DonutRing({
  value,
  size = 48,
  strokeWidth = 4,
  color = '#10b981',
  label,
  className,
}: DonutRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(value, 100) / 100) * circumference;

  return (
    <div className={`relative inline-flex items-center justify-center ${className ?? ''}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      {label !== undefined ? (
        <span className="absolute text-[10px] font-semibold text-white/70">{label}</span>
      ) : (
        <span className="absolute text-[10px] font-semibold text-white/70">{Math.round(value)}%</span>
      )}
    </div>
  );
}

// ── SegmentedBar ─────────────────────────────────────────────────────

interface Segment {
  value: number;
  color: string;
  label: string;
}

interface SegmentedBarProps {
  segments: Segment[];
  height?: number;
  className?: string;
}

export function SegmentedBar({
  segments,
  height = 8,
  className,
}: SegmentedBarProps) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  if (total === 0) return null;

  return (
    <div className={`flex rounded-full overflow-hidden ${className ?? ''}`} style={{ height }}>
      {segments.map((seg, i) => {
        const pct = (seg.value / total) * 100;
        if (pct === 0) return null;
        return (
          <div
            key={i}
            style={{ width: `${pct}%`, backgroundColor: seg.color }}
            className="transition-all duration-500"
            title={`${seg.label}: ${seg.value}`}
          />
        );
      })}
    </div>
  );
}

// ── RadialGauge ──────────────────────────────────────────────────────

interface RadialGaugeProps {
  value: number;
  max: number;
  benchmark?: number;
  size?: number;
  color?: string;
  className?: string;
}

export function RadialGauge({
  value,
  max,
  benchmark,
  size = 48,
  color = '#a78bfa',
  className,
}: RadialGaugeProps) {
  const strokeWidth = 4;
  const radius = (size - strokeWidth) / 2;
  // Semi-circle (180 degrees)
  const halfCirc = Math.PI * radius;
  const pct = Math.min(value / (max || 1), 1);
  const dashOffset = halfCirc - pct * halfCirc;

  // Benchmark tick position
  const benchPct = benchmark != null ? Math.min(benchmark / (max || 1), 1) : null;

  return (
    <div className={`relative inline-flex items-end justify-center ${className ?? ''}`} style={{ width: size, height: size / 2 + 4 }}>
      <svg width={size} height={size / 2 + strokeWidth} viewBox={`0 0 ${size} ${size / 2 + strokeWidth}`}>
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={halfCirc}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
        />
        {/* Benchmark tick */}
        {benchPct != null && (
          <circle
            cx={size / 2 + radius * Math.cos(Math.PI - benchPct * Math.PI)}
            cy={size / 2 - radius * Math.sin(benchPct * Math.PI)}
            r={2.5}
            fill="rgba(255,255,255,0.4)"
          />
        )}
      </svg>
    </div>
  );
}
