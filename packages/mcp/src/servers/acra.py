"""ACRA MCP Server - Singapore Company Registry.

Queries Singapore's Accounting and Corporate Regulatory Authority (ACRA)
data through data.gov.sg APIs. Provides high-confidence company information
from the official government registry.

Data available:
- Company UEN (Unique Entity Number)
- Business name and registration date
- Business status (active, struck off, etc.)
- Entity type (local company, sole proprietor, etc.)
- Primary SSIC code (industry classification)

API Documentation: https://guide.data.gov.sg/developer-guide/api-guide
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from packages.mcp.src.base import APIBasedMCPServer
from packages.mcp.src.types import (
    EntityReference,
    EntityType,
    FactType,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)

logger = structlog.get_logger()

# SSIC code to industry mapping (Singapore Standard Industrial Classification)
# Source: https://www.singstat.gov.sg/standards/standards-and-classifications/ssic
SSIC_INDUSTRY_MAP = {
    "01": "Agriculture",
    "02": "Agriculture",
    "03": "Agriculture",
    "05": "Mining",
    "06": "Mining",
    "07": "Mining",
    "08": "Mining",
    "09": "Mining",
    "10": "Manufacturing",
    "11": "Manufacturing",
    "12": "Manufacturing",
    "13": "Manufacturing",
    "14": "Manufacturing",
    "15": "Manufacturing",
    "16": "Manufacturing",
    "17": "Manufacturing",
    "18": "Manufacturing",
    "19": "Manufacturing",
    "20": "Manufacturing",
    "21": "Manufacturing",
    "22": "Manufacturing",
    "23": "Manufacturing",
    "24": "Manufacturing",
    "25": "Manufacturing",
    "26": "Manufacturing",
    "27": "Manufacturing",
    "28": "Manufacturing",
    "29": "Manufacturing",
    "30": "Manufacturing",
    "31": "Manufacturing",
    "32": "Manufacturing",
    "33": "Manufacturing",
    "35": "Utilities",
    "36": "Utilities",
    "37": "Utilities",
    "38": "Utilities",
    "39": "Utilities",
    "41": "Construction",
    "42": "Construction",
    "43": "Construction",
    "45": "Wholesale & Retail Trade",
    "46": "Wholesale & Retail Trade",
    "47": "Wholesale & Retail Trade",
    "49": "Transportation & Storage",
    "50": "Transportation & Storage",
    "51": "Transportation & Storage",
    "52": "Transportation & Storage",
    "53": "Transportation & Storage",
    "55": "Accommodation",
    "56": "Food & Beverage",
    "58": "Information & Communications",
    "59": "Information & Communications",
    "60": "Information & Communications",
    "61": "Information & Communications",
    "62": "Information Technology",
    "63": "Information Technology",
    "64": "Financial Services",
    "65": "Financial Services",
    "66": "Financial Services",
    "68": "Real Estate",
    "69": "Professional Services",
    "70": "Professional Services",
    "71": "Professional Services",
    "72": "Professional Services",
    "73": "Professional Services",
    "74": "Professional Services",
    "75": "Professional Services",
    "77": "Administrative Services",
    "78": "Administrative Services",
    "79": "Administrative Services",
    "80": "Administrative Services",
    "81": "Administrative Services",
    "82": "Administrative Services",
    "84": "Public Administration",
    "85": "Education",
    "86": "Healthcare",
    "87": "Healthcare",
    "88": "Healthcare",
    "90": "Arts & Entertainment",
    "91": "Arts & Entertainment",
    "92": "Arts & Entertainment",
    "93": "Arts & Entertainment",
    "94": "Other Services",
    "95": "Other Services",
    "96": "Other Services",
    "97": "Household Services",
    "99": "Extraterritorial",
}


class ACRAMCPServer(APIBasedMCPServer):
    """MCP Server for ACRA Singapore company data.

    Uses the data.gov.sg CKAN API to query official company registration data.
    This provides high-confidence (0.95-0.99) facts from the government source.

    Data source: https://data.gov.sg/datasets/d_3f960c10fed6145404ca7b821f263b87/view
    API documentation: https://data.gov.sg/api/action/datastore_search

    Example:
        server = ACRAMCPServer.create()
        result = await server.search("TechCorp")
        for fact in result.facts:
            print(f"{fact.claim} (confidence: {fact.confidence})")
    """

    # data.gov.sg CKAN API endpoint
    BASE_URL = "https://data.gov.sg/api/action"

    # ACRA dataset resource ID (Entities Registered with ACRA)
    # Source: https://data.gov.sg/datasets/d_3f960c10fed6145404ca7b821f263b87/view
    ACRA_RESOURCE_ID = "d_3f960c10fed6145404ca7b821f263b87"

    def __init__(self, config: MCPServerConfig) -> None:
        """Initialize ACRA server.

        Args:
            config: Server configuration
        """
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": "GTM-Advisor/1.0 (Singapore SME GTM Platform)",
            },
        )

    @classmethod
    def create(cls) -> ACRAMCPServer:
        """Create server with default configuration."""
        config = MCPServerConfig(
            name="acra-singapore",
            source_type=SourceType.ACRA,
            description="Singapore ACRA company registry via data.gov.sg",
            requires_api_key=False,  # data.gov.sg is free
            rate_limit_per_hour=100,
            rate_limit_per_day=1000,
            cache_ttl_seconds=86400,  # 24 hours - data doesn't change often
            timeout_seconds=30,
        )
        return cls(config)

    @property
    def is_configured(self) -> bool:
        """ACRA doesn't require API key."""
        return True

    async def _health_check_impl(self) -> bool:
        """Check if data.gov.sg CKAN API is accessible."""
        try:
            # Test with a minimal query to verify API is working
            response = await self._client.get(
                f"{self.BASE_URL}/datastore_search",
                params={
                    "resource_id": self.ACRA_RESOURCE_ID,
                    "limit": 1,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)
            return False
        except Exception as e:
            self._logger.warning("health_check_failed", error=str(e))
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search ACRA for companies matching query.

        Uses the data.gov.sg CKAN datastore_search API with full-text search.

        Args:
            query: Company name or UEN to search
            **kwargs: Additional parameters:
                - limit: Max results (default 20)
                - offset: Pagination offset (default 0)

        Returns:
            Query result with company facts
        """
        limit = min(kwargs.get("limit", 20), 100)
        offset = kwargs.get("offset", 0)

        # Check cache
        cache_key = f"acra:{query}:{limit}:{offset}"
        cached = self._get_cached(cache_key)
        if cached:
            self._logger.debug("cache_hit", query=query)
            return cached

        facts = []
        entities = []
        errors = []
        total_results = 0

        try:
            # Use CKAN datastore_search API with full-text search
            response = await self._client.get(
                f"{self.BASE_URL}/datastore_search",
                params={
                    "resource_id": self.ACRA_RESOURCE_ID,
                    "q": query,  # Full-text search
                    "limit": limit,
                    "offset": offset,
                },
            )

            if response.status_code != 200:
                raise Exception(f"API returned status {response.status_code}")

            data = response.json()

            if not data.get("success"):
                error_msg = data.get("error", {}).get("message", "Unknown API error")
                raise Exception(error_msg)

            result_data = data.get("result", {})
            records = result_data.get("records", [])
            total_results = result_data.get("total", len(records))

            self._logger.info(
                "acra_search_success",
                query=query,
                records_found=len(records),
                total_available=total_results,
            )

            for record in records:
                record_facts, entity = self._parse_company_record(record)
                facts.extend(record_facts)
                if entity:
                    entities.append(entity)

        except Exception as e:
            error_msg = f"ACRA query failed: {str(e)}"
            errors.append(error_msg)
            self._logger.warning("acra_query_failed", query=query, error=str(e))

        result = MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=total_results,
            has_more=total_results > offset + limit,
            errors=errors if not facts else [],  # Only report errors if no results
        )

        if facts:  # Only cache successful results
            self._set_cached(cache_key, result)

        return result

    def _parse_company_record(
        self, record: dict[str, Any]
    ) -> tuple[list, EntityReference | None]:
        """Parse an ACRA record into evidenced facts.

        Handles various field naming conventions used in different datasets.
        """
        facts = []

        # Extract fields with fallbacks for different naming conventions
        uen = (
            record.get("uen") or
            record.get("UEN") or
            record.get("entity_uen") or
            record.get("uen_number") or
            ""
        )
        name = (
            record.get("entity_name") or
            record.get("company_name") or
            record.get("business_name") or
            record.get("name") or
            record.get("reg_name") or
            ""
        )
        status = (
            record.get("entity_status") or
            record.get("entity_status_description") or
            record.get("status") or
            record.get("company_status") or
            ""
        )
        entity_type = (
            record.get("entity_type") or
            record.get("entity_type_description") or
            record.get("business_type") or
            ""
        )
        reg_date = (
            record.get("registration_date") or
            record.get("reg_date") or
            record.get("incorporation_date") or
            ""
        )
        ssic = (
            record.get("primary_ssic_code") or
            record.get("ssic_code") or
            record.get("ssic") or
            ""
        )
        ssic_desc = (
            record.get("primary_ssic_description") or
            record.get("ssic_description") or
            ""
        )

        if not uen and not name:
            return facts, None

        # Source URL - link to ACRA BizFile for UEN lookup
        source_url = f"https://data.gov.sg/datasets/{self.ACRA_RESOURCE_ID}/view"
        if uen:
            source_url = f"https://www.acra.gov.sg/bizfile/company-profile?uen={uen}"

        # Fact 1: Company registration
        claim_parts = []
        if name:
            claim_parts.append(name)
        if uen:
            claim_parts.append(f"(UEN: {uen})")
        claim_parts.append("is registered in Singapore")
        if entity_type:
            claim_parts.append(f"as a {entity_type}")

        facts.append(
            self.create_fact(
                claim=" ".join(claim_parts),
                fact_type=FactType.COMPANY_INFO.value,
                source_name="ACRA Singapore via data.gov.sg",
                source_url=source_url,
                raw_excerpt=str(record)[:500],
                confidence=0.99,  # Government source
                extracted_data={
                    "uen": uen,
                    "company_name": name,
                    "entity_type": entity_type,
                    "status": status,
                    "registration_date": reg_date,
                    "ssic_code": ssic,
                },
                related_entities=[name] if name else [],
            )
        )

        # Fact 2: Business status
        if status:
            is_active = any(
                s in status.lower()
                for s in ["live", "active", "registered", "existing"]
            )
            facts.append(
                self.create_fact(
                    claim=f"{name or uen} has business status: {status}",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="ACRA Singapore",
                    source_url=source_url,
                    confidence=0.99,
                    extracted_data={
                        "uen": uen,
                        "status": status,
                        "is_active": is_active,
                    },
                    related_entities=[name] if name else [],
                )
            )

        # Fact 3: Industry classification
        if ssic:
            industry = self._ssic_to_industry(ssic)
            industry_claim = f"{name or uen} operates in {ssic_desc or industry}"
            if ssic:
                industry_claim += f" (SSIC: {ssic})"

            facts.append(
                self.create_fact(
                    claim=industry_claim,
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name="ACRA Singapore",
                    source_url=source_url,
                    confidence=0.95,
                    extracted_data={
                        "uen": uen,
                        "ssic_code": ssic,
                        "ssic_description": ssic_desc,
                        "industry": industry,
                    },
                    related_entities=[name] if name else [],
                )
            )

        # Fact 4: Registration date
        if reg_date:
            parsed_date = self._parse_date(reg_date)
            if parsed_date:
                facts.append(
                    self.create_fact(
                        claim=f"{name or uen} was registered on {reg_date}",
                        fact_type=FactType.COMPANY_INFO.value,
                        source_name="ACRA Singapore",
                        source_url=source_url,
                        valid_from=parsed_date,
                        confidence=0.99,
                        extracted_data={
                            "uen": uen,
                            "registration_date": reg_date,
                        },
                        related_entities=[name] if name else [],
                    )
                )

        # Create entity reference
        entity = None
        if name or uen:
            entity = EntityReference(
                entity_type=EntityType.COMPANY,
                name=name or f"UEN:{uen}",
                canonical_name=(name or "").upper(),
                acra_uen=uen if uen else None,
                external_ids={"acra_uen": uen} if uen else {},
            )

        return facts, entity

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse various date formats."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _ssic_to_industry(self, ssic_code: str) -> str:
        """Convert SSIC code to industry category."""
        if not ssic_code:
            return "Other"

        # Try first 2 digits
        prefix = ssic_code[:2] if len(ssic_code) >= 2 else ssic_code
        return SSIC_INDUSTRY_MAP.get(prefix, "Other")

    async def search_by_uen(self, uen: str) -> MCPQueryResult:
        """Search for a specific company by UEN."""
        return await self.search(uen, limit=5)

    async def get_company_details(self, uen: str) -> MCPQueryResult:
        """Get detailed information for a specific company by UEN."""
        result = await self.search_by_uen(uen)

        # Filter to only facts about this specific UEN
        filtered_facts = [
            f for f in result.facts
            if f.extracted_data.get("uen") == uen
        ]

        return MCPQueryResult(
            facts=filtered_facts,
            entities=result.entities,
            query=f"uen:{uen}",
            mcp_server=self.name,
            total_results=len(filtered_facts),
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
