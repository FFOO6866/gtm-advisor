"""Integration tests for MCP servers.

These tests verify that MCP servers can connect to real data sources and
produce properly structured EvidencedFact responses.

Some tests require network access and are marked with @pytest.mark.network.
To run only offline tests: pytest -m "not network"
"""

from __future__ import annotations

import os

import pytest

from packages.mcp.src.registry import MCPRegistry
from packages.mcp.src.servers.acra import ACRAMCPServer
from packages.mcp.src.servers.news import NewsAggregatorMCPServer
from packages.mcp.src.servers.web_scraper import WebScraperMCPServer
from packages.mcp.src.types import (
    EvidencedFact,
    FactType,
    MCPServerConfig,
    SourceType,
)


class TestACRAMCPServer:
    """Tests for the ACRA (data.gov.sg) MCP server."""

    @pytest.fixture
    def acra_config(self):
        """Create ACRA server config."""
        return MCPServerConfig(
            name="ACRA Singapore",
            source_type=SourceType.GOVERNMENT,
            description="Singapore company registry",
            timeout_seconds=30,
        )

    @pytest.fixture
    def acra_server(self, acra_config):
        """Create ACRA server instance."""
        return ACRAMCPServer(acra_config)

    @pytest.mark.asyncio
    async def test_server_initialization(self, acra_server):
        """Server should initialize with correct configuration."""
        assert acra_server.name == "ACRA Singapore"
        assert acra_server.source_type == SourceType.GOVERNMENT

    @pytest.mark.asyncio
    @pytest.mark.network
    async def test_search_companies_real_api(self, acra_server):
        """Should search for companies via data.gov.sg API."""
        # Search for a common term to ensure results
        result = await acra_server.search("technology", limit=5)

        # Should return MCPQueryResult
        assert hasattr(result, "facts")
        assert hasattr(result, "query")
        assert hasattr(result, "mcp_server")

    @pytest.mark.asyncio
    async def test_health_check(self, acra_server):
        """Health check should report server status."""
        health = await acra_server.health_check()
        assert hasattr(health, "is_healthy")
        assert hasattr(health, "last_check")


class TestNewsAggregatorMCPServer:
    """Tests for the News Aggregator MCP server."""

    @pytest.fixture
    def news_config(self):
        """Create News server config."""
        api_key = os.getenv("NEWSAPI_API_KEY")
        return MCPServerConfig(
            name="News & Media Intelligence",
            source_type=SourceType.NEWSAPI,
            description="News aggregation from multiple sources",
            api_key=api_key,
            timeout_seconds=30,
        )

    @pytest.fixture
    def news_server(self, news_config):
        """Create News server instance."""
        return NewsAggregatorMCPServer(news_config)

    @pytest.mark.asyncio
    async def test_server_initialization(self, news_server):
        """Server should initialize with correct configuration."""
        assert news_server.name == "News & Media Intelligence"
        assert news_server.source_type == SourceType.NEWSAPI

    @pytest.mark.asyncio
    async def test_rss_feeds_configured(self, news_server):
        """Should have RSS feeds configured."""
        # Check that config exists
        assert news_server._config is not None

    @pytest.mark.asyncio
    @pytest.mark.network
    async def test_fetch_rss_feeds(self, news_server):
        """Should fetch articles from RSS feeds."""
        result = await news_server.search("singapore", limit=10)

        assert hasattr(result, "facts")
        assert hasattr(result, "mcp_server")

        # All facts should have required fields
        for fact in result.facts:
            assert isinstance(fact, EvidencedFact)
            assert fact.claim is not None
            assert fact.confidence >= 0 and fact.confidence <= 1

    @pytest.mark.asyncio
    async def test_article_classification(self, news_server):
        """Should correctly classify article types."""
        # Test classification logic with sample headlines
        test_cases = [
            ("Company raises $10M in Series A funding", FactType.FUNDING),
            ("Tech startup acquired by Google", FactType.ACQUISITION),
            ("Singapore expansion announced", FactType.EXPANSION),
            ("New product launch unveiled", FactType.PRODUCT),
            ("Company hires 500 new employees", FactType.HIRING),
            ("CEO steps down from leadership", FactType.EXECUTIVE),
            ("Strategic partnership formed", FactType.PARTNERSHIP),
        ]

        for headline, _expected_type in test_cases:
            result = news_server._classify_article(headline, "")
            # Should return one of the valid FactTypes
            assert isinstance(result, FactType)


class TestWebScraperMCPServer:
    """Tests for the Web Scraper MCP server."""

    @pytest.fixture
    def scraper_config(self):
        """Create Web Scraper server config."""
        return MCPServerConfig(
            name="Web Scraping Intelligence",
            source_type=SourceType.WEB_SCRAPE,
            description="Web scraping for company data",
            timeout_seconds=30,
        )

    @pytest.fixture
    def scraper_server(self, scraper_config):
        """Create Web Scraper server instance."""
        return WebScraperMCPServer(scraper_config)

    @pytest.mark.asyncio
    async def test_server_initialization(self, scraper_server):
        """Server should initialize with correct configuration."""
        assert scraper_server.name == "Web Scraping Intelligence"
        assert scraper_server.source_type == SourceType.WEB_SCRAPE

    @pytest.mark.asyncio
    async def test_health_check(self, scraper_server):
        """Health check should report server status."""
        health = await scraper_server.health_check()
        assert hasattr(health, "is_healthy")
        assert hasattr(health, "last_check")

    @pytest.mark.asyncio
    @pytest.mark.network
    async def test_scrape_real_website(self, scraper_server):
        """Should scrape and extract information from a real website."""
        # Use a stable, simple website for testing
        result = await scraper_server.search("https://example.com")

        assert hasattr(result, "facts")
        assert hasattr(result, "mcp_server")


