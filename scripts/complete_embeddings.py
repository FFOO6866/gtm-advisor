#!/usr/bin/env python3
"""Complete interrupted embedding run for marketing_knowledge Qdrant collection.

Reads data/knowledge/knowledge_chunks.jsonl, finds chunks with embedding=None,
embeds them via OpenAI text-embedding-3-small, upserts to Qdrant, and rewrites
the JSONL with all embeddings populated.

Usage:
    uv run python scripts/complete_embeddings.py
    uv run python scripts/complete_embeddings.py --dry-run

Environment variables required:
    OPENAI_API_KEY  — for embedding
    QDRANT_PATH     — local Qdrant path (or QDRANT_URL for remote)
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
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("complete_embeddings")

JSONL_PATH = _REPO_ROOT / "data" / "knowledge" / "knowledge_chunks.jsonl"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 50
QDRANT_COLLECTION = "marketing_knowledge"


async def main(dry_run: bool) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)

    qdrant_path = os.environ.get("QDRANT_PATH", "").strip()
    qdrant_url = os.environ.get("QDRANT_URL", "").strip()
    if not qdrant_path and not qdrant_url:
        logger.error("Neither QDRANT_PATH nor QDRANT_URL is set")
        sys.exit(1)

    # Load all chunks from JSONL
    logger.info("Loading chunks from %s", JSONL_PATH)
    all_chunks: list[dict] = []
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))

    needs_embedding = [c for c in all_chunks if c.get("embedding") is None]
    already_done = len(all_chunks) - len(needs_embedding)
    logger.info(
        "Total chunks: %d | Already embedded: %d | Need embedding: %d",
        len(all_chunks),
        already_done,
        len(needs_embedding),
    )

    if not needs_embedding:
        logger.info("All chunks already have embeddings — nothing to do")
        return

    if dry_run:
        logger.info("DRY RUN — would embed %d chunks", len(needs_embedding))
        for bk, count in _per_book_count(needs_embedding).items():
            logger.info("  %s: %d chunks", bk, count)
        return

    # Embed missing chunks
    import openai
    client = openai.AsyncOpenAI(api_key=api_key)
    texts = [c["text"] for c in needs_embedding]
    embeddings = await _embed_all(client, texts)
    logger.info("Embedded %d/%d chunks", sum(1 for e in embeddings if e is not None), len(texts))

    # Attach embeddings
    successful: list[dict] = []
    for chunk, emb in zip(needs_embedding, embeddings, strict=True):
        if emb is not None:
            chunk["embedding"] = emb
            successful.append(chunk)

    # Upsert to Qdrant
    logger.info("Upserting %d chunks to Qdrant collection '%s'", len(successful), QDRANT_COLLECTION)
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import PointStruct

    if qdrant_url:
        qdrant = AsyncQdrantClient(url=qdrant_url)
    else:
        qdrant = AsyncQdrantClient(path=qdrant_path)

    upserted = 0
    for batch_start in range(0, len(successful), 100):
        batch = successful[batch_start : batch_start + 100]
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
        upserted += len(points)
        logger.info("  Upserted %d/%d", upserted, len(successful))

    await qdrant.close()

    # Rewrite JSONL atomically (tmp file then rename)
    logger.info("Rewriting JSONL with complete embeddings…")
    id_to_embedding = {c["id"]: c["embedding"] for c in successful}
    tmp_path = JSONL_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            if chunk.get("embedding") is None and chunk["id"] in id_to_embedding:
                chunk["embedding"] = id_to_embedding[chunk["id"]]
            f.write(json.dumps(chunk) + "\n")
    tmp_path.replace(JSONL_PATH)

    info = await _qdrant_count(qdrant_path, qdrant_url)
    logger.info("=== Complete ===")
    logger.info("  Newly embedded:  %d", len(successful))
    logger.info("  Qdrant total:    %d points", info)
    logger.info("  JSONL updated:   %s", JSONL_PATH)


async def _embed_all(client, texts: list[str]) -> list[list[float] | None]:
    results: list[list[float] | None] = []
    for batch_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = [t.strip()[:6000] for t in texts[batch_start : batch_start + EMBEDDING_BATCH_SIZE]]
        try:
            resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            for item in resp.data:
                results.append(item.embedding)
            logger.info(
                "  Embedded batch %d/%d",
                batch_start // EMBEDDING_BATCH_SIZE + 1,
                (len(texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE,
            )
        except Exception as exc:
            logger.warning("Batch %d failed: %s", batch_start // EMBEDDING_BATCH_SIZE, exc)
            results.extend([None] * len(batch))
    return results


async def _qdrant_count(path: str, url: str) -> int:
    try:
        from qdrant_client import AsyncQdrantClient
        q = AsyncQdrantClient(path=path) if path else AsyncQdrantClient(url=url)
        info = await q.get_collection(QDRANT_COLLECTION)
        count = info.points_count or 0
        await q.close()
        return count
    except Exception:
        return -1


def _per_book_count(chunks: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for c in chunks:
        bk = c.get("book_key", "?")
        result[bk] = result.get(bk, 0) + 1
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Complete interrupted embedding run")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without embedding")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
