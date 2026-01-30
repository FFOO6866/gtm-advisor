"""A2A Communication Hub - Agent-to-Agent messaging infrastructure.

Enables dynamic collaboration between agents through:
- Discovery publishing: Agents broadcast new findings
- Event subscriptions: Agents react to discoveries from others
- Direct messaging: Point-to-point agent communication
- Evidenced discoveries: Facts with full provenance tracking
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class DiscoveryType(str, Enum):
    """Types of discoveries agents can publish."""

    # Company enrichment
    COMPANY_PROFILE = "company_profile"
    COMPANY_PRODUCTS = "company_products"
    COMPANY_TECH_STACK = "company_tech_stack"
    COMPANY_FUNDING = "company_funding"

    # Market intelligence
    MARKET_TREND = "market_trend"
    MARKET_OPPORTUNITY = "market_opportunity"
    MARKET_THREAT = "market_threat"

    # Competitor intelligence
    COMPETITOR_FOUND = "competitor_found"
    COMPETITOR_WEAKNESS = "competitor_weakness"
    COMPETITOR_PRODUCT = "competitor_product"
    COMPETITOR_SIGNAL = "competitor_signal"

    # Customer insights
    ICP_SEGMENT = "icp_segment"
    PERSONA_DEFINED = "persona_defined"
    PAIN_POINT = "pain_point"

    # Lead intelligence
    LEAD_FOUND = "lead_found"
    LEAD_QUALIFIED = "lead_qualified"
    LEAD_ENRICHED = "lead_enriched"
    LEAD_JUSTIFICATION = "lead_justification"

    # Campaign insights
    CHANNEL_RECOMMENDED = "channel_recommended"
    MESSAGE_CRAFTED = "message_crafted"

    # Knowledge Web - Evidence-backed discoveries
    EVIDENCED_FACT = "evidenced_fact"
    ENTITY_DISCOVERED = "entity_discovered"
    RELATION_DISCOVERED = "relation_discovered"
    SIGNAL_DETECTED = "signal_detected"

    # Generic
    INSIGHT = "insight"
    QUESTION = "question"
    COLLABORATION_REQUEST = "collaboration_request"


class EvidenceSource(BaseModel):
    """Source information for evidenced facts."""

    source_type: str = Field(..., description="Type of source (acra, newsapi, etc.)")
    source_name: str = Field(..., description="Name of the source")
    source_url: str | None = Field(default=None, description="URL to the source")
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class EvidencedDiscovery(BaseModel):
    """A discovery backed by evidence with full provenance.

    Unlike regular AgentMessage, EvidencedDiscovery requires:
    - At least one source with URL
    - Explicit confidence score
    - Raw excerpt from source
    """

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # The claim being made
    claim: str = Field(..., description="The factual claim")
    fact_type: str = Field(..., description="Type of fact (company_info, funding, etc.)")

    # Evidence (REQUIRED - no claim without evidence)
    sources: list[EvidenceSource] = Field(
        ..., min_length=1, description="Sources supporting this claim"
    )
    raw_excerpts: list[str] = Field(
        default_factory=list, description="Original text from sources"
    )

    # Extracted structured data
    extracted_data: dict[str, Any] = Field(default_factory=dict)

    # Related entities
    related_entities: list[str] = Field(default_factory=list)

    # Agent context
    from_agent: str = Field(..., description="Agent that discovered this")
    mcp_server: str | None = Field(default=None, description="MCP server that provided data")

    # Verification
    verification_count: int = Field(default=1, description="Number of sources confirming")
    is_verified: bool = Field(default=False, description="Manually verified")

    @property
    def primary_source(self) -> EvidenceSource:
        """Get the primary source."""
        return self.sources[0]

    @property
    def confidence(self) -> float:
        """Calculate overall confidence from sources."""
        if not self.sources:
            return 0.0
        return sum(s.confidence for s in self.sources) / len(self.sources)


class AgentMessage(BaseModel):
    """A message exchanged between agents."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Routing
    from_agent: str = Field(..., description="Source agent ID")
    to_agent: str | None = Field(default=None, description="Target agent ID (None for broadcast)")

    # Content
    discovery_type: DiscoveryType = Field(...)
    title: str = Field(..., description="Brief description of discovery")
    content: dict[str, Any] = Field(default_factory=dict, description="Discovery payload")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    # Evidence (optional - for evidenced discoveries)
    evidence: EvidencedDiscovery | None = Field(
        default=None, description="Evidence backing this discovery"
    )

    # Context
    analysis_id: UUID | None = Field(default=None, description="Related analysis session")
    in_reply_to: UUID | None = Field(default=None, description="Reply to another message")
    requires_response: bool = Field(default=False)


