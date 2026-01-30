# GTM Advisor Knowledge Web Architecture

## Executive Summary

Transform GTM Advisor from a "text dump" system into an **evidence-backed knowledge web** where every insight is traceable to verifiable sources, and entities connect in a navigable graph.

### Core Principles

1. **Every fact needs receipts** - No claim without source URL, timestamp, and confidence
2. **LLM synthesizes, doesn't fabricate** - AI explains the graph, doesn't create it
3. **Agents publish evidence, not opinions** - A2A messages carry EvidencedFacts
4. **MCP servers provide data** - Standardized protocol for all data sources
5. **Graph-first storage** - Relationships are first-class citizens

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
│  Dashboard (React) ←→ WebSocket ←→ Knowledge Graph Visualization            │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATION LAYER                             │
│                                                                             │
│  ┌─────────────┐    ┌─────────────────────────────────────┐                │
│  │   Gateway   │───▶│           Agent Bus (A2A)           │                │
│  │   (FastAPI) │    │  - Pub/Sub for discoveries          │                │
│  └─────────────┘    │  - Evidence-backed messages         │                │
│                     │  - Knowledge graph updates          │                │
│                     └─────────────────────────────────────┘                │
│                                       │                                     │
│         ┌─────────────────────────────┼─────────────────────────────┐      │
│         ▼                             ▼                             ▼      │
│  ┌─────────────┐              ┌─────────────┐              ┌─────────────┐ │
│  │   GTM       │              │   Market    │              │   Lead      │ │
│  │ Strategist  │              │ Intelligence│              │   Hunter    │ │
│  │   Agent     │              │   Agent     │              │   Agent     │ │
│  └─────────────┘              └─────────────┘              └─────────────┘ │
│         │                             │                             │      │
└─────────┼─────────────────────────────┼─────────────────────────────┼──────┘
          │                             │                             │
┌─────────┼─────────────────────────────┼─────────────────────────────┼──────┐
│         ▼                             ▼                             ▼      │
│                              MCP SERVER LAYER                              │
│                                                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  ACRA    │ │  EODHD   │ │  News    │ │  Web     │ │  Social  │        │
│  │  MCP     │ │  MCP     │ │  MCP     │ │  Scraper │ │  MCP     │        │
│  │  Server  │ │  Server  │ │  Server  │ │  MCP     │ │  Server  │        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘        │
│       │            │            │            │            │               │
└───────┼────────────┼────────────┼────────────┼────────────┼───────────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
   [ACRA Gov]   [EODHD API]  [NewsAPI]   [Websites]   [LinkedIn]
```

---

## Part 1: Database Schema (Knowledge Graph)

### Core Evidence Model

```sql
-- ============================================================================
-- EVIDENCE LAYER: Every fact needs a source
-- ============================================================================

CREATE TYPE source_type AS ENUM (
    'government_registry',    -- ACRA, SEC, Companies House
    'financial_api',          -- EODHD, stock exchanges
    'news_article',           -- NewsAPI, TechCrunch, Business Times
    'press_release',          -- PR Newswire, company announcements
    'linkedin_profile',       -- LinkedIn profiles and posts
    'linkedin_post',          -- LinkedIn activity
    'twitter_post',           -- X/Twitter posts
    'job_posting',            -- LinkedIn Jobs, Indeed, MyCareersFuture
    'website_scrape',         -- Company websites
    'tech_scan',              -- BuiltWith, Wappalyzer
    'review_site',            -- G2, Capterra, TrustRadius
    'api_enrichment',         -- Apollo, Clearbit, Cognism
    'funding_database',       -- Crunchbase, PitchBook
    'user_input'              -- Manual entry by user
);

CREATE TYPE fact_type AS ENUM (
    -- Company facts
    'company_exists',
    'company_founded',
    'company_industry',
    'company_employee_count',
    'company_location',
    'company_description',
    'company_funding',
    'company_revenue',
    'company_tech_stack',
    'company_product',

    -- People facts
    'person_works_at',
    'person_title',
    'person_email',
    'person_phone',
    'person_linkedin',

    -- Signal facts
    'hiring_signal',
    'funding_signal',
    'expansion_signal',
    'pain_signal',
    'intent_signal',
    'news_mention',
    'review_posted',
    'price_change',
    'product_launch',
    'exec_change'
);

CREATE TABLE evidenced_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The claim
    fact_type fact_type NOT NULL,
    claim TEXT NOT NULL,                    -- "TechCorp raised $5M Series A"
    structured_data JSONB,                  -- {"amount": 5000000, "round": "series_a"}

    -- Source attribution (THE RECEIPT)
    source_type source_type NOT NULL,
    source_name VARCHAR(255) NOT NULL,      -- "TechCrunch", "ACRA", "LinkedIn"
    source_url TEXT,                        -- Direct link to source
    source_api VARCHAR(100),                -- "eodhd", "newsapi", "apollo"

    -- Evidence
    raw_excerpt TEXT,                       -- Actual quote from source
    published_at TIMESTAMP WITH TIME ZONE,  -- When source was published
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Quality
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    verified BOOLEAN DEFAULT FALSE,         -- Cross-referenced with another source?
    verification_source_id UUID REFERENCES evidenced_facts(id),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,    -- Some facts become stale
    is_active BOOLEAN DEFAULT TRUE,

    -- Indexing
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', claim), 'A') ||
        setweight(to_tsvector('english', COALESCE(raw_excerpt, '')), 'B')
    ) STORED
);

CREATE INDEX idx_facts_type ON evidenced_facts(fact_type);
CREATE INDEX idx_facts_source ON evidenced_facts(source_type, source_name);
CREATE INDEX idx_facts_captured ON evidenced_facts(captured_at DESC);
CREATE INDEX idx_facts_search ON evidenced_facts USING GIN(search_vector);

-- ============================================================================
-- ENTITY LAYER: Things we track
-- ============================================================================

CREATE TYPE entity_type AS ENUM (
    'company',
    'person',
    'competitor',
    'investor',
    'news_article',
    'job_posting',
    'technology',
    'industry',
    'location'
);

CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type entity_type NOT NULL,

    -- Identity
    canonical_name VARCHAR(500) NOT NULL,
    aliases JSONB DEFAULT '[]',             -- ["TechCorp", "TechCorp Pte Ltd", "TECHCORP"]

    -- External IDs
    uen VARCHAR(20),                        -- Singapore UEN from ACRA
    linkedin_url TEXT,
    website TEXT,
    crunchbase_url TEXT,

    -- Computed aggregates (updated by triggers)
    fact_count INTEGER DEFAULT 0,
    last_fact_at TIMESTAMP WITH TIME ZONE,
    confidence_avg FLOAT DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- For company entities
    owner_id UUID REFERENCES users(id),     -- Who owns this company profile

    UNIQUE(entity_type, canonical_name)
);

CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_uen ON entities(uen) WHERE uen IS NOT NULL;
CREATE INDEX idx_entities_name ON entities USING GIN(to_tsvector('english', canonical_name));

-- ============================================================================
-- RELATIONSHIP LAYER: The "Web" in Knowledge Web
-- ============================================================================

CREATE TYPE relation_type AS ENUM (
    -- Company relationships
    'works_at',
    'founded',
    'invested_in',
    'acquired',
    'competes_with',
    'partners_with',
    'uses_technology',
    'located_in',
    'industry_is',

    -- Content relationships
    'mentioned_in',
    'authored',
    'posted',
    'reviewed',

    -- Signal relationships
    'hiring_for',
    'raised_funding',
    'launched_product',
    'changed_pricing'
);

