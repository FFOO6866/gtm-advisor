"""APScheduler integration — always-on scheduled jobs.

Registers cron/interval jobs that run GTM Advisor agents on a schedule.
This is what makes GTM Advisor an "always-on workforce" vs a one-shot tool.

Schedule:
    Every 1 hour:         SignalMonitorAgent — scans for market signals
    Every day 08:00:      SequenceRunner    — sends due sequence steps (after approval)
    Every Sunday:         LeadEnrichmentAgent — re-enriches stale leads
    Every Monday:         Attribution summary — weekly ROI digest
    Every 2 hours :00:   RSS Feed Ingestion — Singapore business news
    Every day 06:00:     SGX Announcement Discovery
    Every day 03:00:     Document Processing — download + extract + embed PDFs
    Every day 02:00:     Financial Snapshot Sync — top 200 companies
    Every Saturday 01:00: SGX Roster Sync — full symbol list refresh
    Every 2 hours :30:   Article Intelligence Pipeline — classify + embed + Qdrant
    Every day 05:00:     Qdrant Catchup — embed unembedded document chunks
    Every day 04:00:     Vertical Benchmark Computation — percentile benchmarks for all 12 verticals
    Every day 03:30:     Document Intelligence — extract business signals from processed documents
    Every 2 hours :45:   Research Embedder — embed public research cache rows → Qdrant
    Every Sunday 04:00:  Singapore Reference Scraper — PSG/PDPA/MAS/EnterpriseSG data
    Every Saturday 03:00: Knowledge Guide Resynthesis — update guides with accumulated research
    Every Sunday 05:00:  Vertical Intelligence Synthesis — per-vertical intelligence reports

All jobs run in the background. Failed jobs are logged but do NOT crash the app.
APScheduler is embedded in-process (no external queue needed for MVP).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Singapore")
    return _scheduler


async def start_scheduler() -> None:
    """Start the APScheduler. Called from FastAPI lifespan."""
    scheduler = get_scheduler()

    # --- Qdrant collection bootstrap ---
    try:
        from packages.vector_store.src import get_qdrant_store
        qdrant_store = get_qdrant_store()
        await qdrant_store.ensure_collections()
        logger.info("Qdrant collections ensured")
    except Exception:
        logger.warning("Qdrant not available — vector search disabled")

    # --- Job 1: Signal Monitor (every hour) ---
    scheduler.add_job(
        _run_signal_monitor_all_active,
        trigger=IntervalTrigger(hours=1),
        id="signal_monitor_hourly",
        name="Signal Monitor — all active workforces",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # --- Job 2: Sequence Runner (daily 08:00 SGT) ---
    scheduler.add_job(
        _run_sequence_runner,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Singapore"),
        id="sequence_runner_daily",
        name="Sequence Runner — process due steps",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    # --- Job 3: Lead Re-enrichment (weekly Sunday 02:00 SGT) ---
    scheduler.add_job(
        _run_lead_enrichment_all,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0, timezone="Asia/Singapore"),
        id="lead_enrichment_weekly",
        name="Lead Enrichment — weekly re-enrichment",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=1800,
    )

    # --- Job 4: Weekly ROI Summary (Monday 07:00 SGT) ---
    scheduler.add_job(
        _run_weekly_roi_summary,
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=0, timezone="Asia/Singapore"),
        id="roi_summary_weekly",
        name="Weekly ROI Summary — attribution digest",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=1800,
    )

    # --- Job 5: RSS Feed Ingestion (every 2 hours) ---
    scheduler.add_job(
        _ingest_rss_feeds,
        trigger=IntervalTrigger(hours=2),
        id="rss_ingestion",
        name="RSS Feed Ingestion — Singapore business news",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    # --- Job 6: SGX Announcement Discovery (daily 06:00 SGT) ---
    scheduler.add_job(
        _discover_sgx_announcements,
        trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Singapore"),
        id="sgx_discovery_daily",
        name="SGX Announcement Discovery",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=1800,
    )

    # --- Job 7: Document Processing (daily 03:00 SGT) ---
    scheduler.add_job(
        _process_pending_documents,
        trigger=CronTrigger(hour=3, minute=0, timezone="Asia/Singapore"),
        id="document_processing_daily",
        name="Document Processing — download + extract + embed PDFs",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 8: Financial Snapshot Sync (daily 02:00 SGT) ---
    scheduler.add_job(
        _sync_financial_snapshots,
        trigger=CronTrigger(hour=2, minute=0, timezone="Asia/Singapore"),
        id="financial_sync_daily",
        name="Financial Snapshot Sync — top 200 companies",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=7200,
    )

    # --- Job 9: SGX Roster Sync (weekly Saturday 01:00 SGT) ---
    scheduler.add_job(
        _sync_sgx_roster,
        trigger=CronTrigger(day_of_week="sat", hour=1, minute=0, timezone="Asia/Singapore"),
        id="sgx_roster_weekly",
        name="SGX Roster Sync — full symbol list refresh",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 10: Article Intelligence Pipeline (every 2h at :30 SGT) ---
    scheduler.add_job(
        _run_article_pipeline,
        trigger=CronTrigger(minute=30, hour="*/2", timezone="Asia/Singapore"),
        id="article_pipeline_bihourly",
        name="Article Intelligence Pipeline — classify + embed + Qdrant",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    # --- Job 11: Qdrant Chunk Catchup (daily 05:00 SGT) ---
    scheduler.add_job(
        _run_qdrant_catchup,
        trigger=CronTrigger(hour=5, minute=0, timezone="Asia/Singapore"),
        id="qdrant_catchup_daily",
        name="Qdrant Catchup — embed unembedded document chunks",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 12: Vertical Benchmark Computation (daily 04:00 SGT) ---
    scheduler.add_job(
        _compute_vertical_benchmarks,
        trigger=CronTrigger(hour=4, minute=0, timezone="Asia/Singapore"),
        id="vertical_benchmarks_daily",
        name="Vertical Benchmark Computation — percentile benchmarks for all 12 verticals",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 13: Document Intelligence Extraction (daily 04:15 SGT) ---
    # Runs at 04:15 to give Job 7 (document processing, 03:00) a full hour to
    # complete before intelligence extraction begins. Job 12 (benchmarks, 04:00)
    # writes to different tables so concurrent execution at 04:00/04:15 is safe.
    scheduler.add_job(
        _run_document_intelligence,
        trigger=CronTrigger(hour=4, minute=15, timezone="Asia/Singapore"),
        id="document_intelligence_daily",
        name="Document Intelligence — extract business signals from processed documents",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 14: Research Embedder Pipeline (every 2h at :45 SGT) ---
    # Runs at :45 to interleave with Article Pipeline (:30) without overlapping.
    scheduler.add_job(
        _run_research_embedder,
        trigger=CronTrigger(minute=45, hour="*/2", timezone="Asia/Singapore"),
        id="research_embedder_bihourly",
        name="Research Embedder — embed public research cache rows into Qdrant",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    # --- Job 15: Singapore Reference Scraper (weekly Sunday 04:00 SGT) ---
    # Scrapes PSG, PDPC, EnterpriseSG, MAS public pages for current grant/
    # regulatory data. Runs after SGX roster (01:00) and before article
    # pipeline (:30) to avoid Qdrant write contention.
    scheduler.add_job(
        _run_sg_reference_scraper,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0, timezone="Asia/Singapore"),
        id="sg_reference_weekly",
        name="Singapore Reference Scraper — PSG/PDPA/MAS/EnterpriseSG data",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 16: Weekly Knowledge Guide Resynthesis (Saturday 03:00 SGT) ---
    # Re-synthesizes domain guides that have accumulated 3+ new public research
    # rows since the last synthesis.  Uses the in-process Qdrant client (no
    # file-lock conflict) and GPT-4o.  Saves results as {slug}_live.json.
    scheduler.add_job(
        _run_guide_resynthesis,
        trigger=CronTrigger(day_of_week="sat", hour=3, minute=0, timezone="Asia/Singapore"),
        id="guide_resynthesis_weekly",
        name="Knowledge Guide Resynthesis — update guides with accumulated research",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=7200,
    )

    # --- Job 17: GTM Financial Intelligence Extraction (daily 04:30 SGT) ---
    # Runs at 04:30, after Document Intelligence (04:15) completes.
    # Extracts structured GTM insights (channels, initiatives, segments)
    # from annual report chunks and stores as SignalEvent rows.
    scheduler.add_job(
        _run_gtm_financial_extraction,
        trigger=CronTrigger(hour=4, minute=30, timezone="Asia/Singapore"),
        id="gtm_financial_extraction_daily",
        name="GTM Financial Intelligence — extract GTM insights from annual reports",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # --- Job 18: Vertical Intelligence Synthesis (Sunday 05:00 SGT) ---
    # Runs after all weekly data pipelines complete.
    # Synthesizes per-vertical intelligence reports from accumulated
    # articles, benchmarks, financial trends, and executive movements.
    scheduler.add_job(
        _run_vertical_intelligence_synthesis,
        trigger=CronTrigger(day_of_week="sun", hour=5, minute=0, timezone="Asia/Singapore"),
        id="vertical_intelligence_weekly",
        name="Vertical Intelligence — synthesize per-vertical reports",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=7200,
    )

    scheduler.start()
    logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))


async def stop_scheduler() -> None:
    """Stop the scheduler. Called from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    _scheduler = None


