/**
 * GTM Advisor Workspace API Client
 *
 * API client for workspace-specific data: competitors, ICPs, leads, campaigns, insights.
 */

/// <reference types="vite/client" />

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ============================================================================
// Types
// ============================================================================

// Competitor types
export interface Competitor {
  id: string;
  company_id: string;
  name: string;
  website: string | null;
  description: string | null;
  threat_level: 'low' | 'medium' | 'high';
  positioning: string | null;
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
  our_advantages: string[];
  their_advantages: string[];
  key_objection_handlers: string[];
  pricing_info: Record<string, unknown> | null;
  is_active: boolean;
  last_updated: string;
  created_at: string;
  updated_at: string | null;
  alert_count: number;
}

export interface CompetitorCreate {
  name: string;
  website?: string;
  description?: string;
  threat_level?: 'low' | 'medium' | 'high';
  positioning?: string;
  strengths?: string[];
  weaknesses?: string[];
  opportunities?: string[];
  threats?: string[];
  our_advantages?: string[];
  their_advantages?: string[];
  key_objection_handlers?: string[];
  pricing_info?: Record<string, unknown>;
}

export interface CompetitorAlert {
  id: string;
  competitor_id: string;
  alert_type: string;
  severity: string;
  title: string;
  description: string | null;
  source_url: string | null;
  is_read: boolean;
  is_dismissed: boolean;
  detected_at: string;
  read_at: string | null;
}

export interface CompetitorListResponse {
  competitors: Competitor[];
  total: number;
  high_threat_count: number;
  medium_threat_count: number;
  low_threat_count: number;
  unread_alerts_count: number;
}

export interface BattleCard {
  competitor_id: string;
  competitor_name: string;
  our_advantages: string[];
  their_advantages: string[];
  key_objection_handlers: string[];
  positioning: string | null;
  pricing_comparison: Record<string, unknown> | null;
  win_strategies: string[];
  generated_at: string;
}

