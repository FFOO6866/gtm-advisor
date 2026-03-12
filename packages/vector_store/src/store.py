"""Qdrant-backed ANN vector store for market articles and document chunks.

Falls back gracefully to a pure-Python cosine similarity implementation when
Qdrant is not configured (neither QDRANT_URL nor QDRANT_PATH is set).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

try:
    import numpy as np

    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMPY_AVAILABLE = False

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )

    _QDRANT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QDRANT_AVAILABLE = False
    AsyncQdrantClient = None  # type: ignore[assignment,misc]
    Distance = None  # type: ignore[assignment]
    FieldCondition = None  # type: ignore[assignment]
    Filter = None  # type: ignore[assignment]
    MatchValue = None  # type: ignore[assignment]
    PointStruct = None  # type: ignore[assignment]
    VectorParams = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ARTICLES_COLLECTION = "market_articles_sg"
CHUNKS_COLLECTION = "document_chunks_sg"
RESEARCH_COLLECTION = "research_cache_sg"
EMBEDDING_DIM = 1536  # text-embedding-3-small


# ---------------------------------------------------------------------------
# Data-transfer objects
# ---------------------------------------------------------------------------


@dataclass
class ArticleVector:
    id: str  # article UUID as string
    vector: list[float]
    vertical_slug: str | None
    signal_type: str | None
    sentiment: str | None
    published_at: str  # ISO datetime string


@dataclass
class ChunkVector:
    id: str  # chunk UUID as string
    vector: list[float]
    document_id: str
    document_type: str | None
    vertical_slug: str | None  # from the parent listed_company.vertical_id join
    chunk_index: int


@dataclass
class ResearchCacheVector:
    id: str          # ResearchCache UUID as string
    vector: list[float]
    source: str
    vertical_slug: str | None
    query_snippet: str  # first 100 chars of query
    published_at: str   # ISO datetime string


@dataclass
class SearchResult:
    id: str
    score: float
    payload: dict
    collection: str  # which collection it came from


# ---------------------------------------------------------------------------
# Store implementation
# ---------------------------------------------------------------------------


class QdrantStore:
    """ANN store backed by Qdrant.

    When neither QDRANT_URL nor QDRANT_PATH is set the store is created with
    ``_enabled = False`` and all methods are silent no-ops (returning 0 / []).
    """

    def __init__(self, client: AsyncQdrantClient | None, *, enabled: bool) -> None:
        self._client = client
        self._enabled = enabled

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    async def ensure_collections(self) -> None:
        """Create both collections if they don't exist. No-op when disabled."""
        if not self._enabled or self._client is None:
            return
        for collection_name, _payload_schema in (
            (
                ARTICLES_COLLECTION,
                {
                    "vertical_slug": "keyword",
                    "signal_type": "keyword",
                    "sentiment": "keyword",
                    "published_at": "keyword",
                },
            ),
            (
                CHUNKS_COLLECTION,
                {
                    "document_id": "keyword",
                    "document_type": "keyword",
                    "vertical_slug": "keyword",
                    "chunk_index": "integer",
                },
            ),
            (
                RESEARCH_COLLECTION,
                {
                    "source": "keyword",
                    "vertical_slug": "keyword",
                    "published_at": "keyword",
                },
            ),
        ):
            try:
                existing = await self._client.get_collections()
                names = {c.name for c in existing.collections}
                if collection_name not in names:
                    await self._client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=EMBEDDING_DIM,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info("Created Qdrant collection: %s", collection_name)
            except Exception:
                logger.warning(
                    "Failed to ensure collection %s", collection_name, exc_info=True
                )

    # ------------------------------------------------------------------
    # Upsert helpers
    # ------------------------------------------------------------------

    async def upsert_articles(self, records: list[ArticleVector]) -> int:
        """Upsert article embeddings. Returns count inserted. No-op when disabled.

        Raises on Qdrant failure so callers can rollback the DB transaction and
        retry on the next run rather than silently marking articles as classified.
        """
        if not self._enabled or self._client is None or not records:
            return 0
        points = [
            PointStruct(
                id=r.id,
                vector=r.vector,
                payload={
                    "vertical_slug": r.vertical_slug,
                    "signal_type": r.signal_type,
                    "sentiment": r.sentiment,
                    "published_at": r.published_at,
                },
            )
            for r in records
        ]
        await self._client.upsert(
            collection_name=ARTICLES_COLLECTION,
            points=points,
        )
        return len(points)

    async def upsert_research_cache(self, records: list[ResearchCacheVector]) -> int:
        """Upsert research cache embeddings. Returns count inserted. No-op when disabled.

        Raises on Qdrant failure so callers can rollback the DB transaction and
        retry on the next run rather than silently marking rows as embedded.
        """
        if not self._enabled or self._client is None or not records:
            return 0
        points = [
            PointStruct(
                id=r.id,
                vector=r.vector,
                payload={
                    "source": r.source,
                    "vertical_slug": r.vertical_slug,
                    "query_snippet": r.query_snippet,
                    "published_at": r.published_at,
                },
            )
            for r in records
        ]
        await self._client.upsert(
            collection_name=RESEARCH_COLLECTION,
            points=points,
        )
        return len(points)

    async def upsert_chunks(self, records: list[ChunkVector]) -> int:
        """Upsert chunk embeddings. Returns count inserted. No-op when disabled.

        Raises on Qdrant failure so callers can rollback and retry.
        """
        if not self._enabled or self._client is None or not records:
            return 0
        points = [
            PointStruct(
                id=r.id,
                vector=r.vector,
                payload={
                    "document_id": r.document_id,
                    "document_type": r.document_type,
                    "vertical_slug": r.vertical_slug,
                    "chunk_index": r.chunk_index,
                },
            )
            for r in records
        ]
        await self._client.upsert(
            collection_name=CHUNKS_COLLECTION,
            points=points,
        )
        return len(points)

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------

    def _build_filter(self, field: str, value: str | None) -> Filter | None:
        """Return a Qdrant Filter for a keyword field, or None if value is None."""
        if value is None:
            return None
        return Filter(
            must=[
                FieldCondition(
                    key=field,
                    match=MatchValue(value=value),
                )
            ]
        )

    async def _query_collection(
        self,
        collection_name: str,
        query_vector: list[float],
        query_filter: Filter | None,
        limit: int,
    ) -> list[SearchResult]:
        """Internal helper — uses query_points() (qdrant-client ≥ 1.9) with
        fallback to the legacy search() API for older builds."""
        if hasattr(self._client, "query_points"):
            response = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            points = response.points
        else:
            # Legacy qdrant-client < 1.9
            points = await self._client.search(  # type: ignore[attr-defined]
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        return [
            SearchResult(
                id=str(h.id),
                score=h.score,
                payload=h.payload or {},
                collection=collection_name,
            )
            for h in points
        ]

    async def search_articles(
        self,
        query_vector: list[float],
        vertical_slug: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """ANN search in ARTICLES_COLLECTION, optional vertical_slug filter."""
        if not self._enabled or self._client is None:
            return []
        try:
            query_filter = self._build_filter("vertical_slug", vertical_slug)
            return await self._query_collection(
                ARTICLES_COLLECTION, query_vector, query_filter, limit
            )
        except Exception:
            logger.warning("search_articles failed", exc_info=True)
            return []

    async def search_chunks(
        self,
        query_vector: list[float],
        document_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """ANN search in CHUNKS_COLLECTION, optional document_type filter."""
        if not self._enabled or self._client is None:
            return []
        try:
            query_filter = self._build_filter("document_type", document_type)
            return await self._query_collection(
                CHUNKS_COLLECTION, query_vector, query_filter, limit
            )
        except Exception:
            logger.warning("search_chunks failed", exc_info=True)
            return []

    async def search_research_cache(
        self,
        query_vector: list[float],
        vertical_slug: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """ANN search in RESEARCH_COLLECTION, optional vertical_slug filter."""
        if not self._enabled or self._client is None:
            return []
        try:
            query_filter = self._build_filter("vertical_slug", vertical_slug)
            return await self._query_collection(
                RESEARCH_COLLECTION, query_vector, query_filter, limit
            )
        except Exception:
            logger.warning("search_research_cache failed", exc_info=True)
            return []

    async def search_all(
        self,
        query_vector: list[float],
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search both collections, merge, deduplicate by ID, and re-rank by score.

        In practice the same UUID should not exist in both collections, but if it does
        (e.g. during a migration or a bug) we keep the higher-scored entry.
        """
        article_results = await self.search_articles(query_vector, limit=limit)
        chunk_results = await self.search_chunks(query_vector, limit=limit)
        # Deduplicate by ID, keeping the result with the higher score
        seen: dict[str, SearchResult] = {}
        for result in article_results + chunk_results:
            existing = seen.get(result.id)
            if existing is None or result.score > existing.score:
                seen[result.id] = result
        merged = sorted(seen.values(), key=lambda r: r.score, reverse=True)
        return merged[:limit]


# ---------------------------------------------------------------------------
# Module-level cosine fallback (no class, no Qdrant dependency)
# ---------------------------------------------------------------------------


def cosine_similarity_fallback(
    query_vector: list[float],
    candidates: list[tuple[str, list[float], dict]],
    limit: int = 10,
) -> list[SearchResult]:
    """Pure-Python cosine similarity for when Qdrant is not configured.

    Parameters
    ----------
    query_vector:
        The embedding to search against.
    candidates:
        A list of ``(id, vector, payload)`` tuples to rank.
    limit:
        Maximum number of results to return.

    Returns
    -------
    list[SearchResult]
        Sorted by score descending, capped at *limit*.
    """
    if not candidates:
        return []

    results: list[SearchResult] = []

    if _NUMPY_AVAILABLE:
        q = np.array(query_vector, dtype=np.float64)
        q_norm = np.linalg.norm(q)
        if q_norm == 0.0:
            q_norm = 1.0
        for doc_id, vector, payload in candidates:
            v = np.array(vector, dtype=np.float64)
            v_norm = np.linalg.norm(v)
            if v_norm == 0.0:
                score = 0.0
            else:
                score = float(np.dot(q, v) / (q_norm * v_norm))
            results.append(
                SearchResult(
                    id=doc_id,
                    score=score,
                    payload=payload,
                    collection="fallback",
                )
            )
    else:
        # Pure-Python path (no numpy)
        def _dot(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b, strict=False))

        def _norm(v: list[float]) -> float:
            return sum(x * x for x in v) ** 0.5

        q_norm = _norm(query_vector) or 1.0
        for doc_id, vector, payload in candidates:
            v_norm = _norm(vector)
            if v_norm == 0.0:
                score = 0.0
            else:
                score = _dot(query_vector, vector) / (q_norm * v_norm)
            results.append(
                SearchResult(
                    id=doc_id,
                    score=score,
                    payload=payload,
                    collection="fallback",
                )
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_qdrant_store() -> QdrantStore:
    """Return a cached QdrantStore instance.

    Connection priority:
    1. ``QDRANT_URL`` env var → ``AsyncQdrantClient(url=...)``
    2. ``QDRANT_PATH`` env var → ``AsyncQdrantClient(path=...)`` (local file)
    3. Neither set → store created with ``_enabled = False``

    Note — ``@lru_cache`` is evaluated once per process lifetime.  If you set
    ``QDRANT_URL`` or ``QDRANT_PATH`` *after* the first call (e.g. in tests that
    patch env vars), the cached disabled instance will be returned instead of a
    connected one.  In tests, call ``get_qdrant_store.cache_clear()`` before
    patching env vars to force re-evaluation.
    """
    if not _QDRANT_AVAILABLE:
        logger.warning(
            "qdrant-client is not installed; vector store disabled."
        )
        return QdrantStore(client=None, enabled=False)

    qdrant_url = os.environ.get("QDRANT_URL", "").strip()
    qdrant_path = os.environ.get("QDRANT_PATH", "").strip()

    if qdrant_url:
        logger.info("Connecting to Qdrant at URL: %s", qdrant_url)
        client = AsyncQdrantClient(url=qdrant_url)
        return QdrantStore(client=client, enabled=True)

    if qdrant_path:
        logger.info("Connecting to Qdrant at local path: %s", qdrant_path)
        client = AsyncQdrantClient(path=qdrant_path)
        return QdrantStore(client=client, enabled=True)

    logger.info(
        "Neither QDRANT_URL nor QDRANT_PATH is set; vector store disabled."
    )
    return QdrantStore(client=None, enabled=False)
