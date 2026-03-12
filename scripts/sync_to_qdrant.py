#!/usr/bin/env python3
"""Full sync of knowledge_chunks.jsonl → Qdrant marketing_knowledge collection.

Unlike complete_embeddings.py (which only processes null-embedding chunks),
this script upserts ALL chunks regardless of whether they were previously
upserted, ensuring Qdrant is exactly in sync with the JSONL.

Also cleans chapter metadata in-place before upserting:
  - Filters "In This Chapter, We..." false positives (TOC intro sentences)
  - Filters titles that look truncated (end in preposition/article mid-sentence)

Usage:
    uv run python scripts/sync_to_qdrant.py
    uv run python scripts/sync_to_qdrant.py --dry-run
    uv run python scripts/sync_to_qdrant.py --skip-chapter-fix

Environment variables:
    OPENAI_API_KEY  — not needed (embeddings already in JSONL)
    QDRANT_PATH     — local Qdrant path  (e.g. data/qdrant)
    QDRANT_URL      — remote Qdrant URL  (alternative to QDRANT_PATH)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sync_to_qdrant")

JSONL_PATH = _REPO_ROOT / "data" / "knowledge" / "knowledge_chunks.jsonl"
QDRANT_COLLECTION = "marketing_knowledge"
UPSERT_BATCH = 100

# --------------------------------------------------------------------------
# Chapter metadata cleaning
# --------------------------------------------------------------------------

import re as _re

_CHAPTER_PREFIX_RE = _re.compile(r"^chapter\s+\d+[:\s]+", _re.IGNORECASE)

# Phrases that indicate a TOC intro sentence, not a real chapter heading.
# Checked against the TITLE portion (after "Chapter N: ") so that
# "Chapter 2: In This Chapter, We" is correctly rejected.
_FALSE_POSITIVE_PREFIXES = (
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

# Trailing tokens that indicate the title was truncated by the 60-char regex cap.
_TRUNCATION_SUFFIXES = (
    " the", " a", " an", " of", " and", " or", " in", " for",
    " to", " with", " on", " at", " by", " from", " that", " its",
    ",",  # ends mid-list (e.g. "Retailing, Wholesaling,")
)


def _clean_chapter(chapter: str | None) -> str | None:
    """Return None if the chapter name is a false positive or truncated fragment.

    Checks both the full string AND the title portion after "Chapter N: " for
    prefix patterns, so "Chapter 2: In This Chapter, We" is correctly rejected.
    """
    if not chapter:
        return None

    lower = chapter.lower()

    # Extract the title part after "Chapter N: " for prefix/case checks
    title_match = _CHAPTER_PREFIX_RE.match(chapter)
    title_original = chapter[title_match.end():] if title_match else chapter
    title_lower = title_original.lower()

    # Filter TOC intro sentences (check title portion, not full string)
    for prefix in _FALSE_POSITIVE_PREFIXES:
        if title_lower.startswith(prefix):
            return None

    # Filter titles whose content starts with a lowercase letter (sentence fragments)
    # Checked on the ORIGINAL (not lowercased) title so uppercase headings pass.
    if title_original and title_original[0].islower():
        return None

    # Filter truncated titles (checked on full lower string)
    for suffix in _TRUNCATION_SUFFIXES:
        if lower.endswith(suffix):
            return None

    return chapter


def _clean_all_chapters(chunks: list[dict]) -> tuple[list[dict], int]:
    """Apply chapter cleaning to all chunks. Returns (chunks, n_cleaned)."""
    n_cleaned = 0
    for c in chunks:
        original = c.get("chapter")
        cleaned = _clean_chapter(original)
        if cleaned != original:
            c["chapter"] = cleaned
            n_cleaned += 1
    return chunks, n_cleaned


# --------------------------------------------------------------------------
# Qdrant helpers
# --------------------------------------------------------------------------

async def _get_qdrant(qdrant_path: str, qdrant_url: str):
    from qdrant_client import AsyncQdrantClient
    if qdrant_url:
        return AsyncQdrantClient(url=qdrant_url)
    return AsyncQdrantClient(path=qdrant_path)


async def _ensure_collection(qdrant, dim: int = 1536) -> None:
    """Create collection if it doesn't exist; no-op otherwise."""
    from qdrant_client.models import Distance, VectorParams
    try:
        await qdrant.get_collection(QDRANT_COLLECTION)
        logger.info("Collection '%s' already exists", QDRANT_COLLECTION)
    except Exception:
        await qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        logger.info("Created collection '%s'", QDRANT_COLLECTION)