// ICP and Persona types
export interface Persona {
  id: string;
  icp_id: string;
  name: string;
  role: string;
  avatar: string | null;
  age_range: string | null;
  experience_years: string | null;
  education: string | null;
  goals: string[];
  challenges: string[];
  objections: string[];
  preferred_channels: string[];
  messaging_hooks: string[];
  content_preferences: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface PersonaCreate {
  name: string;
  role: string;
  avatar?: string;
  age_range?: string;
  experience_years?: string;
  education?: string;
  goals?: string[];
  challenges?: string[];
  objections?: string[];
  preferred_channels?: string[];
  messaging_hooks?: string[];
  content_preferences?: string[];
}

export interface ICP {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  fit_score: number;
  company_size: string | null;
  revenue_range: string | null;
  industry: string | null;
  tech_stack: string | null;
  buying_triggers: string[];
  pain_points: string[];
  needs: string[];
  matching_companies_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
  personas: Persona[];
}

export interface ICPCreate {
  name: string;
  description?: string;
  fit_score?: number;
  company_size?: string;
  revenue_range?: string;
  industry?: string;
  tech_stack?: string;
  buying_triggers?: string[];
  pain_points?: string[];
  needs?: string[];
}

export interface ICPListResponse {
  icps: ICP[];
  total: number;
  active_count: number;
  total_personas: number;
}

// Lead types
export interface Lead {
  id: string;
  company_id: string;
  icp_id: string | null;
  lead_company_name: string;
  lead_company_website: string | null;
  lead_company_industry: string | null;
  lead_company_size: string | null;
  lead_company_description: string | null;
  contact_name: string | null;
  contact_title: string | null;
  contact_email: string | null;
  contact_linkedin: string | null;
  fit_score: number;
  intent_score: number;
  overall_score: number;
  status: 'new' | 'qualified' | 'contacted' | 'converted' | 'lost';
  qualification_reasons: string[];
  disqualification_reasons: string[];
  source: string | null;
  source_url: string | null;
  notes: string | null;
  tags: string[];
  created_at: string;
  updated_at: string | null;
  contacted_at: string | null;
  converted_at: string | null;
}

export interface LeadCreate {
  lead_company_name: string;
  lead_company_website?: string;
  lead_company_industry?: string;
  lead_company_size?: string;
  lead_company_description?: string;
  contact_name?: string;
  contact_title?: string;
  contact_email?: string;
  contact_linkedin?: string;
  fit_score?: number;
  intent_score?: number;
  icp_id?: string;
  source?: string;
  source_url?: string;
  qualification_reasons?: string[];
  notes?: string;
  tags?: string[];
}

export interface LeadListResponse {
  leads: Lead[];
  total: number;
  by_status: Record<string, number>;
  avg_fit_score: number;
  avg_intent_score: number;
  high_score_count: number;
}

// Campaign types
export interface EmailTemplate {
  id?: string;
  name: string;
  subject: string;
  body: string;
  type: string;
  variables: string[];
}

export interface ContentAsset {
  id?: string;
  type: string;
  title?: string;
  content: string;
  channel?: string;
  target_persona?: string;
}

export interface Campaign {
  id: string;
  company_id: string;
  icp_id: string | null;
  name: string;
  description: string | null;
  objective: string;
  status: 'draft' | 'active' | 'paused' | 'completed';
  target_personas: string[];
  target_industries: string[];
  target_company_sizes: string[];
  key_messages: string[];
  value_propositions: string[];
  call_to_action: string | null;
  channels: string[];
  email_templates: EmailTemplate[];
  linkedin_posts: ContentAsset[];
  ad_copy: ContentAsset[];
  landing_page_copy: Record<string, unknown> | null;
  blog_outlines: ContentAsset[];
  budget: number | null;
  currency: string;
  start_date: string | null;
  end_date: string | null;
  metrics: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}

export interface CampaignCreate {
  name: string;
  description?: string;
  objective?: string;
  icp_id?: string;
  target_personas?: string[];
  target_industries?: string[];
  target_company_sizes?: string[];
  key_messages?: string[];
  value_propositions?: string[];
  call_to_action?: string;
  channels?: string[];
  budget?: number;
  currency?: string;
  start_date?: string;
  end_date?: string;
}

export interface CampaignListResponse {
  campaigns: Campaign[];
  total: number;
  by_status: Record<string, number>;
  by_objective: Record<string, number>;
  total_budget: number;
}

// Market Insight types
export interface MarketInsight {
  id: string;
  company_id: string;
  insight_type: 'trend' | 'opportunity' | 'threat' | 'news';
  category: string | null;
  title: string;
  summary: string | null;
  full_content: string | null;
  impact_level: 'low' | 'medium' | 'high' | null;
  relevance_score: number;
  source_name: string | null;
  source_url: string | null;
  published_at: string | null;
  recommended_actions: string[];
  related_agents: string[];
  is_read: boolean;
  is_archived: boolean;
  created_at: string;
  expires_at: string | null;
}

export interface MarketInsightListResponse {
  insights: MarketInsight[];
  total: number;
  unread_count: number;
  by_type: Record<string, number>;
  by_impact: Record<string, number>;
  recent_high_impact: MarketInsight[];
}

// User Settings types
export interface UserPreferences {
  notifications: {
    email_alerts: boolean;
    competitor_alerts: boolean;
    lead_alerts: boolean;
    insight_alerts: boolean;
    weekly_digest: boolean;
  };
  display: {
    theme: 'dark' | 'light' | 'auto';
    dashboard_layout: 'default' | 'compact' | 'expanded';
    default_tab: string;
    show_confidence_scores: boolean;
  };
  agents: {
    auto_run_enrichment: boolean;
    confidence_threshold: number;
    max_leads_per_run: number;
    enable_a2a_sharing: boolean;
    parallel_execution: boolean;
  };
}

export interface UserSettings {
  id: string;
  email: string;
  full_name: string;
  company_name: string | null;
  tier: string;
  tier_display_name: string;
  tier_limits: Record<string, number>;
  daily_requests: number;
  daily_limit: number;
  usage_percentage: number;
  preferences: UserPreferences;
  api_keys_configured: {
    openai_configured: boolean;
    perplexity_configured: boolean;
    newsapi_configured: boolean;
    eodhd_configured: boolean;
  };
  created_at: string;
  updated_at: string | null;
}

// ============================================================================
// API Error Class
// ============================================================================

class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

// ============================================================================
// Fetch Helper
// ============================================================================

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new APIError(
      errorData.message || errorData.detail || `API Error: ${response.status}`,
      response.status,
      errorData
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// ============================================================================
// Competitors API
// ============================================================================

export async function listCompetitors(
  companyId: string,
  options?: { threatLevel?: string; isActive?: boolean }
): Promise<CompetitorListResponse> {
  const params = new URLSearchParams();
  if (options?.threatLevel) params.append('threat_level', options.threatLevel);
  if (options?.isActive !== undefined) params.append('is_active', String(options.isActive));

  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchAPI(`/api/v1/companies/${companyId}/competitors${query}`);
}

export async function getCompetitor(companyId: string, competitorId: string): Promise<Competitor> {
  return fetchAPI(`/api/v1/companies/${companyId}/competitors/${competitorId}`);
}

export async function createCompetitor(
  companyId: string,
  data: CompetitorCreate
): Promise<Competitor> {
  return fetchAPI(`/api/v1/companies/${companyId}/competitors`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCompetitor(
  companyId: string,
  competitorId: string,
  data: Partial<CompetitorCreate>
): Promise<Competitor> {
  return fetchAPI(`/api/v1/companies/${companyId}/competitors/${competitorId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteCompetitor(companyId: string, competitorId: string): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/competitors/${competitorId}`, {
    method: 'DELETE',
  });
}

export async function getCompetitorAlerts(
  companyId: string,
  competitorId: string,
  unreadOnly?: boolean
): Promise<CompetitorAlert[]> {
  const params = unreadOnly ? '?unread_only=true' : '';
  return fetchAPI(`/api/v1/companies/${companyId}/competitors/${competitorId}/alerts${params}`);
}

export async function markAlertRead(
  companyId: string,
  competitorId: string,
  alertId: string
): Promise<void> {
  return fetchAPI(
    `/api/v1/companies/${companyId}/competitors/${competitorId}/alerts/${alertId}/read`,
    { method: 'POST' }
  );
}

export async function getBattleCard(companyId: string, competitorId: string): Promise<BattleCard> {
  return fetchAPI(`/api/v1/companies/${companyId}/competitors/${competitorId}/battlecard`);
}

// ============================================================================
// ICPs & Personas API
// ============================================================================

export async function listICPs(
  companyId: string,
  isActive?: boolean
): Promise<ICPListResponse> {
  const params = isActive !== undefined ? `?is_active=${isActive}` : '';
  return fetchAPI(`/api/v1/companies/${companyId}/icps${params}`);
}

export async function getICP(companyId: string, icpId: string): Promise<ICP> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps/${icpId}`);
}

export async function createICP(companyId: string, data: ICPCreate): Promise<ICP> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateICP(
  companyId: string,
  icpId: string,
  data: Partial<ICPCreate>
): Promise<ICP> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps/${icpId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteICP(companyId: string, icpId: string): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps/${icpId}`, {
    method: 'DELETE',
  });
}

export async function createPersona(
  companyId: string,
  icpId: string,
  data: PersonaCreate
): Promise<Persona> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps/${icpId}/personas`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updatePersona(
  companyId: string,
  icpId: string,
  personaId: string,
  data: Partial<PersonaCreate>
): Promise<Persona> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps/${icpId}/personas/${personaId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deletePersona(
  companyId: string,
  icpId: string,
  personaId: string
): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/icps/${icpId}/personas/${personaId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Leads API
// ============================================================================

export async function listLeads(
  companyId: string,
  options?: {
    status?: string;
    minScore?: number;
    search?: string;
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
  }
): Promise<LeadListResponse> {
  const params = new URLSearchParams();
  if (options?.status) params.append('status', options.status);
  if (options?.minScore) params.append('min_score', String(options.minScore));
  if (options?.search) params.append('search', options.search);
  if (options?.page) params.append('page', String(options.page));
  if (options?.pageSize) params.append('page_size', String(options.pageSize));
  if (options?.sortBy) params.append('sort_by', options.sortBy);
  if (options?.sortOrder) params.append('sort_order', options.sortOrder);

  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchAPI(`/api/v1/companies/${companyId}/leads${query}`);
}

export async function getLead(companyId: string, leadId: string): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}`);
}

