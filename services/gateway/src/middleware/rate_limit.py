"""Rate limiting middleware for GTM Advisor API.

Implements tier-based rate limiting that respects subscription levels.
Uses Redis for distributed rate limiting in production.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from packages.core.src.config import Environment, get_config

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Key prefix for rate limiter to avoid conflicts with other Redis data
RATE_LIMIT_KEY_PREFIX = "gtm:ratelimit:"


def _get_tier_name(user: object | None) -> str:
    """Extract tier name from user object.

    Args:
        user: User object with tier attribute, or None

    Returns:
        Lowercase tier name (free, tier1, tier2)
    """
    if user is None:
        return "free"

    tier = getattr(user, "tier", "free")

    if isinstance(tier, str):
        return tier.lower()

    # Handle enum types
    if hasattr(tier, "value"):
        return str(tier.value).lower()

    return "free"


def get_user_tier_key(request: Request) -> str:
    """Get rate limit key based on user's subscription tier.

    Returns a key in format: "prefix:user:user_id" or "prefix:ip:address" for anonymous.
    """
    user = getattr(request.state, "user", None)

    if user:
        user_id = getattr(user, "id", None)
        if user_id:
            return f"{RATE_LIMIT_KEY_PREFIX}user:{user_id}"

    ip = get_remote_address(request)
    return f"{RATE_LIMIT_KEY_PREFIX}ip:{ip}"


def get_rate_limit_for_request(request: Request) -> str:
    """Get the appropriate rate limit string for a request.

    Reads limits from configuration at request time.
    """
    config = get_config()
    user = getattr(request.state, "user", None)
    tier_name = _get_tier_name(user)

    limit = config.get_rate_limit_requests(tier_name)
    return f"{limit}/day"


def get_analysis_limit_for_request(request: Request) -> str:
    """Get analysis-specific rate limit for a request.

    Reads limits from configuration at request time.
    """
    config = get_config()
    user = getattr(request.state, "user", None)
    tier_name = _get_tier_name(user)

    limit = config.get_rate_limit_analyses(tier_name)
    return f"{limit}/day"


# Lazy limiter initialization
_limiter: Limiter | None = None


def _get_storage_uri() -> str:
    """Get rate limiter storage URI with proper validation."""
    config = get_config()

    if config.redis_url:
        logger.info("Rate limiter using Redis backend")
        return config.redis_url

    if config.environment == Environment.PRODUCTION:
        raise RuntimeError(
            "Redis URL (GTM_REDIS_URL) is required in production for distributed rate limiting. "
            "Set GTM_REDIS_URL environment variable to a valid Redis connection string."
        )

    logger.warning(
        "Rate limiter using in-memory storage. This is only suitable for development. "
        "Set GTM_REDIS_URL for production deployments."
    )
    return "memory://"


def get_limiter() -> Limiter:
    """Get or create the rate limiter instance.

    Creates limiter lazily on first access, allowing config to be loaded first.
    """
    global _limiter

    if _limiter is None:
        config = get_config()
        storage_uri = _get_storage_uri()
        default_limit = f"{config.rate_limit_free_requests}/day"

        _limiter = Limiter(
            key_func=get_user_tier_key,
            default_limits=[default_limit],
            storage_uri=storage_uri,
            strategy="fixed-window",
        )
        logger.info("Rate limiter initialized with default limit: %s", default_limit)

    return _limiter


class _LimiterProxy:
    """Proxy class that delegates to the lazily-initialized limiter."""

    def limit(self, *args, **kwargs):
        return get_limiter().limit(*args, **kwargs)

    def shared_limit(self, *args, **kwargs):
        return get_limiter().shared_limit(*args, **kwargs)

    @property
    def enabled(self):
        return get_limiter().enabled

    def __getattr__(self, name):
        return getattr(get_limiter(), name)


# Export a proxy that initializes limiter on first use
limiter = _LimiterProxy()


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    user = getattr(request.state, "user", None)
    tier_name = _get_tier_name(user)

    raise HTTPException(
        status_code=429,
        detail={
            "error": "RateLimitExceeded",
            "message": f"Rate limit exceeded for {tier_name} tier. Please upgrade your subscription for higher limits.",
            "retry_after": exc.detail,
        },
    )


def dynamic_limit():
    """Rate limit based on user's subscription tier.

    Reads limits from config at request time.

    Usage:
        @router.get("/endpoint")
        @dynamic_limit()
        async def endpoint():
            ...
    """
    return get_limiter().limit(get_rate_limit_for_request)


def analysis_limit():
    """Rate limit for expensive analysis operations.

    Reads limits from config at request time.

    Usage:
        @router.post("/analysis/start")
        @analysis_limit()
        async def start_analysis():
            ...
    """
    return get_limiter().limit(get_analysis_limit_for_request)


def free_tier_limit():
    """Rate limit decorator for free tier endpoints."""

    def _get_free_limit(_request: Request) -> str:
        config = get_config()
        return f"{config.rate_limit_free_requests}/day"

    return get_limiter().limit(_get_free_limit)


def tier1_limit():
    """Rate limit decorator for tier1 endpoints."""

    def _get_tier1_limit(_request: Request) -> str:
        config = get_config()
        return f"{config.rate_limit_tier1_requests}/day"

    return get_limiter().limit(_get_tier1_limit)


def tier2_limit():
    """Rate limit decorator for tier2 endpoints."""

    def _get_tier2_limit(_request: Request) -> str:
        config = get_config()
        return f"{config.rate_limit_tier2_requests}/day"

    return get_limiter().limit(_get_tier2_limit)
