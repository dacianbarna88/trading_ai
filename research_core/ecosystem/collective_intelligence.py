"""Collective intelligence — fuse evidence packets into research decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from research_core.ecosystem.evidence_packet import EvidencePacket


class CollectiveConfidenceLevel(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class CollectiveDecision:
    """
    Research-stage collective output — NOT BUY/SELL.
    """

    collective_confidence: float
    collective_trust: float
    agreement: float
    disagreement: float
    organism_participation: int
    confidence_level: CollectiveConfidenceLevel
    explanation: str
    contributing_organisms: list[str] = field(default_factory=list)
    packet_summaries: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "collective_confidence": round(self.collective_confidence, 2),
            "collective_trust": round(self.collective_trust, 2),
            "agreement": round(self.agreement, 2),
            "disagreement": round(self.disagreement, 2),
            "organism_participation": self.organism_participation,
            "confidence_level": self.confidence_level.value,
            "explanation": self.explanation,
            "contributing_organisms": self.contributing_organisms,
        }


class CollectiveIntelligence:
    """
    Receives EvidencePackets via the bus and produces CollectiveDecision.
    """

    HIGH_THRESHOLD: float = 75.0
    MEDIUM_THRESHOLD: float = 55.0
    LOW_THRESHOLD: float = 35.0
    MIN_PACKETS: int = 1

    def __init__(self) -> None:
        self._packets: list[EvidencePacket] = []
        self._decisions: list[CollectiveDecision] = []

    def on_packet(self, packet: EvidencePacket) -> None:
        self._packets.append(packet)

    def clear_session(self) -> None:
        self._packets.clear()

    def aggregate(self) -> CollectiveDecision:
        packets = list(self._packets)
        if len(packets) < self.MIN_PACKETS:
            decision = CollectiveDecision(
                collective_confidence=0.0,
                collective_trust=0.0,
                agreement=0.0,
                disagreement=0.0,
                organism_participation=0,
                confidence_level=CollectiveConfidenceLevel.INSUFFICIENT_EVIDENCE,
                explanation="No evidence packets received — insufficient evidence for collective view.",
            )
            self._decisions.append(decision)
            return decision

        confidences = [p.confidence for p in packets]
        trusts = [p.trust for p in packets]
        weights = [p.trust / 100.0 for p in packets]
        weight_sum = sum(weights) or 1.0

        collective_confidence = sum(c * w for c, w in zip(confidences, weights)) / weight_sum
        collective_trust = sum(trusts) / len(trusts)

        mean_conf = sum(confidences) / len(confidences)
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
        spread = variance ** 0.5
        agreement = max(0.0, 100.0 - spread * 2.0)
        disagreement = min(100.0, spread * 2.0)

        level = self._classify_level(collective_confidence, len(packets))
        organisms = [p.organism_name for p in packets]
        summaries = [p.observation_summary for p in packets]

        explanation = self._build_explanation(
            packets, collective_confidence, collective_trust, agreement, disagreement, level
        )

        decision = CollectiveDecision(
            collective_confidence=collective_confidence,
            collective_trust=collective_trust,
            agreement=agreement,
            disagreement=disagreement,
            organism_participation=len(packets),
            confidence_level=level,
            explanation=explanation,
            contributing_organisms=organisms,
            packet_summaries=summaries,
        )
        self._decisions.append(decision)
        return decision

    def decisions(self) -> list[CollectiveDecision]:
        return list(self._decisions)

    def packet_count(self) -> int:
        return len(self._packets)

    def _classify_level(self, confidence: float, packet_count: int) -> CollectiveConfidenceLevel:
        if packet_count < self.MIN_PACKETS:
            return CollectiveConfidenceLevel.INSUFFICIENT_EVIDENCE
        if confidence >= self.HIGH_THRESHOLD:
            return CollectiveConfidenceLevel.HIGH_CONFIDENCE
        if confidence >= self.MEDIUM_THRESHOLD:
            return CollectiveConfidenceLevel.MEDIUM_CONFIDENCE
        if confidence >= self.LOW_THRESHOLD:
            return CollectiveConfidenceLevel.LOW_CONFIDENCE
        return CollectiveConfidenceLevel.INSUFFICIENT_EVIDENCE

    def _build_explanation(
        self,
        packets: list[EvidencePacket],
        confidence: float,
        trust: float,
        agreement: float,
        disagreement: float,
        level: CollectiveConfidenceLevel,
    ) -> str:
        parts = [
            f"Collective assessment: {level.value}.",
            f"Weighted confidence {confidence:.1f} from {len(packets)} organism(s).",
            f"Mean trust {trust:.1f}. Agreement {agreement:.1f}% disagreement {disagreement:.1f}%.",
        ]
        for packet in packets:
            parts.append(
                f"[{packet.organism_name}] confidence={packet.confidence:.1f} "
                f"trust={packet.trust:.1f}: {packet.explanation}"
            )
        parts.append("RESEARCH_ONLY — not a trade instruction.")
        return " ".join(parts)
