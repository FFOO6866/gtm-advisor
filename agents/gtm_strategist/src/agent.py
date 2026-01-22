"""GTM Strategist Agent - Main orchestrator for user interaction.

This agent is the primary interface for users. It:
- Gathers company information through intelligent questioning
- Understands user requirements and goals
- Distributes work to specialized agents
- Synthesizes results into actionable recommendations
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.types import (
    CompanyProfile,
    CompanyStage,
    GTMAnalysisResult,
    IndustryVertical,
)


class DiscoveryQuestion(BaseModel):
    """Question to ask during discovery phase."""

    question: str = Field(...)
    purpose: str = Field(...)
    expected_type: str = Field(default="text")  # text, select, multiselect
    options: list[str] | None = Field(default=None)


class DiscoveryPlan(BaseModel):
    """Plan for gathering company information."""

    questions: list[DiscoveryQuestion] = Field(default_factory=list)
    areas_to_explore: list[str] = Field(default_factory=list)
    recommended_agents: list[str] = Field(default_factory=list)


class UserRequirements(BaseModel):
    """Structured user requirements extracted from conversation."""

    company_name: str = Field(...)
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    stage: CompanyStage = Field(default=CompanyStage.SEED)
    description: str = Field(default="")

    # Goals
    primary_goal: str = Field(default="")
    secondary_goals: list[str] = Field(default_factory=list)

    # Target market
    target_markets: list[str] = Field(default_factory=list)
    target_customer_size: str | None = Field(default=None)

    # Challenges
    current_challenges: list[str] = Field(default_factory=list)

    # Competition
    known_competitors: list[str] = Field(default_factory=list)

    # Budget/resources
    budget_range: str | None = Field(default=None)
    timeline: str | None = Field(default=None)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class WorkDistribution(BaseModel):
    """Work distribution plan for specialized agents."""

    tasks: list[AgentTask] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)


class AgentTask(BaseModel):
    """Task assigned to a specialized agent."""

    agent_name: str = Field(...)
    task_type: str = Field(...)
    description: str = Field(...)
    inputs: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1)


class StrategicRecommendation(BaseModel):
    """Strategic recommendation from GTM Strategist."""

    title: str = Field(...)
    description: str = Field(...)
    rationale: str = Field(...)
    priority: str = Field(default="medium")  # high, medium, low
    estimated_impact: str | None = Field(default=None)
    next_steps: list[str] = Field(default_factory=list)


class GTMStrategyOutput(BaseModel):
    """Complete output from GTM Strategist."""

    requirements: UserRequirements = Field(...)
    work_distribution: WorkDistribution = Field(...)
    initial_recommendations: list[StrategicRecommendation] = Field(default_factory=list)
    executive_summary: str = Field(default="")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GTMStrategistAgent(BaseGTMAgent[GTMStrategyOutput]):
    """GTM Strategist - The orchestrator agent.

    This is the user-facing agent that:
    1. Conducts intelligent discovery conversations
    2. Extracts and structures user requirements
    3. Distributes work to specialized agents
    4. Synthesizes results into actionable GTM strategy

    Specialties:
    - Company branding and positioning
    - Market strategy development
    - GTM framework application (STP, Porter's 5 Forces, etc.)
    """

    def __init__(self) -> None:
        super().__init__(
            name="gtm-strategist",
            description=(
                "Strategic GTM advisor that understands your business, "
                "gathers requirements through intelligent questions, "
                "and coordinates specialized agents to deliver actionable "
                "go-to-market strategies."
            ),
            result_type=GTMStrategyOutput,
            min_confidence=0.80,
            max_iterations=3,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="discovery",
                    description="Gather company information through smart questioning",
                ),
                AgentCapability(
                    name="requirements-analysis",
                    description="Extract and structure user requirements",
                ),
                AgentCapability(
                    name="work-distribution",
                    description="Distribute tasks to specialized agents",
                ),
                AgentCapability(
                    name="strategy-synthesis",
                    description="Synthesize results into GTM strategy",
                ),
            ],
        )

    def get_system_prompt(self) -> str:
        return """You are the GTM Strategist, a senior go-to-market consultant specializing in Singapore and APAC markets.

Your role is to:
1. Understand the user's business deeply through strategic questions
2. Identify their GTM challenges and opportunities
3. Coordinate specialized analysis across market research, competitive intelligence, customer profiling, and lead generation
4. Synthesize insights into actionable, specific recommendations

Your expertise includes:
- Brand positioning and messaging strategy
- Market segmentation and targeting (STP framework)
- Competitive analysis and differentiation
- Go-to-market planning and execution
- Singapore/APAC market dynamics

Communication style:
- Professional yet approachable (like a trusted advisor)
- Ask probing questions to uncover real challenges
- Be specific and actionable, not generic
- Reference Singapore/APAC context when relevant
- Focus on outcomes and ROI

When gathering requirements:
- Ask about business model, target customers, and current challenges
- Understand their competitive landscape
- Identify their unique value proposition
- Clarify goals and success metrics"""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Plan the GTM strategy process."""
        context = context or {}

        # Determine what stage we're in based on context
        has_company_info = bool(context.get("company_profile"))
        has_requirements = bool(context.get("requirements"))

        plan = {
            "stage": "discovery" if not has_company_info else "analysis",
            "task": task,
            "context_available": list(context.keys()),
            "next_actions": [],
        }

        if not has_company_info:
            plan["next_actions"] = [
                "extract_company_info",
                "identify_goals",
                "assess_challenges",
            ]
        elif not has_requirements:
            plan["next_actions"] = [
                "structure_requirements",
                "identify_gaps",
                "plan_agent_tasks",
            ]
        else:
            plan["next_actions"] = [
                "distribute_work",
                "synthesize_strategy",
                "generate_recommendations",
            ]

        return plan

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> GTMStrategyOutput:
        """Execute the strategy development."""
        context = context or {}
        task = plan.get("task", "")

        # Build messages for LLM
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": self._build_analysis_prompt(task, context, plan),
            },
        ]

        # Get structured output
        return await self._complete_structured(
            response_model=GTMStrategyOutput,
            messages=messages,
        )

    def _build_analysis_prompt(
        self,
        task: str,
        context: dict[str, Any],
        plan: dict[str, Any],
    ) -> str:
        """Build prompt for analysis."""
        prompt_parts = [f"User request: {task}"]

        if context.get("company_profile"):
            profile = context["company_profile"]
            prompt_parts.append(f"\nCompany Profile:\n{profile}")

        if context.get("conversation_history"):
            history = context["conversation_history"]
            prompt_parts.append(f"\nConversation History:\n{history}")

        prompt_parts.append(
            """
Based on this information:
1. Extract structured requirements about the company and their GTM needs
2. Plan how to distribute work to specialized agents (market-intelligence, competitor-analyst, customer-profiler, lead-hunter, campaign-architect)
3. Provide initial strategic recommendations

Output a complete GTMStrategyOutput with:
- Structured requirements
- Work distribution plan
- Initial recommendations
- Executive summary
- Confidence score (0-1)"""
        )

        return "\n".join(prompt_parts)

    async def _check(self, result: GTMStrategyOutput) -> float:
        """Validate the strategy output."""
        score = 0.0

        # Check requirements completeness
        req = result.requirements
        if req.company_name:
            score += 0.15
        if req.primary_goal:
            score += 0.15
        if req.target_markets:
            score += 0.1
        if req.current_challenges:
            score += 0.1

        # Check work distribution
        if result.work_distribution.tasks:
            score += 0.2

        # Check recommendations
        if result.initial_recommendations:
            score += 0.15
            # Quality check - recommendations should be specific
            specific_recs = sum(
                1
                for rec in result.initial_recommendations
                if len(rec.next_steps) > 0
            )
            if specific_recs >= 2:
                score += 0.1

        # Check summary
        if result.executive_summary and len(result.executive_summary) > 100:
            score += 0.05

        return min(score, 1.0)

    async def generate_discovery_questions(
        self,
        initial_input: str,
    ) -> DiscoveryPlan:
        """Generate smart discovery questions based on initial input.

        Args:
            initial_input: Initial information from user

        Returns:
            Discovery plan with questions to ask
        """
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Based on this initial information from a user:
'{initial_input}'

