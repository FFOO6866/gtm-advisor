#!/usr/bin/env python3
"""Synthesize domain knowledge guides from Qdrant book chunks.

Reads the 'marketing_knowledge' Qdrant collection (populated by
scripts/build_knowledge_base_books.py), retrieves the most relevant
book excerpts for each guide topic, and uses GPT-4o to synthesize them
into structured operational guides stored in data/knowledge/guides/.

Each guide is a JSON file agents load at runtime via
KnowledgeMCPServer.get_domain_guide() — they tell agents HOW to do
things (step-by-step methodology, decision rules, Singapore specifics)
rather than just WHAT frameworks exist.

Prerequisites:
    1. Run scripts/build_knowledge_base_books.py first to populate Qdrant.
    2. Set OPENAI_API_KEY and (QDRANT_URL or QDRANT_PATH).

Usage:
    uv run python scripts/synthesize_domain_guides.py
    uv run python scripts/synthesize_domain_guides.py --slug digital_awareness_campaign
    uv run python scripts/synthesize_domain_guides.py --dry-run
    uv run python scripts/synthesize_domain_guides.py --list

Environment variables:
    OPENAI_API_KEY   — required for synthesis (GPT-4o) and embedding
    QDRANT_URL       — Qdrant HTTP endpoint (preferred)
    QDRANT_PATH      — local Qdrant data path (fallback)

Cost estimate:
    ~18 guides × ~3K prompt tokens × GPT-4o input = ~54K tokens input
    ~18 guides × ~1K completion tokens = ~18K tokens output
    Total: well under $1 at current GPT-4o pricing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("synthesize_guides")

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

GUIDES_DIR = _REPO_ROOT / "data" / "knowledge" / "guides"

# ---------------------------------------------------------------------------
# Guide catalog
#
# Each entry defines:
#   slug           — filename (without .json) and identifier used by agents
#   title          — human-readable title
#   agent_relevance — which agents load this guide
#   search_queries  — Qdrant queries to retrieve relevant book chunks
#                     (run in order; results are deduplicated by chunk id)
#   must_cover     — topics the synthesis prompt explicitly asks GPT-4o to address
# ---------------------------------------------------------------------------

GUIDE_CATALOG: list[dict] = [
    # --- Campaign Architect ---
    {
        "slug": "digital_awareness_campaign",
        "title": "B2B Digital Awareness Campaign Launch",
        "agent_relevance": ["campaign-architect", "gtm-strategist"],
        "search_queries": [
            "how to launch a B2B digital awareness campaign phases reach act convert engage",
            "content marketing strategy for B2B awareness brand visibility",
            "LinkedIn advertising B2B campaign targeting strategy",
            "digital marketing campaign budget allocation channels",
            "campaign launch sequencing awareness nurture conversion",
        ],
        "must_cover": [
            "campaign phases (reach, act, convert, engage) with timing and budget allocation",
            "channel selection and sequencing for B2B Singapore market",
            "creative and messaging principles from the literature",
            "how to measure awareness campaign success",
            "common mistakes in B2B awareness campaigns",
        ],
    },
    {
        "slug": "cold_email_sequence",
        "title": "B2B Cold Email Sequence Design",
        "agent_relevance": ["campaign-architect", "lead-hunter"],
        "search_queries": [
            "cold email outreach sequence design B2B persuasion copywriting",
            "PAS problem agitate solution email framework cold outreach",
            "Cialdini reciprocity social proof cold email sequence",
            "email sequence touches follow-up cadence B2B",
            "objection handling in email sequences just listen Goulston",
        ],
        "must_cover": [
            "email sequence structure: number of touches, spacing, subject line principles",
            "Cialdini principles applied to cold email (reciprocity, social proof, authority)",
            "PAS vs AIDA framework selection for different email types",
            "subject line rules from Ogilvy and copywriting literature",
            "follow-up strategy and when to stop",
        ],
    },
    {
        "slug": "content_marketing_b2b",
        "title": "B2B Content Marketing Strategy",
        "agent_relevance": ["campaign-architect", "gtm-strategist"],
        "search_queries": [
            "B2B content marketing strategy thought leadership inbound",
            "new rules of marketing PR David Meerman Scott content creation",
            "content calendar planning B2B blog LinkedIn articles",
            "educational content marketing buyer journey awareness",
            "content distribution amplification B2B channels",
        ],
        "must_cover": [
            "content types by buyer journey stage (awareness, consideration, decision)",
            "thought leadership vs product content balance",
            "distribution channels and amplification strategy",
            "editorial calendar planning and publishing cadence",
            "how to measure content marketing ROI",
        ],
    },
    {
        "slug": "campaign_measurement",
        "title": "Campaign Measurement and Attribution",
        "agent_relevance": ["campaign-architect"],
        "search_queries": [
            "marketing campaign measurement attribution ROI metrics",
            "RACE framework reach act convert engage measurement KPIs",
            "marketing attribution models first-touch last-touch multi-touch",
            "campaign analytics conversion tracking B2B",
            "marketing ROI calculation revenue attribution pipeline",
        ],
        "must_cover": [
            "attribution models (first-touch, last-touch, linear, time-decay) and when to use each",
            "KPIs per campaign phase: awareness, engagement, conversion, retention",
            "how to set up tracking before a campaign launches",
            "reporting cadence and stakeholder communication",
            "common measurement mistakes and vanity metrics to avoid",
        ],
    },
    {
        "slug": "linkedin_b2b_campaign",
        "title": "LinkedIn B2B Campaign Strategy",
        "agent_relevance": ["campaign-architect"],
        "search_queries": [
            "LinkedIn advertising B2B campaign Sponsored Content Message Ads",
            "LinkedIn targeting job title company size account-based marketing",
            "social media marketing B2B LinkedIn organic content strategy",
            "LinkedIn lead generation forms conversion B2B",
            "digital advertising social proof authority LinkedIn",
        ],
        "must_cover": [
            "LinkedIn ad format selection: Sponsored Content vs Message Ads vs Dynamic Ads",
            "audience targeting criteria for Singapore B2B (job titles, company size, industry)",
            "organic vs paid LinkedIn strategy and when to invest in each",
            "creative principles for LinkedIn: image, video, carousel formats",
            "LinkedIn campaign metrics: CTR benchmarks, CPL targets, frequency caps",
        ],
    },
    # --- GTM Strategist ---
    {
        "slug": "gtm_motion_selection",
        "title": "GTM Motion Selection: PLG, SLG, MLG",
        "agent_relevance": ["gtm-strategist"],
        "search_queries": [
            "product-led growth sales-led marketing-led go-to-market motion selection",
            "go-to-market strategy framework product market fit motion",
            "when to use PLG vs SLG vs channel-led growth startup",
            "sales motion selection deal size sales cycle complexity",
            "go-to-market strategy B2B SaaS revenue model",
        ],
        "must_cover": [
            "decision criteria for PLG vs SLG vs MLG vs partner-led",
            "how deal size and sales cycle complexity drive motion selection",
            "hybrid motions: when and how to combine PLG with sales overlay",
            "signals that indicate a motion is working vs needs to change",
            "Singapore/APAC market considerations for motion selection",
        ],
    },
    {
        "slug": "singapore_market_entry",
        "title": "Singapore and APAC Market Entry",
        "agent_relevance": ["gtm-strategist", "market-intelligence"],
        "search_queries": [
            "Singapore market entry strategy B2B technology SME",
            "ASEAN market expansion Singapore hub internationalization",
            "Singapore SME buying behaviour decision making grants PSG",
            "market entry strategy Asia Pacific competitive landscape",
            "go-to-market Singapore regulatory environment MAS PDPA",
        ],
        "must_cover": [
            "Singapore as APAC hub: advantages, infrastructure, talent pool",
            "PSG grant and EnterpriseSG programmes as GTM levers",
            "Singapore SME buyer behaviour: risk aversion, relationship-first, grant eligibility",
            "ASEAN expansion sequence from Singapore HQ",
            "PDPA compliance requirements for marketing and sales activities",
        ],
    },
    {
        "slug": "b2b_saas_pricing",
        "title": "B2B SaaS Pricing Strategy",
        "agent_relevance": ["gtm-strategist"],
        "search_queries": [
            "B2B SaaS pricing strategy subscription tiers value-based pricing",
            "pricing strategy Kotler value proposition pricing models",
            "freemium vs trial vs direct sales pricing model selection",
            "price anchoring packaging tiers enterprise pricing",
            "pricing psychology willingness to pay B2B software",
        ],
        "must_cover": [
            "pricing model selection: per-seat, usage-based, value-based, tiered",
            "value-based pricing methodology: how to anchor on ROI not cost",
            "packaging design: starter, growth, enterprise tier criteria",
            "price psychology: anchoring, decoy pricing, loss aversion",
            "Singapore pricing considerations: PSG grant impact, SME budget cycles",
        ],
    },
    # --- Customer Profiler ---
    {
        "slug": "icp_development",
        "title": "ICP Development Methodology",
        "agent_relevance": ["customer-profiler", "gtm-strategist"],
        "search_queries": [
            "ideal customer profile ICP development firmographic technographic behavioral",
            "market segmentation targeting B2B Kotler STP framework",
            "ICP criteria qualification signals buying triggers",
            "B2B customer segmentation criteria employee count revenue stage",
            "ICP scoring prioritization tier 1 2 3 customer segments",
        ],
        "must_cover": [
            "ICP dimension framework: firmographic, technographic, behavioural, psychographic",
            "how to derive ICP from limited data vs rich data",
            "qualification signals and disqualification criteria",
            "ICP tiering: Tier 1 (ideal), Tier 2 (good), Tier 3 (acceptable)",
            "how to validate ICP against win/loss data or market signals",
        ],
    },
    {
        "slug": "buyer_persona_research",
        "title": "Buyer Persona Research and Development",
        "agent_relevance": ["customer-profiler"],
        "search_queries": [
            "buyer persona development research B2B decision maker champion",
            "persona job title KPIs pain points goals challenges",
            "buying committee B2B stakeholder map decision maker influencer",
            "persona research methodology interview survey data synthesis",
            "B2B persona messaging personalisation by role",
        ],
        "must_cover": [
            "persona components: job title, KPIs, pain points, goals, tools used, trigger events",
            "buying committee mapping: champion, decision maker, influencer, gatekeeper",
            "research methods to validate personas (interviews, win/loss, LinkedIn data)",
            "how to differentiate personas when data is limited vs rich",
            "messaging personalisation by persona role and pain point",
        ],
    },
    {
        "slug": "buyer_journey_mapping",
        "title": "B2B Buyer Journey Mapping",
        "agent_relevance": ["customer-profiler", "campaign-architect"],
        "search_queries": [
            "B2B buyer journey stages awareness consideration decision purchase",
            "customer journey mapping touchpoints content alignment",
            "AIDA funnel awareness interest desire action B2B",
            "buyer journey content strategy what to create for each stage",
            "sales and marketing alignment buyer journey handoff",
        ],
        "must_cover": [
            "B2B buyer journey stages and typical duration in Singapore SME market",
            "content mapping: what content type for which stage",
            "touchpoint sequencing: how buyers move from awareness to consideration",
            "sales/marketing handoff criteria: when MQL becomes SQL",
            "how to measure and optimise stage conversion rates",
        ],
    },
    # --- Competitor Analyst ---
    {
        "slug": "competitive_intelligence",
        "title": "Competitive Intelligence Gathering",
        "agent_relevance": ["competitor-analyst"],
        "search_queries": [
            "competitive intelligence gathering methods research competitor analysis",
            "Porter five forces competitive analysis industry structure",
            "SWOT analysis competitor strengths weaknesses opportunities threats",
            "competitive landscape mapping market positioning",
            "competitor research sources data signals product pricing",
        ],
        "must_cover": [
            "intelligence gathering sources: public filings, job postings, pricing pages, reviews",
            "Porter Five Forces application to competitor landscape",
            "SWOT construction methodology: what evidence goes into each quadrant",
            "how to identify competitor weaknesses to exploit in positioning",
            "ongoing competitive monitoring: signals, triggers, cadence",
        ],
    },
    {
        "slug": "positioning_differentiation",
        "title": "Positioning and Differentiation Strategy",
        "agent_relevance": ["competitor-analyst", "gtm-strategist"],
        "search_queries": [
            "positioning differentiation strategy value proposition unique",
            "competitive positioning statement blue ocean red ocean strategy",
            "differentiation strategy Kotler brand positioning map",
            "how to position against competitors messaging differentiation",
            "value proposition development unique selling point",
        ],
        "must_cover": [
            "positioning statement structure: for [ICP] who [problem], [product] is [category] that [differentiator]",
            "positioning map methodology: axes selection and competitor plotting",
            "Blue Ocean vs Red Ocean: when to compete vs create new space",
            "how to identify and own a defensible differentiation axis",
            "messaging hierarchy: how positioning flows to persona-level copy",
        ],
    },
    {
        "slug": "swot_to_strategy",
        "title": "SWOT Analysis to Strategic Action",
        "agent_relevance": ["competitor-analyst", "gtm-strategist"],
        "search_queries": [
            "SWOT analysis strategic planning SO WO ST WT strategies",
            "converting SWOT to actionable strategy competitive advantage",
            "strategic options from SWOT strengths opportunities threats weaknesses",
            "competitive strategy offensive defensive based on SWOT",
            "SWOT analysis B2B technology company strategic planning",
        ],
        "must_cover": [
            "SWOT construction: what qualifies as a true strength vs assumption",
            "SO/WO/ST/WT strategy matrix: how each quadrant drives a strategic direction",
            "priority ranking: which SWOT items matter most for GTM",
            "how to convert SWOT insights into specific GTM actions (not just observations)",
            "validation: how to test strategic assumptions from SWOT",
        ],
    },
    # --- Market Intelligence ---
    {
        "slug": "market_sizing",
        "title": "Market Sizing: TAM, SAM, SOM",
        "agent_relevance": ["market-intelligence", "gtm-strategist"],
        "search_queries": [
            "market sizing TAM SAM SOM total addressable market methodology",
            "top-down bottom-up market sizing approach calculation",
            "market sizing B2B software Singapore APAC methodology",
            "addressable market calculation revenue potential estimation",
            "market research demand estimation industry size",
        ],
        "must_cover": [
            "TAM/SAM/SOM definitions and the distinction that matters for GTM decisions",
            "top-down sizing: industry reports, multipliers, assumptions",
            "bottom-up sizing: unit economics × addressable accounts methodology",
            "how to label estimates with confidence levels (data-backed vs inferred)",
            "common sizing mistakes: confusing TAM with SAM, overstating capture rate",
        ],
    },
    {
        "slug": "industry_trend_analysis",
        "title": "Industry Trend Analysis and Signal Interpretation",
        "agent_relevance": ["market-intelligence"],
        "search_queries": [
            "industry trend analysis market signals macro trends technology adoption",
            "market trend identification Porter five forces macro environment",
            "PESTLE analysis political economic social technology legal environmental",
            "market signal interpretation competitive intelligence trends",
            "emerging market trends B2B technology disruption opportunities",
        ],
        "must_cover": [
            "trend signal types: macro (PESTLE), industry (Porter), micro (company signals)",
            "how to distinguish signal from noise in market data",
            "trend validation methodology: multiple source corroboration",
            "translating trend insights into GTM actions (not just observations)",
            "Singapore-specific macro signals: government initiatives, MAS regulations, digitisation push",
        ],
    },
    # --- Lead Hunter ---
    {
        "slug": "lead_qualification",
        "title": "Lead Qualification Methodology",
        "agent_relevance": ["lead-hunter"],
        "search_queries": [
            "lead qualification BANT budget authority need timeline",
            "MEDDIC qualification methodology enterprise sales",
            "SPIN selling qualification discovery questions",
            "lead scoring criteria fit intent activity qualification",
            "sales qualification framework deal size complexity",
        ],
        "must_cover": [
            "BANT: when to use it and its limitations in modern B2B sales",
            "MEDDIC: metrics, economic buyer, decision criteria, decision process, identify pain, champion",
            "SPIN: situation, problem, implication, need-payoff question sequences",
            "how to select the right framework by deal size and complexity",
            "disqualification criteria: what signals mean a lead should not be pursued",
        ],
    },
    {
        "slug": "signal_based_prospecting",
        "title": "Signal-Based Prospecting",
        "agent_relevance": ["lead-hunter", "market-intelligence"],
        "search_queries": [
            "buying signals intent data trigger events prospect outreach timing",
            "signal-based selling trigger events hiring funding expansion",
            "intent data prospecting B2B sales signal identification",
            "buying trigger events company announcements news signals",
            "right time to reach prospect trigger event signal outreach",
        ],
        "must_cover": [
            "signal types: hiring signals, funding signals, technology signals, event signals",
            "signal urgency classification: act within 24h vs 1 week vs 1 month",
            "how to correlate signals to ICP fit before reaching out",
            "outreach personalisation using the specific signal that triggered contact",
            "signal monitoring cadence and tooling recommendations",
        ],
    },
    # --- Singapore-specific guides ---
    {
        "slug": "singapore_psg_grants",
        "title": "Singapore PSG & EDG Grant Strategy for SaaS Vendors",
        "agent_relevance": ["gtm-strategist", "customer-profiler", "lead-hunter"],
        "search_queries": [
            "PSG productivity solutions grant Singapore SME eligible vendors SaaS",
            "EDG enterprise development grant Singapore capability development funding",
            "Singapore government grant B2B sales strategy vendor positioning",
            "PSG approved vendor list category fintech SaaS HR CRM",
            "Singapore SME grant funding cycle budget approval procurement",
        ],
        "must_cover": [
            "PSG eligibility criteria and funding percentages",
            "How to position product as PSG-eligible solution",
            "Grant application cycle timing and budget planning",
            "EDG vs PSG choice framework for vendors",
        ],
    },
    {
        "slug": "singapore_pdpa_gtm",
        "title": "PDPA-Compliant GTM Execution in Singapore",
        "agent_relevance": ["campaign-architect", "gtm-strategist", "outreach-executor"],
        "search_queries": [
            "PDPA marketing consent Singapore B2B email outreach compliance",
            "Do Not Call DNC registry Singapore marketing exemptions",
            "Singapore personal data protection marketing best practices",
            "PDPA B2B exception corporate email marketing Singapore",
            "data protection officer DPO Singapore SME marketing requirements",
        ],
        "must_cover": [
            "PDPA consent requirements for B2B email marketing",
            "DNC registry checking workflow before outreach",
            "Opt-out mechanisms in email campaigns",
            "Safe harbor for B2B corporate address marketing",
        ],
    },
    {
        "slug": "singapore_asean_expansion",
        "title": "Singapore as ASEAN Hub: Regional Expansion GTM",
        "agent_relevance": ["gtm-strategist", "market-intelligence", "customer-profiler"],
        "search_queries": [
            "Singapore ASEAN hub regional expansion strategy B2B SaaS",
            "MRA market readiness assistance grant overseas expansion Singapore",
            "ASEAN market entry from Singapore localization GTM",
            "Singapore regional HQ APAC expansion gateway strategy",
            "Southeast Asia B2B market differences Singapore Malaysia Indonesia",
        ],
        "must_cover": [
            "Why Singapore-first then ASEAN expansion is the optimal GTM motion",
            "MRA grant for overseas market entry costs",
            "Key ASEAN market differences: payment, language, regulation",
            "EnterpriseSG overseas market support resources",
        ],
    },
]

# ---------------------------------------------------------------------------
# Synthesis prompt templates
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = """You are a marketing knowledge synthesizer. Your task is to extract structured, actionable operational guidance from real book excerpts — not from your general training knowledge.

