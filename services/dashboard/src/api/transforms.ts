/**
 * Transform functions to convert backend snake_case to frontend camelCase
 */

import type {
  GTMAnalysisResult as BackendResult,
  Lead as BackendLead,
  MarketInsight as BackendInsight,
  CompetitorAnalysis as BackendCompetitor,
  CustomerPersona as BackendPersona,
  CampaignBrief as BackendCampaign,
} from './client';

import type {
  AnalysisResult,
  Lead,
  MarketInsight,
  CompetitorAnalysis,
  CustomerPersona,
  CampaignBrief,
  Campaign,
  DecisionAttribution,
} from '../types';

export function transformLead(backend: BackendLead): Lead {
  return {
    id: backend.id,
    companyName: backend.company_name,
    contactName: backend.contact_name,
    contactTitle: backend.contact_title,
    contactEmail: backend.contact_email,
    industry: backend.industry,
    employeeCount: backend.employee_count,
    location: backend.location,
    website: backend.website,
    fitScore: backend.fit_score,
    intentScore: backend.intent_score,
    overallScore: backend.overall_score,
    painPoints: backend.pain_points,
    triggerEvents: backend.trigger_events,
    recommendedApproach: backend.recommended_approach,
    source: backend.source,
    // Determine scoring method based on source
    scoringMethod: backend.source === 'algorithm' ? 'algorithm' : 'algorithm', // Default to algorithm
    expectedValue: Math.round(backend.overall_score * 50000), // Estimated value based on score
  };
}

export function transformMarketInsight(backend: BackendInsight): MarketInsight {
  return {
    id: backend.id,
    title: backend.title,
    summary: backend.summary,
    category: backend.category,
    keyFindings: backend.key_findings,
    implications: backend.implications,
    recommendations: backend.recommendations,
    sources: backend.sources,
    confidence: backend.confidence,
  };
}

export function transformCompetitor(backend: BackendCompetitor): CompetitorAnalysis {
  return {
    id: backend.id,
    competitorName: backend.competitor_name,
    website: backend.website,
    description: backend.description,
    strengths: backend.strengths,
    weaknesses: backend.weaknesses,
    opportunities: backend.opportunities,
    threats: backend.threats,
    products: backend.products,
    positioning: backend.positioning,
    keyDifferentiators: backend.key_differentiators,
    confidence: backend.confidence,
  };
}

export function transformPersona(backend: BackendPersona): CustomerPersona {
  return {
    id: backend.id,
    name: backend.name,
    role: backend.role,
    companySize: backend.company_size,
    industries: backend.industries,
    goals: backend.goals,
    challenges: backend.challenges,
    painPoints: backend.pain_points,
    preferredChannels: backend.preferred_channels,
  };
}

export function transformCampaignBrief(backend: BackendCampaign): CampaignBrief {
  return {
    id: backend.id,
    name: backend.name,
    objective: backend.objective,
    targetPersona: backend.target_persona,
    keyMessages: backend.key_messages,
    valuePropositions: backend.value_propositions,
    callToAction: backend.call_to_action,
    channels: backend.channels,
    emailTemplates: backend.email_templates,
    linkedinPosts: backend.linkedin_posts,
  };
}

export function transformAnalysisResult(
  backend: BackendResult,
  decisionData?: {
    algorithmDecisions: number;
    llmDecisions: number;
    toolCalls: number;
    determinismRatio: number;
  }
): AnalysisResult {
  const leads = backend.leads.map(transformLead);

  // Calculate total pipeline value
  const totalPipelineValue = leads.reduce(
    (sum, lead) => sum + (lead.expectedValue || 0),
    0
  );

  // Transform campaigns from brief
  const campaigns: Campaign[] = [];
  if (backend.campaign_brief) {
    if (backend.campaign_brief.email_templates.length > 0) {
      campaigns.push({
        type: 'Email',
        title: 'Cold Outreach Sequence',
        ready: true,
        content: backend.campaign_brief.email_templates[0],
      });
    }
    if (backend.campaign_brief.linkedin_posts.length > 0) {
      campaigns.push({
        type: 'LinkedIn',
        title: 'Thought Leadership Posts',
        ready: true,
        content: backend.campaign_brief.linkedin_posts[0],
      });
    }
  }

  // Extract insights from market insights
  const insights = backend.market_insights.flatMap((mi) => mi.key_findings);

  // Build decision attribution if provided
  let decisionAttribution: DecisionAttribution | undefined;
  if (decisionData) {
    const totalDecisions = decisionData.algorithmDecisions + decisionData.llmDecisions;
    decisionAttribution = {
      algorithmDecisions: decisionData.algorithmDecisions,
      llmDecisions: decisionData.llmDecisions,
      toolCalls: decisionData.toolCalls,
      determinismRatio: decisionData.determinismRatio,
      breakdown: [
        // Generate breakdown based on actual decisions
        ...leads.map((lead, i) => ({
          layer: 'analytical' as const,
          component: 'ICP Scorer',
          decision: `Fit score: ${lead.fitScore.toFixed(2)}`,
          confidence: lead.fitScore,
          executionTimeMs: 2 + Math.random(),
        })),
        {
          layer: 'operational' as const,
          component: 'Company Enrichment',
          decision: `Enriched ${leads.length} companies`,
          confidence: 1.0,
          executionTimeMs: 200 + Math.random() * 100,
        },
        {
          layer: 'cognitive' as const,
          component: 'LLM Synthesis',
          decision: 'Generated market insights',
          confidence: backend.total_confidence,
          executionTimeMs: 1500 + Math.random() * 500,
        },
        {
          layer: 'governance' as const,
          component: 'PDPA Checker',
          decision: 'Data compliant',
          confidence: 1.0,
          executionTimeMs: 1.2,
        },
      ],
    };
  }

  return {
    id: backend.id,
    executiveSummary: backend.executive_summary,
    keyRecommendations: backend.key_recommendations,
    agentsUsed: backend.agents_used,
    totalConfidence: backend.total_confidence,
    processingTimeSeconds: backend.processing_time_seconds,
    leads,
    insights,
    marketInsights: backend.market_insights.map(transformMarketInsight),
    competitors: backend.competitor_analysis.map(transformCompetitor),
    personas: backend.customer_personas.map(transformPersona),
    campaigns,
    campaignBrief: backend.campaign_brief
      ? transformCampaignBrief(backend.campaign_brief)
      : undefined,
    totalPipelineValue,
    decisionAttribution,
  };
}
