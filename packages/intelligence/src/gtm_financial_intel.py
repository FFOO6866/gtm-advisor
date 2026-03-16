"""GTM Financial Intelligence Extractor.

Extracts structured GTM data from annual report document chunks using OpenAI.
Follows the same pattern as DocumentIntelligenceExtractor but focuses on
go-to-market intelligence: marketing spend, GTM channels, strategic
initiatives, customer segments, and competitive positioning.

Persistence: stores extracted insights as SignalEvent rows with
source="GTMIntel:{vertical_slug}" — no new migration needed, signals are
already accessible to agents via the MCP server.  Structured metadata
(channels, initiatives, segments, geo focus) is serialised as JSON into the
``recommended_action`` text column so it survives the round-trip.

Design constraints:
  - No new DB migrations: uses existing SignalEvent schema.
  - Dedup: source_url = "gtm_intel:{document_id}" as idempotency key.
  - Graceful fallback: if OPENAI_API_KEY is absent, returns 0 silently.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from sqlalchemy import func, select
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
# Sections relevant to GTM intelligence extraction
# ---------------------------------------------------------------------------

GTM_SECTIONS: frozenset[str] = frozenset({
    "chairman",
    "ceo",
    "chief executive",
    "strategy",
    "strategic",
    "business overview",
    "operations review",
    "sales and marketing",
    "selling and distribution",
    "research and development",
    "r&d",
    "segment",
    "management discussion",
    "md&a",
    "operating expenses",
})

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_GTM_EXTRACTION_PROMPT = """\
You are a GTM (go-to-market) intelligence analyst. Extract structured GTM \
insights from this {document_type} excerpt for {company_name} ({company_ticker}), \
fiscal year {fiscal_year}.

Extract ALL of the following if mentioned:

1. **Quantitative metrics** (only if explicitly stated with numbers):
   - marketing_spend_pct: marketing/sales spend as percentage of revenue
   - rnd_spend_pct: R&D spend as percentage of revenue
   - sales_headcount_mentioned: number of sales/marketing employees

2. **GTM channels** used (select all that apply):
   direct_sales, digital, partnerships, channel, events, content_marketing,
   social_media, pr_media, referral, marketplace

3. **Strategic initiatives** (select all that apply):
   geographic_expansion, product_led_growth, ma_driven, partnership_led,
   digital_transformation, cost_optimization, vertical_expansion,
   platform_strategy, freemium_to_enterprise

4. **Customer segments** targeted:
   enterprise, sme, mid_market, consumer, government, startups

5. **Geographic focus** regions:
   singapore, southeast_asia, apac, global, north_america, europe, middle_east

6. **Competitive positioning**: 1-2 sentence summary of how the company
   positions itself vs competitors.

Return JSON:
{{
  "marketing_spend_pct": null,
  "rnd_spend_pct": null,
  "sales_headcount_mentioned": null,
  "gtm_channels": [],
  "strategic_initiatives": [],
  "customer_segments": [],
  "geographic_focus": [],
  "competitive_positioning": null,
  "confidence": 0.0
}}

Only include data explicitly stated in the text. Set confidence 0.0-1.0 \
based on how much GTM-relevant content was found. Return confidence < 0.3 \
if the excerpt has minimal GTM-relevant content.

