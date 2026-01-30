/**
 * GTM Strategist Workspace
 *
 * Central command for orchestrating GTM strategy across all agents.
 * Connected to real backend API.
 */

import { useState, useCallback } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import {
  Card,
  Badge,
  Button,
  EmptyState,
  SkeletonCard,
  SkeletonList,
  ErrorState,
  useToast,
} from '../components/common';
import { AGENTS } from '../types';
import { useCompanyId } from '../context/CompanyContext';
import { useStrategyDashboard, useMutation, useAgentStatus } from '../hooks/useApi';
import * as api from '../api/workspaces';
import type { StrategyRecommendation, StrategyPhase, AgentActivity } from '../api/workspaces';

export function StrategyWorkspace() {
  const companyId = useCompanyId();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [isRunning, setIsRunning] = useState(false);

  // Fetch strategy dashboard from API
  const { data: dashboard, isLoading, error, refresh } = useStrategyDashboard(companyId);

  const agent = AGENTS.find((a) => a.id === 'gtm-strategist')!;

  // Mutation to run analysis with proper error handling
  const runAnalysisMutation = useMutation(
    () => {
      if (!companyId) return Promise.reject(new Error('No company selected'));
      return api.runStrategyAnalysis(companyId);
    },
    {
      invalidateKeys: ['strategy-dashboard', 'strategy-recommendations'],
      onSuccess: () => {
        refresh();
        setIsRunning(false);
        toast.success('Strategy analysis completed');
      },
      onError: (err) => {
        setIsRunning(false);
        toast.error('Failed to run strategy analysis', err.message);
      },
    }
  );

  // Mutation to update recommendation status
  const updateRecommendationMutation = useMutation(
    ({ id, status }: { id: string; status: 'in_progress' | 'completed' | 'dismissed' }) => {
      if (!companyId) return Promise.reject(new Error('No company selected'));
      return api.updateRecommendationStatus(companyId, id, status);
    },
    {
      invalidateKeys: ['strategy-dashboard', 'strategy-recommendations'],
      onSuccess: () => {
        refresh();
        toast.success('Recommendation updated');
      },
      onError: (err) => {
        toast.error('Failed to update recommendation', err.message);
      },
    }
  );

  const handleRun = useCallback(async () => {
    if (!companyId) {
      toast.error('Please complete onboarding first', 'No company selected');
      return;
    }
    setIsRunning(true);
    await runAnalysisMutation.mutate(undefined);
  }, [companyId, runAnalysisMutation, toast]);

  const phases = dashboard?.phases || [];
  const recommendations = dashboard?.recommendations || [];
  const recentActivity = dashboard?.recent_activity || [];
  const metrics = dashboard?.metrics;
  const lastRunAt = dashboard?.last_run_at ? new Date(dashboard.last_run_at) : undefined;

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'recommendations', label: 'Recommendations', badge: recommendations.length, icon: '💡' },
    { id: 'agents', label: 'Agent Status', icon: '🤖' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  // Loading state
  if (isLoading) {
    return (
      <AgentWorkspace
        agent={agent}
        status="active"
        lastRun={new Date()}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRun={handleRun}
        isRunning={isRunning}
      >
        <div className="space-y-6">
          <SkeletonCard />
          <div className="grid grid-cols-4 gap-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <SkeletonList count={3} />
        </div>
      </AgentWorkspace>
    );
  }

  // Error state
  if (error) {
    return (
      <AgentWorkspace
        agent={agent}
        status="error"
        lastRun={new Date()}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRun={handleRun}
        isRunning={isRunning}
      >
        <ErrorState
          title="Failed to load strategy dashboard"
          message={error.message}
          onRetry={refresh}
        />
      </AgentWorkspace>
    );
  }

  // No company selected
  if (!companyId) {
    return (
      <AgentWorkspace
        agent={agent}
        status="idle"
        lastRun={new Date()}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRun={handleRun}
        isRunning={isRunning}
      >
        <EmptyState
          icon="🏢"
          title="No Company Selected"
          description="Please complete onboarding to start your GTM strategy."
        />
      </AgentWorkspace>
    );
  }

  return (
    <AgentWorkspace
      agent={agent}
      status={isRunning ? 'processing' : 'active'}
      lastRun={lastRunAt}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Strategy Phases */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">GTM Strategy Phases</h3>
            {phases.length > 0 ? (
              <div className="flex items-center justify-between">
                {phases.map((phase, index) => (
                  <PhaseItem
                    key={phase.id}
                    phase={phase}
                    isLast={index === phases.length - 1}
                  />
                ))}
              </div>
            ) : (
              <p className="text-white/50 text-center py-4">
                Run the strategist to begin your GTM journey
              </p>
            )}
          </Card>

          {/* Key Metrics */}
          {metrics && (
            <div className="grid grid-cols-4 gap-4">
              <MetricCard
                label="Agents Active"
                value={`${metrics.agents_active}/${metrics.agents_total}`}
                trend={metrics.agents_active === metrics.agents_total ? 'up' : 'stable'}
              />
              <MetricCard
                label="Tasks Completed"
                value={String(metrics.tasks_completed)}
                trend="up"
              />
              <MetricCard
                label="Avg Confidence"
                value={`${Math.round(metrics.avg_confidence * 100)}%`}
                trend={metrics.avg_confidence >= 0.8 ? 'up' : 'stable'}
              />
              <MetricCard
                label="Avg Execution"
                value={`${(metrics.avg_execution_time_ms / 1000).toFixed(1)}s`}
                trend={metrics.avg_execution_time_ms < 5000 ? 'down' : 'stable'}
              />
            </div>
          )}

          {/* Recent Activity */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Recent Agent Activity</h3>
            {recentActivity.length > 0 ? (
              <div className="space-y-3">
                {recentActivity.map((activity) => (
                  <ActivityItem key={activity.id} activity={activity} />
                ))}
              </div>
            ) : (
              <p className="text-white/50 text-center py-4">
                No recent activity. Run the strategist to see agent coordination.
              </p>
            )}
          </Card>
        </div>
      )}

      {/* Recommendations Tab */}
      {activeTab === 'recommendations' && (
        <div className="space-y-4">
          {recommendations.length > 0 ? (
            recommendations.map((rec) => (
              <RecommendationCard
                key={rec.id}
                recommendation={rec}
                onTakeAction={() =>
                  updateRecommendationMutation.execute({ id: rec.id, status: 'in_progress' })
                }
                onDismiss={() =>
                  updateRecommendationMutation.execute({ id: rec.id, status: 'dismissed' })
                }
                onComplete={() =>
                  updateRecommendationMutation.execute({ id: rec.id, status: 'completed' })
                }
              />
            ))
          ) : (
            <EmptyState
              icon="💡"
              title="No Recommendations Yet"
              description="Run the GTM strategist to generate recommendations based on market analysis."
              action={{ label: 'Run Analysis', onClick: handleRun }}
            />
          )}
        </div>
      )}

      {/* Agents Tab */}
      {activeTab === 'agents' && (
        <div className="grid grid-cols-2 gap-4">
          {AGENTS.filter((a) => a.id !== 'gtm-strategist').map((agentItem) => (
            <AgentStatusCard key={agentItem.id} agent={agentItem} companyId={companyId} />
          ))}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <EmptyState
          icon="📜"
          title="Analysis History"
          description="Previous GTM analyses will appear here once you run your first analysis."
          action={!lastRunAt ? { label: 'Run Analysis', onClick: handleRun } : undefined}
        />
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="space-y-6">
          <Card className="border border-amber-500/30 bg-amber-500/5">
            <div className="flex items-start gap-3">
              <span className="text-amber-400 text-xl">⚙️</span>
              <div>
                <h4 className="text-amber-400 font-medium">Settings Configuration Coming Soon</h4>
                <p className="text-white/60 text-sm mt-1">
                  These settings will be configurable in a future update. Current values shown are system defaults.
                </p>
              </div>
            </div>
          </Card>
          <div className="grid grid-cols-2 gap-6">
            <Card>
              <h3 className="text-lg font-semibold text-white mb-4">Orchestration Settings</h3>
              <div className="space-y-4">
                <SettingItem label="Auto-run on company update" value="Disabled" isDefault />
                <SettingItem label="Agent timeout" value="30 seconds" isDefault />
                <SettingItem label="Max retries" value="3" isDefault />
                <SettingItem label="Parallel execution" value="Enabled" isDefault />
              </div>
            </Card>
            <Card>
              <h3 className="text-lg font-semibold text-white mb-4">Output Preferences</h3>
              <div className="space-y-4">
                <SettingItem label="Include executive summary" value="Yes" isDefault />
                <SettingItem label="Confidence threshold" value="70%" isDefault />
                <SettingItem label="Export format" value="JSON" isDefault />
              </div>
            </Card>
          </div>
        </div>
      )}
    </AgentWorkspace>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface PhaseItemProps {
  phase: StrategyPhase;
  isLast: boolean;
}

function PhaseItem({ phase, isLast }: PhaseItemProps) {
  return (
    <div className="flex items-center">
      <div className="text-center">
        <div
          className={`w-12 h-12 rounded-full flex items-center justify-center text-xl mb-2 ${
            phase.status === 'complete'
              ? 'bg-green-500/20 border-2 border-green-500'
              : phase.status === 'in_progress'
              ? 'bg-purple-500/20 border-2 border-purple-500 animate-pulse'
              : 'bg-white/10 border-2 border-white/20'
          }`}
        >
          {phase.icon}
        </div>
        <p className="text-xs text-white/70">{phase.name}</p>
        <Badge
          variant={
            phase.status === 'complete'
              ? 'success'
              : phase.status === 'in_progress'
              ? 'warning'
              : 'default'
          }
        >
          {phase.status === 'in_progress' ? 'Active' : phase.status}
        </Badge>
      </div>
      {!isLast && (
        <div
          className={`w-16 h-0.5 mx-2 ${
            phase.status === 'complete' ? 'bg-green-500' : 'bg-white/20'
          }`}
        />
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  trend,
}: {
  label: string;
  value: string;
  trend: 'up' | 'down' | 'stable';
}) {
  const trendIcons = { up: '↑', down: '↓', stable: '→' };
  const trendColors = { up: 'text-green-400', down: 'text-green-400', stable: 'text-white/50' };

  return (
    <Card>
      <p className="text-white/50 text-xs">{label}</p>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">{value}</span>
        <span className={trendColors[trend]}>{trendIcons[trend]}</span>
      </div>
    </Card>
  );
}

interface ActivityItemProps {
  activity: AgentActivity;
}

function ActivityItem({ activity }: ActivityItemProps) {
  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr);
    const diff = Date.now() - date.getTime();
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes} min ago`;
    return 'Just now';
  };

  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-white/5">
      <span className="text-xl">{activity.icon}</span>
      <div className="flex-1">
        <p className="text-white text-sm">
          <span className="font-medium">{activity.agent_name}</span> {activity.action}
        </p>
      </div>
      <span className="text-white/40 text-xs">{formatTimeAgo(activity.created_at)}</span>
    </div>
  );
}

interface RecommendationCardProps {
  recommendation: StrategyRecommendation;
  onTakeAction: () => void;
  onDismiss: () => void;
  onComplete: () => void;
}

function RecommendationCard({
  recommendation,
  onTakeAction,
  onDismiss,
  onComplete,
}: RecommendationCardProps) {
  return (
    <Card
      className={`border-l-4 ${
        recommendation.priority === 'high'
          ? 'border-l-red-500'
          : recommendation.priority === 'medium'
          ? 'border-l-amber-500'
          : 'border-l-blue-500'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <Badge variant={recommendation.priority === 'high' ? 'danger' : 'warning'}>
              {recommendation.priority} priority
            </Badge>
            <Badge variant="default">{recommendation.impact}</Badge>
            {recommendation.status !== 'pending' && (
              <Badge
                variant={recommendation.status === 'completed' ? 'success' : 'default'}
              >
                {recommendation.status}
              </Badge>
            )}
          </div>
          <h4 className="text-white font-semibold">{recommendation.title}</h4>
          <p className="text-white/70 text-sm mt-1">{recommendation.description}</p>
          <div className="flex items-center gap-2 mt-3">
            <span className="text-xs text-white/50">Sources:</span>
            {recommendation.source_agents.map((agentId) => {
              const sourceAgent = AGENTS.find((a) => a.id === agentId);
              return (
                <span key={agentId} className="text-xs text-white/70">
                  {sourceAgent?.avatar} {sourceAgent?.name}
                </span>
              );
            })}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-white">
            {Math.round(recommendation.confidence * 100)}%
          </div>
          <div className="text-xs text-white/50">confidence</div>
        </div>
      </div>
      {recommendation.status === 'pending' && (
        <div className="flex gap-2 mt-4">
          <Button variant="primary" size="sm" onClick={onTakeAction}>
            Take Action
          </Button>
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            Dismiss
          </Button>
        </div>
      )}
      {recommendation.status === 'in_progress' && (
        <div className="flex gap-2 mt-4">
          <Button variant="primary" size="sm" onClick={onComplete}>
            Mark Complete
          </Button>
        </div>
      )}
    </Card>
  );
}

interface AgentStatusCardProps {
  agent: (typeof AGENTS)[number];
  companyId: string;
}

function AgentStatusCard({ agent: agentItem, companyId }: AgentStatusCardProps) {
  const { data: statusData, isLoading } = useAgentStatus(companyId, agentItem.id);

  const getStatusBadge = () => {
    if (isLoading) {
      return <Badge variant="default">Loading...</Badge>;
    }

    const status = statusData?.status || 'idle';
    switch (status) {
      case 'running':
        return <Badge variant="warning">Running</Badge>;
      case 'completed':
        return <Badge variant="success">Completed</Badge>;
      case 'error':
        return <Badge variant="danger">Error</Badge>;
      default:
        return <Badge variant="success">Ready</Badge>;
    }
  };

  const formatLastRun = () => {
    if (!statusData?.last_run_at) return null;
    const date = new Date(statusData.last_run_at);
    const diff = Date.now() - date.getTime();
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  return (
    <Card>
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-xl"
          style={{
            background: `linear-gradient(135deg, rgba(${agentItem.color}, 0.2), rgba(${agentItem.color}, 0.1))`,
            border: `2px solid rgba(${agentItem.color}, 0.5)`,
          }}
        >
          {agentItem.avatar}
        </div>
        <div className="flex-1">
          <h4 className="text-white font-medium">{agentItem.name}</h4>
          <p className="text-white/50 text-xs">{agentItem.capabilities.join(' • ')}</p>
          {statusData?.last_run_at && (
            <p className="text-white/40 text-xs mt-1">Last run: {formatLastRun()}</p>
          )}
        </div>
        {getStatusBadge()}
      </div>
      {statusData?.status === 'error' && statusData.error_message && (
        <p className="text-red-400 text-xs mt-2">{statusData.error_message}</p>
      )}
    </Card>
  );
}

function SettingItem({ label, value, isDefault }: { label: string; value: string; isDefault?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-white/70">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-white font-medium">{value}</span>
        {isDefault && (
          <span className="text-xs text-white/40 bg-white/10 px-1.5 py-0.5 rounded">default</span>
        )}
      </div>
    </div>
  );
}
