"""Base MCP Server abstraction.

MCP (Model Context Protocol) servers are the data sources for the
Knowledge Web. Each server collects evidence-backed facts from a
specific source type (ACRA, NewsAPI, web scraping, etc.).

All facts produced by MCP servers MUST have:
- Source URL or identifier
- Source name
- Capture timestamp
- Confidence score
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog

from packages.mcp.src.types import (
    EvidencedFact,
    MCPHealthStatus,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)

logger = structlog.get_logger()


class MCPServerError(Exception):
    """Base exception for MCP server errors."""

    pass


class MCPRateLimitError(MCPServerError):
    """Rate limit exceeded."""

    def __init__(self, reset_at: datetime | None = None) -> None:
        self.reset_at = reset_at
        super().__init__(
            f"Rate limit exceeded. Reset at: {reset_at.isoformat() if reset_at else 'unknown'}"
        )


class MCPConfigurationError(MCPServerError):
    """Server not properly configured."""

    pass


class BaseMCPServer(ABC):
    """Abstract base class for MCP servers.

    Each MCP server is responsible for:
    1. Connecting to a data source (API, scraping, database)
    2. Extracting facts with full provenance
    3. Normalizing data into EvidencedFact format
    4. Handling rate limiting and errors gracefully

    Example implementation:
        class ACRAMCPServer(BaseMCPServer):
            async def search_company(self, query: str) -> MCPQueryResult:
                # Query ACRA API
                raw_data = await self._acra_client.search(query)

                # Convert to evidenced facts
                facts = []
                for company in raw_data:
                    facts.append(EvidencedFact(
                        claim=f"{company['name']} registered with UEN {company['uen']}",
                        fact_type=FactType.COMPANY_INFO,
                        source_type=SourceType.ACRA,
                        source_name="ACRA Singapore",
                        source_url=f"https://data.gov.sg/dataset/acra-{company['uen']}",
                        confidence=0.99,  # Government source
                        extracted_data=company,
                    ))

                return MCPQueryResult(
                    facts=facts,
                    query=query,
                    mcp_server=self.name,
                )
    """

    def __init__(self, config: MCPServerConfig) -> None:
        """Initialize MCP server.

        Args:
            config: Server configuration
        """
        self._config = config
        self._logger = logger.bind(mcp_server=config.name)

        # Rate limiting state
        self._request_count_hour = 0
        self._request_count_day = 0
        self._hour_reset_at: datetime | None = None
        self._day_reset_at: datetime | None = None

        # Health tracking
        self._last_health_check: datetime | None = None
        self._is_healthy = True
        self._last_error: str | None = None

        # Stats
        self._total_facts_produced = 0
        self._total_queries = 0
        self._total_confidence_sum = 0.0

        # Simple in-memory cache with TTL (default 15 minutes)
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl_seconds = 900  # 15 minutes

    @property
    def name(self) -> str:
        """Server name."""
        return self._config.name

    @property
    def source_type(self) -> SourceType:
        """Source type this server produces."""
        return self._config.source_type

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if server is properly configured.

        Returns:
            True if all required configuration is present
        """
        ...

    @abstractmethod
    async def _health_check_impl(self) -> bool:
        """Implementation of health check.

        Returns:
            True if server is reachable and functioning
        """
        ...

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search for facts matching a query.

        This is the main method for retrieving data. Subclasses should
        override this to query their specific data source.

        Args:
            query: Search query
            **kwargs: Additional search parameters

        Returns:
            Query result with evidenced facts
        """
        ...

    async def health_check(self) -> MCPHealthStatus:
        """Check server health and return status.

        Returns:
            Health status with diagnostics
        """
        try:
            is_healthy = await self._health_check_impl()
            self._is_healthy = is_healthy
            self._last_health_check = datetime.utcnow()
            self._last_error = None

            return MCPHealthStatus(
                server_name=self.name,
                is_healthy=is_healthy,
                last_check=self._last_health_check,
                total_queries_today=self._total_queries,
                total_facts_produced=self._total_facts_produced,
                avg_confidence=self._avg_confidence,
                rate_limit_remaining=self._rate_limit_remaining,
                rate_limit_reset_at=self._hour_reset_at,
            )
        except Exception as e:
            self._is_healthy = False
            self._last_error = str(e)
            self._last_health_check = datetime.utcnow()

            self._logger.error("health_check_failed", error=str(e))

            return MCPHealthStatus(
                server_name=self.name,
                is_healthy=False,
                last_check=self._last_health_check,
                error_message=str(e),
            )

    @property
    def _avg_confidence(self) -> float:
        """Calculate average confidence of produced facts."""
        if self._total_facts_produced == 0:
            return 0.0
        return self._total_confidence_sum / self._total_facts_produced

    @property
    def _rate_limit_remaining(self) -> int | None:
        """Calculate remaining rate limit."""
        if self._config.rate_limit_per_hour is None:
            return None
        return max(0, self._config.rate_limit_per_hour - self._request_count_hour)

    def _get_cached(self, key: str) -> Any | None:
        """Get cached result if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        if key not in self._cache:
            return None

        value, cached_at = self._cache[key]
        now = datetime.utcnow()

        # Check if expired
        from datetime import timedelta

        if now - cached_at > timedelta(seconds=self._cache_ttl_seconds):
            del self._cache[key]
            return None

        return value

    def _set_cached(self, key: str, value: Any) -> None:
        """Cache a result.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, datetime.utcnow())

    def _clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting.

        Raises:
            MCPRateLimitError: If rate limit exceeded
        """
        now = datetime.utcnow()

        # Reset hourly counter if needed
        if self._hour_reset_at and now >= self._hour_reset_at:
            self._request_count_hour = 0
            self._hour_reset_at = None

        # Reset daily counter if needed
        if self._day_reset_at and now >= self._day_reset_at:
            self._request_count_day = 0
            self._day_reset_at = None

        # Check hourly limit
        if self._config.rate_limit_per_hour:
            if self._request_count_hour >= self._config.rate_limit_per_hour:
                if self._hour_reset_at is None:
                    from datetime import timedelta

                    self._hour_reset_at = now + timedelta(hours=1)
                raise MCPRateLimitError(self._hour_reset_at)

        # Check daily limit
        if self._config.rate_limit_per_day:
            if self._request_count_day >= self._config.rate_limit_per_day:
                if self._day_reset_at is None:
                    from datetime import timedelta

                    self._day_reset_at = now + timedelta(days=1)
                raise MCPRateLimitError(self._day_reset_at)

    def _record_request(self) -> None:
        """Record a request for rate limiting."""
        self._request_count_hour += 1
        self._request_count_day += 1
        self._total_queries += 1

    def _record_facts(self, facts: list[EvidencedFact]) -> None:
        """Record produced facts for stats."""
        self._total_facts_produced += len(facts)
        for fact in facts:
            self._total_confidence_sum += fact.confidence

    async def execute_query(
        self,
        query: str,
        **kwargs: Any,
    ) -> MCPQueryResult:
        """Execute a query with rate limiting and error handling.

        This is the public method that should be called by consumers.
        It wraps the search() method with rate limiting and error handling.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            Query result with evidenced facts
        """
        if not self.is_configured:
            raise MCPConfigurationError(f"MCP server '{self.name}' is not configured")

        start_time = time.time()

        try:
            # Check rate limit
            await self._check_rate_limit()

            # Record request
            self._record_request()

            # Execute search
            result = await self.search(query, **kwargs)

            # Record facts
            self._record_facts(result.facts)

            # Add timing
            result.query_time_ms = (time.time() - start_time) * 1000

            self._logger.info(
                "query_executed",
                query=query,
                facts_found=len(result.facts),
                time_ms=result.query_time_ms,
            )

            return result

        except MCPRateLimitError:
            raise
        except Exception as e:
            self._logger.error("query_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                query_time_ms=(time.time() - start_time) * 1000,
                errors=[str(e)],
            )

    def create_fact(
        self,
        claim: str,
        fact_type: str,
        source_name: str,
        source_url: str | None = None,
        raw_excerpt: str | None = None,
        published_at: datetime | None = None,
        confidence: float = 0.8,
        extracted_data: dict[str, Any] | None = None,
        related_entities: list[str] | None = None,
    ) -> EvidencedFact:
        """Helper to create an EvidencedFact with this server's metadata.

        This ensures all facts have proper provenance.

        Args:
            claim: The factual claim
            fact_type: Type of fact
            source_name: Name of the source
            source_url: URL to source
            raw_excerpt: Original text from source
            published_at: When source was published
            confidence: Confidence score
            extracted_data: Structured data extracted
            related_entities: Related entity names

        Returns:
            EvidencedFact with full provenance
        """
        from packages.mcp.src.types import FactType

        return EvidencedFact(
            claim=claim,
            fact_type=FactType(fact_type),
            source_type=self.source_type,
            source_name=source_name,
            source_url=source_url,
            raw_excerpt=raw_excerpt,
            published_at=published_at,
            captured_at=datetime.utcnow(),
            confidence=confidence,
            extracted_data=extracted_data or {},
            related_entities=related_entities or [],
            mcp_server=self.name,
        )


