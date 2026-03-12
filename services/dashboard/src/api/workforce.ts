/**
 * Workforce API client — Digital Workforce design, execution, and monitoring.
 */

import { apiClient } from './client';

export interface AgentSpec {
  agent_type: string;
  agent_name: string;
  rationale: string;
  primary_mcp: string;
  trigger: string;
  estimated_hours_saved_per_week: number;
}

export interface ProcessStep {
  step_number: number;
  name: string;
  responsible_agent: string;
  mcp_call?: string;
  description: string;
  estimated_duration_seconds: number;
}

export interface KPI {
  name: string;
  target_value: number;
  unit: string;
  measurement_source: string;
  baseline_value: number;
}

export interface WorkforceDefinition {
  agent_roster: AgentSpec[];
  value_chain: ProcessStep[];
  kpis: KPI[];
  executive_summary: string;
  estimated_weekly_hours_saved: number;
  estimated_monthly_revenue_impact_sgd: number;
  confidence: number;
}

export interface WorkforceConfig {
  id: string;
  company_id: string;
  analysis_id?: string;
  status: 'draft' | 'active' | 'paused' | 'archived';
  definition: WorkforceDefinition;
  approved_agents: string[];
  executive_summary?: string;
  estimated_weekly_hours_saved: number;
  estimated_monthly_revenue_impact_sgd: number;
  agent_count: number;
  created_at: string;
  updated_at?: string;
}

export interface ExecutionRun {
  id: string;
  workforce_config_id: string;
  status: 'pending' | 'running' | 'completed' | 'partial' | 'failed';
  trigger: string;
  steps_total: number;
  steps_completed: number;
  steps_failed: number;
  emails_sent: number;
  crm_records_updated: number;
  leads_contacted: number;
  started_at: string;
  completed_at?: string;
  execution_log?: Array<{step: string; agent: string; status: string; result?: string; duration_ms?: number}>;
}

export const workforceApi = {
  async design(companyId: string, analysisId: string): Promise<{workforce_config_id: string; status: string}> {
    return apiClient.post(`/companies/${companyId}/workforce/design`, { analysis_id: analysisId });
  },

  async getConfig(companyId: string): Promise<WorkforceConfig> {
    return apiClient.get(`/companies/${companyId}/workforce`);
  },

  async approve(companyId: string, configId: string, approvedAgents: string[]): Promise<WorkforceConfig> {
    return apiClient.patch(`/companies/${companyId}/workforce/${configId}/approve`, { approved_agents: approvedAgents });
  },

  async execute(companyId: string, configId: string, trigger = 'manual'): Promise<{execution_run_id: string; status: string}> {
    return apiClient.post(`/companies/${companyId}/workforce/${configId}/execute`, { trigger });
  },

  async listRuns(companyId: string, limit = 20): Promise<ExecutionRun[]> {
    return apiClient.get(`/companies/${companyId}/workforce/runs/list?limit=${limit}`);
  },

  async getRun(companyId: string, runId: string): Promise<ExecutionRun> {
    return apiClient.get(`/companies/${companyId}/workforce/runs/${runId}`);
  },
};