STRICT RULES:
1. Every item in core_principles MUST cite its exact source book from the excerpts provided.
2. Do NOT use knowledge not present in the provided excerpts — mark gaps as "(inferred — verify with source)".
3. All text fields must be under 130 characters each (for token efficiency).
4. decision_rules must follow strict IF/WHEN → action format.
5. singapore_adaptations must be specific and practical, not generic.
6. Return valid JSON ONLY — no markdown fences, no explanation text outside the JSON."""

_SYNTHESIS_USER_TEMPLATE = """GUIDE TOPIC: {title}
AGENT USERS: {agents}
WHAT THIS GUIDE MUST COVER:
{must_cover}

BOOK EXCERPTS ({chunk_count} passages from {book_count} books):
---
{excerpts}
---

Synthesize ONLY from the excerpts above into this exact JSON structure:
{{
  "core_principles": [
    {{"principle": "concise principle statement", "source": "exact book title from excerpts", "application": "how to apply it"}}
  ],
  "process_steps": [
    {{"step": 1, "phase": "phase name", "objective": "what to achieve", "actions": ["specific action 1", "specific action 2"], "timing": "e.g. Week 1-2"}}
  ],
  "decision_rules": [
    "If [condition]: [specific action]",
    "When [condition]: [specific action]"
  ],
  "singapore_adaptations": [
    "Specific Singapore B2B adaptation with concrete detail"
  ],
  "common_mistakes": [
    "Specific mistake to avoid (not a generic warning)"
  ],
  "success_metrics": {{
    "metric name": "specific target value or formula"
  }}
}}

