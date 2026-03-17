"""Vertical Ecosystem Registry — standardised industry context for every vertical.

Each vertical can define its ecosystem: associations, publications, awards bodies,
regulators, events/conferences, key influencers, RSS feeds, social accounts, and
research firms. This data feeds into:

1. VerticalIntelligenceSynthesizer — enriches deterministic reports
2. VerticalIntelligenceAgent — injects ecosystem context into LLM prompts
3. Signal Monitor — knows which sources matter per vertical
4. Intel gathering scripts — vertical-specific Perplexity queries

Ecosystem definitions live in data/intel/{slug}/_ecosystem.json (generated or
hand-curated). This module loads, validates, and provides typed access.

To add a new vertical ecosystem:
1. Create data/intel/{slug}/_ecosystem.json following ECOSYSTEM_SCHEMA
2. Optionally register vertical-specific RSS feeds in VERTICAL_RSS_FEEDS
3. Run: uv run python scripts/intel_vertical.py --vertical {slug}

The framework is designed so that verticals WITHOUT an ecosystem file still work —
the synthesizer and agent fall back to generic analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Root of the project (packages/intelligence/src/vertical_ecosystem.py → 3 levels up)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_INTEL_DIR = _PROJECT_ROOT / "data" / "intel"


# ---------------------------------------------------------------------------
# Data classes — typed ecosystem components
# ---------------------------------------------------------------------------

@dataclass
class EcosystemOrganization:
    """An industry body, publication, regulator, or research firm."""
    name: str
    abbr: str = ""
    website: str = ""
    description: str = ""
    sg_relevance: str = "medium"  # critical / high / medium / low
    sg_notes: str = ""
    category: str = ""  # e.g. "association", "publication", "awards", "regulator"


@dataclass
class EcosystemEvent:
    """A recurring industry conference, awards show, or summit."""
    name: str
    frequency: str = "annual"  # annual / biannual / quarterly / monthly
    typical_month: str = ""  # e.g. "June", "Q1"
    location: str = ""
    website: str = ""
    description: str = ""
    sg_relevance: str = "medium"


@dataclass
class EcosystemRSSFeed:
    """An RSS feed relevant to a specific vertical."""
    url: str
    name: str
    category: str = "industry_news"  # industry_news / trade_publication / regulator / blog
    priority: str = "medium"  # high / medium / low


@dataclass
class EcosystemInfluencer:
    """A key thought leader or influencer in the vertical."""
    name: str
    title: str = ""
    organization: str = ""
    platforms: list[str] = field(default_factory=list)  # ["linkedin", "twitter", "substack"]
    sg_relevance: str = "medium"
    notes: str = ""


@dataclass
class VerticalEcosystem:
    """Complete ecosystem definition for a market vertical.

    This is the canonical structure. Every vertical CAN define all sections,
    but none are required — missing sections return empty lists.
    """
    vertical_slug: str
    vertical_name: str = ""
    generated_at: str = ""

    # Core ecosystem components
    associations: list[EcosystemOrganization] = field(default_factory=list)
    publications: list[EcosystemOrganization] = field(default_factory=list)
    awards_bodies: list[EcosystemOrganization] = field(default_factory=list)
    research_firms: list[EcosystemOrganization] = field(default_factory=list)
    regulators: list[EcosystemOrganization] = field(default_factory=list)
    certification_bodies: list[EcosystemOrganization] = field(default_factory=list)

    # Dynamic intelligence sources
    events: list[EcosystemEvent] = field(default_factory=list)
    rss_feeds: list[EcosystemRSSFeed] = field(default_factory=list)
    influencers: list[EcosystemInfluencer] = field(default_factory=list)

    # Quick-reference summary (for LLM injection)
    sg_summary: dict[str, Any] = field(default_factory=dict)

    # Perplexity research prompts — vertical-specific angles to query
    # These supplement the generic company research prompts
    research_angles: list[str] = field(default_factory=list)

    @property
    def all_organizations(self) -> list[EcosystemOrganization]:
        """All organizations across all categories."""
        return (
            self.associations
            + self.publications
            + self.awards_bodies
            + self.research_firms
            + self.regulators
            + self.certification_bodies
        )

    @property
    def critical_sg_orgs(self) -> list[EcosystemOrganization]:
        """Organizations with critical Singapore relevance."""
        return [o for o in self.all_organizations if o.sg_relevance == "critical"]

    @property
    def high_priority_feeds(self) -> list[EcosystemRSSFeed]:
        """RSS feeds marked as high priority."""
        return [f for f in self.rss_feeds if f.priority == "high"]

    def get_upcoming_events(self, month: str | None = None) -> list[EcosystemEvent]:
        """Events in or near a given month."""
        if not month:
            return self.events
        return [e for e in self.events if month.lower() in e.typical_month.lower()]

    def format_for_llm(self, *, max_orgs: int = 15, include_feeds: bool = False) -> str:
        """Format ecosystem context for LLM prompt injection.

        Produces a compact text block suitable for inclusion in agent prompts.
        Prioritizes critical/high relevance organizations.
        """
        lines: list[str] = []
        lines.append(f"## Industry Ecosystem: {self.vertical_name or self.vertical_slug}")

        # Sort by relevance: critical > high > medium > low
        relevance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        if self.associations:
            lines.append("\n### Key Industry Bodies")
            sorted_assocs = sorted(self.associations, key=lambda o: relevance_order.get(o.sg_relevance, 3))
            for org in sorted_assocs[:max_orgs]:
                abbr = f" ({org.abbr})" if org.abbr else ""
                rel = f" [{org.sg_relevance.upper()}]" if org.sg_relevance in ("critical", "high") else ""
                lines.append(f"- {org.name}{abbr}{rel}: {org.description[:120]}")

        if self.publications:
            lines.append("\n### Trade Publications")
            sorted_pubs = sorted(self.publications, key=lambda o: relevance_order.get(o.sg_relevance, 3))
            for pub in sorted_pubs[:8]:
                lines.append(f"- {pub.name}: {pub.description[:100]}")

        if self.awards_bodies:
            lines.append("\n### Awards & Recognition")
            sorted_awards = sorted(self.awards_bodies, key=lambda o: relevance_order.get(o.sg_relevance, 3))
            for aw in sorted_awards[:8]:
                lines.append(f"- {aw.name}: {aw.description[:100]}")

        if self.regulators:
            lines.append("\n### Regulatory Bodies")
            for reg in self.regulators:
                lines.append(f"- {reg.name} ({reg.abbr}): {reg.description[:100]}")

        if self.events:
            lines.append("\n### Key Events & Conferences")
            for ev in self.events:
                loc = f" ({ev.location})" if ev.location else ""
                lines.append(f"- {ev.name}{loc}, {ev.frequency}: {ev.description[:80]}")

        if self.research_firms:
            lines.append("\n### Research & Data Providers")
            for rf in self.research_firms[:6]:
                lines.append(f"- {rf.name}: {rf.description[:80]}")

        if include_feeds and self.rss_feeds:
            lines.append("\n### Monitored RSS Feeds")
            for feed in self.high_priority_feeds:
                lines.append(f"- {feed.name} ({feed.category})")

        if self.sg_summary:
            lines.append("\n### Singapore Quick Reference")
            for k, v in self.sg_summary.items():
                if isinstance(v, list):
                    lines.append(f"- {k}: {', '.join(str(i) for i in v)}")
                else:
                    lines.append(f"- {k}: {v}")

        return "\n".join(lines)

    def get_research_angles(self) -> list[str]:
        """Return vertical-specific research angles for Perplexity queries.

        These are appended to the standard company research prompts to capture
        vertical-specific intelligence (events, awards, publications, etc.).
        """
        if self.research_angles:
            return self.research_angles

        # Auto-generate from ecosystem data
        angles: list[str] = []

        if self.awards_bodies:
            award_names = ", ".join(a.name for a in self.awards_bodies[:5])
            angles.append(
                f"Recent awards and recognition: {award_names}. "
                "List any wins, shortlists, or jury memberships in the last 2 years."
            )

        if self.events:
            event_names = ", ".join(e.name for e in self.events[:5])
            angles.append(
                f"Conference and event participation: {event_names}. "
                "Speaking engagements, sponsorships, or booth presence in the last year."
            )

        if self.associations:
            assoc_names = ", ".join(a.abbr or a.name for a in self.associations[:5])
            angles.append(
                f"Industry body membership and leadership: {assoc_names}. "
                "Board positions, committee roles, or published contributions."
            )

        if self.publications:
            pub_names = ", ".join(p.name for p in self.publications[:5])
            angles.append(
                f"Thought leadership and media coverage in: {pub_names}. "
                "Published articles, interviews, op-eds, or case studies."
            )

        return angles


# ---------------------------------------------------------------------------
# Loading & parsing
# ---------------------------------------------------------------------------

def _parse_org_list(items: list[dict], category: str) -> list[EcosystemOrganization]:
    """Parse a list of organization dicts into typed objects."""
    return [
        EcosystemOrganization(
            name=item.get("name", ""),
            abbr=item.get("abbr", ""),
            website=item.get("website", ""),
            description=item.get("description", ""),
            sg_relevance=item.get("sg_relevance", "medium"),
            sg_notes=item.get("sg_notes", ""),
            category=category,
        )
        for item in items
    ]


def _parse_events(items: list[dict]) -> list[EcosystemEvent]:
    """Parse event dicts."""
    return [
        EcosystemEvent(
            name=item.get("name", ""),
            frequency=item.get("frequency", "annual"),
            typical_month=item.get("typical_month", ""),
            location=item.get("location", ""),
            website=item.get("website", ""),
            description=item.get("description", ""),
            sg_relevance=item.get("sg_relevance", "medium"),
        )
        for item in items
    ]


def _parse_feeds(items: list[dict]) -> list[EcosystemRSSFeed]:
    """Parse RSS feed dicts."""
    return [
        EcosystemRSSFeed(
            url=item.get("url", ""),
            name=item.get("name", ""),
            category=item.get("category", "industry_news"),
            priority=item.get("priority", "medium"),
        )
        for item in items
    ]


def _parse_influencers(items: list[dict]) -> list[EcosystemInfluencer]:
    """Parse influencer dicts."""
    return [
        EcosystemInfluencer(
            name=item.get("name", ""),
            title=item.get("title", ""),
            organization=item.get("organization", ""),
            platforms=item.get("platforms", []),
            sg_relevance=item.get("sg_relevance", "medium"),
            notes=item.get("notes", ""),
        )
        for item in items
    ]


def load_vertical_ecosystem(slug: str) -> VerticalEcosystem | None:
    """Load a vertical's ecosystem definition from data/intel/{slug}/_ecosystem.json.

    Returns None if the file doesn't exist (vertical has no ecosystem defined yet).
    This is expected for newly created verticals — the pipeline still works without it.
    """
    # Try new canonical path first, then legacy path
    ecosystem_path = _INTEL_DIR / slug / "_ecosystem.json"
    if not ecosystem_path.exists():
        # Legacy: _industry_ecosystem.json
        legacy_path = _INTEL_DIR / slug / "_industry_ecosystem.json"
        if legacy_path.exists():
            ecosystem_path = legacy_path
        else:
            logger.debug("No ecosystem file for vertical %s", slug)
            return None

    try:
        data = json.loads(ecosystem_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load ecosystem for %s: %s", slug, e)
        return None

    # Map JSON keys to ecosystem sections
    # Supports both the new canonical keys and the legacy _industry_ecosystem.json keys
    return VerticalEcosystem(
        vertical_slug=data.get("vertical_slug", slug),
        vertical_name=data.get("vertical_name", data.get("description", "")),
        generated_at=data.get("generated_at", ""),

        associations=_parse_org_list(
            data.get("associations", [])
            + data.get("global_industry_associations", [])
            + data.get("singapore_apac_associations", []),
            "association",
        ),
        publications=_parse_org_list(
            data.get("publications", [])
            + data.get("trade_publications", []),
            "publication",
        ),
        awards_bodies=_parse_org_list(
            data.get("awards_bodies", []),
            "awards",
        ),
        research_firms=_parse_org_list(
            data.get("research_firms", [])
            + data.get("research_data_organizations", []),
            "research",
        ),
        regulators=_parse_org_list(
            data.get("regulators", [])
            + data.get("regulatory_bodies_singapore", [])
            + data.get("international_regulatory_bodies", []),
            "regulator",
        ),
        certification_bodies=_parse_org_list(
            data.get("certification_bodies", [])
            + data.get("professional_certification_bodies", []),
            "certification",
        ),

        events=_parse_events(data.get("events", [])),
        rss_feeds=_parse_feeds(data.get("rss_feeds", [])),
        influencers=_parse_influencers(data.get("influencers", [])),

        sg_summary=data.get("key_sg_ecosystem_summary", data.get("sg_summary", {})),
        research_angles=data.get("research_angles", []),
    )


# ---------------------------------------------------------------------------
# Registry — cached ecosystem access
# ---------------------------------------------------------------------------

_ECOSYSTEM_CACHE: dict[str, VerticalEcosystem | None] = {}


def get_vertical_ecosystem(slug: str, *, force_reload: bool = False) -> VerticalEcosystem | None:
    """Get ecosystem for a vertical (cached).

    Returns None if no ecosystem file exists for this vertical.
    """
    if slug not in _ECOSYSTEM_CACHE or force_reload:
        _ECOSYSTEM_CACHE[slug] = load_vertical_ecosystem(slug)
    return _ECOSYSTEM_CACHE[slug]


def list_available_ecosystems() -> list[str]:
    """List all vertical slugs that have ecosystem definitions."""
    slugs: list[str] = []
    if not _INTEL_DIR.exists():
        return slugs
    for child in sorted(_INTEL_DIR.iterdir()):
        if not child.is_dir():
            continue
        if (child / "_ecosystem.json").exists() or (child / "_industry_ecosystem.json").exists():
            slugs.append(child.name)
    return slugs


def clear_ecosystem_cache() -> None:
    """Clear the in-memory ecosystem cache."""
    _ECOSYSTEM_CACHE.clear()


# ---------------------------------------------------------------------------
# Vertical-specific RSS feeds (static registry)
# ---------------------------------------------------------------------------

VERTICAL_RSS_FEEDS: dict[str, list[dict[str, str]]] = {
    "marketing_comms": [
        {"url": "https://www.campaignasia.com/rss", "name": "Campaign Asia-Pacific", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.marketing-interactive.com/rss.xml", "name": "Marketing-Interactive", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.thedrum.com/feeds/all.rss", "name": "The Drum", "category": "trade_publication", "priority": "medium"},
        {"url": "https://adage.com/arc/outboundfeeds/rss/", "name": "Ad Age", "category": "trade_publication", "priority": "medium"},
        {"url": "https://www.adweek.com/feed/", "name": "Adweek", "category": "trade_publication", "priority": "medium"},
        {"url": "https://feeds.feedburner.com/Mumbrella", "name": "Mumbrella Asia", "category": "trade_publication", "priority": "medium"},
    ],
    "fintech": [
        {"url": "https://fintechnews.sg/feed/", "name": "Fintech News Singapore", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.finextra.com/rss/headlines.aspx", "name": "Finextra", "category": "trade_publication", "priority": "medium"},
        {"url": "https://www.pymnts.com/feed/", "name": "PYMNTS", "category": "trade_publication", "priority": "medium"},
    ],
    "biomedical": [
        {"url": "https://www.fiercebiotech.com/rss.xml", "name": "Fierce Biotech", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.biopharmadive.com/feeds/news/", "name": "BioPharma Dive", "category": "trade_publication", "priority": "medium"},
    ],
    "ict_saas": [
        {"url": "https://techcrunch.com/feed/", "name": "TechCrunch", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.techinasia.com/feed", "name": "Tech in Asia", "category": "trade_publication", "priority": "high"},
    ],
    "maritime": [
        {"url": "https://splash247.com/feed/", "name": "Splash 247", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.seatrade-maritime.com/rss.xml", "name": "Seatrade Maritime", "category": "trade_publication", "priority": "medium"},
    ],
    "clean_energy": [
        {"url": "https://cleantechnica.com/feed/", "name": "CleanTechnica", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.greentechmedia.com/feed", "name": "GreenTech Media", "category": "trade_publication", "priority": "medium"},
    ],
    "logistics": [
        {"url": "https://www.supplychaindive.com/feeds/news/", "name": "Supply Chain Dive", "category": "trade_publication", "priority": "high"},
        {"url": "https://theloadstar.com/feed/", "name": "The Loadstar", "category": "trade_publication", "priority": "medium"},
    ],
    "retail_ecommerce": [
        {"url": "https://www.retaildive.com/feeds/news/", "name": "Retail Dive", "category": "trade_publication", "priority": "high"},
        {"url": "https://www.modernretail.co/feed/", "name": "Modern Retail", "category": "trade_publication", "priority": "medium"},
    ],
}


# ---------------------------------------------------------------------------
# Vertical-specific Perplexity research angles (static fallback)
# ---------------------------------------------------------------------------

VERTICAL_RESEARCH_ANGLES: dict[str, list[str]] = {
    "marketing_comms": [
        "Recent advertising and marketing awards: Cannes Lions, Effies, Spikes Asia, Campaign AOY, Marketing-Interactive AOY. Wins, shortlists, jury roles in last 2 years.",
        "Conference participation: Spikes Asia, ADFEST, Campaign360, Advertising Week, CES, SXSW. Speaking, sponsoring, or attending in last year.",
        "Industry body roles: AAMS, SAA, IPRS, MIS, IAB SEA+India, PRCA APAC. Board positions, committee leadership, published papers.",
        "Thought leadership: articles in Campaign Asia, Marketing-Interactive, The Drum, Ad Age, Adweek, Mumbrella, PRWeek Asia. Op-eds, research reports, podcast appearances.",
        "Social media thought leadership: LinkedIn posts by company leaders, viral campaign posts, industry commentary on Instagram/Twitter/TikTok.",
    ],
    "fintech": [
        "Regulatory milestones: MAS licences (MPI, DPT, CMS), sandbox approvals, compliance certifications in last 2 years.",
        "Fintech awards: SFF Innovation Lab, MAS FinTech Awards, Singapore FinTech Festival participation, Global Fintech Awards.",
        "Industry body roles: Singapore FinTech Association (SFA), Payments Council, ASIFMA, AICPA. Board, committee, working group participation.",
        "Thought leadership: articles in The Banker, Finextra, PYMNTS, Fintech News SG. Research papers, conference keynotes.",
    ],
    "biomedical": [
        "Clinical milestones: FDA/HSA approvals, clinical trial results, CE marking, WHO prequalification in last 2 years.",
        "Research publications: Nature, The Lancet, BMJ, peer-reviewed journals. Patent filings, R&D collaborations.",
        "Industry events: BIO International, MEDICA, Asia Health, Singapore Biodesign. Speaking, exhibiting, partnerships announced.",
    ],
    "ict_saas": [
        "Product launches: new features, platform releases, API announcements, integrations in last year.",
        "Industry recognition: Gartner Magic Quadrant, Forrester Wave, G2 rankings, Product Hunt launches.",
        "Developer community: GitHub stars, open-source contributions, developer conferences (AWS re:Invent, Google I/O, STACK by GovTech).",
    ],
    "maritime": [
        "Fleet and vessel developments: new builds, acquisitions, scrapping, charter rates in last year.",
        "Regulatory: IMO regulations, MPA Singapore directives, green shipping corridor participation.",
        "Industry events: Singapore Maritime Week, Posidonia, Nor-Shipping. Speaking, sponsoring, exhibition presence.",
    ],
}


# ---------------------------------------------------------------------------
# Ecosystem schema documentation (for generating new ecosystems)
# ---------------------------------------------------------------------------

ECOSYSTEM_SCHEMA_TEMPLATE: dict[str, Any] = {
    "vertical_slug": "{slug}",
    "vertical_name": "{human-readable vertical name}",
    "generated_at": "{YYYY-MM-DD}",
    "description": "Industry ecosystem reference for {vertical_name}.",

    "associations": [
        {
            "name": "Example Association",
            "abbr": "EA",
            "website": "https://example.org",
            "description": "What this body does.",
            "sg_relevance": "high",  # critical / high / medium / low
            "sg_notes": "Singapore-specific context.",
        },
    ],
    "publications": [],
    "awards_bodies": [],
    "research_firms": [],
    "regulators": [],
    "certification_bodies": [],

    "events": [
        {
            "name": "Example Conference",
            "frequency": "annual",
            "typical_month": "June",
            "location": "Singapore",
            "website": "https://example.com",
            "description": "Premier industry gathering.",
            "sg_relevance": "high",
        },
    ],

    "rss_feeds": [
        {
            "url": "https://example.com/feed",
            "name": "Example Publication",
            "category": "trade_publication",  # industry_news / trade_publication / regulator / blog
            "priority": "high",  # high / medium / low
        },
    ],

    "influencers": [
        {
            "name": "Jane Doe",
            "title": "CEO",
            "organization": "Example Agency",
            "platforms": ["linkedin", "twitter"],
            "sg_relevance": "high",
            "notes": "Frequent speaker at industry events.",
        },
    ],

    "research_angles": [
        "Vertical-specific Perplexity query angle 1.",
        "Vertical-specific Perplexity query angle 2.",
    ],

    "sg_summary": {
        "primary_trade_body": "Name (description)",
        "key_regulator": "Name",
        "premier_award": "Name",
        "key_publications": ["Pub 1", "Pub 2"],
    },
}
