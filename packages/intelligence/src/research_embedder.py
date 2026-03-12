"""Research Cache Embedding Pipeline — embed public ResearchCache rows into Qdrant."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import ResearchCache
from packages.documents.src.embeddings import get_embedding_service
from packages.intelligence.src.pipeline import PipelineStats
from packages.vector_store.src.store import ResearchCacheVector, get_qdrant_store

logger = logging.getLogger(__name__)


class ResearchEmbedderPipeline:
    """Embed unembedded public ResearchCache rows and upsert to research_cache_sg Qdrant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run(self, batch_size: int = 100) -> PipelineStats:
        """Run the full pipeline for a batch of unembedded public research rows.

        Args:
            batch_size: Maximum number of rows to process per call.

        Returns:
            :class:`PipelineStats` describing what was processed.
        """
        total = 0
        classified = 0
        embedded = 0
        qdrant_upserted = 0

        try:
            # Step 1: Load unembedded public rows
            result = await self._session.execute(
                select(ResearchCache)
                .where(
                    ResearchCache.is_public == True,  # noqa: E712
                    ResearchCache.is_embedded == False,  # noqa: E712
                )
                .order_by(ResearchCache.created_at.desc())
                .limit(batch_size)
            )
            rows: list[ResearchCache] = list(result.scalars().all())
            total = len(rows)

            if not rows:
                logger.info("ResearchEmbedderPipeline: no unembedded public rows found")
                return PipelineStats(total=0, classified=0, embedded=0, qdrant_upserted=0)

            logger.info("ResearchEmbedderPipeline: processing %d rows", total)

            # Step 2: Embed
            embedding_service = get_embedding_service()
            texts = [f"{r.query}. {r.content[:500]}" for r in rows]

            if embedding_service.is_configured:
                embeddings: list[str | None] = await embedding_service.embed_batch(texts)
            else:
                logger.info(
                    "ResearchEmbedderPipeline: embedding service not configured, skipping"
                )
                embeddings = [None] * len(rows)

            # Step 3: Apply embeddings to ORM objects
            for row, emb in zip(rows, embeddings, strict=True):
                row.embedding = emb
                if emb is not None:
                    embedded += 1

            # Step 4: Upsert to Qdrant (only rows that have embeddings)
            qdrant = get_qdrant_store()
            research_vectors: list[ResearchCacheVector] = []
            for row, emb in zip(rows, embeddings, strict=True):
                if emb is None:
                    continue
                try:
                    vector: list[float] = json.loads(emb)
                    research_vectors.append(
                        ResearchCacheVector(
                            id=str(row.id),
                            vector=vector,
                            source=row.source,
                            vertical_slug=row.vertical_slug,
                            query_snippet=row.query[:100],
                            published_at=row.created_at.isoformat(),
                        )
                    )
                except Exception:
                    logger.warning(
                        "ResearchEmbedderPipeline: failed to parse embedding for row %s",
                        row.id,
                        exc_info=True,
                    )

            if research_vectors:
                qdrant_upserted = await qdrant.upsert_research_cache(research_vectors)

            # Step 5: Mark successfully embedded rows
            now = datetime.now(UTC)
            if embedding_service.is_configured:
                for row, emb in zip(rows, embeddings, strict=True):
                    if emb is not None:
                        row.is_embedded = True
                        row.embedded_at = now
            else:
                for row in rows:
                    row.is_embedded = True
                    row.embedded_at = now

            # Step 6: Commit
            await self._session.commit()

            logger.info(
                "ResearchEmbedderPipeline: done — embedded=%d qdrant=%d",
                embedded,
                qdrant_upserted,
            )

        except Exception:
            logger.error(
                "ResearchEmbedderPipeline: unhandled error, rolling back",
                exc_info=True,
            )
            await self._session.rollback()

        # Cleanup: mark old private rows as "embedded" (tombstone) so they don't accumulate.
        # Private rows are never actually embedded — this just prevents unbounded table growth.
        try:
            cutoff = datetime.now(UTC) - timedelta(days=30)
            old_private = await self._session.execute(
                select(ResearchCache)
                .where(
                    ResearchCache.is_public == False,  # noqa: E712
                    ResearchCache.is_embedded == False,  # noqa: E712
                    ResearchCache.created_at < cutoff,
                )
                .limit(500)
            )
            for row in old_private.scalars().all():
                row.is_embedded = True  # tombstone — not actually embedded, just cleaned up
                row.embedded_at = datetime.now(UTC)
            await self._session.commit()
        except Exception:
            logger.warning(
                "ResearchEmbedderPipeline: private-row cleanup failed",
                exc_info=True,
            )

        return PipelineStats(
            total=total,
            classified=classified,
            embedded=embedded,
            qdrant_upserted=qdrant_upserted,
        )
