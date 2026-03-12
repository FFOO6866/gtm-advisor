"""Unit tests for CampaignArchitectAgent placeholder detection and _check() scoring."""

from __future__ import annotations

import pytest

from agents.campaign_architect.src.agent import (
    CampaignArchitectAgent,
    CampaignPlanOutput,
    ContentPiece,
    MessagingFramework,
)
from packages.core.src.types import CampaignBrief


def _make_brief() -> CampaignBrief:
    return CampaignBrief(
        name="Test Campaign",
        objective="lead generation",
        target_persona="SaaS startup founders",
        budget_sgd=None,
        channels=[],
    )


def _make_output(content_pieces: list[ContentPiece]) -> CampaignPlanOutput:
    return CampaignPlanOutput(
        campaign_brief=_make_brief(),
        messaging_framework=MessagingFramework(
            value_proposition="We help Singapore SMEs close deals faster",
            key_messages=["Reduce sales cycle by 30%", "No setup fee"],
            proof_points=["50+ customers", "SGD 2M ARR"],
            tone_and_voice="Professional but approachable",
        ),
        content_pieces=content_pieces,
        channel_strategy={"LinkedIn": "primary", "Email": "secondary"},
        success_metrics=["10 demos booked per month", "20% open rate"],
    )


class TestPlaceholderDetection:
    """Verify the regex catches placeholder patterns and leaves clean content alone."""

    PATTERN = CampaignArchitectAgent._PLACEHOLDER_RE

    def _count(self, text: str) -> int:
        return len(self.PATTERN.findall(text))

    def test_detects_recipient_name(self):
        assert self._count("Hi [RECIPIENT NAME], I noticed...") == 1

    def test_detects_company(self):
        assert self._count("Your company [COMPANY] is growing fast.") == 1

    def test_detects_insert(self):
        assert self._count("We [INSERT VALUE PROP] here.") == 1

    def test_detects_your_name(self):
        assert self._count("Regards, [YOUR NAME]") == 1

    def test_detects_case_insensitive(self):
        assert self._count("[recipient name] is good.") == 1
        assert self._count("[Recipient Name]") == 1

    def test_ignores_clean_content(self):
        clean = (
            "Hi Sarah, I came across Acme Corp's recent expansion into ASEAN and "
            "thought you might be exploring GTM tooling for your outbound team. "
            "We've helped similar SaaS companies in Singapore reduce their sales cycle by 30%."
        )
        assert self._count(clean) == 0

    def test_multiple_placeholders_counted_separately(self):
        text = "Hi [RECIPIENT NAME], [COMPANY] is great. Regards, [YOUR NAME]"
        assert self._count(text) >= 3

    def test_detects_first_name(self):
        assert self._count("Dear [FIRST NAME],") == 1

    def test_detects_pain_point(self):
        assert self._count("We solve [PAIN POINT] for you.") == 1

    def test_ignores_generic_brackets(self):
        # Non-placeholder bracket content should not match
        assert self._count("[Series A startups]") == 0
        assert self._count("[Q3 2024 results]") == 0

    def test_detects_curly_brace_first_name(self):
        # LLMs sometimes use {first_name} style — must be caught
        assert self._count("Hi {first_name}, I noticed your company...") == 1

    def test_detects_curly_brace_company_name(self):
        assert self._count("Congrats on {company_name}'s expansion!") == 1

    def test_detects_curly_brace_your_name(self):
        assert self._count("Best, {your_name}") == 1

    def test_ignores_non_placeholder_curly_braces(self):
        # Python dict literals and non-placeholder curly content should not match
        assert self._count('{"key": "value"}') == 0
        assert self._count("{Q3 results}") == 0


@pytest.mark.asyncio
async def test_check_penalizes_placeholders():
    """_check() should reduce score when placeholders are present."""
    agent = CampaignArchitectAgent()

    clean_piece = ContentPiece(
        type="email",
        title="Cold outreach",
        content="Hi Sarah, Acme Corp's expansion into ASEAN caught my eye. We help SaaS teams...",
        target_persona="Head of Sales",
        call_to_action="Book a 20-min call",
    )
    placeholder_piece = ContentPiece(
        type="email",
        title="Cold outreach",
        content="Hi [RECIPIENT NAME], [COMPANY] recently expanded. We can help. - [YOUR NAME]",
        target_persona="Head of Sales",
        call_to_action="Book a call",
    )

    clean_output = _make_output([clean_piece])
    placeholder_output = _make_output([placeholder_piece])

    clean_score = await agent._check(clean_output)
    placeholder_score = await agent._check(placeholder_output)

    assert placeholder_score < clean_score, (
        f"Placeholder content ({placeholder_score:.2f}) should score lower than clean ({clean_score:.2f})"
    )
    # 3 placeholders × 0.05 = 0.15 penalty
    assert placeholder_score <= clean_score - 0.14


@pytest.mark.asyncio
async def test_check_no_penalty_clean_content():
    """_check() should give no placeholder penalty for clean, specific content."""
    agent = CampaignArchitectAgent()

    piece = ContentPiece(
        type="email",
        title="Subject: Singapore fintech teams scaling outbound — quick question",
        content=(
            "Hi Priya, I noticed TechVenture just hired 3 BDRs on LinkedIn — "
            "congrats on the team growth! We help Singapore SaaS companies like yours "
            "cut outbound ramp time by 40% using AI-assisted sequencing. "
            "Worth a 15-min chat this week? — Jason from GTM Advisor"
        ),
        target_persona="VP Sales",
        call_to_action="Reply to book 15 mins",
    )

    output = _make_output([piece])
    score = await agent._check(output)

    # Should score at least 0.60 for a well-structured output with no placeholders
    assert score >= 0.60


@pytest.mark.asyncio
async def test_check_diversity_bonus():
    """_check() awards bonus for multiple content types."""
    agent = CampaignArchitectAgent()

    pieces = [
        ContentPiece(type="email", title="Email", content="Specific email content here for Acme.", call_to_action="Book call"),
        ContentPiece(type="linkedin", title="LinkedIn post", content="Singapore SaaS growth story here.", call_to_action="Connect"),
    ]
    output = _make_output(pieces)
    score = await agent._check(output)

    # Base 0.2 + structure bonuses + diversity bonus — should be well above 0.5
    assert score >= 0.55
