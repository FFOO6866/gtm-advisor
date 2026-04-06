# Platform Flow Architecture — Insights → Strategy → Campaigns → Execute → Monitor

> **Date**: 2026-03-18
> **Status**: Design proposal

---

## The Problem

Current flow skips the strategy layer:
```
Analysis agents run → Insights generated → Campaign Strategist auto-generates Gantt chart → User sees tasks
```

The user has no control over WHAT strategies to pursue before the system decides HOW to execute them. The Gantt chart appears with tasks the user never agreed to.

## The Correct Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ INSIGHTS │ ──→ │ STRATEGY │ ──→ │CAMPAIGNS │ ──→ │ EXECUTE  │ ──→ │ RESULTS  │
│          │     │          │     │          │     │          │     │          │
│ What's   │     │ What     │     │ Concrete │     │ Agents   │     │ What     │
│ happening│     │ should   │     │ tasks +  │     │ create + │     │ worked?  │
│ in our   │     │ we do?   │     │ timeline │     │ publish  │     │ Feed     │
│ market?  │     │          │     │          │     │ + send   │     │ back     │
│          │     │ USER     │     │ AUTO-    │     │          │     │          │
│ AUTO     │     │ APPROVES │     │ GENERATED│     │ AUTO     │     │ AUTO     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                ↑                                                   │
     └────────────────┴───────────── FEEDBACK LOOP ───────────────────────┘
```

### Gate: Strategy Approval

The ONLY human gate is at Strategy. Everything else is autonomous:
- Insights: agents gather automatically
- Strategy: **AI proposes, human approves/edits**
- Campaigns: auto-generated from approved strategies
- Execution: agents create assets, publish, send
- Results: monitored automatically, fed back

---

## Navigation Update

```
Today → Insights → Strategy → Campaigns → Approvals → Prospects → Results
                   ^^^^^^^^
                   NEW PAGE
```

| Page | Purpose | Human Action |
|------|---------|-------------|
| **Today** | Daily briefing, attention items | Read |
| **Insights** | What's happening — market, competitors, opportunities | Read + "What does this mean for us?" |
| **Strategy** | AI-proposed strategies from insights | **Review, edit, approve** ← THE GATE |
| **Campaigns** | Gantt chart of tasks (from approved strategies) | View, drag, edit details |
| **Approvals** | Review creative assets + outreach before publish | Approve/reject |
| **Prospects** | Pipeline: customers + partners + channels | Manage |
| **Results** | Performance → feeds back to strategy | Review, trigger re-optimization |

---

## Data Model: Strategy Layer

### New DB Model: `Strategy`

```python
class StrategyStatus(str, PyEnum):
    PROPOSED = "proposed"      # AI proposed, awaiting user review
    APPROVED = "approved"      # User accepted
    REJECTED = "rejected"      # User rejected (with reason)
    IN_PROGRESS = "in_progress"  # Campaigns being generated/executed
    COMPLETED = "completed"    # Strategy goals achieved
    REVISED = "revised"        # Revised based on results

class Strategy(Base):
    """A high-level strategic initiative proposed by AI, approved by user."""
    __tablename__ = "strategies"

    id: UUID PK
    company_id: FK companies
    roadmap_id: FK gtm_roadmaps (nullable)

    # Strategy content (AI-generated)
    name: str                    # "Target Independent Agency Founders"
    description: str             # What this strategy entails
    insight_sources: JSON        # Which insights triggered this strategy
    rationale: str               # Why this strategy matters (advisory language)
    expected_outcome: str        # "15 demos booked in 90 days"
    success_metrics: JSON        # [{metric, target, current}]
    priority: str                # high, medium, low
    estimated_timeline: str      # "30-90 days"

    # User interaction
    status: StrategyStatus
    user_notes: str              # User's edits/comments
    approved_at: datetime
    approved_by: str

    # Downstream link
    # Campaigns FK back to this strategy via Campaign.strategy_id

    created_at, updated_at
```

### Extend Campaign Model

```python
    strategy_id = Column(FK strategies, nullable=True)  # Links campaign to approved strategy
```

### Flow

```
1. Analysis runs → 6 agents produce insights
2. Insights page shows: market trends, competitor gaps, opportunities
   Each insight has: "What this means" + "Recommended action"

3. Strategy page:
   a. AI reads insights → proposes 4-7 strategies
   b. Each strategy card shows: name, rationale, expected outcome, priority
   c. User can: ✅ Approve | ✏️ Edit | ❌ Reject | 🔄 Ask AI to revise
   d. User can add their own strategies manually

4. Once strategies are approved:
   a. Campaign Strategist takes ONLY approved strategies
   b. Expands each strategy into granular tasks (the two-pass approach)
   c. Populates the Gantt chart

5. Campaigns page shows Gantt chart — all tasks linked to their parent strategy
   User can see which strategy drives which tasks

