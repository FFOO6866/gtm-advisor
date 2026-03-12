#!/usr/bin/env python3
"""One-time knowledge base build script.

Loads all Singapore market verticals, company rosters, financial data,
RSS articles, and runs the intelligence pipeline.

Usage:
    uv run python scripts/build_knowledge_base.py [--skip-financials] [--skip-docs] [--limit N]

Options:
    --skip-financials   Skip EODHD financial sync (useful if API quota is low)
    --skip-docs         Skip SGX document discovery
    --limit N           Max companies to sync financials for (default: 300)

Expected runtime (default --limit 300):
    - Steps 1-2 (seed + roster):  ~30 s
    - Step 3 (financial sync):    ~20-25 min  (300 companies × 3 EODHD calls × 0.5 s delay each)
    - Step 4 (benchmarks):        ~10 s
    - Steps 5-6 (RSS + classify): ~2-5 min depending on feed size
    - Step 7 (SGX documents):     ~5-10 min

    Total with financials: ~30 min.  Use --skip-financials to reduce to ~10 min.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_kb")


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------


async def step_seed_verticals(db) -> int:  # type: ignore[type-arg]
    """Upsert the 12 Singapore market verticals."""
    from packages.database.src.vertical_seeds import seed_verticals

    count = await seed_verticals(db)
    await db.commit()
    logger.info("Verticals: %d upserted", count)
    return count


async def step_sync_roster(db, eodhd_client) -> dict[str, int]:  # type: ignore[type-arg]
    """Sync the full SGX symbol roster plus curated overseas-listed SG companies."""
    from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

    sync = FinancialIntelligenceSync(session=db, eodhd_client=eodhd_client)
    counts = await sync.sync_exchange_roster("SG")
    await db.commit()
    logger.info(
        "SGX roster: %d created, %d updated, %d skipped",
        counts["created"],
        counts["updated"],
        counts["skipped"],
    )
    return counts


async def step_sync_financials(eodhd_client, limit: int) -> int:
    """Sync full fundamental data for the top N companies by market cap.

    Each company requires ~3 EODHD API calls with 0.5 s delay between each, so
    expect ~1.5 s of sleep overhead per company plus network latency.
    At limit=300 this step alone takes approximately 20-25 minutes.

    Commits per-company so progress is preserved if the process is killed mid-run.
    Re-running skips companies that already have financial snapshots (resumable).
    """
    from sqlalchemy import func, select

    from packages.database.src.models import CompanyFinancialSnapshot, ListedCompany
    from packages.database.src.session import async_session_factory
    from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

    # Fetch the ordered list of (ticker, exchange) pairs in a short-lived session.
    async with async_session_factory() as db:
        stmt = (
            select(ListedCompany.ticker, ListedCompany.exchange)
            .order_by(ListedCompany.market_cap_sgd.desc().nullslast())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()

    synced = 0
    failed = 0
    skipped = 0

    for ticker, exchange in rows:
        # Check if this company already has snapshots (resumable skip).
        async with async_session_factory() as db:
            existing_count = (
                await db.execute(
                    select(func.count())
                    .select_from(CompanyFinancialSnapshot)
                    .join(ListedCompany)
                    .where(
                        ListedCompany.ticker == ticker,
                        ListedCompany.exchange == exchange,
                    )
                )
            ).scalar()
            if existing_count > 0:
                skipped += 1
                continue

        # Sync this company in its own session and commit immediately.
        try:
            async with async_session_factory() as db:
                sync_svc = FinancialIntelligenceSync(session=db, eodhd_client=eodhd_client)
                ok = await sync_svc.sync_company(ticker=ticker, exchange=exchange)
                await db.commit()
                if ok:
                    synced += 1
                else:
                    skipped += 1
        except Exception as e:
            failed += 1
            logger.warning("Financial sync failed for %s.%s: %s", ticker, exchange, e)

        completed = synced + failed
        if completed > 0 and completed % 10 == 0:
            logger.info(
                "  financial sync progress: %d/%d synced, %d failed, %d skipped",
                synced,
                limit,
                failed,
                skipped,
            )

    logger.info(
        "Financial snapshots: %d synced, %d failed, %d skipped", synced, failed, skipped
    )
    return synced


async def step_assign_verticals() -> int:
    """Assign vertical_id to all listed_companies that still have NULL vertical_id.

    Safe to re-run — only touches NULL rows.
    """
    from packages.database.src.session import async_session_factory
    from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

    async with async_session_factory() as db:
        sync_svc = FinancialIntelligenceSync(session=db)
        result = await sync_svc.assign_verticals_to_companies()
        await db.commit()
        logger.info(
            "Vertical assignment: %d assigned, %d no match",
            result["assigned"],
            result["no_match"],
        )
        return result["assigned"]


async def step_upgrade_gics() -> int:
    """Re-assign companies from name-keyword to GICS-based vertical assignment.

    Processes companies that already have a vertical_id but now also have
    gics_industry data, preferring the more authoritative GICS classification.
    Safe to re-run — only updates rows where the GICS assignment differs.
    """
    from packages.database.src.session import async_session_factory
    from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

    async with async_session_factory() as db:
        sync_svc = FinancialIntelligenceSync(session=db)
        result = await sync_svc.upgrade_to_gics_assignment()
        await db.commit()
        logger.info(
            "GICS upgrade: %d companies upgraded from name-keyword to GICS assignment",
            result["upgraded"],
        )
        return result["upgraded"]


async def step_compute_benchmarks(db, eodhd_client) -> int:
    """Compute vertical benchmarks for all 12 market verticals.

    Tries the current quarter first, then falls back up to 8 quarters back
    (covering 2 full years).  This ensures benchmarks are computed even when
    the current quarter has no financial snapshot data yet.
    """
    from packages.database.src.vertical_seeds import VERTICAL_SEEDS
    from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

    sync = FinancialIntelligenceSync(session=db, eodhd_client=eodhd_client)

    # Build list of period labels: current quarter first, then the 7 prior quarters.
    now = datetime.now(tz=UTC)
    current_quarter = (now.month - 1) // 3 + 1
    periods_to_try: list[str] = []
    year, quarter = now.year, current_quarter
    for _ in range(8):
        periods_to_try.append(f"{year}-Q{quarter}")
        quarter -= 1
        if quarter == 0:
            quarter = 4
            year -= 1

    success = 0
    # Track the period that succeeded for each vertical to avoid double-counting.
    resolved: dict[str, str] = {}

    for v in VERTICAL_SEEDS:
        slug = v["slug"]
        if slug in resolved:
            continue
        for period_label in periods_to_try:
            try:
                ok = await sync.compute_and_store_benchmarks(
                    vertical_slug=slug,
                    period_label=period_label,
                )
                if ok:
                    resolved[slug] = period_label
                    success += 1
                    logger.info("  benchmark: %s done (%s)", slug, period_label)
                    break
            except Exception as exc:
                logger.warning("  benchmark: %s FAILED for %s — %s", slug, period_label, exc)
        else:
            logger.info("  benchmark: %s skipped (no data in any of last 8 quarters)", slug)

    await db.commit()
    logger.info(
        "Benchmarks: %d/%d computed", success, len(VERTICAL_SEEDS)
    )
    return success


async def step_ingest_rss(db) -> int:
    """Fetch all configured RSS feeds and insert new articles into market_articles."""
    from sqlalchemy import select

    from packages.database.src.models import MarketArticle
    from packages.integrations.rss.src.client import RSSClient

    client = RSSClient()
    # fetch_all() returns dict[feed_name, list[RSSArticle]]
    feed_results = await client.fetch_all()

    inserted = 0
    for _feed_name, articles in feed_results.items():
        for art in articles:
            if not art.url:
                continue

            existing = await db.execute(
                select(MarketArticle).where(MarketArticle.source_url == art.url)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            db.add(
                MarketArticle(
                    source_name=art.source_name,
                    source_url=art.url,
                    title=art.title,
                    summary=art.summary,
                    published_at=art.published_at,
                    is_classified=False,
                )
            )
            inserted += 1

    await db.commit()
    logger.info("RSS articles: %d ingested", inserted)
    return inserted


async def step_classify_embed(db) -> None:
    """Classify and embed ALL unclassified articles into Qdrant.

    Runs pipeline.run() in a loop until no unclassified articles remain, so
    the batch_size ceiling does not silently cap throughput.
    """
    from packages.intelligence.src import ArticleIntelligencePipeline

    pipeline = ArticleIntelligencePipeline(db)
    total_classified = 0
    total_embedded = 0
    total_qdrant = 0
    batch_num = 0

    while True:
        batch_num += 1
        stats = await pipeline.run(batch_size=500)
        total_classified += stats.classified
        total_embedded += stats.embedded
        total_qdrant += stats.qdrant_upserted

        if stats.classified == 0:
            # No more unclassified articles
            break

        logger.info(
            "Article pipeline batch %d: classified=%d embedded=%d qdrant=%d",
            batch_num,
            stats.classified,
            stats.embedded,
            stats.qdrant_upserted,
        )

    logger.info(
        "Article pipeline complete (%d batches): classified=%d embedded=%d qdrant=%d",
        batch_num,
        total_classified,
        total_embedded,
        total_qdrant,
    )


async def step_extract_document_intelligence(limit: int = 50) -> int:
    """Extract structured business signals from already-chunked documents."""
    from packages.database.src.session import async_session_factory
    from packages.intelligence.src.document_intel import DocumentIntelligenceExtractor

    try:
        async with async_session_factory() as db:
            extractor = DocumentIntelligenceExtractor(db)
            count = await extractor.process_pending_documents(batch_size=limit)
            await db.commit()
            logger.info("Document intelligence: %d signals extracted", count)
            return count
    except Exception as exc:
        logger.warning("Document intelligence extraction failed (non-fatal): %s", exc)
        return 0


async def step_discover_documents(db, days_back: int = 365) -> dict[str, int]:
    """Discover SGX corporate announcements going back N days."""
    from packages.documents.src.sync import DocumentSyncService

    svc = DocumentSyncService(session=db)
    # stock_codes=None queries all active SG-exchange companies (up to 200)
    counts = await svc.discover_announcements(stock_codes=None, days_back=days_back)
    logger.info(
        "SGX documents: %d discovered, %d already known, %d errors",
        counts["discovered"],
        counts["already_known"],
        counts["errors"],
    )
    return counts


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def main(limit: int, skip_financials: bool, skip_docs: bool) -> None:
    from packages.database.src.session import async_session_factory, init_db
    from packages.integrations.eodhd.src.client import get_eodhd_client
    from packages.vector_store.src.store import get_qdrant_store

    logger.info("=== GTM Advisor Knowledge Base Build ===")
    logger.info("Started at %s", datetime.now(tz=UTC).isoformat())

    # Ensure DB tables exist (idempotent — SQLAlchemy uses CREATE TABLE IF NOT EXISTS)
    await init_db()
    logger.info("Database tables ready")

    # Ensure Qdrant collections exist (non-fatal if Qdrant is unavailable)
    try:
        qdrant = get_qdrant_store()
        await qdrant.ensure_collections()
        logger.info("Qdrant collections ready")
    except Exception as exc:
        logger.warning("Qdrant unavailable — vector search disabled: %s", exc)

    eodhd_client = get_eodhd_client()

    # Steps 1 + 2: short-lived writes — seed verticals and company roster
    async with async_session_factory() as db:
        await step_seed_verticals(db)
        await step_sync_roster(db, eodhd_client)

    if not skip_financials:
        # Step 3: Financial snapshots — manages its own per-company sessions so
        # each company is committed independently (resumable on kill).
        try:
            await step_sync_financials(eodhd_client, limit=limit)
        except Exception as exc:
            logger.warning(
                "Financial sync failed (non-fatal, continuing with RSS): %s", exc
            )

        # Step 3b: Assign verticals to companies that are still NULL.
        # Must run after financials so gics_sector fields are populated.
        await step_assign_verticals()

        # Step 3c: Upgrade name-keyword assignments to GICS where possible.
        # GICS industry data is more authoritative than heuristic name matching.
        await step_upgrade_gics()

        # Step 4: Vertical benchmarks — requires committed snapshot data from step 3.
        # Separate session so we see the committed rows.
        async with async_session_factory() as db:
            await step_compute_benchmarks(db, eodhd_client)

    # Step 5: RSS articles
    async with async_session_factory() as db:
        await step_ingest_rss(db)

    # Step 6: Classify + embed articles (loops until all articles are processed)
    async with async_session_factory() as db:
        await step_classify_embed(db)

    if not skip_docs:
        # Step 7: SGX document discovery (non-fatal)
        async with async_session_factory() as db:
            try:
                await step_discover_documents(db, days_back=365)
            except Exception as exc:
                logger.warning("Document discovery failed (non-fatal): %s", exc)

        # Step 8: Extract intelligence from documents (non-fatal)
        await step_extract_document_intelligence(limit=50)

    logger.info("=== Knowledge Base Build Complete ===")
    logger.info("Finished at %s", datetime.now(tz=UTC).isoformat())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build the GTM Advisor Singapore market intelligence knowledge base"
    )
    parser.add_argument(
        "--skip-financials",
        action="store_true",
        help="Skip EODHD financial sync (useful when API quota is low)",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip SGX document discovery",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Max companies to sync financial snapshots for (default: 300)",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            limit=args.limit,
            skip_financials=args.skip_financials,
            skip_docs=args.skip_docs,
        )
    )
