"""Unit tests for capex_to_revenue extension in financial_benchmarks.py."""

from __future__ import annotations

import pytest

from packages.scoring.src.financial_benchmarks import (
    OUTLIER_BOUNDS,
    CompanyMetrics,
    FinancialBenchmarkEngine,
)


@pytest.fixture
def engine() -> FinancialBenchmarkEngine:
    return FinancialBenchmarkEngine()


def _make_company_gtm(
    ticker: str,
    *,
    revenue_growth_yoy: float = 0.10,
    gross_margin: float = 0.60,
    sga_to_revenue: float | None = None,
    rnd_to_revenue: float | None = None,
    operating_margin: float | None = None,
    capex_to_revenue: float | None = None,
) -> CompanyMetrics:
    return CompanyMetrics(
        ticker=ticker,
        name=ticker,
        is_reit=False,
        revenue_growth_yoy=revenue_growth_yoy,
        gross_margin=gross_margin,
        ebitda_margin=0.25,
        net_margin=0.15,
        roe=0.18,
        net_debt_ebitda=1.0,
        revenue_ttm_sgd=1e8,
        sga_to_revenue=sga_to_revenue,
        rnd_to_revenue=rnd_to_revenue,
        operating_margin=operating_margin,
        capex_to_revenue=capex_to_revenue,
    )


# ---------------------------------------------------------------------------
# capex_to_revenue in OUTLIER_BOUNDS
# ---------------------------------------------------------------------------


class TestOutlierBounds:
    def test_capex_to_revenue_bounds_exist(self) -> None:
        assert "capex_to_revenue" in OUTLIER_BOUNDS
        lo, hi = OUTLIER_BOUNDS["capex_to_revenue"]
        assert lo == 0.0
        assert hi == 1.0


# ---------------------------------------------------------------------------
# capex_to_revenue in compute_benchmark
# ---------------------------------------------------------------------------


class TestCapexBenchmark:
    def _sample_companies(self) -> list[CompanyMetrics]:
        return [
            _make_company_gtm("A", capex_to_revenue=0.03, sga_to_revenue=0.30, operating_margin=0.20),
            _make_company_gtm("B", capex_to_revenue=0.05, sga_to_revenue=0.35, operating_margin=0.22),
            _make_company_gtm("C", capex_to_revenue=0.08, sga_to_revenue=0.40, operating_margin=0.25),
            _make_company_gtm("D", capex_to_revenue=0.12, sga_to_revenue=0.45, operating_margin=0.28),
            _make_company_gtm("E", capex_to_revenue=0.20, sga_to_revenue=0.50, operating_margin=0.30),
        ]

    def test_capex_distribution_computed(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            "ict_saas", "2024", "annual", self._sample_companies()
        )
        assert result.capex_to_revenue.p50 is not None
        assert result.capex_to_revenue.sample_size == 5

    def test_capex_outlier_filtering(self, engine: FinancialBenchmarkEngine) -> None:
        """capex_to_revenue > 1.0 should be filtered out."""
        companies = self._sample_companies()
        companies.append(_make_company_gtm("MEGA", capex_to_revenue=1.20))
        result = engine.compute_benchmark("ict_saas", "2024", "annual", companies)
        assert result.capex_to_revenue.sample_size == 5  # 1.20 excluded

    def test_none_capex_excluded(self, engine: FinancialBenchmarkEngine) -> None:
        companies = self._sample_companies()
        companies.append(_make_company_gtm("NOCAP", capex_to_revenue=None))
        result = engine.compute_benchmark("ict_saas", "2024", "annual", companies)
        assert result.capex_to_revenue.sample_size == 5  # None excluded

    def test_rank_company_includes_capex(self, engine: FinancialBenchmarkEngine) -> None:
        companies = self._sample_companies()
        benchmark = engine.compute_benchmark("ict_saas", "2024", "annual", companies)
        target = companies[0]  # lowest capex
        ranks = engine.rank_company(target, benchmark)
        assert "capex_to_revenue" in ranks
        # Lowest capex should rank below median
        assert ranks["capex_to_revenue"] < 0.5

    def test_serialisation_includes_capex(self, engine: FinancialBenchmarkEngine) -> None:
        result = engine.compute_benchmark(
            "ict_saas", "2024", "annual", self._sample_companies()
        )
        d = result.to_vertical_benchmark_dict()
        assert "capex_to_revenue" in d
        assert d["capex_to_revenue"]["n"] == 5

    def test_describe_position_surfaces_high_capex(self, engine: FinancialBenchmarkEngine) -> None:
        """High capex rank should produce a capacity investment narrative."""
        ranks = {"revenue_growth_yoy": 0.60, "gross_margin": 0.60, "capex_to_revenue": 0.85}
        text = engine.describe_position(ranks)
        assert "capex" in text.lower()

    def test_describe_position_low_capex_no_mention(self, engine: FinancialBenchmarkEngine) -> None:
        """Low capex rank should NOT produce a capex narrative (only surfaces at top quartile)."""
        ranks = {"revenue_growth_yoy": 0.60, "gross_margin": 0.60, "capex_to_revenue": 0.30}
        text = engine.describe_position(ranks)
        assert "capex" not in text.lower()


# ---------------------------------------------------------------------------
# Full pipeline: compute → rank → describe with all GTM metrics
# ---------------------------------------------------------------------------


class TestFullGTMPipeline:
    def test_end_to_end_with_all_gtm_metrics(self, engine: FinancialBenchmarkEngine) -> None:
        companies = [
            _make_company_gtm(
                f"CO{i}",
                sga_to_revenue=0.20 + i * 0.05,
                rnd_to_revenue=0.05 + i * 0.03,
                operating_margin=0.10 + i * 0.03,
                capex_to_revenue=0.02 + i * 0.02,
            )
            for i in range(6)
        ]
        benchmark = engine.compute_benchmark("ict_saas", "2024", "annual", companies)

        # All distributions should be valid
        assert benchmark.sga_to_revenue.p50 is not None
        assert benchmark.rnd_to_revenue.p50 is not None
        assert benchmark.operating_margin.p50 is not None
        assert benchmark.capex_to_revenue.p50 is not None

        # Rank top company
        top = companies[-1]
        ranks = engine.rank_company(top, benchmark)
        assert "sga_to_revenue" in ranks
        assert "rnd_to_revenue" in ranks
        assert "operating_margin" in ranks
        assert "capex_to_revenue" in ranks

        # Describe position
        text = engine.describe_position(ranks)
        assert isinstance(text, str)
        assert len(text) > 20
