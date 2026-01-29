/**
 * Competitor Analyst Workspace
 *
 * SWOT analysis, competitive intelligence, and market positioning.
 */

import { useState } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS } from '../types';

// Mock competitor data
const MOCK_COMPETITORS = [
  {
    id: '1',
    name: 'TechRival Inc.',
    website: 'techrival.com',
    threatLevel: 'high',
    strengths: ['Strong brand recognition', 'Large sales team', 'Enterprise focus'],
    weaknesses: ['Slow product updates', 'Poor customer support', 'Limited API'],
    opportunities: ['They recently laid off 20% of staff'],
    threats: ['Just raised $50M Series C', 'Aggressive pricing'],
    positioning: 'Enterprise-first, feature-rich platform',
    lastUpdated: new Date(Date.now() - 2 * 60 * 60 * 1000),
  },
  {
    id: '2',
    name: 'InnovateCo',
    website: 'innovateco.io',
    threatLevel: 'medium',
    strengths: ['Modern UI/UX', 'Strong developer community', 'API-first'],
    weaknesses: ['Limited enterprise features', 'Small team', 'No Singapore presence'],
    opportunities: ['No local support offering'],
    threats: ['Planning Singapore expansion', 'Well-funded'],
    positioning: 'Developer-friendly, modern stack',
    lastUpdated: new Date(Date.now() - 24 * 60 * 60 * 1000),
  },
  {
    id: '3',
    name: 'MarketPro',
    website: 'marketpro.sg',
    threatLevel: 'low',
    strengths: ['Local presence', 'Government connections', 'Established'],
    weaknesses: ['Outdated technology', 'Slow innovation', 'Legacy pricing'],
    opportunities: ['Customers frustrated with old UI'],
    threats: ['Strong existing customer base'],
    positioning: 'Traditional, relationship-based',
    lastUpdated: new Date(Date.now() - 72 * 60 * 60 * 1000),
  },
];

