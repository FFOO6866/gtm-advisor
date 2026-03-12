"""SEC EDGAR client for US-listed Singapore company filings.

Covers Singapore-headquartered companies listed on NYSE/Nasdaq that file with
the US Securities and Exchange Commission.  Foreign private issuers like Sea
Limited, Grab Holdings, and PropertyGuru file Form 20-F (annual report) and
6-K (material periodic reports) instead of the domestic 10-K/10-Q equivalents.

No API key required — SEC EDGAR is a public database.  The only requirement
is a descriptive User-Agent header per SEC guidelines.

Endpoint reference: https://www.sec.gov/developer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_EDGAR_BASE = "https://data.sec.gov"
_EDGAR_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
# SEC requires an informative User-Agent (company name + email)
_USER_AGENT = "GTM-Advisor market-research/1.0 contact@gtm-advisor.sg"

# ---------------------------------------------------------------------------
# Curated CIK registry — Singapore-headquartered companies on US exchanges
# Format: EODHD ticker → (CIK zero-padded-10, human name)
# ---------------------------------------------------------------------------

SG_COMPANY_CIKS: dict[str, tuple[str, str]] = {
    # US-listed SG tech / consumer companies
    "SE": ("0001703399", "Sea Ltd"),           # NYSE: SE — Shopee, Garena, SeaMoney
    "GRAB": ("0001855612", "Grab Holdings Ltd"),   # Nasdaq: GRAB — superapp
    "PGRU": ("0001873331", "PropertyGuru Group Ltd"),  # NYSE: PGRU
    "MNY": ("0001974044", "MoneyHero Ltd"),     # Nasdaq: MNY — financial comparison
    # Add new SG-founded US-listed companies here as they IPO
}

# Document form types → DocumentType string (matches DocumentType enum values)
_FORM_TO_DOC_TYPE: dict[str, str] = {
    "20-F": "annual_report",       # Foreign private issuer annual report
    "20-F/A": "annual_report",     # Amended annual report
    "6-K": "earnings_release",     # Material current report (quarterly results etc.)
    "DEF 14A": "investor_presentation",  # Proxy statement / AGM
    "F-1": "investor_presentation",     # IPO registration statement
    "F-3": "investor_presentation",     # Shelf registration
}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


@dataclass
class EDGARFiling:
    """A single SEC EDGAR filing for a SG company."""

    ticker: str                 # EODHD ticker e.g. "SE"
    cik: str                    # 10-digit CIK e.g. "0001703399"
    company_name: str
    form: str                   # "20-F", "6-K", etc.
    doc_type: str               # maps to DocumentType enum value
    filing_date: datetime
    accession_number: str       # e.g. "0001193125-25-084311"
    primary_document: str       # filename e.g. "d940352d20f.htm"
    document_url: str           # full URL to primary document (HTML or PDF)
    index_url: str              # filing index page URL
    fiscal_year: int | None     # extracted from period_of_report when available
    description: str = ""       # e.g. "FORM 20-F"


@dataclass
class EDGARClientResult:
    """Result of fetching filings for one or more companies."""

    filings: list[EDGARFiling] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SECEdgarClient:
    """Async client for the SEC EDGAR public filings API.

    Fetches annual reports (20-F) and material current reports (6-K) for
    Singapore-headquartered companies listed on US exchanges.

    No authentication required.  All methods return empty results on error.

    Usage::

        client = SECEdgarClient()
        result = await client.get_annual_reports("SE", years_back=3)
        for filing in result.filings:
            print(filing.document_url)
        await client.close()
    """

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": _USER_AGENT},
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def get_submissions(self, cik: str) -> dict[str, Any]:
        """Fetch the full submissions JSON for a CIK.

        Returns an empty dict on error.
        """
        # EDGAR requires 10-digit zero-padded CIK
        padded = cik.lstrip("0").zfill(10)
        url = f"{_EDGAR_BASE}/submissions/CIK{padded}.json"
        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("sec_edgar.get_submissions.error cik=%s: %s", cik, exc)
            return {}

    def _build_filing_url(self, cik: str, accession_number: str, primary_doc: str) -> str:
        """Build the EDGAR document download URL.

        Format: /Archives/edgar/data/{cik_no_zeros}/{acc_no_dashes}/{doc}
        """
        cik_int = int(cik)  # strips leading zeros
        acc_clean = accession_number.replace("-", "")
        return f"{_EDGAR_ARCHIVES}/{cik_int}/{acc_clean}/{primary_doc}"

    def _build_index_url(self, cik: str, accession_number: str) -> str:
        cik_int = int(cik)
        acc_clean = accession_number.replace("-", "")
        return f"{_EDGAR_ARCHIVES}/{cik_int}/{acc_clean}/"

    def _extract_year(self, period_of_report: str | None) -> int | None:
        if not period_of_report:
            return None
        try:
            return int(period_of_report[:4])
        except (ValueError, TypeError):
            return None

    def _extract_year_from_filename(self, filename: str) -> int | None:
        """Extract fiscal year from EDGAR document filename as a fallback.

        Many EDGAR primary documents embed the period date in their name:
          pgru-20231231.htm  → 2023
          ck0001855612-20221231.htm → 2022

        Looks for an 8-digit YYYYMMDD sequence; returns the YYYY portion when
        the year is plausible (2000–2040).
        """
        import re as _re

        matches = _re.findall(r"(\d{4})\d{4}", filename)
        for m in matches:
            year = int(m)
            if 2000 <= year <= 2040:
                return year
        return None

    async def get_filings(
        self,
        ticker: str,
        forms: list[str] | None = None,
        years_back: int = 3,
    ) -> EDGARClientResult:
        """Fetch filings of specified form types for a SG company.

        Args:
            ticker: EODHD ticker (must be in ``SG_COMPANY_CIKS``).
            forms: List of SEC form types to include, e.g. ``["20-F"]``.
                   Defaults to ``["20-F", "20-F/A"]``.
            years_back: How many years of history to return.

        Returns:
            :class:`EDGARClientResult` with matching filings.
        """
        forms = forms or ["20-F", "20-F/A"]
        result = EDGARClientResult()

        cik_entry = SG_COMPANY_CIKS.get(ticker.upper())
        if cik_entry is None:
            result.errors.append(f"Ticker {ticker!r} not in SG_COMPANY_CIKS registry")
            return result

        cik, company_name = cik_entry
        submissions = await self.get_submissions(cik)
        if not submissions:
            result.errors.append(f"No EDGAR submissions found for {ticker} (CIK {cik})")
            return result

        recent = submissions.get("filings", {}).get("recent", {})
        all_forms: list[str] = recent.get("form", [])
        all_dates: list[str] = recent.get("filingDate", [])
        all_accessions: list[str] = recent.get("accessionNumber", [])
        all_docs: list[str] = recent.get("primaryDocument", [])
        all_descriptions: list[str] = recent.get("primaryDocDescription", [])
        all_periods: list[str] = recent.get("periodOfReport", [])

        cutoff = datetime.now(tz=UTC).replace(
            year=datetime.now(tz=UTC).year - years_back
        )

        forms_set = {f.upper() for f in forms}
        for i, form in enumerate(all_forms):
            if form.upper() not in forms_set:
                continue

            raw_date = all_dates[i] if i < len(all_dates) else ""
            try:
                filing_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=UTC)
            except (ValueError, TypeError):
                filing_date = datetime.now(tz=UTC)

            if filing_date < cutoff:
                continue

            accession = all_accessions[i] if i < len(all_accessions) else ""
            primary_doc = all_docs[i] if i < len(all_docs) else ""
            description = all_descriptions[i] if i < len(all_descriptions) else ""
            period = all_periods[i] if i < len(all_periods) else None

            if not accession or not primary_doc:
                continue

            doc_type = _FORM_TO_DOC_TYPE.get(form, "press_release")

            fiscal_year = (
                self._extract_year(period)
                or self._extract_year_from_filename(primary_doc)
            )

            result.filings.append(
                EDGARFiling(
                    ticker=ticker.upper(),
                    cik=cik,
                    company_name=company_name,
                    form=form,
                    doc_type=doc_type,
                    filing_date=filing_date,
                    accession_number=accession,
                    primary_document=primary_doc,
                    document_url=self._build_filing_url(cik, accession, primary_doc),
                    index_url=self._build_index_url(cik, accession),
                    fiscal_year=fiscal_year,
                    description=description,
                )
            )

        logger.info(
            "sec_edgar.get_filings ticker=%s forms=%s found=%d",
            ticker,
            forms,
            len(result.filings),
        )
        return result

    async def get_annual_reports(
        self,
        ticker: str,
        years_back: int = 3,
    ) -> EDGARClientResult:
        """Fetch 20-F annual reports for a SG company.

        Convenience wrapper around :meth:`get_filings`.
        """
        return await self.get_filings(ticker, forms=["20-F", "20-F/A"], years_back=years_back)

    async def get_all_sg_annual_reports(
        self,
        years_back: int = 3,
    ) -> EDGARClientResult:
        """Fetch 20-F annual reports for ALL known SG companies in one call.

        Aggregates results from all tickers in :data:`SG_COMPANY_CIKS`.
        """
        combined = EDGARClientResult()
        for ticker in SG_COMPANY_CIKS:
            partial = await self.get_annual_reports(ticker, years_back=years_back)
            combined.filings.extend(partial.filings)
            combined.errors.extend(partial.errors)
        return combined
