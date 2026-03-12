"""Layer 3: PDF extraction, chunking, embedding, and Qdrant ingestion.

Extracts text from marketing reference books, splits into 400-word chunks,
embeds via OpenAI text-embedding-3-small, and stores in:
  - Qdrant collection 'marketing_knowledge' (vector search)
  - JSONL file data/knowledge/knowledge_chunks.jsonl (local backup)

Large books (Kotler 34MB, Principles 32MB) are capped at PAGE_LIMIT=100
pages to keep embedding costs reasonable.

Usage:
    extractor = BookKnowledgeExtractor()
    counts = await extractor.extract_all()
    # {'kotler_keller...': 87, 'The Psychology...': 43, ...}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOOKS_DIR = Path("/Users/ssfoo/Desktop/Reference Book")
OUTPUT_DIR = Path("/Users/ssfoo/Documents/GitHub/gtm-advisor/data/knowledge")
CHUNK_WORDS = 400
PAGE_LIMIT = 100
QDRANT_COLLECTION = "marketing_knowledge"
EMBEDDING_DIM = 1536  # text-embedding-3-small
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 50
MAX_CHARS_PER_TEXT = 6000

# Agent tagging rules: keyword → list[agent_name]
_AGENT_TAG_RULES: list[tuple[list[str], list[str]]] = [
    (
        ["persuasion", "cialdini", "reciprocity", "social proof", "scarcity", "authority",
         "liking", "commitment", "copywriting", "ogilvy", "headline", "copy"],
        ["campaign_architect", "outreach_executor"],
    ),
    (
        ["segmentation", "icp", "ideal customer", "persona", "psychographic",
         "firmographic", "target market", "targeting", "positioning", "stp"],
        ["customer_profiler", "gtm_strategist"],
    ),
    (
        ["bant", "meddic", "spin selling", "qualification", "prospect", "lead scoring",
         "challenger sale", "discovery", "objection"],
        ["lead_hunter", "outreach_executor"],
    ),
    (
        ["market analysis", "competitor", "porter", "five forces", "swot",
         "competitive", "market share", "industry analysis", "market trend"],
        ["market_intelligence", "competitor_analyst"],
    ),
    (
        ["campaign", "aida", "messaging", "content", "email marketing", "sequence",
         "channel strategy", "marketing mix", "promotion"],
        ["campaign_architect"],
    ),
    (
        ["go-to-market", "gtm", "product-led", "sales-led", "marketing strategy",
         "brand positioning", "value proposition", "market entry"],
        ["gtm_strategist"],
    ),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeChunk:
    """A single chunk of extracted book knowledge."""

    id: str
    book_title: str
    book_key: str
    chapter: str | None
    page_number: int
    text: str
    agent_tags: list[str]
    embedding: list[float] | None = field(default=None, repr=False)

    def to_payload(self) -> dict:
        """Qdrant payload (excludes the vector itself)."""
        return {
            "book_title": self.book_title,
            "book_key": self.book_key,
            "chapter": self.chapter,
            "page_number": self.page_number,
            "text": self.text,
            "agent_tags": self.agent_tags,
        }

    def to_jsonl_dict(self) -> dict:
        """Serialisable dict for JSONL output (embedding stored as list[float])."""
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Qdrant helpers (lazy import guard)
# ---------------------------------------------------------------------------


def _get_qdrant_client():
    """Return an AsyncQdrantClient or None if qdrant-client is not installed."""
    try:
        from qdrant_client import AsyncQdrantClient  # noqa: PLC0415

        qdrant_url = os.environ.get("QDRANT_URL", "").strip()
        qdrant_path = os.environ.get("QDRANT_PATH", "").strip()
        if qdrant_url:
            return AsyncQdrantClient(url=qdrant_url)
        if qdrant_path:
            return AsyncQdrantClient(path=qdrant_path)
    except ImportError:
        logger.warning("qdrant-client not installed — Qdrant upsert will be skipped")
    return None


def _get_openai_client():
    """Return an AsyncOpenAI client or None if not configured."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — embedding will be skipped")
        return None
    try:
        import openai  # noqa: PLC0415

        return openai.AsyncOpenAI(api_key=api_key)
    except ImportError:
        logger.warning("openai package not installed — embedding will be skipped")
        return None


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------


def _tag_chunk(text: str) -> list[str]:
    """Determine which agents a chunk is relevant to based on keyword matching."""
    text_lower = text.lower()
    tags: set[str] = set()
    for keywords, agents in _AGENT_TAG_RULES:
        if any(kw in text_lower for kw in keywords):
            tags.update(agents)
    # Default: tag all agents if no specific match (general marketing knowledge)
    return sorted(tags) if tags else ["campaign_architect", "customer_profiler", "gtm_strategist"]


