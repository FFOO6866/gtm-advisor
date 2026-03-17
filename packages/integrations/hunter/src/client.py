"""Hunter.io client for email finding and verification.

Hunter.io provides:
- Email verification: validates deliverability beyond DNS checks
- Email finder: discovers professional emails for a person + domain
- Domain search: lists known email addresses at a company domain

Used by LeadEnrichmentAgent to gate leads with invalid emails before
sequence enrollment, and to surface emails for leads that lack them.

Endpoint reference: https://hunter.io/api-documentation/v2
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_BASE_URL = "https://api.hunter.io/v2"


# ---------------------------------------------------------------------------
# Response models (dataclasses — no Pydantic dep in this thin client)
# ---------------------------------------------------------------------------


@dataclass
class EmailVerification:
    """Result of an email-verifier call."""

    email: str
    # "valid", "invalid", "accept_all", "unknown"
    status: str
    # "deliverable", "undeliverable", "risky", "unknown"
    result: str
    score: int  # 0–100 confidence score from Hunter
    mx_records: bool
    smtp_server: bool
    smtp_check: bool
    disposable: bool
    webmail: bool
    gibberish: bool
    block: bool


@dataclass
class EmailFindResult:
    """Result of an email-finder call."""

    email: str | None
    score: int  # 0–100 confidence
    first_name: str | None
    last_name: str | None
    position: str | None
    company: str | None
    domain: str | None
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DomainSearchResult:
    """One email contact returned by domain-search."""

    email: str
    first_name: str | None
    last_name: str | None
    position: str | None
    confidence: int  # 0–100


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class HunterClient:
    """Async client for the Hunter.io v2 API.

    All methods return ``None`` on API / network errors (non-fatal) or when
    the client is not configured (no API key).  Callers should treat a ``None``
    return as "data unavailable, proceed without it".
    """

    # Hunter.io free plan returns 403 when too many concurrent requests
    # arrive from the same key. Limit to 3 parallel calls.
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(3)

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("HUNTER_API_KEY", "")
        self._http = httpx.AsyncClient(timeout=15.0)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def verify_email(self, email: str) -> EmailVerification | None:
        """Verify a single email address.

        Returns ``None`` when the client is unconfigured or the API call fails.
        A ``status`` of ``"invalid"`` with ``result`` ``"undeliverable"`` is a
        hard gate — do not send to that address.
        """
        if not self.is_configured:
            return None
        async with self._semaphore:
            try:
                resp = await self._http.get(
                    f"{_BASE_URL}/email-verifier",
                    params={"email": email, "api_key": self._api_key},
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json().get("data", {})
                return EmailVerification(
                    email=data.get("email", email),
                    status=data.get("status", "unknown"),
                    result=data.get("result", "unknown"),
                    score=int(data.get("score") or 0),
                    mx_records=bool(data.get("mx_records")),
                    smtp_server=bool(data.get("smtp_server")),
                    smtp_check=bool(data.get("smtp_check")),
                    disposable=bool(data.get("disposable")),
                    webmail=bool(data.get("webmail")),
                    gibberish=bool(data.get("gibberish")),
                    block=bool(data.get("block")),
                )
            except Exception as exc:
                logger.debug("hunter.verify_email.failed", email=email, error=str(exc))
                return None

    async def find_email(
        self,
        domain: str,
        first_name: str,
        last_name: str,
    ) -> EmailFindResult | None:
        """Find a professional email address for a person at a domain.

        Returns ``None`` when unconfigured, the API call fails, or no match
        was found (Hunter returns HTTP 200 with ``email: null`` in that case).
        """
        if not self.is_configured or not domain or not first_name or not last_name:
            return None
        async with self._semaphore:
            try:
                resp = await self._http.get(
                    f"{_BASE_URL}/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first_name,
                        "last_name": last_name,
                        "api_key": self._api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                return EmailFindResult(
                    email=data.get("email"),
                    score=int(data.get("score") or 0),
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    position=data.get("position"),
                    company=data.get("company"),
                    domain=data.get("domain"),
                    sources=data.get("sources") or [],
                )
            except Exception as exc:
                logger.debug(
                    "hunter.find_email.failed",
                    domain=domain,
                    name=f"{first_name} {last_name}",
                    error=str(exc),
                )
                return None

    async def domain_search(
        self,
        domain: str,
        limit: int = 10,
    ) -> list[DomainSearchResult]:
        """Return known email contacts at a company domain.

        Useful for surfacing decision-maker contacts at a target account
        when the lead only has a company name / domain but no contact email.
        Returns an empty list on failure or when unconfigured.
        """
        if not self.is_configured or not domain:
            return []
        async with self._semaphore:
            try:
                resp = await self._http.get(
                    f"{_BASE_URL}/domain-search",
                    params={"domain": domain, "limit": limit, "api_key": self._api_key},
                )
                resp.raise_for_status()
                emails_raw: list[dict[str, Any]] = resp.json().get("data", {}).get("emails", [])
                return [
                    DomainSearchResult(
                        email=e["value"],
                        first_name=e.get("first_name"),
                        last_name=e.get("last_name"),
                        position=e.get("position"),
                        confidence=int(e.get("confidence") or 0),
                    )
                    for e in emails_raw
                    if e.get("value")
                ]
            except Exception as exc:
                logger.debug("hunter.domain_search.failed", domain=domain, error=str(exc))
            return []


@lru_cache(maxsize=1)
def get_hunter_client() -> HunterClient:
    """Return a cached HunterClient instance.

    Note: ``@lru_cache`` is evaluated once per process.  In tests, call
    ``get_hunter_client.cache_clear()`` before patching ``HUNTER_API_KEY``
    to force re-evaluation.
    """
    return HunterClient()
