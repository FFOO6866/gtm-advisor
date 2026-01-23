import { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AGENTS, AgentActivity } from '../types';

interface AgentNetworkProps {
  activities: AgentActivity[];
  activeConnections: [string, string][];
  isAnalyzing: boolean;
}

// Position agents in a hexagonal pattern around the center strategist
// Company Enricher is positioned at top center as the first agent in the flow
const AGENT_POSITIONS: Record<string, { x: number; y: number }> = {
  'gtm-strategist': { x: 50, y: 50 },
  'company-enricher': { x: 50, y: 15 },  // Top center - first in A2A flow
  'market-intelligence': { x: 20, y: 30 },
  'competitor-analyst': { x: 80, y: 30 },
  'customer-profiler': { x: 85, y: 60 },
  'lead-hunter': { x: 65, y: 85 },
  'campaign-architect': { x: 20, y: 70 },
};

export function AgentNetwork({ activities, activeConnections, isAnalyzing }: AgentNetworkProps) {
  const getAgentActivity = (agentId: string) => {
    return activities.find(a => a.agentId === agentId) || { status: 'idle', progress: 0 };
  };

  // Calculate connection paths with offset to avoid overlaying nodes
  const connectionPaths = useMemo(() => {
    const nodeRadius = 8; // Radius to stop before nodes (in viewBox units)

    return activeConnections.map(([from, to]) => {
      const fromPos = AGENT_POSITIONS[from];
      const toPos = AGENT_POSITIONS[to];
      if (!fromPos || !toPos) return null;

      const dx = toPos.x - fromPos.x;
      const dy = toPos.y - fromPos.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      // Normalize direction
      const nx = dx / distance;
      const ny = dy / distance;

      // Offset start and end points to stop before node circles
      const startX = fromPos.x + nx * nodeRadius;
      const startY = fromPos.y + ny * nodeRadius;
      const endX = toPos.x - nx * nodeRadius;
      const endY = toPos.y - ny * nodeRadius;

      // Create curved path with larger curve offset
      const midX = (startX + endX) / 2;
      const midY = (startY + endY) / 2;
      // Perpendicular offset for curve - increased for better arcing
      const curveOffset = Math.sqrt(dx * dx + dy * dy) * 0.35;
      const perpX = -ny * curveOffset;
      const perpY = nx * curveOffset;

      return {
        id: `${from}-${to}`,
        d: `M ${startX} ${startY} Q ${midX + perpX} ${midY + perpY} ${endX} ${endY}`,
        from,
        to,
      };
    }).filter(Boolean);
  }, [activeConnections]);

  return (
    <div className="relative w-full h-full flex items-center justify-center p-8">
      {/* Title */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 text-center">
        <h2 className="text-lg font-medium text-white/80">Agent Command Center</h2>
        <p className="text-sm text-white/40 mt-1">
          {isAnalyzing ? 'Agents collaborating...' : 'Ready to analyze'}
        </p>
      </div>

      {/* Network Container */}
      <div className="relative w-full max-w-2xl aspect-square">
        {/* Connection SVG Layer */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Gradient for connections */}
            <linearGradient id="connection-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(139, 92, 246, 0.8)" />
              <stop offset="50%" stopColor="rgba(59, 130, 246, 0.8)" />
              <stop offset="100%" stopColor="rgba(139, 92, 246, 0.8)" />
            </linearGradient>

            {/* Glow filter */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="1" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Static connection lines (subtle) - offset from node centers */}
          {AGENTS.slice(1).map(agent => {
            const strategist = AGENT_POSITIONS['gtm-strategist'];
            const agentPos = AGENT_POSITIONS[agent.id];
            const nodeRadius = 8;

            const dx = agentPos.x - strategist.x;
            const dy = agentPos.y - strategist.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            const nx = dx / distance;
            const ny = dy / distance;

            // Offset to stop before node circles
            const x1 = strategist.x + nx * nodeRadius;
            const y1 = strategist.y + ny * nodeRadius;
            const x2 = agentPos.x - nx * nodeRadius;
            const y2 = agentPos.y - ny * nodeRadius;

            return (
              <line
                key={`static-${agent.id}`}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth="0.5"
                strokeDasharray="2 2"
              />
            );
          })}

          {/* Active connections */}
          <AnimatePresence>
            {connectionPaths.map(path => path && (
              <motion.g key={path.id}>
                {/* Glow layer */}
                <motion.path
                  d={path.d}
                  fill="none"
                  stroke="url(#connection-gradient)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  filter="url(#glow)"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 0.6 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.5 }}
                />
                {/* Main line */}
                <motion.path
                  d={path.d}
                  fill="none"
                  stroke="url(#connection-gradient)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.5 }}
                />
                {/* Animated particle */}
                <motion.circle
                  r="1.5"
                  fill="white"
                  filter="url(#glow)"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0, 1, 1, 0] }}
                  transition={{
                    duration: 1.5,
                    repeat: Infinity,
                    ease: 'linear',
                  }}
                >
                  <animateMotion
                    dur="1.5s"
                    repeatCount="indefinite"
                    path={path.d}
                  />
                </motion.circle>
              </motion.g>
            ))}
          </AnimatePresence>
        </svg>

        {/* Agent Nodes */}
        {AGENTS.map(agent => {
          const pos = AGENT_POSITIONS[agent.id];
          const activity = getAgentActivity(agent.id);
          const isCenter = agent.id === 'gtm-strategist';

          return (
            <motion.div
              key={agent.id}
              className="absolute"
              style={{
                left: `${pos.x}%`,
                top: `${pos.y}%`,
                transform: 'translate(-50%, -50%)',
                '--agent-color': agent.color,
              } as React.CSSProperties}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: AGENTS.indexOf(agent) * 0.1, duration: 0.5 }}
            >
              <AgentNode
                agent={agent}
                activity={activity}
                isCenter={isCenter}
              />
            </motion.div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex gap-6 text-xs text-white/50">
        <div className="flex items-center gap-2">
          <div className="status-indicator idle" />
          <span>Idle</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="status-indicator thinking" />
          <span>Thinking</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="status-indicator active" />
          <span>Active</span>
        </div>
      </div>
    </div>
  );
}

interface AgentNodeProps {
  agent: typeof AGENTS[0];
  activity: { status: string; progress: number };
  isCenter: boolean;
}

function AgentNode({ agent, activity, isCenter }: AgentNodeProps) {
  const isActive = activity.status === 'thinking' || activity.status === 'active';
  const isComplete = activity.status === 'complete';

  return (
    <motion.div
      className={`
        relative flex flex-col items-center gap-2
        ${isCenter ? 'scale-125' : ''}
      `}
      whileHover={{ scale: isCenter ? 1.3 : 1.1 }}
    >
      {/* Outer glow ring (when active) */}
      <AnimatePresence>
        {isActive && (
          <motion.div
            className="absolute inset-0 -m-4 rounded-full"
            style={{
              background: `radial-gradient(circle, rgba(${agent.color}, 0.3) 0%, transparent 70%)`,
            }}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.8, 0.5] }}
            exit={{ scale: 0.8, opacity: 0 }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        )}
      </AnimatePresence>

      {/* Progress ring */}
      <div className="relative">
        <svg
          width={isCenter ? 80 : 64}
          height={isCenter ? 80 : 64}
          className="absolute -inset-2"
        >
          {/* Background ring */}
          <circle
            cx="50%"
            cy="50%"
            r={isCenter ? 36 : 28}
            fill="none"
            stroke="rgba(255, 255, 255, 0.1)"
            strokeWidth="3"
          />
          {/* Progress ring */}
          {activity.progress > 0 && (
            <motion.circle
              cx="50%"
              cy="50%"
              r={isCenter ? 36 : 28}
              fill="none"
              stroke={`rgba(${agent.color}, 0.8)`}
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={isCenter ? 226 : 176}
              initial={{ strokeDashoffset: isCenter ? 226 : 176 }}
              animate={{
                strokeDashoffset: (isCenter ? 226 : 176) * (1 - activity.progress / 100),
              }}
              style={{ transform: 'rotate(-90deg)', transformOrigin: 'center' }}
              transition={{ duration: 0.3 }}
            />
          )}
        </svg>

        {/* Avatar */}
        <motion.div
          className={`
            relative flex items-center justify-center rounded-full
            ${isCenter ? 'w-16 h-16' : 'w-12 h-12'}
            ${isActive ? 'animate-pulse-glow' : ''}
          `}
          style={{
            background: `linear-gradient(135deg, rgba(${agent.color}, 0.2), rgba(${agent.color}, 0.1))`,
            border: `2px solid rgba(${agent.color}, ${isActive || isComplete ? 0.8 : 0.3})`,
            boxShadow: isActive
              ? `0 0 30px rgba(${agent.color}, 0.5), inset 0 0 20px rgba(${agent.color}, 0.2)`
              : `0 0 20px rgba(${agent.color}, 0.2)`,
            '--glow-color': `rgba(${agent.color}, 0.5)`,
          } as React.CSSProperties}
        >
          <span className={`${isCenter ? 'text-2xl' : 'text-xl'}`}>
            {agent.avatar}
          </span>

          {/* Status indicator */}
          <div
            className={`
              absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-surface
              ${activity.status === 'thinking' ? 'bg-amber-500' : ''}
              ${activity.status === 'active' ? 'bg-green-500' : ''}
              ${activity.status === 'complete' ? 'bg-green-500' : ''}
              ${activity.status === 'idle' ? 'bg-gray-500' : ''}
            `}
          >
            {(activity.status === 'thinking' || activity.status === 'active') && (
              <span className="absolute inset-0 rounded-full animate-ping bg-inherit opacity-75" />
            )}
          </div>
        </motion.div>
      </div>

      {/* Name */}
      <div className="text-center">
        <p className={`font-medium text-white ${isCenter ? 'text-sm' : 'text-xs'}`}>
          {agent.name}
        </p>
        {isActive && (
          <motion.div
            className="flex justify-center mt-1"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="thinking-dots">
              <span />
              <span />
              <span />
            </div>
          </motion.div>
        )}
        {isComplete && (
          <motion.p
            className="text-xs text-green-400 mt-0.5"
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
          >
            ✓ Complete
          </motion.p>
        )}
      </div>
    </motion.div>
  );
}
