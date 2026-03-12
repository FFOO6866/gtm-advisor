"""Intelligence pipelines — classification, embedding, and Qdrant ingestion.

Two pipelines:
  - :class:`ArticleIntelligencePipeline`: classify + embed market articles
  - :class:`ChunkEmbeddingPipeline`: embed unembedded document chunks
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import (
    DocumentChunk,
    ListedCompany,
    MarketArticle,
    MarketVertical,
)
from packages.documents.src.embeddings import get_embedding_service
from packages.intelligence.src.classifier import ArticleClassifier
from packages.vector_store.src.store import ArticleVector, ChunkVector, get_qdrant_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stats dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PipelineStats:
    total: int
    classified: int
    embedded: int
    qdrant_upserted: int


# ---------------------------------------------------------------------------
# Article intelligence pipeline
# ---------------------------------------------------------------------------


class ArticleIntelligencePipeline:
    """Full pipeline: load unclassified articles → classify → embed → Qdrant → commit."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run(self, batch_size: int = 100) -> PipelineStats:
        """Run the full pipeline for a batch of unclassified articles.

        Args:
            batch_size: Maximum number of articles to process per call.

        Returns:
            :class:`PipelineStats` describing what was processed.
        """
        total = 0
        classified = 0
        embedded = 0
        qdrant_upserted = 0

        try:
            # Step 1: Load unclassified articles
            result = await self._session.execute(
                select(MarketArticle)
                .where(MarketArticle.is_classified == False)  # noqa: E712
                .order_by(MarketArticle.published_at.desc())
                .limit(batch_size)
            )
            articles: list[MarketArticle] = list(result.scalars().all())
            total = len(articles)

            if not articles:
                logger.info("ArticleIntelligencePipeline: no unclassified articles found")
                return PipelineStats(total=0, classified=0, embedded=0, qdrant_upserted=0)

            logger.info("ArticleIntelligencePipeline: processing %d articles", total)

            # Step 2: Classify
            classifier = ArticleClassifier()
            classifications = classifier.classify_batch(
                [(a.title, a.summary) for a in articles]
            )

            # Step 3: Apply classification to ORM objects
            for article, cls_result in zip(articles, classifications, strict=True):
                article.vertical_slug = cls_result.vertical_slug
                article.signal_type = cls_result.signal_type
                article.sentiment = cls_result.sentiment
            classified = total

            # Step 4: Embed
            embedding_service = get_embedding_service()
            texts = [f"{a.title}. {a.summary or ''}" for a in articles]

            if embedding_service.is_configured:
                embeddings: list[str | None] = await embedding_service.embed_batch(texts)
            else:
                logger.info(
                    "ArticleIntelligencePipeline: embedding service not configured, skipping"
                )
                embeddings = [None] * len(articles)

            # Step 5: Apply embeddings to ORM objects
            for article, emb in zip(articles, embeddings, strict=True):
                article.embedding = emb
                if emb is not None:
                    embedded += 1

            # Step 6: Upsert to Qdrant (only articles that have embeddings)
            qdrant = get_qdrant_store()
            article_vectors: list[ArticleVector] = []
            for article, emb in zip(articles, embeddings, strict=True):
                if emb is None:
                    continue
                try:
                    vector: list[float] = json.loads(emb)
                    article_vectors.append(
                        ArticleVector(
                            id=str(article.id),
                            vector=vector,
                            vertical_slug=article.vertical_slug,
                            signal_type=article.signal_type,
                            sentiment=article.sentiment,
                            published_at=article.published_at.isoformat(),
                        )
                    )
                except Exception:
                    logger.warning(
                        "ArticleIntelligencePipeline: failed to parse embedding for article %s",
                        article.id,
                        exc_info=True,
                    )

            if article_vectors:
                qdrant_upserted = await qdrant.upsert_articles(article_vectors)

            # Step 7: Mark articles as classified.
            # If the embedding service is configured, only mark articles that
            # received a successful embedding — articles where embedding failed
            # (e.g. OpenAI batch error) stay is_classified=False and will be
            # retried on the next pipeline run.
            # If the embedding service is not configured we mark all as classified
            # regardless, to avoid an infinite retry loop.
            if embedding_service.is_configured:
                for article, emb in zip(articles, embeddings, strict=True):
                    if emb is not None:
                        article.is_classified = True
            else:
                for article in articles:
                    article.is_classified = True

            # Step 8: Commit
            await self._session.commit()

            logger.info(
                "ArticleIntelligencePipeline: done — classified=%d embedded=%d qdrant=%d",
                classified,
                embedded,
                qdrant_upserted,
            )

        except Exception:
            logger.error(
                "ArticleIntelligencePipeline: unhandled error, rolling back",
                exc_info=True,
            )
            await self._session.rollback()

        return PipelineStats(
            total=total,
            classified=classified,
            embedded=embedded,
            qdrant_upserted=qdrant_upserted,
        )


