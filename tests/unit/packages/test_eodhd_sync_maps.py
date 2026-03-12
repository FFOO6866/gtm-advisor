"""Unit tests for GICS industry/sector → vertical slug mapping logic in sync.py.

These cover the _GICS_INDUSTRY_MAP and _SP500_SECTOR_MAP constants used by
sync_sp500_roster() and assign_verticals_to_companies().
"""

from __future__ import annotations

import pytest

from packages.integrations.eodhd.src.sync import (
    _GICS_INDUSTRY_MAP,
    _NAME_KEYWORD_RULES,
    _SP500_SECTOR_MAP,
)

# ---------------------------------------------------------------------------
# Helper: reproduce the matching logic from sync_sp500_roster()
# ---------------------------------------------------------------------------


def _resolve_vertical(industry: str, sector: str) -> str | None:
    """Mirror the two-level lookup used in sync_sp500_roster()."""
    industry_lower = industry.lower()
    for substring, slug in _GICS_INDUSTRY_MAP:
        if substring in industry_lower:
            return slug
    return _SP500_SECTOR_MAP.get(sector)


# ---------------------------------------------------------------------------
# _GICS_INDUSTRY_MAP correctness
# ---------------------------------------------------------------------------


class TestGICSIndustryMap:
    """Verify specific GICS industry strings resolve to the expected vertical."""

    @pytest.mark.parametrize("industry,expected_vertical", [
        # REITs — must match before generic 'real estate'
        ("Real Estate Investment Trusts (REITs)", "reits"),
        ("Equity Real Estate Investment Trusts", "reits"),
        # Maritime
        ("Marine", "maritime"),
        ("Oil, Gas & Consumable Fuels", "maritime"),
        ("Energy Equipment & Services", "maritime"),
        # Logistics
        ("Air Freight & Logistics", "logistics"),
        ("Road & Rail", "logistics"),
        ("Ground Transportation", "logistics"),
        # Clean Energy
        ("Electric Utilities", "clean_energy"),
        ("Water Utilities", "clean_energy"),
        ("Gas Utilities", "clean_energy"),
        ("Independent Power Producers & Energy Traders", "clean_energy"),
        # Advanced Manufacturing
        ("Semiconductors & Semiconductor Equipment", "advanced_manufacturing"),
        ("Technology Hardware, Storage & Peripherals", "advanced_manufacturing"),
        ("Aerospace & Defense", "advanced_manufacturing"),
        ("Industrial Conglomerates", "advanced_manufacturing"),
        # PropTech
        ("Construction & Engineering", "proptech"),
        ("Building Products", "proptech"),
        # ICT / SaaS
        ("Software", "ict_saas"),
        ("IT Services", "ict_saas"),
        ("Interactive Media & Services", "ict_saas"),
        ("Wireless Telecommunication Services", "ict_saas"),
        # Biomedical
        ("Pharmaceuticals", "biomedical"),
        ("Health Care Equipment & Supplies", "biomedical"),
        ("Biotechnology", "biomedical"),
        ("Life Sciences Tools & Services", "biomedical"),
        # Retail / Consumer
        ("Food & Staples Retailing", "retail_ecommerce"),
        ("Food Products", "retail_ecommerce"),
        ("Hotels, Restaurants & Leisure", "retail_ecommerce"),
        # Fintech
        ("Banks", "fintech"),
        ("Diversified Financials", "fintech"),
        ("Insurance", "fintech"),
        ("Capital Markets", "fintech"),
        # EdTech
        ("Diversified Consumer Services", "edtech"),
    ])
    def test_industry_match(self, industry: str, expected_vertical: str) -> None:
        result = _resolve_vertical(industry, sector="")
        assert result == expected_vertical, (
            f"Industry '{industry}' resolved to '{result}', expected '{expected_vertical}'"
        )

    def test_unknown_industry_returns_none_or_sector_fallback(self) -> None:
        result = _resolve_vertical("Completely Unknown Industry XYZ", sector="")
        assert result is None

    def test_reit_takes_precedence_over_generic_real_estate(self) -> None:
        """Ensure 'real estate investment trust' matches before any generic rule."""
        result = _resolve_vertical("Real Estate Investment Trust", sector="Real Estate")
        assert result == "reits"

    def test_case_insensitive(self) -> None:
        """Industry matching must be case-insensitive."""
        assert _resolve_vertical("SOFTWARE", sector="") == "ict_saas"
        assert _resolve_vertical("software", sector="") == "ict_saas"
        assert _resolve_vertical("Software", sector="") == "ict_saas"

    def test_no_duplicate_slugs_for_ambiguous_string(self) -> None:
        """Each industry string should produce exactly one vertical — first match wins."""
        # "semiconductors" contains "semi" but also "manufacturing" — check it maps correctly
        result = _resolve_vertical("Semiconductors", sector="")
        assert result == "advanced_manufacturing"

    def test_all_slugs_in_map_are_non_empty_strings(self) -> None:
        for substring, slug in _GICS_INDUSTRY_MAP:
            assert isinstance(substring, str) and substring, "Empty substring in map"
            assert isinstance(slug, str) and slug, f"Empty slug for '{substring}'"

    def test_no_duplicate_substrings(self) -> None:
        """Each substring should appear at most once (to avoid silent shadowing)."""
        substrings = [s for s, _ in _GICS_INDUSTRY_MAP]
        assert len(substrings) == len(set(substrings)), "Duplicate substring in _GICS_INDUSTRY_MAP"


