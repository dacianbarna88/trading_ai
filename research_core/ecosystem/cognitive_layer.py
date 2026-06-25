"""Cognitive layer orchestrator — active remembrance, feedback, and questioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_core.ecosystem.collective_intelligence import CollectiveDecision, CollectiveIntelligence
from research_core.ecosystem.communication_bus import CommunicationBus
from research_core.ecosystem.curiosity_organism import CuriosityOrganism, CuriosityQuestion
from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.feedback_loop import FeedbackLoop, OrganismFeedback
from research_core.ecosystem.health_monitor import HealthMonitor, HealthReport
from research_core.ecosystem.knowledge_core import KnowledgeCore, PatternStatus
from research_core.ecosystem.knowledge_graph import EdgeType, KnowledgeGraph, NodeType
from research_core.ecosystem.memory_layer import MemoryLayer
from research_core.ecosystem.organism import Organism
from research_core.ecosystem.organism_registry import OrganismRegistry
from research_core.ecosystem.regime_trust import RegimeAwareTrust, TrustRegime
from research_core.ecosystem.trust_manager import TrustManager


@dataclass
class CognitiveCycleResult:
    """Outcome of one full cognitive processing cycle."""

    packets: list[EvidencePacket]
    decision: CollectiveDecision
    feedback: list[OrganismFeedback]
    curiosity_questions: list[CuriosityQuestion]
    memory_stats: dict[str, Any]
    trust_profiles: dict[str, dict[str, float]]
    regime_statistics: dict[str, Any]
    graph_stats: dict[str, Any]
    cognitive_status: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_count": len(self.packets),
            "collective_confidence": round(self.decision.collective_confidence, 2),
            "agreement": round(self.decision.agreement, 2),
            "disagreement": round(self.decision.disagreement, 2),
            "decision_level": self.decision.confidence_level.value,
            "feedback_count": len(self.feedback),
            "curiosity_count": len(self.curiosity_questions),
            "memory_stats": self.memory_stats,
            "graph_stats": self.graph_stats,
            "regime_statistics": self.regime_statistics,
            "cognitive_status": self.cognitive_status,
            "timestamp": self.timestamp.isoformat(),
        }


class CognitiveLayer:
    """
    Sprint 3 orchestrator connecting communication, memory, feedback, trust,
    curiosity, and knowledge graph into active cognition cycles.
    """

    def __init__(
        self,
        bus: CommunicationBus | None = None,
        knowledge: KnowledgeCore | None = None,
        collective: CollectiveIntelligence | None = None,
        memory: MemoryLayer | None = None,
        feedback_loop: FeedbackLoop | None = None,
        regime_trust: RegimeAwareTrust | None = None,
        curiosity: CuriosityOrganism | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
        trust_manager: TrustManager | None = None,
        registry: OrganismRegistry | None = None,
        health_monitor: HealthMonitor | None = None,
    ) -> None:
        self.bus = bus or CommunicationBus()
        self.knowledge = knowledge or KnowledgeCore()
        self.collective = collective or CollectiveIntelligence()
        self.memory = memory or MemoryLayer()
        self.feedback_loop = feedback_loop or FeedbackLoop()
        self.regime_trust = regime_trust or RegimeAwareTrust()
        self.knowledge_graph = knowledge_graph or KnowledgeGraph()
        self.trust_manager = trust_manager or TrustManager()
        self.registry = registry or OrganismRegistry(self.trust_manager)
        self.curiosity = curiosity or CuriosityOrganism(self.memory, self.regime_trust)
        self.health_monitor = health_monitor

        self.bus.subscribe("evidence", self.knowledge.on_packet)
        self.bus.subscribe("evidence", self.collective.on_packet)
        self._cycle_count: int = 0

    def register_organism(self, organism: Organism, initial_trust: float | None = None) -> str:
        name = self.registry.register(organism, initial_trust)
        self.regime_trust.register(name, initial_trust)
        self.knowledge_graph.add_node(
            f"organism:{name}",
            NodeType.ORGANISM,
            name,
            {"registered_at": datetime.now(timezone.utc).isoformat()},
        )
        return name

    def process_cycle(
        self,
        organisms: list[Organism] | None = None,
        trust_weights: dict[str, float] | None = None,
    ) -> CognitiveCycleResult:
        self._cycle_count += 1
        self.collective.clear_session()

        target_organisms = organisms or self.registry.list_organisms()
        packets: list[EvidencePacket] = []

        for organism in target_organisms:
            if organism.name == self.curiosity.name:
                continue
            packet = organism.run_cycle()
            packets.append(packet)
            self.bus.publish(packet)
            self.memory.remember_evidence(packet)
            self._update_graph_for_packet(packet)

        decision = self.collective.aggregate(trust_weights=trust_weights)
        self.memory.remember_decision(decision)
        self._apply_knowledge_core_feedback(decision, packets)
        self._update_graph_for_decision(decision)

        feedback_batch = self.feedback_loop.generate(decision, packets)
        for fb in feedback_batch:
            self.memory.remember_feedback(fb)
        delivered = self.feedback_loop.deliver(feedback_batch, target_organisms)

        for fb in feedback_batch:
            packet = next((p for p in packets if p.organism_name == fb.organism_name), None)
            regime = TrustRegime.GLOBAL
            if packet is not None:
                regime = self.regime_trust.infer_regime_from_features(packet.supporting_features)
            self.regime_trust.update_trust(
                fb.organism_name,
                regime,
                fb.trust_delta,
                fb.lesson,
            )
            if fb.trust_delta >= 0:
                self.trust_manager.increase(fb.organism_name, fb.trust_delta, fb.lesson)
            else:
                self.trust_manager.decrease(fb.organism_name, abs(fb.trust_delta), fb.lesson)
            self.memory.remember_learning_event(
                fb.organism_name,
                "feedback_applied",
                fb.lesson,
                {"trust_delta": fb.trust_delta, "regime": regime.value},
            )

        for organism in target_organisms:
            self.memory.remember_performance_snapshot(
                organism.name,
                organism.health_status(),
            )

        self.curiosity.set_session_context(packets, decision)
        curiosity_packet = self.curiosity.run_cycle()
        self.bus.publish(curiosity_packet)
        self.memory.remember_evidence(curiosity_packet)
        curiosity_questions = self.curiosity.last_questions()
        for question in curiosity_questions:
            self.memory.remember_learning_event(
                self.curiosity.name,
                "curiosity_question",
                question.question,
                question.to_dict(),
            )
            self._update_graph_for_question(question)

        cognitive_status = self._assess_cognitive_status(decision, delivered, curiosity_questions)

        return CognitiveCycleResult(
            packets=packets,
            decision=decision,
            feedback=feedback_batch,
            curiosity_questions=curiosity_questions,
            memory_stats=self.memory.memory_statistics(),
            trust_profiles=self.regime_trust.all_profiles(),
            regime_statistics=self.regime_trust.regime_statistics(),
            graph_stats=self.knowledge_graph.graph_statistics(),
            cognitive_status=cognitive_status,
        )

    def health_report(self) -> HealthReport | None:
        if self.health_monitor is None:
            return None
        return self.health_monitor.report()

    def _apply_knowledge_core_feedback(
        self,
        decision: CollectiveDecision,
        packets: list[EvidencePacket],
    ) -> None:
        level = decision.confidence_level.value
        for packet in packets:
            ref = packet.knowledge_reference
            if not ref:
                continue
            pattern = self.knowledge.retrieve_pattern(ref)
            if pattern is None:
                continue
            if level == "HIGH_CONFIDENCE" and packet.confidence >= 70:
                self.knowledge.update_pattern(
                    ref,
                    {
                        "confidence": min(100.0, pattern.confidence + 1.0),
                        "metadata": {
                            **pattern.metadata,
                            "last_collective_support": decision.collective_confidence,
                        },
                    },
                )
            elif level == "INSUFFICIENT_EVIDENCE" or decision.disagreement > 50:
                self.knowledge.update_pattern(
                    ref,
                    {
                        "metadata": {
                            **pattern.metadata,
                            "last_collective_warning": decision.explanation[:200],
                        },
                    },
                )
        if level == "HIGH_CONFIDENCE" and decision.organism_participation >= 3:
            for pattern in self.knowledge.list_candidates():
                if pattern.status == PatternStatus.VALIDATED and pattern.confidence >= 75:
                    self.knowledge.promote_pattern(
                        pattern.pattern_id,
                        f"Collective HIGH_CONFIDENCE with {decision.organism_participation} organisms",
                    )

    def _update_graph_for_packet(self, packet: EvidencePacket) -> None:
        org_id = f"organism:{packet.organism_name}"
        if self.knowledge_graph.get_node(org_id) is None:
            self.knowledge_graph.add_node(org_id, NodeType.ORGANISM, packet.organism_name)

        evidence_id = f"evidence:{packet.organism_name}:{packet.timestamp.isoformat()}"
        self.knowledge_graph.add_node(
            evidence_id,
            NodeType.EVIDENCE_TYPE,
            packet.observation_summary[:80],
            {"confidence": packet.confidence},
        )
        self.knowledge_graph.add_edge(
            org_id,
            evidence_id,
            EdgeType.OBSERVED_IN,
            weight=packet.confidence / 100.0,
            explanation=packet.explanation[:120],
        )

        regime = str(packet.supporting_features.get("regime", "NEUTRAL"))
        regime_id = f"regime:{regime}"
        if self.knowledge_graph.get_node(regime_id) is None:
            self.knowledge_graph.add_node(regime_id, NodeType.MARKET_REGIME, regime)
        self.knowledge_graph.add_edge(
            evidence_id,
            regime_id,
            EdgeType.OBSERVED_IN,
            weight=0.8,
            explanation=f"Evidence observed in {regime} context",
        )

        if packet.knowledge_reference:
            pattern_id = f"pattern:{packet.knowledge_reference}"
            if self.knowledge_graph.get_node(pattern_id) is None:
                self.knowledge_graph.add_node(
                    pattern_id,
                    NodeType.PATTERN,
                    packet.knowledge_reference,
                )
            self.knowledge_graph.add_edge(
                pattern_id,
                evidence_id,
                EdgeType.VALIDATED_BY,
                weight=packet.trust / 100.0,
                explanation="Pattern linked to evidence packet",
            )

        vol = packet.supporting_features.get("volatility_regime", "")
        if "HIGH" in str(vol).upper():
            risk_id = "risk:high_volatility"
            if self.knowledge_graph.get_node(risk_id) is None:
                self.knowledge_graph.add_node(
                    risk_id,
                    NodeType.RISK_CONDITION,
                    "high_volatility",
                )
            if "risk" in packet.organism_name:
                self.knowledge_graph.add_edge(
                    org_id,
                    risk_id,
                    EdgeType.OBSERVED_IN,
                    weight=0.9,
                    explanation="Risk organism active in high volatility",
                )

    def _update_graph_for_decision(self, decision: CollectiveDecision) -> None:
        decision_id = f"decision:{decision.timestamp.isoformat()}"
        self.knowledge_graph.add_node(
            decision_id,
            NodeType.DECISION_LEVEL,
            decision.confidence_level.value,
            decision.to_dict(),
        )
        for org_name in decision.contributing_organisms:
            org_id = f"organism:{org_name}"
            if self.knowledge_graph.get_node(org_id):
                self.knowledge_graph.add_edge(
                    org_id,
                    decision_id,
                    EdgeType.SUPPORTS,
                    weight=decision.agreement / 100.0,
                    explanation="Organism contributed to collective decision",
                )

    def _update_graph_for_question(self, question: CuriosityQuestion) -> None:
        q_id = f"question:{hash(question.question) & 0xFFFFFFFF}"
        self.knowledge_graph.add_node(
            q_id,
            NodeType.EVIDENCE_TYPE,
            question.suggested_next_research_area,
            question.to_dict(),
        )
        curiosity_id = f"organism:{self.curiosity.name}"
        self.knowledge_graph.add_edge(
            curiosity_id,
            q_id,
            EdgeType.DEPENDS_ON,
            weight=question.priority_score / 100.0,
            explanation=question.reason,
        )

    def _assess_cognitive_status(
        self,
        decision: CollectiveDecision,
        feedback_delivered: int,
        questions: list[CuriosityQuestion],
    ) -> str:
        if feedback_delivered == 0:
            return "COGNITIVE_IDLE"
        if decision.confidence_level.value == "HIGH_CONFIDENCE" and decision.agreement > 70:
            return "COGNITIVE_ALIGNED"
        if questions and questions[0].priority_score >= 80:
            return "COGNITIVE_QUESTIONING"
        if decision.disagreement > 40:
            return "COGNITIVE_CONFLICTED"
        return "COGNITIVE_ACTIVE"
