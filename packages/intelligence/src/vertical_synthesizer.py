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

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
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
        key_trends: list[dict],
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

        return implications
