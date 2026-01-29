/**
 * Company Enricher Workspace
 *
 * Website analysis, company profile enrichment, and A2A discovery.
 */

import { useState } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS } from '../types';

// Mock enrichment data
const MOCK_ENRICHMENT = {
  company: {
    name: 'TechStartup Pte Ltd',
    website: 'techstartup.sg',
    description: 'B2B SaaS platform for SME financial management',
    founded: '2021',
    headquarters: 'Singapore',
    employeeCount: '25-50',
    funding: 'Series A ($5M)',
  },
  products: [
    { name: 'FinanceHub', description: 'Core accounting platform', type: 'Primary' },
    { name: 'PayrollPro', description: 'Payroll automation add-on', type: 'Add-on' },
    { name: 'TaxMate', description: 'Tax compliance module', type: 'Add-on' },
  ],
  techStack: ['React', 'Node.js', 'PostgreSQL', 'AWS', 'Stripe'],
  discoveredCompetitors: ['Xero', 'QuickBooks', 'Financio'],
  targetMarkets: ['Singapore SMEs', 'Malaysia SMEs', 'Fintech Startups'],
  confidence: 0.89,
  lastEnriched: new Date(Date.now() - 4 * 60 * 60 * 1000),
};

// Mock A2A discoveries
const MOCK_DISCOVERIES = [
  {
    id: '1',
    type: 'company_products',
    title: 'Discovered 3 product offerings',
    toAgent: 'campaign-architect',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
    status: 'delivered',
  },
  {
    id: '2',
    type: 'competitor_found',
    title: 'Identified 3 competitors from website',
    toAgent: 'competitor-analyst',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
    status: 'delivered',
  },
  {
    id: '3',
    type: 'company_tech_stack',
    title: 'Extracted technology stack',
    toAgent: 'lead-hunter',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
    status: 'delivered',
  },
  {
    id: '4',
    type: 'target_markets',
    title: 'Identified target market segments',
    toAgent: 'customer-profiler',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
    status: 'delivered',
  },
];

