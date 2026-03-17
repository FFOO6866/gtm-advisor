"""Shared vertical detection utility for Singapore market verticals."""

from __future__ import annotations

_VERTICAL_KEYWORDS: dict[str, list[str]] = {
    "fintech": ["fintech", "finance", "payment", "bank", "insurance", "wealth"],
    "biomedical": ["biomedical", "biotech", "pharma", "health", "medical", "diagnostic"],
    "advanced_manufacturing": ["manufacturing", "semiconductor", "aerospace", "precision"],
    "logistics": ["logistics", "supply chain", "shipping", "freight", "warehouse"],
    "retail_ecommerce": ["retail", "ecommerce", "e-commerce", "consumer", "marketplace"],
    "proptech": ["property", "real estate", "proptech", "construction", "building"],
    "reits": ["reit", "investment trust"],
    "clean_energy": ["energy", "solar", "green", "sustainability", "carbon"],
    "maritime": ["maritime", "shipping", "marine", "vessel", "offshore"],
    "marketing_comms": [
        "advertising", "creative agency", "public relations", "media agency",
        "communications", "branding", "marketing agency", "digital marketing",
        "media buying", "martech", "adtech", "out-of-home",
        "marketing_comms", "marketing comms",
        "go-to-market", "gtm", "marketing campaign", "lead generation",
        "outreach", "content marketing", "marketing platform",
    ],
    "professional_services": [
        "consulting", "legal", "human resources", "professional services",
        "professional_services", "advisory",
    ],
    "edtech": ["education", "edtech", "learning", "training", "skillsfuture"],
    "ict_saas": [
        "software", "saas", "tech", "cloud", "cybersecurity", "data",
        "artificial intelligence", "machine learning", "ict_saas", "ict saas",
    ],
}

# Slugs that are also valid inputs (exact match takes priority over substring scan)
_SLUG_SET = frozenset(_VERTICAL_KEYWORDS.keys())


def detect_vertical_slug(text: str) -> str | None:
    """Map free-text industry/task description to one of 13 KB vertical slugs.

    Returns the best matching slug, or None when no keyword match is found.
    Slugs map to rows in the vertical_seeds table (fintech, ict_saas, etc.).

    When the text is a bare slug (e.g. "marketing_comms"), returns it directly.
    When the text contains a slug PLUS additional context, scans for the most
    specific keyword match — so "professional_services marketing campaigns"
    correctly returns "marketing_comms" (more specific) rather than the
    generic "professional_services".
    """
    text_lower = text.strip().lower()

    # Fast path: input is ONLY a known slug with no additional context
    if text_lower in _SLUG_SET and " " not in text_lower.replace("_", ""):
        return text_lower

    # Normalise underscores to spaces for keyword matching
    text_normalised = text_lower.replace("_", " ")

    # Score each vertical by number of keyword hits — pick the most specific
    best_slug: str | None = None
    best_hits = 0
    for slug, keywords in _VERTICAL_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_normalised)
        if hits > best_hits:
            best_hits = hits
            best_slug = slug

    return best_slug
