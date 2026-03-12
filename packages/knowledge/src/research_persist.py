"""Helpers for agents to persist real-time research into the ResearchCache staging table.

This function opens its OWN database session and commits internally, so callers
(agents, schedulers) do NOT need to pass a session or manage a transaction.

Usage in agent _act() methods:
    import asyncio
    from packages.knowledge.src.research_persist import persist_research

    # Fire-and-forget — does not block the caller
    asyncio.create_task(persist_research(
        source="market_intelligence",
        query="Singapore fintech market trends 2026",
        content=perplexity_result_text,
        vertical_slug="fintech",
        analysis_id=self._analysis_id,
        is_public=True,   # market-level research, not company-specific
    ))

    # Company-specific (private) research:
    asyncio.create_task(persist_research(
        source="competitor_analyst",
        query="Competitor analysis: Acme Corp",
        content=str(competitor_data),
        company_id=company_id,
        analysis_id=self._analysis_id,
        is_public=False,
    ))
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


async def persist_research(
    *,
    source: str,
    query: str,
    content: str,
    vertical_slug: str | None = None,
    company_id: uuid.UUID | None = None,
    analysis_id: uuid.UUID | None = None,
    is_public: bool = False,
) -> None:
    """Insert a ResearchCache row in its own session/transaction.

    The function opens a new async session, creates the row, and commits.
    Any exception is caught and logged — it never blocks or raises to the caller.

    Args:
        source: Short identifier for the data source (e.g. "perplexity", "newsapi").
        query: The query or topic string (truncated to 500 chars).
        content: Raw text content to store.
        vertical_slug: Optional Singapore market vertical identifier.
        company_id: Optional company UUID (for company-scoped research).
        analysis_id: Optional analysis UUID for traceability.
        is_public: When True the row is eligible for Qdrant embedding and shared
            retrieval. Set False for company-specific / sensitive research.
    """
    try:
        # Lazy import to avoid circular imports at module load time.
        from packages.database.src.models import ResearchCache  # noqa: PLC0415
        from packages.database.src.session import async_session_factory  # noqa: PLC0415

        async with async_session_factory() as session:
            row = ResearchCache(
                source=source[:20],
                query=query[:500],
                content=content,
                vertical_slug=vertical_slug,
                company_id=company_id,
                analysis_id=analysis_id,
                is_public=is_public,
            )
            session.add(row)
            await session.commit()
    except Exception:
        logger.warning("persist_research_failed", exc_info=True)