export function EnricherWorkspace() {
  const [activeTab, setActiveTab] = useState('profile');
  const [isRunning, setIsRunning] = useState(false);

  const agent = AGENTS.find((a) => a.id === 'company-enricher')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const tabs = [
    { id: 'profile', label: 'Company Profile', icon: '🏢' },
    { id: 'products', label: 'Products', badge: MOCK_ENRICHMENT.products.length, icon: '📦' },
    { id: 'discoveries', label: 'A2A Discoveries', badge: MOCK_DISCOVERIES.length, icon: '📡' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
  ];

  return (
    <AgentWorkspace
      agent={agent}
      status="active"
      lastRun={MOCK_ENRICHMENT.lastEnriched}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          {/* Enrichment Status */}
          <Card className="border-l-4 border-l-green-500">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Enrichment Complete</h3>
                <p className="text-white/60 text-sm">
                  Last updated {formatTimeAgo(MOCK_ENRICHMENT.lastEnriched)}
                </p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-green-400">
                  {Math.round(MOCK_ENRICHMENT.confidence * 100)}%
                </div>
                <p className="text-xs text-white/50">confidence</p>
              </div>
            </div>
          </Card>

          {/* Company Info */}
          <div className="grid grid-cols-2 gap-6">
            <Card>
              <h3 className="text-lg font-semibold text-white mb-4">Company Information</h3>
              <div className="space-y-3">
                <InfoRow label="Name" value={MOCK_ENRICHMENT.company.name} />
                <InfoRow label="Website" value={MOCK_ENRICHMENT.company.website} isLink />
                <InfoRow label="Description" value={MOCK_ENRICHMENT.company.description} />
                <InfoRow label="Founded" value={MOCK_ENRICHMENT.company.founded} />
                <InfoRow label="Headquarters" value={MOCK_ENRICHMENT.company.headquarters} />
                <InfoRow label="Employees" value={MOCK_ENRICHMENT.company.employeeCount} />
                <InfoRow label="Funding" value={MOCK_ENRICHMENT.company.funding} />
              </div>
            </Card>

            <div className="space-y-6">
              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">Tech Stack</h3>
                <div className="flex flex-wrap gap-2">
                  {MOCK_ENRICHMENT.techStack.map((tech) => (
                    <Badge key={tech} variant="default">
                      {tech}
                    </Badge>
                  ))}
                </div>
              </Card>

              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">Discovered Competitors</h3>
                <div className="space-y-2">
                  {MOCK_ENRICHMENT.discoveredCompetitors.map((comp) => (
                    <div
                      key={comp}
                      className="flex items-center justify-between p-2 bg-white/5 rounded"
                    >
                      <span className="text-white">{comp}</span>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">Target Markets</h3>
                <div className="flex flex-wrap gap-2">
                  {MOCK_ENRICHMENT.targetMarkets.map((market) => (
                    <Badge key={market} variant="info">
                      {market}
                    </Badge>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* Products Tab */}
      {activeTab === 'products' && (
        <div className="space-y-4">
          {MOCK_ENRICHMENT.products.map((product, i) => (
            <Card key={i}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-white font-semibold">{product.name}</h4>
                    <Badge variant={product.type === 'Primary' ? 'success' : 'default'}>
                      {product.type}
                    </Badge>
                  </div>
                  <p className="text-white/60 text-sm mt-1">{product.description}</p>
                </div>
                <Button variant="ghost" size="sm">
                  Edit
                </Button>
              </div>
            </Card>
          ))}
          <Button variant="ghost" className="w-full">
            + Add Product
          </Button>
        </div>
      )}

      {/* A2A Discoveries Tab */}
      {activeTab === 'discoveries' && (
        <div className="space-y-4">
          <Card className="bg-purple-500/10 border-purple-500/30">
            <div className="flex items-center gap-3">
              <span className="text-2xl">📡</span>
              <div>
                <h3 className="text-white font-semibold">Agent-to-Agent Communication</h3>
                <p className="text-white/60 text-sm">
                  This agent shares discoveries with other agents to enhance their analysis
                </p>
              </div>
            </div>
          </Card>

          {MOCK_DISCOVERIES.map((discovery) => {
            const targetAgent = AGENTS.find((a) => a.id === discovery.toAgent);
            return (
              <Card key={discovery.id}>
                <div className="flex items-center gap-4">
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{
                      background: `linear-gradient(135deg, rgba(${agent.color}, 0.2), rgba(${agent.color}, 0.1))`,
                    }}
                  >
                    {agent.avatar}
                  </div>
                  <div className="flex-1">
                    <p className="text-white font-medium">{discovery.title}</p>
                    <p className="text-xs text-white/50">{formatTimeAgo(discovery.timestamp)}</p>
                  </div>
                  <div className="text-white/50">→</div>
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{
                      background: targetAgent
                        ? `linear-gradient(135deg, rgba(${targetAgent.color}, 0.2), rgba(${targetAgent.color}, 0.1))`
                        : 'rgba(255,255,255,0.1)',
                    }}
                  >
                    {targetAgent?.avatar || '?'}
                  </div>
                  <div className="text-right">
                    <p className="text-white text-sm">{targetAgent?.name}</p>
                    <Badge variant="success">{discovery.status}</Badge>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <EmptyState
          icon="📜"
          title="Enrichment History"
          description="View past enrichment runs and how the profile has evolved over time."
        />
      )}

      {/* Configure Tab */}
      {activeTab === 'configure' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Enrichment Sources</h3>
            <div className="space-y-4">
              <SettingItem label="Website Scraping" value="Enabled" />
              <SettingItem label="Perplexity AI" value="Enabled" />
              <SettingItem label="LinkedIn" value="Not configured" />
              <SettingItem label="Crunchbase" value="Not configured" />
            </div>
          </Card>
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">A2A Settings</h3>
            <div className="space-y-4">
              <SettingItem label="Auto-share discoveries" value="Enabled" />
              <SettingItem label="Confidence threshold" value="70%" />
              <SettingItem label="Broadcast to all agents" value="Yes" />
            </div>
          </Card>
        </div>
      )}
    </AgentWorkspace>
  );
}

function InfoRow({ label, value, isLink }: { label: string; value: string; isLink?: boolean }) {
  return (
    <div className="flex justify-between py-1 border-b border-white/10 last:border-0">
      <span className="text-white/50">{label}</span>
      {isLink ? (
        <a
          href={`https://${value}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          {value}
        </a>
      ) : (
        <span className="text-white">{value}</span>
      )}
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

function formatTimeAgo(date: Date): string {
  const diff = Date.now() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
