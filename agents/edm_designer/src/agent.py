"""EDM Designer Agent — Responsive email HTML generation from campaign briefs.

Generates production-ready HTML email campaigns by:
1. Structuring content into typed sections (hero, body, cta, testimonial, stats)
2. Building MJML markup from the structured sections
3. Compiling MJML to responsive HTML via the MJML tool
4. Optionally generating hero images via DALL-E

Subscribes to CAMPAIGN_READY events on the bus so it activates automatically
when the Campaign Architect completes a brief. Publishes CREATIVE_READY on
completion so downstream agents (e.g. Outreach Executor) can act.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.dalle import DalleMCPServer
from packages.tools.src.mjml import build_edm_mjml, compile_mjml

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class EDMSection(BaseModel):
    """A section of the email."""

    section_type: str = Field(...)  # hero, body, cta, testimonial, stats
    headline: str = Field(default="")
    body_text: str = Field(default="")
    cta_text: str = Field(default="")
    cta_url: str = Field(default="")
    image_prompt: str = Field(default="")  # DALL-E prompt for section image


class _EDMStructure(BaseModel):
    """Intermediate structured output from the LLM before HTML compilation."""

    subject_line: str = Field(...)
    preview_text: str = Field(default="")
    hero_headline: str = Field(default="")
    hero_subheadline: str = Field(default="")
    body_paragraphs: list[str] = Field(default_factory=list)
    cta_text: str = Field(default="Learn More")
    cta_url: str = Field(default="https://example.com")
    hero_image_prompt: str = Field(default="")
    sections: list[EDMSection] = Field(default_factory=list)
    target_persona: str = Field(default="")
    variant_label: str = Field(default="A")


class EDMDesignOutput(BaseModel):
    """Complete EDM design output."""

    subject_line: str = Field(...)
    preview_text: str = Field(default="")
    sections: list[EDMSection] = Field(default_factory=list)
    mjml_source: str = Field(default="")
    html_output: str = Field(default="")
    hero_image_url: str = Field(default="")
    target_persona: str = Field(default="")
    variant_label: str = Field(default="A")
    compliance_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class EDMDesignerAgent(BaseGTMAgent[EDMDesignOutput]):
    """Generates responsive HTML email campaigns from campaign briefs.

    Subscribes to CAMPAIGN_READY on the agent bus and produces CREATIVE_READY
    when the email is compiled and validated. Uses MJML for cross-client
    compatibility and DALL-E for optional hero images.
    """

    def __init__(self, agent_bus: AgentBus | None = None) -> None:
        super().__init__(
            name="edm-designer",
            description=(
                "Generates responsive HTML email campaigns (EDMs) from campaign briefs. "
                "Structures content into typed sections, compiles via MJML, and optionally "
                "generates hero images via DALL-E."
            ),
            result_type=EDMDesignOutput,
            min_confidence=0.55,
            max_iterations=2,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="edm-generation",
                    description="Generate responsive HTML email from campaign brief",
                ),
                AgentCapability(
                    name="mjml-compilation",
                    description="Compile MJML markup to cross-client responsive HTML",
                ),
            ],
        )
        self._bus = agent_bus or get_agent_bus()
        self._dalle = DalleMCPServer.from_env()
        self._knowledge_pack: dict[str, Any] = {}
        self._analysis_id: Any = None

        self._bus.subscribe(
            agent_id=self.name,
            discovery_type=DiscoveryType.CAMPAIGN_READY,
            handler=self._on_campaign_ready,
        )

    def get_system_prompt(self) -> str:
        return (
            "You are an expert email marketing designer specialising in B2B campaigns for "
            "Singapore SMEs. You create compelling, conversion-focused EDMs (Electronic Direct "
            "Mailers) that are: concise, benefit-led, PDPA-compliant, and optimised for mobile. "
            "Always structure content with a clear hero, value proposition body, and a single "
            "primary CTA. Subject lines must be specific and under 60 characters. "
            "Preview text must complement the subject (not repeat it). "
            "Never include placeholders like [Company Name] — use the actual context provided."
        )

    async def _on_campaign_ready(self, message: AgentMessage) -> None:
        """React to CAMPAIGN_READY events from CampaignArchitect."""
        try:
            if (
                self._analysis_id
                and message.analysis_id
                and str(message.analysis_id) != str(self._analysis_id)
            ):
                return
            context = {
                "company_name": message.content.get("company_name", ""),
                "value_proposition": message.content.get("value_proposition", ""),
                "personas": message.content.get("personas", []),
                "campaign_goal": message.content.get("campaign_goal", "lead generation"),
                "industry": message.content.get("industry", ""),
                "uen": message.content.get("uen", ""),
                "analysis_id": message.analysis_id,
            }
            task = f"Design EDM for campaign: {message.title}"
            await self.run(task=task, context=context)
        except Exception as e:
            self._logger.warning("edm_on_campaign_ready_failed", error=str(e))

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Extract campaign brief fields
        company_name = context.get("company_name", "")
        value_proposition = context.get("value_proposition", "")
        personas = context.get("personas", [])
        campaign_goal = context.get("campaign_goal", "lead generation")
        industry = context.get("industry", "")
        uen = context.get("uen", "")

        # Load synthesized domain knowledge for email marketing
        self._knowledge_pack = {}
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="edm-designer",
                task_context=task,
            )
        except Exception as e:
            self._logger.debug("edm_knowledge_pack_failed", error=str(e))

        # Determine primary persona
        primary_persona = ""
        if personas:
            if isinstance(personas[0], dict):
                primary_persona = personas[0].get("title", "") or personas[0].get("name", "")
            else:
                primary_persona = str(personas[0])

        return {
            "company_name": company_name,
            "value_proposition": value_proposition,
            "personas": personas,
            "primary_persona": primary_persona,
            "campaign_goal": campaign_goal,
            "industry": industry,
            "uen": uen,
            "task": task,
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> EDMDesignOutput:
        company_name = plan.get("company_name", "")
        value_proposition = plan.get("value_proposition", "")
        personas = plan.get("personas", [])
        primary_persona = plan.get("primary_persona", "")
        campaign_goal = plan.get("campaign_goal", "lead generation")
        industry = plan.get("industry", "")
        uen = plan.get("uen", "")

        data_sources: list[str] = []

        # Inject knowledge pack into LLM user message (Rule 6 / Rule 7)
        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        if _knowledge_ctx:
            data_sources.append("KnowledgeBase")

        personas_text = ""
        if personas:
            if isinstance(personas[0], dict):
                personas_text = "; ".join(
                    p.get("title", str(p)) for p in personas[:3]
                )
            else:
                personas_text = "; ".join(str(p) for p in personas[:3])

        user_prompt = (
            f"{_knowledge_header}"
            f"Design a complete EDM for a {campaign_goal} campaign.\n\n"
            f"Company: {company_name}\n"
            f"Industry: {industry}\n"
            f"Value Proposition: {value_proposition}\n"
            f"Target Personas: {personas_text or primary_persona or 'Decision makers at Singapore SMEs'}\n\n"
            "Return a structured email with:\n"
            "- subject_line: compelling, under 60 chars, no placeholders\n"
            "- preview_text: complements subject, under 100 chars\n"
            "- hero_headline: bold statement of value\n"
            "- hero_subheadline: one supporting sentence\n"
            "- body_paragraphs: 2-4 paragraphs (problem → solution → proof → next step)\n"
            "- cta_text: action-oriented, under 40 chars\n"
            "- cta_url: placeholder URL like https://[company].com/[goal]\n"
            "- hero_image_prompt: DALL-E prompt for professional Singapore B2B hero image\n"
            "- sections: list of EDMSection objects for each content block\n"
            f"- target_persona: '{primary_persona or 'SME Decision Maker'}'\n"
            "- variant_label: 'A'\n\n"
            "Write in a confident, professional tone suited to Singapore B2B. "
            "No placeholders in visible copy — use the actual company name and value proposition."
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        # Structured LLM call — this is the primary real data source (campaign brief → email)
        edm_structure = await self._complete_structured(
            response_model=_EDMStructure,
            messages=messages,
        )
        data_sources.append("GPT-4o (EDM structured generation)")

        # Build MJML from the structured output
        body_paragraphs = edm_structure.body_paragraphs or [
            f"{value_proposition}",
            "Our solution is purpose-built for Singapore SMEs.",
        ]

        mjml_source = build_edm_mjml(
            headline=edm_structure.hero_headline,
            subheadline=edm_structure.hero_subheadline,
            body_paragraphs=body_paragraphs,
            cta_text=edm_structure.cta_text,
            cta_url=edm_structure.cta_url,
            company_name=company_name,
            company_address="Singapore",
            uen=uen,
        )
        data_sources.append("MJML builder")

        # Compile MJML to responsive HTML
        try:
            html_output = await compile_mjml(mjml_source)
            data_sources.append("MJML compiler")
        except Exception as e:
            self._logger.warning("mjml_compile_failed", error=str(e))
            html_output = ""

        # Optionally generate hero image via DALL-E
        hero_image_url = ""
        if edm_structure.hero_image_prompt and self._dalle.is_configured:
            try:
                dalle_result = await self._dalle.generate_image(
                    prompt=edm_structure.hero_image_prompt,
                    platform="email_header",
                    quality="standard",
                    style="natural",
                )
                if not dalle_result.get("error"):
                    hero_image_url = dalle_result.get("url", "")
                    data_sources.append("DALL-E 3 (hero image)")
                    self._logger.info(
                        "edm_hero_image_generated",
                        local_path=dalle_result.get("local_path", ""),
                    )
            except Exception as e:
                self._logger.warning("edm_dalle_failed", error=str(e))

        # Validate compliance flags
        compliance_flags: list[str] = []
        html_lower = html_output.lower()
        if "unsubscribe" not in html_lower:
            compliance_flags.append("MISSING_UNSUBSCRIBE_LINK")
        if uen and uen.upper() not in html_output.upper():
            compliance_flags.append("MISSING_UEN_IN_FOOTER")
        if re.search(r"\[.*?\]", html_output):
            compliance_flags.append("PLACEHOLDER_TEXT_DETECTED")

        return EDMDesignOutput(
            subject_line=edm_structure.subject_line,
            preview_text=edm_structure.preview_text,
            sections=edm_structure.sections,
            mjml_source=mjml_source,
            html_output=html_output,
            hero_image_url=hero_image_url,
            target_persona=edm_structure.target_persona,
            variant_label=edm_structure.variant_label,
            compliance_flags=compliance_flags,
            confidence=0.0,  # Set by _check
            data_sources_used=list(set(data_sources)),
        )

    async def _check(self, result: EDMDesignOutput) -> float:
        score = 0.20  # Base — must earn the rest from data quality

        # HTML compiled and non-empty
        if result.html_output and len(result.html_output) > 200:
            html_lower = result.html_output.lower()

            # Unsubscribe link present (PDPA / anti-spam)
            if "unsubscribe" in html_lower:
                score += 0.15

            # UEN in footer (Singapore PDPA compliance marker)
            if "uen" in html_lower or (
                result.mjml_source and "uen" in result.mjml_source.lower()
            ):
                score += 0.10

            # No placeholder text remaining
            if not re.search(r"\[.*?\]", result.html_output):
                score += 0.15

        # Sufficient section count (2+ sections = real structure, not stub)
        if len(result.sections) >= 2:
            score += 0.10

        # Subject line specificity — not generic, not empty, not a placeholder
        subject = result.subject_line
        is_specific = (
            bool(subject)
            and len(subject) > 10
            and not re.search(r"\[.*?\]", subject)
            and subject.lower() not in {"subject line", "untitled", "email subject"}
        )
        if is_specific:
            score += 0.10

        # Knowledge pack was loaded and injected
        if getattr(self, "_knowledge_pack", {}).get("formatted_injection"):
            score += 0.05

        # Hero image generated (optional bonus — not penalised if absent)
        if result.hero_image_url:
            score += 0.05

        return min(score, 1.0)

    async def _act(self, result: EDMDesignOutput, confidence: float) -> EDMDesignOutput:
        result.confidence = confidence

        # Publish CREATIVE_READY to the bus so downstream agents can act
        if self._bus is not None:
            try:
                await self._bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.CREATIVE_READY,
                    title=f"EDM ready: {result.subject_line[:80]}",
                    content={
                        "creative_type": "edm",
                        "subject_line": result.subject_line,
                        "preview_text": result.preview_text,
                        "html_output": result.html_output[:500],  # Truncated for bus
                        "hero_image_url": result.hero_image_url,
                        "variant_label": result.variant_label,
                        "target_persona": result.target_persona,
                        "compliance_flags": result.compliance_flags,
                        "sections_count": len(result.sections),
                        "data_sources_used": result.data_sources_used,
                    },
                    confidence=confidence,
                    analysis_id=self._analysis_id,
                )
                self._logger.info(
                    "edm_creative_ready_published",
                    subject=result.subject_line,
                    confidence=round(confidence, 3),
                    compliance_flags=result.compliance_flags,
                )
            except Exception as e:
                self._logger.warning("edm_bus_publish_failed", error=str(e))

        return result
