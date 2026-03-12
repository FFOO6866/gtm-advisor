"""Warm-tier cache for completed analysis summaries.

Analysis results are expensive to compute (~$2–10 each).
Cache the summary for 7 days so repeat lookups are instant.
"""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from typing import Any
from uuid import UUID

from services.gateway.src.cache import CacheBackend

_CACHE_ERRORS = (OSError, ConnectionError, json.JSONDecodeError, TimeoutError)

logger = logging.getLogger(__name__)

TTL = 604_800         # 7 days
KEY_PREFIX = "gtm:summary:"


class AnalysisSummaryCache:
    """Warm-tier cache for analysis result summaries.

    Usage:
        cache = AnalysisSummaryCache(backend)
        summary = await cache.get(analysis_id)
        if summary is None:
            summary = await repo.reconstruct_result(analysis_id)
            await cache.set(analysis_id, summary.model_dump())
    """

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    def _key(self, analysis_id: UUID) -> str:
        return f"{KEY_PREFIX}{analysis_id}"

    async def get(self, analysis_id: UUID) -> dict[str, Any] | None:
        """Return cached analysis summary dict or None on miss."""
        key = self._key(analysis_id)
        with suppress(*_CACHE_ERRORS):
            raw = await self._backend.get(key)
            if raw:
                logger.debug("analysis_cache_hit analysis_id=%s", str(analysis_id)[:8])
                return json.loads(raw)
        return None

    async def set(self, analysis_id: UUID, summary: dict[str, Any]) -> None:
        """Cache analysis summary for 7 days."""
        key = self._key(analysis_id)
        with suppress(*_CACHE_ERRORS):
            await self._backend.set(key, json.dumps(summary, default=str), TTL)
            logger.debug("analysis_cache_set analysis_id=%s", str(analysis_id)[:8])

    async def invalidate(self, analysis_id: UUID) -> None:
        """Remove cached entry (call when result is updated)."""
        with suppress(*_CACHE_ERRORS):
            await self._backend.delete(self._key(analysis_id))
