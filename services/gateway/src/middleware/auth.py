"""Authentication middleware for GTM Advisor API.

Sets user information on request.state for use by other middleware and endpoints.
Uses Redis-backed caching for user lookups with proper error logging.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from packages.database.src.models import SubscriptionTier
from packages.database.src.models import User as DBUser
from packages.database.src.session import async_session_factory

from ..auth.dependencies import db_user_to_api_user
from ..auth.models import User
from ..auth.utils import decode_token, is_token_blacklisted
from ..cache import INACTIVE_MARKER, get_user_cache, mask_email

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts user from JWT token and sets on request.state.

    This allows other components (like rate limiting) to access user info
    without requiring authentication to be enforced on every endpoint.

    Uses Redis-backed caching to reduce database queries.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")

        user: User | None = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            user = await self._get_user_from_token(token, request.url.path)

        # Set user on request state (may be None for unauthenticated requests)
        request.state.user = user

        # Continue processing request
        response = await call_next(request)

        return response

    async def _get_user_from_token(self, token: str, path: str) -> User | None:
        """Extract and validate user from JWT token.

        Uses caching to reduce database queries for repeated requests.
        Cache stores only non-PII data needed for authorization.

        Args:
            token: The JWT access token
            path: Request path for logging context

        Returns:
            User object if valid, None otherwise
        """
        try:
            # Check if token is blacklisted (logged out)
            if await is_token_blacklisted(token):
                logger.debug("Blacklisted token for path: %s", path)
                return None

            token_data = decode_token(token, token_type="access")

            if token_data is None:
                logger.debug("Invalid or expired token for path: %s", path)
                return None

            user_id_str = str(token_data.user_id)

            # Check cache first
            cache = None
            try:
                cache = get_user_cache()
                cached_data = await cache.get(user_id_str)

                if cached_data is not None:
                    # Check if user was marked as inactive in cache
                    if cached_data.get(INACTIVE_MARKER):
                        logger.debug("Cached inactive user: %s", user_id_str[:8])
                        return None

                    logger.debug("User %s loaded from cache", user_id_str[:8])

                    # Reconstruct User with proper types
                    # Note: email and full_name must come from DB on cache miss
                    # Cache only stores authorization-relevant data
                    return self._user_from_cache(cached_data, token_data.email)

            except RuntimeError:
                # Cache not initialized - continue without cache
                logger.warning("Cache not initialized, querying database directly")

            # Look up user in database
            return await self._load_user_from_db(token_data.user_id, user_id_str, cache)

        except SQLAlchemyError as e:
            logger.error(
                "Database error during auth middleware lookup: %s",
                str(e),
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                "Unexpected error in auth middleware: %s",
                str(e),
                exc_info=True,
            )
            return None

    def _user_from_cache(self, cached_data: dict, email_from_token: str) -> User:
        """Reconstruct User object from cached data.

        Args:
            cached_data: Data from cache (no PII)
            email_from_token: Email from JWT token for User object

        Returns:
            User object
        """
        # Convert tier string back to enum
        tier_str = cached_data.get("tier", "free")
        try:
            tier = SubscriptionTier(tier_str)
        except ValueError:
            tier = SubscriptionTier.FREE

        # Convert UUID string back to UUID
        user_id = cached_data.get("id")
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        return User(
            id=user_id,
            email=email_from_token,  # From token, not cached
            full_name=cached_data.get("full_name", ""),
            company_name=cached_data.get("company_name"),
            tier=tier,
            is_active=cached_data.get("is_active", True),
            created_at=cached_data.get("created_at"),
            daily_requests=cached_data.get("daily_requests", 0),
            last_request_date=cached_data.get("last_request_date"),
        )

    async def _load_user_from_db(
        self,
        user_id: UUID,
        user_id_str: str,
        cache,
    ) -> User | None:
        """Load user from database and optionally cache.

        Args:
            user_id: User UUID
            user_id_str: String version for cache key
            cache: UserCache instance or None

        Returns:
            User object or None if not found/inactive
        """
        async with async_session_factory() as db:
            result = await db.execute(select(DBUser).where(DBUser.id == user_id))
            db_user = result.scalar_one_or_none()

            if db_user is None:
                logger.warning(
                    "Token contains non-existent user_id: %s",
                    user_id_str[:8],
                )
                return None

            if not db_user.is_active:
                logger.info(
                    "Inactive user attempted access: %s",
                    mask_email(db_user.email),
                )
                # Cache the inactive status to avoid repeated DB lookups
                if cache:
                    await cache.set(user_id_str, {INACTIVE_MARKER: True})
                return None

            # Use single source of truth for DBUser → User transformation
            user = db_user_to_api_user(db_user)

            # Cache user data (no PII - email not stored)
            if cache:
                await cache.set(
                    user_id_str,
                    {
                        "id": str(db_user.id),
                        "full_name": db_user.full_name,
                        "company_name": db_user.company_name,
                        "tier": db_user.tier.value
                        if hasattr(db_user.tier, "value")
                        else str(db_user.tier),
                        "is_active": db_user.is_active,
                        "created_at": db_user.created_at.isoformat()
                        if db_user.created_at
                        else None,
                        "daily_requests": db_user.daily_requests or 0,
                        "last_request_date": db_user.last_request_date.isoformat()
                        if db_user.last_request_date
                        else None,
                    },
                )
                logger.debug("User %s cached from database", user_id_str[:8])

            return user


async def invalidate_user_cache(user_id: str) -> None:
    """Invalidate a user's cache entry.

    Call this when user data changes (tier upgrade, deactivation, etc.).

    Args:
        user_id: The user ID to invalidate
    """
    try:
        cache = get_user_cache()
        await cache.invalidate(user_id)
    except RuntimeError:
        # Cache not initialized
        pass
