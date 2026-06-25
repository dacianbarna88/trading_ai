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


DEFAULT_NEUTRAL_TRUST: float = 50.0


@dataclass
class OrganismContribution:
    """Per-organism breakdown for trust-weighted collective decisions."""

    organism_name: str
    confidence: float
    trust_used: float
    packet_trust: float
    weight: float
    weighted_contribution: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "organism_name": self.organism_name,
            "confidence": round(self.confidence, 2),
            "trust_used": round(self.trust_used, 2),
            "packet_trust": round(self.packet_trust, 2),
            "weight": round(self.weight, 4),
            "weighted_contribution": round(self.weighted_contribution, 2),
        }


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
    unweighted_confidence: float = 0.0
    trust_weighted_confidence: float = 0.0
    organism_contributions: list[OrganismContribution] = field(default_factory=list)
    trust_weighting_applied: bool = False
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
            "unweighted_confidence": round(self.unweighted_confidence, 2),
            "trust_weighted_confidence": round(self.trust_weighted_confidence, 2),
            "trust_weighting_applied": self.trust_weighting_applied,
            "organism_contributions": [item.to_dict() for item in self.organism_contributions],
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

    def resolve_trust_weight(
        self,
        packet: EvidencePacket,
        trust_weights: dict[str, float] | None,
    ) -> float:
        """Resolve trust for weighting — memory trust, packet trust, or neutral 50."""
        if trust_weights is not None:
            if packet.organism_name in trust_weights:
                return max(0.0, min(100.0, float(trust_weights[packet.organism_name])))
            return DEFAULT_NEUTRAL_TRUST
        return max(0.0, min(100.0, float(packet.trust)))

    def aggregate(self, trust_weights: dict[str, float] | None = None) -> CollectiveDecision:
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
                unweighted_confidence=0.0,
                trust_weighted_confidence=0.0,
                trust_weighting_applied=trust_weights is not None,
            )
            self._decisions.append(decision)
            return decision

        confidences = [p.confidence for p in packets]
        unweighted_confidence = sum(confidences) / len(confidences)

        contributions: list[OrganismContribution] = []
        weights: list[float] = []
        trusts_used: list[float] = []

        for packet in packets:
            trust_used = self.resolve_trust_weight(packet, trust_weights)
            weight = trust_used / 100.0
            weights.append(weight)
            trusts_used.append(trust_used)
            contributions.append(
                OrganismContribution(
                    organism_name=packet.organism_name,
                    confidence=packet.confidence,
                    trust_used=trust_used,
                    packet_trust=packet.trust,
                    weight=weight,
                    weighted_contribution=packet.confidence * weight,
                )
            )

        weight_sum = sum(weights) or 1.0
        trust_weighted_confidence = sum(c.weighted_contribution for c in contributions) / weight_sum
        collective_trust = sum(trusts_used) / len(trusts_used)
        collective_confidence = trust_weighted_confidence

        mean_conf = unweighted_confidence
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
        spread = variance ** 0.5
        agreement = max(0.0, 100.0 - spread * 2.0)
        disagreement = min(100.0, spread * 2.0)

        level = self._classify_level(collective_confidence, len(packets))
        organisms = [p.organism_name for p in packets]
        summaries = [p.observation_summary for p in packets]

        explanation = self._build_explanation(
            packets,
            collective_confidence,
            collective_trust,
            agreement,
            disagreement,
            level,
            unweighted_confidence,
            trust_weighted_confidence,
            trust_weights is not None,
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
            unweighted_confidence=unweighted_confidence,
            trust_weighted_confidence=trust_weighted_confidence,
            organism_contributions=contributions,
            trust_weighting_applied=trust_weights is not None,
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
        unweighted_confidence: float = 0.0,
        trust_weighted_confidence: float = 0.0,
        memory_trust_weighting: bool = False,
    ) -> str:
        weight_label = "memory-calibrated trust" if memory_trust_weighting else "packet trust"
        parts = [
            f"Collective assessment: {level.value}.",
            f"Trust-weighted confidence {trust_weighted_confidence:.1f} "
            f"(unweighted {unweighted_confidence:.1f}) from {len(packets)} organism(s).",
            f"Weighting: {weight_label}. Mean trust used {trust:.1f}.",
            f"Agreement {agreement:.1f}% disagreement {disagreement:.1f}%.",
        ]
        for packet in packets:
            parts.append(
                f"[{packet.organism_name}] confidence={packet.confidence:.1f} "
                f"trust={packet.trust:.1f}: {packet.explanation}"
            )
        parts.append("RESEARCH_ONLY — not a trade instruction.")
        return " ".join(parts)