# ---------------------------------------------------------------------------
# _SP500_SECTOR_MAP correctness
# ---------------------------------------------------------------------------


class TestSP500SectorMap:
    @pytest.mark.parametrize("sector,expected_vertical", [
        ("Technology", "ict_saas"),
        ("Financial Services", "fintech"),
        ("Healthcare", "biomedical"),
        ("Real Estate", "reits"),
        ("Utilities", "clean_energy"),
        ("Industrials", "advanced_manufacturing"),
        ("Consumer Cyclical", "retail_ecommerce"),
        ("Consumer Defensive", "retail_ecommerce"),
        ("Communication Services", "ict_saas"),
        ("Energy", "clean_energy"),
        ("Basic Materials", "advanced_manufacturing"),
    ])
    def test_sector_match(self, sector: str, expected_vertical: str) -> None:
        result = _SP500_SECTOR_MAP.get(sector)
        assert result == expected_vertical, (
            f"Sector '{sector}' → '{result}', expected '{expected_vertical}'"
        )

    def test_unknown_sector_returns_none(self) -> None:
        assert _SP500_SECTOR_MAP.get("Unknown Sector XYZ") is None

    def test_all_11_gics_sectors_covered(self) -> None:
        """All 11 GICS sector names from EODHD should be in the map."""
        assert len(_SP500_SECTOR_MAP) == 11

    def test_no_empty_values(self) -> None:
        for sector, slug in _SP500_SECTOR_MAP.items():
            assert slug, f"Empty slug for sector '{sector}'"


# ---------------------------------------------------------------------------
# Integration: industry beats sector (priority test)
# ---------------------------------------------------------------------------


class TestResolutionPriority:
    def test_industry_match_wins_over_sector(self) -> None:
        """A specific industry match should override the sector fallback."""
        # "Semiconductors" → advanced_manufacturing via industry
        # but sector "Technology" → ict_saas
        result = _resolve_vertical("Semiconductors & Semiconductor Equipment", sector="Technology")
        assert result == "advanced_manufacturing"  # industry wins

    def test_sector_fallback_used_when_no_industry_match(self) -> None:
        """When industry has no match, fall back to sector map."""
        result = _resolve_vertical("", sector="Technology")
        assert result == "ict_saas"

    def test_both_empty_returns_none(self) -> None:
        result = _resolve_vertical("", sector="")
        assert result is None


# ---------------------------------------------------------------------------
# _NAME_KEYWORD_RULES correctness
# ---------------------------------------------------------------------------


def _resolve_by_name(name: str) -> str | None:
    """Mirror the Level 4 name-keyword lookup used in assign_verticals_to_companies()."""
    name_lower = name.lower()
    for keywords, slug in _NAME_KEYWORD_RULES:
        if any(kw in name_lower for kw in keywords):
            return slug
    return None


class TestNameKeywordRules:
    """Verify specific company name strings resolve to the expected vertical."""

    @pytest.mark.unit
    def test_grand_banks_yachts_resolves_to_maritime(self) -> None:
        """'grand banks yachts' keyword should map to maritime."""
        result = _resolve_by_name("grand banks yachts limited")
        assert result == "maritime"

    @pytest.mark.unit
    def test_healthbank_resolves_to_biomedical(self) -> None:
        """'healthbank' keyword should map to biomedical."""
        result = _resolve_by_name("healthbank holdings limited")
        assert result == "biomedical"

    @pytest.mark.unit
    def test_unknown_name_returns_none(self) -> None:
        """A company name with no matching keyword should return None."""
        result = _resolve_by_name("zephyr novelties pte ltd")
        assert result is None
