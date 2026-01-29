/**
 * Customer Profiler Workspace
 *
 * ICP development, buyer personas, and customer segmentation.
 * Connected to real backend API.
 */

import { useState } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import {
  Card,
  Badge,
  Button,
  EmptyState,
  ICPListLoading,
  ErrorState,
} from '../components/common';
import { AGENTS } from '../types';
import { useCompanyId } from '../context/CompanyContext';
import { useICPs } from '../hooks/useApi';
import type { ICP, Persona } from '../api/workspaces';

export function CustomerWorkspace() {
  const companyId = useCompanyId();
  const [activeTab, setActiveTab] = useState('icps');
  const [selectedICPId, setSelectedICPId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Fetch ICPs from API
  const { data: icpData, isLoading, error, refresh } = useICPs(companyId);

  const agent = AGENTS.find((a) => a.id === 'customer-profiler')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    refresh();
    setIsRunning(false);
  };

  const icps = icpData?.icps || [];
  const selectedICP = icps.find((icp) => icp.id === selectedICPId);

  // Auto-select first ICP if none selected
  if (!selectedICPId && icps.length > 0) {
    setSelectedICPId(icps[0].id);
  }

  const tabs = [
    { id: 'icps', label: 'ICPs', badge: icps.length, icon: '🎯' },
    { id: 'personas', label: 'Personas', badge: icpData?.total_personas || 0, icon: '👥' },
    { id: 'segments', label: 'Segments', icon: '📊' },
    { id: 'journey', label: 'Buyer Journey', icon: '🗺️' },
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
        <ICPListLoading />
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
          title="Failed to load customer profiles"
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
          description="Please complete onboarding to define your ideal customers."
        />
      </AgentWorkspace>
    );
  }

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
      {/* ICPs Tab */}
      {activeTab === 'icps' && (
        <div className="grid grid-cols-3 gap-6">
          {/* ICP List */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-white/70">Ideal Customer Profiles</h3>
            {icps.length === 0 ? (
              <EmptyState
                icon="🎯"
                title="No ICPs Yet"
                description="Run the customer profiler to generate ICPs."
                action={{ label: 'Generate ICPs', onClick: handleRun }}
              />
            ) : (
              <>
                {icps.map((icp) => (
                  <ICPCard
                    key={icp.id}
                    icp={icp}
                    isSelected={selectedICPId === icp.id}
                    onClick={() => setSelectedICPId(icp.id)}
                  />
                ))}
                <Button variant="ghost" className="w-full">
                  + Create ICP
                </Button>
              </>
            )}
          </div>

          {/* ICP Details */}
          <div className="col-span-2 space-y-4">
            {selectedICP ? (
              <ICPDetails icp={selectedICP} />
            ) : (
              <EmptyState
                icon="🎯"
                title="Select an ICP"
                description="Choose an ICP to view details"
              />
            )}
          </div>
        </div>
      )}

      {/* Personas Tab */}
      {activeTab === 'personas' && (
        <div className="space-y-6">
          {icps.length === 0 ? (
            <EmptyState
              icon="👥"
              title="No Personas Yet"
              description="Create ICPs first, then add personas to each."
            />
          ) : (
            <div className="grid grid-cols-2 gap-6">
              {icps.flatMap((icp) =>
                icp.personas.map((persona) => (
                  <PersonaCard key={persona.id} persona={persona} icpName={icp.name} />
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Segments Tab */}
      {activeTab === 'segments' && (
        <EmptyState
          icon="📊"
          title="Customer Segments"
          description="Segment analysis based on behavior, engagement, and value. Run analysis to generate segments."
          action={{ label: 'Generate Segments', onClick: handleRun }}
        />
      )}

      {/* Journey Tab */}
      {activeTab === 'journey' && (
        <Card>
          <h3 className="text-lg font-semibold text-white mb-4">Buyer Journey Map</h3>
          <div className="flex items-center justify-between">
            {['Awareness', 'Consideration', 'Decision', 'Onboarding', 'Expansion'].map(
              (stage, i) => (
                <div key={stage} className="flex items-center">
                  <div className="text-center">
                    <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center text-2xl mb-2">
                      {['👀', '🤔', '✅', '🚀', '📈'][i]}
                    </div>
                    <p className="text-sm text-white">{stage}</p>
                    <p className="text-xs text-white/50">~{[7, 14, 7, 30, 90][i]} days</p>
                  </div>
                  {i < 4 && <div className="w-12 h-0.5 bg-white/20 mx-2" />}
                </div>
              )
            )}
          </div>
        </Card>
      )}

      {/* Configure Tab */}
      {activeTab === 'configure' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">ICP Scoring Weights</h3>
            <div className="space-y-4">
              <SettingItem label="Company Size" value="25%" />
              <SettingItem label="Industry Fit" value="30%" />
              <SettingItem label="Tech Stack" value="20%" />
              <SettingItem label="Budget Signals" value="25%" />
            </div>
          </Card>
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Data Sources</h3>
            <div className="space-y-4">
              <SettingItem label="CRM Integration" value="HubSpot" />
              <SettingItem label="Enrichment" value="Perplexity AI" />
              <SettingItem label="Intent Data" value="Not configured" />
            </div>
          </Card>
        </div>
      )}
    </AgentWorkspace>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface ICPCardProps {
  icp: ICP;
  isSelected: boolean;
  onClick: () => void;
}

function ICPCard({ icp, isSelected, onClick }: ICPCardProps) {
  return (
    <Card
      className={`cursor-pointer transition-colors ${
        isSelected ? 'border-purple-500 bg-purple-500/10' : 'hover:bg-white/5'
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-white font-medium">{icp.name}</h4>
          <p className="text-white/50 text-xs mt-1">
            {icp.matching_companies_count} companies match
          </p>
        </div>
        <div className="text-right">
          <div
            className={`text-lg font-bold ${
              icp.fit_score >= 90
                ? 'text-green-400'
                : icp.fit_score >= 80
                ? 'text-amber-400'
                : 'text-white'
            }`}
          >
            {icp.fit_score}%
          </div>
          <p className="text-xs text-white/40">fit score</p>
        </div>
      </div>
    </Card>
  );
}

interface ICPDetailsProps {
  icp: ICP;
}

function ICPDetails({ icp }: ICPDetailsProps) {
  return (
    <>
      <Card>
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white">{icp.name}</h3>
            <p className="text-white/60">{icp.description}</p>
          </div>
          <Badge variant="success">{icp.fit_score}% fit</Badge>
        </div>

        <h4 className="text-sm font-medium text-white/70 mb-2">Characteristics</h4>
        <div className="grid grid-cols-2 gap-2">
          {[
            { key: 'Company Size', value: icp.company_size },
            { key: 'Revenue Range', value: icp.revenue_range },
            { key: 'Industry', value: icp.industry },
            { key: 'Tech Stack', value: icp.tech_stack },
            { key: 'Buying Triggers', value: icp.buying_triggers?.join(', ') },
          ]
            .filter((item) => item.value)
            .map((item) => (
              <div key={item.key} className="bg-white/5 rounded p-2">
                <p className="text-xs text-white/50">{item.key}</p>
                <p className="text-sm text-white">{item.value}</p>
              </div>
            ))}
        </div>
      </Card>

      {icp.pain_points && icp.pain_points.length > 0 && (
        <Card>
          <h4 className="text-sm font-medium text-white/70 mb-3">Pain Points</h4>
          <ul className="space-y-2">
            {icp.pain_points.map((pain, i) => (
              <li key={i} className="flex items-start gap-2 text-white/80">
                <span className="text-red-400">•</span>
                {pain}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {icp.personas && icp.personas.length > 0 && (
        <Card>
          <h4 className="text-sm font-medium text-white/70 mb-3">Associated Personas</h4>
          <div className="flex gap-3 flex-wrap">
            {icp.personas.map((persona) => (
              <div
                key={persona.id}
                className="flex items-center gap-2 bg-white/5 rounded-lg p-2"
              >
                <span className="text-2xl">{persona.avatar || '👤'}</span>
                <div>
                  <p className="text-white text-sm font-medium">{persona.name}</p>
                  <p className="text-white/50 text-xs">{persona.role}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

interface PersonaCardProps {
  persona: Persona;
  icpName: string;
}

function PersonaCard({ persona, icpName }: PersonaCardProps) {
  return (
    <Card>
      <div className="flex items-start gap-4">
        <div className="text-4xl">{persona.avatar || '👤'}</div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white">{persona.name}</h3>
          <p className="text-white/60">{persona.role}</p>
          <div className="mt-1">
            <Badge variant="default">{icpName}</Badge>
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {persona.goals && persona.goals.length > 0 && (
          <div>
            <p className="text-xs text-white/50 mb-1">Goals</p>
            <ul className="text-sm text-white/80 space-y-1">
              {persona.goals.slice(0, 3).map((g, i) => (
                <li key={i}>• {g}</li>
              ))}
            </ul>
          </div>
        )}

        {persona.challenges && persona.challenges.length > 0 && (
          <div>
            <p className="text-xs text-white/50 mb-1">Challenges</p>
            <ul className="text-sm text-white/80 space-y-1">
              {persona.challenges.slice(0, 3).map((c, i) => (
                <li key={i}>• {c}</li>
              ))}
            </ul>
          </div>
        )}

        {persona.preferred_channels && persona.preferred_channels.length > 0 && (
          <div>
            <p className="text-xs text-white/50 mb-1">Preferred Channels</p>
            <div className="flex gap-2 flex-wrap">
              {persona.preferred_channels.map((ch) => (
                <Badge key={ch} variant="default">
                  {ch}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {persona.messaging_hooks && persona.messaging_hooks.length > 0 && (
          <div>
            <p className="text-xs text-white/50 mb-1">Messaging Hooks</p>
            <ul className="text-sm text-green-400 space-y-1">
              {persona.messaging_hooks.slice(0, 3).map((m, i) => (
                <li key={i}>✓ {m}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <Button variant="ghost" size="sm" className="mt-4">
        Edit Persona
      </Button>
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
