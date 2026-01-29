# Gap Analysis: Business Plan vs Current Implementation

## Business Plan Overview

### Brand Identity
- **Proposed Name**: HiMeet AI Pte. Ltd.
- **Brand**: HiMeet
- **Products**: HiMeet Platform ($700), HiMeet Advisory ($7,000)

### Target Positioning
> "An AI-powered marketing execution engine informed by strategy" (Tier 1)
> "A C-suite growth partner that governs marketing" (Tier 2)

### Key Differentiators
- NOT an agency
- NOT a SaaS tool
- Advisory-first, intelligence-led, outcome-driven

---

## Agent Mapping: Business Plan → Current Implementation

### 1. Enterprise Marketing & Growth Strategy Agent

**Business Plan Requirements:**
- Ingest company inputs (industry, ambition, revenue targets, constraints)
- Analyse business model, revenue levers, pricing logic, margin drivers
- Synthesize market, customer, competitive insights into growth hypotheses
- Identify strategic growth priorities and trade-offs
- Stress-test assumptions and highlight execution/reputational risks
- Translate analysis into board-ready strategic recommendations

**Current Implementation:** `GTMStrategistAgent`

| Requirement | Status | Gap |
|-------------|--------|-----|
| Ingest company inputs | ✅ Partial | Missing: revenue targets, constraints, margin drivers |
| Analyse business model | ❌ Missing | No business model analysis capability |
| Growth hypotheses | ❌ Missing | No hypothesis generation |
| Strategic priorities | ⚠️ Basic | Generic recommendations only |
| Stress-test assumptions | ❌ Missing | No risk analysis |
| Board-ready outputs | ❌ Missing | No executive formatting |

**Required Changes:**
```python
# Extend UserRequirements model
class UserRequirements(BaseModel):
    # ADD:
    revenue_targets: dict[str, float]  # {"year1": 1000000, "year2": 2000000}
    constraints: list[str]  # Budget, team size, timeline
    margin_targets: float
    risk_tolerance: str  # conservative, moderate, aggressive

# ADD new output type
class BoardReadyBrief(BaseModel):
    executive_summary: str  # 1 paragraph
    strategic_priorities: list[StrategicPriority]
    growth_hypotheses: list[GrowthHypothesis]
    risk_assessment: RiskMatrix
    recommended_actions: list[ActionItem]
    appendix: dict[str, Any]
```

---

### 2. Continuous Market & Competitive Intelligence Agent

**Business Plan Requirements:**
- Continuously scan market, industry, regulatory, macroeconomic signals
- Monitor competitor positioning, messaging, GTM moves, campaigns
- Track share of voice, narrative ownership, influence shifts
- Identify emerging threats, opportunities, white spaces
- Surface early-warning alerts with business implications
- Translate intelligence into executive-level insights

**Current Implementation:** `MarketIntelligenceAgent` + `CompetitorAnalystAgent`

| Requirement | Status | Gap |
|-------------|--------|-----|
| Continuous scanning | ❌ Missing | One-time analysis only |
| Competitor monitoring | ⚠️ Basic | No ongoing tracking |
| Share of voice | ❌ Missing | No social listening |
| Early-warning alerts | ❌ Missing | No alert system |
| Executive insights | ⚠️ Basic | No "what this means" framing |

**Required Changes:**
```python
# NEW: Continuous monitoring service
class IntelligenceMonitor:
    async def schedule_scan(self, company_id: UUID, frequency: str):
        """Schedule recurring intelligence scans."""

    async def compare_to_baseline(self, current: IntelReport, baseline: IntelReport):
        """Identify what changed since last scan."""

    async def generate_alerts(self, changes: list[Change]) -> list[Alert]:
        """Surface significant changes as alerts."""

# NEW: Share of voice tracking
class ShareOfVoiceTracker:
    async def track_mentions(self, brand: str, competitors: list[str]):
        """Track brand mentions across platforms."""

    async def calculate_sov(self, period: str) -> SOVReport:
        """Calculate share of voice metrics."""
```

**Data Sources Needed:**
- Social listening API (Brandwatch, Sprout Social, or build with Twitter/LinkedIn APIs)
- Regulatory feed (Singapore government announcements)
- Scheduled job runner (Celery, APScheduler, or cron)

---

### 3. GTM Strategy & Commercialisation Agent

**Business Plan Requirements:**
- Analyse priority segments, buying committees, routes to market
- Design GTM strategies aligned to growth and revenue objectives
- Evaluate channel effectiveness across owned, earned, paid, partnerships
- Recommend pricing, packaging, offer structures
- Align marketing outputs with sales enablement needs
- Define success metrics tied to commercial outcomes

