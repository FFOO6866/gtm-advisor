"""Document sync service for SGX RegNet corporate filings.

Pipeline per document:
  1. SGX RegNet → discover new announcements → CompanyDocument rows
  2. Download PDF → update file_path, file_size_bytes, page_count
  3. Extract sections → DocumentChunk rows (is_chunked=False → True)
  4. Embed chunks → populate embedding fields

Runs as separate scheduler jobs:
  - Daily: discover_announcements (fast, no download)
  - Weekly: process_pending_documents (slow, batched)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    CompanyDocument,
    DocumentChunk,
    DocumentType,
    ListedCompany,
    MarketVertical,
)
from packages.documents.src.downloader import DocumentDownloader, get_document_downloader
from packages.documents.src.embeddings import EmbeddingService, get_embedding_service
from packages.documents.src.extractor import DocumentExtractor
from packages.integrations.eodhd.src.client import EODHDClient, get_eodhd_client
from packages.integrations.sec_edgar.src.client import SECEdgarClient
from packages.integrations.sgx.src.client import SGXClient, get_sgx_client

logger = structlog.get_logger(__name__)

# Maps SGX announcement category substrings → DocumentType.
# Checked in order; first match wins.  Keep longer / more specific strings first
# to avoid a broad keyword swallowing a narrower one.
_CATEGORY_MAP: list[tuple[str, DocumentType]] = [
    # ── High-value corporate filings ────────────────────────────────────────
    ("Annual Report", DocumentType.ANNUAL_REPORT),
    ("Sustainability Report", DocumentType.SUSTAINABILITY_REPORT),
    ("Sustainability", DocumentType.SUSTAINABILITY_REPORT),
    # ── Earnings / financial results ─────────────────────────────────────────
    ("Financial Results", DocumentType.EARNINGS_RELEASE),
    ("Quarterly Results", DocumentType.EARNINGS_RELEASE),
    ("Half Year Results", DocumentType.EARNINGS_RELEASE),
    ("Full Year Results", DocumentType.EARNINGS_RELEASE),
    ("Quarterly", DocumentType.EARNINGS_RELEASE),
    ("Half Year", DocumentType.EARNINGS_RELEASE),
    ("Full Year", DocumentType.EARNINGS_RELEASE),
    ("Earnings Release", DocumentType.EARNINGS_RELEASE),
    ("Profit Guidance", DocumentType.EARNINGS_RELEASE),
    # ── Material corporate events ────────────────────────────────────────────
    ("Merger", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Acquisition", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Takeover", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Disposal", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Joint Venture", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Strategic Investment", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Change in Director", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Change in Substantial Shareholder", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Material Information", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Material Contract", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Corporate Action", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Rights Issue", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Placement", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Delisting", DocumentType.MATERIAL_ANNOUNCEMENT),
    ("Winding Up", DocumentType.MATERIAL_ANNOUNCEMENT),
    # ── Investor presentations ────────────────────────────────────────────────
    ("Investor Presentation", DocumentType.INVESTOR_PRESENTATION),
    ("Analyst Briefing", DocumentType.INVESTOR_PRESENTATION),
    ("Investor Day", DocumentType.INVESTOR_PRESENTATION),
    # ── Press releases (low signal; mapped but not persisted by default) ──────
    ("Press Release", DocumentType.PRESS_RELEASE),
    ("Media Release", DocumentType.PRESS_RELEASE),
]

# Only these types are persisted to company_documents.
# PRESS_RELEASE has too low a signal-to-noise ratio for the document chunking pipeline.
# CIRCULAR (scheme documents, scheme of arrangement) is excluded — rarely contains GTM signal.
_SAVE_TYPES: frozenset[DocumentType] = frozenset(
    {
        DocumentType.ANNUAL_REPORT,
        DocumentType.SUSTAINABILITY_REPORT,
        DocumentType.EARNINGS_RELEASE,
        DocumentType.MATERIAL_ANNOUNCEMENT,   # M&A, strategic investments, leadership changes
        DocumentType.INVESTOR_PRESENTATION,    # Analyst briefings, investor days
    }
)


def _map_category(category: str) -> DocumentType:
    """Map an SGX announcement category string to a DocumentType."""
    for keyword, doc_type in _CATEGORY_MAP:
        if keyword.lower() in category.lower():
            return doc_type
    return DocumentType.PRESS_RELEASE


def _map_eodhd_news_to_doc_type(title: str, tags: list[str]) -> DocumentType:
    """Map an EODHD news item to a DocumentType using title and tag signals.

    EODHD news items carry free-text titles and tag lists.  We apply simple
    keyword matching on both to distinguish earnings releases and annual reports
    from generic press releases.

    Sustainability is checked first because sustainability report titles often
    also contain "annual" — without precedence the annual-report branch would
    swallow those items.

    Args:
        title: News article headline.
        tags: List of EODHD tag strings (e.g. ["earnings", "annual-report"]).

    Returns:
        The most specific matching DocumentType, defaulting to PRESS_RELEASE.
    """
    combined = (title + " " + " ".join(tags or [])).lower()

    # Sustainability first — more specific than annual report.
    _sustainability_kws = ["sustainability report", "esg report", "annual sustainability"]
    if any(kw in combined for kw in _sustainability_kws):
        return DocumentType.SUSTAINABILITY_REPORT

    # Annual report.
    _annual_kws = ["annual report", "full year results", "full-year results", "fy20", "fy 20"]
    if any(kw in combined for kw in _annual_kws):
        return DocumentType.ANNUAL_REPORT

    # Earnings.
    _earnings_kws = [
        "earnings", "quarterly results",
        "q1 ", "q2 ", "q3 ", "q4 ",
        "half year", "half-year", "interim results",
    ]
    if any(kw in combined for kw in _earnings_kws):
        return DocumentType.EARNINGS_RELEASE

    # Everything else is a press release (filtered out by _SAVE_TYPES).
    return DocumentType.PRESS_RELEASE


class DocumentSyncService:
    """Syncs corporate documents from SGX RegNet and company websites.

    Pipeline per document:
      1. SGX RegNet → discover new announcements → CompanyDocument rows
      2. Download PDF → update file_path, file_size_bytes, page_count
      3. Extract sections → DocumentChunk rows (is_chunked=False → True)
      4. Embed chunks → populate embedding fields

    Runs as separate scheduler jobs:
      - Daily: discover new announcements (fast, no download)
      - Weekly: download + process unprocessed documents (slow, batched)
    """

    MAX_PDF_SIZE_MB = 50
    EMBED_BATCH_SIZE = 20  # embed 20 chunks at a time

    def __init__(
        self,
        session: AsyncSession,
        sgx_client: SGXClient | None = None,
        downloader: DocumentDownloader | None = None,
        extractor: DocumentExtractor | None = None,
        embedding_service: EmbeddingService | None = None,
        eodhd_client: EODHDClient | None = None,
    ) -> None:
        self._session = session
        self._sgx = sgx_client or get_sgx_client()
        self._downloader = downloader or get_document_downloader()
        self._extractor = extractor or DocumentExtractor()
        self._embeddings = embedding_service or get_embedding_service()
        self._eodhd = eodhd_client or get_eodhd_client()
        self._edgar = SECEdgarClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def discover_announcements(
        self,
        stock_codes: list[str] | None = None,
        days_back: int = 7,
    ) -> dict[str, int]:
        """Discover new SGX announcements and save to CompanyDocument (without downloading).

        Primary source: SGX RegNet announcements API.
        Fallback: EODHD financial news when the SGX API returns 0 results across all
        tickers (indicates an API regression or endpoint change).

        Args:
            stock_codes: SGX tickers to poll. If None, queries all active SG-exchange
                         ListedCompany rows (up to 200).
            days_back: How many days of announcement history to retrieve per ticker.

        Returns:
            Counts dict: {"discovered": N, "already_known": N, "errors": N,
                          "source": "sgx"|"eodhd"}
        """
        tickers = stock_codes or await self._active_sg_tickers()

        # Use a single SGXClient instance so _endpoint_broken persists across tickers.
        sgx_client = self._sgx

        discovered = 0
        already_known = 0
        errors = 0

        for ticker in tickers:
            try:
                company = await self._company_by_ticker(ticker)
                if company is None:
                    logger.warning("discover_announcements.no_company", ticker=ticker)
                    errors += 1
                    continue

                announcements = await sgx_client.get_all_recent_announcements(
                    ticker, days_back=days_back
                )

                for ann in announcements:
                    doc_type = _map_category(ann.category)
                    if doc_type not in _SAVE_TYPES:
                        continue

                    # No URL → nothing to download; skip
                    if not ann.url:
                        continue

                    # Check whether this URL is already persisted
                    existing = await self._session.scalar(
                        select(CompanyDocument.id).where(
                            CompanyDocument.source_url == ann.url
                        )
                    )
                    if existing is not None:
                        already_known += 1
                        continue

                    published_str = ann.date.strftime("%Y-%m-%d")
                    doc = CompanyDocument(
                        listed_company_id=company.id,
                        document_type=doc_type,
                        title=ann.title or ann.announcement_id,
                        source_url=ann.url,
                        published_date=published_str,
                        sgx_announcement_id=ann.announcement_id,
                        sgx_category=ann.category,
                        is_downloaded=False,
                    )
                    self._session.add(doc)
                    discovered += 1

                await self._session.commit()

            except Exception as exc:
                logger.warning(
                    "discover_announcements.ticker_error",
                    ticker=ticker,
                    error=str(exc),
                )
                await self._session.rollback()
                errors += 1

        # If the SGX endpoint raised the known SGX_4041 regression error, fall
        # back to EODHD financial news.  We rely on the flag rather than a
        # zero-result check so that legitimately quiet windows (weekend, no
        # filings for the ticker set) do not trigger an unnecessary fallback.
        source = "sgx"
        if sgx_client.is_endpoint_broken and tickers:
            logger.info(
                "sgx_endpoint_broken_falling_back_to_eodhd",
                ticker_count=len(tickers),
                days_back=days_back,
            )
            eodhd_counts = await self._discover_from_eodhd_news(tickers, days_back)
            discovered += eodhd_counts["discovered"]
            already_known += eodhd_counts["already_known"]
            errors += eodhd_counts["errors"]
            source = "eodhd"

        # Always run SEC EDGAR discovery for US-listed SG companies.
        # This runs regardless of SGX status — EDGAR is an independent source
        # covering Sea Limited, Grab, PropertyGuru, and MoneyHero 20-F filings.
        edgar_counts = await self._discover_from_edgar(years_back=3)
        discovered += edgar_counts["discovered"]
        already_known += edgar_counts["already_known"]
        errors += edgar_counts["errors"]
        if edgar_counts["discovered"] > 0:
            source = source + "+edgar"

        logger.info(
            "discover_announcements.done",
            discovered=discovered,
            already_known=already_known,
            errors=errors,
            source=source,
        )
        return {
            "discovered": discovered,
            "already_known": already_known,
            "errors": errors,
            "source": source,
        }

    async def process_pending_documents(
        self,
        document_types: list[DocumentType] | None = None,
        batch_size: int = 10,
    ) -> dict[str, int]:
        """Download + extract + embed pending documents.

        Args:
            document_types: Types to process. Defaults to ANNUAL_REPORT and
                            SUSTAINABILITY_REPORT (the expensive, high-value ones).
            batch_size: Maximum number of documents to process in this run.

        Returns:
            Counts dict: {"downloaded": N, "extracted": N, "embedded": N, "failed": N}
        """
        types_to_process = document_types or [
            DocumentType.ANNUAL_REPORT,
            DocumentType.SUSTAINABILITY_REPORT,
        ]

        query = (
            select(CompanyDocument)
            .where(
                CompanyDocument.is_downloaded.is_(False),
                CompanyDocument.download_error.is_(None),
                CompanyDocument.document_type.in_(types_to_process),
            )
            .limit(batch_size)
        )
        result = await self._session.execute(query)
        pending = list(result.scalars().all())

        downloaded = 0
        extracted = 0
        embedded = 0
        failed = 0

        for doc in pending:
            try:
                # 1. Download
                success = await self._download_document(doc)
                if success:
                    downloaded += 1
                else:
                    failed += 1
                    await self._session.commit()
                    continue

                # 2. Extract + chunk
                chunked = await self._extract_and_chunk(doc)
                if chunked:
                    extracted += 1

                await self._session.commit()

                # 3. Embed new chunks
                newly_embedded = await self._embed_document_chunks(doc)
                embedded += newly_embedded

                await self._session.commit()

            except Exception as exc:
                logger.warning(
                    "process_pending_documents.doc_error",
                    document_id=str(doc.id),
                    title=doc.title[:80],
                    error=str(exc),
                )
                await self._session.rollback()
                failed += 1

        logger.info(
            "process_pending_documents.done",
            downloaded=downloaded,
            extracted=extracted,
            embedded=embedded,
            failed=failed,
        )
        return {
            "downloaded": downloaded,
            "extracted": extracted,
            "embedded": embedded,
            "failed": failed,
        }

    async def embed_pending_chunks(self, limit: int = 500) -> int:
        """Embed chunks that are missing embeddings. For catch-up runs.

        Args:
            limit: Maximum number of chunks to embed in this run.

        Returns:
            Count of chunks successfully embedded.
        """
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.embedding.is_(None))
            .limit(limit)
        )
        result = await self._session.execute(query)
        chunks = list(result.scalars().all())

        total_embedded = 0

        for batch_start in range(0, len(chunks), self.EMBED_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + self.EMBED_BATCH_SIZE]
            texts = [c.chunk_text for c in batch]

            try:
                embeddings = await self._embeddings.embed_batch(texts)
                for chunk, emb in zip(batch, embeddings, strict=False):
                    if emb is not None:
                        chunk.embedding = emb
                        total_embedded += 1
                await self._session.commit()
            except Exception as exc:
                logger.warning(
                    "embed_pending_chunks.batch_error",
                    batch_start=batch_start,
                    error=str(exc),
                )
                await self._session.rollback()

        logger.info("embed_pending_chunks.done", embedded=total_embedded)
        return total_embedded

    async def search_chunks(
        self,
        query: str,
        vertical_slug: str | None = None,
        document_type: DocumentType | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search over document chunks.

        Embeds the query and performs cosine similarity in Python against
        candidate chunks (up to 1 000 fetched from the database).  Falls back
        to a LIKE keyword search when the embedding service is not configured.

        Args:
            query: Natural language query string.
            vertical_slug: Filter to a specific market vertical (e.g. "fintech").
            document_type: Restrict to a specific document type.
            top_k: Maximum number of results to return.

        Returns:
            List of dicts with keys:
              chunk_text, section_name, document_title, company_name, similarity
        """
        # Build base query: chunk → document → company (→ vertical if filtering)
        stmt = (
            select(DocumentChunk, CompanyDocument, ListedCompany)
            .join(CompanyDocument, DocumentChunk.document_id == CompanyDocument.id)
            .join(ListedCompany, CompanyDocument.listed_company_id == ListedCompany.id)
        )

        if vertical_slug is not None:
            stmt = stmt.join(
                MarketVertical,
                ListedCompany.vertical_id == MarketVertical.id,
            ).where(MarketVertical.slug == vertical_slug)

        if document_type is not None:
            stmt = stmt.where(CompanyDocument.document_type == document_type)

        if self._embeddings.is_configured:
            # Fetch candidates that already have embeddings (skip nulls)
            stmt = stmt.where(DocumentChunk.embedding.is_not(None)).limit(1000)
            result = await self._session.execute(stmt)
            rows = result.all()

            candidates: list[tuple[str, str]] = [
                (str(chunk.id), chunk.embedding)
                for chunk, _doc, _company in rows
                if chunk.embedding
            ]

            # Build lookup maps for metadata
            chunk_map: dict[str, DocumentChunk] = {
                str(chunk.id): chunk for chunk, _doc, _company in rows
            }
            doc_map: dict[str, CompanyDocument] = {
                str(chunk.id): doc for chunk, doc, _company in rows
            }
            company_map: dict[str, ListedCompany] = {
                str(chunk.id): company for chunk, _doc, company in rows
            }

            scored = await self._embeddings.find_similar(query, candidates, top_k=top_k)

            results: list[dict[str, Any]] = []
            for chunk_id_str, similarity in scored:
                chunk = chunk_map.get(chunk_id_str)
                doc = doc_map.get(chunk_id_str)
                company = company_map.get(chunk_id_str)
                if chunk is None or doc is None or company is None:
                    continue
                results.append(
                    {
                        "chunk_text": chunk.chunk_text,
                        "section_name": chunk.section_name,
                        "document_title": doc.title,
                        "company_name": company.name,
                        "similarity": similarity,
                    }
                )
            return results

        # Fallback: keyword LIKE search
        like_pattern = f"%{query}%"
        stmt = stmt.where(DocumentChunk.chunk_text.like(like_pattern)).limit(top_k)
        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            {
                "chunk_text": chunk.chunk_text,
                "section_name": chunk.section_name,
                "document_title": doc.title,
                "company_name": company.name,
                "similarity": 0.0,
            }
            for chunk, doc, company in rows
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _discover_from_edgar(self, years_back: int = 3) -> dict[str, int]:
        """Discover annual reports (20-F) for US-listed SG companies via SEC EDGAR.

        Fetches Form 20-F filings for Sea Limited, Grab Holdings, PropertyGuru,
        and MoneyHero from the SEC's public submissions API.  No API key required.

        The filings are HTML documents on EDGAR.  They are stored as
        ``CompanyDocument`` rows with ``is_downloaded=False`` so the existing
        download + extract pipeline can process them.

        Returns:
            Counts dict: {"discovered": N, "already_known": N, "errors": N}
        """
        discovered = 0
        already_known = 0
        errors = 0

        try:
            result = await self._edgar.get_all_sg_annual_reports(years_back=years_back)
            for filing in result.filings:
                # Look up the company in our DB by ticker + US exchange
                company = await self._session.scalar(
                    select(ListedCompany).where(
                        ListedCompany.ticker == filing.ticker,
                        ListedCompany.exchange == "US",
                    )
                )
                if company is None:
                    logger.warning(
                        "edgar_discovery.company_not_found",
                        ticker=filing.ticker,
                        detail="Add to OVERSEAS_LISTED_SG_COMPANIES and re-run roster sync",
                    )
                    errors += 1
                    continue

                # Deduplicate by document_url (== source_url in our schema)
                existing = await self._session.scalar(
                    select(CompanyDocument.id).where(
                        CompanyDocument.source_url == filing.document_url
                    )
                )
                if existing is not None:
                    already_known += 1
                    continue

                doc_type = DocumentType(filing.doc_type) if filing.doc_type in {
                    e.value for e in DocumentType
                } else DocumentType.ANNUAL_REPORT

                title = (
                    f"{filing.company_name} {filing.form} "
                    f"{filing.fiscal_year or filing.filing_date.year}"
                )
                doc = CompanyDocument(
                    listed_company_id=company.id,
                    document_type=doc_type,
                    title=title[:255],
                    source_url=filing.document_url,
                    published_date=filing.filing_date.strftime("%Y-%m-%d"),
                    fiscal_year=filing.fiscal_year,
                    sgx_announcement_id=filing.accession_number,
                    sgx_category=f"sec_edgar_{filing.form}",
                    is_downloaded=False,
                )
                self._session.add(doc)
                discovered += 1

            await self._session.commit()

        except Exception as exc:
            logger.warning("edgar_discovery.error", error=str(exc))
            await self._session.rollback()
            errors += 1

        logger.info(
            "edgar_discovery.done",
            discovered=discovered,
            already_known=already_known,
            errors=errors,
        )
        return {"discovered": discovered, "already_known": already_known, "errors": errors}

    async def _active_sg_tickers(self) -> list[str]:
        """Return up to 200 active SGX-listed tickers."""
        result = await self._session.execute(
            select(ListedCompany.ticker)
            .where(
                ListedCompany.exchange == "SG",
                ListedCompany.is_active.is_(True),
            )
            .limit(200)
        )
        return list(result.scalars().all())

    async def _company_by_ticker(self, ticker: str) -> ListedCompany | None:
        """Look up a ListedCompany by ticker (SG exchange)."""
        return await self._session.scalar(
            select(ListedCompany).where(
                ListedCompany.ticker == ticker,
                ListedCompany.exchange == "SG",
            )
        )

    async def _discover_from_eodhd_news(
        self,
        tickers: list[str],
        days_back: int,
    ) -> dict[str, int]:
        """Fallback discovery using EODHD financial news API.

        Called when the SGX RegNet /announcements endpoint is broken or returns
        no results.  EODHD's news endpoint provides article-level coverage of
        SGX-listed companies including earnings, annual report filings, and
        material announcements.

        The EODHD symbol format for SGX-listed stocks is "<TICKER>.SG"
        (e.g. "D05.SG" for DBS Group).

        Args:
            tickers: List of bare SGX ticker codes (e.g. ["D05", "U11"]).
            days_back: News look-back window in days.

        Returns:
            Counts dict: {"discovered": N, "already_known": N, "errors": N}
        """
        if not self._eodhd.is_configured:
            logger.warning(
                "discover_announcements.eodhd_not_configured",
                detail="EODHD_API_KEY not set; cannot use EODHD news fallback.",
            )
            return {"discovered": 0, "already_known": 0, "errors": 0}

        cutoff = datetime.now(tz=UTC) - timedelta(days=days_back)

        discovered = 0
        already_known = 0
        errors = 0

        for ticker in tickers:
            try:
                company = await self._company_by_ticker(ticker)
                if company is None:
                    errors += 1
                    continue

                # EODHD uses "<TICKER>.SG" for SGX-listed equities
                eodhd_symbol = f"{ticker}.SG"
                news_items = await self._eodhd.get_financial_news(
                    symbol=eodhd_symbol,
                    limit=20,
                )
                # Pace at 4 RPS — within EODHD standard tier limits.
                await asyncio.sleep(0.25)

                for item in news_items:
                    # Skip articles older than the look-back window
                    item_date = item.date
                    if item_date.tzinfo is None:
                        item_date = item_date.replace(tzinfo=UTC)
                    if item_date < cutoff:
                        continue

                    # Skip items without a link (nothing to store)
                    if not item.link:
                        continue

                    # Map tags/title to a DocumentType
                    doc_type = _map_eodhd_news_to_doc_type(item.title, item.tags)
                    if doc_type not in _SAVE_TYPES:
                        continue

                    # Deduplicate by source URL
                    existing = await self._session.scalar(
                        select(CompanyDocument.id).where(
                            CompanyDocument.source_url == item.link
                        )
                    )
                    if existing is not None:
                        already_known += 1
                        continue

                    published_str = item.date.strftime("%Y-%m-%d")
                    doc = CompanyDocument(
                        listed_company_id=company.id,
                        document_type=doc_type,
                        title=item.title[:255],
                        source_url=item.link,
                        published_date=published_str,
                        sgx_category="eodhd_news",
                        is_downloaded=False,
                    )
                    self._session.add(doc)
                    discovered += 1

                await self._session.commit()

            except Exception as exc:
                logger.warning(
                    "discover_announcements.eodhd_ticker_error",
                    ticker=ticker,
                    error=str(exc),
                )
                await self._session.rollback()
                errors += 1

        logger.info(
            "discover_announcements.eodhd_done",
            discovered=discovered,
            already_known=already_known,
            errors=errors,
        )
        return {"discovered": discovered, "already_known": already_known, "errors": errors}

    async def _download_document(self, doc: CompanyDocument) -> bool:
        """Download document PDF and update the CompanyDocument row in-place.

        Returns True on success, False on failure.
        Mutates doc.file_path, doc.file_size_bytes, doc.is_downloaded, doc.fetched_at,
        and doc.download_error.
        """
        url_lower = (doc.source_url or "").lower()
        ext = ".htm" if url_lower.endswith((".htm", ".html")) else ".pdf"
        filename = _safe_filename(doc.title) + ext
        result = await self._downloader.download(
            url=doc.source_url,
            company_id=str(doc.listed_company_id),
            doc_type=doc.document_type.value,
            filename=filename,
        )

        if result.success:
            doc.file_path = result.file_path
            doc.file_size_bytes = result.file_size_bytes
            doc.is_downloaded = True
            doc.fetched_at = datetime.now(tz=UTC)
            logger.info(
                "document.downloaded",
                document_id=str(doc.id),
                file_size_bytes=result.file_size_bytes,
            )
            return True

        doc.download_error = result.error or "Unknown download error"
        logger.warning(
            "document.download_failed",
            document_id=str(doc.id),
            error=doc.download_error,
        )
        return False

    async def _extract_and_chunk(self, doc: CompanyDocument) -> bool:
        """Run the extractor (sync, wrapped in executor) and create DocumentChunk rows.

        Returns True when chunking completed (even if no sections found).
        Mutates doc.is_chunked, doc.page_count.
        """
        if not doc.is_downloaded or doc.file_path is None or doc.is_chunked:
            return False

        loop = asyncio.get_event_loop()
        extraction = await loop.run_in_executor(
            None, self._extractor.extract, doc.file_path
        )

        doc.page_count = extraction.total_pages

        if extraction.is_scanned:
            logger.warning(
                "document.scanned_pdf_skipped",
                document_id=str(doc.id),
                title=doc.title[:80],
            )
            doc.is_chunked = True
            return True

        if not extraction.success:
            logger.warning(
                "document.extraction_failed",
                document_id=str(doc.id),
                error=extraction.error,
            )
            # Do not mark is_chunked — allow retry after fixing the PDF
            return False

        chunk_index = 0

        if extraction.sections:
            for section in extraction.sections:
                for chunk_text in self._extractor.chunk_section(section):
                    if not chunk_text.strip():
                        continue
                    chunk = DocumentChunk(
                        document_id=doc.id,
                        chunk_index=chunk_index,
                        section_name=section.section_name,
                        chunk_text=chunk_text,
                        token_count=len(chunk_text) // 4,
                    )
                    self._session.add(chunk)
                    chunk_index += 1
        else:
            # No sections detected — add a single overview chunk from the beginning
            overview_text = extraction.full_text[:3000].strip()
            if overview_text:
                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=0,
                    section_name="Overview",
                    chunk_text=overview_text,
                    token_count=len(overview_text) // 4,
                )
                self._session.add(chunk)

        doc.is_chunked = True
        logger.info(
            "document.chunked",
            document_id=str(doc.id),
            chunk_count=chunk_index,
            sections=len(extraction.sections),
        )
        return True

    async def _embed_document_chunks(self, doc: CompanyDocument) -> int:
        """Embed all unembedded chunks for a single document.

        Returns the count of chunks successfully embedded.
        """
        result = await self._session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.embedding.is_(None),
            )
        )
        chunks = list(result.scalars().all())

        if not chunks:
            return 0

        total_embedded = 0

        for batch_start in range(0, len(chunks), self.EMBED_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + self.EMBED_BATCH_SIZE]
            texts = [c.chunk_text for c in batch]

            try:
                embeddings = await self._embeddings.embed_batch(texts)
                for chunk, emb in zip(batch, embeddings, strict=False):
                    if emb is not None:
                        chunk.embedding = emb
                        total_embedded += 1
            except Exception as exc:
                logger.warning(
                    "embed_document_chunks.batch_error",
                    document_id=str(doc.id),
                    batch_start=batch_start,
                    error=str(exc),
                )

        return total_embedded


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _safe_filename(title: str, max_len: int = 80) -> str:
    """Convert a document title into a safe filesystem filename (no extension)."""
    import re

    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "document"
