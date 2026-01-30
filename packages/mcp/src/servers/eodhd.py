"""EODHD MCP Server - Financial and Company Data.

Wraps the existing EODHD client to produce evidence-backed facts from
financial data sources. Provides company fundamentals, economic indicators,
and financial news.

Useful for:
- Analyzing public companies
- Understanding market conditions
- Competitive intelligence on public competitors
"""

from __future__ import annotations

import os
from typing import Any

from packages.integrations.eodhd.src import EODHDClient, get_eodhd_client
from packages.mcp.src.base import APIBasedMCPServer
from packages.mcp.src.types import (
    EntityReference,
    EntityType,
    EvidencedFact,
    FactType,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)


class EODHDMCPServer(APIBasedMCPServer):
    """MCP Server for EODHD financial data.

    Converts EODHD API responses into evidence-backed facts with
    proper provenance tracking.

    Example:
        server = EODHDMCPServer.from_env()
        result = await server.search("AAPL")
        for fact in result.facts:
            print(f"{fact.claim}")
    """

    def __init__(self, config: MCPServerConfig, client: EODHDClient | None = None) -> None:
        """Initialize EODHD MCP server.

        Args:
            config: Server configuration
            client: Optional EODHD client (uses singleton if not provided)
        """
        super().__init__(config)
        self._eodhd = client or get_eodhd_client()

    @classmethod
    def from_env(cls) -> EODHDMCPServer:
        """Create server from environment variables."""
        api_key = os.getenv("EODHD_API_KEY")
        config = MCPServerConfig(
            name="eodhd-financial",
            source_type=SourceType.EODHD,
            description="EODHD financial data and company fundamentals",
            api_key=api_key,
            requires_api_key=True,
            rate_limit_per_hour=500,  # EODHD has generous limits
            rate_limit_per_day=5000,
            cache_ttl_seconds=3600,  # 1 hour
        )
        return cls(config)

    @property
    def is_configured(self) -> bool:
        """Check if EODHD client is configured."""
        return self._eodhd.is_configured

    async def _health_check_impl(self) -> bool:
        """Check EODHD API health."""
        return await self._eodhd.health_check()

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search EODHD for company data.

        This method routes to the appropriate EODHD API based on query type.

        Args:
            query: Company name, symbol, or search term
            **kwargs: Additional parameters:
                - search_type: "company", "indicators", "news"
                - exchange: Stock exchange code
                - country: Country for economic indicators

        Returns:
            Query result with financial facts
        """
        search_type = kwargs.get("search_type", "company")
        exchange = kwargs.get("exchange", "US")
        country = kwargs.get("country", "SGP")

        # Check cache
        cache_key = f"eodhd:{search_type}:{query}:{exchange}:{country}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            if search_type == "indicators":
                result = await self._get_economic_indicators(country)
            elif search_type == "news":
                result = await self._get_financial_news(query)
            else:
                result = await self._search_company(query, exchange)

            self._set_cached(cache_key, result)
            return result

        except Exception as e:
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"EODHD query failed: {str(e)}"],
            )

    async def _search_company(self, query: str, exchange: str) -> MCPQueryResult:
        """Search for company fundamentals."""
        facts = []
        entities = []

        # First, search for companies
        companies = await self._eodhd.search_companies(query, exchange=exchange, limit=5)

        for company in companies:
            symbol = company.get("Code", "")
            name = company.get("Name", "")
            company_exchange = company.get("Exchange", exchange)

            if not symbol:
                continue

            # Get detailed fundamentals
            fundamentals = await self._eodhd.get_company_fundamentals(
                symbol, company_exchange
            )

            if fundamentals:
                company_facts, entity = self._parse_fundamentals(fundamentals)
                facts.extend(company_facts)
                if entity:
                    entities.append(entity)
            else:
                # Create basic fact from search result
                facts.append(
                    self.create_fact(
                        claim=f"{name} ({symbol}) is listed on {company_exchange}",
                        fact_type=FactType.COMPANY_INFO.value,
                        source_name="EODHD",
                        source_url=f"https://eodhd.com/financial-apis/stock-{symbol}",
                        confidence=0.85,
                        extracted_data={
                            "symbol": symbol,
                            "name": name,
                            "exchange": company_exchange,
                        },
                        related_entities=[name],
                    )
                )

        return MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(companies),
        )

    def _parse_fundamentals(
        self, fundamentals: Any
    ) -> tuple[list[EvidencedFact], EntityReference | None]:
        """Parse company fundamentals into facts."""
        facts = []

        symbol = fundamentals.symbol
        name = fundamentals.name
        exchange = fundamentals.exchange
        source_url = f"https://eodhd.com/financial-apis/stock-{symbol}"

        # Fact: Company info
        if name and fundamentals.industry:
            facts.append(
                self.create_fact(
                    claim=f"{name} is a {fundamentals.industry} company in the {fundamentals.sector or 'N/A'} sector",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="EODHD",
                    source_url=source_url,
                    confidence=0.90,
                    extracted_data={
                        "symbol": symbol,
                        "name": name,
                        "industry": fundamentals.industry,
                        "sector": fundamentals.sector,
                    },
                    related_entities=[name],
                )
            )

        # Fact: Market cap (financial)
        if fundamentals.market_cap and fundamentals.market_cap > 0:
            market_cap_b = fundamentals.market_cap / 1_000_000_000
            facts.append(
                self.create_fact(
                    claim=f"{name} has a market capitalization of ${market_cap_b:.2f}B",
                    fact_type=FactType.FINANCIAL.value,
                    source_name="EODHD",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={
                        "symbol": symbol,
                        "market_cap": fundamentals.market_cap,
                        "market_cap_billions": round(market_cap_b, 2),
                        "currency": fundamentals.currency,
                    },
                    related_entities=[name],
                )
            )

        # Fact: Revenue
        if fundamentals.revenue and fundamentals.revenue > 0:
            revenue_b = fundamentals.revenue / 1_000_000_000
            facts.append(
                self.create_fact(
                    claim=f"{name} reported revenue of ${revenue_b:.2f}B",
                    fact_type=FactType.FINANCIAL.value,
                    source_name="EODHD",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={
                        "symbol": symbol,
                        "revenue": fundamentals.revenue,
                        "revenue_billions": round(revenue_b, 2),
                        "currency": fundamentals.currency,
                    },
                    related_entities=[name],
                )
            )

        # Fact: Employees
        if fundamentals.employees:
            facts.append(
                self.create_fact(
                    claim=f"{name} has approximately {fundamentals.employees:,} employees",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="EODHD",
                    source_url=source_url,
                    confidence=0.85,
                    extracted_data={
                        "symbol": symbol,
                        "employee_count": fundamentals.employees,
                    },
                    related_entities=[name],
                )
            )

        # Fact: PE Ratio
        if fundamentals.pe_ratio:
            facts.append(
                self.create_fact(
                    claim=f"{name} trades at a P/E ratio of {fundamentals.pe_ratio:.1f}",
                    fact_type=FactType.FINANCIAL.value,
                    source_name="EODHD",
                    source_url=source_url,
                    confidence=0.90,
                    extracted_data={
                        "symbol": symbol,
                        "pe_ratio": fundamentals.pe_ratio,
                    },
                    related_entities=[name],
                )
            )

        # Create entity reference
        entity = EntityReference(
            entity_type=EntityType.COMPANY,
            name=name,
            canonical_name=name.upper(),
            website=fundamentals.website,
            external_ids={
                "eodhd_symbol": f"{symbol}.{exchange}",
            },
        )

        return facts, entity

    async def _get_economic_indicators(self, country: str) -> MCPQueryResult:
        """Get economic indicators for a country."""
        indicators = await self._eodhd.get_economic_indicators(country)

        facts = []
        for ind in indicators:
            facts.append(
                self.create_fact(
                    claim=f"{country} {ind.indicator}: {ind.value} ({ind.period})",
                    fact_type=FactType.MARKET_TREND.value,
                    source_name="EODHD Economic Data",
                    source_url="https://eodhd.com/financial-apis/economic-data-api",
                    published_at=ind.date,
                    confidence=0.90,
                    extracted_data={
                        "indicator": ind.indicator,
                        "country": country,
                        "value": ind.value,
                        "previous_value": ind.previous_value,
                        "change": ind.change,
                        "period": ind.period,
                    },
                )
            )

        return MCPQueryResult(
            facts=facts,
            query=f"indicators:{country}",
            mcp_server=self.name,
            total_results=len(indicators),
        )

    async def _get_financial_news(self, query: str) -> MCPQueryResult:
        """Get financial news."""
        news_items = await self._eodhd.get_financial_news(symbol=query, limit=20)

        facts = []
        for news in news_items:
            facts.append(
                self.create_fact(
                    claim=news.title,
                    fact_type=FactType.MARKET_TREND.value,
                    source_name="EODHD Financial News",
                    source_url=news.link,
                    raw_excerpt=news.content[:500] if news.content else None,
                    published_at=news.date,
                    confidence=0.80,
                    extracted_data={
                        "symbols": news.symbols,
                        "tags": news.tags,
                        "sentiment": news.sentiment,
                    },
                    related_entities=news.symbols,
                )
            )

        return MCPQueryResult(
            facts=facts,
            query=f"news:{query}",
            mcp_server=self.name,
            total_results=len(news_items),
        )

    async def get_singapore_data(self) -> MCPQueryResult:
        """Get Singapore-specific market data.

        Convenience method for Singapore-focused analysis.
        """
        # Get economic indicators
        indicators_result = await self._get_economic_indicators("SGP")

        # Search Singapore exchange
        sg_companies = await self._eodhd.search_companies("", exchange="SG", limit=10)

        # Combine facts
        facts = indicators_result.facts.copy()

        for company in sg_companies:
            symbol = company.get("Code", "")
            name = company.get("Name", "")
            if symbol and name:
                facts.append(
                    self.create_fact(
                        claim=f"{name} ({symbol}) is listed on Singapore Exchange (SGX)",
                        fact_type=FactType.COMPANY_INFO.value,
                        source_name="EODHD",
                        source_url=f"https://eodhd.com/financial-apis/stock-{symbol}.SG",
                        confidence=0.85,
                        extracted_data={
                            "symbol": symbol,
                            "name": name,
                            "exchange": "SG",
                        },
                        related_entities=[name],
                    )
                )

        return MCPQueryResult(
            facts=facts,
            query="singapore_market",
            mcp_server=self.name,
            total_results=len(facts),
        )

    async def close(self) -> None:
        """Close EODHD client."""
        await self._eodhd.close()
