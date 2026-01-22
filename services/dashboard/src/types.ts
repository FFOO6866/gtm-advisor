/**
 * GTM Advisor Dashboard Types
 *
 * Types aligned with backend Pydantic models for production use.
 */

export interface CompanyInfo {
  name: string;
  description: string;
  industry: string;
  goals: string[];
  challenges: string[];
  competitors: string[];
  targetMarkets: string[];
  valueProposition?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'agent' | 'system';
  agentId?: string;
  agentName?: string;
  content: string;
  timestamp: Date;
}

export interface AgentActivity {
  agentId: string;
  agentName?: string;
  status: 'idle' | 'thinking' | 'active' | 'complete' | 'error';
  progress: number;
  currentTask?: string;
  message?: string;
}

// Lead from backend
export interface Lead {
  id: string;
  companyName: string;
  contactName: string | null;
  contactTitle: string | null;
  contactEmail: string | null;
  industry: string;
  employeeCount: number | null;
  location: string | null;
  website: string | null;
  fitScore: number;
  intentScore: number;
  overallScore: number;
  painPoints: string[];
  triggerEvents: string[];
  recommendedApproach: string | null;
  source: string;
  // UI display fields
  scoringMethod?: 'algorithm' | 'llm';
  expectedValue?: number;
}

// Market insight from backend
export interface MarketInsight {
  id: string;
  title: string;
  summary: string;
  category: string;
  keyFindings: string[];
  implications: string[];
  recommendations: string[];
  sources: string[];
  confidence: number;
}

// Competitor analysis from backend
export interface CompetitorAnalysis {
  id: string;
  competitorName: string;
  website: string | null;
  description: string;
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
  products: string[];
  positioning: string | null;
  keyDifferentiators: string[];
  confidence: number;
}

// Customer persona from backend
export interface CustomerPersona {
  id: string;
  name: string;
  role: string;
  companySize: string | null;
  industries: string[];
  goals: string[];
  challenges: string[];
  painPoints: string[];
  preferredChannels: string[];
}

// Campaign brief from backend
export interface CampaignBrief {
  id: string;
  name: string;
  objective: string;
  targetPersona: string | null;
  keyMessages: string[];
  valuePropositions: string[];
  callToAction: string | null;
  channels: string[];
  emailTemplates: string[];
  linkedinPosts: string[];
}

// Decision attribution for transparency
export interface DecisionAttribution {
  algorithmDecisions: number;
  llmDecisions: number;
  toolCalls: number;
  determinismRatio: number;
  breakdown: DecisionBreakdown[];
}

export interface DecisionBreakdown {
  layer: 'cognitive' | 'analytical' | 'operational' | 'governance';
  component: string;
  decision: string;
  confidence: number;
  executionTimeMs: number;
}

// Campaign for display (simplified)
export interface Campaign {
  type: string;
  title: string;
  ready: boolean;
  content?: string;
}

// Full analysis result
export interface AnalysisResult {
  // From backend
  id?: string;
  executiveSummary?: string;
  keyRecommendations?: string[];
  agentsUsed?: string[];
  totalConfidence?: number;
  processingTimeSeconds?: number;

  // Transformed for UI display
  leads: Lead[];
  insights: string[];
  marketInsights?: MarketInsight[];
  competitors?: CompetitorAnalysis[];
  personas?: CustomerPersona[];
  campaigns: Campaign[];
  campaignBrief?: CampaignBrief;

  // Metrics
  totalPipelineValue?: number;
  decisionAttribution?: DecisionAttribution;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  color: string;
  avatar: string;
  capabilities: string[];
}

export const AGENTS: Agent[] = [
  {
    id: 'gtm-strategist',
    name: 'GTM Strategist',
    description: 'Orchestrates your GTM strategy and coordinates the team',
    color: '139, 92, 246', // Purple
    avatar: '🎯',
    capabilities: ['Discovery', 'Strategy', 'Coordination'],
  },
  {
    id: 'market-intelligence',
    name: 'Market Intelligence',
    description: 'Analyzes market trends and opportunities',
    color: '16, 185, 129', // Green
    avatar: '📊',
    capabilities: ['Market Research', 'Trend Analysis', 'Data Synthesis'],
  },
  {
    id: 'competitor-analyst',
    name: 'Competitor Analyst',
    description: 'Researches competitors and positioning',
    color: '245, 158, 11', // Amber
    avatar: '🔍',
    capabilities: ['SWOT Analysis', 'Competitive Intel', 'Positioning'],
  },
  {
    id: 'customer-profiler',
    name: 'Customer Profiler',
    description: 'Develops ICPs and buyer personas',
    color: '236, 72, 153', // Pink
    avatar: '👥',
    capabilities: ['ICP Development', 'Persona Creation', 'Segmentation'],
  },
  {
    id: 'lead-hunter',
    name: 'Lead Hunter',
    description: 'Finds and qualifies real prospects',
    color: '59, 130, 246', // Blue
    avatar: '🎣',
    capabilities: ['Prospecting', 'Lead Scoring', 'Contact Research'],
  },
  {
    id: 'campaign-architect',
    name: 'Campaign Architect',
    description: 'Creates messaging and campaigns',
    color: '239, 68, 68', // Red
    avatar: '📣',
    capabilities: ['Messaging', 'Content Creation', 'Campaign Planning'],
  },
];

// Industry options matching backend
export const INDUSTRIES = [
  { value: 'fintech', label: 'Fintech' },
  { value: 'saas', label: 'SaaS' },
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'healthtech', label: 'Healthtech' },
  { value: 'edtech', label: 'Edtech' },
  { value: 'proptech', label: 'Proptech' },
  { value: 'logistics', label: 'Logistics' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'professional_services', label: 'Professional Services' },
  { value: 'other', label: 'Other' },
] as const;

export type IndustryValue = typeof INDUSTRIES[number]['value'];
