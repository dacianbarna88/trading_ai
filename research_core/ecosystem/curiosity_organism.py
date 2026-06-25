"""Curiosity organism — meta-research question generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_core.ecosystem.collective_intelligence import CollectiveDecision
from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.memory_layer import MemoryLayer
from research_core.ecosystem.organism import Organism
from research_core.ecosystem.regime_trust import RegimeAwareTrust, TrustRegime


@dataclass
class CuriosityQuestion:
    question: str
    reason: str
    priority_score: float
    suggested_next_research_area: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "reason": self.reason,
            "priority_score": round(self.priority_score, 2),
            "suggested_next_research_area": self.suggested_next_research_area,
            "timestamp": self.timestamp.isoformat(),
        }


class CuriosityOrganism(Organism):
    """
    Meta-organism that inspects ecosystem state and asks research questions.
    Does not produce BUY/SELL — only curiosity and research direction.
    """

    def __init__(
        self,
        memory: MemoryLayer | None = None,
        regime_trust: RegimeAwareTrust | None = None,
    ) -> None:
        self._memory = memory
        self._regime_trust = regime_trust
        self._cycles: int = 0
        self._trust: float = 60.0
        self._last_questions: list[CuriosityQuestion] = []
        self._last_learning: str = ""
        self._session_packets: list[EvidencePacket] = []
        self._session_decision: CollectiveDecision | None = None

    @property
    def name(self) -> str:
        return "curiosity_organism"

    def set_session_context(
        self,
        packets: list[EvidencePacket],
        decision: CollectiveDecision | None,
    ) -> None:
        self._session_packets = list(packets)
        self._session_decision = decision

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        stats = self._memory.memory_statistics() if self._memory else {}
        return {
            "packet_count": len(self._session_packets),
            "decision_level": (
                self._session_decision.confidence_level.value
                if self._session_decision
                else "NONE"
            ),
            "memory_stats": stats,
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        questions = self.generate_questions(
            self._session_packets,
            self._session_decision,
        )
        self._last_questions = questions
        return {
            "question_count": len(questions),
            "top_priority": questions[0].priority_score if questions else 0.0,
            "questions": [q.to_dict() for q in questions],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        from research_core.ecosystem.evidence_packet import EvidencePacket

        top = self._last_questions[0] if self._last_questions else None
        summary = top.question if top else "No curiosity questions generated this cycle."
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Curiosity cycle {self._cycles}: {analysis['question_count']} questions",
            confidence=min(100.0, analysis.get("top_priority", 50.0)),
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={"questions": analysis.get("questions", [])},
            recommended_action="INVESTIGATE_RESEARCH_GAP",
            knowledge_reference=None,
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        if not self._last_questions:
            return "Curiosity organism found no urgent research gaps in this cycle."
        parts = [f"Generated {len(self._last_questions)} research question(s)."]
        for q in self._last_questions[:3]:
            parts.append(f"[priority={q.priority_score:.0f}] {q.question}")
        return " ".join(parts)

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Curiosity noted collective feedback."))
        return {"organism": self.name, "learning": self._last_learning}

    def receive_feedback(self, feedback: dict[str, Any]) -> None:
        if "trust_delta" in feedback:
            self.update_trust(float(feedback["trust_delta"]), feedback.get("reason", "feedback"))

    def update_trust(self, delta: float, reason: str) -> float:
        self._trust = max(0.0, min(100.0, self._trust + delta))
        return self._trust

    def health_status(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "cycles_completed": self._cycles,
            "trust": self._trust,
            "last_learning": self._last_learning,
            "last_question_count": len(self._last_questions),
        }

    def generate_questions(
        self,
        packets: list[EvidencePacket],
        decision: CollectiveDecision | None,
    ) -> list[CuriosityQuestion]:
        questions: list[CuriosityQuestion] = []

        if decision and decision.disagreement > 30 and len(packets) >= 2:
            high = max(packets, key=lambda p: p.confidence)
            low = min(packets, key=lambda p: p.confidence)
            questions.append(
                CuriosityQuestion(
                    question=f"Why does {high.organism_name} disagree with {low.organism_name} in this cycle?",
                    reason=f"Collective disagreement {decision.disagreement:.1f}% exceeds threshold.",
                    priority_score=min(100.0, decision.disagreement + 20),
                    suggested_next_research_area="cross_organism_conflict_analysis",
                )
            )

        if decision and decision.confidence_level.value in (
            "LOW_CONFIDENCE",
            "INSUFFICIENT_EVIDENCE",
        ):
            questions.append(
                CuriosityQuestion(
                    question="Which evidence category lacks enough history for confident collective view?",
                    reason=f"Collective level is {decision.confidence_level.value}.",
                    priority_score=75.0,
                    suggested_next_research_area="evidence_history_expansion",
                )
            )

        regime_packets: dict[str, list[EvidencePacket]] = {}
        for packet in packets:
            regime = str(packet.supporting_features.get("regime", "NEUTRAL"))
            regime_packets.setdefault(regime, []).append(packet)

        for regime, group in regime_packets.items():
            if "BEAR" in regime.upper() and len(group) >= 1:
                momentums = [p for p in group if "momentum" in p.organism_name]
                risks = [p for p in group if "risk" in p.organism_name]
                if momentums and risks:
                    m_conf = momentums[0].confidence
                    r_conf = risks[0].confidence
                    if abs(m_conf - r_conf) > 25:
                        questions.append(
                            CuriosityQuestion(
                                question=f"Why does Momentum disagree with Risk in {regime} regimes?",
                                reason=f"Confidence spread {abs(m_conf - r_conf):.1f} in synthetic {regime} context.",
                                priority_score=82.0,
                                suggested_next_research_area="regime_conditional_organism_calibration",
                            )
                        )

        if self._regime_trust and packets:
            for packet in packets:
                features = packet.supporting_features
                regime = self._regime_trust.infer_regime_from_features(features)
                trust = self._regime_trust.current_trust(packet.organism_name, regime)
                if trust < 45:
                    questions.append(
                        CuriosityQuestion(
                            question=f"Which organism has low trust in {regime.value} context?",
                            reason=f"{packet.organism_name} trust {trust:.1f} in {regime.value}.",
                            priority_score=70.0 + (45 - trust),
                            suggested_next_research_area=f"trust_recovery_{regime.value.lower()}",
                        )
                    )

        if self._memory:
            stats = self._memory.memory_statistics()
            if stats.get("evidence_count", 0) < 3:
                questions.append(
                    CuriosityQuestion(
                        question="Which evidence category lacks enough history?",
                        reason=f"Only {stats.get('evidence_count', 0)} evidence records in memory.",
                        priority_score=68.0,
                        suggested_next_research_area="memory_seeding_and_history",
                    )
                )

        seen: set[str] = set()
        unique: list[CuriosityQuestion] = []
        for q in sorted(questions, key=lambda x: -x.priority_score):
            if q.question not in seen:
                seen.add(q.question)
                unique.append(q)
        return unique[:8]

    def last_questions(self) -> list[CuriosityQuestion]:
        return list(self._last_questions)
