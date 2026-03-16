"""Campaign Architect Agent - Messaging and campaign planning.

Creates actionable campaign plans with messaging, content, and outreach templates.
Pulls LEAD_FOUND and PERSONA_DEFINED history from the bus to personalize campaigns.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.algorithms.src.scoring import MessageAlignmentScorer
from packages.core.src.agent_bus import AgentBus, DiscoveryType
from packages.core.src.types import CampaignBrief
from packages.core.src.vertical import detect_vertical_slug
from packages.database.src.session import async_session_factory
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.llm.src import get_llm_manager
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer


class MessagingFramework(BaseModel):
    """Messaging framework for campaigns."""

    value_proposition: str = Field(...)
    key_messages: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    objection_handling: dict[str, str] = Field(default_factory=dict)
    tone_and_voice: str = Field(default="")


class ContentPiece(BaseModel):
    """A content piece for the campaign."""

    type: str = Field(...)  # email, linkedin, blog, case_study
    title: str = Field(...)
    content: str = Field(...)
    target_persona: str | None = Field(default=None)
    call_to_action: str | None = Field(default=None)


class SequenceStep(BaseModel):
    """One step in a multi-touch outreach sequence."""

    day: int = Field(..., ge=1)  # Day offset from sequence start (1, 3, 7, 10, 14...)
    channel: str = Field(...)  # "email" | "linkedin_message" | "linkedin_connect" | "phone" | "sms"
    action: str = Field(...)  # "initial_outreach" | "follow_up" | "value_add" | "breakup"
    subject_line: str = Field(default="")  # Email subject / LinkedIn message opener
    body_preview: str = Field(default="")  # First 150 chars of message content
    condition: str = Field(default="none")  # "none" | "if_no_reply" | "if_opened" | "if_clicked"
    persona_target: str | None = Field(default=None)  # Which persona this step targets


class OutreachSequence(BaseModel):
    """Multi-touch outreach sequence across channels with timing."""

    name: str = Field(...)
    total_days: int = Field(default=14)
    steps: list[SequenceStep] = Field(default_factory=list)
    expected_reply_rate: str = Field(default="")  # e.g. "8-12% for cold outreach in SaaS"
    ab_variant: str = Field(default="A")  # "A" or "B" for A/B testing


class CampaignPlanOutput(BaseModel):
    """Complete campaign plan."""

    campaign_brief: CampaignBrief = Field(...)
    messaging_framework: MessagingFramework = Field(...)
    content_pieces: list[ContentPiece] = Field(default_factory=list)
    outreach_sequences: list[OutreachSequence] = Field(default_factory=list)
    channel_strategy: dict[str, str] = Field(default_factory=dict)
    timeline_recommendations: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=False)  # True if bus had personas OR leads
    compliance_flags: list[str] = Field(default_factory=list)


class CampaignArchitectAgent(BaseGTMAgent[CampaignPlanOutput]):
    """Campaign Architect - Creates actionable campaign plans.

    Develops:
    - Messaging frameworks
    - Email templates
    - LinkedIn content
    - Outreach sequences
    """

    def __init__(self, bus: AgentBus | None = None) -> None:
        super().__init__(
            name="campaign-architect",
            description=(
                "Creates actionable marketing and outreach campaigns. "
                "Develops messaging, content, and multi-channel strategies "
                "tailored to your target audience."
            ),
            result_type=CampaignPlanOutput,
            min_confidence=0.60,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="messaging-development", description="Create messaging frameworks"
                ),
                AgentCapability(name="content-creation", description="Generate campaign content"),
                AgentCapability(name="channel-strategy", description="Plan multi-channel approach"),
            ],
        )
        self._bus = bus
        self._bus_personas: list[dict[str, Any]] = []
        self._bus_leads: list[dict[str, Any]] = []
        self._bus_competitor_weaknesses: list[dict[str, Any]] = []
        self._current_analysis_id: Any = None
        self._perplexity = get_llm_manager().perplexity

    def get_system_prompt(self) -> str:
        return """You are the Campaign Architect, an expert in B2B marketing for Singapore/APAC markets.