CREATE TABLE entity_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The relationship
    from_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type relation_type NOT NULL,
    to_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,

    -- Relationship metadata
    relation_data JSONB,                    -- {"title": "CEO", "start_date": "2023-01"}
    strength FLOAT DEFAULT 0.5,             -- How strong is this connection

    -- Timestamps
    valid_from TIMESTAMP WITH TIME ZONE,
    valid_to TIMESTAMP WITH TIME ZONE,      -- NULL means current

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Prevent duplicates
    UNIQUE(from_entity_id, relation_type, to_entity_id, valid_from)
);

CREATE INDEX idx_relations_from ON entity_relations(from_entity_id);
CREATE INDEX idx_relations_to ON entity_relations(to_entity_id);
CREATE INDEX idx_relations_type ON entity_relations(relation_type);

-- ============================================================================
-- EVIDENCE LINKING: Connect facts to entities and relations
-- ============================================================================

CREATE TABLE fact_entity_links (
    fact_id UUID NOT NULL REFERENCES evidenced_facts(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,              -- "subject", "object", "mentioned"
    PRIMARY KEY (fact_id, entity_id, role)
);

CREATE TABLE fact_relation_links (
    fact_id UUID NOT NULL REFERENCES evidenced_facts(id) ON DELETE CASCADE,
    relation_id UUID NOT NULL REFERENCES entity_relations(id) ON DELETE CASCADE,
    PRIMARY KEY (fact_id, relation_id)
);

-- ============================================================================
-- LEAD INTELLIGENCE: Evidence-backed lead scoring
-- ============================================================================

CREATE TABLE lead_justifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The lead
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    company_entity_id UUID NOT NULL REFERENCES entities(id),

    -- Evidence-backed scores
    fit_score FLOAT NOT NULL DEFAULT 0 CHECK (fit_score >= 0 AND fit_score <= 1),
    intent_score FLOAT NOT NULL DEFAULT 0 CHECK (intent_score >= 0 AND intent_score <= 1),
    timing_score FLOAT NOT NULL DEFAULT 0 CHECK (timing_score >= 0 AND timing_score <= 1),
    overall_score FLOAT NOT NULL DEFAULT 0 CHECK (overall_score >= 0 AND overall_score <= 1),

    -- Score breakdown (which facts contributed)
    fit_evidence JSONB DEFAULT '[]',        -- [{"fact_id": "...", "weight": 0.3, "reason": "..."}]
    intent_evidence JSONB DEFAULT '[]',
    timing_evidence JSONB DEFAULT '[]',
    competitive_evidence JSONB DEFAULT '[]',

    -- LLM synthesis (generated FROM evidence, not made up)
    narrative TEXT,                         -- "TechCorp is a strong lead because..."
    recommended_approach TEXT,
    talking_points JSONB DEFAULT '[]',

    -- Metadata
    scored_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    scoring_version VARCHAR(20) DEFAULT 'v1',

    UNIQUE(lead_id)
);

-- ============================================================================
-- COMPETITOR INTELLIGENCE: Evidence-backed competitor tracking
-- ============================================================================

CREATE TABLE competitor_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    competitor_entity_id UUID NOT NULL REFERENCES entities(id),
    company_id UUID NOT NULL REFERENCES companies(id),  -- Our company tracking this

    -- The signal
    signal_type VARCHAR(50) NOT NULL,       -- "pricing_change", "product_launch", "exec_hire"
    headline VARCHAR(500) NOT NULL,

    -- Evidence
    evidence_fact_ids UUID[] NOT NULL,      -- Array of fact IDs that support this

    -- Analysis
    impact_analysis TEXT,                   -- "This means we should..."
    threat_level VARCHAR(20),               -- "high", "medium", "low"

    -- Affected leads
    affected_lead_ids UUID[],               -- Leads using this competitor

    -- Timestamps
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_competitor_signals_competitor ON competitor_signals(competitor_entity_id);
CREATE INDEX idx_competitor_signals_company ON competitor_signals(company_id);
```

### Graph Queries Examples

```sql
-- Find all evidence for why TechCorp is a good lead
SELECT
    ef.fact_type,
    ef.claim,
    ef.source_name,
    ef.source_url,
    ef.confidence,
    ef.published_at
FROM lead_justifications lj
JOIN LATERAL unnest(lj.fit_evidence) AS fe ON true
JOIN evidenced_facts ef ON ef.id = (fe->>'fact_id')::uuid
WHERE lj.lead_id = 'xxx';

-- Find all leads affected by a competitor's price increase
SELECT
    l.*,
    cs.headline,
    cs.impact_analysis
FROM competitor_signals cs
JOIN LATERAL unnest(cs.affected_lead_ids) AS lid ON true
JOIN leads l ON l.id = lid
WHERE cs.signal_type = 'pricing_change'
  AND cs.competitor_entity_id = 'yyy';

-- Graph traversal: Find companies 2 degrees from an investor
WITH RECURSIVE company_graph AS (
    -- Start: Companies directly invested in by investor X
    SELECT
        er.to_entity_id as company_id,
        1 as depth,
        ARRAY[er.from_entity_id, er.to_entity_id] as path
    FROM entity_relations er
    WHERE er.from_entity_id = 'investor-uuid'
      AND er.relation_type = 'invested_in'

    UNION ALL

    -- Recurse: Find related companies
    SELECT
        er.to_entity_id,
        cg.depth + 1,
        cg.path || er.to_entity_id
    FROM company_graph cg
    JOIN entity_relations er ON er.from_entity_id = cg.company_id
    WHERE cg.depth < 2
      AND NOT er.to_entity_id = ANY(cg.path)  -- Prevent cycles
)
SELECT DISTINCT e.*
FROM company_graph cg
JOIN entities e ON e.id = cg.company_id;
```

---

## Part 2: MCP Server Architecture

### MCP Server Interface

```python
# packages/mcp/src/base.py
"""Base MCP Server for Knowledge Web data sources."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EvidencedFact(BaseModel):
    """A fact with full source attribution."""

    id: UUID = Field(default_factory=uuid4)
    fact_type: str
    claim: str
    structured_data: dict[str, Any] | None = None

    # Source attribution
    source_type: str
    source_name: str
    source_url: str | None = None
    source_api: str | None = None

    # Evidence
    raw_excerpt: str | None = None
    published_at: datetime | None = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)

    # Quality
    confidence: float = 0.5


class MCPResource(BaseModel):
    """A resource exposed by an MCP server."""

    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


class MCPTool(BaseModel):
    """A tool exposed by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


class BaseMCPServer(ABC):
    """Base class for MCP servers.

    Each MCP server wraps a data source and produces EvidencedFacts.
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._source_type: str = "api_enrichment"
        self._source_name: str = name

    @abstractmethod
    async def list_resources(self) -> list[MCPResource]:
        """List available resources."""
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> list[EvidencedFact]:
        """Read a resource and return evidenced facts."""
        pass

    @abstractmethod
    async def list_tools(self) -> list[MCPTool]:
        """List available tools."""
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[EvidencedFact]:
        """Call a tool and return evidenced facts."""
        pass

    def _create_fact(
        self,
        fact_type: str,
        claim: str,
        source_url: str | None = None,
        raw_excerpt: str | None = None,
        published_at: datetime | None = None,
        confidence: float = 0.5,
        structured_data: dict | None = None,
    ) -> EvidencedFact:
        """Helper to create a properly attributed fact."""
        return EvidencedFact(
            fact_type=fact_type,
            claim=claim,
            structured_data=structured_data,
            source_type=self._source_type,
            source_name=self._source_name,
            source_url=source_url,
            source_api=self.name,
            raw_excerpt=raw_excerpt,
            published_at=published_at,
            confidence=confidence,
        )
```

### MCP Server Implementations

#### 1. ACRA MCP Server (Singapore Company Registry - FREE)

```python
# packages/mcp/src/servers/acra.py
"""ACRA MCP Server - Singapore Company Registry.

