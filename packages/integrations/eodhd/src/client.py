"""EODHD Client for financial and company data.

EODHD provides financial data APIs including:
- Stock prices and fundamentals
- Company financials
- Economic indicators
- News and sentiment

Useful for analyzing target companies and market conditions.
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from typing import Any

import httpx
from pydantic import BaseModel, Field


class CompanyFundamentals(BaseModel):
    """Company fundamental data from EODHD."""

    symbol: str = Field(...)
    name: str = Field(...)
    exchange: str = Field(...)
    currency: str = Field(default="USD")

    # General info
    sector: str | None = Field(default=None)
    industry: str | None = Field(default=None)
    description: str | None = Field(default=None)
    website: str | None = Field(default=None)
    employees: int | None = Field(default=None)
    address: str | None = Field(default=None)
    country: str | None = Field(default=None)

    # Financials
    market_cap: float | None = Field(default=None)
    pe_ratio: float | None = Field(default=None)
    eps: float | None = Field(default=None)
    dividend_yield: float | None = Field(default=None)
    revenue: float | None = Field(default=None)
    profit_margin: float | None = Field(default=None)


class EconomicIndicator(BaseModel):
    """Economic indicator data."""

    indicator: str = Field(...)
    country: str = Field(...)
    period: str = Field(...)
    value: float = Field(...)
    previous_value: float | None = Field(default=None)
    change: float | None = Field(default=None)
    date: datetime = Field(...)


class FinancialNews(BaseModel):
    """Financial news item."""

    title: str = Field(...)
    content: str | None = Field(default=None)
    date: datetime = Field(...)
    symbols: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sentiment: str | None = Field(default=None)
    link: str | None = Field(default=None)


class EODHDClient:
    """Client for EODHD financial data API.

    Provides access to:
    - Company fundamentals and financials
    - Stock prices and historical data
    - Economic indicators
    - Financial news

    Particularly useful for:
    - Analyzing potential B2B leads (public companies)
    - Understanding market conditions
    - Competitive intelligence on public competitors
    """

    BASE_URL = "https://eodhd.com/api"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("EODHD_API_KEY")
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return self._api_key is not None and len(self._api_key) > 0

    async def health_check(self) -> bool:
        """Check if EODHD API is accessible."""
        if not self.is_configured:
            return False
        try:
            # Simple check with a known symbol
            await self._request("exchange-symbol-list/US", {"fmt": "json"})
            return True
        except Exception:
            return False

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make request to EODHD API.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            API response data

        Raises:
            Exception: If request fails
        """
        if not self.is_configured:
            raise ValueError("EODHD API key not configured")

        params = params or {}
        params["api_token"] = self._api_key
        params["fmt"] = "json"

        url = f"{self.BASE_URL}/{endpoint}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_company_fundamentals(
        self,
        symbol: str,
        exchange: str = "US",
    ) -> CompanyFundamentals | None:
        """Get company fundamental data.

        Args:
            symbol: Stock symbol (e.g., AAPL)
            exchange: Exchange code (e.g., US, SG)

        Returns:
            Company fundamentals or None if not found
        """
        try:
            data = await self._request(
                f"fundamentals/{symbol}.{exchange}",
            )

            if not data or "General" not in data:
                return None

            general = data.get("General", {})
            highlights = data.get("Highlights", {})

            return CompanyFundamentals(
                symbol=symbol,
                name=general.get("Name", symbol),
                exchange=exchange,
                currency=general.get("CurrencyCode", "USD"),
                sector=general.get("Sector"),
                industry=general.get("Industry"),
                description=general.get("Description"),
                website=general.get("WebURL"),
                employees=general.get("FullTimeEmployees"),
                address=general.get("Address"),
                country=general.get("CountryName"),
                market_cap=highlights.get("MarketCapitalization"),
                pe_ratio=highlights.get("PERatio"),
                eps=highlights.get("EarningsShare"),
                dividend_yield=highlights.get("DividendYield"),
                revenue=highlights.get("Revenue"),
                profit_margin=highlights.get("ProfitMargin"),
            )

        except Exception:
            return None

    async def search_companies(
        self,
        query: str,
        exchange: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for companies by name or symbol.

        Args:
            query: Search query
            exchange: Optional exchange filter
            limit: Maximum results

        Returns:
            List of matching companies
        """
        params: dict[str, Any] = {
            "query_string": query,
            "limit": limit,
        }
        if exchange:
            params["exchange"] = exchange

        try:
            data = await self._request("search", params)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_economic_indicators(
        self,
        country: str = "SGP",  # Singapore
        indicator: str | None = None,
    ) -> list[EconomicIndicator]:
        """Get economic indicators for a country.

        Args:
            country: Country code (SGP for Singapore)
            indicator: Specific indicator (GDP, inflation, etc.)

        Returns:
            List of economic indicators
        """
        try:
            endpoint = f"macro-indicator/{country}"
            params: dict[str, Any] = {}
            if indicator:
                params["indicator"] = indicator

            data = await self._request(endpoint, params)

            if not isinstance(data, list):
                return []

            indicators = []
            for item in data[:20]:  # Limit results
                try:
                    indicators.append(
                        EconomicIndicator(
                            indicator=item.get("indicator", "Unknown"),
                            country=country,
                            period=item.get("Period", ""),
                            value=float(item.get("Value", 0)),
                            previous_value=(
                                float(item["PreviousValue"])
                                if item.get("PreviousValue")
                                else None
                            ),
                            change=(
                                float(item["Change"]) if item.get("Change") else None
                            ),
                            date=datetime.strptime(item["Date"], "%Y-%m-%d")
                            if item.get("Date")
                            else datetime.utcnow(),
                        )
                    )
                except (ValueError, KeyError):
                    continue

            return indicators

        except Exception:
            return []

    async def get_financial_news(
        self,
        symbol: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> list[FinancialNews]:
        """Get financial news.

        Args:
            symbol: Filter by stock symbol
            tag: Filter by tag (e.g., "earnings", "IPO")
            limit: Maximum results

        Returns:
            List of news items
        """
        try:
            params: dict[str, Any] = {"limit": limit}
            if symbol:
                params["s"] = symbol
            if tag:
                params["t"] = tag

            data = await self._request("news", params)

            if not isinstance(data, list):
                return []

            news_items = []
            for item in data:
                try:
                    news_items.append(
                        FinancialNews(
                            title=item.get("title", ""),
                            content=item.get("content"),
                            date=datetime.strptime(
                                item["date"], "%Y-%m-%d %H:%M:%S"
                            )
                            if item.get("date")
                            else datetime.utcnow(),
                            symbols=item.get("symbols", []),
                            tags=item.get("tags", []),
                            sentiment=item.get("sentiment"),
                            link=item.get("link"),
                        )
                    )
                except (ValueError, KeyError):
                    continue

            return news_items

        except Exception:
            return []

    async def get_singapore_market_data(self) -> dict[str, Any]:
        """Get Singapore market overview.

        Convenience method for Singapore-focused GTM analysis.

        Returns:
            Singapore market data summary
        """
        results: dict[str, Any] = {
            "economic_indicators": [],
            "market_news": [],
        }

        # Get Singapore economic indicators
        indicators = await self.get_economic_indicators("SGP")
        results["economic_indicators"] = [i.model_dump() for i in indicators[:10]]

        # Get relevant financial news
        news = await self.get_financial_news(tag="earnings", limit=10)
        results["market_news"] = [n.model_dump() for n in news]

        return results

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


@lru_cache
def get_eodhd_client() -> EODHDClient:
    """Get cached EODHD client instance."""
    return EODHDClient()