**Current Implementation:** Partially in `GTMStrategistAgent`, mostly missing

| Requirement | Status | Gap |
|-------------|--------|-----|
| Segment analysis | ⚠️ Basic | In CustomerProfiler, not commercial focus |
| Buying committees | ❌ Missing | No B2B buying process mapping |
| GTM strategy design | ⚠️ Generic | No revenue-aligned strategies |
| Channel effectiveness | ❌ Missing | No channel analysis |
| Pricing/packaging | ❌ Missing | No pricing optimization |
| Sales enablement | ❌ Missing | No sales alignment |
| Success metrics | ⚠️ Basic | Not tied to commercial outcomes |

**Required Changes:**
```python
# NEW AGENT: agents/gtm_commercial/
class GTMCommercialAgent(BaseGTMAgent[CommercialStrategyOutput]):
    """GTM Strategy & Commercialisation Agent."""

    async def analyze_buying_committee(self, company_profile: CompanyProfile):
        """Map the buying committee structure."""

    async def evaluate_channels(self, current_channels: list[Channel]):
        """Analyze channel effectiveness and recommend changes."""

    async def optimize_pricing(self, current_pricing: PricingModel):
        """Recommend pricing and packaging improvements."""

    async def create_sales_enablement(self, strategy: GTMStrategy):
        """Generate sales enablement materials."""

class CommercialStrategyOutput(BaseModel):
    segment_priorities: list[SegmentPriority]
    buying_committee_map: BuyingCommitteeMap
    gtm_strategy: GTMStrategy
    channel_recommendations: list[ChannelRecommendation]
    pricing_recommendations: PricingRecommendation
    sales_enablement: SalesEnablementPack
    success_metrics: list[CommercialKPI]
```

---

### 4. Strategic Campaign Architecture Agent

**Business Plan Requirements:**
- Translate business/GTM objectives into campaign strategies
- Define campaign audiences across decision-makers and influencers
- Develop campaign narrative and message architecture
- Model budget allocation scenarios based on impact and ROI
- Orchestrate channel sequencing and integration
- Define outcome-led KPIs beyond vanity metrics

**Current Implementation:** `CampaignArchitectAgent`

| Requirement | Status | Gap |
|-------------|--------|-----|
| Campaign strategies | ✅ Yes | Needs business objective alignment |
| Audience definition | ✅ Yes | Needs buying committee integration |
| Message architecture | ✅ Yes | Good |
| Budget modeling | ❌ Missing | No ROI modeling |
| Channel sequencing | ⚠️ Basic | No orchestration logic |
| Outcome-led KPIs | ⚠️ Basic | Mostly vanity metrics |

**Required Changes:**
```python
# EXTEND CampaignArchitectAgent
class CampaignArchitectAgent(BaseGTMAgent[CampaignOutput]):
    # ADD methods:
    async def model_budget_scenarios(
        self,
        total_budget: float,
        objectives: list[Objective]
    ) -> list[BudgetScenario]:
        """Model 3 budget allocation scenarios with ROI projections."""

    async def design_channel_sequence(
        self,
        channels: list[Channel],
        buyer_journey: BuyerJourney
    ) -> ChannelOrchestration:
        """Design integrated channel sequencing."""

    async def define_outcome_kpis(
        self,
        business_objectives: list[Objective]
    ) -> list[OutcomeKPI]:
        """Define KPIs tied to business outcomes, not vanity metrics."""

# NEW types
class BudgetScenario(BaseModel):
    name: str  # "Conservative", "Balanced", "Aggressive"
    allocations: dict[str, float]  # {"linkedin": 0.4, "content": 0.3, ...}
    projected_roi: float
    projected_leads: int
    risk_level: str

class OutcomeKPI(BaseModel):
    metric: str
    target: float
    business_outcome: str  # "Revenue", "Pipeline", "Retention"
    measurement_method: str
    vanity_equivalent: str | None  # What vanity metric this replaces
```

---

### 5. Brand, Narrative & Corporate Communications Agent

**Business Plan Requirements:**
- Map media, platform, influencer landscapes
- Analyse existing brand narratives and credibility gaps
- Develop corporate narrative and message frameworks
- Identify thought leadership opportunities for senior leaders
- Recommend channels and formats to build trust
- Monitor sentiment, tone of voice, narrative consistency

**Current Implementation:** ❌ **DOES NOT EXIST**

