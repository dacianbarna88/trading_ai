"""Abstract organism base class — architecture only, no market logic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from research_core.ecosystem.evidence_packet import EvidencePacket


class Organism(ABC):
    """
    Base class for all TAE organisms.
    Every concrete organism implements the full lifecycle without direct peer calls.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique organism identifier."""

    @abstractmethod
    def observe(self) -> dict[str, Any]:
        """Gather raw observations from the organism's domain."""

    @abstractmethod
    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        """Interpret observations into structured understanding."""

    @abstractmethod
    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        """Emit a standardized evidence packet for the communication bus."""

    @abstractmethod
    def explain(self, analysis: dict[str, Any]) -> str:
        """Human-readable explanation of the current analysis."""

    @abstractmethod
    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        """Integrate feedback and return learning summary."""

    @abstractmethod
    def receive_feedback(self, feedback: dict[str, Any]) -> None:
        """Accept ecosystem feedback (outcomes, trust deltas, peer signals)."""

    @abstractmethod
    def update_trust(self, delta: float, reason: str) -> float:
        """Apply trust adjustment and return new trust level."""

    @abstractmethod
    def health_status(self) -> dict[str, Any]:
        """Return operational health metrics for monitoring."""

    def run_cycle(self) -> EvidencePacket:
        """Standard observe → analyze → evidence pipeline."""
        observations = self.observe()
        analysis = self.analyze(observations)
        return self.produce_evidence(analysis)
