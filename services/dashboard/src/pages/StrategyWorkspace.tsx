/**
 * GTM Strategist Workspace
 *
 * Central command for orchestrating GTM strategy across all agents.
 */

import { useState } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS } from '../types';

// Strategy phases
const STRATEGY_PHASES = [
  { id: 'discovery', name: 'Discovery', status: 'complete', icon: '🔍' },
  { id: 'analysis', name: 'Analysis', status: 'complete', icon: '📊' },
  { id: 'strategy', name: 'Strategy', status: 'in_progress', icon: '🎯' },
  { id: 'execution', name: 'Execution', status: 'pending', icon: '🚀' },
  { id: 'optimization', name: 'Optimization', status: 'pending', icon: '📈' },
];

// Mock strategic recommendations
const MOCK_RECOMMENDATIONS = [
  {
    id: '1',
    priority: 'high',
    title: 'Focus on Fintech Vertical',
    description: 'Market analysis shows 34% YoY growth in Singapore fintech. Prioritize this segment for Q1.',
    sourceAgents: ['market-intelligence', 'customer-profiler'],
    impact: 'High Revenue Impact',
    confidence: 0.87,
  },
  {
    id: '2',
    priority: 'high',
    title: 'Address Competitor Pricing Threat',
    description: 'TechRival reduced pricing by 20%. Consider value-based positioning or feature differentiation.',
    sourceAgents: ['competitor-analyst'],
    impact: 'Defensive',
    confidence: 0.92,
  },
  {
    id: '3',
    priority: 'medium',
    title: 'Launch LinkedIn Thought Leadership',
    description: 'Target audience is highly active on LinkedIn. 3 posts/week recommended.',
    sourceAgents: ['campaign-architect', 'customer-profiler'],
    impact: 'Brand Awareness',
    confidence: 0.78,
  },
];

export function StrategyWorkspace() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRunning, setIsRunning] = useState(false);

  const agent = AGENTS.find((a) => a.id === 'gtm-strategist')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'recommendations', label: 'Recommendations', badge: MOCK_RECOMMENDATIONS.length, icon: '💡' },
    { id: 'agents', label: 'Agent Status', icon: '🤖' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  return (
    <AgentWorkspace
      agent={agent}
      status="active"
      lastRun={new Date(Date.now() - 1 * 60 * 60 * 1000)}
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
            <div className="flex items-center justify-between">
              {STRATEGY_PHASES.map((phase, index) => (
                <div key={phase.id} className="flex items-center">
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
                  {index < STRATEGY_PHASES.length - 1 && (
                    <div
                      className={`w-16 h-0.5 mx-2 ${
                        phase.status === 'complete' ? 'bg-green-500' : 'bg-white/20'
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Key Metrics */}
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="Agents Active" value="6/7" trend="up" />
            <MetricCard label="Tasks Completed" value="23" trend="up" />
            <MetricCard label="Avg Confidence" value="84%" trend="stable" />
            <MetricCard label="Time to Insight" value="4.2s" trend="down" />
          </div>

          {/* Recent Activity */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Recent Agent Activity</h3>
            <div className="space-y-3">
              <ActivityItem
                agent="Market Intelligence"
                action="Discovered new market trend"
                time="2 min ago"
                icon="📊"
              />
              <ActivityItem
                agent="Competitor Analyst"
                action="Updated SWOT for TechRival"
                time="5 min ago"
                icon="🔍"
              />
              <ActivityItem
                agent="Lead Hunter"
                action="Found 3 high-fit prospects"
                time="12 min ago"
                icon="🎣"
              />
            </div>
          </Card>
        </div>
      )}

      {/* Recommendations Tab */}
      {activeTab === 'recommendations' && (
        <div className="space-y-4">
          {MOCK_RECOMMENDATIONS.map((rec) => (
            <Card
              key={rec.id}
              className={`border-l-4 ${
                rec.priority === 'high'
                  ? 'border-l-red-500'
                  : rec.priority === 'medium'
                  ? 'border-l-amber-500'
                  : 'border-l-blue-500'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant={rec.priority === 'high' ? 'danger' : 'warning'}>
                      {rec.priority} priority
                    </Badge>
                    <Badge variant="default">{rec.impact}</Badge>
                  </div>
                  <h4 className="text-white font-semibold">{rec.title}</h4>
                  <p className="text-white/70 text-sm mt-1">{rec.description}</p>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="text-xs text-white/50">Sources:</span>
                    {rec.sourceAgents.map((agentId) => {
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
                  <div className="text-2xl font-bold text-white">{Math.round(rec.confidence * 100)}%</div>
                  <div className="text-xs text-white/50">confidence</div>
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <Button variant="primary" size="sm">
                  Take Action
                </Button>
                <Button variant="ghost" size="sm">
                  View Details
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Agents Tab */}
      {activeTab === 'agents' && (
        <div className="grid grid-cols-2 gap-4">
          {AGENTS.filter((a) => a.id !== 'gtm-strategist').map((agentItem) => (
            <Card key={agentItem.id}>
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
                </div>
                <Badge variant="success">Ready</Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <EmptyState
          icon="📜"
          title="Analysis History"
          description="Previous GTM analyses will appear here. Run your first analysis to get started."
          action={{ label: 'Run Analysis', onClick: handleRun }}
        />
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Orchestration Settings</h3>
            <div className="space-y-4">
              <SettingItem label="Auto-run on company update" value="Enabled" />
              <SettingItem label="Agent timeout" value="30 seconds" />
              <SettingItem label="Max retries" value="3" />
              <SettingItem label="Parallel execution" value="Enabled" />
            </div>
          </Card>
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Output Preferences</h3>
            <div className="space-y-4">
              <SettingItem label="Include executive summary" value="Yes" />
              <SettingItem label="Confidence threshold" value="70%" />
              <SettingItem label="Export format" value="PDF, JSON" />
            </div>
          </Card>
        </div>
      )}
    </AgentWorkspace>
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
  const trendColors = { up: 'text-green-400', down: 'text-red-400', stable: 'text-white/50' };

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

function ActivityItem({
  agent,
  action,
  time,
  icon,
}: {
  agent: string;
  action: string;
  time: string;
  icon: string;
}) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-white/5">
      <span className="text-xl">{icon}</span>
      <div className="flex-1">
        <p className="text-white text-sm">
          <span className="font-medium">{agent}</span> {action}
        </p>
      </div>
      <span className="text-white/40 text-xs">{time}</span>
    </div>
  );
}

function SettingItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-white/70">{label}</span>
      <span className="text-white font-medium">{value}</span>
    </div>
  );
}
