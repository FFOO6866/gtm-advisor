# Campaign Strategic Planner — Design Document

> **Date**: 2026-03-18
> **Core insight**: The Campaigns module is an autonomous AI marketing director, not a campaign builder.

---

## The Problem

Current Campaigns module is tactical: "Create a campaign → fill in fields → generate content → launch." This is what every marketing tool does. It's a form, not intelligence.

## The Vision

GTM Advisor acts as a **marketing agency** that:
1. **Diagnoses** where the company is (maturity, digital presence gaps, competitive position)
2. **Prescribes** a phased GTM roadmap grounded in the 14 marketing books + 18 domain guides
3. **Organises** campaigns across time horizons (Immediate → 30/60/90 days → 6-12 months → 1-3 years)
4. **Executes** each campaign autonomously (creative → approve → publish → monitor)
5. **Adapts** based on performance data

Every recommendation cites its source framework (Cialdini, RACE, Challenger, etc.) — this is the platform's differentiation vs ChatGPT.

---

## Knowledge Assets That Drive Recommendations

### Layer 1: Static Frameworks (always available)
| Framework | From | Drives |
|-----------|------|--------|
| RACE (Reach→Act→Convert→Engage) | Kingsnorth | Campaign phase sequencing |
| CIALDINI_PRINCIPLES (6 principles) | Cialdini | Campaign hook + CTA psychology |
| MESSAGING_FRAMEWORKS (AIDA, PAS, BAB, FAB, STAR) | Various | Per-campaign copy strategy |
| GTM_FRAMEWORKS (PLG, SLG, MLG, partner, community) | Strategy literature | Motion selection |
| STP_FRAMEWORK | Kotler | Segment → target → position |
| CAMPAIGN_BRIEF_TEMPLATE | Synthesized | Brief structure for each campaign |
| SINGAPORE_SME_CONTEXT | Local research | PSG, PDPA, market specifics |
| MARKETING_MIX_4P | Kotler | Tactical campaign mix |

### Layer 3: Qdrant Book Chunks (2,804 chunks from 14 books)
Semantic search for campaign-type-specific guidance: "how to launch a LinkedIn thought leadership series for Singapore B2B"

### Layer 4: Synthesized Domain Guides (18 guides)
`digital_awareness_campaign`, `cold_email_sequence`, `content_marketing_b2b`, `campaign_measurement`, `linkedin_b2b_campaign`, `gtm_motion_selection`, `singapore_market_entry`, `b2b_saas_pricing`, `icp_development`, `buyer_persona_research`, `buyer_journey_mapping`, `competitive_intelligence`, `positioning_differentiation`, `swot_to_strategy`, `market_sizing`, `industry_trend_analysis`, `lead_qualification`, `signal_based_prospecting`, `singapore_psg_grants`, `singapore_pdpa_gtm`, `singapore_asean_expansion`

---

## Data Model: GTM Roadmap

### New DB Model: `GTMRoadmap`

```python
class RoadmapPhase(str, PyEnum):
    IMMEDIATE = "immediate"      # Week 1-2: Foundation setup
    SHORT_TERM = "short_term"    # 30-60-90 days: Quick wins
    MID_TERM = "mid_term"        # 3-6 months: Growth engine
    LONG_TERM = "long_term"      # 6-12+ months: Scale + brand

class RoadmapStatus(str, PyEnum):
    PROPOSED = "proposed"        # AI proposed, not yet reviewed
    APPROVED = "approved"        # User accepted the roadmap
    IN_PROGRESS = "in_progress"  # Actively executing
    COMPLETED = "completed"
    REVISED = "revised"          # AI revised based on performance data

class GTMRoadmap(Base):
    """AI-generated strategic GTM roadmap for a company."""
    __tablename__ = "gtm_roadmaps"

    id
    company_id (FK)
    analysis_id (FK, nullable) — links to the analysis that generated context

    # Roadmap metadata
    title                     # e.g. "HiMeetAI 2026 GTM Roadmap"
    executive_summary         # 2-3 sentence overview
    gtm_motion                # PLG, SLG, MLG, hybrid
    status                    # proposed → approved → in_progress

    # AI reasoning (transparency)
    company_diagnosis         # JSON: maturity_stage, gaps, strengths, competitive_position
    frameworks_applied        # JSON: list of framework names used + why
    knowledge_sources         # JSON: which books/guides informed the plan

    # Timeline
    planning_horizon_months   # 12 (default)
    created_at
    updated_at
    approved_at
```

