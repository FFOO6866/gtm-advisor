"""Social Publisher Agent — publishes approved creative assets to social media platforms.

An execution-tier agent (not analysis). Given a list of approved content assets,
it formats them per-platform and publishes via the Post Bridge MCP server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.post_bridge import PostBridgeMCPServer

# Maximum caption lengths per platform — enforced before sending.
_PLATFORM_CHAR_LIMITS: dict[str, int] = {
    "x": 280,
    "instagram": 2200,
    "linkedin": 3000,
    "facebook": 63206,
    "threads": 500,
    "bluesky": 300,
    "pinterest": 500,
    "tiktok": 2200,
    "youtube": 5000,
}

# Hashtag templates appended for platforms where hashtags aid discoverability.
_PLATFORM_HASHTAG_SUFFIX: dict[str, str] = {
    "linkedin": "\n\n#GTM #B2BSales #SingaporeSME",
    "instagram": "\n\n#GTM #B2B #SingaporeStartup #SME",
    "x": " #GTM #B2B",
    "threads": " #GTM #B2B",
}


class PublishedPost(BaseModel):
    """A post published to a specific platform."""

    platform: str = Field(...)
    post_id: str = Field(default="")
    status: str = Field(default="pending")  # pending, published, failed, scheduled
    caption: str = Field(default="")
    media_url: str = Field(default="")
    error: str = Field(default="")
    published_at: str = Field(default="")


class PublishOutput(BaseModel):
    """Complete publishing output."""

    campaign_name: str = Field(default="")
    posts: list[PublishedPost] = Field(default_factory=list)
    total_published: int = Field(default=0)
    total_failed: int = Field(default=0)
    platforms_reached: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)


class SocialPublisherAgent(BaseGTMAgent[PublishOutput]):
    """Publishes approved creative assets to social media platforms.

    Execution agent — not an analysis agent. Reads approved content from context
    (or from CONTENT_APPROVED bus events) and distributes via Post Bridge MCP.
    """

    def __init__(self) -> None:
        super().__init__(
            name="social-publisher",
            description=(
                "Publishes approved creative assets to social media platforms. "
                "Handles per-platform formatting, character limits, and hashtag injection."
            ),
            result_type=PublishOutput,
            min_confidence=0.60,
            max_iterations=1,  # Never retry live publishes
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="social-publish",
                    description="Publish formatted content to social platforms via Post Bridge",
                ),
            ],
        )
        self._post_bridge = PostBridgeMCPServer.from_env()
        self._agent_bus: AgentBus | None = get_agent_bus()
        self._analysis_id: Any = None
        self._knowledge_pack: dict = {}
        self._approved_assets: list[dict[str, Any]] = []  # Populated by CONTENT_APPROVED bus events
        self._campaign_context: dict[str, Any] | None = None  # Populated by CAMPAIGN_READY bus events

        try:
            if self._agent_bus is not None:
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.CONTENT_APPROVED,
                    handler=self._on_content_approved,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.CAMPAIGN_READY,
                    handler=self._on_campaign_ready,
                )
        except Exception:
            pass

    async def _on_content_approved(self, message: AgentMessage) -> None:
        """Cache approved creative assets from upstream (e.g. graphic-designer or content review)."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        content = message.content
        # Accept both a single asset dict and a list of assets in one message.
        if isinstance(content, list):
            self._approved_assets.extend(content)
        elif isinstance(content, dict):
            self._approved_assets.append(content)
        self._logger.debug(
            "social_publisher_received_approved_content",
            total_assets=len(self._approved_assets),
        )

    async def _on_campaign_ready(self, message: AgentMessage) -> None:
        """Cache campaign context for channel alignment."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        self._campaign_context = message.content
        self._logger.debug(
            "social_publisher_received_campaign_context",
            channels=self._campaign_context.get("channels", []),
        )

    def get_system_prompt(self) -> str:
        return """You are a social media publishing agent. Your job is to adapt approved
copy to the specific requirements of each platform.

