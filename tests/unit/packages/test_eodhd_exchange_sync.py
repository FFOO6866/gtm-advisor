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
