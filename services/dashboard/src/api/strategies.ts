/**
 * Strategy API client — all content is AI-generated from analysis insights.
 * Strategies are GENERIC — they work for any company on the platform.
 */
import { apiClient } from './client';

export interface Strategy {
  id: string;
  company_id: string;
  name: string;
  description: string;
  insight_sources: string[];
  rationale: string;
  expected_outcome: string;
  success_metrics: Array<{ metric: string; target: string; current?: string }>;
  priority: 'high' | 'medium' | 'low';
  estimated_timeline: string;
  target_segment: string;
  status: 'proposed' | 'approved' | 'rejected' | 'in_progress' | 'completed' | 'revised';
  user_notes?: string;
  approved_at?: string;
  created_at: string;
}

export interface StrategiesResponse {
  strategies: Strategy[];
  total: number;
  by_status: Record<string, number>;
}

export const strategiesApi = {
  list: (companyId: string, status?: string) =>
    apiClient.get<StrategiesResponse>(
      `/companies/${companyId}/strategies${status ? `?status=${status}` : ''}`
    ),

  approve: (companyId: string, strategyId: string, notes?: string) =>
    apiClient.post<Strategy>(
      `/companies/${companyId}/strategies/${strategyId}/approve`,
      { approved_by: 'user', user_notes: notes }
    ),

  reject: (companyId: string, strategyId: string, reason?: string) =>
    apiClient.post<{ status: string }>(
      `/companies/${companyId}/strategies/${strategyId}/reject`,
      { reason }
    ),

  update: (companyId: string, strategyId: string, data: Partial<Strategy>) =>
    apiClient.patch<Strategy>(`/companies/${companyId}/strategies/${strategyId}`, data),

  generate: (companyId: string) =>
    apiClient.post<{ status: string; message: string }>(
      `/companies/${companyId}/strategies/generate`, {}
    ),

  generateCampaigns: (companyId: string) =>
    apiClient.post<{ status: string; message: string }>(
      `/companies/${companyId}/strategies/generate-campaigns`, {}
    ),
};
