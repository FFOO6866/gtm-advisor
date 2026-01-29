/**
 * Customer Profiler Workspace
 *
 * ICP development, buyer personas, and customer segmentation.
 */

import { useState } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS } from '../types';

// Mock ICP data
const MOCK_ICPS = [
  {
    id: '1',
    name: 'Growth-Stage SaaS',
    fitScore: 92,
    description: 'Series A-B SaaS companies in Singapore looking to scale their GTM',
    characteristics: {
      companySize: '20-100 employees',
      revenue: 'SGD 2-10M ARR',
      industry: 'B2B SaaS',
      techStack: 'Modern (Cloud-native)',
      buyingTriggers: ['New funding round', 'Hiring sales team', 'Expanding to APAC'],
    },
    painPoints: [
      'Manual lead qualification taking too much time',
      'Inconsistent messaging across channels',
      'Lack of market intelligence for Singapore',
    ],
    count: 156,
  },
  {
    id: '2',
    name: 'Fintech Innovators',
    fitScore: 87,
    description: 'Fintech startups targeting SME banking and payments',
    characteristics: {
      companySize: '10-50 employees',
      revenue: 'SGD 1-5M ARR',
      industry: 'Fintech',
      techStack: 'API-first, Cloud',
      buyingTriggers: ['MAS license approval', 'Partnership announcements', 'New product launch'],
    },
    painPoints: [
      'Complex regulatory requirements for marketing',
      'Need to build trust quickly',
      'Limited marketing budget',
    ],
    count: 89,
  },
];

// Mock personas
const MOCK_PERSONAS = [
  {
    id: '1',
    name: 'Marketing Michelle',
    role: 'Head of Marketing',
    icpId: '1',
    avatar: '👩‍💼',
    demographics: {
      age: '30-40',
      experience: '8-12 years',
      education: 'MBA or Marketing degree',
    },
    goals: [
      'Prove marketing ROI to leadership',
      'Scale demand generation efficiently',
      'Build predictable pipeline',
    ],
    challenges: [
      'Limited team and budget',
      'Pressure to show quick wins',
      'Keeping up with AI tools',
    ],
    preferredChannels: ['LinkedIn', 'Email', 'Webinars'],
    objections: ['Is this just another AI hype tool?', "How is this different from what we're doing?"],
    messagingHooks: [
      'Save 10+ hours/week on market research',
      'Get Singapore-specific insights',
      'AI that actually understands B2B',
    ],
  },
  {
    id: '2',
    name: 'Founder Frank',
    role: 'CEO / Founder',
    icpId: '1',
    avatar: '👨‍💻',
    demographics: {
      age: '35-45',
      experience: '15+ years (often technical)',
      education: 'Engineering or MBA',
    },
    goals: ['Accelerate growth for next funding round', 'Build scalable GTM engine', 'Reduce CAC'],
    challenges: [
      'Wearing too many hats',
      'No dedicated marketing expertise',
      'Need to move fast',
    ],
    preferredChannels: ['LinkedIn', 'Referrals', 'Tech communities'],
    objections: ['I can just use ChatGPT', 'We need to focus on product first'],
    messagingHooks: [
      'GTM expertise on autopilot',
      'Used by 50+ Singapore startups',
      'PSG grant eligible',
    ],
  },
];

