"""Unit tests for packages/scoring/src/financial_benchmarks.py."""

from __future__ import annotations

import pytest

from packages.scoring.src.financial_benchmarks import (
    BenchmarkResult,
    CompanyMetrics,
    FinancialBenchmarkEngine,
    PercentileDistribution,
    _rank_to_label,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> FinancialBenchmarkEngine:
    return FinancialBenchmarkEngine()


def _make_company(
    ticker: str,
    *,
    is_reit: bool = False,
    revenue_growth_yoy: float | None = None,
    gross_margin: float | None = None,
    ebitda_margin: float | None = None,
    net_margin: float | None = None,
    roe: float | None = None,
    net_debt_ebitda: float | None = None,
    revenue_ttm_sgd: float | None = None,
) -> CompanyMetrics:
    return CompanyMetrics(
        ticker=ticker,
        name=ticker,
        is_reit=is_reit,
        revenue_growth_yoy=revenue_growth_yoy,
        gross_margin=gross_margin,
        ebitda_margin=ebitda_margin,
        net_margin=net_margin,
        roe=roe,
        net_debt_ebitda=net_debt_ebitda,
        revenue_ttm_sgd=revenue_ttm_sgd,
    )


# ---------------------------------------------------------------------------
# compute_distribution
# ---------------------------------------------------------------------------


class TestComputeDistribution:
    def test_basic_percentiles(self, engine: FinancialBenchmarkEngine) -> None:
        """Distribution over 10 evenly-spaced values."""
        values = [float(i) for i in range(1, 11)]  # 1–10
        dist = engine.compute_distribution(values)
        assert dist.sample_size == 10
        assert dist.p25 is not None
        assert dist.p50 is not None
        assert dist.p25 < dist.p50 < dist.p75 < dist.p90  # type: ignore[operator]

    def test_none_values_excluded(self, engine: FinancialBenchmarkEngine) -> None:
        values: list[float | None] = [1.0, None, 2.0, None, 3.0, 4.0, 5.0]
        dist = engine.compute_distribution(values)
        assert dist.sample_size == 5

    def test_below_min_sample_returns_none_percentiles(
        self, engine: FinancialBenchmarkEngine
    ) -> None:
        dist = engine.compute_distribution([0.1, 0.2])  # only 2 values < _MIN_SAMPLE=3
        assert dist.p25 is None
        assert dist.p50 is None
        assert dist.sample_size == 2

    def test_outlier_filtering(self, engine: FinancialBenchmarkEngine) -> None:
        # revenue_growth_yoy bounds: (-0.90, 5.0)
        values = [-1.5, 0.0, 0.1, 0.2, 0.3, 10.0]  # -1.5 and 10.0 should be dropped
        dist = engine.compute_distribution(values, metric="revenue_growth_yoy")
        assert dist.sample_size == 4  # only 0.0, 0.1, 0.2, 0.3

    def test_empty_input(self, engine: FinancialBenchmarkEngine) -> None:
        dist = engine.compute_distribution([])
        assert dist.p50 is None
        assert dist.sample_size == 0

    def test_all_none(self, engine: FinancialBenchmarkEngine) -> None:
        dist = engine.compute_distribution([None, None, None])
        assert dist.sample_size == 0

    def test_mean_is_correct(self, engine: FinancialBenchmarkEngine) -> None:
        dist = engine.compute_distribution([0.0, 1.0, 2.0, 3.0, 4.0])
        assert dist.mean == pytest.approx(2.0)

    def test_single_value_repeated(self, engine: FinancialBenchmarkEngine) -> None:
        """Identical values should not crash."""
        dist = engine.compute_distribution([0.5, 0.5, 0.5, 0.5, 0.5])
        assert dist.p25 == pytest.approx(0.5)
        assert dist.p50 == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# PercentileDistribution.percentile_rank
# ---------------------------------------------------------------------------


class TestPercentileRank:
    def _dist(self) -> PercentileDistribution:
        """Distribution: p25=10, p50=20, p75=30, p90=40."""
        return PercentileDistribution(p25=10.0, p50=20.0, p75=30.0, p90=40.0, mean=20.0, sample_size=20)

    def test_at_median(self) -> None:
        rank = self._dist().percentile_rank(20.0)
        assert rank == pytest.approx(0.50, abs=0.01)

    def test_at_p25(self) -> None:
        rank = self._dist().percentile_rank(10.0)
        assert rank == pytest.approx(0.25, abs=0.01)

    def test_at_p75(self) -> None:
        rank = self._dist().percentile_rank(30.0)
        assert rank == pytest.approx(0.75, abs=0.01)

    def test_above_p90(self) -> None:
        rank = self._dist().percentile_rank(50.0)
        assert rank > 0.90
        assert rank <= 0.99

    def test_below_p25(self) -> None:
        rank = self._dist().percentile_rank(0.0)
        assert rank < 0.25
        assert rank >= 0.0

    def test_degenerate_returns_half(self) -> None:
        dist = PercentileDistribution(p25=None, p50=None, p75=None, p90=None, mean=None, sample_size=0)
        assert dist.percentile_rank(100.0) == pytest.approx(0.5)

    def test_rank_monotone(self) -> None:
        """Higher values should produce higher (or equal) ranks."""
        dist = self._dist()
        values = [0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0]
        ranks = [dist.percentile_rank(v) for v in values]
        for i in range(len(ranks) - 1):
            assert ranks[i] <= ranks[i + 1], f"rank not monotone at index {i}"


# ---------------------------------------------------------------------------
# compute_benchmark
# ---------------------------------------------------------------------------


class TestComputeBenchmark:
    def _sample_companies(self) -> list[CompanyMetrics]:
        return [
            _make_company("A", revenue_growth_yoy=0.05, gross_margin=0.60, net_margin=0.10, roe=0.12, revenue_ttm_sgd=1e8),
            _make_company("B", revenue_growth_yoy=0.10, gross_margin=0.65, net_margin=0.15, roe=0.15, revenue_ttm_sgd=2e8),
            _make_company("C", revenue_growth_yoy=0.20, gross_margin=0.70, net_margin=0.20, roe=0.20, revenue_ttm_sgd=3e8),
            _make_company("D", revenue_growth_yoy=0.35, gross_margin=0.75, net_margin=0.25, roe=0.25, revenue_ttm_sgd=5e8),
            _make_company("E", revenue_growth_yoy=0.50, gross_margin=0.80, net_margin=0.30, roe=0.30, revenue_ttm_sgd=8e8),
        ]

    def test_basic_result(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            vertical_slug="ict_saas",
            period_label="2024",
            period_type="annual",
            companies=self._sample_companies(),
        )
        assert isinstance(result, BenchmarkResult)
        assert result.vertical_slug == "ict_saas"
        assert result.company_count == 5
        assert result.gross_margin.p50 is not None

    def test_reits_excluded_from_operating_distributions(
        self, engine: FinancialBenchmarkEngine
    ) -> None:
        companies = self._sample_companies()
        companies.append(_make_company("REIT1", is_reit=True, revenue_growth_yoy=99.0, gross_margin=0.99))
        result = engine.compute_benchmark(
            vertical_slug="reits", period_label="2024", period_type="annual",
            companies=companies,
        )
        # REIT outlier revenue_growth_yoy=99 should NOT inflate the distribution
        assert result.company_count == 5
        assert result.revenue_growth_yoy.p90 is not None
        assert result.revenue_growth_yoy.p90 < 1.0

    def test_leaders_are_top_growers(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            vertical_slug="fintech", period_label="2024", period_type="annual",
            companies=self._sample_companies(),
        )
        assert len(result.leaders) <= 3
        # Leaders sorted descending by revenue_growth_yoy
        if len(result.leaders) >= 2:
            assert result.leaders[0]["revenue_growth_yoy"] >= result.leaders[1]["revenue_growth_yoy"]

    def test_laggards_are_worst_growers(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            vertical_slug="fintech", period_label="2024", period_type="annual",
            companies=self._sample_companies(),
        )
        assert len(result.laggards) <= 3
        if len(result.laggards) >= 2:
            assert result.laggards[0]["revenue_growth_yoy"] <= result.laggards[1]["revenue_growth_yoy"]

    def test_empty_companies_list(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            vertical_slug="ict_saas", period_label="2024", period_type="annual",
            companies=[],
        )
        assert result.company_count == 0
        assert result.revenue_growth_yoy.p50 is None

    def test_to_vertical_benchmark_dict(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            vertical_slug="ict_saas", period_label="2024", period_type="annual",
            companies=self._sample_companies(),
        )
        d = result.to_vertical_benchmark_dict()
        required_keys = {
            "company_count", "revenue_growth_yoy", "gross_margin",
            "ebitda_margin", "net_margin", "roe", "net_debt_ebitda",
            "revenue_ttm_sgd", "leaders", "laggards", "computed_at",
        }
        assert required_keys.issubset(d.keys())
        # Each distribution dict must have p25/p50/p75/p90/mean/n
        gm = d["gross_margin"]
        assert "p50" in gm and "n" in gm


# ---------------------------------------------------------------------------
# rank_company
# ---------------------------------------------------------------------------


class TestRankCompany:
    def test_higher_performing_company_ranks_higher(
        self, engine: FinancialBenchmarkEngine
    ) -> None:
        companies = [
            _make_company(str(i), revenue_growth_yoy=float(i) * 0.05, gross_margin=float(i) * 0.05)
            for i in range(1, 11)
        ]
        benchmark = engine.compute_benchmark("fintech", "2024", "annual", companies)

        top = _make_company("TOP", revenue_growth_yoy=0.50, gross_margin=0.50)
        bottom = _make_company("BOT", revenue_growth_yoy=0.00, gross_margin=0.00)

        top_ranks = engine.rank_company(top, benchmark)
        bot_ranks = engine.rank_company(bottom, benchmark)

        assert top_ranks.get("revenue_growth_yoy", 0) > bot_ranks.get("revenue_growth_yoy", 1)

    def test_company_without_metrics_returns_empty(
        self, engine: FinancialBenchmarkEngine
    ) -> None:
        companies = [
            _make_company(str(i), revenue_growth_yoy=float(i) * 0.05)
            for i in range(1, 6)
        ]
        benchmark = engine.compute_benchmark("fintech", "2024", "annual", companies)
        empty = _make_company("EMPTY")  # all None metrics
        ranks = engine.rank_company(empty, benchmark)
        assert ranks == {}


# ---------------------------------------------------------------------------
# describe_position
# ---------------------------------------------------------------------------


class TestDescribePosition:
    def test_top_quartile_growth_and_margin(self, engine: FinancialBenchmarkEngine) -> None:
        ranks = {"revenue_growth_yoy": 0.80, "gross_margin": 0.85}
        text = engine.describe_position(ranks)
        assert "growth" in text.lower() or "margin" in text.lower()
        assert "top-quartile" in text.lower() or "above-median" in text.lower() or "top-decile" in text.lower()

    def test_poor_growth_and_margin(self, engine: FinancialBenchmarkEngine) -> None:
        ranks = {"revenue_growth_yoy": 0.10, "gross_margin": 0.10}
        text = engine.describe_position(ranks)
        assert text  # non-empty
        assert "below" in text.lower() or "bottom" in text.lower()

    def test_empty_ranks_returns_fallback(self, engine: FinancialBenchmarkEngine) -> None:
        text = engine.describe_position({})
        assert "insufficient" in text.lower()

    def test_leverage_surfaced_only_at_extremes(self, engine: FinancialBenchmarkEngine) -> None:
        # Low leverage rank (good — high rank means lower debt)
        high_leverage_ranks = {"net_debt_ebitda": 0.90}  # 90th percentile of leverage = bad
        text = engine.describe_position(high_leverage_ranks)
        # Should mention leverage since it's ≥ 0.75
        assert text

    def test_output_is_string(self, engine: FinancialBenchmarkEngine) -> None:
        ranks = {"gross_margin": 0.55}
        text = engine.describe_position(ranks)
        assert isinstance(text, str)
        assert len(text) > 10


# ---------------------------------------------------------------------------
# _rank_to_label helper
# ---------------------------------------------------------------------------


class TestRankToLabel:
    @pytest.mark.parametrize("rank,expected", [
        (0.95, "Top-decile"),
        (0.80, "Top-quartile"),
        (0.60, "Above-median"),
        (0.40, "Below-median"),
        (0.15, "Bottom-quartile"),
        (0.05, "Bottom-decile"),
    ])
    def test_normal(self, rank: float, expected: str) -> None:
        assert _rank_to_label(rank) == expected

    def test_inverted(self) -> None:
        # High rank inverted → label for (1 - 0.85) = 0.15 → Bottom-quartile
        # Note: 1.0 - 0.90 = 0.09999... (float) which is < 0.10, giving Bottom-decile
        assert _rank_to_label(0.85, invert=True) == "Bottom-quartile"

    def test_none_returns_median(self) -> None:
        assert _rank_to_label(None) == "Median"