async def _run_signal_monitor_all_active() -> None:
    """Run SignalMonitorAgent for all companies with active workforces."""
    logger.info("scheduled_job_start", job="signal_monitor")
    try:
        from sqlalchemy import select

        from agents.signal_monitor.src import SignalMonitorAgent
        from packages.database.src.models import Company, WorkforceConfig, WorkforceStatus
        from packages.database.src.session import async_session_factory

        async with async_session_factory() as db:
            stmt = (
                select(WorkforceConfig, Company)
                .join(Company, Company.id == WorkforceConfig.company_id)
                .where(WorkforceConfig.status == WorkforceStatus.ACTIVE)
            )
            rows = (await db.execute(stmt)).all()
            logger.info("signal_monitor_active_workforces", count=len(rows))

            from packages.database.src.models import SignalEvent, SignalUrgency

            for _config, company in rows[:20]:  # Cap at 20 per run
                try:
                    agent = SignalMonitorAgent()
                    context = {
                        "company_id": str(company.id),
                        "industry": company.industry or "technology",
                        "competitors": [],
                        "target_region": "Singapore",
                        "scan_hours": 2,
                    }
                    result = await agent.run(
                        task=f"Monitor signals for {company.name}",
                        context=context,
                    )
                    logger.info(
                        "signal_monitor_complete",
                        company=company.name,
                        signals_found=result.signals_found if result else 0,
                        signals_actionable=result.signals_actionable if result else 0,
                    )
                    # Persist high-relevance signals to DB
                    if result and result.scored_signals:
                        for sig in result.scored_signals:
                            score = sig.get("relevance_score", 0.0)
                            if score >= 0.85:
                                urgency = SignalUrgency.IMMEDIATE
                            elif score >= 0.65:
                                urgency = SignalUrgency.THIS_WEEK
                            else:
                                urgency = SignalUrgency.THIS_MONTH
                            db.add(SignalEvent(
                                company_id=company.id,
                                signal_type=sig.get("signal_type", "general_news"),
                                urgency=urgency,
                                headline=sig.get("signal_text", "")[:500],
                                source=sig.get("source", ""),
                                relevance_score=score,
                                competitors_mentioned=sig.get("competitors_mentioned", []),
                                recommended_action=sig.get("recommended_action"),
                            ))
                        await db.commit()

                    # Auto-enroll leads when high-relevance signals detected
                    try:
                        from services.gateway.src.services.sequence_engine import SequenceEngine
                        engine = SequenceEngine(db)
                        enrollments = await engine.auto_enroll_from_signals(
                            company_id=str(company.id),
                            db=db,
                        )
                        if enrollments > 0:
                            logger.info(
                                "auto_enrolled_from_signals",
                                company_id=str(company.id),
                                count=enrollments,
                            )
                    except Exception as e:
                        logger.warning(
                            "auto_enroll_from_signals_failed",
                            company_id=str(company.id),
                            error=str(e),
                        )
                except Exception as e:
                    logger.error(
                        "signal_monitor_company_failed",
                        company=str(company.id),
                        error=str(e),
                    )

    except Exception as e:
        logger.error("scheduled_job_failed", job="signal_monitor", error=str(e))


