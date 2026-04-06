"""Observability package for Kairos.

Provides real-time monitoring of agent execution via AgentBus subscription.
Implements continuous insight posture from the agentic-os pattern.
"""

from .observer import AgentObserver, AnomalyAlert, AnomalyDetector, ObservationMetrics

__all__ = [
    "AgentObserver",
    "ObservationMetrics",
    "AnomalyDetector",
    "AnomalyAlert",
]