Data source: data.gov.sg (FREE)
Update frequency: Monthly
Coverage: 588,764 Singapore registered entities
"""

import csv
from datetime import datetime
from pathlib import Path

from ..base import BaseMCPServer, EvidencedFact, MCPResource, MCPTool


class ACRAMCPServer(BaseMCPServer):
    """MCP Server for ACRA Singapore company data.

    Provides:
    - Company existence verification
    - UEN lookup
    - Registration date
    - Entity type (Pte Ltd, LLP, etc.)
    - Business status (Live, Struck Off, etc.)

    Data source: https://data.gov.sg/datasets/d_3f960c10fed6145404ca7b821f263b87
    """

    DATA_URL = "https://data.gov.sg/api/action/datastore_search"
    RESOURCE_ID = "d_3f960c10fed6145404ca7b821f263b87"

    def __init__(self, data_path: Path | None = None):
        super().__init__(
            name="acra",
            description="Singapore ACRA company registry"
        )
        self._source_type = "government_registry"
        self._source_name = "ACRA Singapore"
        self._data_path = data_path
        self._companies: dict[str, dict] = {}

    async def load_data(self, csv_path: Path) -> None:
        """Load ACRA data from CSV."""
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uen = row.get('uen', '').strip()
                if uen:
                    self._companies[uen.upper()] = row
                    # Also index by name
                    name = row.get('entity_name', '').strip().upper()
                    if name:
                        self._companies[f"name:{name}"] = row

    async def list_resources(self) -> list[MCPResource]:
        return [
            MCPResource(
                uri="acra://companies",
                name="Singapore Companies",
                description="All registered Singapore companies from ACRA"
            )
        ]

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="lookup_uen",
                description="Look up a company by UEN (Unique Entity Number)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "uen": {"type": "string", "description": "Singapore UEN"}
                    },
                    "required": ["uen"]
                }
            ),
            MCPTool(
                name="search_company",
                description="Search for companies by name",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Company name to search"}
                    },
                    "required": ["name"]
                }
            ),
            MCPTool(
                name="verify_company",
                description="Verify a company exists and is active",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "uen": {"type": "string"}
                    }
                }
            )
        ]

    async def call_tool(self, name: str, arguments: dict) -> list[EvidencedFact]:
        if name == "lookup_uen":
            return await self._lookup_uen(arguments["uen"])
        elif name == "search_company":
            return await self._search_company(arguments["name"])
        elif name == "verify_company":
            return await self._verify_company(
                arguments.get("name"),
                arguments.get("uen")
            )
        return []

    async def _lookup_uen(self, uen: str) -> list[EvidencedFact]:
        """Look up company by UEN."""
        facts = []
        company = self._companies.get(uen.upper())

        if company:
            # Company exists fact
            facts.append(self._create_fact(
                fact_type="company_exists",
                claim=f"{company['entity_name']} is a registered Singapore entity",
                source_url=f"https://www.bizfile.gov.sg/ngbbizfileinternet/faces/oracle/webcenter/portalapp/pages/BizfileHomepage.jspx?_afrLoop=1&uen={uen}",
                confidence=0.95,
                structured_data={
                    "uen": uen,
                    "entity_name": company['entity_name'],
                    "entity_type": company.get('entity_type'),
                    "status": company.get('uen_status'),
                    "registration_date": company.get('registration_date'),
                }
            ))

            # Registration date fact
            if company.get('registration_date'):
                facts.append(self._create_fact(
                    fact_type="company_founded",
                    claim=f"{company['entity_name']} was registered on {company['registration_date']}",
                    source_url=f"https://www.bizfile.gov.sg/",
                    confidence=0.95,
                    structured_data={
                        "date": company['registration_date'],
                        "type": "registration"
                    }
                ))

        return facts

    async def _search_company(self, name: str) -> list[EvidencedFact]:
        """Search companies by name."""
        facts = []
        name_upper = name.upper()

        # Simple fuzzy search
        matches = [
            (uen, data) for uen, data in self._companies.items()
            if not uen.startswith("name:") and name_upper in data.get('entity_name', '').upper()
        ]

        for uen, company in matches[:10]:
            facts.append(self._create_fact(
                fact_type="company_exists",
                claim=f"Found company: {company['entity_name']} (UEN: {uen})",
                source_url="https://data.gov.sg/datasets/d_3f960c10fed6145404ca7b821f263b87",
                confidence=0.95,
                structured_data={
                    "uen": uen,
                    "entity_name": company['entity_name'],
                    "entity_type": company.get('entity_type'),
                    "status": company.get('uen_status'),
                }
            ))

        return facts

    async def read_resource(self, uri: str) -> list[EvidencedFact]:
        """Read resource - not implemented for ACRA (use tools instead)."""
        return []
```

#### 2. EODHD MCP Server (Financial Data - Already Integrated)

```python
# packages/mcp/src/servers/eodhd.py
"""EODHD MCP Server - Financial and Economic Data.

Data source: eodhd.com API (Freemium)
- Company fundamentals for public companies
- Economic indicators (Singapore GDP, inflation, etc.)
- Financial news with sentiment
"""

from datetime import datetime

from packages.integrations.eodhd.src.client import EODHDClient, get_eodhd_client

from ..base import BaseMCPServer, EvidencedFact, MCPResource, MCPTool


class EODHDMCPServer(BaseMCPServer):
    """MCP Server for EODHD financial data."""

    def __init__(self):
        super().__init__(
            name="eodhd",
            description="Financial data, economic indicators, and news"
        )
        self._source_type = "financial_api"
        self._source_name = "EODHD"
        self._client = get_eodhd_client()

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="get_company_fundamentals",
                description="Get financial fundamentals for a public company",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock symbol (e.g., D05 for DBS)"},
                        "exchange": {"type": "string", "default": "SG", "description": "Exchange code"}
                    },
                    "required": ["symbol"]
                }
            ),
            MCPTool(
                name="get_economic_indicators",
                description="Get economic indicators for Singapore",
                input_schema={
                    "type": "object",
                    "properties": {
                        "country": {"type": "string", "default": "SGP"},
                        "indicator": {"type": "string", "description": "Specific indicator (GDP, inflation, etc.)"}
                    }
                }
            ),
            MCPTool(
                name="get_financial_news",
                description="Get financial news, optionally filtered by symbol",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "tag": {"type": "string"},
                        "limit": {"type": "integer", "default": 20}
                    }
                }
            )
        ]

    async def call_tool(self, name: str, arguments: dict) -> list[EvidencedFact]:
        if name == "get_company_fundamentals":
            return await self._get_fundamentals(
                arguments["symbol"],
                arguments.get("exchange", "SG")
            )
        elif name == "get_economic_indicators":
            return await self._get_indicators(
                arguments.get("country", "SGP"),
                arguments.get("indicator")
            )
        elif name == "get_financial_news":
            return await self._get_news(
                arguments.get("symbol"),
                arguments.get("tag"),
                arguments.get("limit", 20)
            )
        return []

    async def _get_fundamentals(self, symbol: str, exchange: str) -> list[EvidencedFact]:
        """Get company fundamentals as evidenced facts."""
        facts = []
        data = await self._client.get_company_fundamentals(symbol, exchange)

        if not data:
            return facts

        source_url = f"https://eodhd.com/financial-summary/{symbol}.{exchange}"

        # Company info fact
        facts.append(self._create_fact(
            fact_type="company_exists",
            claim=f"{data.name} ({symbol}) is a public company on {exchange}",
            source_url=source_url,
            confidence=0.90,
            structured_data={
                "symbol": symbol,
                "exchange": exchange,
                "name": data.name,
                "sector": data.sector,
                "industry": data.industry,
            }
        ))

        # Employee count fact
        if data.employees:
            facts.append(self._create_fact(
                fact_type="company_employee_count",
                claim=f"{data.name} has {data.employees:,} employees",
                source_url=source_url,
                confidence=0.85,
                structured_data={"count": data.employees}
            ))

        # Revenue fact
        if data.revenue:
            facts.append(self._create_fact(
                fact_type="company_revenue",
                claim=f"{data.name} has revenue of {data.currency} {data.revenue:,.0f}",
                source_url=source_url,
                confidence=0.90,
                structured_data={
                    "amount": data.revenue,
                    "currency": data.currency
                }
            ))

        # Market cap fact
        if data.market_cap:
            facts.append(self._create_fact(
                fact_type="company_funding",
                claim=f"{data.name} has market cap of {data.currency} {data.market_cap:,.0f}",
                source_url=source_url,
                confidence=0.90,
                structured_data={
                    "market_cap": data.market_cap,
                    "currency": data.currency
                }
            ))

        return facts

    async def _get_indicators(self, country: str, indicator: str | None) -> list[EvidencedFact]:
        """Get economic indicators as evidenced facts."""
        facts = []
        indicators = await self._client.get_economic_indicators(country, indicator)

        for ind in indicators:
            facts.append(self._create_fact(
                fact_type="news_mention",  # Using as economic context
                claim=f"{country} {ind.indicator}: {ind.value} (Period: {ind.period})",
                source_url="https://eodhd.com/macro-indicator",
                published_at=ind.date,
                confidence=0.90,
                structured_data={
                    "indicator": ind.indicator,
                    "value": ind.value,
                    "previous_value": ind.previous_value,
                    "change": ind.change,
                    "period": ind.period,
                    "country": country,
                }
            ))

        return facts

    async def _get_news(self, symbol: str | None, tag: str | None, limit: int) -> list[EvidencedFact]:
        """Get financial news as evidenced facts."""
        facts = []
        news = await self._client.get_financial_news(symbol, tag, limit)

        for item in news:
            facts.append(self._create_fact(
                fact_type="news_mention",
                claim=item.title,
                source_url=item.link,
                raw_excerpt=item.content[:500] if item.content else None,
                published_at=item.date,
                confidence=0.80,
                structured_data={
                    "symbols": item.symbols,
                    "tags": item.tags,
                    "sentiment": item.sentiment,
                }
            ))

        return facts

    async def list_resources(self) -> list[MCPResource]:
        return [
            MCPResource(
                uri="eodhd://sg-market",
                name="Singapore Market Overview",
                description="Economic indicators and market news for Singapore"
            )
        ]

    async def read_resource(self, uri: str) -> list[EvidencedFact]:
        if uri == "eodhd://sg-market":
            facts = []
            facts.extend(await self._get_indicators("SGP", None))
            facts.extend(await self._get_news(None, "earnings", 10))
            return facts
        return []
```

#### 3. News Aggregator MCP Server (FREE sources)

```python
# packages/mcp/src/servers/news.py
"""News Aggregator MCP Server - Multiple free news sources.