You create ACTIONABLE campaigns with:
1. Clear, differentiated messaging
2. Ready-to-use email templates
3. LinkedIn content and outreach messages
4. Multi-channel strategies

For Singapore B2B:
- Direct, professional communication style
- Reference local context (PSG grants, APAC expansion)
- Focus on ROI and efficiency
- Consider relationship-based selling culture

Provide COMPLETE content - not placeholders.
Templates should be ready to personalize and send."""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        analysis_id = context.get("analysis_id")

        # Load domain knowledge pack — injected into _do() synthesis prompt.
        kmcp = get_knowledge_mcp()
        self._knowledge_pack = await kmcp.get_agent_knowledge_pack(
            agent_name="campaign-architect",
            task_context=task,
        )

        # Load live Singapore reference data (PDPA rules, grant eligibility for campaign compliance)
        self._sg_reference = await kmcp.get_sg_reference(
            query=f"PDPA compliance Singapore B2B email marketing {task[:200]}",
            limit=3,
        )

        # Reset per-run accumulation to prevent cross-analysis contamination.
        # Bus history (scoped by analysis_id) is the authoritative source.
        self._bus_personas.clear()
        self._bus_leads.clear()
        self._bus_competitor_weaknesses.clear()
        self._current_analysis_id = analysis_id

        # Pull personas and leads from bus history (supplementing any live subscriptions)
        bus_personas: list[dict[str, Any]] = []
        bus_leads: list[dict[str, Any]] = []

        if self._bus is not None:
            seen_persona_titles: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.PERSONA_DEFINED,
                limit=5,
            ):
                key = msg.title
                if key not in seen_persona_titles:
                    seen_persona_titles.add(key)
                    bus_personas.append({"title": msg.title, **msg.content})

            seen_lead_titles: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.LEAD_FOUND,
                limit=20,
            ):
                key = msg.title
                if key not in seen_lead_titles:
                    seen_lead_titles.add(key)
                    bus_leads.append({"title": msg.title, **msg.content})

            bus_weaknesses: list[dict[str, Any]] = []
            seen_weakness_titles: set[str] = set()
            for msg in self._bus.get_history(
                analysis_id=analysis_id,
                discovery_type=DiscoveryType.COMPETITOR_WEAKNESS,
                limit=10,
            ):
                key = msg.title
                if key not in seen_weakness_titles:
                    seen_weakness_titles.add(key)
                    bus_weaknesses.append({"title": msg.title, **msg.content})
            self._bus_competitor_weaknesses.extend(bus_weaknesses)

        # Repopulate instance lists from history pull so _check() grounding bonus works.
        # Bus history pull is the authoritative data source for personas and leads.
        self._bus_personas.extend(bus_personas)
        self._bus_leads.extend(bus_leads)

        # Merge with context data (bus data takes precedence if available)
        personas = bus_personas or context.get("personas", [])
        leads = bus_leads or context.get("leads", [])

        # --- KB Phase 1: Market vertical landscape ---
        kb_vertical_context: dict[str, Any] = {}
        kb_vertical_benchmarks: dict[str, Any] = {}
        kb_vertical_intel: dict[str, Any] = {}
        industry_text = context.get("industry", "") or context.get("description", "")
        vertical_slug = detect_vertical_slug(industry_text)
        if vertical_slug:
            try:
                async with async_session_factory() as db:
                    mcp = MarketIntelMCPServer(session=db)
                    kb_vertical_context = await mcp.get_vertical_landscape(vertical_slug) or {}
                    kb_vertical_benchmarks = await mcp.get_vertical_benchmarks(vertical_slug) or {}
                    kb_vertical_intel = await mcp.get_vertical_intelligence(vertical_slug) or {}
            except Exception as e:
                self._logger.debug("kb_campaign_enrichment_failed", error=str(e))

        # --- KB Phase 2: Marketing knowledge frameworks (static, always available) ---
        kb_messaging_framework: dict[str, Any] = {}
        kb_cialdini_principles: list[dict] = []
        campaign_goal = context.get("goals") or "lead generation"
        try:
            kmcp = get_knowledge_mcp()
            msg_fw = await kmcp.get_messaging_framework(f"cold outreach {campaign_goal}")
            kb_messaging_framework = {
                "recommended": msg_fw.get("recommended_framework", "PAS"),
                "rationale": msg_fw.get("rationale", ""),
                "stages": (msg_fw.get("framework_content") or {}).get("stages", []),
                "best_for": (msg_fw.get("framework_content") or {}).get("best_for", ""),
            }
            cialdini = await kmcp.get_framework("CIALDINI_PRINCIPLES")
            principles = cialdini.get("content") or {}
            for key in ("reciprocity", "social_proof", "scarcity"):
                p = principles.get(key, {})
                if p:
                    kb_cialdini_principles.append({
                        "principle": key,
                        "sg_angle": p.get("sg_angle", ""),
                        "best_for": p.get("best_for", []),
                    })
        except Exception as e:
            self._logger.debug("knowledge_mcp_failed", error=str(e))

        return {
            "company_info": context.get("company_profile") or {
                "company_name": context.get("company_name", ""),
                "description": context.get("description", ""),
                "industry": context.get("industry", ""),
                "target_markets": context.get("target_markets", []),
            },
            "company_name": context.get("company_name", ""),
            "known_competitors": context.get("known_competitors", []),
            "personas": personas,
            "leads": leads,
            "competitor_weaknesses": list(self._bus_competitor_weaknesses),
            "value_proposition": context.get("value_proposition", ""),
            "campaign_goal": campaign_goal,
            "kb_vertical_context": kb_vertical_context,
            "kb_vertical_benchmarks": kb_vertical_benchmarks,
            "kb_vertical_intel": kb_vertical_intel,
            "kb_messaging_framework": kb_messaging_framework,
            "kb_cialdini_principles": kb_cialdini_principles,
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CampaignPlanOutput:
        personas = plan.get("personas", [])
        leads = plan.get("leads", [])
        competitor_weaknesses = plan.get("competitor_weaknesses", [])

        # --- Phase 0: Live competitor messaging research via Perplexity ---
        competitor_messaging_intel: str = ""
        known_competitors = plan.get("known_competitors", [])
        if known_competitors and self._perplexity is not None:
            try:
                industry_label = plan.get("industry", "B2B")
                current_year = datetime.now().year
                query = (
                    f"Current messaging, positioning, and pricing of these {industry_label} competitors "
                    f"in Singapore/APAC: {', '.join(known_competitors[:3])}. "
                    f"What are their main value propositions and outreach strategies in {current_year}?"
                )
                research = await self._perplexity.research_market_with_citations(
                    topic=query,
                    region=f"Singapore {industry_label}",
                )
                if research and research.text:
                    competitor_messaging_intel = research.text[:800]
            except Exception as e:
                self._logger.debug("campaign_architect_perplexity_failed", error=str(e))

        self._has_live_intel = bool(competitor_messaging_intel)

        # Extract KB vertical context surfaced during _plan()
        kb_vertical_context = plan.get("kb_vertical_context", {})
        self._kb_vertical_hit = bool(kb_vertical_context)
        kb_vertical_str = ""
        if kb_vertical_context:
            leaders = [c.get("name", "") for c in kb_vertical_context.get("leaders", [])[:3] if c.get("name")]
            trends = kb_vertical_context.get("top_signals", [])[:2]
            if leaders:
                kb_vertical_str = f"\n\nMarket Leaders in Vertical: {', '.join(leaders)}"
            if trends:
                kb_vertical_str += f"\nLatest Market Signals: {'; '.join(str(t) for t in trends)}"

        # Vertical intelligence — data-backed messaging angles from EODHD + documents
        kb_vertical_intel = plan.get("kb_vertical_intel", {})
        vi_context = ""
        if kb_vertical_intel:
            vi_lines: list[str] = []
            # GTM implications = pre-computed messaging angles from financial data
            gtm_impl = kb_vertical_intel.get("gtm_implications") or []
            if gtm_impl:
                vi_lines.append("Data-Backed Messaging Angles (from financial analysis):")
                for impl in gtm_impl[:4]:
                    insight = impl.get("insight", str(impl)) if isinstance(impl, dict) else str(impl)
                    vi_lines.append(f"  - {insight[:250]}")
            # Competitive dynamics — who's investing in GTM
            comp_dyn = kb_vertical_intel.get("competitive_dynamics") or {}
            gtm_investors = comp_dyn.get("gtm_investors", [])
            if gtm_investors:
                investor_names = [
                    g.get("name", str(g)) if isinstance(g, dict) else str(g)
                    for g in gtm_investors[:3]
                ]
                vi_lines.append(f"Companies investing heavily in GTM: {', '.join(investor_names)}")
            # Financial pulse — SG&A trends for budget framing
            fin_pulse = kb_vertical_intel.get("financial_pulse") or {}
            sga_median = fin_pulse.get("sga_median")
            if isinstance(sga_median, (int, float)) and sga_median > 0:
                vi_lines.append(
                    f"Industry median marketing spend: {sga_median*100:.1f}% of revenue"
                    " — use for budget framing in messaging"
                )
            if vi_lines:
                vi_context = (
                    "\n\n--- VERTICAL INTELLIGENCE (EODHD + annual reports) ---\n"
                    + "\n".join(vi_lines)
                )
        self._kb_vertical_intel_hit = bool(vi_context)

        # Vertical benchmarks — industry-level financial distributions for social proof
        kb_vertical_benchmarks = plan.get("kb_vertical_benchmarks", {})
        bench_context = ""
        if kb_vertical_benchmarks:
            dist = kb_vertical_benchmarks.get("distributions") or {}
            growth_dist = dist.get("revenue_growth_yoy") or {}
            growth_p50 = growth_dist.get("p50")
            if growth_p50 is not None:
                bench_context += f"\nIndustry median revenue growth: {growth_p50*100:.1f}% YoY"

        # Format knowledge framework guidance for LLM
        kb_framework_str = ""
        kb_msg_fw = plan.get("kb_messaging_framework", {})
        if kb_msg_fw.get("recommended"):
            stages_str = " → ".join(kb_msg_fw.get("stages") or [])
            kb_framework_str = (
                f"\n\nMessaging Framework (from Cialdini/Ogilvy reference library): "
                f"Use {kb_msg_fw['recommended']} ({stages_str}). "
                f"{kb_msg_fw.get('rationale', '')}"
            )
        kb_cialdini = plan.get("kb_cialdini_principles", [])
        if kb_cialdini:
            principles_str = "; ".join(
                f"{p['principle']} — {p.get('sg_angle', '')[:100]}"
                for p in kb_cialdini[:2]
            )
            kb_framework_str += f"\nActivate these Cialdini principles: {principles_str}"
        self._kb_framework_hit = bool(kb_framework_str)

        competitor_intel_str = ""
        if competitor_messaging_intel:
            competitor_intel_str = (
                f"\n\nLive Competitor Intelligence (from Perplexity):\n{competitor_messaging_intel}"
            )

        # Format competitor weakness context for differentiation messaging
        weakness_context = ""
        if competitor_weaknesses:
            weakness_lines = []
            for w in competitor_weaknesses[:5]:
                name = w.get("competitor_name") or w.get("title", "Competitor")
                weaknesses = w.get("weaknesses", [])
                opportunities = w.get("opportunities", [])
                line = f"  - {name}"
                if weaknesses:
                    line += f": weaknesses={weaknesses[:2]}"
                if opportunities:
                    line += f", gaps={opportunities[:2]}"
                weakness_lines.append(line)
            weakness_context = "\nCompetitor Weaknesses (exploit in messaging):\n" + "\n".join(
                weakness_lines
            )

        # Format persona context for LLM — include all decision-relevant fields so
        # messaging is persona-specific rather than generic.
        persona_context = ""
        if personas:
            persona_lines = []
            for p in personas[:3]:  # Top 3 personas
                name = p.get("title") or p.get("name", "Unknown")
                role = p.get("role") or p.get("job_title", "")
                company_size = p.get("company_size", "")
                pain_points = p.get("pain_points", [])
                goals = p.get("goals", [])
                objections = p.get("objections", [])
                decision_criteria = p.get("decision_criteria", [])
                preferred_channels = p.get("preferred_channels", [])
                tools = p.get("tools_used", [])
                kpis = p.get("kpis", [])

                line = f"  - {name}"
                if role:
                    line += f" | Role: {role}"
                if company_size:
                    line += f" | Co size: {company_size}"
                if kpis:
                    line += f" | KPIs: {', '.join(kpis[:2])}"
                if pain_points:
                    line += f" | Pains: {', '.join(pain_points[:2])}"
                if goals:
                    line += f" | Goals: {', '.join(goals[:2])}"
                if objections:
                    line += f" | Objections: {', '.join(objections[:2])}"
                if decision_criteria:
                    line += f" | Buys on: {', '.join(decision_criteria[:2])}"
                if preferred_channels:
                    line += f" | Prefers: {', '.join(preferred_channels[:2])}"
                if tools:
                    line += f" | Uses: {', '.join(tools[:2])}"
                persona_lines.append(line)
            persona_context = "\nBus-sourced Personas:\n" + "\n".join(persona_lines)

        # Summarize lead signals for personalization hints
        lead_context = f"{len(leads)} leads identified"
        if leads:
            industries = list({lead.get("industry", "") for lead in leads[:10] if lead.get("industry")})
            if industries:
                lead_context += f" (industries: {', '.join(industries[:3])})"

        company_info = plan.get("company_info", {})
        if isinstance(company_info, dict):
            company_text = ", ".join(
                f"{k.replace('_', ' ').title()}: {v}"
                for k, v in company_info.items()
                if v
            )
        else:
            company_text = str(company_info) or "Not specified"

        # Singapore/APAC compliance flags — always required for outreach
        compliance_flags = [
            "PDPA_CONSENT_REQUIRED",          # Singapore Personal Data Protection Act
            "CAN_SPAM_UNSUBSCRIBE_REQUIRED",  # US CAN-SPAM if any US recipients
            "GDPR_LEGITIMATE_INTEREST",       # If any EU recipients
        ]
        # Stash for _act()
        self._compliance_flags = compliance_flags
        self._campaign_data_sources: list[str] = []
        if self._bus_personas:
            self._campaign_data_sources.append("AgentBus (Personas)")
        if self._bus_leads:
            self._campaign_data_sources.append("AgentBus (Leads)")
        if self._bus_competitor_weaknesses:
            self._campaign_data_sources.append("AgentBus (Competitor Weaknesses)")
        if plan.get("kb_vertical_context"):
            self._campaign_data_sources.append("Market Intel DB")

        compliance_prompt = """
