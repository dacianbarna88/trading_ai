"""Feedback loop — CollectiveDecision drives organism learning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from research_core.ecosystem.collective_intelligence import CollectiveDecision
from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.organism import Organism


@dataclass
class OrganismFeedback:
    """Structured feedback delivered to a single organism after collective aggregation."""

    organism_name: str
    decision_level: str
    agreement_score: float
    disagreement_score: float
    confidence_delta: float
    trust_delta: float
    lesson: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "organism_name": self.organism_name,
            "decision_level": self.decision_level,
            "agreement_score": round(self.agreement_score, 2),
            "disagreement_score": round(self.disagreement_score, 2),
            "confidence_delta": round(self.confidence_delta, 2),
            "trust_delta": round(self.trust_delta, 2),
            "lesson": self.lesson,
            "timestamp": self.timestamp.isoformat(),
        }

    def as_receive_payload(self) -> dict[str, Any]:
        """Payload compatible with Organism.receive_feedback()."""
        return {
            "organism_name": self.organism_name,
            "decision_level": self.decision_level,
            "agreement_score": self.agreement_score,
            "disagreement_score": self.disagreement_score,
            "confidence_delta": self.confidence_delta,
            "trust_delta": self.trust_delta,
            "lesson": self.lesson,
            "reason": self.lesson,
            "summary": self.lesson,
            "timestamp": self.timestamp.isoformat(),
        }


class FeedbackLoop:
    """
    Translates CollectiveDecision into per-organism feedback and delivers it.
    Sprint 3: active cognition — decisions teach organisms.
    """

    def __init__(self) -> None:
        self._history: list[OrganismFeedback] = []

    def generate(
        self,
        decision: CollectiveDecision,
        packets: list[EvidencePacket],
    ) -> list[OrganismFeedback]:
        if not packets:
            return []

        mean_confidence = decision.collective_confidence
        feedback_batch: list[OrganismFeedback] = []

        for packet in packets:
            confidence_delta = mean_confidence - packet.confidence
            trust_delta = self._compute_trust_delta(
                packet, decision, confidence_delta
            )
            lesson = self._build_lesson(packet, decision, confidence_delta, trust_delta)
            feedback = OrganismFeedback(
                organism_name=packet.organism_name,
                decision_level=decision.confidence_level.value,
                agreement_score=decision.agreement,
                disagreement_score=decision.disagreement,
                confidence_delta=confidence_delta,
                trust_delta=trust_delta,
                lesson=lesson,
                timestamp=datetime.now(timezone.utc),
            )
            feedback_batch.append(feedback)
            self._history.append(feedback)

        return feedback_batch

    def deliver(
        self,
        feedback_batch: list[OrganismFeedback],
        organisms: list[Organism],
    ) -> int:
        organism_map = {o.name: o for o in organisms}
        delivered = 0
        for feedback in feedback_batch:
            organism = organism_map.get(feedback.organism_name)
            if organism is None:
                continue
            organism.receive_feedback(feedback.as_receive_payload())
            organism.learn(feedback.as_receive_payload())
            delivered += 1
        return delivered

    def history(self) -> list[OrganismFeedback]:
        return list(self._history)

    def count(self) -> int:
        return len(self._history)

    def _compute_trust_delta(
        self,
        packet: EvidencePacket,
        decision: CollectiveDecision,
        confidence_delta: float,
    ) -> float:
        delta = 0.0
        if decision.agreement > 65 and abs(confidence_delta) < 15:
            delta += 1.5
        if decision.disagreement > 35:
            delta -= 0.5
        if packet.confidence > decision.collective_confidence + 20:
            delta += 0.5
        if packet.confidence < decision.collective_confidence - 20:
            delta -= 1.0
        if decision.confidence_level.value == "HIGH_CONFIDENCE":
            delta += 1.0
        if decision.confidence_level.value == "INSUFFICIENT_EVIDENCE":
            delta -= 1.5
        return round(max(-5.0, min(5.0, delta)), 2)

    def _build_lesson(
        self,
        packet: EvidencePacket,
        decision: CollectiveDecision,
        confidence_delta: float,
        trust_delta: float,
    ) -> str:
        alignment = "aligned" if abs(confidence_delta) < 10 else "divergent"
        return (
            f"Collective {decision.confidence_level.value} with agreement "
            f"{decision.agreement:.1f}%. Your confidence was "
            f"{packet.confidence:.1f} ({alignment} vs collective {decision.collective_confidence:.1f}). "
            f"Trust adjustment {trust_delta:+.1f}. RESEARCH_ONLY reflection."
        )