Rules:
- LinkedIn: Professional tone, up to 3000 characters, include hashtags
- X (Twitter): Max 280 characters, concise and punchy, minimal hashtags
- Instagram: Visual storytelling focus, CTA referencing link in bio, include hashtags
- Facebook: Casual and engaging, include full link, conversational
- Threads: Short and conversational, max 500 characters
- Bluesky: Max 300 characters, community-oriented tone
- Never change the core message — adapt format only
- Never invent claims not present in the approved copy"""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Reset per-run state to prevent cross-analysis contamination.
        self._approved_assets.clear()
        self._campaign_context = None

        # Load domain knowledge pack for social publishing / content marketing.
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="social-publisher",
                task_context=task,
            )
        except Exception as _e:
            self._logger.debug("knowledge_pack_load_failed", error=str(_e))

        # Backfill from bus history — catches events published before subscription.
        if self._agent_bus is not None:
            approved_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.CONTENT_APPROVED,
                limit=50,
            )
            for msg in approved_history:
                content = msg.content
                if isinstance(content, list):
                    for asset in content:
                        if asset not in self._approved_assets:
                            self._approved_assets.append(asset)
                elif isinstance(content, dict) and content not in self._approved_assets:
                    self._approved_assets.append(content)

            campaign_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.CAMPAIGN_READY,
                limit=1,
            )
            if campaign_history and self._campaign_context is None:
                self._campaign_context = campaign_history[0].content

        # Assets can also be passed directly in context (e.g. from the gateway).
        direct_assets: list[dict[str, Any]] = context.get("approved_assets", [])
        for asset in direct_assets:
            if asset not in self._approved_assets:
                self._approved_assets.append(asset)

        # Determine which platforms to publish to.
        target_platforms: list[str] = context.get("platforms", [])
        if not target_platforms and self._campaign_context:
            # Infer from campaign channels — map channel names to Post Bridge platform slugs.
            campaign_channels: list[str] = self._campaign_context.get("channels", [])
            channel_to_platform = {
                "linkedin": "linkedin",
                "twitter": "x",
                "x": "x",
                "instagram": "instagram",
                "facebook": "facebook",
                "threads": "threads",
                "bluesky": "bluesky",
                "tiktok": "tiktok",
                "youtube": "youtube",
                "pinterest": "pinterest",
            }
            for ch in campaign_channels:
                mapped = channel_to_platform.get(ch.lower())
                if mapped and mapped not in target_platforms:
                    target_platforms.append(mapped)

        return {
            "campaign_name": context.get("campaign_name", ""),
            "approved_assets": self._approved_assets,
            "target_platforms": target_platforms,
            "schedule_time": context.get("schedule_time"),  # ISO 8601 or None for immediate
        }

    def _format_caption_for_platform(self, platform: str, base_copy: str, cta: str) -> str:
        """Apply platform-specific formatting to the base copy text."""
        # Append CTA if provided and not already in the copy.
        if cta and cta not in base_copy:
            if platform == "instagram":
                caption = f"{base_copy}\n\n{cta}\n\n(Link in bio)"
            elif platform in ("facebook", "linkedin"):
                caption = f"{base_copy}\n\n{cta}"
            else:
                # X, Threads, Bluesky — space-constrained, keep CTA short
                short_cta = cta.split(".")[0] if "." in cta else cta
                short_cta = short_cta[:60]
                caption = f"{base_copy} {short_cta}"
        else:
            caption = base_copy

        # Append platform hashtags.
        hashtag_suffix = _PLATFORM_HASHTAG_SUFFIX.get(platform, "")
        if hashtag_suffix:
            caption = caption + hashtag_suffix

        # Enforce character limit — hard-truncate with ellipsis.
        limit = _PLATFORM_CHAR_LIMITS.get(platform, 3000)
        if len(caption) > limit:
            caption = caption[: limit - 3] + "..."

        return caption

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> PublishOutput:
        campaign_name: str = plan.get("campaign_name", "")
        approved_assets: list[dict[str, Any]] = plan.get("approved_assets", [])
        target_platforms: list[str] = plan.get("target_platforms", [])
        schedule_time: str | None = plan.get("schedule_time")

        if not approved_assets:
            self._logger.warning("social_publisher_no_assets")
            # Return with confidence high enough to avoid MaxIterationsExceededError.
            # No-op publish is a valid outcome (nothing to publish = success).
            return PublishOutput(
                campaign_name=campaign_name,
                confidence=0.70,
                data_sources_used=["no_assets_to_publish"],
            )

        posts: list[PublishedPost] = []
        now_iso = datetime.now(UTC).isoformat()

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""

        for asset in approved_assets:
            # Each asset dict must specify at least: platform, copy_text.
            # Optionally: image_url, call_to_action, caption (pre-formatted override).
            asset_platform: str = asset.get("platform", "").lower()
            copy_text: str = asset.get("copy_text", asset.get("caption", ""))
            image_url: str = asset.get("image_url", asset.get("media_url", ""))
            cta: str = asset.get("call_to_action", "")

            # Resolve which platforms to post this asset to.
            # An asset may override target_platforms if it specifies its own platform.
            if asset_platform and asset_platform in PostBridgeMCPServer.PLATFORMS:
                platforms_for_asset = [asset_platform]
            elif target_platforms:
                platforms_for_asset = [p for p in target_platforms if p in PostBridgeMCPServer.PLATFORMS]
            else:
                # No explicit platform — skip and log.
                self._logger.warning(
                    "social_publisher_asset_no_platform",
                    copy_preview=copy_text[:60],
                )
                posts.append(
                    PublishedPost(
                        platform="unknown",
                        status="failed",
                        caption=copy_text,
                        error="No valid platform specified for asset",
                        published_at=now_iso,
                    )
                )
                continue

            if not copy_text:
                # Nothing to publish — use LLM to generate a caption from context.
                try:
                    messages = [
                        {"role": "system", "content": self.get_system_prompt()},
                        {
                            "role": "user",
                            "content": (
                                f"{_knowledge_header}Generate a short social media caption "
                                f"for platforms: {', '.join(platforms_for_asset)}.\n"
                                f"Campaign: {campaign_name}\n"
                                f"CTA: {cta or 'Learn more'}\n"
                                f"Return only the caption text, no preamble."
                            ),
                        },
                    ]
                    copy_text = await self._complete(messages)
                    copy_text = copy_text.strip() if isinstance(copy_text, str) else ""
                except Exception as gen_err:
                    self._logger.warning("caption_generation_failed", error=str(gen_err))
                    for plat in platforms_for_asset:
                        posts.append(
                            PublishedPost(
                                platform=plat,
                                status="failed",
                                error=f"Caption generation failed: {gen_err}",
                                published_at=now_iso,
                            )
                        )
                    continue

            # Build per-platform caption overrides.
            platform_captions: dict[str, str] = {}
            for plat in platforms_for_asset:
                platform_captions[plat] = self._format_caption_for_platform(plat, copy_text, cta)

            # Publish via Post Bridge — single API call covers all platforms.
            media_urls = [image_url] if image_url else None
            default_caption = platform_captions.get(platforms_for_asset[0], copy_text)

            api_result = await self._post_bridge.create_post(
                platforms=platforms_for_asset,
                caption=default_caption,
                media_urls=media_urls,
                platform_captions=platform_captions if len(platform_captions) > 1 else None,
                schedule_time=schedule_time,
            )

            # Parse per-platform results from the API response.
            if "error" in api_result:
                # Entire request failed — create a failed post entry per platform.
                for plat in platforms_for_asset:
                    posts.append(
                        PublishedPost(
                            platform=plat,
                            status="failed",
                            caption=platform_captions.get(plat, copy_text),
                            media_url=image_url,
                            error=api_result["error"],
                            published_at=now_iso,
                        )
                    )
            else:
                # Post Bridge returns a dict keyed by platform name.
                for plat in platforms_for_asset:
                    plat_result: dict[str, Any] = api_result.get(plat, {})
                    post_id: str = plat_result.get("post_id", plat_result.get("id", ""))
                    plat_status: str = plat_result.get("status", "published" if post_id else "failed")
                    plat_error: str = plat_result.get("error", "")
                    posts.append(
                        PublishedPost(
                            platform=plat,
                            post_id=post_id,
                            status=plat_status,
                            caption=platform_captions.get(plat, copy_text),
                            media_url=image_url,
                            error=plat_error,
                            published_at=now_iso,
                        )
                    )

        total_published = sum(1 for p in posts if p.status in ("published", "scheduled"))
        total_failed = sum(1 for p in posts if p.status == "failed")
        platforms_reached = list({p.platform for p in posts if p.status in ("published", "scheduled")})

        return PublishOutput(
            campaign_name=campaign_name,
            posts=posts,
            total_published=total_published,
            total_failed=total_failed,
            platforms_reached=platforms_reached,
            data_sources_used=["post_bridge"],
        )

    async def _check(self, result: PublishOutput) -> float:
        """Compute confidence from publishing data quality — base 0.2, earned via results."""
        score = 0.2  # base — must earn confidence from data

        if not result.posts:
            return score

        total_posts = len(result.posts)
        published_count = result.total_published
        failed_count = result.total_failed

        # +0.3 if all submitted posts were published without error
        if published_count > 0 and failed_count == 0:
            score += 0.30
        elif published_count > 0 and failed_count < published_count:
            # Partial success — partial credit proportional to success rate
            score += 0.30 * (published_count / total_posts)

        # +0.2 if all target platforms were reached (at least one published post per platform)
        target_platforms_from_plan: list[str] = []
        for post in result.posts:
            if post.platform not in target_platforms_from_plan:
                target_platforms_from_plan.append(post.platform)
        if target_platforms_from_plan and set(result.platforms_reached) >= set(target_platforms_from_plan):
            score += 0.20
        elif result.platforms_reached:
            score += 0.20 * (len(result.platforms_reached) / len(target_platforms_from_plan))

        # +0.2 if at least one post has a confirmed external post_id (delivery evidence)
        has_post_id = any(p.post_id for p in result.posts if p.status in ("published", "scheduled"))
        if has_post_id:
            score += 0.20

        # +0.1 if campaign_name is set (full context was provided)
        if result.campaign_name:
            score += 0.10

        return min(score, 1.0)

    async def _act(self, result: PublishOutput, confidence: float) -> PublishOutput:
        """Attach confidence to result and publish ENGAGEMENT_RECEIVED placeholder on the bus."""
        result.confidence = confidence

        if self._agent_bus is not None and result.total_published > 0:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.ENGAGEMENT_RECEIVED,
                    title=f"Published {result.total_published} post(s) for '{result.campaign_name}'",
                    content={
                        "campaign_name": result.campaign_name,
                        "total_published": result.total_published,
                        "total_failed": result.total_failed,
                        "platforms_reached": result.platforms_reached,
                        "post_ids": [p.post_id for p in result.posts if p.post_id],
                        "analysis_id": self._analysis_id,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.warning("engagement_received_publish_failed", error=str(e))

        return result