async def _run_sequence_runner() -> None:
    """Run the sequence engine to process due outreach steps."""
    logger.info("scheduled_job_start", job="sequence_runner")
    try:
        from packages.database.src.session import async_session_factory
        from services.gateway.src.services.sequence_engine import SequenceEngine

        async with async_session_factory() as db:
            engine = SequenceEngine(db)
            processed = await engine.run_due_steps()
            logger.info("sequence_runner_complete", steps_queued_for_approval=processed)

    except Exception as e:
        logger.error("scheduled_job_failed", job="sequence_runner", error=str(e))


async def _run_lead_enrichment_all() -> None:
    """Re-enrich stale leads for all active companies."""
    logger.info("scheduled_job_start", job="lead_enrichment")
    try:
        from datetime import timedelta

        from sqlalchemy import select

        from agents.lead_enrichment.src import LeadEnrichmentAgent
        from packages.database.src.models import Lead
        from packages.database.src.session import async_session_factory

        cutoff = datetime.now(UTC) - timedelta(days=30)  # Re-enrich leads > 30 days old

        async with async_session_factory() as db:
            stmt = select(Lead).where(
                (Lead.updated_at < cutoff) | (Lead.updated_at.is_(None))
            ).limit(200)
            leads = (await db.execute(stmt)).scalars().all()

        if not leads:
            logger.info("lead_enrichment_nothing_to_do")
            return

        agent = LeadEnrichmentAgent()
        lead_dicts = [
            {
                "id": str(lead.id),
                "email": lead.contact_email,
                "name": lead.contact_name,
                "title": lead.contact_title,
                "company": lead.lead_company_name,
            }
            for lead in leads
        ]
        result = await agent.run(
            task="Re-enrich stale leads",
            context={"leads": lead_dicts},
        )
        logger.info(
            "lead_enrichment_complete",
            processed=result.total_processed if result else 0,
            qualified=result.total_qualified if result else 0,
            blocked=result.total_blocked if result else 0,
        )

    except Exception as e:
        logger.error("scheduled_job_failed", job="lead_enrichment", error=str(e))


