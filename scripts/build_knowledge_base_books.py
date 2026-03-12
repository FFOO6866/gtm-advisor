#!/usr/bin/env python3
"""Build the marketing knowledge base from reference books.

Processes all 14 marketing reference books in /Users/ssfoo/Desktop/Reference Book/:
  1. Creates the 'marketing_knowledge' Qdrant collection
  2. Extracts text from each PDF (capped at 100 pages for large files)
  3. Chunks into 400-word pieces with 50-word overlap
  4. Embeds with OpenAI text-embedding-3-small
  5. Stores to Qdrant marketing_knowledge collection
  6. Writes a JSONL backup to data/knowledge/knowledge_chunks.jsonl

Usage:
    uv run python scripts/build_knowledge_base_books.py
    uv run python scripts/build_knowledge_base_books.py --dry-run
    uv run python scripts/build_knowledge_base_books.py --book cialdini_persuasion

Environment variables required:
    OPENAI_API_KEY    — for embedding generation (required)
    QDRANT_URL        — Qdrant HTTP endpoint (optional; falls back to QDRANT_PATH)
    QDRANT_PATH       — local Qdrant data path (optional)

Cost estimate:
    ~3,000 chunks × 400 words × 1.3 chars/word ÷ 4 chars/token = ~390,000 tokens
    text-embedding-3-small: $0.020/1M tokens → ~$0.008 total
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — must come before local imports
# ---------------------------------------------------------------------------

# Add repo root to sys.path so package imports resolve correctly
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_kb_books")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(dry_run: bool, book_key: str | None, page_limit: int) -> None:
    from packages.knowledge.src.book_index import BOOK_KNOWLEDGE_MAP
    from packages.knowledge.src.extractor import BOOKS_DIR, OUTPUT_DIR, BookKnowledgeExtractor

    logger.info("=== GTM Advisor Marketing Knowledge Base Builder ===")
    logger.info("Books directory: %s", BOOKS_DIR)
    logger.info("Output directory: %s", OUTPUT_DIR)
    logger.info("Default page limit: %d pages per book", page_limit)

    if dry_run:
        logger.info("DRY RUN — showing what would be processed without embedding or storing")
        for key, meta in BOOK_KNOWLEDGE_MAP.items():
            file_path = BOOKS_DIR / meta["file"]
            exists = "EXISTS" if file_path.exists() else "MISSING"
            limit = meta.get("page_limit") or page_limit
            priority = meta.get("extraction_priority", "medium")
            logger.info(
                "  [%s] %s (%s): %s — limit=%s pages — agents=%s",
                priority.upper(),
                exists,
                key,
                meta["file"],
                limit,
                ", ".join(meta.get("agent_relevance", [])),
            )
        return

    extractor = BookKnowledgeExtractor(page_limit=page_limit)

    if book_key:
        # Process a single book
        if book_key not in BOOK_KNOWLEDGE_MAP:
            logger.error(
                "Book key '%s' not found. Available keys: %s",
                book_key,
                list(BOOK_KNOWLEDGE_MAP.keys()),
            )
            sys.exit(1)

        meta = BOOK_KNOWLEDGE_MAP[book_key]
        book_path = BOOKS_DIR / meta["file"]
        if not book_path.exists():
            logger.error("Book file not found: %s", book_path)
            sys.exit(1)

        per_book_limit = meta.get("page_limit") or page_limit
        logger.info("Processing single book: %s", meta["title"])

        # Initialise clients
        from packages.knowledge.src.extractor import (  # noqa: PLC0415
            _get_openai_client,
            _get_qdrant_client,
        )

        extractor._openai = _get_openai_client()
        extractor._qdrant = _get_qdrant_client()
        await extractor._ensure_qdrant_collection()

        chunks = await extractor.extract_book(
            book_path,
            book_key=book_key,
            book_title=meta["title"],
            page_limit=per_book_limit,
        )
        logger.info("Extracted %d chunks", len(chunks))

        if chunks:
            stored = await extractor.embed_and_store(chunks)
            logger.info("Stored %d chunks to Qdrant", stored)

            # Write JSONL backup
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            import json

            jsonl_path = OUTPUT_DIR / "knowledge_chunks.jsonl"
            with jsonl_path.open("a", encoding="utf-8") as f:
                for chunk in chunks:
                    f.write(json.dumps(chunk.to_jsonl_dict()) + "\n")
            logger.info("JSONL backup written to %s", jsonl_path)

        _print_summary({meta["file"]: len(chunks)})
        return

    # Process all books
    results = await extractor.extract_all()
    _print_summary(results)


def _print_summary(results: dict[str, int]) -> None:
    """Print a formatted summary table of extraction results."""
    total_chunks = sum(results.values())
    logger.info("")
    logger.info("=== Extraction Summary ===")
    logger.info("%-70s %s", "Book", "Chunks")
    logger.info("-" * 80)
    for filename, count in sorted(results.items(), key=lambda x: -x[1]):
        short_name = Path(filename).stem[:65]
        logger.info("%-70s %d", short_name, count)
    logger.info("-" * 80)
    logger.info("%-70s %d", "TOTAL", total_chunks)
    logger.info("")
    logger.info(
        "JSONL backup: /Users/ssfoo/Documents/GitHub/gtm-advisor/data/knowledge/knowledge_chunks.jsonl"
    )
    logger.info("Qdrant collection: marketing_knowledge")
    logger.info("=== Build Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build the GTM Advisor marketing knowledge base from reference books"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without embedding or storing",
    )
    parser.add_argument(
        "--book",
        type=str,
        default=None,
        metavar="BOOK_KEY",
        help="Process a single book by key (e.g. cialdini_persuasion). See book_index.py for keys.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=100,
        metavar="N",
        help="Override default page limit per book (default: 100)",
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, book_key=args.book, page_limit=args.page_limit))
