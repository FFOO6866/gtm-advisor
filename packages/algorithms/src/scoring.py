"""Deterministic Scoring Algorithms.

These replace LLM-based scoring with repeatable, explainable calculations.
Same inputs → same outputs, with full attribution of why a score was assigned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScoreComponent(Enum):
    """Components that contribute to a score."""

    FIRMOGRAPHIC_FIT = "firmographic_fit"
    TECHNOGRAPHIC_FIT = "technographic_fit"
    BEHAVIORAL_SIGNAL = "behavioral_signal"
    INTENT_SIGNAL = "intent_signal"
    TIMING_SIGNAL = "timing_signal"
    BUDGET_SIGNAL = "budget_signal"
    AUTHORITY_SIGNAL = "authority_signal"
    NEED_SIGNAL = "need_signal"


@dataclass
class ScoreExplanation:
    """Explainable score breakdown."""

    total_score: float
    confidence: float
    components: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    data_completeness: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": round(self.total_score, 3),
            "confidence": round(self.confidence, 3),
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "reasons": self.reasons,
            "penalties": self.penalties,
            "data_completeness": round(self.data_completeness, 3),
        }


@dataclass
class ICPCriteria:
    """Ideal Customer Profile criteria with weights."""

    # Firmographics
    target_industries: list[str] = field(default_factory=list)
    target_company_sizes: list[str] = field(default_factory=list)  # "1-10", "11-50", etc.
    target_locations: list[str] = field(default_factory=list)
    target_stages: list[str] = field(default_factory=list)  # seed, series_a, etc.
    min_revenue: float | None = None
    max_revenue: float | None = None

    # Technographics
    required_technologies: list[str] = field(default_factory=list)
    preferred_technologies: list[str] = field(default_factory=list)
    excluded_technologies: list[str] = field(default_factory=list)

    # Behavioral
    required_signals: list[str] = field(default_factory=list)  # "hiring", "funding", "expansion"
    preferred_signals: list[str] = field(default_factory=list)

    # Weights (must sum to 1.0)
    weight_industry: float = 0.25
    weight_size: float = 0.20
    weight_location: float = 0.15
    weight_stage: float = 0.10
    weight_technology: float = 0.15
    weight_signals: float = 0.15


class ICPScorer:
    """Deterministic ICP (Ideal Customer Profile) fit scoring.

    Uses weighted rule-based scoring instead of LLM reasoning.
    Fully explainable - every score can be attributed to specific criteria.
    """

    def __init__(self, criteria: ICPCriteria | None = None):
        self.criteria = criteria or ICPCriteria()  # Use defaults if not provided
        self._validate_weights()

    def configure(self, criteria: ICPCriteria) -> None:
        """Update scoring criteria."""
        self.criteria = criteria
        self._validate_weights()

    def _validate_weights(self) -> None:
        """Ensure weights sum to 1.0."""
        total = (
            self.criteria.weight_industry
            + self.criteria.weight_size
            + self.criteria.weight_location
            + self.criteria.weight_stage
            + self.criteria.weight_technology
            + self.criteria.weight_signals
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"ICP weights must sum to 1.0, got {total}")

    def score(self, company: dict[str, Any]) -> ScoreExplanation:
        """Score a company against ICP criteria.

        Args:
            company: Company data with fields:
                - industry: str
                - employee_count: int or str range
                - location: str
                - stage: str
                - technologies: list[str]
                - signals: list[str] (e.g., ["hiring", "funding"])
                - revenue: float (optional)

        Returns:
            Explainable score breakdown
        """
        components: dict[str, float] = {}
        reasons: list[str] = []
        penalties: list[str] = []
        data_points = 0
        available_points = 0

        # 1. Industry fit
        available_points += 1
        industry = company.get("industry", "").lower()
        if industry:
            data_points += 1
            if any(t.lower() in industry for t in self.criteria.target_industries):
                components["industry"] = self.criteria.weight_industry
                reasons.append(f"Industry '{industry}' matches target")
            else:
                components["industry"] = 0.0
                penalties.append(f"Industry '{industry}' not in target list")
        else:
            components["industry"] = (
                self.criteria.weight_industry * 0.5
            )  # Partial score for unknown

        # 2. Company size fit
        available_points += 1
        size = self._normalize_size(company.get("employee_count"))
        if size:
            data_points += 1
            size_match = self._check_size_match(size)
            if size_match == "exact":
                components["size"] = self.criteria.weight_size
                reasons.append(f"Company size {size} matches target")
            elif size_match == "close":
                components["size"] = self.criteria.weight_size * 0.7
                reasons.append(f"Company size {size} close to target")
            else:
                components["size"] = 0.0
                penalties.append(f"Company size {size} outside target range")
        else:
            components["size"] = self.criteria.weight_size * 0.3

        # 3. Location fit
        available_points += 1
        location = company.get("location", "").lower()
        if location:
            data_points += 1
            if any(loc.lower() in location for loc in self.criteria.target_locations):
                components["location"] = self.criteria.weight_location
                reasons.append(f"Location '{location}' in target geography")
            elif "singapore" in location or "apac" in location.lower():
                components["location"] = self.criteria.weight_location * 0.8
                reasons.append(f"Location '{location}' in APAC region")
            else:
                components["location"] = self.criteria.weight_location * 0.3
                penalties.append(f"Location '{location}' not primary target")
        else:
            components["location"] = self.criteria.weight_location * 0.5

        # 4. Stage fit
        available_points += 1
        stage = company.get("stage", "").lower()
        if stage:
            data_points += 1
            if any(s.lower() in stage for s in self.criteria.target_stages):
                components["stage"] = self.criteria.weight_stage
                reasons.append(f"Stage '{stage}' matches target")
            else:
                components["stage"] = self.criteria.weight_stage * 0.5
        else:
            components["stage"] = self.criteria.weight_stage * 0.5

        # 5. Technology fit
        available_points += 1
        technologies = [t.lower() for t in company.get("technologies", [])]
        if technologies:
            data_points += 1
            # Check for exclusions first
            excluded = [
                t
                for t in technologies
                if any(e.lower() in t for e in self.criteria.excluded_technologies)
            ]
            if excluded:
                components["technology"] = 0.0
                penalties.append(f"Uses excluded technology: {excluded}")
            else:
                required_match = sum(
                    1
                    for r in self.criteria.required_technologies
                    if any(r.lower() in t for t in technologies)
                )
                preferred_match = sum(
                    1
                    for p in self.criteria.preferred_technologies
                    if any(p.lower() in t for t in technologies)
                )

                if self.criteria.required_technologies:
                    tech_score = (required_match / len(self.criteria.required_technologies)) * 0.7
                else:
                    tech_score = 0.5

                if self.criteria.preferred_technologies and preferred_match > 0:
                    tech_score += 0.3 * (
                        preferred_match / len(self.criteria.preferred_technologies)
                    )

                components["technology"] = self.criteria.weight_technology * tech_score
                if required_match > 0:
                    reasons.append(f"Uses {required_match} required technologies")
        else:
            components["technology"] = self.criteria.weight_technology * 0.3

        # 6. Signal fit
        available_points += 1
        signals = [s.lower() for s in company.get("signals", [])]
        if signals:
            data_points += 1
            required_signals = sum(
                1 for r in self.criteria.required_signals if r.lower() in signals
            )
            preferred_signals = sum(
                1 for p in self.criteria.preferred_signals if p.lower() in signals
            )

            signal_score = 0.0
            if self.criteria.required_signals:
                signal_score = (required_signals / len(self.criteria.required_signals)) * 0.6
            else:
                signal_score = 0.4

            if preferred_signals > 0:
                signal_score += 0.4 * min(preferred_signals / 3, 1.0)

            components["signals"] = self.criteria.weight_signals * signal_score
            if required_signals > 0 or preferred_signals > 0:
                all_signals = required_signals + preferred_signals
                reasons.append(f"Shows {all_signals} buying signals")
        else:
            components["signals"] = 0.0
            penalties.append("No buying signals detected")

        # Calculate total
        total_score = sum(components.values())
        data_completeness = data_points / available_points if available_points > 0 else 0

        # Confidence based on data completeness
        confidence = min(data_completeness + 0.2, 1.0)  # Minimum 0.2 confidence

        return ScoreExplanation(
            total_score=total_score,
            confidence=confidence,
            components=components,
            reasons=reasons,
            penalties=penalties,
            data_completeness=data_completeness,
        )

    def _normalize_size(self, size: Any) -> str | None:
        """Normalize employee count to range string."""
        if size is None:
            return None
        if isinstance(size, str):
            return size
        if isinstance(size, int):
            if size <= 10:
                return "1-10"
            elif size <= 50:
                return "11-50"
            elif size <= 200:
                return "51-200"
            elif size <= 500:
                return "201-500"
            else:
                return "500+"
        return None

    def _check_size_match(self, size: str) -> str:
        """Check if size matches target ranges."""
        if size in self.criteria.target_company_sizes:
            return "exact"

        # Check adjacent ranges
        ranges = ["1-10", "11-50", "51-200", "201-500", "500+"]
        try:
            size_idx = ranges.index(size)
            for target in self.criteria.target_company_sizes:
                if target in ranges:
                    target_idx = ranges.index(target)
                    if abs(size_idx - target_idx) == 1:
                        return "close"
        except ValueError:
            pass

        return "no_match"


class LeadScorer:
    """Lead scoring using BANT + fit framework.

    Combines:
    - Budget signals
    - Authority signals
    - Need signals
    - Timing signals
    - ICP fit score

    Uses gradient boosting-like weighted combination for production,
    but starts with interpretable rule-based scoring.
    """

    # Default weights based on B2B research
    DEFAULT_WEIGHTS = {
        "budget": 0.20,
        "authority": 0.15,
        "need": 0.25,
        "timing": 0.20,
        "fit": 0.20,
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        icp_scorer: ICPScorer | None = None,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.icp_scorer = icp_scorer
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = sum(self.weights.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Lead weights must sum to 1.0, got {total}")

    def score(
        self,
        lead: dict[str, Any],
        company: dict[str, Any] | None = None,
    ) -> ScoreExplanation:
        """Score a lead.

        Args:
            lead: Lead data with:
                - title: str (job title)
                - seniority: str
                - budget_indicators: list[str]
                - engagement_signals: list[str]
                - pain_points: list[str]
                - timeline: str (optional)
            company: Company data for ICP scoring

        Returns:
            Explainable score breakdown
        """
        components: dict[str, float] = {}
        reasons: list[str] = []
        penalties: list[str] = []

        # 1. Budget score
        budget_indicators = lead.get("budget_indicators", [])
        budget_score = self._score_budget(budget_indicators)
        components["budget"] = budget_score * self.weights["budget"]
        if budget_score > 0.7:
            reasons.append(f"Strong budget indicators: {len(budget_indicators)} signals")
        elif budget_score < 0.3:
            penalties.append("Weak budget signals")

        # 2. Authority score
        title = lead.get("title", "")
        seniority = lead.get("seniority", "")
        authority_score = self._score_authority(title, seniority)
        components["authority"] = authority_score * self.weights["authority"]
        if authority_score > 0.7:
            reasons.append(f"Decision-maker: {title}")
        elif authority_score < 0.3:
            penalties.append("Not a decision-maker")

        # 3. Need score
        pain_points = lead.get("pain_points", [])
        need_score = self._score_need(pain_points)
        components["need"] = need_score * self.weights["need"]
        if need_score > 0.7:
            reasons.append(f"Clear pain points identified: {len(pain_points)}")

        # 4. Timing score
        timeline = lead.get("timeline", "")
        engagement = lead.get("engagement_signals", [])
        timing_score = self._score_timing(timeline, engagement)
        components["timing"] = timing_score * self.weights["timing"]
        if timing_score > 0.7:
            reasons.append("Active buying timeline")
        elif timing_score < 0.3:
            penalties.append("No clear timeline")

        # 5. Fit score (ICP)
        if company and self.icp_scorer:
            fit_result = self.icp_scorer.score(company)
            components["fit"] = fit_result.total_score * self.weights["fit"]
            if fit_result.total_score > 0.7:
                reasons.append("Strong ICP fit")
            reasons.extend(fit_result.reasons[:2])  # Top 2 fit reasons
        else:
            components["fit"] = self.weights["fit"] * 0.5  # Neutral if no company data

        total_score = sum(components.values())

        # Confidence based on data quality
        data_fields = [
            lead.get("title"),
            lead.get("budget_indicators"),
            lead.get("pain_points"),
            company,
        ]
        data_completeness = sum(1 for f in data_fields if f) / len(data_fields)
        confidence = 0.5 + (data_completeness * 0.5)

        return ScoreExplanation(
            total_score=total_score,
            confidence=confidence,
            components=components,
            reasons=reasons,
            penalties=penalties,
            data_completeness=data_completeness,
        )

    def _score_budget(self, indicators: list[str]) -> float:
        """Score budget signals."""
        high_signals = ["funding_raised", "budget_approved", "rfp_issued", "expansion"]
        medium_signals = ["hiring", "new_project", "vendor_evaluation"]

        score = 0.3  # Base score
        for indicator in indicators:
            indicator_lower = indicator.lower()
            if any(h in indicator_lower for h in high_signals):
                score += 0.25
            elif any(m in indicator_lower for m in medium_signals):
                score += 0.15

        return min(score, 1.0)

    def _score_authority(self, title: str, seniority: str) -> float:
        """Score decision-making authority."""
        title_lower = title.lower()

        # C-level and founders
        if any(
            t in title_lower for t in ["ceo", "cto", "cfo", "coo", "founder", "owner", "president"]
        ):
            return 1.0

        # VP/Director level
        if any(t in title_lower for t in ["vp", "vice president", "director", "head of"]):
            return 0.85

        # Manager level
        if any(t in title_lower for t in ["manager", "lead", "principal"]):
            return 0.6

        # Seniority fallback
        seniority_scores = {
            "executive": 1.0,
            "senior": 0.7,
            "mid": 0.5,
            "junior": 0.3,
        }
        return seniority_scores.get(seniority.lower(), 0.4)

    def _score_need(self, pain_points: list[str]) -> float:
        """Score need/pain intensity."""
        if not pain_points:
            return 0.3

        # More pain points = higher need (diminishing returns)
        count_score = min(len(pain_points) * 0.2, 0.6)

        # Check for urgent keywords
        urgent_keywords = ["urgent", "critical", "asap", "deadline", "compliance", "risk"]
        urgency_bonus = 0.0
        for pain in pain_points:
            if any(u in pain.lower() for u in urgent_keywords):
                urgency_bonus = 0.3
                break

        return min(0.3 + count_score + urgency_bonus, 1.0)

    def _score_timing(self, timeline: str, engagement: list[str]) -> float:
        """Score timing/urgency."""
        score = 0.3  # Base score

        # Timeline keywords
        timeline_lower = timeline.lower()
        if any(
            t in timeline_lower
            for t in ["immediate", "this month", "this quarter", "q1", "q2", "q3", "q4"]
        ):
            score += 0.4
        elif any(t in timeline_lower for t in ["next quarter", "6 months", "this year"]):
            score += 0.2

        # Engagement signals
        high_engagement = ["demo_requested", "pricing_viewed", "trial_started", "meeting_scheduled"]
        medium_engagement = ["content_downloaded", "webinar_attended", "email_opened"]

        for signal in engagement:
            signal_lower = signal.lower()
            if any(h in signal_lower for h in high_engagement):
                score += 0.15
            elif any(m in signal_lower for m in medium_engagement):
                score += 0.05

        return min(score, 1.0)


class MessageAlignmentScorer:
    """Score message-persona alignment.

    Ensures messaging resonates with target persona's priorities.
    """

    def score(
        self,
        message: str,
        persona: dict[str, Any],
    ) -> ScoreExplanation:
        """Score message alignment with persona.

        Args:
            message: The message content
            persona: Persona data with:
                - pain_points: list[str]
                - priorities: list[str]
                - objections: list[str]
                - tone_preference: str

        Returns:
            Alignment score
        """
        components: dict[str, float] = {}
        reasons: list[str] = []
        penalties: list[str] = []

        message_lower = message.lower()

        # 1. Pain point coverage
        pain_points = persona.get("pain_points", [])
        if pain_points:
            addressed = sum(1 for p in pain_points if p.lower() in message_lower)
            coverage = addressed / len(pain_points)
            components["pain_coverage"] = coverage * 0.35
            if coverage > 0.5:
                reasons.append(f"Addresses {addressed}/{len(pain_points)} pain points")
            else:
                penalties.append("Misses key pain points")
        else:
            components["pain_coverage"] = 0.15

        # 2. Priority alignment
        priorities = persona.get("priorities", [])
        if priorities:
            aligned = sum(1 for p in priorities if p.lower() in message_lower)
            alignment = aligned / len(priorities)
            components["priority_alignment"] = alignment * 0.30
            if aligned > 0:
                reasons.append(f"Aligns with {aligned} priorities")
        else:
            components["priority_alignment"] = 0.15

        # 3. Objection handling
        objections = persona.get("objections", [])
        if objections:
            handled = sum(1 for o in objections if self._addresses_objection(message_lower, o))
            handling = handled / len(objections)
            components["objection_handling"] = handling * 0.20
            if handled > 0:
                reasons.append(f"Pre-handles {handled} objections")
        else:
            components["objection_handling"] = 0.10

        # 4. Tone match (simplified)
        tone = persona.get("tone_preference", "professional")
        tone_score = self._score_tone(message, tone)
        components["tone_match"] = tone_score * 0.15

        total_score = sum(components.values())

        return ScoreExplanation(
            total_score=total_score,
            confidence=0.7,  # Messaging scoring is inherently less certain
            components=components,
            reasons=reasons,
            penalties=penalties,
            data_completeness=0.8,
        )

    def _addresses_objection(self, message: str, objection: str) -> bool:
        """Check if message addresses an objection."""
        objection_keywords = {
            "price": ["roi", "value", "cost-effective", "investment", "savings"],
            "time": ["quick", "fast", "easy", "simple", "automated"],
            "trust": ["proven", "customers", "case study", "results", "guarantee"],
            "complexity": ["simple", "easy", "intuitive", "support", "onboarding"],
        }

        objection_lower = objection.lower()
        for category, keywords in objection_keywords.items():
            if category in objection_lower:
                return any(k in message for k in keywords)

        return False

    def _score_tone(self, message: str, preferred_tone: str) -> float:
        """Score tone match (simplified heuristic)."""
        message_lower = message.lower()

        tone_indicators = {
            "professional": ["pleased to", "would like to", "opportunity", "discuss"],
            "casual": ["hey", "quick", "chat", "catch up"],
            "urgent": ["urgent", "asap", "immediately", "critical"],
            "educational": ["learn", "discover", "insights", "research"],
        }

        indicators = tone_indicators.get(preferred_tone.lower(), tone_indicators["professional"])
        matches = sum(1 for i in indicators if i in message_lower)

        return min(0.5 + (matches * 0.2), 1.0)


class CompetitorThreatScorer:
    """Score competitive threat level."""

    def score(
        self,
        competitor: dict[str, Any],
        your_company: dict[str, Any],
    ) -> ScoreExplanation:
        """Score threat level from a competitor.

        Args:
            competitor: Competitor data
            your_company: Your company data for comparison

        Returns:
            Threat score (higher = more threatening)
        """
        components: dict[str, float] = {}
        reasons: list[str] = []
        penalties: list[str] = []  # Actually advantages in threat context

        # 1. Market overlap
        your_markets = set(your_company.get("target_markets", []))
        their_markets = set(competitor.get("target_markets", []))
        if your_markets and their_markets:
            overlap = len(your_markets & their_markets) / len(your_markets)
            components["market_overlap"] = overlap * 0.25
            if overlap > 0.7:
                reasons.append("High market overlap - direct competitor")
        else:
            components["market_overlap"] = 0.1

        # 2. Feature parity
        your_features = set(your_company.get("features", []))
        their_features = set(competitor.get("features", []))
        if your_features and their_features:
            parity = len(your_features & their_features) / len(your_features)
            components["feature_parity"] = parity * 0.20
            if parity > 0.8:
                reasons.append("High feature parity")
        else:
            components["feature_parity"] = 0.1

        # 3. Resource advantage
        their_funding = competitor.get("funding_raised", 0)
        your_funding = your_company.get("funding_raised", 0)
        if their_funding > your_funding * 3:
            components["resource_advantage"] = 0.20
            reasons.append("Significantly more funding")
        elif their_funding > your_funding * 1.5:
            components["resource_advantage"] = 0.10
        else:
            components["resource_advantage"] = 0.05
            penalties.append("Similar or less funding")

        # 4. Growth signals
        growth_signals = competitor.get("growth_signals", [])
        growth_score = min(len(growth_signals) * 0.05, 0.20)
        components["growth_momentum"] = growth_score
        if len(growth_signals) >= 3:
            reasons.append(f"Strong growth signals: {len(growth_signals)}")

        # 5. Brand strength
        brand_mentions = competitor.get("brand_mentions", 0)
        brand_score = min(brand_mentions / 100, 1.0) * 0.15
        components["brand_strength"] = brand_score

        total_score = sum(components.values())

        return ScoreExplanation(
            total_score=total_score,
            confidence=0.65,
            components=components,
            reasons=reasons,
            penalties=penalties,
            data_completeness=0.7,
        )
