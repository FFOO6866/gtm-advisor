"""NewsAPI Client for market news and trends.

NewsAPI provides access to news articles from over 80,000 sources worldwide.
Useful for market research, competitor monitoring, and trend analysis.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx
from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    """News article from NewsAPI."""

    title: str = Field(...)
    description: str | None = Field(default=None)
    author: str | None = Field(default=None)
    source_name: str = Field(...)
    url: str = Field(...)
    published_at: datetime = Field(...)
    content: str | None = Field(default=None)


class NewsSearchResult(BaseModel):
    """Search result from NewsAPI."""

    total_results: int = Field(default=0)
    articles: list[NewsArticle] = Field(default_factory=list)
    query: str = Field(...)


class NewsAPIClient:
    """Client for NewsAPI integration.

    Provides access to global news for market research and trend analysis.

    Features:
    - Search news by keywords
    - Filter by date range
    - Filter by source/domain
    - Get top headlines by category/country
    """

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("NEWSAPI_API_KEY")
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return self._api_key is not None and len(self._api_key) > 0

    async def health_check(self) -> bool:
        """Check if NewsAPI is accessible."""
        if not self.is_configured:
            return False
        try:
            # Use a minimal query to check connectivity
            result = await self.search("test", page_size=1)
            return True
        except Exception:
            return False

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Make request to NewsAPI.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            API response

        Raises:
            Exception: If request fails
        """
        if not self.is_configured:
            raise ValueError("NewsAPI API key not configured")

        params["apiKey"] = self._api_key
        url = f"{self.BASE_URL}/{endpoint}"

        response = await self._client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        if data.get("status") != "ok":
            raise Exception(f"NewsAPI error: {data.get('message', 'Unknown error')}")

        return data

    async def search(
        self,
        query: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        language: str = "en",
        sort_by: str = "relevancy",
        page: int = 1,
        page_size: int = 20,
    ) -> NewsSearchResult:
        """Search news articles.

        Args:
            query: Search keywords
            from_date: Start date for articles
            to_date: End date for articles
            domains: Domains to include (e.g., ['techcrunch.com', 'wired.com'])
            exclude_domains: Domains to exclude
            language: Article language (default: en)
            sort_by: Sort order (relevancy, popularity, publishedAt)
            page: Page number
            page_size: Results per page (max 100)

        Returns:
            Search results with articles
        """
        params: dict[str, Any] = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "page": page,
            "pageSize": min(page_size, 100),
        }

        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if domains:
            params["domains"] = ",".join(domains)
        if exclude_domains:
            params["excludeDomains"] = ",".join(exclude_domains)

        data = await self._request("everything", params)

        articles = [
            NewsArticle(
                title=article["title"] or "",
                description=article.get("description"),
                author=article.get("author"),
                source_name=article.get("source", {}).get("name", "Unknown"),
                url=article["url"],
                published_at=datetime.fromisoformat(
                    article["publishedAt"].replace("Z", "+00:00")
                ),
                content=article.get("content"),
            )
            for article in data.get("articles", [])
            if article.get("title")  # Skip articles without titles
        ]

        return NewsSearchResult(
            total_results=data.get("totalResults", 0),
            articles=articles,
            query=query,
        )

    async def get_top_headlines(
        self,
        category: str | None = None,
        country: str = "sg",  # Singapore
        query: str | None = None,
        page_size: int = 20,
    ) -> NewsSearchResult:
        """Get top headlines.

        Args:
            category: Category (business, technology, etc.)
            country: Country code (sg for Singapore)
            query: Optional search keywords
            page_size: Results per page

        Returns:
            Top headlines
        """
        params: dict[str, Any] = {
            "country": country,
            "pageSize": min(page_size, 100),
        }

        if category:
            params["category"] = category
        if query:
            params["q"] = query

        data = await self._request("top-headlines", params)

        articles = [
            NewsArticle(
                title=article["title"] or "",
                description=article.get("description"),
                author=article.get("author"),
                source_name=article.get("source", {}).get("name", "Unknown"),
                url=article["url"],
                published_at=datetime.fromisoformat(
                    article["publishedAt"].replace("Z", "+00:00")
                ),
                content=article.get("content"),
            )
            for article in data.get("articles", [])
            if article.get("title")
        ]

        return NewsSearchResult(
            total_results=data.get("totalResults", 0),
            articles=articles,
            query=query or f"headlines:{country}",
        )

    async def search_market_news(
        self,
        industry: str,
        region: str = "Singapore",
        days_back: int = 7,
    ) -> NewsSearchResult:
        """Search for market-specific news.

        Convenience method for GTM research.

        Args:
            industry: Industry to search (e.g., fintech, SaaS)
            region: Geographic region focus
            days_back: How many days back to search

        Returns:
            Market news results
        """
        query = f"{industry} {region} market startup business"
        from_date = datetime.utcnow() - timedelta(days=days_back)

        return await self.search(
            query=query,
            from_date=from_date,
            sort_by="relevancy",
            page_size=30,
        )

    async def search_competitor_news(
        self,
        competitor_name: str,
        days_back: int = 30,
    ) -> NewsSearchResult:
        """Search for competitor-specific news.

        Args:
            competitor_name: Competitor company name
            days_back: How many days back to search

        Returns:
            Competitor news results
        """
        from_date = datetime.utcnow() - timedelta(days=days_back)

        return await self.search(
            query=f'"{competitor_name}"',
            from_date=from_date,
            sort_by="publishedAt",
            page_size=20,
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


@lru_cache
def get_newsapi_client() -> NewsAPIClient:
    """Get cached NewsAPI client instance."""
    return NewsAPIClient()
