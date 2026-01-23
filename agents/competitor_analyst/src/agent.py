"""Competitor Analyst Agent - Real competitive intelligence.

Uses Perplexity for real-time competitor research and EODHD for financial data.
Subscribes to COMPETITOR_FOUND discoveries from other agents for dynamic analysis.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.types import CompetitorAnalysis
from packages.core.src.agent_bus import (
    AgentBus,
    AgentMessage,
    DiscoveryType,
    get_agent_bus,
)
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

    A2A Integration:
    - Subscribes to COMPETITOR_FOUND discoveries from CompanyEnricher
    - Dynamically adds discovered competitors to analysis
    - Publishes COMPETITOR_WEAKNESS discoveries for other agents
    """

    def __init__(
        self,
        agent_bus: AgentBus | None = None,
        analysis_id: UUID | None = None,
    ) -> None:
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
                AgentCapability(
                    name="a2a-discovery",
                    description="React to competitor discoveries from other agents",
                ),
            ],
        )

        self._perplexity = get_llm_manager().perplexity
        self._eodhd = get_eodhd_client()
        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id = analysis_id
        self._discovered_competitors: list[str] = []

        # Subscribe to competitor discoveries
        self._subscribe_to_discoveries()

    def _subscribe_to_discoveries(self) -> None:
        """Subscribe to relevant discovery types from other agents."""
        self._agent_bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.COMPETITOR_FOUND,
            handler=self._on_competitor_discovered,
        )

        # Also subscribe to company profile for context
        self._agent_bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.COMPANY_PROFILE,
            handler=self._on_company_profile,
        )

    async def _on_competitor_discovered(self, message: AgentMessage) -> None:
        """Handle competitor discovery from another agent."""
        competitor_name = message.content.get("competitor_name")
        if competitor_name and competitor_name not in self._discovered_competitors:
            self._discovered_competitors.append(competitor_name)
            self._logger.info(
                "competitor_discovered_via_a2a",
                competitor=competitor_name,
                from_agent=message.from_agent,
            )

    async def _on_company_profile(self, message: AgentMessage) -> None:
        """Handle company profile discovery for context enrichment."""
        self._logger.debug(
            "company_profile_received",
            company=message.content.get("company_name"),
            from_agent=message.from_agent,
        )

    def set_analysis_id(self, analysis_id: UUID) -> None:
        """Set the current analysis ID."""
        self._analysis_id = analysis_id

    def get_discovered_competitors(self) -> list[str]:
        """Get competitors discovered via A2A communication."""
        return self._discovered_competitors.copy()

    def clear_discovered_competitors(self) -> None:
        """Clear discovered competitors (call between analyses)."""
        self._discovered_competitors.clear()

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

        # Merge in competitors discovered via A2A communication
        all_competitors = list(set(competitors + self._discovered_competitors))

        self._logger.info(
            "planning_competitor_analysis",
            known_competitors=len(competitors),
            discovered_competitors=len(self._discovered_competitors),
            total_competitors=len(all_competitors),
        )

        return {
            "known_competitors": all_competitors,
            "industry": industry,
            "research_queries": [
                f"{comp} company analysis products pricing" for comp in all_competitors[:5]
            ]
            + [f"top {industry} competitors Singapore"],
            "discovered_via_a2a": self._discovered_competitors.copy(),
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

    async def _act(self, result: CompetitorIntelOutput, confidence: float) -> CompetitorIntelOutput:
        """Publish discovered weaknesses to the AgentBus."""
        result.confidence = confidence

        # Publish competitor weaknesses for Campaign Architect to exploit
        if self._agent_bus and result.competitors:
            for competitor in result.competitors:
                if competitor.weaknesses:
                    await self._agent_bus.publish(
                        from_agent=self.name,
                        discovery_type=DiscoveryType.COMPETITOR_WEAKNESS,
                        title=f"Weaknesses: {competitor.competitor_name}",
                        content={
                            "competitor_name": competitor.competitor_name,
                            "weaknesses": competitor.weaknesses,
                            "opportunities": competitor.opportunities,
                        },
                        confidence=confidence,
                        analysis_id=self._analysis_id,
                    )

        return result