_CHAPTER_FALSE_POSITIVE_PREFIXES = (
    "in this chapter",
    "this chapter",
    "by the end of",
    "after reading",
    "learning objective",
    "summary :",
    "summary:",
    'from "',
    "from '",
)

_CHAPTER_TRUNCATION_SUFFIXES = (
    " the", " a", " an", " of", " and", " or", " in",
    " for", " to", " with", " on", " at", " by", " from",
    " that", " its",
    ",",  # ends mid-list
)


def _extract_chapter_hint(text: str) -> str | None:
    """Try to detect a chapter heading from the first 200 characters of text."""
    head = text[:200]
    # Primary: "Chapter N: Title" — reliable across all books
    match = re.search(r"(?:Chapter|CHAPTER)\s+(\d+)[:\s]+([^\n]{5,60})", head)
    if match:
        title = match.group(2).strip()
        title_lower = title.lower()
        # Reject TOC intro sentences ("In This Chapter, We Will Address…")
        if any(title_lower.startswith(p) for p in _CHAPTER_FALSE_POSITIVE_PREFIXES):
            return None
        # Reject titles whose content starts lowercase (sentence fragments, not headings).
        # Checked on the ORIGINAL (not lowercased) title so all-caps headings pass.
        if title and title[0].islower():
            return None
        # Reject titles that ended mid-sentence due to the 60-char regex cap
        if any(title_lower.endswith(s) for s in _CHAPTER_TRUNCATION_SUFFIXES):
            return None
        return f"Chapter {match.group(1)}: {title}"
    # Secondary: all-caps heading — strict: single line, 2–5 words, no acronym noise
    match = re.search(r"\n([A-Z][A-Z ]{8,50})\n", head)  # space not \s — no newlines inside
    if match:
        heading = match.group(1).strip()
        words = heading.split()
        # Require 2-5 words, each word at least 3 chars (filters JFK, FBI, NATO etc.)
        # and no more than one very short word (allows "THE CHALLENGER SALE")
        if (
            2 <= len(words) <= 5
            and sum(1 for w in words if len(w) <= 2) <= 1
            and all(w.isalpha() for w in words)  # pure letters — no numbers, punctuation
        ):
            return heading.title()
    return None


def _chunk_text(text: str, chunk_words: int = CHUNK_WORDS) -> list[str]:
    """Split text into overlapping chunks of approximately chunk_words words.

    Uses a 50-word overlap to maintain context across boundaries.
    """
    if not text.strip():
        return []

    words = text.split()
    if not words:
        return []

    overlap = 50
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 100:  # skip tiny chunks
            chunks.append(chunk)
        if end >= len(words):
            break
        start += chunk_words - overlap

    return chunks


# ---------------------------------------------------------------------------
# PDF extraction (sync, runs in executor)
# ---------------------------------------------------------------------------


def _extract_pdf_pages(pdf_path: Path, page_limit: int | None) -> list[tuple[int, str]]:
    """Synchronously extract text from a PDF, returning (page_number, text) tuples.

    Runs in a thread executor to avoid blocking the event loop.
    Caps extraction at page_limit if provided.
    """
    try:
        import pypdf  # noqa: PLC0415
    except ImportError:
        logger.error("pypdf is not installed — cannot extract PDF: %s", pdf_path)
        return []

    results: list[tuple[int, str]] = []
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        total_pages = len(reader.pages)
        limit = min(total_pages, page_limit) if page_limit else total_pages
        logger.info(
            "Extracting %s: %d/%d pages (limit=%s)",
            pdf_path.name,
            limit,
            total_pages,
            page_limit,
        )
        for page_num in range(limit):
            try:
                page = reader.pages[page_num]
                text = page.extract_text() or ""
                if text.strip():
                    results.append((page_num + 1, text))
            except Exception as exc:
                logger.warning("Page %d extract failed in %s: %s", page_num + 1, pdf_path.name, exc)
    except Exception as exc:
        logger.error("Failed to open PDF %s: %s", pdf_path, exc)
    return results


def _extract_docx_text(docx_path: Path) -> list[tuple[int, str]]:
    """Synchronously extract text from a DOCX file, treating each paragraph as a 'page'."""
    try:
        import docx  # noqa: PLC0415
    except ImportError:
        logger.warning("python-docx not installed — skipping DOCX: %s", docx_path)
        return []

    results: list[tuple[int, str]] = []
    try:
        doc = docx.Document(str(docx_path))
        # Group paragraphs into pseudo-pages of ~500 words
        buffer: list[str] = []
        pseudo_page = 1
        word_count = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            buffer.append(text)
            word_count += len(text.split())
            if word_count >= 500:
                results.append((pseudo_page, "\n".join(buffer)))
                buffer = []
                word_count = 0
                pseudo_page += 1
        if buffer:
            results.append((pseudo_page, "\n".join(buffer)))
    except Exception as exc:
        logger.error("Failed to open DOCX %s: %s", docx_path, exc)
    return results


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------


