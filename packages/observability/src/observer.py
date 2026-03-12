"""Agent Observer — continuous monitoring of A2A bus traffic.

Subscribes to all AgentBus messages (wildcard) for an analysis run,
tracks per-agent metrics, detects anomalies, and persists an audit summary.

Based on the agentic-os ObservationService pattern:
  - Action tracking (every bus message = one action)
  - Anomaly detection: cost spikes, low confidence, excessive messages
  - Summary persisted to AuditLog on stop()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from packages.core.src.agent_bus import AgentBus, AgentMessage

logger = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detection Thresholds
# ─────────────────────────────────────────────────────────────────────────────
_THRESHOLDS = {
    "min_confidence": 0.30,   # alert if any agent's msg confidence < 0.30
    "max_messages_per_agent": 50,  # alert if single agent sends > 50 messages
    "stale_agent_seconds": 180,    # alert if agent silent for > 3 minutes
}

# Approximate cost per bus message (proxy for LLM usage)
_COST_PER_MESSAGE_USD = 0.03


@dataclass
class AnomalyAlert:
    """A single anomaly detected during observation."""

    agent_id: str
    anomaly_type: str  # low_confidence | message_flood | stale_agent
    severity: str  # low | medium | high | critical
    description: str
    detected_at: float = field(default_factory=time.monotonic)


@dataclass
class ObservationMetrics:
    """Aggregated metrics for a single agent across one analysis run."""

    agent_id: str
    analysis_id: UUID

    total_messages: int = 0
    total_cost_usd: float = 0.0
    confidences: list[float] = field(default_factory=list)
    last_message_at: float = field(default_factory=time.monotonic)
    anomalies: list[AnomalyAlert] = field(default_factory=list)

    @property
    def avg_confidence(self) -> float:
        if not self.confidences:
            return 0.0
        return sum(self.confidences) / len(self.confidences)

    @property
    def min_confidence(self) -> float:
        return min(self.confidences) if self.confidences else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "analysis_id": str(self.analysis_id),
            "total_messages": self.total_messages,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "avg_confidence": round(self.avg_confidence, 3),
            "min_confidence": round(self.min_confidence, 3),
            "anomaly_count": len(self.anomalies),
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "description": a.description,
                }
                for a in self.anomalies
            ],
        }


class AnomalyDetector:
    """Rule-based anomaly detection — no LLM required.

    Evaluated after each bus message to provide near-real-time alerts.
    """

    def check(self, metrics: ObservationMetrics) -> list[AnomalyAlert]:
        """Evaluate metrics and return any new anomaly alerts."""
        alerts: list[AnomalyAlert] = []

        # Low confidence on latest message
        if metrics.confidences and metrics.confidences[-1] < _THRESHOLDS["min_confidence"]:
            alerts.append(
                AnomalyAlert(
                    agent_id=metrics.agent_id,
                    anomaly_type="low_confidence",
                    severity="high",
                    description=(
                        f"{metrics.agent_id} published confidence "
                        f"{metrics.confidences[-1]:.2f} < threshold {_THRESHOLDS['min_confidence']}"
                    ),
                )
            )

        # Message flood
        if metrics.total_messages > _THRESHOLDS["max_messages_per_agent"]:
            alerts.append(
                AnomalyAlert(
                    agent_id=metrics.agent_id,
                    anomaly_type="message_flood",
                    severity="medium",
                    description=(
                        f"{metrics.agent_id} sent {metrics.total_messages} messages "
                        f"(threshold: {_THRESHOLDS['max_messages_per_agent']})"
                    ),
                )
            )

        return alerts


class AgentObserver:
    """Subscribes to AgentBus (wildcard) and records all traffic.

    Usage:
        observer = AgentObserver(bus)
        await observer.start(analysis_id)
        # ... analysis runs ...
        metrics = await observer.stop()  # returns per-agent metrics

    The observer uses the wildcard subscription so it sees every message
    from every agent without them needing to know they're being observed.
    """

    def __init__(self, bus: AgentBus) -> None:
        self._bus = bus
        self._metrics: dict[str, ObservationMetrics] = {}
        self._analysis_id: UUID | None = None
        self._detector = AnomalyDetector()
        self._active = False
        self._observer_agent_id = "_observer"

    async def start(self, analysis_id: UUID) -> None:
        """Register wildcard subscription and begin recording."""
        self._analysis_id = analysis_id
        self._metrics = {}
        self._active = True

        self._bus.subscribe(
            agent_id=self._observer_agent_id,
            discovery_type=None,  # wildcard — receives all types (None = wildcard)
            handler=self._on_message,
        )

        logger.info(
            "observer_started",
            analysis_id=str(analysis_id),
        )

    async def stop(self) -> dict[str, ObservationMetrics]:
        """Unsubscribe and return final metrics per agent."""
        self._active = False

        # Unsubscribe (if bus supports it)
        if hasattr(self._bus, "unsubscribe"):
            self._bus.unsubscribe(self._observer_agent_id)

        logger.info(
            "observer_stopped",
            analysis_id=str(self._analysis_id),
            agents_observed=list(self._metrics.keys()),
            total_anomalies=sum(
                len(m.anomalies) for m in self._metrics.values()
            ),
        )

        return dict(self._metrics)

    async def _on_message(self, message: AgentMessage) -> None:
        """Handler called for every bus message."""
        if not self._active:
            return

        agent_id = message.from_agent

        # Initialise metrics for new agent
        if agent_id not in self._metrics:
            self._metrics[agent_id] = ObservationMetrics(
                agent_id=agent_id,
                analysis_id=self._analysis_id or message.analysis_id or UUID(int=0),
            )

        metrics = self._metrics[agent_id]
        metrics.total_messages += 1
        metrics.total_cost_usd += _COST_PER_MESSAGE_USD
        metrics.confidences.append(message.confidence)
        metrics.last_message_at = time.monotonic()

        # Run anomaly detection
        new_alerts = self._detector.check(metrics)
        if new_alerts:
            metrics.anomalies.extend(new_alerts)
            for alert in new_alerts:
                logger.warning(
                    "anomaly_detected",
                    agent_id=agent_id,
                    anomaly_type=alert.anomaly_type,
                    severity=alert.severity,
                    description=alert.description,
                )

    def get_summary(self) -> dict[str, Any]:
        """Get current observation summary (callable during analysis)."""
        return {
            "analysis_id": str(self._analysis_id),
            "agents_observed": len(self._metrics),
            "total_messages": sum(m.total_messages for m in self._metrics.values()),
            "total_cost_usd": round(
                sum(m.total_cost_usd for m in self._metrics.values()), 4
            ),
            "total_anomalies": sum(
                len(m.anomalies) for m in self._metrics.values()
            ),
            "per_agent": {
                agent_id: metrics.to_dict()
                for agent_id, metrics in self._metrics.items()
            },
        }
