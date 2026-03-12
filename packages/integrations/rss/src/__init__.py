"""RSS integration — Singapore market intelligence feed ingestion."""

from .client import RSS_FEEDS, RSSArticle, RSSClient, get_rss_client

__all__ = [
    "RSS_FEEDS",
    "RSSArticle",
    "RSSClient",
    "get_rss_client",
]
