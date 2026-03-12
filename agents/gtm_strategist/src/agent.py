"""GTM Strategist Agent - Main orchestrator for user interaction.

This agent is the primary interface for users. It:
- Gathers company information through intelligent questioning
- Understands user requirements and goals
- Distributes work to specialized agents
- Synthesizes results into actionable recommendations
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from agents.core.src.mcp_integration import AgentMCPClient
from packages.core.src.agent_bus import AgentBus, DiscoveryType, get_agent_bus
from packages.core.src.types import (
    CompanyStage,
    IndustryVertical,
)
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer


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


class MarketSizing(BaseModel):
    """TAM/SAM/SOM market size estimates."""

    tam_description: str = Field(default="")  # Total Addressable Market narrative
    sam_description: str = Field(default="")  # Serviceable Addressable Market
    som_description: str = Field(default="")  # Serviceable Obtainable Market (Year 1)
    tam_sgd_estimate: str | None = Field(default=None)  # e.g. "SGD 500M–2B"
    sam_sgd_estimate: str | None = Field(default=None)  # e.g. "SGD 50M–200M"
    som_sgd_estimate: str | None = Field(default=None)  # e.g. "SGD 2M–10M (Year 1)"
    assumptions: list[str] = Field(default_factory=list)


class SalesMotion(BaseModel):
    """Sales motion architecture — how to actually sell."""

    primary_motion: str = Field(default="")  # "PLG" | "SLG" | "Channel" | "Hybrid"
    deal_size_sgd: str = Field(default="")  # e.g. "SGD 5k–30k ACV"
    sales_cycle_days: int | None = Field(default=None)  # Typical days from first touch to close
    quota_per_rep_sgd: str | None = Field(default=None)  # e.g. "SGD 500k ARR per rep"
    key_objections: list[str] = Field(default_factory=list)
    win_themes: list[str] = Field(default_factory=list)  # Why you win vs. competition
    loss_themes: list[str] = Field(default_factory=list)  # Why you lose
    recommended_first_90_days: list[str] = Field(default_factory=list)  # Concrete action steps


class GTMStrategyOutput(BaseModel):
    """Complete output from GTM Strategist."""

    requirements: UserRequirements = Field(...)
    work_distribution: WorkDistribution = Field(...)
    initial_recommendations: list[StrategicRecommendation] = Field(default_factory=list)
    executive_summary: str = Field(default="")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=False)  # True only if >=1 real API succeeded
    market_sizing: MarketSizing | None = Field(default=None)
    sales_motion: SalesMotion | None = Field(default=None)


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

    def __init__(
        self,
        agent_bus: AgentBus | None = None,
        analysis_id: UUID | None = None,
    ) -> None:
        super().__init__(
            name="gtm-strategist",
            description=(
                "Strategic GTM advisor that understands your business, "
                "gathers requirements through intelligent questions, "
                "and coordinates specialized agents to deliver actionable "
                "go-to-market strategies."
            ),
            result_type=GTMStrategyOutput,
            min_confidence=0.65,
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
        self._mcp = AgentMCPClient()
        self._agent_bus = agent_bus or get_agent_bus()
        self._analysis_id: UUID | None = analysis_id

        # Bus backfill caches — populated in _plan()
        self._campaign_summary: dict | None = None
        self._bus_leads: list[dict] = []
        self._bus_personas: list[dict] = []
        # Vertical slug captured during _do() for COMPANY_PROFILE publish
        self._vertical_slug: str = ""

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

        # Load domain knowledge pack — injected into _do() synthesis prompt.
        kmcp = get_knowledge_mcp()
        self._knowledge_pack = await kmcp.get_agent_knowledge_pack(
            agent_name="gtm-strategist",
            task_context=task,
        )

        # Load live Singapore reference data (PSG grants, PDPA rules, market stats)
        self._sg_reference = await kmcp.get_sg_reference(
            query=f"Singapore SME grants PSG EDG PDPA {task[:200]}",
            limit=4,
        )

        # Capture analysis_id for bus publishing scope
        if context.get("analysis_id"):
            self._analysis_id = context["analysis_id"]

        # Determine what stage we're in based on context
        has_company_info = bool(context.get("company_name") or context.get("description"))
        has_requirements = bool(context.get("goals") or context.get("value_proposition"))

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

        # ── A2A backfill: pull downstream discoveries so the orchestrator can
        # synthesize results from specialist agents into its own output. ──────
        if self._agent_bus is not None:
            try:
                campaign_msgs = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.CAMPAIGN_READY,
                    limit=1,
                )
                self._campaign_summary = campaign_msgs[0].content if campaign_msgs else None
            except Exception as e:
                self._logger.debug("bus_backfill_campaign_failed", error=str(e))

            try:
                lead_msgs = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.LEAD_FOUND,
                    limit=5,
                )
                self._bus_leads = [m.content for m in lead_msgs]
            except Exception as e:
                self._logger.debug("bus_backfill_leads_failed", error=str(e))

            try:
                persona_msgs = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.PERSONA_DEFINED,
                    limit=3,
                )
                self._bus_personas = [m.content for m in persona_msgs]
            except Exception as e:
                self._logger.debug("bus_backfill_personas_failed", error=str(e))

        return plan

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> GTMStrategyOutput:
        """Execute the strategy development, grounded in real company + market data."""
        context = context or {}
        task = plan.get("task", "")
        company_name = context.get("company_name", "")
        industry = context.get("industry", "")
        website = context.get("website", "")

        # ── Real data phase ─────────────────────────────────────────────────
        real_facts: list[str] = []
        self._real_data_count = 0
        data_sources_used: list[str] = []

        try:
            # 1. Look up the company in real databases (ACRA, web scraper, news)
            if company_name:
                company_facts = await self._mcp.get_company_info(
                    company_name=company_name,
                    website=website or None,
                )
                for fact in company_facts[:10]:
                    real_facts.append(f"[{fact.source_name}] {fact.claim}")
                    if fact.source_name and fact.source_name not in data_sources_used:
                        data_sources_used.append(fact.source_name)
                self._real_data_count += len(company_facts)

            # 2. Research the industry/market landscape in Singapore
            if industry or company_name:
                _vp = context.get("value_proposition", "") or context.get("description", "")
                _vp_short = _vp[:120].rsplit(" ", 1)[0] if len(_vp) > 120 else _vp
                if company_name and _vp_short:
                    topic = f"{company_name}: {_vp_short} — market opportunities Singapore APAC"
                elif company_name:
                    topic = f"{company_name} — {industry or 'technology'} market opportunities Singapore"
                else:
                    topic = f"{industry} market opportunities Singapore APAC"
                market_facts = await self._mcp.research_topic(
                    topic=topic,
                    industry=industry or None,
                    region="Singapore",
                    limit=15,
                )
                for fact in market_facts[:10]:
                    real_facts.append(f"[{fact.source_name}] {fact.claim}")
                    if fact.source_name and fact.source_name not in data_sources_used:
                        data_sources_used.append(fact.source_name)
                self._real_data_count += len(market_facts)
        except Exception as e:
            self._logger.warning("mcp_data_fetch_failed", error=str(e))
            # Degrade gracefully — LLM still runs, just without real-data grounding

        # ── KB enrichment — vertical landscape + GTM frameworks ──────────────
        kb_vertical_data: dict[str, Any] = {}
        industry_str = (
            str(plan.get("company_info", {}).get("industry", "")) + " " + task
            if isinstance(plan.get("company_info"), dict)
            else task
        )
        vertical_slug = detect_vertical_slug(industry_str)
        self._vertical_slug = vertical_slug or ""
        if vertical_slug:
            try:
                async with async_session_factory() as db:
                    mcp_kb = MarketIntelMCPServer(session=db)
                    kb_vertical_data = await mcp_kb.get_vertical_landscape(vertical_slug) or {}
            except Exception as e:
                self._logger.debug("kb_gtm_enrichment_failed", error=str(e))

        if kb_vertical_data:
            leaders = [
                c.get("name", "")
                for c in kb_vertical_data.get("leaders", [])[:3]
                if c.get("name")
            ]
            if leaders:
                real_facts.append(f"Market leaders in {vertical_slug}: {', '.join(leaders)}")
                if "Market Intel DB" not in data_sources_used:
                    data_sources_used.append("Market Intel DB")

        # GTM motion frameworks + Singapore context from knowledge library (static, always available)
        try:
            kmcp = get_knowledge_mcp()
            sg_ctx = await kmcp.get_singapore_context()
            gtm_fw = await kmcp.get_framework("GTM_FRAMEWORKS")
            motions = list((gtm_fw.get("content") or {}).keys())
            if motions:
                real_facts.append(f"Proven GTM motions to consider: {', '.join(motions)}")
            sg_facts = sg_ctx.get("content", {})
            if sg_facts:
                grants = sg_facts.get("government_grants", {})
                if grants:
                    grant_names = list(grants.keys())[:3]
                    real_facts.append(
                        f"Singapore funding/grants relevant to SME GTM: {', '.join(grant_names)}"
                    )
            if motions or sg_facts:
                if "Knowledge MCP" not in data_sources_used:
                    data_sources_used.append("Knowledge MCP")
        except Exception as e:
            self._logger.debug("knowledge_mcp_gtm_failed", error=str(e))

        # ── Inject real data into the prompt ─────────────────────────────────
        real_data_section = ""
        if real_facts:
            real_data_section = (
                "\n\nREAL DATA FETCHED FROM LIVE SOURCES (use this to ground your analysis):\n"
                + "\n".join(f"- {f}" for f in real_facts[:20])
                + "\n\nBase your recommendations on the above real data, not assumptions."
            )

        # Stash for _act() to inject into the final result
        self._data_sources_used = data_sources_used

        # ── A2A context: append downstream discoveries so synthesis is informed ──
        a2a_parts: list[str] = []
        if self._campaign_summary:
            a2a_parts.append(
                f"Campaign ready: {self._campaign_summary.get('campaign_name', '')} — "
                f"{self._campaign_summary.get('primary_message', '')}"
            )
        if self._bus_leads:
            lead_names = [
                ld.get("company_name") or ld.get("lead_name") or ld.get("title", "")
                for ld in self._bus_leads[:5]
            ]
            a2a_parts.append(f"Leads found: {', '.join(n for n in lead_names if n)}")
        if self._bus_personas:
            persona_names = [
                p.get("name") or p.get("persona_name") or p.get("title", "")
                for p in self._bus_personas[:3]
            ]
            a2a_parts.append(f"Personas defined: {', '.join(n for n in persona_names if n)}")
        if a2a_parts:
            real_data_section += (
                "\n\nA2A CONTEXT FROM SPECIALIST AGENTS (incorporate into synthesis):\n"
                + "\n".join(f"- {p}" for p in a2a_parts)
            )

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        _sg_ref = getattr(self, "_sg_reference", [])
        _sg_context = ""
        if _sg_ref:
            _sg_context = "\n\n--- LIVE SINGAPORE REFERENCE DATA ---\n" + "\n".join(
                f"• {r['title']}: {r.get('summary', '')[:300]}" for r in _sg_ref
            ) + "\n---"
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": _knowledge_header
                + self._build_analysis_prompt(task, context, plan)
                + real_data_section
                + _sg_context,
            },
        ]

        result = await self._complete_structured(
            response_model=GTMStrategyOutput,
            messages=messages,
        )

        # Set is_live_data and data_sources_used before returning so _check() can use them.
        # _act() will overwrite with the same values, but _check() runs before _act().
        is_live_data = self._real_data_count > 0
        if kb_vertical_data and "Market Intel DB" not in data_sources_used:
            data_sources_used.append("Market Intel DB")
            # KB is a daily-synced snapshot — do NOT count as live data
        result.is_live_data = is_live_data
        result.data_sources_used = data_sources_used

        return result

    def _build_analysis_prompt(
        self,
        task: str,
        context: dict[str, Any],
        plan: dict[str, Any],
    ) -> str:
        """Build prompt for analysis."""
        prompt_parts = [f"User request: {task}"]

        if context.get("company_name"):
            prompt_parts.append(f"\nCompany: {context['company_name']}")
            if context.get("description"):
                prompt_parts.append(f"Description: {context['description']}")
            if context.get("industry"):
                prompt_parts.append(f"Industry: {context['industry']}")
            if context.get("value_proposition"):
                prompt_parts.append(f"Value Proposition: {context['value_proposition']}")
            if context.get("goals"):
                prompt_parts.append(f"Goals: {context['goals']}")
            if context.get("current_challenges"):
                prompt_parts.append(f"Challenges: {context['current_challenges']}")

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
- Confidence score (0-1)

Also provide:
1. MARKET SIZING (TAM/SAM/SOM) for Singapore/APAC:
   CRITICAL: Provide numeric estimates ONLY if the REAL DATA FETCHED section above contains
   market size figures, growth rates, or industry benchmarks from cited sources.
   If such data is NOT present, write "Market sizing requires additional research —
   data not available in current sources" for each field.
   Do NOT invent TAM/SAM/SOM figures. Invented market sizes give founders false confidence.
   - TAM: Total addressable market (cite source if available)
   - SAM: Serviceable addressable market (cite source if available)
   - SOM: Realistic Year 1 target (derive from company team size and motion, not market data)
   - List any assumptions made

2. SALES MOTION ARCHITECTURE:
   - Primary motion: PLG (Product-Led), SLG (Sales-Led), Channel, or Hybrid — choose ONE and explain why based on the product description
   - Typical deal size in SGD ACV (estimate from value proposition if no data; label as "estimated")
   - Sales cycle length in days for SME vs Enterprise (derive from product complexity; label as "estimated")
   - Top 3 objections prospects will raise + how to handle each (derive from competitive landscape and product)
   - Top 3 reasons you win vs competition (derive from differentiators in the description)
   - First 90-day action plan (5–7 specific steps with owners)"""
        )

        return "\n".join(prompt_parts)

    async def _check(self, result: GTMStrategyOutput) -> float:
        """Validate the strategy output. Confidence is gated on real data to prevent LLM gaming."""
        score = 0.20  # Base

        # Only award real-data bonus if live data was actually fetched
        if result.is_live_data:
            score += 0.15  # Live data bonus

        # Structure bonuses (capped lower than before to prevent LLM gaming)
        if result.requirements and result.requirements.company_name:
            score += 0.10
        if result.initial_recommendations:
            score += min(len(result.initial_recommendations) * 0.05, 0.15)
        if result.market_sizing and result.market_sizing.tam_sgd_estimate:
            score += 0.10
        if result.sales_motion and result.sales_motion.primary_motion:
            score += 0.10
        if result.work_distribution and result.work_distribution.tasks:
            score += 0.10

        return min(score, 0.90)  # Cap at 0.90 — never perfect without CRM/real validation

    async def _act(self, result: GTMStrategyOutput, confidence: float) -> GTMStrategyOutput:
        """Stamp confidence and data provenance onto the result, then publish to bus."""
        result.confidence = confidence
        data_sources = getattr(self, "_data_sources_used", [])
        result.data_sources_used = data_sources
        # is_live_data was already set correctly in _do() (MCP real_data_count only).
        # Do NOT recompute here — KB ("Market Intel DB") in data_sources is daily-synced,
        # not live, so len(data_sources) > 0 would give a false positive.

        # Publish enriched company profile so Competitor Analyst + Customer Profiler can use it
        if self._agent_bus is not None and result.requirements and result.requirements.company_name:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.COMPANY_PROFILE,
                    title=f"Company Profile: {result.requirements.company_name}",
                    content={
                        "company_name": result.requirements.company_name,
                        "industry": result.requirements.industry.value
                        if result.requirements.industry
                        else "",
                        "target_market": (
                            ", ".join(result.requirements.target_markets)
                            if result.requirements.target_markets
                            else ""
                        ),
                        "company_size": result.requirements.target_customer_size or "",
                        "geography": "Singapore",
                        "vertical": self._vertical_slug,
                        "key_offerings": [],
                        "analysis_id": str(self._analysis_id) if self._analysis_id else "",
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.debug("bus_publish_company_profile_failed", error=str(e))

        # Publish market sizing and sales motion to bus so downstream agents can use them
        if self._agent_bus is not None and result.market_sizing and result.sales_motion:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.MARKET_TREND,
                    title=(
                        f"Market Sizing: "
                        f"{result.requirements.company_name if result.requirements else 'Company'}"
                    ),
                    content={
                        "tam_sgd_estimate": result.market_sizing.tam_sgd_estimate,
                        "sam_sgd_estimate": result.market_sizing.sam_sgd_estimate,
                        "som_sgd_estimate": result.market_sizing.som_sgd_estimate,
                        "primary_motion": (
                            result.sales_motion.primary_motion if result.sales_motion else ""
                        ),
                        "deal_size_sgd": (
                            result.sales_motion.deal_size_sgd if result.sales_motion else ""
                        ),
                        "sales_cycle_days": (
                            result.sales_motion.sales_cycle_days if result.sales_motion else None
                        ),
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.debug("bus_publish_market_sizing_failed", error=str(e))

        return result

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
        conversation_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in conversation)

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