Data sources:
- NewsAPI.org (dev tier FREE)
- Google News RSS (FREE)
- Business Times RSS (FREE)
- TechCrunch RSS (FREE)
"""

import asyncio
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

import httpx

from packages.integrations.newsapi.src.client import NewsAPIClient, get_newsapi_client

from ..base import BaseMCPServer, EvidencedFact, MCPResource, MCPTool


class NewsAggregatorMCPServer(BaseMCPServer):
    """MCP Server aggregating multiple news sources."""

    # Free RSS feeds
    RSS_FEEDS = {
        "business_times": "https://www.businesstimes.com.sg/rss/singapore",
        "techcrunch": "https://techcrunch.com/feed/",
        "tech_in_asia": "https://www.techinasia.com/feed",
        "e27": "https://e27.co/feed/",
    }

    def __init__(self):
        super().__init__(
            name="news_aggregator",
            description="Aggregated news from multiple sources"
        )
        self._source_type = "news_article"
        self._newsapi = get_newsapi_client()
        self._http = httpx.AsyncClient(timeout=30.0)

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="search_news",
                description="Search news across all sources",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific sources to search"
                        },
                        "days": {"type": "integer", "default": 7}
                    },
                    "required": ["query"]
                }
            ),
            MCPTool(
                name="get_company_news",
                description="Get news about a specific company",
                input_schema={
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "limit": {"type": "integer", "default": 20}
                    },
                    "required": ["company_name"]
                }
            ),
            MCPTool(
                name="get_industry_news",
                description="Get news for an industry vertical",
                input_schema={
                    "type": "object",
                    "properties": {
                        "industry": {"type": "string"},
                        "region": {"type": "string", "default": "singapore"}
                    },
                    "required": ["industry"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: dict) -> list[EvidencedFact]:
        if name == "search_news":
            return await self._search_all(
                arguments["query"],
                arguments.get("sources"),
                arguments.get("days", 7)
            )
        elif name == "get_company_news":
            return await self._get_company_news(
                arguments["company_name"],
                arguments.get("limit", 20)
            )
        elif name == "get_industry_news":
            return await self._get_industry_news(
                arguments["industry"],
                arguments.get("region", "singapore")
            )
        return []

    async def _search_all(
        self,
        query: str,
        sources: list[str] | None,
        days: int
    ) -> list[EvidencedFact]:
        """Search across all news sources."""
        facts = []

        # Search NewsAPI
        if self._newsapi.is_configured:
            newsapi_facts = await self._search_newsapi(query, days)
            facts.extend(newsapi_facts)

        # Search RSS feeds
        rss_facts = await self._search_rss(query)
        facts.extend(rss_facts)

        # Search Google News
        google_facts = await self._search_google_news(query)
        facts.extend(google_facts)

        # Deduplicate by URL
        seen_urls = set()
        unique_facts = []
        for fact in facts:
            url = fact.source_url
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_facts.append(fact)
            elif not url:
                # Keep facts without URLs but dedupe by claim hash
                claim_hash = hashlib.md5(fact.claim.encode()).hexdigest()
                if claim_hash not in seen_urls:
                    seen_urls.add(claim_hash)
                    unique_facts.append(fact)

        return unique_facts

    async def _search_newsapi(self, query: str, days: int) -> list[EvidencedFact]:
        """Search NewsAPI."""
        facts = []
        try:
            from datetime import timedelta
            result = await self._newsapi.search(
                query=query,
                from_date=datetime.utcnow() - timedelta(days=days),
                page_size=20
            )

            for article in result.articles:
                facts.append(EvidencedFact(
                    fact_type="news_mention",
                    claim=article.title,
                    source_type="news_article",
                    source_name=article.source_name,
                    source_url=article.url,
                    source_api="newsapi",
                    raw_excerpt=article.description,
                    published_at=article.published_at,
                    confidence=0.80,
                ))
        except Exception:
            pass

        return facts

    async def _search_rss(self, query: str) -> list[EvidencedFact]:
        """Search RSS feeds."""
        facts = []
        query_lower = query.lower()

        for source_name, feed_url in self.RSS_FEEDS.items():
            try:
                response = await self._http.get(feed_url)
                root = ET.fromstring(response.text)

                for item in root.findall(".//item")[:50]:
                    title = item.findtext("title", "")
                    description = item.findtext("description", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")

                    # Simple relevance check
                    if query_lower in title.lower() or query_lower in description.lower():
                        facts.append(EvidencedFact(
                            fact_type="news_mention",
                            claim=title,
                            source_type="news_article",
                            source_name=source_name.replace("_", " ").title(),
                            source_url=link,
                            source_api="rss",
                            raw_excerpt=description[:500] if description else None,
                            published_at=self._parse_rss_date(pub_date),
                            confidence=0.75,
                        ))
            except Exception:
                continue

        return facts

    async def _search_google_news(self, query: str) -> list[EvidencedFact]:
        """Search Google News RSS."""
        facts = []
        try:
            url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-SG&gl=SG&ceid=SG:en"
            response = await self._http.get(url)
            root = ET.fromstring(response.text)

            for item in root.findall(".//item")[:20]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source = item.findtext("source", "")

                facts.append(EvidencedFact(
                    fact_type="news_mention",
                    claim=title,
                    source_type="news_article",
                    source_name=source or "Google News",
                    source_url=link,
                    source_api="google_news_rss",
                    published_at=self._parse_rss_date(pub_date),
                    confidence=0.75,
                ))
        except Exception:
            pass

        return facts

    def _parse_rss_date(self, date_str: str) -> datetime | None:
        """Parse various RSS date formats."""
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    async def _get_company_news(self, company_name: str, limit: int) -> list[EvidencedFact]:
        """Get news about a specific company."""
        return await self._search_all(company_name, None, 30)

    async def _get_industry_news(self, industry: str, region: str) -> list[EvidencedFact]:
        """Get industry news."""
        query = f"{industry} {region}"
        return await self._search_all(query, None, 14)

    async def list_resources(self) -> list[MCPResource]:
        return [
            MCPResource(
                uri="news://singapore/tech",
                name="Singapore Tech News",
                description="Latest tech news from Singapore"
            ),
            MCPResource(
                uri="news://singapore/startups",
                name="Singapore Startup News",
                description="Startup and funding news"
            )
        ]

    async def read_resource(self, uri: str) -> list[EvidencedFact]:
        if uri == "news://singapore/tech":
            return await self._search_all("Singapore technology", None, 7)
        elif uri == "news://singapore/startups":
            return await self._search_all("Singapore startup funding", None, 7)
        return []
```

#### 4. Web Scraper MCP Server (FREE - replaces paid enrichment)

```python
# packages/mcp/src/servers/web_scraper.py
"""Web Scraper MCP Server - Extract data from public websites.

