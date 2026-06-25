"""
TAE Sprint 4.3 — Organism Trust Calibration

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Uses organism memory to conservatively calibrate trust, then records cycle to life state.
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
from research_core.ecosystem.trust_calibration import TrustCalibrator, TrustCalibrationResult
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import BridgeRecordSummary, EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import build_cognitive_stack
from tae_sprint4_multi_organism_demo import _register_knowledge_patterns

SUMMARY_TXT = "tae_sprint4_trust_calibration_summary.txt"


def _next_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint4_trust_calibration_cycle_")
    )
    return f"sprint4_trust_calibration_cycle_{existing + 1}"


def _apply_memory_trust(organisms: list[Organism], memory_store: OrganismMemoryStore) -> None:
    for organism in organisms:
        memory = memory_store.get(organism.name)
        if memory is None:
            continue
        target = memory.trust_score if memory.trust_score > 0 else memory.avg_trust
        if target <= 0:
            continue
        current = float(organism.health_status().get("trust", 50.0))
        organism.update_trust(target - current, "loaded calibrated trust from organism memory")


def _record_calibration_life_events(
    life: LifeManager,
    calibration_results: list[TrustCalibrationResult],
) -> None:
    if not life.timeline.has_title("Organism Trust Calibration"):
        life.record_event(
            "milestone",
            "Organism Trust Calibration",
            "Sprint 4.3 — trust scores calibrated from memory stability and participation.",
            milestone_importance=8,
        )
        life.record_event(
            "research_experiment",
            "Sprint 4.3 Trust Calibration",
            "tae_sprint4_trust_calibration_demo — conservative memory-based trust updates.",
        )

    for result in calibration_results:
        life.record_event(
            "self_correction",
            f"Trust Calibrated: {result.organism_name}",
            (
                f"{result.previous_trust:.1f} → {result.new_trust:.1f} "
                f"(Δ{result.trust_delta:+.1f}) {result.calibration_reason[:120]}"
            ),
            add_timeline=False,
        )


def build_report(
    organism_names: list[str],
    result: CognitiveCycleResult,
    bridge_summary: BridgeRecordSummary,
    life: LifeManager,
    memory_store: OrganismMemoryStore,
    calibration_results: list[TrustCalibrationResult],
    calibrator: TrustCalibrator,
    cycle_label: str,
    memory_path: Path,
) -> str:
    lines = [
        "===== TAE SPRINT 4.3 — TRUST CALIBRATION =====",
        "",
        f"Cycle Label: {cycle_label}",
        f"Organisms Active: {len(organism_names)}",
        "",
        "Registered organisms:",
    ]
    for name in organism_names:
        lines.append(f"  • {name}")
    lines.extend(
        [
            "",
            f"Packets Produced: {len(result.packets)}",
            f"Cognitive Status: {result.cognitive_status}",
            f"Collective Confidence: {result.decision.collective_confidence:.2f}",
            f"Agreement: {result.decision.agreement:.2f}",
            f"Disagreement: {result.decision.disagreement:.2f}",
            f"Life Events Recorded (bridge): {bridge_summary.events_recorded}",
            "",
            calibrator.format_report(calibration_results),
            memory_store.format_summary(),
            f"Organism Memory Loaded At Startup: {memory_store.loaded_at_startup}",
            f"Organism Memory Persisted: {memory_path}",
            f"Life State Persisted: {life.state_path}",
            "",
            f"TAE Generation: {life.generation.current_generation()}",
            f"Journal Entries: {life.journal.count()}",
            f"Timeline Events: {life.timeline.count()}",
            "",
        ]
    )
    return "\n".join(lines)


def run_trust_calibration_demo() -> tuple[CognitiveCycleResult, list[TrustCalibrationResult]]:
    print("===== TAE SPRINT 4.3 — ORGANISM TRUST CALIBRATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — conservative trust calibration from organism memory.")
    print("No broker. No order execution. No live bot changes.")
    print()

    memory_store = OrganismMemoryStore()
    if memory_store.loaded_at_startup:
        print(f"Loaded organism memory from: {memory_store.path}")
        for memory in memory_store.all_memories():
            trust_display = memory.trust_score if memory.trust_score > 0 else memory.avg_trust
            print(
                f"  {memory.organism_name}: cycles={memory.cycles_seen} "
                f"trust_score={trust_display:.2f} stability={memory.confidence_stability:.2f}"
            )
    else:
        print(f"No prior organism memory — will persist to {memory_store.path}")
    print()

    life = LifeManager(start_generation=4)
    print(f"Life state: {'loaded' if life.loaded_from_storage else 'fresh'} from {life.state_path}")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Organism trust calibration from memory")

    cognitive = build_cognitive_stack()
    _register_knowledge_patterns(cognitive)

    evidence = EvidenceOrganism()
    context = ContextOrganism()
    momentum = MomentumOrganism()
    organisms: list[Organism] = [evidence, context, momentum]
    organism_names = [EVIDENCE_ORGANISM_NAME, CONTEXT_ORGANISM_NAME, MOMENTUM_ORGANISM_NAME]

    _apply_memory_trust(organisms, memory_store)

    for organism in organisms:
        cognitive.register_organism(organism, initial_trust=organism.health_status().get("trust"))

    bridge = EcosystemLifeBridge(life)
    cycle_label = _next_cycle_label(life)
    calibrator = TrustCalibrator()

    print("Running cognitive cycle...")
    result = cognitive.process_cycle(organisms)

    memory_store.record_cycle(result.packets, result.decision)
    calibration_results = calibrator.calibrate_store(memory_store)
    memory_path = memory_store.persist()

    bridge_summary = bridge.record_cognitive_cycle(
        result,
        cycle_label=cycle_label,
        write_journal=True,
    )
    life.persist()

    _record_calibration_life_events(life, calibration_results)
    life.persist()

    report = build_report(
        organism_names,
        result,
        bridge_summary,
        life,
        memory_store,
        calibration_results,
        calibrator,
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

    return result, calibration_results


def main() -> None:
    run_trust_calibration_demo()


if __name__ == "__main__":
    main()
