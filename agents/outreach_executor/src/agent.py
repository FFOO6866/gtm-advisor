"""Outreach Executor Agent - Sends personalised outreach emails via SendGrid.

An execution-tier agent (not analysis). Given a lead and campaign brief,
it constructs and sends a personalised email using the SendGrid MCP server.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from agents.core.src.mcp_integration import AgentMCPClient
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp

# Detects unfilled template placeholders in subject/body — same patterns as CampaignArchitect.
# Any match means the email was not properly personalised and must NOT be sent.
_UNFILLED_RE = re.compile(
    r"\[(?:YOUR|RECIPIENT|COMPANY|CONTACT|INSERT|PLACEHOLDER|NAME|EMAIL|PRODUCT|"
    r"FIRST[\s_]NAME|LAST[\s_]NAME|CLIENT|PROSPECT|SENDER|TITLE|ROLE|INDUSTRY|"
    r"PAIN[\s_]POINT|VALUE[\s_]PROP|CTA|DATE|TIME|URL|LINK|PHONE|POSITION)[^\]]*\]"
    r"|\{(?:first_name|last_name|full_name|company|company_name|recipient|contact|"
    r"product|value_prop|pain_point|industry|role|title|cta|your_name|sender)[^}]*\}",
    re.IGNORECASE,
)

_MAX_SUBJECT_LEN = 78  # RFC 5322 recommended line length; longer subjects are clipped by most clients


class OutreachResult(BaseModel):
    """Result of a single outreach email send."""

    lead_id: str = Field(...)
    email_to: str = Field(...)
    subject: str = Field(default="")
    message_id: str | None = Field(default=None)
    status: str = Field(...)  # "sent", "skipped_no_config", "failed"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OutreachExecutorAgent(BaseGTMAgent[OutreachResult]):
    """Sends personalised outreach emails to qualified leads.

    Execution agent — not an analysis agent. Does NOT call LLM for reasoning;
    uses the campaign brief templates from the analysis phase as-is.
    """

    def __init__(self) -> None:
        super().__init__(
            name="outreach-executor",
            description=(
                "Sends personalised cold outreach emails to qualified leads. "
                "Uses campaign templates from analysis with lead-specific personalisation."
            ),
            result_type=OutreachResult,
            min_confidence=0.70,
            max_iterations=1,  # Never retry email sends
            model="gpt-4o-mini",
            capabilities=[
                AgentCapability(
                    name="email-send",
                    description="Send personalised email via SendGrid",
                ),
            ],
        )
        self._mcp = AgentMCPClient()
        self._agent_bus: AgentBus | None = get_agent_bus()
        self._analysis_id: Any = None
        self._knowledge_pack: dict = {}
        self._workforce_config: dict[str, Any] | None = None  # Populated by WORKFORCE_READY bus events
        self._campaign_context: dict[str, Any] | None = None  # Populated by CAMPAIGN_READY bus events
        self._enriched_leads: dict[str, dict[str, Any]] = {}  # keyed by lead_id
        self._bus_qualified_leads: list[dict] = []
        self._bus_signals: list[dict] = []
        try:
            if self._agent_bus is not None:
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.WORKFORCE_READY,
                    handler=self._on_workforce_ready,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.CAMPAIGN_READY,
                    handler=self._on_campaign_ready,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.LEAD_ENRICHED,
                    handler=self._on_lead_enriched,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.LEAD_QUALIFIED,
                    handler=self._on_lead_qualified,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.SIGNAL_DETECTED,
                    handler=self._on_signal_detected,
                )
        except Exception:
            pass

    async def _on_workforce_ready(self, message: AgentMessage) -> None:
        """Cache workforce config from WorkforceArchitect for outreach prioritisation."""
        # Cross-contamination guard — only process events for the current analysis
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        self._workforce_config = message.content
        self._logger.debug(
            "outreach_executor_received_workforce_config",
            approved_agents=self._workforce_config.get("approved_agents", []),
        )

    async def _on_campaign_ready(self, message: AgentMessage) -> None:
        """Cache campaign context from CampaignArchitect for channel/persona alignment."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        self._campaign_context = message.content
        self._logger.debug(
            "outreach_executor_received_campaign_context",
            channels=self._campaign_context.get("channels", []),
        )

    async def _on_lead_enriched(self, message: AgentMessage) -> None:
        """Cache enrichment data for deliverability gating before send."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        lead_id = message.content.get("lead_id", "")
        if lead_id:
            self._enriched_leads[lead_id] = message.content

    async def _on_lead_qualified(self, message: AgentMessage) -> None:
        """Cache HubSpot-synced qualified leads for follow-up outreach prioritisation."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        self._bus_qualified_leads.append(message.content)

    async def _on_signal_detected(self, message: AgentMessage) -> None:
        """Cache market signals from SignalMonitor to trigger signal-based outreach."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        self._bus_signals.append(message.content)

    def get_system_prompt(self) -> str:
        return """You are an outreach execution agent. Your only job is to personalise