### Enhanced `Campaign` Model — Add Roadmap Link

```python
# Add to existing Campaign model:
roadmap_id (FK to GTMRoadmap, nullable)
phase: RoadmapPhase             # immediate, short_term, mid_term, long_term
priority_rank: int              # Order within phase (1 = first to execute)
framework_rationale: str        # "RACE:Reach — build brand visibility before outreach"
recommended_by_ai: bool         # True if AI-proposed, False if user-created
estimated_impact: str           # "High", "Medium", "Low"
depends_on_campaign_id (FK)     # Sequencing dependency
```

---

## Campaign Strategic Planner Agent

**Name**: `campaign-strategist` (NEW — separate from `campaign-architect`)

**Purpose**: Takes company context + analysis results → produces a full GTM Roadmap with phased campaigns.

**Distinction**:
- `campaign-strategist` = WHAT to do and WHEN (the marketing director)
- `campaign-architect` = HOW to do a specific campaign (the creative lead)

### Input Context
From analysis results + company profile:
- Company name, industry, description, products
- ICP segments (from Customer Profiler)
- Competitor landscape (from Competitor Analyst)
- Market signals (from Signal Monitor / Market Intel)
- Leads found (from Lead Hunter)
- Current digital presence (website, social profiles detected)

### PDCA Implementation

**_plan():**
1. Load ALL knowledge packs — this agent needs maximum book coverage
2. Query Qdrant for campaign planning chunks
3. Assess company maturity stage:
   - **Foundation** (no web presence, no social, no content) → heavy Immediate phase
   - **Early** (website exists, some content, no systematic outreach) → balanced Short/Mid
   - **Growth** (active campaigns, leads flowing, needs scale) → Mid/Long focus
   - **Mature** (established brand, optimising efficiency) → Long-term + innovation

**_do():**
1. Select GTM motion (PLG/SLG/MLG/hybrid) using GTM_FRAMEWORKS
2. Map RACE stages to time phases:
   - IMMEDIATE: Reach foundation (LinkedIn page, website SEO, basic content)
   - SHORT (30-60-90): Act (lead magnets, cold outreach, LinkedIn campaigns)
   - MID (3-6mo): Convert (case studies, webinars, sales enablement)
   - LONG (6-12mo): Engage (community, advocacy, thought leadership, ASEAN expansion)
3. For each phase, generate 2-4 campaigns with:
   - Objective + KPIs
   - Framework rationale ("Cialdini:Reciprocity — lead with free audit")
   - Channels (from RACE stage tactics)
   - Content types needed
   - Dependencies (Campaign B depends on Campaign A)
   - Estimated timeline and budget
4. Cross-reference with competitive landscape — differentiation opportunities
5. Inject Singapore-specific context (PSG eligibility, PDPA compliance)

**_check():**
- All 4 phases populated
- Each campaign has framework rationale (not generic)
- Dependencies form valid DAG (no circular)
- Budget is realistic for Singapore SME
- KPIs are measurable
- Knowledge sources cited

**_act():**
- Persist GTMRoadmap + Campaign rows
- Publish ROADMAP_READY event on bus

### Output: GTMRoadmapOutput

