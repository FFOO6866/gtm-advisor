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

    Uses the data.gov.sg API to query official company registration data.
    This provides high-confidence (0.95-0.99) facts from the government source.

    The API supports two modes:
    1. Dataset search - Search across ACRA datasets
    2. Direct resource query - Query specific dataset resources

    Example:
        server = ACRAMCPServer.create()
        result = await server.search("TechCorp")
        for fact in result.facts:
            print(f"{fact.claim} (confidence: {fact.confidence})")
    """

    # data.gov.sg API endpoints
    # See: https://guide.data.gov.sg/developer-guide/api-guide
    BASE_URL = "https://api-production.data.gov.sg/v2/public/api"

    # Known ACRA-related dataset IDs on data.gov.sg
    # These are discovered by searching the data.gov.sg catalog
    ACRA_DATASET_IDS = [
        "d_6ae244ecbbcda21e5fd32a9e6b7c3dde",  # Entities registered with ACRA
    ]

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
        self._discovered_resources: dict[str, str] = {}

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
        """Check if data.gov.sg API is accessible."""
        try:
            # Try to list datasets to verify API is working
            response = await self._client.get(
                f"{self.BASE_URL}/datasets",
                params={"page": 1, "limit": 1},
            )
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("health_check_failed", error=str(e))
            return False

    async def _discover_resources(self) -> None:
        """Discover available ACRA resources from data.gov.sg."""
        if self._discovered_resources:
            return  # Already discovered

        for dataset_id in self.ACRA_DATASET_IDS:
            try:
                response = await self._client.get(
                    f"{self.BASE_URL}/datasets/{dataset_id}/metadata",
                )
                if response.status_code == 200:
                    data = response.json()
                    dataset_info = data.get("data", {})

                    # Store dataset info
                    self._discovered_resources[dataset_id] = {
                        "name": dataset_info.get("name", "ACRA Dataset"),
                        "description": dataset_info.get("description", ""),
                        "last_updated": dataset_info.get("lastUpdatedAt", ""),
                    }

                    self._logger.info(
                        "discovered_acra_resource",
                        dataset_id=dataset_id,
                        name=dataset_info.get("name"),
                    )
            except Exception as e:
                self._logger.warning(
                    "resource_discovery_failed",
                    dataset_id=dataset_id,
                    error=str(e),
                )

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search ACRA for companies matching query.

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

        # Discover resources if not done yet
        await self._discover_resources()

        facts = []
        entities = []
        errors = []
        total_results = 0

        # Try each known ACRA dataset
        for dataset_id in self.ACRA_DATASET_IDS:
            try:
                result = await self._query_dataset(dataset_id, query, limit, offset)
                facts.extend(result.get("facts", []))
                entities.extend(result.get("entities", []))
                total_results += result.get("total", 0)
            except Exception as e:
                error_msg = f"Dataset {dataset_id} query failed: {str(e)}"
                errors.append(error_msg)
                self._logger.warning("dataset_query_failed", dataset_id=dataset_id, error=str(e))

        # If no results from datasets, try search API
        if not facts:
            try:
                search_result = await self._search_datasets(query, limit)
                facts.extend(search_result.get("facts", []))
                entities.extend(search_result.get("entities", []))
                total_results += search_result.get("total", 0)
            except Exception as e:
                errors.append(f"Search API failed: {str(e)}")

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

    async def _query_dataset(
        self,
        dataset_id: str,
        query: str,
        limit: int,
        offset: int,  # noqa: ARG002 - reserved for pagination
    ) -> dict[str, Any]:
        """Query a specific ACRA dataset."""
        # Use the initiate download endpoint to get data
        # This is the recommended way to query large datasets on data.gov.sg

        params = {
            "format": "json",
        }

        # For search, we use the poll endpoint with filters
        response = await self._client.get(
            f"{self.BASE_URL}/datasets/{dataset_id}/poll-download",
            params=params,
        )

        if response.status_code != 200:
            raise Exception(f"API returned status {response.status_code}")

        data = response.json()

        # Check if download is ready
        if data.get("data", {}).get("status") != "completed":
            # Data not ready, return empty
            return {"facts": [], "entities": [], "total": 0}

        # Get the download URL and fetch data
        download_url = data.get("data", {}).get("url")
        if not download_url:
            return {"facts": [], "entities": [], "total": 0}

        # Fetch the actual data
        data_response = await self._client.get(download_url)
        if data_response.status_code != 200:
            return {"facts": [], "entities": [], "total": 0}

        records = data_response.json()
        if not isinstance(records, list):
            records = records.get("data", []) if isinstance(records, dict) else []

        # Filter records by query
        query_lower = query.lower()
        matching_records = [
            r for r in records
            if self._record_matches_query(r, query_lower)
        ][:limit]

        facts = []
        entities = []

        for record in matching_records:
            record_facts, entity = self._parse_company_record(record, dataset_id)
            facts.extend(record_facts)
            if entity:
                entities.append(entity)

        return {
            "facts": facts,
            "entities": entities,
            "total": len(matching_records),
        }

    def _record_matches_query(self, record: dict[str, Any], query_lower: str) -> bool:
        """Check if a record matches the search query."""
        # Check common field names for company data
        searchable_fields = [
            "entity_name", "uen", "company_name", "business_name",
            "name", "reg_name", "registered_name",
        ]

        for field in searchable_fields:
            value = record.get(field, "")
            if value and query_lower in str(value).lower():
                return True

        return False

    async def _search_datasets(self, query: str, limit: int) -> dict[str, Any]:
        """Search across datasets using the search API."""
        try:
            # Search for ACRA-related datasets
            response = await self._client.get(
                f"{self.BASE_URL}/datasets",
                params={
                    "query": f"ACRA {query}",
                    "page": 1,
                    "limit": 10,
                },
            )

            if response.status_code != 200:
                return {"facts": [], "entities": [], "total": 0}

            data = response.json()
            datasets = data.get("data", {}).get("datasets", [])

            # Create facts about found datasets (metadata)
            facts = []
            for dataset in datasets[:limit]:
                if "acra" in dataset.get("name", "").lower():
                    facts.append(
                        self.create_fact(
                            claim=f"ACRA dataset available: {dataset.get('name', 'Unknown')}",
                            fact_type=FactType.COMPANY_INFO.value,
                            source_name="data.gov.sg",
                            source_url=f"https://data.gov.sg/datasets/{dataset.get('datasetId', '')}",
                            confidence=0.95,
                            extracted_data={
                                "dataset_id": dataset.get("datasetId"),
                                "name": dataset.get("name"),
                                "description": dataset.get("description"),
                            },
                        )
                    )

            return {"facts": facts, "entities": [], "total": len(facts)}

        except Exception as e:
            self._logger.warning("search_failed", error=str(e))
            return {"facts": [], "entities": [], "total": 0}

    def _parse_company_record(
        self, record: dict[str, Any], dataset_id: str
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

        # Source URL
        source_url = f"https://data.gov.sg/datasets/{dataset_id}"
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
