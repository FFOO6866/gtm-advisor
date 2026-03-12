"""EODHD Client for financial and company data.

EODHD provides financial data APIs including:
- Stock prices and fundamentals
- Company financials (full income statement, balance sheet, cash flow)
- Economic indicators
- News and sentiment
- Exchange symbol lists

Useful for analyzing target companies, market benchmarking, and the
Singapore Market Intelligence Database (SGX + overseas-listed SG companies).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


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


class ExchangeSymbol(BaseModel):
    """One instrument from EODHD exchange-symbol-list."""

    code: str = Field(...)           # Ticker code (e.g. "D05")
    name: str = Field(...)
    country: str = Field(default="")
    exchange: str = Field(default="")
    currency: str = Field(default="SGD")
    type: str = Field(default="Common Stock")   # "Common Stock", "ETF", "Fund", etc.
    isin: str | None = Field(default=None)


class FinancialStatementRow(BaseModel):
    """One row from an income statement / balance sheet / cash flow."""

    date: str = Field(...)           # YYYY-MM-DD
    filing_date: str | None = Field(default=None)
    currency_symbol: str = Field(default="USD")

    # Income Statement
    total_revenue: float | None = Field(default=None)
    gross_profit: float | None = Field(default=None)
    ebitda: float | None = Field(default=None)
    ebit: float | None = Field(default=None)
    net_income: float | None = Field(default=None)
    diluted_eps: float | None = Field(default=None)

    # Balance Sheet
    total_assets: float | None = Field(default=None)
    total_equity: float | None = Field(default=None)
    short_long_term_debt_total: float | None = Field(default=None)
    cash_and_equivalents: float | None = Field(default=None)

    # Cash Flow
    total_cash_from_operating_activities: float | None = Field(default=None)
    capital_expenditures: float | None = Field(default=None)


class FullFundamentals(BaseModel):
    """Full company fundamentals from EODHD — all sections."""

    symbol: str
    exchange: str

    # General / Highlights
    name: str = Field(default="")
    description: str | None = Field(default=None)
    currency: str = Field(default="USD")
    country: str | None = Field(default=None)
    sector: str | None = Field(default=None)
    industry: str | None = Field(default=None)
    website: str | None = Field(default=None)
    employees: int | None = Field(default=None)
    address: str | None = Field(default=None)
    gics_sector: str | None = Field(default=None)
    gics_industry: str | None = Field(default=None)
    isin: str | None = Field(default=None)
    listing_type: str = Field(default="Common Stock")   # from General.Type

    # Highlights
    market_cap: float | None = Field(default=None)
    pe_ratio: float | None = Field(default=None)
    ev_ebitda: float | None = Field(default=None)
    revenue_ttm: float | None = Field(default=None)
    gross_margin_ttm: float | None = Field(default=None)
    profit_margin_ttm: float | None = Field(default=None)
    return_on_equity_ttm: float | None = Field(default=None)
    dividend_yield: float | None = Field(default=None)

    # Time series financials
    annual_income: list[FinancialStatementRow] = Field(default_factory=list)
    quarterly_income: list[FinancialStatementRow] = Field(default_factory=list)
    annual_balance: list[FinancialStatementRow] = Field(default_factory=list)
    quarterly_balance: list[FinancialStatementRow] = Field(default_factory=list)
    annual_cashflow: list[FinancialStatementRow] = Field(default_factory=list)
    quarterly_cashflow: list[FinancialStatementRow] = Field(default_factory=list)


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
                                float(item["PreviousValue"]) if item.get("PreviousValue") else None
                            ),
                            change=(float(item["Change"]) if item.get("Change") else None),
                            date=datetime.strptime(item["Date"], "%Y-%m-%d")
                            if item.get("Date")
                            else datetime.now(UTC),
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
                            date=datetime.strptime(item["date"], "%Y-%m-%d %H:%M:%S")
                            if item.get("date")
                            else datetime.now(UTC),
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

    async def get_exchange_symbol_list(
        self,
        exchange: str = "SG",
    ) -> list[ExchangeSymbol]:
        """Get all symbols listed on an exchange.

        Args:
            exchange: Exchange code (e.g. "SG" for SGX)

        Returns:
            List of ExchangeSymbol, filtered to common equities.
        """
        _allowed_types = {"Common Stock", "Real Estate Investment Trust", "Business Trust"}
        try:
            # No server-side type filter — let all types through and filter client-side
            # so REITs and Business Trusts are included alongside Common Stock.
            data = await self._request(f"exchange-symbol-list/{exchange}")
            if not isinstance(data, list):
                return []
            symbols = [
                ExchangeSymbol(
                    code=item.get("Code", ""),
                    name=item.get("Name", ""),
                    country=item.get("Country", ""),
                    exchange=item.get("Exchange", ""),
                    currency=item.get("Currency", "SGD"),
                    type=item.get("Type", "Common Stock"),
                    isin=item.get("Isin") or None,
                )
                for item in data
                if item.get("Type") in _allowed_types
            ]
            logger.info("eodhd_symbol_list_fetched", exchange=exchange, count=len(symbols))
            return symbols
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Helpers for get_full_fundamentals
    # ------------------------------------------------------------------

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert EODHD string values to float, treating None / "None" / "" as None."""
        if value is None or value == "" or value == "None":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_statement_rows(
        section: dict[str, Any],
        limit: int,
    ) -> list[FinancialStatementRow]:
        """Parse a dict-keyed EODHD financial statement section into rows.

        Args:
            section: Dict keyed by date string, values are dicts of fields.
            limit: Maximum number of rows to return (most recent first).

        Returns:
            List of FinancialStatementRow sorted descending by date.
        """
        if not isinstance(section, dict):
            return []

        _field_map: dict[str, str] = {
            "totalRevenue": "total_revenue",
            "grossProfit": "gross_profit",
            "ebitda": "ebitda",
            "ebit": "ebit",
            "netIncome": "net_income",
            "dilutedEPS": "diluted_eps",
            "totalAssets": "total_assets",
            "totalStockholderEquity": "total_equity",
            "shortLongTermDebtTotal": "short_long_term_debt_total",
            "cashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
            "totalCashFromOperatingActivities": "total_cash_from_operating_activities",
            "capitalExpenditures": "capital_expenditures",
        }

        rows: list[FinancialStatementRow] = []
        for date_key in sorted(section.keys(), reverse=True)[:limit]:
            raw = section[date_key]
            if not isinstance(raw, dict):
                continue
            kwargs: dict[str, Any] = {
                "date": raw.get("date", date_key),
                "filing_date": raw.get("filingDate") or None,
                "currency_symbol": raw.get("currencySymbol", "USD") or "USD",
            }
            for eodhd_key, model_key in _field_map.items():
                kwargs[model_key] = EODHDClient._to_float(raw.get(eodhd_key))
            rows.append(FinancialStatementRow(**kwargs))

        return rows

    async def get_full_fundamentals(
        self,
        symbol: str,
        exchange: str = "SG",
    ) -> FullFundamentals | None:
        """Get comprehensive fundamentals for a single symbol.

        Maps the full EODHD fundamentals JSON (General, Highlights, Financials)
        to FullFundamentals.

        Args:
            symbol: Ticker symbol (e.g. "D05")
            exchange: Exchange code (e.g. "SG")

        Returns:
            FullFundamentals instance or None if data unavailable.
        """
        try:
            data = await self._request(f"fundamentals/{symbol}.{exchange}")
            if not data or "General" not in data:
                return None

            general = data.get("General", {})
            highlights = data.get("Highlights", {})
            financials = data.get("Financials", {})

            # Compute gross_margin_ttm from raw figures
            gross_margin_ttm: float | None = None
            gross_profit_raw = self._to_float(highlights.get("GrossProfitTTM"))
            revenue_raw = self._to_float(highlights.get("RevenueTTM"))
            if gross_profit_raw is not None and revenue_raw and revenue_raw != 0:
                gross_margin_ttm = gross_profit_raw / revenue_raw

            def _stmt(section_name: str, period: str) -> dict[str, Any]:
                return (
                    financials.get(section_name, {}).get(period, {})
                )

            return FullFundamentals(
                symbol=symbol,
                exchange=exchange,
                # General
                name=general.get("Name", ""),
                description=general.get("Description") or None,
                currency=general.get("CurrencyCode", "USD") or "USD",
                country=general.get("CountryName") or None,
                sector=general.get("Sector") or None,
                industry=general.get("Industry") or None,
                website=general.get("WebURL") or None,
                employees=general.get("FullTimeEmployees") or None,
                address=general.get("Address") or None,
                gics_sector=general.get("GicsSector") or None,
                gics_industry=general.get("GicsIndustry") or None,
                isin=general.get("ISIN") or None,
                listing_type=general.get("Type", "Common Stock") or "Common Stock",
                # Highlights
                market_cap=self._to_float(highlights.get("MarketCapitalization")),
                pe_ratio=self._to_float(highlights.get("PERatio")),
                ev_ebitda=self._to_float(highlights.get("EnterpriseValueEbitda")),
                revenue_ttm=revenue_raw,
                gross_margin_ttm=gross_margin_ttm,
                profit_margin_ttm=self._to_float(highlights.get("ProfitMargin")),
                return_on_equity_ttm=self._to_float(highlights.get("ReturnOnEquityTTM")),
                dividend_yield=self._to_float(highlights.get("DividendYield")),
                # Financials
                annual_income=self._parse_statement_rows(
                    _stmt("Income_Statement", "yearly"), limit=5
                ),
                quarterly_income=self._parse_statement_rows(
                    _stmt("Income_Statement", "quarterly"), limit=12
                ),
                annual_balance=self._parse_statement_rows(
                    _stmt("Balance_Sheet", "yearly"), limit=5
                ),
                quarterly_balance=self._parse_statement_rows(
                    _stmt("Balance_Sheet", "quarterly"), limit=12
                ),
                annual_cashflow=self._parse_statement_rows(
                    _stmt("Cash_Flow", "yearly"), limit=5
                ),
                quarterly_cashflow=self._parse_statement_rows(
                    _stmt("Cash_Flow", "quarterly"), limit=12
                ),
            )
        except Exception:
            return None

    async def get_executives(
        self,
        symbol: str,
        exchange: str = "SG",
    ) -> list[dict[str, Any]]:
        """Get executive officers for a company.

        Extracts General.Officers from EODHD fundamentals.

        Args:
            symbol: Ticker symbol
            exchange: Exchange code

        Returns:
            List of officer dicts (Name, Title, YearBorn, Since).
        """
        try:
            data = await self._request(f"fundamentals/{symbol}.{exchange}")
            if not data or "General" not in data:
                return []
            officers = data["General"].get("Officers")
            if isinstance(officers, dict):
                return list(officers.values())
            if isinstance(officers, list):
                return officers
            return []
        except Exception:
            return []

    async def get_sp500_constituents(self) -> list[dict[str, str]]:
        """Get current S&P 500 index constituents with GICS sector/industry.

        Returns:
            List of dicts with keys: code, exchange, name, sector, industry, weight.
            Empty list on error or if plan does not support index data.
        """
        try:
            data = await self._request("fundamentals/GSPC.INDX", {"filter": "Components"})
            if not isinstance(data, dict):
                return []
            results: list[dict[str, str]] = []
            for entry in data.values():
                results.append(
                    {
                        "code": entry.get("Code", ""),
                        "exchange": entry.get("Exchange", ""),
                        "name": entry.get("Name", ""),
                        "sector": entry.get("Sector", ""),
                        "industry": entry.get("Industry", ""),
                        "weight": entry.get("Weight", ""),
                    }
                )
            logger.info("eodhd_sp500_fetched", count=len(results))
            return results
        except Exception:
            return []

    async def get_sgx_all_bulk(self) -> list[dict[str, Any]]:
        """Get simplified bulk fundamentals for all SGX-listed companies.

        Calls EODHD bulk-fundamentals endpoint and returns a flat list of
        dicts with keys: ticker, general, highlights.

        Returns:
            List of company dicts, capped at 500 entries.
        """
        try:
            data = await self._request("bulk-fundamentals/SG", {"fmt": "json"})
            if not isinstance(data, dict):
                return []
            results: list[dict[str, Any]] = []
            for ticker, company in list(data.items())[:500]:
                results.append(
                    {
                        "ticker": ticker,
                        "general": company.get("General", {}),
                        "highlights": company.get("Highlights", {}),
                    }
                )
            return results
        except Exception:
            logger.warning("eodhd_bulk_fundamentals_failed", exchange="SG")
            return []

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


@lru_cache
def get_eodhd_client() -> EODHDClient:
    """Get cached EODHD client instance."""
    return EODHDClient()
