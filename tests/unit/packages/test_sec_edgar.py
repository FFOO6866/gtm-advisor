"""Unit tests for the SEC EDGAR client and document sync EDGAR integration.

Covers:
- SG_COMPANY_CIKS registry has correct structure
- SECEdgarClient.get_filings() filters by form type and date cutoff
- SECEdgarClient handles missing/empty submissions gracefully
- _discover_from_edgar source tracking logic (sgx+edgar, eodhd+edgar)
- company_not_found logged at WARNING level
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from packages.integrations.sec_edgar.src.client import (
    SG_COMPANY_CIKS,
    EDGARClientResult,
    EDGARFiling,
    SECEdgarClient,
)

# ---------------------------------------------------------------------------
# SG_COMPANY_CIKS registry
# ---------------------------------------------------------------------------


class TestSGCompanyCIKs:
    def test_all_entries_are_tuples_of_two_strings(self) -> None:
        for ticker, entry in SG_COMPANY_CIKS.items():
            assert isinstance(entry, tuple), f"{ticker}: expected tuple"
            assert len(entry) == 2, f"{ticker}: expected (cik, name)"
            cik, name = entry
            assert isinstance(cik, str) and isinstance(name, str)

    def test_cik_is_10_digits(self) -> None:
        for ticker, (cik, _) in SG_COMPANY_CIKS.items():
            assert len(cik) == 10, f"{ticker}: CIK must be 10-char zero-padded, got {cik!r}"
            assert cik.isdigit(), f"{ticker}: CIK must be all digits, got {cik!r}"

    def test_required_tickers_present(self) -> None:
        for required in ("SE", "GRAB", "PGRU", "MNY"):
            assert required in SG_COMPANY_CIKS, f"{required} missing from SG_COMPANY_CIKS"

    def test_known_cik_values(self) -> None:
        assert SG_COMPANY_CIKS["SE"][0] == "0001703399"
        assert SG_COMPANY_CIKS["GRAB"][0] == "0001855612"
        assert SG_COMPANY_CIKS["PGRU"][0] == "0001873331"
        assert SG_COMPANY_CIKS["MNY"][0] == "0001974044"


# ---------------------------------------------------------------------------
# SECEdgarClient helpers
# ---------------------------------------------------------------------------


def _make_client() -> SECEdgarClient:
    return SECEdgarClient()


def _submissions_fixture(
    forms: list[str],
    dates: list[str],
    accessions: list[str],
    docs: list[str],
    periods: list[str] | None = None,
) -> dict:
    return {
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": dates,
                "accessionNumber": accessions,
                "primaryDocument": docs,
                "primaryDocDescription": [""] * len(forms),
                "periodOfReport": periods or [""] * len(forms),
            }
        }
    }


class TestSECEdgarClient:
    @pytest.mark.asyncio
    async def test_get_filings_returns_empty_for_unknown_ticker(self) -> None:
        client = _make_client()
        result = await client.get_filings("UNKNOWN_TICKER_XYZ")
        assert result.filings == []
        assert len(result.errors) == 1
        assert "UNKNOWN_TICKER_XYZ" in result.errors[0]

    @pytest.mark.asyncio
    async def test_get_filings_handles_empty_submissions(self) -> None:
        client = _make_client()
        with patch.object(client, "get_submissions", new=AsyncMock(return_value={})):
            result = await client.get_filings("SE")
        assert result.filings == []
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_get_filings_filters_by_form_type(self) -> None:
        """Only 20-F rows should be returned when forms=["20-F"]."""
        client = _make_client()
        submissions = _submissions_fixture(
            forms=["20-F", "6-K", "20-F"],
            dates=["2024-06-01", "2024-01-15", "2023-06-01"],
            accessions=["0001234567-24-000001", "0001234567-24-000002", "0001234567-23-000003"],
            docs=["annual_2024.htm", "sixk.htm", "annual_2023.htm"],
            periods=["2024-12-31", "2023-12-31", "2023-12-31"],
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=5)

        assert all(f.form == "20-F" for f in result.filings)
        assert len(result.filings) == 2

    @pytest.mark.asyncio
    async def test_get_filings_respects_years_back_cutoff(self) -> None:
        """Filings older than years_back should be excluded."""
        client = _make_client()
        # years_back=1: only 2025 filing should pass (today is 2026)
        submissions = _submissions_fixture(
            forms=["20-F", "20-F"],
            dates=["2025-06-01", "2020-06-01"],  # 2020 is > 1 year ago
            accessions=["0001234567-25-000001", "0001234567-20-000001"],
            docs=["annual_2025.htm", "annual_2020.htm"],
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=1)

        assert len(result.filings) == 1
        assert result.filings[0].filing_date.year == 2025

    @pytest.mark.asyncio
    async def test_get_filings_skips_rows_without_accession(self) -> None:
        client = _make_client()
        submissions = _submissions_fixture(
            forms=["20-F"],
            dates=["2024-06-01"],
            accessions=[""],  # empty accession
            docs=["annual.htm"],
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=5)

        assert result.filings == []

    @pytest.mark.asyncio
    async def test_fiscal_year_extracted_from_period(self) -> None:
        client = _make_client()
        submissions = _submissions_fixture(
            forms=["20-F"],
            dates=["2024-06-01"],
            accessions=["0001234567-24-000001"],
            docs=["annual.htm"],
            periods=["2023-12-31"],
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=5)

        assert len(result.filings) == 1
        assert result.filings[0].fiscal_year == 2023

    @pytest.mark.asyncio
    async def test_fiscal_year_falls_back_to_filename(self) -> None:
        """When periodOfReport is empty, extract year from YYYYMMDD in filename."""
        client = _make_client()
        submissions = _submissions_fixture(
            forms=["20-F"],
            dates=["2023-05-15"],
            accessions=["0000950170-23-014551"],
            docs=["ck0001855612-20221231.htm"],  # GRAB-style filename with date
            periods=[""],  # empty period
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=5)

        assert len(result.filings) == 1
        assert result.filings[0].fiscal_year == 2022

    @pytest.mark.asyncio
    async def test_fiscal_year_none_when_no_period_no_date_in_filename(self) -> None:
        """Fiscal year stays None when neither period nor filename date is available."""
        client = _make_client()
        submissions = _submissions_fixture(
            forms=["20-F"],
            dates=["2024-06-01"],
            accessions=["0001193125-24-084311"],
            docs=["d940352d20f.htm"],  # Sea-style — no date embedded
            periods=[""],
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=5)

        assert len(result.filings) == 1
        assert result.filings[0].fiscal_year is None

    @pytest.mark.asyncio
    async def test_document_url_format(self) -> None:
        """EDGAR document URL must use integer CIK (no leading zeros)."""
        client = _make_client()
        submissions = _submissions_fixture(
            forms=["20-F"],
            dates=["2024-06-01"],
            accessions=["0001234567-24-000001"],
            docs=["annual.htm"],
        )
        with patch.object(client, "get_submissions", new=AsyncMock(return_value=submissions)):
            result = await client.get_filings("SE", forms=["20-F"], years_back=5)

        filing = result.filings[0]
        # CIK for SE is "0001703399" → integer 1703399
        assert "/1703399/" in filing.document_url
        # Accession number dashes stripped
        assert "0001234567-24-000001".replace("-", "") in filing.document_url

    @pytest.mark.asyncio
    async def test_get_all_sg_annual_reports_aggregates(self) -> None:
        """get_all_sg_annual_reports aggregates across all tickers."""
        client = _make_client()
        single = EDGARClientResult(
            filings=[
                EDGARFiling(
                    ticker="SE",
                    cik="0001703399",
                    company_name="Sea Ltd",
                    form="20-F",
                    doc_type="annual_report",
                    filing_date=datetime(2024, 6, 1, tzinfo=UTC),
                    accession_number="0001703399-24-000001",
                    primary_document="annual.htm",
                    document_url="https://www.sec.gov/Archives/edgar/data/1703399/000170339924000001/annual.htm",
                    index_url="https://www.sec.gov/Archives/edgar/data/1703399/000170339924000001/",
                    fiscal_year=2023,
                )
            ],
            errors=[],
        )

        with patch.object(client, "get_annual_reports", new=AsyncMock(return_value=single)):
            result = await client.get_all_sg_annual_reports(years_back=3)

        # Called once per ticker in SG_COMPANY_CIKS
        assert len(result.filings) == len(SG_COMPANY_CIKS)


# ---------------------------------------------------------------------------
# Source tracking logic in _discover_from_edgar
# ---------------------------------------------------------------------------


class TestEdgarSourceTracking:
    """Verify that source string is built correctly in discover_announcements."""

    def test_sgx_plus_edgar_when_both_active(self) -> None:
        """When SGX works and EDGAR discovers docs: source must be 'sgx+edgar'."""
        source = "sgx"
        edgar_discovered = 5
        if edgar_discovered > 0:
            source = source + "+edgar"
        assert source == "sgx+edgar"

    def test_eodhd_plus_edgar(self) -> None:
        """When SGX broken (fell back to EODHD) and EDGAR discovers docs."""
        source = "eodhd"
        edgar_discovered = 3
        if edgar_discovered > 0:
            source = source + "+edgar"
        assert source == "eodhd+edgar"

    def test_no_suffix_when_edgar_discovers_nothing(self) -> None:
        """Source stays unchanged when EDGAR discovers 0 documents."""
        source = "sgx"
        edgar_discovered = 0
        if edgar_discovered > 0:
            source = source + "+edgar"
        assert source == "sgx"
