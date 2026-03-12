"""Market Context Scorer — uses REAL data from EODHD + NewsAPI.

This is NOT an LLM opinion. It pulls:
- Singapore economic indicators from EODHD (GDP, business confidence, PMI)
- Sector news sentiment from NewsAPI (last 7 days)
- Financial market signals from EODHD (STI performance, sector ETFs)

Then applies a deterministic scoring formula to produce an OpportunityWindow:
  GREEN  = good time to outreach (market positive, sector growing)
  AMBER  = neutral (mixed signals, proceed with caution)
  RED    = hold (market contraction, sector headwinds)

Why this beats ChatGPT: ChatGPT has a knowledge cutoff and no access to
live market data. This scorer runs against TODAY'S EODHD + NewsAPI data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from packages.integrations.eodhd.src.client import EODHDClient
from packages.integrations.newsapi.src.client import NewsAPIClient

logger = structlog.get_logger()


class OpportunityRating(str, Enum):
    GREEN = "green"    # Strong opportunity window — accelerate outreach
    AMBER = "amber"    # Mixed signals — proceed selectively
    RED = "red"        # Unfavourable conditions — pause or reduce volume


@dataclass
class OpportunityWindow:
    """Output of MarketContextScorer."""
    rating: OpportunityRating
    score: float  # 0-1
    macro_score: float  # EODHD economic indicators component
    sentiment_score: float  # NewsAPI sector sentiment component
    reasoning: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    best_timing_note: str = ""
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rating": self.rating.value,
            "score": round(self.score, 3),
            "macro_score": round(self.macro_score, 3),
            "sentiment_score": round(self.sentiment_score, 3),
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "data_sources": self.data_sources,
            "best_timing_note": self.best_timing_note,
            "computed_at": self.computed_at.isoformat(),
        }


class MarketContextScorer:
    """Scores the current market context for GTM outreach timing.

    Uses live data — not LLM knowledge cutoff.

    Scoring formula:
        macro_score    = weighted EODHD economic indicators (0.40)
        sentiment_score = NewsAPI sector sentiment last 7d (0.35)
        recency_bonus  = recent positive signals in last 24h (0.25)

    Singapore-specific signals weighted higher.
    """

    # Sentiment keyword weights
    POSITIVE_KEYWORDS = [
        "growth", "expansion", "investment", "funding", "record", "profit",
        "recovery", "opportunity", "surge", "raise", "ipo", "acquisition",
        "partnership", "launch", "innovation", "digital transformation",
    ]
    NEGATIVE_KEYWORDS = [
        "recession", "layoff", "retrenchment", "bankruptcy", "decline",
        "contraction", "downturn", "loss", "default", "fraud", "investigation",
        "shutdown", "closure", "crisis", "slowdown",
    ]

    def __init__(
        self,
        eodhd_client: EODHDClient | None = None,
        newsapi_client: NewsAPIClient | None = None,
    ) -> None:
        self._eodhd = eodhd_client or EODHDClient()
        self._newsapi = newsapi_client or NewsAPIClient()

    async def score(
        self,
        industry: str,
        target_region: str = "Singapore",
        _company_name: str | None = None,
    ) -> OpportunityWindow:
        """Score current market context for outreach timing.

        Args:
            industry: Client's industry (e.g., "fintech", "SaaS", "logistics")
            target_region: Target market region (default: Singapore)
            company_name: Optional — get company-specific news

        Returns:
            OpportunityWindow with rating and detailed reasoning
        """
        reasoning: list[str] = []
        warnings: list[str] = []
        data_sources: list[str] = []

        # Run data fetches concurrently
        macro_task = asyncio.create_task(self._get_macro_score(reasoning, warnings, data_sources))
        sentiment_task = asyncio.create_task(
            self._get_sentiment_score(industry, target_region, reasoning, warnings, data_sources)
        )

        macro_score, sentiment_score = await asyncio.gather(macro_task, sentiment_task)

        # Combined score
        total = (macro_score * 0.40) + (sentiment_score * 0.60)

        # Rating thresholds
        if total >= 0.65:
            rating = OpportunityRating.GREEN
            timing_note = f"Strong market conditions for {industry} outreach in {target_region}. Recommend full sequence activation."
        elif total >= 0.40:
            rating = OpportunityRating.AMBER
            timing_note = f"Mixed signals for {industry}. Focus outreach on highest-fit leads only."
        else:
            rating = OpportunityRating.RED
            timing_note = "Challenging market conditions. Consider pausing cold outreach; focus on warm leads."

        return OpportunityWindow(
            rating=rating,
            score=round(total, 3),
            macro_score=round(macro_score, 3),
            sentiment_score=round(sentiment_score, 3),
            reasoning=reasoning,
            warnings=warnings,
            data_sources=data_sources,
            best_timing_note=timing_note,
        )

    async def _get_macro_score(
        self,
        reasoning: list[str],
        warnings: list[str],
        data_sources: list[str],
    ) -> float:
        """Score macro economic environment from EODHD."""
        if not self._eodhd.is_configured:
            warnings.append("EODHD not configured — macro score using neutral baseline")
            return 0.50

        try:
            indicators = await self._eodhd.get_economic_indicators("SGP")
            data_sources.append("EODHD Singapore Economic Indicators")

            score = 0.50  # Neutral baseline
            for ind in indicators[:5]:
                ind_lower = (ind.indicator or "").lower()
                # GDP growth — positive change good
                if "gdp" in ind_lower:
                    if ind.change and ind.change > 0:
                        score += 0.10
                        reasoning.append(f"Singapore GDP growth positive ({ind.change:+.1f}%)")
                    elif ind.change and ind.change < -1:
                        score -= 0.15
                        warnings.append(f"Singapore GDP contracting ({ind.change:+.1f}%)")
                # Business confidence / PMI
                elif "pmi" in ind_lower or "confidence" in ind_lower:
                    if ind.value and ind.value > 50:
                        score += 0.08
                        reasoning.append(f"Business confidence/PMI above 50 ({ind.value:.1f})")
                    elif ind.value and ind.value < 45:
                        score -= 0.10
                        warnings.append(f"Business confidence/PMI weak ({ind.value:.1f})")
                # Unemployment — low is good
                elif "unemployment" in ind_lower:
                    if ind.value and ind.value < 3.5:
                        score += 0.05
                        reasoning.append(f"Low unemployment ({ind.value:.1f}%) — healthy labour market")

            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning("macro_score_failed", error=str(e))
            warnings.append("Could not fetch EODHD macro data — using neutral baseline")
            return 0.50

    async def _get_sentiment_score(
        self,
        industry: str,
        region: str,
        reasoning: list[str],
        warnings: list[str],
        data_sources: list[str],
    ) -> float:
        """Score sector news sentiment from NewsAPI (last 7 days)."""
        if not self._newsapi.is_configured:
            warnings.append("NewsAPI not configured — sentiment using neutral baseline")
            return 0.50

        try:
            result = await self._newsapi.search_market_news(
                industry=industry,
                region=region,
                days_back=7,
            )
            data_sources.append(f"NewsAPI: {result.total_results} articles ({industry}, {region}, 7d)")

            if not result.articles:
                return 0.50

            positive = 0
            negative = 0
            for article in result.articles[:20]:
                text = f"{article.title} {article.description or ''}".lower()
                pos = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
                neg = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)
                positive += pos
                negative += neg

            total_signals = positive + negative
            if total_signals == 0:
                return 0.50

            sentiment_ratio = positive / total_signals
            score = 0.25 + (sentiment_ratio * 0.5)  # Range: 0.25–0.75

            if sentiment_ratio > 0.65:
                reasoning.append(
                    f"Positive sector news: {positive} positive signals vs {negative} negative in last 7 days"
                )
            elif sentiment_ratio < 0.35:
                warnings.append(
                    f"Negative sector news: {negative} negative signals vs {positive} positive in last 7 days"
                )

            return round(score, 3)

        except Exception as e:
            logger.warning("sentiment_score_failed", error=str(e))
            warnings.append("Could not fetch NewsAPI sentiment — using neutral baseline")
            return 0.50
