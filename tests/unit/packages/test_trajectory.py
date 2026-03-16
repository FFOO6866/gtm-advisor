"""Unit tests for packages/scoring/src/trajectory.py."""

from __future__ import annotations

import pytest

from packages.scoring.src.trajectory import TrajectoryEngine


@pytest.fixture
def engine() -> TrajectoryEngine:
    return TrajectoryEngine()


def _make_snapshot(
    period: str,
    revenue: float | None = None,
    gross_margin: float | None = None,
    operating_margin: float | None = None,
    net_margin: float | None = None,
    sga_to_revenue: float | None = None,
    rnd_to_revenue: float | None = None,
    free_cash_flow: float | None = None,
    revenue_growth_yoy: float | None = None,
    ticker: str = "TEST",
    name: str = "Test Co",
) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "period_end_date": period,
        "revenue": revenue,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "sga_to_revenue": sga_to_revenue,
        "rnd_to_revenue": rnd_to_revenue,
        "free_cash_flow": free_cash_flow,
        "revenue_growth_yoy": revenue_growth_yoy,
    }


# ---------------------------------------------------------------------------
# Insufficient data
# ---------------------------------------------------------------------------


class TestInsufficientData:
    def test_empty_snapshots(self, engine: TrajectoryEngine) -> None:
        report = engine.compute([])
        assert report.trajectory_class == "INSUFFICIENT_DATA"
        assert report.periods_analyzed == 0

    def test_one_period(self, engine: TrajectoryEngine) -> None:
        report = engine.compute([_make_snapshot("2024-12-31", revenue=1e6)])
        assert report.trajectory_class == "INSUFFICIENT_DATA"
        assert report.periods_analyzed == 1

    def test_two_periods(self, engine: TrajectoryEngine) -> None:
        report = engine.compute([
            _make_snapshot("2023-12-31", revenue=1e6),
            _make_snapshot("2024-12-31", revenue=1.2e6),
        ])
        assert report.trajectory_class == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# CAGR
# ---------------------------------------------------------------------------


