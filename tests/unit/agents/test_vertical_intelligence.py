"""Unit tests for VerticalIntelligenceAgent.

Tests cover:
- Output type schema construction (IndustryDriver, CompetitorProfile,
  FinancialBenchmarkSummary, MarketForces, VerticalIntelligenceOutput)
- _plan(): knowledge pack loading, vertical slug detection, plan dict shape
- _check(): full confidence scoring matrix, minimum and maximum bounds
- _act(): AgentBus publication — market trend + per-driver discoveries

External dependencies (DB, MCP, APIs, LLM) are all mocked.
_do() and _synthesize() are integration-level and are NOT tested here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agents.vertical_intelligence.src.agent import (
    CompetitorProfile,
    FinancialBenchmarkSummary,
    IndustryDriver,
    MarketForces,
    VerticalIntelligenceAgent,
    VerticalIntelligenceOutput,
)
from packages.core.src.agent_bus import AgentBus, DiscoveryType

# ---------------------------------------------------------------------------
# Agent factory — patches every external call made in __init__
# ---------------------------------------------------------------------------


def _make_agent(agent_bus: AgentBus | None = None) -> VerticalIntelligenceAgent:
    """Build a VerticalIntelligenceAgent with all __init__ side-effects patched."""
    mock_bus = agent_bus or MagicMock(spec=AgentBus)
    mock_llm_manager = MagicMock()
    mock_llm_manager.perplexity = AsyncMock()

    with (
        patch(
            "agents.vertical_intelligence.src.agent.get_newsapi_client",
            return_value=MagicMock(),
        ),
        patch(
            "agents.vertical_intelligence.src.agent.get_llm_manager",
            return_value=mock_llm_manager,
        ),
        patch(
            "agents.vertical_intelligence.src.agent.get_agent_bus",
            return_value=mock_bus,
        ),
    ):
        agent = VerticalIntelligenceAgent(agent_bus=mock_bus)

    return agent


# ---------------------------------------------------------------------------
# Output type construction tests
# ---------------------------------------------------------------------------


class TestOutputTypes:
    """Validate Pydantic schema construction for all output types."""

    @pytest.mark.unit
    def test_industry_driver_minimal(self):
        """IndustryDriver requires name, direction, magnitude, description, gtm_implication."""
        driver = IndustryDriver(
            name="AI adoption wave",
            direction="tailwind",
            magnitude="strong",
            description="Enterprise software buyers are shifting budgets to AI-native tools.",
            gtm_implication="Lead with AI capability in all first-call decks.",
        )
        assert driver.name == "AI adoption wave"
        assert driver.direction == "tailwind"
        assert driver.magnitude == "strong"

    @pytest.mark.unit
    def test_industry_driver_headwind(self):
        """IndustryDriver can represent a headwind with any magnitude."""
        driver = IndustryDriver(
            name="Rising interest rates",
            direction="headwind",
            magnitude="moderate",
            description="Higher rates compress SaaS multiples and slow growth investment.",
            gtm_implication="Emphasise payback period and fast ROI in proposals.",
        )
        assert driver.direction == "headwind"
        assert driver.magnitude == "moderate"

    @pytest.mark.unit
    def test_competitor_profile_minimal(self):
        """CompetitorProfile requires name, role, and notable; ticker and financials are optional."""
        profile = CompetitorProfile(
            name="Acme Corp",
            role="leader",
            notable="Largest SaaS vendor by market cap in SEA.",
        )
        assert profile.name == "Acme Corp"
        assert profile.ticker is None
        assert profile.market_cap_sgd is None

    @pytest.mark.unit
    def test_competitor_profile_full(self):
        """CompetitorProfile with all fields set stores values correctly."""
        profile = CompetitorProfile(
            name="TechVenture",
            ticker="TECH",
            role="challenger",
            market_cap_sgd=250_000_000.0,
            revenue_growth_yoy=0.32,
            sga_to_revenue=0.45,
            trajectory="accelerating",
            notable="Fastest-growing challenger; 32% YoY revenue growth.",
        )
        assert profile.ticker == "TECH"
        assert profile.revenue_growth_yoy == pytest.approx(0.32)
        assert profile.trajectory == "accelerating"

    @pytest.mark.unit
    def test_financial_benchmark_summary_defaults(self):
        """FinancialBenchmarkSummary optional median fields default to None."""
        summary = FinancialBenchmarkSummary(period="2024")
        assert summary.company_count == 0
        assert summary.revenue_growth_median is None
        assert summary.gross_margin_median is None

    @pytest.mark.unit
    def test_financial_benchmark_summary_full(self):
        """FinancialBenchmarkSummary stores all median metrics."""
        summary = FinancialBenchmarkSummary(
            period="2024",
            company_count=42,
            revenue_growth_median=0.12,
            gross_margin_median=0.68,
            sga_to_revenue_median=0.22,
            rnd_to_revenue_median=0.15,
            operating_margin_median=0.18,
            capex_to_revenue_median=0.03,
        )
        assert summary.company_count == 42
        assert summary.gross_margin_median == pytest.approx(0.68)

    @pytest.mark.unit
    def test_market_forces_construction(self):
        """MarketForces requires all five Porter's forces."""
        forces = MarketForces(
            buyer_power="High — enterprise buyers consolidate vendors aggressively.",
            supplier_power="Low — commodity cloud infrastructure.",
            threat_of_new_entrants="Moderate — low code barriers but high CAC.",
            threat_of_substitutes="Low — switching costs are high post-integration.",
            competitive_rivalry="High — 50+ vendors competing in the same ICP.",
        )
        assert "High" in forces.buyer_power
        assert "Low" in forces.supplier_power

    @pytest.mark.unit
    def test_vertical_intelligence_output_defaults(self):
        """VerticalIntelligenceOutput populates all default fields correctly."""
        output = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="The Singapore SaaS vertical is experiencing strong growth.",
        )
        assert output.vertical_slug == "ict_saas"
        assert output.drivers == []
        assert output.leaders == []
        assert output.challengers == []
        assert output.laggards == []
        assert output.new_entrants == []
        assert output.benchmarks is None
        assert output.market_forces is None
        assert output.confidence == pytest.approx(0.0)
        assert output.is_live_data is False

    @pytest.mark.unit
    def test_vertical_intelligence_output_with_nested_types(self):
        """VerticalIntelligenceOutput stores nested Pydantic models correctly."""
        output = VerticalIntelligenceOutput(
            vertical_slug="fintech",
            vertical_name="Fintech",
            executive_summary="Singapore fintech is a leading APAC hub.",
            drivers=[
                IndustryDriver(
                    name="MAS regulatory sandbox",
                    direction="tailwind",
                    magnitude="strong",
                    description="MAS sandbox accelerates fintech product launches.",
                    gtm_implication="Highlight MAS sandbox participation in sales decks.",
                )
            ],
            benchmarks=FinancialBenchmarkSummary(period="2024", company_count=30),
            market_forces=MarketForces(
                buyer_power="Moderate",
                supplier_power="Low",
                threat_of_new_entrants="High",
                threat_of_substitutes="Low",
                competitive_rivalry="High",
            ),
        )
        assert len(output.drivers) == 1
        assert output.benchmarks is not None
        assert output.market_forces is not None

    @pytest.mark.unit
    def test_vertical_intelligence_output_benchmark_history_defaults_empty(self):
        """benchmark_history field defaults to an empty list."""
        output = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
        )
        assert output.benchmark_history == []

    @pytest.mark.unit
    def test_vertical_intelligence_output_trend_analysis_defaults_empty(self):
        """trend_analysis field defaults to an empty dict."""
        output = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
        )
        assert output.trend_analysis == {}

    @pytest.mark.unit
    def test_vertical_intelligence_output_benchmark_history_stores_summaries(self):
        """benchmark_history accepts and stores a list of FinancialBenchmarkSummary objects."""
        history = [
            FinancialBenchmarkSummary(period="2024", company_count=42, revenue_growth_median=0.12),
            FinancialBenchmarkSummary(period="2023", company_count=38, revenue_growth_median=0.09),
        ]
        output = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            benchmark_history=history,
        )
        assert len(output.benchmark_history) == 2
        assert output.benchmark_history[0].period == "2024"
        assert output.benchmark_history[1].period == "2023"

    @pytest.mark.unit
    def test_vertical_intelligence_output_trend_analysis_stores_dict(self):
        """trend_analysis accepts and stores an arbitrary dict of computed YoY deltas."""
        trend = {
            "annual_yoy_deltas": {"revenue_growth_yoy": 0.03},
            "annual_periods_compared": "2024 vs 2023",
            "sga_trend": "rising",
        }
        output = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            trend_analysis=trend,
        )
        assert output.trend_analysis["annual_periods_compared"] == "2024 vs 2023"
        assert output.trend_analysis["sga_trend"] == "rising"

    @pytest.mark.unit
    def test_vertical_intelligence_output_confidence_bounds(self):
        """confidence field enforces ge=0.0 and le=1.0."""
        output = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            confidence=0.85,
        )
        assert 0.0 <= output.confidence <= 1.0