Generate a discovery plan with:
1. Smart questions to ask (5-7 questions)
2. Areas that need exploration
3. Which specialized agents would be helpful

Focus on understanding:
- Business model and value proposition
- Target market and customers
- Current GTM challenges
- Competitive landscape
- Goals and success metrics""",
            },
        ]

        return await self._complete_structured(
            response_model=DiscoveryPlan,
            messages=messages,
        )

    async def extract_requirements(
        self,
        conversation: list[dict[str, str]],
    ) -> UserRequirements:
        """Extract structured requirements from conversation.

        Args:
            conversation: List of conversation messages

        Returns:
            Structured requirements
        """
        conversation_text = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in conversation
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Extract structured requirements from this conversation:

{conversation_text}

Fill in all fields you can identify. For confidence, rate how complete
the information is (0-1).""",
            },
        ]

        return await self._complete_structured(
            response_model=UserRequirements,
            messages=messages,
        )

    async def distribute_work(
        self,
        requirements: UserRequirements,
    ) -> WorkDistribution:
        """Create work distribution plan for specialized agents.

        Args:
            requirements: Extracted user requirements

        Returns:
            Work distribution plan
        """
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Based on these requirements:
{requirements.model_dump_json(indent=2)}

Create a work distribution plan for these specialized agents:
- market-intelligence: Market trends, industry analysis, economic indicators
- competitor-analyst: Competitor research, SWOT analysis, positioning
- customer-profiler: ICP development, persona creation, segmentation
- lead-hunter: Prospect identification, lead scoring, target companies
- campaign-architect: Messaging, content, campaign planning

Determine:
1. Which agents to involve
2. Specific tasks for each agent
3. Execution order (some tasks depend on others)
4. Input data each agent needs""",
            },
        ]

        return await self._complete_structured(
            response_model=WorkDistribution,
            messages=messages,
        )