class TestCAGR:
    def test_cagr_3y(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot("2020-12-31", revenue=100.0),
            _make_snapshot("2021-12-31", revenue=110.0),
            _make_snapshot("2022-12-31", revenue=121.0),
            _make_snapshot("2023-12-31", revenue=133.1),
        ]
        report = engine.compute(snapshots)
        assert report.revenue_cagr_3y is not None
        assert report.revenue_cagr_3y == pytest.approx(0.10, abs=0.01)

    def test_cagr_5y(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(f"{year}-12-31", revenue=100.0 * (1.15 ** i))
            for i, year in enumerate(range(2019, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.revenue_cagr_5y is not None
        assert report.revenue_cagr_5y == pytest.approx(0.15, abs=0.01)

    def test_cagr_negative_revenue_returns_none(self, engine: TrajectoryEngine) -> None:
        """Cannot compute CAGR with negative starting revenue."""
        snapshots = [
            _make_snapshot("2020-12-31", revenue=-100.0),
            _make_snapshot("2021-12-31", revenue=50.0),
            _make_snapshot("2022-12-31", revenue=100.0),
            _make_snapshot("2023-12-31", revenue=150.0),
        ]
        report = engine.compute(snapshots)
        assert report.revenue_cagr_3y is None

    def test_cagr_zero_start_returns_none(self, engine: TrajectoryEngine) -> None:
        result = engine._cagr(0.0, 100.0, 3)
        assert result is None

    def test_cagr_with_gaps_too_few_valid(self, engine: TrajectoryEngine) -> None:
        """When fewer than 4 valid revenues, CAGR_3y is None."""
        snapshots = [
            _make_snapshot("2019-12-31", revenue=100.0),
            _make_snapshot("2020-12-31", revenue=None),   # gap
            _make_snapshot("2021-12-31", revenue=None),   # gap
            _make_snapshot("2022-12-31", revenue=121.0),
            _make_snapshot("2023-12-31", revenue=133.1),
        ]
        report = engine.compute(snapshots)
        # valid entries = [(0, 100), (3, 121), (4, 133.1)] — only 3, need 4
        assert report.revenue_cagr_3y is None

    def test_cagr_with_gaps_uses_actual_year_span(self, engine: TrajectoryEngine) -> None:
        """CAGR computes using actual year difference from period_end_date, not array index."""
        snapshots = [
            _make_snapshot("2019-12-31", revenue=100.0),
            _make_snapshot("2020-12-31", revenue=110.0),
            _make_snapshot("2021-12-31", revenue=None),   # gap — missing year
            _make_snapshot("2022-12-31", revenue=None),   # gap — missing year
            _make_snapshot("2023-12-31", revenue=133.1),
            _make_snapshot("2024-12-31", revenue=146.4),
        ]
        report = engine.compute(snapshots)
        # valid = [(0, 100), (1, 110), (4, 133.1), (5, 146.4)]
        # 3y CAGR: start=(1, 110), end=(5, 146.4), year_span = 2024-2020 = 4 years
        # CAGR = (146.4/110)^(1/4) - 1 ≈ 7.4%
        assert report.revenue_cagr_3y is not None
        assert report.revenue_cagr_3y == pytest.approx(0.074, abs=0.01)


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------


class TestTrend:
    def test_expanding_trend(self, engine: TrajectoryEngine) -> None:
        values = [0.10, 0.15, 0.20, 0.25, 0.30]
        assert engine._trend(values) == "expanding"

    def test_compressing_trend(self, engine: TrajectoryEngine) -> None:
        values = [0.30, 0.25, 0.20, 0.15, 0.10]
        assert engine._trend(values) == "compressing"

    def test_stable_trend(self, engine: TrajectoryEngine) -> None:
        values = [0.20, 0.20, 0.21, 0.20, 0.20]
        assert engine._trend(values) == "stable"

    def test_none_values_ignored(self, engine: TrajectoryEngine) -> None:
        values = [0.10, None, 0.15, None, 0.20, 0.25, 0.30]
        assert engine._trend(values) == "expanding"

    def test_too_few_values_returns_stable(self, engine: TrajectoryEngine) -> None:
        assert engine._trend([0.1, 0.2]) == "stable"


# ---------------------------------------------------------------------------
# Acceleration
# ---------------------------------------------------------------------------


class TestAcceleration:
    def test_accelerating(self, engine: TrajectoryEngine) -> None:
        growth_rates = [0.05, 0.08, 0.12, 0.18, 0.25]
        assert engine._acceleration(growth_rates) == "accelerating"

    def test_decelerating(self, engine: TrajectoryEngine) -> None:
        growth_rates = [0.25, 0.20, 0.15, 0.10, 0.05]
        assert engine._acceleration(growth_rates) == "decelerating"

    def test_stable_growth(self, engine: TrajectoryEngine) -> None:
        growth_rates = [0.10, 0.11, 0.10, 0.11, 0.10]
        assert engine._acceleration(growth_rates) == "stable"


# ---------------------------------------------------------------------------
# Overall classification
# ---------------------------------------------------------------------------


class TestClassify:
    def test_accelerating_classification(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (1.10 ** i),
                revenue_growth_yoy=0.05 + i * 0.05,
                gross_margin=0.60 + i * 0.02,
                operating_margin=0.15 + i * 0.02,
                net_margin=0.10,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.trajectory_class == "ACCELERATING"

    def test_stable_classification(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (1.08 ** i),
                revenue_growth_yoy=0.08,
                gross_margin=0.55,
                operating_margin=0.20,
                net_margin=0.10,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.trajectory_class == "STABLE"

    def test_decelerating_classification(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (0.97 ** i),
                revenue_growth_yoy=0.10 - i * 0.05,
                gross_margin=0.50 - i * 0.02,
                operating_margin=0.15 - i * 0.03,
                net_margin=0.08,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.trajectory_class == "DECELERATING"

    def test_turnaround_classification(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (0.95 ** i),
                revenue_growth_yoy=-0.05,
                gross_margin=0.30 + i * 0.05,
                operating_margin=0.05 + i * 0.04,
                net_margin=0.02,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.trajectory_class == "TURNAROUND"


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------


class TestNarrative:
    def test_narrative_is_nonempty_string(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (1.10 ** i),
                revenue_growth_yoy=0.10,
                gross_margin=0.60,
                operating_margin=0.20,
                net_margin=0.10,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert isinstance(report.narrative, str)
        assert len(report.narrative) > 20

    def test_insufficient_data_narrative(self, engine: TrajectoryEngine) -> None:
        report = engine.compute([_make_snapshot("2024-12-31", revenue=1e6)])
        assert "insufficient" in report.narrative.lower()


# ---------------------------------------------------------------------------
# to_dict serialisation
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_has_all_keys(self, engine: TrajectoryEngine) -> None:
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (1.10 ** i),
                revenue_growth_yoy=0.10,
                gross_margin=0.60,
                operating_margin=0.20,
                net_margin=0.10,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        d = report.to_dict()
        expected_keys = {
            "ticker", "name", "periods_analyzed",
            "revenue_cagr_3y", "revenue_cagr_5y", "acceleration",
            "gross_margin_trend", "operating_margin_trend", "net_margin_trend",
            "sga_efficiency_trend", "rnd_intensity_trend",
            "fcf_conversion_trend",
            "trajectory_class", "narrative",
        }
        assert expected_keys.issubset(d.keys())


# ---------------------------------------------------------------------------
# GTM efficiency (SG&A)
# ---------------------------------------------------------------------------


class TestGTMEfficiency:
    def test_improving_sga_efficiency(self, engine: TrajectoryEngine) -> None:
        """Declining SG&A ratio = improving efficiency."""
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (1.10 ** i),
                sga_to_revenue=0.40 - i * 0.03,
                revenue_growth_yoy=0.10,
                gross_margin=0.60,
                operating_margin=0.20,
                net_margin=0.10,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.sga_efficiency_trend == "improving"

    def test_declining_sga_efficiency(self, engine: TrajectoryEngine) -> None:
        """Rising SG&A ratio = declining efficiency."""
        snapshots = [
            _make_snapshot(
                f"{year}-12-31",
                revenue=100.0 * (1.10 ** i),
                sga_to_revenue=0.20 + i * 0.04,
                revenue_growth_yoy=0.10,
                gross_margin=0.60,
                operating_margin=0.20,
                net_margin=0.10,
            )
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.sga_efficiency_trend == "declining"

    def test_all_none_metrics_except_revenue(self, engine: TrajectoryEngine) -> None:
        """Snapshots with only revenue — all other metrics None — should not crash."""
        snapshots = [
            _make_snapshot(f"{year}-12-31", revenue=100.0 * (1.10 ** i))
            for i, year in enumerate(range(2020, 2025))
        ]
        report = engine.compute(snapshots)
        assert report.trajectory_class == "STABLE"
        assert report.gross_margin_trend == "stable"
        assert report.sga_efficiency_trend == "stable"
        assert report.fcf_conversion_trend == "stable"