6. Execution:
   - Creative agents generate assets per task
   - Social Publisher distributes
   - Outreach Executor sends emails
   - CRM Sync updates HubSpot

7. Results feed back:
   - "Strategy X is performing well" → suggest scaling
   - "Strategy Y underperforming" → suggest pivot or pause
```

---

## Strategy Page UI Design

```
┌─────────────────────────────────────────────────────────────────────┐
│  Strategy                                        [Regenerate AI]   │
│                                                                     │
│  Based on your market analysis, we recommend these strategic        │
│  initiatives. Review and approve to generate your campaign plan.    │
│                                                                     │
│  ┌── HIGH PRIORITY ─────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │ 🎯 Target Independent Agency Founders                   │ │  │
│  │  │                                                         │ │  │
│  │  │ 36 independent agencies make decisions faster than the  │ │  │
│  │  │ 49 network agencies. Go direct to founders — skip       │ │  │
│  │  │ procurement. Your AI-driven GTM tool solves their       │ │  │
│  │  │ exact pain point: scaling without hiring.               │ │  │
│  │  │                                                         │ │  │
│  │  │ From: Ownership mapping (23 groups), Lead Hunter        │ │  │
│  │  │ Outcome: 15 demos booked in 90 days                     │ │  │
│  │  │ Timeline: 30-90 days                                    │ │  │
│  │  │                                                         │ │  │
│  │  │ [✅ Approve]  [✏️ Edit]  [❌ Skip]                      │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │ 🏛️ PSG Pre-Approved Vendor Positioning                 │ │  │
│  │  │                                                         │ │  │
│  │  │ SGD-for-SGD matching via PSG makes your SGD 2,000/mo    │ │  │
│  │  │ product effectively SGD 1,000 for buyers. This is the   │ │  │
│  │  │ single biggest conversion lever for SG SME sales.       │ │  │
│  │  │                                                         │ │  │
│  │  │ From: SG market context, PSG eligibility analysis       │ │  │
│  │  │ Outcome: 3 PSG-funded deals in 6 months                 │ │  │
│  │  │ Timeline: 4-8 weeks (application) + ongoing             │ │  │
│  │  │                                                         │ │  │
│  │  │ [✅ Approve]  [✏️ Edit]  [❌ Skip]                      │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌── MEDIUM PRIORITY ───────────────────────────────────────────┐  │
│  │  🔬 LinkedIn Authority in MarTech Space                      │  │
│  │  📊 Industry Benchmark Content Series                        │  │
│  │  🤝 ASME Technology Partner Program                          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌── USER-ADDED ────────────────────────────────────────────────┐  │
│  │  [+ Add Your Own Strategy]                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  3 of 5 strategies approved                                  │   │
│  │  [Generate Campaign Plan from Approved Strategies →]         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prospects: Broader Than Customers

Current Prospects page only shows customer leads. It should have three tabs:

```
┌─────────────────────────────────────────────────┐
│  Prospects                                       │
│                                                   │
│  [Customers]  [Partners]  [Channels]              │
│  ──────────   ────────    ────────                │
│                                                   │
│  Customers: leads from Lead Hunter               │
│  Partners: ASME, SBF, SGTech, co-marketing       │
│  Channels: resellers, referral partners, APAC     │
└─────────────────────────────────────────────────┘
```

Each tab has its own pipeline stages:
- **Customers**: New → Qualified → Contacted → Converted → Lost
- **Partners**: Identified → Approached → Negotiating → Active → Inactive
- **Channels**: Research → Outreach → Agreement → Onboarded → Producing

---

## Implementation Sequence

### Phase 1: Strategy Layer (Backend)
1. Add `Strategy` + `StrategyStatus` to models.py
2. Add `strategy_id` FK to Campaign model
3. Create Strategy Proposer agent (or enhance Campaign Strategist with two modes)
4. Create `/api/v1/companies/{id}/strategies` router (CRUD + approve/reject)
5. Wire: analysis completion → auto-propose strategies

### Phase 2: Strategy Page (Frontend)
6. Create StrategyPage.tsx with strategy cards
7. Approve/Edit/Reject interactions
8. "Generate Campaign Plan" button → triggers Campaign Strategist with ONLY approved strategies
9. Update nav: Today → Insights → **Strategy** → Campaigns → Approvals → Prospects → Results

### Phase 3: Campaign Generation from Strategies
10. Campaign Strategist reads approved strategies (not raw insights)
11. Each strategy.id linked to its downstream campaigns
12. Gantt chart groups by strategy (which maps to tracks)

### Phase 4: Prospects Expansion
13. Add partner/channel models to DB
14. Prospects page with 3 tabs
15. Partner pipeline stages

### Phase 5: Results Feedback Loop
16. Strategy-level metrics aggregation
17. "This strategy is working/not working" AI analysis
18. Suggest strategy revisions based on performance
