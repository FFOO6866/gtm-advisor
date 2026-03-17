"""RSS feed ingestion client for Singapore market intelligence.

Fetches and parses RSS feeds from Singapore business publications
concurrently, returning structured RSSArticle dataclass instances.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import feedparser
import structlog

logger = structlog.get_logger(__name__)

RSS_FEEDS: dict[str, str] = {
    # ── Business Times (multiple sections — /rss/all-news returns 0 entries) ─
    "Business Times Technology": "https://www.businesstimes.com.sg/rss/technology",
    "Business Times SME": "https://www.businesstimes.com.sg/rss/sme",
    "Business Times Property": "https://www.businesstimes.com.sg/rss/property",
    # Straits Times Business returns HTML (not RSS) — removed
    # ── Tech / Startup ────────────────────────────────────────────────────────
    "e27": "https://e27.co/feed/",
    # Tech in Asia blocks crawlers (HTTP 403) — removed
    "Vulcan Post": "https://vulcanpost.com/feed/",
    # ── Finance / Deals ───────────────────────────────────────────────────────
    # Deal Street Asia is intermittently down (HTTP 503) — removed
    "Fintech News Singapore": "https://fintechnews.sg/feed/",
    # ── General Singapore Business ────────────────────────────────────────────
    # CNA feedburner URL returns 404; direct API endpoints are live
    # cat 6511 = Business, cat 10416 = Singapore (general SG news with business relevance)
    "CNA Business": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",
    "CNA Singapore": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=10416",
    "Singapore Business Review": "https://sbr.com.sg/rss.xml",
    # ── Regulatory (blocked or dead) ─────────────────────────────────────────
    # MAS /news/media-releases.rss returns maintenance HTML — removed
    # Enterprise Singapore blocks crawlers (HTTP 403) — removed
    # SGX /rss/news returns HTML — removed
    # The Edge Singapore HTTP 403 — removed
}

# Vertical-specific industry trade publication feeds.
# Each entry: {"url": str, "name": str}.
# These are ingested alongside RSS_FEEDS but with vertical_slug pre-assigned —
# no LLM classifier needed.
VERTICAL_FEEDS: dict[str, list[dict[str, str]]] = {
    "marketing_comms": [
        # ── Verified working (2026-03-17) ──────────────────────────────────
        {"url": "https://feeds.feedburner.com/socialmediaexaminer", "name": "Social Media Examiner"},
        {"url": "https://blog.hubspot.com/marketing/rss.xml", "name": "HubSpot Marketing Blog"},
        {"url": "https://sproutsocial.com/insights/feed/", "name": "Sprout Social Insights"},
        {"url": "https://martech.org/feed/", "name": "MarTech"},
        {"url": "https://www.marketingdive.com/feeds/news/", "name": "Marketing Dive"},
        {"url": "https://digiday.com/feed/", "name": "Digiday"},
        # Campaign Asia (500), The Drum (404), PRWeek (directory page),
        # Marketing Interactive (404), Mumbrella Asia (403),
        # Content Marketing Institute (HTML not RSS) — all broken as of 2026-03-17
    ],
    "fintech": [
        {"url": "https://www.finextra.com/rss/headlines.aspx", "name": "Finextra"},
        {"url": "https://www.fintechnews.sg/feed/", "name": "Fintech News SG"},
    ],
    "ict_saas": [
        {"url": "https://techcrunch.com/feed/", "name": "TechCrunch"},
        {"url": "https://feeds.feedburner.com/venturebeat/SZYF", "name": "VentureBeat"},
    ],
}

# Thought-leadership feeds from major agency / consultancy blogs.
# Grouped by vertical, same shape as VERTICAL_FEEDS.
THOUGHT_LEADERSHIP_FEEDS: dict[str, list[dict[str, str]]] = {
    "marketing_comms": [
        # ── Verified working (2026-03-17) ──────────────────────────────────
        {"url": "https://fleishmanhillard.com/feed/", "name": "FleishmanHillard"},
        # Edelman (403), Ogilvy (404), Weber Shandwick (403) — no RSS feeds.
        # Compensated by MarTech, Marketing Dive, Digiday in VERTICAL_FEEDS.
    ],
}

_ARTICLE_LIMIT = 50
_SUMMARY_MAX_CHARS = 500


@dataclass
class RSSArticle:
    """A single article parsed from an RSS feed."""

    source_name: str
    title: str
    url: str
    summary: str | None
    published_at: datetime
    raw_tags: list[str] = field(default_factory=list)


def _parse_published_at(entry: feedparser.FeedParserDict) -> datetime:
    """Convert feedparser's time.struct_time to an aware datetime (UTC)."""
    struct = getattr(entry, "published_parsed", None)
    if struct is None:
        return datetime.now(UTC)
    try:
        return datetime(*struct[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _parse_entry(source_name: str, entry: feedparser.FeedParserDict) -> RSSArticle:
    """Build an RSSArticle from a feedparser entry dict."""
    title: str = entry.get("title", "").strip()
    url: str = entry.get("link", "")

    raw_summary: str = entry.get("summary", "") or entry.get("description", "") or ""
    summary: str | None = raw_summary[:_SUMMARY_MAX_CHARS] if raw_summary else None

    published_at = _parse_published_at(entry)

    raw_tags: list[str] = [
        t.get("term", "") for t in entry.get("tags", []) if t.get("term")
    ]

    return RSSArticle(
        source_name=source_name,
        title=title,
        url=url,
        summary=summary,
        published_at=published_at,
        raw_tags=raw_tags,
    )


class RSSClient:
    """Async client for ingesting RSS feeds from Singapore business publications.

    Uses feedparser (synchronous) via run_in_executor so the event loop is
    never blocked.  Feed failures are logged and return an empty list so that
    a single bad feed never kills the entire batch.
    """

    async def fetch_feed(
        self,
        feed_name: str,
        feed_url: str,
        since: datetime | None = None,
    ) -> list[RSSArticle]:
        """Fetch and parse a single RSS feed.

        Args:
            feed_name: Human-readable source name stored on each article.
            feed_url: Full URL of the RSS/Atom feed.
            since: If provided, skip articles published before this datetime.

        Returns:
            Parsed articles, up to 50 per feed.  Returns [] on any error.
        """
        loop = asyncio.get_running_loop()
        try:
            parsed: feedparser.FeedParserDict = await loop.run_in_executor(
                None, feedparser.parse, feed_url
            )
        except Exception:
            logger.warning(
                "rss.fetch_feed.parse_error",
                feed_name=feed_name,
                feed_url=feed_url,
                exc_info=True,
            )
            return []

        articles: list[RSSArticle] = []
        for entry in parsed.get("entries", []):
            try:
                article = _parse_entry(feed_name, entry)
            except Exception:
                logger.warning(
                    "rss.fetch_feed.entry_parse_error",
                    feed_name=feed_name,
                    exc_info=True,
                )
                continue

            if since is not None and article.published_at < since:
                continue

            articles.append(article)
            if len(articles) >= _ARTICLE_LIMIT:
                break

        logger.debug(
            "rss.fetch_feed.done",
            feed_name=feed_name,
            article_count=len(articles),
        )
        return articles

    async def fetch_all(
        self,
        since: datetime | None = None,
        feed_names: list[str] | None = None,
    ) -> dict[str, list[RSSArticle]]:
        """Fetch multiple RSS feeds concurrently.

        Args:
            since: Optional lower-bound for article publication time.
            feed_names: Subset of feed names to fetch.  Defaults to all feeds
                defined in RSS_FEEDS.

        Returns:
            Mapping of feed name → list of articles.  Feeds that fail return
            an empty list; no exception is raised.
        """
        target_feeds: dict[str, str]
        if feed_names is not None:
            target_feeds = {
                name: url for name, url in RSS_FEEDS.items() if name in feed_names
            }
        else:
            target_feeds = RSS_FEEDS

        tasks = [
            self.fetch_feed(name, url, since=since)
            for name, url in target_feeds.items()
        ]
        results: list[list[RSSArticle]] = await asyncio.gather(*tasks)

        return dict(zip(target_feeds.keys(), results, strict=True))

    async def fetch_recent(self, hours: int = 24) -> list[RSSArticle]:
        """Fetch all feeds and return articles from the last N hours.

        Args:
            hours: Look-back window in hours (default 24).

        Returns:
            Flat list of articles sorted by published_at descending.
        """
        since = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=hours)
        results = await self.fetch_all(since=since)
        return self.get_all_articles_flat(results)

    async def fetch_vertical_feeds(
        self,
        vertical_slug: str,
        hours: int = 24,
    ) -> list[RSSArticle]:
        """Fetch industry trade publication feeds for a specific vertical.

        Unlike ``fetch_recent()``, the vertical is KNOWN at call time, so no
        LLM classifier is required. The returned articles already have their
        ``source_name`` set to the feed's human-readable name; callers are
        responsible for stamping ``vertical_slug`` on the database row.

        Args:
            vertical_slug: Key into ``VERTICAL_FEEDS`` (e.g. ``"marketing_comms"``).
            hours: Look-back window in hours (default 24).

        Returns:
            Flat list of articles sorted by ``published_at`` descending.
            Returns [] when the slug is not registered in ``VERTICAL_FEEDS``.
        """
        feeds = VERTICAL_FEEDS.get(vertical_slug)
        if not feeds:
            logger.debug("fetch_vertical_feeds.unknown_slug", vertical_slug=vertical_slug)
            return []

        since = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=hours)
        tasks = [
            self.fetch_feed(feed["name"], feed["url"], since=since)
            for feed in feeds
        ]
        results: list[list[RSSArticle]] = await asyncio.gather(*tasks)
        flat: list[RSSArticle] = [a for batch in results for a in batch]
        flat.sort(key=lambda a: a.published_at, reverse=True)
        logger.debug(
            "fetch_vertical_feeds.done",
            vertical_slug=vertical_slug,
            article_count=len(flat),
        )
        return flat

    async def fetch_thought_leadership(
        self,
        vertical_slug: str,
        hours: int = 24,
    ) -> list[RSSArticle]:
        """Fetch agency/consultancy thought-leadership feeds for a vertical.

        Same contract as ``fetch_vertical_feeds()`` but reads from
        ``THOUGHT_LEADERSHIP_FEEDS``.

        Args:
            vertical_slug: Key into ``THOUGHT_LEADERSHIP_FEEDS``.
            hours: Look-back window in hours (default 24).

        Returns:
            Flat list sorted by ``published_at`` descending. Returns [] when
            the slug is not registered in ``THOUGHT_LEADERSHIP_FEEDS``.
        """
        feeds = THOUGHT_LEADERSHIP_FEEDS.get(vertical_slug)
        if not feeds:
            logger.debug(
                "fetch_thought_leadership.unknown_slug", vertical_slug=vertical_slug
            )
            return []

        since = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=hours)
        tasks = [
            self.fetch_feed(feed["name"], feed["url"], since=since)
            for feed in feeds
        ]
        results: list[list[RSSArticle]] = await asyncio.gather(*tasks)
        flat: list[RSSArticle] = [a for batch in results for a in batch]
        flat.sort(key=lambda a: a.published_at, reverse=True)
        logger.debug(
            "fetch_thought_leadership.done",
            vertical_slug=vertical_slug,
            article_count=len(flat),
        )
        return flat

    def get_all_articles_flat(
        self, results: dict[str, list[RSSArticle]]
    ) -> list[RSSArticle]:
        """Flatten fetch_all() output into a single sorted list.

        Args:
            results: Output of fetch_all().

        Returns:
            All articles sorted by published_at descending (newest first).
        """
        flat: list[RSSArticle] = [
            article for articles in results.values() for article in articles
        ]
        flat.sort(key=lambda a: a.published_at, reverse=True)
        return flat


@lru_cache
def get_rss_client() -> RSSClient:
    """Return the module-level singleton RSSClient."""
    return RSSClient()
