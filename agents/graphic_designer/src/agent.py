"""Graphic Designer Agent — Social media graphics and ad banner generation.

Generates platform-specific marketing visuals by:
1. Determining target platforms from the campaign brief (linkedin, instagram, facebook, x)
2. Building tailored DALL-E prompts per platform (dimensions, tone, composition)
3. Generating images concurrently via DalleMCPServer
4. Generating social copy + hashtags via LLM, matched to each platform's voice

Subscribes to CAMPAIGN_READY events on the bus and publishes CREATIVE_READY
on completion so the Outreach Executor or Campaign Architect can proceed.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.dalle import DalleMCPServer

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class PlatformCreative(BaseModel):
    """Creative asset for a specific platform."""

    platform: str = Field(...)  # linkedin, instagram, facebook, x
    image_url: str = Field(default="")
    image_local_path: str = Field(default="")
    image_prompt: str = Field(default="")
    copy_text: str = Field(default="")
    hashtags: list[str] = Field(default_factory=list)
    call_to_action: str = Field(default="")
    dimensions: str = Field(default="")


class _PlatformCopySpec(BaseModel):
    """LLM-generated copy specification for a single platform."""

    platform: str = Field(...)
    copy_text: str = Field(default="")
    hashtags: list[str] = Field(default_factory=list)
    call_to_action: str = Field(default="")
    image_prompt: str = Field(default="")


class _AllPlatformCopy(BaseModel):
    """Structured LLM output: copy specs for all requested platforms."""

    platforms: list[_PlatformCopySpec] = Field(default_factory=list)


class GraphicDesignOutput(BaseModel):
    """Complete graphic design output for a campaign."""

    campaign_name: str = Field(default="")
    brand_context: str = Field(default="")
    creatives: list[PlatformCreative] = Field(default_factory=list)
    platforms_covered: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Platform configuration
# ---------------------------------------------------------------------------

_PLATFORM_CONFIG: dict[str, dict[str, str]] = {
    "linkedin": {
        "dalle_platform": "linkedin_share",
        "dimensions": "1200x627",
        "copy_tone": "professional, insight-led, thought leadership",
        "copy_length": "150-250 characters",
        "hashtag_count": "3-5",
    },
    "instagram": {
        "dalle_platform": "instagram_feed",
        "dimensions": "1080x1080",
        "copy_tone": "engaging, visual-first, community-driven",
        "copy_length": "100-150 characters + line breaks",
        "hashtag_count": "5-10",
    },
    "facebook": {
        "dalle_platform": "facebook_share",
        "dimensions": "1200x628",
        "copy_tone": "conversational, relatable, benefit-focused",
        "copy_length": "80-150 characters",
        "hashtag_count": "2-3",
    },
    "x": {
        "dalle_platform": "x_post",
        "dimensions": "1600x900",
        "copy_tone": "punchy, direct, newsworthy",
        "copy_length": "under 240 characters",
        "hashtag_count": "1-2",
    },
}

_DEFAULT_PLATFORMS = ["linkedin", "instagram"]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class GraphicDesignerAgent(BaseGTMAgent[GraphicDesignOutput]):
    """Generates platform-specific social media graphics and ad banners.

    Subscribes to CAMPAIGN_READY on the agent bus. Uses DALL-E 3 for image
    generation and GPT-4o for platform-adapted social copy. Publishes
    CREATIVE_READY on completion.
    """

    def __init__(self, agent_bus: AgentBus | None = None) -> None:
        super().__init__(
            name="graphic-designer",
            description=(
                "Generates social media graphics and ad banners for campaigns. "
                "Produces platform-adapted visuals (LinkedIn, Instagram, Facebook, X) "
                "with matching copy and hashtags via DALL-E 3 and GPT-4o."
            ),
            result_type=GraphicDesignOutput,
            min_confidence=0.40,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="social-graphics",
                    description="Generate platform-specific social media images via DALL-E 3",
                ),
                AgentCapability(
                    name="social-copy",
                    description="Generate platform-adapted copy and hashtags via GPT-4o",
                ),
            ],
        )
        self._bus = agent_bus or get_agent_bus()
        self._dalle = DalleMCPServer.from_env()
        self._knowledge_pack: dict[str, Any] = {}
        self._analysis_id: Any = None

        self._bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.CAMPAIGN_READY,
            handler=self._on_campaign_ready,
        )

    def get_system_prompt(self) -> str:
        return (
            "You are an expert social media creative director specialising in B2B campaigns "
            "for Singapore SMEs. You craft platform-native content that is:\n"
            "- LinkedIn: professional, insight-led, thought leadership tone\n"
            "- Instagram: visual-first, engaging, community-driven\n"
            "- Facebook: conversational, benefit-focused, relatable\n"
            "- X (Twitter): punchy, direct, newsworthy\n\n"
            "Your copy must include a clear call-to-action, relevant hashtags, and "
            "never contain placeholder text like [Company Name]. "
            "DALL-E prompts must be specific, visual, and exclude any text overlays "
            "(copy is added separately in the design tool)."
        )

    async def _on_campaign_ready(self, message: AgentMessage) -> None:
        """React to CAMPAIGN_READY events from CampaignArchitect."""
        try:
            if (
                self._analysis_id
                and message.analysis_id
                and str(message.analysis_id) != str(self._analysis_id)
            ):
                return
            context = {
                "campaign_name": message.title,
                "company_name": message.content.get("company_name", ""),
                "value_proposition": message.content.get("value_proposition", ""),
                "campaign_goal": message.content.get("campaign_goal", "brand awareness"),
                "industry": message.content.get("industry", ""),
                "platforms": message.content.get("platforms", _DEFAULT_PLATFORMS),
                "brand_tone": message.content.get("brand_tone", "professional"),
                "analysis_id": message.analysis_id,
            }
            task = f"Design social media graphics for campaign: {message.title}"
            await self.run(task=task, context=context)
        except Exception as e:
            self._logger.warning("graphic_on_campaign_ready_failed", error=str(e))

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Extract campaign brief fields
        campaign_name = context.get("campaign_name", "Campaign")
        company_name = context.get("company_name", "")
        value_proposition = context.get("value_proposition", "")
        campaign_goal = context.get("campaign_goal", "brand awareness")
        industry = context.get("industry", "")
        brand_tone = context.get("brand_tone", "professional")

        # Resolve requested platforms — validate against known platforms
        requested_platforms: list[str] = context.get("platforms", _DEFAULT_PLATFORMS)
        platforms = [p.lower() for p in requested_platforms if p.lower() in _PLATFORM_CONFIG]
        if not platforms:
            platforms = list(_DEFAULT_PLATFORMS)

        # Load synthesized domain knowledge pack
        self._knowledge_pack = {}
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="graphic-designer",
                task_context=task,
            )
        except Exception as e:
            self._logger.debug("graphic_knowledge_pack_failed", error=str(e))

        # Build brand context string used across all platform prompts
        brand_context = (
            f"{company_name} — {industry} company in Singapore. "
            f"Brand tone: {brand_tone}. "
            f"Campaign: {campaign_goal}. "
            f"Value proposition: {value_proposition}."
        ).strip()

        return {
            "campaign_name": campaign_name,
            "company_name": company_name,
            "value_proposition": value_proposition,
            "campaign_goal": campaign_goal,
            "industry": industry,
            "brand_tone": brand_tone,
            "platforms": platforms,
            "brand_context": brand_context,
            "task": task,
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> GraphicDesignOutput:
        campaign_name = plan.get("campaign_name", "Campaign")
        company_name = plan.get("company_name", "")
        value_proposition = plan.get("value_proposition", "")
        campaign_goal = plan.get("campaign_goal", "brand awareness")
        platforms = plan.get("platforms", list(_DEFAULT_PLATFORMS))
        brand_context = plan.get("brand_context", "")

        data_sources: list[str] = []

        # Inject knowledge pack (Rule 6 / Rule 7)
        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        if _knowledge_ctx:
            data_sources.append("KnowledgeBase")

        # Build platform guidance for the copy generation prompt
        platform_specs = []
        for platform in platforms:
            cfg = _PLATFORM_CONFIG[platform]
            platform_specs.append(
                f"- {platform}: tone={cfg['copy_tone']}, "
                f"length={cfg['copy_length']}, "
                f"hashtags={cfg['hashtag_count']}"
            )
        platform_guidance = "\n".join(platform_specs)

        copy_prompt = (
            f"{_knowledge_header}"
            f"Generate social media copy and DALL-E image prompts for a {campaign_goal} campaign.\n\n"
            f"Company: {company_name}\n"
            f"Industry: {plan.get('industry', '')}\n"
            f"Value Proposition: {value_proposition}\n"
            f"Brand Context: {brand_context}\n\n"
            f"Generate for these platforms:\n{platform_guidance}\n\n"
            "For each platform return:\n"
            "- copy_text: platform-native post copy (no placeholders)\n"
            "- hashtags: platform-appropriate hashtag list\n"
            "- call_to_action: short CTA phrase\n"
            "- image_prompt: detailed DALL-E 3 prompt for a professional Singapore B2B visual. "
            "NO text overlays in the image — copy is added separately. "
            "Be specific about composition, lighting, and mood."
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": copy_prompt},
        ]

        # Structured LLM call for all platform copy in one shot
        all_copy = await self._complete_structured(
            response_model=_AllPlatformCopy,
            messages=messages,
        )
        data_sources.append("GPT-4o (social copy generation)")

        # Index copy specs by platform for lookup
        copy_by_platform: dict[str, _PlatformCopySpec] = {
            spec.platform.lower(): spec for spec in all_copy.platforms
        }

        # Generate images concurrently — one per platform
        image_tasks = []
        ordered_platforms: list[str] = []
        for platform in platforms:
            spec = copy_by_platform.get(platform)
            image_prompt = spec.image_prompt if spec and spec.image_prompt else (
                f"Professional {platform} marketing visual for Singapore B2B company "
                f"in {plan.get('industry', 'technology')} sector. {brand_context}"
            )
            dalle_platform_key = _PLATFORM_CONFIG[platform]["dalle_platform"]

            if self._dalle.is_configured:
                image_tasks.append(
                    self._dalle.generate_image(
                        prompt=image_prompt,
                        platform=dalle_platform_key,
                        quality="standard",
                        style="natural",
                    )
                )
            else:
                image_tasks.append(self._mock_image_result(platform))
            ordered_platforms.append(platform)

        image_results = await asyncio.gather(*image_tasks, return_exceptions=True)

        dalle_success = 0
        creatives: list[PlatformCreative] = []
        for platform, image_result in zip(ordered_platforms, image_results, strict=False):
            spec = copy_by_platform.get(platform)
            cfg = _PLATFORM_CONFIG[platform]

            image_url = ""
            image_local_path = ""
            image_prompt_used = spec.image_prompt if spec else ""

            if isinstance(image_result, dict) and not image_result.get("error"):
                image_url = image_result.get("url", "")
                image_local_path = image_result.get("local_path", "")
                dalle_success += 1
            elif isinstance(image_result, Exception):
                self._logger.warning(
                    "graphic_image_generation_failed",
                    platform=platform,
                    error=str(image_result),
                )

            creatives.append(PlatformCreative(
                platform=platform,
                image_url=image_url,
                image_local_path=image_local_path,
                image_prompt=image_prompt_used,
                copy_text=spec.copy_text if spec else "",
                hashtags=spec.hashtags if spec else [],
                call_to_action=spec.call_to_action if spec else "",
                dimensions=cfg["dimensions"],
            ))

        if dalle_success > 0:
            data_sources.append(f"DALL-E 3 ({dalle_success} images)")
        elif self._dalle.is_configured:
            self._logger.warning("graphic_no_images_generated")

        return GraphicDesignOutput(
            campaign_name=campaign_name,
            brand_context=brand_context,
            creatives=creatives,
            platforms_covered=[c.platform for c in creatives],
            confidence=0.0,  # Set by _check
            data_sources_used=list(set(data_sources)),
        )

    async def _mock_image_result(self, platform: str) -> dict[str, Any]:
        """Return an empty result when DALL-E is not configured (no API key)."""
        return {"url": "", "local_path": "", "error": "dalle_not_configured"}

    async def _check(self, result: GraphicDesignOutput) -> float:
        score = 0.20  # Base — must earn the rest from data quality

        if not result.creatives:
            return score

        # Images generated successfully (at least one real URL)
        images_with_url = [c for c in result.creatives if c.image_url]
        if images_with_url:
            # Scale: partial credit for partial coverage
            image_fraction = len(images_with_url) / len(result.creatives)
            score += 0.25 * image_fraction

        # Copy has a CTA for every creative
        creatives_with_cta = [c for c in result.creatives if c.call_to_action]
        if creatives_with_cta:
            cta_fraction = len(creatives_with_cta) / len(result.creatives)
            score += 0.15 * cta_fraction

        # Hashtags present for every creative
        creatives_with_hashtags = [c for c in result.creatives if c.hashtags]
        if creatives_with_hashtags:
            hashtag_fraction = len(creatives_with_hashtags) / len(result.creatives)
            score += 0.10 * hashtag_fraction

        # Copy text is non-empty for every creative
        creatives_with_copy = [c for c in result.creatives if c.copy_text]
        if creatives_with_copy:
            copy_fraction = len(creatives_with_copy) / len(result.creatives)
            score += 0.15 * copy_fraction

        # Correct number of platforms covered
        expected_platforms = len(result.platforms_covered)
        actual_platforms = len([c for c in result.creatives if c.platform in result.platforms_covered])
        if expected_platforms > 0 and actual_platforms >= expected_platforms:
            score += 0.10

        # Knowledge pack was loaded and injected
        if getattr(self, "_knowledge_pack", {}).get("formatted_injection"):
            score += 0.05

        return min(score, 1.0)

    async def _act(self, result: GraphicDesignOutput, confidence: float) -> GraphicDesignOutput:
        result.confidence = confidence

        # Publish CREATIVE_READY to the bus
        if self._bus is not None:
            try:
                creatives_summary = [
                    {
                        "platform": c.platform,
                        "has_image": bool(c.image_url),
                        "has_copy": bool(c.copy_text),
                        "cta": c.call_to_action,
                        "hashtags_count": len(c.hashtags),
                        "dimensions": c.dimensions,
                    }
                    for c in result.creatives
                ]
                await self._bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.CREATIVE_READY,
                    title=f"Graphics ready: {result.campaign_name} ({len(result.creatives)} platforms)",
                    content={
                        "creative_type": "social_graphics",
                        "campaign_name": result.campaign_name,
                        "platforms_covered": result.platforms_covered,
                        "creatives_summary": creatives_summary,
                        "data_sources_used": result.data_sources_used,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
                self._logger.info(
                    "graphic_creative_ready_published",
                    campaign=result.campaign_name,
                    platforms=result.platforms_covered,
                    confidence=round(confidence, 3),
                )
            except Exception as e:
                self._logger.warning("graphic_bus_publish_failed", error=str(e))

        return result