async def _run_weekly_roi_summary() -> None:
    """Generate weekly ROI attribution summary for all active companies."""
    logger.info("scheduled_job_start", job="roi_summary")
    try:
        from datetime import timedelta

        from sqlalchemy import func, select

        from packages.database.src.models import AttributionEvent
        from packages.database.src.session import async_session_factory

        week_ago = datetime.now(UTC) - timedelta(days=7)

        async with async_session_factory() as db:
            stmt = (
                select(
                    AttributionEvent.company_id,
                    AttributionEvent.event_type,
                    func.count().label("count"),
                    func.sum(AttributionEvent.pipeline_value_sgd).label("pipeline"),
                )
                .where(AttributionEvent.occurred_at >= week_ago)
                .group_by(AttributionEvent.company_id, AttributionEvent.event_type)
            )
            rows = (await db.execute(stmt)).all()

        summary: dict[str, dict] = {}
        for row in rows:
            cid = str(row.company_id)
            if cid not in summary:
                summary[cid] = {}
            summary[cid][row.event_type] = {
                "count": row.count,
                "pipeline_sgd": float(row.pipeline or 0),
            }

        logger.info("roi_summary_complete", companies=len(summary), summary=summary)
        # TODO: send summary email or push to dashboard notification

    except Exception as e:
        logger.error("scheduled_job_failed", job="roi_summary", error=str(e))


