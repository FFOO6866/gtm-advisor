/**
 * GTM Advisor API Client
 *
 * Production-ready API client for connecting to the backend gateway.
 * NO mock data, NO fallbacks - real API calls only.
 */

/// <reference types="vite/client" />

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

// Types matching backend Pydantic models
export interface AnalysisRequest {
  company_name: string;
  website?: string;  // Company website for A2A company enrichment
  description: string;
  industry: string;
  goals: string[];
  challenges: string[];
  competitors: string[];
  target_markets: string[];
  value_proposition?: string;
  include_market_research?: boolean;
  include_competitor_analysis?: boolean;
  include_customer_profiling?: boolean;
  include_lead_generation?: boolean;
  include_campaign_planning?: boolean;
  lead_count?: number;
}

export interface AnalysisStatus {
  analysis_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  current_agent: string | null;
  completed_agents: string[];
  error: string | null;
}

export interface Lead {
  id: string;
  company_name: string;
  contact_name: string | null;
  contact_title: string | null;
  contact_email: string | null;
  industry: string;
  employee_count: number | null;
  location: string | null;
  website: string | null;
  fit_score: number;
  intent_score: number;
  overall_score: number;
  pain_points: string[];
  trigger_events: string[];
  recommended_approach: string | null;
  source: string;
}

export interface MarketInsight {
  id: string;
  title: string;
  summary: string;
  category: string;
  key_findings: string[];
  implications: string[];
  recommendations: string[];
  sources: string[];
  confidence: number;
}

export interface CompetitorAnalysis {
  id: string;
  competitor_name: string;
  website: string | null;
  description: string;
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
  products: string[];
  positioning: string | null;
  key_differentiators: string[];
  confidence: number;
}

export interface CustomerPersona {
  id: string;
  name: string;
  role: string;
  company_size: string | null;
  industries: string[];
  goals: string[];
  challenges: string[];
  pain_points: string[];
  preferred_channels: string[];
}

export interface CampaignBrief {
  id: string;
  name: string;
  objective: string;
  target_persona: string | null;
  key_messages: string[];
  value_propositions: string[];
  call_to_action: string | null;
  channels: string[];
  email_templates: string[];
  linkedin_posts: string[];
}

export interface GTMAnalysisResult {
  id: string;
  company_id: string;
  market_insights: MarketInsight[];
  competitor_analysis: CompetitorAnalysis[];
  customer_personas: CustomerPersona[];
  leads: Lead[];
  campaign_brief: CampaignBrief | null;
  executive_summary: string;
  key_recommendations: string[];
  agents_used: string[];
  total_confidence: number;
  processing_time_seconds: number;
}

export interface AnalysisResponse {
  analysis_id: string;
  status: string;
  result: GTMAnalysisResult | null;
  processing_time_seconds: number;
}

export interface AgentCard {
  name: string;
  title: string;
  description: string;
  status: string;
  capabilities: { name: string; description: string }[];
  avatar: string | null;
  color: string;
}

export interface WebSocketMessage {
  type: 'analysis_started' | 'agent_started' | 'agent_completed' | 'analysis_completed' | 'error' | 'a2a_message';
  agentId: string | null;
  agentName: string | null;
  status: string | null;
  progress: number | null;
  message: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  timestamp: string | null;
}

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

async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
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

  return response.json();
}

// Health check
export async function checkHealth(): Promise<{ status: string }> {
  return fetchAPI('/health');
}

// Agents
export async function listAgents(): Promise<AgentCard[]> {
  return fetchAPI('/api/v1/agents');
}

export async function getAgent(agentName: string): Promise<AgentCard> {
  return fetchAPI(`/api/v1/agents/${agentName}`);
}

// Analysis
export async function startAnalysis(
  request: AnalysisRequest
): Promise<AnalysisStatus> {
  return fetchAPI('/api/v1/analysis/start', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getAnalysisStatus(
  analysisId: string
): Promise<AnalysisStatus> {
  return fetchAPI(`/api/v1/analysis/${analysisId}/status`);
}

export async function getAnalysisResult(
  analysisId: string
): Promise<AnalysisResponse> {
  return fetchAPI(`/api/v1/analysis/${analysisId}/result`);
}

export async function runQuickAnalysis(
  request: AnalysisRequest
): Promise<AnalysisResponse> {
  return fetchAPI('/api/v1/analysis/quick', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// WebSocket connection for real-time updates
export function connectToAnalysis(
  analysisId: string,
  onMessage: (message: WebSocketMessage) => void,
  onError?: (error: Event) => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE_URL}/ws/analysis/${analysisId}`);

  ws.onopen = () => {
    console.log(`WebSocket connected for analysis: ${analysisId}`);
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data) as WebSocketMessage;
      onMessage(message);
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    onError?.(error);
  };

  ws.onclose = () => {
    console.log(`WebSocket closed for analysis: ${analysisId}`);
    onClose?.();
  };

  return ws;
}

// Polling fallback for environments where WebSocket isn't available
export function pollAnalysisStatus(
  analysisId: string,
  onUpdate: (status: AnalysisStatus) => void,
  onComplete: (result: AnalysisResponse) => void,
  onError: (error: Error) => void,
  intervalMs: number = 2000
): () => void {
  let isRunning = true;

  const poll = async () => {
    while (isRunning) {
      try {
        const status = await getAnalysisStatus(analysisId);
        onUpdate(status);

        if (status.status === 'completed') {
          const result = await getAnalysisResult(analysisId);
          onComplete(result);
          isRunning = false;
          return;
        }

        if (status.status === 'failed') {
          onError(new Error(status.error || 'Analysis failed'));
          isRunning = false;
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, intervalMs));
      } catch (e) {
        onError(e instanceof Error ? e : new Error(String(e)));
        isRunning = false;
        return;
      }
    }
  };

  poll();

  return () => {
    isRunning = false;
  };
}

export { APIError };