email templates for specific leads and format them for sending.

Rules:
- Keep emails concise (under 150 words for cold outreach)
- Reference the lead's company and industry specifically
- Use the provided template as structure but adapt to the lead's context
- Never invent claims about the product not present in the campaign brief
- Subject lines should be specific, not clickbait"""

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Load domain knowledge pack for cold email / outreach synthesis.
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="outreach-executor",
                task_context=task,
            )
        except Exception as _e:
            self._logger.debug("knowledge_pack_load_failed", error=str(_e))

        # Backfill from bus history (handles cases where events were published before
        # this agent started listening).
        if self._agent_bus is not None:
            workforce_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.WORKFORCE_READY,
                limit=1,
            )
            if workforce_history:
                self._workforce_config = workforce_history[0].content

            campaign_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.CAMPAIGN_READY,
                limit=1,
            )
            if campaign_history:
                self._campaign_context = campaign_history[0].content

            enriched_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.LEAD_ENRICHED,
                limit=50,
            )
            for msg in enriched_history:
                lead_id = msg.content.get("lead_id", "")
                if lead_id and lead_id not in self._enriched_leads:
                    self._enriched_leads[lead_id] = msg.content

            qualified_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.LEAD_QUALIFIED,
                limit=50,
            )
            for msg in qualified_history:
                if msg.content not in self._bus_qualified_leads:
                    self._bus_qualified_leads.append(msg.content)

            signal_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.SIGNAL_DETECTED,
                limit=20,
            )
            for msg in signal_history:
                if msg.content not in self._bus_signals:
                    self._bus_signals.append(msg.content)

        return {
            "lead_id": context.get("lead_id", ""),
            "lead_email": context.get("lead_email", ""),
            "lead_name": context.get("lead_name", ""),
            "company_name": context.get("company_name", ""),
            "contact_title": context.get("contact_title", ""),
            "industry": context.get("industry", ""),
            "company_size": context.get("company_size", ""),
            "fit_score": context.get("fit_score", 0),
            "intent_score": context.get("intent_score", 0),
            "qualification_reasons": context.get("qualification_reasons", []),
            "campaign_brief": context.get("campaign_brief", {}),
            "from_email": os.getenv("WORKFORCE_OUTREACH_FROM_EMAIL", ""),
            "from_name": os.getenv("WORKFORCE_OUTREACH_FROM_NAME", "GTM Advisor"),
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> OutreachResult:
        lead_email = plan.get("lead_email", "")
        lead_id = plan.get("lead_id", "")
        from_email = plan.get("from_email", "")

        if not lead_email:
            return OutreachResult(
                lead_id=lead_id,
                email_to="",
                status="skipped_no_email",
                confidence=0.0,
            )

        if not from_email:
            return OutreachResult(
                lead_id=lead_id,
                email_to=lead_email,
                status="skipped_no_config",
                confidence=0.0,
            )

        # Deliverability gate: skip if enrichment data marks email as invalid
        if lead_id and lead_id in self._enriched_leads:
            enrichment = self._enriched_leads[lead_id]
            if not enrichment.get("email_valid", True):
                self._logger.warning(
                    "outreach_skipped_invalid_email",
                    lead_id=lead_id,
                    hunter_status=enrichment.get("hunter_status"),
                )
                return OutreachResult(
                    lead_id=lead_id,
                    email_to=lead_email,
                    status="skipped_undeliverable",
                    confidence=0.0,
                )
            if not enrichment.get("qualifies_for_sequence", True):
                self._logger.warning(
                    "outreach_skipped_not_qualified",
                    lead_id=lead_id,
                    quality_score=enrichment.get("quality_score", 0),
                )
                return OutreachResult(
                    lead_id=lead_id,
                    email_to=lead_email,
                    status="skipped_undeliverable",
                    confidence=0.0,
                )

        # Campaign context: validate channel and collect personas for personalisation
        campaign_channels: list[str] = []
        campaign_personas: list[str] = []
        if self._campaign_context:
            campaign_channels = self._campaign_context.get("channels", [])
            campaign_personas = self._campaign_context.get("personas_targeted", [])
            # Log if email channel is not in the campaign plan (soft warning, still send)
            if campaign_channels and not any(
                "email" in ch.lower() for ch in campaign_channels
            ):
                self._logger.debug(
                    "outreach_channel_not_in_campaign_plan",
                    lead_id=lead_id,
                    campaign_channels=campaign_channels,
                )

        # Apply workforce config if available
        if self._workforce_config:
            approved_agents = self._workforce_config.get("approved_agents", [])
            if approved_agents:
                # Only proceed if an outreach-type agent is in the approved roster
                has_outreach = any(
                    "outreach" in name.lower() for name in approved_agents
                )
                if not has_outreach:
                    self._logger.debug(
                        "outreach_skipped_not_in_workforce",
                        lead_id=lead_id,
                        approved_agents=approved_agents,
                    )
                    return OutreachResult(
                        lead_id=lead_id,
                        email_to=lead_email,
                        status="skipped_no_config",
                        confidence=0.0,
                    )
            roi_multiplier = self._workforce_config.get("estimated_roi_multiplier")
            if roi_multiplier is not None and roi_multiplier > 2.0:
                self._logger.debug(
                    "outreach_high_roi_intensity",
                    lead_id=lead_id,
                    roi_multiplier=roi_multiplier,
                )

        # Personalise the email template using LLM
        campaign_brief = plan.get("campaign_brief", {})
        template = ""
        if isinstance(campaign_brief, dict):
            # Try to extract a cold email template from the brief
            email_templates = campaign_brief.get("email_templates", [])
            if email_templates:
                template = email_templates[0]
            key_messages = campaign_brief.get("key_messages", [])
            value_prop = campaign_brief.get("objective", "")
        else:
            key_messages = []
            value_prop = ""

        # Build lead qualification context for personalisation
        contact_title = plan.get("contact_title", "")
        industry = plan.get("industry", "")
        fit_score = plan.get("fit_score", 0)
        intent_score = plan.get("intent_score", 0)
        qual_reasons = plan.get("qualification_reasons", [])

        lead_context_lines = []
        if contact_title:
            lead_context_lines.append(f"Title: {contact_title}")
        if industry:
            lead_context_lines.append(f"Industry: {industry}")
        if plan.get("company_size"):
            lead_context_lines.append(f"Company size: {plan['company_size']}")
        if fit_score is not None and fit_score > 0:
            lead_context_lines.append(f"ICP fit score: {fit_score}/100")
        if intent_score is not None and intent_score > 0:
            lead_context_lines.append(f"Buying intent score: {intent_score}/100")
        if qual_reasons:
            lead_context_lines.append(f"Why qualified: {', '.join(qual_reasons[:3])}")
        lead_context = "\n".join(lead_context_lines)

        persona_hint = ""
        if campaign_personas:
            persona_hint = f"\nTarget Personas: {', '.join(campaign_personas[:3])}"

        # Fetch persuasion framework guidance from knowledge base (non-fatal)
        framework_hint = ""
        try:
            kmcp = get_knowledge_mcp()
            msg_fw = await kmcp.get_messaging_framework("cold email outreach")
            fw_name = msg_fw.get("recommended_framework", "PAS")
            fw_stages = (msg_fw.get("framework_content") or {}).get("stages", [])
            cialdini = await kmcp.get_framework("CIALDINI_PRINCIPLES")
            principles = cialdini.get("content") or {}
            # Pick the 2 most relevant Cialdini principles for cold outreach
            selected = []
            for key in ("reciprocity", "social_proof"):
                p = principles.get(key, {})
                sg = p.get("sg_angle", "") or p.get("application", "")
                if sg:
                    selected.append(f"- {key.replace('_', ' ').title()}: {sg[:120]}")
            stages_str = " → ".join(s.get("name", s) if isinstance(s, dict) else str(s) for s in fw_stages[:4])
            if stages_str or selected:
                framework_hint = (
                    f"\nPersuasion Framework ({fw_name})"
                    + (f": {stages_str}" if stages_str else "")
                    + ("\nCialdini principles to activate:\n" + "\n".join(selected) if selected else "")
                )
        except Exception as e:
            self._logger.debug("knowledge_mcp_failed", error=str(e))

        _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
        _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "user",
                "content": f"""{_knowledge_header}Personalise this outreach email:

