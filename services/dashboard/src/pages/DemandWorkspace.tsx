/**
 * Qualified Demand Agent Workspace
 *
 * Lead management, intent signals, and pipeline analysis.
 */

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  TrendingUp,
  Mail,
  Linkedin,
  Building,
  MapPin,
  ExternalLink,
  Shield,
  Filter,
} from 'lucide-react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS, type Lead } from '../types';

// Mock leads data
const MOCK_LEADS: (Lead & { intentSignals: string[]; fitReasons: string[]; pdpaStatus: string })[] = [
  {
    id: '1',
    companyName: 'TechVentures Pte Ltd',
    contactName: 'Sarah Chen',
    contactTitle: 'Chief Technology Officer',
    contactEmail: 's.chen@techventures.sg',
    industry: 'fintech',
    employeeCount: 75,
    location: 'Singapore',
    website: 'techventures.sg',
    fitScore: 0.92,
    intentScore: 0.88,
    overallScore: 0.92,
    painPoints: ['Scaling marketing without headcount', 'Competitive pressure', 'Manual campaign execution'],
    triggerEvents: ['Series A raised ($5M)', 'Job posting: Head of Marketing'],
    recommendedApproach: 'Reference their Series A and growth trajectory. Offer a 15-min demo focused on scaling marketing without headcount.',
    source: 'LinkedIn + News',
    intentSignals: ['Visited pricing page 3x this week', 'Downloaded enterprise whitepaper', 'CTO engaged with 2 LinkedIn posts'],
    fitReasons: ['Matches ICP: Fintech, growth stage, Singapore HQ', 'Recently raised Series A ($5M)', 'Building marketing team'],
    pdpaStatus: 'Consent verified',
  },
  {
    id: '2',
    companyName: 'DataFlow Analytics',
    contactName: 'Michael Tan',
    contactTitle: 'VP of Marketing',
    contactEmail: 'm.tan@dataflow.io',
    industry: 'saas',
    employeeCount: 45,
    location: 'Singapore',
    website: 'dataflow.io',
    fitScore: 0.85,
    intentScore: 0.82,
    overallScore: 0.87,
    painPoints: ['Agency costs too high', 'Slow campaign turnaround'],
    triggerEvents: ['New VP Marketing hired', 'Expanding to Malaysia'],
    recommendedApproach: 'Focus on agency replacement value prop. Mention Malaysia expansion capabilities.',
    source: 'Perplexity Research',
    intentSignals: ['Visited competitor comparison page', 'Signed up for newsletter'],
    fitReasons: ['SaaS company in growth phase', 'Marketing leadership change'],
    pdpaStatus: 'Consent verified',
  },
  {
    id: '3',
    companyName: 'GreenTech Solutions',
    contactName: 'Amanda Lee',
    contactTitle: 'Marketing Director',
    contactEmail: null,
    industry: 'other',
    employeeCount: 120,
    location: 'Singapore',
    website: 'greentech.com.sg',
    fitScore: 0.72,
    intentScore: 0.68,
    overallScore: 0.74,
    painPoints: ['Limited marketing budget', 'Need to prove ROI'],
    triggerEvents: ['PSG grant application'],
    recommendedApproach: 'Lead with PSG grant eligibility and ROI tracking capabilities.',
    source: 'News',
    intentSignals: ['General website traffic from company IP'],
    fitReasons: ['Singapore-based', 'Applying for government grants'],
    pdpaStatus: 'Consent pending',
  },
];

