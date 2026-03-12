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
    "professional_services": ["consulting", "legal", "hr", "professional services", "advisory"],
    "edtech": ["education", "edtech", "learning", "training", "skillsfuture"],
    "ict_saas": ["software", "saas", "tech", "cloud", "cybersecurity", "ai", "data"],
}


def detect_vertical_slug(text: str) -> str | None:
    """Map free-text industry/task description to one of 12 KB vertical slugs.

    Returns the first matching slug, or None when no keyword match is found.
    Slugs map to rows in the vertical_seeds table (fintech, ict_saas, etc.).
    """
    text_lower = text.lower()
    for slug, keywords in _VERTICAL_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return slug
    return None