Document excerpt:
{text}
"""

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GTMInsight:
    """Structured GTM intelligence extracted from a document."""

    company_ticker: str
    fiscal_year: str
    marketing_spend_pct: float | None = None
    rnd_spend_pct: float | None = None
    sales_headcount_mentioned: int | None = None
    gtm_channels: list[str] = field(default_factory=list)
    strategic_initiatives: list[str] = field(default_factory=list)
    customer_segments: list[str] = field(default_factory=list)
    geographic_focus: list[str] = field(default_factory=list)
    competitive_positioning: str | None = None
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------


class GTMFinancialExtractor:
    """Extracts GTM-specific intelligence from document chunks."""

    MAX_CHUNKS_PER_DOC: int = 20

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._openai_configured = bool(os.getenv("OPENAI_API_KEY"))

    async def process_document(self, document_id: str) -> int:
        """Extract GTM insights from one document. Returns count of signals created."""
        if not self._openai_configured:
            logger.warning("GTMFinancialExtractor: OPENAI_API_KEY not set — skipping %s", document_id)
            return 0

        try:
            import uuid as _uuid
            doc_uuid = _uuid.UUID(document_id)
        except ValueError:
            logger.warning("GTMFinancialExtractor: invalid document_id %r", document_id)
            return 0

        # Check dedup
        if await self._is_document_processed(document_id):
            return 0

        # Load document with relationships
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
        if doc is None or not doc.is_chunked:
            return 0

        listed = doc.listed_company
        vertical_slug = listed.vertical.slug if (listed and listed.vertical) else None

        # Find user companies to link signals
        user_company_ids = await self._find_user_companies(
            company_name=listed.name if listed else "",
        )
        if not user_company_ids:
            logger.warning("GTMFinancialExtractor: no user companies for '%s'", listed.name if listed else document_id)
            return 0

        # Get GTM-relevant chunks
        chunks = await self._get_gtm_chunks(doc_uuid)
        if not chunks:
            return 0

        # Extract via OpenAI
        insight = await self._extract_gtm_insight(
            company_ticker=listed.ticker if listed else "UNKNOWN",
            company_name=listed.name if listed else "Unknown Company",
            document_type=doc.document_type.value.replace("_", " ").title(),
            fiscal_year=doc.fiscal_year or "Unknown",
            text_chunks=[c.chunk_text for c in chunks],
        )

        if insight is None or insight.confidence < 0.3:
            return 0

        # Persist as SignalEvent
        return await self._persist_insight(
            insight=insight,
            document_id=document_id,
            user_company_ids=user_company_ids,
            vertical_slug=vertical_slug,
        )

    async def process_pending_documents(self, batch_size: int = 10) -> int:
        """Process documents that haven't been GTM-extracted yet."""
        if not self._openai_configured:
            logger.warning("GTMFinancialExtractor: OPENAI_API_KEY not set — skipping batch")
            return 0

        doc_result = await self._session.execute(
            select(CompanyDocument)
            .options(
                selectinload(CompanyDocument.listed_company).selectinload(
                    ListedCompany.vertical
                )
            )
            .where(CompanyDocument.is_chunked == True)  # noqa: E712
            .order_by(CompanyDocument.created_at.desc())
            .limit(batch_size * 5)
        )
        all_docs = list(doc_result.scalars().all())

        # Batch dedup check — single query instead of N individual lookups
        candidate_keys = [f"gtm_intel:{doc.id}" for doc in all_docs]
        already_done: set[str] = set()
        if candidate_keys:
            done_result = await self._session.execute(
                select(SignalEvent.source_url).where(
                    SignalEvent.source_url.in_(candidate_keys)
                )
            )
            already_done = {row[0] for row in done_result.all()}

        pending = []
        for doc in all_docs:
            if len(pending) >= batch_size:
                break
            if f"gtm_intel:{doc.id}" not in already_done:
                pending.append(doc)

        if not pending:
            logger.info("GTMFinancialExtractor: no pending documents")
            return 0

        total = 0
        for doc in pending:
            try:
                async with self._session.begin_nested():
                    count = await self._process_doc_object(doc)
                    total += count
            except Exception:
                # Savepoint rolled back — other documents unaffected
                logger.exception("GTMFinancialExtractor: failed for document %s", doc.id)

        return total

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _process_doc_object(self, doc: CompanyDocument) -> int:
        """Process an already-loaded CompanyDocument ORM object (avoids re-query)."""
        listed = doc.listed_company
        if listed is None:
            logger.debug("GTMFinancialExtractor: document %s has no listed_company — skipping", doc.id)
            return 0
        vertical_slug = listed.vertical.slug if listed.vertical else None

        user_company_ids = await self._find_user_companies(
            company_name=listed.name,
        )
        if not user_company_ids:
            return 0

        chunks = await self._get_gtm_chunks(doc.id)
        if not chunks:
            return 0

        insight = await self._extract_gtm_insight(
            company_ticker=listed.ticker,
            company_name=listed.name,
            document_type=doc.document_type.value.replace("_", " ").title(),
            fiscal_year=doc.fiscal_year or "Unknown",
            text_chunks=[c.chunk_text for c in chunks],
        )

        if insight is None or insight.confidence < 0.3:
            return 0

        return await self._persist_insight(
            insight=insight,
            document_id=str(doc.id),
            user_company_ids=user_company_ids,
            vertical_slug=vertical_slug,
        )

    async def _get_gtm_chunks(self, document_id) -> list[DocumentChunk]:
        """Load GTM-relevant chunks for a document."""
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(self.MAX_CHUNKS_PER_DOC * 3)
        )
        all_chunks = list(result.scalars().all())

        gtm = [c for c in all_chunks if self._is_gtm_section(c.section_name)]
        selected = gtm if gtm else all_chunks
        return selected[: self.MAX_CHUNKS_PER_DOC]

    @staticmethod
    def _is_gtm_section(section_name: str | None) -> bool:
        if not section_name:
            return False
        lower = section_name.lower()
        return any(kw in lower for kw in GTM_SECTIONS)

    async def _find_user_companies(self, company_name: str) -> list:
        """Find user Company rows by exact name match.

        Returns empty list if no match — never falls back to an unrelated
        company, which would cause cross-company data leakage.
        """
        if not company_name:
            return []
        result = await self._session.execute(
            select(Company.id).where(
                func.lower(Company.name) == company_name.lower()
            ).limit(5)
        )
        return [row[0] for row in result.all()]

    async def _is_document_processed(self, document_id: str) -> bool:
        source_key = f"gtm_intel:{document_id}"
        result = await self._session.execute(
            select(SignalEvent.id)
            .where(SignalEvent.source_url == source_key)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _extract_gtm_insight(
        self,
        company_ticker: str,
        company_name: str,
        document_type: str,
        fiscal_year: str,
        text_chunks: list[str],
    ) -> GTMInsight | None:
        """Call OpenAI to extract GTM insights from combined chunk text."""
        if not text_chunks:
            return None

        combined = "\n\n---\n\n".join(text_chunks)
        if len(combined) > 12_000:
            combined = combined[:12_000] + "\n\n[truncated]"

        prompt = _GTM_EXTRACTION_PROMPT.format(
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
                max_tokens=1500,
            )
        except Exception:
            logger.exception("GTMFinancialExtractor: OpenAI call failed for %s", company_ticker)
            return None

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("GTMFinancialExtractor: invalid JSON from OpenAI for %s", company_ticker)
            return None

        return GTMInsight(
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
            marketing_spend_pct=data.get("marketing_spend_pct"),
            rnd_spend_pct=data.get("rnd_spend_pct"),
            sales_headcount_mentioned=data.get("sales_headcount_mentioned"),
            gtm_channels=data.get("gtm_channels") or [],
            strategic_initiatives=data.get("strategic_initiatives") or [],
            customer_segments=data.get("customer_segments") or [],
            geographic_focus=data.get("geographic_focus") or [],
            competitive_positioning=data.get("competitive_positioning"),
            confidence=float(data.get("confidence", 0.0)),
        )

    async def _persist_insight(
        self,
        insight: GTMInsight,
        document_id: str,
        user_company_ids: list,
        vertical_slug: str | None,
    ) -> int:
        """Persist GTMInsight as a SignalEvent row."""
        source_key = f"gtm_intel:{document_id}"
        created = 0

        # Build a summary from the insight
        summary_parts = []
        if insight.gtm_channels:
            summary_parts.append(f"GTM channels: {', '.join(insight.gtm_channels)}")
        if insight.strategic_initiatives:
            summary_parts.append(f"Initiatives: {', '.join(insight.strategic_initiatives)}")
        if insight.customer_segments:
            summary_parts.append(f"Segments: {', '.join(insight.customer_segments)}")
        if insight.geographic_focus:
            summary_parts.append(f"Geo focus: {', '.join(insight.geographic_focus)}")
        if insight.competitive_positioning:
            summary_parts.append(f"Positioning: {insight.competitive_positioning}")

        summary = ". ".join(summary_parts) if summary_parts else "GTM intelligence extracted"

        headline = f"GTM Profile: {insight.company_ticker} FY{insight.fiscal_year}"[:79]

        metadata: dict = {
            "gtm_channels": insight.gtm_channels,
            "strategic_initiatives": insight.strategic_initiatives,
            "customer_segments": insight.customer_segments,
            "geographic_focus": insight.geographic_focus,
        }
        if insight.marketing_spend_pct is not None:
            metadata["marketing_spend_pct"] = insight.marketing_spend_pct
        if insight.rnd_spend_pct is not None:
            metadata["rnd_spend_pct"] = insight.rnd_spend_pct
        if insight.sales_headcount_mentioned is not None:
            metadata["sales_headcount"] = insight.sales_headcount_mentioned
        if insight.competitive_positioning:
            metadata["competitive_positioning"] = insight.competitive_positioning

        source_label = f"GTMIntel:{vertical_slug}" if vertical_slug else "GTMIntel"

        for company_id in user_company_ids:
            # Dedup
            existing = await self._session.execute(
                select(SignalEvent.id)
                .where(
                    SignalEvent.company_id == company_id,
                    SignalEvent.source_url == source_key,
                )
                .limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            event = SignalEvent(
                company_id=company_id,
                signal_type=SignalType.MARKET_TREND,
                urgency=SignalUrgency.MONITOR,
                headline=headline,
                summary=summary[:2000],
                source=source_label[:100],
                source_url=source_key,
                relevance_score=insight.confidence,
                competitors_mentioned=[],
                recommended_action=json.dumps(metadata),
            )
            self._session.add(event)
            created += 1

        if created:
            await self._session.flush()

        logger.info(
            "GTMFinancialExtractor: persisted %d signals (document %s)",
            created,
            document_id,
        )
        return created
