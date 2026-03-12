"""Playbook Fit Scorer — recommends the optimal outreach playbook.

Given analysis results (leads, competitors, market signals, ICP),
recommends which pre-built playbook will maximise win probability.

Available playbooks:
  COLD_OUTREACH_BLITZ      — 4-step cold sequence, high volume
  WARM_UP_CAMPAIGN         — content-first, lower volume, higher quality
  COMPETITOR_DISPLACEMENT  — targeting competitor's customers
  SIGNAL_TRIGGERED         — reactive to specific market signal
  PSG_GRANT_OPPORTUNITY    — Singapore PSG grant urgency play
  MARKET_ENTRY             — entering a new market/segment

This scorer does NOT use LLM. It uses:
- Lead count and quality distribution
- Competitor presence and threat score
- Market context (from MarketContextScorer)
- Industry + Singapore-specific patterns
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlaybookType(str, Enum):
    COLD_OUTREACH_BLITZ = "cold_outreach_blitz"
    WARM_UP_CAMPAIGN = "warm_up_campaign"
    COMPETITOR_DISPLACEMENT = "competitor_displacement"
    SIGNAL_TRIGGERED = "signal_triggered"
    PSG_GRANT_OPPORTUNITY = "psg_grant_opportunity"
    MARKET_ENTRY = "market_entry"


PLAYBOOK_METADATA = {
    PlaybookType.COLD_OUTREACH_BLITZ: {
        "name": "Cold Outreach Blitz",
        "description": "4-step cold email sequence targeting your highest-fit ICP leads. Built for volume and speed.",
        "steps": 4,
        "duration_days": 14,
        "best_for": "When you have 20+ qualified leads and want to generate meetings quickly",
        "success_rate_benchmark": "12-18% reply rate for well-targeted lists",
        "sequence": [
            {"day": 0, "type": "cold_intro", "subject_pattern": "Quick question about {company_name}"},
            {"day": 4, "type": "value_insight", "subject_pattern": "Insight for {industry} leaders in SG"},
            {"day": 9, "type": "social_proof", "subject_pattern": "How {peer_company} did it"},
            {"day": 14, "type": "breakup", "subject_pattern": "Closing the loop, {first_name}"},
        ],
    },
    PlaybookType.WARM_UP_CAMPAIGN: {
        "name": "Warm Up Campaign",
        "description": "Content-first approach. Share relevant insights before making an ask. Higher quality, lower volume.",
        "steps": 3,
        "duration_days": 10,
        "best_for": "Enterprise prospects or when cold outreach feels too aggressive for the relationship",
        "success_rate_benchmark": "8-12% meeting conversion, higher quality leads",
        "sequence": [
            {"day": 0, "type": "insight_share", "subject_pattern": "Thought you'd find this {industry} report useful"},
            {"day": 5, "type": "content_followup", "subject_pattern": "Following up on the {industry} article"},
            {"day": 10, "type": "soft_ask", "subject_pattern": "Worth a 15-min chat?"},
        ],
    },
    PlaybookType.COMPETITOR_DISPLACEMENT: {
        "name": "Competitor Displacement",
        "description": "Targets customers of tracked competitors with displacement messaging. Requires competitor intelligence.",
        "steps": 4,
        "duration_days": 12,
        "best_for": "When a competitor is vulnerable (negative news, pricing change, product gaps)",
        "success_rate_benchmark": "15-22% reply rate when competitor signal is fresh (< 7 days)",
        "sequence": [
            {"day": 0, "type": "problem_focused", "subject_pattern": "Re: challenges with {competitor}"},
            {"day": 3, "type": "comparison", "subject_pattern": "How we solve what {competitor} can't"},
            {"day": 7, "type": "roi_focused", "subject_pattern": "ROI in 90 days — is that worth 15 mins?"},
            {"day": 12, "type": "final_ask", "subject_pattern": "Last email, {first_name}"},
        ],
    },
    PlaybookType.SIGNAL_TRIGGERED: {
        "name": "Signal-Triggered Outreach",
        "description": "Reactive play based on a specific market event (funding, regulation, expansion). Highly timely.",
        "steps": 2,
        "duration_days": 4,
        "best_for": "When a high-relevance signal is detected (< 48 hours old). Speed is critical.",
        "success_rate_benchmark": "20-30% reply rate when sent within 24h of signal",
        "sequence": [
            {"day": 0, "type": "signal_reference", "subject_pattern": "Re: {signal_headline}"},
            {"day": 4, "type": "followup", "subject_pattern": "Following up on my note about {signal_topic}"},
        ],
    },
    PlaybookType.PSG_GRANT_OPPORTUNITY: {
        "name": "PSG Grant Opportunity",
        "description": "Singapore-specific. Leads with PSG-eligible profiles receive urgency-driven grant messaging.",
        "steps": 3,
        "duration_days": 7,
        "best_for": "Singapore SMEs eligible for Productivity Solutions Grant — creates urgency around grant cycles",
        "success_rate_benchmark": "25-35% reply rate for PSG-eligible segments (grant = cost reduction)",
        "sequence": [
            {"day": 0, "type": "grant_awareness", "subject_pattern": "SGD grant available for {company_name}"},
            {"day": 3, "type": "roi_with_grant", "subject_pattern": "With PSG: {product} costs you {net_cost}"},
            {"day": 7, "type": "deadline_urgency", "subject_pattern": "Grant deadline approaching — {first_name}"},
        ],
    },
    PlaybookType.MARKET_ENTRY: {
        "name": "Market Entry Play",
        "description": "For clients expanding into a new segment or geography. Education-first messaging.",
        "steps": 3,
        "duration_days": 14,
        "best_for": "Entering a new vertical or expanding from Singapore into APAC",
        "success_rate_benchmark": "10-15% meeting conversion, longer sales cycle",
        "sequence": [
            {"day": 0, "type": "market_intro", "subject_pattern": "{client} is now in {new_market}"},
            {"day": 7, "type": "social_proof", "subject_pattern": "How {peer_company} entered {new_market}"},
            {"day": 14, "type": "direct_ask", "subject_pattern": "Worth exploring together?"},
        ],
    },
}


@dataclass
class PlaybookRecommendation:
    """Recommended playbook with scoring rationale."""
    primary: PlaybookType
    secondary: PlaybookType | None
    primary_score: float
    secondary_score: float | None
    reasoning: list[str] = field(default_factory=list)
    configuration_hints: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_metadata(self) -> dict[str, Any]:
        return PLAYBOOK_METADATA[self.primary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_playbook": self.primary.value,
            "secondary_playbook": self.secondary.value if self.secondary else None,
            "primary_score": round(self.primary_score, 3),
            "secondary_score": round(self.secondary_score, 3) if self.secondary_score else None,
            "primary_metadata": self.primary_metadata,
            "reasoning": self.reasoning,
            "configuration_hints": self.configuration_hints,
        }


class PlaybookFitScorer:
    """Recommends the optimal outreach playbook for a client's context.

    Uses deterministic scoring based on:
    - Lead volume and quality
    - Competitor intelligence freshness
    - Signal urgency
    - Singapore PSG eligibility
    - Market entry context
    - Market context (opportunity window)
    """

    def score(
        self,
        lead_count: int,
        avg_lead_quality: float,
        has_competitor_signal: bool,
        competitor_signal_age_hours: float,
        has_urgent_market_signal: bool,
        client_industry: str,
        is_singapore_sme: bool,
        is_new_market_entry: bool,
        market_opportunity_rating: str = "amber",
    ) -> PlaybookRecommendation:
        """Recommend optimal playbook.

        Args:
            lead_count: Number of qualified leads available
            avg_lead_quality: Average lead quality score (0-1)
            has_competitor_signal: A relevant competitor signal was detected
            competitor_signal_age_hours: How old the competitor signal is
            has_urgent_market_signal: Any urgent (immediate/this_week) signal
            client_industry: Client's industry
            is_singapore_sme: Is the client a Singapore SME (PSG eligible)
            is_new_market_entry: Is this a new market/segment expansion
            market_opportunity_rating: green/amber/red from MarketContextScorer

        Returns:
            PlaybookRecommendation with primary and secondary recommendations
        """
        scores: dict[PlaybookType, float] = dict.fromkeys(PlaybookType, 0.0)
        reasoning: list[str] = []

        # --- Signal-Triggered: highest priority if signal is fresh ---
        if has_urgent_market_signal:
            scores[PlaybookType.SIGNAL_TRIGGERED] += 0.60
            reasoning.append("Urgent market signal detected — Signal-Triggered play activates")

        # --- Competitor Displacement: fresh competitor signal ---
        if has_competitor_signal:
            displacement_score = 0.50
            if competitor_signal_age_hours <= 24:
                displacement_score = 0.80
                reasoning.append("Fresh competitor signal (< 24h) — prime displacement window")
            elif competitor_signal_age_hours <= 72:
                displacement_score = 0.65
                reasoning.append("Recent competitor signal — displacement still relevant")
            scores[PlaybookType.COMPETITOR_DISPLACEMENT] += displacement_score

        # --- PSG Grant: Singapore SME play ---
        if is_singapore_sme:
            scores[PlaybookType.PSG_GRANT_OPPORTUNITY] += 0.55
            reasoning.append("Singapore SME context — PSG Grant play applicable")
            psg_eligible_industries = ["saas", "software", "erp", "crm", "logistics", "hr", "accounting", "cybersecurity"]
            if any(ind in client_industry.lower() for ind in psg_eligible_industries):
                scores[PlaybookType.PSG_GRANT_OPPORTUNITY] += 0.20
                reasoning.append(f"{client_industry} is PSG-eligible — grant angle adds urgency")

        # --- Market Entry ---
        if is_new_market_entry:
            scores[PlaybookType.MARKET_ENTRY] += 0.70
            reasoning.append("New market entry context — Market Entry playbook recommended")

        # --- Cold Outreach Blitz: high volume, good market conditions ---
        if lead_count >= 15 and avg_lead_quality >= 0.55:
            scores[PlaybookType.COLD_OUTREACH_BLITZ] += 0.55
            if market_opportunity_rating == "green":
                scores[PlaybookType.COLD_OUTREACH_BLITZ] += 0.20
                reasoning.append(f"Green market conditions + {lead_count} qualified leads — Blitz conditions met")
            elif market_opportunity_rating == "red":
                scores[PlaybookType.COLD_OUTREACH_BLITZ] -= 0.20
                reasoning.append("Red market conditions — reduce cold volume")

        # --- Warm Up Campaign: smaller list or amber/red market ---
        if lead_count < 15 or avg_lead_quality >= 0.75 or market_opportunity_rating in ("amber", "red"):
            scores[PlaybookType.WARM_UP_CAMPAIGN] += 0.45
            if avg_lead_quality >= 0.75:
                scores[PlaybookType.WARM_UP_CAMPAIGN] += 0.15
                reasoning.append("High-quality leads — Warm Up approach maximises relationship value")

        # Find top 2
        sorted_playbooks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary, primary_score = sorted_playbooks[0]
        secondary, secondary_score = sorted_playbooks[1] if len(sorted_playbooks) > 1 else (None, None)

        # Configuration hints
        config_hints: dict[str, Any] = {
            "recommended_daily_send_limit": 20 if primary == PlaybookType.COLD_OUTREACH_BLITZ else 10,
            "enable_approval_gate": True,  # Always
            "suggested_from_name": "personal name, not company",
            "subject_line_tip": PLAYBOOK_METADATA[primary].get("sequence", [{}])[0].get("subject_pattern", ""),
        }
        if primary == PlaybookType.PSG_GRANT_OPPORTUNITY:
            config_hints["psg_note"] = "Include PSG grant reference in step 1. Check grant.gov.sg for current eligible solutions."

        return PlaybookRecommendation(
            primary=primary,
            secondary=secondary if secondary else None,
            primary_score=round(primary_score, 3),
            secondary_score=round(secondary_score, 3) if secondary_score is not None else None,
            reasoning=reasoning,
            configuration_hints=config_hints,
        )