```python
class ProposedCampaign(BaseModel):
    name: str
    phase: str                  # immediate, short_term, mid_term, long_term
    priority_rank: int
    objective: str
    objective_type: str         # awareness, lead_gen, conversion, retention
    channels: list[str]
    content_types: list[str]    # linkedin_post, edm, whitepaper, webinar, case_study, landing_page
    framework_rationale: str    # "RACE:Reach + Cialdini:Social Proof"
    knowledge_source: str       # "Digital Marketing Strategy (Kingsnorth), Ch.4 — SEO-first awareness"
    target_persona: str
    kpis: list[str]
    estimated_duration_days: int
    estimated_budget_sgd: float
    depends_on: str | None      # Name of prerequisite campaign
    quick_win: bool             # Can show results in <2 weeks

class GTMRoadmapOutput(BaseModel):
    title: str
    executive_summary: str
    gtm_motion: str             # plg, slg, mlg, hybrid
    company_diagnosis: dict     # maturity, gaps, strengths
    planning_horizon_months: int

    # Phased campaigns
    immediate_campaigns: list[ProposedCampaign]    # Week 1-2
    short_term_campaigns: list[ProposedCampaign]   # 30-60-90 days
    mid_term_campaigns: list[ProposedCampaign]     # 3-6 months
    long_term_campaigns: list[ProposedCampaign]    # 6-12+ months

    # Framework transparency
    frameworks_applied: list[dict]   # [{name, why, campaigns_using}]
    knowledge_sources_cited: list[str]

    confidence: float
    data_sources_used: list[str]
```

---

## CampaignsPage Redesign

### New Layout: Roadmap-First

```
┌─────────────────────────────────────────────────────────────────┐
│  CAMPAIGNS                                           [+ New]    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  🎯 2026 GTM ROADMAP — HiMeetAI                         │   │
│  │  Motion: Marketing-Led Growth | Horizon: 12 months       │   │
│  │  Status: In Progress (4/12 campaigns active)             │   │
│  │  Based on: RACE Framework, Cialdini, Challenger Sale     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ─── IMMEDIATE (Week 1-2) ──── ✅ 3/3 complete ─────────────── │
│  ✅ Set up LinkedIn Company Page          [Reach · Cialdini:SP] │
│  ✅ Optimise website SEO + meta tags      [Reach · RACE]        │
│  ✅ Create lead magnet (PSG Calculator)   [Act · Reciprocity]   │
│                                                                  │
│  ─── SHORT TERM (30-60-90 days) ── 🔵 1/3 active ──────────── │
│  🔵 Cold Outreach Sequence (Fintech CTO)  [Convert · PAS]      │
│     └─ 12 leads enrolled · 2 replies · 8% reply rate           │
│  ⏳ LinkedIn Thought Leadership Series     [Reach · Authority]   │
│  ⏳ PSG-Eligible Webinar Campaign          [Act · Reciprocity]   │
│                                                                  │
│  ─── MID TERM (3-6 months) ── ⏳ planned ──────────────────── │
│  ⏳ Customer Case Study Programme          [Convert · STAR]      │
│  ⏳ Industry Report (Fintech GTM Trends)   [Reach · Authority]  │
│  ⏳ Referral Programme Launch              [Engage · Reciprocity]│
│                                                                  │
│  ─── LONG TERM (6-12 months) ── 📋 proposed ──────────────── │
│  📋 ASEAN Expansion Campaign              [Reach · STP]         │
│  📋 Community Platform Launch             [Engage · Social Proof]│
│  📋 Annual Conference / Event             [Reach+Engage]        │
└─────────────────────────────────────────────────────────────────┘
```

### Interaction Flow

1. **First visit (no roadmap)**: "Let me create your GTM roadmap" → Campaign Strategist agent runs in background → Roadmap appears
2. **Roadmap exists**: Shows phased view with campaign cards
3. **Click campaign card**: Opens campaign workspace (brief → assets → launch → monitor)
4. **"Regenerate Roadmap"**: Re-runs strategist with latest data (signals, performance)
5. **Drag to reorder**: User can reprioritise campaigns within a phase
6. **"Add Campaign"**: User can add their own campaigns to any phase

### Status Icons
- 📋 Proposed (AI suggested, not started)
- ⏳ Planned (approved, not yet active)
- 🔵 Active (executing — assets deployed, outreach running)
- ✅ Completed (hit KPIs or timeline elapsed)
- 🔄 Optimising (underperforming, AI generating new variants)

---

## Implementation Sequence

1. **Add DB models**: `GTMRoadmap` + extend `Campaign` with roadmap fields
2. **Create `campaign-strategist` agent** with full PDCA + knowledge integration
3. **Add roadmap API endpoints**: generate, get, approve, revise
4. **Redesign CampaignsPage** as roadmap-first view
5. **Wire generate-creative** to individual campaign cards
6. **Add performance feedback loop** — Campaign Monitor feeds back into Strategist