Compliance requirements for Singapore outreach (mandatory — include in all email templates):
- All emails must include unsubscribe link (PDPA Section 11)
- Do not purchase/scrape emails without consent (PDPA)
- Include company registration number (UEN) in email footer
- CAN-SPAM: physical address + one-click unsubscribe required
- GDPR legitimate interest basis must be documented for EU contacts
"""

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
                "content": f"""{_knowledge_header}Create a complete campaign plan:

Company: {company_text}
Value Proposition: {plan.get("value_proposition", "Not specified")}{persona_context}{weakness_context}{kb_vertical_str}{kb_framework_str}{competitor_intel_str}
Campaign Goal: {plan.get("campaign_goal")}{vi_context}{bench_context}
Target Leads: {lead_context}
{compliance_prompt}
Create:
1. Campaign brief with objectives and targets
2. Messaging framework with key messages and proof points tailored to the personas above
3. 3-5 ready-to-use content pieces:
   - 2 cold outreach emails (initial + follow-up) personalized for each persona's pain points
   - 2 LinkedIn posts/messages
   - 1 value-add content idea
4. Channel strategy (exploit competitor weaknesses where identified above)
5. Success metrics
6. Create EXACTLY 2 outreach sequences: the FIRST with ab_variant='A' (original subject lines), the SECOND with ab_variant='B' (alternative subject lines for email steps only — same channel/day structure as A). Each sequence must include these steps:
   - Day 1: Initial email (cold outreach), action=initial_outreach, channel=email, condition=none
   - Day 3: LinkedIn connection request with note, channel=linkedin_connect, action=follow_up, condition=none
   - Day 7: Follow-up email IF no reply to Day 1, channel=email, action=follow_up, condition=if_no_reply
   - Day 10: Value-add email (case study / insight), channel=email, action=value_add, condition=if_no_reply
   - Day 14: Breakup email ("Last attempt"), channel=email, action=breakup, condition=if_no_reply
   For each step provide: day number (must be >= 1), channel, action type, subject_line (specific, non-generic), body_preview (first 150 chars of message), condition, and persona_target.
   Set expected_reply_rate to a benchmark range for Singapore B2B outreach in this industry (e.g. "8-12%").
   Variant B sequences must have the SAME steps/channels/days as variant A, differing ONLY in subject_line for email steps.

