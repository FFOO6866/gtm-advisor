"""Unit tests for LeadHunterAgent._enrich_with_eodhd().

Covers:
- Returns ticker and exchange when enrichment data is found
- Returns {} when the company is not found in EODHD search results
- Returns {} when EODHD is not configured
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.lead_hunter.src.agent import LeadHunterAgent
from packages.integrations.eodhd.src.client import CompanyFundamentals

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lead_hunter_agent() -> LeadHunterAgent:
    """Build a LeadHunterAgent with all external service calls patched out."""
    with (
        patch("agents.lead_hunter.src.agent.get_agent_bus") as mock_bus_fn,
        patch("agents.lead_hunter.src.agent.EODHDClient"),
    ):
        mock_bus_fn.return_value = MagicMock()
        agent = LeadHunterAgent()
    return agent


def _make_fundamentals(
    *,
    employees: int | None = 500,
    revenue: float | None = 1_000_000.0,
    market_cap: float | None = 50_000_000.0,
) -> CompanyFundamentals:
    """Construct a minimal CompanyFundamentals object."""
    return CompanyFundamentals(
        symbol="D05",
        name="DBS Group Holdings",
        exchange="SG",
        currency="SGD",
        employees=employees,
        revenue=revenue,
        market_cap=market_cap,
    )


# ---------------------------------------------------------------------------
# _enrich_with_eodhd tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_with_eodhd_returns_ticker_and_exchange_when_found() -> None:
    """When search returns a match and fundamentals are available, ticker and exchange are returned."""
    agent = _make_lead_hunter_agent()

    agent._eodhd = MagicMock()
    agent._eodhd.is_configured = True
    agent._eodhd.search_companies = AsyncMock(
        return_value=[{"Code": "D05", "Exchange": "SG", "Name": "DBS Group"}]
    )
    agent._eodhd.get_company_fundamentals = AsyncMock(
        return_value=_make_fundamentals(employees=5000, revenue=5e9, market_cap=80e9)
    )

    result = await agent._enrich_with_eodhd("DBS Group Holdings")

    assert result.get("ticker") == "D05"
    assert result.get("exchange") == "SG"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_with_eodhd_returns_empty_when_company_not_found() -> None:
    """When search returns no SG-exchange match, an empty dict is returned."""
    agent = _make_lead_hunter_agent()

    agent._eodhd = MagicMock()
    agent._eodhd.is_configured = True
    # Search returns results but none with Exchange == "SG"
    agent._eodhd.search_companies = AsyncMock(
        return_value=[{"Code": "UNKN", "Exchange": "US", "Name": "Unknown Corp"}]
    )

    result = await agent._enrich_with_eodhd("NonExistent Pte Ltd")

    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_with_eodhd_returns_empty_when_not_configured() -> None:
    """When EODHD is not configured, returns {} immediately without network calls."""
    agent = _make_lead_hunter_agent()

    agent._eodhd = MagicMock()
    agent._eodhd.is_configured = False
    # search_companies should never be called in this path
    agent._eodhd.search_companies = AsyncMock()

    result = await agent._enrich_with_eodhd("Any Company")

    assert result == {}
    agent._eodhd.search_companies.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_with_eodhd_returns_empty_when_search_empty() -> None:
    """When search returns an empty list, returns {} without calling get_company_fundamentals."""
    agent = _make_lead_hunter_agent()

    agent._eodhd = MagicMock()
    agent._eodhd.is_configured = True
    agent._eodhd.search_companies = AsyncMock(return_value=[])
    agent._eodhd.get_company_fundamentals = AsyncMock()

    result = await agent._enrich_with_eodhd("Obscure Private Co")

    assert result == {}
    agent._eodhd.get_company_fundamentals.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_with_eodhd_returns_empty_when_fundamentals_missing() -> None:
    """When get_company_fundamentals returns None/falsy, returns {}."""
    agent = _make_lead_hunter_agent()

    agent._eodhd = MagicMock()
    agent._eodhd.is_configured = True
    agent._eodhd.search_companies = AsyncMock(
        return_value=[{"Code": "XYZ", "Exchange": "SG", "Name": "XYZ Corp"}]
    )
    agent._eodhd.get_company_fundamentals = AsyncMock(return_value=None)

    result = await agent._enrich_with_eodhd("XYZ Corp")

    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_with_eodhd_ticker_only_set_when_enrichment_has_data() -> None:
    """ticker/exchange are only injected when at least one enrichment field is non-empty."""
    agent = _make_lead_hunter_agent()

    agent._eodhd = MagicMock()
    agent._eodhd.is_configured = True
    agent._eodhd.search_companies = AsyncMock(
        return_value=[{"Code": "SLIM", "Exchange": "SG", "Name": "Slim Co"}]
    )
    # All optional fields are None — no enrichment data
    agent._eodhd.get_company_fundamentals = AsyncMock(
        return_value=_make_fundamentals(employees=None, revenue=None, market_cap=None)
    )

    result = await agent._enrich_with_eodhd("Slim Co")

    # No data fields → ticker and exchange must NOT be injected (empty dict)
    assert result == {}
