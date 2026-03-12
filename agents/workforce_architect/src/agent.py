"""Workforce Architect Agent - Designs bespoke AI Digital Workforces.

Reads completed GTM analysis and produces a WorkforceDefinition: an AI agent
roster, value chain process map, and KPIs tailored to the client's business.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer


class AgentSpec(BaseModel):
    agent_type: str = Field(...)       # "outreach", "nurture", "content", "crm_sync", "monitor"
    agent_name: str = Field(...)       # display name, e.g. "Cold Outreach Agent"
    rationale: str = Field(...)        # why this client needs it
    primary_mcp: str = Field(...)      # "sendgrid", "hubspot", "internal"
    trigger: str = Field(...)          # "on_lead_qualified", "on_email_opened", "scheduled_daily"
    estimated_hours_saved_per_week: float = Field(default=0.0)

class ProcessStep(BaseModel):
    step_number: int = Field(...)
    name: str = Field(...)             # e.g. "Qualify lead from analysis"
    responsible_agent: str = Field(...) # maps back to AgentSpec.agent_type
    mcp_call: str | None = Field(default=None)  # e.g. "sendgrid.send_email"
    description: str = Field(default="")
    estimated_duration_seconds: int = Field(default=30)

class KPI(BaseModel):
    name: str = Field(...)
    target_value: float = Field(...)
    unit: str = Field(...)             # "%", "count/week", "SGD"
    measurement_source: str = Field(...) # "sendgrid", "hubspot", "internal"
    baseline_value: float = Field(default=0.0)

class WorkforceDefinition(BaseModel):
    agent_roster: list[AgentSpec] = Field(default_factory=list)
    value_chain: list[ProcessStep] = Field(default_factory=list)
    kpis: list[KPI] = Field(default_factory=list)
    executive_summary: str = Field(default="")
    estimated_weekly_hours_saved: float = Field(default=0.0)
    estimated_monthly_revenue_impact_sgd: float = Field(default=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

class WorkforceArchitectAgent(BaseGTMAgent[WorkforceDefinition]):
    """Workforce Architect - Designs the client's AI Digital Workforce.

    Transforms GTM analysis results into:
    - A tailored AI agent roster (which agents to deploy and why)
    - A value chain process map (step-by-step execution flow)
    - KPIs to track success
    """

    def __init__(self, bus: AgentBus | None = None) -> None:
        super().__init__(
            name="workforce-architect",
            description=(
                "Designs a bespoke AI Digital Workforce from completed GTM analysis. "
                "Proposes which AI agents to deploy, maps the value chain, and sets KPIs."
            ),
            result_type=WorkforceDefinition,
            min_confidence=0.65,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(name="workforce-design", description="Design AI agent roster"),
                AgentCapability(name="process-mapping", description="Map value chain processes"),
                AgentCapability(name="kpi-definition", description="Define success metrics"),
            ],
        )
        self._agent_bus = bus or get_agent_bus()
        self._analysis_id: str = ""
        self._campaign_context: dict[str, Any] | None = None
        self._lead_pipeline_size: int = 0
        self._bus_personas: list[dict[str, Any]] = []
        try:
            if self._agent_bus is not None:
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.CAMPAIGN_READY,
                    handler=self._on_campaign_ready,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.PERSONA_DEFINED,
                    handler=self._on_persona_defined,
                )
        except Exception:
            pass

    def get_system_prompt(self) -> str:
        return """You are the Workforce Architect, a specialist in designing AI Digital Workforces for Singapore B2B companies.

You transform GTM analysis into a practical, deployable AI agent team. You:
1. Propose only agents that are NECESSARY for the client's specific situation
2. Map a clear value chain with concrete process steps
3. Define measurable KPIs tied to real data sources (SendGrid stats, HubSpot deals)
4. Estimate realistic time savings and revenue impact for Singapore SMEs

Available agent types you can propose:
- "outreach": Sends personalised cold outreach emails via SendGrid
- "nurture": Manages follow-up sequences for leads that opened/clicked
- "content": Generates targeted content pieces (LinkedIn posts, case studies)
- "crm_sync": Creates/updates HubSpot contacts and deals automatically
- "monitor": Tracks campaign metrics and alerts on anomalies
- "scheduler": Books discovery calls via calendar integration

For each agent, specify a clear trigger (what starts it running).
Value chain steps must be sequential and reference specific agent types.
KPIs must be measurable from SendGrid or HubSpot APIs, not vague estimates.

