# Enterprise GTM Roadmap Canvas — Research & Design

> **Date**: 2026-03-18
> **Vision**: An AI-orchestrated, interactive visual canvas where insights flow into strategies, strategies flow into campaigns, campaigns flow into channels, and outcomes flow back as monitoring signals. Everything is clickable, editable, and phased by time horizon.

---

## 1. Industry Landscape — How Leaders Do This

### 1.1 Salesforce Journey Builder + Agentforce (2025)

**Architecture**: Drag-and-drop visual canvas for customer journey orchestration.

**Key patterns**:
- Every touchpoint (email, SMS, social, push, web) is a visual node on a canvas
- Nodes connect via edges showing the flow of customer progression
- AI-powered decisioning nodes (Agentforce) autonomously choose next best action
- "Air Traffic Control" — prioritises across multiple journeys, daisy-chains them
- Campaign Flow listens and reacts to events across journeys

**What we should adopt**: Visual node canvas, AI decision nodes, event-driven edges, cross-campaign prioritisation.

**Source**: [Salesforce Journey Orchestration](https://www.salesforce.com/marketing/engagement/journey-orchestration/)

### 1.2 HubSpot Marketing Studio (INBOUND 2025)

**Architecture**: Miro/Figma-like collaborative visual canvas for campaign management.

**Key patterns**:
- Board-style workspace — every campaign asset displayed visually with live links
- Placeholders highlight what still needs to be created
- Click directly into any element (email, landing page, ad)
- Built-in real-time collaboration (like Miro)
- Generative AI embedded throughout — draft copy, design assets, launch faster

**What we should adopt**: Visual asset board within each campaign node, placeholder indicators, click-to-edit, AI generation integrated into the canvas.

**Source**: [HubSpot Marketing Studio](https://www.innovationvisual.com/knowledge-hub/knowledge/hubspots-marketing-studio-a-transformation-in-your-campaign-workflow)

### 1.3 GTM Studio (Emerging 2025-2026)

**Architecture**: Visual play designer for GTM orchestration.

**Key patterns**:
- Unifies 30+ disconnected tools through a single data model
- Visual architect for creative "plays" without developer dependencies
- Design segmentation and routing logic → activate in Salesforce/HubSpot

**What we should adopt**: "Play" concept — each campaign is a play with visual routing logic.

### 1.4 Capgemini GenAI Campaign Builder

- Creates full campaign concepts from prompts
- Visual canvas showing campaign structure

### 1.5 ActiveCampaign AI Campaign Builder

- Generates full campaigns from simple prompts
- Content, personalisation, emails, activation strategy with goal-focused AI

---

## 2. Visualization Technology: React Flow

### 2.1 Why React Flow

[React Flow](https://reactflow.dev) is the de facto standard for building node-based UIs in React:
- Used by Stripe, Typeform, n8n, and hundreds of enterprise apps
- 20k+ GitHub stars, actively maintained
- MIT licensed, free for commercial use
- Built-in: drag-and-drop, zoom/pan, custom nodes, custom edges, sub-flows, auto-layout
- Works with Tailwind CSS (has official Tailwind example)
- TypeScript-first

### 2.2 Key React Flow Features for GTM Roadmap

| Feature | React Flow Support | Our Use |
|---------|-------------------|---------|
| **Sub-flows / Groups** | `type: 'group'` + `parentId` on children | Phase containers (Immediate, 30-day, etc.) |
| **Custom Nodes** | Any React component as a node | Campaign cards, insight cards, monitoring KPIs |
| **Custom Edges** | Animated, labelled, coloured | Dependencies, data flows, approval gates |
| **Auto Layout** | Dagre, ELK.js, d3-hierarchy | Automatic arrangement of phased campaigns |
| **Horizontal Flow** | `sourcePosition: 'right'`, `targetPosition: 'left'` | Timeline flows left-to-right |
| **Drag and Drop** | Built-in + sidebar example | Add new campaigns from sidebar |
| **Context Menu** | Right-click on nodes | Edit, approve, generate creative, monitor |
| **Save and Restore** | JSON serialisation | Persist layout to DB |
| **Preventing Cycles** | Built-in cycle detection | Campaign dependency validation |
| **Node Toolbar** | Floating toolbar on selected node | Quick actions (approve, edit, generate) |
| **Edge Labels** | `EdgeLabelRenderer` | Show data flow type (e.g., "feeds into", "depends on") |
| **Undo/Redo** | Built-in example | Canvas editing history |

### 2.3 Sub-Flow Architecture for Phase Groups

```javascript
// Phase groups as parent nodes
const nodes = [
  // Phase container (group node)
  {
    id: 'phase-immediate',
    type: 'group',
    data: { label: 'Immediate (Week 1-2)', phase: 'immediate' },
    position: { x: 0, y: 0 },
    style: { width: 400, height: 300, background: 'rgba(59,130,246,0.05)', borderRadius: 16 },
  },
  // Campaign node inside the phase
  {
    id: 'campaign-linkedin-setup',
    type: 'campaignNode',  // Custom node component
    data: {
      name: 'Set up LinkedIn Company Page',
      status: 'completed',
      framework: 'RACE:Reach',
      channels: ['linkedin'],
      kpis: ['Page followers', 'First 10 posts'],
    },
    parentId: 'phase-immediate',
    extent: 'parent',
    position: { x: 20, y: 50 },
  },
  // ... more campaigns in this phase
];
```

---

## 3. Visual Design: The GTM Roadmap Canvas

### 3.1 Layout Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GTM ROADMAP CANVAS                                    [AI ✨] [Save]  │
│                                                                         │
│  ┌─ INSIGHTS ─┐     ┌──── IMMEDIATE (Week 1-2) ────────────────────┐  │
│  │ 📊 Market  │────→│  ┌──────────────┐  ┌──────────────┐         │  │
│  │   Trends   │     │  │ 🔵 LinkedIn  │  │ 🔵 Website   │         │  │
│  │            │     │  │    Page Setup │→ │    SEO Audit  │         │  │
│  │ 🎯 Compet- │     │  │ RACE:Reach   │  │ RACE:Reach    │         │  │
│  │   itive    │────→│  │ ✅ Complete  │  │ ⏳ Planned    │         │  │
│  │   Gaps     │     │  └──────────────┘  └──────┬───────┘         │  │
│  │            │     │  ┌──────────────┐         │                  │  │
│  │ 👤 Persona │────→│  │ 🔵 Lead      │←────────┘                  │  │
│  │   Insights │     │  │    Magnet    │                             │  │
│  │            │     │  │ Cialdini:    │                             │  │
│  └────────────┘     │  │ Reciprocity  │                             │  │
│                     │  └──────────────┘                             │  │
│                     └────────────────────────────┬──────────────────┘  │
│                                                  │ feeds into           │
│                     ┌──── SHORT TERM (30-60-90) ─┼──────────────────┐  │
│                     │  ┌──────────────┐  ┌───────┴──────┐          │  │
│                     │  │ 🟣 Cold      │  │ 🟣 LinkedIn  │          │  │
│                     │  │   Outreach   │  │   Thought    │          │  │
│                     │  │ PAS + Email  │  │   Leadership │          │  │
│                     │  │ 📧 EDM      │  │ 📝 Posts     │          │  │
│                     │  │ 🔄 Running   │  │ 📊 Graphics  │          │  │
│                     │  │ 12% reply    │  │ ⏳ Planned   │          │  │
│                     │  └──────────────┘  └──────────────┘          │  │
│                     │  ┌──────────────┐                             │  │
│                     │  │ 🟣 PSG       │      ┌── MONITORING ──┐   │  │
│                     │  │   Webinar    │      │ Opens: 24%     │   │  │
│                     │  │ Cialdini:    │      │ CTR: 3.8%      │   │  │
│                     │  │ Authority    │      │ Leads: 12      │   │  │
│                     │  └──────────────┘      │ Pipeline: $42K │   │  │
│                     └────────────────────────└────────────────┘───┘  │
│                                                  │                     │
│                     ┌──── MID TERM (3-6 months) ─┴──────────────────┐  │
│                     │  ... more campaign nodes ...                   │  │
│                     └───────────────────────────────────────────────┘  │
│                                                  │                     │
│                     ┌──── LONG TERM (6-12 months) ┴─────────────────┐  │
│                     │  ... expansion + brand nodes ...               │  │
│                     └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Node Types (Custom React Components)

#### 1. Insight Node (left column)
```
┌────────────────────┐
│ 📊 Market Trend    │  ← Icon + category
│                    │
│ "Fintech companies │  ← Key insight text
│  increasing SG&A   │
│  by 15% YoY"       │
│                    │
│ Source: EODHD      │  ← Provenance
│ Confidence: 0.92   │
│ ● feeds 3 campaigns│  ← Impact indicator
└────────────────────┘
```

#### 2. Campaign Node (main canvas)
```
┌──────────────────────────┐
│ 🟣 Cold Outreach Series  │  ← Status icon + name
│ PAS + Cialdini:Scarcity  │  ← Framework rationale
│ ─────────────────────────│
│ 📧 EDM  📱 LinkedIn      │  ← Channel badges
│ 📝 Whitepaper  🎨 Social │
│ ─────────────────────────│
│ KPIs: 12% reply, 5 SQLs │  ← Target KPIs
│ Budget: SGD 2,000        │
│ ─────────────────────────│
│ ■■■■■■■□□□ 65%          │  ← Progress bar
│ 🔄 Running  Day 23/90   │  ← Status + timeline
│ ─────────────────────────│
│ [Edit] [Assets] [Monitor]│  ← Action buttons
└──────────────────────────┘
```

When clicked, the campaign node expands or opens a side panel showing:
- Full campaign details (editable)
- Creative assets (EDM, graphics) with preview thumbnails
- Sequence status (enrollment count, reply rate)
- Monitoring dashboard (opens, clicks, conversions)
- "Generate Creative" / "Launch" / "Pause" action buttons

#### 3. Phase Group Node (container)
```
┌──── IMMEDIATE (Week 1-2) ─────── ✅ 3/3 complete ──┐
│                                                       │
│  (child campaign nodes positioned inside)             │
│                                                       │
│  Timeline: Mar 18 - Mar 31                           │
│  Total Budget: SGD 1,500                             │
└───────────────────────────────────────────────────────┘
```

#### 4. Monitoring Node (floating KPI widget)
```
┌── LIVE METRICS ──┐
│ Opens: 24.3%     │  ← Green (above benchmark)
│ CTR: 3.8%        │  ← Green
│ Leads: 12/25     │  ← Amber (below target)
│ Pipeline: $42K   │
│ Updated: 2m ago  │
└──────────────────┘
```

#### 5. Approval Gate Node (diamond shape)
```
    ◆ Human Approval
    3 items pending
    [Review →]
```

### 3.3 Edge Types

| Edge Type | Style | Meaning |
|-----------|-------|---------|
| **Insight → Campaign** | Dashed blue, animated | "Informed by" — insight drives campaign strategy |
| **Campaign → Campaign** | Solid grey, arrow | "Depends on" — sequential dependency |
| **Phase → Phase** | Thick gradient, arrow | "Feeds into" — phase progression |
| **Campaign → Approval** | Orange dotted | "Requires approval" |
| **Campaign → Monitoring** | Green pulse | "Monitored by" — live data feed |
| **Monitoring → Campaign** | Red arrow (conditional) | "Needs optimisation" — feedback loop |

### 3.4 Interaction Model

| Action | Trigger | Result |
|--------|---------|--------|
| Click campaign node | Single click | Select → show floating toolbar |
| Double-click campaign | Double click | Open detail side panel |
| Right-click campaign | Context menu | Edit / Approve / Generate Creative / Launch / Pause / Delete |
| Drag campaign | Drag within phase | Reorder priority |
| Drag campaign across phases | Drag to another phase group | Change phase assignment |
| Click "AI ✨" button | Top bar | Regenerate/revise roadmap with latest data |
| Click insight node | Single click | Show source data + which campaigns it feeds |
| Hover edge | Hover | Show relationship label |
| Click monitoring node | Click | Expand to full performance dashboard |
| Click approval gate | Click | Navigate to Approvals page filtered for this campaign |

---

## 4. Data Flow: Insights → Strategy → Campaigns → Outcomes

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  INSIGHTS   │     │  STRATEGIST  │     │  CAMPAIGNS   │     │ OUTCOMES │
│             │     │  AGENT       │     │              │     │          │
│ Market Intel│────→│              │────→│ Phase:       │────→│ Opens    │
│ Competitors │     │ Diagnose     │     │ Immediate    │     │ Clicks   │
│ Personas    │     │ Select Motion│     │ Short-term   │     │ Leads    │
│ Signals     │     │ Map RACE     │     │ Mid-term     │     │ Pipeline │
│ Leads       │     │ Apply Ciald. │     │ Long-term    │     │ Revenue  │
│             │     │ Cite Books   │     │              │     │          │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────┘
       ↑                                                            │
       └────────────── FEEDBACK LOOP (re-optimise) ─────────────────┘
```

Each node on the canvas represents a real DB entity:
- Insight nodes → `SignalEvent` + `MarketArticle` + bus history
- Campaign nodes → `Campaign` (with roadmap_id, phase, framework_rationale)
- Asset nodes (within campaign) → `CreativeAsset`
- Monitoring nodes → `EngagementEvent` aggregates + `Campaign.metrics`
- Approval gates → `ApprovalQueueItem` count

---

## 5. Implementation Architecture

### 5.1 React Flow Component Hierarchy

```
CampaignsPage.tsx (refactored)
├── RoadmapCanvas.tsx                    ← Main React Flow canvas
│   ├── InsightNode.tsx                  ← Custom node: market insight
│   ├── PhaseGroupNode.tsx               ← Custom node: phase container
│   ├── CampaignNode.tsx                 ← Custom node: campaign card
│   ├── MonitoringNode.tsx               ← Custom node: live KPIs
│   ├── ApprovalGateNode.tsx             ← Custom node: approval diamond
│   ├── InsightEdge.tsx                  ← Custom edge: dashed animated
│   ├── DependencyEdge.tsx               ← Custom edge: solid arrow
│   └── FeedbackEdge.tsx                 ← Custom edge: red conditional
├── CampaignDetailPanel.tsx              ← Side panel when campaign clicked
│   ├── CampaignBriefTab.tsx             ← Editable brief
│   ├── CampaignAssetsTab.tsx            ← Creative assets grid
│   ├── CampaignSequenceTab.tsx          ← Outreach sequence status
│   └── CampaignMonitorTab.tsx           ← Performance charts
├── RoadmapToolbar.tsx                   ← Top bar: AI regenerate, save, zoom
└── AddCampaignSidebar.tsx               ← Drag-and-drop sidebar for manual adds
```

### 5.2 Layout Algorithm

Use **ELK.js** (Eclipse Layout Kernel) for automatic layout:
- Horizontal flow (left → right for timeline progression)
- Phase groups as hierarchical containers
- Campaign nodes auto-arranged within phase groups
- Edges routed to avoid crossings
- Supports incremental layout (add/remove nodes without full re-layout)

### 5.3 Data Loading

```typescript
// On CampaignsPage mount:
1. GET /api/v1/companies/{id}/roadmap
   → Returns roadmap + campaigns grouped by phase

2. GET /api/v1/companies/{id}/signals?limit=10
   → Returns recent insights for the insight column

3. GET /api/v1/companies/{id}/campaigns/{id}/assets
   → Lazy-loaded when campaign node is clicked

4. GET /api/v1/companies/{id}/attribution/campaign/{id}
   → Lazy-loaded for monitoring node

// Transform to React Flow format:
const { nodes, edges } = transformRoadmapToFlow(roadmap, insights, campaigns)
```

### 5.4 State Management

```typescript
interface RoadmapCanvasState {
  // React Flow state
  nodes: Node[]
  edges: Edge[]

  // Business state
  roadmap: RoadmapResponse | null
  selectedCampaign: Campaign | null
  detailPanelOpen: boolean

  // Actions
  onNodeClick: (node: Node) => void
  onNodeDrag: (node: Node, position: XYPosition) => void
  onRegenerate: () => void
  onApproveCampaign: (campaignId: string) => void
  onGenerateCreative: (campaignId: string) => void
}
```

---

## 6. Phased Implementation

### Phase A: Canvas Foundation (React Flow integration)
1. Install `@xyflow/react` (React Flow v12) in dashboard
2. Create `RoadmapCanvas.tsx` with basic horizontal flow
3. Create `PhaseGroupNode.tsx` — phase containers
4. Create `CampaignNode.tsx` — campaign cards with status/framework
5. Transform roadmap API response to React Flow nodes/edges
6. Basic click → side panel interaction

### Phase B: Insight Integration
7. Create `InsightNode.tsx` — insight cards from signals/market data
8. Create insight → campaign edges (dashed animated)
9. Load insights from signals API + bus history
10. Show which insights informed which campaigns

### Phase C: Interactive Editing
11. Campaign detail side panel (brief, assets, sequences, monitoring)
12. Right-click context menu (edit, approve, generate creative, launch)
13. Drag-and-drop campaign reorder within phase
14. Add campaign from sidebar drag

### Phase D: Live Monitoring Integration
15. Create `MonitoringNode.tsx` — live KPI widgets
16. Create `ApprovalGateNode.tsx` — approval diamonds
17. WebSocket/polling for real-time metric updates
18. Feedback loop edges (underperforming → optimise)

### Phase E: AI Regeneration
19. "AI ✨" button triggers Campaign Strategist re-run
20. Animate new/changed nodes into canvas
21. Diff view: "AI suggests adding 2 campaigns to short-term phase"
22. User approves/rejects changes on canvas

---

## 7. NPM Dependencies

```json
{
  "@xyflow/react": "^12.0.0",
  "elkjs": "^0.9.0",
  "web-worker": "^1.3.0"
}
```

Total bundle impact: ~180KB (React Flow) + ~50KB (ELK.js) = ~230KB gzipped ~65KB.

---

## Sources

- [React Flow — Node-Based UIs in React](https://reactflow.dev)
- [React Flow Sub-Flows Guide](https://reactflow.dev/learn/layouting/sub-flows)
- [React Flow Examples](https://reactflow.dev/examples)
- [Salesforce Journey Orchestration](https://www.salesforce.com/marketing/engagement/journey-orchestration/)
- [HubSpot Marketing Studio](https://www.innovationvisual.com/knowledge-hub/knowledge/hubspots-marketing-studio-a-transformation-in-your-campaign-workflow)
- [GTM Studio](https://pipeline.zoominfo.com/sales/best-gtm-tools)
- [Capgemini GenAI Campaign Builder](https://www.capgemini.com/solutions/genai-campaign-builder/)
- [ActiveCampaign AI Campaign Builder](https://www.activecampaign.com/platform/ai-campaign-builder)
- [Gartner AI GTM Platforms](https://www.gartner.com/reviews/market/ai-gtm-platforms)
- [30-60-90 Day Marketing Plan Guide](https://growthmethod.com/30-60-90/)
- [SVAR React Gantt Chart](https://svar.dev/react/gantt/)
- [Marketing Dashboard Best Practices 2025](https://www.dataslayer.ai/blog/marketing-dashboard-best-practices-2025)
