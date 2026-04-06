/**
 * Workforce Workspace — Design, activate, and monitor the AI Digital Workforce.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Play, CheckCircle, Clock, AlertCircle, Zap, TrendingUp, Users, Mail, Database } from 'lucide-react';
import { workforceApi, WorkforceConfig, ExecutionRun } from '../api/workforce';

interface WorkforceWorkspaceProps {
  companyId: string;
  analysisId?: string;
}

type Tab = 'design' | 'execution' | 'monitoring';

const STATUS_COLORS: Record<string, string> = {
  draft: 'text-yellow-400 bg-yellow-400/10',
  active: 'text-green-400 bg-green-400/10',
  paused: 'text-orange-400 bg-orange-400/10',
  archived: 'text-white/30 bg-white/5',
  pending: 'text-blue-400 bg-blue-400/10',
  running: 'text-purple-400 bg-purple-400/10',
  completed: 'text-green-400 bg-green-400/10',
  partial: 'text-yellow-400 bg-yellow-400/10',
  failed: 'text-red-400 bg-red-400/10',
};

const AGENT_TYPE_ICONS: Record<string, string> = {
  outreach: '📤',
  nurture: '💬',
  content: '✍️',
  crm_sync: '🗄️',
  monitor: '👁️',
  scheduler: '📅',
};

export function WorkforceWorkspace({ companyId, analysisId }: WorkforceWorkspaceProps) {
  const [tab, setTab] = useState<Tab>('design');
  const [config, setConfig] = useState<WorkforceConfig | null>(null);
  const [runs, setRuns] = useState<ExecutionRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [designing, setDesigning] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
  }, [companyId]);

  async function loadConfig() {
    try {
      const c = await workforceApi.getConfig(companyId);
      setConfig(c);
      setSelectedAgents(new Set(c.approved_agents));
    } catch {
      // 404 = no config yet, that's fine
    }
  }

  async function loadRuns() {
    try {
      const r = await workforceApi.listRuns(companyId);
      setRuns(r);
    } catch {
      setRuns([]);
    }
  }

  useEffect(() => {
    if (tab === 'execution') loadRuns();
  }, [tab]);

  async function handleDesign() {
    if (!analysisId) return;
    setDesigning(true);
    setError(null);
    try {
      await workforceApi.design(companyId, analysisId);
      // Poll for completion
      let attempts = 0;
      while (attempts < 30) {
        await new Promise(r => setTimeout(r, 2000));
        try {
          const c = await workforceApi.getConfig(companyId);
          if (c.definition?.agent_roster?.length > 0) {
            setConfig(c);
            setSelectedAgents(new Set(c.definition.agent_roster.map(a => a.agent_type)));
            break;
          }
        } catch {}
        attempts++;
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Design failed');
    } finally {
      setDesigning(false);
    }
  }

  async function handleApprove() {
    if (!config) return;
    setLoading(true);
    try {
      const updated = await workforceApi.approve(companyId, config.id, Array.from(selectedAgents));
      setConfig(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Approval failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute() {
    if (!config) return;
    setExecuting(true);
    try {
      await workforceApi.execute(companyId, config.id);
      await loadRuns();
      setTab('execution');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Execution failed');
    } finally {
      setExecuting(false);
    }
  }

  const definition = config?.definition;
  const agentRoster = definition?.agent_roster ?? [];
  const valueChain = definition?.value_chain ?? [];
  const kpis = definition?.kpis ?? [];

  return (
    <div className="flex flex-col h-full bg-black/20">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
              <Bot className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Digital Workforce</h2>
              <p className="text-xs text-white/40">AI agents executing your growth strategy</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {config && (
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[config.status] ?? 'text-white/50'}`}>
                {config.status.toUpperCase()}
              </span>
            )}
            {config?.status === 'active' && (
              <motion.button
                onClick={handleExecute}
                disabled={executing}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/20 text-green-400 text-sm font-medium hover:bg-green-500/30 transition-colors disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {executing ? 'Running...' : 'Run Now'}
              </motion.button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4">
          {(['design', 'execution', 'monitoring'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                tab === t ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <AnimatePresence mode="wait">
          {tab === 'design' && (
            <motion.div
              key="design"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="space-y-4"
            >
              {!config || !agentRoster.length ? (
                <div className="text-center py-12">
                  <Bot className="w-12 h-12 text-white/20 mx-auto mb-4" />
                  <p className="text-white/50 mb-2">No workforce designed yet</p>
                  <p className="text-white/30 text-sm mb-6">Design an AI workforce based on your completed growth analysis</p>
                  {analysisId && (
                    <motion.button
                      onClick={handleDesign}
                      disabled={designing}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="px-6 py-3 rounded-xl bg-purple-500/20 text-purple-300 font-medium hover:bg-purple-500/30 transition-colors disabled:opacity-50"
                    >
                      {designing ? (
                        <span className="flex items-center gap-2">
                          <Clock className="w-4 h-4 animate-spin" /> Designing workforce...
                        </span>
                      ) : 'Design Digital Workforce'}
                    </motion.button>
                  )}
                </div>
              ) : (
                <>
                  {/* Summary */}
                  {definition?.executive_summary && (
                    <div className="glass-card p-4 rounded-xl border border-purple-500/20">
                      <p className="text-sm text-white/70">{definition.executive_summary}</p>
                      <div className="flex gap-4 mt-3">
                        <div className="text-center">
                          <p className="text-xl font-bold text-purple-400">{definition.estimated_weekly_hours_saved?.toFixed(0)}h</p>
                          <p className="text-xs text-white/40">saved/week</p>
                        </div>
                        <div className="text-center">
                          <p className="text-xl font-bold text-green-400">SGD {definition.estimated_monthly_revenue_impact_sgd?.toLocaleString()}</p>
                          <p className="text-xs text-white/40">monthly impact</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Agent Roster */}
                  <div>
                    <h3 className="text-sm font-medium text-white/60 mb-2 uppercase tracking-wider">Agent Roster</h3>
                    <div className="space-y-2">
                      {agentRoster.map((agent) => (
                        <motion.div
                          key={agent.agent_type}
                          className={`glass-card p-3 rounded-xl cursor-pointer border transition-colors ${
                            selectedAgents.has(agent.agent_type)
                              ? 'border-purple-500/40 bg-purple-500/5'
                              : 'border-white/10'
                          }`}
                          onClick={() => {
                            const next = new Set(selectedAgents);
                            if (next.has(agent.agent_type)) next.delete(agent.agent_type);
                            else next.add(agent.agent_type);
                            setSelectedAgents(next);
                          }}
                          whileHover={{ scale: 1.01 }}
                        >
                          <div className="flex items-start gap-3">
                            <span className="text-2xl">{AGENT_TYPE_ICONS[agent.agent_type] ?? '🤖'}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-white text-sm">{agent.agent_name}</span>
                                <span className="px-2 py-0.5 rounded text-xs bg-white/10 text-white/50">{agent.primary_mcp}</span>
                                {selectedAgents.has(agent.agent_type) && (
                                  <CheckCircle className="w-4 h-4 text-purple-400 ml-auto flex-shrink-0" />
                                )}
                              </div>
                              <p className="text-xs text-white/50 mt-0.5">{agent.rationale}</p>
                              <p className="text-xs text-white/30 mt-1">Trigger: {agent.trigger} • {agent.estimated_hours_saved_per_week}h saved/week</p>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  {/* Value Chain */}
                  {valueChain.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-white/60 mb-2 uppercase tracking-wider">Value Chain</h3>
                      <div className="relative">
                        <div className="absolute left-4 top-0 bottom-0 w-px bg-white/10" />
                        <div className="space-y-2 pl-10">
                          {valueChain.map((step) => (
                            <div key={step.step_number} className="relative">
                              <div className="absolute -left-6 top-3 w-3 h-3 rounded-full bg-purple-500/40 border border-purple-500/60" />
                              <div className="glass-card p-3 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs text-purple-400 font-mono w-6">{step.step_number}</span>
                                  <span className="text-sm text-white font-medium">{step.name}</span>
                                  <span className="ml-auto text-xs text-white/30 flex items-center gap-1">
                                    <span>{AGENT_TYPE_ICONS[step.responsible_agent] ?? '🤖'}</span>
                                    {step.responsible_agent}
                                  </span>
                                </div>
                                {step.description && (
                                  <p className="text-xs text-white/40 mt-1 ml-8">{step.description}</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* KPIs */}
                  {kpis.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-white/60 mb-2 uppercase tracking-wider">KPIs</h3>
                      <div className="grid grid-cols-2 gap-2">
                        {kpis.map((kpi, i) => (
                          <div key={i} className="glass-card p-3 rounded-xl">
                            <p className="text-xs text-white/40">{kpi.name}</p>
                            <p className="text-lg font-bold text-white mt-1">{kpi.target_value} <span className="text-sm font-normal text-white/40">{kpi.unit}</span></p>
                            <p className="text-xs text-white/30 mt-1">via {kpi.measurement_source}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Approve / Activate */}
                  {config.status === 'draft' && (
                    <motion.button
                      onClick={handleApprove}
                      disabled={loading || selectedAgents.size === 0}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="w-full py-3 rounded-xl bg-purple-500/20 text-purple-300 font-medium hover:bg-purple-500/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      <Zap className="w-4 h-4" />
                      {loading ? 'Activating...' : `Activate ${selectedAgents.size} Agent${selectedAgents.size !== 1 ? 's' : ''}`}
                    </motion.button>
                  )}
                </>
              )}
            </motion.div>
          )}

          {tab === 'execution' && (
            <motion.div
              key="execution"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/60 uppercase tracking-wider">Execution History</h3>
                <button onClick={loadRuns} className="text-xs text-white/30 hover:text-white/60">Refresh</button>
              </div>
              {runs.length === 0 ? (
                <div className="text-center py-8 text-white/30 text-sm">No execution runs yet. Activate the workforce and click Run Now.</div>
              ) : (
                runs.map((run) => (
                  <div key={run.id} className="glass-card p-4 rounded-xl">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[run.status] ?? ''}`}>
                          {run.status.toUpperCase()}
                        </span>
                        <span className="text-xs text-white/40">{new Date(run.started_at).toLocaleString()}</span>
                      </div>
                      <span className="text-xs text-white/30">{run.trigger}</span>
                    </div>
                    <div className="flex gap-4 mt-3">
                      <div className="flex items-center gap-1 text-xs text-white/50">
                        <CheckCircle className="w-3 h-3 text-green-400" />
                        {run.steps_completed}/{run.steps_total} steps
                      </div>
                      <div className="flex items-center gap-1 text-xs text-white/50">
                        <Mail className="w-3 h-3 text-blue-400" />
                        {run.emails_sent} emails
                      </div>
                      <div className="flex items-center gap-1 text-xs text-white/50">
                        <Database className="w-3 h-3 text-purple-400" />
                        {run.crm_records_updated} CRM records
                      </div>
                    </div>
                  </div>
                ))
              )}
            </motion.div>
          )}

          {tab === 'monitoring' && (
            <motion.div
              key="monitoring"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Total Emails Sent', value: runs.reduce((s, r) => s + r.emails_sent, 0), icon: Mail, color: 'blue' },
                  { label: 'CRM Records Updated', value: runs.reduce((s, r) => s + r.crm_records_updated, 0), icon: Database, color: 'purple' },
                  { label: 'Runs Completed', value: runs.filter(r => r.status === 'completed').length, icon: CheckCircle, color: 'green' },
                  { label: 'Leads Contacted', value: runs.reduce((s, r) => s + r.leads_contacted, 0), icon: Users, color: 'pink' },
                ].map(({ label, value, icon: Icon, color }) => (
                  <div key={label} className="glass-card p-4 rounded-xl">
                    <div className={`w-8 h-8 rounded-lg bg-${color}-500/20 flex items-center justify-center mb-2`}>
                      <Icon className={`w-4 h-4 text-${color}-400`} />
                    </div>
                    <p className="text-2xl font-bold text-white">{value}</p>
                    <p className="text-xs text-white/40 mt-1">{label}</p>
                  </div>
                ))}
              </div>
              <div className="glass-card p-4 rounded-xl text-center">
                <TrendingUp className="w-8 h-8 text-white/20 mx-auto mb-2" />
                <p className="text-white/40 text-sm">Time-series charts available after 3+ execution runs</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