export async function createLead(companyId: string, data: LeadCreate): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateLead(
  companyId: string,
  leadId: string,
  data: Partial<LeadCreate & { status?: string }>
): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function updateLeadScore(
  companyId: string,
  leadId: string,
  scores: { fit_score?: number; intent_score?: number }
): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}/score`, {
    method: 'PATCH',
    body: JSON.stringify(scores),
  });
}

export async function deleteLead(companyId: string, leadId: string): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}`, {
    method: 'DELETE',
  });
}

export async function qualifyLead(companyId: string, leadId: string): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}/qualify`, {
    method: 'POST',
  });
}

export async function markLeadContacted(companyId: string, leadId: string): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}/contact`, {
    method: 'POST',
  });
}

export async function convertLead(companyId: string, leadId: string): Promise<Lead> {
  return fetchAPI(`/api/v1/companies/${companyId}/leads/${leadId}/convert`, {
    method: 'POST',
  });
}

// ============================================================================
// Campaigns API
// ============================================================================

export async function listCampaigns(
  companyId: string,
  options?: { status?: string; objective?: string }
): Promise<CampaignListResponse> {
  const params = new URLSearchParams();
  if (options?.status) params.append('status', options.status);
  if (options?.objective) params.append('objective', options.objective);

  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns${query}`);
}

export async function getCampaign(companyId: string, campaignId: string): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}`);
}

