#!/usr/bin/env python3
"""Run VerticalIntelligenceAgent on marketing_comms vertical.

Two-step process:
1. VerticalIntelligenceSynthesizer — deterministic DB aggregation (no LLM)
   Creates/updates VerticalIntelligenceReport row with benchmarks, competitive
   dynamics, financial pulse, signal digest, executive movements.
2. VerticalIntelligenceAgent — LLM synthesis (GPT-4o)
   Consumes the pre-synthesized report + live Perplexity/NewsAPI data to produce
   a consulting-grade intelligence report.

Usage:
    uv run python scripts/run_vertical_intel_marketing_comms.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env before any imports that need API keys
from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def main() -> None:
    from packages.database.src.session import async_session_factory, close_db, init_db
    from packages.intelligence.src.vertical_synthesizer import VerticalIntelligenceSynthesizer

    await init_db()

    print("=" * 78)
    print("  Marketing/Comms Vertical Intelligence — Two-Step Pipeline")
    print("=" * 78)

    # ── Step 1: Deterministic synthesis ────────────────────────────────────
    print("\n[Step 1/2] Synthesizing VerticalIntelligenceReport (deterministic)...")
    t0 = time.time()

    try:
        async with async_session_factory() as db:
            synth = VerticalIntelligenceSynthesizer(db)
            report = await synth.synthesize_vertical("marketing_comms")
            if report is None:
                print("  ERROR: marketing_comms vertical not found or no data.")
                await close_db()
                return
            await db.commit()

            print(f"  Report ID: {report.id}")
            print(f"  Period: {report.report_period}")
            print(f"  Companies tracked: {(report.market_overview or {}).get('total_companies', '?')}")
            print(f"  Market cap total: SGD {(report.market_overview or {}).get('total_market_cap_sgd', 0):,.0f}")

            cd = report.competitive_dynamics or {}
            print(f"  Leaders: {len(cd.get('leaders', []))}")
            print(f"  Movers up: {len(cd.get('movers_up', []))}")
            print(f"  Movers down: {len(cd.get('movers_down', []))}")
            print(f"  GTM investors: {len(cd.get('gtm_investors', []))}")

            fp = report.financial_pulse or {}
            print(f"  SG&A median: {fp.get('sga_median', '?')}")
            print(f"  SG&A trend: {fp.get('sga_trend', '?')}")
            print(f"  Margin trend: {fp.get('margin_trend', '?')}")

            gi = report.gtm_implications or []
            print(f"  GTM implications: {len(gi)}")

            em = report.executive_movements or []
            print(f"  Executive movements: {len(em)}")

    except Exception as e:
        print(f"  ERROR in synthesis: {e}")
        import traceback
        traceback.print_exc()
        await close_db()
        return

    t1 = time.time()
    print(f"  Done in {t1 - t0:.1f}s")

    # ── Step 2: LLM agent synthesis ───────────────────────────────────────
    print("\n[Step 2/2] Running VerticalIntelligenceAgent (LLM synthesis)...")
    t2 = time.time()

    try:
        from agents.vertical_intelligence.src import VerticalIntelligenceAgent

        agent = VerticalIntelligenceAgent()
        result = await agent.run(
            task="Produce comprehensive vertical intelligence for the Marketing, Communications & Creative Agencies vertical in Singapore and globally",
            context={
                "vertical_slug": "marketing_comms",
                "industry": "advertising marketing communications creative agencies",
                "region": "Singapore",
            },
        )

        t3 = time.time()
        print(f"\n  Agent completed in {t3 - t2:.1f}s")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Data sources: {result.data_sources_used}")
        print(f"  Live data: {result.is_live_data}")
        print(f"  Drivers: {len(result.drivers)}")
        print(f"  Leaders: {len(result.leaders)}")
        print(f"  Challengers: {len(result.challengers)}")
        print(f"  GTM implications: {len(result.gtm_implications)}")
        print(f"  Trends: {len(result.trends)}")
        print(f"  Signals: {len(result.recent_signals)}")
        print(f"  Exec movements: {len(result.executive_movements)}")
        print(f"  Regulatory items: {len(result.regulatory_environment)}")
        print(f"  Benchmark periods: {len(result.benchmark_history)}")
        print(f"  Companies tracked: {result.total_companies_tracked}")
        print(f"  Market cap: SGD {result.total_market_cap_sgd:,.0f}")
        print(f"  Holding groups: {len(result.holding_group_map)}")
        print(f"  SG agencies: {len(result.sg_agency_landscape)}")
        print(f"  Award winners: {len(result.award_leaderboard)}")
        print(f"  Service lines: {len(result.service_line_distribution)}")

        # Save output
        output_dir = project_root / "data" / "intel" / "marketing_comms"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "_vertical_intelligence_report.json"
        output_path.write_text(json.dumps(result.model_dump(), indent=2, default=str))
        print(f"\n  Report saved: {output_path}")

        # Print executive summary
        print("\n" + "=" * 78)
        print("  EXECUTIVE SUMMARY")
        print("=" * 78)
        print(result.executive_summary)

        # Print drivers
        print("\n" + "-" * 78)
        print("  KEY DRIVERS")
        print("-" * 78)
        for i, d in enumerate(result.drivers, 1):
            arrow = "↑" if d.direction == "tailwind" else "↓"
            print(f"  {i}. {arrow} [{d.magnitude}] {d.name}")
            print(f"     {d.description[:120]}...")
            print(f"     GTM: {d.gtm_implication[:120]}...")
            print()

        # Print GTM implications
        print("-" * 78)
        print("  GTM IMPLICATIONS")
        print("-" * 78)
        for i, g in enumerate(result.gtm_implications, 1):
            print(f"  {i}. [{g.get('priority', '?').upper()}] {g.get('insight', '')[:120]}")
            print(f"     Action: {g.get('recommended_action', '')[:120]}")
            print()

    except Exception as e:
        print(f"  ERROR in agent: {e}")
        import traceback
        traceback.print_exc()

    await close_db()

    total = time.time() - t0
    print("=" * 78)
    print(f"  Total pipeline: {total:.1f}s ({total/60:.1f} min)")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
