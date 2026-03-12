import { apiClient } from './client';

export interface AttributionSummary {
  period_days: number;
  emails_sent: number;
  replies: number;
  reply_rate_pct: number;
  meetings_booked: number;
  pipeline_value_sgd: number;
  meeting_to_email_ratio: number;
  why_us_proof: string;
  breakdown: Record<string, {count: number; pipeline_sgd: number}>;
}

export const attributionApi = {
  summary: (companyId: string, days = 30): Promise<AttributionSummary> =>
    apiClient.get(`/companies/${companyId}/attribution/summary?days=${days}`),
  recordEvent: (companyId: string, leadId: string, eventType: string, pipelineValue?: number, notes?: string): Promise<void> =>
    apiClient.post(`/companies/${companyId}/attribution/events`, {
      lead_id: leadId,
      event_type: eventType,
      pipeline_value_sgd: pipelineValue,
      notes,
    }),
};