export function CompetitorWorkspace() {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedCompetitor, setSelectedCompetitor] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const agent = AGENTS.find((a) => a.id === 'competitor-analyst')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'swot', label: 'SWOT Analysis', icon: '📊' },
    { id: 'tracking', label: 'Change Tracking', badge: 2, icon: '🔔' },
    { id: 'battlecards', label: 'Battle Cards', icon: '⚔️' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
  ];

  const selected = MOCK_COMPETITORS.find((c) => c.id === selectedCompetitor);

  return (
    <AgentWorkspace
      agent={agent}
      status="active"
      lastRun={new Date(Date.now() - 6 * 60 * 60 * 1000)}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Threat Summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card className="border-l-4 border-l-red-500">
              <p className="text-white/50 text-xs">High Threat</p>
              <p className="text-2xl font-bold text-white">1</p>
              <p className="text-xs text-red-400">Requires attention</p>
            </Card>
            <Card className="border-l-4 border-l-amber-500">
              <p className="text-white/50 text-xs">Medium Threat</p>
              <p className="text-2xl font-bold text-white">1</p>
              <p className="text-xs text-amber-400">Monitor closely</p>
            </Card>
            <Card className="border-l-4 border-l-green-500">
              <p className="text-white/50 text-xs">Low Threat</p>
              <p className="text-2xl font-bold text-white">1</p>
              <p className="text-xs text-green-400">Under control</p>
            </Card>
          </div>

          {/* Competitor List */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Tracked Competitors</h3>
            <div className="space-y-3">
              {MOCK_COMPETITORS.map((competitor) => (
                <div
                  key={competitor.id}
                  className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                    selectedCompetitor === competitor.id
                      ? 'bg-white/10 border-purple-500'
                      : 'bg-white/5 border-white/10 hover:bg-white/10'
                  }`}
                  onClick={() => setSelectedCompetitor(competitor.id)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-white font-medium">{competitor.name}</h4>
                      <p className="text-white/50 text-sm">{competitor.website}</p>
                    </div>
                    <div className="text-right">
                      <Badge
                        variant={
                          competitor.threatLevel === 'high'
                            ? 'danger'
                            : competitor.threatLevel === 'medium'
                            ? 'warning'
                            : 'success'
                        }
                      >
                        {competitor.threatLevel} threat
                      </Badge>
                      <p className="text-xs text-white/40 mt-1">
                        Updated {formatTimeAgo(competitor.lastUpdated)}
                      </p>
                    </div>
                  </div>
                  <p className="text-white/60 text-sm mt-2">{competitor.positioning}</p>
                </div>
              ))}
              <Button variant="ghost" className="w-full">
                + Add Competitor
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* SWOT Tab */}
      {activeTab === 'swot' && (
        <div className="space-y-6">
          {selected ? (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">
                  SWOT Analysis: {selected.name}
                </h3>
                <Button variant="secondary" size="sm" onClick={() => setSelectedCompetitor(null)}>
                  View All
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <SWOTCard title="Strengths" items={selected.strengths} color="green" icon="💪" />
                <SWOTCard title="Weaknesses" items={selected.weaknesses} color="red" icon="⚠️" />
                <SWOTCard
                  title="Opportunities"
                  items={selected.opportunities}
                  color="blue"
                  icon="💡"
                />
                <SWOTCard title="Threats" items={selected.threats} color="amber" icon="🎯" />
              </div>
            </>
          ) : (
            <EmptyState
              icon="📊"
              title="Select a Competitor"
              description="Choose a competitor from the Overview tab to view their SWOT analysis."
            />
          )}
        </div>
      )}

      {/* Tracking Tab */}
      {activeTab === 'tracking' && (
        <div className="space-y-4">
          <Card className="border-l-4 border-l-red-500">
            <div className="flex items-start gap-3">
              <span className="text-xl">🚨</span>
              <div className="flex-1">
                <h4 className="text-white font-medium">TechRival Pricing Change</h4>
                <p className="text-white/70 text-sm">
                  Reduced SME tier pricing by 20% - now $560/month (was $700)
                </p>
                <p className="text-xs text-white/40 mt-2">Detected 2 hours ago</p>
              </div>
              <Button variant="ghost" size="sm">
                View
              </Button>
            </div>
          </Card>
          <Card className="border-l-4 border-l-amber-500">
            <div className="flex items-start gap-3">
              <span className="text-xl">📢</span>
              <div className="flex-1">
                <h4 className="text-white font-medium">InnovateCo Singapore Expansion</h4>
                <p className="text-white/70 text-sm">
                  Posted 3 job openings for Singapore office on LinkedIn
                </p>
                <p className="text-xs text-white/40 mt-2">Detected 1 day ago</p>
              </div>
              <Button variant="ghost" size="sm">
                View
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Battle Cards Tab */}
      {activeTab === 'battlecards' && (
        <div className="grid grid-cols-2 gap-4">
          {MOCK_COMPETITORS.map((competitor) => (
            <Card key={competitor.id}>
              <h4 className="text-white font-semibold mb-3">vs {competitor.name}</h4>
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-green-400 font-medium">Our Advantages</p>
                  <ul className="text-sm text-white/70 ml-4 list-disc">
                    <li>Better Singapore support</li>
                    <li>Modern AI capabilities</li>
                  </ul>
                </div>
                <div>
                  <p className="text-xs text-red-400 font-medium">Their Advantages</p>
                  <ul className="text-sm text-white/70 ml-4 list-disc">
                    {competitor.strengths.slice(0, 2).map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs text-blue-400 font-medium">Key Objection Handler</p>
                  <p className="text-sm text-white/70 italic">
                    "While {competitor.name} has brand recognition, our AI-first approach delivers
                    faster time-to-value..."
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" className="mt-3">
                Export Battle Card
              </Button>
            </Card>
          ))}
        </div>
      )}

      {/* Configure Tab */}
      {activeTab === 'configure' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Monitoring Settings</h3>
            <div className="space-y-4">
              <SettingItem label="Scan frequency" value="Every 6 hours" />
              <SettingItem label="Track pricing changes" value="Enabled" />
              <SettingItem label="Track job postings" value="Enabled" />
              <SettingItem label="Track news mentions" value="Enabled" />
            </div>
          </Card>
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Alert Settings</h3>
            <div className="space-y-4">
              <SettingItem label="Email alerts" value="Enabled" />
              <SettingItem label="Slack integration" value="Not configured" />
              <SettingItem label="Alert threshold" value="Medium+" />
            </div>
          </Card>
        </div>
      )}
    </AgentWorkspace>
  );
}

function SWOTCard({
  title,
  items,
  color,
  icon,
}: {
  title: string;
  items: string[];
  color: string;
  icon: string;
}) {
  const bgColors: Record<string, string> = {
    green: 'bg-green-500/10 border-green-500/30',
    red: 'bg-red-500/10 border-red-500/30',
    blue: 'bg-blue-500/10 border-blue-500/30',
    amber: 'bg-amber-500/10 border-amber-500/30',
  };

  return (
    <Card className={`${bgColors[color]} border`}>
      <h4 className="text-white font-semibold flex items-center gap-2 mb-3">
        <span>{icon}</span> {title}
      </h4>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="text-white/80 text-sm flex items-start gap-2">
            <span className="text-white/40">•</span>
            {item}
          </li>
        ))}
      </ul>
    </Card>
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

function formatTimeAgo(date: Date): string {
  const diff = Date.now() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