CRITICAL: All content must be COMPLETE and IMMEDIATELY USABLE.
- NEVER use placeholders like [RECIPIENT NAME], [COMPANY], [INSERT VALUE PROP], [YOUR NAME], etc.
- Use the actual company name, persona details, and pain points provided above.
- If a specific value is unknown, make a reasonable specific assumption (e.g. use "your team" not "[TEAM SIZE]")
- Email subject lines must be specific and non-generic (not "Quick question" or "Following up"){_sg_context}""",
            },
        ]

        return await self._complete_structured(
            response_model=CampaignPlanOutput,
            messages=messages,
        )

    # Detects unfilled template placeholders that indicate the LLM ignored the "no placeholders" instruction.
    # Square brackets: only match ALL-CAPS content (e.g. [RECIPIENT NAME], [COMPANY]) or known
    # instruction words (insert, your, recipient, placeholder, etc.) — avoids false positives on
    # content like [Series A startups] or [Q3 2024 results].
    # Curly braces: match any {snake_case} or {UPPER_CASE} variable-style pattern.
    _PLACEHOLDER_RE = re.compile(
        # ALL-CAPS bracket placeholders: [RECIPIENT NAME], [COMPANY NAME], [PAIN POINT]
        # No re.IGNORECASE on this alternative — [A-Z] must be actual uppercase,
        # otherwise [Series A startups] or [Q3 2024 results] would false-positive.
        r"\[[A-Z][A-Z0-9 _/]{2,}\](?!\()"
        # Instruction-word bracket placeholders: [Recipient Name], [Insert Value], [your name]
        # (?i:...) inline flag makes only this alternative case-insensitive.
        r"|(?i:\[(?:insert|your|recipient|placeholder|company|contact|product|first|last|name|email|value|role|title)[^\]]*\](?!\())"
        # Curly-brace variables: {first_name}, {COMPANY_NAME}, {value_prop}
        # No spaces allowed — prevents {Q3 results} from matching (space breaks the pattern).
        r"|\{[A-Za-z][A-Za-z0-9_]{1,}\}",
    )

    async def _check(self, result: CampaignPlanOutput) -> float:
        # Penalise runs with no real persona/lead context from the bus.
        # Pure LLM with no grounding data should not score above 0.5.
        has_real_personas = bool(self._bus_personas)
        has_real_leads = bool(self._bus_leads)
        grounding_bonus = (0.1 if has_real_personas else 0.0) + (0.05 if has_real_leads else 0.0)

        score = 0.2 + grounding_bonus  # Lower base — 0.3 rewarded doing nothing

        # Structure checks
        if result.messaging_framework.value_proposition:
            score += 0.15
        if result.messaging_framework.key_messages:
            score += 0.1

        if result.content_pieces:
            score += 0.15
            # Diversity check: must have multiple content types, not just length
            content_types = {cp.type for cp in result.content_pieces}
            if len(content_types) >= 2:
                score += 0.1

        if result.channel_strategy:
            score += 0.1
        if result.success_metrics:
            score += 0.1

        # Outreach sequence bonus: reward well-formed multi-touch sequences
        if result.outreach_sequences:
            score += 0.05
            # Extra bonus when steps are present with timing
            if any(len(seq.steps) >= 3 for seq in result.outreach_sequences):
                score += 0.05

        # Placeholder penalty: deduct for each unfilled [PLACEHOLDER] pattern found.
        # Each placeholder found costs 0.05 — more than 4 unfilled means content is unusable.
        # Also scan outreach sequence body_preview and subject_line fields.
        total_placeholders = sum(
            len(self._PLACEHOLDER_RE.findall(cp.content)) for cp in result.content_pieces
        )
        for seq in result.outreach_sequences:
            for step in seq.steps:
                total_placeholders += len(self._PLACEHOLDER_RE.findall(step.subject_line))
                total_placeholders += len(self._PLACEHOLDER_RE.findall(step.body_preview))
        if total_placeholders > 0:
            score = max(0.0, score - total_placeholders * 0.05)
            self._logger.warning(
                "campaign_content_has_placeholders", count=total_placeholders
            )

        # Persona alignment (only meaningful when real personas were used)
        if has_real_personas and result.content_pieces:
            alignment_scorer = MessageAlignmentScorer()
            persona = self._bus_personas[0]
            alignment_scores = [
                alignment_scorer.score(cp.content, persona).total_score
                for cp in result.content_pieces[:3]
            ]
            avg_alignment = sum(alignment_scores) / len(alignment_scores)
            score = min(score + avg_alignment * 0.15, 1.0)

        # KB vertical grounding bonus — real market leaders/signals improve messaging relevance
        if getattr(self, "_kb_vertical_hit", False):
            score += 0.05

        # Knowledge framework bonus — Cialdini/Ogilvy-guided prompts produce better content
        if getattr(self, "_kb_framework_hit", False):
            score += 0.05

        # Live competitor intelligence bonus — real-time messaging research improves relevance
        if getattr(self, "_has_live_intel", False):
            score += 0.10

        # Vertical intelligence bonus — data-backed messaging angles
        if getattr(self, "_kb_vertical_intel_hit", False):
            score += 0.05

        return min(score, 1.0)

    async def _act(self, result: CampaignPlanOutput, confidence: float) -> CampaignPlanOutput:
        """Stamp confidence, data provenance, and compliance flags on the output."""
        result.confidence = confidence
        result.compliance_flags = getattr(self, "_compliance_flags", [
            "PDPA_CONSENT_REQUIRED",
            "CAN_SPAM_UNSUBSCRIBE_REQUIRED",
            "GDPR_LEGITIMATE_INTEREST",
        ])
        data_sources = list(getattr(self, "_campaign_data_sources", []))
        if getattr(self, "_has_live_intel", False):
            data_sources.append("Perplexity")
        if getattr(self, "_kb_vertical_intel_hit", False):
            data_sources.append("Vertical Intelligence Report")
        result.data_sources_used = data_sources
        result.is_live_data = bool(
            getattr(self, "_has_live_intel", False) or self._bus_personas or self._bus_leads
        )

        # Publish CAMPAIGN_READY so execution agents (Outreach Executor, CRM Sync) can react
        if self._bus is not None:
            try:
                # Collect unique persona targets from all sequence steps
                personas_targeted: list[str] = []
                seen_personas: set[str] = set()
                for seq in result.outreach_sequences:
                    for step in seq.steps:
                        if step.persona_target and step.persona_target not in seen_personas:
                            seen_personas.add(step.persona_target)
                            personas_targeted.append(step.persona_target)
                            if len(personas_targeted) >= 3:
                                break
                    if len(personas_targeted) >= 3:
                        break

                await self._bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.CAMPAIGN_READY,
                    title=f"Campaign ready: {result.campaign_brief.name if result.campaign_brief else 'Unnamed'}",
                    content={
                        "content_pieces_count": len(result.content_pieces),
                        "sequence_count": len(result.outreach_sequences),
                        "personas_targeted": personas_targeted,
                        "channels": list({cp.type for cp in result.content_pieces}),
                        "has_ab_variants": any(
                            getattr(seq, "ab_variant", None) for seq in result.outreach_sequences
                        ),
                    },
                    confidence=confidence,
                    analysis_id=self._current_analysis_id,
                )
            except Exception as e:
                self._logger.warning("campaign_ready_publish_failed", error=str(e))

        return result
