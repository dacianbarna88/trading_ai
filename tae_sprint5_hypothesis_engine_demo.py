"""
TAE Sprint 5.0 — Hypothesis Engine Foundation

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Generates explicit research hypotheses from Research Council outputs.
Hypotheses are NOT trading orders — they are objects for future testing (Sprint 5.1).
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
from research_core.ecosystem.organism import Organism
from research_core.ecosystem.organism_memory import OrganismMemoryStore
from research_core.ecosystem.organisms import (
    CONTEXT_ORGANISM_NAME,
    EVIDENCE_ORGANISM_NAME,
    MOMENTUM_ORGANISM_NAME,
    ContextOrganism,
    EvidenceOrganism,
    MomentumOrganism,
)
from research_core.ecosystem.trust_calibration import TrustCalibrator
from research_core.hypothesis import Hypothesis, HypothesisGenerator, HypothesisRegistry
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import build_cognitive_stack
from tae_sprint4_multi_organism_demo import _register_knowledge_patterns
from tae_sprint4_trust_calibration_demo import _apply_memory_trust

SUMMARY_TXT = "tae_sprint5_hypothesis_engine_summary.txt"
ORGANISM_NAMES = [EVIDENCE_ORGANISM_NAME, CONTEXT_ORGANISM_NAME, MOMENTUM_ORGANISM_NAME]


def _next_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint5_hypothesis_cycle_")
    )
    return f"sprint5_hypothesis_cycle_{existing + 1}"


def _record_hypothesis_life_events(life: LifeManager, hypotheses: list[Hypothesis]) -> None:
    if not life.timeline.has_title("Hypothesis Engine Foundation"):
        life.record_event(
            "milestone",
            "Hypothesis Engine Foundation",
            "Sprint 5.0 — TAE generates explicit research hypotheses from council outputs.",
            milestone_importance=9,
        )
        life.record_event(
            "research_experiment",
            "Sprint 5.0 Hypothesis Engine",
            "tae_sprint5_hypothesis_engine_demo — hypotheses are research objects, not trade orders.",
        )

    for hypothesis in hypotheses:
        life.record_event(
            "knowledge_item",
            f"Hypothesis: {hypothesis.title}",
            (
                f"id={hypothesis.hypothesis_id} status={hypothesis.status.value} "
                f"conf={hypothesis.confidence:.1f} horizon={hypothesis.horizon}"
            ),
            add_timeline=False,
        )


def format_hypothesis_report(
    result: CognitiveCycleResult,
    hypotheses: list[Hypothesis],
    registry: HypothesisRegistry,
    cycle_label: str,
    registry_path: Path,
    prior_count: int,
) -> str:
    decision = result.decision
    lines = [
        "===== TAE SPRINT 5.0 — HYPOTHESIS ENGINE =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Hypotheses are research objects — NOT BUY/SELL signals or trade orders.",
        "",
        f"Cycle Label: {cycle_label}",
        f"Organisms Used: {', '.join(ORGANISM_NAMES)}",
        "",
        "===== COUNCIL METRICS =====",
        f"  Collective confidence: {decision.collective_confidence:.2f}",
        f"  Trust-weighted confidence: {decision.trust_weighted_confidence:.2f}",
        f"  Unweighted confidence: {decision.unweighted_confidence:.2f}",
        f"  Decision level: {decision.confidence_level.value}",
        f"  Agreement: {decision.agreement:.2f}%",
        f"  Disagreement: {decision.disagreement:.2f}%",
        "",
        f"Hypotheses generated this run: {len(hypotheses)}",
        f"Registry total (after persist): {registry.count()} (was {prior_count} at startup)",
        f"Registry loaded at startup: {registry.loaded_at_startup}",
        f"Registry persisted: {registry_path}",
        "",
        "===== GENERATED HYPOTHESES =====",
    ]

    for hypothesis in hypotheses:
        lines.extend(
            [
                f"  ID: {hypothesis.hypothesis_id}",
                f"  Title: {hypothesis.title}",
                f"  Status: {hypothesis.status.value}",
                f"  Confidence: {hypothesis.confidence:.2f}",
                f"  Horizon: {hypothesis.horizon}",
                f"  Source cycle: {hypothesis.source_cycle}",
                f"  Source organisms: {', '.join(hypothesis.source_organisms)}",
                f"  Conditions:",
            ]
        )
        for key, value in hypothesis.conditions.items():
            lines.append(f"    {key}: {value}")
        lines.extend(
            [
                f"  Prediction: {hypothesis.prediction}",
                f"  Rationale: {hypothesis.rationale[:200]}{'...' if len(hypothesis.rationale) > 200 else ''}",
                f"  Safety: {hypothesis.safety_mode}",
                "",
            ]
        )

    lines.append(registry.format_summary())
    return "\n".join(lines)


def run_hypothesis_engine_demo() -> tuple[CognitiveCycleResult, list[Hypothesis]]:
    print("===== TAE SPRINT 5.0 — HYPOTHESIS ENGINE FOUNDATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Hypotheses are research objects — NOT trade orders or execution signals.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = HypothesisRegistry()
    prior_count = registry.count()
    if registry.loaded_at_startup:
        print(f"Loaded hypothesis registry: {registry.path} ({prior_count} hypotheses)")
        for hypothesis in registry.list_all()[-3:]:
            print(f"  existing: {hypothesis.hypothesis_id} — {hypothesis.title}")
    else:
        print(f"No prior hypothesis registry — will create {registry.path}")
    print()

    memory_store = OrganismMemoryStore()
    if memory_store.loaded_at_startup:
        print(f"Organism memory loaded: {memory_store.path}")
    else:
        print(f"Organism memory fresh: {memory_store.path}")

    life = LifeManager(start_generation=4)
    print(f"Life state: {'loaded' if life.loaded_from_storage else 'fresh'} → {life.state_path}")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Hypothesis Engine — explicit research hypotheses from council")

    cognitive = build_cognitive_stack()
    _register_knowledge_patterns(cognitive)

    organisms: list[Organism] = [
        EvidenceOrganism(),
        ContextOrganism(),
        MomentumOrganism(),
    ]
    _apply_memory_trust(organisms, memory_store)

    for organism in organisms:
        cognitive.register_organism(organism, initial_trust=organism.health_status().get("trust"))

    trust_weights = memory_store.build_trust_weights()
    bridge = EcosystemLifeBridge(life)
    cycle_label = _next_cycle_label(life)
    calibrator = TrustCalibrator()
    generator = HypothesisGenerator()

    print(f"Running research council cycle ({cycle_label})...")
    result = cognitive.process_cycle(organisms, trust_weights=trust_weights)

    raw_hypotheses = generator.generate_from_council(
        result,
        cycle_label=cycle_label,
        registry_sequence_hint=registry.count(),
    )
    registered: list[Hypothesis] = []
    for hypothesis in raw_hypotheses:
        registered.append(registry.add_generated(hypothesis))

    registry_path = registry.persist()

    memory_store.record_cycle(result.packets, result.decision)
    calibrator.calibrate_store(memory_store)
    memory_path = memory_store.persist()

    bridge_summary = bridge.record_cognitive_cycle(
        result,
        cycle_label=cycle_label,
        write_journal=True,
    )
    life.persist()

    _record_hypothesis_life_events(life, registered)
    life.persist()

    report = format_hypothesis_report(
        result,
        registered,
        registry,
        cycle_label,
        registry_path,
        prior_count,
    )
    print()
    print(report)

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(report + "\n", encoding="utf-8")

    life.status_generator.generate(
        age=life.age,
        generation=life.generation,
        journal=life.journal,
        milestones=life.milestones,
        achievements=life.achievements,
        metrics=life.metrics,
        current_mission=life.current_mission,
    )

    print(f"Saved: {summary_path}")
    print(f"Saved: TAE_STATUS.md")
    print(f"Bridge events recorded: {bridge_summary.events_recorded}")
    print(f"Persisted hypothesis registry: {registry_path}")
    print(f"Persisted organism memory: {memory_path}")
    print(f"Persisted life state: {life.state_path}")

    return result, registered


def main() -> None:
    run_hypothesis_engine_demo()


if __name__ == "__main__":
    main()
