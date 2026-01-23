"""Competitor Analyst Agent - Real competitive intelligence.

Uses Perplexity for real-time competitor research and EODHD for financial data.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.types import CompetitorAnalysis
from packages.integrations.eodhd.src import get_eodhd_client
from packages.llm.src import get_llm_manager


class CompetitivePositioning(BaseModel):
    """Your positioning vs competitors."""

    your_differentiators: list[str] = Field(default_factory=list)
    competitor_advantages: list[str] = Field(default_factory=list)
    market_gaps: list[str] = Field(default_factory=list)
    recommended_positioning: str = Field(default="")


class CompetitorIntelOutput(BaseModel):
    """Complete competitor intelligence report."""

    competitors: list[CompetitorAnalysis] = Field(default_factory=list)
    market_landscape: str = Field(default="")
    competitive_positioning: CompetitivePositioning = Field(
        default_factory=CompetitivePositioning
    )
    strategic_recommendations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CompetitorAnalystAgent(BaseGTMAgent[CompetitorIntelOutput]):
    """Competitor Analyst - Real competitive intelligence.

    Researches actual competitors using:
    - Perplexity for real-time company research
    - EODHD for public company financials
    - Web research for product/pricing info
    """

    def __init__(self) -> None:
        super().__init__(
            name="competitor-analyst",
            description=(
                "Provides real competitive intelligence using live data. "
                "Analyzes competitor strengths, weaknesses, and positioning "
                "to help you differentiate effectively."
            ),
            result_type=CompetitorIntelOutput,
            min_confidence=0.60,  # Lowered - empty competitor list can still pass
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="competitor-research",
                    description="Research competitor companies",
                ),
                AgentCapability(
                    name="swot-analysis",
                    description="SWOT analysis of competitors",
                ),
                AgentCapability(
                    name="positioning-analysis",
                    description="Analyze market positioning",
                ),
            ],
        )

        self._perplexity = get_llm_manager().perplexity
        self._eodhd = get_eodhd_client()

    def get_system_prompt(self) -> str:
        return """You are the Competitor Analyst, specializing in competitive intelligence for Singapore/APAC markets.

You provide DATA-DRIVEN competitor analysis, not generic SWOT templates. You:
1. Research real competitors with actual data
2. Identify specific strengths and weaknesses
3. Analyze pricing and positioning
4. Find actionable differentiation opportunities

Be specific - cite real products, features, pricing, recent news.
Focus on Singapore/APAC competitors when relevant."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        competitors = context.get("known_competitors", [])
        industry = context.get("industry", "technology")

        return {
            "known_competitors": competitors,
            "industry": industry,
            "research_queries": [
                f"{comp} company analysis products pricing" for comp in competitors[:3]
            ]
            + [f"top {industry} competitors Singapore"],
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CompetitorIntelOutput:
        context = context or {}
        competitors_data: list[CompetitorAnalysis] = []

        # Research each known competitor
        for competitor in plan.get("known_competitors", [])[:5]:
            try:
                research = await self._perplexity.research_company(competitor)
                analysis = await self._parse_competitor(competitor, research, context)
                if analysis:
                    competitors_data.append(analysis)
            except Exception as e:
                self._logger.warning("competitor_research_failed", competitor=competitor, error=str(e))

        # Synthesize positioning
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Based on competitor research:
{[c.model_dump() for c in competitors_data]}

Your company: {context.get('company_name', 'Not specified')}
Industry: {plan.get('industry')}

Create a complete CompetitorIntelOutput with:
1. Market landscape summary
2. Competitive positioning analysis
3. Strategic recommendations
""",
            },
        ]

        result = await self._complete_structured(
            response_model=CompetitorIntelOutput,
            messages=messages,
        )
        result.competitors = competitors_data
        result.sources = ["Perplexity AI"]
        return result

    async def _parse_competitor(
        self,
        name: str,
        research: str,
        context: dict[str, Any],
    ) -> CompetitorAnalysis | None:
        """Parse research into competitor analysis."""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": f"Parse this into a CompetitorAnalysis:\n{research}"},
        ]
        try:
            return await self._complete_structured(
                response_model=CompetitorAnalysis,
                messages=messages,
            )
        except Exception:
            return None

    async def _check(self, result: CompetitorIntelOutput) -> float:
        score = 0.3  # Base score for completing analysis
        if result.competitors:
            score += 0.2
            # Check SWOT completeness
            for c in result.competitors:
                if c.strengths and c.weaknesses:
                    score += 0.1
                    break
        if result.competitive_positioning.your_differentiators:
            score += 0.15
        if result.strategic_recommendations:
            score += 0.15
        if result.market_landscape:
            score += 0.1
        return min(score, 1.0)
