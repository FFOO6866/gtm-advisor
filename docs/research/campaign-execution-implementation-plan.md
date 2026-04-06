# Campaign Execution Pipeline — Implementation Plan

> **Date**: 2026-03-18
> **Track**: Campaigns / Prospects / Approvals / Results (concurrent with Today/Insights track)
> **Prerequisite**: [Research Document](campaign-execution-pipeline-research.md)

---

## Executive Summary

Extend GTM Advisor from "campaign planning" to "campaign execution" — closing the gap between strategy output and real-world results. The existing Campaign Architect → Sequence Engine → Approval → SendGrid pipeline handles ~60% of the workflow. This plan adds **creative production** (EDM design, social graphics), **multi-channel publishing** (LinkedIn, Meta, X via Post Bridge), **webhook-driven engagement monitoring**, and a **closed-loop optimisation agent** that feeds performance data back into the system.

**Phased delivery**: 4 phases, each independently valuable, building on the last.

---

## Scope Boundaries

### This Track Owns
- Campaigns: strategy → creative → approve → publish → monitor → optimise
- Prospects: lead pipeline enriched with campaign engagement data
- Approvals: extended to cover social posts and creative assets (not just emails)
- Results: attribution dashboard with email + social engagement metrics

### Other Track Owns (Today/Insights)
- TodayPage strategic briefing
- Signal Feed / market intelligence display
- Vertical intelligence dashboard

### Shared Touchpoints
- `SignalEvent` table (Insights writes, Campaigns reads for signal-triggered campaigns)
- `AttributionEvent` table (Campaigns writes, Results/Today reads for KPIs)
- `AgentBus` events (`SIGNAL_DETECTED` → campaign trigger; `CAMPAIGN_READY` → execution)

---

## Phase 1: Creative Production Agents

**Goal**: Campaign Architect outputs a brief → new agents produce ready-to-send EDM HTML and social media graphics.

### 1.1 New DB Models

Add to `packages/database/src/models.py`:

```python
class CreativeAssetType(str, PyEnum):
    """Type of creative asset."""
    EDM_HTML = "edm_html"           # Full responsive email HTML
    SOCIAL_IMAGE = "social_image"   # Social media graphic (PNG/JPG)
    AD_BANNER = "ad_banner"         # Display ad banner
    LANDING_PAGE = "landing_page"   # Landing page HTML snippet

class CreativeAssetStatus(str, PyEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"

class CreativeAsset(Base):
    """A produced creative asset linked to a campaign."""
    __tablename__ = "creative_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[CreativeAssetType] = mapped_column(Enum(CreativeAssetType), nullable=False)
    status: Mapped[CreativeAssetStatus] = mapped_column(Enum(CreativeAssetStatus), default=CreativeAssetStatus.DRAFT)

    # Content
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)          # For EDM / landing page
    image_url: Mapped[str | None] = mapped_column(String(1000))     # For social images / banners (S3/local path)
    image_prompt: Mapped[str | None] = mapped_column(Text)          # DALL-E prompt used
    copy_text: Mapped[str | None] = mapped_column(Text)             # Social post copy / ad copy
    call_to_action: Mapped[str | None] = mapped_column(String(200))
    target_platform: Mapped[str | None] = mapped_column(String(50)) # linkedin, instagram, facebook, x, email
    target_persona: Mapped[str | None] = mapped_column(String(200))

    # Variant tracking
    variant_label: Mapped[str | None] = mapped_column(String(10))   # "A", "B", "C"
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("creative_assets.id"))

    # Approval
    approved_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Publishing
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_post_id: Mapped[str | None] = mapped_column(String(500))  # Platform post ID after publishing
    publish_error: Mapped[str | None] = mapped_column(Text)

    # Performance (populated by monitor agent)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    engagements: Mapped[int] = mapped_column(Integer, default=0)    # likes + shares + comments
    conversions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class EngagementEvent(Base):
    """Granular engagement event from email webhooks or social API polling."""
    __tablename__ = "engagement_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id"), index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("creative_assets.id"), index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), index=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # event_type: email_open, email_click, email_bounce, email_unsubscribe,
    #             social_impression, social_like, social_share, social_comment,
    #             social_click, page_visit, form_fill

    channel: Mapped[str] = mapped_column(String(30), nullable=False)  # email, linkedin, facebook, x, instagram
    source_message_id: Mapped[str | None] = mapped_column(String(500))  # SendGrid msg ID or social post ID
    url_clicked: Mapped[str | None] = mapped_column(String(1000))       # For click events
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
```