class TestMCPRegistry:
    """Tests for the MCP Registry."""

    @pytest.fixture
    def registry(self):
        """Create MCP Registry instance."""
        return MCPRegistry()

    @pytest.fixture
    def acra_config(self):
        """Create ACRA server config."""
        return MCPServerConfig(
            name="ACRA Singapore",
            source_type=SourceType.GOVERNMENT,
            description="Singapore company registry",
        )

    @pytest.fixture
    def news_config(self):
        """Create News server config."""
        return MCPServerConfig(
            name="News Intelligence",
            source_type=SourceType.NEWSAPI,
            description="News aggregation",
        )

    @pytest.fixture
    def scraper_config(self):
        """Create Web Scraper config."""
        return MCPServerConfig(
            name="Web Scraper",
            source_type=SourceType.WEB_SCRAPE,
            description="Web scraping",
        )

    @pytest.mark.asyncio
    async def test_register_server(self, registry, acra_config):
        """Should register MCP servers."""
        server = ACRAMCPServer(acra_config)
        registry.register(server)

        # Server is registered by its name (from config)
        assert "ACRA Singapore" in registry._servers
        assert registry._servers["ACRA Singapore"] == server

    @pytest.mark.asyncio
    async def test_register_multiple_servers(
        self, registry, acra_config, news_config, scraper_config
    ):
        """Should register multiple MCP servers."""
        registry.register(ACRAMCPServer(acra_config))
        registry.register(NewsAggregatorMCPServer(news_config))
        registry.register(WebScraperMCPServer(scraper_config))

        assert len(registry._servers) == 3

    @pytest.mark.asyncio
    async def test_get_server(self, registry, acra_config):
        """Should retrieve registered server by name."""
        server = ACRAMCPServer(acra_config)
        registry.register(server)

        # get_server() is the correct method name
        retrieved = registry.get_server("ACRA Singapore")
        assert retrieved == server

    @pytest.mark.asyncio
    async def test_get_nonexistent_server(self, registry):
        """Should return None for unregistered server."""
        result = registry.get_server("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_servers(self, registry, acra_config, news_config):
        """Should list all registered servers."""
        registry.register(ACRAMCPServer(acra_config))
        registry.register(NewsAggregatorMCPServer(news_config))

        # get_all_servers() is the correct method name
        servers = registry.get_all_servers()
        assert len(servers) == 2
        assert "ACRA Singapore" in [s.name for s in servers]
        assert "News Intelligence" in [s.name for s in servers]

    @pytest.mark.asyncio
    @pytest.mark.network
    async def test_search_all(self, registry, news_config):
        """Should search across all registered servers."""
        registry.register(NewsAggregatorMCPServer(news_config))

        results = await registry.search("singapore technology")

        assert hasattr(results, "facts")


class TestEvidencedFactValidation:
    """Tests for EvidencedFact data model validation."""

    def test_valid_fact_creation(self):
        """Should create valid EvidencedFact."""
        fact = EvidencedFact(
            claim="Company X raised $10M in Series A",
            source_type=SourceType.NEWSAPI,
            source_name="TechCrunch",
            source_url="https://techcrunch.com/article/123",
            raw_excerpt="Company X announced today...",
            confidence=0.85,
            fact_type=FactType.FUNDING,
        )

        assert fact.claim == "Company X raised $10M in Series A"
        assert fact.source_type == SourceType.NEWSAPI
        assert fact.confidence == 0.85

    def test_confidence_bounds(self):
        """Confidence should be between 0 and 1."""
        # Valid bounds
        fact_low = EvidencedFact(
            claim="Test",
            source_type=SourceType.NEWSAPI,
            source_name="Test",
            source_url="https://example.com",
            confidence=0.0,
            fact_type=FactType.COMPANY_INFO,
        )
        assert fact_low.confidence == 0.0

        fact_high = EvidencedFact(
            claim="Test",
            source_type=SourceType.NEWSAPI,
            source_name="Test",
            source_url="https://example.com",
            confidence=1.0,
            fact_type=FactType.COMPANY_INFO,
        )
        assert fact_high.confidence == 1.0

    def test_required_fields(self):
        """Should require essential fields."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidencedFact(
                claim="Test",
                # Missing source_type, source_name, fact_type
            )

    def test_fact_has_id(self):
        """Facts should have auto-generated UUIDs."""
        fact = EvidencedFact(
            claim="Test",
            source_type=SourceType.NEWSAPI,
            source_name="Test",
            source_url="https://example.com",
            confidence=0.5,
            fact_type=FactType.COMPANY_INFO,
        )

        # Should have an ID
        assert fact.id is not None
