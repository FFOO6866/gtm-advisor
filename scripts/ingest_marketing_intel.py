#!/usr/bin/env python3
"""Ingest marketing/comms industry intelligence as SignalEvents.

Replaces stale, off-vertical analysis signals for the HiMeetAI demo company
(marketing_comms vertical) with curated 2026 industry intelligence covering:
  - Competitor moves: Edelman, Weber Shandwick, Ogilvy, FleishmanHillard, Publicis
  - Market trends: AI orchestration, trust crisis, social fragmentation, GEO, creator commerce

Usage:
    uv run python scripts/ingest_marketing_intel.py
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "gtm_dev.db"
NOW = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")

# Dynamically resolve the Hi Meet.AI company ID so this script works after
# a fresh seed run without needing to update a hardcoded UUID.
def _resolve_company_id() -> str | None:
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id FROM companies WHERE name LIKE '%Hi Meet%' OR name LIKE '%HiMeet%' LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None

COMPANY_ID = _resolve_company_id()

# ---------------------------------------------------------------------------
# Signal definitions
# ---------------------------------------------------------------------------

SIGNALS: list[dict] = [
    # ------------------------------------------------------------------
    # Competitor Intelligence
    # ------------------------------------------------------------------
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "competitor_news",
        "urgency": "this_week",
        "headline": "Edelman — 2026 Trust Barometer: 'Trust Amid Insularity' reshaping PR strategies",
        "summary": (
            "Edelman's 2026 Trust Barometer 'Trust Amid Insularity' surveyed 34,000 respondents across "
            "28 countries (launched Jan 2026). Key findings: 70% are hesitant to trust those with "
            "differing values; Trust Index stagnates in developed markets (49) vs developing (66); "
            "employers now rank as highest-trust institution above media and government. Implication: "
            "businesses must actively broker workplace friction through conflict-resolution programming "
            "and hyperlocal community engagement. PR agencies are repositioning around 'trust brokering' "
            "as a primary service offering for 2026."
        ),
        "source": "analysis",
        "source_url": "https://www.edelman.com/trust/trust-barometer",
        "relevance_score": 0.93,
        "competitors_mentioned": json.dumps(["Edelman"]),
        "recommended_action": (
            "Review Edelman's trust brokering framework — position Hi Meet.AI as a trust-building "
            "partner for SG businesses navigating insularity. Consider adding a 'Trust & Authenticity' "
            "service module that draws on Edelman's data to benchmark client trust scores."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "competitor_news",
        "urgency": "this_week",
        "headline": "Weber Shandwick — HALO AI platform + 2026 prediction: AI orchestration, not plug-and-play",
        "summary": (
            "Weber Shandwick launched HALO, a proprietary agentic AI platform built in partnership "
            "with Google, designed for predictive modeling and campaign orchestration. Their 2026 "
            "industry prediction: AI has moved from experimentation to 'orchestration' — agencies "
            "that treat AI as plug-and-play will fall behind. Human judgment remains essential for "
            "ethics and creative direction. HALO handles research synthesis, audience segmentation, "
            "and performance prediction; humans handle strategy and creative execution."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.92,
        "competitors_mentioned": json.dumps(["Weber Shandwick", "Google"]),
        "recommended_action": (
            "Weber Shandwick positioning AI orchestration as the key differentiator for 2026. "
            "Assess how Hi Meet.AI's AI-native approach competes — specifically whether the PDCA "
            "agent loop can be framed as 'orchestration' rather than 'automation' in sales messaging."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "competitor_news",
        "urgency": "this_month",
        "headline": "Ogilvy — 'Social With Substance' report: audiences shifting from scrolls to saves, niche communities growing",
        "summary": (
            "Ogilvy's 2026 Social Trends report 'Social With Substance' identifies a fundamental shift "
            "from attention-seeking to intention-driven content. Five key trends: (1) Intention Seeking — "
            "audiences saving content for later action; (2) Internet Intimacy — Discord and private "
            "communities surging; (3) Proof of Craft — human imperfection beats AI polish; "
            "(4) Human Algorithm — creators shaping feeds over platform algorithms; "
            "(5) Merchant Entertainers — content-to-cart convergence. Ogilvy won 11 awards at 2026 "
            "PRWeek, the most of any agency. Run clubs +3x, watch parties +72% in community metrics."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.90,
        "competitors_mentioned": json.dumps(["Ogilvy"]),
        "recommended_action": (
            "Ogilvy's community-first playbook is gaining traction with the 'Social With Substance' "
            "framework. Review whether Hi Meet.AI can offer niche community strategy as a differentiator "
            "— particularly Discord-based B2B communities for SG SMEs in tech and fintech verticals."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "competitor_news",
        "urgency": "this_week",
        "headline": "FleishmanHillard — Earned media now ~50% of GPT citations, niche audiences replacing mass channels",
        "summary": (
            "FleishmanHillard's 2026 Corporate Affairs Trends report identifies three macro shifts: "
            "(1) 'Everything Gets Smaller' — niche audiences replacing mass channels, community-led "
            "campaigns outperforming broadcast; (2) 'End of Absolute Trust' — earned media accounts "
            "for ~50% of citations in ChatGPT and other LLM outputs, making GEO (Generative Engine "
            "Optimization) a critical new capability; (3) 'Zero-Sum World' — geopolitical fragmentation "
            "intensifying, with 83% of business leaders now formally monitoring geopolitical risk. "
            "FleishmanHillard is building dedicated GEO practice teams."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.95,
        "competitors_mentioned": json.dumps(["FleishmanHillard"]),
        "recommended_action": (
            "GEO (Generative Engine Optimization) is emerging as the new SEO — earned media drives "
            "~50% of AI citations. Assess the opportunity to add GEO advisory services to Hi Meet.AI's "
            "offering, helping SG clients ensure their brand narrative appears in LLM outputs. "
            "This is a first-mover opportunity in the SG market."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "competitor_news",
        "urgency": "this_month",
        "headline": "Publicis — 'Agentic Commerce' era: AI agents handling purchases, TikTok top retail media for CPG",
        "summary": (
            "Publicis Commerce's 2026 outlook centres on 'Agentic Commerce' — the phase where AI "
            "agents (including ChatGPT's checkout integration) handle product discovery and purchase "
            "decisions autonomously on behalf of consumers. Key findings: TikTok Shop has overtaken "
            "traditional retail media for CPG brands, with items-per-second velocity up 50% YoY; "
            "creator-affiliate commerce is blurring the line between content and cart; AI livestreams "
            "are already normalised in China and spreading across APAC. Publicis is restructuring "
            "its commerce practice around agentic discovery and social-first checkout flows."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.87,
        "competitors_mentioned": json.dumps(["Publicis", "TikTok Shop", "ChatGPT"]),
        "recommended_action": (
            "Social commerce via TikTok Shop is growing explosively in APAC. Consider adding a "
            "social commerce strategy module to Hi Meet.AI's service offering — particularly for "
            "SG retail and F&B SMEs who are underserved by traditional agency models. "
            "Position against Publicis's enterprise-only agentic commerce practice."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    # ------------------------------------------------------------------
    # Market Trend Signals
    # ------------------------------------------------------------------
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "market_trend",
        "urgency": "this_week",
        "headline": "Industry trend: AI moving from experimentation to orchestration across major agencies",
        "summary": (
            "Multiple major agencies (Weber Shandwick HALO, Publicis Marcel, WPP Open X) are moving "
            "from AI experimentation to proprietary AI orchestration platforms. The consensus view for "
            "2026: agencies that treat AI as plug-and-play commodity tools will fall behind; winners "
            "will be those who build proprietary data loops, orchestration layers, and human-AI "
            "workflow integration. Human judgment remains non-negotiable for ethics, legal risk, and "
            "creative direction. SME-focused players like Hi Meet.AI have a window to compete on "
            "orchestration sophistication before large agencies fully productise their platforms."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.94,
        "competitors_mentioned": json.dumps(["Weber Shandwick", "Publicis", "WPP"]),
        "recommended_action": (
            "Reframe Hi Meet.AI's positioning from 'AI marketing tool' to 'AI orchestration platform "
            "for SG SMEs'. Develop content series on orchestration vs automation to build thought "
            "leadership and differentiate from commodity AI tools."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "market_trend",
        "urgency": "this_month",
        "headline": "Trust crisis deepening: 70% hesitant to trust those with differing values — authenticity premium rising",
        "summary": (
            "Edelman's 2026 data shows a deepening trust crisis: 70% of people are hesitant to trust "
            "those with differing values, and the Trust Index in developed markets has stagnated at 49 "
            "(neutral/distrust territory). The implication for marketing communications: audiences can "
            "detect inauthenticity and will disengage or actively oppose brands that feel performative. "
            "Agencies and brands that invest in honest storytelling, community accountability, and "
            "genuine local engagement are commanding an 'authenticity premium' — higher engagement "
            "rates and lower churn. PR must now broker divides, not just broadcast messages."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.91,
        "competitors_mentioned": json.dumps(["Edelman"]),
        "recommended_action": (
            "Build an 'Authenticity Audit' service offering for SG SME clients: assess current "
            "brand communications against Edelman's trust indicators, identify gaps, and deliver "
            "a prioritised action plan. This directly addresses what 70% of audiences are responding "
            "to in 2026."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "market_trend",
        "urgency": "this_month",
        "headline": "Audience fragmentation accelerating: niche communities (Discord, run clubs +3x) replacing mass social",
        "summary": (
            "Ogilvy's 'Social With Substance' data points confirm a structural shift in audience "
            "behaviour: run clubs have grown 3x, watch parties +72%, Discord server memberships "
            "growing at 40%+ YoY. Mass social (Instagram, Facebook) engagement rates are declining "
            "as users migrate to intentional, interest-specific communities. Brands following niche "
            "communities are seeing 3-5x higher engagement than equivalent broadcast campaigns. "
            "The 'Proof of Craft' trend indicates audiences reward visible human effort and imperfection "
            "over AI-generated polish — relevant for both content strategy and creative direction."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.89,
        "competitors_mentioned": json.dumps(["Ogilvy"]),
        "recommended_action": (
            "Develop a 'Community-Led Growth' playbook for SG B2B tech clients — Discord community "
            "setup, niche content strategy, and community-to-lead conversion frameworks. "
            "Position against traditional agency broadcast models. Target SG fintech and SaaS "
            "verticals where professional communities are underserved."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "market_trend",
        "urgency": "this_week",
        "headline": "GEO (Generative Engine Optimization) emerging as critical skill — earned media drives ~50% of AI citations",
        "summary": (
            "FleishmanHillard's 2026 research reveals that earned media (press coverage, third-party "
            "mentions, high-authority backlinks) accounts for approximately 50% of citations in "
            "ChatGPT, Perplexity, and other LLM responses. This fundamentally changes the value "
            "proposition of PR: traditional SEO (ranking in Google) is giving way to GEO (appearing "
            "in AI-generated answers). Brands with strong earned media footprints are now appearing "
            "in AI-generated answers for commercial queries. FleishmanHillard, Burson, and Edelman "
            "are all building dedicated GEO practice teams for 2026 client mandates."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.96,
        "competitors_mentioned": json.dumps(["FleishmanHillard", "Burson", "Edelman"]),
        "recommended_action": (
            "GEO is a first-mover opportunity for Hi Meet.AI in the SG market — major global agencies "
            "are just beginning to build practices. Develop a 'GEO Readiness Assessment' for SG SME "
            "clients: audit current AI citation footprint, identify earned media gaps, and deliver a "
            "90-day GEO action plan. This is a high-value, defensible service with minimal local competition."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
    {
        "id": str(uuid.uuid4()),
        "company_id": COMPANY_ID,
        "signal_type": "market_trend",
        "urgency": "this_month",
        "headline": "Creator commerce exploding: TikTok Shop +50% velocity, AI livestreams mainstream in APAC",
        "summary": (
            "Publicis Commerce 2026 data: TikTok Shop items-per-second up 50% YoY, now the top retail "
            "media platform for CPG brands in SEA. Creator-affiliate commerce is becoming the dominant "
            "format, with the line between content and cart effectively disappearing. AI-powered "
            "livestreams (virtual hosts, real-time personalisation) are already normalised in China "
            "and spreading rapidly to Singapore, Malaysia, and Indonesia. ChatGPT's checkout "
            "integration signals that agentic commerce — where AI agents make purchases on behalf "
            "of consumers — is 12-18 months away from mainstream adoption in SG."
        ),
        "source": "analysis",
        "source_url": None,
        "relevance_score": 0.88,
        "competitors_mentioned": json.dumps(["Publicis", "TikTok Shop"]),
        "recommended_action": (
            "Creator commerce is an underserved segment for SG SMEs — most lack the resources to "
            "run creator programs at scale. Consider a 'Creator Commerce Starter Pack' service: "
            "TikTok Shop setup, micro-creator identification (10K-100K followers), affiliate structure, "
            "and performance tracking. Target SG retail, F&B, and lifestyle SMEs as a wedge market."
        ),
        "is_actioned": 0,
        "created_at": NOW,
    },
]

# ---------------------------------------------------------------------------
# IDs of stale/off-vertical analysis signals to delete for HiMeetAI company
# These were generated by generic agent runs against wrong vertical data.
# ---------------------------------------------------------------------------

STALE_IDS_TO_DELETE: list[str] = [
    "3e188a4ef59e43549fbd32451305e8ac",   # Professional_Services Market Analysis — HiMeetAI
    "69e88011b3b94bef9d872fa55e760ba2",   # Competitive Landscape — Top 5 Players
    "32c552ccff964155be39aca381566fab",   # AI-Driven Growth in Creative Services
    "a3a8b0c63cc54129936406b06ce29af8",   # Instantly.ai — cold email tool, wrong vertical
    "65f1b1327ed14b73900115c6faed63f7",   # Runway ML — video AI, wrong vertical
    "d4eccfb3672f4b3d8dd495188209057c",   # HubSpot, Inc. — CRM, wrong vertical
    "b1b34e758a904711b93b7896121c8b2a",   # Apollo.io — sales tool, wrong vertical
    "8a20a3cd304f42118e2dda433403e5b6",   # QuinStreet Inc. — finance domains, wrong vertical
    "c9da12207d8c4294858c56a834858075",   # Braze Inc. — martech, wrong vertical
]

INSERT_SQL = """
INSERT OR REPLACE INTO signal_events (
    id, company_id, signal_type, urgency,
    headline, summary, source, source_url,
    relevance_score, competitors_mentioned,
    recommended_action, is_actioned, created_at
) VALUES (
    :id, :company_id, :signal_type, :urgency,
    :headline, :summary, :source, :source_url,
    :relevance_score, :competitors_mentioned,
    :recommended_action, :is_actioned, :created_at
)
"""


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    if COMPANY_ID is None:
        raise ValueError(
            "Hi Meet.AI company not found in database. "
            "Run: uv run python scripts/seed_himeetai.py first."
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Verify company exists
        cursor.execute("SELECT id, name FROM companies WHERE id = ?", (COMPANY_ID,))
        company = cursor.fetchone()
        if company is None:
            raise ValueError(
                f"Company {COMPANY_ID} not found in companies table. "
                "Run: uv run python scripts/seed_himeetai.py first."
            )
        print(f"Target company: {company['name']} ({COMPANY_ID})")

        # Delete stale off-vertical signals
        placeholders = ",".join("?" * len(STALE_IDS_TO_DELETE))
        cursor.execute(
            f"DELETE FROM signal_events WHERE id IN ({placeholders})",
            STALE_IDS_TO_DELETE,
        )
        deleted = cursor.rowcount
        print(f"Deleted {deleted} stale/off-vertical signal(s)")

        # Insert new industry intelligence signals
        inserted = 0
        for signal in SIGNALS:
            cursor.execute(INSERT_SQL, signal)
            inserted += 1

        conn.commit()
        print(f"Inserted {inserted} marketing/comms industry intelligence signal(s)")

        # Summary
        cursor.execute(
            "SELECT signal_type, urgency, headline FROM signal_events "
            "WHERE company_id = ? AND source = 'analysis' "
            "ORDER BY urgency, signal_type",
            (COMPANY_ID,),
        )
        rows = cursor.fetchall()
        print(f"\nTotal analysis signals now for {company['name']}: {len(rows)}")
        for row in rows:
            urgency_label = row["urgency"].upper().replace("_", " ")
            print(f"  [{urgency_label}] [{row['signal_type']}] {row['headline'][:80]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