export function DemandWorkspace() {
  const [activeTab, setActiveTab] = useState('sales-ready');
  const [isRunning, setIsRunning] = useState(false);
  const [selectedLead, setSelectedLead] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium'>('all');

  const agent = AGENTS.find((a) => a.id === 'lead-hunter')!;

  const filteredLeads = useMemo(() => {
    if (filter === 'all') return MOCK_LEADS;
    if (filter === 'high') return MOCK_LEADS.filter((l) => l.overallScore >= 0.85);
    return MOCK_LEADS.filter((l) => l.overallScore >= 0.7 && l.overallScore < 0.85);
  }, [filter]);

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const totalPipelineValue = MOCK_LEADS.reduce((sum, lead) => sum + lead.overallScore * 50000, 0);

  const tabs = [
    { id: 'sales-ready', label: 'Sales Ready', badge: MOCK_LEADS.filter((l) => l.overallScore >= 0.85).length, icon: '🎯' },
    { id: 'all-accounts', label: 'All Accounts', badge: MOCK_LEADS.length, icon: '📋' },
    { id: 'intent-signals', label: 'Intent Signals', icon: '📡' },
    { id: 'pipeline', label: 'Pipeline Analysis', icon: '📊' },
    { id: 'scoring', label: 'Configure Scoring', icon: '⚙️' },
  ];

  return (
    <AgentWorkspace
      agent={agent}
      status="active"
      lastRun={new Date(Date.now() - 4 * 60 * 60 * 1000)}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Sales Ready Tab */}
      {(activeTab === 'sales-ready' || activeTab === 'all-accounts') && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-4 gap-4">
            <StatCard
              icon={<Users className="w-5 h-5 text-blue-400" />}
              value={MOCK_LEADS.length}
              label="Total Accounts"
            />
            <StatCard
              icon={<TrendingUp className="w-5 h-5 text-green-400" />}
              value={MOCK_LEADS.filter((l) => l.overallScore >= 0.85).length}
              label="Sales Ready"
            />
            <StatCard
              icon={<Shield className="w-5 h-5 text-purple-400" />}
              value={MOCK_LEADS.filter((l) => l.pdpaStatus === 'Consent verified').length}
              label="PDPA Verified"
            />
            <StatCard
              value={`SGD ${(totalPipelineValue / 1000).toFixed(0)}K`}
              label="Pipeline Value"
            />
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-white/50" />
            {(['all', 'high', 'medium'] as const).map((f) => (
              <Button
                key={f}
                variant={filter === f ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setFilter(f)}
              >
                {f === 'all' ? 'All' : f === 'high' ? 'High Score (85%+)' : 'Medium Score'}
              </Button>
            ))}
          </div>

          {/* Lead Cards */}
          <div className="space-y-4">
            {filteredLeads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                isExpanded={selectedLead === lead.id}
                onToggle={() => setSelectedLead(selectedLead === lead.id ? null : lead.id)}
              />
            ))}
          </div>

          {filteredLeads.length === 0 && (
            <EmptyState
              icon="🔍"
              title="No accounts found"
              description="Try adjusting your filters or run the agent to find new prospects."
              action={{ label: 'Run Agent', onClick: handleRun }}
            />
          )}
        </div>
      )}

      {/* Intent Signals Tab */}
      {activeTab === 'intent-signals' && (
        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Recent Intent Signals</h3>
            <div className="space-y-3">
              {MOCK_LEADS.flatMap((lead) =>
                lead.intentSignals.map((signal, idx) => (
                  <div key={`${lead.id}-${idx}`} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                    <span className="text-lg">📡</span>
                    <div className="flex-1">
                      <p className="text-white">{signal}</p>
                      <p className="text-sm text-white/50">{lead.companyName}</p>
                    </div>
                    <Button variant="ghost" size="sm">
                      View Account
                    </Button>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Pipeline Analysis Tab */}
      {activeTab === 'pipeline' && (
        <div className="space-y-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Pipeline Summary</h3>
            <div className="text-3xl font-bold text-white mb-2">
              SGD {totalPipelineValue.toLocaleString()}
            </div>
            <p className="text-white/60">Total pipeline value across {MOCK_LEADS.length} accounts</p>

            {/* Pipeline Stages */}
            <div className="mt-6 space-y-3">
              <PipelineStage
                label="Sales Ready"
                count={MOCK_LEADS.filter((l) => l.overallScore >= 0.85).length}
                value={MOCK_LEADS.filter((l) => l.overallScore >= 0.85).reduce((s, l) => s + l.overallScore * 50000, 0)}
                percentage={45}
                color="bg-green-500"
              />
              <PipelineStage
                label="Nurturing"
                count={MOCK_LEADS.filter((l) => l.overallScore >= 0.7 && l.overallScore < 0.85).length}
                value={MOCK_LEADS.filter((l) => l.overallScore >= 0.7 && l.overallScore < 0.85).reduce((s, l) => s + l.overallScore * 50000, 0)}
                percentage={35}
                color="bg-amber-500"
              />
              <PipelineStage
                label="New"
                count={MOCK_LEADS.filter((l) => l.overallScore < 0.7).length}
                value={MOCK_LEADS.filter((l) => l.overallScore < 0.7).reduce((s, l) => s + l.overallScore * 50000, 0)}
                percentage={20}
                color="bg-blue-500"
              />
            </div>
          </Card>

          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Conversion Bottlenecks</h3>
            <p className="text-white/60">
              Analysis shows 3 accounts stuck in nurturing stage for 30+ days. Recommended action:
              personalized outreach or content refresh.
            </p>
            <Button variant="secondary" className="mt-4">
              View Stuck Accounts
            </Button>
          </Card>
        </div>
      )}

      {/* Configure Scoring Tab */}
      {activeTab === 'scoring' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">ICP Criteria (Fit Score)</h3>
            <div className="space-y-4">
              <ScoringCriteria label="Industry Match" weight={25} />
              <ScoringCriteria label="Company Size" weight={20} />
              <ScoringCriteria label="Location" weight={15} />
              <ScoringCriteria label="Growth Stage" weight={20} />
              <ScoringCriteria label="Technology Fit" weight={20} />
            </div>
          </Card>

          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Intent Signals (Intent Score)</h3>
            <div className="space-y-4">
              <ScoringCriteria label="Website Visits" weight={30} />
              <ScoringCriteria label="Content Downloads" weight={25} />
              <ScoringCriteria label="Email Engagement" weight={20} />
              <ScoringCriteria label="Social Engagement" weight={15} />
              <ScoringCriteria label="Demo Requests" weight={10} />
            </div>
          </Card>
        </div>
      )}
    </AgentWorkspace>
  );
}

// Helper Components

interface StatCardProps {
  icon?: React.ReactNode;
  value: string | number;
  label: string;
}

function StatCard({ icon, value, label }: StatCardProps) {
  return (
    <Card padding="sm">
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <div className="text-xl font-bold text-white">{value}</div>
          <div className="text-xs text-white/50">{label}</div>
        </div>
      </div>
    </Card>
  );
}

interface LeadCardProps {
  lead: Lead & { intentSignals: string[]; fitReasons: string[]; pdpaStatus: string };
  isExpanded: boolean;
  onToggle: () => void;
}

function LeadCard({ lead, isExpanded, onToggle }: LeadCardProps) {
  const scoreColor = lead.overallScore >= 0.85 ? 'text-green-400' : lead.overallScore >= 0.7 ? 'text-amber-400' : 'text-blue-400';
  const scoreBg = lead.overallScore >= 0.85 ? 'bg-green-500/20' : lead.overallScore >= 0.7 ? 'bg-amber-500/20' : 'bg-blue-500/20';

  return (
    <Card className={isExpanded ? 'ring-1 ring-purple-500/50' : ''}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className={`w-12 h-12 rounded-lg ${scoreBg} flex items-center justify-center`}>
            <span className={`text-lg font-bold ${scoreColor}`}>{Math.round(lead.overallScore * 100)}</span>
          </div>
          <div>
            <h4 className="font-semibold text-white">{lead.companyName}</h4>
            <div className="flex items-center gap-3 mt-1 text-sm text-white/60">
              <span className="flex items-center gap-1">
                <Building className="w-3 h-3" />
                {lead.industry}
              </span>
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                {lead.employeeCount} employees
              </span>
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {lead.location}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={lead.pdpaStatus === 'Consent verified' ? 'success' : 'warning'}>
            <Shield className="w-3 h-3 mr-1" />
            {lead.pdpaStatus}
          </Badge>
          <Button variant="ghost" size="sm" onClick={onToggle}>
            {isExpanded ? '▲' : '▼'}
          </Button>
        </div>
      </div>

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-4 pt-4 border-t border-white/10">
              {/* Contact Info */}
              {lead.contactName && (
                <div className="mb-4 p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-white">{lead.contactName}</p>
                      <p className="text-sm text-white/60">{lead.contactTitle}</p>
                    </div>
                    <div className="flex gap-2">
                      {lead.contactEmail && (
                        <Button variant="ghost" size="sm" leftIcon={<Mail className="w-3 h-3" />}>
                          Email
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" leftIcon={<Linkedin className="w-3 h-3" />}>
                        LinkedIn
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Intent Signals */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Intent Signals</h5>
                  <ul className="space-y-1">
                    {lead.intentSignals.map((signal, idx) => (
                      <li key={idx} className="text-sm text-white/80 flex items-start gap-2">
                        <span className="text-green-400">•</span>
                        {signal}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Fit Reasons</h5>
                  <ul className="space-y-1">
                    {lead.fitReasons.map((reason, idx) => (
                      <li key={idx} className="text-sm text-white/80 flex items-start gap-2">
                        <span className="text-blue-400">•</span>
                        {reason}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Recommended Approach */}
              {lead.recommendedApproach && (
                <div className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/20 mb-4">
                  <h5 className="text-xs font-medium text-purple-400 uppercase mb-1">Recommended Approach</h5>
                  <p className="text-sm text-white/80">{lead.recommendedApproach}</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <Button variant="primary" size="sm">
                  Generate Outreach Email
                </Button>
                <Button variant="secondary" size="sm">
                  Add to CRM
                </Button>
                <Button variant="ghost" size="sm" rightIcon={<ExternalLink className="w-3 h-3" />}>
                  View Full Profile
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

interface PipelineStageProps {
  label: string;
  count: number;
  value: number;
  percentage: number;
  color: string;
}

function PipelineStage({ label, count, value, percentage, color }: PipelineStageProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-white/80">{label} ({count})</span>
        <span className="text-white/60">SGD {value.toLocaleString()}</span>
      </div>
      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
        <motion.div
          className={`h-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>
    </div>
  );
}

function ScoringCriteria({ label, weight }: { label: string; weight: number }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-white/70">{label}</span>
      <div className="flex items-center gap-2">
        <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
          <div className="h-full bg-purple-500" style={{ width: `${weight}%` }} />
        </div>
        <span className="text-white text-sm w-8">{weight}%</span>
      </div>
    </div>
  );
}
