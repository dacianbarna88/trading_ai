"""In-memory Knowledge Core — validated pattern registry."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from research_core.ecosystem.evidence_packet import EvidencePacket


class PatternStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    PROMOTED = "PROMOTED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


@dataclass
class KnowledgePattern:
    pattern_id: str
    description: str
    status: PatternStatus
    confidence: float
    trust: float
    success_conditions: list[str] = field(default_factory=list)
    failure_conditions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeCore:
    """
    Central memory for validated patterns and evidence references.
    Sprint 2: in-memory only — no persistence layer.
    """

    def __init__(self) -> None:
        self._patterns: dict[str, KnowledgePattern] = {}
        self._received_packets: list[EvidencePacket] = []
        self._learning_events: list[dict[str, Any]] = []

    def on_packet(self, packet: EvidencePacket) -> None:
        """Subscriber hook — record packets for audit and knowledge linkage."""
        self._received_packets.append(packet)
        if packet.knowledge_reference and packet.knowledge_reference in self._patterns:
            pattern = self._patterns[packet.knowledge_reference]
            pattern.updated_at = datetime.now(timezone.utc)
            pattern.metadata["last_packet_confidence"] = packet.confidence

    def store_validated_pattern(
        self,
        pattern_id: str,
        description: str,
        confidence: float,
        trust: float,
        success_conditions: list[str] | None = None,
        failure_conditions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgePattern:
        pattern = KnowledgePattern(
            pattern_id=pattern_id,
            description=description,
            status=PatternStatus.VALIDATED,
            confidence=confidence,
            trust=trust,
            success_conditions=success_conditions or [],
            failure_conditions=failure_conditions or [],
            metadata=metadata or {},
        )
        self._patterns[pattern_id] = pattern
        return deepcopy(pattern)

    def retrieve_pattern(self, pattern_id: str) -> KnowledgePattern | None:
        pattern = self._patterns.get(pattern_id)
        return deepcopy(pattern) if pattern else None

    def update_pattern(self, pattern_id: str, updates: dict[str, Any]) -> KnowledgePattern | None:
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None
        for key, value in updates.items():
            if key == "status" and isinstance(value, str):
                pattern.status = PatternStatus(value)
            elif hasattr(pattern, key):
                setattr(pattern, key, value)
        pattern.updated_at = datetime.now(timezone.utc)
        return deepcopy(pattern)

    def archive_pattern(self, pattern_id: str, reason: str) -> KnowledgePattern | None:
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None
        pattern.status = PatternStatus.ARCHIVED
        pattern.metadata["archive_reason"] = reason
        pattern.updated_at = datetime.now(timezone.utc)
        self._record_learning("ARCHIVE", pattern_id, reason)
        return deepcopy(pattern)

    def promote_pattern(self, pattern_id: str, reason: str) -> KnowledgePattern | None:
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None
        pattern.status = PatternStatus.PROMOTED
        pattern.metadata["promote_reason"] = reason
        pattern.updated_at = datetime.now(timezone.utc)
        self._record_learning("PROMOTE", pattern_id, reason)
        return deepcopy(pattern)

    def reject_pattern(self, pattern_id: str, reason: str) -> KnowledgePattern | None:
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None
        pattern.status = PatternStatus.REJECTED
        pattern.metadata["reject_reason"] = reason
        pattern.updated_at = datetime.now(timezone.utc)
        self._record_learning("REJECT", pattern_id, reason)
        return deepcopy(pattern)

    def list_candidates(self) -> list[KnowledgePattern]:
        return [
            deepcopy(p)
            for p in self._patterns.values()
            if p.status in (PatternStatus.CANDIDATE, PatternStatus.VALIDATED)
        ]

    def knowledge_statistics(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for pattern in self._patterns.values():
            by_status[pattern.status.value] = by_status.get(pattern.status.value, 0) + 1
        return {
            "total_patterns": len(self._patterns),
            "by_status": by_status,
            "packets_received": len(self._received_packets),
            "learning_events": len(self._learning_events),
        }

    def packet_count(self) -> int:
        return len(self._received_packets)

    def learning_events(self) -> list[dict[str, Any]]:
        return list(self._learning_events)

    def _record_learning(self, event_type: str, pattern_id: str, detail: str) -> None:
        self._learning_events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "pattern_id": pattern_id,
                "detail": detail,
            }
        )
