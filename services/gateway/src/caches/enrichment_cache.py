"""Hot-tier cache for company enrichment data.

Cache-aside pattern: check before enrichment API call, store on hit.
TTL 24h — company data changes slowly.
"""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from typing import Any

from services.gateway.src.cache import CacheBackend

# Only suppress infrastructure/IO errors so programming bugs surface normally
_CACHE_ERRORS = (OSError, ConnectionError, json.JSONDecodeError, TimeoutError)

logger = logging.getLogger(__name__)

TTL = 86_400          # 24 hours
KEY_PREFIX = "gtm:enrich:"


class EnrichmentCache:
    """Hot-tier cache for company enrichment results.

    Usage:
        cache = EnrichmentCache(backend)
        data = await cache.get("techcorp.com")
        if data is None:
            data = await enrichment_api.fetch("techcorp.com")
            await cache.set("techcorp.com", data)
    """

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    def _key(self, domain: str) -> str:
        # Normalise domain: lowercase, strip http(s)://
        domain = domain.lower().strip()
        if "://" in domain:
            domain = domain.split("://", 1)[1]
        domain = domain.rstrip("/")
        return f"{KEY_PREFIX}{domain}"

    async def get(self, domain: str) -> dict[str, Any] | None:
        """Return cached enrichment dict or None on cache miss."""
        key = self._key(domain)
        with suppress(*_CACHE_ERRORS):
            raw = await self._backend.get(key)
            if raw:
                logger.debug("enrichment_cache_hit domain=%s", domain[:30])
                return json.loads(raw)
        return None

    async def set(self, domain: str, data: dict[str, Any]) -> None:
        """Store enrichment data for 24 hours."""
        key = self._key(domain)
        with suppress(*_CACHE_ERRORS):
            await self._backend.set(key, json.dumps(data, default=str), TTL)
            logger.debug("enrichment_cache_set domain=%s", domain[:30])

    async def invalidate(self, domain: str) -> None:
        """Remove cached entry (call when company data known to have changed)."""
        with suppress(*_CACHE_ERRORS):
            await self._backend.delete(self._key(domain))
