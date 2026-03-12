/**
 * LeadsPipeline — Kanban board for the lead pipeline state machine.
 *
 * Columns: Discovered → Enriched → Qualified → In Sequence → Replied → Meeting → Won
 *
 * Each card shows:
 * - Lead name + company
 * - Fit score badge (green/amber/red)
 * - Email verified badge
 * - Current sequence step (if in sequence)
 * - Quick actions: Enroll in sequence, Mark replied, Book meeting
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Mail, Building2, Zap, CheckCircle, AlertCircle, TrendingUp } from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';

interface Lead {
  id: string;
  name: string;
  email?: string;
  title?: string;
  company_name?: string;
  industry?: string;
  fit_score?: number;
  status?: string;
  email_verified?: boolean;
  enrichment_data?: Record<string, unknown>;
}

const PIPELINE_STAGES = [
  { key: 'new', label: 'New', color: 'border-white/20', count_color: 'text-white/40' },
  { key: 'qualified', label: 'Qualified', color: 'border-purple-500/30', count_color: 'text-purple-400' },
  { key: 'contacted', label: 'Contacted', color: 'border-cyan-500/30', count_color: 'text-cyan-400' },
  { key: 'converted', label: 'Won', color: 'border-emerald-500/30', count_color: 'text-emerald-400' },
  { key: 'lost', label: 'Lost', color: 'border-red-500/30', count_color: 'text-red-400' },
];

function FitBadge({ score }: { score?: number }) {
  if (!score) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? 'bg-green-500/20 text-green-400' : pct >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400';
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${color}`}>{pct}%</span>;
}

function LeadCard({ lead, onStatusChange }: { lead: Lead; onStatusChange: (id: string, status: string) => void }) {
  const enrichment = lead.enrichment_data as Record<string, unknown> | undefined;
  const emailDeliverable = enrichment?.email_deliverable as boolean | undefined;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-3 rounded-xl cursor-pointer hover:bg-white/5 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-white truncate">{lead.name}</p>
          <p className="text-xs text-white/50 truncate">{lead.title}</p>
          <div className="flex items-center gap-1.5 mt-1.5">
            <Building2 className="w-3 h-3 text-white/30 flex-shrink-0" />
            <span className="text-xs text-white/40 truncate">{lead.company_name}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <FitBadge score={lead.fit_score} />
          {emailDeliverable !== undefined && (
            emailDeliverable
              ? <CheckCircle className="w-3 h-3 text-green-400" />
              : <AlertCircle className="w-3 h-3 text-red-400" />
          )}
        </div>
      </div>

      {lead.email && (
        <div className="flex items-center gap-1 mt-2">
          <Mail className="w-3 h-3 text-white/30" />
          <span className="text-xs text-white/30 truncate">{lead.email}</span>
        </div>
      )}

      {/* Quick actions */}
      <div className="flex gap-1 mt-2.5 pt-2 border-t border-white/5">
        {lead.status === 'new' && (
          <button
            onClick={() => onStatusChange(lead.id, 'qualified')}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-purple-500/10 text-purple-400 text-[10px] hover:bg-purple-500/20 transition-colors"
          >
            <Zap className="w-3 h-3" />
            Qualify
          </button>
        )}
        {lead.status === 'qualified' && (
          <button
            onClick={() => onStatusChange(lead.id, 'contacted')}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-cyan-500/10 text-cyan-400 text-[10px] hover:bg-cyan-500/20 transition-colors"
          >
            <Mail className="w-3 h-3" />
            Contact
          </button>
        )}
        {lead.status === 'contacted' && (
          <button
            onClick={() => onStatusChange(lead.id, 'converted')}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-[10px] hover:bg-emerald-500/20 transition-colors"
          >
            <TrendingUp className="w-3 h-3" />
            Won
          </button>
        )}
        {lead.status !== 'converted' && lead.status !== 'lost' && (
          <button
            onClick={() => onStatusChange(lead.id, 'lost')}
            className="ml-auto flex items-center gap-1 px-2 py-1 rounded-lg bg-red-500/10 text-red-400 text-[10px] hover:bg-red-500/20 transition-colors"
          >
            Lost
          </button>
        )}
      </div>
    </motion.div>
  );
}

export function LeadsPipeline() {
  const companyId = useCompanyId() ?? '';
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) return;
    apiClient
      .get<{
        leads: Array<{
          id: string;
          contact_name: string | null;
          contact_email: string | null;
          contact_title: string | null;
          lead_company_name: string;
          lead_company_industry: string | null;
          fit_score: number;
          status: string | null;
        }>;
      }>(`/companies/${companyId}/leads`)
      .then(data => {
        setLeads(data.leads.map(l => ({
          id: l.id,
          name: l.contact_name || l.lead_company_name,
          email: l.contact_email ?? undefined,
          title: l.contact_title ?? undefined,
          company_name: l.lead_company_name,
          industry: l.lead_company_industry ?? undefined,
          fit_score: (l.fit_score || 0) / 100,
          status: l.status ?? 'new',
        })));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [companyId]);

  const handleStatusChange = async (leadId: string, newStatus: string) => {
    const previousStatus = leads.find(l => l.id === leadId)?.status;
    // Optimistic update
    setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: newStatus } : l));
    try {
      await apiClient.patch(`/companies/${companyId}/leads/${leadId}`, { status: newStatus });
    } catch {
      // Revert on failure
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: previousStatus } : l));
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const leadsByStage = PIPELINE_STAGES.reduce((acc, stage) => {
    acc[stage.key] = leads.filter(l => (l.status || 'discovered') === stage.key);
    return acc;
  }, {} as Record<string, Lead[]>);

  const totalLeads = leads.length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white">Lead Pipeline</h1>
            <p className="text-xs text-white/40">{totalLeads} leads across {PIPELINE_STAGES.length} stages</p>
          </div>
          <div className="flex items-center gap-3 text-xs text-white/40">
            <span className="flex items-center gap-1.5">
              <CheckCircle className="w-3 h-3 text-green-400" />
              Email verified
            </span>
            <span className="flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3 text-red-400" />
              Needs verification
            </span>
          </div>
        </div>
      </div>

      {/* Kanban board */}
      <div className="flex-1 overflow-x-auto p-4">
        <div className="flex gap-3 h-full min-w-max">
          {PIPELINE_STAGES.map(stage => {
            const stageLeads = leadsByStage[stage.key] || [];
            return (
              <div
                key={stage.key}
                className={`flex flex-col w-52 rounded-xl border ${stage.color} bg-white/2`}
              >
                {/* Column header */}
                <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/5">
                  <span className="text-xs font-medium text-white/70">{stage.label}</span>
                  <span className={`text-xs font-bold ${stage.count_color}`}>{stageLeads.length}</span>
                </div>
                {/* Cards */}
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                  {stageLeads.map(lead => (
                    <LeadCard key={lead.id} lead={lead} onStatusChange={handleStatusChange} />
                  ))}
                  {stageLeads.length === 0 && (
                    <div className="text-center py-6 text-white/20 text-xs">No leads</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