**Required: New Agent**
```python
# NEW: agents/brand_communications/
class BrandCommunicationsAgent(BaseGTMAgent[BrandAnalysisOutput]):
    """Brand, Narrative & Corporate Communications Agent."""

    def __init__(self):
        super().__init__(
            name="brand-communications",
            description="Develops and governs brand narrative and communications strategy",
            result_type=BrandAnalysisOutput,
            min_confidence=0.70,
        )

    async def map_media_landscape(self, industry: str, region: str):
        """Map relevant media outlets, platforms, influencers."""

    async def analyze_brand_narrative(self, company: CompanyProfile):
        """Analyze current narrative and identify gaps."""

    async def develop_message_framework(self, strategy: GTMStrategy):
        """Create corporate narrative and message house."""

    async def identify_thought_leadership(self, executives: list[Executive]):
        """Identify thought leadership opportunities."""

    async def monitor_sentiment(self, brand: str):
        """Track sentiment and narrative consistency."""

class BrandAnalysisOutput(BaseModel):
    media_landscape: MediaLandscapeMap
    current_narrative_analysis: NarrativeAnalysis
    credibility_gaps: list[CredibilityGap]
    message_framework: MessageFramework
    thought_leadership_opportunities: list[ThoughtLeadershipOpp]
    channel_recommendations: list[ChannelRecommendation]
    sentiment_baseline: SentimentReport
```

**Data Sources Needed:**
- Media database (Muck Rack, Cision, or build custom)
- Social listening (for sentiment)
- Influencer discovery API
- Content analysis pipeline

---

### 6. Marketing Performance Governance & ROI Agent

**Business Plan Requirements:**
- Define marketing performance governance frameworks
- Track full-funnel performance (visibility → engagement → qualified demand)
- Analyse marketing investment effectiveness and efficiency
- Identify underperforming and high-performing initiatives
- Generate executive-ready performance insights
- Support quarterly and board-level reviews

**Current Implementation:** ❌ **DOES NOT EXIST**

**Required: New Agent**
```python
# NEW: agents/performance_governance/
class PerformanceGovernanceAgent(BaseGTMAgent[PerformanceReport]):
    """Marketing Performance Governance & ROI Agent."""

    def __init__(self):
        super().__init__(
            name="performance-governance",
            description="Governs marketing performance and ROI accountability",
            result_type=PerformanceReport,
            min_confidence=0.80,
        )

    async def define_governance_framework(self, company: CompanyProfile):
        """Define performance governance structure."""

    async def track_full_funnel(self, period: str):
        """Track visibility → engagement → demand metrics."""

    async def analyze_investment_effectiveness(self, spend_data: SpendData):
        """Analyze marketing spend ROI."""

    async def identify_performance_outliers(self, metrics: list[Metric]):
        """Flag under/over performers."""

    async def generate_board_report(self, period: str):
        """Generate board-ready performance summary."""

class PerformanceReport(BaseModel):
    period: str
    governance_framework: GovernanceFramework
    funnel_metrics: FunnelMetrics
    roi_analysis: ROIAnalysis
    outliers: list[PerformanceOutlier]
    recommendations: list[PerformanceRecommendation]
    board_summary: BoardSummary
```

**Data Integrations Needed:**
- Google Analytics 4
- Marketing automation (HubSpot, Marketo)
- CRM (Salesforce, HubSpot CRM)
- Ad platforms (Google Ads, LinkedIn Ads, Meta)
- Finance/spend tracking

---

### 7. Qualified Demand & Pipeline Enablement Agent (PDPA-Safe)

**Business Plan Requirements:**
- Define what constitutes "qualified demand" for the organisation
- Analyse buyer intent signals and high-value engagement behaviours
- Map content and campaigns to conversion stages
- Apply lead scoring and prioritisation logic (PDPA-compliant)
- Identify accounts/opportunities ready for sales follow-up
- Analyse pipeline contribution and conversion bottlenecks

**Current Implementation:** `LeadHunterAgent`

| Requirement | Status | Gap |
|-------------|--------|-----|
| Define qualified demand | ⚠️ Basic | Generic scoring, not customizable |
| Buyer intent signals | ❌ Missing | No intent data integration |
| Content-to-conversion mapping | ❌ Missing | No attribution |
| PDPA-compliant scoring | ⚠️ Framework exists | Not enforced in scoring |
| Sales-ready identification | ⚠️ Basic | No CRM integration |
| Pipeline analysis | ❌ Missing | No pipeline visibility |

