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
    scoringMethod: backend.source || 'unknown',
    verifiedEmail: backend.verified_email,
    emailDomainValid: backend.email_domain_valid,
    buyingCycleStage: backend.buying_cycle_stage ?? undefined,
    contactLinkedin: backend.contact_linkedin ?? undefined,
    status: backend.status ?? undefined,
    sourceUrl: backend.source_url ?? undefined,
    lastEnrichedAt: backend.last_enriched_at ?? undefined,
    createdAt: backend.created_at ?? undefined,
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
    relevantIndustries: backend.relevant_industries ?? [],
    relevantToCompany: backend.relevant_to_company ?? true,
    createdAt: backend.created_at ?? undefined,
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
    foundedYear: backend.founded_year ?? undefined,
    employeeCount: backend.employee_count ?? undefined,
    fundingRaised: backend.funding_raised ?? undefined,
    headquarters: backend.headquarters ?? undefined,
    pricingModel: backend.pricing_model ?? undefined,
    targetMarket: backend.target_market ?? undefined,
    marketShareEstimate: backend.market_share_estimate ?? undefined,
    recentNews: backend.recent_news ?? [],
    strategicMoves: backend.strategic_moves ?? [],
    pricingTiers: (backend.pricing_tiers ?? []).map(t => ({
      tierName: t.tier_name,
      priceSgd: t.price_sgd,
      priceUsd: t.price_usd,
      frequency: t.frequency,
      featuresSummary: t.features_summary,
      source: t.source,
    })),
    latestFunding: backend.latest_funding ? {
      roundType: backend.latest_funding.round_type,
      amountUsd: backend.latest_funding.amount_usd,
      announcedDate: backend.latest_funding.announced_date,
      investors: backend.latest_funding.investors,
      useOfFunds: backend.latest_funding.use_of_funds,
    } : undefined,
    employeeCountEstimate: backend.employee_count_estimate ?? undefined,
    hiringVelocity: backend.hiring_velocity ?? undefined,
    recentExecutiveMoves: backend.recent_executive_moves ?? [],
    sources: backend.sources ?? [],
    createdAt: backend.created_at ?? undefined,
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
    ageRange: backend.age_range ?? undefined,
    experienceLevel: backend.experience_level ?? undefined,
    education: backend.education ?? undefined,
    companyStage: backend.company_stage ?? undefined,
    motivations: backend.motivations ?? [],
    objections: backend.objections ?? [],
    informationSources: backend.information_sources ?? [],
    decisionCriteria: backend.decision_criteria ?? [],
    buyingProcess: backend.buying_process ?? undefined,
    contentPreferences: backend.content_preferences ?? [],
    messagingTone: backend.messaging_tone ?? undefined,
    createdAt: backend.created_at ?? undefined,
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
    targetIndustries: backend.target_industries ?? [],
    targetCompanySize: backend.target_company_size ?? undefined,
    targetGeography: backend.target_geography ?? [],
    budgetSgd: backend.budget_sgd ?? undefined,
    contentIdeas: backend.content_ideas ?? [],
    createdAt: backend.created_at ?? undefined,
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
  const BASE_ACV_SGD = 15000; // Conservative SME SaaS ACV
  const totalPipelineValue = leads.reduce(
    (sum, lead) => sum + (lead.overallScore ?? 0) * BASE_ACV_SGD,
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
    decisionAttribution = {
      algorithmDecisions: decisionData.algorithmDecisions,
      llmDecisions: decisionData.llmDecisions,
      toolCalls: decisionData.toolCalls,
      determinismRatio: decisionData.determinismRatio,
      breakdown: [
        // Generate breakdown based on actual decisions
        ...leads.map((lead) => ({
          layer: 'analytical' as const,
          component: 'ICP Scorer',
          decision: `Fit score: ${lead.fitScore.toFixed(2)}`,
          confidence: lead.fitScore,
        })),
        {
          layer: 'operational' as const,
          component: 'Company Enrichment',
          decision: `Enriched ${leads.length} companies`,
          confidence: 1.0,
        },
        {
          layer: 'cognitive' as const,
          component: 'LLM Synthesis',
          decision: 'Generated market insights',
          confidence: backend.total_confidence,
        },
        {
          layer: 'governance' as const,
          component: 'PDPA Checker',
          decision: 'Data compliant',
          confidence: 1.0,
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
    marketSizing: backend.market_sizing ? (() => {
      const ms = backend.market_sizing as Record<string, unknown>;
      return {
        tamDescription: (ms.tam_description as string) ?? '',
        samDescription: (ms.sam_description as string) ?? '',
        somDescription: (ms.som_description as string) ?? '',
        tamSgdEstimate: ms.tam_sgd_estimate as string | undefined,
        samSgdEstimate: ms.sam_sgd_estimate as string | undefined,
        somSgdEstimate: ms.som_sgd_estimate as string | undefined,
        assumptions: (ms.assumptions as string[]) ?? [],
      };
    })() : undefined,
    salesMotion: backend.sales_motion ? (() => {
      const sm = backend.sales_motion as Record<string, unknown>;
      return {
        primaryMotion: (sm.primary_motion as string) ?? '',
        dealSizeSgd: (sm.deal_size_sgd as string) ?? '',
        salesCycleDays: sm.sales_cycle_days as number | undefined,
        keyObjections: (sm.key_objections as string[]) ?? [],
        winThemes: (sm.win_themes as string[]) ?? [],
        recommendedFirst90Days: (sm.recommended_first_90_days as string[]) ?? [],
      };
    })() : undefined,
    outreachSequences: (backend.outreach_sequences ?? []).map((seq) => {
      const s = seq as Record<string, unknown>;
      return {
        name: (s.name as string) ?? '',
        targetPersona: s.target_persona as string | undefined,
        steps: ((s.steps as unknown[]) ?? []).map((step) => {
          const st = step as Record<string, unknown>;
          return {
            stepNumber: (st.step_number as number) ?? (st.day as number) ?? 0,
            channelType: (st.channel_type as string) ?? (st.channel as string) ?? '',
            subjectLine: (st.subject_line as string) ?? '',
            timing: (st.timing as string) ?? (st.timing_description as string) ?? '',
          };
        }),
      };
    }),
    successMetrics: backend.success_metrics ?? [],
    complianceFlags: backend.compliance_flags ?? [],
    totalPipelineValue,
    decisionAttribution,
  };
}