# ---------------------------------------------------------------------------
# Chunk embedding pipeline
# ---------------------------------------------------------------------------


class ChunkEmbeddingPipeline:
    """Embed unembedded document chunks and upsert to Qdrant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run(self, batch_size: int = 200) -> int:
        """Embed a batch of unembedded document chunks and upsert to Qdrant.

        Args:
            batch_size: Maximum number of chunks to process per call.

        Returns:
            Count of chunks processed (attempted).
        """
        processed = 0

        try:
            # Step 1: Load unembedded chunks, joined with CompanyDocument for metadata
            result = await self._session.execute(
                select(DocumentChunk)
                .where(DocumentChunk.embedding.is_(None))
                .options(selectinload(DocumentChunk.document))
                .limit(batch_size)
            )
            chunks: list[DocumentChunk] = list(result.scalars().all())

            if not chunks:
                logger.info("ChunkEmbeddingPipeline: no unembedded chunks found")
                return 0

            logger.info("ChunkEmbeddingPipeline: processing %d chunks", len(chunks))

            # Step 2: Embed
            embedding_service = get_embedding_service()
            texts = [c.chunk_text for c in chunks]

            if embedding_service.is_configured:
                embeddings: list[str | None] = await embedding_service.embed_batch(texts)
            else:
                logger.info(
                    "ChunkEmbeddingPipeline: embedding service not configured, skipping"
                )
                embeddings = [None] * len(chunks)

            # Step 3: Apply embeddings to ORM objects
            for chunk, emb in zip(chunks, embeddings, strict=True):
                chunk.embedding = emb

            # Step 4: Gather vertical slugs for chunks that have embeddings
            # Build a set of unique listed_company_ids we need to resolve
            company_ids_needed: set[str] = set()
            for chunk, emb in zip(chunks, embeddings, strict=True):
                if emb is not None and chunk.document is not None:
                    company_ids_needed.add(str(chunk.document.listed_company_id))

            vertical_slug_by_company: dict[str, str | None] = {}
            if company_ids_needed:
                vertical_slug_by_company = await self._fetch_vertical_slugs(
                    list(company_ids_needed)
                )

            # Step 5: Build ChunkVector objects for Qdrant
            chunk_vectors: list[ChunkVector] = []
            for chunk, emb in zip(chunks, embeddings, strict=True):
                if emb is None:
                    continue
                try:
                    vector: list[float] = json.loads(emb)
                    doc = chunk.document
                    company_id_str = str(doc.listed_company_id) if doc is not None else None
                    vertical_slug = (
                        vertical_slug_by_company.get(company_id_str)
                        if company_id_str
                        else None
                    )
                    document_type = (
                        doc.document_type.value if doc is not None else None
                    )
                    chunk_vectors.append(
                        ChunkVector(
                            id=str(chunk.id),
                            vector=vector,
                            document_id=str(chunk.document_id),
                            document_type=document_type,
                            vertical_slug=vertical_slug,
                            chunk_index=chunk.chunk_index,
                        )
                    )
                except Exception:
                    logger.warning(
                        "ChunkEmbeddingPipeline: failed to parse embedding for chunk %s",
                        chunk.id,
                        exc_info=True,
                    )

            # Step 6: Upsert to Qdrant
            if chunk_vectors:
                qdrant = get_qdrant_store()
                await qdrant.upsert_chunks(chunk_vectors)

            processed = len(chunks)

            # Step 7: Commit
            await self._session.commit()

            logger.info(
                "ChunkEmbeddingPipeline: done — processed=%d vectors_upserted=%d",
                processed,
                len(chunk_vectors),
            )

        except Exception:
            logger.error(
                "ChunkEmbeddingPipeline: unhandled error, rolling back",
                exc_info=True,
            )
            await self._session.rollback()

        return processed

    async def _fetch_vertical_slugs(
        self, company_ids: list[str]
    ) -> dict[str, str | None]:
        """Return a mapping of listed_company_id → vertical_slug.

        Joins ListedCompany → MarketVertical to resolve slugs in one query.
        Returns None for companies with no vertical assigned.
        """
        import uuid as _uuid

        try:
            uuid_ids = [_uuid.UUID(cid) for cid in company_ids]
        except ValueError:
            logger.warning(
                "ChunkEmbeddingPipeline._fetch_vertical_slugs: invalid UUID(s) in %r",
                company_ids,
            )
            return dict.fromkeys(company_ids)

        result = await self._session.execute(
            select(ListedCompany.id, MarketVertical.slug)
            .join(
                MarketVertical,
                ListedCompany.vertical_id == MarketVertical.id,
                isouter=True,
            )
            .where(ListedCompany.id.in_(uuid_ids))
        )
        rows = result.all()
        return {str(row[0]): row[1] for row in rows}