Replaces paid services like Clearbit, Apollo for basic data:
- Company about pages
- Team/leadership pages
- Job postings (hiring signals)
- Tech stack from meta tags
"""

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..base import BaseMCPServer, EvidencedFact, MCPResource, MCPTool


class WebScraperMCPServer(BaseMCPServer):
    """MCP Server for web scraping company data."""

    def __init__(self):
        super().__init__(
            name="web_scraper",
            description="Extract company data from public websites"
        )
        self._source_type = "website_scrape"
        self._http = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GTMAdvisor/1.0; +https://gtm-advisor.com)"
            }
        )

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="scrape_company_website",
                description="Extract company info from their website",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Company website URL"},
                        "include_team": {"type": "boolean", "default": True},
                        "include_jobs": {"type": "boolean", "default": True}
                    },
                    "required": ["url"]
                }
            ),
            MCPTool(
                name="scrape_about_page",
                description="Extract company description and founding info",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"}
                    },
                    "required": ["url"]
                }
            ),
            MCPTool(
                name="detect_tech_stack",
                description="Detect technologies used on a website",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"}
                    },
                    "required": ["url"]
                }
            ),
            MCPTool(
                name="scrape_job_postings",
                description="Extract job postings from company careers page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "careers_path": {"type": "string", "default": "/careers"}
                    },
                    "required": ["url"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: dict) -> list[EvidencedFact]:
        if name == "scrape_company_website":
            return await self._scrape_full(
                arguments["url"],
                arguments.get("include_team", True),
                arguments.get("include_jobs", True)
            )
        elif name == "scrape_about_page":
            return await self._scrape_about(arguments["url"])
        elif name == "detect_tech_stack":
            return await self._detect_tech(arguments["url"])
        elif name == "scrape_job_postings":
            return await self._scrape_jobs(
                arguments["url"],
                arguments.get("careers_path", "/careers")
            )
        return []

    async def _scrape_full(
        self,
        url: str,
        include_team: bool,
        include_jobs: bool
    ) -> list[EvidencedFact]:
        """Full website scrape."""
        facts = []
        base_url = self._normalize_url(url)

        # Scrape homepage
        facts.extend(await self._scrape_homepage(base_url))

        # Scrape about page
        about_facts = await self._scrape_about(base_url)
        facts.extend(about_facts)

        # Detect tech stack
        tech_facts = await self._detect_tech(base_url)
        facts.extend(tech_facts)

        # Scrape team page
        if include_team:
            team_facts = await self._scrape_team(base_url)
            facts.extend(team_facts)

        # Scrape jobs
        if include_jobs:
            job_facts = await self._scrape_jobs(base_url, "/careers")
            facts.extend(job_facts)

        return facts

    async def _scrape_homepage(self, url: str) -> list[EvidencedFact]:
        """Scrape homepage for basic info."""
        facts = []
        try:
            response = await self._http.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title = soup.title.string if soup.title else None
            if title:
                company_name = title.split('|')[0].split('-')[0].strip()
                facts.append(self._create_fact(
                    fact_type="company_exists",
                    claim=f"Company website found: {company_name}",
                    source_url=url,
                    confidence=0.80,
                    structured_data={"name": company_name, "website": url}
                ))

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                facts.append(self._create_fact(
                    fact_type="company_description",
                    claim=meta_desc['content'][:500],
                    source_url=url,
                    raw_excerpt=meta_desc['content'],
                    confidence=0.75,
                ))

            # Extract social links
            social_links = {}
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                if 'linkedin.com/company' in href:
                    social_links['linkedin'] = link['href']
                elif 'twitter.com' in href or 'x.com' in href:
                    social_links['twitter'] = link['href']

            if social_links:
                for platform, link in social_links.items():
                    facts.append(self._create_fact(
                        fact_type="company_exists",
                        claim=f"Company {platform} profile: {link}",
                        source_url=url,
                        confidence=0.85,
                        structured_data={"platform": platform, "url": link}
                    ))

        except Exception:
            pass

        return facts

    async def _scrape_about(self, url: str) -> list[EvidencedFact]:
        """Scrape about page."""
        facts = []
        about_paths = ['/about', '/about-us', '/company', '/our-story']

        for path in about_paths:
            try:
                about_url = urljoin(url, path)
                response = await self._http.get(about_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Remove script and style
                    for tag in soup(['script', 'style', 'nav', 'footer']):
                        tag.decompose()

                    # Get main content
                    main = soup.find('main') or soup.find('article') or soup.find('body')
                    if main:
                        text = main.get_text(separator=' ', strip=True)[:2000]

                        # Look for founding year
                        year_match = re.search(r'founded\s+(?:in\s+)?(\d{4})', text.lower())
                        if year_match:
                            facts.append(self._create_fact(
                                fact_type="company_founded",
                                claim=f"Company founded in {year_match.group(1)}",
                                source_url=about_url,
                                raw_excerpt=text[max(0, year_match.start()-50):year_match.end()+50],
                                confidence=0.80,
                                structured_data={"year": int(year_match.group(1))}
                            ))

                        # Look for employee count
                        emp_match = re.search(r'(\d+(?:,\d+)?)\+?\s*(?:employees|team members|people)', text.lower())
                        if emp_match:
                            count = int(emp_match.group(1).replace(',', ''))
                            facts.append(self._create_fact(
                                fact_type="company_employee_count",
                                claim=f"Company has approximately {count} employees",
                                source_url=about_url,
                                raw_excerpt=text[max(0, emp_match.start()-50):emp_match.end()+50],
                                confidence=0.70,
                                structured_data={"count": count, "approximate": True}
                            ))

                        # Add general description
                        facts.append(self._create_fact(
                            fact_type="company_description",
                            claim=f"About page content extracted",
                            source_url=about_url,
                            raw_excerpt=text[:1000],
                            confidence=0.75,
                        ))

                    break  # Found about page, stop searching

            except Exception:
                continue

        return facts

    async def _detect_tech(self, url: str) -> list[EvidencedFact]:
        """Detect tech stack from HTML and headers."""
        facts = []
        tech_detected = []

        try:
            response = await self._http.get(url)
            html = response.text.lower()
            headers = {k.lower(): v for k, v in response.headers.items()}

            # Check for common technologies
            tech_patterns = {
                'react': [r'react', r'_react', r'__next'],
                'vue': [r'vue\.js', r'v-bind', r'v-model'],
                'angular': [r'ng-app', r'angular'],
                'next.js': [r'__next', r'_next/static'],
                'wordpress': [r'wp-content', r'wordpress'],
                'shopify': [r'shopify', r'cdn\.shopify'],
                'hubspot': [r'hubspot', r'hs-scripts'],
                'salesforce': [r'salesforce', r'force\.com'],
                'google_analytics': [r'google-analytics', r'gtag', r'ga\.js'],
                'segment': [r'segment\.com', r'analytics\.js'],
                'intercom': [r'intercom', r'widget\.intercom'],
                'zendesk': [r'zendesk', r'zdassets'],
                'stripe': [r'stripe\.com', r'js\.stripe'],
                'aws': [r'amazonaws\.com'],
                'cloudflare': [r'cloudflare'],
            }

            for tech, patterns in tech_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, html):
                        tech_detected.append(tech)
                        break

            # Check headers
            if 'x-powered-by' in headers:
                powered_by = headers['x-powered-by']
                tech_detected.append(f"server:{powered_by}")

            if 'server' in headers:
                server = headers['server']
                tech_detected.append(f"server:{server}")

            # Create facts for each technology
            for tech in set(tech_detected):
                facts.append(self._create_fact(
                    fact_type="company_tech_stack",
                    claim=f"Website uses {tech.replace('_', ' ').title()}",
                    source_url=url,
                    confidence=0.75,
                    structured_data={"technology": tech}
                ))

            if tech_detected:
                facts.append(self._create_fact(
                    fact_type="company_tech_stack",
                    claim=f"Tech stack detected: {', '.join(set(tech_detected))}",
                    source_url=url,
                    confidence=0.75,
                    structured_data={"technologies": list(set(tech_detected))}
                ))

        except Exception:
            pass

        return facts

    async def _scrape_team(self, url: str) -> list[EvidencedFact]:
        """Scrape team/leadership page."""
        facts = []
        team_paths = ['/team', '/about/team', '/leadership', '/our-team', '/people']

        for path in team_paths:
            try:
                team_url = urljoin(url, path)
                response = await self._http.get(team_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for team member cards
                    # Common patterns: divs with person info
                    people = []

                    for card in soup.find_all(['div', 'article'], class_=re.compile(r'team|member|person|card', re.I)):
                        name_el = card.find(['h2', 'h3', 'h4', 'strong'])
                        title_el = card.find(['p', 'span'], class_=re.compile(r'title|role|position', re.I))

                        if name_el:
                            name = name_el.get_text(strip=True)
                            title = title_el.get_text(strip=True) if title_el else None

                            if name and len(name) < 100:  # Sanity check
                                people.append({"name": name, "title": title})

                    # Create facts for leadership
                    for person in people[:20]:  # Limit to 20
                        claim = f"{person['name']}"
                        if person['title']:
                            claim += f" - {person['title']}"

                        facts.append(self._create_fact(
                            fact_type="person_works_at",
                            claim=claim,
                            source_url=team_url,
                            confidence=0.70,
                            structured_data=person
                        ))

                    if people:
                        break

            except Exception:
                continue

        return facts

    async def _scrape_jobs(self, url: str, careers_path: str) -> list[EvidencedFact]:
        """Scrape job postings as hiring signals."""
        facts = []
        job_paths = [careers_path, '/careers', '/jobs', '/join-us', '/open-positions']

        for path in job_paths:
            try:
                jobs_url = urljoin(url, path)
                response = await self._http.get(jobs_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Count job postings
                    job_elements = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'job|position|opening|vacancy', re.I))

                    job_titles = []
                    for job in job_elements[:30]:
                        title_el = job.find(['h2', 'h3', 'h4', 'a', 'strong'])
                        if title_el:
                            title = title_el.get_text(strip=True)
                            if title and len(title) < 200:
                                job_titles.append(title)

                    if job_titles:
                        # Hiring signal
                        facts.append(self._create_fact(
                            fact_type="hiring_signal",
                            claim=f"Company is actively hiring: {len(job_titles)} open positions",
                            source_url=jobs_url,
                            confidence=0.85,
                            structured_data={
                                "open_positions": len(job_titles),
                                "sample_roles": job_titles[:10]
                            }
                        ))

                        # Analyze hiring for specific signals
                        titles_text = ' '.join(job_titles).lower()

                        if any(x in titles_text for x in ['sales', 'account executive', 'sdr', 'bdr']):
                            facts.append(self._create_fact(
                                fact_type="expansion_signal",
                                claim="Company is scaling sales team",
                                source_url=jobs_url,
                                confidence=0.75,
                                structured_data={"signal_type": "sales_expansion"}
                            ))

                        if any(x in titles_text for x in ['engineer', 'developer', 'architect']):
                            facts.append(self._create_fact(
                                fact_type="expansion_signal",
                                claim="Company is scaling engineering team",
                                source_url=jobs_url,
                                confidence=0.75,
                                structured_data={"signal_type": "engineering_expansion"}
                            ))

                        break

            except Exception:
                continue

        return facts

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to include scheme."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def list_resources(self) -> list[MCPResource]:
        return []

    async def read_resource(self, uri: str) -> list[EvidencedFact]:
        return []
```

#### 5. LinkedIn MCP Server (FREE scraping alternative)

```python
# packages/mcp/src/servers/linkedin.py
"""LinkedIn MCP Server - Public LinkedIn data.

