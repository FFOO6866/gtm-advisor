/**
 * Qualified Demand Agent Workspace
 *
 * Lead management, intent signals, and pipeline analysis.
 * Connected to real backend API.
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
import {
  Card,
  Badge,
  Button,
  EmptyState,
  LeadListLoading,
  ErrorState,
} from '../components/common';
import { AGENTS } from '../types';
import { useCompanyId } from '../context/CompanyContext';
import { useLeads, useMutation } from '../hooks/useApi';
import * as api from '../api/workspaces';
import type { Lead, LeadUpdate } from '../api/workspaces';

export function DemandWorkspace() {
  const companyId = useCompanyId();
  const [activeTab, setActiveTab] = useState('sales-ready');
  const [isRunning, setIsRunning] = useState(false);
  const [selectedLead, setSelectedLead] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium'>('all');

  // Fetch leads from API
  const { data: leadData, isLoading, error, refresh } = useLeads(companyId);

  const agent = AGENTS.find((a) => a.id === 'lead-hunter')!;

  // Mutations
  const qualifyMutation = useMutation(
    (leadId: string) => api.qualifyLead(companyId!, leadId),
    {
      invalidateKeys: ['leads'],
      onSuccess: () => refresh(),
    }
  );

  const updateMutation = useMutation(
    ({ leadId, data }: { leadId: string; data: LeadUpdate }) =>
      api.updateLead(companyId!, leadId, data),
    {
      invalidateKeys: ['leads'],
      onSuccess: () => refresh(),
    }
  );

  const leads = leadData?.leads || [];

  const filteredLeads = useMemo(() => {
    if (filter === 'all') return leads;
    if (filter === 'high') return leads.filter((l) => l.overall_score >= 85);
    return leads.filter((l) => l.overall_score >= 70 && l.overall_score < 85);
  }, [filter, leads]);

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    refresh();
    setIsRunning(false);
  };

  const totalPipelineValue = leads.reduce((sum, lead) => sum + (lead.overall_score / 100) * 50000, 0);
  const salesReadyCount = leads.filter((l) => l.overall_score >= 85).length;
  const pdpaVerifiedCount = leads.filter((l) => l.pdpa_consent_status === 'verified').length;

  const tabs = [
    { id: 'sales-ready', label: 'Sales Ready', badge: salesReadyCount, icon: '🎯' },
    { id: 'all-accounts', label: 'All Accounts', badge: leads.length, icon: '📋' },
    { id: 'intent-signals', label: 'Intent Signals', icon: '📡' },
    { id: 'pipeline', label: 'Pipeline Analysis', icon: '📊' },
    { id: 'scoring', label: 'Configure Scoring', icon: '⚙️' },
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
        <LeadListLoading />
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
          title="Failed to load leads"
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
          description="Please complete onboarding to start finding qualified leads."
        />
      </AgentWorkspace>
    );
  }

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
              value={leads.length}
              label="Total Accounts"
            />
            <StatCard
              icon={<TrendingUp className="w-5 h-5 text-green-400" />}
              value={salesReadyCount}
              label="Sales Ready"
            />
            <StatCard
              icon={<Shield className="w-5 h-5 text-purple-400" />}
              value={pdpaVerifiedCount}
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
                onQualify={() => qualifyMutation.execute(lead.id)}
                onUpdateStatus={(status) =>
                  updateMutation.execute({ leadId: lead.id, data: { status } })
                }
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
            {leads.length === 0 ? (
              <EmptyState
                icon="📡"
                title="No Intent Signals"
                description="Run the lead hunter to gather intent signals."
                action={{ label: 'Run Agent', onClick: handleRun }}
              />
            ) : (
              <div className="space-y-3">
                {leads.flatMap((lead) =>
                  (lead.intent_signals || []).map((signal, idx) => (
                    <div key={`${lead.id}-${idx}`} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                      <span className="text-lg">📡</span>
                      <div className="flex-1">
                        <p className="text-white">{signal}</p>
                        <p className="text-sm text-white/50">{lead.company_name}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedLead(lead.id)}
                      >
                        View Account
                      </Button>
                    </div>
                  ))
                )}
              </div>
            )}
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
            <p className="text-white/60">Total pipeline value across {leads.length} accounts</p>

            {/* Pipeline Stages */}
            <div className="mt-6 space-y-3">
              <PipelineStage
                label="Sales Ready"
                count={leads.filter((l) => l.overall_score >= 85).length}
                value={leads.filter((l) => l.overall_score >= 85).reduce((s, l) => s + (l.overall_score / 100) * 50000, 0)}
                percentage={leads.length > 0 ? (leads.filter((l) => l.overall_score >= 85).length / leads.length) * 100 : 0}
                color="bg-green-500"
              />
              <PipelineStage
                label="Nurturing"
                count={leads.filter((l) => l.overall_score >= 70 && l.overall_score < 85).length}
                value={leads.filter((l) => l.overall_score >= 70 && l.overall_score < 85).reduce((s, l) => s + (l.overall_score / 100) * 50000, 0)}
                percentage={leads.length > 0 ? (leads.filter((l) => l.overall_score >= 70 && l.overall_score < 85).length / leads.length) * 100 : 0}
                color="bg-amber-500"
              />
              <PipelineStage
                label="New"
                count={leads.filter((l) => l.overall_score < 70).length}
                value={leads.filter((l) => l.overall_score < 70).reduce((s, l) => s + (l.overall_score / 100) * 50000, 0)}
                percentage={leads.length > 0 ? (leads.filter((l) => l.overall_score < 70).length / leads.length) * 100 : 0}
                color="bg-blue-500"
              />
            </div>
          </Card>

          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Conversion Bottlenecks</h3>
            <p className="text-white/60">
              {leadData?.stuck_leads_count || 0} accounts stuck in nurturing stage for 30+ days.
              Recommended action: personalized outreach or content refresh.
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
  lead: Lead;
  isExpanded: boolean;
  onToggle: () => void;
  onQualify: () => void;
  onUpdateStatus: (status: string) => void;
}