export function CustomerWorkspace() {
  const [activeTab, setActiveTab] = useState('icps');
  const [selectedICP, setSelectedICP] = useState<string | null>(MOCK_ICPS[0].id);
  const [isRunning, setIsRunning] = useState(false);

  const agent = AGENTS.find((a) => a.id === 'customer-profiler')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const tabs = [
    { id: 'icps', label: 'ICPs', badge: MOCK_ICPS.length, icon: '🎯' },
    { id: 'personas', label: 'Personas', badge: MOCK_PERSONAS.length, icon: '👥' },
    { id: 'segments', label: 'Segments', icon: '📊' },
    { id: 'journey', label: 'Buyer Journey', icon: '🗺️' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
  ];

  const selectedICPData = MOCK_ICPS.find((icp) => icp.id === selectedICP);
  const icpPersonas = MOCK_PERSONAS.filter((p) => p.icpId === selectedICP);

  return (
    <AgentWorkspace
      agent={agent}
      status="active"
      lastRun={new Date(Date.now() - 12 * 60 * 60 * 1000)}
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
            {MOCK_ICPS.map((icp) => (
              <Card
                key={icp.id}
                className={`cursor-pointer transition-colors ${
                  selectedICP === icp.id
                    ? 'border-purple-500 bg-purple-500/10'
                    : 'hover:bg-white/5'
                }`}
                onClick={() => setSelectedICP(icp.id)}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-white font-medium">{icp.name}</h4>
                    <p className="text-white/50 text-xs mt-1">{icp.count} companies match</p>
                  </div>
                  <div className="text-right">
                    <div
                      className={`text-lg font-bold ${
                        icp.fitScore >= 90
                          ? 'text-green-400'
                          : icp.fitScore >= 80
                          ? 'text-amber-400'
                          : 'text-white'
                      }`}
                    >
                      {icp.fitScore}%
                    </div>
                    <p className="text-xs text-white/40">fit score</p>
                  </div>
                </div>
              </Card>
            ))}
            <Button variant="ghost" className="w-full">
              + Create ICP
            </Button>
          </div>

          {/* ICP Details */}
          <div className="col-span-2 space-y-4">
            {selectedICPData ? (
              <>
                <Card>
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-white">{selectedICPData.name}</h3>
                      <p className="text-white/60">{selectedICPData.description}</p>
                    </div>
                    <Badge variant="success">{selectedICPData.fitScore}% fit</Badge>
                  </div>

                  <h4 className="text-sm font-medium text-white/70 mb-2">Characteristics</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(selectedICPData.characteristics).map(([key, value]) => (
                      <div key={key} className="bg-white/5 rounded p-2">
                        <p className="text-xs text-white/50 capitalize">
                          {key.replace(/([A-Z])/g, ' $1')}
                        </p>
                        <p className="text-sm text-white">
                          {Array.isArray(value) ? value.join(', ') : value}
                        </p>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card>
                  <h4 className="text-sm font-medium text-white/70 mb-3">Pain Points</h4>
                  <ul className="space-y-2">
                    {selectedICPData.painPoints.map((pain, i) => (
                      <li key={i} className="flex items-start gap-2 text-white/80">
                        <span className="text-red-400">•</span>
                        {pain}
                      </li>
                    ))}
                  </ul>
                </Card>

                <Card>
                  <h4 className="text-sm font-medium text-white/70 mb-3">Associated Personas</h4>
                  <div className="flex gap-3">
                    {icpPersonas.map((persona) => (
                      <div
                        key={persona.id}
                        className="flex items-center gap-2 bg-white/5 rounded-lg p-2"
                      >
                        <span className="text-2xl">{persona.avatar}</span>
                        <div>
                          <p className="text-white text-sm font-medium">{persona.name}</p>
                          <p className="text-white/50 text-xs">{persona.role}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </>
            ) : (
              <EmptyState icon="🎯" title="Select an ICP" description="Choose an ICP to view details" />
            )}
          </div>
        </div>
      )}

      {/* Personas Tab */}
      {activeTab === 'personas' && (
        <div className="grid grid-cols-2 gap-6">
          {MOCK_PERSONAS.map((persona) => (
            <Card key={persona.id}>
              <div className="flex items-start gap-4">
                <div className="text-4xl">{persona.avatar}</div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-white">{persona.name}</h3>
                  <p className="text-white/60">{persona.role}</p>
                  <div className="mt-1">
                    <Badge variant="default">
                      {MOCK_ICPS.find((i) => i.id === persona.icpId)?.name}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <div>
                  <p className="text-xs text-white/50 mb-1">Goals</p>
                  <ul className="text-sm text-white/80 space-y-1">
                    {persona.goals.map((g, i) => (
                      <li key={i}>• {g}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <p className="text-xs text-white/50 mb-1">Challenges</p>
                  <ul className="text-sm text-white/80 space-y-1">
                    {persona.challenges.map((c, i) => (
                      <li key={i}>• {c}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <p className="text-xs text-white/50 mb-1">Preferred Channels</p>
                  <div className="flex gap-2">
                    {persona.preferredChannels.map((ch) => (
                      <Badge key={ch} variant="default">
                        {ch}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-white/50 mb-1">Messaging Hooks</p>
                  <ul className="text-sm text-green-400 space-y-1">
                    {persona.messagingHooks.map((m, i) => (
                      <li key={i}>✓ {m}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <Button variant="ghost" size="sm" className="mt-4">
                Edit Persona
              </Button>
            </Card>
          ))}
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

function SettingItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-white/70">{label}</span>
      <span className="text-white font-medium">{value}</span>
    </div>
  );
}
