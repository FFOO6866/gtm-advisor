"""CRM Sync Agent - Creates/updates HubSpot contacts for qualified leads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from agents.core.src.mcp_integration import AgentMCPClient
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp


class CRMSyncResult(BaseModel):
    """Result of a CRM sync operation for one lead."""

    lead_id: str = Field(...)
    crm_contact_id: str | None = Field(default=None)
    crm_deal_id: str | None = Field(default=None)
    action_taken: str = Field(...)  # "created_contact", "updated_contact", "skipped_no_config", "failed"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CRMSyncAgent(BaseGTMAgent[CRMSyncResult]):
    """Creates/updates HubSpot contacts and deals for qualified leads.

    Execution agent — not analysis. Uses HubSpot MCP write methods.
    """

    def __init__(self) -> None:
        super().__init__(
            name="crm-sync",
            description=(
                "Creates or updates HubSpot CRM contacts and deals for qualified leads. "
                "Keeps the CRM in sync with Kairos's lead pipeline."
            ),
            result_type=CRMSyncResult,
            min_confidence=0.70,
            max_iterations=1,
            model="gpt-4o-mini",
            capabilities=[
                AgentCapability(
                    name="crm-write",
                    description="Create/update HubSpot contacts and deals",
                ),
            ],
        )
        self._mcp = AgentMCPClient()
        self._agent_bus: AgentBus | None = get_agent_bus()
        self._analysis_id: Any = None
        self._knowledge_pack: dict = {}
        self._workforce_config: dict[str, Any] | None = None  # Populated by WORKFORCE_READY bus events
        self._pending_leads: list[dict[str, Any]] = []  # Populated by LEAD_FOUND bus events
        self._enrichment_data: dict[str, dict[str, Any]] = {}  # keyed by lead_id
        self._bus_messages_crafted: list[dict] = []
        try:
            if self._agent_bus is not None:
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.WORKFORCE_READY,
                    handler=self._on_workforce_ready,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.LEAD_FOUND,
                    handler=self._on_lead_found,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.LEAD_ENRICHED,
                    handler=self._on_lead_enriched,
                )
                self._agent_bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.MESSAGE_CRAFTED,
                    handler=self._on_message_crafted,
                )
        except Exception:
            pass

    async def _on_workforce_ready(self, message: AgentMessage) -> None:
        """Cache workforce config from WorkforceArchitect for CRM tagging."""
        # Cross-contamination guard — only process events for the current analysis
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        self._workforce_config = message.content
        self._logger.debug(
            "crm_sync_received_workforce_config",
            approved_agents=self._workforce_config.get("approved_agents", []),
        )

    async def _on_lead_found(self, message: AgentMessage) -> None:
        """Accumulate leads discovered by Lead Hunter for automatic CRM population."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        self._pending_leads.append(message.content)

    async def _on_lead_enriched(self, message: AgentMessage) -> None:
        """Cache enrichment data so CRM contacts include verification fields."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        lead_id = message.content.get("lead_id", "")
        if lead_id:
            self._enrichment_data[lead_id] = message.content

    async def _on_message_crafted(self, message: AgentMessage) -> None:
        """Cache sent-message events so CRM activity logs stay in sync."""
        if (
            self._analysis_id
            and message.analysis_id
            and str(message.analysis_id) != str(self._analysis_id)
        ):
            return
        self._bus_messages_crafted.append(message.content)
        self._logger.debug(
            "message_crafted_received",
            email_to=message.content.get("email_to"),
            from_agent=message.from_agent,
        )

    def get_system_prompt(self) -> str:
        return "CRM sync agent. Writes lead data to HubSpot."

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Load domain knowledge pack (execution agent — no LLM call in _do(),
        # but pack is loaded per Rule #6 for future enrichment steps).
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="crm-sync",
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

            lead_found_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.LEAD_FOUND,
                limit=20,
            )
            for msg in lead_found_history:
                if msg.content not in self._pending_leads:
                    self._pending_leads.append(msg.content)

            enriched_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.LEAD_ENRICHED,
                limit=50,
            )
            for msg in enriched_history:
                lead_id = msg.content.get("lead_id", "")
                if lead_id and lead_id not in self._enrichment_data:
                    self._enrichment_data[lead_id] = msg.content

            message_history = self._agent_bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.MESSAGE_CRAFTED,
                limit=50,
            )
            for msg in message_history:
                if msg.content not in self._bus_messages_crafted:
                    self._bus_messages_crafted.append(msg.content)

        name_parts = (context.get("name") or "").split(" ", 1)
        return {
            "lead_id": context.get("lead_id", ""),
            "email": context.get("email", ""),
            "first_name": name_parts[0] if name_parts else "",
            "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "company": context.get("company", ""),
            "job_title": context.get("job_title", ""),
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CRMSyncResult:
        lead_id = plan.get("lead_id", "")
        email = plan.get("email", "")

        # If no email was provided directly but we have a pending lead from the bus,
        # use the first matching pending lead as a supplement.
        if not email and self._pending_leads:
            for pending in self._pending_leads:
                candidate_email = pending.get("email") or pending.get("contact_email", "")
                if candidate_email:
                    email = candidate_email
                    lead_id = lead_id or pending.get("lead_id") or pending.get("id", lead_id)
                    if not plan.get("company"):
                        plan = {**plan, "company": pending.get("company") or pending.get("company_name", "")}
                    if not plan.get("first_name") and not plan.get("last_name"):
                        name_parts = (pending.get("name") or "").split(" ", 1)
                        plan = {
                            **plan,
                            "first_name": name_parts[0] if name_parts else "",
                            "last_name": name_parts[1] if len(name_parts) > 1 else "",
                        }
                    break

        if not email:
            return CRMSyncResult(
                lead_id=lead_id,
                action_taken="skipped_no_email",
                confidence=0.0,
            )

        # Merge enrichment data into the contact properties if available
        enrichment = self._enrichment_data.get(lead_id, {})

        try:
            hubspot = self._mcp._registry.get_server("HubSpot CRM")
            if not hubspot or not hubspot.is_configured:
                return CRMSyncResult(
                    lead_id=lead_id,
                    action_taken="skipped_no_config",
                    confidence=0.0,
                )

            contact_id = await hubspot.create_or_update_contact(
                email=email,
                first_name=plan.get("first_name", ""),
                last_name=plan.get("last_name", ""),
                company=plan.get("company", ""),
                job_title=plan.get("job_title", ""),
                lead_source="Kairos",
            )

            # Log enrichment metadata for observability (HubSpot MCP has no
            # update_contact_properties method, so these are trace-only).
            if enrichment and contact_id:
                self._logger.debug(
                    "crm_sync_enrichment_metadata",
                    contact_id=contact_id,
                    email_valid=enrichment.get("email_valid"),
                    hunter_status=enrichment.get("hunter_status"),
                    acra_verified=enrichment.get("acra_verified"),
                )

            # Log workforce metadata at DEBUG level for observability.
            # HubSpot MCP has no update_contact_properties method, so these
            # fields are not written to CRM — they are available for tracing only.
            if self._workforce_config and contact_id:
                approved_agents = self._workforce_config.get("approved_agents", [])
                self._logger.debug(
                    "crm_sync_workforce_metadata",
                    contact_id=contact_id,
                    workforce_enabled=True,
                    workforce_agents=", ".join(approved_agents) if approved_agents else "",
                )

            if contact_id:
                return CRMSyncResult(
                    lead_id=lead_id,
                    crm_contact_id=contact_id,
                    action_taken="contact_synced",  # create_or_update — accurate regardless
                    confidence=0.90,
                )
            return CRMSyncResult(
                lead_id=lead_id,
                action_taken="failed",
                confidence=0.1,
            )

        except Exception as e:
            self._logger.error("crm_sync_failed", lead_id=lead_id, error=str(e))
            return CRMSyncResult(
                lead_id=lead_id,
                action_taken="failed",
                confidence=0.0,
            )

    async def _check(self, result: CRMSyncResult) -> float:
        score = 0.2  # base — must be earned from data quality
        if result.action_taken == "contact_synced":
            score += 0.30  # sync completed
            if result.crm_contact_id:
                score += 0.30  # CRM confirmed with contact ID
            if result.lead_id:
                score += 0.05  # lead traceability maintained
            if result.crm_deal_id:
                score += 0.05  # deal also created
        elif result.action_taken in ("skipped_no_email", "skipped_no_config"):
            score += 0.45  # expected skip — correct decision
        # else: failed → stays at base 0.2
        return min(score, 1.0)

    async def _act(self, result: CRMSyncResult, confidence: float) -> CRMSyncResult:
        # Publish LEAD_QUALIFIED after a successful CRM sync so downstream agents
        # (attribution tracking, signal monitor) know this lead is now in HubSpot.
        if result.action_taken == "contact_synced" and self._agent_bus is not None:
            try:
                await self._agent_bus.publish(
                    from_agent=self.name,
                    discovery_type=DiscoveryType.LEAD_QUALIFIED,
                    title=f"CRM contact synced: {result.lead_id}",
                    content={
                        "contact_id": result.crm_contact_id,
                        "lead_id": result.lead_id,
                        "sync_status": result.action_taken,
                        "crm_platform": "hubspot",
                        "analysis_id": self._analysis_id,
                    },
                    confidence=0.85,
                    analysis_id=self._analysis_id,
                )
            except Exception as e:
                self._logger.warning("lead_qualified_publish_failed", error=str(e))
        return result
