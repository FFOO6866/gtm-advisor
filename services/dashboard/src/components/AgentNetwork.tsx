/**
 * AgentNetwork — full-SVG orbital visualization.
 *
 * All geometry lives in a single SVG coordinate space so connection lines
 * always terminate flush with node boundaries. No HTML/SVG split.
 *
 * Layout: GTM Strategist at centre; 6 specialists on a perfect hexagonal
 * orbit, evenly spaced at 60° starting from 12 o'clock.
 */

import { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AGENTS, AgentActivity } from '../types';

interface AgentNetworkProps {
  activities: AgentActivity[];
  activeConnections: [string, string][];
  isAnalyzing: boolean;
  onAgentClick?: (agentId: string) => void;
}

// ─── Geometry constants ────────────────────────────────────────────────────
const VW = 400;
const VH = 360;
const CX = 200;
const CY = 180;
const ORBIT_R = 112;   // orbit ring radius
const CENTER_R = 32;   // strategist node radius
const NODE_R = 22;     // specialist node radius
const LABEL_GAP = 13;  // gap from node edge to label baseline

// Specialists in clockwise order from 12 o'clock (must match AGENTS order)
const SPECIALIST_IDS = AGENTS.slice(1).map(a => a.id);

// ─── Geometry helpers ──────────────────────────────────────────────────────
function nodeCenter(id: string): { x: number; y: number } {
  if (id === 'gtm-strategist') return { x: CX, y: CY };
  const i = SPECIALIST_IDS.indexOf(id);
  if (i < 0) return { x: CX, y: CY };
  const rad = (i * 60 - 90) * (Math.PI / 180);
  return { x: CX + ORBIT_R * Math.cos(rad), y: CY + ORBIT_R * Math.sin(rad) };
}

interface Endpoints { x1: number; y1: number; x2: number; y2: number }

function connEndpoints(fromId: string, toId: string): Endpoints | null {
  const a = nodeCenter(fromId);
  const b = nodeCenter(toId);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const d = Math.hypot(dx, dy);
  if (d === 0) return null;
  const nx = dx / d;
  const ny = dy / d;
  const r1 = fromId === 'gtm-strategist' ? CENTER_R : NODE_R;
  const r2 = toId   === 'gtm-strategist' ? CENTER_R : NODE_R;
  return { x1: a.x + nx * r1, y1: a.y + ny * r1, x2: b.x - nx * r2, y2: b.y - ny * r2 };
}

// Pre-compute static spines once at module level — they never change
const SPINES: { id: string; pts: Endpoints }[] = SPECIALIST_IDS
  .map(id => ({ id, pts: connEndpoints('gtm-strategist', id)! }))
  .filter(s => s.pts !== null);

// ─── Appearance ────────────────────────────────────────────────────────────
const STATUS_DOT: Record<string, string> = {
  idle:     '#374151',
  thinking: '#F59E0B',
  active:   '#10B981',
  complete: '#10B981',
};
const STATUS_LABEL: Record<string, string> = {
  thinking: 'Working…',
  active:   'Working…',
  complete: '✓ Done',
};