NOTE: LinkedIn aggressively blocks scraping. This uses:
1. Public profile pages (no login required)
2. Google search cache as fallback
3. Rate limiting to avoid blocks

For production, consider:
- Proxycurl API ($0.01/request)
- Apify LinkedIn scrapers
- Official LinkedIn Marketing API (requires partnership)
"""

import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from ..base import BaseMCPServer, EvidencedFact, MCPResource, MCPTool


class LinkedInMCPServer(BaseMCPServer):
    """MCP Server for LinkedIn public data."""

    def __init__(self):
        super().__init__(
            name="linkedin",
            description="LinkedIn public profile and company data"
        )
        self._source_type = "linkedin_profile"
        self._source_name = "LinkedIn"
        self._http = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="search_company",
                description="Search for a company on LinkedIn via Google",
                input_schema={
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"}
                    },
                    "required": ["company_name"]
                }
            ),
            MCPTool(
                name="get_company_info",
                description="Get company info from LinkedIn company page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "linkedin_url": {"type": "string", "description": "LinkedIn company URL"}
                    },
                    "required": ["linkedin_url"]
                }
            ),
            MCPTool(
                name="search_employees",
                description="Search for employees at a company via Google",
                input_schema={
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "title_filter": {"type": "string", "description": "e.g., 'CEO', 'VP Sales'"}
                    },
                    "required": ["company_name"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: dict) -> list[EvidencedFact]:
        if name == "search_company":
            return await self._search_company(arguments["company_name"])
        elif name == "get_company_info":
            return await self._get_company_info(arguments["linkedin_url"])
        elif name == "search_employees":
            return await self._search_employees(
                arguments["company_name"],
                arguments.get("title_filter")
            )
        return []

    async def _search_company(self, company_name: str) -> list[EvidencedFact]:
        """Search for company via Google."""
        facts = []

        try:
            # Google search for LinkedIn company page
            query = f'site:linkedin.com/company "{company_name}"'
            google_url = f"https://www.google.com/search?q={quote(query)}"

            response = await self._http.get(google_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find LinkedIn URLs in results
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/company/' in href:
                    # Extract clean URL
                    match = re.search(r'(https?://[a-z]+\.linkedin\.com/company/[^&"\'?\s]+)', href)
                    if match:
                        linkedin_url = match.group(1)

                        facts.append(self._create_fact(
                            fact_type="company_exists",
                            claim=f"LinkedIn company page found for {company_name}",
                            source_url=linkedin_url,
                            confidence=0.80,
                            structured_data={
                                "linkedin_url": linkedin_url,
                                "company_name": company_name
                            }
                        ))
                        break

        except Exception:
            pass

        return facts

    async def _get_company_info(self, linkedin_url: str) -> list[EvidencedFact]:
        """Get company info from LinkedIn page (limited without login)."""
        facts = []

        try:
            # Try Google cache version
            cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{linkedin_url}"

            response = await self._http.get(linkedin_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract what we can from public page
            # Note: Most data requires login

            # Company name from title
            title = soup.title.string if soup.title else None
            if title:
                company_name = title.split('|')[0].strip()
                facts.append(self._create_fact(
                    fact_type="company_exists",
                    claim=f"LinkedIn profile: {company_name}",
                    source_url=linkedin_url,
                    confidence=0.85,
                    structured_data={"name": company_name}
                ))

            # Look for structured data
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    import json
                    data = json.loads(script.string)

                    if data.get('@type') == 'Organization':
                        if data.get('numberOfEmployees'):
                            facts.append(self._create_fact(
                                fact_type="company_employee_count",
                                claim=f"LinkedIn shows {data['numberOfEmployees']} employees",
                                source_url=linkedin_url,
                                confidence=0.80,
                                structured_data={"count": data['numberOfEmployees']}
                            ))

                        if data.get('description'):
                            facts.append(self._create_fact(
                                fact_type="company_description",
                                claim=data['description'][:500],
                                source_url=linkedin_url,
                                raw_excerpt=data['description'],
                                confidence=0.85,
                            ))
                except Exception:
                    continue

        except Exception:
            pass

        return facts

    async def _search_employees(
        self,
        company_name: str,
        title_filter: str | None
    ) -> list[EvidencedFact]:
        """Search for employees via Google."""
        facts = []

        try:
            query = f'site:linkedin.com/in "{company_name}"'
            if title_filter:
                query += f' "{title_filter}"'

            google_url = f"https://www.google.com/search?q={quote(query)}"

            response = await self._http.get(google_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract profile info from search results
            for result in soup.find_all('div', class_='g')[:10]:
                title_el = result.find('h3')
                snippet_el = result.find('span', class_='st') or result.find('div', class_='VwiC3b')

                if title_el:
                    title_text = title_el.get_text()

                    # Extract name and title from Google result
                    # Format: "Name - Title - Company | LinkedIn"
                    match = re.match(r'^([^-]+)\s*-\s*([^-|]+)', title_text)
                    if match:
                        name = match.group(1).strip()
                        role = match.group(2).strip()

                        # Find LinkedIn URL
                        link = result.find('a', href=True)
                        profile_url = None
                        if link and 'linkedin.com/in/' in link['href']:
                            url_match = re.search(r'(https?://[a-z]+\.linkedin\.com/in/[^&"\'?\s]+)', link['href'])
                            if url_match:
                                profile_url = url_match.group(1)

                        facts.append(self._create_fact(
                            fact_type="person_works_at",
                            claim=f"{name} - {role} at {company_name}",
                            source_url=profile_url or google_url,
                            confidence=0.70,
                            structured_data={
                                "name": name,
                                "title": role,
                                "company": company_name,
                                "linkedin_url": profile_url
                            }
                        ))

        except Exception:
            pass

        return facts

    async def list_resources(self) -> list[MCPResource]:
        return []

    async def read_resource(self, uri: str) -> list[EvidencedFact]:
        return []
```

---

## Part 3: A2A Integration

### Enhanced Agent Message with Evidence

```python
# packages/core/src/agent_bus.py - Enhanced

class DiscoveryType(str, Enum):
    """Types of discoveries agents can publish."""

    # Evidence-backed discoveries (NEW)
    EVIDENCED_FACT = "evidenced_fact"
    ENTITY_FOUND = "entity_found"
    RELATION_FOUND = "relation_found"

    # Lead intelligence (ENHANCED)
    LEAD_JUSTIFIED = "lead_justified"  # Lead with full evidence chain
    LEAD_SIGNAL = "lead_signal"        # Single signal about a lead

    # Competitor intelligence (ENHANCED)
    COMPETITOR_SIGNAL = "competitor_signal"  # Price change, product launch, etc.

    # ... existing types ...


class EvidencedDiscovery(BaseModel):
    """A discovery with full evidence chain."""

    # The discovery
    discovery_type: DiscoveryType
    title: str
    summary: str

    # Evidence (the receipts)
    facts: list[EvidencedFact]

    # Entities involved
    entity_ids: list[UUID]
    relation_ids: list[UUID]

    # Quality
    confidence: float
    fact_count: int
    source_count: int


# Updated AgentMessage
class AgentMessage(BaseModel):
    """A message exchanged between agents - now with evidence."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Routing
    from_agent: str
    to_agent: str | None = None

    # Content
    discovery_type: DiscoveryType
    title: str

    # Evidence-backed content (NEW)
    evidence: EvidencedDiscovery | None = None

    # Legacy content (for backward compatibility)
    content: dict[str, Any] = Field(default_factory=dict)

    confidence: float = 0.7
    analysis_id: UUID | None = None
