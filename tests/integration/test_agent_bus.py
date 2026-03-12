"""Integration tests for AgentBus pub/sub messaging infrastructure."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bus():
    """Fresh AgentBus instance per test — NOT the global singleton."""
    return AgentBus()


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_reaches_subscriber(bus: AgentBus):
    """A subscribed callback should be invoked when a matching message is published."""
    received: list[AgentMessage] = []

    async def handler(msg: AgentMessage) -> None:
        received.append(msg)

    bus.subscribe("market-intelligence", DiscoveryType.MARKET_TREND, handler)

    await bus.publish(
        from_agent="competitor-analyst",
        discovery_type=DiscoveryType.MARKET_TREND,
        title="Singapore fintech growing 30% YoY",
        content={"growth_rate": 0.30, "sector": "fintech"},
    )

    assert len(received) == 1
    assert received[0].title == "Singapore fintech growing 30% YoY"
    assert received[0].content["growth_rate"] == pytest.approx(0.30)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wildcard_subscription_receives_all_types(bus: AgentBus):
    """An agent subscribing with discovery_type=None should receive all message types."""
    received: list[AgentMessage] = []

    async def wildcard_handler(msg: AgentMessage) -> None:
        received.append(msg)

    bus.subscribe("observer-agent", None, wildcard_handler)

    types_to_publish = [
        DiscoveryType.MARKET_TREND,
        DiscoveryType.COMPETITOR_FOUND,
        DiscoveryType.LEAD_FOUND,
    ]

    for discovery_type in types_to_publish:
        await bus.publish(
            from_agent="source-agent",
            discovery_type=discovery_type,
            title=f"Discovery of type {discovery_type.value}",
            content={"type": discovery_type.value},
        )

    assert len(received) == 3
    received_types = {msg.discovery_type for msg in received}
    assert received_types == set(types_to_publish)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(bus: AgentBus):
    """A direct message (to_agent set) must not be delivered to other subscribers."""
    agent_a_received: list[AgentMessage] = []
    agent_b_received: list[AgentMessage] = []

    async def handler_a(msg: AgentMessage) -> None:
        agent_a_received.append(msg)

    async def handler_b(msg: AgentMessage) -> None:
        agent_b_received.append(msg)

    bus.subscribe("agent-a", DiscoveryType.INSIGHT, handler_a)
    bus.subscribe("agent-b", DiscoveryType.INSIGHT, handler_b)

    # Send directly to agent-a only
    await bus.publish(
        from_agent="orchestrator",
        discovery_type=DiscoveryType.INSIGHT,
        title="Private insight for agent-a",
        content={"secret": True},
        to_agent="agent-a",
    )

    assert len(agent_a_received) == 1
    assert len(agent_b_received) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_history_filtered_by_analysis_id(bus: AgentBus):
    """get_history() with an analysis_id should return only messages for that session."""
    analysis_alpha = uuid4()
    analysis_beta = uuid4()

    for i in range(3):
        await bus.publish(
            from_agent="agent-x",
            discovery_type=DiscoveryType.MARKET_TREND,
            title=f"Alpha trend {i}",
            content={"idx": i},
            analysis_id=analysis_alpha,
        )

    for i in range(2):
        await bus.publish(
            from_agent="agent-y",
            discovery_type=DiscoveryType.COMPETITOR_FOUND,
            title=f"Beta competitor {i}",
            content={"idx": i},
            analysis_id=analysis_beta,
        )

    alpha_messages = bus.get_history(analysis_id=analysis_alpha)
    beta_messages = bus.get_history(analysis_id=analysis_beta)

    assert len(alpha_messages) == 3
    assert len(beta_messages) == 2
    assert all(m.analysis_id == analysis_alpha for m in alpha_messages)
    assert all(m.analysis_id == analysis_beta for m in beta_messages)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_publishes_safe(bus: AgentBus):
    """Concurrent publishes should all be stored safely without race conditions."""
    num_publishes = 10
    analysis_id = uuid4()

    tasks = [
        bus.publish(
            from_agent=f"agent-{i}",
            discovery_type=DiscoveryType.INSIGHT,
            title=f"Concurrent insight {i}",
            content={"n": i},
            analysis_id=analysis_id,
        )
        for i in range(num_publishes)
    ]

    await asyncio.gather(*tasks)

    history = bus.get_history(analysis_id=analysis_id)
    assert len(history) == num_publishes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_message_confidence_stored(bus: AgentBus):
    """Confidence value passed to publish() should be retrievable from history."""
    analysis_id = uuid4()

    await bus.publish(
        from_agent="confidence-agent",
        discovery_type=DiscoveryType.LEAD_QUALIFIED,
        title="High confidence lead",
        content={"company": "Acme Pte Ltd"},
        confidence=0.75,
        analysis_id=analysis_id,
    )

    history = bus.get_history(analysis_id=analysis_id)

    assert len(history) == 1
    assert history[0].confidence == pytest.approx(0.75)
