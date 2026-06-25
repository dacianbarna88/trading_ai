"""Memory layer — ecosystem remembrance of evidence, decisions, and learning."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_core.ecosystem.collective_intelligence import CollectiveDecision
from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.feedback_loop import OrganismFeedback


@dataclass
class MemoryRecord:
    category: str
    timestamp: datetime
    payload: dict[str, Any]


class MemoryLayer:
    """
    In-memory temporal store for ecosystem cognition.
    Enables organisms and curiosity to reason over recent history.
    """

    def __init__(self, max_records_per_category: int = 500) -> None:
        self._max = max_records_per_category
        self._evidence: deque[MemoryRecord] = deque(maxlen=self._max)
        self._decisions: deque[MemoryRecord] = deque(maxlen=self._max)
        self._feedback: deque[MemoryRecord] = deque(maxlen=self._max)
        self._learning: deque[MemoryRecord] = deque(maxlen=self._max)
        self._performance: deque[MemoryRecord] = deque(maxlen=self._max)

    def remember_evidence(self, packet: EvidencePacket) -> None:
        self._evidence.append(
            MemoryRecord(
                category="evidence",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "organism_name": packet.organism_name,
                    "confidence": packet.confidence,
                    "trust": packet.trust,
                    "observation_summary": packet.observation_summary,
                    "explanation": packet.explanation,
                    "supporting_features": dict(packet.supporting_features),
                    "recommended_action": packet.recommended_action,
                    "knowledge_reference": packet.knowledge_reference,
                },
            )
        )

    def remember_decision(self, decision: CollectiveDecision) -> None:
        self._decisions.append(
            MemoryRecord(
                category="decision",
                timestamp=decision.timestamp,
                payload=decision.to_dict(),
            )
        )

    def remember_feedback(self, feedback: OrganismFeedback) -> None:
        self._feedback.append(
            MemoryRecord(
                category="feedback",
                timestamp=feedback.timestamp,
                payload=feedback.to_dict(),
            )
        )

    def remember_learning_event(
        self,
        organism_name: str,
        event_type: str,
        detail: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._learning.append(
            MemoryRecord(
                category="learning",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "organism_name": organism_name,
                    "event_type": event_type,
                    "detail": detail,
                    "metadata": metadata or {},
                },
            )
        )

    def remember_performance_snapshot(
        self,
        organism_name: str,
        metrics: dict[str, Any],
    ) -> None:
        self._performance.append(
            MemoryRecord(
                category="performance",
                timestamp=datetime.now(timezone.utc),
                payload={"organism_name": organism_name, "metrics": metrics},
            )
        )

    def recent_memory(self, category: str | None = None, limit: int = 20) -> list[MemoryRecord]:
        if category == "evidence":
            source = self._evidence
        elif category == "decision":
            source = self._decisions
        elif category == "feedback":
            source = self._feedback
        elif category == "learning":
            source = self._learning
        elif category == "performance":
            source = self._performance
        elif category is None:
            combined = sorted(
                self._all_records(),
                key=lambda r: r.timestamp,
                reverse=True,
            )
            return combined[:limit]
        else:
            return []

        records = list(source)
        records.reverse()
        return records[:limit]

    def memory_statistics(self) -> dict[str, Any]:
        return {
            "evidence_count": len(self._evidence),
            "decision_count": len(self._decisions),
            "feedback_count": len(self._feedback),
            "learning_event_count": len(self._learning),
            "performance_snapshot_count": len(self._performance),
            "total_records": (
                len(self._evidence)
                + len(self._decisions)
                + len(self._feedback)
                + len(self._learning)
                + len(self._performance)
            ),
        }

    def evidence_history(self) -> list[MemoryRecord]:
        return list(self._evidence)

    def decision_history(self) -> list[MemoryRecord]:
        return list(self._decisions)

    def _all_records(self) -> list[MemoryRecord]:
        return (
            list(self._evidence)
            + list(self._decisions)
            + list(self._feedback)
            + list(self._learning)
            + list(self._performance)
        )
