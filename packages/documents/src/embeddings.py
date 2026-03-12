"""Embedding service for market intelligence RAG.

Uses OpenAI text-embedding-3-small (1536 dims, $0.02/1M tokens).
Embeddings stored as JSON text: json.dumps(list[float]).

Gracefully degrades: if OpenAI unavailable, returns None for embeddings.
Cosine similarity search done in Python for SQLite dev environment.
On PostgreSQL production, use a separate pgvector migration for ANN index.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_MODEL = "text-embedding-3-small"
_MAX_CHARS = 8000


class EmbeddingService:
    """Embeds text via OpenAI and provides cosine-similarity search.

    Embeddings are serialised as JSON strings (``json.dumps(list[float])``)
    so they can be stored in any text/varchar column, including SQLite in
    development and PostgreSQL in production.

    The ``openai`` package is imported lazily so that environments without it
    (e.g. CI jobs that only run non-embedding tests) do not fail at import time.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: Any | None = None  # lazy-init openai.AsyncOpenAI

    @property
    def is_configured(self) -> bool:
        """Return True when an API key is available."""
        return bool(self._api_key)

    async def _get_client(self) -> Any:
        """Lazily initialise and return an ``openai.AsyncOpenAI`` client."""
        if self._client is None:
            import openai  # noqa: PLC0415 — intentional lazy import

            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed_text(self, text: str) -> str | None:
        """Embed a single text string and return a JSON-serialised embedding.

        Args:
            text: The text to embed.

        Returns:
            JSON string (``json.dumps(list[float])``) on success, or ``None``
            when the service is not configured or the API call fails.
        """
        if not self.is_configured:
            return None

        truncated = text.strip()[:_MAX_CHARS]
        try:
            client = await self._get_client()
            response = await client.embeddings.create(
                model=_MODEL,
                input=truncated,
            )
            return json.dumps(response.data[0].embedding)
        except Exception as exc:
            logger.warning(
                "embed_text failed",
                error=str(exc),
                text_length=len(text),
            )
            return None

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[str | None]:
        """Embed a list of texts in batches, returning one result per input.

        OpenAI's embeddings endpoint accepts list input, so each batch is a
        single API call.  ``batch_size`` is kept small (default 100) to avoid
        hitting per-request token limits.

        Args:
            texts: Texts to embed.
            batch_size: Maximum number of texts per API call.

        Returns:
            List of the same length as ``texts``.  Each element is a
            JSON-serialised embedding string or ``None`` on failure.
        """
        if not texts:
            return []

        if not self.is_configured:
            return [None] * len(texts)

        results: list[str | None] = []
        client = await self._get_client()

        for batch_start in range(0, len(texts), batch_size):
            texts_batch = [
                t.strip()[:_MAX_CHARS]
                for t in texts[batch_start : batch_start + batch_size]
            ]
            try:
                response = await client.embeddings.create(
                    model=_MODEL,
                    input=texts_batch,
                )
                # The API returns embeddings in the same order as the input.
                batch_results = [
                    json.dumps(item.embedding) for item in response.data
                ]
                results.extend(batch_results)
            except Exception as exc:
                logger.warning(
                    "embed_batch failed for batch",
                    error=str(exc),
                    batch_start=batch_start,
                    batch_size=len(texts_batch),
                )
                results.extend([None] * len(texts_batch))

        return results

    def deserialise(self, embedding_json: str) -> list[float]:
        """Deserialise a stored embedding JSON string back to a float list.

        Args:
            embedding_json: JSON string as produced by ``embed_text`` /
                ``embed_batch``.

        Returns:
            List of floats representing the embedding vector.
        """
        return json.loads(embedding_json)

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two equal-length vectors.

        Args:
            a: First embedding vector.
            b: Second embedding vector.

        Returns:
            Similarity score in ``[-1.0, 1.0]``, or ``0.0`` if either vector
            is the zero vector.
        """
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return dot / (mag_a * mag_b)

    async def find_similar(
        self,
        query: str,
        candidates: list[tuple[str, str]],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Find the most similar candidates to a query string.

        Embeds the query then performs brute-force cosine similarity against
        all candidates in Python.  This is the fallback path used in the
        SQLite development environment where pgvector ANN indexes are not
        available.

        Args:
            query: The query text to search with.
            candidates: List of ``(id_str, embedding_json)`` pairs.
            top_k: Maximum number of results to return.

        Returns:
            Up to ``top_k`` ``(id_str, similarity_score)`` tuples sorted by
            similarity descending.  Returns an empty list if the query cannot
            be embedded or ``candidates`` is empty.
        """
        if not candidates:
            return []

        query_json = await self.embed_text(query)
        if query_json is None:
            return []

        query_vec = self.deserialise(query_json)

        scored: list[tuple[str, float]] = []
        for id_str, embedding_json in candidates:
            try:
                candidate_vec = self.deserialise(embedding_json)
                score = self.cosine_similarity(query_vec, candidate_vec)
                scored.append((id_str, score))
            except Exception as exc:
                logger.warning(
                    "find_similar: failed to score candidate",
                    candidate_id=id_str,
                    error=str(exc),
                )

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Return the process-wide singleton ``EmbeddingService``."""
    return EmbeddingService()
