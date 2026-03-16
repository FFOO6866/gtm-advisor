"""Unit tests for packages/intelligence/src/vertical_synthesizer.py.

Covers:
- _normalise_company_name(): suffix stripping and lowercasing
- _build_competitive_dynamics(): dual-class share dedup by market cap
- _build_regulatory_environment(): generic + vertical-specific articles, dedup, limit
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.intelligence.src.vertical_synthesizer import (
    VerticalIntelligenceSynthesizer,
    _normalise_company_name,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vertical(slug: str = "fintech", name: str = "Fintech") -> MagicMock:
    """Minimal MarketVertical stand-in."""
    v = MagicMock()
    v.id = uuid.uuid4()
    v.slug = slug
    v.name = name
    return v


def _make_listed_company(
    name: str,
    ticker: str = "TEST",
    market_cap_sgd: float | None = None,
) -> MagicMock:
    """Minimal ListedCompany stand-in."""
    lc = MagicMock()
    lc.id = uuid.uuid4()
    lc.name = name
    lc.ticker = ticker
    lc.market_cap_sgd = market_cap_sgd
    return lc


def _make_snapshot(
    revenue_growth_yoy: float | None = None,
    revenue: float | None = None,
    sga_to_revenue: float | None = None,
    rnd_to_revenue: float | None = None,
) -> MagicMock:
    """Minimal CompanyFinancialSnapshot stand-in."""
    snap = MagicMock()
    snap.revenue_growth_yoy = revenue_growth_yoy
    snap.revenue = revenue
    snap.sga_to_revenue = sga_to_revenue
    snap.rnd_to_revenue = rnd_to_revenue
    return snap


def _make_sg_article(
    url: str,
    title: str,
    category_type: str = "compliance",
    summary: str | None = None,
    source: str = "MAS",
    effective_date: str | None = None,
    fetched_at: datetime | None = None,
) -> MagicMock:
    """Minimal SgKnowledgeArticle stand-in."""
    art = MagicMock()
    art.url = url
    art.title = title
    art.category_type = category_type
    art.summary = summary
    art.source = source
    art.effective_date = effective_date
    art.fetched_at = fetched_at or datetime.now(UTC)
    return art


def _make_mock_session() -> AsyncMock:
    """Return an AsyncMock that satisfies the AsyncSession interface."""
    session = AsyncMock()
    return session


def _patch_session_execute(session: AsyncMock, scalars: list) -> None:
    """Configure session.execute() to return a result whose scalars().all() yields scalars."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars
    session.execute = AsyncMock(return_value=result)


def _patch_session_execute_rows(session: AsyncMock, rows: list) -> None:
    """Configure session.execute() to return a result whose .all() yields rows directly."""
    result = MagicMock()
    result.all.return_value = rows
    session.execute = AsyncMock(return_value=result)


# ---------------------------------------------------------------------------
# _normalise_company_name
# ---------------------------------------------------------------------------


class TestNormaliseCompanyName:
    """Tests for the module-level _normalise_company_name() function."""

    @pytest.mark.unit
    def test_strips_inc_and_class_a_suffix(self) -> None:
        """'Alphabet Inc. Class A' normalises to 'alphabet'."""
        assert _normalise_company_name("Alphabet Inc. Class A") == "alphabet"

    @pytest.mark.unit
    def test_strips_inc_and_class_c_suffix(self) -> None:
        """'Alphabet Inc. Class C' produces the same normalised form as Class A."""
        assert _normalise_company_name("Alphabet Inc. Class C") == "alphabet"

    @pytest.mark.unit
    def test_class_a_and_class_c_produce_same_key(self) -> None:
        """Dedup key for Class A equals dedup key for Class C."""
        key_a = _normalise_company_name("Alphabet Inc. Class A")
        key_c = _normalise_company_name("Alphabet Inc. Class C")
        assert key_a == key_c

    @pytest.mark.unit
    def test_strips_ltd_suffix(self) -> None:
        """'DBS Group Holdings Ltd' normalises to 'dbs'."""
        assert _normalise_company_name("DBS Group Holdings Ltd") == "dbs"

    @pytest.mark.unit
    def test_strips_trailing_inc_dot(self) -> None:
        """'Apple Inc.' normalises to 'apple'."""
        assert _normalise_company_name("Apple Inc.") == "apple"

    @pytest.mark.unit
    def test_strips_bare_ltd(self) -> None:
        """'Sea Ltd' normalises to 'sea'."""
        assert _normalise_company_name("Sea Ltd") == "sea"

    @pytest.mark.unit
    def test_plain_name_lowercased(self) -> None:
        """A name with no suffix is just lowercased."""
        assert _normalise_company_name("Grab") == "grab"

    @pytest.mark.unit
    def test_case_insensitive_suffix_strip(self) -> None:
        """Suffix matching is case-insensitive ('INC' vs 'Inc.')."""
        assert _normalise_company_name("FooBar INC") == "foobar"

    @pytest.mark.unit
    def test_corp_suffix_stripped(self) -> None:
        """'Some Corp' normalises to 'some'."""
        assert _normalise_company_name("Some Corp") == "some"

    @pytest.mark.unit
    def test_pte_suffix_stripped(self) -> None:
        """'TechStart Pte' normalises to 'techstart'."""
        assert _normalise_company_name("TechStart Pte") == "techstart"


