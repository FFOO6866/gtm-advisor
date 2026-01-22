export interface CompanyInfo {
  name: string;
  description: string;
  industry: string;
  goals: string[];
  competitors: string[];
  valueProposition?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'agent';
  agentId?: string;
  content: string;
  timestamp: Date;
}

export interface AgentActivity {
  agentId: string;
  status: 'idle' | 'thinking' | 'active' | 'complete';
  progress: number;
  currentTask?: string;
}

export interface Lead {
  name: string;
  fitScore: number;
  industry: string;
  size: string;
  scoringMethod?: 'algorithm' | 'llm';  // How this lead was scored
  expectedValue?: number;  // Pipeline value
}

// Decision attribution for transparency
export interface DecisionAttribution {
  algorithmDecisions: number;
  llmDecisions: number;
  toolCalls: number;
  determinismRatio: number;  // 0-1, higher = more deterministic
  breakdown: DecisionBreakdown[];
}

export interface DecisionBreakdown {
  layer: 'cognitive' | 'analytical' | 'operational' | 'governance';
  component: string;
  decision: string;
  confidence: number;
  executionTimeMs: number;
}

export interface Insight {
  text: string;
}

export interface Campaign {
  type: string;
  title: string;
  ready: boolean;
}

export interface AnalysisResult {
  leads: Lead[];
  insights: string[];
  campaigns: Campaign[];
  decisionAttribution?: DecisionAttribution;
  totalPipelineValue?: number;
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
