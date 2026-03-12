"""Journey Orchestrator — parallel agent wave execution with Redis checkpointing.

Replaces the sequential for-loop in analysis.py with:
  1. A dependency-graph-driven wave executor (agents in same wave run concurrently)
  2. Redis-backed checkpoints so interrupted analyses can resume

Based on agentic-os JourneyOrchestrator + JourneyCheckpoint pattern.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from packages.core.src.agent_bus import AgentBus
from packages.governance.src.trust import TrustContext
from services.gateway.src.cache import CacheBackend
from services.gateway.src.services.task_decomposition import TaskDependencyGraph

logger = structlog.get_logger()

CHECKPOINT_TTL = 21_600  # 6 hours
CHECKPOINT_PREFIX = "gtm:journey:"


@dataclass
class JourneyCheckpoint:
    """Persistent snapshot of journey progress."""

    analysis_id: UUID
    wave_index: int                          # Most recently completed wave (0-based)
    completed_agents: list[str] = field(default_factory=list)
    partial_results: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_json(self) -> str:
        return json.dumps(
            {
                "analysis_id": str(self.analysis_id),
                "wave_index": self.wave_index,
                "completed_agents": self.completed_agents,
                "partial_results": self.partial_results,
                "created_at": self.created_at,
            },
            default=str,
        )

    @classmethod
    def from_json(cls, raw: str) -> JourneyCheckpoint:
        data = json.loads(raw)
        return cls(
            analysis_id=UUID(data["analysis_id"]),
            wave_index=data["wave_index"],
            completed_agents=data.get("completed_agents", []),
            partial_results=data.get("partial_results", {}),
            created_at=data.get("created_at", ""),
        )


class JourneyOrchestrator:
    """Executes agent waves with parallelism, gating, and checkpointing.

    Usage:
        orchestrator = JourneyOrchestrator(bus, cache, trust_context)
        results = await orchestrator.execute_graph(graph, analysis_id, context, agent_runners)

    agent_runners is a dict mapping agent_name → async callable(context) → dict
    """

    def __init__(
        self,
        bus: AgentBus,
        cache: CacheBackend | None = None,
        trust_context: TrustContext | None = None,
    ) -> None:
        self._bus = bus
        self._cache = cache
        self._trust = trust_context

    async def execute_graph(
        self,
        graph: TaskDependencyGraph,
        analysis_id: UUID,
        context: dict[str, Any],
        agent_runners: dict[str, Any],  # {agent_name: async callable}
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Execute all waves in the dependency graph.

        Agents within the same wave run concurrently via asyncio.gather().
        Between waves, trust gating is applied (pauses in SUPERVISED mode).
        After each wave, progress is checkpointed to Redis.

        Args:
            graph: Dependency graph from TaskDecompositionService
            analysis_id: Current analysis UUID
            context: Shared context dict passed to all agents
            agent_runners: {agent_name: async function(context) -> dict}
            progress_callback: Optional async(agent_id, wave_idx, total_waves) -> None

        Returns:
            Merged dict of all agent results keyed by agent_name
        """
        waves = graph.topological_order()
        merged_results: dict[str, Any] = {}
        completed_agents: list[str] = []

        # Check for resumable checkpoint
        start_wave = 0
        checkpoint = await self.load_checkpoint(analysis_id)
        if checkpoint:
            start_wave = checkpoint.wave_index + 1
            completed_agents = checkpoint.completed_agents
            merged_results = checkpoint.partial_results
            logger.info(
                "journey_resumed",
                analysis_id=str(analysis_id),
                resuming_from_wave=start_wave,
                already_completed=completed_agents,
            )

        for wave_idx, wave in enumerate(waves):
            if wave_idx < start_wave:
                continue  # Already completed this wave

            # Filter to agents that have runners and weren't already completed
            runnable = [
                agent_name for agent_name in wave
                if agent_name in agent_runners and agent_name not in completed_agents
            ]

            if not runnable:
                logger.debug("journey_wave_skipped", wave_idx=wave_idx, wave=wave)
                continue

            # Trust gate between waves (pauses in SUPERVISED mode)
            if wave_idx > start_wave and self._trust:
                previous_agents = waves[wave_idx - 1] if wave_idx > 0 else []
                gate_from = ", ".join(previous_agents) if previous_agents else "start"
                gate_to = ", ".join(runnable)
                approved = await self._trust.gate_agent_handoff(
                    from_agent=gate_from,
                    to_agent=gate_to,
                    context={"wave": wave_idx, "agents": runnable},
                )
                if not approved:
                    logger.warning(
                        "journey_wave_rejected_by_trust_gate",
                        wave_idx=wave_idx,
                        agents=runnable,
                    )
                    break

            logger.info(
                "journey_wave_started",
                analysis_id=str(analysis_id),
                wave_idx=wave_idx,
                agents=runnable,
                parallel=len(runnable) > 1,
            )

            # Execute agents in this wave concurrently
            wave_results = await self._execute_wave(
                wave_agents=runnable,
                context={**context, "_merged_results": merged_results},
                agent_runners=agent_runners,
                analysis_id=analysis_id,
            )

            # Merge results
            merged_results.update(wave_results)
            completed_agents.extend(runnable)

            # Checkpoint after each wave
            await self.save_checkpoint(
                JourneyCheckpoint(
                    analysis_id=analysis_id,
                    wave_index=wave_idx,
                    completed_agents=list(completed_agents),
                    partial_results=merged_results,
                )
            )

            if progress_callback:
                for agent_name in runnable:
                    with contextlib.suppress(Exception):
                        await progress_callback(agent_name, wave_idx, len(waves))

        return merged_results

    async def _execute_wave(
        self,
        wave_agents: list[str],
        context: dict[str, Any],
        agent_runners: dict[str, Any],
        analysis_id: UUID,
    ) -> dict[str, Any]:
        """Run all agents in a wave concurrently, return merged results."""

        async def run_one(agent_name: str) -> tuple[str, Any]:
            try:
                runner = agent_runners[agent_name]
                result = await runner(context)
                logger.debug(
                    "journey_agent_completed",
                    agent=agent_name,
                    analysis_id=str(analysis_id),
                )
                return agent_name, result
            except Exception as e:
                logger.error(
                    "journey_agent_failed",
                    agent=agent_name,
                    analysis_id=str(analysis_id),
                    error=str(e),
                )
                return agent_name, None

        tasks = [run_one(agent_name) for agent_name in wave_agents]
        pairs = await asyncio.gather(*tasks, return_exceptions=False)

        results = {name: result for name, result in pairs if result is not None}
        failed = [name for name, result in pairs if result is None]
        if failed:
            logger.warning(
                "journey_wave_agents_failed",
                failed_agents=failed,
                succeeded_agents=list(results.keys()),
            )
        return results

    async def save_checkpoint(self, cp: JourneyCheckpoint) -> None:
        """Persist checkpoint to cache with 6h TTL."""
        if self._cache is None:
            return
        key = f"{CHECKPOINT_PREFIX}{cp.analysis_id}"
        with contextlib.suppress(Exception):
            await self._cache.set(key, cp.to_json(), CHECKPOINT_TTL)
            logger.debug("journey_checkpoint_saved", analysis_id=str(cp.analysis_id))

    async def load_checkpoint(self, analysis_id: UUID) -> JourneyCheckpoint | None:
        """Load checkpoint from cache. Returns None if not found."""
        if self._cache is None:
            return None
        key = f"{CHECKPOINT_PREFIX}{analysis_id}"
        with contextlib.suppress(Exception):
            raw = await self._cache.get(key)
            if raw:
                cp = JourneyCheckpoint.from_json(raw)
                logger.info(
                    "journey_checkpoint_loaded",
                    analysis_id=str(analysis_id),
                    wave_index=cp.wave_index,
                )
                return cp
        return None

    async def clear_checkpoint(self, analysis_id: UUID) -> None:
        """Remove checkpoint after successful analysis completion."""
        if self._cache is None:
            return
        key = f"{CHECKPOINT_PREFIX}{analysis_id}"
        with contextlib.suppress(Exception):
            await self._cache.delete(key)