class AgentBus:
    """Central hub for agent-to-agent communication.

    Implements pub/sub pattern for dynamic agent collaboration:
    - Agents subscribe to discovery types they care about
    - Agents publish discoveries for others to react to
    - The bus routes messages and maintains history

    Example:
        bus = AgentBus()

        # Subscribe to competitor discoveries
        async def on_competitor_found(msg: AgentMessage):
            print(f"New competitor: {msg.content}")

        bus.subscribe("market-intelligence", DiscoveryType.COMPETITOR_FOUND, on_competitor_found)

        # Publish a discovery
        await bus.publish(
            from_agent="competitor-analyst",
            discovery_type=DiscoveryType.COMPETITOR_FOUND,
            title="Found new competitor: Acme Corp",
            content={"name": "Acme Corp", "website": "acme.com"},
        )
    """

    def __init__(self) -> None:
        # Subscriptions: {discovery_type: {agent_id: [handlers]}}
        self._subscriptions: dict[DiscoveryType, dict[str, list[Callable]]] = {}

        # All subscriptions regardless of type: {agent_id: [handlers]}
        self._wildcard_subscriptions: dict[str, list[Callable]] = {}

        # Message history for the current analysis
        self._message_history: list[AgentMessage] = []

        # WebSocket broadcast callback (set by orchestrator)
        self._ws_broadcast: Callable[[AgentMessage], Coroutine] | None = None

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    def set_ws_broadcast(self, callback: Callable[[AgentMessage], Coroutine]) -> None:
        """Set WebSocket broadcast callback for real-time frontend updates."""
        self._ws_broadcast = callback

    def subscribe(
        self,
        agent_id: str,
        discovery_type: DiscoveryType | None,
        handler: Callable[[AgentMessage], Coroutine],
    ) -> None:
        """Subscribe an agent to a discovery type.

        Args:
            agent_id: The subscribing agent's ID
            discovery_type: Type to subscribe to (None for all types)
            handler: Async callback when discovery is published
        """
        if discovery_type is None:
            # Wildcard subscription
            if agent_id not in self._wildcard_subscriptions:
                self._wildcard_subscriptions[agent_id] = []
            self._wildcard_subscriptions[agent_id].append(handler)
            logger.debug("agent_subscribed_wildcard", agent_id=agent_id)
        else:
            if discovery_type not in self._subscriptions:
                self._subscriptions[discovery_type] = {}
            if agent_id not in self._subscriptions[discovery_type]:
                self._subscriptions[discovery_type][agent_id] = []
            self._subscriptions[discovery_type][agent_id].append(handler)
            logger.debug(
                "agent_subscribed",
                agent_id=agent_id,
                discovery_type=discovery_type.value,
            )

    def unsubscribe(
        self,
        agent_id: str,
        discovery_type: DiscoveryType | None = None,
    ) -> None:
        """Unsubscribe an agent from discoveries.

        Args:
            agent_id: The agent to unsubscribe
            discovery_type: Specific type to unsubscribe from (None for all)
        """
        if discovery_type is None:
            # Unsubscribe from everything
            self._wildcard_subscriptions.pop(agent_id, None)
            for dt in self._subscriptions.values():
                dt.pop(agent_id, None)
        else:
            if discovery_type in self._subscriptions:
                self._subscriptions[discovery_type].pop(agent_id, None)

    async def publish(
        self,
        from_agent: str,
        discovery_type: DiscoveryType,
        title: str,
        content: dict[str, Any],
        confidence: float = 0.7,
        to_agent: str | None = None,
        analysis_id: UUID | None = None,
        in_reply_to: UUID | None = None,
        requires_response: bool = False,
        evidence: EvidencedDiscovery | None = None,
    ) -> AgentMessage:
        """Publish a discovery to the bus.

        Args:
            from_agent: Publishing agent's ID
            discovery_type: Type of discovery
            title: Brief description
            content: Discovery payload
            confidence: Confidence score (0-1)
            to_agent: Target agent for direct message (None for broadcast)
            analysis_id: Related analysis session
            in_reply_to: Reply to another message
            requires_response: Whether this needs a response
            evidence: Optional evidence backing this discovery

        Returns:
            The published message
        """
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            discovery_type=discovery_type,
            title=title,
            content=content,
            confidence=confidence,
            analysis_id=analysis_id,
            in_reply_to=in_reply_to,
            requires_response=requires_response,
            evidence=evidence,
        )

        async with self._lock:
            self._message_history.append(message)

        logger.info(
            "discovery_published",
            from_agent=from_agent,
            to_agent=to_agent,
            discovery_type=discovery_type.value,
            title=title,
        )

        # Broadcast to WebSocket if configured
        if self._ws_broadcast:
            try:
                await self._ws_broadcast(message)
            except Exception as e:
                logger.warning("ws_broadcast_failed", error=str(e))

        # Route to subscribers
        await self._route_message(message)

        return message

    async def _route_message(self, message: AgentMessage) -> None:
        """Route a message to appropriate subscribers."""
        handlers_called = 0

        # Direct message to specific agent
        if message.to_agent:
            # Check type-specific subscriptions
            if message.discovery_type in self._subscriptions:
                handlers = self._subscriptions[message.discovery_type].get(message.to_agent, [])
                for handler in handlers:
                    try:
                        await handler(message)
                        handlers_called += 1
                    except Exception as e:
                        logger.error(
                            "handler_error",
                            agent_id=message.to_agent,
                            error=str(e),
                        )

            # Check wildcard subscriptions
            handlers = self._wildcard_subscriptions.get(message.to_agent, [])
            for handler in handlers:
                try:
                    await handler(message)
                    handlers_called += 1
                except Exception as e:
                    logger.error(
                        "handler_error",
                        agent_id=message.to_agent,
                        error=str(e),
                    )
        else:
            # Broadcast to all subscribers of this type
            if message.discovery_type in self._subscriptions:
                for agent_id, handlers in self._subscriptions[message.discovery_type].items():
                    # Don't send back to sender
                    if agent_id == message.from_agent:
                        continue
                    for handler in handlers:
                        try:
                            await handler(message)
                            handlers_called += 1
                        except Exception as e:
                            logger.error(
                                "handler_error",
                                agent_id=agent_id,
                                error=str(e),
                            )

            # Also notify wildcard subscribers
            for agent_id, handlers in self._wildcard_subscriptions.items():
                if agent_id == message.from_agent:
                    continue
                for handler in handlers:
                    try:
                        await handler(message)
                        handlers_called += 1
                    except Exception as e:
                        logger.error(
                            "handler_error",
                            agent_id=agent_id,
                            error=str(e),
                        )

        logger.debug(
            "message_routed",
            message_id=str(message.id),
            handlers_called=handlers_called,
        )

    async def publish_evidenced(
        self,
        from_agent: str,
        claim: str,
        fact_type: str,
        source_type: str,
        source_name: str,
        source_url: str | None = None,
        raw_excerpt: str | None = None,
        confidence: float = 0.8,
        extracted_data: dict[str, Any] | None = None,
        related_entities: list[str] | None = None,
        mcp_server: str | None = None,
        analysis_id: UUID | None = None,
    ) -> AgentMessage:
        """Publish an evidence-backed discovery.

        This is the preferred method for publishing facts with provenance.
        Every claim must have at least one source.

        Args:
            from_agent: Publishing agent's ID
            claim: The factual claim being made
            fact_type: Type of fact (company_info, funding, etc.)
            source_type: Type of source (acra, newsapi, etc.)
            source_name: Name of the source
            source_url: URL to the source
            raw_excerpt: Original text excerpt from source
            confidence: Confidence score (0-1)
            extracted_data: Structured data extracted from the fact
            related_entities: Entity names related to this fact
            mcp_server: MCP server that provided the data
            analysis_id: Related analysis session

        Returns:
            The published message with evidence
        """
        # Create evidence source
        evidence_source = EvidenceSource(
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
            confidence=confidence,
        )

        # Create evidenced discovery
        evidence = EvidencedDiscovery(
            claim=claim,
            fact_type=fact_type,
            sources=[evidence_source],
            raw_excerpts=[raw_excerpt] if raw_excerpt else [],
            extracted_data=extracted_data or {},
            related_entities=related_entities or [],
            from_agent=from_agent,
            mcp_server=mcp_server,
        )

        # Map fact_type to discovery_type
        discovery_type_map = {
            "company_info": DiscoveryType.COMPANY_PROFILE,
            "funding": DiscoveryType.COMPANY_FUNDING,
            "technology": DiscoveryType.COMPANY_TECH_STACK,
            "executive": DiscoveryType.LEAD_ENRICHED,
            "market_trend": DiscoveryType.MARKET_TREND,
            "competitor_move": DiscoveryType.COMPETITOR_SIGNAL,
            "hiring": DiscoveryType.SIGNAL_DETECTED,
            "product": DiscoveryType.COMPANY_PRODUCTS,
        }
        discovery_type = discovery_type_map.get(fact_type, DiscoveryType.EVIDENCED_FACT)

        return await self.publish(
            from_agent=from_agent,
            discovery_type=discovery_type,
            title=claim[:200],
            content=extracted_data or {},
            confidence=confidence,
            analysis_id=analysis_id,
            evidence=evidence,
        )

    async def publish_from_mcp_result(
        self,
        from_agent: str,
        mcp_result: Any,  # MCPQueryResult
        analysis_id: UUID | None = None,
    ) -> list[AgentMessage]:
        """Publish multiple evidenced discoveries from an MCP query result.

        Convenience method for publishing facts from MCP servers.

        Args:
            from_agent: Publishing agent's ID
            mcp_result: Result from an MCP server query
            analysis_id: Related analysis session

        Returns:
            List of published messages
        """
        messages = []

        # Import here to avoid circular imports
        try:
            from packages.mcp.src.types import EvidencedFact, MCPQueryResult

            if not isinstance(mcp_result, MCPQueryResult):
                logger.warning("invalid_mcp_result", type=type(mcp_result).__name__)
                return messages

            for fact in mcp_result.facts:
                if isinstance(fact, EvidencedFact):
                    message = await self.publish_evidenced(
                        from_agent=from_agent,
                        claim=fact.claim,
                        fact_type=fact.fact_type.value,
                        source_type=fact.source_type.value,
                        source_name=fact.source_name,
                        source_url=fact.source_url,
                        raw_excerpt=fact.raw_excerpt,
                        confidence=fact.confidence,
                        extracted_data=fact.extracted_data,
                        related_entities=fact.related_entities,
                        mcp_server=fact.mcp_server,
                        analysis_id=analysis_id,
                    )
                    messages.append(message)

        except ImportError:
            logger.warning("mcp_types_not_available")

        return messages

    def get_evidenced_discoveries(
        self,
        analysis_id: UUID | None = None,
        fact_type: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[EvidencedDiscovery]:
        """Get all evidenced discoveries matching criteria.

        Args:
            analysis_id: Filter by analysis session
            fact_type: Filter by fact type
            min_confidence: Minimum confidence threshold
            limit: Maximum results

        Returns:
            List of evidenced discoveries
        """
        discoveries = []

        for msg in self._message_history:
            if msg.evidence is None:
                continue

            if analysis_id and msg.analysis_id != analysis_id:
                continue

            if fact_type and msg.evidence.fact_type != fact_type:
                continue

            if msg.evidence.confidence < min_confidence:
                continue

            discoveries.append(msg.evidence)

            if len(discoveries) >= limit:
                break

        return discoveries

    def get_history(
        self,
        analysis_id: UUID | None = None,
        discovery_type: DiscoveryType | None = None,
        from_agent: str | None = None,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """Get message history with optional filters.

        Args:
            analysis_id: Filter by analysis session
            discovery_type: Filter by discovery type
            from_agent: Filter by source agent
            limit: Maximum messages to return

        Returns:
            List of matching messages (newest first)
        """
        messages = self._message_history.copy()

        if analysis_id:
            messages = [m for m in messages if m.analysis_id == analysis_id]
        if discovery_type:
            messages = [m for m in messages if m.discovery_type == discovery_type]
        if from_agent:
            messages = [m for m in messages if m.from_agent == from_agent]

        # Return newest first, limited
        return list(reversed(messages[-limit:]))

    def get_discoveries_for_agent(
        self,
        agent_id: str,
        analysis_id: UUID | None = None,
    ) -> list[AgentMessage]:
        """Get all discoveries relevant to an agent.

        This includes:
        - Messages directly addressed to the agent
        - Broadcasts of types the agent is subscribed to
        """
        relevant = []

        for msg in self._message_history:
            if analysis_id and msg.analysis_id != analysis_id:
                continue

            # Direct messages to this agent
            if msg.to_agent == agent_id:
                relevant.append(msg)
                continue

            # Broadcasts the agent is subscribed to
            if msg.to_agent is None:
                if msg.discovery_type in self._subscriptions:
                    if agent_id in self._subscriptions[msg.discovery_type]:
                        relevant.append(msg)
                        continue
                if agent_id in self._wildcard_subscriptions:
                    relevant.append(msg)

        return relevant

    def clear_history(self, analysis_id: UUID | None = None) -> None:
        """Clear message history.

        Args:
            analysis_id: Only clear messages for this analysis (None for all)
        """
        if analysis_id:
            self._message_history = [
                m for m in self._message_history if m.analysis_id != analysis_id
            ]
        else:
            self._message_history.clear()

    def get_active_agents(self) -> set[str]:
        """Get set of all agents that have published or subscribed."""
        agents = set()

        for subs in self._subscriptions.values():
            agents.update(subs.keys())
        agents.update(self._wildcard_subscriptions.keys())

        for msg in self._message_history:
            agents.add(msg.from_agent)
            if msg.to_agent:
                agents.add(msg.to_agent)

        return agents


# Global singleton instance
_bus_instance: AgentBus | None = None


def get_agent_bus() -> AgentBus:
    """Get the global AgentBus singleton."""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = AgentBus()
    return _bus_instance


def reset_agent_bus() -> None:
    """Reset the global AgentBus (for testing)."""
    global _bus_instance
    _bus_instance = None
