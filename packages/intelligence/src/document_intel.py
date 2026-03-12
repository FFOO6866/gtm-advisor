"""Document Intelligence Extractor.

Reads high-signal sections from chunked annual reports, sustainability reports,
and investor communications, then uses OpenAI to extract structured business
signals (expansion plans, M&A, capex guidance, risks) and persists them as
SignalEvent rows.

Design constraints:
  - No DB migrations: works with the existing SignalEvent schema.
  - company_id on SignalEvent is non-nullable and FKs to companies.id (user
    companies), not listed_companies.id. Signals are associated to matching
    user Company rows (by name/industry) when available; otherwise the signal
    text is logged but not persisted.
  - Dedup: uses source_url = "document:{document_id}" as natural idempotency key.
  - Graceful fallback: if OPENAI_API_KEY is absent, returns 0 silently.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import (
    Company,
    CompanyDocument,
    DocumentChunk,
    ListedCompany,
    SignalEvent,
    SignalType,
    SignalUrgency,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal type mapping
# ---------------------------------------------------------------------------

# Map OpenAI-returned string values → SignalType enum.
# Keys are the values the prompt instructs the LLM to return.
_SIGNAL_TYPE_MAP: dict[str, SignalType] = {
    "expansion": SignalType.EXPANSION,
    "product_launch": SignalType.PRODUCT_LAUNCH,
    "acquisition": SignalType.ACQUISITION,
    "funding": SignalType.FUNDING,
    "leadership": SignalType.HIRING,          # closest available: HIRING covers exec changes
    "regulation": SignalType.REGULATION,
    "market_trend": SignalType.MARKET_TREND,
    # Fallback aliases (LLM may improvise)
    "partnership": SignalType.MARKET_TREND,
    "capex": SignalType.EXPANSION,
    "guidance": SignalType.MARKET_TREND,
    "risk": SignalType.MARKET_TREND,
    "hiring": SignalType.HIRING,
    "general_news": SignalType.GENERAL_NEWS,
}

_URGENCY_MAP: dict[str, SignalUrgency] = {
    "high": SignalUrgency.THIS_WEEK,
    "medium": SignalUrgency.THIS_MONTH,
    "low": SignalUrgency.MONITOR,
}

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
You are a Singapore market intelligence analyst. Extract business signals \
from this {document_type} excerpt for {company_name} ({company_ticker}), \
fiscal year {fiscal_year}.

Extract ALL of the following signal types if present:
- expansion: Geographic expansion, new market entry, new offices, regional growth
- product_launch: New products, services, platforms, digital initiatives
- acquisition: M&A activity, acquisitions, JVs, strategic partnerships
- funding: Capital raises, new financing, debt issuance
- leadership: Executive appointments, board changes
- regulation: Regulatory approvals, licensing, compliance milestones
- market_trend: Industry outlook statements, market share targets, guidance

For each signal found, return:
{{
  "signals": [
    {{
      "signal_type": "expansion|product_launch|acquisition|funding|\
leadership|regulation|market_trend",
      "urgency": "high|medium|low",
      "headline": "Short headline under 80 chars",
      "signal_text": "1-2 sentence description with specific details",
      "mentioned_markets": ["Singapore", "Indonesia"],
      "mentioned_companies": ["DBS", "Grab"],
      "dollar_amount": "SGD 500M or null",
      "timeline": "FY2025 or null",
      "confidence": 0.0
    }}
  ]
}}

Return empty signals array if no clear signals found. \
Only include high-confidence (>0.6) signals.

Document excerpt:
{text}
"""

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SignalExtraction:
    """A single structured business signal extracted from document text."""

    signal_type: str
    urgency: str
    signal_text: str
    headline: str
    mentioned_companies: list[str] = field(default_factory=list)
    mentioned_markets: list[str] = field(default_factory=list)
    dollar_amount: str | None = None
    timeline: str | None = None
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------


