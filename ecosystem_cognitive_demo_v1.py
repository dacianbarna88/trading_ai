"""
Ecosystem Cognitive Demo V1 — TAE Sprint 3 Cognitive Layer

RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

Demonstrates memory, feedback, regime trust, curiosity, and knowledge graph.
No market data. No trading. Cognition only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem import (
    CommunicationBus,
    CollectiveIntelligence,
    HealthMonitor,
    KnowledgeCore,
    Organism,
    OrganismRegistry,
    TrustManager,
)
from research_core.ecosystem.cognitive_layer import CognitiveLayer, CognitiveCycleResult
from research_core.ecosystem.evidence_packet import EvidencePacket

SUMMARY_TXT = "ecosystem_cognitive_demo_summary.txt"


class ContextCognitiveOrganism(Organism):
    """Synthetic context organism with regime metadata for cognitive demo."""

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
            "regime": "BEAR",
            "volatility_regime": "HIGH",
            "macro_alignment": "below_long_term_average",
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        return {
            "context_score": 78.0,
            "regime": observations["regime"],
            "volatility_regime": observations["volatility_regime"],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Context cycle {self._cycles}: {analysis['regime']} / {analysis['volatility_regime']} vol",
            confidence=analysis["context_score"],
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "regime": analysis["regime"],
                "market_regime": analysis["regime"],
                "volatility_regime": analysis["volatility_regime"],
                "high_volatility": True,
            },
            recommended_action="ELEVATE_CONTEXT_ATTENTION",
            knowledge_reference="pattern_demo_bear_context",
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        return (
            f"Synthetic {analysis['regime']} context with {analysis['volatility_regime']} volatility — "
            "defensive regime alignment for research demo."
        )

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Context learned from collective."))
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


class MomentumCognitiveOrganism(Organism):
    """Synthetic momentum organism — disagrees with risk in BEAR for curiosity demo."""

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
            "regime": "BEAR",
            "volatility_regime": "HIGH",
            "impulse_strength": "synthetic_strong",
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        return {
            "momentum_score": 81.0,
            "regime": observations["regime"],
            "volatility_regime": observations["volatility_regime"],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Momentum cycle {self._cycles}: strong impulse in {analysis['regime']}",
            confidence=analysis["momentum_score"],
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "regime": analysis["regime"],
                "market_regime": analysis["regime"],
                "volatility_regime": analysis["volatility_regime"],
                "high_volatility": True,
            },
            recommended_action="ACKNOWLEDGE_MOMENTUM_IMPULSE",
            knowledge_reference="pattern_demo_momentum_burst",
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        return f"Strong synthetic momentum in {analysis['regime']} despite elevated volatility."

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Momentum learned from collective."))
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


class RiskCognitiveOrganism(Organism):
    """Synthetic risk organism — low confidence vs momentum for conflict demo."""

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
            "regime": "BEAR",
            "volatility_regime": "HIGH",
            "drawdown_risk": "synthetic_elevated",
            "cycle": self._cycles,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        return {
            "risk_score": 42.0,
            "regime": observations["regime"],
            "volatility_regime": observations["volatility_regime"],
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=f"Risk cycle {self._cycles}: elevated drawdown in {analysis['regime']}",
            confidence=analysis["risk_score"],
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "regime": analysis["regime"],
                "market_regime": analysis["regime"],
                "volatility_regime": analysis["volatility_regime"],
                "high_volatility": True,
            },
            recommended_action="FLAG_ELEVATED_RISK",
            knowledge_reference=None,
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        return (
            f"Elevated synthetic drawdown risk in {analysis['regime']} with "
            f"{analysis['volatility_regime']} volatility — caution warranted."
        )

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Risk learned from collective."))
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


def build_cognitive_stack() -> CognitiveLayer:
    trust_manager = TrustManager()
    bus = CommunicationBus()
    knowledge = KnowledgeCore()
    collective = CollectiveIntelligence()
    registry = OrganismRegistry(trust_manager)
    health = HealthMonitor(registry, trust_manager, knowledge, bus, collective)

    cognitive = CognitiveLayer(
        bus=bus,
        knowledge=knowledge,
        collective=collective,
        trust_manager=trust_manager,
        registry=registry,
        health_monitor=health,
    )

    knowledge.store_validated_pattern(
        pattern_id="pattern_demo_bear_context",
        description="Synthetic bear context pattern",
        confidence=75.0,
        trust=60.0,
        success_conditions=["BEAR regime"],
        failure_conditions=["BULL regime"],
    )
    knowledge.store_validated_pattern(
        pattern_id="pattern_demo_momentum_burst",
        description="Synthetic momentum burst pattern",
        confidence=80.0,
        trust=65.0,
        success_conditions=["strong impulse"],
        failure_conditions=["weak impulse"],
    )

    return cognitive


def run_demo() -> CognitiveCycleResult:
    print("===== TAE ECOSYSTEM COGNITIVE DEMO V1 — Sprint 3 =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Active cognition: memory, feedback, regime trust, curiosity, knowledge graph.")
    print("No market data. No trading.")
    print()

    cognitive = build_cognitive_stack()

    organisms: list[Organism] = [
        ContextCognitiveOrganism(),
        MomentumCognitiveOrganism(),
        RiskCognitiveOrganism(),
    ]
    for organism in organisms:
        cognitive.register_organism(organism)

    result = cognitive.process_cycle(organisms)

    print(f"Packets processed: {len(result.packets)}")
    print(f"Collective Confidence: {result.decision.collective_confidence:.2f}")
    print(f"Agreement: {result.decision.agreement:.2f}")
    print(f"Disagreement: {result.decision.disagreement:.2f}")
    print(f"Decision Level: {result.decision.confidence_level.value}")
    print(f"Feedback generated: {len(result.feedback)}")
    print(f"Cognitive Status: {result.cognitive_status}")
    print()
    print("Curiosity questions:")
    for q in result.curiosity_questions:
        print(f"  [{q.priority_score:.0f}] {q.question}")
    print()

    health = cognitive.health_report()
    summary_lines = build_summary(result, health)
    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"Saved: {summary_path}")

    return result


def build_summary(result: CognitiveCycleResult, health: Any) -> list[str]:
    lines = [
        "===== TAE ECOSYSTEM COGNITIVE DEMO V1 — Sprint 3 =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Cognitive Layer — remembrance, feedback, questioning. No execution.",
        "",
        "===== COGNITIVE CYCLE FLOW =====",
        "",
        "1. Organisms → EvidencePackets → CommunicationBus",
        "2. MemoryLayer.remember_evidence()",
        "3. CollectiveIntelligence.aggregate() → CollectiveDecision",
        "4. MemoryLayer.remember_decision()",
        "5. KnowledgeCore active feedback (pattern confidence / promote)",
        "6. FeedbackLoop.generate() → deliver() → organisms.receive_feedback()",
        "7. RegimeAwareTrust.update_trust() per regime context",
        "8. CuriosityOrganism.generate_questions()",
        "9. KnowledgeGraph nodes/edges updated",
        "",
        "===== RESULTS =====",
        "",
        f"Packets processed: {len(result.packets)}",
        f"Collective Confidence: {result.decision.collective_confidence:.2f}",
        f"Collective Trust: {result.decision.collective_trust:.2f}",
        f"Agreement: {result.decision.agreement:.2f}",
        f"Disagreement: {result.decision.disagreement:.2f}",
        f"Decision Level: {result.decision.confidence_level.value}",
        f"Feedback generated: {len(result.feedback)}",
        f"Cognitive Status: {result.cognitive_status}",
        "",
        "===== MEMORY STATISTICS =====",
    ]
    for key, value in result.memory_stats.items():
        lines.append(f"  {key}: {value}")
    lines.extend(["", "===== TRUST PROFILES (regime-aware) ====="])
    for organism, profile in result.trust_profiles.items():
        lines.append(f"  {organism}:")
        for regime, level in profile.items():
            lines.append(f"    {regime}: {level}")
    lines.extend(["", "===== REGIME TRUST STATISTICS ====="])
    for regime, stats in result.regime_statistics.items():
        lines.append(
            f"  {regime}: mean={stats.get('mean', 0)} "
            f"min={stats.get('min', 0)} max={stats.get('max', 0)} count={stats.get('count', 0)}"
        )
    lines.extend(["", "===== CURIOSITY QUESTIONS ====="])
    if not result.curiosity_questions:
        lines.append("  None generated.")
    for q in result.curiosity_questions:
        lines.append(f"  [{q.priority_score:.0f}] {q.question}")
        lines.append(f"    Reason: {q.reason}")
        lines.append(f"    Research area: {q.suggested_next_research_area}")
    lines.extend(["", "===== KNOWLEDGE GRAPH STATISTICS ====="])
    for key, value in result.graph_stats.items():
        lines.append(f"  {key}: {value}")
    lines.extend(["", "===== FEEDBACK SAMPLES ====="])
    for fb in result.feedback[:5]:
        lines.append(
            f"  {fb.organism_name}: trust_delta={fb.trust_delta:+.1f} "
            f"confidence_delta={fb.confidence_delta:+.1f} — {fb.lesson[:80]}..."
        )
    if health is not None:
        lines.extend(
            [
                "",
                "===== HEALTH SUMMARY =====",
                f"  System health: {health.system_health}",
                f"  Active organisms: {health.active_organisms}",
                f"  Agreement ratio: {health.agreement_ratio:.2f}",
            ]
        )
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
