"""Executive Intelligence Service — news-based monitoring of listed company executives.

Sources (all public, no social scraping):
  1. NewsAPI: search by "FirstName LastName" + company name
  2. SGX RegNet: board-change announcements (Change in Directors/CEO/CFO)
  3. Existing MarketArticle table: executive name mentions already ingested

Why not LinkedIn: ToS violation + cost. News sources are more credible for
factual statements (speeches, interviews, regulatory filings).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.database.src.models import CompanyExecutive, ListedCompany, MarketArticle
from packages.integrations.newsapi.src.client import NewsAPIClient, get_newsapi_client
from packages.integrations.sgx.src.client import SGXClient, get_sgx_client

logger = structlog.get_logger()

# Board-change announcement categories to watch on SGX RegNet
_BOARD_CHANGE_CATEGORIES = [
    "Change in Directors",
    "Change in CEO",
    "Change in CFO",
]

# How many days before we consider an executive's news "stale" and recheck
_STALE_AFTER_DAYS = 7

# Maximum executives to process per run (NewsAPI free tier: 100 req/day)
_MAX_EXECUTIVES_PER_RUN = 50

# Batch size for DB commits
_COMMIT_BATCH_SIZE = 10


class ExecutiveIntelligenceService:
    """Monitors executives at listed companies via news and SGX filings.

    Sources (all public, no social scraping):
      1. NewsAPI: search by "FirstName LastName" + company name
      2. SGX RegNet: board-change announcements (Change in Directors/CEO)
      3. Existing MarketArticle table: search for executive name mentions

    Output: MarketArticle rows tagged with mentioned executive info,
    and CompanyExecutive.last_news_checked_at updated.

    Why not LinkedIn: ToS violation + cost. News sources are more credible
    for factual statements (speeches, interviews, regulatory filings).
    """

    def __init__(
        self,
        session: AsyncSession,
        newsapi_client: NewsAPIClient | None = None,
        sgx_client: SGXClient | None = None,
    ) -> None:
        self._session = session
        self._newsapi = newsapi_client or get_newsapi_client()
        self._sgx = sgx_client or get_sgx_client()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def monitor_executives(
        self,
        company_tickers: list[str] | None = None,
        days_back: int = 30,
        ceo_only: bool = False,
    ) -> dict[str, int]:
        """Scan news for executive mentions and persist as MarketArticle rows.

        Args:
            company_tickers: If None, check all active executives not checked
                in the last 7 days (up to _MAX_EXECUTIVES_PER_RUN).
            days_back: How far back to search for articles.
            ceo_only: If True, only monitor CEOs (reduces API calls).

        Returns:
            {"executives_checked": N, "articles_found": N, "new_articles": N}
        """
        stale_cutoff = datetime.now(UTC) - timedelta(days=_STALE_AFTER_DAYS)
        from_date = datetime.now(UTC) - timedelta(days=days_back)

        # Build query: active executives joined to their listed company + vertical
        stmt = (
            select(CompanyExecutive)
            .join(ListedCompany, CompanyExecutive.listed_company_id == ListedCompany.id)
            .options(
                joinedload(CompanyExecutive.listed_company).joinedload(ListedCompany.vertical)
            )
            .where(CompanyExecutive.is_active == True)  # noqa: E712
            .where(
                (CompanyExecutive.last_news_checked_at == None)  # noqa: E711
                | (CompanyExecutive.last_news_checked_at < stale_cutoff)
            )
        )

        if ceo_only:
            stmt = stmt.where(CompanyExecutive.is_ceo == True)  # noqa: E712

        if company_tickers:
            stmt = stmt.where(ListedCompany.ticker.in_(company_tickers))

        stmt = stmt.limit(_MAX_EXECUTIVES_PER_RUN)

        result = await self._session.execute(stmt)
        executives: list[CompanyExecutive] = list(result.scalars().all())

        executives_checked = 0
        articles_found = 0
        new_articles = 0
        batch_counter = 0

        for executive in executives:
            listed_company: ListedCompany = executive.listed_company
            vertical_slug: str | None = (
                listed_company.vertical.slug if listed_company.vertical else None
            )

            search_query = f'"{executive.name}" {listed_company.name}'

            log = logger.bind(
                executive=executive.name,
                ticker=listed_company.ticker,
                query=search_query,
            )

            try:
                search_result = await self._newsapi.search(
                    query=search_query,
                    from_date=from_date,
                    page_size=5,
                )
            except Exception as exc:
                log.warning("executive_intel.newsapi.error", error=str(exc))
                executive.last_news_checked_at = datetime.now(UTC)
                executives_checked += 1
                batch_counter += 1
                if batch_counter >= _COMMIT_BATCH_SIZE:
                    await self._session.commit()
                    batch_counter = 0
                await asyncio.sleep(0.2)
                continue

            articles_found += len(search_result.articles)

            for article in search_result.articles:
                inserted = await self._upsert_market_article(
                    source_name=article.source_name,
                    source_url=article.url,
                    title=article.title,
                    summary=article.description[:500] if article.description else None,
                    published_at=article.published_at,
                    signal_type="executive_mention",
                    vertical_slug=vertical_slug,
                    mentioned_tickers=[
                        {"ticker": listed_company.ticker, "exchange": listed_company.exchange}
                    ],
                )
                if inserted:
                    new_articles += 1

            executive.last_news_checked_at = datetime.now(UTC)
            executives_checked += 1
            batch_counter += 1

            if batch_counter >= _COMMIT_BATCH_SIZE:
                await self._session.commit()
                batch_counter = 0

            log.info(
                "executive_intel.executive_checked",
                articles_found=len(search_result.articles),
            )
            await asyncio.sleep(0.2)

        if batch_counter > 0:
            await self._session.commit()

        logger.info(
            "executive_intel.monitor_executives.done",
            executives_checked=executives_checked,
            articles_found=articles_found,
            new_articles=new_articles,
        )
        return {
            "executives_checked": executives_checked,
            "articles_found": articles_found,
            "new_articles": new_articles,
        }

    async def monitor_board_changes(self, days_back: int = 30) -> dict[str, int]:
        """Poll SGX RegNet for board change announcements across all SGX companies.

        Fetches "Change in Directors", "Change in CEO", and "Change in CFO"
        categories and persists them as MarketArticle rows with signal_type
        "board_change".

        Args:
            days_back: How far back to look for announcements.

        Returns:
            {"announcements_found": N, "executives_updated": N}
        """
        from_date = datetime.now(UTC) - timedelta(days=days_back)
        announcements_found = 0
        executives_updated = 0

        for category in _BOARD_CHANGE_CATEGORIES:
            try:
                announcements = await self._sgx.get_announcements(
                    category=category,
                    from_date=from_date,
                )
            except Exception as exc:
                logger.warning(
                    "executive_intel.sgx.error",
                    category=category,
                    error=str(exc),
                )
                continue

            for announcement in announcements:
                announcements_found += 1

                # Persist as MarketArticle
                article_title = f"[{category}] {announcement.title}"
                source_url = announcement.url or (
                    f"https://www.sgx.com/securities/equities/{announcement.stock_code}"
                    f"/announcements/{announcement.announcement_id}"
                )
                await self._upsert_market_article(
                    source_name="SGX RegNet",
                    source_url=source_url,
                    title=article_title[:500],
                    summary=None,
                    published_at=announcement.date,
                    signal_type="board_change",
                    vertical_slug=None,
                    mentioned_tickers=[
                        {"ticker": announcement.stock_code, "exchange": "SG"}
                    ],
                )

                # Try to find the matching listed company to log context
                company_stmt = select(ListedCompany).where(
                    ListedCompany.ticker == announcement.stock_code
                )
                company_result = await self._session.execute(company_stmt)
                listed_company = company_result.scalar_one_or_none()

                if listed_company:
                    executives_updated += 1
                    logger.info(
                        "executive_intel.board_change_detected",
                        category=category,
                        stock_code=announcement.stock_code,
                        company=listed_company.name,
                        announcement_title=announcement.title,
                    )
                else:
                    logger.info(
                        "executive_intel.board_change_detected",
                        category=category,
                        stock_code=announcement.stock_code,
                        announcement_title=announcement.title,
                    )

        await self._session.commit()

        logger.info(
            "executive_intel.monitor_board_changes.done",
            announcements_found=announcements_found,
            executives_updated=executives_updated,
        )
        return {
            "announcements_found": announcements_found,
            "executives_updated": executives_updated,
        }

    async def get_executive_profile(
        self,
        executive_id: str,
        include_recent_news: bool = True,
    ) -> dict[str, Any]:
        """Return a structured profile for one executive with recent news.

        Args:
            executive_id: UUID of the CompanyExecutive row.
            include_recent_news: Whether to include recent MarketArticle headlines.

        Returns:
            dict with name, title, company, tenure_years, recent_news_headlines,
            bio_snippet.
        """
        exec_stmt = (
            select(CompanyExecutive)
            .options(
                joinedload(CompanyExecutive.listed_company).joinedload(ListedCompany.vertical)
            )
            .where(CompanyExecutive.id == uuid.UUID(executive_id))
        )
        exec_result = await self._session.execute(exec_stmt)
        executive = exec_result.scalar_one_or_none()

        if executive is None:
            return {}

        listed_company: ListedCompany = executive.listed_company

        # Compute tenure_years from since_date (stored as "YYYY-MM-DD" string)
        tenure_years: float | None = None
        if executive.since_date:
            try:
                since = datetime.strptime(executive.since_date, "%Y-%m-%d").replace(tzinfo=UTC)
                tenure_years = round((datetime.now(UTC) - since).days / 365.25, 1)
            except ValueError:
                tenure_years = None

        recent_news_headlines: list[str] = []
        if include_recent_news:
            ticker = listed_company.ticker
            # Filter client-side for ticker membership (JSON array contains check).
            # SQLAlchemy JSON-contains syntax is dialect-specific; a portable approach
            # is to fetch the most recent executive_mention rows and filter in Python.
            # The volume of executive_mention rows is small, so this is acceptable.
            full_news_stmt = (
                select(MarketArticle)
                .where(MarketArticle.signal_type == "executive_mention")
                .order_by(MarketArticle.published_at.desc())
                .limit(50)
            )
            full_news_result = await self._session.execute(full_news_stmt)
            candidate_articles: list[MarketArticle] = list(full_news_result.scalars().all())

            for article in candidate_articles:
                tickers_list = article.mentioned_tickers or []
                if any(t.get("ticker") == ticker for t in tickers_list):
                    recent_news_headlines.append(article.title)
                if len(recent_news_headlines) >= 5:
                    break

        bio_snippet: str | None = None
        if executive.bio:
            bio_snippet = executive.bio[:300]

        return {
            "name": executive.name,
            "title": executive.title,
            "company": listed_company.name,
            "ticker": listed_company.ticker,
            "exchange": listed_company.exchange,
            "is_ceo": executive.is_ceo,
            "is_cfo": executive.is_cfo,
            "is_chair": executive.is_chair,
            "tenure_years": tenure_years,
            "age": executive.age,
            "bio_snippet": bio_snippet,
            "recent_news_headlines": recent_news_headlines,
            "last_news_checked_at": (
                executive.last_news_checked_at.isoformat()
                if executive.last_news_checked_at
                else None
            ),
        }

    async def search_executive_news(
        self,
        executive_name: str,
        company_name: str | None = None,
        days_back: int = 90,
    ) -> list[dict[str, Any]]:
        """On-demand search for executive news (called by MCP tool).

        Args:
            executive_name: Full name of the executive.
            company_name: Optional company name to narrow results.
            days_back: How many days back to search.

        Returns:
            List of dicts with title, source, published_at, url, summary
            (max 10 results).
        """
        query = f'"{executive_name}"'
        if company_name:
            query = f"{query} {company_name}"

        from_date = datetime.now(UTC) - timedelta(days=days_back)

        try:
            search_result = await self._newsapi.search(
                query=query,
                from_date=from_date,
                sort_by="relevancy",
                page_size=10,
            )
        except Exception as exc:
            logger.warning(
                "executive_intel.search_executive_news.error",
                executive_name=executive_name,
                error=str(exc),
            )
            return []

        return [
            {
                "title": article.title,
                "source": article.source_name,
                "published_at": article.published_at.isoformat(),
                "url": article.url,
                "summary": article.description[:300] if article.description else None,
            }
            for article in search_result.articles[:10]
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _upsert_market_article(
        self,
        source_name: str,
        source_url: str,
        title: str,
        summary: str | None,
        published_at: datetime,
        signal_type: str,
        vertical_slug: str | None,
        mentioned_tickers: list[dict[str, str]],
    ) -> bool:
        """Insert a MarketArticle row if source_url is not already present.

        Returns True if a new row was inserted, False if it already existed.
        """
        existing_stmt = select(MarketArticle.id).where(
            MarketArticle.source_url == source_url
        )
        existing = await self._session.execute(existing_stmt)
        if existing.scalar_one_or_none() is not None:
            return False

        article = MarketArticle(
            source_name=source_name,
            source_url=source_url,
            title=title[:500],
            summary=summary,
            published_at=published_at,
            signal_type=signal_type,
            vertical_slug=vertical_slug,
            mentioned_tickers=mentioned_tickers,
        )
        self._session.add(article)
        return True