async def _ingest_rss_feeds() -> None:
    """Ingest RSS feeds and classify articles into market_articles table."""
    logger.info("scheduled_job_start", job="rss_ingestion")
    try:
        from sqlalchemy import select

        from packages.database.src.models import MarketArticle
        from packages.database.src.session import async_session_factory
        from packages.integrations.rss.src.client import RSSClient

        client = RSSClient()
        articles = await client.fetch_recent(hours=3)

        async with async_session_factory() as db:
            new_count = 0
            for article in articles:
                existing = await db.execute(
                    select(MarketArticle.id).where(MarketArticle.source_url == article.url).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue
                db.add(MarketArticle(
                    source_name=article.source_name,
                    source_url=article.url,
                    title=article.title,
                    summary=article.summary,
                    published_at=article.published_at,
                    is_classified=False,
                ))
                new_count += 1
            await db.commit()
        logger.info("rss_ingestion_complete", new_articles=new_count, total_fetched=len(articles))
    except Exception as e:
        logger.error("scheduled_job_failed", job="rss_ingestion", error=str(e))


async def _discover_sgx_announcements() -> None:
    """Discover new SGX announcements for all active SGX companies."""
    logger.info("scheduled_job_start", job="sgx_discovery")
    try:
        from packages.database.src.session import async_session_factory
        from packages.documents.src.sync import DocumentSyncService
        from packages.integrations.sgx.src.client import get_sgx_client

        # Reset the cached client so each daily run starts with a fresh
        # _endpoint_broken=False state — ensures we retry SGX after it recovers.
        get_sgx_client.cache_clear()

        async with async_session_factory() as db:
            svc = DocumentSyncService(db)
            counts = await svc.discover_announcements(days_back=2)
            logger.info("sgx_discovery_complete", **counts)
    except Exception as e:
        logger.error("scheduled_job_failed", job="sgx_discovery", error=str(e))


async def _process_pending_documents() -> None:
    """Download, extract, and embed pending corporate documents."""
    logger.info("scheduled_job_start", job="document_processing")
    try:
        from packages.database.src.models import DocumentType
        from packages.database.src.session import async_session_factory
        from packages.documents.src.sync import DocumentSyncService

        async with async_session_factory() as db:
            svc = DocumentSyncService(db)
            counts = await svc.process_pending_documents(
                document_types=[DocumentType.ANNUAL_REPORT, DocumentType.SUSTAINABILITY_REPORT],
                batch_size=5,   # conservative — PDF processing is slow
            )
            logger.info("document_processing_complete", **counts)
    except Exception as e:
        logger.error("scheduled_job_failed", job="document_processing", error=str(e))


async def _sync_financial_snapshots() -> None:
    """Sync full financial data for top 200 companies by market cap."""
    logger.info("scheduled_job_start", job="financial_sync")
    try:
        from packages.database.src.session import async_session_factory
        from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

        async with async_session_factory() as db:
            sync = FinancialIntelligenceSync(db)
            counts = await sync.sync_financial_snapshots(limit=200)
            logger.info("financial_sync_complete", **counts)
    except Exception as e:
        logger.error("scheduled_job_failed", job="financial_sync", error=str(e))


async def _sync_sgx_roster() -> None:
    """Weekly: refresh the full SGX company roster from EODHD."""
    logger.info("scheduled_job_start", job="sgx_roster_sync")
    try:
        from packages.database.src.session import async_session_factory
        from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

        async with async_session_factory() as db:
            sync = FinancialIntelligenceSync(db)
            counts = await sync.sync_exchange_roster("SG")
            logger.info("sgx_roster_sync_complete", **counts)
    except Exception as e:
        logger.error("scheduled_job_failed", job="sgx_roster_sync", error=str(e))


async def _run_article_pipeline() -> None:
    """Classify unclassified articles, embed them, push to Qdrant."""
    try:
        from packages.database.src.session import async_session_factory
        from packages.intelligence.src import ArticleIntelligencePipeline
        async with async_session_factory() as db:
            pipeline = ArticleIntelligencePipeline(db)
            stats = await pipeline.run(batch_size=200)
            logger.info(
                "Article pipeline: total=%d classified=%d embedded=%d qdrant=%d",
                stats.total, stats.classified, stats.embedded, stats.qdrant_upserted,
            )
    except Exception:
        logger.exception("Article pipeline job failed")


async def _run_qdrant_catchup() -> None:
    """Embed and push unembedded document chunks to Qdrant."""
    try:
        from packages.database.src.session import async_session_factory
        from packages.intelligence.src import ChunkEmbeddingPipeline
        async with async_session_factory() as db:
            pipeline = ChunkEmbeddingPipeline(db)
            count = await pipeline.run(batch_size=500)
            logger.info("Qdrant catchup: processed %d chunks", count)
    except Exception:
        logger.exception("Qdrant catchup job failed")


async def _run_document_intelligence() -> None:
    """Extract business signals from newly-processed documents."""
    try:
        from packages.database.src.session import async_session_factory
        from packages.intelligence.src.document_intel import DocumentIntelligenceExtractor

        async with async_session_factory() as db:
            extractor = DocumentIntelligenceExtractor(db)
            count = await extractor.process_pending_documents(batch_size=20)
            logger.info("Document intelligence: %d signals extracted", count)
            await db.commit()
    except Exception:
        logger.exception("Document intelligence job failed")


async def _compute_vertical_benchmarks() -> None:
    """Compute percentile benchmarks for all 12 verticals after financial sync."""
    try:
        from datetime import UTC, datetime

        from packages.database.src.session import async_session_factory
        from packages.database.src.vertical_seeds import VERTICAL_SEEDS
        from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync

        now = datetime.now(tz=UTC)
        quarter = (now.month - 1) // 3 + 1
        period_label = f"{now.year}-Q{quarter}"

        async with async_session_factory() as db:
            sync = FinancialIntelligenceSync(session=db)

            success = 0
            for v in VERTICAL_SEEDS:
                try:
                    await sync.compute_and_store_benchmarks(
                        vertical_slug=v["slug"],
                        period_label=period_label,
                    )
                    success += 1
                except Exception:
                    logger.exception(
                        "Benchmark failed for vertical %s", v["slug"]
                    )
                    # Roll back any aborted DB transaction so the session
                    # remains usable for the remaining verticals.
                    await db.rollback()

            await db.commit()
            logger.info(
                "Vertical benchmarks computed: %d/12 succeeded", success
            )
    except Exception:
        logger.exception("Benchmark computation job failed")


async def _run_research_embedder() -> None:
    """Embed unembedded public ResearchCache rows and upsert to research_cache_sg Qdrant."""
    logger.info("scheduled_job_start", job="research_embedder")
    try:
        from packages.database.src.session import async_session_factory  # noqa: PLC0415
        from packages.intelligence.src.research_embedder import (  # noqa: PLC0415
            ResearchEmbedderPipeline,
        )

        async with async_session_factory() as db:
            pipeline = ResearchEmbedderPipeline(session=db)
            stats = await pipeline.run()
            logger.info(
                "research_embedder_complete",
                total=stats.total,
                embedded=stats.embedded,
                qdrant_upserted=stats.qdrant_upserted,
            )
    except Exception:
        logger.exception("research_embedder_failed")


async def _run_sg_reference_scraper() -> None:
    """Scrape Singapore government reference data (PSG, PDPC, MAS, EnterpriseSG)."""
    logger.info("scheduled_job_start", job="sg_reference_scraper")
    try:
        from sqlalchemy import select  # noqa: PLC0415

        from packages.database.src.models import SgKnowledgeArticle  # noqa: PLC0415
        from packages.database.src.session import async_session_factory  # noqa: PLC0415
        from packages.integrations.sg_reference.src.scraper import (
            SgReferenceScraper,  # noqa: PLC0415
        )

        scraper = SgReferenceScraper()
        all_items: list[dict] = []

        for method in [
            scraper.scrape_psg_vendors,
            scraper.scrape_pdpc_decisions,
            scraper.scrape_enterprisesg_programmes,
            scraper.scrape_mas_consultations,
        ]:
            items, error = await method()
            if error:
                logger.warning("sg_scraper_source_failed", source=method.__name__, error=error)
            if not items:
                logger.warning("sg_scraper_zero_items", source=method.__name__)
            all_items.extend(items)

        if not all_items:
            logger.warning("sg_reference_scraper_no_data")
            return

        async with async_session_factory() as db:
            inserted = 0
            for item in all_items:
                url = item.get("url", "")
                if not url:
                    continue
                # Upsert: skip if URL already exists
                existing = (await db.execute(
                    select(SgKnowledgeArticle).where(SgKnowledgeArticle.url == url).limit(1)
                )).scalar_one_or_none()
                if existing:
                    existing.title = item.get("title", existing.title)
                    existing.summary = item.get("summary") or item.get("description")
                else:
                    db.add(SgKnowledgeArticle(
                        source=item.get("source", "unknown"),
                        category_type=item.get("category_type", "general"),
                        title=item.get("title", "")[:500],
                        summary=item.get("summary") or item.get("description"),
                        url=url[:1000],
                        last_verified=item.get("last_verified"),
                    ))
                    inserted += 1
            try:
                await db.commit()
                logger.info("sg_reference_scraper_complete", total=len(all_items), inserted=inserted)
            except Exception:
                await db.rollback()
                logger.warning("sg_reference_scraper_commit_failed", exc_info=True)
    except Exception:
        logger.exception("sg_reference_scraper_failed")


async def _run_guide_resynthesis() -> None:
    """Re-synthesize domain guides that have accumulated new public research.

    For each guide in ``_AGENT_GUIDE_MAP``, count recent public ResearchCache
    rows that match the guide's relevance keywords.  If a guide has ≥3 new
    rows (created in the last 7 days), re-synthesize it using Qdrant book
    chunks + the new research texts.  Results are saved as ``{slug}_live.json``.
    """
    logger.info("scheduled_job_start", job="guide_resynthesis")
    try:
        import re  # noqa: PLC0415
        from datetime import timedelta  # noqa: PLC0415

        from sqlalchemy import select  # noqa: PLC0415

        from packages.database.src.models import ResearchCache  # noqa: PLC0415
        from packages.database.src.session import async_session_factory  # noqa: PLC0415
        from packages.knowledge.src.knowledge_mcp import (  # noqa: PLC0415
            get_guide_relevance_keywords,
            get_knowledge_mcp,
        )

        # Use naive UTC to match SQLite's naive datetime storage.
        cutoff = (datetime.now(UTC) - timedelta(days=7)).replace(tzinfo=None)

        async with async_session_factory() as db:
            # Load all recent public research rows.
            result = await db.execute(
                select(ResearchCache)
                .where(
                    ResearchCache.is_public.is_(True),
                    ResearchCache.created_at >= cutoff,
                )
                .order_by(ResearchCache.created_at.desc())
                .limit(500)
            )
            recent_rows = list(result.scalars().all())

        if not recent_rows:
            logger.info("guide_resynthesis_skipped", reason="no recent public research")
            return

        # Score each guide by word-boundary keyword overlap with recent research.
        guide_keywords = get_guide_relevance_keywords()
        guide_research: dict[str, list[str]] = {}
        for slug, keywords in guide_keywords.items():
            # Pre-compile word-boundary patterns to avoid substring false positives
            # (e.g. "sg" matching "messaging", "ads" matching "downloads").
            patterns = [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in keywords]
            matching_texts: list[str] = []
            for row in recent_rows:
                row_text = f"{row.query} {row.content[:500]}".lower()
                hits = sum(1 for pat in patterns if pat.search(row_text))
                if hits >= 2:
                    matching_texts.append(row.content[:1000])
            if len(matching_texts) >= 3:
                guide_research[slug] = matching_texts

        if not guide_research:
            logger.info(
                "guide_resynthesis_skipped",
                reason="no guide has 3+ matching research rows",
                total_rows=len(recent_rows),
            )
            return

        kmcp = get_knowledge_mcp()
        synthesized = 0
        for slug, texts in guide_research.items():
            try:
                ok = await kmcp.synthesize_guide_incremental(slug=slug, extra_texts=texts)
                if ok:
                    synthesized += 1
                logger.info(
                    "guide_resynthesis_result",
                    slug=slug,
                    matching_research=len(texts),
                    success=ok,
                )
            except Exception:
                logger.exception("guide_resynthesis_slug_failed slug=%s", slug)

        logger.info("guide_resynthesis_complete", guides_updated=synthesized)

    except Exception:
        logger.exception("guide_resynthesis_failed")


async def _run_gtm_financial_extraction() -> None:
    """Extract structured GTM intelligence from processed annual reports.

    Uses begin_nested() savepoints inside process_pending_documents() so that
    individual document failures are rolled back without losing earlier work.
    The outer commit() only runs after the full batch completes.
    """
    logger.info("scheduled_job_start", job="gtm_financial_extraction")
    try:
        from packages.database.src.session import async_session_factory
        from packages.intelligence.src.gtm_financial_intel import GTMFinancialExtractor

        async with async_session_factory() as db:
            extractor = GTMFinancialExtractor(db)
            count = await extractor.process_pending_documents(batch_size=10)
            logger.info("GTM financial extraction: %d signals created", count)
            # Commit only after full batch — per-document savepoints inside
            # process_pending_documents() protect against partial corruption.
            await db.commit()
    except Exception:
        logger.exception("GTM financial extraction job failed")


async def _run_vertical_intelligence_synthesis() -> None:
    """Synthesize per-vertical intelligence reports from accumulated data."""
    logger.info("scheduled_job_start", job="vertical_intelligence_synthesis")
    try:
        from packages.database.src.session import async_session_factory
        from packages.intelligence.src.vertical_synthesizer import VerticalIntelligenceSynthesizer

        async with async_session_factory() as db:
            synthesizer = VerticalIntelligenceSynthesizer(db)
            count = await synthesizer.synthesize_all()
            logger.info("vertical_intelligence_synthesis_complete", reports_created=count)
    except Exception:
        logger.exception("Vertical intelligence synthesis job failed")
