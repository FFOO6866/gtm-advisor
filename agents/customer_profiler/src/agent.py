"""Customer Profiler Agent - ICP and persona development.

Develops detailed ideal customer profiles and personas based on market research.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.types import CustomerPersona, IndustryVertical


class ICPDefinition(BaseModel):
    """Ideal Customer Profile definition."""

    company_characteristics: dict[str, Any] = Field(default_factory=dict)
    firmographics: dict[str, Any] = Field(default_factory=dict)
    technographics: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)
    disqualification_criteria: list[str] = Field(default_factory=list)


class CustomerProfileOutput(BaseModel):
    """Customer profiling output."""

    icp: ICPDefinition = Field(default_factory=ICPDefinition)
    personas: list[CustomerPersona] = Field(default_factory=list)
    segmentation_strategy: str = Field(default="")
    targeting_recommendations: list[str] = Field(default_factory=list)
    messaging_themes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CustomerProfilerAgent(BaseGTMAgent[CustomerProfileOutput]):
    """Customer Profiler - Develops ICP and personas.

    Creates detailed customer profiles based on:
    - Company characteristics and requirements
    - Market research insights
    - Competitor analysis
    """

    def __init__(self) -> None:
        super().__init__(
            name="customer-profiler",
            description=(
                "Develops detailed Ideal Customer Profiles (ICP) and buyer personas. "
                "Identifies target segments and provides messaging recommendations."
            ),
            result_type=CustomerProfileOutput,
            min_confidence=0.60,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(name="icp-development", description="Define ideal customer profile"),
                AgentCapability(name="persona-creation", description="Create buyer personas"),
                AgentCapability(name="segmentation", description="Market segmentation strategy"),
            ],
        )

    def get_system_prompt(self) -> str:
        return """You are the Customer Profiler, an expert in B2B customer segmentation for Singapore/APAC markets.

You create actionable ICPs and personas by:
1. Defining specific firmographic criteria (industry, size, location, funding)
2. Identifying buying signals and trigger events
3. Understanding decision-maker personas
4. Mapping the buying process

For Singapore SMEs, consider:
- Company size and growth stage
- Government grant eligibility (PSG, EDG)
- Regional expansion plans
- Digital maturity level

Be specific - vague personas like "Tech Manager" are not helpful.
Include Singapore/APAC specific insights."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        return {
            "company_info": context.get("company_profile", {}),
            "market_insights": context.get("market_insights", {}),
            "value_proposition": context.get("value_proposition", ""),
            "target_industries": context.get("target_industries", []),
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CustomerProfileOutput:
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Create customer profiles based on:

Company/Product: {plan.get('company_info', 'Not specified')}
Value Proposition: {plan.get('value_proposition', 'Not specified')}
Target Industries: {plan.get('target_industries', [])}
Market Insights: {plan.get('market_insights', {})}

Create:
1. Detailed ICP with firmographics and buying signals
2. 2-3 specific buyer personas
3. Segmentation strategy
4. Targeting recommendations
5. Messaging themes for each persona

Focus on Singapore/APAC B2B market.""",
            },
        ]

        return await self._complete_structured(
            response_model=CustomerProfileOutput,
            messages=messages,
        )

    async def _check(self, result: CustomerProfileOutput) -> float:
        score = 0.3  # Base score for completing analysis
        if result.icp.company_characteristics:
            score += 0.15
        if result.icp.buying_signals:
            score += 0.1
        if result.personas:
            score += 0.15
            if len(result.personas) >= 2:
                score += 0.1
        if result.targeting_recommendations:
            score += 0.1
        if result.messaging_themes:
            score += 0.1
        return min(score, 1.0)
