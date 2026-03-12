"""SGX RegNet Client for Singapore Exchange company announcements.

The Singapore Exchange (SGX) provides a public announcements API (no auth required)
at https://api.sgx.com/securities/v1.1/.

Useful for:
- Monitoring listed company regulatory filings
- Fetching annual reports and sustainability disclosures
- Tracking earnings releases and material information
- Research on Singapore-listed companies as B2B prospects or competitors
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class SGXAnnouncement(BaseModel):
    """A single SGX company announcement."""

    announcement_id: str = Field(...)
    company_name: str = Field(...)
    stock_code: str = Field(...)  # SGX ticker e.g. "D05"
    title: str = Field(...)
    category: str = Field(...)  # e.g. "Annual Reports and Related Documents"
    date: datetime = Field(...)
    url: str | None = Field(default=None)  # Direct link to PDF/document if available
    is_pdf: bool = Field(default=False)  # True when url points to a PDF


def _parse_announcement(raw: dict[str, Any]) -> SGXAnnouncement | None:
    """Parse a raw announcement dict into an SGXAnnouncement.

    Returns None if required fields are missing or unparseable.
    """
    announcement_id = raw.get("id") or raw.get("announcementId")
    if not announcement_id:
        return None

    title = raw.get("title") or raw.get("headline") or ""
    company_name = raw.get("companyName") or raw.get("company_name") or ""
    stock_code = raw.get("stockCode") or raw.get("stock_code") or ""
    category = raw.get("category") or raw.get("type") or ""

    # Parse date — accept "YYYY-MM-DD" or ISO datetime strings
    raw_date = raw.get("date") or raw.get("announcementDate") or ""
    parsed_date: datetime
    try:
        if "T" in raw_date:
            parsed_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        else:
            parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(
                tzinfo=UTC
            )
    except (ValueError, TypeError):
        parsed_date = datetime.now(tz=UTC)

    # Resolve attachment URL; prefer PDFs
    url: str | None = None
    is_pdf = False
    attachments = raw.get("attachments") or []
    if isinstance(attachments, list):
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            attach_url = attachment.get("url") or attachment.get("link") or ""
            attach_name = (attachment.get("name") or "").lower()
            attach_type = (attachment.get("type") or "").lower()
            if attach_name.endswith(".pdf") or attach_type == "pdf":
                url = attach_url
                is_pdf = True
                break
            # Fall back to any attachment URL
            if attach_url and url is None:
                url = attach_url

    return SGXAnnouncement(
        announcement_id=str(announcement_id),
        company_name=company_name,
        stock_code=stock_code,
        title=title,
        category=category,
        date=parsed_date,
        url=url if url else None,
        is_pdf=is_pdf,
    )


class SGXClient:
    """Client for the SGX RegNet public announcements API.

    No authentication is required.  All public methods return empty lists
    on error so callers never need to handle exceptions.

    Usage:
        client = SGXClient()
        reports = await client.get_recent_annual_reports("D05")
        await client.close()
    """

    BASE_URL = "https://api.sgx.com/securities/v1.1"

    # Announcement categories grouped by intent
    DOCUMENT_CATEGORIES: dict[str, list[str]] = {
        "annual_report": ["Annual Reports and Related Documents"],
        "sustainability": ["Sustainability Report"],
        "earnings": [
            "Financial Results",
            "Quarterly Results",
            "Half Year Results",
            "Full Year Results",
        ],
        "material": [
            "Material Information",
            "Change in Shareholding",
            "Change in Directors",
        ],
        "press_release": ["Others", "General Announcement"],
    }

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._endpoint_broken = False  # set to True when SGX_4041 seen

    # Error code returned when the SGX /announcements path is mis-routed to the
    # securities-price handler (API regression observed March 2026).
    _BROKEN_META_CODE = "SGX_4041"

    @property
    def is_endpoint_broken(self) -> bool:
        """True once a SGX_4041 response has been detected in this process lifetime."""
        return self._endpoint_broken

    async def get_announcements(
        self,
        stock_code: str | None = None,
        category: str | None = None,
        from_date: datetime | None = None,
        limit: int = 50,
    ) -> list[SGXAnnouncement]:
        """Fetch company announcements from SGX RegNet.

        Args:
            stock_code: SGX ticker to filter by (e.g. "D05" for DBS).
            category: Announcement category string to filter by.
            from_date: Only return announcements on or after this date.
            limit: Maximum number of announcements to return.

        Returns:
            List of parsed announcements; empty on error or if the endpoint
            is currently mis-routed (SGX API regression).
        """
        params: dict[str, Any] = {"limit": limit}
        if stock_code:
            params["companyCode"] = stock_code
        if category:
            params["category"] = category
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")

        try:
            url = f"{self.BASE_URL}/announcements"
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning(
                "sgx.get_announcements.error",
                stock_code=stock_code,
                category=category,
                error=str(exc),
            )
            return []

        # Detect the known API regression: the /announcements path now routes
        # to the securities-price handler which always returns
        # {"meta": {"code": "SGX_4041", ...}, "data": {"prices": [...]}}
        # instead of the expected {"data": {"announcements": [...]}}.
        meta = payload.get("meta") or {}
        if meta.get("code") == self._BROKEN_META_CODE:
            self._endpoint_broken = True
            logger.warning(
                "sgx.endpoint_broken",
                detail=(
                    "SGX /announcements path is returning price data "
                    f"(meta.code={self._BROKEN_META_CODE!r}). "
                    "The SGX RegNet announcements API endpoint has changed. "
                    "Falling back to EODHD news discovery."
                ),
                stock_code=stock_code,
            )
            return []

        # Navigate the nested response shape defensively
        data = payload.get("data") or {}
        raw_list = data.get("announcements") or []

        if not isinstance(raw_list, list):
            return []

        results: list[SGXAnnouncement] = []
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            announcement = _parse_announcement(raw)
            if announcement is not None:
                results.append(announcement)

        return results

    async def get_recent_annual_reports(
        self,
        stock_code: str,
        years_back: int = 3,
    ) -> list[SGXAnnouncement]:
        """Fetch annual reports for a listed company.

        Args:
            stock_code: SGX ticker (e.g. "D05").
            years_back: How many years of history to retrieve.

        Returns:
            Annual report announcements; empty on error.
        """
        from_date = datetime.now(tz=UTC) - timedelta(days=years_back * 365)
        category = self.DOCUMENT_CATEGORIES["annual_report"][0]
        return await self.get_announcements(
            stock_code=stock_code,
            category=category,
            from_date=from_date,
        )

    async def get_recent_earnings(
        self,
        stock_code: str,
        quarters_back: int = 8,
    ) -> list[SGXAnnouncement]:
        """Fetch earnings releases for a listed company.

        Args:
            stock_code: SGX ticker (e.g. "D05").
            quarters_back: How many quarters of history to retrieve.

        Returns:
            Earnings announcements; empty on error.
        """
        from_date = datetime.now(tz=UTC) - timedelta(
            days=quarters_back * 91
        )
        # SGX API accepts one category at a time; use the primary label
        category = self.DOCUMENT_CATEGORIES["earnings"][0]
        return await self.get_announcements(
            stock_code=stock_code,
            category=category,
            from_date=from_date,
        )

    async def get_all_recent_announcements(
        self,
        stock_code: str,
        days_back: int = 90,
    ) -> list[SGXAnnouncement]:
        """Fetch all announcement types for a company over a recent window.

        Args:
            stock_code: SGX ticker (e.g. "D05").
            days_back: Number of days of history to retrieve.

        Returns:
            All announcements in the window; empty on error.
        """
        from_date = datetime.now(tz=UTC) - timedelta(days=days_back)
        return await self.get_announcements(
            stock_code=stock_code,
            from_date=from_date,
        )

    async def health_check(self) -> bool:
        """Check whether the SGX announcements API is reachable.

        Returns:
            True if the API returns HTTP 200, False otherwise.
        """
        try:
            url = f"{self.BASE_URL}/announcements"
            response = await self._client.get(url, params={"limit": 1})
            return response.status_code == 200
        except Exception as exc:
            logger.warning("sgx.health_check.error", error=str(exc))
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


@lru_cache
def get_sgx_client() -> SGXClient:
    """Return a cached singleton SGXClient instance.

    Note for tests: once ``_endpoint_broken`` is set to ``True`` on the cached
    instance it stays ``True`` for the lifetime of the process.  Call
    ``get_sgx_client.cache_clear()`` in test teardown to get a fresh instance.
    """
    return SGXClient()