class BookKnowledgeExtractor:
    """Extracts, chunks, embeds, and stores marketing knowledge from reference PDFs.

    Usage:
        extractor = BookKnowledgeExtractor()
        counts = await extractor.extract_all()

        # Or process a single book:
        chunks = await extractor.extract_book(Path("/path/to/book.pdf"))
        stored = await extractor.embed_and_store(chunks)
    """

    def __init__(
        self,
        books_dir: Path = BOOKS_DIR,
        output_dir: Path = OUTPUT_DIR,
        page_limit: int = PAGE_LIMIT,
    ) -> None:
        self.books_dir = books_dir
        self.output_dir = output_dir
        self.page_limit = page_limit
        self._openai = None  # lazy-initialised
        self._qdrant = None  # lazy-initialised

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def extract_all(self) -> dict[str, int]:
        """Process all books in BOOKS_DIR. Returns {book_filename: chunk_count}.

        Respects per-book page limits defined in BOOK_KNOWLEDGE_MAP.
        Skips books that cannot be found.
        """
        from packages.knowledge.src.book_index import BOOK_KNOWLEDGE_MAP  # noqa: PLC0415

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialise clients once
        self._openai = _get_openai_client()
        self._qdrant = _get_qdrant_client()

        await self._ensure_qdrant_collection()

        results: dict[str, int] = {}
        jsonl_path = self.output_dir / "knowledge_chunks.jsonl"

        with jsonl_path.open("a", encoding="utf-8") as jsonl_file:
            for book_key, book_meta in BOOK_KNOWLEDGE_MAP.items():
                filename = book_meta["file"]
                # Determine extension
                if filename.endswith(".docx"):
                    book_path = self.books_dir / filename
                else:
                    book_path = self.books_dir / filename

                if not book_path.exists():
                    logger.warning("Book not found, skipping: %s", book_path)
                    results[filename] = 0
                    continue

                per_book_limit = book_meta.get("page_limit") or self.page_limit
                logger.info("Processing: %s (limit=%s pages)", filename, per_book_limit)

                try:
                    chunks = await self.extract_book(
                        book_path,
                        book_key=book_key,
                        book_title=book_meta["title"],
                        page_limit=per_book_limit,
                    )
                    if not chunks:
                        logger.warning("No chunks extracted from: %s", filename)
                        results[filename] = 0
                        continue

                    stored = await self.embed_and_store(chunks)
                    results[filename] = stored

                    # Write to JSONL (streaming, one line per chunk)
                    for chunk in chunks:
                        jsonl_file.write(json.dumps(chunk.to_jsonl_dict()) + "\n")
                    jsonl_file.flush()

                    logger.info(
                        "Completed %s: %d chunks extracted, %d stored to Qdrant",
                        filename,
                        len(chunks),
                        stored,
                    )
                except Exception as exc:
                    logger.error("Failed to process %s: %s", filename, exc, exc_info=True)
                    results[filename] = 0

        logger.info("extract_all complete: %s", results)
        return results

    async def extract_book(
        self,
        pdf_path: Path,
        book_key: str = "unknown",
        book_title: str = "",
        page_limit: int | None = None,
    ) -> list[KnowledgeChunk]:
        """Extract one book into KnowledgeChunk objects.

        Args:
            pdf_path: Path to the PDF (or DOCX) file.
            book_key: Key from BOOK_KNOWLEDGE_MAP.
            book_title: Human-readable title.
            page_limit: Override the default page limit.

        Returns:
            List of KnowledgeChunk objects (without embeddings).
        """
        effective_limit = page_limit if page_limit is not None else self.page_limit
        title = book_title or pdf_path.stem

        # Run blocking I/O in executor
        loop = asyncio.get_event_loop()
        if pdf_path.suffix.lower() == ".docx":
            page_texts = await loop.run_in_executor(None, _extract_docx_text, pdf_path)
        else:
            page_texts = await loop.run_in_executor(
                None, _extract_pdf_pages, pdf_path, effective_limit
            )

        if not page_texts:
            return []

        chunks: list[KnowledgeChunk] = []
        current_chapter: str | None = None

        for page_num, page_text in page_texts:
            # Update chapter hint from page text
            chapter_hint = _extract_chapter_hint(page_text)
            if chapter_hint:
                current_chapter = chapter_hint

            text_chunks = _chunk_text(page_text, chunk_words=CHUNK_WORDS)
            for chunk_text in text_chunks:
                chunk = KnowledgeChunk(
                    id=str(uuid.uuid4()),
                    book_title=title,
                    book_key=book_key,
                    chapter=current_chapter,
                    page_number=page_num,
                    text=chunk_text[:MAX_CHARS_PER_TEXT],
                    agent_tags=_tag_chunk(chunk_text),
                )
                chunks.append(chunk)

        logger.info("Extracted %d chunks from %s", len(chunks), pdf_path.name)
        return chunks

    async def embed_and_store(self, chunks: list[KnowledgeChunk]) -> int:
        """Embed chunks and upsert to Qdrant marketing_knowledge collection.

        Args:
            chunks: List of KnowledgeChunk objects (embedding may be None).

        Returns:
            Number of chunks successfully stored in Qdrant.
        """
        if not chunks:
            return 0

        if self._openai is None:
            logger.warning("OpenAI client not available — skipping embedding")
            return 0

        # Batch embed
        texts = [c.text for c in chunks]
        embeddings = await self._embed_batch(texts)

        # Attach embeddings to chunks
        for chunk, emb in zip(chunks, embeddings, strict=True):
            chunk.embedding = emb

        embedded_chunks = [c for c in chunks if c.embedding is not None]
        logger.info(
            "Embedded %d/%d chunks successfully",
            len(embedded_chunks),
            len(chunks),
        )

        if not embedded_chunks or self._qdrant is None:
            return 0

        # Upsert to Qdrant
        return await self._upsert_to_qdrant(embedded_chunks)

    async def search(self, query: str, limit: int = 10) -> list[KnowledgeChunk]:
        """Search the knowledge base by semantic similarity.

        Args:
            query: Natural language search query.
            limit: Maximum number of results to return.

        Returns:
            List of KnowledgeChunk objects sorted by relevance (no embedding field).
        """
        if self._openai is None:
            self._openai = _get_openai_client()
        if self._qdrant is None:
            self._qdrant = _get_qdrant_client()

        if self._openai is None or self._qdrant is None:
            return []

        # Embed query
        query_emb = await self._embed_single(query)
        if query_emb is None:
            return []

        try:
            response = await self._qdrant.query_points(
                collection_name=QDRANT_COLLECTION,
                query=query_emb,
                limit=limit,
                with_payload=True,
            )
            results: list[KnowledgeChunk] = []
            for hit in response.points:
                payload = hit.payload or {}
                chunk = KnowledgeChunk(
                    id=str(hit.id),
                    book_title=payload.get("book_title", ""),
                    book_key=payload.get("book_key", ""),
                    chapter=payload.get("chapter"),
                    page_number=payload.get("page_number", 0),
                    text=payload.get("text", ""),
                    agent_tags=payload.get("agent_tags", []),
                    embedding=None,
                )
                results.append(chunk)
            return results
        except Exception as exc:
            logger.warning("Qdrant search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Embed texts in batches, returning None for failed items."""
        results: list[list[float] | None] = []
        client = self._openai

        for batch_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = [
                t.strip()[:MAX_CHARS_PER_TEXT]
                for t in texts[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
            ]
            try:
                response = await client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                )
                for item in response.data:
                    results.append(item.embedding)
            except Exception as exc:
                logger.warning(
                    "Embedding batch %d failed: %s",
                    batch_start // EMBEDDING_BATCH_SIZE,
                    exc,
                )
                results.extend([None] * len(batch))

        return results

    async def _embed_single(self, text: str) -> list[float] | None:
        """Embed a single text string."""
        results = await self._embed_batch([text])
        return results[0] if results else None

    async def _ensure_qdrant_collection(self) -> None:
        """Create the marketing_knowledge collection if it does not exist."""
        if self._qdrant is None:
            return
        try:
            from qdrant_client.models import Distance, VectorParams  # noqa: PLC0415

            existing = await self._qdrant.get_collections()
            names = {c.name for c in existing.collections}
            if QDRANT_COLLECTION not in names:
                await self._qdrant.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection: %s", QDRANT_COLLECTION)
            else:
                logger.info("Qdrant collection already exists: %s", QDRANT_COLLECTION)
        except Exception as exc:
            logger.warning("Could not ensure Qdrant collection: %s", exc)

    async def _upsert_to_qdrant(self, chunks: list[KnowledgeChunk]) -> int:
        """Upsert embedded chunks to Qdrant. Returns count upserted."""
        try:
            from qdrant_client.models import PointStruct  # noqa: PLC0415

            points = [
                PointStruct(
                    id=chunk.id,
                    vector=chunk.embedding,
                    payload=chunk.to_payload(),
                )
                for chunk in chunks
                if chunk.embedding is not None
            ]
            if not points:
                return 0
            await self._qdrant.upsert(
                collection_name=QDRANT_COLLECTION,
                points=points,
            )
            return len(points)
        except Exception as exc:
            logger.error("Qdrant upsert failed: %s", exc, exc_info=True)
            return 0
