/**
 * Generic Agent Workspace
 *
 * Fallback workspace for agents that don't have a custom implementation yet.
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS } from '../types';

export function GenericAgentWorkspace() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [isRunning, setIsRunning] = useState(false);

  const agent = AGENTS.find((a) => a.id === agentId);

  if (!agent) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <Card className="max-w-md text-center">
          <span className="text-5xl mb-4 block">🤖</span>
          <h2 className="text-xl font-bold text-white">Agent Not Found</h2>
          <p className="text-white/60 mt-2">The agent "{agentId}" doesn't exist.</p>
          <Button variant="primary" className="mt-4" onClick={() => navigate('/')}>
            Back to Command Center
          </Button>
        </Card>
      </div>
    );
  }

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
  ];

  return (
    <AgentWorkspace
      agent={agent}
      status="idle"
      lastRun={new Date(Date.now() - 48 * 60 * 60 * 1000)}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">About {agent.name}</h3>
            <p className="text-white/70">{agent.description}</p>

            <div className="mt-4">
              <h4 className="text-sm font-medium text-white/50 uppercase mb-2">Capabilities</h4>
              <div className="flex flex-wrap gap-2">
                {agent.capabilities.map((cap) => (
                  <Badge key={cap} variant="purple">
                    {cap}
                  </Badge>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <EmptyState
              icon={agent.avatar}
              title="Workspace Coming Soon"
              description={`The detailed workspace for ${agent.name} is being developed. Run the agent from the main dashboard for now.`}
              action={{ label: 'Run Agent', onClick: handleRun }}
            />
          </Card>

          {/* Quick Stats */}
          <div className="grid grid-cols-3 gap-4">
            <Card padding="sm">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">0</div>
                <div className="text-xs text-white/50">Runs This Week</div>
              </div>
            </Card>
            <Card padding="sm">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">-</div>
                <div className="text-xs text-white/50">Avg. Confidence</div>
              </div>
            </Card>
            <Card padding="sm">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">-</div>
                <div className="text-xs text-white/50">Insights Generated</div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <EmptyState
          icon="📜"
          title="No History Yet"
          description="Run this agent to see execution history."
          action={{ label: 'Run Agent', onClick: handleRun }}
        />
      )}

      {/* Configure Tab */}
      {activeTab === 'configure' && (
        <Card>
          <h3 className="text-lg font-semibold text-white mb-4">Configuration</h3>
          <p className="text-white/60">
            Agent configuration options will be available here. This feature is coming soon.
          </p>
        </Card>
      )}
    </AgentWorkspace>
  );
}
