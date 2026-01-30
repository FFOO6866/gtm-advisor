"""News Aggregator MCP Server - Multiple news sources.

Aggregates news from:
- NewsAPI (80,000+ sources worldwide)
- Singapore-specific RSS feeds
- Press release services

Provides evidence-backed facts from news coverage with
full source attribution and confidence scoring.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any
from xml.etree import ElementTree

import httpx

from packages.integrations.newsapi.src import NewsAPIClient, get_newsapi_client
from packages.mcp.src.base import APIBasedMCPServer
from packages.mcp.src.types import (
    EvidencedFact,
    FactType,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)

# Singapore-specific RSS feeds
SINGAPORE_RSS_FEEDS = {
    "business_times": {
        "url": "https://www.businesstimes.com.sg/rss/singapore",
        "name": "Business Times Singapore",
    },
    "straits_times_business": {
        "url": "https://www.straitstimes.com/news/business/rss.xml",
        "name": "Straits Times Business",
    },
    "channel_news_asia": {
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",
        "name": "Channel NewsAsia Business",
    },
    "tech_in_asia": {
        "url": "https://www.techinasia.com/feed",
        "name": "Tech in Asia",
    },
    "e27": {
        "url": "https://e27.co/feed/",
        "name": "e27",
    },
}


# News categories for fact extraction
NEWS_FACT_PATTERNS = {
    "funding": [
        "raised",
        "funding",
        "series a",
        "series b",
        "series c",
        "seed round",
        "investment",
        "backed by",
    ],
    "acquisition": [
        "acquired",
        "acquisition",
        "buys",
        "merger",
        "acquires",
    ],
    "expansion": [
        "expands",
        "expansion",
        "opens office",
        "enters market",
        "launches in",
    ],
    "hiring": [
        "hires",
        "appoints",
        "names",
        "joins as",
        "new ceo",
        "new cto",
    ],
    "product": [
        "launches",
        "announces",
        "unveils",
        "introduces",
        "new product",
    ],
    "partnership": [
        "partners with",
        "partnership",
        "collaborates",
        "teams up",
        "alliance",
    ],
}


class NewsAggregatorMCPServer(APIBasedMCPServer):
    """MCP Server for aggregated news from multiple sources.

    Combines:
    - NewsAPI for global coverage
    - Singapore RSS feeds for local news
    - Press release monitoring

    Example:
        server = NewsAggregatorMCPServer.from_env()
        result = await server.search("fintech Singapore")
        for fact in result.facts:
            print(f"[{fact.source_name}] {fact.claim}")
    """

    def __init__(
        self,
        config: MCPServerConfig,
        newsapi_client: NewsAPIClient | None = None,
    ) -> None:
        """Initialize news aggregator.

        Args:
            config: Server configuration
            newsapi_client: Optional NewsAPI client
        """
        super().__init__(config)
        self._newsapi = newsapi_client or get_newsapi_client()
        self._http = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_env(cls) -> NewsAggregatorMCPServer:
        """Create server from environment variables."""
        api_key = os.getenv("NEWSAPI_API_KEY")
        config = MCPServerConfig(
            name="news-aggregator",
            source_type=SourceType.NEWSAPI,
            description="Aggregated news from NewsAPI and Singapore RSS feeds",
            api_key=api_key,
            requires_api_key=False,  # Can still use RSS without API key
            rate_limit_per_hour=100,
            cache_ttl_seconds=1800,  # 30 minutes - news changes often
        )
        return cls(config)

    @property
    def is_configured(self) -> bool:
        """Check if at least one news source is available."""
        # Always configured - RSS feeds don't need API key
        return True

    async def _health_check_impl(self) -> bool:
        """Check if news sources are accessible."""
        # Try RSS first (no API key needed)
        try:
            response = await self._http.get(
                SINGAPORE_RSS_FEEDS["e27"]["url"],
                follow_redirects=True,
            )
            if response.status_code == 200:
                return True
        except Exception:
            pass

        # Try NewsAPI if configured
        if self._newsapi.is_configured:
            return await self._newsapi.health_check()

        return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search news sources for relevant articles.

        Args:
            query: Search query
            **kwargs: Additional parameters:
                - days_back: How many days back to search (default 14)
                - include_rss: Include Singapore RSS feeds (default True)
                - include_newsapi: Include NewsAPI (default True)
                - category: News category filter

        Returns:
            Query result with news facts
        """
        days_back = kwargs.get("days_back", 14)
        include_rss = kwargs.get("include_rss", True)
        include_newsapi = kwargs.get("include_newsapi", True)

        # Check cache
        cache_key = f"news:{query}:{days_back}:{include_rss}:{include_newsapi}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        all_facts: list[EvidencedFact] = []
        all_errors: list[str] = []

        # Gather from multiple sources in parallel
        tasks = []

        if include_rss:
            tasks.append(self._search_rss_feeds(query))

        if include_newsapi and self._newsapi.is_configured:
            tasks.append(self._search_newsapi(query, days_back))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                all_errors.append(str(result))
            elif isinstance(result, list):
                all_facts.extend(result)

        # Deduplicate by title similarity
        deduped_facts = self._deduplicate_facts(all_facts)

        # Sort by published date
        deduped_facts.sort(
            key=lambda f: f.published_at or datetime.min,
            reverse=True,
        )

        result = MCPQueryResult(
            facts=deduped_facts,
            query=query,
            mcp_server=self.name,
            total_results=len(deduped_facts),
            errors=all_errors,
        )

        self._set_cached(cache_key, result)
        return result

    async def _search_newsapi(
        self, query: str, days_back: int
    ) -> list[EvidencedFact]:
        """Search NewsAPI for articles."""
        facts = []

        try:
            from_date = datetime.utcnow() - timedelta(days=days_back)
            result = await self._newsapi.search(
                query=query,
                from_date=from_date,
                sort_by="relevancy",
                page_size=30,
            )

            for article in result.articles:
                # Determine fact type from content
                fact_type = self._classify_article(article.title, article.description)

                facts.append(
                    self.create_fact(
                        claim=article.title,
                        fact_type=fact_type.value,
                        source_name=article.source_name,
                        source_url=article.url,
                        raw_excerpt=article.description or article.content,
                        published_at=article.published_at,
                        confidence=0.85,
                        extracted_data={
                            "author": article.author,
                            "source": article.source_name,
                        },
                    )
                )

        except Exception as e:
            self._logger.warning("newsapi_search_failed", error=str(e))

        return facts

    async def _search_rss_feeds(self, query: str) -> list[EvidencedFact]:
        """Search Singapore RSS feeds for relevant articles."""
        facts = []
        query_lower = query.lower()

        for feed_id, feed_config in SINGAPORE_RSS_FEEDS.items():
            try:
                feed_facts = await self._fetch_rss_feed(
                    feed_config["url"],
                    feed_config["name"],
                    query_lower,
                )
                facts.extend(feed_facts)
            except Exception as e:
                self._logger.warning(
                    "rss_feed_failed",
                    feed=feed_id,
                    error=str(e),
                )

        return facts

    async def _fetch_rss_feed(
        self,
        url: str,
        source_name: str,
        query: str,
    ) -> list[EvidencedFact]:
        """Fetch and parse a single RSS feed."""
        facts = []

        try:
            response = await self._http.get(url, follow_redirects=True)
            response.raise_for_status()

            # Parse XML
            root = ElementTree.fromstring(response.content)

            # Handle different RSS formats
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items[:20]:  # Limit per feed
                title = self._get_rss_element(item, "title")
                link = self._get_rss_element(item, "link")
                description = self._get_rss_element(item, "description")
                pub_date = self._get_rss_element(item, "pubDate")

                if not title or not link:
                    continue

                # Filter by query relevance
                content = f"{title} {description or ''}".lower()
                if query and query not in content:
                    # Check for partial matches
                    query_words = query.split()
                    if not any(word in content for word in query_words):
                        continue

                # Parse date
                published_at = self._parse_rss_date(pub_date)

                # Classify article
                fact_type = self._classify_article(title, description)

                facts.append(
                    self.create_fact(
                        claim=title,
                        fact_type=fact_type.value,
                        source_name=source_name,
                        source_url=link,
                        raw_excerpt=description[:500] if description else None,
                        published_at=published_at,
                        confidence=0.80,  # RSS slightly lower confidence
                        extracted_data={
                            "source": source_name,
                            "feed_url": url,
                        },
                    )
                )

        except Exception as e:
            self._logger.warning("rss_parse_failed", url=url, error=str(e))

        return facts

    def _get_rss_element(self, item: ElementTree.Element, tag: str) -> str | None:
        """Get text from RSS element, handling namespaces."""
        # Try standard RSS
        elem = item.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()

        # Try Atom namespace
        atom_ns = "{http://www.w3.org/2005/Atom}"
        elem = item.find(f"{atom_ns}{tag}")
        if elem is not None:
            if tag == "link" and elem.get("href"):
                return elem.get("href")
            if elem.text:
                return elem.text.strip()

        return None

    def _parse_rss_date(self, date_str: str | None) -> datetime | None:
        """Parse various RSS date formats."""
        if not date_str:
            return None

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _classify_article(
        self, title: str, description: str | None
    ) -> FactType:
        """Classify article into fact type based on content."""
        content = f"{title} {description or ''}".lower()

        # Map category to fact type
        category_to_fact_type = {
            "funding": FactType.FUNDING,
            "acquisition": FactType.ACQUISITION,
            "expansion": FactType.EXPANSION,
            "hiring": FactType.EXECUTIVE,
            "product": FactType.PRODUCT,
            "partnership": FactType.PARTNERSHIP,
        }

        for fact_category, patterns in NEWS_FACT_PATTERNS.items():
            if any(pattern in content for pattern in patterns):
                if fact_category in category_to_fact_type:
                    return category_to_fact_type[fact_category]

        return FactType.MARKET_TREND

    def _deduplicate_facts(
        self, facts: list[EvidencedFact]
    ) -> list[EvidencedFact]:
        """Remove duplicate facts based on title similarity."""
        seen_titles: set[str] = set()
        unique_facts = []

        for fact in facts:
            # Normalize title for comparison
            normalized = fact.claim.lower()[:100]

            if normalized not in seen_titles:
                seen_titles.add(normalized)
                unique_facts.append(fact)

        return unique_facts

    async def get_singapore_business_news(
        self,
        days_back: int = 7,
    ) -> MCPQueryResult:
        """Get Singapore business news from all sources.

        Convenience method for Singapore-focused research.
        """
        return await self.search(
            "Singapore business startup",
            days_back=days_back,
            include_rss=True,
            include_newsapi=True,
        )

    async def get_funding_news(
        self,
        region: str = "Singapore",
        days_back: int = 14,
    ) -> MCPQueryResult:
        """Get funding and investment news."""
        return await self.search(
            f"{region} funding series investment raised",
            days_back=days_back,
        )

    async def monitor_company(
        self,
        company_name: str,
        days_back: int = 30,
    ) -> MCPQueryResult:
        """Monitor news for a specific company."""
        return await self.search(
            f'"{company_name}"',
            days_back=days_back,
        )

    async def close(self) -> None:
        """Close HTTP clients."""
        await self._http.aclose()
        await self._newsapi.close()
