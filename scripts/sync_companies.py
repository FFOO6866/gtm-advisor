#!/usr/bin/env python3
"""Populate the listed_companies knowledge base.

Phase 1: SGX roster (all Singapore Exchange symbols + curated overseas SG cos)
Phase 2: S&P 500 roster (503 index members via EODHD index components)
Phase 3: S&P 500 financials (full fundamentals; ~8 min at 0.5s/company)
Phase 4: Vertical benchmarks (aggregate KPIs per industry vertical)

Usage:
    uv run python scripts/sync_companies.py [--phases 1,2,3,4] [--limit N]

    --phases  comma-separated list of phases to run (default: all)
    --limit   max companies for Phase 3 (default: 503, use 20 for quick test)
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import func, select  # noqa: E402

from packages.database.src.models import ListedCompany, MarketVertical  # noqa: E402
from packages.database.src.session import (  # noqa: E402
    async_session_factory,
    close_db,
    init_db,
)
from packages.integrations.eodhd.src.sync import FinancialIntelligenceSync  # noqa: E402


async def _count(table) -> int:
    async with async_session_factory() as db:
        return (await db.execute(select(func.count()).select_from(table))).scalar() or 0


async def phase1_sgx_roster() -> None:
    print("\n[Phase 1] Syncing SGX roster…")
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        counts = await sync.sync_exchange_roster("SG")
    total = await _count(ListedCompany)
    print(f"  SGX: created={counts['created']} updated={counts['updated']} skipped={counts['skipped']}")
    print(f"  listed_companies total: {total}")


async def phase2_sp500_roster() -> None:
    print("\n[Phase 2] Syncing S&P 500 roster…")
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        counts = await sync.sync_sp500_roster()
    total = await _count(ListedCompany)
    print(f"  S&P 500: created={counts['created']} updated={counts['updated']} skipped={counts['skipped']}")
    print(f"  listed_companies total: {total}")


async def phase3_sp500_financials(limit: int = 503) -> None:
    print(f"\n[Phase 3] Syncing S&P 500 financials (limit={limit})…")
    print(f"  Estimated time: ~{limit * 1:.0f}s at 0.5s/call × 2 calls/company")
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        counts = await sync.sync_sp500_financials(limit=limit)
    print(f"  synced={counts['synced']} failed={counts['failed']} skipped={counts['skipped']}")


async def phase4_benchmarks() -> None:
    print("\n[Phase 4] Computing vertical benchmarks…")
    async with async_session_factory() as db:
        verticals_result = await db.execute(select(MarketVertical))
        verticals = verticals_result.scalars().all()

    period_labels = ["2024", "2023", "2025-Q3", "2024-Q3"]
    ok = 0
    skip = 0

    for vertical in verticals:
        for period in period_labels:
            async with async_session_factory() as db:
                sync = FinancialIntelligenceSync(db)
                success = await sync.compute_and_store_benchmarks(vertical.slug, period)
                if success:
                    ok += 1
                else:
                    skip += 1

    print(f"  benchmarks computed={ok} skipped/insufficient={skip}")


async def phase5_assign_verticals() -> None:
    print("\n[Phase 5] Assigning verticals to companies with vertical_id=NULL…")
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        counts = await sync.assign_verticals_to_companies()
    print(f"  assigned={counts['assigned']} no_match={counts['no_match']}")


async def phase7_deactivate_stubs() -> None:
    print("\n[Phase 7] Deactivating stub/derived-security listings…")
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        counts = await sync.deactivate_stub_listings()
    print(f"  deactivated={counts['deactivated']} kept={counts['kept']}")


async def phase6_sgx_financials(limit: int = 700) -> None:
    print(f"\n[Phase 6] Syncing SGX financials (limit={limit})…")
    print(f"  Estimated time: ~{limit * 1:.0f}s at 0.5s/call × 2 calls/company")
    async with async_session_factory() as db:
        sync = FinancialIntelligenceSync(db)
        counts = await sync.sync_exchange_financials("SG", limit=limit)
    print(f"  synced={counts['synced']} failed={counts['failed']} skipped={counts['skipped']}")


def _install_signal_handlers() -> None:
    """Log SIGTERM / SIGINT so silent kills leave a trace in the log."""
    def _handler(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        print(f"\n[sync_companies] Received {sig_name} — exiting.", flush=True)
        sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


async def main(phases: list[int], limit: int) -> None:
    _install_signal_handlers()
    print("Initialising database…")
    await init_db()

    before = await _count(ListedCompany)
    print(f"  listed_companies at start: {before}")

    if 1 in phases:
        await phase1_sgx_roster()

    if 2 in phases:
        await phase2_sp500_roster()

    if 3 in phases:
        await phase3_sp500_financials(limit=limit)

    if 4 in phases:
        await phase4_benchmarks()

    if 5 in phases:
        await phase5_assign_verticals()

    if 6 in phases:
        await phase6_sgx_financials(limit=limit)

    if 7 in phases:
        await phase7_deactivate_stubs()

    after = await _count(ListedCompany)
    print(f"\nDone. listed_companies: {before} → {after}")

    await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phases",
        default="1,2,3,4",
        help="Comma-separated phases to run (default: 1,2,3,4). Phase 5: assign verticals",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=503,
        help="Max companies for Phase 3 (default: 503) and Phase 6 (default: 503, use 700 for all SGX)",
    )
    args = parser.parse_args()
    phases = [int(p.strip()) for p in args.phases.split(",")]
    asyncio.run(main(phases=phases, limit=args.limit))