Singapore context: Focus on PSG grant eligibility, APAC expansion narratives, direct ROI metrics."""

    async def _on_campaign_ready(self, message: AgentMessage) -> None:
        """Cache campaign context for workforce right-sizing."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        self._campaign_context = message.content
        self._logger.debug(
            "workforce_architect_received_campaign_context",
            sequence_count=self._campaign_context.get("sequence_count", 0),
        )

    async def _on_persona_defined(self, message: AgentMessage) -> None:
        """Accumulate persona definitions for workforce capacity planning."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        self._bus_personas.append(message.content)

    async def _plan(self, task: str, context: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id", "")

        # Backfill bus history for events published before this agent subscribed
        try:
            if self._agent_bus is not None:
                campaign_history = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.CAMPAIGN_READY,
                    limit=1,
                )
                if campaign_history:
                    self._campaign_context = campaign_history[0].content

                persona_history = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.PERSONA_DEFINED,
                    limit=5,
                )
                for msg in persona_history:
                    if msg.content not in self._bus_personas:
                        self._bus_personas.append(msg.content)

                lead_found_history = self._agent_bus.get_history(
                    analysis_id=self._analysis_id,
                    discovery_type=DiscoveryType.LEAD_FOUND,
                    limit=200,
                )
                self._lead_pipeline_size = len(lead_found_history)
        except Exception as e:
            self._logger.debug("workforce_bus_backfill_failed", error=str(e))

        return {
            "company_info": context.get("company_profile", context.get("company_name", "")),
            "personas": context.get("customer_personas", context.get("personas", [])),
            "leads": context.get("leads", []),
            "campaign_brief": context.get("campaign_brief", {}),
            "key_recommendations": context.get("key_recommendations", []),
            "industry": context.get("industry", ""),
            "value_proposition": context.get("value_proposition", ""),
        }

    async def _do(self, plan: dict[str, Any], context: dict[str, Any] | None = None, **kwargs: Any) -> WorkforceDefinition:
        company_info = plan.get("company_info", "Not specified")
        personas = plan.get("personas", [])
        leads = plan.get("leads", [])
        campaign_brief = plan.get("campaign_brief", {})
        key_recs = plan.get("key_recommendations", [])
        industry = plan.get("industry", "")
        value_prop = plan.get("value_proposition", "")

        # Format persona summary
        persona_summary = ""
        if personas:
            lines = []
            for p in personas[:3]:
                name = p.get("name") or p.get("title", "Unknown")
                role = p.get("role") or p.get("job_title", "")
                pain = p.get("pain_points", [])
                lines.append(f"  - {name} ({role}): {pain[:2] if pain else 'unknown pain points'}")
            persona_summary = "\nPersonas:\n" + "\n".join(lines)

        lead_count = len(leads)
        lead_industries = list({lead.get("industry", "") for lead in leads[:20] if lead.get("industry")})[:3]
        lead_summary = f"{lead_count} qualified leads"
        if lead_industries:
            lead_summary += f" in {', '.join(lead_industries)}"

        # --- Real data phase: KB frameworks + vertical benchmarks ---
        # Satisfies Rule #3: _do() must call at least one real data source.
        kb_guidance_lines: list[str] = []

        # Phase A: KnowledgeMCPServer — workforce design calibration from GTM/RACE frameworks
        try:
            kmcp = get_knowledge_mcp()
            race_fw = await kmcp.get_framework("RACE_FRAMEWORK")
            gtm_fw = await kmcp.get_framework("GTM_FRAMEWORKS")
            race_stages = list((race_fw.get("content") or {}).keys())
            gtm_motions = list((gtm_fw.get("content") or {}).keys())
            if race_stages:
                kb_guidance_lines.append(f"RACE execution stages to map: {', '.join(race_stages[:4])}")
            if gtm_motions:
                kb_guidance_lines.append(f"GTM motions to consider: {', '.join(gtm_motions[:3])}")
        except Exception as e:
            self._logger.debug("workforce_kb_frameworks_failed", error=str(e))

        # Phase B: MarketIntelMCPServer — vertical benchmarks for realistic KPI calibration
        vertical_slug = detect_vertical_slug(f"{industry} {value_prop}")
        if vertical_slug:
            try:
                async with async_session_factory() as db:
                    mcp_kb = MarketIntelMCPServer(session=db)
                    benchmarks = await mcp_kb.get_vertical_benchmarks(vertical_slug) or {}
                if benchmarks.get("company_count"):
                    kb_guidance_lines.append(
                        f"Vertical peer set: {benchmarks['company_count']} listed companies "
                        f"— calibrate hours-saved estimates against this market scale"
                    )
            except Exception as e:
                self._logger.debug("workforce_kb_benchmarks_failed", error=str(e))

        kb_context_str = "\n".join(kb_guidance_lines)
        self._kb_hit = bool(kb_guidance_lines)

        # Build pipeline context section from A2A bus data
        pipeline_context_lines: list[str] = []
        if self._campaign_context is not None:
            pipeline_context_lines.append(
                f"- Campaigns designed: {self._campaign_context.get('sequence_count', 0)} sequences, "
                f"{self._campaign_context.get('content_pieces_count', 0)} content pieces"
            )
        if self._bus_personas:
            pipeline_context_lines.append(f"- Target personas: {len(self._bus_personas)} identified")
        if self._lead_pipeline_size:
            pipeline_context_lines.append(
                f"- Lead pipeline: {self._lead_pipeline_size} leads discovered"
            )
        pipeline_context_str = ""
        if pipeline_context_lines:
            pipeline_context_str = (
                "\n\n## Pipeline Context\n"
                + "\n".join(pipeline_context_lines)
                + "\nUse this context to right-size the workforce (more leads = more outreach capacity needed)."
            )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""Design a Digital Workforce based on this completed GTM analysis:

Company: {company_info}
Industry: {industry}
Value Proposition: {value_prop}{persona_summary}
Qualified Leads: {lead_summary}
Key GTM Recommendations: {key_recs[:3] if key_recs else 'Not specified'}
Campaign Brief: {str(campaign_brief)[:500] if campaign_brief else 'Not available'}

Design a Digital Workforce that will EXECUTE the GTM strategy:
1. Agent Roster: 3-5 agents with clear triggers and rationale
2. Value Chain: 6-10 sequential process steps mapping lead → revenue
3. KPIs: 4-6 measurable metrics (email open rate, demos booked, deals created, etc.)
4. Executive Summary: 2-3 sentence overview
5. Estimate: Weekly hours saved and monthly revenue impact (be conservative, base on lead count)

Only propose agents that make sense for this specific company and lead pipeline."""
                + pipeline_context_str
                + (f"\n\nKB Calibration:\n{kb_context_str}" if kb_context_str else ""),
            },
        ]

        return await self._complete_structured(
            response_model=WorkforceDefinition,
            messages=messages,
        )

    async def _check(self, result: WorkforceDefinition) -> float:
        score = 0.2  # base

        if len(result.agent_roster) >= 2:
            score += 0.15
        if len(result.agent_roster) >= 3:
            score += 0.05
        if len(result.value_chain) >= 5:
            score += 0.15
        if result.kpis:
            score += 0.15
        if result.executive_summary and len(result.executive_summary) > 50:
            score += 0.10
        if result.estimated_weekly_hours_saved > 0:
            score += 0.05
        # Diversity: at least 2 different agent types
        agent_types = {spec.agent_type for spec in result.agent_roster}
        if len(agent_types) >= 2:
            score += 0.10

        # KB grounding bonus — frameworks ground workforce design in proven methodology
        if getattr(self, "_kb_hit", False):
            score += 0.05

        return min(score, 1.0)

    async def _act(self, result: WorkforceDefinition, confidence: float) -> WorkforceDefinition:
        result.confidence = confidence
        # Clamp LLM-generated estimates to realistic Singapore SME bounds
        # (max 168h/week total, max SGD 1M/month revenue impact for an SME)
        result.estimated_weekly_hours_saved = min(result.estimated_weekly_hours_saved, 168.0)
        result.estimated_monthly_revenue_impact_sgd = min(
            result.estimated_monthly_revenue_impact_sgd, 1_000_000.0
        )
        self._logger.info(
            "workforce_designed",
            kb_used=getattr(self, "_kb_hit", False),
            company=str(self._current_state.plan.get("company_info", "") if self._current_state and self._current_state.plan else "")[:50],
        )

        # Publish WORKFORCE_READY so execution agents (Outreach Executor, CRM Sync) can react
        try:
            roi_multiplier: float | None = None
            for kpi in result.kpis:
                if "roi" in kpi.name.lower() or "revenue" in kpi.name.lower():
                    baseline = kpi.baseline_value or 1.0
                    if baseline > 0:
                        roi_multiplier = round(kpi.target_value / baseline, 2)
                    break

            await self._agent_bus.publish(
                from_agent=self.name,
                discovery_type=DiscoveryType.WORKFORCE_READY,
                title=f"Workforce design ready: {len(result.agent_roster)} agents",
                content={
                    "agent_count": len(result.agent_roster),
                    "process_steps": len(result.value_chain),
                    "kpi_count": len(result.kpis),
                    "approved_agents": [spec.agent_name for spec in result.agent_roster],
                    "estimated_roi_multiplier": roi_multiplier,
                },
                analysis_id=self._analysis_id,
                confidence=confidence,
            )
        except Exception as e:
            self._logger.warning("workforce_ready_publish_failed", error=str(e))

        return result
