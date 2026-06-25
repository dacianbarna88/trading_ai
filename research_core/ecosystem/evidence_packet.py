"""Evidence packet — common language of the Trading AI Ecosystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EvidencePacket:
    """
    Standard message every organism publishes to the communication bus.
    Organisms never call each other directly — only through this structure.
    """

    organism_name: str
    timestamp: datetime
    observation_summary: str
    confidence: float
    trust: float
    explanation: str
    supporting_features: dict[str, Any] = field(default_factory=dict)
    recommended_action: str = "CONTINUE_OBSERVATION"
    knowledge_reference: str | None = None

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(100.0, float(self.confidence)))
        self.trust = max(0.0, min(100.0, float(self.trust)))

    @classmethod
    def create(
        cls,
        organism_name: str,
        observation_summary: str,
        confidence: float,
        trust: float,
        explanation: str,
        supporting_features: dict[str, Any] | None = None,
        recommended_action: str = "CONTINUE_OBSERVATION",
        knowledge_reference: str | None = None,
    ) -> EvidencePacket:
        return cls(
            organism_name=organism_name,
            timestamp=datetime.now(timezone.utc),
            observation_summary=observation_summary,
            confidence=confidence,
            trust=trust,
            explanation=explanation,
            supporting_features=supporting_features or {},
            recommended_action=recommended_action,
            knowledge_reference=knowledge_reference,
        )
