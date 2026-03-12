"""Deterministic article classification pipeline — no LLM required.

Three classifiers run purely on keyword matching:
  - Vertical classification (12 Singapore industry verticals)
  - Signal type classification (funding, partnership, expansion, etc.)
  - Sentiment classification (positive / negative / neutral)

All keyword matching uses whole-word boundaries (``re`` word-boundary anchors) to
prevent false positives such as 'ai' matching inside 'gain', 'port' matching inside
'reported', or 'api' matching inside 'capital'.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from packages.database.src.vertical_seeds import VERTICAL_SEEDS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword matching helper
# ---------------------------------------------------------------------------


def _make_pattern(keyword: str) -> re.Pattern[str]:
    """Return a compiled whole-word regex pattern for *keyword*.

    Multi-word phrases (e.g. 'real estate') are anchored with ``\\b`` at each
    end so they don't spuriously match inside a longer token.  The pattern is
    case-insensitive but callers always pass lower-cased text for speed.
    """
    escaped = re.escape(keyword)
    return re.compile(r"\b" + escaped + r"\b")


def _kw_matches(pattern: re.Pattern[str], text: str) -> bool:
    """Return True when *pattern* has a whole-word match in *text*."""
    return pattern.search(text) is not None


# ---------------------------------------------------------------------------
# Keyword tables built once at import time
# ---------------------------------------------------------------------------

# Map slug → list of compiled whole-word patterns
_VERTICAL_PATTERNS: dict[str, list[re.Pattern[str]]] = {}
for _seed in VERTICAL_SEEDS:
    _slug = _seed["slug"]
    _kws: list[str] = [k.lower() for k in _seed["keywords"]]
    # Also add individual words from the vertical name so we pick up plain matches.
    # Only words longer than 4 characters are added to reduce generic noise.
    # This threshold excludes common short tokens ('real', 'tech', 'saas', 'mro',
    # 'pcb') that are too broad even with word boundaries, while still capturing
    # descriptive words like 'fintech', 'biomedical', 'logistics', 'maritime', etc.
    # The explicit seed keywords list covers any short domain terms individually.
    for _word in _seed["name"].lower().split():
        _cleaned = _word.strip("/()")
        if len(_cleaned) > 4 and _cleaned not in _kws:
            _kws.append(_cleaned)
    _VERTICAL_PATTERNS[_slug] = [_make_pattern(kw) for kw in _kws]

# Keep the raw keyword strings for backward-compatibility (used in tests).
_VERTICAL_KEYWORDS: dict[str, list[str]] = {
    slug: [p.pattern.strip(r"\b").replace(r"\b", "").replace("\\", "") for p in patterns]
    for slug, patterns in _VERTICAL_PATTERNS.items()
}

_SIGNAL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    signal_type: [_make_pattern(kw) for kw in keywords]
    for signal_type, keywords in {
        "funding": [
            "raised",
            "series a",
            "series b",
            "series c",
            "funding",
            "investment",
            "venture",
            "seed round",
            "pre-series",
        ],
        "partnership": [
            "partnership",
            "collaboration",
            "joint venture",
            "mou",
            "memorandum",
            "agreement",
            "alliance",
        ],
        "expansion": [
            "expansion",
            "new market",
            "new office",
            "launches",
            "launch",
            "opens",
            "entering",
            "southeast asia",
        ],
        "ipo": [
            "ipo",
            "initial public offering",
            "listing",
            "listed on",
            "sgx listing",
            "stock exchange",
        ],
        "acquisition": [
            "acquires",
            "acquisition",
            "takeover",
            "merger",
            "buys",
            "purchased",
            "acquired",
        ],
        "regulation": [
            "regulation",
            "regulatory",
            "mas",
            "compliance",
            "license",
            "licenced",
            "approval",
            "policy",
        ],
        "leadership": [
            "appointed",
            "ceo",
            "cfo",
            "cto",
            "chairman",
            "resigns",
            "resignation",
            "new chief",
            "board",
        ],
        "product": [
            "product launch",
            "new feature",
            "releases",
            "update",
            "version",
            "platform",
            "solution",
        ],
        "market_trend": [
            "market share",
            "growth",
            "demand",
            "trend",
            "opportunity",
            "report",
            "forecast",
            "outlook",
        ],
    }.items()
}

_POSITIVE_PATTERNS: list[re.Pattern[str]] = [
    _make_pattern(w)
    for w in [
        "growth",
        "record",
        "profit",
        "strong",
        "innovative",
        "award",
        "leading",
        "expand",
        "success",
        "positive",
        "beat",
        "exceeded",
        "partnership",
        "launch",
        "milestone",
    ]
]
_NEGATIVE_PATTERNS: list[re.Pattern[str]] = [
    _make_pattern(w)
    for w in [
        "loss",
        "decline",
        "risk",
        "lawsuit",
        "fail",
        "layoff",
        "restructur",
        "downgrad",
        "concern",
        "weak",
        "miss",
        "below",
        "closure",
        "fraud",
    ]
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    vertical_slug: str | None
    signal_type: str | None
    sentiment: str  # always "positive", "negative", or "neutral"


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class ArticleClassifier:
    """Deterministic article classifier — no database access, no LLM calls."""

    def classify(self, title: str, summary: str | None) -> ClassificationResult:
        """Classify a single article by title and optional summary.

        Args:
            title: Article headline.
            summary: Short article summary or body extract.

        Returns:
            :class:`ClassificationResult` with vertical, signal type, and sentiment.
        """
        text = (title + " " + (summary or "")).lower()

        vertical_slug = self._classify_vertical(text)
        signal_type = self._classify_signal(text)
        sentiment = self._classify_sentiment(text)

        return ClassificationResult(
            vertical_slug=vertical_slug,
            signal_type=signal_type,
            sentiment=sentiment,
        )

    def classify_batch(
        self,
        articles: list[tuple[str, str | None]],
    ) -> list[ClassificationResult]:
        """Classify a list of (title, summary) pairs.

        Args:
            articles: List of ``(title, summary)`` tuples.

        Returns:
            One :class:`ClassificationResult` per input, in the same order.
        """
        return [self.classify(title, summary) for title, summary in articles]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_vertical(self, text: str) -> str | None:
        best_slug: str | None = None
        best_count = 0
        for slug, patterns in _VERTICAL_PATTERNS.items():
            count = sum(1 for p in patterns if _kw_matches(p, text))
            if count > best_count:
                best_count = count
                best_slug = slug
        return best_slug if best_count >= 1 else None

    def _classify_signal(self, text: str) -> str | None:
        for signal_type, patterns in _SIGNAL_PATTERNS.items():
            if any(_kw_matches(p, text) for p in patterns):
                return signal_type
        return None

    def _classify_sentiment(self, text: str) -> str:
        pos = sum(1 for p in _POSITIVE_PATTERNS if _kw_matches(p, text))
        neg = sum(1 for p in _NEGATIVE_PATTERNS if _kw_matches(p, text))
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"
