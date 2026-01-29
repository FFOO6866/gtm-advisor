/**
 * Intelligence Agent Workspace
 *
 * Displays market intelligence, competitive insights, and alerts.
 * Connected to real backend API.
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, TrendingUp, AlertTriangle, Lightbulb, Archive } from 'lucide-react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import {
  Card,
  Badge,
  Button,
  InsightCard,
  EmptyState,
  InsightListLoading,
  ErrorState,
} from '../components/common';
import { AGENTS } from '../types';
import { useCompanyId } from '../context/CompanyContext';
import { useInsights, useMutation } from '../hooks/useApi';
import * as api from '../api/workspaces';
import type { MarketInsight } from '../api/workspaces';

export function IntelligenceWorkspace() {
  const navigate = useNavigate();
  const companyId = useCompanyId();
  const [activeTab, setActiveTab] = useState('insights');
  const [isRunning, setIsRunning] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  // Fetch insights from API
  const { data: insightData, isLoading, error, refresh } = useInsights(companyId);

  const agent = AGENTS.find((a) => a.id === 'market-intelligence')!;

  // Mutations
  const markReadMutation = useMutation(
    (insightId: string) => api.markInsightRead(companyId!, insightId),
    {
      invalidateKeys: ['insights'],
      onSuccess: () => refresh(),
    }
  );

  const archiveMutation = useMutation(
    (insightId: string) => api.archiveInsight(companyId!, insightId),
    {
      invalidateKeys: ['insights'],
      onSuccess: () => refresh(),
    }
  );

  const insights = insightData?.insights || [];
  const unreadCount = insightData?.unread_count || 0;
  const alerts = insights.filter((i) => i.priority === 'high' && !i.is_read);

  const filteredInsights = useMemo(() => {
    if (filter === 'all') return insights;
    return insights.filter((i) => i.priority === filter || i.category === filter);
  }, [filter, insights]);

  const groupedInsights = useMemo(() => ({
    high: filteredInsights.filter((i) => i.priority === 'high'),
    medium: filteredInsights.filter((i) => i.priority === 'medium'),
    opportunity: filteredInsights.filter((i) => i.priority === 'opportunity'),
  }), [filteredInsights]);

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    refresh();
    setIsRunning(false);
  };

  const handleSendToAgent = (agentId: string) => {
    navigate(`/agent/${agentId}`);
  };

  const tabs = [
    { id: 'insights', label: 'Insights', badge: unreadCount, icon: '📊' },
    { id: 'alerts', label: 'Alerts', badge: alerts.length, icon: '🔔' },
    { id: 'competitors', label: 'Competitors', icon: '🔍' },
    { id: 'trends', label: 'Trends', icon: '📈' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
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
        <InsightListLoading />
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
          title="Failed to load insights"
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
          description="Please complete onboarding to start gathering market intelligence."
        />
      </AgentWorkspace>
    );
  }

  return (
    <AgentWorkspace
      agent={agent}
      status="active"
      lastRun={new Date(Date.now() - 2 * 60 * 60 * 1000)}
      nextScheduledRun={new Date(Date.now() + 4 * 60 * 60 * 1000)}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Insights Tab */}
      {activeTab === 'insights' && (
        <div className="space-y-6">
          {/* Filters */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-white/50" />
            <div className="flex gap-2">
              {['all', 'high', 'medium', 'opportunity', 'competitor', 'trend'].map((f) => (
                <Button
                  key={f}
                  variant={filter === f ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setFilter(f)}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </Button>
              ))}
            </div>
          </div>

          {/* High Priority */}
          {groupedInsights.high.length > 0 && (
            <InsightSection
              title="High Priority"
              icon={<AlertTriangle className="w-4 h-4 text-red-400" />}
              count={groupedInsights.high.length}
            >
              {groupedInsights.high.map((insight) => (
                <InsightCardWrapper
                  key={insight.id}
                  insight={insight}
                  expanded
                  onSendToAgent={handleSendToAgent}
                  onMarkRead={() => markReadMutation.execute(insight.id)}
                  onArchive={() => archiveMutation.execute(insight.id)}
                />
              ))}
            </InsightSection>
          )}

          {/* Medium Priority */}
          {groupedInsights.medium.length > 0 && (
            <InsightSection
              title="Medium Priority"
              icon={<TrendingUp className="w-4 h-4 text-amber-400" />}
              count={groupedInsights.medium.length}
              defaultCollapsed
            >
              {groupedInsights.medium.map((insight) => (
                <InsightCardWrapper
                  key={insight.id}
                  insight={insight}
                  onSendToAgent={handleSendToAgent}
                  onMarkRead={() => markReadMutation.execute(insight.id)}
                  onArchive={() => archiveMutation.execute(insight.id)}
                />
              ))}
            </InsightSection>
          )}

          {/* Opportunities */}
          {groupedInsights.opportunity.length > 0 && (
            <InsightSection
              title="Opportunities"
              icon={<Lightbulb className="w-4 h-4 text-green-400" />}
              count={groupedInsights.opportunity.length}
              defaultCollapsed
            >
              {groupedInsights.opportunity.map((insight) => (
                <InsightCardWrapper
                  key={insight.id}
                  insight={insight}
                  onSendToAgent={handleSendToAgent}
                  onMarkRead={() => markReadMutation.execute(insight.id)}
                  onArchive={() => archiveMutation.execute(insight.id)}
                />
              ))}
            </InsightSection>
          )}

          {filteredInsights.length === 0 && (
            <EmptyState
              icon="🔍"
              title="No insights found"
              description="Try adjusting your filters or run the agent to gather new intelligence."
              action={{ label: 'Run Agent', onClick: handleRun }}
            />
          )}
        </div>
      )}

      {/* Alerts Tab */}
      {activeTab === 'alerts' && (
        <div className="space-y-4">
          {alerts.length === 0 ? (
            <EmptyState
              icon="✅"
              title="No active alerts"
              description="All caught up! We'll notify you when something needs attention."
            />
          ) : (
            alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                insight={alert}
                onAcknowledge={() => markReadMutation.execute(alert.id)}
              />
            ))
          )}
        </div>
      )}

      {/* Competitors Tab */}
      {activeTab === 'competitors' && (
        <div className="grid grid-cols-2 gap-4">
          {insightData?.competitor_summaries?.map((comp) => (
            <CompetitorCard
              key={comp.name}
              name={comp.name}
              status={comp.status}
              lastActivity={comp.last_activity}
              threatLevel={comp.threat_level}
            />
          )) || (
            <>
              <CompetitorCard
                name="TechRival Inc."
                status="Actively Monitoring"
                lastActivity="No recent activity"
                threatLevel="medium"
              />
              <Card className="border-dashed border-2 border-white/20 flex items-center justify-center min-h-[150px]">
                <Button variant="ghost" onClick={() => navigate('/agent/competitor-analyst')}>
                  + Add Competitor
                </Button>
              </Card>
            </>
          )}
        </div>
      )}

      {/* Trends Tab */}
      {activeTab === 'trends' && (
        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Market Trends</h3>
            {insights.filter((i) => i.category === 'trend').length > 0 ? (
              <div className="space-y-3">
                {insights
                  .filter((i) => i.category === 'trend')
                  .map((insight) => (
                    <div key={insight.id} className="p-3 bg-white/5 rounded-lg">
                      <h4 className="font-medium text-white">{insight.title}</h4>
                      <p className="text-sm text-white/60 mt-1">{insight.summary}</p>
                    </div>
                  ))}
              </div>
            ) : (
              <p className="text-white/60">
                Trend analysis visualization would go here - showing market movements,
                share of voice changes, and emerging topics over time.
              </p>
            )}
          </Card>
        </div>
      )}

      {/* Configure Tab */}
      {activeTab === 'configure' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Monitoring Settings</h3>
            <div className="space-y-4">
              <ConfigItem label="Scan Frequency" value="Every 6 hours" />
              <ConfigItem label="Competitors Tracked" value={`${insightData?.competitors_count || 0} companies`} />
              <ConfigItem label="Keywords Monitored" value="12 terms" />
              <ConfigItem label="News Sources" value="47 sources" />
            </div>
          </Card>
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Alert Preferences</h3>
            <div className="space-y-4">
              <ConfigItem label="Email Alerts" value="Enabled" />
              <ConfigItem label="High Priority Only" value="No" />
              <ConfigItem label="Daily Digest" value="9:00 AM SGT" />
            </div>
          </Card>
        </div>
      )}

      {/* Connected Agents Footer */}
      <Card className="mt-8" padding="sm">
        <div className="flex items-center justify-between">
          <div className="text-sm text-white/50">
            <span className="font-medium text-white">Connected Agents:</span> This agent's insights feed into
            Campaign Agent ({insightData?.a2a_connections?.campaign || 0} this month), Strategy Agent ({insightData?.a2a_connections?.strategy || 0}), GTM Commercial ({insightData?.a2a_connections?.gtm || 0})
          </div>
          <Button variant="ghost" size="sm">
            View A2A Log
          </Button>
        </div>
      </Card>
    </AgentWorkspace>
  );
}

