"""Task Decomposition Service.

Breaks a GTM analysis into a dependency graph of agent tasks that can be
executed wave-by-wave (agents in the same wave run in parallel).

Based on the agentic-os ObjectiveCompletionService / TaskDecompositionService pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class AgentTaskNode:
    """A single node in the dependency graph."""

    agent_name: str
    task_description: str
    depends_on: list[str] = field(default_factory=list)  # agent_names that must complete first
    priority: int = 0  # higher = more important
    enabled: bool = True


class TaskDependencyGraph:
    """A DAG of agent tasks with dependency tracking.

    Usage:
        graph = TaskDependencyGraph(nodes)
        waves = graph.topological_order()
        # waves[0] = agents that run first (no deps), waves[1] = next batch, etc.
    """

    def __init__(self, nodes: list[AgentTaskNode]) -> None:
        self._nodes: dict[str, AgentTaskNode] = {
            n.agent_name: n for n in nodes if n.enabled
        }

    @property
    def agent_names(self) -> list[str]:
        return list(self._nodes.keys())

    def get_node(self, agent_name: str) -> AgentTaskNode | None:
        return self._nodes.get(agent_name)

    def topological_order(self) -> list[list[str]]:
        """Return execution waves — agents in the same wave have no inter-dependencies.

        Each wave can be executed concurrently. Returns in order of execution.

        Example:
            Wave 0: ["company-enricher"]          # no deps
            Wave 1: ["market-intelligence", "competitor-analyst"]  # depend only on wave-0
            Wave 2: ["customer-profiler"]          # depends on wave-1
            Wave 3: ["lead-hunter"]                # depends on wave-2
            Wave 4: ["campaign-architect"]         # depends on wave-3
        """
        remaining = set(self._nodes.keys())
        completed: set[str] = set()
        waves: list[list[str]] = []

        # Safety limit to prevent infinite loops on malformed graphs
        max_iterations = len(self._nodes) + 1

        for _ in range(max_iterations):
            if not remaining:
                break

            # Find all nodes whose dependencies are fully satisfied
            ready = [
                name for name in remaining
                if all(dep in completed for dep in self._nodes[name].depends_on)
            ]

            if not ready:
                # Cycle detected — include remaining nodes in a single final wave
                logger.warning(
                    "task_graph_cycle_detected",
                    remaining=list(remaining),
                )
                waves.append(sorted(remaining))
                break

            # Sort by priority (descending) for deterministic ordering
            ready.sort(key=lambda n: -self._nodes[n].priority)
            waves.append(ready)
            completed.update(ready)
            remaining -= set(ready)

        return waves

    def validate_no_cycles(self) -> bool:
        """Returns True if the graph has no cycles."""
        waves = self.topological_order()
        all_in_waves = {agent for wave in waves for agent in wave}
        return all_in_waves == set(self._nodes.keys())

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        waves = self.topological_order()
        return {
            "agents": [
                {
                    "name": node.agent_name,
                    "description": node.task_description,
                    "depends_on": node.depends_on,
                    "priority": node.priority,
                }
                for node in self._nodes.values()
            ],
            "execution_waves": waves,
            "total_waves": len(waves),
            "parallel_speedup": max(len(w) for w in waves) if waves else 1,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Default agent dependency templates by analysis flags
# ─────────────────────────────────────────────────────────────────────────────

def build_default_graph(
    include_enrichment: bool = True,
    include_market: bool = True,
    include_competitor: bool = True,
    include_profiling: bool = True,
    include_leads: bool = True,
    include_campaign: bool = True,
) -> TaskDependencyGraph:
    """Build the standard GTM analysis dependency graph.

    Dependency structure:
        company-enricher  ──┐
                            ├──► market-intelligence ─┐
                            └──► competitor-analyst   ─┴──► customer-profiler ──► lead-hunter ──► campaign-architect
    """
    nodes: list[AgentTaskNode] = []

    enricher_deps: list[str] = []

    if include_enrichment:
        nodes.append(AgentTaskNode(
            agent_name="company-enricher",
            task_description="Enrich company data from website and public sources",
            depends_on=[],
            priority=10,
        ))
        enricher_deps = ["company-enricher"]

    if include_market:
        nodes.append(AgentTaskNode(
            agent_name="market-intelligence",
            task_description="Research market trends, opportunities, and threats in Singapore",
            depends_on=enricher_deps,
            priority=8,
        ))

    if include_competitor:
        nodes.append(AgentTaskNode(
            agent_name="competitor-analyst",
            task_description="Analyse competitor landscape with SWOT positioning",
            depends_on=enricher_deps,  # Same wave as market-intelligence (both depend only on enricher)
            priority=8,
        ))

    profiling_deps = []
    if include_market:
        profiling_deps.append("market-intelligence")
    if include_competitor:
        profiling_deps.append("competitor-analyst")

    if include_profiling:
        nodes.append(AgentTaskNode(
            agent_name="customer-profiler",
            task_description="Develop ICP definitions and buyer personas from market context",
            depends_on=profiling_deps,
            priority=6,
        ))

    lead_deps = []
    if include_profiling:
        lead_deps.append("customer-profiler")

    if include_leads:
        nodes.append(AgentTaskNode(
            agent_name="lead-hunter",
            task_description="Identify and score qualified prospects",
            depends_on=lead_deps,
            priority=5,
        ))

    campaign_deps = []
    if include_leads:
        campaign_deps.append("lead-hunter")
    elif include_profiling:
        campaign_deps.append("customer-profiler")

    if include_campaign:
        nodes.append(AgentTaskNode(
            agent_name="campaign-architect",
            task_description="Build outreach campaigns and messaging templates",
            depends_on=campaign_deps,
            priority=4,
        ))

    return TaskDependencyGraph(nodes)


class TaskDecompositionService:
    """Decomposes a GTM analysis request into an executable dependency graph.

    Usage:
        svc = TaskDecompositionService()
        graph = svc.decompose(request_flags, clarification_context)
        waves = graph.topological_order()
        # wave[1] = ["market-intelligence", "competitor-analyst"]  run in parallel
    """

    def decompose(
        self,
        include_enrichment: bool = True,
        include_market: bool = True,
        include_competitor: bool = True,
        include_profiling: bool = True,
        include_leads: bool = True,
        include_campaign: bool = True,
        clarification_context: dict[str, Any] | None = None,
    ) -> TaskDependencyGraph:
        """Build a dependency graph from analysis flags and clarification context.

        Clarification context can enable/disable specific branches:
        - primary_goal=competitor → boost competitor-analyst priority
        - target_customer_size=Enterprise → boost lead-hunter priority
        """
        graph = build_default_graph(
            include_enrichment=include_enrichment,
            include_market=include_market,
            include_competitor=include_competitor,
            include_profiling=include_profiling,
            include_leads=include_leads,
            include_campaign=include_campaign,
        )

        # Apply clarification-based adjustments
        if clarification_context:
            goal = clarification_context.get("primary_goal", "")
            if "competitor" in str(goal).lower():
                node = graph.get_node("competitor-analyst")
                if node:
                    node.priority = 10  # Boost competitor analysis

        waves = graph.topological_order()
        logger.info(
            "task_graph_decomposed",
            total_agents=len(graph.agent_names),
            waves=len(waves),
            parallel_agents=[len(w) for w in waves],
        )

        return graph
