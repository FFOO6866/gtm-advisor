"""Market Intelligence Agent - Real market research and trend analysis.

This agent provides genuine market insights by combining:
- Perplexity AI for real-time web search
- NewsAPI for industry news
- EODHD for economic indicators

NOT generic LLM advice - actual data-driven insights.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.types import IndustryVertical, MarketInsight
from packages.integrations.eodhd.src import get_eodhd_client
from packages.integrations.newsapi.src import get_newsapi_client
from packages.llm.src import get_llm_manager


class MarketTrend(BaseModel):
    """A market trend with supporting data."""

    name: str = Field(...)
    description: str = Field(...)
    relevance: str = Field(...)  # How it affects the user's business
    evidence: list[str] = Field(default_factory=list)  # Sources/data points
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0)


class MarketOpportunity(BaseModel):
    """Market opportunity identified."""

    title: str = Field(...)
    description: str = Field(...)
    market_size_estimate: str | None = Field(default=None)
    growth_rate: str | None = Field(default=None)
    competitive_intensity: str = Field(default="medium")  # low, medium, high
    time_sensitivity: str = Field(default="medium")  # low, medium, high
    recommended_action: str = Field(...)


class MarketIntelligenceOutput(BaseModel):
    """Complete market intelligence report."""

    industry: IndustryVertical = Field(...)
    region: str = Field(default="Singapore")

    # Market Overview
    market_summary: str = Field(...)
    market_size: str | None = Field(default=None)
    growth_outlook: str | None = Field(default=None)

    # Trends
    key_trends: list[MarketTrend] = Field(default_factory=list)

    # Opportunities & Threats
    opportunities: list[MarketOpportunity] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)

    # Economic Context
    economic_indicators: list[dict[str, Any]] = Field(default_factory=list)

    # News & Events
    recent_news: list[dict[str, str]] = Field(default_factory=list)

    # Recommendations
    implications_for_gtm: list[str] = Field(default_factory=list)

    # Metadata
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_freshness: str = Field(default="real-time")


class MarketIntelligenceAgent(BaseGTMAgent[MarketIntelligenceOutput]):
    """Market Intelligence Agent - Real data-driven market research.

    This agent goes beyond generic LLM responses by:
    1. Using Perplexity for real-time web search
    2. Pulling actual news from NewsAPI
    3. Incorporating economic indicators from EODHD
    4. Synthesizing data into actionable insights

    Focus: Singapore and APAC markets
    """

    def __init__(self) -> None:
        super().__init__(
            name="market-intelligence",
            description=(
                "Provides real-time market intelligence using live data sources. "
                "Analyzes market trends, opportunities, and threats specific to "
                "Singapore/APAC markets with actual news and economic data."
            ),
            result_type=MarketIntelligenceOutput,
            min_confidence=0.75,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="market-research",
                    description="Research market trends and dynamics",
                ),
                AgentCapability(
                    name="trend-analysis",
                    description="Identify and analyze market trends",
                ),
                AgentCapability(
                    name="opportunity-identification",
                    description="Spot market opportunities",
                ),
                AgentCapability(
                    name="economic-analysis",
                    description="Incorporate economic indicators",
                ),
            ],
        )

        # Initialize data source clients
        self._newsapi = get_newsapi_client()
        self._eodhd = get_eodhd_client()
        self._perplexity = get_llm_manager().perplexity

    def get_system_prompt(self) -> str:
        return """You are the Market Intelligence Agent, a specialist in APAC market research with deep expertise in Singapore's business landscape.

Your role is to provide DATA-DRIVEN market intelligence, not generic advice. You:
1. Use real news and data to identify trends
2. Analyze economic indicators for context
3. Identify specific opportunities and threats
4. Provide actionable insights with evidence

Key focus areas for Singapore:
- Strong government support for startups (PSG grants, etc.)
- High digital adoption rates
- Regional hub for fintech, SaaS
- Growing SME ecosystem
- ASEAN expansion gateway

When analyzing markets:
- Cite specific sources and data points
- Quantify market sizes when possible
- Identify timing and urgency
- Connect trends to GTM implications

