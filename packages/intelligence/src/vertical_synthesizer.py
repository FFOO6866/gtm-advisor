"""Vertical Intelligence Synthesizer — aggregates market data into per-vertical reports.

Deterministic aggregation (no LLM) that combines:
- VerticalBenchmark financial distributions
- MarketArticle signal classification
- CompanyFinancialSnapshot operational trends (SG&A, R&D)
- CompanyExecutive movements
- Listed company metrics (leaders, laggards, movers)

Output: VerticalIntelligenceReport rows consumed by agents via MCP.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    CompanyExecutive,
    CompanyFinancialSnapshot,
    FinancialPeriodType,
    ListedCompany,
    MarketArticle,
    MarketVertical,
    SgKnowledgeArticle,
    VerticalBenchmark,
    VerticalIntelligenceReport,
)

logger = logging.getLogger(__name__)

# Regex strips suffixes like "Inc.", "Ltd", "Pte", "Class A/C", etc.
_NAME_STRIP_RE = re.compile(
    r"\s*(Inc\.?|Ltd\.?|Pte\.?|Corp\.?|Group|Holdings?|Class\s+[A-Z])\s*",
    re.IGNORECASE,
)

# Vertical-slug → keyword sets for matching SG regulatory articles.
# Verticals not listed get only generic (compliance / grant) articles.
_VERTICAL_REGULATORY_KEYWORDS: dict[str, list[str]] = {
    "fintech": ["mas", "monetary authority", "payment services", "digital payment", "financial"],
    "healthcare": ["hsa", "health sciences", "healthcare", "medical device"],
    "reits": ["reit", "real estate", "property"],
    "maritime": ["mpa", "maritime", "shipping"],
    "telecommunications": ["imda", "telecom", "spectrum"],
    "marketing_comms": [
        "advertising", "marketing", "pdpa", "personal data", "data protection",
        "digital advertising", "spam", "influencer", "endorsement", "asas",
        "imda", "media development", "content regulation",
    ],
}

_INTEL_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "intel"

# Private SG agency segment classification
_PRIVATE_SEGMENTS: dict[str, dict[str, str]] = {
    "marketing_comms": {
        # Full-service / holding group SG operations
        "OGILVY-SG": "independent_creative", "BBDO-SG": "independent_creative",
        "DDB-SG": "independent_creative", "TBWA-SG": "independent_creative",
        "MCCANN-SG": "independent_creative", "SAATCHI-SG": "independent_creative",
        "LEO-SG": "independent_creative", "DENTSU-SG": "independent_creative",
        "ANOMALY-SG": "independent_creative", "FORSMAN-SG": "independent_creative",
        "BLKJ-HAVAS": "independent_creative", "MONKS-SG": "independent_creative",
        "TSLA-SG": "independent_creative", "GOODSTUPH": "independent_creative",
        "FISHERMEN-SG": "independent_creative", "EIGHT-SG": "independent_creative",
        "DSTNCT": "independent_creative", "GOVT-VCCP": "independent_creative",
        # PR & Communications
        "EDELMAN-SG": "pr_comms", "WEBER-SG": "pr_comms", "FLEISHMAN-SG": "pr_comms",
        "GOLIN-SG": "pr_comms", "BRUNSWICK-SG": "pr_comms", "APRW": "pr_comms",
        "RUDER-FINN-SG": "pr_comms", "PRECIOUS-SG": "pr_comms", "REDHILL-SG": "pr_comms",
        "TATEANZUR": "pr_comms", "MUTANT-SG": "pr_comms", "BURSON-SG": "pr_comms",
        "HOFFMAN-SG": "pr_comms", "WACHSMAN-SG": "pr_comms", "FTI-SG": "pr_comms",
        "FINN-SG": "pr_comms", "ARCHETYPE-SG": "pr_comms", "RICE-FINN": "pr_comms",
        # Media / Outdoor
        "OMD-SG": "media", "PHD-SG": "media", "CARAT-SG": "media",
        "STARCOM-SG": "media", "ZENITH-SG": "media", "ASSEMBLY-SG": "media",
        "GROUPM-SG": "media", "VML-SG": "media", "IPROSPECT-SG": "media",
        "JCDECAUX-SG": "outdoor_ooh", "MOOVE-SG": "outdoor_ooh",
        "SPHMEDIA-SG": "outdoor_ooh", "MEDIACORP-SG": "outdoor_ooh",
        # Research / Measurement
        "KANTAR-SG": "media", "NIELSEN-SG": "media", "IPSOS-SG": "media",
        "MELTWATER-SG": "media",
        # Digital / Performance
        "HEROES-SG": "digital_performance", "FIRSTPAGE": "digital_performance",
        "OOM-SG": "digital_performance", "STALLIONS": "digital_performance",
        "CLICKR": "digital_performance", "HASHMETA": "digital_performance",
        "IMPOSSIBLE-MKT": "digital_performance", "DIGITALNOMADS": "digital_performance",
        "MASHWIRE": "digital_performance", "DEPT-SG": "digital_performance",
        "RGA-SG": "digital_performance", "SAPIENT-SG": "digital_performance",
        "SONG-SG": "digital_performance",
        # Experiential / events
        "PICO-SG": "experiential", "UNIPLAN-SG": "experiential",
        "KINGSMEN-SG": "experiential", "JACKMORTON-SG": "experiential",
        # Influencer / creator
        "GUSHCLOUD": "influencer_creator", "HEPMIL": "influencer_creator",
        "NUFFNANG": "influencer_creator", "KOBE-GLOBAL": "influencer_creator",
        # Social-first
        "WEARESOCIAL-SG": "social_first", "VAYNER-SG": "social_first",
        "VIRTUE-ASIA": "social_first",
        # Consulting-agency hybrids
        "DELOITTE-DIGITAL-SG": "digital_performance", "PWC-DIGITAL-SG": "digital_performance",
        # Full-service / holding group SG ops
        "CHEIL-SG": "creative", "MINDSHARE-SG": "media",
        "SERVICEPLAN-SG": "creative", "BLUEFOCUS-SG": "digital_performance",
        "WK-SG": "independent_creative",
    },
}

# Holding group ownership map — SG agency ticker → parent group
_HOLDING_GROUP_MAP: dict[str, dict[str, str]] = {
    "marketing_comms": {
        # WPP subsidiaries
        "OGILVY-SG": "WPP", "GROUPM-SG": "WPP", "VML-SG": "WPP",
        "BURSON-SG": "WPP", "KANTAR-SG": "WPP", "MINDSHARE-SG": "WPP",
        # Omnicom (incl. IPG post-merger)
        "BBDO-SG": "Omnicom", "DDB-SG": "Omnicom", "PHD-SG": "Omnicom",
        "OMD-SG": "Omnicom", "TBWA-SG": "Omnicom", "FLEISHMAN-SG": "Omnicom",
        "MCCANN-SG": "Omnicom", "GOLIN-SG": "Omnicom", "WEBER-SG": "Omnicom",
        "JACKMORTON-SG": "Omnicom", "RGA-SG": "Omnicom",
        # Publicis Groupe
        "SAATCHI-SG": "Publicis", "LEO-SG": "Publicis", "STARCOM-SG": "Publicis",
        "ZENITH-SG": "Publicis", "SAPIENT-SG": "Publicis", "HEPMIL": "Publicis",
        # Dentsu
        "DENTSU-SG": "Dentsu", "CARAT-SG": "Dentsu", "IPROSPECT-SG": "Dentsu",
        # Havas / Vivendi
        "BLKJ-HAVAS": "Havas",
        # Stagwell
        "ASSEMBLY-SG": "Stagwell", "ANOMALY-SG": "Stagwell",
        "FORSMAN-SG": "Stagwell", "FINN-SG": "Stagwell", "RICE-FINN": "Stagwell",
        # Accenture Song
        "SONG-SG": "Accenture Song",
        # S4 Capital / Monks
        "MONKS-SG": "S4 Capital",
        # Cheil Worldwide (Samsung)
        "CHEIL-SG": "Cheil Worldwide",
        # Next Fifteen Group
        "ARCHETYPE-SG": "Next Fifteen",
        # BlueFocus (China — owns We Are Social)
        "WEARESOCIAL-SG": "BlueFocus", "BLUEFOCUS-SG": "BlueFocus",
        # Deloitte / PwC (consulting-agency hybrids)
        "DELOITTE-DIGITAL-SG": "Deloitte", "PWC-DIGITAL-SG": "PwC",
        # Serviceplan (Germany's largest independent)
        "SERVICEPLAN-SG": "Serviceplan",
        # Other corporate parents
        "DEPT-SG": "DEPT (Carlyle)", "GOVT-VCCP": "VCCP",
        "MEDIACORP-SG": "Mediacorp (SG Gov)", "SPHMEDIA-SG": "SPH Media",
        "MOOVE-SG": "ComfortDelGro", "PICO-SG": "Pico Holdings (HK)",
        "VIRTUE-ASIA": "VICE Media", "WILD-SG": "Prap Japan",
        # Listed company tickers → their holding group
        "OMC": "Omnicom", "IPG": "Omnicom", "WPP": "WPP",
        "PUB": "Publicis", "STGW": "Stagwell", "SFOR": "S4 Capital",
        "ACN": "Accenture Song", "SAA": "M&C Saatchi", "ADV": "Advantage Solutions",
        "030000": "Cheil", "214320": "Innocean (Hyundai)",
        "0752": "Pico Holdings (HK)", "HAVAS": "Havas",
        "VIV": "Vivendi/Havas", "DEC": "JCDecaux",
    },
}

_SEGMENT_LABELS: dict[str, str] = {
    "holding_group": "Holding Groups",
    "outdoor_ooh": "Outdoor / OOH",
    "independent_creative": "Independent Creative",
    "creative": "Creative Agencies",
    "media": "Media Agencies",
    "pr_comms": "PR & Communications",
    "digital_performance": "Digital / Performance",
    "experiential": "Experiential / Events",
    "influencer_creator": "Influencer / Creator Economy",
    "social_first": "Social-First Agencies",
    "general": "General",
}


def _normalise_company_name(name: str) -> str:
    """Normalise company name for dedup (e.g. 'Alphabet Inc. Class A' → 'alphabet')."""
    return _NAME_STRIP_RE.sub("", name).strip().lower()


class VerticalIntelligenceSynthesizer:
    """Synthesizes per-vertical intelligence reports from accumulated data.

    All methods are deterministic — no LLM calls. Designed to run weekly
    via the scheduler.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def synthesize_vertical(self, vertical_slug: str) -> VerticalIntelligenceReport | None:
        """Synthesize a full intelligence report for the given vertical.

        Returns the created VerticalIntelligenceReport, or None if the
        vertical doesn't exist or has insufficient data.
        """
        # Fetch vertical
        vert_result = await self._session.execute(
            select(MarketVertical).where(MarketVertical.slug == vertical_slug)
        )
        vertical: MarketVertical | None = vert_result.scalar_one_or_none()
        if vertical is None:
            logger.warning("vertical_synth.no_vertical", slug=vertical_slug)
            return None

        # Compute period label (ISO week)
        now = datetime.now(UTC)
        report_period = now.strftime("%G-W%V")

        # Gather data in parallel-safe sequential calls
        market_overview = await self._build_market_overview(vertical)
        key_trends = await self._build_key_trends(vertical)
        competitive_dynamics = await self._build_competitive_dynamics(vertical)
        financial_pulse = await self._build_financial_pulse(vertical)
        signal_digest = await self._build_signal_digest(vertical)
        executive_movements = await self._build_executive_movements(vertical)
        regulatory_environment = await self._build_regulatory_environment(vertical)

        # Enrich competitive dynamics with SG private agency data from dossiers
        sg_agency_landscape = self._build_sg_agency_landscape(vertical.slug)
        if sg_agency_landscape:
            competitive_dynamics["sg_agency_landscape"] = sg_agency_landscape
            # Add segment breakdown
            seg_counts: dict[str, int] = {}
            for a in sg_agency_landscape:
                seg = a.get("segment", "general")
                seg_counts[seg] = seg_counts.get(seg, 0) + 1
            competitive_dynamics["segment_breakdown"] = seg_counts
            competitive_dynamics["excluded_count"] = 0

            # Holding group consolidation
            holding_groups: dict[str, dict] = {}
            for a in sg_agency_landscape:
                pg = a.get("parent_group", "Independent")
                if pg not in holding_groups:
                    holding_groups[pg] = {"agencies": [], "subsidiary_count": 0}
                holding_groups[pg]["agencies"].append(a.get("name", "?"))
                holding_groups[pg]["subsidiary_count"] += 1
            competitive_dynamics["holding_group_map"] = holding_groups

            # Award leaderboard
            award_leaders = sorted(
                [
                    {
                        "name": a["name"],
                        "awards": a.get("awards_won", []),
                        "parent_group": a.get("parent_group", "Independent"),
                    }
                    for a in sg_agency_landscape
                    if a.get("awards_won")
                ],
                key=lambda x: len(x["awards"]),
                reverse=True,
            )
            competitive_dynamics["award_leaderboard"] = award_leaders[:20]

            # Service line matrix
            svc_matrix: dict[str, dict] = {}
            for a in sg_agency_landscape:
                for svc in a.get("service_lines", []):
                    if svc not in svc_matrix:
                        svc_matrix[svc] = {"count": 0, "agencies": []}
                    svc_matrix[svc]["count"] += 1
                    if len(svc_matrix[svc]["agencies"]) < 10:
                        svc_matrix[svc]["agencies"].append(a.get("name", "?"))
            competitive_dynamics["service_line_matrix"] = dict(
                sorted(svc_matrix.items(), key=lambda x: x[1]["count"], reverse=True)
            )

            # SG market pulse
            hiring_count = sum(1 for a in sg_agency_landscape if a.get("hiring_openings", 0) > 0)
            total_openings = sum(a.get("hiring_openings", 0) for a in sg_agency_landscape)
            award_count = sum(1 for a in sg_agency_landscape if a.get("has_major_awards"))
            competitive_dynamics["sg_market_pulse"] = {
                "hiring_velocity": {
                    "agencies_hiring": hiring_count,
                    "total_openings": total_openings,
                    "signal": (
                        "strong_growth"
                        if hiring_count > len(sg_agency_landscape) * 0.5
                        else "moderate_growth"
                    ),
                },
                "award_density": {
                    "award_winning_agencies": award_count,
                    "pct_with_major_awards": round(
                        award_count / max(len(sg_agency_landscape), 1) * 100, 1
                    ),
                    "signal": "established" if award_count > 10 else "emerging",
                },
            }

        # Merge dossier-based signals and exec movements
        dossier_signals = self._extract_dossier_signals(vertical.slug)
        if dossier_signals:
            seen_headlines = {s.get("headline", "").lower()[:100] for s in signal_digest}
            for ds in dossier_signals:
                key = ds.get("headline", "").lower()[:100]
                if key and key not in seen_headlines:
                    signal_digest.append(ds)
                    seen_headlines.add(key)
            signal_digest = signal_digest[:15]

        dossier_movements = self._extract_dossier_exec_movements(vertical.slug)
        if dossier_movements:
            seen_companies = {m.get("company", "").lower() for m in executive_movements}
            for dm in dossier_movements:
                key = dm.get("company", "").lower()
                if key and key not in seen_companies:
                    executive_movements.append(dm)
                    seen_companies.add(key)

        gtm_implications = self._derive_gtm_implications(
            market_overview, competitive_dynamics, financial_pulse, key_trends
        )

        # Count data sources
        data_sources = {
            "articles_analyzed": len(key_trends),
            "companies_tracked": market_overview.get("total_companies", 0),
            "benchmarks_used": 1 if market_overview.get("benchmark_period") else 0,
            "signals_processed": len(signal_digest),
            "executive_movements_tracked": len(executive_movements),
            "regulatory_items": len(regulatory_environment),
        }
        if sg_agency_landscape:
            data_sources["sg_agencies_profiled"] = len(sg_agency_landscape)

        # Mark previous reports as not current
        await self._session.execute(
            VerticalIntelligenceReport.__table__.update()
            .where(
                VerticalIntelligenceReport.vertical_id == vertical.id,
                VerticalIntelligenceReport.is_current.is_(True),
            )
            .values(is_current=False)
        )

        # Create new report
        report = VerticalIntelligenceReport(
            id=uuid.uuid4(),
            vertical_id=vertical.id,
            report_period=report_period,
            is_current=True,
            market_overview=market_overview,
            key_trends=key_trends,
            competitive_dynamics=competitive_dynamics,
            financial_pulse=financial_pulse,
            signal_digest=signal_digest,
            executive_movements=executive_movements,
            regulatory_environment=regulatory_environment,
            gtm_implications=gtm_implications,
            data_sources=data_sources,
            computed_at=now,
        )
        self._session.add(report)
        await self._session.flush()

        logger.info(
            "vertical_synth.ok",
            slug=vertical_slug,
            period=report_period,
            companies=market_overview.get("total_companies", 0),
            trends=len(key_trends),
            signals=len(signal_digest),
        )
        return report

    async def synthesize_all(self) -> int:
        """Synthesize reports for all verticals. Returns count of reports created."""
        result = await self._session.execute(select(MarketVertical))
        verticals = list(result.scalars().all())
        count = 0
        for v in verticals:
            report = await self.synthesize_vertical(v.slug)
            if report is not None:
                count += 1
        await self._session.commit()
        logger.info("vertical_synth.all_done", count=count, total=len(verticals))
        return count

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    async def _build_market_overview(self, vertical: MarketVertical) -> dict[str, Any]:
        """Aggregate company count, market cap, and benchmark highlights."""
        # Active companies in this vertical
        co_stmt = select(
            func.count(ListedCompany.id),
            func.sum(ListedCompany.market_cap_sgd),
        ).where(
            ListedCompany.vertical_id == vertical.id,
            ListedCompany.is_active.is_(True),
        )
        co_result = await self._session.execute(co_stmt)
        row = co_result.one()
        total_companies = row[0] or 0
        total_market_cap = row[1] or 0

        # Latest benchmark
        bm_stmt = (
            select(VerticalBenchmark)
            .where(
                VerticalBenchmark.vertical_id == vertical.id,
                VerticalBenchmark.period_type == FinancialPeriodType.ANNUAL,
            )
            .order_by(desc(VerticalBenchmark.computed_at))
            .limit(1)
        )
        bm: VerticalBenchmark | None = await self._session.scalar(bm_stmt)

        benchmark_highlights: dict[str, Any] = {}
        benchmark_period = None
        if bm is not None:
            benchmark_period = bm.period_label
            rev_growth = bm.revenue_growth_yoy or {}
            gross_m = bm.gross_margin or {}
            sga = bm.sga_to_revenue or {}
            rnd = bm.rnd_to_revenue or {}
            benchmark_highlights = {
                "revenue_growth_median": rev_growth.get("p50"),
                "gross_margin_median": gross_m.get("p50"),
                "sga_to_revenue_median": sga.get("p50"),
                "rnd_to_revenue_median": rnd.get("p50"),
                "company_count_in_benchmark": bm.company_count,
            }

        return {
            "vertical_name": vertical.name,
            "vertical_slug": vertical.slug,
            "total_companies": total_companies,
            "total_market_cap_sgd": total_market_cap,
            "benchmark_period": benchmark_period,
            "benchmark_highlights": benchmark_highlights,
        }

    async def _build_key_trends(self, vertical: MarketVertical) -> list[dict[str, Any]]:
        """Extract key trends from recent articles classified to this vertical."""
        cutoff = datetime.now(UTC) - timedelta(days=30)
        articles_stmt = (
            select(MarketArticle)
            .where(
                MarketArticle.vertical_slug == vertical.slug,
                MarketArticle.published_at >= cutoff,
            )
            .order_by(desc(MarketArticle.published_at))
            .limit(50)
        )
        result = await self._session.execute(articles_stmt)
        articles: list[MarketArticle] = list(result.scalars().all())

        if not articles:
            return []

        # Group by signal_type and count
        type_counts: dict[str, list[str]] = {}
        for article in articles:
            signal_type = article.signal_type or "general"
            type_counts.setdefault(signal_type, []).append(article.title)

        trends: list[dict[str, Any]] = []
        for signal_type, titles in sorted(type_counts.items(), key=lambda x: -len(x[1])):
            trends.append({
                "trend": signal_type,
                "evidence": titles[:3],  # Top 3 article titles as evidence
                "source_count": len(titles),
                "impact": "high" if len(titles) >= 5 else "medium" if len(titles) >= 2 else "low",
            })

        return trends[:10]  # Top 10 trends

    async def _build_competitive_dynamics(self, vertical: MarketVertical) -> dict[str, Any]:
        """Identify leaders, challengers, and movers in the vertical."""
        # Get companies with latest annual snapshots
        stmt = (
            select(ListedCompany, CompanyFinancialSnapshot)
            .join(
                CompanyFinancialSnapshot,
                CompanyFinancialSnapshot.company_id == ListedCompany.id,
            )
            .where(
                ListedCompany.vertical_id == vertical.id,
                ListedCompany.is_active.is_(True),
                CompanyFinancialSnapshot.period_type == FinancialPeriodType.ANNUAL,
            )
            .order_by(desc(CompanyFinancialSnapshot.period_end_date))
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        # Deduplicate: keep only latest snapshot per company.
        # Also dedup by normalised name to collapse dual-class listings
        # (e.g. Alphabet Class A / Class C → keep largest by market cap).
        seen: set[uuid.UUID] = set()
        seen_names: dict[str, int] = {}  # normalised name → index in companies
        companies: list[tuple[ListedCompany, CompanyFinancialSnapshot]] = []
        for lc, snap in rows:
            if lc.id in seen:
                continue
            seen.add(lc.id)
            norm = _normalise_company_name(lc.name)
            if norm in seen_names:
                # Keep whichever has the larger market cap
                idx = seen_names[norm]
                existing_cap = companies[idx][0].market_cap_sgd or 0
                new_cap = lc.market_cap_sgd or 0
                if new_cap > existing_cap:
                    companies[idx] = (lc, snap)
            else:
                seen_names[norm] = len(companies)
                companies.append((lc, snap))

        if not companies:
            return {}

        # Leaders by market cap
        by_market_cap = sorted(
            companies,
            key=lambda x: x[0].market_cap_sgd or 0,
            reverse=True,
        )
        leaders = [
            {
                "ticker": lc.ticker,
                "name": lc.name,
                "market_cap_sgd": lc.market_cap_sgd,
                "revenue_growth_yoy": snap.revenue_growth_yoy,
            }
            for lc, snap in by_market_cap[:5]
        ]

        # Fastest growers — filter to companies with meaningful revenue (>$10M SGD)
        with_growth = [
            (lc, snap) for lc, snap in companies
            if snap.revenue_growth_yoy is not None
            and snap.revenue is not None
            and snap.revenue > 10_000_000
            and -0.9 < snap.revenue_growth_yoy < 5.0  # same outlier bounds as benchmark engine
        ]
        by_growth = sorted(with_growth, key=lambda x: x[1].revenue_growth_yoy, reverse=True)  # type: ignore[arg-type]
        movers_up = [
            {
                "ticker": lc.ticker,
                "name": lc.name,
                "revenue_growth_yoy": snap.revenue_growth_yoy,
                "sga_to_revenue": snap.sga_to_revenue,
            }
            for lc, snap in by_growth[:5]
        ]
        movers_down = [
            {
                "ticker": lc.ticker,
                "name": lc.name,
                "revenue_growth_yoy": snap.revenue_growth_yoy,
            }
            for lc, snap in by_growth[-5:][::-1]
        ]

        # Top SG&A spenders (GTM investment leaders)
        # Filter: revenue > $10M SGD and SG&A ratio in 0–100% range
        with_sga = [
            (lc, snap) for lc, snap in companies
            if snap.sga_to_revenue is not None
            and 0 < snap.sga_to_revenue < 1.0
            and snap.revenue is not None
            and snap.revenue > 10_000_000
        ]
        top_sga = sorted(with_sga, key=lambda x: x[1].sga_to_revenue, reverse=True)  # type: ignore[arg-type]
        gtm_investors = [
            {
                "ticker": lc.ticker,
                "name": lc.name,
                "sga_to_revenue": snap.sga_to_revenue,
                "rnd_to_revenue": snap.rnd_to_revenue,
            }
            for lc, snap in top_sga[:5]
        ]

        return {
            "leaders": leaders,
            "movers_up": movers_up,
            "movers_down": movers_down,
            "gtm_investors": gtm_investors,
            "total_tracked": len(companies),
        }

    async def _build_financial_pulse(self, vertical: MarketVertical) -> dict[str, Any]:
        """Compute SG&A/R&D trends and margin dynamics for the vertical."""
        # Get two most recent annual benchmarks for trend comparison
        bm_stmt = (
            select(VerticalBenchmark)
            .where(
                VerticalBenchmark.vertical_id == vertical.id,
                VerticalBenchmark.period_type == FinancialPeriodType.ANNUAL,
            )
            .order_by(desc(VerticalBenchmark.period_label))
            .limit(2)
        )
        bm_result = await self._session.execute(bm_stmt)
        benchmarks: list[VerticalBenchmark] = list(bm_result.scalars().all())

        if not benchmarks:
            return {}

        latest = benchmarks[0]
        sga_data = latest.sga_to_revenue or {}
        rnd_data = latest.rnd_to_revenue or {}
        opm_data = getattr(latest, "operating_margin_dist", None) or {}
        gross_data = latest.gross_margin or {}

        pulse: dict[str, Any] = {
            "period": latest.period_label,
            "sga_median": sga_data.get("p50"),
            "sga_p75": sga_data.get("p75"),
            "sga_sample": sga_data.get("n", 0),
            "rnd_median": rnd_data.get("p50"),
            "rnd_p75": rnd_data.get("p75"),
            "rnd_sample": rnd_data.get("n", 0),
            "operating_margin_median": opm_data.get("p50"),
            "gross_margin_median": gross_data.get("p50"),
        }

        # Trend comparison with previous year
        if len(benchmarks) >= 2:
            prev = benchmarks[1]
            prev_sga = (prev.sga_to_revenue or {}).get("p50")
            prev_opm = (getattr(prev, "operating_margin_dist", None) or {}).get("p50")
            curr_sga = sga_data.get("p50")
            curr_opm = opm_data.get("p50")

            if curr_sga is not None and prev_sga is not None and prev_sga > 0:
                pulse["sga_trend_pct"] = (curr_sga - prev_sga) / prev_sga
                pulse["sga_trend"] = "increasing" if curr_sga > prev_sga else "decreasing"
            if curr_opm is not None and prev_opm is not None:
                pulse["margin_trend"] = "expanding" if curr_opm > prev_opm else "compressing"

            # Revenue growth trend
            curr_rg = (latest.revenue_growth_yoy or {}).get("p50")
            prev_rg = (prev.revenue_growth_yoy or {}).get("p50")
            if curr_rg is not None and prev_rg is not None:
                rg_delta = curr_rg - prev_rg
                pulse["revenue_growth_median"] = curr_rg
                pulse["revenue_growth_prev"] = prev_rg
                if abs(rg_delta) < 0.02:
                    pulse["revenue_growth_trend"] = "stable"
                else:
                    pulse["revenue_growth_trend"] = "accelerating" if rg_delta > 0 else "decelerating"

        return pulse

    async def _build_signal_digest(self, vertical: MarketVertical) -> list[dict[str, Any]]:
        """Extract the 10 most recent high-impact signals for this vertical."""
        cutoff = datetime.now(UTC) - timedelta(days=14)
        stmt = (
            select(MarketArticle)
            .where(
                MarketArticle.vertical_slug == vertical.slug,
                MarketArticle.published_at >= cutoff,
                MarketArticle.signal_type.isnot(None),
            )
            .order_by(desc(MarketArticle.published_at))
            .limit(10)
        )
        result = await self._session.execute(stmt)
        articles: list[MarketArticle] = list(result.scalars().all())

        return [
            {
                "headline": a.title,
                "signal_type": a.signal_type,
                "source": a.source_name,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "sentiment": a.sentiment,
            }
            for a in articles
        ]

    async def _build_executive_movements(self, vertical: MarketVertical) -> list[dict[str, Any]]:
        """Find recent executive changes in the vertical's companies."""
        # Get companies in this vertical
        co_ids_stmt = (
            select(ListedCompany.id, ListedCompany.name)
            .where(
                ListedCompany.vertical_id == vertical.id,
                ListedCompany.is_active.is_(True),
            )
        )
        co_result = await self._session.execute(co_ids_stmt)
        company_map = {row[0]: row[1] for row in co_result.all()}

        if not company_map:
            return []

        # Find executives with recent changes (added in last 90 days — proxy for new appointments)
        cutoff = datetime.now(UTC) - timedelta(days=90)
        exec_stmt = (
            select(CompanyExecutive)
            .where(
                CompanyExecutive.listed_company_id.in_(list(company_map.keys())),
                CompanyExecutive.is_active.is_(True),
            )
            .order_by(desc(CompanyExecutive.since_date))
            .limit(20)
        )
        exec_result = await self._session.execute(exec_stmt)
        executives: list[CompanyExecutive] = list(exec_result.scalars().all())

        # Filter to recent appointments
        movements: list[dict[str, Any]] = []
        for ex in executives:
            if ex.since_date and str(ex.since_date) >= cutoff.strftime("%Y"):
                company_name = company_map.get(ex.listed_company_id, "Unknown")
                role = "CEO" if ex.is_ceo else "CFO" if ex.is_cfo else "Chair" if ex.is_chair else "Executive"
                movements.append({
                    "company": company_name,
                    "name": ex.name,
                    "title": ex.title,
                    "role_type": role,
                    "since": str(ex.since_date) if ex.since_date else None,
                })

        return movements[:10]

    async def _build_regulatory_environment(self, vertical: MarketVertical) -> list[dict[str, Any]]:
        """Pull relevant SG regulatory/grant articles for this vertical."""
        # Always include generic categories relevant to all verticals
        generic_types = ("compliance", "enforcement", "grant", "grant_overview", "psg_overview")
        stmt = (
            select(SgKnowledgeArticle)
            .where(
                SgKnowledgeArticle.is_active.is_(True),
                SgKnowledgeArticle.category_type.in_(generic_types),
            )
            .order_by(desc(SgKnowledgeArticle.fetched_at))
            .limit(20)
        )
        result = await self._session.execute(stmt)
        articles: list[SgKnowledgeArticle] = list(result.scalars().all())

        # For verticals with specific regulatory keywords, also pull
        # regulation-type articles whose title/summary match.
        vertical_kws = _VERTICAL_REGULATORY_KEYWORDS.get(vertical.slug, [])
        if vertical_kws:
            reg_stmt = (
                select(SgKnowledgeArticle)
                .where(
                    SgKnowledgeArticle.is_active.is_(True),
                    SgKnowledgeArticle.category_type == "regulation",
                )
                .order_by(desc(SgKnowledgeArticle.fetched_at))
                .limit(30)
            )
            reg_result = await self._session.execute(reg_stmt)
            for art in reg_result.scalars().all():
                text = (art.title + " " + (art.summary or "")).lower()
                if any(kw in text for kw in vertical_kws):
                    articles.append(art)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[SgKnowledgeArticle] = []
        for a in articles:
            if a.url not in seen_urls:
                seen_urls.add(a.url)
                unique.append(a)

        return [
            {
                "title": a.title,
                "category": a.category_type,
                "source": a.source,
                "summary": a.summary[:300] if a.summary else None,
                "effective_date": a.effective_date,
                "url": a.url,
            }
            for a in unique[:10]
        ]

    def _derive_gtm_implications(
        self,
        market_overview: dict,
        competitive_dynamics: dict,
        financial_pulse: dict,
        key_trends: list[dict],  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Derive actionable GTM implications from aggregated data."""
        implications: list[dict[str, Any]] = []

        # SG&A intensity signals
        sga_median = financial_pulse.get("sga_median")
        if sga_median is not None:
            if sga_median > 0.30:
                implications.append({
                    "insight": f"High industry SG&A spend ({sga_median:.0%} median) — companies are investing heavily in GTM.",
                    "evidence": "Vertical benchmark SG&A distribution",
                    "recommended_action": "Position efficiency-focused solutions; ROI messaging resonates.",
                    "priority": "high",
                })
            elif sga_median < 0.10:
                implications.append({
                    "insight": f"Low industry SG&A ({sga_median:.0%} median) — lean operations, cost-sensitive buyers.",
                    "evidence": "Vertical benchmark SG&A distribution",
                    "recommended_action": "Lead with cost savings and quick wins; long enterprise sales cycles unlikely.",
                    "priority": "medium",
                })

        # SG&A trend signals
        sga_trend = financial_pulse.get("sga_trend")
        if sga_trend == "increasing":
            implications.append({
                "insight": "Industry SG&A spend is accelerating YoY — companies are investing in growth.",
                "evidence": f"SG&A median change: {financial_pulse.get('sga_trend_pct', 0):.0%}",
                "recommended_action": "Good timing for GTM tooling — budgets are expanding.",
                "priority": "high",
            })
        elif sga_trend == "decreasing":
            implications.append({
                "insight": "Industry SG&A spend is contracting YoY — cost optimization cycle.",
                "evidence": f"SG&A median change: {financial_pulse.get('sga_trend_pct', 0):.0%}",
                "recommended_action": "Position as cost reduction tool; emphasize payback period.",
                "priority": "medium",
            })

        # Margin dynamics
        margin_trend = financial_pulse.get("margin_trend")
        if margin_trend == "compressing":
            implications.append({
                "insight": "Operating margins compressing across the vertical.",
                "evidence": "YoY operating margin benchmark comparison",
                "recommended_action": "Prospects likely open to efficiency tools; margin pressure creates urgency.",
                "priority": "high",
            })

        # R&D intensity
        rnd_median = financial_pulse.get("rnd_median")
        if rnd_median is not None and rnd_median > 0.10:
            implications.append({
                "insight": f"R&D-intensive vertical ({rnd_median:.0%} median) — product innovation is table stakes.",
                "evidence": "Vertical benchmark R&D distribution",
                "recommended_action": "Lead with technical depth; decision-makers are likely engineers/PMs.",
                "priority": "medium",
            })

        # Growth momentum
        growth_median = (market_overview.get("benchmark_highlights") or {}).get("revenue_growth_median")
        if growth_median is not None:
            if growth_median > 0.15:
                implications.append({
                    "insight": f"High-growth vertical ({growth_median:.0%} median revenue growth).",
                    "evidence": "Vertical benchmark revenue growth distribution",
                    "recommended_action": "Companies scaling fast — they need tools that scale with them.",
                    "priority": "medium",
                })
            elif growth_median < 0:
                implications.append({
                    "insight": f"Vertical revenue declining ({growth_median:.0%} median) — consolidation likely.",
                    "evidence": "Vertical benchmark revenue growth distribution",
                    "recommended_action": "Focus on market share capture messaging; cost optimization resonates.",
                    "priority": "high",
                })

        # Fast movers as social proof
        movers = competitive_dynamics.get("movers_up", [])
        if movers:
            top_mover = movers[0]
            sga = top_mover.get("sga_to_revenue")
            if sga is not None and 0.20 < sga < 1.0:
                implications.append({
                    "insight": f"Fastest grower ({top_mover['name']}) has high GTM spend ({sga:.0%} SG&A).",
                    "evidence": "Financial snapshot analysis",
                    "recommended_action": "Use as social proof: 'Industry leaders invest heavily in GTM.'",
                    "priority": "low",
                })

        # Holding group concentration — signals buying dynamics
        hg_map = competitive_dynamics.get("holding_group_map", {})
        if hg_map:
            network_agencies = sum(
                info.get("subsidiary_count", 0) for grp, info in hg_map.items()
                if grp != "Independent"
            )
            independent_count = hg_map.get("Independent", {}).get("subsidiary_count", 0)
            if network_agencies > 0:
                implications.append({
                    "insight": (
                        f"Holding-group consolidation: {network_agencies} network agencies vs "
                        f"{independent_count} independents. Network agencies have global procurement "
                        f"processes and slower buying cycles."
                    ),
                    "evidence": f"Ownership mapping of {len(hg_map)} groups",
                    "recommended_action": (
                        "For network agencies: engage regional/global procurement. "
                        "For independents: founder-direct selling is faster and more effective."
                    ),
                    "priority": "high",
                })

        # Service line concentration
        sg_count = len(competitive_dynamics.get("sg_agency_landscape", []))
        svc_matrix = competitive_dynamics.get("service_line_matrix", {})
        if svc_matrix and sg_count > 0:
            top_svc = next(iter(svc_matrix.items()), None)
            if top_svc:
                svc_name, svc_data = top_svc
                svc_pct = round(svc_data.get("count", 0) / max(sg_count, 1) * 100)
                implications.append({
                    "insight": (
                        f"'{svc_name}' is the most crowded service line ({svc_pct}% of agencies). "
                        f"Differentiation is critical in this space."
                    ),
                    "evidence": f"Service line analysis across {sg_count} agencies",
                    "recommended_action": (
                        "When targeting agencies in crowded service lines, lead with unique value prop. "
                        "Niche service lines (data, experiential) may be easier entry points."
                    ),
                    "priority": "medium",
                })

        # Revenue growth trend
        rg_trend = financial_pulse.get("revenue_growth_trend")
        rg_median = financial_pulse.get("revenue_growth_median")
        if rg_trend and rg_median is not None:
            if rg_trend == "accelerating":
                implications.append({
                    "insight": f"Revenue growth accelerating ({rg_median:.0%} median YoY) — industry tailwind.",
                    "evidence": "YoY revenue growth benchmark comparison",
                    "recommended_action": "Growth-mode companies invest in tooling; emphasise scaling capabilities.",
                    "priority": "medium",
                })
            elif rg_trend == "decelerating":
                implications.append({
                    "insight": f"Revenue growth decelerating ({rg_median:.0%} median YoY) — tightening budgets.",
                    "evidence": "YoY revenue growth benchmark comparison",
                    "recommended_action": "Lead with cost savings and efficiency; longer sales cycles expected.",
                    "priority": "high",
                })

        return implications

    # ------------------------------------------------------------------
    # Static helpers — dossier-based SG agency landscape
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sg_agency_landscape(vertical_slug: str) -> list[dict[str, Any]]:
        """Build SG agency competitive landscape from dossier files."""
        dossier_dir = _INTEL_DATA_DIR / vertical_slug
        if not dossier_dir.exists():
            return []

        segments = _PRIVATE_SEGMENTS.get(vertical_slug, {})
        agencies: list[dict[str, Any]] = []

        for path in sorted(dossier_dir.glob("*_PRIVATE.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            name = data.get("company_name", path.stem.replace("_PRIVATE", ""))
            ticker = data.get("ticker", path.stem.replace("_PRIVATE", ""))
            segment = segments.get(ticker, "general")

            website = data.get("website_intel", {})
            research = data.get("perplexity_research", {})

            headcount = None
            hiring_count = 0
            if isinstance(website, dict):
                for fact in website.get("facts", []):
                    if not isinstance(fact, dict):
                        continue
                    ft = fact.get("fact_type", "")
                    fd = fact.get("data", {})
                    if not isinstance(fd, dict):
                        continue
                    if ft == "hiring" and "job_count" in fd:
                        hiring_count = max(hiring_count, fd["job_count"])
                    if ft == "company_info" and "employee_count" in fd:
                        headcount = fd["employee_count"]

            # Awards — scan ALL sections for award mentions
            awards_text_parts: list[str] = []
            positioning = ""
            if isinstance(research, dict):
                for _key, section in research.items():
                    if not isinstance(section, dict):
                        continue
                    content = section.get("content", "")
                    if not isinstance(content, str):
                        continue
                    if "award" in _key.lower() or "news" in _key.lower():
                        awards_text_parts.append(content[:600])
                    elif any(
                        kw in content.lower()
                        for kw in [
                            "cannes", "spikes", "effie", "agency of the year",
                            "d&ad", "clio", "prism", "sabre", "one show", "adfest",
                            "won ", "awarded", "shortlisted", "grand prix",
                        ]
                    ):
                        awards_text_parts.append(content[:400])
                    if "overview" in _key.lower() or "leadership" in _key.lower():
                        positioning = content[:200]
            awards_text = "\n".join(awards_text_parts)[:1500]

            # Strip prompt-template boilerplate
            awards_text_clean = re.sub(
                r"awards?\s*\(?\s*(?:including|such as|e\.g\.|like)\s+[^.]*?\.",
                "", awards_text, flags=re.IGNORECASE,
            )

            # Award detection with negation check
            award_keywords = [
                "cannes", "spikes", "effie", "lions", "campaign asia",
                "agency of the year", "prism", "sabre", "d&ad",
            ]
            _clean_lower = awards_text_clean.lower()
            has_awards = any(
                kw in _clean_lower
                and not VerticalIntelligenceSynthesizer._is_negated(_clean_lower, kw)
                for kw in award_keywords
            )

            # Holding group
            holding_groups = _HOLDING_GROUP_MAP.get(vertical_slug, {})
            parent_group = holding_groups.get(ticker, "Independent")

            # Service lines from ALL sections
            all_content_parts: list[str] = []
            if isinstance(research, dict):
                for _key, section in research.items():
                    if isinstance(section, dict):
                        c = section.get("content", "")
                        if isinstance(c, str):
                            all_content_parts.append(c)
            overview_content = "\n".join(all_content_parts)

            svc_keywords: dict[str, list[str]] = {
                "creative": ["creative agency", "brand strategy", "advertising agency", "copywriting", "creative services"],
                "media": ["media buying", "media planning", "programmatic", "media agency", "media network"],
                "pr": ["public relations", "media relations", "reputation management", "corporate communications", "pr agency"],
                "digital": ["digital marketing", "seo", "sem", "performance marketing", "ppc", "digital agency"],
                "social": ["social media marketing", "social media management", "social media agency", "social-first", "social media strategy", "community management"],
                "experiential": ["experiential", "event marketing", "activation", "exhibition", "live event"],
                "influencer": ["influencer marketing", "creator economy", "kol management", "content creator"],
                "data": ["data analytics", "martech", "customer data platform", "marketing analytics"],
            }
            service_lines: list[str] = []
            if overview_content:
                oc_lower = overview_content.lower()
                for svc, kws in svc_keywords.items():
                    if any(kw in oc_lower for kw in kws):
                        service_lines.append(svc)

            # Specific awards won
            awards_won: list[str] = []
            award_names: dict[str, str] = {
                "cannes": "Cannes Lions", "spikes asia": "Spikes Asia",
                "effie": "Effie Awards", "d&ad": "D&AD",
                "campaign asia": "Campaign AOY", "clio": "Clio Awards",
                "agency of the year": "Agency of the Year",
                "prism": "PRISM Awards", "sabre": "SABRE Awards",
                "one show": "One Show", "adfest": "ADFEST",
                "marketing-interactive": "Marketing-Interactive Awards",
                "grand prix": "Grand Prix", "webby": "Webby Awards",
                "singapore creative circle": "SCC Awards",
                "mumbrella": "Mumbrella Awards", "pr daily": "PR Daily Awards",
                "holmes report": "Holmes Report", "provoke": "PRovoke Awards",
                "won gold": "Gold Award", "won silver": "Silver Award",
            }
            if awards_text_clean:
                at_lower = awards_text_clean.lower()
                for trigger, label in award_names.items():
                    if (
                        trigger in at_lower
                        and not VerticalIntelligenceSynthesizer._is_negated(at_lower, trigger)
                        and label not in awards_won
                    ):
                        awards_won.append(label)

            agencies.append({
                "name": name,
                "ticker": ticker,
                "segment": _SEGMENT_LABELS.get(segment, segment),
                "parent_group": parent_group,
                "headcount": headcount,
                "hiring_openings": hiring_count,
                "has_major_awards": has_awards,
                "awards_won": awards_won[:5],
                "service_lines": service_lines[:5],
                "positioning_summary": positioning[:150] if positioning else None,
                "dossier_available": True,
            })

        return agencies

    @staticmethod
    def _extract_dossier_signals(vertical_slug: str) -> list[dict[str, Any]]:
        """Extract market signals from dossier files."""
        dossier_dir = _INTEL_DATA_DIR / vertical_slug
        if not dossier_dir.exists():
            return []

        signal_keywords: dict[str, list[str]] = {
            "leadership_change": [
                "appoint", "named", "promoted", "hired", "new ceo", "new cmo",
                "new cfo", "joins as", "steps down", "departs",
            ],
            "partnership": [
                "partner", "collaborat", "alliance", "joint venture", "teamed up",
                "integrated with", "certified partner",
            ],
            "acquisition": ["acquir", "merger", "bought", "merged with", "takeover"],
            "product_launch": ["launch", "unveiled", "introduced", "rolled out", "new platform"],
            "expansion": ["expand", "new office", "opened", "entered the market", "regional hub"],
            "award": ["won the", "awarded", "recognized", "shortlisted", "named agency of"],
            "investment": ["raised", "funding", "invested", "valuation", "series"],
            "client_win": [
                "won the account", "agency of record", "awarded the", "selected as",
                "appointed by", "pitch win", "retained by", "secured the",
            ],
            "client_loss": [
                "lost the account", "parted ways", "ended its relationship",
                "dropped by", "review following",
            ],
        }
        signals: list[dict[str, Any]] = []
        company_signal_count: dict[str, int] = {}

        for path in sorted(dossier_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            company_name = data.get("company_name", path.stem)
            if company_signal_count.get(company_name, 0) >= 2:
                continue

            research = data.get("perplexity_research", {})
            if not isinstance(research, dict):
                continue

            for _section_key, section in research.items():
                if not isinstance(section, dict):
                    continue
                content = section.get("content", "")
                if not isinstance(content, str) or len(content) < 50:
                    continue

                for line in VerticalIntelligenceSynthesizer._split_into_sentences(content):
                    if VerticalIntelligenceSynthesizer._is_section_header(line):
                        continue
                    line_lower = line.lower()
                    for signal_type, keywords in signal_keywords.items():
                        for kw in keywords:
                            if kw in line_lower and not VerticalIntelligenceSynthesizer._is_negated(
                                line_lower, kw
                            ):
                                headline = VerticalIntelligenceSynthesizer._extract_keyword_context(
                                    line, kw
                                )
                                if len(headline) < 30:
                                    continue
                                signals.append({
                                    "headline": headline,
                                    "signal_type": signal_type,
                                    "source": f"dossier:{company_name}",
                                    "published_at": datetime.now(UTC).isoformat(),
                                    "sentiment": "neutral",
                                })
                                company_signal_count[company_name] = (
                                    company_signal_count.get(company_name, 0) + 1
                                )
                                break
                        if company_signal_count.get(company_name, 0) >= 2:
                            break
                    if company_signal_count.get(company_name, 0) >= 2:
                        break
                if company_signal_count.get(company_name, 0) >= 2:
                    break

        return signals[:15]

    @staticmethod
    def _extract_dossier_exec_movements(vertical_slug: str) -> list[dict[str, Any]]:
        """Extract executive movements from dossier files."""
        dossier_dir = _INTEL_DATA_DIR / vertical_slug
        if not dossier_dir.exists():
            return []

        movements: list[dict[str, Any]] = []
        seen_companies: set[str] = set()
        exec_keywords = [
            "appoint", "named as", "promoted to", "hired as", "joins as",
            "new ceo", "new cmo", "new cfo", "new coo", "managing director",
            "chief executive", "chief marketing", "chief financial",
        ]
        bio_markers = [
            "diploma", "bachelor", "master", "degree", "university",
            "no cco", "no cmo", "no cfo", "no linkedin", "not detailed",
            "average management tenure", "search results", "not found", "not provide",
        ]

        for path in sorted(dossier_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            company_name = data.get("company_name", path.stem)
            if company_name.lower() in seen_companies:
                continue

            research = data.get("perplexity_research", {})
            if not isinstance(research, dict):
                continue

            for _section_key, section in research.items():
                if not isinstance(section, dict):
                    continue
                content = section.get("content", "")
                if not isinstance(content, str) or len(content) < 50:
                    continue

                for line in VerticalIntelligenceSynthesizer._split_into_sentences(content):
                    ll = line.lower()
                    if any(bm in ll for bm in bio_markers):
                        continue
                    if any(kw in ll for kw in exec_keywords):
                        matching_kw = next(kw for kw in exec_keywords if kw in ll)
                        detail = VerticalIntelligenceSynthesizer._extract_keyword_context(
                            line, matching_kw, max_len=200
                        )
                        if len(detail) < 30:
                            continue
                        movements.append({
                            "company": company_name,
                            "detail": detail,
                            "source": "dossier_research",
                        })
                        seen_companies.add(company_name.lower())
                        break
                if company_name.lower() in seen_companies:
                    break

        return movements[:15]

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """Split text into sentences for per-sentence keyword matching."""
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])|(?<=\]\s)(?=[A-Z])', text)
        return [p.strip() for p in parts if p and len(p.strip()) >= 20]

    @staticmethod
    def _is_negated(text_lower: str, keyword: str) -> bool:
        """Check if keyword occurrence is negated in its clause."""
        kw_pos = text_lower.find(keyword)
        if kw_pos < 0:
            return False
        pre = text_lower[:kw_pos]
        last_boundary = max(pre.rfind(". "), pre.rfind("? "), pre.rfind("! "), 0)
        clause = pre[last_boundary:]
        negation_markers = ("no ", "not ", "n't ", "no other", "without ", "nor ", "never ", "none ", "neither ")
        return any(neg in clause for neg in negation_markers)

    @staticmethod
    def _extract_keyword_context(line: str, keyword: str, max_len: int = 150) -> str:
        """Extract text around keyword, snapping to word boundaries."""
        ll = line.lower()
        kw_pos = ll.find(keyword)
        if kw_pos < 0:
            return line[:max_len]
        raw_start = max(0, kw_pos - 60)
        if raw_start > 0:
            space_pos = line.find(" ", raw_start)
            start = space_pos + 1 if space_pos != -1 and space_pos < kw_pos else raw_start
        else:
            start = 0
        text = line[start : start + max_len].strip()
        text = re.sub(r"\[\d+\]", "", text).strip()
        text = text.replace("**", "").replace("__", "")
        text = text.strip("*_.,;: ")
        return text

    @staticmethod
    def _is_section_header(text: str) -> bool:
        """Filter ALL-CAPS headers and common dossier section titles."""
        stripped = text.strip()
        if not stripped:
            return True
        if stripped[:3].replace(".", "").replace(" ", "").isdigit():
            return True
        words = stripped.split()
        if words and words[0].isupper() and len(words[0]) > 2:
            caps_count = sum(1 for w in words[:3] if w.isupper() and len(w) > 1)
            if caps_count >= 2:
                return True
        header_phrases = (
            "press releases", "awards", "news and", "overview",
            "recent announcements", "key developments", "leadership",
        )
        sl = stripped.lower()
        if any(sl.startswith(hp) for hp in header_phrases):
            return True
        return False