Target: {plan.get('lead_name', 'Decision maker')} at {plan.get('company_name', 'their company')}
{lead_context}{persona_hint}{framework_hint}
Template: {template or 'No template — write a short cold outreach email'}
Value Proposition: {value_prop}
Key Messages: {key_messages[:2]}

Return ONLY a JSON object with:
{{"subject": "email subject line", "body": "full email body text"}}""",
            },
        ]

        try:
            raw = await self._complete(messages)
            # Parse the JSON from LLM response using raw_decode so trailing prose
            # or curly braces inside string values don't break extraction.
            text = raw if isinstance(raw, str) else str(raw)
            start = text.find("{")
            if start >= 0:
                decoder = json.JSONDecoder()
                parsed, _ = decoder.raw_decode(text, start)
                subject = parsed.get("subject", "Following up on your GTM strategy")
                body = parsed.get("body", text)
            else:
                subject = "Quick question about your GTM"
                body = text
        except Exception as e:
            self._logger.warning("email_personalisation_failed", error=str(e))
            if not template:
                # No template and LLM failed — refuse to send a generic placeholder
                return OutreachResult(
                    lead_id=lead_id,
                    email_to=lead_email,
                    status="failed",
                    confidence=0.0,
                )
            subject = "Following up on your GTM strategy"
            body = template

        # --- Pre-send quality gates ---

        # Gate 1: Opt-out / enrollment status check.
        # The caller must pass opted_out=True in context if the lead has unsubscribed.
        if context and context.get("opted_out"):
            self._logger.warning("outreach_blocked_opted_out", lead_id=lead_id)
            return OutreachResult(
                lead_id=lead_id,
                email_to=lead_email,
                status="skipped_opted_out",
                confidence=0.0,
            )

        # Gate 2: Unfilled placeholder detection — never send a template with [PLACEHOLDER] or {var}.
        placeholders_in_subject = _UNFILLED_RE.findall(subject)
        placeholders_in_body = _UNFILLED_RE.findall(body)
        if placeholders_in_subject or placeholders_in_body:
            total = len(placeholders_in_subject) + len(placeholders_in_body)
            self._logger.error(
                "outreach_blocked_unfilled_placeholders",
                lead_id=lead_id,
                count=total,
                examples=(placeholders_in_subject + placeholders_in_body)[:3],
            )
            return OutreachResult(
                lead_id=lead_id,
                email_to=lead_email,
                status="failed_unfilled_placeholders",
                confidence=0.0,
            )

        # Gate 3: Subject length — truncate to RFC 5322 recommended limit.
        if len(subject) > _MAX_SUBJECT_LEN:
            subject = subject[:_MAX_SUBJECT_LEN - 3] + "..."

        # Attempt to send via SendGrid
        try:
            sendgrid = self._mcp._registry.get_server("SendGrid Email")
            if sendgrid and sendgrid.is_configured:
                message_id = await sendgrid.send_email(
                    to=lead_email,
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    from_name=plan.get("from_name", "GTM Advisor"),
                    categories=["gtm-outreach"],
                    custom_args={"lead_id": lead_id},
                )
                return OutreachResult(
                    lead_id=lead_id,
                    email_to=lead_email,
                    subject=subject,
                    message_id=message_id,
                    status="sent" if message_id else "failed",
                    confidence=0.95 if message_id else 0.3,
                )
        except Exception as e:
            self._logger.error("sendgrid_send_failed", lead_id=lead_id, error=str(e))
            return OutreachResult(
                lead_id=lead_id,
                email_to=lead_email,
                subject=subject,
                status="failed",
                confidence=0.0,
            )

        return OutreachResult(
            lead_id=lead_id,
            email_to=lead_email,
            subject=subject,
            status="skipped_no_config",
            confidence=0.0,
        )

    async def _check(self, result: OutreachResult) -> float:
        score = 0.2  # base — must earn confidence from data
        if result.status == "sent":
            score += 0.30  # email was sent
            if result.message_id:
                score += 0.30  # delivery confirmed via SendGrid message_id
            if result.subject:
                score += 0.05  # subject line present
            if result.email_to:
                score += 0.05  # recipient address present
        elif result.status in ("skipped_no_email", "skipped_no_config"):
            score += 0.45  # expected skip — correct decision, not a failure
        # else: failed → stays at base 0.2
        return min(score, 1.0)

    async def _act(self, result: OutreachResult, confidence: float) -> OutreachResult:
        # Publish MESSAGE_CRAFTED so CRM Sync, Campaign Architect, and attribution
        # tracking are aware the email was sent. Skip publishing for config-missing skips
        # to avoid polluting the bus with non-events.
        if result.status != "skipped_no_config" and self._agent_bus is not None:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.MESSAGE_CRAFTED,
                    title=f"Email sent to {result.email_to}",
                    content={
                        "lead_id": result.lead_id,
                        "email_to": result.email_to,
                        "status": result.status,
                        "subject": result.subject,
                        "sequence_step": None,
                        "analysis_id": self._analysis_id,
                    },
                    confidence=0.9 if result.status == "sent" else 0.3,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.warning("message_crafted_publish_failed", error=str(e))
        return result