Be specific and data-driven. Generic statements like "the market is growing" are not helpful without supporting data."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan market intelligence gathering."""
        context = context or {}

        # Determine industry and region
        industry = context.get("industry", "technology")
        region = context.get("region", "Singapore")
        company_name = context.get("company_name", "")

        # Plan data gathering
        plan = {
            "industry": industry,
            "region": region,
            "company_name": company_name,
            "data_sources": [],
            "queries": [],
        }

        # Plan Perplexity queries
        plan["queries"] = [
            f"{industry} market trends Singapore 2024 2025",
            f"{industry} startup ecosystem APAC growth",
            f"{industry} Singapore SME challenges opportunities",
        ]

        # Plan data sources to use
        if self._newsapi.is_configured:
            plan["data_sources"].append("newsapi")
        if self._eodhd.is_configured:
            plan["data_sources"].append("eodhd")
        if self._perplexity.is_configured:
            plan["data_sources"].append("perplexity")

        return plan

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MarketIntelligenceOutput:
        """Execute market intelligence gathering."""
        context = context or {}
        industry = plan.get("industry", "technology")
        region = plan.get("region", "Singapore")

        # Gather data from multiple sources
        gathered_data: dict[str, Any] = {
            "news": [],
            "economic": [],
            "research": [],
        }

        # 1. Get news from NewsAPI
        if "newsapi" in plan.get("data_sources", []):
            try:
                news_result = await self._newsapi.search_market_news(
                    industry=industry,
                    region=region,
                    days_back=14,
                )
                gathered_data["news"] = [
                    {
                        "title": article.title,
                        "source": article.source_name,
                        "url": article.url,
                        "date": article.published_at.isoformat(),
                    }
                    for article in news_result.articles[:10]
                ]
            except Exception as e:
                self._logger.warning("newsapi_fetch_failed", error=str(e))

        # 2. Get economic indicators from EODHD
        if "eodhd" in plan.get("data_sources", []):
            try:
                indicators = await self._eodhd.get_economic_indicators("SGP")
                gathered_data["economic"] = [
                    {
                        "indicator": ind.indicator,
                        "value": ind.value,
                        "period": ind.period,
                    }
                    for ind in indicators[:5]
                ]
            except Exception as e:
                self._logger.warning("eodhd_fetch_failed", error=str(e))

        # 3. Get real-time research from Perplexity
        if "perplexity" in plan.get("data_sources", []):
            try:
                research_query = f"""
                Provide detailed market analysis for {industry} in {region}:
                1. Current market size and growth rate
                2. Key trends driving the market
                3. Major opportunities for new entrants
                4. Challenges and threats
                5. Regulatory environment
                Include specific data points, statistics, and sources.
                """
                research = await self._perplexity.research_market(
                    topic=f"{industry} market",
                    region=region,
                )
                gathered_data["research"] = research
            except Exception as e:
                self._logger.warning("perplexity_fetch_failed", error=str(e))

        # 4. Synthesize with LLM
        return await self._synthesize_intelligence(
            industry=industry,
            region=region,
            gathered_data=gathered_data,
            context=context,
        )

    async def _synthesize_intelligence(
        self,
        industry: str,
        region: str,
        gathered_data: dict[str, Any],
        context: dict[str, Any],
    ) -> MarketIntelligenceOutput:
        """Synthesize gathered data into market intelligence."""
        # Build synthesis prompt with real data
        data_summary = []

        if gathered_data.get("news"):
            news_text = "\n".join(
                f"- {n['title']} ({n['source']})" for n in gathered_data["news"][:5]
            )
            data_summary.append(f"Recent News:\n{news_text}")

        if gathered_data.get("economic"):
            econ_text = "\n".join(
                f"- {e['indicator']}: {e['value']} ({e['period']})"
                for e in gathered_data["economic"]
            )
            data_summary.append(f"Economic Indicators:\n{econ_text}")

        if gathered_data.get("research"):
            data_summary.append(f"Research Insights:\n{gathered_data['research']}")

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Synthesize this real market data into a comprehensive intelligence report:

Industry: {industry}
Region: {region}
Company Context: {context.get('company_name', 'Not specified')}

GATHERED DATA:
{chr(10).join(data_summary) if data_summary else 'Limited data available - provide analysis based on general knowledge.'}

Create a MarketIntelligenceOutput with:
1. Market summary with specific data points
2. Key trends (with evidence from the data)
3. Opportunities (quantified where possible)
4. Threats and challenges
5. Economic context
6. Recent news highlights
7. GTM implications

Be specific and cite the data provided. Confidence should reflect data quality.""",
            },
        ]

        result = await self._complete_structured(
            response_model=MarketIntelligenceOutput,
            messages=messages,
        )

        # Add news to result
        result.recent_news = gathered_data.get("news", [])[:5]
        result.economic_indicators = gathered_data.get("economic", [])

        # Add sources
        sources = []
        if gathered_data.get("news"):
            sources.append("NewsAPI")
        if gathered_data.get("economic"):
            sources.append("EODHD")
        if gathered_data.get("research"):
            sources.append("Perplexity AI")
        result.sources = sources

        return result

    async def _check(self, result: MarketIntelligenceOutput) -> float:
        """Validate market intelligence quality."""
        score = 0.0

        # Check data presence
        if result.market_summary and len(result.market_summary) > 100:
            score += 0.2

        # Check trends
        if result.key_trends:
            score += 0.15
            # Quality check - trends should have evidence
            with_evidence = sum(1 for t in result.key_trends if t.evidence)
            if with_evidence >= 2:
                score += 0.1

        # Check opportunities
        if result.opportunities:
            score += 0.15
            # Quality check - opportunities should have recommendations
            with_recs = sum(
                1 for o in result.opportunities if o.recommended_action
            )
            if with_recs >= 2:
                score += 0.1

        # Check GTM implications
        if result.implications_for_gtm:
            score += 0.15

        # Check data sources
        if result.sources:
            score += 0.05 * len(result.sources)

        # Check news and economic data
        if result.recent_news:
            score += 0.05
        if result.economic_indicators:
            score += 0.05

        return min(score, 1.0)

    async def research_industry(
        self,
        industry: IndustryVertical,
        region: str = "Singapore",
        focus_areas: list[str] | None = None,
    ) -> MarketIntelligenceOutput:
        """Research a specific industry.

        Convenience method for direct industry research.

        Args:
            industry: Industry to research
            region: Geographic region
            focus_areas: Specific areas to focus on

        Returns:
            Market intelligence report
        """
        task = f"Research {industry.value} market in {region}"
        context = {
            "industry": industry.value,
            "region": region,
            "focus_areas": focus_areas or [],
        }
        return await self.run(task, context=context)
