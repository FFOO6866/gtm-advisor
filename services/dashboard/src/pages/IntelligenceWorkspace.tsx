/**
 * Intelligence Agent Workspace
 *
 * Displays market intelligence, competitive insights, and alerts.
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, TrendingUp, AlertTriangle, Lightbulb } from 'lucide-react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, InsightCard, EmptyState } from '../components/common';
import { AGENTS, type Insight, type Alert } from '../types';

// Mock data - in production this would come from API
const MOCK_INSIGHTS: Insight[] = [
  {
    id: '1',
    title: 'Competitor Pricing Change Detected',
    summary: 'TechRival Inc. reduced their SME tier pricing by 20%, positioning directly against your $700/month offering.',
    priority: 'high',
    category: 'competitor',
    agentId: 'market-intelligence',
    isNew: true,
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
    evidence: 'Pricing page change detected on 2024-01-28. LinkedIn announcement post received 234 engagements.',
    implication: 'May increase churn risk for price-sensitive customers in the SME segment.',
    recommendedAction: 'Review value messaging, consider limited-time offer or feature differentiation campaign.',
    sources: ['TechRival pricing page', 'LinkedIn', 'G2 Reviews'],
    confidence: 0.92,
  },
  {
    id: '2',
    title: 'AI Adoption Surge in Singapore SMEs',
    summary: 'Market research shows 34% YoY growth in AI tool adoption among Singapore SMEs, with marketing automation leading.',
    priority: 'opportunity',
    category: 'trend',
    agentId: 'market-intelligence',
    isNew: true,
    createdAt: new Date(Date.now() - 5 * 60 * 60 * 1000), // 5 hours ago
    evidence: 'Multiple industry reports confirm trend. Government PSG grants expanded for AI tools.',
    implication: 'Favorable market conditions for growth. PSG positioning could accelerate sales.',
    recommendedAction: 'Develop PSG-focused marketing campaign highlighting grant eligibility.',
    sources: ['IMDA Report 2024', 'Enterprise Singapore', 'TechInAsia'],
    confidence: 0.88,
  },
  {
    id: '3',
    title: 'Regulatory Update: PDPA Amendments',
    summary: 'Proposed PDPA amendments may require enhanced consent mechanisms for marketing automation tools.',
    priority: 'medium',
    category: 'regulatory',
    agentId: 'market-intelligence',
    createdAt: new Date(Date.now() - 24 * 60 * 60 * 1000), // 1 day ago
    evidence: 'PDPC consultation paper released. Industry feedback period ends March 2024.',
    implication: 'May need to enhance consent workflows. Could be competitive advantage if addressed early.',
    recommendedAction: 'Review current consent mechanisms. Consider proactive compliance messaging.',
    sources: ['PDPC.gov.sg', 'Law firm analysis'],
    confidence: 0.78,
  },
  {
    id: '4',
    title: 'Competitor InnovateCo Raised Series B',
    summary: 'InnovateCo announced $15M Series B, planning to expand into Singapore market.',
    priority: 'medium',
    category: 'competitor',
    agentId: 'market-intelligence',
    createdAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000), // 2 days ago
    evidence: 'Press release and TechCrunch coverage. Job postings for Singapore roles.',
    implication: 'Increased competition expected in 6-12 months. They may compete on features.',
    recommendedAction: 'Accelerate roadmap for differentiating features. Strengthen customer relationships.',
    sources: ['TechCrunch', 'LinkedIn Jobs', 'Crunchbase'],
    confidence: 0.85,
  },
  {
    id: '5',
    title: 'White Space: No Local Competitor for Enterprise Segment',
    summary: 'Analysis shows no local Singapore player adequately serving enterprise marketing teams (200+ employees).',
    priority: 'opportunity',
    category: 'market',
    agentId: 'market-intelligence',
    createdAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000), // 3 days ago
    evidence: 'Competitive analysis of 12 players. Enterprise features gap identified.',
    implication: 'First-mover advantage opportunity in enterprise segment.',
    recommendedAction: 'Consider enterprise tier development. Target 3-5 enterprise pilots.',
    sources: ['Internal competitive analysis', 'G2 Grid', 'Customer interviews'],
    confidence: 0.72,
  },
];

const MOCK_ALERTS: Alert[] = [
  {
    id: 'a1',
    title: 'Competitor launched new campaign',
    description: 'TechRival started aggressive LinkedIn campaign targeting your keywords.',
    severity: 'warning',
    agentId: 'market-intelligence',
    createdAt: new Date(Date.now() - 1 * 60 * 60 * 1000),
  },
  {
    id: 'a2',
    title: 'Market sentiment shift detected',
    description: 'Negative sentiment increasing around "AI marketing" terms due to recent industry news.',
    severity: 'info',
    agentId: 'market-intelligence',
    createdAt: new Date(Date.now() - 6 * 60 * 60 * 1000),
  },
];

export function IntelligenceWorkspace() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('insights');
  const [isRunning, setIsRunning] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  const agent = AGENTS.find((a) => a.id === 'market-intelligence')!;

  const filteredInsights = useMemo(() => {
    if (filter === 'all') return MOCK_INSIGHTS;
    return MOCK_INSIGHTS.filter((i) => i.priority === filter || i.category === filter);
  }, [filter]);

  const groupedInsights = useMemo(() => ({
    high: filteredInsights.filter((i) => i.priority === 'high'),
    medium: filteredInsights.filter((i) => i.priority === 'medium'),
    opportunity: filteredInsights.filter((i) => i.priority === 'opportunity'),
  }), [filteredInsights]);

  const handleRun = async () => {
    setIsRunning(true);
    // Simulate agent run
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const handleSendToAgent = (agentId: string) => {
    navigate(`/agent/${agentId}`);
  };

  const tabs = [
    { id: 'insights', label: 'Insights', badge: MOCK_INSIGHTS.filter((i) => i.isNew).length, icon: '📊' },
    { id: 'alerts', label: 'Alerts', badge: MOCK_ALERTS.length, icon: '🔔' },
    { id: 'competitors', label: 'Competitors', icon: '🔍' },
    { id: 'trends', label: 'Trends', icon: '📈' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
  ];

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
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  expanded
                  onSendToAgent={handleSendToAgent}
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
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  onSendToAgent={handleSendToAgent}
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
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  onSendToAgent={handleSendToAgent}
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
          {MOCK_ALERTS.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
          {MOCK_ALERTS.length === 0 && (
            <EmptyState
              icon="✅"
              title="No active alerts"
              description="All caught up! We'll notify you when something needs attention."
            />
          )}
        </div>
      )}

      {/* Competitors Tab */}
      {activeTab === 'competitors' && (
        <div className="grid grid-cols-2 gap-4">
          <CompetitorCard
            name="TechRival Inc."
            status="Actively Monitoring"
            lastActivity="Pricing change detected 2h ago"
            threatLevel="high"
          />
          <CompetitorCard
            name="InnovateCo"
            status="Watching"
            lastActivity="Series B announced 2d ago"
            threatLevel="medium"
          />
          <CompetitorCard
            name="MarketPro"
            status="Low Activity"
            lastActivity="No significant changes in 30d"
            threatLevel="low"
          />
          <Card className="border-dashed border-2 border-white/20 flex items-center justify-center min-h-[150px]">
            <Button variant="ghost">+ Add Competitor</Button>
          </Card>
        </div>
      )}

      {/* Trends Tab */}
      {activeTab === 'trends' && (
        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Market Trends</h3>
            <p className="text-white/60">
              Trend analysis visualization would go here - showing market movements,
              share of voice changes, and emerging topics over time.
            </p>
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
              <ConfigItem label="Competitors Tracked" value="5 companies" />
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
            Campaign Agent (12 this month), Strategy Agent (5), GTM Commercial (3)
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

interface AlertCardProps {
  alert: Alert;
}

function AlertCard({ alert }: AlertCardProps) {
  const severityConfig = {
    critical: { color: 'border-l-red-500 bg-red-500/10', icon: '🚨' },
    warning: { color: 'border-l-amber-500 bg-amber-500/10', icon: '⚠️' },
    info: { color: 'border-l-blue-500 bg-blue-500/10', icon: 'ℹ️' },
  };

  const config = severityConfig[alert.severity];

  return (
    <Card className={`border-l-4 ${config.color}`}>
      <div className="flex items-start gap-3">
        <span className="text-xl">{config.icon}</span>
        <div className="flex-1">
          <h4 className="font-semibold text-white">{alert.title}</h4>
          <p className="text-sm text-white/70 mt-1">{alert.description}</p>
        </div>
        <Button variant="ghost" size="sm">
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