// Helper Components

interface InsightSectionProps {
  title: string;
  icon: React.ReactNode;
  count: number;
  defaultCollapsed?: boolean;
  children: React.ReactNode;
}

function InsightSection({ title, icon, count, defaultCollapsed, children }: InsightSectionProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  return (
    <div className="space-y-3">
      <button
        className="flex items-center gap-2 text-white hover:text-white/80 transition-colors"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        {icon}
        <span className="font-semibold">{title}</span>
        <Badge variant="default">{count}</Badge>
        <span className="text-white/50 text-sm ml-2">
          {isCollapsed ? '▶ Show' : '▼ Hide'}
        </span>
      </button>
      {!isCollapsed && <div className="space-y-3">{children}</div>}
    </div>
  );
}

interface InsightCardWrapperProps {
  insight: MarketInsight;
  expanded?: boolean;
  onSendToAgent: (agentId: string) => void;
  onMarkRead: () => void;
  onArchive: () => void;
}

function InsightCardWrapper({ insight, expanded, onSendToAgent, onMarkRead, onArchive }: InsightCardWrapperProps) {
  // Transform API insight to the format expected by InsightCard
  // Map impact_level to priority if priority is not set
  const priorityFromImpact = insight.impact_level === 'high' ? 'high' :
                             insight.impact_level === 'medium' ? 'medium' : 'opportunity';

  const transformedInsight = {
    id: insight.id,
    title: insight.title,
    summary: insight.summary || '', // Ensure non-null string
    priority: (insight.priority || priorityFromImpact) as 'high' | 'medium' | 'low' | 'opportunity',
    category: insight.category || insight.insight_type || 'market',
    agentId: 'market-intelligence',
    isNew: !insight.is_read,
    createdAt: new Date(insight.created_at),
    evidence: insight.evidence,
    implication: insight.implication,
    recommendedAction: insight.recommended_action || insight.recommended_actions?.[0],
    sources: insight.sources || [],
    confidence: insight.confidence,
  };

  return (
    <div className="relative">
      <InsightCard
        insight={transformedInsight}
        expanded={expanded}
        onSendToAgent={onSendToAgent}
      />
      <div className="absolute top-4 right-4 flex gap-1">
        {!insight.is_read && (
          <Button variant="ghost" size="sm" onClick={onMarkRead}>
            Mark Read
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onArchive}
          leftIcon={<Archive className="w-3 h-3" />}
        >
          Archive
        </Button>
      </div>
    </div>
  );
}

interface AlertCardProps {
  insight: MarketInsight;
  onAcknowledge: () => void;
}

function AlertCard({ insight, onAcknowledge }: AlertCardProps) {
  return (
    <Card className="border-l-4 border-l-red-500 bg-red-500/10">
      <div className="flex items-start gap-3">
        <span className="text-xl">🚨</span>
        <div className="flex-1">
          <h4 className="font-semibold text-white">{insight.title}</h4>
          <p className="text-sm text-white/70 mt-1">{insight.summary}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onAcknowledge}>
          Acknowledge
        </Button>
      </div>
    </Card>
  );
}

interface CompetitorCardProps {
  name: string;
  status: string;
  lastActivity: string;
  threatLevel: 'high' | 'medium' | 'low';
}

function CompetitorCard({ name, status, lastActivity, threatLevel }: CompetitorCardProps) {
  const threatConfig = {
    high: { color: 'text-red-400', label: 'High Threat' },
    medium: { color: 'text-amber-400', label: 'Medium Threat' },
    low: { color: 'text-green-400', label: 'Low Threat' },
  };

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-semibold text-white">{name}</h4>
          <p className="text-sm text-white/50 mt-1">{status}</p>
        </div>
        <Badge variant={threatLevel === 'high' ? 'danger' : threatLevel === 'medium' ? 'warning' : 'success'}>
          {threatConfig[threatLevel].label}
        </Badge>
      </div>
      <p className="text-sm text-white/60 mt-3">{lastActivity}</p>
      <Button variant="ghost" size="sm" className="mt-3">
        View Details →
      </Button>
    </Card>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-white/70">{label}</span>
      <span className="text-white font-medium">{value}</span>
    </div>
  );
}
