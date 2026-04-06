# Campaign Roadmap — Red Team & Corrected Architecture

> **Date**: 2026-03-18
> **Issue**: Current implementation has a "Generate GTM Roadmap" button that requires manual trigger. The roadmap should be AUTOMATICALLY produced as the final step of the analysis pipeline.

---

## Red Team Findings

### Problem 1: Manual Trigger = Wrong UX

**Current**: User runs analysis → gets results → navigates to Campaigns → sees empty state → clicks "Generate GTM Roadmap" → waits again.

**Should be**: User runs analysis → 6 agents produce insights → Campaign Strategist AUTOMATICALLY converts insights + strategies into a multi-track roadmap → user arrives at Campaigns and sees the roadmap already there.

### Problem 2: Single Campaign ≠ Strategy

**Current Step 5**: Campaign Architect produces ONE campaign with email templates and LinkedIn posts.

**Should be Step 6**: Campaign Strategist reads ALL agent outputs (market intel, competitors, personas, leads, campaign brief) and produces a COMPREHENSIVE multi-track roadmap where each strategy maps to a track of activities.

### Problem 3: Flat Phase List ≠ Network Map

**Current**: Campaigns shown in 4 flat phase buckets (Immediate, Short-term, Mid-term, Long-term).

**Should be**: A NETWORK GRAPH where:
- Strategies (from insights) are top-level nodes
- Each strategy spawns a TRACK of related campaigns/activities
- Activities within a track have dependencies
- Cross-track dependencies visible (e.g., "LinkedIn page must exist before LinkedIn campaign")
- Multiple VIEW MODES: network graph, timeline/Gantt, activity list, strategy tracks

---

## Corrected Architecture

### Analysis Pipeline: Add Step 6

```
STEP 0: Company Enrichment
STEP 1-3: Market Intel + Competitor + Customer (parallel)
STEP 4: Lead Generation
STEP 5: Campaign Architect (existing — tactical content)
STEP 6: Campaign Strategist (NEW — strategic roadmap)
        ↓
        Reads ALL agent outputs from bus history:
        - Market trends, opportunities, threats
        - Competitor weaknesses, gaps
        - Persona pain points, preferred channels
        - Lead industries, company sizes
        - Campaign brief (from Step 5)
        ↓
        Produces GTMRoadmap + Campaign rows
        Organized as STRATEGY TRACKS, not flat phases
```

### Data Model: Strategy Tracks

Instead of just `phase`, campaigns should be organized by STRATEGY TRACK:

```
Strategy Track: "Digital Presence" (from insight: "No LinkedIn page detected")
├── Activity: Set up LinkedIn Company Page (Immediate, Week 1)
├── Activity: Optimise Website SEO (Immediate, Week 2)
└── Activity: Create Lead Magnet (Short-term, Day 15)

Strategy Track: "Outbound Sales" (from insight: "12 qualified fintech leads found")
├── Activity: Cold Email Sequence A/B (Short-term, Day 30)
├── Activity: LinkedIn Connection Campaign (Short-term, Day 45)
└── Activity: Follow-up Webinar Invite (Mid-term, Month 3)

Strategy Track: "Thought Leadership" (from insight: "Low brand awareness in fintech vertical")
├── Activity: Weekly LinkedIn Posts (Short-term, ongoing)
├── Activity: Industry Whitepaper (Mid-term, Month 4)
└── Activity: Speaking Engagement at SFF (Long-term, Month 8)

Strategy Track: "Customer Advocacy" (from insight: "3 existing customers in pipeline")
├── Activity: Customer Case Study (Mid-term, Month 3)
└── Activity: Referral Programme (Long-term, Month 6)
```

### Network Graph View

```
┌──────────────────────────────────────────────────────┐
│  INSIGHTS          STRATEGY TRACKS          OUTCOMES │
│                                                      │
│  📊 No LinkedIn → ─── Digital Presence Track ─── →  │
│     detected     │  └ LinkedIn Page ✅               │
│                  │  └ Website SEO ⏳                  │
│                  │  └ Lead Magnet 🔵                  │
│                                                      │
│  🎯 12 fintech → ─── Outbound Sales Track ─── →    │
│     leads found  │  └ Cold Email A/B 🔄              │
│                  │  └ LinkedIn Connect ⏳             │  → Pipeline
│                  │  └ Webinar Invite ⏳               │    $42K
│                                                      │
│  💡 Low brand  → ─── Thought Leadership Track ── →  │
│     awareness    │  └ LinkedIn Posts 🔄              │
│                  │  └ Whitepaper 📋                   │
│                  │  └ Conference 📋                   │
│                                                      │
│  👤 3 existing → ─── Customer Advocacy Track ─── →  │
│     customers    │  └ Case Study ⏳                   │
│                  │  └ Referral Prog 📋               │
└──────────────────────────────────────────────────────┘
```

### View Modes

1. **Network Graph** (default): Strategy tracks as horizontal swim lanes, activities as nodes within tracks, dependency edges between activities
2. **Timeline**: Gantt-like view — activities on timeline, grouped by track, with dependencies as arrows
3. **Activity List**: Flat list sortable by track, phase, status, priority
4. **Strategy Overview**: Cards showing each strategy track with progress %

### CampaignsPage States

| State | What Shows |
|-------|-----------|
| **No analysis run** | "Run an analysis to get your GTM roadmap" → links to teaser/analysis page |
| **Analysis running** | "Your agents are working... roadmap will appear when analysis completes" |
| **Roadmap generated** | Network graph canvas with strategy tracks, activities, insights |
| **Roadmap in progress** | Same canvas with live status updates, monitoring KPIs |

There is NO "Generate Roadmap" button. The roadmap is the natural output of the analysis.

### New DB Column on Campaign

```python
strategy_track = Column(String(200), nullable=True)  # "Digital Presence", "Outbound Sales", etc.
```

This replaces `phase` as the PRIMARY grouping (phase is secondary — a campaign has BOTH a track AND a phase).

### Campaign Strategist Output Enhancement

```python
class StrategyTrack(BaseModel):
    """A strategic track grouping related campaigns."""
    name: str                          # "Digital Presence", "Outbound Sales"
    insight_source: str                # Which insight triggered this track
    rationale: str                     # Why this track matters
    framework: str                     # RACE stage or Cialdini principle driving it
    campaigns: list[ProposedCampaign]  # Ordered activities within this track
    expected_outcome: str              # "Establish brand credibility on LinkedIn"
    success_metric: str                # "1000 LinkedIn followers in 90 days"

class GTMRoadmapOutput(BaseModel):
    # ... existing fields ...
    strategy_tracks: list[StrategyTrack]  # PRIMARY grouping
    # immediate/short/mid/long still exist as SECONDARY grouping
```

---

## Implementation Changes Needed

### Backend
1. Add `strategy_track` column to Campaign model
2. Add `StrategyTrack` to GTMRoadmapOutput
3. Add STEP 6 to analysis pipeline (after Step 5)
4. Update `_run_roadmap_generator` to persist strategy_track on campaigns
5. Update `GET /roadmap` to return campaigns grouped by strategy_track + phase

### Frontend
6. Remove "Generate GTM Roadmap" empty state — replace with "Run analysis first"
7. Add strategy track swim lanes to RoadmapCanvas
8. Add view mode switcher: Network / Timeline / List / Tracks
9. CampaignNode shows strategy track badge
10. PhaseGroupNode → StrategyTrackNode (horizontal swim lanes)
