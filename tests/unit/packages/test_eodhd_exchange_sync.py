"""Unit tests for sync_exchange_financials / sync_sp500_financials skip-predicate logic.

Tests the cutoff check:
    company.last_synced_at and company.last_synced_at > cutoff
where cutoff = datetime.now(UTC) - timedelta(days=7).

Both sync_exchange_financials and sync_sp500_financials share this predicate.
No database or async infrastructure is needed — the predicate is pure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helper: the exact predicate extracted from sync_exchange_financials
# ---------------------------------------------------------------------------

def _cutoff() -> datetime:
    """Reproduce the cutoff formula from sync_exchange_financials / sync_sp500_financials.

    The implementation strips tzinfo so the comparison works against SQLite's
    naive datetimes.  Tests use the same naive cutoff.
    """
    return (datetime.now(UTC) - timedelta(days=7)).replace(tzinfo=None)


def _should_skip(company: MagicMock, cutoff: datetime) -> bool:
    """Return True when the company was synced recently enough to skip.

    Mirrors the production code: strips tzinfo from last_synced_at before
    comparing so both sides are naive UTC datetimes.
    """
    last_synced = company.last_synced_at
    if last_synced is not None:
        last_synced = last_synced.replace(tzinfo=None)
    return bool(last_synced and last_synced > cutoff)


def _make_company(last_synced_at: datetime | None) -> MagicMock:
    """Create a minimal ListedCompany stand-in with the given last_synced_at."""
    company = MagicMock()
    company.last_synced_at = last_synced_at
    return company


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncExchangeFinancialsSkipLogic:
    """Verify the skip predicate for recently-synced companies."""

    @pytest.mark.unit
    def test_recent_company_is_skipped(self) -> None:
        """A company synced 1 day ago is within the 7-day window and should be skipped."""
        cutoff = _cutoff()
        company = _make_company(last_synced_at=datetime.now(UTC) - timedelta(days=1))
        assert _should_skip(company, cutoff) is True

    @pytest.mark.unit
    def test_old_company_is_not_skipped(self) -> None:
        """A company synced 8 days ago is outside the window and should not be skipped."""
        cutoff = _cutoff()
        company = _make_company(last_synced_at=datetime.now(UTC) - timedelta(days=8))
        assert _should_skip(company, cutoff) is False

    @pytest.mark.unit
    def test_exactly_7_days_ago_is_not_skipped(self) -> None:
        """Boundary condition: synced exactly 7 days ago equals the cutoff.

        The predicate uses strict '>' so equality must NOT be skipped.
        """
        # Use the same cutoff the predicate would use, then set last_synced_at
        # to something equal to (not greater than) that cutoff.
        cutoff = _cutoff()
        company = _make_company(last_synced_at=cutoff)
        assert _should_skip(company, cutoff) is False

    @pytest.mark.unit
    def test_none_last_synced_at_is_not_skipped(self) -> None:
        """A company that has never been synced (last_synced_at=None) must not be skipped."""
        cutoff = _cutoff()
        company = _make_company(last_synced_at=None)
        assert _should_skip(company, cutoff) is False

    @pytest.mark.unit
    def test_cutoff_is_7_days_before_now(self) -> None:
        """The cutoff formula should produce a naive timestamp ~7 days in the past."""
        before = datetime.now(UTC).replace(tzinfo=None)
        cutoff = _cutoff()
        after = datetime.now(UTC).replace(tzinfo=None)

        assert cutoff.tzinfo is None, "cutoff must be naive (no tzinfo)"
        expected_delta = timedelta(days=7)
        lower_bound = before - expected_delta - timedelta(seconds=1)
        upper_bound = after - expected_delta + timedelta(seconds=1)

        assert lower_bound <= cutoff <= upper_bound


# ---------------------------------------------------------------------------
# Helper: classification logic from deactivate_stub_listings
# ---------------------------------------------------------------------------

def _classify(ticker: str, name: str) -> bool:
    """Return True if the listing should be deactivated.

    Mirrors the logic in FinancialIntelligenceSync.deactivate_stub_listings():
    - stub: name is identical to ticker
    - derived: name contains any of the derived-security keywords
    """
    KEYWORDS = [
        " pref", "preference", " sdr ", "sdr 1", " warrant", " rights",
        " notes", "structured product", "etf ", " trust cert",
    ]
    is_stub = name == ticker
    is_derived = any(kw in name.lower() for kw in KEYWORDS)
    return is_stub or is_derived


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeactivateStubListings:
    """Verify the stub / derived-security classification logic."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "ticker, name, expected",
        [
            # 1. Pure stub: name equals ticker
            ("A93", "A93", True),
            # 2. Pure stub: another ticker-equals-name example
            ("CXU", "CXU", True),
            # 3. Real company: should be kept active
            ("G50", "GRAND BANKS YACHTS LIMITED", False),
            # 4. Real company: should be kept active
            ("40B", "HEALTHBANK HOLDINGS LIMITED", False),
            # 5. Preference share: contains " pref"
            ("N2H", "HYFLUX 6% CUM PREF CLASS A 10", True),
            # 6. SDR: contains " sdr " (and "sdr 1" variant covered by same entry)
            ("HJDD", "h JD HK SDR 10to1", True),
            # 7. Warrant: contains " warrant"
            ("XYZ", "SOME COMPANY WARRANT 2025", True),
            # 8. Rights issue: contains " rights"
            ("ABC", "ABC RIGHTS ISSUE 2024", True),
        ],
    )
    def test_classify(self, ticker: str, name: str, expected: bool) -> None:
        """Each (ticker, name) pair should classify to the expected deactivation flag."""
        assert _classify(ticker, name) is expected