// ─── Component ─────────────────────────────────────────────────────────────
export function AgentNetwork({ activities, activeConnections, isAnalyzing, onAgentClick }: AgentNetworkProps) {
  const getActivity = (id: string) =>
    activities.find(a => a.agentId === id) ?? { status: 'idle', progress: 0 };

  const activeLines = useMemo(() =>
    activeConnections
      .map(([f, t]) => ({ key: `${f}→${t}`, pts: connEndpoints(f, t), f, t }))
      .filter((l): l is { key: string; pts: Endpoints; f: string; t: string } => l.pts !== null),
    [activeConnections],
  );

  return (
    <div className="relative w-full h-full flex flex-col items-center justify-center">
      {/* Status line */}
      <p className="absolute top-4 left-1/2 -translate-x-1/2 text-xs text-white/40 pointer-events-none whitespace-nowrap">
        {isAnalyzing ? 'Agents collaborating…' : 'Ready to analyse'}
      </p>

      {/* ── Single SVG canvas ── */}
      <svg
        viewBox={`0 0 ${VW} ${VH}`}
        className="w-full h-full"
        style={{ maxHeight: 'calc(100% - 56px)', overflow: 'visible' }}
      >
        <defs>
          {/* Per-agent radial gradient fills */}
          {AGENTS.map(a => (
            <radialGradient key={a.id} id={`rg-${a.id}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%"   stopColor={`rgba(${a.color},0.22)`} />
              <stop offset="100%" stopColor={`rgba(${a.color},0.03)`} />
            </radialGradient>
          ))}

          {/* Glow filter for particles */}
          <filter id="ptglow" x="-120%" y="-120%" width="340%" height="340%">
            <feGaussianBlur stdDeviation="2.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>

          {/* Soft glow for active connection backing */}
          <filter id="lnglow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="1.8" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* ── Orbit ring ── */}
        <circle
          cx={CX} cy={CY} r={ORBIT_R}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="1"
          strokeDasharray="3 6"
        />

        {/* ── Static spine connections ── */}
        {SPINES.map(({ id, pts }) => (
          <line
            key={`sp-${id}`}
            x1={pts.x1} y1={pts.y1} x2={pts.x2} y2={pts.y2}
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="1"
            strokeDasharray="3 5"
          />
        ))}

        {/* ── Active connections ── */}
        <AnimatePresence>
          {activeLines.map(({ key, pts }) => (
            <motion.g
              key={key}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {/* Glow backing */}
              <line
                x1={pts.x1} y1={pts.y1} x2={pts.x2} y2={pts.y2}
                stroke="rgba(139,92,246,0.3)"
                strokeWidth="6"
                strokeLinecap="round"
                filter="url(#lnglow)"
              />
              {/* Animated dash */}
              <motion.line
                x1={pts.x1} y1={pts.y1} x2={pts.x2} y2={pts.y2}
                stroke="rgba(167,139,250,0.9)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeDasharray="5 3"
                animate={{ strokeDashoffset: [0, -16] }}
                transition={{ duration: 0.7, repeat: Infinity, ease: 'linear' }}
              />
              {/* Travelling particle */}
              <circle r="2.5" fill="white" filter="url(#ptglow)" opacity="0.85">
                <animateMotion
                  dur="0.9s"
                  repeatCount="indefinite"
                  path={`M${pts.x1},${pts.y1}L${pts.x2},${pts.y2}`}
                />
              </circle>
            </motion.g>
          ))}
        </AnimatePresence>

        {/* ── Agent nodes ── */}
        {AGENTS.map((agent, idx) => {
          const pos = nodeCenter(agent.id);
          const isCenter = agent.id === 'gtm-strategist';
          const r = isCenter ? CENTER_R : NODE_R;
          const act = getActivity(agent.id);
          const working = act.status === 'thinking' || act.status === 'active';
          const done    = act.status === 'complete';
          const dotColor = STATUS_DOT[act.status] ?? STATUS_DOT.idle;
          const subLabel = STATUS_LABEL[act.status];

          const circ      = 2 * Math.PI * r;
          const progPct   = Math.min(act.progress ?? 0, 100);
          const progOffset = circ * (1 - progPct / 100);

          return (
            // Outer <g> handles position only — no animation
            <g key={agent.id} transform={`translate(${pos.x},${pos.y})`}>
              {/*
               * Inner motion.g handles scale/opacity/hover.
               * transformBox + transformOrigin ensure scale is relative
               * to this element's own bounding box centre, not the SVG origin.
               */}
              <motion.g
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: idx * 0.07, type: 'spring', stiffness: 280, damping: 22 }}
                whileHover={{ scale: 1.1 }}
                onClick={() => onAgentClick?.(agent.id)}
                style={{
                  cursor: 'pointer',
                  transformBox: 'fill-box',
                  transformOrigin: 'center',
                } as React.CSSProperties}
              >
                {/* Transparent hit-area so hover works over empty space */}
                <circle r={r + 14} fill="transparent" />

                {/* Pulse ring — animates r directly (no transform-origin issues) */}
                {working && (
                  <motion.circle
                    r={r + 8}
                    fill="none"
                    stroke={`rgba(${agent.color},0.4)`}
                    strokeWidth="1.5"
                    animate={{ r: [r + 4, r + 20], opacity: [0.55, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
                  />
                )}

                {/* Node fill */}
                <circle r={r} fill={`url(#rg-${agent.id})`} />

                {/* Node border */}
                <circle
                  r={r}
                  fill="none"
                  stroke={`rgba(${agent.color},${working || done ? 0.85 : 0.28})`}
                  strokeWidth={isCenter ? 2 : 1.5}
                />

                {/* Progress arc — rotated via svg transform, not CSS */}
                {progPct > 0 && (
                  <g transform="rotate(-90)">
                    <motion.circle
                      r={r}
                      fill="none"
                      stroke={`rgba(${agent.color},0.9)`}
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeDasharray={circ}
                      initial={{ strokeDashoffset: circ }}
                      animate={{ strokeDashoffset: progOffset }}
                      transition={{ duration: 0.6, ease: 'easeOut' }}
                    />
                  </g>
                )}

                {/* Avatar emoji */}
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={isCenter ? 19 : 14}
                  style={{ userSelect: 'none' }}
                >
                  {agent.avatar}
                </text>

                {/* Status dot */}
                <g transform={`translate(${(r * 0.68).toFixed(1)},${(r * 0.68).toFixed(1)})`}>
                  <circle r="5"   fill="#0F172A" />
                  <circle r="3.5" fill={dotColor} />
                  {working && (
                    <motion.circle
                      r={3.5}
                      fill={dotColor}
                      animate={{ r: [3.5, 8], opacity: [0.7, 0] }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'easeOut' }}
                    />
                  )}
                </g>

                {/* Agent name */}
                <text
                  y={r + LABEL_GAP}
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.82)"
                  fontSize={isCenter ? 11 : 9}
                  fontWeight={isCenter ? '600' : '500'}
                  style={{ userSelect: 'none' }}
                >
                  {agent.name}
                </text>

                {/* Sub-label: done or working */}
                {(done || working) && (
                  <motion.text
                    y={r + LABEL_GAP + 11}
                    textAnchor="middle"
                    fill={done ? '#10B981' : 'rgba(245,158,11,0.8)'}
                    fontSize="7.5"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    style={{ userSelect: 'none' }}
                  >
                    {subLabel}
                  </motion.text>
                )}
              </motion.g>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-5 text-[11px] text-white/35 pointer-events-none">
        {([
          { color: '#374151', label: 'Idle' },
          { color: '#F59E0B', label: 'Thinking' },
          { color: '#10B981', label: 'Active' },
        ] as const).map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <svg width="7" height="7" viewBox="0 0 7 7">
              <circle cx="3.5" cy="3.5" r="3" fill={color} />
            </svg>
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