# ---------------------------------------------------------------------------
# _build_competitive_dynamics — dual-class dedup
# ---------------------------------------------------------------------------


class TestBuildCompetitiveDynamicsDualClassDedup:
    """Verify that dual-class share listings are collapsed to a single entry."""

    def _make_synthesizer(self, session: AsyncMock) -> VerticalIntelligenceSynthesizer:
        return VerticalIntelligenceSynthesizer(session=session)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dedup_keeps_larger_market_cap(self) -> None:
        """When two rows share the same normalised name, the one with larger market cap is kept."""
        session = _make_mock_session()
        vertical = _make_vertical()

        lc_class_a = _make_listed_company("Alphabet Inc. Class A", ticker="GOOGL", market_cap_sgd=100_000)
        lc_class_c = _make_listed_company("Alphabet Inc. Class C", ticker="GOOG", market_cap_sgd=200_000)
        snap_a = _make_snapshot(revenue_growth_yoy=0.10, revenue=5e7)
        snap_c = _make_snapshot(revenue_growth_yoy=0.10, revenue=5e7)

        # Both rows are returned by the query (Class A first, then Class C)
        rows = [(lc_class_a, snap_a), (lc_class_c, snap_c)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        session.execute = AsyncMock(return_value=result_mock)

        synthesizer = self._make_synthesizer(session)
        dynamics = await synthesizer._build_competitive_dynamics(vertical)

        # Only one entry should survive dedup
        assert dynamics.get("total_tracked") == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dedup_selects_ticker_with_higher_cap(self) -> None:
        """The surviving entry's ticker must be from the company with the higher market cap."""
        session = _make_mock_session()
        vertical = _make_vertical()

        lc_small = _make_listed_company("Alphabet Inc. Class A", ticker="GOOGL", market_cap_sgd=50_000)
        lc_large = _make_listed_company("Alphabet Inc. Class C", ticker="GOOG", market_cap_sgd=300_000)
        snap_small = _make_snapshot(revenue_growth_yoy=0.10, revenue=5e7)
        snap_large = _make_snapshot(revenue_growth_yoy=0.10, revenue=5e7)

        rows = [(lc_small, snap_small), (lc_large, snap_large)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        session.execute = AsyncMock(return_value=result_mock)

        synthesizer = self._make_synthesizer(session)
        dynamics = await synthesizer._build_competitive_dynamics(vertical)

        # The leaders list contains the surviving company — must be the large-cap one
        leaders = dynamics.get("leaders", [])
        assert len(leaders) == 1
        assert leaders[0]["ticker"] == "GOOG"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_distinct_names_are_not_merged(self) -> None:
        """Two companies with different normalised names are kept as separate entries."""
        session = _make_mock_session()
        vertical = _make_vertical()

        lc_a = _make_listed_company("DBS Group Holdings Ltd", ticker="D05", market_cap_sgd=80_000)
        lc_b = _make_listed_company("OCBC Ltd", ticker="O39", market_cap_sgd=60_000)
        snap_a = _make_snapshot()
        snap_b = _make_snapshot()

        rows = [(lc_a, snap_a), (lc_b, snap_b)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        session.execute = AsyncMock(return_value=result_mock)

        synthesizer = self._make_synthesizer(session)
        dynamics = await synthesizer._build_competitive_dynamics(vertical)

        assert dynamics.get("total_tracked") == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_dict(self) -> None:
        """When no rows are returned, an empty dict is produced without error."""
        session = _make_mock_session()
        vertical = _make_vertical()

        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.execute = AsyncMock(return_value=result_mock)

        synthesizer = self._make_synthesizer(session)
        dynamics = await synthesizer._build_competitive_dynamics(vertical)

        assert dynamics == {}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_duplicate_company_id_is_skipped(self) -> None:
        """A company appearing twice (same id) in the result set is only counted once."""
        session = _make_mock_session()
        vertical = _make_vertical()

        shared_id = uuid.uuid4()
        lc = _make_listed_company("Sea Ltd", ticker="SE", market_cap_sgd=500_000)
        lc.id = shared_id
        snap1 = _make_snapshot()
        snap2 = _make_snapshot()

        # Same company id appears twice (e.g. two annual snapshots returned)
        rows = [(lc, snap1), (lc, snap2)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        session.execute = AsyncMock(return_value=result_mock)

        synthesizer = self._make_synthesizer(session)
        dynamics = await synthesizer._build_competitive_dynamics(vertical)

        assert dynamics.get("total_tracked") == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_leaders_sorted_by_market_cap_descending(self) -> None:
        """Leaders list must be ordered largest market cap first."""
        session = _make_mock_session()
        vertical = _make_vertical()

        companies = [
            (_make_listed_company("Alpha Inc.", ticker="A", market_cap_sgd=10_000), _make_snapshot()),
            (_make_listed_company("Beta Inc.", ticker="B", market_cap_sgd=50_000), _make_snapshot()),
            (_make_listed_company("Gamma Inc.", ticker="C", market_cap_sgd=30_000), _make_snapshot()),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = companies
        session.execute = AsyncMock(return_value=result_mock)

        synthesizer = self._make_synthesizer(session)
        dynamics = await synthesizer._build_competitive_dynamics(vertical)

        leaders = dynamics.get("leaders", [])
        caps = [entry["market_cap_sgd"] for entry in leaders]
        assert caps == sorted(caps, reverse=True)


# ---------------------------------------------------------------------------
# _build_regulatory_environment
# ---------------------------------------------------------------------------


class TestBuildRegulatoryEnvironment:
    """Verify regulatory article retrieval, vertical-specific filtering, dedup, and limit."""

    def _make_synthesizer(self, session: AsyncMock) -> VerticalIntelligenceSynthesizer:
        return VerticalIntelligenceSynthesizer(session=session)

    def _configure_session_for_regulatory(
        self,
        session: AsyncMock,
        generic_articles: list,
        regulation_articles: list,
    ) -> None:
        """Set up the session to return generic articles on the first execute call
        and regulation articles on the second call (used for vertical-specific lookup)."""
        generic_result = MagicMock()
        generic_result.scalars.return_value.all.return_value = generic_articles

        regulation_result = MagicMock()
        regulation_result.scalars.return_value.all.return_value = regulation_articles

        session.execute = AsyncMock(side_effect=[generic_result, regulation_result])

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_generic_compliance_articles(self) -> None:
        """Compliance, enforcement, and grant articles are always returned."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="maritime")  # no special keywords for a second query

        compliance_art = _make_sg_article(
            url="https://example.com/compliance-1",
            title="PDPA Compliance Update",
            category_type="compliance",
        )
        grant_art = _make_sg_article(
            url="https://example.com/grant-1",
            title="PSG Grant Overview",
            category_type="grant",
        )

        # Maritime has special keywords, so two execute calls will be made.
        # Second call returns no regulation articles to keep the test focused.
        self._configure_session_for_regulatory(
            session,
            generic_articles=[compliance_art, grant_art],
            regulation_articles=[],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        urls = [item["url"] for item in result]
        assert "https://example.com/compliance-1" in urls
        assert "https://example.com/grant-1" in urls

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fintech_vertical_includes_mas_regulation_articles(self) -> None:
        """For the fintech vertical, regulation articles mentioning MAS keywords are included."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="fintech")

        generic_art = _make_sg_article(
            url="https://example.com/generic",
            title="Generic Compliance Note",
            category_type="compliance",
        )
        mas_art = _make_sg_article(
            url="https://example.com/mas-circular",
            title="MAS Payment Services Circular",
            category_type="regulation",
            summary="New MAS requirements for payment services providers.",
        )
        # Regulation article that does NOT match fintech keywords — should be excluded
        unrelated_art = _make_sg_article(
            url="https://example.com/building-regulation",
            title="BCA Building Safety Notice",
            category_type="regulation",
            summary="Construction safety standards update.",
        )

        self._configure_session_for_regulatory(
            session,
            generic_articles=[generic_art],
            regulation_articles=[mas_art, unrelated_art],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        urls = [item["url"] for item in result]
        assert "https://example.com/mas-circular" in urls
        assert "https://example.com/building-regulation" not in urls

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deduplicates_by_url(self) -> None:
        """An article appearing in both generic and regulation results is returned only once."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="fintech")

        shared_url = "https://example.com/shared-article"
        art_generic = _make_sg_article(
            url=shared_url,
            title="MAS Payment Services Act",
            category_type="compliance",
            summary="mas payment services",
        )
        art_regulation = _make_sg_article(
            url=shared_url,
            title="MAS Payment Services Act",
            category_type="regulation",
            summary="mas payment services",
        )

        self._configure_session_for_regulatory(
            session,
            generic_articles=[art_generic],
            regulation_articles=[art_regulation],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        seen_urls = [item["url"] for item in result]
        assert seen_urls.count(shared_url) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_limits_output_to_ten_items(self) -> None:
        """The output list is capped at 10 items even when more articles are available."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="maritime")

        # 15 unique generic articles
        many_articles = [
            _make_sg_article(
                url=f"https://example.com/art-{i}",
                title=f"Article {i}",
                category_type="compliance",
            )
            for i in range(15)
        ]

        self._configure_session_for_regulatory(
            session,
            generic_articles=many_articles,
            regulation_articles=[],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        assert len(result) <= 10

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_articles(self) -> None:
        """An empty database returns an empty list without error."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="fintech")

        self._configure_session_for_regulatory(
            session,
            generic_articles=[],
            regulation_articles=[],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        assert result == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_output_shape_contains_required_keys(self) -> None:
        """Each item in the result must contain the expected keys."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="maritime")

        art = _make_sg_article(
            url="https://example.com/mpa-notice",
            title="MPA Port Circular",
            category_type="enforcement",
            summary="Maritime and Port Authority update on vessel registration.",
            source="MPA",
            effective_date="2024-01-15",
        )

        self._configure_session_for_regulatory(
            session,
            generic_articles=[art],
            regulation_articles=[],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        assert len(result) == 1
        item = result[0]
        required_keys = {"title", "category", "source", "summary", "effective_date", "url"}
        assert required_keys.issubset(item.keys())

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_vertical_without_keywords_does_not_make_second_query(self) -> None:
        """A vertical with no _VERTICAL_REGULATORY_KEYWORDS entry triggers only one DB query."""
        session = _make_mock_session()
        # "ict_saas" is not in _VERTICAL_REGULATORY_KEYWORDS, so no second query
        vertical = _make_vertical(slug="ict_saas")

        generic_result = MagicMock()
        generic_result.scalars.return_value.all.return_value = [
            _make_sg_article(url="https://example.com/a", title="SME Grant", category_type="grant")
        ]
        session.execute = AsyncMock(return_value=generic_result)

        synthesizer = self._make_synthesizer(session)
        await synthesizer._build_regulatory_environment(vertical)

        # Only one execute call should have been made
        assert session.execute.call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summary_truncated_to_300_chars(self) -> None:
        """Long summaries are truncated to 300 characters in the output."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="maritime")

        long_summary = "A" * 500
        art = _make_sg_article(
            url="https://example.com/long",
            title="Verbose Regulation",
            category_type="compliance",
            summary=long_summary,
        )

        self._configure_session_for_regulatory(
            session,
            generic_articles=[art],
            regulation_articles=[],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        assert len(result) == 1
        assert len(result[0]["summary"]) == 300

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_summary_returned_as_none(self) -> None:
        """Articles with no summary produce summary: None in the output, not an error."""
        session = _make_mock_session()
        vertical = _make_vertical(slug="maritime")

        art = _make_sg_article(
            url="https://example.com/no-summary",
            title="Brief Notice",
            category_type="grant",
            summary=None,
        )

        self._configure_session_for_regulatory(
            session,
            generic_articles=[art],
            regulation_articles=[],
        )

        synthesizer = self._make_synthesizer(session)
        result = await synthesizer._build_regulatory_environment(vertical)

        assert result[0]["summary"] is None


# ---------------------------------------------------------------------------
# _build_financial_pulse — key name contract
# ---------------------------------------------------------------------------


def _make_vertical_benchmark(
    period_label: str = "2024",
    sga_p50: float | None = 0.32,
    rnd_p50: float | None = 0.18,
    gross_margin_p50: float | None = 0.65,
    operating_margin_p50: float | None = 0.20,
    sga_p75: float | None = 0.45,
    rnd_p75: float | None = 0.28,
    sga_n: int = 12,
    rnd_n: int = 10,
) -> MagicMock:
    """Minimal VerticalBenchmark stand-in for _build_financial_pulse tests."""
    bm = MagicMock()
    bm.period_label = period_label
    bm.sga_to_revenue = {
        "p50": sga_p50,
        "p75": sga_p75,
        "n": sga_n,
    }
    bm.rnd_to_revenue = {
        "p50": rnd_p50,
        "p75": rnd_p75,
        "n": rnd_n,
    }
    bm.gross_margin = {
        "p50": gross_margin_p50,
    }
    # operating_margin is stored as operating_margin_dist attribute on the model
    bm.operating_margin_dist = {
        "p50": operating_margin_p50,
    }
    return bm


class TestBuildFinancialPulse:
    """Verify that _build_financial_pulse returns the correct key names."""

    def _make_synthesizer(self, session: AsyncMock) -> VerticalIntelligenceSynthesizer:
        return VerticalIntelligenceSynthesizer(session=session)

    def _configure_session_for_pulse(
        self, session: AsyncMock, benchmarks: list
    ) -> None:
        """Configure session.execute() to return VerticalBenchmark scalars."""
        result = MagicMock()
        result.scalars.return_value.all.return_value = benchmarks
        session.execute = AsyncMock(return_value=result)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_sga_median_not_sga_to_revenue_median(self) -> None:
        """The dict key must be 'sga_median', NOT 'sga_to_revenue_median'."""
        session = _make_mock_session()
        vertical = _make_vertical()
        bm = _make_vertical_benchmark(sga_p50=0.32)
        self._configure_session_for_pulse(session, [bm])

        synthesizer = self._make_synthesizer(session)
        pulse = await synthesizer._build_financial_pulse(vertical)

        assert "sga_median" in pulse
        assert "sga_to_revenue_median" not in pulse

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_rnd_median_not_rnd_to_revenue_median(self) -> None:
        """The dict key must be 'rnd_median', NOT 'rnd_to_revenue_median'."""
        session = _make_mock_session()
        vertical = _make_vertical()
        bm = _make_vertical_benchmark(rnd_p50=0.18)
        self._configure_session_for_pulse(session, [bm])

        synthesizer = self._make_synthesizer(session)
        pulse = await synthesizer._build_financial_pulse(vertical)

        assert "rnd_median" in pulse
        assert "rnd_to_revenue_median" not in pulse

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_gross_margin_median_and_operating_margin_median(self) -> None:
        """Both 'gross_margin_median' and 'operating_margin_median' must be present."""
        session = _make_mock_session()
        vertical = _make_vertical()
        bm = _make_vertical_benchmark(gross_margin_p50=0.65, operating_margin_p50=0.20)
        self._configure_session_for_pulse(session, [bm])

        synthesizer = self._make_synthesizer(session)
        pulse = await synthesizer._build_financial_pulse(vertical)

        assert "gross_margin_median" in pulse
        assert "operating_margin_median" in pulse

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sga_median_value_equals_p50(self) -> None:
        """'sga_median' must carry the p50 value from the benchmark distribution."""
        session = _make_mock_session()
        vertical = _make_vertical()
        bm = _make_vertical_benchmark(sga_p50=0.37)
        self._configure_session_for_pulse(session, [bm])

        synthesizer = self._make_synthesizer(session)
        pulse = await synthesizer._build_financial_pulse(vertical)

        assert pulse["sga_median"] == pytest.approx(0.37)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rnd_median_value_equals_p50(self) -> None:
        """'rnd_median' must carry the p50 value from the benchmark distribution."""
        session = _make_mock_session()
        vertical = _make_vertical()
        bm = _make_vertical_benchmark(rnd_p50=0.21)
        self._configure_session_for_pulse(session, [bm])

        synthesizer = self._make_synthesizer(session)
        pulse = await synthesizer._build_financial_pulse(vertical)

        assert pulse["rnd_median"] == pytest.approx(0.21)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_benchmarks_returns_empty_dict(self) -> None:
        """When no benchmarks exist, _build_financial_pulse must return {}."""
        session = _make_mock_session()
        vertical = _make_vertical()
        self._configure_session_for_pulse(session, [])

        synthesizer = self._make_synthesizer(session)
        pulse = await synthesizer._build_financial_pulse(vertical)

        assert pulse == {}