class DocumentIntelligenceExtractor:
    """Extracts structured business signals from document chunks using OpenAI."""

    # Only process chunks whose section_name contains one of these keywords
    HIGH_SIGNAL_SECTIONS: frozenset[str] = frozenset({
        "chairman",
        "ceo",
        "chief executive",
        "strategy",
        "strategic",
        "business overview",
        "financial highlights",
        "outlook",
        "guidance",
        "operations review",
        "sustainability",
        "risk",
    })

    # Max chunks to process per document (cost control)
    MAX_CHUNKS_PER_DOC: int = 30

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._openai_configured = bool(os.getenv("OPENAI_API_KEY"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_document(self, document_id: str) -> int:
        """Extract signals from one document. Returns count of signals created."""
        if not self._openai_configured:
            logger.warning(
                "DocumentIntelligenceExtractor: OPENAI_API_KEY not set — skipping document %s",
                document_id,
            )
            return 0

        try:
            import uuid as _uuid
            doc_uuid = _uuid.UUID(document_id)
        except ValueError:
            logger.warning(
                "DocumentIntelligenceExtractor: invalid document_id %r", document_id
            )
            return 0

        # Load document + listed company + vertical
        result = await self._session.execute(
            select(CompanyDocument)
            .options(
                selectinload(CompanyDocument.listed_company).selectinload(
                    ListedCompany.vertical
                )
            )
            .where(CompanyDocument.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            logger.warning(
                "DocumentIntelligenceExtractor: document %s not found", document_id
            )
            return 0

        if not doc.is_chunked:
            logger.info(
                "DocumentIntelligenceExtractor: document %s not yet chunked — skipping",
                document_id,
            )
            return 0

        listed = doc.listed_company
        vertical_slug = listed.vertical.slug if (listed and listed.vertical) else None

        # Find user Company rows to associate signals with
        user_company_ids = await self._find_user_companies(
            company_name=listed.name if listed else "",
            industry=listed.gics_sector or listed.gics_industry if listed else None,
        )
        if not user_company_ids:
            logger.warning(
                "DocumentIntelligenceExtractor: companies table is empty —"
                " cannot persist signals for listed company '%s'",
                listed.name if listed else document_id,
            )
            return 0

        # Get high-signal chunks
        chunks = await self._get_high_signal_chunks(doc_uuid)
        if not chunks:
            logger.info(
                "DocumentIntelligenceExtractor: no high-signal chunks in document %s",
                document_id,
            )
            return 0

        # Extract signals via OpenAI
        extractions = await self._extract_signals(
            company_ticker=listed.ticker if listed else "UNKNOWN",
            company_name=listed.name if listed else "Unknown Company",
            document_type=doc.document_type.value.replace("_", " ").title(),
            fiscal_year=doc.fiscal_year or "Unknown",
            text_chunks=[c.chunk_text for c in chunks],
        )

        if not extractions:
            return 0

        # Persist signals
        created = await self._persist_signals(
            extractions=extractions,
            document_id=str(doc_uuid),
            user_company_ids=user_company_ids,
            vertical_slug=vertical_slug,
        )
        return created

    async def process_pending_documents(self, batch_size: int = 10) -> int:
        """Process documents that are chunked but not yet intelligence-extracted.

        Uses source_url = 'document:{id}' on SignalEvent as the dedup/processed marker.
        Returns total signals created across all documents in this batch.
        """
        if not self._openai_configured:
            logger.warning(
                "DocumentIntelligenceExtractor: OPENAI_API_KEY not set — skipping batch"
            )
            return 0

        # Find chunked documents
        doc_result = await self._session.execute(
            select(CompanyDocument)
            .options(
                selectinload(CompanyDocument.listed_company).selectinload(
                    ListedCompany.vertical
                )
            )
            .where(CompanyDocument.is_chunked == True)  # noqa: E712
            .order_by(CompanyDocument.created_at.desc())
            .limit(batch_size * 5)  # Fetch more to account for already-processed ones
        )
        all_docs = list(doc_result.scalars().all())

        if not all_docs:
            logger.info("DocumentIntelligenceExtractor: no chunked documents found")
            return 0

        # Filter to those not yet processed (no SignalEvent with source_url = "document:{id}")
        pending_docs = []
        for doc in all_docs:
            if len(pending_docs) >= batch_size:
                break
            already_done = await self._is_document_processed(str(doc.id))
            if not already_done:
                pending_docs.append(doc)

        if not pending_docs:
            logger.info(
                "DocumentIntelligenceExtractor: all %d chunked documents already processed",
                len(all_docs),
            )
            return 0

        logger.info(
            "DocumentIntelligenceExtractor: processing %d pending documents",
            len(pending_docs),
        )

        total_signals = 0
        for doc in pending_docs:
            try:
                count = await self._process_doc_object(doc)
                total_signals += count
                logger.info(
                    "DocumentIntelligenceExtractor: document %s → %d signals",
                    doc.id,
                    count,
                )
            except Exception:
                logger.exception(
                    "DocumentIntelligenceExtractor: failed to process document %s", doc.id
                )

        return total_signals

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _process_doc_object(self, doc: CompanyDocument) -> int:
        """Process a CompanyDocument ORM object (already loaded with relationships)."""
        listed = doc.listed_company
        vertical_slug = listed.vertical.slug if (listed and listed.vertical) else None

        user_company_ids = await self._find_user_companies(
            company_name=listed.name if listed else "",
            industry=listed.gics_sector or listed.gics_industry if listed else None,
        )
        if not user_company_ids:
            logger.warning(
                "DocumentIntelligenceExtractor: companies table is empty —"
                " cannot persist signals for '%s'",
                listed.name if listed else str(doc.id),
            )
            return 0

        chunks = await self._get_high_signal_chunks(doc.id)
        if not chunks:
            return 0

        extractions = await self._extract_signals(
            company_ticker=listed.ticker if listed else "UNKNOWN",
            company_name=listed.name if listed else "Unknown Company",
            document_type=doc.document_type.value.replace("_", " ").title(),
            fiscal_year=doc.fiscal_year or "Unknown",
            text_chunks=[c.chunk_text for c in chunks],
        )

        if not extractions:
            return 0

        return await self._persist_signals(
            extractions=extractions,
            document_id=str(doc.id),
            user_company_ids=user_company_ids,
            vertical_slug=vertical_slug,
        )

    async def _get_high_signal_chunks(self, document_id) -> list[DocumentChunk]:
        """Load up to MAX_CHUNKS_PER_DOC high-signal chunks for a document."""
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(self.MAX_CHUNKS_PER_DOC * 3)  # Over-fetch, then filter
        )
        all_chunks = list(result.scalars().all())

        # Prioritise high-signal sections, fall back to all sections if none match
        high_signal = [
            c for c in all_chunks if self._is_high_signal_section(c.section_name)
        ]
        selected = high_signal if high_signal else all_chunks
        return selected[: self.MAX_CHUNKS_PER_DOC]

    def _is_high_signal_section(self, section_name: str | None) -> bool:
        """Return True if this section likely contains business signals."""
        if not section_name:
            return False
        lower = section_name.lower()
        return any(kw in lower for kw in self.HIGH_SIGNAL_SECTIONS)

    async def _find_user_companies(
        self, company_name: str, industry: str | None
    ) -> list:
        """Find user Company rows to associate market signals with.

        Strategy (in order):
          1. Exact name match (case-insensitive)
          2. Industry/sector match (first 5 companies in same industry)
          3. Any company in the DB (fallback so signals are never silently dropped)

        The fallback (step 3) stores market-level signals against existing user
        companies when no thematic match exists. This is intentional: on a fresh
        install all signals would otherwise be discarded, giving 0% signal coverage.
        Signals remain distinguishable by their source_url ("document:{id}") and
        signal_type so callers can filter by vertical independently.

        Returns list of Company.id values (UUIDs). Returns [] only when the
        companies table is completely empty.
        """
        if company_name:
            exact_result = await self._session.execute(
                select(Company.id).where(
                    func.lower(Company.name) == company_name.lower()
                ).limit(5)
            )
            exact_ids = [row[0] for row in exact_result.all()]
            if exact_ids:
                return exact_ids

        if industry:
            industry_result = await self._session.execute(
                select(Company.id).where(
                    or_(
                        func.lower(Company.industry).contains(industry.lower()),
                        func.lower(Company.name).contains(
                            company_name.split()[0].lower() if company_name else ""
                        ),
                    )
                ).limit(5)
            )
            industry_ids = [row[0] for row in industry_result.all()]
            if industry_ids:
                return industry_ids

        # Fallback: no name/industry match — use first company so signals persist
        # as market-level intelligence (visible to all verticals).
        fallback_result = await self._session.execute(
            select(Company.id).order_by(Company.created_at).limit(1)
        )
        fallback_id = fallback_result.scalar_one_or_none()
        if fallback_id is not None:
            logger.debug(
                "DocumentIntelligenceExtractor: no thematic Company match for '%s';"
                " storing signal against fallback company %s",
                company_name,
                fallback_id,
            )
            return [fallback_id]

        return []

    async def _is_document_processed(self, document_id: str) -> bool:
        """Check if signals already exist for this document (dedup via source_url)."""
        source_key = f"document:{document_id}"
        result = await self._session.execute(
            select(SignalEvent.id)
            .where(SignalEvent.source_url == source_key)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _extract_signals(
        self,
        company_ticker: str,
        company_name: str,
        document_type: str,
        fiscal_year: str,
        text_chunks: list[str],
    ) -> list[SignalExtraction]:
        """Call OpenAI to extract signals from combined chunk text."""
        if not text_chunks:
            return []

        # Combine chunk texts (respect ~12K char budget)
        combined = "\n\n---\n\n".join(text_chunks)
        if len(combined) > 12_000:
            combined = combined[:12_000] + "\n\n[truncated]"

        prompt = _EXTRACTION_PROMPT.format(
            document_type=document_type,
            company_name=company_name,
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
            text=combined,
        )

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000,
            )
        except Exception:
            logger.exception(
                "DocumentIntelligenceExtractor: OpenAI call failed for %s %s",
                company_ticker,
                document_type,
            )
            return []

        raw_content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning(
                "DocumentIntelligenceExtractor: invalid JSON from OpenAI for %s",
                company_ticker,
            )
            return []

        raw_signals: list[dict] = data.get("signals", [])
        extractions: list[SignalExtraction] = []

        for sig in raw_signals:
            if not isinstance(sig, dict):
                continue
            confidence = float(sig.get("confidence", 0.0))
            if confidence <= 0.6:
                continue  # Filter low-confidence signals per prompt instructions

            signal_type_str = str(sig.get("signal_type", "general_news")).lower()
            urgency_str = str(sig.get("urgency", "low")).lower()
            headline = str(sig.get("headline", ""))[:79]
            signal_text = str(sig.get("signal_text", ""))

            if not headline or not signal_text:
                continue

            extractions.append(
                SignalExtraction(
                    signal_type=signal_type_str,
                    urgency=urgency_str,
                    signal_text=signal_text,
                    headline=headline,
                    mentioned_companies=list(sig.get("mentioned_companies") or []),
                    mentioned_markets=list(sig.get("mentioned_markets") or []),
                    dollar_amount=sig.get("dollar_amount") or None,
                    timeline=sig.get("timeline") or None,
                    confidence=confidence,
                )
            )

        logger.info(
            "DocumentIntelligenceExtractor: extracted %d signals from %s %s",
            len(extractions),
            company_ticker,
            document_type,
        )
        return extractions

    async def _persist_signals(
        self,
        extractions: list[SignalExtraction],
        document_id: str,
        user_company_ids: list,
        vertical_slug: str | None,
    ) -> int:
        """Persist SignalExtraction objects as SignalEvent rows.

        Each signal is linked to each matching user Company.
        Dedup: skip if SignalEvent already exists with same (company_id, signal_type, source_url).
        Returns count of newly created rows.
        """
        source_key = f"document:{document_id}"
        created = 0

        for extraction in extractions:
            signal_type = _SIGNAL_TYPE_MAP.get(
                extraction.signal_type, SignalType.GENERAL_NEWS
            )
            urgency = _URGENCY_MAP.get(extraction.urgency, SignalUrgency.MONITOR)

            metadata: dict = {}
            if extraction.dollar_amount:
                metadata["dollar_amount"] = extraction.dollar_amount
            if extraction.timeline:
                metadata["timeline"] = extraction.timeline
            if extraction.mentioned_companies:
                metadata["mentioned_companies"] = extraction.mentioned_companies

            for company_id in user_company_ids:
                # Dedup check: same document + company + signal_type + headline prefix
                dedup_result = await self._session.execute(
                    select(SignalEvent.id)
                    .where(
                        SignalEvent.company_id == company_id,
                        SignalEvent.signal_type == signal_type,
                        SignalEvent.source_url == source_key,
                        SignalEvent.headline == extraction.headline,
                    )
                    .limit(1)
                )
                if dedup_result.scalar_one_or_none() is not None:
                    continue

                source_label = (
                    f"DocumentIntel:{vertical_slug}" if vertical_slug else "DocumentIntel"
                )
                event = SignalEvent(
                    company_id=company_id,
                    signal_type=signal_type,
                    urgency=urgency,
                    headline=extraction.headline,
                    summary=extraction.signal_text,
                    source=source_label[:100],
                    source_url=source_key,
                    relevance_score=extraction.confidence,
                    competitors_mentioned=extraction.mentioned_companies,
                    recommended_action=None,
                )
                self._session.add(event)
                created += 1

        if created:
            await self._session.flush()

        logger.info(
            "DocumentIntelligenceExtractor: persisted %d new SignalEvent rows (document %s)",
            created,
            document_id,
        )
        return created