**Migration**: `alembic revision --autogenerate -m "add_creative_assets_and_engagement_events"`

### 1.2 EDM Designer Agent

**File**: `agents/edm_designer/src/agent.py`

```
agents/edm_designer/
├── pyproject.toml
└── src/
    ├── __init__.py
    ├── agent.py
    └── templates/          # Base MJML templates (header, footer, layouts)
        ├── single_column.mjml
        ├── two_column.mjml
        └── newsletter.mjml
```

**Responsibilities**:
- Receives campaign brief (from Campaign Architect `ContentPiece` with type=email)
- Generates MJML markup using Claude structured output
- Compiles MJML → responsive HTML via `mjml` CLI or Python wrapper
- Optionally generates header image via DALL-E 3 API
- Outputs `CreativeAsset` with type=EDM_HTML, variant A/B

**PDCA cycle**:
- `_plan()`: Load campaign brief, company brand info (logo URL, colours, UEN), knowledge pack
- `_do()`: Claude generates MJML with personalised sections → compile to HTML → optionally generate hero image via DALL-E
- `_check()`: Validate HTML renders (no broken tags), check PDPA compliance (unsubscribe link, UEN in footer), check no placeholders, score responsive rendering
- `_act()`: Publish `CREATIVE_READY` event, persist CreativeAsset

**Key dependency**: `mjml` npm package (CLI: `npx mjml input.mjml -o output.html`)

**Bus subscriptions**:
- Subscribes to `CAMPAIGN_READY` → auto-trigger EDM creation for email campaigns

### 1.3 Graphic Designer Agent

**File**: `agents/graphic_designer/src/agent.py`

```
agents/graphic_designer/
├── pyproject.toml
└── src/
    ├── __init__.py
    └── agent.py
```

**Responsibilities**:
- Receives campaign brief (ContentPiece with type=linkedin, ad, or social)
- Generates image via DALL-E 3 API (or Canva Autofill for template-based)
- Produces platform-specific dimensions:
  - LinkedIn: 1200x627 (link share), 1080x1080 (carousel)
  - Instagram: 1080x1080 (feed), 1080x1920 (story)
  - Facebook: 1200x630 (link share)
  - X: 1600x900
- Generates copy + CTA overlay prompt (Ideogram for text-in-image)
- Outputs `CreativeAsset` with type=SOCIAL_IMAGE

**PDCA cycle**:
- `_plan()`: Parse brief, determine platforms needed, load brand voice/colours
- `_do()`: Build DALL-E prompt from campaign messaging + brand guidelines → generate image → store locally or S3 → generate platform-specific copy
- `_check()`: Image generated successfully, resolution correct, copy matches tone, no placeholder text
- `_act()`: Publish `CREATIVE_READY` event, persist CreativeAsset per platform

**Key dependency**: OpenAI Images API (already have `OPENAI_API_KEY`)

### 1.4 New MCP Server: DALL-E Image Generation

**File**: `packages/mcp/src/servers/dalle.py`

Tools:
- `generate_image(prompt, size, quality, style)` → returns image URL + local path
- `generate_image_edit(image_path, prompt, mask_path)` → image edit/inpainting
- `get_image_variations(image_path, n)` → N variations of existing image

### 1.5 MJML Compilation Utility

**File**: `packages/tools/src/mjml.py`

```python
async def compile_mjml(mjml_source: str) -> str:
    """Compile MJML markup to responsive HTML email.

    Uses mjml CLI via subprocess. Falls back to mjml-python if CLI unavailable.
    """
```

