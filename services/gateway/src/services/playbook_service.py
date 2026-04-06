"""Playbook Service — manages pre-built GTM playbook templates.

Handles:
1. Seeding built-in playbooks to the database on startup
2. Converting PlaybookFitScorer recommendations into SequenceTemplate records
3. Providing playbook configuration for the WorkforceArchitect
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    PlaybookTemplate,
    SequenceStep,
    SequenceTemplate,
)
from packages.scoring.src.playbook_fit import PlaybookType

logger = structlog.get_logger()


BUILT_IN_PLAYBOOKS: list[dict[str, Any]] = [
    {
        "playbook_type": PlaybookType.COLD_OUTREACH_BLITZ.value,
        "name": "Cold Outreach Blitz",
        "description": "4-step cold email sequence targeting your highest-fit ICP leads. Built for volume and speed.",
        "best_for": "When you have 20+ qualified leads and want to generate meetings quickly",
        "steps_count": 4,
        "duration_days": 14,
        "success_rate_benchmark": "12-18% reply rate for well-targeted Singapore B2B lists",
        "is_singapore_specific": False,
        "sequence_config": {
            "steps": [
                {"day_offset": 0, "step_type": "cold_intro", "subject_pattern": "Quick question about {company_name}", "body_instructions": "Write a concise cold intro (under 100 words). Reference their industry and a specific pain point from the ICP analysis. End with one clear question."},
                {"day_offset": 4, "step_type": "value_insight", "subject_pattern": "Insight for {industry} leaders in SG", "body_instructions": "Share a specific market insight relevant to their industry (use signal events if available). Tie back to how Kairos addresses it. Soft CTA."},
                {"day_offset": 9, "step_type": "social_proof", "subject_pattern": "How similar companies solved this", "body_instructions": "Reference a social proof point or outcome. Ask if this challenge resonates. Direct meeting request."},
                {"day_offset": 14, "step_type": "breakup", "subject_pattern": "Closing the loop, {first_name}", "body_instructions": "Brief break-up email. Acknowledge they may be busy. Leave door open. No hard sell."},
            ]
        },
    },
    {
        "playbook_type": PlaybookType.WARM_UP_CAMPAIGN.value,
        "name": "Warm Up Campaign",
        "description": "Content-first approach. Share relevant insights before making an ask.",
        "best_for": "Enterprise prospects or high-value leads where cold outreach feels too aggressive",
        "steps_count": 3,
        "duration_days": 10,
        "success_rate_benchmark": "8-12% meeting conversion, higher quality leads",
        "is_singapore_specific": False,
        "sequence_config": {
            "steps": [
                {"day_offset": 0, "step_type": "insight_share", "subject_pattern": "Thought you'd find this {industry} data useful", "body_instructions": "Share a relevant market insight or stat (from signal monitor if available). Zero ask. Pure value."},
                {"day_offset": 5, "step_type": "content_followup", "subject_pattern": "Following up on the {industry} article", "body_instructions": "Reference the previous message. Add another insight or framework. Soft: 'Worth exploring if this applies to {company_name}?'"},
                {"day_offset": 10, "step_type": "soft_ask", "subject_pattern": "Worth a 15-min chat, {first_name}?", "body_instructions": "Direct, respectful meeting request. Reference the two previous messages. Offer specific value for the 15 minutes."},
            ]
        },
    },
    {
        "playbook_type": PlaybookType.COMPETITOR_DISPLACEMENT.value,
        "name": "Competitor Displacement",
        "description": "Targets competitor customers with displacement messaging when a competitor signal is detected.",
        "best_for": "When a competitor has negative news, pricing change, or product gaps",
        "steps_count": 4,
        "duration_days": 12,
        "success_rate_benchmark": "15-22% reply rate when competitor signal is fresh (< 7 days)",
        "is_singapore_specific": False,
        "sequence_config": {
            "steps": [
                {"day_offset": 0, "step_type": "problem_focused", "subject_pattern": "Re: [competitor signal headline]", "body_instructions": "Reference the competitor news (funding, product issue, pricing change). Empathise with the challenge this creates. Position as an alternative. No hard sell."},
                {"day_offset": 3, "step_type": "comparison", "subject_pattern": "How we solve what they can't", "body_instructions": "One clear differentiator from the competitor. Specific, not generic. Real example if possible."},
                {"day_offset": 7, "step_type": "roi_focused", "subject_pattern": "ROI in 90 days — worth 15 mins?", "body_instructions": "Quantify the value. If PSG grant eligible, mention the grant subsidy. Direct meeting ask with specific time slots."},
                {"day_offset": 12, "step_type": "final_ask", "subject_pattern": "Last email, {first_name}", "body_instructions": "Brief final message. Acknowledge they may be happy with their current solution. Leave door open for future."},
            ]
        },
    },
    {
        "playbook_type": PlaybookType.SIGNAL_TRIGGERED.value,
        "name": "Signal-Triggered Outreach",
        "description": "Reactive 2-step play based on a specific market event. Speed is critical — send within 24h.",
        "best_for": "High-relevance signals (funding, acquisition, regulation) detected within 48 hours",
        "steps_count": 2,
        "duration_days": 4,
        "success_rate_benchmark": "20-30% reply rate when sent within 24h of signal",
        "is_singapore_specific": False,
        "sequence_config": {
            "steps": [
                {"day_offset": 0, "step_type": "signal_reference", "subject_pattern": "Re: [signal headline]", "body_instructions": "Reference the specific signal event (e.g. 'Saw that [competitor] just raised Series B'). Connect it to how your client is positioned. Be specific and timely. Very brief."},
                {"day_offset": 4, "step_type": "followup", "subject_pattern": "Following up on my note", "body_instructions": "Brief follow-up referencing the original signal. Direct meeting ask. One sentence."},
            ]
        },
    },
    {
        "playbook_type": PlaybookType.PSG_GRANT_OPPORTUNITY.value,
        "name": "PSG Grant Opportunity",
        "description": "Singapore-specific. Leverages the Productivity Solutions Grant to create urgency and reduce perceived cost.",
        "best_for": "Singapore SMEs eligible for PSG grant. Creates urgency around grant cycles.",
        "steps_count": 3,
        "duration_days": 7,
        "success_rate_benchmark": "25-35% reply rate for PSG-eligible segments (grant = cost reduction)",
        "is_singapore_specific": True,
        "sequence_config": {
            "steps": [
                {"day_offset": 0, "step_type": "grant_awareness", "subject_pattern": "PSG grant available for {company_name}", "body_instructions": "Introduce the PSG grant eligibility. State the grant percentage (up to 50%). Connect to specific pain point. Keep under 100 words."},
                {"day_offset": 3, "step_type": "roi_with_grant", "subject_pattern": "With PSG: your net investment is much lower", "body_instructions": "Show the ROI calculation with PSG subsidy applied. Example: 'Investment: SGD X, Grant covers 50%, your cost: SGD Y, payback: Z months.' Very concrete numbers."},
                {"day_offset": 7, "step_type": "deadline_urgency", "subject_pattern": "Grant applications close [date] — {first_name}", "body_instructions": "Create urgency with grant cycle deadline. Offer to help with application. Direct CTA: 15-min call to assess eligibility."},
            ]
        },
    },
    {
        "playbook_type": PlaybookType.MARKET_ENTRY.value,
        "name": "Market Entry Play",
        "description": "For clients expanding into a new segment or geography. Education-first messaging.",
        "best_for": "Entering a new vertical or expanding from Singapore into APAC markets",
        "steps_count": 3,
        "duration_days": 14,
        "success_rate_benchmark": "10-15% meeting conversion, longer sales cycle expected",
        "is_singapore_specific": False,
        "sequence_config": {
            "steps": [
                {"day_offset": 0, "step_type": "market_intro", "subject_pattern": "Exploring {new_market} opportunities", "body_instructions": "Brief intro explaining you're expanding into their market/segment. Reference a specific insight about their market. Genuine curiosity — ask about their perspective."},
                {"day_offset": 7, "step_type": "social_proof", "subject_pattern": "How [peer company] expanded into this space", "body_instructions": "Share a relevant case study or proof point of success in their market. Connect to the prospect's context."},
                {"day_offset": 14, "step_type": "direct_ask", "subject_pattern": "Worth exploring together, {first_name}?", "body_instructions": "Direct meeting ask. Frame as mutual exploration of fit. Not a hard sell — you're both evaluating fit."},
            ]
        },
    },
]


class PlaybookService:
    """Manages playbook templates and sequence creation."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def seed_built_in_playbooks(self) -> int:
        """Seed built-in playbook templates to the database.

        Idempotent — checks if template exists before creating.
        Called from FastAPI lifespan startup.

        Returns:
            Number of playbooks created (0 if already seeded)
        """
        created = 0
        for pb_data in BUILT_IN_PLAYBOOKS:
            existing = await self._db.execute(
                select(PlaybookTemplate).where(
                    PlaybookTemplate.playbook_type == pb_data["playbook_type"]
                )
            )
            if existing.scalar_one_or_none():
                continue

            template = PlaybookTemplate(
                playbook_type=pb_data["playbook_type"],
                name=pb_data["name"],
                description=pb_data["description"],
                best_for=pb_data["best_for"],
                steps_count=pb_data["steps_count"],
                duration_days=pb_data["duration_days"],
                success_rate_benchmark=pb_data.get("success_rate_benchmark"),
                sequence_config=pb_data.get("sequence_config", {}),
                is_singapore_specific=pb_data.get("is_singapore_specific", False),
            )
            self._db.add(template)
            created += 1

        if created > 0:
            await self._db.commit()
            logger.info("playbooks_seeded", count=created)

        return created

    async def create_sequence_from_playbook(
        self,
        playbook_type: str,
        company_id: UUID,
        custom_name: str | None = None,
    ) -> SequenceTemplate:
        """Create a SequenceTemplate from a PlaybookTemplate.

        Args:
            playbook_type: The playbook type string
            company_id: The company workspace
            custom_name: Optional override for the template name

        Returns:
            The created SequenceTemplate with its steps
        """
        pb = await self._db.execute(
            select(PlaybookTemplate).where(PlaybookTemplate.playbook_type == playbook_type)
        )
        playbook = pb.scalar_one_or_none()
        if not playbook:
            raise ValueError(f"Playbook type '{playbook_type}' not found")

        name = custom_name or playbook.name
        template = SequenceTemplate(
            company_id=company_id,
            name=name,
            playbook_type=playbook_type,
            description=playbook.description,
            total_steps=playbook.steps_count,
            total_duration_days=playbook.duration_days,
        )
        self._db.add(template)
        await self._db.flush()  # Get ID before adding steps

        # Create steps from sequence_config
        steps_config = playbook.sequence_config.get("steps", [])
        for i, step_data in enumerate(steps_config):
            step = SequenceStep(
                template_id=template.id,
                step_number=i,
                day_offset=step_data.get("day_offset", i * 3),
                step_type=step_data.get("step_type", "followup"),
                subject_pattern=step_data.get("subject_pattern", "Following up, {first_name}"),
                body_instructions=step_data.get("body_instructions"),
                requires_approval=True,
            )
            self._db.add(step)

        await self._db.commit()
        await self._db.refresh(template)

        logger.info(
            "sequence_created_from_playbook",
            playbook=playbook_type,
            template_id=str(template.id),
            steps=len(steps_config),
        )
        return template

    async def get_all_playbooks(self) -> list[PlaybookTemplate]:
        """Get all active playbook templates."""
        result = await self._db.execute(
            select(PlaybookTemplate).where(PlaybookTemplate.is_active == True).order_by(PlaybookTemplate.name)
        )
        return list(result.scalars().all())
