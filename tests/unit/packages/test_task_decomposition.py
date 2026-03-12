"""Unit tests for TaskDependencyGraph and TaskDecompositionService."""

from __future__ import annotations

import pytest

from services.gateway.src.services.task_decomposition import (
    TaskDecompositionService,
    TaskDependencyGraph,
    build_default_graph,
)


@pytest.mark.unit
def test_default_graph_has_no_cycles():
    """The default GTM graph must be a valid DAG (no cycles)."""
    graph = build_default_graph()

    assert graph.validate_no_cycles() is True


@pytest.mark.unit
def test_market_intel_and_competitor_same_wave():
    """market-intelligence and competitor-analyst should run in parallel (same wave)."""
    graph = build_default_graph()
    waves = graph.topological_order()

    # Find which wave index each agent lives in
    market_wave = None
    competitor_wave = None
    for idx, wave in enumerate(waves):
        if "market-intelligence" in wave:
            market_wave = idx
        if "competitor-analyst" in wave:
            competitor_wave = idx

    assert market_wave is not None, "market-intelligence not found in any wave"
    assert competitor_wave is not None, "competitor-analyst not found in any wave"
    assert market_wave == competitor_wave, (
        f"Expected same wave but market-intelligence is in wave {market_wave} "
        f"and competitor-analyst is in wave {competitor_wave}"
    )


@pytest.mark.unit
def test_campaign_last_wave():
    """campaign-architect depends on lead-hunter and must appear in the final wave."""
    graph = build_default_graph()
    waves = graph.topological_order()

    last_wave = waves[-1]
    assert "campaign-architect" in last_wave, (
        f"Expected campaign-architect in last wave {last_wave}, got waves: {waves}"
    )


@pytest.mark.unit
def test_topological_waves_are_valid():
    """Each agent must appear in exactly one wave — no duplicates across waves."""
    graph = build_default_graph()
    waves = graph.topological_order()

    all_agents_in_waves: list[str] = [agent for wave in waves for agent in wave]
    unique_agents = set(all_agents_in_waves)

    # No agent appears in two different waves
    assert len(all_agents_in_waves) == len(unique_agents), (
        "Some agents appear in multiple waves"
    )

    # All graph agents are accounted for
    assert unique_agents == set(graph.agent_names), (
        "Waves do not cover all agents in the graph"
    )


@pytest.mark.unit
def test_decompose_returns_graph():
    """TaskDecompositionService.decompose() should return a TaskDependencyGraph instance."""
    service = TaskDecompositionService()

    result = service.decompose()

    assert isinstance(result, TaskDependencyGraph)
    # Sanity check: returned graph also has no cycles
    assert result.validate_no_cycles() is True
    assert len(result.agent_names) > 0
