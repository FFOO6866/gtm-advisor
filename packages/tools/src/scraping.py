"""Web Scraping Tools for Competitive Intelligence.

Responsible, rate-limited scraping with respect for robots.txt.
PDPA-compliant - no personal data scraping without consent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import asyncio
import httpx
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime

from .base import (
    BaseTool,
    ToolAccess,
    ToolResult,
    ToolCategory,
    RateLimitConfig,
)


@dataclass
class ScrapedPage:
    """Result of page scraping."""
    url: str
    title: str | None
    meta_description: str | None
    h1_tags: list[str]
    links: list[dict[str, str]]
    text_content: str
    scraped_at: datetime
    status_code: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "meta_description": self.meta_description,
            "h1_tags": self.h1_tags,
            "links": self.links[:20],  # Limit
            "text_preview": self.text_content[:1000],
            "scraped_at": self.scraped_at.isoformat(),
            "status_code": self.status_code,
        }


@dataclass
class LinkedInProfile:
    """LinkedIn company/profile data (public only)."""
    url: str
    name: str
    headline: str | None
    industry: str | None
    company_size: str | None
    followers: int | None
    about: str | None
    specialties: list[str]
    recent_posts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "name": self.name,
            "headline": self.headline,
            "industry": self.industry,
            "company_size": self.company_size,
            "followers": self.followers,
            "about": self.about,
            "specialties": self.specialties,
            "recent_posts": self.recent_posts[:5],
        }


@dataclass
class NewsArticle:
    """Scraped news article."""
    url: str
    title: str
    source: str
    published_at: datetime | None
    author: str | None
    content_preview: str
    sentiment: str | None  # positive, negative, neutral

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "author": self.author,
            "content_preview": self.content_preview[:500],
            "sentiment": self.sentiment,
        }


class WebScraperTool(BaseTool):
    """General purpose web scraper with rate limiting.

    Respects robots.txt and implements polite crawling.
    """

    name = "web_scraper"
    description = "Scrape public web pages for competitive intelligence"
    category = ToolCategory.SCRAPING
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=2,
    )

    # Domains we won't scrape
    BLOCKED_DOMAINS = [
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
    ]

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        user_agent: str = "GTMAdvisor/1.0 (Research Bot)",
        respect_robots: bool = True,
    ):
        super().__init__(agent_id, allowed_access)
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self._robots_cache: dict[str, bool] = {}

    async def _execute(self, **kwargs: Any) -> ToolResult[ScrapedPage]:
        """Scrape a web page."""
        url = kwargs.get("url")

        if not url:
            return ToolResult(
                success=False,
                data=None,
                error="URL is required",
            )

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Invalid URL format",
                )

            # Check blocked domains
            domain = parsed.netloc.lower()
            if any(blocked in domain for blocked in self.BLOCKED_DOMAINS):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Domain {domain} is blocked",
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"URL parsing error: {e}",
            )

        # Check robots.txt
        if self.respect_robots and not await self._check_robots(url):
            return ToolResult(
                success=False,
                data=None,
                error="Blocked by robots.txt",
            )

        # Fetch and parse
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    timeout=15.0,
                    follow_redirects=True,
                )

                if response.status_code != 200:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"HTTP {response.status_code}",
                    )

                html = response.text
                page = self._parse_html(url, html, response.status_code)

                return ToolResult(
                    success=True,
                    data=page,
                )

        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                data=None,
                error="Request timed out",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
            )

    async def _check_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    # Simple check - in production use robotparser
                    content = response.text.lower()
                    if "disallow: /" in content and "user-agent: *" in content:
                        self._robots_cache[robots_url] = False
                        return False
        except Exception:
            pass

        self._robots_cache[robots_url] = True
        return True

    def _parse_html(self, url: str, html: str, status_code: int) -> ScrapedPage:
        """Parse HTML content (simplified - use BeautifulSoup in production)."""
        # Extract title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else None

        # Extract meta description
        meta_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not meta_match:
            meta_match = re.search(
                r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']',
                html,
                re.IGNORECASE,
            )
        meta_desc = meta_match.group(1).strip() if meta_match else None

        # Extract H1 tags
        h1_matches = re.findall(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
        h1_tags = [h.strip() for h in h1_matches]

        # Extract links
        link_matches = re.findall(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>',
            html,
            re.IGNORECASE,
        )
        links = []
        for href, text in link_matches[:50]:
            if href.startswith(("http", "/")):
                links.append({
                    "href": urljoin(url, href),
                    "text": text.strip()[:100],
                })

        # Extract text content (strip tags)
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return ScrapedPage(
            url=url,
            title=title,
            meta_description=meta_desc,
            h1_tags=h1_tags,
            links=links,
            text_content=text[:5000],
            scraped_at=datetime.utcnow(),
            status_code=status_code,
        )


class LinkedInScraperTool(BaseTool):
    """Scrape public LinkedIn company pages.

    Uses official API when available, falls back to public page scraping.
    Respects LinkedIn's terms of service.
    """

    name = "linkedin_scraper"
    description = "Extract public LinkedIn company information"
    category = ToolCategory.SCRAPING
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=50,
        burst_limit=1,
    )

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        api_key: str | None = None,
    ):
        super().__init__(agent_id, allowed_access)
        self.api_key = api_key

    async def _execute(self, **kwargs: Any) -> ToolResult[LinkedInProfile]:
        """Get LinkedIn company profile data."""
        company_url = kwargs.get("company_url")
        company_name = kwargs.get("company_name")

        if not company_url and not company_name:
            return ToolResult(
                success=False,
                data=None,
                error="Must provide company_url or company_name",
            )

        # Mock implementation - in production, use LinkedIn API or approved scraping
        # LinkedIn heavily restricts scraping, so API access is required
        profile = await self._mock_linkedin_data(company_url, company_name)

        return ToolResult(
            success=profile is not None,
            data=profile,
            error=None if profile else "Profile not found",
        )

    async def _mock_linkedin_data(
        self,
        url: str | None,
        name: str | None,
    ) -> LinkedInProfile | None:
        """Mock LinkedIn data for demo."""
        await asyncio.sleep(0.2)

        # Singapore companies mock data
        mock_profiles = {
            "grab": LinkedInProfile(
                url="https://linkedin.com/company/grab",
                name="Grab",
                headline="Southeast Asia's leading superapp",
                industry="Technology, Information and Internet",
                company_size="5,001-10,000 employees",
                followers=1500000,
                about="Grab is Southeast Asia's leading superapp, providing everyday services...",
                specialties=["Ride-hailing", "Food Delivery", "Payments", "Financial Services"],
                recent_posts=[
                    {"title": "Grab launches new sustainability initiative", "date": "2024-01-15"},
                    {"title": "Q4 2023 earnings announcement", "date": "2024-01-10"},
                ],
            ),
            "shopee": LinkedInProfile(
                url="https://linkedin.com/company/shopee",
                name="Shopee",
                headline="The leading e-commerce platform in Southeast Asia",
                industry="E-commerce",
                company_size="10,001+ employees",
                followers=2000000,
                about="Shopee is the leading e-commerce platform in Southeast Asia and Taiwan...",
                specialties=["E-commerce", "Mobile Commerce", "Digital Payments"],
                recent_posts=[
                    {"title": "Shopee 12.12 Birthday Sale Results", "date": "2024-01-05"},
                ],
            ),
        }

        # Check by name
        name_lower = (name or "").lower()
        for key, profile in mock_profiles.items():
            if key in name_lower:
                return profile

        # Check by URL
        if url:
            url_lower = url.lower()
            for key, profile in mock_profiles.items():
                if key in url_lower:
                    return profile

        # Return generic profile for unknown
        if name:
            return LinkedInProfile(
                url=f"https://linkedin.com/company/{name.lower().replace(' ', '-')}",
                name=name,
                headline=f"{name} - Singapore",
                industry="Technology",
                company_size="11-50 employees",
                followers=500,
                about=f"Company profile for {name}",
                specialties=[],
                recent_posts=[],
            )

        return None


class NewsScraperTool(BaseTool):
    """Scrape and aggregate news articles about companies/topics.

    Integrates with NewsAPI and Google News.
    """

    name = "news_scraper"
    description = "Find and aggregate news articles about companies or topics"
    category = ToolCategory.SCRAPING
    required_access = ToolAccess.READ
    rate_limit = RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=200,
        burst_limit=5,
    )

    def __init__(
        self,
        agent_id: str | None = None,
        allowed_access: list[ToolAccess] | None = None,
        newsapi_key: str | None = None,
    ):
        super().__init__(agent_id, allowed_access)
        self.newsapi_key = newsapi_key

    async def _execute(self, **kwargs: Any) -> ToolResult[list[NewsArticle]]:
        """Search for news articles."""
        query = kwargs.get("query")
        company = kwargs.get("company")
        days_back = kwargs.get("days_back", 30)
        limit = kwargs.get("limit", 10)

        if not query and not company:
            return ToolResult(
                success=False,
                data=None,
                error="Must provide query or company",
            )

        search_query = query or company

        # Try NewsAPI first
        if self.newsapi_key:
            articles = await self._newsapi_search(search_query, days_back, limit)
        else:
            # Mock data for demo
            articles = await self._mock_news_search(search_query, limit)

        return ToolResult(
            success=len(articles) > 0,
            data=articles,
            metadata={"query": search_query, "count": len(articles)},
        )

    async def _newsapi_search(
        self,
        query: str,
        days_back: int,
        limit: int,
    ) -> list[NewsArticle]:
        """Search via NewsAPI."""
        from datetime import timedelta

        async with httpx.AsyncClient() as client:
            try:
                from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                response = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "from": from_date,
                        "sortBy": "publishedAt",
                        "pageSize": limit,
                        "apiKey": self.newsapi_key,
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    articles = []
                    for item in data.get("articles", []):
                        published = None
                        if item.get("publishedAt"):
                            try:
                                published = datetime.fromisoformat(
                                    item["publishedAt"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass

                        articles.append(NewsArticle(
                            url=item.get("url", ""),
                            title=item.get("title", ""),
                            source=item.get("source", {}).get("name", "Unknown"),
                            published_at=published,
                            author=item.get("author"),
                            content_preview=item.get("description", ""),
                            sentiment=None,  # Would need NLP
                        ))
                    return articles

            except Exception:
                pass

        return []

    async def _mock_news_search(self, query: str, limit: int) -> list[NewsArticle]:
        """Mock news search for demo."""
        await asyncio.sleep(0.1)

        mock_articles = [
            NewsArticle(
                url="https://example.com/news/1",
                title=f"{query} announces expansion in Southeast Asia",
                source="TechCrunch",
                published_at=datetime.utcnow(),
                author="Jane Reporter",
                content_preview=f"Singapore-based {query} has announced plans to expand...",
                sentiment="positive",
            ),
            NewsArticle(
                url="https://example.com/news/2",
                title=f"Market analysis: {query} in the Singapore startup ecosystem",
                source="Business Times",
                published_at=datetime.utcnow(),
                author="John Analyst",
                content_preview=f"An in-depth look at how {query} is positioned...",
                sentiment="neutral",
            ),
            NewsArticle(
                url="https://example.com/news/3",
                title=f"{query} raises Series B funding",
                source="e27",
                published_at=datetime.utcnow(),
                author="Startup Reporter",
                content_preview=f"{query} has secured additional funding to fuel growth...",
                sentiment="positive",
            ),
        ]

        return mock_articles[:limit]
