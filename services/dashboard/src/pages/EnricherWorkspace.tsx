/**
 * Company Enricher Workspace
 *
 * Website analysis, company profile enrichment, and A2A discovery.
 * Connected to company context for real data.
 */

import { useState } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState, ErrorState } from '../components/common';
import { AGENTS } from '../types';
import { useCompany, useCompanyId } from '../context/CompanyContext';

export function EnricherWorkspace() {
  const companyId = useCompanyId();
  const { company, isLoading: _isLoading, error, refreshCompany } = useCompany();
  const [activeTab, setActiveTab] = useState('profile');
  const [isRunning, setIsRunning] = useState(false);

  const agent = AGENTS.find((a) => a.id === 'company-enricher')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    // In production, this would trigger the company enricher agent
    await refreshCompany();
    setIsRunning(false);
  };

  // Compute enriched data from company context
  const enrichment = company ? {
    company: {
      name: company.name,
      website: company.website || 'Not provided',
      description: company.description || 'Not provided',
      founded: company.founded_year || 'Unknown',
      headquarters: company.headquarters || 'Singapore',
      employeeCount: company.employee_count || 'Unknown',
      funding: company.funding_stage || 'Not disclosed',
    },
    products: company.products || [],
    techStack: company.tech_stack || [],
    discoveredCompetitors: company.competitors || [],
    targetMarkets: company.target_markets || [],
    confidence: company.enrichment_confidence || 0,
    lastEnriched: company.last_enriched_at ? new Date(company.last_enriched_at) : null,
  } : null;

  // Mock A2A discoveries based on company data
  const discoveries = company ? [
    ...(company.products.length > 0 ? [{
      id: '1',
      type: 'company_products',
      title: `Discovered ${company.products.length} product offerings`,
      toAgent: 'campaign-architect',
      timestamp: enrichment?.lastEnriched || new Date(),
      status: 'delivered',
    }] : []),
    ...(company.competitors.length > 0 ? [{
      id: '2',
      type: 'competitor_found',
      title: `Identified ${company.competitors.length} competitors`,
      toAgent: 'competitor-analyst',
      timestamp: enrichment?.lastEnriched || new Date(),
      status: 'delivered',
    }] : []),
    ...(company.tech_stack.length > 0 ? [{
      id: '3',
      type: 'company_tech_stack',
      title: 'Extracted technology stack',
      toAgent: 'lead-hunter',
      timestamp: enrichment?.lastEnriched || new Date(),
      status: 'delivered',
    }] : []),
    ...(company.target_markets.length > 0 ? [{
      id: '4',
      type: 'target_markets',
      title: 'Identified target market segments',
      toAgent: 'customer-profiler',
      timestamp: enrichment?.lastEnriched || new Date(),
      status: 'delivered',
    }] : []),
  ] : [];

  const tabs = [
    { id: 'profile', label: 'Company Profile', icon: '🏢' },
    { id: 'products', label: 'Products', badge: enrichment?.products.length || 0, icon: '📦' },
    { id: 'discoveries', label: 'A2A Discoveries', badge: discoveries.length, icon: '📡' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
  ];

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
          description="Please complete onboarding to enrich your company profile."
        />
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
          title="Failed to load company data"
          message={error.message}
          onRetry={refreshCompany}
        />
      </AgentWorkspace>
    );
  }

  return (
    <AgentWorkspace
      agent={agent}
      status={enrichment?.confidence && enrichment.confidence > 0.5 ? 'active' : 'idle'}
      lastRun={enrichment?.lastEnriched || new Date()}
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
          <Card className={`border-l-4 ${enrichment?.confidence && enrichment.confidence > 0.7 ? 'border-l-green-500' : 'border-l-amber-500'}`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">
                  {enrichment?.confidence && enrichment.confidence > 0.7 ? 'Enrichment Complete' : 'Partial Enrichment'}
                </h3>
                <p className="text-white/60 text-sm">
                  {enrichment?.lastEnriched ? `Last updated ${formatTimeAgo(enrichment.lastEnriched)}` : 'Not yet enriched'}
                </p>
              </div>
              <div className="text-right">
                <div className={`text-2xl font-bold ${enrichment?.confidence && enrichment.confidence > 0.7 ? 'text-green-400' : 'text-amber-400'}`}>
                  {Math.round((enrichment?.confidence || 0) * 100)}%
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
                <InfoRow label="Name" value={enrichment?.company.name || '-'} />
                <InfoRow label="Website" value={enrichment?.company.website || '-'} isLink={!!company?.website} />
                <InfoRow label="Description" value={enrichment?.company.description || '-'} />
                <InfoRow label="Founded" value={enrichment?.company.founded || '-'} />
                <InfoRow label="Headquarters" value={enrichment?.company.headquarters || '-'} />
                <InfoRow label="Employees" value={enrichment?.company.employeeCount || '-'} />
                <InfoRow label="Funding" value={enrichment?.company.funding || '-'} />
              </div>
            </Card>

            <div className="space-y-6">
              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">Tech Stack</h3>
                {enrichment?.techStack && enrichment.techStack.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {enrichment.techStack.map((tech) => (
                      <Badge key={tech} variant="default">
                        {tech}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-white/50 text-sm">No tech stack data yet. Run enrichment to discover.</p>
                )}
              </Card>

              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">Discovered Competitors</h3>
                {enrichment?.discoveredCompetitors && enrichment.discoveredCompetitors.length > 0 ? (
                  <div className="space-y-2">
                    {enrichment.discoveredCompetitors.map((comp) => (
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
                ) : (
                  <p className="text-white/50 text-sm">No competitors discovered yet. Run enrichment to identify.</p>
                )}
              </Card>

              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">Target Markets</h3>
                {enrichment?.targetMarkets && enrichment.targetMarkets.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {enrichment.targetMarkets.map((market) => (
                      <Badge key={market} variant="info">
                        {market}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-white/50 text-sm">No target markets defined yet.</p>
                )}
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* Products Tab */}
      {activeTab === 'products' && (
        <div className="space-y-4">
          {enrichment?.products && enrichment.products.length > 0 ? (
            <>
              {enrichment.products.map((product, i) => (
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
            </>
          ) : (
            <EmptyState
              icon="📦"
              title="No Products Found"
              description="Run the company enricher to discover products from your website."
              action={{ label: 'Run Enrichment', onClick: handleRun }}
            />
          )}
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

          {discoveries.length > 0 ? (
            discoveries.map((discovery) => {
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
            })
          ) : (
            <EmptyState
              icon="📡"
              title="No Discoveries Yet"
              description="Run the company enricher to generate discoveries for other agents."
              action={{ label: 'Run Enrichment', onClick: handleRun }}
            />
          )}
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
      {isLink && value !== '-' ? (
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