class WebScrapingMCPServer(BaseMCPServer):
    """Base class for MCP servers that use web scraping.

    Provides common functionality for:
    - User agent rotation
    - Rate limiting for scraping
    - HTML parsing helpers
    - Error handling for blocked requests
    """

    # Default user agents for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ]

    # Default delay between requests (seconds)
    DEFAULT_REQUEST_DELAY = 1.0

    def __init__(self, config: MCPServerConfig) -> None:
        super().__init__(config)
        self._user_agent_index = 0
        self._last_request_time = 0.0

    def _get_user_agent(self) -> str:
        """Get next user agent in rotation."""
        ua = self.USER_AGENTS[self._user_agent_index]
        self._user_agent_index = (self._user_agent_index + 1) % len(self.USER_AGENTS)
        return ua

    async def _respect_rate_limit(self, delay: float | None = None) -> None:
        """Wait if needed to respect rate limiting.

        Args:
            delay: Custom delay in seconds
        """
        delay = delay or self.DEFAULT_REQUEST_DELAY
        elapsed = time.time() - self._last_request_time
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def _get_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Get request headers with user agent rotation.

        Args:
            extra_headers: Additional headers to include

        Returns:
            Headers dict
        """
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers


class APIBasedMCPServer(BaseMCPServer):
    """Base class for MCP servers that use APIs.

    Provides common functionality for:
    - API key management
    - Request retries
    - Response caching
    """

    def __init__(self, config: MCPServerConfig) -> None:
        super().__init__(config)
        self._cache: dict[str, tuple[MCPQueryResult, datetime]] = {}

    @property
    def api_key(self) -> str | None:
        """Get API key from config."""
        return self._config.api_key

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured (if required)."""
        if self._config.requires_api_key:
            return bool(self._config.api_key)
        return True

    def _get_cached(self, cache_key: str) -> MCPQueryResult | None:
        """Get cached result if not expired.

        Args:
            cache_key: Cache key

        Returns:
            Cached result or None
        """
        if cache_key not in self._cache:
            return None

        result, cached_at = self._cache[cache_key]
        elapsed = (datetime.utcnow() - cached_at).total_seconds()

        if elapsed > self._config.cache_ttl_seconds:
            del self._cache[cache_key]
            return None

        return result

    def _set_cached(self, cache_key: str, result: MCPQueryResult) -> None:
        """Cache a result.

        Args:
            cache_key: Cache key
            result: Result to cache
        """
        self._cache[cache_key] = (result, datetime.utcnow())

    def _clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