export async function createCampaign(companyId: string, data: CampaignCreate): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCampaign(
  companyId: string,
  campaignId: string,
  data: Partial<CampaignCreate & { status?: string; email_templates?: EmailTemplate[]; linkedin_posts?: ContentAsset[] }>
): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteCampaign(companyId: string, campaignId: string): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}`, {
    method: 'DELETE',
  });
}

export async function activateCampaign(companyId: string, campaignId: string): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}/activate`, {
    method: 'POST',
  });
}

export async function pauseCampaign(companyId: string, campaignId: string): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}/pause`, {
    method: 'POST',
  });
}

export async function completeCampaign(companyId: string, campaignId: string): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}/complete`, {
    method: 'POST',
  });
}

export async function duplicateCampaign(companyId: string, campaignId: string): Promise<Campaign> {
  return fetchAPI(`/api/v1/companies/${companyId}/campaigns/${campaignId}/duplicate`, {
    method: 'POST',
  });
}

// ============================================================================
// Market Insights API
// ============================================================================

export async function listInsights(
  companyId: string,
  options?: {
    insightType?: string;
    impactLevel?: string;
    unreadOnly?: boolean;
    includeArchived?: boolean;
    page?: number;
    pageSize?: number;
  }
): Promise<MarketInsightListResponse> {
  const params = new URLSearchParams();
  if (options?.insightType) params.append('insight_type', options.insightType);
  if (options?.impactLevel) params.append('impact_level', options.impactLevel);
  if (options?.unreadOnly) params.append('unread_only', 'true');
  if (options?.includeArchived) params.append('include_archived', 'true');
  if (options?.page) params.append('page', String(options.page));
  if (options?.pageSize) params.append('page_size', String(options.pageSize));

  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchAPI(`/api/v1/companies/${companyId}/insights${query}`);
}

export async function getInsight(companyId: string, insightId: string): Promise<MarketInsight> {
  return fetchAPI(`/api/v1/companies/${companyId}/insights/${insightId}`);
}

export async function markInsightsRead(companyId: string, insightIds: string[]): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/insights/mark-read`, {
    method: 'POST',
    body: JSON.stringify({ insight_ids: insightIds }),
  });
}

export async function archiveInsights(companyId: string, insightIds: string[]): Promise<void> {
  return fetchAPI(`/api/v1/companies/${companyId}/insights/archive`, {
    method: 'POST',
    body: JSON.stringify({ insight_ids: insightIds }),
  });
}

export async function unarchiveInsight(
  companyId: string,
  insightId: string
): Promise<MarketInsight> {
  return fetchAPI(`/api/v1/companies/${companyId}/insights/${insightId}/unarchive`, {
    method: 'POST',
  });
}

export async function getInsightsSummary(
  companyId: string
): Promise<{
  total_insights: number;
  unread_insights: number;
  high_impact_count: number;
  recent_trends: MarketInsight[];
  top_opportunities: MarketInsight[];
}> {
  return fetchAPI(`/api/v1/companies/${companyId}/insights/summary`);
}

// ============================================================================
// Exports API
// ============================================================================

export function getExportUrl(
  companyId: string,
  type: 'analysis' | 'competitors' | 'battlecards' | 'icps' | 'leads' | 'campaign' | 'full-report',
  id?: string,
  options?: { minScore?: number; status?: string }
): string {
  let path = `/api/v1/exports/${companyId}`;

  switch (type) {
    case 'analysis':
      path += `/analysis/${id}/json`;
      break;
    case 'competitors':
      path += '/competitors/json';
      break;
    case 'battlecards':
      path += '/battlecards/json';
      break;
    case 'icps':
      path += '/icps/json';
      break;
    case 'leads':
      const params = new URLSearchParams();
      if (options?.minScore) params.append('min_score', String(options.minScore));
      if (options?.status) params.append('status', options.status);
      path += `/leads/json${params.toString() ? `?${params.toString()}` : ''}`;
      break;
    case 'campaign':
      path += `/campaigns/${id}/json`;
      break;
    case 'full-report':
      path += '/full-report/json';
      break;
  }

  return `${API_BASE_URL}${path}`;
}

// ============================================================================
// User Settings API
// ============================================================================

export async function getUserSettings(userId: string): Promise<UserSettings> {
  return fetchAPI(`/api/v1/settings/me?user_id=${userId}`);
}

export async function updateUserSettings(
  userId: string,
  data: Partial<{
    full_name: string;
    company_name: string;
    preferences: Partial<UserPreferences>;
  }>
): Promise<UserSettings> {
  return fetchAPI(`/api/v1/settings/me?user_id=${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function getUsageStats(
  userId: string
): Promise<{
  daily_requests: { used: number; limit: number; remaining: number };
  last_request_date: string | null;
  tier: string;
  tier_display_name: string;
}> {
  return fetchAPI(`/api/v1/settings/usage?user_id=${userId}`);
}

export { APIError };