```

### Knowledge Graph Agent

```python
# agents/knowledge_graph/src/agent.py
"""Knowledge Graph Agent - Maintains the evidence web.

Responsibilities:
1. Receives EvidencedFacts from MCP servers
2. Creates/updates entities and relations
3. Deduplicates and merges facts
4. Publishes graph updates to other agents
"""

from uuid import UUID

from agents.core.src.base_agent import BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, DiscoveryType, get_agent_bus
from packages.mcp.src.base import EvidencedFact


class KnowledgeGraphOutput(BaseModel):
    """Output from knowledge graph operations."""

    entities_created: int
    entities_updated: int
    facts_added: int
    facts_deduplicated: int
    relations_created: int


class KnowledgeGraphAgent(BaseGTMAgent[KnowledgeGraphOutput]):
    """Maintains the evidence-backed knowledge graph."""

    def __init__(self):
        super().__init__(
            name="knowledge-graph",
            description="Maintains the evidence-backed knowledge web",
            result_type=KnowledgeGraphOutput,
            min_confidence=0.5,
        )
        self._bus = get_agent_bus()

        # Subscribe to all evidence-related discoveries
        self._bus.subscribe(
            self.name,
            DiscoveryType.EVIDENCED_FACT,
            self._on_fact_received
        )

    async def _on_fact_received(self, message: AgentMessage) -> None:
        """Handle incoming evidenced facts."""
        if message.evidence:
            for fact in message.evidence.facts:
                await self._process_fact(fact, message.analysis_id)

    async def _process_fact(
        self,
        fact: EvidencedFact,
        analysis_id: UUID | None
    ) -> None:
        """Process a single fact into the knowledge graph."""
        # 1. Check for duplicates
        existing = await self._find_duplicate(fact)

        if existing:
            # Update confidence if new source is better
            if fact.confidence > existing.confidence:
                await self._update_fact(existing.id, fact)
            # Mark as verified if different source
            if fact.source_name != existing.source_name:
                await self._mark_verified(existing.id, fact.id)
        else:
            # 2. Store new fact
            fact_id = await self._store_fact(fact)

            # 3. Extract/link entities
            entities = await self._extract_entities(fact)
            for entity in entities:
                await self._link_fact_entity(fact_id, entity.id)

            # 4. Extract/create relations
            relations = await self._extract_relations(fact, entities)
            for relation in relations:
                await self._link_fact_relation(fact_id, relation.id)

            # 5. Publish to bus for other agents
            await self._bus.publish(
                from_agent=self.name,
                discovery_type=DiscoveryType.ENTITY_FOUND,
                title=f"New fact: {fact.claim[:100]}",
                content={
                    "fact_id": str(fact_id),
                    "fact_type": fact.fact_type,
                    "entity_ids": [str(e.id) for e in entities],
                },
                confidence=fact.confidence,
                analysis_id=analysis_id,
            )

    async def _extract_entities(self, fact: EvidencedFact) -> list:
        """Extract entities from a fact."""
        # Implementation would use NER or structured data
        entities = []

        if fact.structured_data:
            # Company entity
            if 'company_name' in fact.structured_data or 'name' in fact.structured_data:
                name = fact.structured_data.get('company_name') or fact.structured_data.get('name')
                entity = await self._get_or_create_entity(
                    entity_type='company',
                    name=name,
                    uen=fact.structured_data.get('uen')
                )
                entities.append(entity)

            # Person entity
            if fact.fact_type == 'person_works_at':
                person = await self._get_or_create_entity(
                    entity_type='person',
                    name=fact.structured_data.get('name'),
                    linkedin_url=fact.structured_data.get('linkedin_url')
                )
                entities.append(person)

        return entities
