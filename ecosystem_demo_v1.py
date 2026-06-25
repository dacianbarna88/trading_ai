"""
Ecosystem Demo V1 — Birth of Collective Intelligence

RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

Demonstrates TAE Sprint 2 architecture with three fake organisms.
No market data. No trading. Communication only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem import (
    CollectiveIntelligence,
    CommunicationBus,
    EcosystemStateTracker,
    EvidencePacket,
    HealthMonitor,
    KnowledgeCore,
    Organism,
    OrganismRegistry,
    TrustManager,
)

SUMMARY_TXT = "ecosystem_demo_summary.txt"


class ContextDemoOrganism(Organism):
    """Fake context observer — no market logic."""

    def __init__(self) -> None:
        self._trust: float = 55.0
        self._cycles: int = 0
        self._last_learning: str = ""

    @property
    def name(self) -> str:
        return "context_demo_organism"

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        return {
            "regime_label": "synthetic_bear_context",
            "macro_alignment": "below_long_term_average",
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        return {
            "context_score": 78.0,
            "regime": observations["regime_label"],
            "alignment": observations["macro_alignment"],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Context cycle {self._cycles}: {analysis['regime']}",
            confidence=analysis["context_score"],
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={"regime": analysis["regime"], "alignment": analysis["alignment"]},
            recommended_action="ELEVATE_CONTEXT_ATTENTION",
            knowledge_reference="pattern_demo_bear_context",
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        return (
            f"Synthetic context favors defensive regime ({analysis['regime']}) "
            f"with alignment {analysis['alignment']}."
        )

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("summary", "Context organism noted peer agreement.")
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
        }


class MomentumDemoOrganism(Organism):
    """Fake momentum observer — no market logic."""

    def __init__(self) -> None:
        self._trust: float = 62.0
        self._cycles: int = 0
        self._last_learning: str = ""

    @property
    def name(self) -> str:
        return "momentum_demo_organism"

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        return {
            "impulse_strength": "synthetic_strong",
            "continuation_probability": 0.72,
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        return {
            "momentum_score": 81.0,
            "impulse": observations["impulse_strength"],
            "continuation_prob": observations["continuation_probability"],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Momentum cycle {self._cycles}: {analysis['impulse']}",
            confidence=analysis["momentum_score"],
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "impulse": analysis["impulse"],
                "continuation_probability": analysis["continuation_prob"],
            },
            recommended_action="ACKNOWLEDGE_MOMENTUM_IMPULSE",
            knowledge_reference="pattern_demo_momentum_burst",
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        return (
            f"Synthetic momentum impulse is {analysis['impulse']} "
            f"with continuation probability {analysis['continuation_prob']:.2f}."
        )

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("summary", "Momentum organism recorded collective signal.")
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
        }


class RiskDemoOrganism(Organism):
    """Fake risk observer — no market logic."""

    def __init__(self) -> None:
        self._trust: float = 48.0
        self._cycles: int = 0
        self._last_learning: str = ""

    @property
    def name(self) -> str:
        return "risk_demo_organism"

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        return {
            "drawdown_risk": "synthetic_elevated",
            "tail_risk_flag": True,
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        return {
            "risk_score": 42.0,
            "drawdown": observations["drawdown_risk"],
            "tail_risk": observations["tail_risk_flag"],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Risk cycle {self._cycles}: {analysis['drawdown']}",
            confidence=analysis["risk_score"],
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "drawdown_risk": analysis["drawdown"],
                "tail_risk": analysis["tail_risk"],
            },
            recommended_action="FLAG_ELEVATED_RISK",
            knowledge_reference=None,
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        return (
            f"Synthetic risk assessment: drawdown {analysis['drawdown']}, "
            f"tail risk flagged={analysis['tail_risk']}."
        )

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("summary", "Risk organism noted dissent in collective view.")
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
        }


def wire_ecosystem() -> tuple[
    CommunicationBus,
    KnowledgeCore,
    CollectiveIntelligence,
    OrganismRegistry,
    TrustManager,
    EcosystemStateTracker,
    HealthMonitor,
]:
    trust_manager = TrustManager()
    bus = CommunicationBus()
    knowledge = KnowledgeCore()
    collective = CollectiveIntelligence()
    registry = OrganismRegistry(trust_manager)
    state_tracker = EcosystemStateTracker()

    bus.subscribe("evidence", knowledge.on_packet)
    bus.subscribe("evidence", collective.on_packet)

    health = HealthMonitor(registry, trust_manager, knowledge, bus, collective)

    return bus, knowledge, collective, registry, trust_manager, state_tracker, health


def run_demo() -> dict[str, Any]:
    print("===== TAE ECOSYSTEM DEMO V1 — Birth of Collective Intelligence =====")
    print(RESEARCH_SAFETY_BANNER)
    print("No market data. No trading. Communication architecture only.")
    print()

    bus, knowledge, collective, registry, trust_manager, state_tracker, health_monitor = wire_ecosystem()

    knowledge.store_validated_pattern(
        pattern_id="pattern_demo_bear_context",
        description="Synthetic bear context pattern for demo",
        confidence=75.0,
        trust=60.0,
        success_conditions=["synthetic_bear_context"],
        failure_conditions=["synthetic_bull_context"],
    )
    knowledge.store_validated_pattern(
        pattern_id="pattern_demo_momentum_burst",
        description="Synthetic momentum burst pattern for demo",
        confidence=80.0,
        trust=65.0,
        success_conditions=["synthetic_strong_impulse"],
        failure_conditions=["synthetic_weak_impulse"],
    )

    organisms: list[Organism] = [
        ContextDemoOrganism(),
        MomentumDemoOrganism(),
        RiskDemoOrganism(),
    ]
    for organism in organisms:
        registry.register(organism)

    state_tracker.advance_generation()

    packets: list[EvidencePacket] = []
    for organism in registry.list_organisms():
        packet = organism.run_cycle()
        packets.append(packet)
        bus.publish(packet)

    decision = collective.aggregate()

    feedback = {
        "summary": "Collective cycle completed with mixed risk and momentum signals.",
        "collective_confidence": decision.collective_confidence,
    }
    for organism in registry.list_organisms():
        organism.receive_feedback(feedback)
        organism.learn(feedback)

    if decision.agreement > 60:
        trust_manager.increase("context_demo_organism", 2.0, "high collective agreement")
        trust_manager.increase("momentum_demo_organism", 2.0, "high collective agreement")
    if decision.disagreement > 30:
        trust_manager.decrease("risk_demo_organism", 1.0, "elevated dissent expected for risk role")

    state_tracker.record_learning_events(len(knowledge.learning_events()))

    health_report = health_monitor.report()
    snapshot = state_tracker.build_snapshot(
        active_organisms=registry.list(),
        knowledge_size=knowledge.knowledge_statistics()["total_patterns"],
        health_score=100.0 if health_report.system_health == "HEALTHY" else 70.0,
        packet_count=bus.packet_count(),
        collective_confidence=decision.collective_confidence,
        confidence_level=decision.confidence_level.value,
    )

    print(f"Collective Confidence: {decision.collective_confidence:.2f}")
    print(f"Collective Trust: {decision.collective_trust:.2f}")
    print(f"Agreement: {decision.agreement:.2f}")
    print(f"Disagreement: {decision.disagreement:.2f}")
    print(f"Confidence Level: {decision.confidence_level.value}")
    print(f"Organism Participation: {decision.organism_participation}")
    print()
    print("Explanation:")
    print(decision.explanation)
    print()
    print("Trust distribution:", trust_manager.distribution())

    summary_lines = build_summary(
        decision=decision,
        health_report=health_report,
        snapshot=snapshot,
        trust_manager=trust_manager,
        packets=packets,
    )
    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"Saved: {summary_path}")

    return {
        "collective_confidence": decision.collective_confidence,
        "agreement": decision.agreement,
        "trust": decision.collective_trust,
        "confidence_level": decision.confidence_level.value,
    }


def build_summary(
    decision: Any,
    health_report: Any,
    snapshot: Any,
    trust_manager: TrustManager,
    packets: list[EvidencePacket],
) -> list[str]:
    lines = [
        "===== TAE ECOSYSTEM DEMO V1 — Birth of Collective Intelligence =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Sprint 2 — nervous system demonstration. No market data. No execution.",
        "",
        "===== ARCHITECTURE FLOW =====",
        "",
        "1. Organisms (observe → analyze → produce_evidence)",
        "   ├── context_demo_organism",
        "   ├── momentum_demo_organism",
        "   └── risk_demo_organism",
        "",
        "2. Each organism emits EvidencePacket (never direct calls)",
        "",
        "3. CommunicationBus.publish(packet)",
        "   ├── subscriber: KnowledgeCore.on_packet",
        "   └── subscriber: CollectiveIntelligence.on_packet",
        "",
        "4. CollectiveIntelligence.aggregate()",
        "   → CollectiveDecision (HIGH/MEDIUM/LOW/INSUFFICIENT — not BUY/SELL)",
        "",
        "5. Feedback loop",
        "   ├── organisms.receive_feedback()",
        "   ├── organisms.learn()",
        "   └── TrustManager increase/decrease",
        "",
        "6. HealthMonitor.report() + EcosystemStateTracker snapshot",
        "",
        "===== DEMO RESULTS =====",
        "",
        f"Collective Confidence: {decision.collective_confidence:.2f}",
        f"Collective Trust: {decision.collective_trust:.2f}",
        f"Agreement: {decision.agreement:.2f}",
        f"Disagreement: {decision.disagreement:.2f}",
        f"Confidence Level: {decision.confidence_level.value}",
        f"Organism Participation: {decision.organism_participation}",
        "",
        "Explanation:",
        decision.explanation,
        "",
        "===== PACKETS PUBLISHED =====",
    ]
    for packet in packets:
        lines.append(
            f"  [{packet.organism_name}] confidence={packet.confidence:.1f} "
            f"trust={packet.trust:.1f} action={packet.recommended_action}"
        )
    lines.extend(
        [
            "",
            "===== TRUST DISTRIBUTION =====",
        ]
    )
    for name, level in trust_manager.distribution().items():
        lines.append(f"  {name}: {level:.1f}")
    lines.extend(
        [
            "",
            "===== HEALTH REPORT =====",
            f"  System health: {health_report.system_health}",
            f"  Active organisms: {health_report.active_organisms}",
            f"  Knowledge count: {health_report.knowledge_count}",
            f"  Packet count: {health_report.packet_count}",
            f"  Agreement ratio: {health_report.agreement_ratio:.2f}",
            f"  Learning events: {health_report.learning_events}",
            "",
            "===== ECOSYSTEM STATE =====",
        ]
    )
    for key, value in snapshot.to_dict().items():
        lines.append(f"  {key}: {value}")
    lines.extend(
        [
            "",
            "We never stop learning.",
            "We never stop moving.",
            "We never stop questioning.",
            "We never stop teaching.",
            "We never stop evolving.",
            "",
        ]
    )
    return lines


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
