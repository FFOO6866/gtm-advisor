"""DALL-E MCP Server — AI image generation for marketing creative.

Generates social media graphics, email headers, ad banners via OpenAI's
DALL-E 3 API. Used by the Graphic Designer and EDM Designer agents.

API Documentation: https://platform.openai.com/docs/api-reference/images
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Image output directory
_IMAGES_DIR = Path(__file__).resolve().parents[4] / "data" / "creative_assets"


class DalleMCPServer:
    """MCP Server for DALL-E image generation.

    Generates images via OpenAI's Images API for campaign creative:
    - Social media graphics (LinkedIn, Instagram, Facebook, X)
    - Email header/hero images
    - Ad banners

    Requires: OPENAI_API_KEY environment variable (same key as LLM)

    Example:
        server = DalleMCPServer.from_env()
        result = await server.generate_image(
            prompt="Professional business meeting in Singapore skyline...",
            size="1200x627",  # LinkedIn link share
        )
    """

    BASE_URL = "https://api.openai.com/v1"

    # Platform-specific dimensions
    PLATFORM_SIZES = {
        "linkedin_share": "1792x1024",    # Closest DALL-E size to 1200x627
        "linkedin_square": "1024x1024",   # Square post
        "instagram_feed": "1024x1024",    # Square feed
        "instagram_story": "1024x1792",   # Vertical story
        "facebook_share": "1792x1024",    # Link share
        "x_post": "1792x1024",            # Tweet image
        "email_header": "1792x1024",      # Email hero
        "ad_banner": "1792x1024",         # Display ad
    }

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,  # Image generation can be slow
        )
        self._logger = logger.bind(server="dalle")
        _IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> DalleMCPServer:
        return cls()

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def generate_image(
        self,
        prompt: str,
        platform: str = "linkedin_share",
        quality: str = "standard",
        style: str = "natural",
    ) -> dict[str, Any]:
        """Generate an image using DALL-E 3.

        DALL-E 3 only supports n=1, so this always generates a single image.

        Args:
            prompt: Description of desired image
            platform: Target platform (determines dimensions). One of PLATFORM_SIZES keys.
            quality: "standard" or "hd"
            style: "natural" or "vivid"

        Returns:
            Dict with: url (temporary OpenAI URL), local_path (saved file), revised_prompt
        """
        if not self.is_configured:
            self._logger.warning("dalle_not_configured")
            return {"error": "OPENAI_API_KEY not configured"}

        size = self.PLATFORM_SIZES.get(platform, "1024x1024")

        try:
            response = await self._client.post(
                "/images/generations",
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,  # DALL-E 3 only supports n=1
                    "size": size,
                    "quality": quality,
                    "style": style,
                    "response_format": "url",
                },
            )

            if response.status_code != 200:
                error_text = response.text[:300]
                self._logger.warning("dalle_generation_failed", status=response.status_code, error=error_text)
                return {"error": f"DALL-E API error {response.status_code}: {error_text}"}

            data = response.json()
            image_data = data.get("data", [{}])[0]
            image_url = image_data.get("url", "")
            revised_prompt = image_data.get("revised_prompt", "")

            # Download and save locally
            local_path = ""
            if image_url:
                local_path = await self._download_image(image_url, platform)

            self._logger.info(
                "dalle_image_generated",
                platform=platform,
                size=size,
                quality=quality,
                local_path=local_path,
            )

            return {
                "url": image_url,
                "local_path": local_path,
                "revised_prompt": revised_prompt,
                "size": size,
                "platform": platform,
                "model": "dall-e-3",
            }

        except Exception as e:
            self._logger.error("dalle_generation_error", error=str(e))
            return {"error": str(e)}

    async def generate_campaign_visuals(
        self,
        campaign_brief: str,
        brand_context: str,
        platforms: list[str],
        style: str = "natural",
    ) -> list[dict[str, Any]]:
        """Generate images for multiple platforms from a single campaign brief.

        Args:
            campaign_brief: Campaign messaging / value prop
            brand_context: Company name, industry, brand tone
            platforms: List of platform keys (e.g. ["linkedin_share", "instagram_feed"])
            style: "natural" or "vivid"

        Returns:
            List of generation results, one per platform
        """
        results = []
        for platform in platforms:
            # Enhance prompt with brand context and platform-specific guidance
            enhanced_prompt = self._build_platform_prompt(campaign_brief, brand_context, platform)
            result = await self.generate_image(
                prompt=enhanced_prompt,
                platform=platform,
                style=style,
            )
            result["platform"] = platform
            results.append(result)
        return results

    def _build_platform_prompt(self, brief: str, brand_context: str, platform: str) -> str:
        """Build a platform-aware DALL-E prompt."""
        platform_guidance = {
            "linkedin_share": "Professional, corporate style. Clean composition suitable for B2B LinkedIn posts. No text overlay.",
            "linkedin_square": "Professional square format for LinkedIn carousel. Clean, minimal design.",
            "instagram_feed": "Vibrant, eye-catching square format for Instagram. Modern design aesthetic.",
            "instagram_story": "Vertical format for Instagram story. Bold, engaging visual.",
            "facebook_share": "Engaging visual for Facebook link share. Clear focal point.",
            "x_post": "Impactful widescreen image for X/Twitter. Clean, shareable.",
            "email_header": "Professional email header image. Clean, brand-aligned. No text — text will be overlaid in HTML.",
            "ad_banner": "Display ad visual. Clean product/concept imagery. No text — copy added separately.",
        }

        guidance = platform_guidance.get(platform, "Professional marketing image.")

        return (
            f"{guidance}\n\n"
            f"Brand: {brand_context}\n"
            f"Campaign: {brief}\n\n"
            "Style: Professional, modern, suitable for Singapore/APAC B2B marketing. "
            "High quality photography or illustration. Do NOT include any text, "
            "logos, or watermarks in the image."
        )

    async def _download_image(self, url: str, platform: str) -> str:
        """Download image from OpenAI URL and save locally."""
        import uuid as _uuid

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    filename = f"{platform}_{_uuid.uuid4().hex[:8]}.png"
                    local_path = _IMAGES_DIR / filename
                    local_path.write_bytes(response.content)
                    return str(local_path)
        except Exception as e:
            self._logger.warning("dalle_download_failed", error=str(e))
        return ""

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