```

---

## Part 4: Execution Plan

### Phase 1: Foundation (Weeks 1-2)
**Goal**: Set up infrastructure and FREE data sources

| # | Task | Owner | Dependencies | Output |
|---|------|-------|--------------|--------|
| 1.1 | Create database schema | Backend | None | SQL migrations |
| 1.2 | Implement EvidencedFact model | Backend | 1.1 | Pydantic models |
| 1.3 | Create MCP base server | Backend | 1.2 | BaseMCPServer class |
| 1.4 | Implement ACRA MCP server | Backend | 1.3 | acra.py |
| 1.5 | Download ACRA data.gov.sg CSV | Backend | None | data/acra_companies.csv |
| 1.6 | Implement News Aggregator MCP | Backend | 1.3 | news.py |
| 1.7 | Implement Web Scraper MCP | Backend | 1.3 | web_scraper.py |
| 1.8 | Enhance EODHD as MCP server | Backend | 1.3 | eodhd.py (enhanced) |
| 1.9 | Create Knowledge Graph agent | Backend | 1.2, A2A | knowledge_graph/agent.py |
| 1.10 | Update A2A with EvidencedDiscovery | Backend | 1.2 | agent_bus.py (enhanced) |

### Phase 2: Integration (Weeks 3-4)
**Goal**: Connect MCP servers to agents via A2A

| # | Task | Owner | Dependencies | Output |
|---|------|-------|--------------|--------|
| 2.1 | Update Market Intelligence agent | Backend | 1.6, 1.8, 1.9 | Uses MCP for data |
| 2.2 | Update Company Enricher agent | Backend | 1.4, 1.7, 1.9 | Uses MCP for data |
| 2.3 | Update Lead Hunter agent | Backend | 1.7, 1.9 | Produces LeadJustification |
| 2.4 | Update Competitor Analyst agent | Backend | 1.6, 1.7, 1.9 | Produces CompetitorSignal |
| 2.5 | Implement LinkedIn MCP server | Backend | 1.3 | linkedin.py |
| 2.6 | Add evidence chain to API responses | Backend | 2.1-2.4 | API returns sources |
| 2.7 | Create fact deduplication logic | Backend | 1.9 | Merge duplicate facts |
| 2.8 | Add graph queries for lead justification | Backend | 1.1 | SQL functions |

### Phase 3: UI (Weeks 5-6)
**Goal**: Visualize the knowledge web

| # | Task | Owner | Dependencies | Output |
|---|------|-------|--------------|--------|
| 3.1 | Create Evidence component | Frontend | 2.6 | Shows source attribution |
| 3.2 | Create LeadJustification panel | Frontend | 2.3, 3.1 | Full evidence chain UI |
| 3.3 | Create Knowledge Graph visualization | Frontend | 2.6 | D3/Cytoscape graph |
| 3.4 | Create CompetitorSignal feed | Frontend | 2.4, 3.1 | Alert feed with evidence |
| 3.5 | Add source links to all insights | Frontend | 2.6 | Click to verify |
| 3.6 | Create fact confidence indicator | Frontend | 2.6 | Visual confidence scoring |

### Phase 4: Enrichment (Weeks 7-8)
**Goal**: Add paid data sources (freemium first)

| # | Task | Owner | Dependencies | Output |
|---|------|-------|--------------|--------|
| 4.1 | Integrate Apollo.io MCP (free tier) | Backend | 1.3 | apollo.py |
| 4.2 | Integrate Hunter.io MCP (free tier) | Backend | 1.3 | hunter.py |
| 4.3 | Integrate Crunchbase MCP (free tier) | Backend | 1.3 | crunchbase.py |
| 4.4 | Implement G2 review scraper | Backend | 1.7 | g2_scraper.py |
| 4.5 | Implement Glassdoor scraper | Backend | 1.7 | glassdoor_scraper.py |
| 4.6 | Create data source priority logic | Backend | 4.1-4.5 | Source ranking |
| 4.7 | Add MyCareersFuture job scraper | Backend | 1.7 | mcf_scraper.py |
| 4.8 | Implement GeBIZ tender scraper | Backend | 1.7 | gebiz_scraper.py |

---

## Cost Summary

### Phase 1-2: FREE Sources Only
| Source | Monthly Cost | Data Provided |
|--------|-------------|---------------|
| ACRA data.gov.sg | $0 | 588K Singapore companies |
| EODHD (existing) | $0 (free tier) | Public company financials |
| NewsAPI.org | $0 (dev tier) | News search |
| Google News RSS | $0 | News aggregation |
| Business Times RSS | $0 | Singapore business news |
| TechCrunch RSS | $0 | Tech news |
| Web scraping | $0 | Company websites |
| **Total** | **$0** | |

### Phase 4: Freemium Additions
| Source | Monthly Cost | Data Provided |
|--------|-------------|---------------|
| Apollo.io | $0 (free tier) | 50 credits/month |
| Hunter.io | $0 (free tier) | 25 searches/month |
| Crunchbase | $0 (free tier) | Basic company data |
| **Total** | **$0** | |

### Future: Paid Upgrades
| Source | Monthly Cost | When to Add |
|--------|-------------|-------------|
| Apollo.io Basic | $49/mo | When free tier exhausted |
| Hunter.io Starter | $49/mo | When free tier exhausted |
| Proxycurl (LinkedIn) | ~$50/mo | For reliable LinkedIn data |
| BuiltWith | $295/mo | For comprehensive tech stack |
| **Total** | **~$450/mo** | |

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Facts with sources | 100% | Every fact has source_url |
| Source diversity | ≥3 sources/company | Unique source_names per entity |
| Lead justification depth | ≥5 facts/lead | Facts linked to lead_justification |
| Confidence accuracy | ≥80% | Spot-check sample of facts |
| Graph connectivity | ≥3 relations/entity | Average relations per entity |
| User trust | NPS ≥50 | Survey on "Do you trust the data?" |

---

## Architecture Principles

1. **Facts are immutable** - Once captured, facts don't change (append new facts instead)
2. **Sources are sacred** - Every fact MUST have a verifiable source
3. **Confidence is computed** - Based on source type, not LLM opinion
4. **Graph is the truth** - Agents read from graph, not generate from scratch
5. **LLM synthesizes only** - AI explains the graph, doesn't create facts
6. **Deduplication is continuous** - Same fact from multiple sources = higher confidence
7. **Staleness is tracked** - Facts have expiry, must be refreshed