**Install**: `npm install -g mjml` (or include in services/dashboard/package.json dev deps)

### 1.6 Campaign Router Extension

Add to `services/gateway/src/routers/campaigns.py`:

```
POST /{company_id}/campaigns/{campaign_id}/generate-creative
    → Triggers EDM Designer + Graphic Designer agents in background
    → Returns: {job_id, status: "generating"}

GET  /{company_id}/campaigns/{campaign_id}/assets
    → List all CreativeAssets for campaign

PATCH /{company_id}/campaigns/{campaign_id}/assets/{asset_id}
    → Update asset (edit copy, swap image, change CTA)

POST /{company_id}/campaigns/{campaign_id}/assets/{asset_id}/approve
    → Set status=APPROVED, record reviewer

POST /{company_id}/campaigns/{campaign_id}/assets/{asset_id}/reject
    → Set status=REJECTED with reason

GET  /{company_id}/campaigns/{campaign_id}/assets/{asset_id}/preview
    → Return rendered HTML (for EDM) or image URL (for social)
```

### 1.7 Extend ApprovalQueueItem

Add optional fields to support creative asset approval (not just email outreach):

```python
# Add to ApprovalQueueItem
asset_id: Mapped[uuid.UUID | None]        # FK to creative_assets.id
asset_type: Mapped[str | None]            # "edm_html", "social_image", etc.
proposed_image_url: Mapped[str | None]    # Preview image for social assets
channel: Mapped[str | None]              # "email", "linkedin", "facebook", etc.
```

This allows the existing ApprovalsInbox UI to show both email outreach items AND creative assets for review.

### 1.8 AgentBus Events

Add to `DiscoveryType` enum:
- `CREATIVE_BRIEF` — Campaign Architect → Creative agents (campaign brief + brand context)
- `CREATIVE_READY` — EDM Designer / Graphic Designer → Review Agent (assets produced)
- `CONTENT_APPROVED` — Review flow → Distribution agents (asset approved for publish)
- `ENGAGEMENT_RECEIVED` — Monitor Agent → Optimisation loop (performance signal)

---

## Phase 2: Multi-Channel Distribution

**Goal**: Approved assets get published to social media platforms and email via a unified interface.

### 2.1 New MCP Server: Post Bridge (Social Publishing)

**File**: `packages/mcp/src/servers/post_bridge.py`