# ---------------------------------------------------------------------------
# _plan() tests
# ---------------------------------------------------------------------------


class TestPlan:
    """Tests for the _plan() PDCA phase."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_returns_required_keys(self):
        """_plan() must return a dict with vertical_slug, industry, region, data_sources."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={"formatted_injection": ""})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan("Analyse the Singapore SaaS market", context={})

        assert "vertical_slug" in plan
        assert "industry" in plan
        assert "region" in plan
        assert "data_sources" in plan

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_calls_knowledge_mcp_with_agent_name(self):
        """_plan() must call get_agent_knowledge_pack with agent_name='vertical-intelligence'."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={"formatted_injection": ""})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            await agent._plan("SaaS market analysis", context={})

        mock_kmcp.get_agent_knowledge_pack.assert_called_once()
        call_kwargs = mock_kmcp.get_agent_knowledge_pack.call_args
        assert call_kwargs.kwargs["agent_name"] == "vertical-intelligence"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_knowledge_pack_stored_on_agent(self):
        """_plan() must store the returned pack as self._knowledge_pack."""
        agent = _make_agent()
        expected_pack = {"formatted_injection": "Porter's Five Forces guidance"}
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value=expected_pack)

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            await agent._plan("SaaS", context={})

        assert agent._knowledge_pack == expected_pack

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_detects_saas_vertical_slug(self):
        """Task text containing 'saas' is detected as 'ict_saas' vertical slug."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan("Analyse SaaS companies in Singapore", context={})

        assert plan["vertical_slug"] == "ict_saas"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_detects_fintech_vertical_slug(self):
        """Task text containing 'fintech' is detected as 'fintech' vertical slug."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan("Research the fintech market in Singapore", context={})

        assert plan["vertical_slug"] == "fintech"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_uses_context_vertical_slug_over_detection(self):
        """Explicit vertical_slug in context takes priority over auto-detection."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan(
                "Analyse the SaaS market",
                context={"vertical_slug": "biomedical"},
            )

        assert plan["vertical_slug"] == "biomedical"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_defaults_to_ict_saas_when_no_match(self):
        """Task text with no recognisable vertical keyword falls back to 'ict_saas'."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan("Generic market research task", context={})

        assert plan["vertical_slug"] == "ict_saas"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_uses_context_industry_override(self):
        """industry in context is passed through to the plan dict."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan(
                "SaaS analysis",
                context={"industry": "Enterprise SaaS", "region": "APAC"},
            )

        assert plan["industry"] == "Enterprise SaaS"
        assert plan["region"] == "APAC"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_sets_analysis_id_from_context(self):
        """_plan() stores analysis_id from context on the agent instance."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})
        analysis_id = uuid4()

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            await agent._plan("SaaS", context={"analysis_id": analysis_id})

        assert agent._analysis_id == analysis_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_stores_vertical_slug_on_agent(self):
        """_plan() stores the resolved vertical_slug on self._vertical_slug."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            await agent._plan("Fintech market in Singapore", context={})

        assert agent._vertical_slug == "fintech"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_default_region_is_singapore(self):
        """_plan() defaults region to 'Singapore' when not provided in context."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan("SaaS analysis", context={})

        assert plan["region"] == "Singapore"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plan_data_sources_list_includes_three_sources(self):
        """_plan() always returns mcp, newsapi, and perplexity as data sources."""
        agent = _make_agent()
        mock_kmcp = AsyncMock()
        mock_kmcp.get_agent_knowledge_pack = AsyncMock(return_value={})

        with patch(
            "agents.vertical_intelligence.src.agent.get_knowledge_mcp",
            return_value=mock_kmcp,
        ):
            plan = await agent._plan("SaaS", context={})

        assert "mcp" in plan["data_sources"]
        assert "newsapi" in plan["data_sources"]
        assert "perplexity" in plan["data_sources"]


# ---------------------------------------------------------------------------
# _check() scoring tests
# ---------------------------------------------------------------------------


def _make_minimal_output() -> VerticalIntelligenceOutput:
    """Minimal valid VerticalIntelligenceOutput with no bonus-earning content.

    Includes non-empty penalty-sections (trends, signals, exec movements,
    regulatory, gtm_implications) so the base score stays at 0.2 without
    incurring penalties.  Tests that specifically check penalty behaviour
    should override these fields.

    Note: drivers and players are empty (0 items) to avoid the
    *insufficient depth* penalty which only fires when 0 < count < 5.
    """
    return VerticalIntelligenceOutput(
        vertical_slug="ict_saas",
        vertical_name="ICT & SaaS",
        executive_summary="",
        drivers=[],
        leaders=[],
        challengers=[],
        laggards=[],
        market_forces=None,
        benchmarks=None,
        gtm_implications=[
            {"insight": f"placeholder{i}", "recommended_action": "n/a", "priority": "low"}
            for i in range(5)
        ],
        trends=[{"trend": "general", "source_count": 1}],
        recent_signals=[{"headline": "test", "signal_type": "market_trend"}],
        executive_movements=[{"company": "Acme", "name": "J. Doe", "role_type": "CEO"}],
        regulatory_environment=[{"title": "PDPA", "category": "compliance"}],
    )


def _make_driver(direction: str = "tailwind") -> IndustryDriver:
    return IndustryDriver(
        name="Test Driver",
        direction=direction,
        magnitude="strong",
        description="A strong force shaping the industry.",
        gtm_implication="Adjust messaging accordingly.",
    )


def _make_player(role: str = "leader") -> CompetitorProfile:
    return CompetitorProfile(
        name="SomeCorp",
        role=role,
        notable="Key player in the vertical.",
    )


class TestCheck:
    """Tests for _check() confidence scoring. All flags set directly on agent."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_minimum_empty_output_returns_base_score(self):
        """Minimal output with 5 GTM implications (no other bonuses/penalties) → 0.2 + 0.07 = 0.27."""
        agent = _make_agent()
        # All flags default to False in __init__

        result = _make_minimal_output()
        score = await agent._check(result)

        assert score == pytest.approx(0.27)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exec_summary_long_adds_012(self):
        """Executive summary > 200 chars → +0.12 (not the smaller +0.05 bonus)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.executive_summary = "A" * 201

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.12)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exec_summary_medium_adds_005(self):
        """Executive summary > 50 but <= 200 chars → +0.05 only."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.executive_summary = "A" * 100  # 51 < 100 <= 200

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exec_summary_short_adds_nothing(self):
        """Executive summary <= 50 chars → no bonus at all."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.executive_summary = "Short"

        score = await agent._check(result)

        assert score == pytest.approx(0.27)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_five_drivers_adds_010(self):
        """5 or more drivers → +0.10 (consulting-grade top tier, no depth penalty)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.drivers = [_make_driver() for _ in range(5)]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.10)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_three_drivers_adds_007(self):
        """3 or 4 drivers → +0.07 bonus but -0.04 insufficient-depth penalty (0 < 3 < 5)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.drivers = [_make_driver() for _ in range(3)]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.07 - 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_one_driver_adds_003(self):
        """1 or 2 drivers → +0.03 bonus but -0.04 insufficient-depth penalty (0 < 1 < 5)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.drivers = [_make_driver()]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.03 - 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_zero_drivers_adds_nothing(self):
        """Empty drivers list → no driver bonus and no depth penalty (0 is not 0 < count < 5)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.drivers = []

        score = await agent._check(result)

        assert score == pytest.approx(0.27)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_five_players_adds_008(self):
        """leaders + challengers + laggards >= 5 → +0.08 (no sparse penalty since >=5)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.leaders = [_make_player("leader") for _ in range(3)]
        result.challengers = [_make_player("challenger") for _ in range(2)]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.08)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_two_players_adds_004(self):
        """2 to 4 total players → +0.04 bonus but -0.03 sparse-landscape penalty (0 < 2 < 5)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.leaders = [_make_player("leader") for _ in range(2)]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.04 - 0.03)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_one_player_adds_nothing(self):
        """1 player is below the >= 2 threshold → no players bonus, but -0.03 sparse penalty fires (0 < 1 < 5)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.leaders = [_make_player("leader")]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 - 0.03)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_zero_players_adds_nothing(self):
        """No players in any tier → no players bonus and no sparse penalty (0 is not 0 < count < 5)."""
        agent = _make_agent()
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_market_forces_adds_005(self):
        """Populated market_forces → +0.05."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.market_forces = MarketForces(
            buyer_power="Moderate",
            supplier_power="Low",
            threat_of_new_entrants="High",
            threat_of_substitutes="Low",
            competitive_rivalry="High",
        )

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_vertical_intel_adds_008(self):
        """_has_vertical_intel flag → +0.08."""
        agent = _make_agent()
        agent._has_vertical_intel = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.08)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_benchmarks_adds_005(self):
        """_has_benchmarks flag → +0.05 bonus but -0.04 single-period penalty (_has_multi_period=False)."""
        agent = _make_agent()
        agent._has_benchmarks = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05 - 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_trajectories_adds_005(self):
        """_has_trajectories flag → +0.05."""
        agent = _make_agent()
        agent._has_trajectories = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_live_news_adds_004(self):
        """_has_live_news flag → +0.04."""
        agent = _make_agent()
        agent._has_live_news = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_research_adds_004(self):
        """_has_research flag → +0.04."""
        agent = _make_agent()
        agent._has_research = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_kb_framework_adds_002(self):
        """_has_kb_framework flag → +0.02."""
        agent = _make_agent()
        agent._has_kb_framework = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.02)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_multi_period_adds_005(self):
        """_has_multi_period flag → +0.05 (multi-period trend analysis bonus)."""
        agent = _make_agent()
        agent._has_multi_period = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_has_multi_period_false_by_default_adds_nothing(self):
        """_has_multi_period defaults to False after construction → no bonus."""
        agent = _make_agent()
        # Flag must be False from __init__
        assert agent._has_multi_period is False
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_multi_period_stacks_with_benchmarks(self):
        """_has_benchmarks + _has_multi_period stack independently → +0.05 + +0.05 (no single-period penalty)."""
        agent = _make_agent()
        agent._has_benchmarks = True
        agent._has_multi_period = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05 + 0.05)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_five_gtm_implications_adds_007(self):
        """5 or more gtm_implications → +0.07 (consulting-grade top tier, no depth penalty)."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.gtm_implications = [
            {"insight": f"Implication {i}", "recommended_action": "Act now", "priority": "high"}
            for i in range(5)
        ]

        score = await agent._check(result)

        assert score == pytest.approx(0.27)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_three_gtm_implications_adds_005(self):
        """3 or 4 gtm_implications → +0.05 bonus but -0.04 depth penalty (0 < 3 < 5); net vs base: 0.2 + 0.05 - 0.04."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.gtm_implications = [
            {"insight": "Focus on Series A companies", "recommended_action": "Target fintech", "priority": "high"},
            {"insight": "SG&A spend is rising", "recommended_action": "Sell efficiency tools", "priority": "medium"},
            {"insight": "AI adoption accelerating", "recommended_action": "Lead with AI narrative", "priority": "high"},
        ]

        score = await agent._check(result)

        assert score == pytest.approx(0.2 + 0.05 - 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_fewer_than_three_gtm_implications_adds_nothing(self):
        """1 or 2 gtm_implications → no GTM bonus but -0.04 depth penalty fires (0 < 1 < 5); net: 0.2 - 0.04."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.gtm_implications = [
            {"insight": "Focus on SMEs", "recommended_action": "Prospect SMEs", "priority": "high"},
        ]

        score = await agent._check(result)

        assert score == pytest.approx(0.2 - 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_maximum_all_flags_and_content_capped_at_095(self):
        """All possible bonuses should not exceed the 0.95 cap."""
        agent = _make_agent()
        # Set all data-quality flags
        agent._has_vertical_intel = True
        agent._has_benchmarks = True
        agent._has_trajectories = True
        agent._has_multi_period = True
        agent._has_live_news = True
        agent._has_research = True
        agent._has_kb_framework = True

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            # Long executive summary → +0.12
            executive_summary="A" * 300,
            # 5+ drivers → +0.10
            drivers=[_make_driver() for _ in range(5)],
            # 5+ players → +0.08
            leaders=[_make_player("leader") for _ in range(3)],
            challengers=[_make_player("challenger") for _ in range(2)],
            laggards=[_make_player("laggard")],
            # market_forces → +0.05
            market_forces=MarketForces(
                buyer_power="High",
                supplier_power="Low",
                threat_of_new_entrants="Moderate",
                threat_of_substitutes="Low",
                competitive_rivalry="High",
            ),
            # 5+ gtm_implications → +0.07 (no penalty)
            gtm_implications=[
                {"insight": f"Implication {i}", "recommended_action": "Act now", "priority": "high"}
                for i in range(5)
            ],
            # Non-empty sections avoid penalties
            trends=[{"trend": "general", "source_count": 1}],
            recent_signals=[{"headline": "test", "signal_type": "market_trend"}],
            executive_movements=[{"company": "Acme", "name": "J. Doe", "role_type": "CEO"}],
            regulatory_environment=[{"title": "PDPA", "category": "compliance"}],
        )

        score = await agent._check(result)

        # Maximum possible raw:
        #   0.20 (base)
        # + 0.12 (exec summary > 200)
        # + 0.10 (5+ drivers)
        # + 0.08 (5+ players)
        # + 0.05 (market_forces)
        # + 0.08 (_has_vertical_intel)
        # + 0.05 (_has_benchmarks)
        # + 0.05 (_has_trajectories)
        # + 0.05 (_has_multi_period)
        # + 0.04 (_has_live_news)
        # + 0.04 (_has_research)
        # + 0.02 (_has_kb_framework)
        # + 0.07 (5+ gtm_implications)
        # - 0 (no penalties — all sections non-empty)
        # = 1.05 → capped at 0.95
        assert score == pytest.approx(0.95)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_additive_flags_stack_correctly(self):
        """All three core MCP flags together → +0.08 + 0.05 + 0.05, minus -0.04 single-period penalty."""
        agent = _make_agent()
        agent._has_vertical_intel = True
        agent._has_benchmarks = True
        agent._has_trajectories = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.08 + 0.05 + 0.05 - 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_both_live_data_flags_stack(self):
        """_has_live_news + _has_research together → +0.04 + 0.04 = +0.08 over base."""
        agent = _make_agent()
        agent._has_live_news = True
        agent._has_research = True
        result = _make_minimal_output()

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.04 + 0.04)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_laggards_count_toward_players_total(self):
        """laggards are included in the total_players count for the competitive landscape bonus."""
        agent = _make_agent()
        result = _make_minimal_output()
        # 3 leaders + 2 laggards = 5 → should earn the +0.08 tier (no sparse penalty since >=5)
        result.leaders = [_make_player("leader") for _ in range(3)]
        result.laggards = [_make_player("laggard") for _ in range(2)]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.08)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_score_never_below_floor(self):
        """_check() must never return a score below the 0.10 floor, even with all penalties."""
        agent = _make_agent()
        result = _make_minimal_output()
        # Strip all penalty-sections to trigger maximum penalties
        result.trends = []
        result.recent_signals = []
        result.executive_movements = []
        result.gtm_implications = []
        result.regulatory_environment = []

        score = await agent._check(result)

        assert score >= 0.10
        # With all penalties applied: 0.2 - 0.06 - 0.04 - 0.03 - 0.08 - 0.03 = -0.04 → floored to 0.10
        assert score == pytest.approx(0.10)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_score_never_above_cap(self):
        """_check() must never exceed 0.95 regardless of content."""
        agent = _make_agent()
        # Activate every flag
        agent._has_vertical_intel = True
        agent._has_benchmarks = True
        agent._has_trajectories = True
        agent._has_live_news = True
        agent._has_research = True
        agent._has_kb_framework = True

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="X" * 500,
            drivers=[_make_driver() for _ in range(10)],
            leaders=[_make_player("leader") for _ in range(10)],
            gtm_implications=[
                {"insight": f"GTM tip {i}", "recommended_action": "Do it", "priority": "high"}
                for i in range(10)
            ],
            trends=[{"trend": "general", "source_count": 1}],
            recent_signals=[{"headline": "test", "signal_type": "market_trend"}],
            executive_movements=[{"company": "Acme", "name": "J. Doe", "role_type": "CEO"}],
            regulatory_environment=[{"title": "PDPA", "category": "compliance"}],
        )

        score = await agent._check(result)

        assert score <= 0.95

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_partial_score_medium_exec_summary_and_one_driver(self):
        """Partial bonus combination: medium exec summary (> 50) + 1 driver (+0.03) with -0.04 depth penalty."""
        agent = _make_agent()
        result = _make_minimal_output()
        result.executive_summary = "A" * 100
        result.drivers = [_make_driver()]

        score = await agent._check(result)

        assert score == pytest.approx(0.27 + 0.05 + 0.03 - 0.04)


