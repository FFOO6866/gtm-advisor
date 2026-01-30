"""Campaign Architect Agent - Messaging and campaign planning.

Creates actionable campaign plans with messaging, content, and outreach templates.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.types import CampaignBrief


class MessagingFramework(BaseModel):
    """Messaging framework for campaigns."""

    value_proposition: str = Field(...)
    key_messages: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    objection_handling: dict[str, str] = Field(default_factory=dict)
    tone_and_voice: str = Field(default="")


class ContentPiece(BaseModel):
    """A content piece for the campaign."""

    type: str = Field(...)  # email, linkedin, blog, case_study
    title: str = Field(...)
    content: str = Field(...)
    target_persona: str | None = Field(default=None)
    call_to_action: str | None = Field(default=None)


class CampaignPlanOutput(BaseModel):
    """Complete campaign plan."""

    campaign_brief: CampaignBrief = Field(...)
    messaging_framework: MessagingFramework = Field(...)
    content_pieces: list[ContentPiece] = Field(default_factory=list)
    channel_strategy: dict[str, str] = Field(default_factory=dict)
    timeline_recommendations: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CampaignArchitectAgent(BaseGTMAgent[CampaignPlanOutput]):
    """Campaign Architect - Creates actionable campaign plans.

    Develops:
    - Messaging frameworks
    - Email templates
    - LinkedIn content
    - Outreach sequences
    """

    def __init__(self) -> None:
        super().__init__(
            name="campaign-architect",
            description=(
                "Creates actionable marketing and outreach campaigns. "
                "Develops messaging, content, and multi-channel strategies "
                "tailored to your target audience."
            ),
            result_type=CampaignPlanOutput,
            min_confidence=0.60,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="messaging-development", description="Create messaging frameworks"
                ),
                AgentCapability(name="content-creation", description="Generate campaign content"),
                AgentCapability(name="channel-strategy", description="Plan multi-channel approach"),
            ],
        )

    def get_system_prompt(self) -> str:
        return """You are the Campaign Architect, an expert in B2B marketing for Singapore/APAC markets.

You create ACTIONABLE campaigns with:
1. Clear, differentiated messaging
2. Ready-to-use email templates
3. LinkedIn content and outreach messages
4. Multi-channel strategies

For Singapore B2B:
- Direct, professional communication style
- Reference local context (PSG grants, APAC expansion)
- Focus on ROI and efficiency
- Consider relationship-based selling culture

Provide COMPLETE content - not placeholders.
Templates should be ready to personalize and send."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        return {
            "company_info": context.get("company_profile", {}),
            "personas": context.get("personas", []),
            "leads": context.get("leads", []),
            "value_proposition": context.get("value_proposition", ""),
            "campaign_goal": context.get("goal", "lead generation"),
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CampaignPlanOutput:
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Create a complete campaign plan:

Company: {plan.get("company_info", "Not specified")}
Value Proposition: {plan.get("value_proposition", "Not specified")}
Target Personas: {plan.get("personas", [])}
Campaign Goal: {plan.get("campaign_goal")}
Target Leads: {len(plan.get("leads", []))} leads identified

Create:
1. Campaign brief with objectives and targets
2. Messaging framework with key messages and proof points
3. 3-5 ready-to-use content pieces:
   - 2 cold outreach emails (initial + follow-up)
   - 2 LinkedIn posts/messages
   - 1 value-add content idea
4. Channel strategy
5. Success metrics

Make all content COMPLETE and READY TO USE - not templates with placeholders.""",
            },
        ]

        return await self._complete_structured(
            response_model=CampaignPlanOutput,
            messages=messages,
        )

    async def _check(self, result: CampaignPlanOutput) -> float:
        score = 0.3  # Base score
        if result.messaging_framework.value_proposition:
            score += 0.2
        if result.messaging_framework.key_messages:
            score += 0.15
        if result.content_pieces:
            score += 0.2
            # Check content quality
            complete_content = sum(1 for c in result.content_pieces if len(c.content) > 100)
            if complete_content >= 3:
                score += 0.15
        if result.channel_strategy:
            score += 0.15
        if result.success_metrics:
            score += 0.1
        return min(score, 1.0)