Wraps [Post Bridge API](https://www.post-bridge.com/agents) ($14/mo) for 9-platform publishing.

Tools:
- `create_post(platforms, caption, media_urls, schedule_time)` → returns per-platform post IDs
- `get_post_analytics(post_id)` → returns impressions, likes, comments, shares
- `list_connected_accounts()` → returns connected social accounts
- `schedule_post(platforms, caption, media_urls, schedule_time)` → deferred publish

**Auth**: API key from `POST_BRIDGE_API_KEY` env var.

**Alternative**: Build individual platform MCPs (Meta Marketing API, LinkedIn Marketing API, X API v2) for enterprises that need more control. Post Bridge is the MVP path.

### 2.2 Social Publisher Agent

**File**: `agents/social_publisher/src/agent.py`

```
agents/social_publisher/
├── pyproject.toml
└── src/
    ├── __init__.py
    └── agent.py
```

**Responsibilities**:
- Receives approved `CreativeAsset` with type=SOCIAL_IMAGE
- Publishes to target platforms via Post Bridge MCP
- Records `external_post_id` on the asset for later analytics polling
- Handles platform-specific caption formatting (hashtags for LinkedIn, thread for X, etc.)
- Respects scheduling (not all posts go out at once)

**PDCA cycle**:
- `_plan()`: Load approved assets, determine publish schedule (stagger posts), load platform accounts
- `_do()`: Call Post Bridge API per platform → get post IDs → update CreativeAsset
- `_check()`: Verify post IDs returned, no platform errors, confirm publish times
- `_act()`: Publish `CONTENT_PUBLISHED` event, update asset status to PUBLISHED, log AttributionEvent

**Bus subscriptions**:
- Subscribes to `CONTENT_APPROVED` → auto-publish social assets

### 2.3 Extend Email Sending (Already Exists)

The existing `_send_approved_email()` in approvals router already handles email via SendGrid. Extend it to:

1. Use `CreativeAsset` HTML content (if asset_id present) instead of plain text body
2. Include UTM parameters in all links for attribution tracking
3. Pass `campaign_id` in SendGrid custom_args for webhook attribution

### 2.4 Campaign Activation Flow

New endpoint: `POST /{company_id}/campaigns/{campaign_id}/launch`

This is the "big button" that:
1. Validates all assets are approved (status=APPROVED)
2. Creates SequenceEnrollments for email sequences (existing flow)
3. Schedules social posts via Social Publisher agent (staggered)
4. Sets campaign status to ACTIVE
5. Starts the monitoring loop

### 2.5 Scheduler Jobs

Add to `services/gateway/src/scheduler.py`:

```python
# Job 19: Social Post Scheduler (every 4 hours)
# Checks for CreativeAssets with status=APPROVED, scheduled_publish_at <= now
# Triggers Social Publisher agent

# Job 20: Social Engagement Poller (every 2 hours)
# For all PUBLISHED social assets, poll Post Bridge analytics
# Update impressions/clicks/engagements on CreativeAsset
# Create EngagementEvent rows
```

---

## Phase 3: Engagement Monitoring & Attribution

**Goal**: Closed-loop — every email open, click, social like, and conversion flows back into the system for attribution and optimisation.

### 3.1 SendGrid Webhook Handler

**File**: `services/gateway/src/routers/webhooks.py`

```
POST /api/v1/webhooks/sendgrid
    → Receives batch of SendGrid Event Webhook events
    → Extracts: event_type, email, timestamp, url (clicks), sg_message_id, custom_args
    → Creates EngagementEvent rows
    → For "reply" events: triggers sequence_engine.pause_on_reply()
    → For "bounce/spam_report": marks lead email as invalid
```

**SendGrid Webhook Events** consumed:
| Event | Action |
|-------|--------|
| `open` | Create EngagementEvent(email_open), increment asset.impressions |
| `click` | Create EngagementEvent(email_click, url_clicked), increment asset.clicks |
| `bounce` | Create EngagementEvent(email_bounce), flag lead email |
| `unsubscribe` | Create EngagementEvent(email_unsubscribe), flag lead DNC |
| `spam_report` | Create EngagementEvent(email_spam), flag lead DNC, alert |

**Security**: Verify SendGrid webhook signature via `X-Twilio-Email-Event-Webhook-Signature` header.

### 3.2 Social Engagement Poller

Extend the scheduled job from Phase 2 to:
1. For each PUBLISHED CreativeAsset with `external_post_id`:
2. Call Post Bridge `get_post_analytics(post_id)`
3. Calculate deltas (new impressions/clicks since last poll)
4. Create `EngagementEvent` rows for significant changes
5. Update `CreativeAsset.impressions/clicks/engagements`

### 3.3 Enhanced Attribution Router

Extend `services/gateway/src/routers/attribution.py`:

```
GET /{company_id}/attribution/summary?days=30
    → Enhanced with:
      - email_opens, email_clicks, email_bounces (from EngagementEvent)
      - social_impressions, social_clicks, social_engagements (from EngagementEvent)
      - open_rate_pct, click_through_rate_pct (computed)
      - top_performing_assets (by CTR)
      - channel_breakdown (email vs linkedin vs facebook vs x)
      - funnel: impressions → clicks → leads → meetings → pipeline

GET /{company_id}/attribution/campaign/{campaign_id}
    → Per-campaign performance breakdown
    → A/B variant comparison (variant A vs B performance)

GET /{company_id}/attribution/assets/top?limit=10&metric=ctr
    → Top performing creative assets
```

### 3.4 Campaign Monitor Agent

**File**: `agents/campaign_monitor/src/agent.py`

```
agents/campaign_monitor/
├── pyproject.toml
└── src/
    ├── __init__.py
    └── agent.py
```

**Responsibilities**:
- Runs daily for each active campaign
- Aggregates EngagementEvents into campaign-level metrics
- Compares performance against benchmarks (industry CTR, open rates)
- Identifies underperforming assets and recommends actions:
  - "Email variant B has 3x higher open rate — pause variant A"
  - "LinkedIn post CTR is below industry median — suggest new creative"
  - "No clicks in 48 hours — recommend subject line change"
- Updates `Campaign.metrics` JSON with latest performance data

**PDCA cycle**:
- `_plan()`: Load campaign, all assets, all EngagementEvents since last check
- `_do()`: Compute metrics (open rate, CTR, engagement rate per asset), compare to benchmarks, identify top/bottom performers, generate recommendations
- `_check()`: Confidence based on data volume (more events = higher confidence)
- `_act()`: Update Campaign.metrics, publish `CAMPAIGN_PERFORMANCE` event, flag underperformers

**Bus subscriptions**:
- Subscribes to `ENGAGEMENT_RECEIVED` → aggregate into campaign metrics

### 3.5 Lead Pipeline Enrichment

Extend the existing Lead model / LeadsPipeline to show engagement data:
- Add `last_email_opened_at`, `last_link_clicked_at`, `email_engagement_score` to Lead
- Score = weighted sum of opens (1pt), clicks (3pt), replies (10pt)
- Leads Pipeline Kanban shows engagement heat (cold/warm/hot icon)
- Sort leads by engagement score for prioritisation

---

## Phase 4: Campaign Optimisation Loop

**Goal**: AI-driven continuous optimisation — underperforming content gets automatically refreshed with human approval gate.

### 4.1 Content Refresh Agent

**File**: `agents/content_refresh/src/agent.py`

**Triggered when** Campaign Monitor identifies underperforming assets:
1. Receives the underperforming asset + campaign context + performance data
2. Generates a new variant (copy, subject line, or image)
3. Creates new `CreativeAsset` as variant with `parent_asset_id` pointing to original
4. Routes through approval flow (no auto-publish)
5. If approved → replaces/supplements the underperformer

**This closes the loop**: Campaign → Create → Publish → Monitor → Refresh → Approve → Publish

### 4.2 A/B Test Automation

For campaigns with A/B variants:
1. Campaign Monitor tracks per-variant metrics
2. After sufficient data (e.g. 100+ opens per variant):
   - Compute statistical significance
   - Recommend winner
3. Auto-pause losing variant (with approval gate)
4. Scale up winning variant

### 4.3 Campaign Performance Dashboard (Frontend)

Enhance `ResultsPage.tsx` with:
- **Campaign Funnel**: Impressions → Clicks → Leads → Meetings → Pipeline (per campaign)
- **Channel Breakdown**: Email vs LinkedIn vs other (bar chart)
- **A/B Results**: Side-by-side variant comparison with winner badge
- **Top Assets**: Leaderboard of best-performing creative (by CTR, engagement)
- **Trend Lines**: Daily/weekly performance over campaign lifetime
- **ROI Summary**: Cost per lead, cost per meeting, pipeline ROI

---

## File Inventory (New Files)

### Agents (4 new)
| Path | Agent | Phase |
|------|-------|-------|
| `agents/edm_designer/src/agent.py` | EDM Designer | 1 |
| `agents/graphic_designer/src/agent.py` | Graphic Designer | 1 |
| `agents/social_publisher/src/agent.py` | Social Publisher | 2 |
| `agents/campaign_monitor/src/agent.py` | Campaign Monitor | 3 |

### MCP Servers (2 new)
| Path | Server | Phase |
|------|--------|-------|
| `packages/mcp/src/servers/dalle.py` | DALL-E Image Generation | 1 |
| `packages/mcp/src/servers/post_bridge.py` | Post Bridge Social Publishing | 2 |

### Backend (3 new files, 5 modified)
| Path | Purpose | Phase |
|------|---------|-------|
| `services/gateway/src/routers/webhooks.py` | SendGrid webhook handler | 3 |
| `packages/tools/src/mjml.py` | MJML→HTML compilation | 1 |
| `packages/database/migrations/versions/xxx_creative_assets.py` | Migration | 1 |
| `packages/database/src/models.py` (modify) | CreativeAsset, EngagementEvent | 1 |
| `services/gateway/src/routers/campaigns.py` (modify) | Asset CRUD + generate-creative | 1 |
| `services/gateway/src/routers/approvals.py` (modify) | Support asset approval | 1 |
| `services/gateway/src/routers/attribution.py` (modify) | Enhanced metrics | 3 |
| `services/gateway/src/scheduler.py` (modify) | 2 new jobs | 2 |

### Frontend (2 new, 3 modified)
| Path | Purpose | Phase |
|------|---------|-------|
| `services/dashboard/src/pages/CampaignWorkspace.tsx` | Unified campaign view | 1 |
| `services/dashboard/src/components/AssetPreview.tsx` | EDM/image preview component | 1 |
| `services/dashboard/src/pages/CampaignsPage.tsx` (modify) | Link to workspace | 1 |
| `services/dashboard/src/pages/ApprovalsInbox.tsx` (modify) | Show creative assets | 1 |
| `services/dashboard/src/pages/ResultsPage.tsx` (modify) | Campaign performance dashboard | 3 |

---

## Environment Variables (New)

```bash
# Phase 1
# (OPENAI_API_KEY already exists — used for DALL-E 3)

# Phase 2
POST_BRIDGE_API_KEY=pb_...        # Post Bridge social publishing
POST_BRIDGE_WORKSPACE_ID=ws_...   # Optional workspace ID

# Phase 3
SENDGRID_WEBHOOK_SECRET=...       # For webhook signature verification
```

---

## Data Flow Diagram

```
                     ┌──────────────────────────────────────────────────────┐
                     │                 PHASE 1: CREATE                      │
                     │                                                      │
  Campaign           │   ┌──────────────┐    ┌─────────────────┐           │
  Architect ─────────┼──►│ EDM Designer │    │ Graphic Designer│           │
  (existing)         │   │              │    │                 │           │
  CAMPAIGN_READY     │   │ MJML→HTML    │    │ DALL-E 3 API    │           │
  event              │   │ + hero image │    │ + copy gen      │           │
                     │   └──────┬───────┘    └────────┬────────┘           │
                     │          │   CreativeAsset      │                    │
                     │          └──────────┬───────────┘                    │
                     │                     ▼                                │
                     │          ┌──────────────────┐                       │
                     │          │  Approval Gate    │ ← ApprovalsInbox UI  │
                     │          │  (human review)   │                       │
                     │          └────────┬─────────┘                       │
                     └───────────────────┼─────────────────────────────────┘
                                         │ CONTENT_APPROVED event
                     ┌───────────────────┼─────────────────────────────────┐
                     │                   ▼          PHASE 2: DISTRIBUTE    │
                     │   ┌───────────────────────┐                         │
                     │   │ Social Publisher Agent │                         │
                     │   │                       │                         │
                     │   │ Post Bridge MCP       │    SendGrid (existing)  │
                     │   │ → LinkedIn, X, Meta,  │    → Email sends        │
                     │   │   Instagram, etc.     │                         │
                     │   └───────────┬───────────┘                         │
                     │               │ external_post_id                    │
                     └───────────────┼─────────────────────────────────────┘
                                     │
                     ┌───────────────┼─────────────────────────────────────┐
                     │               ▼          PHASE 3: MONITOR           │
                     │   ┌───────────────────────┐                         │
                     │   │ SendGrid Webhooks     │  Social API Polling     │
                     │   │ open/click/bounce     │  impressions/likes      │
                     │   └───────────┬───────────┘                         │
                     │               │ EngagementEvent rows                │
                     │               ▼                                     │
                     │   ┌───────────────────────┐                         │
                     │   │ Campaign Monitor Agent│                         │
                     │   │ aggregate + benchmark │                         │
                     │   │ + recommend actions   │                         │
                     │   └───────────┬───────────┘                         │
                     │               │ CAMPAIGN_PERFORMANCE event          │
                     └───────────────┼─────────────────────────────────────┘
                                     │
                     ┌───────────────┼─────────────────────────────────────┐
                     │               ▼          PHASE 4: OPTIMISE          │
                     │   ┌───────────────────────┐                         │
                     │   │ Content Refresh Agent  │                         │
                     │   │ new variant → approve  │                         │
                     │   │ → re-publish          │                         │
                     │   └───────────────────────┘                         │
                     │                                                      │
                     │   Campaign Performance Dashboard (ResultsPage)       │
                     │   Funnel · Channel breakdown · A/B results · ROI    │
                     └──────────────────────────────────────────────────────┘
```

---

## Implementation Order

### Phase 1 Tasks (Creative Production) — Foundation

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 1.1 | Add `CreativeAsset` + `EngagementEvent` models | `models.py`, migration | — |
| 1.2 | Add `CreativeAssetType`, `CreativeAssetStatus` enums | `models.py` | — |
| 1.3 | Add new `DiscoveryType` values: `CREATIVE_BRIEF`, `CREATIVE_READY`, `CONTENT_APPROVED`, `ENGAGEMENT_RECEIVED` | `agent_bus.py` | — |
| 1.4 | Create MJML compilation utility | `packages/tools/src/mjml.py` | — |
| 1.5 | Create DALL-E MCP server | `packages/mcp/src/servers/dalle.py` | — |
| 1.6 | Create EDM Designer agent | `agents/edm_designer/` | 1.1, 1.3, 1.4 |
| 1.7 | Create Graphic Designer agent | `agents/graphic_designer/` | 1.1, 1.3, 1.5 |
| 1.8 | Add asset CRUD endpoints to campaigns router | `routers/campaigns.py` | 1.1 |
| 1.9 | Extend ApprovalQueueItem for creative assets | `models.py`, `routers/approvals.py` | 1.1 |
| 1.10 | Add `POST /{campaign_id}/generate-creative` endpoint | `routers/campaigns.py` | 1.6, 1.7 |
| 1.11 | Register new agents in `agents_registry.py` | `agents_registry.py` | 1.6, 1.7 |
| 1.12 | Frontend: AssetPreview component | `components/AssetPreview.tsx` | 1.8 |
| 1.13 | Frontend: CampaignWorkspace page (brief→assets→approval) | `pages/CampaignWorkspace.tsx` | 1.12 |
| 1.14 | Frontend: ApprovalsInbox shows creative assets | `pages/ApprovalsInbox.tsx` | 1.9, 1.12 |

### Phase 2 Tasks (Distribution)

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 2.1 | Create Post Bridge MCP server | `packages/mcp/src/servers/post_bridge.py` | — |
| 2.2 | Create Social Publisher agent | `agents/social_publisher/` | 1.1, 2.1 |
| 2.3 | Extend email sending with UTM params + campaign_id tracking | `routers/approvals.py` | — |
| 2.4 | Add `POST /{campaign_id}/launch` endpoint | `routers/campaigns.py` | 2.2 |
| 2.5 | Add scheduler jobs (social post scheduler, engagement poller) | `scheduler.py` | 2.1 |
| 2.6 | Register social publisher in agents_registry | `agents_registry.py` | 2.2 |

### Phase 3 Tasks (Monitoring)

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 3.1 | Create SendGrid webhook handler router | `routers/webhooks.py` | 1.1 |
| 3.2 | Social engagement polling (scheduled job) | `scheduler.py` | 2.5 |
| 3.3 | Create Campaign Monitor agent | `agents/campaign_monitor/` | 1.1 |
| 3.4 | Enhance attribution summary with engagement metrics | `routers/attribution.py` | 3.1 |
| 3.5 | Add per-campaign attribution endpoint | `routers/attribution.py` | 3.4 |
| 3.6 | Extend Lead model with engagement scoring | `models.py` | 3.1 |
| 3.7 | Add monitor to scheduler (daily per active campaign) | `scheduler.py` | 3.3 |
| 3.8 | Register campaign monitor in agents_registry | `agents_registry.py` | 3.3 |
| 3.9 | Frontend: ResultsPage campaign performance dashboard | `pages/ResultsPage.tsx` | 3.4, 3.5 |

### Phase 4 Tasks (Optimisation)

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 4.1 | Content Refresh agent | `agents/content_refresh/` | Phase 3 |
| 4.2 | A/B test statistical significance calculator | `packages/scoring/src/ab_testing.py` | 3.3 |
| 4.3 | Auto-variant-swap recommendation flow | Campaign Monitor enhancement | 4.2 |
| 4.4 | Frontend: A/B results + winner badge in CampaignWorkspace | Frontend | 4.2 |

---

## Testing Strategy

### Unit Tests
- `tests/unit/agents/test_edm_designer.py` — MJML generation + compilation
- `tests/unit/agents/test_graphic_designer.py` — DALL-E prompt construction
- `tests/unit/agents/test_social_publisher.py` — Post Bridge API call mock
- `tests/unit/agents/test_campaign_monitor.py` — Metric aggregation + benchmark comparison
- `tests/unit/mcp/test_dalle.py` — Image generation mock
- `tests/unit/mcp/test_post_bridge.py` — Social posting mock
- `tests/unit/routers/test_webhooks.py` — SendGrid webhook payload parsing + signature verification

### Integration Tests
- `tests/integration/test_campaign_creative_flow.py` — Campaign → generate-creative → approve → launch
- `tests/integration/test_engagement_attribution.py` — Webhook → EngagementEvent → Attribution summary

### Key Mocking Patterns
- DALL-E API: Mock `openai.images.generate()` → return fixture image URL
- Post Bridge: Mock HTTP POST → return fixture post IDs
- SendGrid webhook: Mock incoming POST with signed payload
- MJML CLI: Mock subprocess.run → return fixture HTML

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| DALL-E cost overrun | Budget cap per campaign (default 10 images); track spend in CreativeAsset metadata |
| Post Bridge rate limits | Queue + stagger social posts; fall back to scheduling for large campaigns |
| SendGrid webhook volume | Batch process; debounce rapid open/click events (same email+event within 5min → skip) |
| MJML rendering inconsistencies | Test against top 5 email clients (Gmail, Outlook, Apple Mail, Yahoo, Samsung); use battle-tested base templates |
| Platform ToS violations | Rate limit social posting (max 3 posts/day/platform); human approval gate before publish |
| Image generation quality | Include brand guidelines in DALL-E prompt; human review before publish; no fully autonomous posting |
| Webhook security | Verify SendGrid signature; IP allowlist; rate limit incoming |

---

## Cost Estimates (Monthly, per company)

| Service | Usage | Cost |
|---------|-------|------|
| DALL-E 3 | ~50 images/mo × $0.04 | ~$2 |
| Post Bridge | 1 workspace | $14 |
| SendGrid | Already included | $0 |
| Claude (EDM copy) | ~20 calls/mo | ~$1 |
| **Total incremental** | | **~$17/mo** |

---

## Agent Architecture Summary

After all 4 phases, the full agent team is **16 agents**:

| # | Agent | Type | Phase |
|---|-------|------|-------|
| 1-6 | GTM Strategist, Market Intel, Competitor, Customer, Lead Hunter, Campaign Architect | Analysis | Existing |
| 7-9 | Workforce Architect, Outreach Executor, CRM Sync | Execution | Existing |
| 10-12 | Signal Monitor, Lead Enrichment, Company Enricher | Intelligence | Existing |
| **13** | **EDM Designer** | **Creative** | **Phase 1** |
| **14** | **Graphic Designer** | **Creative** | **Phase 1** |
| **15** | **Social Publisher** | **Distribution** | **Phase 2** |
| **16** | **Campaign Monitor** | **Analytics** | **Phase 3** |

Plus a Content Refresh agent in Phase 4 (agent #17).

All agents inherit `BaseGTMAgent`, implement PDCA, and communicate via `AgentBus` pub/sub — consistent with existing architecture.
