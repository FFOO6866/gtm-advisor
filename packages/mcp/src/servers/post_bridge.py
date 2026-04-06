"""Post Bridge MCP Server — Multi-platform social media publishing.

Publishes content to 9 social media platforms via a single API:
Instagram, TikTok, YouTube, X, LinkedIn, Facebook, Pinterest, Threads, Bluesky.

Used by the Social Publisher agent for campaign distribution.

API: https://www.post-bridge.com/agents
Cost: $14/mo (Starter + API add-on)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class PostBridgeMCPServer:
    """MCP Server for Post Bridge social media publishing.

    Single API call publishes to up to 9 platforms with per-platform
    caption overrides and media customization.

    Requires: POST_BRIDGE_API_KEY environment variable

    Example:
        server = PostBridgeMCPServer.from_env()
        result = await server.create_post(
            platforms=["linkedin", "x"],
            caption="Exciting news from our team...",
            media_urls=["https://example.com/image.png"],
        )
    """

    BASE_URL = "https://api.post-bridge.com/v1"

    # Supported platforms
    PLATFORMS = [
        "instagram", "tiktok", "youtube", "x", "linkedin",
        "facebook", "pinterest", "threads", "bluesky",
    ]

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("POST_BRIDGE_API_KEY")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        self._logger = logger.bind(server="post_bridge")

    @classmethod
    def from_env(cls) -> PostBridgeMCPServer:
        return cls()

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def create_post(
        self,
        platforms: list[str],
        caption: str,
        media_urls: list[str] | None = None,
        platform_captions: dict[str, str] | None = None,
        schedule_time: str | None = None,
    ) -> dict[str, Any]:
        """Publish or schedule a post to multiple platforms.

        Args:
            platforms: List of platform names (e.g. ["linkedin", "x"])
            caption: Default caption for all platforms
            media_urls: Optional list of image/video URLs to attach
            platform_captions: Optional per-platform caption overrides
            schedule_time: ISO 8601 timestamp for scheduled posting

        Returns:
            Dict with per-platform results: {platform: {post_id, status, error}}
        """
        if not self.is_configured:
            self._logger.warning("post_bridge_not_configured")
            return {"error": "POST_BRIDGE_API_KEY not configured"}

        # Validate platforms
        valid_platforms = [p for p in platforms if p in self.PLATFORMS]
        if not valid_platforms:
            return {"error": f"No valid platforms. Supported: {', '.join(self.PLATFORMS)}"}

        payload: dict[str, Any] = {
            "platforms": valid_platforms,
            "caption": caption,
        }

        if media_urls:
            payload["media_urls"] = media_urls

        if platform_captions:
            payload["platform_captions"] = platform_captions

        if schedule_time:
            payload["schedule_time"] = schedule_time

        try:
            response = await self._client.post("/posts", json=payload)

            if response.status_code in (200, 201, 202):
                data = response.json()
                self._logger.info(
                    "post_bridge_post_created",
                    platforms=valid_platforms,
                    scheduled=bool(schedule_time),
                )
                return data

            error_text = response.text[:300]
            self._logger.warning(
                "post_bridge_post_failed",
                status=response.status_code,
                error=error_text,
            )
            return {"error": f"Post Bridge API error {response.status_code}: {error_text}"}

        except Exception as e:
            self._logger.error("post_bridge_post_error", error=str(e))
            return {"error": str(e)}

    async def get_post_analytics(self, post_id: str) -> dict[str, Any]:
        """Get engagement analytics for a published post.

        Args:
            post_id: Post Bridge post ID

        Returns:
            Dict with: impressions, likes, comments, shares, clicks (per platform)
        """
        if not self.is_configured:
            return {"error": "POST_BRIDGE_API_KEY not configured"}

        try:
            response = await self._client.get(f"/posts/{post_id}/analytics")

            if response.status_code == 200:
                return response.json()

            return {"error": f"Analytics fetch failed: {response.status_code}"}

        except Exception as e:
            self._logger.error("post_bridge_analytics_error", post_id=post_id, error=str(e))
            return {"error": str(e)}

    async def list_accounts(self) -> list[dict[str, Any]]:
        """List connected social media accounts.

        Returns:
            List of account dicts with: platform, username, status
        """
        if not self.is_configured:
            return []

        try:
            response = await self._client.get("/accounts")
            if response.status_code == 200:
                return response.json().get("accounts", [])
            return []
        except Exception as e:
            self._logger.error("post_bridge_list_accounts_error", error=str(e))
            return []

    async def delete_post(self, post_id: str) -> bool:
        """Delete a scheduled or published post.

        Args:
            post_id: Post Bridge post ID

        Returns:
            True if deleted successfully
        """
        if not self.is_configured:
            return False

        try:
            response = await self._client.delete(f"/posts/{post_id}")
            return response.status_code in (200, 204)
        except Exception as e:
            self._logger.error("post_bridge_delete_error", post_id=post_id, error=str(e))
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
