/**
 * Base Agent Workspace Template
 *
 * Provides consistent layout for all agent detail views.
 * Individual agents extend this with their specific tabs and content.
 */

import { motion } from 'framer-motion';
import { Play, Clock, Zap } from 'lucide-react';
import { BackButton, Tabs, Button, Badge } from '../common';
import type { TabItem } from '../common/Tabs';
import type { Agent } from '../../types';

interface AgentWorkspaceProps {
  agent: Agent;
  status: 'active' | 'idle' | 'processing' | 'error';
  lastRun?: Date;
  nextScheduledRun?: Date;
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  onRun: () => void;
  isRunning?: boolean;
  children: React.ReactNode;
  headerExtra?: React.ReactNode;
}

export function AgentWorkspace({
  agent,
  status,
  lastRun,
  nextScheduledRun,
  tabs,
  activeTab,
  onTabChange,
  onRun,
  isRunning,
  children,
  headerExtra,
}: AgentWorkspaceProps) {
  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - new Date(date).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    return 'Just now';
  };

  const statusConfig = {
    active: { color: 'bg-green-500', label: 'Active', pulse: true },
    processing: { color: 'bg-amber-500', label: 'Processing', pulse: true },
    idle: { color: 'bg-gray-500', label: 'Idle', pulse: false },
    error: { color: 'bg-red-500', label: 'Error', pulse: false },
  };

  const currentStatus = statusConfig[status];

  return (
    <div className="min-h-screen bg-surface">
      {/* Background gradient matching the agent color */}
      <div
        className="fixed inset-0 pointer-events-none opacity-30"
        style={{
          background: `radial-gradient(ellipse at top, rgba(${agent.color}, 0.15) 0%, transparent 50%)`,
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-6">
        {/* Header */}
        <motion.header
          className="mb-6"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {/* Back Navigation */}
          <BackButton />

          {/* Agent Info */}
          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center gap-4">
              {/* Agent Avatar */}
              <motion.div
                className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl"
                style={{
                  background: `linear-gradient(135deg, rgba(${agent.color}, 0.2), rgba(${agent.color}, 0.1))`,
                  border: `2px solid rgba(${agent.color}, 0.3)`,
                  boxShadow: `0 0 30px rgba(${agent.color}, 0.2)`,
                }}
                whileHover={{ scale: 1.05 }}
              >
                {agent.avatar}
              </motion.div>

              <div>
                <h1 className="text-2xl font-bold text-white">{agent.name}</h1>
                <p className="text-white/60 text-sm mt-0.5">{agent.description}</p>

                {/* Status Row */}
                <div className="flex items-center gap-4 mt-2">
                  {/* Status Badge */}
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <div className={`w-2 h-2 rounded-full ${currentStatus.color}`} />
                      {currentStatus.pulse && (
                        <div
                          className={`absolute inset-0 rounded-full ${currentStatus.color} animate-ping opacity-75`}
                        />
                      )}
                    </div>
                    <span className="text-sm text-white/70">{currentStatus.label}</span>
                  </div>

                  {/* Last Run */}
                  {lastRun && (
                    <div className="flex items-center gap-1 text-sm text-white/50">
                      <Clock className="w-3 h-3" />
                      <span>Last run: {formatTimeAgo(lastRun)}</span>
                    </div>
                  )}

                  {/* Next Scheduled */}
                  {nextScheduledRun && (
                    <div className="flex items-center gap-1 text-sm text-white/50">
                      <Zap className="w-3 h-3" />
                      <span>Next: {formatTimeAgo(nextScheduledRun)}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              {headerExtra}
              <Button
                variant="primary"
                onClick={onRun}
                isLoading={isRunning}
                leftIcon={<Play className="w-4 h-4" />}
              >
                Run Agent
              </Button>
            </div>
          </div>
        </motion.header>

        {/* Capabilities */}
        <motion.div
          className="flex gap-2 mb-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          {agent.capabilities.map((capability) => (
            <Badge key={capability} variant="purple">
              {capability}
            </Badge>
          ))}
        </motion.div>

        {/* Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Tabs tabs={tabs} activeTab={activeTab} onChange={onTabChange} />
        </motion.div>

        {/* Content */}
        <motion.div
          className="mt-6"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {children}
        </motion.div>
      </div>
    </div>
  );
}