async def _upsert_all(qdrant, chunks: list[dict]) -> int:
    """Upsert all chunks (must have embeddings). Returns total upserted."""
    from qdrant_client.models import PointStruct

    total = 0
    for batch_start in range(0, len(chunks), UPSERT_BATCH):
        batch = chunks[batch_start: batch_start + UPSERT_BATCH]
        points = [
            PointStruct(
                id=c["id"],
                vector=c["embedding"],
                payload={
                    "book_title": c.get("book_title", ""),
                    "book_key": c.get("book_key", ""),
                    "chapter": c.get("chapter"),
                    "page_number": c.get("page_number", 0),
                    "text": c.get("text", ""),
                    "agent_tags": c.get("agent_tags", []),
                },
            )
            for c in batch
        ]
        await qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
        total += len(points)
        logger.info(
            "  Upserted %d / %d  (batch %d–%d)",
            total,
            len(chunks),
            batch_start + 1,
            batch_start + len(batch),
        )
    return total


async def _count(qdrant) -> int:
    info = await qdrant.get_collection(QDRANT_COLLECTION)
    return info.points_count or 0


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

async def main(dry_run: bool, skip_chapter_fix: bool) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    qdrant_path = os.environ.get("QDRANT_PATH", "").strip()
    qdrant_url = os.environ.get("QDRANT_URL", "").strip()
    if not qdrant_path and not qdrant_url:
        logger.error("Neither QDRANT_PATH nor QDRANT_URL is set")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load JSONL
    # ------------------------------------------------------------------
    logger.info("Loading chunks from %s", JSONL_PATH)
    chunks: list[dict] = []
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    logger.info("Loaded %d chunks", len(chunks))

    missing_embeddings = [c for c in chunks if not c.get("embedding")]
    if missing_embeddings:
        logger.error(
            "%d chunks have no embedding — run complete_embeddings.py first",
            len(missing_embeddings),
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Clean chapter metadata
    # ------------------------------------------------------------------
    n_cleaned = 0
    if not skip_chapter_fix:
        chunks, n_cleaned = _clean_all_chapters(chunks)

        # Show what was cleaned
        if n_cleaned:
            logger.info("Chapter metadata: cleaned %d false positive / truncated titles", n_cleaned)
        else:
            logger.info("Chapter metadata: nothing to clean")

    # ------------------------------------------------------------------
    # Dry-run report
    # ------------------------------------------------------------------
    if dry_run:
        by_book: dict[str, int] = {}
        for c in chunks:
            bk = c.get("book_key", "?")
            by_book[bk] = by_book.get(bk, 0) + 1
        logger.info("DRY RUN — would upsert %d chunks to '%s'", len(chunks), QDRANT_COLLECTION)
        logger.info("Chapter titles cleaned: %d", n_cleaned)
        logger.info("Per-book breakdown:")
        for bk, cnt in sorted(by_book.items()):
            logger.info("  %-40s  %d", bk, cnt)
        return

    # ------------------------------------------------------------------
    # Atomically rewrite JSONL with cleaned metadata
    # ------------------------------------------------------------------
    if not skip_chapter_fix and n_cleaned:
        tmp = JSONL_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c) + "\n")
        tmp.replace(JSONL_PATH)
        logger.info("JSONL rewritten with cleaned chapter metadata")

    # ------------------------------------------------------------------
    # Upsert to Qdrant
    # ------------------------------------------------------------------
    qdrant = await _get_qdrant(qdrant_path, qdrant_url)
    await _ensure_collection(qdrant)

    logger.info("Upserting %d chunks to Qdrant…", len(chunks))
    upserted = await _upsert_all(qdrant, chunks)

    final_count = await _count(qdrant)
    await qdrant.close()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info("=" * 50)
    logger.info("JSONL chunks:          %d", len(chunks))
    logger.info("Upserted this run:     %d", upserted)
    logger.info("Qdrant final count:    %d", final_count)
    logger.info("Chapter titles fixed:  %d", n_cleaned)

    if final_count == len(chunks):
        logger.info("✓ Qdrant is 100%% in sync with JSONL")
    else:
        logger.warning(
            "✗ Mismatch: JSONL has %d but Qdrant reports %d",
            len(chunks),
            final_count,
        )
        sys.exit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full JSONL → Qdrant sync")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-chapter-fix", action="store_true",
                        help="Skip chapter metadata cleaning")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, skip_chapter_fix=args.skip_chapter_fix))
