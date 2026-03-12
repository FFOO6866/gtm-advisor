import { apiClient } from './client';

export interface ApprovalItem {
  id: string;
  lead_id: string;
  to_email: string;
  to_name?: string;
  sequence_name?: string;
  step_number: number;
  proposed_subject: string;
  proposed_body: string;
  status: 'pending' | 'approved' | 'rejected' | 'edited_approved';
  created_at: string;
  expires_at?: string;
}

export const approvalsApi = {
  list: (companyId: string, status = 'pending'): Promise<ApprovalItem[]> =>
    apiClient.get(`/companies/${companyId}/approvals?status=${status}`),
  count: (companyId: string): Promise<{pending: number}> =>
    apiClient.get(`/companies/${companyId}/approvals/count`),
  approve: (companyId: string, itemId: string, editedSubject?: string, editedBody?: string): Promise<void> =>
    apiClient.post(`/companies/${companyId}/approvals/${itemId}/approve`, {
      edited_subject: editedSubject,
      edited_body: editedBody,
      approved_by: 'user',
    }),
  reject: (companyId: string, itemId: string, reason?: string): Promise<void> =>
    apiClient.post(`/companies/${companyId}/approvals/${itemId}/reject`, { reason }),
  bulkApprove: (companyId: string, itemIds: string[]): Promise<{approved: number}> =>
    apiClient.post(`/companies/${companyId}/approvals/bulk-approve`, { item_ids: itemIds, approved_by: 'user' }),
};
