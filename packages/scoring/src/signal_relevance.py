"""Signal Relevance Scorer — deterministic scoring of market signals.

Given a raw signal event (from Perplexity/NewsAPI/EODHD) and a client context,
scores how relevant and actionable the signal is for THIS client.

This is NOT an LLM deciding if something is interesting.
It's a deterministic weighted scoring model using:
- Industry match (does the signal affect this client's sector?)
- Competitor mention (is a tracked competitor named?)
- Regulatory impact (does this affect Singapore SME compliance?)
- Market opportunity (does this create a buying trigger?)
- Signal recency (fresher signals score higher)
- Trigger quality (funding > hiring > product launch > general news)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Signal type taxonomy
SIGNAL_TYPES = {
    "funding": 1.0,           # Competitor/market funding — high action potential
    "acquisition": 0.9,        # M&A activity — displacement opportunity
    "product_launch": 0.8,     # Competitor product launch — counter messaging
    "regulation": 0.85,        # Regulatory change — compliance-driven buying
    "expansion": 0.75,         # Market expansion — new territory opportunity
    "hiring": 0.65,            # Hiring signals — growth = budget available
    "layoff": 0.50,            # Industry layoffs — budget squeeze, but pain visible
    "partnership": 0.70,       # Partnership announcement — ecosystem signal
    "market_trend": 0.55,      # General trend — awareness, not immediate action
    "general_news": 0.30,      # Background noise
}

# Recommended actions per signal type
SIGNAL_ACTIONS = {
    "funding": "Accelerate outreach — competitor gaining resources, act now",
    "acquisition": "Deploy Competitor Displacement playbook immediately",
    "product_launch": "Update competitive messaging; outreach with comparison angle",
    "regulation": "Deploy PSG Grant / Compliance playbook — regulatory buying trigger",
    "expansion": "Identify leads in new markets; market entry play",
    "hiring": "Target companies hiring in your ICP roles — budget signal",
    "layoff": "Nurture play — empathy-first messaging, cost/efficiency angle",
    "partnership": "Research ecosystem fit; joint opportunity framing",
    "market_trend": "Use in content marketing; educational outreach angle",
    "general_news": "Monitor for follow-on signals",
}


@dataclass
class ScoredSignal:
    """A market signal scored for a specific client context."""
    signal_text: str
    signal_type: str
    relevance_score: float  # 0-1
    urgency: str  # "immediate", "this_week", "this_month", "monitor"
    recommended_action: str
    reasoning: list[str] = field(default_factory=list)
    competitors_mentioned: list[str] = field(default_factory=list)
    industries_affected: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_text": self.signal_text,
            "signal_type": self.signal_type,
            "relevance_score": round(self.relevance_score, 3),
            "urgency": self.urgency,
            "recommended_action": self.recommended_action,
            "reasoning": self.reasoning,
            "competitors_mentioned": self.competitors_mentioned,
            "industries_affected": self.industries_affected,
            "source": self.source,
        }


class SignalRelevanceScorer:
    """Scores market signals for relevance to a specific client.

    Deterministic weighted scoring — same input, same output.
    No LLM in the scoring path.

    Scoring components:
        industry_match    (0.30) — signal affects client's industry
        competitor_match  (0.25) — signal mentions tracked competitor
        trigger_quality   (0.25) — type of signal (funding > hiring > general)
        recency           (0.20) — how fresh is the signal
    """

    def score(
        self,
        signal_text: str,
        signal_type: str,
        signal_published_at: datetime,
        client_industry: str,
        client_competitors: list[str],
        _client_target_segments: list[str] | None = None,
        source: str = "",
    ) -> ScoredSignal:
        """Score a signal for relevance to a specific client.

        Args:
            signal_text: The raw signal headline/content
            signal_type: Type from SIGNAL_TYPES taxonomy
            signal_published_at: When the signal was published
            client_industry: Client's industry
            client_competitors: List of tracked competitor names
            client_target_segments: Optional target customer segments
            source: Data source (e.g., "NewsAPI", "Perplexity", "EODHD")

        Returns:
            ScoredSignal with relevance score and recommended action
        """
        reasoning: list[str] = []
        components: dict[str, float] = {}
        signal_lower = signal_text.lower()
        competitors_mentioned: list[str] = []
        industries_affected: list[str] = []

        # 1. Trigger quality (signal type score)
        type_score = SIGNAL_TYPES.get(signal_type.lower(), 0.30)
        components["trigger_quality"] = type_score * 0.25
        reasoning.append(f"Signal type '{signal_type}' — base relevance {type_score:.0%}")

        # 2. Industry match
        industry_lower = client_industry.lower()
        industry_keywords = self._expand_industry_keywords(industry_lower)
        industry_matches = sum(1 for kw in industry_keywords if kw in signal_lower)
        if industry_matches >= 2:
            components["industry_match"] = 0.30
            reasoning.append(f"Strong industry match ({industry_matches} keywords matched)")
            industries_affected.append(client_industry)
        elif industry_matches == 1:
            components["industry_match"] = 0.15
            reasoning.append("Partial industry match")
            industries_affected.append(client_industry)
        else:
            components["industry_match"] = 0.0

        # 3. Competitor mention (highest value signal)
        for competitor in client_competitors:
            comp_lower = competitor.lower()
            # Match on full name or significant partial (≥4 chars)
            if comp_lower in signal_lower or (len(comp_lower) >= 4 and comp_lower[:6] in signal_lower):
                competitors_mentioned.append(competitor)
        if competitors_mentioned:
            components["competitor_match"] = 0.25
            reasoning.append(f"Competitor mentioned: {', '.join(competitors_mentioned)}")
        else:
            components["competitor_match"] = 0.0

        # 4. Recency score
        age_hours = (datetime.now(UTC) - signal_published_at).total_seconds() / 3600
        if age_hours <= 24:
            recency_score = 1.0
            reasoning.append("Fresh signal (< 24 hours)")
        elif age_hours <= 72:
            recency_score = 0.75
        elif age_hours <= 168:  # 1 week
            recency_score = 0.50
        else:
            recency_score = 0.25
        components["recency"] = recency_score * 0.20

        # 5. Singapore/APAC bonus (context-specific)
        sg_keywords = ["singapore", "apac", "sea", "southeast asia", "asean", "mas ", "sme", "psg"]
        if any(kw in signal_lower for kw in sg_keywords):
            components["regional_bonus"] = 0.10
            reasoning.append("Singapore/APAC relevance detected")
        else:
            components["regional_bonus"] = 0.0

        total = sum(components.values())
        total = min(1.0, total)

        # Urgency classification
        if total >= 0.70 and type_score >= 0.75:
            urgency = "immediate"
        elif total >= 0.50:
            urgency = "this_week"
        elif total >= 0.30:
            urgency = "this_month"
        else:
            urgency = "monitor"

        recommended_action = SIGNAL_ACTIONS.get(signal_type.lower(), "Monitor for follow-on signals")

        return ScoredSignal(
            signal_text=signal_text,
            signal_type=signal_type,
            relevance_score=round(total, 3),
            urgency=urgency,
            recommended_action=recommended_action,
            reasoning=reasoning,
            competitors_mentioned=competitors_mentioned,
            industries_affected=industries_affected,
            source=source,
        )

    def _expand_industry_keywords(self, industry: str) -> list[str]:
        """Expand industry to related keywords for matching."""
        expansions: dict[str, list[str]] = {
            "fintech": ["fintech", "financial technology", "payments", "banking", "insurtech", "wealthtech", "mas", "monetary authority"],
            "saas": ["saas", "software", "cloud", "subscription", "platform", "api", "developer tools"],
            "logistics": ["logistics", "supply chain", "fulfillment", "warehouse", "shipping", "last mile", "freight"],
            "ecommerce": ["ecommerce", "e-commerce", "retail", "marketplace", "d2c", "direct to consumer"],
            "healthtech": ["healthtech", "health tech", "medtech", "telemedicine", "digital health", "healthcare"],
            "proptech": ["proptech", "property", "real estate", "reit", "construction tech"],
            "edtech": ["edtech", "education technology", "e-learning", "training", "skills"],
            "hrtech": ["hrtech", "hr tech", "hrms", "payroll", "talent", "recruiting", "workforce"],
        }
        keywords = [industry]
        for key, kws in expansions.items():
            if key in industry or industry in key:
                keywords.extend(kws)
        return list(set(keywords))