**Required Changes:**
```python
# RENAME: lead_hunter → qualified_demand
# EXTEND capabilities

class QualifiedDemandAgent(ToolEmpoweredAgent[QualifiedDemandOutput]):
    """Qualified Demand & Pipeline Enablement Agent."""

    async def define_qualification_criteria(self, company: CompanyProfile):
        """Work with user to define what 'qualified' means for them."""

    async def analyze_intent_signals(self, accounts: list[Account]):
        """Analyze buyer intent from multiple sources."""

    async def map_content_attribution(self, conversions: list[Conversion]):
        """Map which content contributed to conversions."""

    async def score_with_consent(self, leads: list[Lead]):
        """Score leads with PDPA consent verification."""

    async def identify_sales_ready(self, scored_leads: list[ScoredLead]):
        """Identify accounts ready for sales outreach."""

    async def analyze_pipeline(self, pipeline: Pipeline):
        """Analyze pipeline health and bottlenecks."""

# Enhanced output
class QualifiedDemandOutput(BaseModel):
    qualification_criteria: QualificationCriteria
    intent_analysis: IntentAnalysis
    content_attribution: ContentAttributionReport
    qualified_accounts: list[QualifiedAccount]
    sales_ready_accounts: list[SalesReadyAccount]
    pipeline_analysis: PipelineAnalysis
    pdpa_compliance: PDPAComplianceReport
```

**Data Sources Needed:**
- Website analytics (for behavioral intent)
- Email engagement data
- Content consumption tracking
- CRM pipeline data

---

## Tier-Specific Feature Matrix

### Tier 1: $700/month (Self-Serve)

| Feature | Current Status | Required |
|---------|----------------|----------|
| Monthly intelligence summary | ❌ | Automated monthly report |
| Competitive monitoring | ❌ | Competitor tracking dashboard |
| Campaign builder | ❌ | Self-serve campaign planner |
| Content generation | ❌ | 50 pieces/month limit |
| Distribution planning | ❌ | Channel recommendations |
| Performance snapshot | ❌ | Monthly metrics summary |
| Self-serve UI | ⚠️ Partial | Full workflow UI |

### Tier 2: $7,000/month (Advisory + Governance)

| Feature | Current Status | Required |
|---------|----------------|----------|
| All Tier 1 features | ❌ | Yes, unlimited |
| Board-ready outputs | ❌ | Executive templates |
| Human-in-the-loop | ❌ (auto-approve) | Real approval workflows |
| Monthly advisory session | ❌ | Calendar + notes integration |
| Full agent capabilities | ⚠️ | All 7 agents, full depth |
| Pipeline governance | ❌ | Full pipeline visibility |
| Custom integrations | ❌ | API access, webhooks |

---

## Data Integration Gaps

| Integration | Business Plan Need | Current Status | Priority |
|-------------|-------------------|----------------|----------|
| CRM (HubSpot/Salesforce) | Pipeline, contacts | Mock only | P1 |
| Google Analytics | Performance tracking | None | P1 |
| LinkedIn Ads | Campaign performance | None | P2 |
| Social listening | Sentiment, SOV | None | P2 |
| Email platform | Engagement signals | None | P2 |
| Finance/ERP | Spend data | None | P2 |
| Media database | PR landscape | None | P3 |

---

## UI/UX Gaps for Business Plan

### Missing Screens

1. **Tier Selection & Onboarding**
   - Pricing comparison
   - Feature explanation
   - Payment integration (Stripe)

2. **Self-Serve Dashboard (Tier 1)**
   - Intelligence feed
   - Campaign builder
   - Content generator
   - Performance metrics

3. **Advisory Dashboard (Tier 2)**
   - Board report generator
   - Approval workflow
   - Advisory session scheduler
   - Custom report builder

4. **Settings & Integrations**
   - API key management
   - Platform connections
   - Notification preferences
   - Team management (Tier 2)

---

## Summary: Effort Estimation

| Category | New Development | Modifications | Estimated Effort |
|----------|-----------------|---------------|------------------|
| New Agents | 2 agents | - | 3-4 weeks |
| Agent Enhancements | - | 5 agents | 2-3 weeks |
| Tier Implementation | Full system | - | 2-3 weeks |
| Data Integrations | 5-7 integrations | - | 3-4 weeks |
| UI/UX | 4 major screens | 3 screens | 2-3 weeks |
| Testing | Full suite | - | 2 weeks |
| **Total** | | | **14-19 weeks** |

With parallel development across team members, this could be compressed to **10-12 weeks**.