# ---------------------------------------------------------------------------
# _validated_sga_ratio — EODHD SGA data quality correction
# ---------------------------------------------------------------------------

from packages.integrations.eodhd.src.sync import _validated_sga_ratio


class TestValidatedSgaRatio:
    """Tests for the SGA validation/correction function.

    EODHD sometimes reports partial SGA (e.g. only "Selling" without
    "General & Administrative"). The function detects and corrects this
    using the income statement identity: GP - OpInc >= SGA + R&D.
    """

    @pytest.mark.unit
    def test_anomalous_sga_is_corrected(self) -> None:
        """When reported SGA is < 40% of implied, use the implied value."""
        # AAPL-like: reported 2B, implied ~7.17B
        ratio = _validated_sga_ratio(
            reported_sga=2.07e9,
            gross_profit=58.27e9,
            operating_income=42.83e9,
            research_development=8.27e9,
            revenue=124.3e9,
        )
        assert ratio is not None
        assert abs(ratio - 0.0577) < 0.001

    @pytest.mark.unit
    def test_normal_sga_kept_as_reported(self) -> None:
        """When reported SGA is >= 60% of implied, keep reported."""
        ratio = _validated_sga_ratio(
            reported_sga=7.0e9,
            gross_profit=42.27e9,
            operating_income=27.9e9,
            research_development=7.9e9,
            revenue=90.75e9,
        )
        # Should be reported_sga / revenue = 7/90.75 ≈ 7.7%
        assert ratio is not None
        assert abs(ratio - 7.0e9 / 90.75e9) < 0.0001

    @pytest.mark.unit
    def test_none_sga_returns_none(self) -> None:
        """Genuinely null SGA (company doesn't report it) → None."""
        ratio = _validated_sga_ratio(
            reported_sga=None,
            gross_profit=10e9,
            operating_income=5e9,
            research_development=None,
            revenue=20e9,
        )
        assert ratio is None

    @pytest.mark.unit
    def test_no_gp_or_opinc_uses_reported(self) -> None:
        """Without GP or OpInc, can't cross-check — use reported."""
        ratio = _validated_sga_ratio(
            reported_sga=3e9,
            gross_profit=None,
            operating_income=None,
            research_development=None,
            revenue=30e9,
        )
        assert ratio is not None
        assert abs(ratio - 0.10) < 0.001

    @pytest.mark.unit
    def test_zero_revenue_returns_none(self) -> None:
        """Zero revenue → cannot compute ratio."""
        ratio = _validated_sga_ratio(
            reported_sga=1e9,
            gross_profit=5e9,
            operating_income=2e9,
            research_development=0,
            revenue=0,
        )
        assert ratio is None

    @pytest.mark.unit
    def test_negative_implied_sga_uses_reported(self) -> None:
        """When OpInc > GP (unusual), fall back to reported."""
        ratio = _validated_sga_ratio(
            reported_sga=1e9,
            gross_profit=5e9,
            operating_income=6e9,
            research_development=0,
            revenue=20e9,
        )
        # Falls back to reported: 1/20 = 5%
        assert ratio is not None
        assert abs(ratio - 0.05) < 0.001

    @pytest.mark.unit
    def test_zero_reported_sga_is_corrected(self) -> None:
        """SGA = 0 with positive implied → corrected."""
        ratio = _validated_sga_ratio(
            reported_sga=0,
            gross_profit=10e9,
            operating_income=5e9,
            research_development=2e9,
            revenue=20e9,
        )
        # implied = 10 - 5 - 2 = 3B, ratio = 3/20 = 15%
        assert ratio is not None
        assert abs(ratio - 0.15) < 0.001

    @pytest.mark.unit
    def test_sga_at_60pct_threshold_kept(self) -> None:
        """SGA exactly at the 60% boundary is kept as reported."""
        # implied = 10 - 5 - 2 = 3B; 60% of 3B = 1.8B
        ratio = _validated_sga_ratio(
            reported_sga=1.8e9,  # exactly 60%
            gross_profit=10e9,
            operating_income=5e9,
            research_development=2e9,
            revenue=20e9,
        )
        # Should keep reported: 1.8/20 = 9%
        assert ratio is not None
        assert abs(ratio - 0.09) < 0.001

    @pytest.mark.unit
    def test_sga_just_below_threshold_corrected(self) -> None:
        """SGA just below 60% boundary is corrected."""
        ratio = _validated_sga_ratio(
            reported_sga=1.79e9,  # just below 60% of 3B
            gross_profit=10e9,
            operating_income=5e9,
            research_development=2e9,
            revenue=20e9,
        )
        # implied = 3B, ratio = 3/20 = 15%
        assert ratio is not None
        assert abs(ratio - 0.15) < 0.001

    @pytest.mark.unit
    def test_implied_ratio_exceeding_100pct_returns_none(self) -> None:
        """If correction would produce ratio > 100%, return None."""
        ratio = _validated_sga_ratio(
            reported_sga=100,
            gross_profit=25e9,
            operating_income=1e9,
            research_development=1e9,
            revenue=20e9,  # implied = 25 - 1 - 1 = 23B → 115% of rev
        )
        assert ratio is None

    @pytest.mark.unit
    def test_no_rd_implied_uses_gp_minus_opinc(self) -> None:
        """Without R&D, implied SGA = GP - OpInc."""
        ratio = _validated_sga_ratio(
            reported_sga=1e9,
            gross_profit=10e9,
            operating_income=5e9,
            research_development=None,
            revenue=20e9,
        )
        # implied = 10 - 5 - 0 = 5B; reported 1B < 5B*0.6 → corrected
        # corrected ratio = 5/20 = 25%
        assert ratio is not None
        assert abs(ratio - 0.25) < 0.001