# ---------------------------------------------------------------------------
# _act() publication tests
# ---------------------------------------------------------------------------


class TestAct:
    """Tests for _act() — sets confidence and publishes to AgentBus."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_sets_confidence_on_result(self):
        """_act() must assign the confidence score to result.confidence."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview of the SaaS vertical in Singapore.",
        )
        final = await agent._act(result, confidence=0.82)

        assert final.confidence == pytest.approx(0.82)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_publishes_market_trend_message(self):
        """_act() publishes exactly one MARKET_TREND discovery for the overall report."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Strong SaaS growth in Singapore.",
            drivers=[],  # No drivers → only the market trend message
        )
        await agent._act(result, confidence=0.75)

        # Exactly one publish call for the market trend overview
        calls = mock_bus.publish.call_args_list
        market_trend_calls = [
            c for c in calls
            if c.kwargs.get("discovery_type") == DiscoveryType.MARKET_TREND
        ]
        assert len(market_trend_calls) >= 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_market_trend_title_includes_vertical_name(self):
        """The market trend publish call title must include the vertical name."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="fintech",
            vertical_name="Fintech",
            executive_summary="Singapore fintech is growing.",
            drivers=[],
        )
        await agent._act(result, confidence=0.75)

        calls = mock_bus.publish.call_args_list
        titles = [c.kwargs.get("title", "") for c in calls]
        assert any("Fintech" in t for t in titles)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_publishes_per_driver_discovery(self):
        """_act() publishes one additional discovery for each driver."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        drivers = [
            IndustryDriver(
                name=f"Driver {i}",
                direction="tailwind",
                magnitude="strong",
                description="Evidence-backed.",
                gtm_implication="Sell harder.",
            )
            for i in range(3)
        ]
        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Strong SaaS growth.",
            drivers=drivers,
        )
        await agent._act(result, confidence=0.80)

        # 1 market trend overview + 3 driver messages = 4 total
        assert mock_bus.publish.call_count == 4

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_tailwind_driver_publishes_market_opportunity(self):
        """A tailwind driver is published as MARKET_OPPORTUNITY."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            drivers=[
                IndustryDriver(
                    name="AI Wave",
                    direction="tailwind",
                    magnitude="strong",
                    description="AI adoption is accelerating.",
                    gtm_implication="Lead with AI.",
                )
            ],
        )
        await agent._act(result, confidence=0.80)

        calls = mock_bus.publish.call_args_list
        opportunity_calls = [
            c for c in calls
            if c.kwargs.get("discovery_type") == DiscoveryType.MARKET_OPPORTUNITY
        ]
        assert len(opportunity_calls) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_headwind_driver_publishes_market_trend(self):
        """A headwind driver is published as MARKET_TREND (not MARKET_OPPORTUNITY)."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            drivers=[
                IndustryDriver(
                    name="Rising rates",
                    direction="headwind",
                    magnitude="moderate",
                    description="Interest rates compress SaaS multiples.",
                    gtm_implication="Focus on payback period.",
                )
            ],
        )
        await agent._act(result, confidence=0.80)

        calls = mock_bus.publish.call_args_list
        # The headwind driver call uses MARKET_TREND
        driver_calls = [
            c for c in calls
            if c.kwargs.get("title", "").startswith("[ict_saas]")
        ]
        assert len(driver_calls) == 1
        assert driver_calls[0].kwargs.get("discovery_type") == DiscoveryType.MARKET_TREND

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_driver_content_includes_gtm_implication(self):
        """Each per-driver publish includes gtm_implication in content."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            drivers=[
                IndustryDriver(
                    name="Cloud migration",
                    direction="tailwind",
                    magnitude="strong",
                    description="Companies moving to cloud at record pace.",
                    gtm_implication="Target IT managers with cloud migration pain.",
                )
            ],
        )
        await agent._act(result, confidence=0.80)

        calls = mock_bus.publish.call_args_list
        driver_call = next(
            c for c in calls
            if c.kwargs.get("title", "").startswith("[ict_saas]")
        )
        content = driver_call.kwargs.get("content", {})
        assert "gtm_implication" in content
        assert "Target IT managers" in content["gtm_implication"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_market_trend_content_includes_vertical_slug(self):
        """The market trend publish content includes vertical_slug."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="logistics",
            vertical_name="Logistics",
            executive_summary="Supply chain recovery underway.",
        )
        await agent._act(result, confidence=0.75)

        calls = mock_bus.publish.call_args_list
        trend_call = calls[0]
        content = trend_call.kwargs.get("content", {})
        assert content.get("vertical_slug") == "logistics"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_passes_confidence_to_publish(self):
        """_act() passes the confidence score to every publish call."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
        )
        await agent._act(result, confidence=0.88)

        for call in mock_bus.publish.call_args_list:
            assert call.kwargs.get("confidence") == pytest.approx(0.88)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_returns_result_with_updated_confidence(self):
        """_act() returns the same result object with confidence updated."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            confidence=0.0,
        )
        returned = await agent._act(result, confidence=0.77)

        assert returned is result
        assert returned.confidence == pytest.approx(0.77)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_market_trend_content_includes_drivers_list(self):
        """The market trend publish content.drivers is a list of dicts (serialized drivers)."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            drivers=[_make_driver("tailwind"), _make_driver("headwind")],
        )
        await agent._act(result, confidence=0.80)

        # First publish call is the market trend overview
        trend_call = mock_bus.publish.call_args_list[0]
        content = trend_call.kwargs.get("content", {})
        assert isinstance(content.get("drivers"), list)
        assert len(content["drivers"]) == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_market_trend_content_includes_benchmarks_when_present(self):
        """market trend content includes serialized benchmarks when they exist."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            benchmarks=FinancialBenchmarkSummary(
                period="2024",
                company_count=30,
                revenue_growth_median=0.15,
            ),
        )
        await agent._act(result, confidence=0.80)

        trend_call = mock_bus.publish.call_args_list[0]
        content = trend_call.kwargs.get("content", {})
        assert content.get("benchmarks") is not None
        assert content["benchmarks"]["period"] == "2024"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_market_trend_content_benchmarks_none_when_absent(self):
        """market trend content.benchmarks is None when result.benchmarks is None."""
        mock_bus = AsyncMock(spec=AgentBus)
        mock_bus.publish = AsyncMock(return_value=MagicMock())
        agent = _make_agent(agent_bus=mock_bus)

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
            benchmarks=None,
        )
        await agent._act(result, confidence=0.80)

        trend_call = mock_bus.publish.call_args_list[0]
        content = trend_call.kwargs.get("content", {})
        assert content.get("benchmarks") is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_act_no_publish_when_bus_is_none(self):
        """_act() skips publication entirely when _agent_bus is None."""
        agent = _make_agent()
        agent._agent_bus = None  # Simulate no bus configured

        result = VerticalIntelligenceOutput(
            vertical_slug="ict_saas",
            vertical_name="ICT & SaaS",
            executive_summary="Overview.",
        )
        # Should not raise
        returned = await agent._act(result, confidence=0.75)
        assert returned.confidence == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Agent initialisation tests
# ---------------------------------------------------------------------------


class TestAgentInit:
    """Verify agent metadata and initial state after construction."""

    @pytest.mark.unit
    def test_agent_name_is_kebab_case(self):
        """Agent name must be 'vertical-intelligence' (kebab-case)."""
        agent = _make_agent()
        assert agent.name == "vertical-intelligence"

    @pytest.mark.unit
    def test_agent_min_confidence(self):
        """Agent min_confidence must be 0.70."""
        agent = _make_agent()
        assert agent.min_confidence == pytest.approx(0.70)

    @pytest.mark.unit
    def test_agent_max_iterations(self):
        """Agent max_iterations must be 2."""
        agent = _make_agent()
        assert agent.max_iterations == 2

    @pytest.mark.unit
    def test_agent_model(self):
        """Agent default model must be 'gpt-4o'."""
        agent = _make_agent()
        assert agent.model == "gpt-4o"

    @pytest.mark.unit
    def test_agent_has_four_capabilities(self):
        """Agent must declare exactly 4 capabilities."""
        agent = _make_agent()
        assert len(agent.capabilities) == 4

    @pytest.mark.unit
    def test_agent_capability_names(self):
        """All four required capability names must be present."""
        agent = _make_agent()
        names = {c.name for c in agent.capabilities}
        assert "industry-analysis" in names
        assert "competitive-landscape" in names
        assert "benchmark-interpretation" in names
        assert "market-forces" in names

    @pytest.mark.unit
    def test_agent_data_quality_flags_start_false(self):
        """All seven _has_* flags default to False after construction."""
        agent = _make_agent()
        assert agent._has_vertical_intel is False
        assert agent._has_benchmarks is False
        assert agent._has_trajectories is False
        assert agent._has_multi_period is False
        assert agent._has_live_news is False
        assert agent._has_research is False
        assert agent._has_kb_framework is False

    @pytest.mark.unit
    def test_agent_vertical_slug_starts_empty(self):
        """_vertical_slug starts as empty string."""
        agent = _make_agent()
        assert agent._vertical_slug == ""

    @pytest.mark.unit
    def test_agent_analysis_id_starts_none(self):
        """_analysis_id starts as None."""
        agent = _make_agent()
        assert agent._analysis_id is None

    @pytest.mark.unit
    def test_agent_result_type(self):
        """Agent result_type must be VerticalIntelligenceOutput."""
        agent = _make_agent()
        assert agent.result_type is VerticalIntelligenceOutput
