"""Fix garbage chapter metadata in knowledge_chunks.jsonl and Qdrant.

Reads every chunk, detects garbage chapter values using heuristics, re-runs
the improved _extract_chapter_hint() on each chunk's own text, then atomically
rewrites the JSONL and updates Qdrant payloads for changed chunks.

Usage:
    uv run python scripts/fix_chapter_metadata.py --dry-run   # preview only
    uv run python scripts/fix_chapter_metadata.py              # apply changes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow importing packages.knowledge without a full install
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from packages.knowledge.src.extractor import _extract_chapter_hint  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JSONL_PATH = REPO_ROOT / "data" / "knowledge" / "knowledge_chunks.jsonl"
QDRANT_COLLECTION = "marketing_knowledge"
QDRANT_PATH = str(REPO_ROOT / "data" / "qdrant")

# ---------------------------------------------------------------------------
# Garbage detection
# ---------------------------------------------------------------------------

# Patterns that are never legitimate chapter titles

# Known verbatim garbage values observed in this dataset — caught by exact match
_KNOWN_GARBAGE: frozenset[str] = frozenset(
    {
        "Complete Ly",
        "Success Publicationssuccess Publications",
        "Jfk Fbi Nato Ups Nasa Irs",
        "Philip Kotler",
    }
)

# A "split-word" artefact: a word that ends with a capital letter followed by
# a space-separated titlecase suffix that is a common morpheme fragment.
# e.g. "Complete Ly" — detected by whether the last token is a known suffix.
# Only matches exactly two tokens (not chapter-prefixed strings).
_SPLIT_SUFFIX = re.compile(r"^[A-Z][a-z]+\s+[A-Z][a-z]{1,3}$")
_KNOWN_SUFFIXES = {"ly", "ed", "er", "ry", "ty", "al", "ic", "nt", "ng", "tion"}

# Acronym-list pattern: string of 3+ space-separated tokens where every token is
# 2-5 chars and title-cased (not a chapter-prefixed string).
_ACRONYM_TOKEN = re.compile(r"^[A-Z][a-z]{0,3}$")


def _is_garbage_chapter(chapter: str | None) -> bool:
    """Return True if the chapter value is a known-bad artefact."""
    if chapter is None:
        return False

    # Newlines or tabs inside chapter string — multi-line capture bug or PDF noise
    if "\n" in chapter or "\t" in chapter:
        return True

    # Exact known-bad values
    if chapter in _KNOWN_GARBAGE:
        return True

    # Chapter-prefixed strings: only flag for whitespace contamination (already caught above)
    # Everything starting with "Chapter N" is preserved unless it has a tab/newline.
    if re.match(r"^Chapter\s+\d+", chapter):
        return False

    # Acronym lists: 3+ tokens all matching 1-5 char title-case
    tokens = chapter.split()
    if len(tokens) >= 3 and all(_ACRONYM_TOKEN.match(t) for t in tokens):
        return True

    # Split-word artefacts like "Complete Ly" (exactly two title-case words,
    # last word is a known morpheme suffix)
    if _SPLIT_SUFFIX.match(chapter):
        tail = tokens[-1].lower()
        if tail in _KNOWN_SUFFIXES:
            return True

    # Single word longer than any reasonable chapter title
    if len(tokens) == 1 and len(chapter) > 25:
        return True

    return False


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------


async def _update_qdrant_payloads(
    changed: list[tuple[str, str | None]],
) -> int:
    """Update Qdrant chapter payloads for changed chunks.

    Args:
        changed: List of (chunk_id, new_chapter) tuples.

    Returns:
        Number of Qdrant points successfully updated.
    """
    try:
        from qdrant_client import AsyncQdrantClient  # noqa: PLC0415
        from qdrant_client.models import PointIdsList  # noqa: PLC0415
    except ImportError:
        logger.warning("qdrant-client not installed — skipping Qdrant update")
        return 0

    qdrant_url = os.environ.get("QDRANT_URL", "").strip()
    qdrant_path = os.environ.get("QDRANT_PATH", QDRANT_PATH).strip()

    try:
        if qdrant_url:
            qdrant = AsyncQdrantClient(url=qdrant_url)
        else:
            qdrant = AsyncQdrantClient(path=qdrant_path)
    except Exception as exc:
        logger.warning("Could not open Qdrant (possibly locked by gateway): %s", exc)
        return 0

    updated = 0
    # Group by new_chapter value to minimise round-trips
    by_chapter: dict[str | None, list[str]] = {}
    for chunk_id, new_chapter in changed:
        by_chapter.setdefault(new_chapter, []).append(chunk_id)

    for new_chapter, ids in by_chapter.items():
        try:
            await qdrant.set_payload(
                collection_name=QDRANT_COLLECTION,
                payload={"chapter": new_chapter},
                points=PointIdsList(points=ids),
            )
            updated += len(ids)
        except Exception as exc:
            logger.warning(
                "Qdrant set_payload failed for %d points (chapter=%r): %s",
                len(ids),
                new_chapter,
                exc,
            )

    try:
        await qdrant.close()
    except Exception:
        pass

    return updated


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


async def run(dry_run: bool) -> None:
    if not JSONL_PATH.exists():
        logger.error("JSONL not found: %s", JSONL_PATH)
        sys.exit(1)

    # --- Load all chunks ---
    chunks: list[dict] = []
    with JSONL_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    logger.info("Loaded %d chunks from %s", len(chunks), JSONL_PATH)

    # --- Analyse and fix ---
    changed: list[tuple[str, str | None]] = []  # (id, new_chapter)
    improved = 0    # garbage → good chapter
    set_to_none = 0  # garbage → None (no hint found)
    already_ok = 0  # not garbage, unchanged

    for chunk in chunks:
        old_chapter = chunk.get("chapter")

        if not _is_garbage_chapter(old_chapter):
            already_ok += 1
            continue

        new_chapter = _extract_chapter_hint(chunk["text"])
        chunk_id = chunk["id"]

        if dry_run:
            logger.info(
                "[DRY-RUN] id=%s  old=%r  ->  new=%r",
                chunk_id[:8],
                old_chapter,
                new_chapter,
            )
        else:
            chunk["chapter"] = new_chapter

        changed.append((chunk_id, new_chapter))

        if new_chapter is not None:
            improved += 1
        else:
            set_to_none += 1

    # --- Summary ---
    logger.info(
        "Analysis: %d garbage chapters found (%d improved, %d -> None), %d already OK",
        len(changed),
        improved,
        set_to_none,
        already_ok,
    )

    if not changed:
        logger.info("Nothing to fix — exiting.")
        return

    if dry_run:
        logger.info("[DRY-RUN] No files written, no Qdrant updates performed.")
        return

    # --- Atomic JSONL rewrite ---
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=JSONL_PATH.parent, suffix=".tmp", prefix="knowledge_chunks_"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            for chunk in chunks:
                fh.write(json.dumps(chunk) + "\n")
        os.replace(tmp_path, JSONL_PATH)
        logger.info("JSONL atomically rewritten: %s", JSONL_PATH)
    except Exception as exc:
        logger.error("Failed to rewrite JSONL: %s", exc)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        sys.exit(1)

    # --- Qdrant update ---
    qdrant_updated = await _update_qdrant_payloads(changed)
    if qdrant_updated:
        logger.info("Qdrant: updated %d point payloads", qdrant_updated)
    else:
        logger.info(
            "Qdrant: 0 points updated (client unavailable or locked) — JSONL is the source of truth"
        )

    # --- Final report ---
    logger.info(
        "Done. Cleaned up %d chapters: %d improved to valid heading, %d set to None.",
        len(changed),
        improved,
        set_to_none,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix garbage chapter metadata in knowledge_chunks.jsonl"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing anything",
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
