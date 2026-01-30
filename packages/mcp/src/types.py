"""Data types for MCP (Model Context Protocol) servers.

These types define the evidence-backed fact model at the core of the
Knowledge Web architecture. Every fact must have provenance.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Source types for evidenced facts - matches database enum."""

    ACRA = "acra"
    EODHD = "eodhd"
    NEWSAPI = "newsapi"
    PERPLEXITY = "perplexity"
    WEB_SCRAPE = "web_scrape"
    LINKEDIN = "linkedin"
    JOB_BOARD = "job_board"
    GOVERNMENT = "government"
    REVIEW_SITE = "review_site"
    PRESS_RELEASE = "press_release"
    SEC_FILING = "sec_filing"
    USER_INPUT = "user_input"


class FactType(str, Enum):
    """Types of evidenced facts - matches database enum."""

    COMPANY_INFO = "company_info"
    FUNDING = "funding"
    EXECUTIVE = "executive"
    PRODUCT = "product"
    PARTNERSHIP = "partnership"
    EXPANSION = "expansion"
    HIRING = "hiring"
    TECHNOLOGY = "technology"
    FINANCIAL = "financial"
    MARKET_TREND = "market_trend"
    COMPETITOR_MOVE = "competitor_move"
    REGULATION = "regulation"
    ACQUISITION = "acquisition"
    SENTIMENT = "sentiment"


class EntityType(str, Enum):
    """Types of entities in the knowledge graph."""

    COMPANY = "company"
    PERSON = "person"
    PRODUCT = "product"
    INVESTOR = "investor"
    INDUSTRY = "industry"
    TECHNOLOGY = "technology"
    LOCATION = "location"


class EvidencedFact(BaseModel):
    """A fact with full provenance tracking.

    This is the core data model for the Knowledge Web.
    NO FACT WITHOUT SOURCE - every claim must have evidence.

    Example:
        EvidencedFact(
            claim="TechCorp raised $10M Series A",
            fact_type=FactType.FUNDING,
            source_type=SourceType.NEWSAPI,
            source_name="TechCrunch",
            source_url="https://techcrunch.com/2024/01/15/techcorp-series-a",
            raw_excerpt="TechCorp announced today that it has raised $10 million...",
            published_at=datetime(2024, 1, 15),
            confidence=0.95,
            extracted_data={"amount": 10000000, "round": "series_a"}
        )
    """

    id: UUID = Field(default_factory=uuid4)

    # The actual claim - what we're asserting as true
    claim: str = Field(..., description="The factual claim being made")
    fact_type: FactType = Field(..., description="Category of fact")

    # Source provenance (REQUIRED - no fact without source)
    source_type: SourceType = Field(..., description="Type of source")
    source_name: str = Field(..., description="Name of the source (e.g., 'TechCrunch')")
    source_url: str | None = Field(default=None, description="URL to the original source")
    raw_excerpt: str | None = Field(
        default=None, description="Original text excerpt from source"
    )

    # Temporal context
    published_at: datetime | None = Field(
        default=None, description="When the source was published"
    )
    captured_at: datetime = Field(
        default_factory=datetime.utcnow, description="When we captured this fact"
    )
    valid_from: datetime | None = Field(
        default=None, description="When this fact became true"
    )
    valid_until: datetime | None = Field(
        default=None, description="When this fact stopped being true"
    )

    # Confidence scoring
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    verification_count: int = Field(
        default=1, description="Number of sources confirming this fact"
    )

    # Structured data extraction
    extracted_data: dict[str, Any] = Field(
        default_factory=dict, description="Key-value data extracted from the fact"
    )

    # Related entities (by name for cross-referencing)
    related_entities: list[str] = Field(
        default_factory=list, description="Names of related entities"
    )

    # Processing metadata
    mcp_server: str | None = Field(
        default=None, description="MCP server that produced this fact"
    )

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class EntityReference(BaseModel):
    """Reference to an entity in the knowledge graph."""

    entity_type: EntityType
    name: str
    canonical_name: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)

    # Known identifiers
    acra_uen: str | None = None
    linkedin_url: str | None = None
    website: str | None = None


class MCPQueryResult(BaseModel):
    """Result from an MCP server query.

    Contains the facts discovered and metadata about the query.
    """

    facts: list[EvidencedFact] = Field(default_factory=list)
    entities: list[EntityReference] = Field(default_factory=list)

    # Query metadata
    query: str = Field(..., description="The original query")
    mcp_server: str = Field(..., description="MCP server that processed this")
    query_time_ms: float = Field(default=0.0, description="Query execution time")

    # Result metadata
    total_results: int = Field(default=0, description="Total results found")
    has_more: bool = Field(default=False, description="Whether more results exist")

    # Errors/warnings
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MCPHealthStatus(BaseModel):
    """Health status of an MCP server."""

    server_name: str
    is_healthy: bool
    last_check: datetime = Field(default_factory=datetime.utcnow)
    error_message: str | None = None

    # Usage stats
    total_queries_today: int = 0
    total_facts_produced: int = 0
    avg_confidence: float = 0.0

    # Rate limiting
    rate_limit_remaining: int | None = None
    rate_limit_reset_at: datetime | None = None


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    name: str
    source_type: SourceType
    description: str = ""

    # API configuration
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 30

    # Rate limiting
    rate_limit_per_hour: int | None = None
    rate_limit_per_day: int | None = None

    # Feature flags
    is_enabled: bool = True
    requires_api_key: bool = True

    # Caching
    cache_ttl_seconds: int = 3600  # 1 hour default


class SignalCategory(str, Enum):
    """Categories for lead qualification signals."""

    FIT = "fit"  # How well they match ICP
    INTENT = "intent"  # Buying intent signals
    TIMING = "timing"  # Timing/urgency signals


class LeadSignal(BaseModel):
    """A signal contributing to lead qualification.

    Each signal must be backed by evidenced facts.
    """

    signal_category: SignalCategory
    signal_type: str = Field(
        ..., description="Specific signal type (e.g., 'hiring_sales_team')"
    )
    description: str = Field(..., description="Human-readable description")
    impact_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Impact on qualification"
    )

    # Evidence
    evidence_facts: list[EvidencedFact] = Field(
        default_factory=list, description="Facts supporting this signal"
    )
    evidence_summary: str | None = Field(
        default=None, description="Human-readable evidence summary"
    )


class CompetitorAlert(BaseModel):
    """Alert about competitor activity.

    Each alert must be backed by evidenced facts.
    """

    competitor_name: str
    signal_type: str = Field(
        ..., description="Type of signal (product, pricing, hiring, etc.)"
    )
    title: str
    description: str
    severity: str = Field(default="medium", description="low, medium, high, critical")

    # Evidence
    primary_fact: EvidencedFact | None = None
    supporting_facts: list[EvidencedFact] = Field(default_factory=list)

    # Recommendations
    response_options: list[str] = Field(default_factory=list)
    recommended_action: str | None = None

    detected_at: datetime = Field(default_factory=datetime.utcnow)
