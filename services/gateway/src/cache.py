"""Caching infrastructure for GTM Advisor Gateway.

Provides Redis-backed caching with in-memory fallback for development.
Used for user session data and other high-frequency lookups.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from packages.core.src.config import Environment, get_config

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Constants
CACHE_KEY_PREFIX = "gtm:user:"
INACTIVE_MARKER = "__inactive__"


class CacheBackend(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int) -> None:
        """Set value in cache with TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close cache connection."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if cache backend is healthy."""
        pass


class RedisCache(CacheBackend):
    """Redis-backed cache implementation with connection pooling and retry logic."""

    def __init__(self, redis_url: str, max_connections: int = 10, retry_attempts: int = 3):
        self._redis_url = redis_url
        self._max_connections = max_connections
        self._retry_attempts = retry_attempts
        self._client: Redis | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Redis:
        """Get or create Redis client with proper locking."""
        if self._client is not None:
            return self._client

        async with self._client_lock:
            # Double-check after acquiring lock
            if self._client is not None:
                return self._client

            from redis.asyncio import ConnectionPool, Redis

            pool = ConnectionPool.from_url(
                self._redis_url,
                max_connections=self._max_connections,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
            )
            self._client = Redis(connection_pool=pool)
            return self._client

    async def _execute_with_retry(self, operation: str, func, *args, **kwargs):
        """Execute Redis operation with retry logic."""
        last_error = None
        for attempt in range(self._retry_attempts):
            try:
                client = await self._get_client()
                return await func(client, *args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(
                    "Redis %s failed (attempt %d/%d): %s",
                    operation,
                    attempt + 1,
                    self._retry_attempts,
                    str(e),
                )
                # Reset client on connection errors to force reconnect
                if "connection" in str(e).lower() or "timeout" in str(e).lower():
                    async with self._client_lock:
                        if self._client is not None:
                            with suppress(Exception):
                                await self._client.close()
                            self._client = None
                if attempt < self._retry_attempts - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))

        logger.error("Redis %s failed after %d attempts", operation, self._retry_attempts)
        raise last_error

    async def get(self, key: str) -> str | None:
        """Get value from Redis with retry."""
        return await self._execute_with_retry("GET", lambda client, k: client.get(k), key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Set value in Redis with TTL and retry."""
        await self._execute_with_retry(
            "SETEX", lambda client, k, v, t: client.setex(k, t, v), key, value, ttl
        )

    async def delete(self, key: str) -> None:
        """Delete key from Redis with retry."""
        await self._execute_with_retry("DELETE", lambda client, k: client.delete(k), key)

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        result = await self._execute_with_retry("EXISTS", lambda client, k: client.exists(k), key)
        return bool(result)

    async def close(self) -> None:
        """Close Redis connection."""
        async with self._client_lock:
            if self._client is not None:
                await self._client.close()
                self._client = None

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed: %s", str(e))
            return False


class InMemoryCache(CacheBackend):
    """Thread-safe in-memory LRU cache with TTL support.

    Only suitable for development/single-instance deployments.
    """

    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._cleanup_counter = 0
        self._cleanup_interval = 100  # Cleanup every N operations

    async def get(self, key: str) -> str | None:
        """Get value from cache if not expired (thread-safe)."""
        async with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]

            if time.time() > expires_at:
                del self._cache[key]
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Set value in cache with TTL (thread-safe)."""
        async with self._lock:
            # Periodic cleanup
            self._cleanup_counter += 1
            if self._cleanup_counter >= self._cleanup_interval:
                self._cleanup_counter = 0
                self._cleanup_expired_unsafe()

            # Remove oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (value, time.time() + ttl)
            self._cache.move_to_end(key)

    async def delete(self, key: str) -> None:
        """Delete key from cache (thread-safe)."""
        async with self._lock:
            self._cache.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return await self.get(key) is not None

    async def close(self) -> None:
        """Clear cache."""
        async with self._lock:
            self._cache.clear()

    async def health_check(self) -> bool:
        """In-memory cache is always healthy."""
        return True

    def _cleanup_expired_unsafe(self) -> int:
        """Remove expired entries (must be called with lock held)."""
        now = time.time()
        expired_keys = [key for key, (_, expires_at) in self._cache.items() if now > expires_at]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


class UserCache:
    """High-level user caching with serialization.

    Provides a clean interface for caching user data with automatic
    serialization/deserialization and key prefixing.

    Note: Does NOT cache sensitive PII (email). Only caches data needed
    for authorization decisions.
    """

    def __init__(self, backend: CacheBackend, ttl: int):
        self._backend = backend
        self._ttl = ttl

    async def get(self, user_id: str) -> dict[str, Any] | None:
        """Get user data from cache.

        Args:
            user_id: User ID (UUID string)

        Returns:
            User data dict or None if not found/expired
        """
        key = f"{CACHE_KEY_PREFIX}{user_id}"
        data = await self._backend.get(key)
        if data is None:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in cache for user %s", user_id[:8])
            with suppress(Exception):
                await self._backend.delete(key)
            return None

    async def set(self, user_id: str, user_data: dict[str, Any]) -> None:
        """Cache user data.

        Args:
            user_id: User ID (UUID string)
            user_data: User data to cache (should not contain PII)
        """
        key = f"{CACHE_KEY_PREFIX}{user_id}"
        try:
            await self._backend.set(key, json.dumps(user_data, default=str), self._ttl)
        except Exception as e:
            # Log but don't fail - caching is optimization, not critical path
            logger.warning("Failed to cache user %s: %s", user_id[:8], str(e))

    async def invalidate(self, user_id: str) -> None:
        """Remove user from cache.

        Args:
            user_id: User ID to invalidate
        """
        key = f"{CACHE_KEY_PREFIX}{user_id}"
        try:
            await self._backend.delete(key)
            logger.debug("Invalidated cache for user %s", user_id[:8])
        except Exception as e:
            logger.warning("Failed to invalidate cache for user %s: %s", user_id[:8], str(e))

    async def health_check(self) -> bool:
        """Check if cache backend is healthy."""
        return await self._backend.health_check()


# Global cache instance
_cache_backend: CacheBackend | None = None
_user_cache: UserCache | None = None
_token_blacklist: TokenBlacklist | None = None


async def init_cache() -> UserCache:
    """Initialize and return the cache.

    Call this during application startup.

    Returns:
        Configured UserCache instance

    Raises:
        RuntimeError: If Redis is required but unavailable
    """
    global _cache_backend, _user_cache

    config = get_config()

    if config.redis_url:
        logger.info("Initializing Redis cache")
        _cache_backend = RedisCache(
            config.redis_url,
            max_connections=20,
            retry_attempts=3,
        )

        # Verify Redis connection
        if not await _cache_backend.health_check():
            if config.environment == Environment.PRODUCTION:
                raise RuntimeError(
                    "Redis is configured but not reachable. "
                    "Check GTM_REDIS_URL and Redis server status."
                )
            logger.warning(
                "Redis not reachable, falling back to in-memory cache. "
                "This is not suitable for production."
            )
            _cache_backend = InMemoryCache(max_size=config.user_cache_max_size)
    else:
        if config.environment == Environment.PRODUCTION:
            raise RuntimeError(
                "Redis URL (GTM_REDIS_URL) is required in production. "
                "Set GTM_REDIS_URL environment variable."
            )

        logger.warning(
            "Using in-memory cache. This is only suitable for development "
            "with a single instance. Set GTM_REDIS_URL for production."
        )
        _cache_backend = InMemoryCache(max_size=config.user_cache_max_size)

    _user_cache = UserCache(
        backend=_cache_backend,
        ttl=config.user_cache_ttl_seconds,
    )

    global _token_blacklist
    _token_blacklist = TokenBlacklist(backend=_cache_backend)

    return _user_cache


async def close_cache() -> None:
    """Close cache connections. Call during shutdown."""
    global _cache_backend, _user_cache, _token_blacklist

    if _cache_backend is not None:
        await _cache_backend.close()
        _cache_backend = None
        _user_cache = None
        _token_blacklist = None
        logger.info("Cache closed")


def get_user_cache() -> UserCache:
    """Get the user cache instance.

    Returns:
        UserCache instance

    Raises:
        RuntimeError: If cache not initialized
    """
    if _user_cache is None:
        raise RuntimeError("Cache not initialized. Call init_cache() during startup.")
    return _user_cache


class TokenBlacklist:
    """Token blacklist for logout functionality.

    Stores blacklisted token JTIs (JWT IDs) or token hashes to prevent
    use of tokens that have been logged out before their natural expiration.

    Uses the same cache backend as user caching.
    """

    KEY_PREFIX = "gtm:blacklist:"

    def __init__(self, backend: CacheBackend):
        self._backend = backend

    async def add(self, token_jti: str, ttl: int) -> None:
        """Add a token to the blacklist.

        Args:
            token_jti: Token JTI (unique identifier) or hash
            ttl: Time-to-live in seconds (should match token expiration)
        """
        key = f"{self.KEY_PREFIX}{token_jti}"
        try:
            await self._backend.set(key, "1", ttl)
            logger.debug("Token added to blacklist: %s", token_jti[:8])
        except Exception as e:
            logger.error("Failed to blacklist token: %s", str(e))
            raise

    async def is_blacklisted(self, token_jti: str) -> bool:
        """Check if a token is blacklisted.

        Args:
            token_jti: Token JTI or hash

        Returns:
            True if blacklisted, False otherwise
        """
        key = f"{self.KEY_PREFIX}{token_jti}"
        try:
            return await self._backend.exists(key)
        except Exception as e:
            logger.error("Failed to check token blacklist: %s", str(e))
            # Fail open in development, fail closed in production
            config = get_config()
            return config.environment == Environment.PRODUCTION


def get_token_blacklist() -> TokenBlacklist:
    """Get the token blacklist instance.

    Returns:
        TokenBlacklist instance

    Raises:
        RuntimeError: If cache not initialized
    """
    if _token_blacklist is None:
        raise RuntimeError("Token blacklist not initialized. Call init_cache() during startup.")
    return _token_blacklist


def mask_email(email: str) -> str:
    """Mask email for logging (PII protection).

    Example: john.doe@example.com -> j***@e***.com
    """
    if not email or "@" not in email:
        return "***"

    local, domain = email.rsplit("@", 1)
    domain_parts = domain.rsplit(".", 1)

    masked_local = local[0] + "***" if local else "***"
    masked_domain = domain_parts[0][0] + "***" if domain_parts[0] else "***"

    if len(domain_parts) > 1:
        return f"{masked_local}@{masked_domain}.{domain_parts[1]}"
    return f"{masked_local}@{masked_domain}"
