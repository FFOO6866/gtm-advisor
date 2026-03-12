import { apiClient } from './client';

export interface SignalEvent {
  id: string;
  signal_type: string;
  urgency: 'immediate' | 'this_week' | 'this_month' | 'monitor';
  headline: string;
  summary?: string;
  source?: string;
  source_url?: string;
  relevance_score: number;
  competitors_mentioned: string[];
  recommended_action?: string;
  is_actioned: boolean;
  published_at?: string;
  created_at: string;
}

export const signalsApi = {
  list: (companyId: string, urgency?: string, limit = 20): Promise<SignalEvent[]> =>
    apiClient.get(`/companies/${companyId}/signals?limit=${limit}${urgency ? `&urgency=${urgency}` : ''}`),
  markActioned: (companyId: string, signalId: string): Promise<void> =>
    apiClient.post(`/companies/${companyId}/signals/${signalId}/action`),
};