function LeadCard({ lead, isExpanded, onToggle, onQualify, onUpdateStatus }: LeadCardProps) {
  const scoreColor = lead.overall_score >= 85 ? 'text-green-400' : lead.overall_score >= 70 ? 'text-amber-400' : 'text-blue-400';
  const scoreBg = lead.overall_score >= 85 ? 'bg-green-500/20' : lead.overall_score >= 70 ? 'bg-amber-500/20' : 'bg-blue-500/20';

  const pdpaStatus = lead.pdpa_consent_status === 'verified' ? 'Consent verified' : 'Consent pending';

  return (
    <Card className={isExpanded ? 'ring-1 ring-purple-500/50' : ''}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className={`w-12 h-12 rounded-lg ${scoreBg} flex items-center justify-center`}>
            <span className={`text-lg font-bold ${scoreColor}`}>{Math.round(lead.overall_score)}</span>
          </div>
          <div>
            <h4 className="font-semibold text-white">{lead.company_name}</h4>
            <div className="flex items-center gap-3 mt-1 text-sm text-white/60">
              <span className="flex items-center gap-1">
                <Building className="w-3 h-3" />
                {lead.industry}
              </span>
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                {lead.employee_count} employees
              </span>
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {lead.location || 'Singapore'}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={lead.pdpa_consent_status === 'verified' ? 'success' : 'warning'}>
            <Shield className="w-3 h-3 mr-1" />
            {pdpaStatus}
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
              {lead.contact_name && (
                <div className="mb-4 p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-white">{lead.contact_name}</p>
                      <p className="text-sm text-white/60">{lead.contact_title}</p>
                    </div>
                    <div className="flex gap-2">
                      {lead.contact_email && (
                        <Button variant="ghost" size="sm" leftIcon={<Mail className="w-3 h-3" />}>
                          Email
                        </Button>
                      )}
                      {lead.contact_linkedin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<Linkedin className="w-3 h-3" />}
                          onClick={() => window.open(lead.contact_linkedin!, '_blank')}
                        >
                          LinkedIn
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Intent Signals & Fit Reasons */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Intent Signals</h5>
                  <ul className="space-y-1">
                    {(lead.intent_signals || []).map((signal, idx) => (
                      <li key={idx} className="text-sm text-white/80 flex items-start gap-2">
                        <span className="text-green-400">•</span>
                        {signal}
                      </li>
                    ))}
                    {(!lead.intent_signals || lead.intent_signals.length === 0) && (
                      <li className="text-sm text-white/40 italic">No signals yet</li>
                    )}
                  </ul>
                </div>
                <div>
                  <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Fit Reasons</h5>
                  <ul className="space-y-1">
                    {(lead.fit_reasons || []).map((reason, idx) => (
                      <li key={idx} className="text-sm text-white/80 flex items-start gap-2">
                        <span className="text-blue-400">•</span>
                        {reason}
                      </li>
                    ))}
                    {(!lead.fit_reasons || lead.fit_reasons.length === 0) && (
                      <li className="text-sm text-white/40 italic">No fit reasons yet</li>
                    )}
                  </ul>
                </div>
              </div>

              {/* Recommended Approach */}
              {lead.recommended_approach && (
                <div className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/20 mb-4">
                  <h5 className="text-xs font-medium text-purple-400 uppercase mb-1">Recommended Approach</h5>
                  <p className="text-sm text-white/80">{lead.recommended_approach}</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <Button variant="primary" size="sm" onClick={onQualify}>
                  Generate Outreach Email
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onUpdateStatus('contacted')}
                >
                  Mark as Contacted
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