REQUIREMENTS:
- 3–5 core_principles, each citing a source book present in the excerpts
- 4–8 process_steps covering the complete end-to-end workflow
- 5–8 decision_rules as actionable IF/WHEN → action statements
- 3–5 singapore_adaptations specific to Singapore B2B SME context
- 3–5 common_mistakes (concrete, not vague)
- 3–5 success_metrics with realistic quantitative targets where available"""


# ---------------------------------------------------------------------------
# Helper: collect chunks from Qdrant for a list of queries
# ---------------------------------------------------------------------------


async def _collect_chunks(
    qdrant_client,
    openai_client,
    queries: list[str],
    limit_per_query: int = 8,
) -> list[dict]:
    """Run each query against Qdrant and return deduplicated chunks."""
    seen_ids: set[str] = set()
    chunks: list[dict] = []

    for query in queries:
        try:
            embed_resp = await openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query.strip()[:6000],
            )
            embedding = embed_resp.data[0].embedding

            response = await qdrant_client.query_points(
                collection_name="marketing_knowledge",
                query=embedding,
                limit=limit_per_query,
                with_payload=True,
            )
            for hit in response.points:
                payload = hit.payload or {}
                chunk_id = str(hit.id)
                if chunk_id in seen_ids:
                    continue
                seen_ids.add(chunk_id)
                chunks.append({
                    "id": chunk_id,
                    "book_title": payload.get("book_title", "Unknown"),
                    "book_key": payload.get("book_key", ""),
                    "chapter": payload.get("chapter"),
                    "page_number": payload.get("page_number", 0),
                    "text": payload.get("text", ""),
                    "score": round(hit.score, 4),
                })
        except Exception as exc:
            logger.warning("Query failed for '%s': %s", query[:60], exc)

    # Sort by relevance score descending.
    chunks.sort(key=lambda c: c["score"], reverse=True)
    return chunks


# ---------------------------------------------------------------------------
# Synthesize one guide
# ---------------------------------------------------------------------------


async def synthesize_guide(
    guide_def: dict,
    qdrant_client,
    openai_client,
    dry_run: bool = False,
) -> dict | None:
    """Retrieve chunks for a guide topic and synthesize into a structured guide dict."""
    slug = guide_def["slug"]
    title = guide_def["title"]
    logger.info("Synthesizing: %s", slug)

    if dry_run:
        # In dry-run mode, skip Qdrant queries and just show the search queries.
        logger.info("  DRY RUN: %d search queries — %s", len(guide_def["search_queries"]),
                    guide_def["search_queries"][0][:80])
        return None

    if openai_client is None:
        raise ValueError(f"openai_client is required to synthesize guide '{slug}' (OPENAI_API_KEY not set?)")

    chunks = await _collect_chunks(
        qdrant_client,
        openai_client,
        guide_def["search_queries"],
        limit_per_query=8,
    )

    if not chunks:
        logger.warning("No Qdrant chunks found for '%s' — skipping (is Qdrant populated?)", slug)
        return None

    # Cap at 20 most relevant chunks to keep prompt size manageable.
    chunks = chunks[:20]
    book_titles = list(dict.fromkeys(c["book_title"] for c in chunks))

    # Format excerpts for the synthesis prompt.
    excerpt_parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        chapter_note = f", {c['chapter']}" if c.get("chapter") else ""
        excerpt_parts.append(
            f"[{i}] {c['book_title']}{chapter_note} (p.{c['page_number']}, score={c['score']}):\n"
            f"{c['text'][:800]}"
        )
    excerpts = "\n\n".join(excerpt_parts)

    must_cover_str = "\n".join(f"  - {item}" for item in guide_def.get("must_cover", []))
    agents_str = ", ".join(guide_def.get("agent_relevance", []))

    user_content = _SYNTHESIS_USER_TEMPLATE.format(
        title=title,
        agents=agents_str,
        must_cover=must_cover_str,
        chunk_count=len(chunks),
        book_count=len(book_titles),
        excerpts=excerpts,
    )

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYNTHESIS_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,  # Low temperature for consistent structured output.
            max_tokens=2000,
        )
        raw = response.choices[0].message.content or "{}"
        synthesized = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("GPT-4o returned invalid JSON for '%s': %s", slug, exc)
        return None
    except Exception as exc:
        logger.error("Synthesis API call failed for '%s': %s", slug, exc)
        return None

    # Attach metadata — placed after **synthesized so our keys always win
    # even if GPT-4o erroneously includes them in its JSON output.
    guide = {
        **synthesized,
        "slug": slug,
        "title": title,
        "search_queries": guide_def.get("search_queries", []),
        "agent_relevance": guide_def.get("agent_relevance", []),
        "source_books": book_titles,
        "source_chunk_count": len(chunks),
        "synthesized_at": datetime.now(UTC).isoformat(),
    }
    return guide


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(
    slug: str | None,
    dry_run: bool,
    list_only: bool,
    force: bool,
) -> None:
    if list_only:
        print("Available guide slugs:")
        for entry in GUIDE_CATALOG:
            agents = ", ".join(entry["agent_relevance"])
            print(f"  {entry['slug']:<35} [{agents}]")
        return

    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    qdrant_url = os.environ.get("QDRANT_URL", "").strip()
    qdrant_path = os.environ.get("QDRANT_PATH", "").strip()

    if not openai_api_key and not dry_run:
        logger.error("OPENAI_API_KEY is required (set it in your environment).")
        sys.exit(1)
    if not qdrant_url and not qdrant_path and not dry_run:
        logger.error("Set QDRANT_URL or QDRANT_PATH (run build_knowledge_base_books.py first).")
        sys.exit(1)

    # Initialise clients.
    try:
        import openai  # noqa: PLC0415
        from qdrant_client import AsyncQdrantClient  # noqa: PLC0415
    except ImportError as exc:
        logger.error("Missing dependency: %s — run `uv sync`", exc)
        sys.exit(1)

    openai_client = openai.AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None
    qdrant_client = None
    if qdrant_url:
        qdrant_client = AsyncQdrantClient(url=qdrant_url)
    elif qdrant_path:
        qdrant_client = AsyncQdrantClient(path=qdrant_path)

    GUIDES_DIR.mkdir(parents=True, exist_ok=True)

    # Determine which guides to process.
    if slug:
        catalog = [e for e in GUIDE_CATALOG if e["slug"] == slug]
        if not catalog:
            slugs = [e["slug"] for e in GUIDE_CATALOG]
            logger.error("Slug '%s' not in catalog. Available: %s", slug, slugs)
            sys.exit(1)
    else:
        catalog = GUIDE_CATALOG

    logger.info(
        "Processing %d guide(s) — dry_run=%s force=%s", len(catalog), dry_run, force
    )

    success = 0
    skipped = 0
    failed = 0

    for guide_def in catalog:
        out_path = GUIDES_DIR / f"{guide_def['slug']}.json"

        if out_path.exists() and not force and not dry_run:
            logger.info("  SKIP: %s already exists (use --force to overwrite)", guide_def["slug"])
            skipped += 1
            continue

        guide = await synthesize_guide(
            guide_def, qdrant_client, openai_client, dry_run=dry_run
        )

        if dry_run:
            continue

        if guide is None:
            failed += 1
            continue

        out_path.write_text(json.dumps(guide, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("  SAVED: %s (%d chunks)", out_path.name, guide.get("source_chunk_count", 0))
        success += 1

    if not dry_run:
        logger.info(
            "Done — %d synthesized, %d skipped (already exist), %d failed.",
            success, skipped, failed,
        )
        if failed > 0:
            logger.warning(
                "%d guide(s) failed — check Qdrant has book chunks "
                "(run build_knowledge_base_books.py if not).",
                failed,
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthesize domain knowledge guides from Qdrant book chunks."
    )
    parser.add_argument(
        "--slug",
        metavar="SLUG",
        help="Synthesize only this guide slug (e.g. digital_awareness_campaign).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which chunks would be retrieved without calling GPT-4o.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List all available guide slugs and exit.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing guide files (default: skip if already exists).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(
        slug=args.slug,
        dry_run=args.dry_run,
        list_only=args.list_only,
        force=args.force,
    ))
