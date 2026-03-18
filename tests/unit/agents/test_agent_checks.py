"""Unit tests for _check() confidence scoring and pure logic across 5 agents.

Tests are pure unit tests — no network calls, no DB, no LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# CompetitorAnalystAgent
# ---------------------------------------------------------------------------
from agents.competitor_analyst.src.agent import (
    CompetitivePositioning,
    CompetitorAnalystAgent,
    CompetitorIntelOutput,
)

# ---------------------------------------------------------------------------
# CustomerProfilerAgent
# ---------------------------------------------------------------------------
from agents.customer_profiler.src.agent import (
    CustomerProfileOutput,
    CustomerProfilerAgent,
    ICPDefinition,
)

# ---------------------------------------------------------------------------
# GTMStrategistAgent
# ---------------------------------------------------------------------------
from agents.gtm_strategist.src.agent import (
    AgentTask,
    GTMStrategistAgent,
    GTMStrategyOutput,
    MarketSizing,
    SalesMotion,
    StrategicRecommendation,
    UserRequirements,
    WorkDistribution,
)

# ---------------------------------------------------------------------------
# LeadHunterAgent
# ---------------------------------------------------------------------------
from agents.lead_hunter.src.agent import (
    LeadHunterAgent,
    LeadHuntingOutput,
    LeadScoringCriteria,
    ProspectCompany,
    _guess_domain,
)

# ---------------------------------------------------------------------------
# SignalMonitorAgent
# ---------------------------------------------------------------------------
from agents.signal_monitor.src.agent import (
    SignalMonitorAgent,
    SignalMonitorResult,
)
from packages.core.src.types import (
    CompetitorAnalysis,
    CompetitorFundingRound,
    CompetitorPricing,
    CustomerPersona,
    LeadProfile,
    LeadStatus,
)
from packages.scoring.src.signal_relevance import ScoredSignal

# =============================================================================
# Helpers — suppress external __init__ side-effects for agents that connect
# to external services in __init__ (AgentBus, Perplexity, NewsAPI, etc.)
# =============================================================================


def _make_competitor_agent() -> CompetitorAnalystAgent:
    """Build a CompetitorAnalystAgent with all external calls patched out."""
    mock_bus = MagicMock()
    mock_bus.subscribe = MagicMock()
    with (
        patch("agents.competitor_analyst.src.agent.get_llm_manager") as mock_llm,
        patch("agents.competitor_analyst.src.agent.get_eodhd_client") as mock_eo,
        patch("agents.competitor_analyst.src.agent.get_agent_bus", return_value=mock_bus),
        patch("agents.competitor_analyst.src.agent.AgentMCPClient"),
    ):
        mock_llm.return_value = MagicMock(perplexity=AsyncMock())
        mock_eo.return_value = MagicMock()
        agent = CompetitorAnalystAgent(agent_bus=mock_bus)
    return agent


def _make_customer_profiler_agent() -> CustomerProfilerAgent:
    """Build a CustomerProfilerAgent with the AgentBus patched out."""
    mock_bus = MagicMock()
    mock_bus.get_history = MagicMock(return_value=[])
    with patch("agents.customer_profiler.src.agent.get_agent_bus", return_value=mock_bus):
        agent = CustomerProfilerAgent(bus=mock_bus)
    return agent


def _make_gtm_strategist_agent() -> GTMStrategistAgent:
    """Build a GTMStrategistAgent with external calls patched."""
    mock_bus = MagicMock()
    with (
        patch("agents.gtm_strategist.src.agent.get_agent_bus", return_value=mock_bus),
        patch("agents.gtm_strategist.src.agent.AgentMCPClient"),
    ):
        agent = GTMStrategistAgent(agent_bus=mock_bus)
    return agent


def _make_lead_hunter_agent() -> LeadHunterAgent:
    """Build a LeadHunterAgent with external calls patched."""
    with (
        patch("agents.lead_hunter.src.agent.get_agent_bus") as mock_bus_fn,
        patch("agents.lead_hunter.src.agent.EODHDClient"),
    ):
        mock_bus_fn.return_value = MagicMock()
        agent = LeadHunterAgent()
    return agent


def _make_signal_monitor_agent() -> SignalMonitorAgent:
    """Build a SignalMonitorAgent with external calls patched."""
    mock_bus = MagicMock()
    with (
        patch("agents.signal_monitor.src.agent.get_agent_bus", return_value=mock_bus),
        patch("agents.signal_monitor.src.agent.NewsAPIClient"),
        patch("agents.signal_monitor.src.agent.EODHDClient"),
        patch("agents.signal_monitor.src.agent.SignalRelevanceScorer"),
    ):
        agent = SignalMonitorAgent(agent_bus=mock_bus)
    return agent


# =============================================================================
# CompetitorAnalystAgent — _check() tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_competitor_check_no_competitors_base_score():
    """Empty competitors list with no real data → base score of 0.20 only."""
    agent = _make_competitor_agent()
    agent._competitors_with_real_data = set()

    result = CompetitorIntelOutput(
        competitors=[],
        market_landscape="",
        competitive_positioning=CompetitivePositioning(),
        strategic_recommendations=[],
    )
    score = await agent._check(result)

    # Path: no competitors → base_score = 0.20, no bonuses (Rule #4)
    assert score == pytest.approx(0.20)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_competitor_check_competitors_no_real_data_capped_at_065():
    """Competitors present but _competitors_with_real_data is empty → cap 0.65."""
    agent = _make_competitor_agent()
    agent._competitors_with_real_data = set()  # No MCP data fetched

    competitor = CompetitorAnalysis(
        competitor_name="Competitor A",
        strengths=["Fast product"],
        weaknesses=["No mobile app"],
    )
    result = CompetitorIntelOutput(
        competitors=[competitor],
        market_landscape="Active market",
        competitive_positioning=CompetitivePositioning(
            your_differentiators=["Lower price"],
        ),
        strategic_recommendations=["Target SMEs"],
    )
    score = await agent._check(result)

    # base 0.20 + 0.15 (competitors) + 0.10 (strengths+weaknesses) + 0.10 (differentiators)
    # + 0.10 (strategic_recommendations) + 0.05 (market_landscape) = 0.70, capped at 0.65
    assert score <= 0.65


@pytest.mark.unit
@pytest.mark.asyncio
async def test_competitor_check_full_data_scores_high():
    """2 competitors with real data + all bonus fields → score ≥ 0.80."""
    agent = _make_competitor_agent()
    agent._competitors_with_real_data = {"Competitor A", "Competitor B"}

    competitors = [
        CompetitorAnalysis(
            competitor_name="Competitor A",
            strengths=["Enterprise grade"],
            weaknesses=["Expensive"],
        ),
        CompetitorAnalysis(
            competitor_name="Competitor B",
            strengths=["Easy UI"],
            weaknesses=["No support"],
        ),
    ]
    result = CompetitorIntelOutput(
        competitors=competitors,
        market_landscape="Competitive SaaS landscape",
        competitive_positioning=CompetitivePositioning(
            your_differentiators=["Singapore-focused", "SME pricing"],
        ),
        strategic_recommendations=["Target mid-market", "Compete on price"],
    )
    score = await agent._check(result)

    # Path: 2 competitors, 2 with real data → data_coverage = 1.0, base = 0.5, cap = 1.0
    # + 0.15 (competitors non-empty) + 0.10 (strengths+weaknesses) + 0.10 (differentiators)
    # + 0.10 (recommendations) + 0.05 (landscape) = 1.00, no cap hit
    assert score >= 0.80


@pytest.mark.unit
@pytest.mark.asyncio
async def test_competitor_check_pricing_tiers_bonus():
    """Competitor with pricing_tiers earns +0.05 vs same result without."""
    agent = _make_competitor_agent()
    agent._competitors_with_real_data = set()

    competitor_base = CompetitorAnalysis(competitor_name="TechCo")
    result_no_pricing = CompetitorIntelOutput(competitors=[competitor_base])

    competitor_with_pricing = CompetitorAnalysis(
        competitor_name="TechCo",
        pricing_tiers=[
            CompetitorPricing(tier_name="Starter", price_sgd=99.0, frequency="monthly")
        ],
    )
    result_with_pricing = CompetitorIntelOutput(competitors=[competitor_with_pricing])

    score_no_pricing = await agent._check(result_no_pricing)
    score_with_pricing = await agent._check(result_with_pricing)

    assert score_with_pricing == pytest.approx(score_no_pricing + 0.05)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_competitor_check_funding_bonus():
    """Competitor with latest_funding earns +0.05 vs same result without."""
    agent = _make_competitor_agent()
    agent._competitors_with_real_data = set()

    competitor_base = CompetitorAnalysis(competitor_name="FinCo", latest_funding=None)
    result_no_funding = CompetitorIntelOutput(competitors=[competitor_base])

    competitor_with_funding = CompetitorAnalysis(
        competitor_name="FinCo",
        latest_funding=CompetitorFundingRound(
            round_type="Series A",
            amount_usd=5_000_000.0,
        ),
    )
    result_with_funding = CompetitorIntelOutput(competitors=[competitor_with_funding])

    score_no_funding = await agent._check(result_no_funding)
    score_with_funding = await agent._check(result_with_funding)

    assert score_with_funding == pytest.approx(score_no_funding + 0.05)


# =============================================================================
# CustomerProfilerAgent — _check() tests
# =============================================================================


def _make_persona(name: str = "Tech Buyer") -> CustomerPersona:
    return CustomerPersona(
        name=name,
        role="VP Engineering",
        pain_points=["slow deployments"],
        goals=["reduce time-to-market"],
        challenges=["legacy systems"],
        preferred_channels=["email"],
        decision_criteria=["ROI", "ease of use"],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_customer_profiler_check_empty_output_returns_base():
    """Completely empty output → score == 0.2 (base only)."""
    agent = _make_customer_profiler_agent()
    # Ensure _kb_hit is not set (no KB grounding)
    agent._kb_hit = False

    result = CustomerProfileOutput(
        icp=ICPDefinition(),
        personas=[],
        targeting_recommendations=[],
        messaging_themes=[],
    )
    score = await agent._check(result)

    assert score == pytest.approx(0.2)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_customer_profiler_check_full_output_scores_high():
    """ICP with chars + buying_signals + 2 personas + recommendations + themes → ≥ 0.80."""
    agent = _make_customer_profiler_agent()
    agent._kb_hit = False
    agent._has_live_data = True  # Simulate live data so confidence cap (0.45) doesn't fire

    icp = ICPDefinition(
        company_characteristics={"size": "10-50", "stage": "Series A"},
        buying_signals=["Hiring sales reps", "Raised funding"],
    )
    result = CustomerProfileOutput(
        icp=icp,
        personas=[_make_persona("Buyer One"), _make_persona("Buyer Two")],
        targeting_recommendations=["Start with fintech", "Focus on Series A"],
        messaging_themes=["Speed to revenue", "SME focus"],
    )
    score = await agent._check(result)

    # 0.2 + 0.15 (chars) + 0.10 (buying_signals) + 0.15 (personas) + 0.10 (≥2 personas)
    # + 0.10 (recommendations) + 0.10 (themes) = 0.90
    assert score >= 0.80


@pytest.mark.unit
@pytest.mark.asyncio
async def test_customer_profiler_check_kb_hit_bonus():
    """Setting _kb_hit = True adds exactly +0.10 to score vs _kb_hit = False."""
    agent = _make_customer_profiler_agent()
    agent._has_live_data = True  # Simulate live data so confidence cap (0.45) doesn't fire

    icp = ICPDefinition(
        company_characteristics={"size": "50-200"},
        buying_signals=["Looking for CRM"],
    )
    result = CustomerProfileOutput(
        icp=icp,
        personas=[_make_persona()],
        targeting_recommendations=["Target fintech"],
        messaging_themes=["Automate outreach"],
    )

    agent._kb_hit = False
    score_without_kb = await agent._check(result)

    agent._kb_hit = True
    score_with_kb = await agent._check(result)

    assert score_with_kb == pytest.approx(score_without_kb + 0.10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_customer_profiler_check_single_persona_no_second_bonus():
    """1 persona → +0.15 first-persona bonus, but NOT the +0.10 second-persona bonus."""
    agent = _make_customer_profiler_agent()
    agent._kb_hit = False

    result = CustomerProfileOutput(
        icp=ICPDefinition(),
        personas=[_make_persona()],
        targeting_recommendations=[],
        messaging_themes=[],
    )
    score = await agent._check(result)

    # Base 0.20 + 0.15 (one persona present) = 0.35; no second-persona bonus
    assert score == pytest.approx(0.35)


# =============================================================================
# GTMStrategistAgent — _check() tests
# =============================================================================


def _make_minimal_gtm_output(company_name: str = "Acme") -> GTMStrategyOutput:
    """Minimal valid GTMStrategyOutput (no live data, no extras)."""
    return GTMStrategyOutput(
        requirements=UserRequirements(company_name=company_name),
        work_distribution=WorkDistribution(),
        initial_recommendations=[],
        is_live_data=False,
        market_sizing=None,
        sales_motion=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gtm_strategist_check_base_score_no_data():
    """Minimal result with no live data → score ≈ 0.20 (base) + company_name bonus only."""
    agent = _make_gtm_strategist_agent()

    result = _make_minimal_gtm_output()
    score = await agent._check(result)

    # Base 0.20 + 0.10 (company_name present) = 0.30
    assert score == pytest.approx(0.30)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gtm_strategist_check_live_data_bonus():
    """Setting is_live_data = True adds +0.15 to the score."""
    agent = _make_gtm_strategist_agent()

    result_no_live = _make_minimal_gtm_output()
    result_no_live.is_live_data = False
    score_no_live = await agent._check(result_no_live)

    result_live = _make_minimal_gtm_output()
    result_live.is_live_data = True
    score_live = await agent._check(result_live)

    assert score_live == pytest.approx(score_no_live + 0.15)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gtm_strategist_check_market_sizing_and_sales_motion_bonus():
    """market_sizing.tam_sgd_estimate and sales_motion.primary_motion each add +0.10."""
    agent = _make_gtm_strategist_agent()

    result = _make_minimal_gtm_output()
    result.market_sizing = MarketSizing(tam_sgd_estimate="SGD 500M")
    result.sales_motion = SalesMotion(primary_motion="SLG")

    score = await agent._check(result)

    # Base 0.20 + 0.10 (company_name) + 0.10 (market_sizing) + 0.10 (sales_motion) = 0.50
    assert score == pytest.approx(0.50)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gtm_strategist_check_capped_at_090():
    """Fully populated result should never exceed the 0.90 cap."""
    agent = _make_gtm_strategist_agent()

    tasks = [
        AgentTask(agent_name="market-intelligence", task_type="research", description="Market research")
    ]
    recommendations = [
        StrategicRecommendation(
            title=f"Rec {i}",
            description="Do it",
            rationale="Important",
        )
        for i in range(5)  # 5 × 0.05 = 0.15 (capped at 0.15)
    ]
    result = GTMStrategyOutput(
        requirements=UserRequirements(company_name="Acme"),
        work_distribution=WorkDistribution(tasks=tasks),
        initial_recommendations=recommendations,
        is_live_data=True,
        market_sizing=MarketSizing(tam_sgd_estimate="SGD 500M"),
        sales_motion=SalesMotion(primary_motion="SLG"),
    )

    score = await agent._check(result)

    assert score <= 0.90


# =============================================================================
# LeadHunterAgent — _guess_domain() tests (sync, no async)
# =============================================================================


@pytest.mark.unit
def test_guess_domain_strips_pte_ltd():
    """'Acme Pte Ltd' → 'acme.com'."""
    assert _guess_domain("Acme Pte Ltd") == "acme.com"


@pytest.mark.unit
def test_guess_domain_strips_limited():
    """'GlobalTech Limited' → 'globaltech.com'."""
    assert _guess_domain("GlobalTech Limited") == "globaltech.com"


@pytest.mark.unit
def test_guess_domain_handles_spaces_and_special_chars():
    """'Tech & Co Solutions' should collapse non-alpha runs into hyphens."""
    result = _guess_domain("Tech & Co Solutions")
    # Ampersand and spaces collapse to hyphens; strip trailing hyphens
    assert result.endswith(".com")
    # The domain slug should contain 'tech' and 'co' and 'solutions'
    slug = result[:-4]  # strip '.com'
    assert "tech" in slug
    assert "co" in slug


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lead_hunter_check_empty_prospects():
    """Empty prospects list → score 0.35 (below threshold, skip retry)."""
    agent = _make_lead_hunter_agent()

    result = LeadHuntingOutput(
        target_criteria=LeadScoringCriteria(),
        prospects=[],
        qualified_leads=[],
        suggested_approach="",
        top_recommendations=[],
        determinism_ratio=0.0,
    )
    score = await agent._check(result)

    assert score == pytest.approx(0.35)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lead_hunter_check_algo_scored_prospects_score_high():
    """Algorithm-scored prospects with qualified leads and high determinism → ≥ 0.85."""
    agent = _make_lead_hunter_agent()

    prospects = [
        ProspectCompany(
            company_name=f"Company {i}",
            fit_reasons=["Matches ICP", "Growing fast"],
            scoring_method="algorithm",
            fit_score=0.8,
            intent_score=0.7,
        )
        for i in range(3)
    ]
    qualified = [
        LeadProfile(
            company_name=f"Company {i}",
            status=LeadStatus.QUALIFIED,
            fit_score=0.8,
            intent_score=0.7,
            overall_score=0.76,
        )
        for i in range(3)
    ]
    result = LeadHuntingOutput(
        target_criteria=LeadScoringCriteria(),
        prospects=prospects,
        qualified_leads=qualified,
        suggested_approach="Use LinkedIn outreach with personalised messages referencing their recent funding round.",
        top_recommendations=["Focus on Series A fintech", "Personalise by trigger events"],
        determinism_ratio=0.85,
        sources_searched=["company_enrichment", "algorithms"],
    )
    score = await agent._check(result)

    # 0.30 + 0.20 (prospects) + 0.20 (qualified) + 0.15 (≥2 with reasons) + 0.15 (≥80% algo)
    # + 0.15 (approach > 50 chars) + 0.10 (recommendations) + 0.05 (determinism ≥ 0.7) = 1.30 → capped 1.0
    assert score >= 0.85


# =============================================================================
# SignalMonitorAgent — _check() tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signal_monitor_check_no_data():
    """Result with no data sources and no signals → base score 0.20."""
    agent = _make_signal_monitor_agent()

    result = SignalMonitorResult(
        company_id="test-company-id",
        data_sources_queried=[],
        signals_actionable=0,
        signals_urgent=0,
    )
    score = await agent._check(result)

    assert score == pytest.approx(0.20)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signal_monitor_check_3_sources_actionable_urgent():
    """3 sources + signals_actionable > 0 + signals_urgent > 0 → score ≥ 0.90."""
    agent = _make_signal_monitor_agent()

    result = SignalMonitorResult(
        company_id="test-company-id",
        data_sources_queried=["NewsAPI", "EODHD", "Perplexity"],
        signals_actionable=5,
        signals_urgent=2,
    )
    score = await agent._check(result)

    # 0.20 + 3×0.15 (capped 0.45) + 0.20 (actionable) + 0.15 (urgent) = 1.00 → capped 1.0
    assert score >= 0.90


# =============================================================================
# SignalMonitorAgent — _compute_account_summaries() tests (pure / sync-called)
# =============================================================================


def _make_scored_signal(
    signal_text: str,
    signal_type: str,
    competitors_mentioned: list[str],
    urgency: str = "this_week",
) -> ScoredSignal:
    """Create a ScoredSignal dataclass for testing."""
    return ScoredSignal(
        signal_text=signal_text,
        signal_type=signal_type,
        relevance_score=0.60,
        urgency=urgency,
        recommended_action="Outreach now",
        reasoning=["Test signal"],
        competitors_mentioned=competitors_mentioned,
        industries_affected=["fintech"],
        source="NewsAPI",
    )


@pytest.mark.unit
def test_compute_account_summaries_funding_signal():
    """Single funding signal mentioning TechCo → deal_probability ≥ 0.40 (base 0.20 + 0.25)."""
    agent = _make_signal_monitor_agent()

    signal = _make_scored_signal(
        signal_text="TechCo raises Series B funding round",
        signal_type="funding",
        competitors_mentioned=["TechCo"],
    )
    summaries = agent._compute_account_summaries([signal], company_id="test-id")

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["company_name"] == "techco"
    assert summary["deal_probability"] >= 0.40


@pytest.mark.unit
def test_compute_account_summaries_multi_signal_bonus():
    """3 funding signals for same company → higher deal_probability than single signal."""
    agent = _make_signal_monitor_agent()

    single_signal = [
        _make_scored_signal("TechCo raises funding", "funding", ["TechCo"])
    ]
    multi_signals = [
        _make_scored_signal("TechCo raises Series A", "funding", ["TechCo"]),
        _make_scored_signal("TechCo closes Series B", "funding", ["TechCo"]),
        _make_scored_signal("TechCo secures growth capital", "funding", ["TechCo"]),
    ]

    single_summaries = agent._compute_account_summaries(single_signal, company_id="test-id")
    multi_summaries = agent._compute_account_summaries(multi_signals, company_id="test-id")

    assert len(single_summaries) == 1
    assert len(multi_summaries) == 1
    single_prob = single_summaries[0]["deal_probability"]
    multi_prob = multi_summaries[0]["deal_probability"]

    # Multi-signal bonus: +0.10 per additional signal (capped at +0.30)
    assert multi_prob > single_prob


@pytest.mark.unit
def test_compute_account_summaries_skips_market_bucket():
    """Signals with no competitors_mentioned are bucketed as 'market' and excluded from summaries."""
    agent = _make_signal_monitor_agent()

    market_signal = _make_scored_signal(
        signal_text="Singapore fintech market grows 20% YoY",
        signal_type="market_trend",
        competitors_mentioned=[],  # No specific company
    )
    summaries = agent._compute_account_summaries([market_signal], company_id="test-id")

    # The 'market' bucket is explicitly skipped in the loop
    assert len(summaries) == 0
