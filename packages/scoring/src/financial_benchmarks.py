"""Financial Benchmarking Engine — deterministic, no LLM.

Computes percentile distributions for a vertical's listed companies.
Used by:
- VerticalBenchmark DB rows (precomputed, refreshed weekly)
- MarketIntelAgent._do() for real-time peer comparison
- Kairos UI: "Your company vs peers"

Metrics for OPERATING COMPANIES:
  revenue_growth_yoy, gross_margin, ebitda_margin, net_margin, roe, net_debt_ebitda

REIT-specific metrics handled separately:
  dpu_yield, nav_premium_discount, gearing_ratio
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Outlier filtering bounds — inclusive range; values outside are excluded
# ---------------------------------------------------------------------------

OUTLIER_BOUNDS: dict[str, tuple[float, float]] = {
    "revenue_growth_yoy": (-0.90, 5.0),   # -90% to +500%
    "gross_margin": (-0.50, 1.0),          # can be negative for some cos
    "ebitda_margin": (-1.0, 1.0),
    "net_margin": (-2.0, 1.0),
    "roe": (-2.0, 2.0),
    "net_debt_ebitda": (-5.0, 20.0),
    "sga_to_revenue": (0.0, 1.0),         # 0–100% of revenue; >100% is outlier (e.g. litigation)
    "rnd_to_revenue": (0.0, 1.0),         # 0–100%
    "operating_margin": (-1.0, 1.0),      # mirrors ebitda_margin bounds
    "capex_to_revenue": (0.0, 1.0),       # 0–100%; capital-intensive verticals (maritime, energy, telco) can exceed 50%
}

# Minimum sample size to compute meaningful percentiles
_MIN_SAMPLE = 3


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PercentileDistribution:
    """Percentile summary for a single metric across a sample of companies."""

    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    mean: float | None
    sample_size: int

    def to_dict(self) -> dict:
        return {
            "p25": self.p25,
            "p50": self.p50,
            "p75": self.p75,
            "p90": self.p90,
            "mean": self.mean,
            "n": self.sample_size,
        }

    def percentile_rank(self, value: float) -> float:
        """Return 0–1 indicating where *value* sits in this distribution.

        Uses linear interpolation between the four known percentile anchors.
        Below P25 → interpolate 0–0.25 using P25 as ceiling.
        P25–P50 → 0.25–0.50, P50–P75 → 0.50–0.75, P75–P90 → 0.75–0.90.
        Above P90 → extrapolate but cap at 0.99.

        Returns 0.5 when the distribution is unavailable (degenerate case).
        """
        # Gather defined anchors as (percentile_rank, value) pairs
        anchors: list[tuple[float, float]] = []
        for rank, pval in (
            (0.25, self.p25),
            (0.50, self.p50),
            (0.75, self.p75),
            (0.90, self.p90),
        ):
            if pval is not None:
                anchors.append((rank, pval))

        if not anchors:
            return 0.5

        # Below lowest anchor
        if value <= anchors[0][1]:
            lo_rank, lo_val = 0.0, anchors[0][1] - (anchors[-1][1] - anchors[0][1])
            hi_rank, hi_val = anchors[0]
            if hi_val == lo_val:
                return anchors[0][0]
            t = (value - lo_val) / (hi_val - lo_val)
            return max(0.0, lo_rank + t * (hi_rank - lo_rank))

        # Above highest anchor → extrapolate, cap at 0.99
        if value >= anchors[-1][1]:
            if len(anchors) >= 2:
                prev_rank, prev_val = anchors[-2]
                top_rank, top_val = anchors[-1]
                span = top_val - prev_val
                if span <= 0:
                    return min(0.99, anchors[-1][0])
                excess = value - top_val
                # Each additional span beyond P90 adds half the prior rank gap
                rank_gap = top_rank - prev_rank
                extrapolated = top_rank + (excess / span) * rank_gap * 0.5
                return min(0.99, extrapolated)
            return min(0.99, anchors[-1][0])

        # Within range — find surrounding pair and interpolate
        for i in range(len(anchors) - 1):
            lo_rank, lo_val = anchors[i]
            hi_rank, hi_val = anchors[i + 1]
            if lo_val <= value <= hi_val:
                if hi_val == lo_val:
                    return (lo_rank + hi_rank) / 2
                t = (value - lo_val) / (hi_val - lo_val)
                return lo_rank + t * (hi_rank - lo_rank)

        # Fallback (should not be reached)
        return 0.5


@dataclass
class CompanyMetrics:
    """Input record for a single listed company entering the benchmark."""

    ticker: str
    name: str
    is_reit: bool
    revenue_growth_yoy: float | None
    gross_margin: float | None
    ebitda_margin: float | None
    net_margin: float | None
    roe: float | None
    net_debt_ebitda: float | None
    revenue_ttm_sgd: float | None
    # Exchange where listed — used by Market Intel agent to disambiguate trajectory lookups
    exchange: str = "SG"
    # GTM-relevant operational detail
    sga_to_revenue: float | None = None
    rnd_to_revenue: float | None = None
    operating_margin: float | None = None
    capex_to_revenue: float | None = None
    # REIT-specific
    dpu_yield: float | None = None
    gearing_ratio: float | None = None


@dataclass
class BenchmarkResult:
    """Output of FinancialBenchmarkEngine.compute_benchmark().

    Distributions are computed over operating companies only (is_reit=False).
    company_count reflects the total operating company sample used.
    """

    vertical_slug: str
    period_label: str
    period_type: str           # "annual" or "quarterly"
    company_count: int
    # Operating company distributions
    revenue_growth_yoy: PercentileDistribution
    gross_margin: PercentileDistribution
    ebitda_margin: PercentileDistribution
    net_margin: PercentileDistribution
    roe: PercentileDistribution
    net_debt_ebitda: PercentileDistribution
    revenue_ttm_sgd: PercentileDistribution
    # GTM-relevant operational benchmarks
    sga_to_revenue: PercentileDistribution
    rnd_to_revenue: PercentileDistribution
    operating_margin: PercentileDistribution
    capex_to_revenue: PercentileDistribution
    # Leaders / laggards by revenue growth
    leaders: list[dict]    # top 3: [{"ticker", "name", "revenue_growth_yoy", "gross_margin"}]
    laggards: list[dict]   # bottom 3
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_vertical_benchmark_dict(self) -> dict:
        """Serialise for VerticalBenchmark JSON columns.

        Returns a dict whose keys map directly to VerticalBenchmark model fields.
        """
        return {
            "company_count": self.company_count,
            "revenue_growth_yoy": self.revenue_growth_yoy.to_dict(),
            "gross_margin": self.gross_margin.to_dict(),
            "ebitda_margin": self.ebitda_margin.to_dict(),
            "net_margin": self.net_margin.to_dict(),
            "roe": self.roe.to_dict(),
            "net_debt_ebitda": self.net_debt_ebitda.to_dict(),
            "revenue_ttm_sgd": self.revenue_ttm_sgd.to_dict(),
            "sga_to_revenue": self.sga_to_revenue.to_dict(),
            "rnd_to_revenue": self.rnd_to_revenue.to_dict(),
            "operating_margin": self.operating_margin.to_dict(),
            "capex_to_revenue": self.capex_to_revenue.to_dict(),
            "leaders": self.leaders,
            "laggards": self.laggards,
            "computed_at": self.computed_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class FinancialBenchmarkEngine:
    """Deterministic financial benchmarking — no LLM, stdlib only.

    All methods are synchronous and pure: given the same inputs they always
    produce the same outputs.  Thread-safe (no mutable instance state).
    """

    # Rank thresholds for describe_position()
    _TOP_QUARTILE = 0.75
    _BOTTOM_QUARTILE = 0.25
    _MEDIAN = 0.50

    def compute_distribution(
        self, values: list[float | None], metric: str | None = None
    ) -> PercentileDistribution:
        """Compute P25/P50/P75/P90 for a list of raw metric values.

        Args:
            values: Raw values, may contain None.
            metric:  Optional metric name used to look up OUTLIER_BOUNDS.

        Returns:
            PercentileDistribution.  All percentile fields are None when the
            cleaned sample has fewer than _MIN_SAMPLE data points.
        """
        lo, hi = (-math.inf, math.inf)
        if metric and metric in OUTLIER_BOUNDS:
            lo, hi = OUTLIER_BOUNDS[metric]

        cleaned: list[float] = [
            v
            for v in values
            if v is not None
            and math.isfinite(v)
            and lo <= v <= hi
        ]

        n = len(cleaned)
        if n < _MIN_SAMPLE:
            return PercentileDistribution(
                p25=None, p50=None, p75=None, p90=None,
                mean=None, sample_size=n,
            )

        cleaned.sort()

        # statistics.quantiles(data, n=4) → [Q1, Q2, Q3] = [P25, P50, P75]
        q1, q2, q3 = statistics.quantiles(cleaned, n=4)

        # P90: index at 90th percentile using nearest-rank
        p90_idx = max(0, math.ceil(0.90 * n) - 1)
        p90 = cleaned[p90_idx]

        mean_val = statistics.mean(cleaned)

        return PercentileDistribution(
            p25=round(q1, 6),
            p50=round(q2, 6),
            p75=round(q3, 6),
            p90=round(p90, 6),
            mean=round(mean_val, 6),
            sample_size=n,
        )

    def percentile_rank(self, value: float, dist: PercentileDistribution) -> float:
        """Return 0.0–1.0 where *value* sits in *dist*.

        Delegates to PercentileDistribution.percentile_rank() — exposed here
        so callers can use the engine as a single entry point.
        """
        return dist.percentile_rank(value)

    def compute_benchmark(
        self,
        vertical_slug: str,
        period_label: str,
        period_type: str,
        companies: list[CompanyMetrics],
    ) -> BenchmarkResult:
        """Compute full vertical benchmark from a list of company metric records.

        REITs (is_reit=True) are excluded from operating-company distributions.
        Leaders and laggards are identified among operating companies with a
        non-None revenue_growth_yoy, then serialised as lightweight dicts.

        Args:
            vertical_slug:  e.g. "fintech", "reit-industrial"
            period_label:   e.g. "2024", "2024-Q3"
            period_type:    "annual" or "quarterly"
            companies:      One CompanyMetrics per company; may be empty.

        Returns:
            BenchmarkResult with distributions and leader/laggard snapshots.
        """
        operating = [c for c in companies if not c.is_reit]

        def _values(attr: str) -> list[float | None]:
            return [getattr(c, attr) for c in operating]

        revenue_growth_dist = self.compute_distribution(
            _values("revenue_growth_yoy"), metric="revenue_growth_yoy"
        )
        gross_margin_dist = self.compute_distribution(
            _values("gross_margin"), metric="gross_margin"
        )
        ebitda_margin_dist = self.compute_distribution(
            _values("ebitda_margin"), metric="ebitda_margin"
        )
        net_margin_dist = self.compute_distribution(
            _values("net_margin"), metric="net_margin"
        )
        roe_dist = self.compute_distribution(_values("roe"), metric="roe")
        net_debt_ebitda_dist = self.compute_distribution(
            _values("net_debt_ebitda"), metric="net_debt_ebitda"
        )
        # Revenue scale — no outlier bounds; any non-negative is valid
        revenue_ttm_dist = self.compute_distribution(
            [v for v in _values("revenue_ttm_sgd") if v is None or v >= 0],
        )

        # GTM-relevant operational benchmarks
        sga_dist = self.compute_distribution(
            _values("sga_to_revenue"), metric="sga_to_revenue"
        )
        rnd_dist = self.compute_distribution(
            _values("rnd_to_revenue"), metric="rnd_to_revenue"
        )
        operating_margin_dist = self.compute_distribution(
            _values("operating_margin"), metric="operating_margin"
        )
        capex_dist = self.compute_distribution(
            _values("capex_to_revenue"), metric="capex_to_revenue"
        )

        # Leaders and laggards — ranked by revenue_growth_yoy
        ranked = sorted(
            [c for c in operating if c.revenue_growth_yoy is not None],
            key=lambda c: c.revenue_growth_yoy,  # type: ignore[arg-type]
            reverse=True,
        )

        def _snapshot(c: CompanyMetrics) -> dict:
            return {
                "ticker": c.ticker,
                "name": c.name,
                "exchange": c.exchange,
                "revenue_growth_yoy": c.revenue_growth_yoy,
                "gross_margin": c.gross_margin,
                "sga_to_revenue": c.sga_to_revenue,
                "rnd_to_revenue": c.rnd_to_revenue,
            }

        leaders = [_snapshot(c) for c in ranked[:3]]
        laggards = [_snapshot(c) for c in ranked[-3:][::-1]]  # worst first

        return BenchmarkResult(
            vertical_slug=vertical_slug,
            period_label=period_label,
            period_type=period_type,
            company_count=len(operating),
            revenue_growth_yoy=revenue_growth_dist,
            gross_margin=gross_margin_dist,
            ebitda_margin=ebitda_margin_dist,
            net_margin=net_margin_dist,
            roe=roe_dist,
            net_debt_ebitda=net_debt_ebitda_dist,
            revenue_ttm_sgd=revenue_ttm_dist,
            sga_to_revenue=sga_dist,
            rnd_to_revenue=rnd_dist,
            operating_margin=operating_margin_dist,
            capex_to_revenue=capex_dist,
            leaders=leaders,
            laggards=laggards,
        )

    def rank_company(
        self,
        company: CompanyMetrics,
        benchmark: BenchmarkResult,
    ) -> dict[str, float]:
        """Return per-metric percentile ranks (0–1) for a company vs the benchmark.

        Only metrics where *company* has a non-None value are included in the
        returned dict.  Metrics whose benchmark distribution is degenerate
        (all-None percentiles) are also excluded.

        Example output:
            {"revenue_growth_yoy": 0.73, "gross_margin": 0.55, ...}
        """
        metric_pairs: list[tuple[str, float | None, PercentileDistribution]] = [
            ("revenue_growth_yoy", company.revenue_growth_yoy, benchmark.revenue_growth_yoy),
            ("gross_margin", company.gross_margin, benchmark.gross_margin),
            ("ebitda_margin", company.ebitda_margin, benchmark.ebitda_margin),
            ("net_margin", company.net_margin, benchmark.net_margin),
            ("roe", company.roe, benchmark.roe),
            ("net_debt_ebitda", company.net_debt_ebitda, benchmark.net_debt_ebitda),
            ("revenue_ttm_sgd", company.revenue_ttm_sgd, benchmark.revenue_ttm_sgd),
            ("sga_to_revenue", company.sga_to_revenue, benchmark.sga_to_revenue),
            ("rnd_to_revenue", company.rnd_to_revenue, benchmark.rnd_to_revenue),
            ("operating_margin", company.operating_margin, benchmark.operating_margin),
            ("capex_to_revenue", company.capex_to_revenue, benchmark.capex_to_revenue),
        ]

        ranks: dict[str, float] = {}
        for metric_name, company_val, dist in metric_pairs:
            if company_val is None:
                continue
            if dist.p50 is None:
                # Distribution is degenerate — skip
                continue
            rank = self.percentile_rank(company_val, dist)
            ranks[metric_name] = round(rank, 4)

        return ranks

    def describe_position(self, ranks: dict[str, float]) -> str:
        """Generate a deterministic 1–2 sentence position description from ranks.

        No LLM — plain conditional logic on rank thresholds.
        Returns a generic statement when ranks is empty.
        """
        if not ranks:
            return "Insufficient data to benchmark this company against its peers."

        # Growth narrative
        growth_rank = ranks.get("revenue_growth_yoy")
        growth_phrase = _rank_to_label(growth_rank, invert=False) if growth_rank is not None else None

        # Margin narrative — use gross margin if available, else net margin
        margin_rank = ranks.get("gross_margin")
        if margin_rank is None:
            margin_rank = ranks.get("net_margin")
        margin_phrase = _rank_to_label(margin_rank, invert=False) if margin_rank is not None else None

        # Leverage narrative — high net_debt_ebitda is bad, so invert the rank
        leverage_rank = ranks.get("net_debt_ebitda")
        leverage_phrase = _rank_to_label(leverage_rank, invert=True) if leverage_rank is not None else None

        sentences: list[str] = []

        if growth_phrase and margin_phrase:
            growth_pct = int(round(growth_rank * 100))
            margin_pct = int(round(margin_rank * 100))
            sentences.append(
                f"{growth_phrase} revenue growth ({growth_pct}th percentile) "
                f"with {margin_phrase.lower()} margins ({margin_pct}th percentile)."
            )
        elif growth_phrase:
            growth_pct = int(round(growth_rank * 100))
            sentences.append(f"{growth_phrase} revenue growth ({growth_pct}th percentile).")
        elif margin_phrase:
            margin_pct = int(round(margin_rank * 100))
            sentences.append(f"{margin_phrase} margins ({margin_pct}th percentile).")

        # Second sentence — actionable insight
        if growth_rank is not None and margin_rank is not None:
            if growth_rank >= self._TOP_QUARTILE and margin_rank < self._MEDIAN:
                sentences.append(
                    "Strong growth story with margin improvement opportunity."
                )
            elif growth_rank >= self._TOP_QUARTILE and margin_rank >= self._TOP_QUARTILE:
                sentences.append(
                    "Excellent unit economics — top-quartile on both growth and profitability."
                )
            elif growth_rank < self._BOTTOM_QUARTILE and margin_rank >= self._TOP_QUARTILE:
                sentences.append(
                    "Mature, high-margin business; focus on reinvesting for renewed growth."
                )
            elif growth_rank < self._BOTTOM_QUARTILE and margin_rank < self._BOTTOM_QUARTILE:
                sentences.append(
                    "Both growth and margins below peer median — strategic repositioning recommended."
                )

        if leverage_phrase and leverage_rank is not None:
            leverage_pct = int(round(leverage_rank * 100))
            # Only surface leverage if it's a notable signal (top or bottom quartile)
            if leverage_rank <= self._BOTTOM_QUARTILE or leverage_rank >= self._TOP_QUARTILE:
                sentences.append(
                    f"{leverage_phrase} balance sheet ({leverage_pct}th percentile leverage)."
                )

        # GTM spend narrative — SG&A and R&D intensity
        sga_rank = ranks.get("sga_to_revenue")
        rnd_rank = ranks.get("rnd_to_revenue")
        if sga_rank is not None:
            sga_pct = int(round(sga_rank * 100))
            if sga_rank >= self._TOP_QUARTILE:
                sentences.append(
                    f"High GTM spend intensity (SG&A at {sga_pct}th percentile) — aggressive market investment."
                )
            elif sga_rank <= self._BOTTOM_QUARTILE:
                sentences.append(
                    f"Lean GTM operation (SG&A at {sga_pct}th percentile) — may indicate efficiency or underinvestment."
                )
        if rnd_rank is not None:
            rnd_pct = int(round(rnd_rank * 100))
            if rnd_rank >= self._TOP_QUARTILE:
                sentences.append(
                    f"R&D-intensive ({rnd_pct}th percentile) — product-led growth potential."
                )

        capex_rank = ranks.get("capex_to_revenue")
        if capex_rank is not None:
            capex_pct = int(round(capex_rank * 100))
            if capex_rank >= self._TOP_QUARTILE:
                sentences.append(
                    f"High capex intensity ({capex_pct}th percentile) — investing heavily in capacity."
                )

        if not sentences:
            # Fallback when only one or two sparse metrics available
            avg_rank = statistics.mean(ranks.values())
            overall = _rank_to_label(avg_rank, invert=False)
            sentences.append(
                f"{overall} peer positioning based on available metrics "
                f"(avg rank {int(round(avg_rank * 100))}th percentile)."
            )

        return " ".join(sentences)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rank_to_label(rank: float | None, *, invert: bool = False) -> str:
    """Convert a 0–1 rank to a qualitative label.

    When invert=True a high rank is negative (e.g. high leverage is bad).
    """
    if rank is None:
        return "Median"

    effective = (1.0 - rank) if invert else rank

    if effective >= 0.90:
        return "Top-decile"
    if effective >= 0.75:
        return "Top-quartile"
    if effective >= 0.50:
        return "Above-median"
    if effective >= 0.25:
        return "Below-median"
    if effective >= 0.10:
        return "Bottom-quartile"
    return "Bottom-decile"
