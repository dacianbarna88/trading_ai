"""
TAE Sprint 4.4 — Trust-Weighted Collective Decision

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Uses calibrated organism memory trust to weight collective confidence.
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
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import BridgeRecordSummary, EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import build_cognitive_stack
from tae_sprint4_multi_organism_demo import _register_knowledge_patterns
from tae_sprint4_trust_calibration_demo import _apply_memory_trust

SUMMARY_TXT = "tae_sprint4_trust_weighted_decision_summary.txt"


def _next_weighted_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint4_trust_weighted_cycle_")
    )
    return f"sprint4_trust_weighted_cycle_{existing + 1}"


def _record_weighted_life_events(life: LifeManager, result: CognitiveCycleResult) -> None:
    if not life.timeline.has_title("Trust-Weighted Collective Decision"):
        life.record_event(
            "milestone",
            "Trust-Weighted Collective Decision",
            "Sprint 4.4 — collective confidence weighted by calibrated organism trust.",
            milestone_importance=8,
        )
        life.record_event(
            "research_experiment",
            "Sprint 4.4 Trust-Weighted Decision",
            "tae_sprint4_trust_weighted_decision_demo — memory trust drives collective weighting.",
        )

    decision = result.decision
    life.record_event(
        "collective_decision",
        f"Trust-Weighted: {decision.confidence_level.value}",
        (
            f"unweighted={decision.unweighted_confidence:.1f} "
            f"weighted={decision.trust_weighted_confidence:.1f} "
            f"agreement={decision.agreement:.1f}"
        ),
        add_timeline=False,
    )


def format_contribution_report(result: CognitiveCycleResult, trust_weights: dict[str, float]) -> str:
    lines = [
        "===== ORGANISM CONTRIBUTIONS =====",
        "",
        "Memory trust weights applied:",
    ]
    for name in sorted(trust_weights):
        lines.append(f"  • {name}: {trust_weights[name]:.2f}")
    lines.extend(["", "Per-organism breakdown:"])

    for contrib in result.decision.organism_contributions:
        lines.extend(
            [
                f"  {contrib.organism_name}:",
                f"    confidence: {contrib.confidence:.2f}",
                f"    trust (memory): {contrib.trust_used:.2f}",
                f"    packet trust: {contrib.packet_trust:.2f}",
                f"    weight: {contrib.weight:.4f}",
                f"    weighted contribution: {contrib.weighted_contribution:.2f}",
                "",
            ]
        )

    decision = result.decision
    lines.extend(
        [
            "===== COLLECTIVE DECISION =====",
            f"  unweighted confidence: {decision.unweighted_confidence:.2f}",
            f"  trust-weighted confidence: {decision.trust_weighted_confidence:.2f}",
            f"  collective confidence (reported): {decision.collective_confidence:.2f}",
            f"  decision level: {decision.confidence_level.value}",
            f"  agreement: {decision.agreement:.2f}",
            f"  disagreement: {decision.disagreement:.2f}",
            f"  trust weighting applied: {decision.trust_weighting_applied}",
            "",
        ]
    )
    return "\n".join(lines)


def build_report(
    result: CognitiveCycleResult,
    bridge_summary: BridgeRecordSummary,
    life: LifeManager,
    memory_store: OrganismMemoryStore,
    trust_weights: dict[str, float],
    cycle_label: str,
    memory_path: Path,
) -> str:
    contribution_report = format_contribution_report(result, trust_weights)
    lines = [
        "===== TAE SPRINT 4.4 — TRUST-WEIGHTED COLLECTIVE DECISION =====",
        "",
        f"Cycle Label: {cycle_label}",
        f"Packets Produced: {len(result.packets)}",
        f"Cognitive Status: {result.cognitive_status}",
        f"Life Events Recorded (bridge): {bridge_summary.events_recorded}",
        "",
        contribution_report,
        memory_store.format_summary(),
        f"Organism Memory Loaded At Startup: {memory_store.loaded_at_startup}",
        f"Organism Memory Persisted: {memory_path}",
        f"Life State Persisted: {life.state_path}",
        "",
    ]
    return "\n".join(lines)


def run_trust_weighted_decision_demo() -> CognitiveCycleResult:
    print("===== TAE SPRINT 4.4 — TRUST-WEIGHTED COLLECTIVE DECISION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — collective confidence weighted by calibrated organism trust.")
    print("No broker. No order execution. No live bot changes.")
    print()

    memory_store = OrganismMemoryStore()
    trust_weights = memory_store.build_trust_weights()

    if memory_store.loaded_at_startup:
        print(f"Loaded organism memory from: {memory_store.path}")
        for name, trust in sorted(trust_weights.items()):
            print(f"  {name}: memory trust={trust:.2f}")
    else:
        print(f"No prior organism memory — weights will use packet trust / neutral 50")
    print()

    life = LifeManager(start_generation=4)
    print(f"Life state: {'loaded' if life.loaded_from_storage else 'fresh'} from {life.state_path}")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Trust-weighted collective decision")

    cognitive = build_cognitive_stack()
    _register_knowledge_patterns(cognitive)

    evidence = EvidenceOrganism()
    context = ContextOrganism()
    momentum = MomentumOrganism()
    organisms: list[Organism] = [evidence, context, momentum]

    _apply_memory_trust(organisms, memory_store)

    for organism in organisms:
        cognitive.register_organism(organism, initial_trust=organism.health_status().get("trust"))

    bridge = EcosystemLifeBridge(life)
    cycle_label = _next_weighted_cycle_label(life)
    calibrator = TrustCalibrator()

    # Rebuild trust weights after applying memory trust to organisms
    trust_weights = memory_store.build_trust_weights()

    print("Running cognitive cycle with memory trust weighting...")
    result = cognitive.process_cycle(organisms, trust_weights=trust_weights)

    memory_store.record_cycle(result.packets, result.decision)
    calibrator.calibrate_store(memory_store)
    memory_path = memory_store.persist()

    bridge_summary = bridge.record_cognitive_cycle(
        result,
        cycle_label=cycle_label,
        write_journal=True,
    )
    life.persist()

    _record_weighted_life_events(life, result)
    life.persist()

    report = build_report(
        result,
        bridge_summary,
        life,
        memory_store,
        trust_weights,
        cycle_label,
        memory_path,
    )
    print()
    print(report)

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(report + "\n" + RESEARCH_SAFETY_BANNER + "\nANALYSIS_ONLY\n", encoding="utf-8")

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
    print(f"Persisted organism memory: {memory_path}")
    print(f"Persisted life state: {life.state_path}")

    return result


def main() -> None:
    run_trust_weighted_decision_demo()


if __name__ == "__main__":
    main()
