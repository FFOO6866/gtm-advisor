"""Hot-tier cache for Perplexity query results.

Perplexity is the most expensive data source (~$0.05/query).
Cache results for 1 hour — market data is still relevant within that window.
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import suppress
from typing import Any

from services.gateway.src.cache import CacheBackend

_CACHE_ERRORS = (OSError, ConnectionError, json.JSONDecodeError, TimeoutError)

logger = logging.getLogger(__name__)

TTL = 3_600           # 1 hour
KEY_PREFIX = "gtm:perplexity:"


def _hash_query(query: str, context: dict[str, Any] | None = None) -> str:
    """Deterministic hash for a (query, context) pair.

    Context is included because the same query string may yield different
    results for different industries/regions.
    """
    context_str = json.dumps(context or {}, sort_keys=True, default=str)
    combined = f"{query}||{context_str}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


class PerplexityCache:
    """Hot-tier cache for Perplexity search results.

    Usage:
        cache = PerplexityCache(backend)
        cached = await cache.get(query, context)
        if cached is None:
            result = await perplexity_api.search(query)
            await cache.set(query, context, result)
    """

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    @staticmethod
    def hash_query(query: str, context: dict[str, Any] | None = None) -> str:
        """Public alias for deterministic query hashing."""
        return _hash_query(query, context)

    def _key(self, query: str, context: dict[str, Any] | None = None) -> str:
        return f"{KEY_PREFIX}{_hash_query(query, context)}"

    async def get(self, query: str, context: dict[str, Any] | None = None) -> str | None:
        """Return cached Perplexity result string or None on miss."""
        key = self._key(query, context)
        with suppress(*_CACHE_ERRORS):
            result = await self._backend.get(key)
            if result:
                logger.debug("perplexity_cache_hit query_prefix=%s", query[:40])
                return result
        return None

    async def set(
        self,
        query: str,
        context: dict[str, Any] | None,
        result: str,
    ) -> None:
        """Cache Perplexity result for 1 hour."""
        key = self._key(query, context)
        with suppress(*_CACHE_ERRORS):
            await self._backend.set(key, result, TTL)
            logger.debug("perplexity_cache_set query_prefix=%s", query[:40])
