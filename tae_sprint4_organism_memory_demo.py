"""
TAE Sprint 4.2 — Organism Memory & Performance Tracking

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Runs three research organisms, updates per-organism memory, persists to JSON,
and records the cycle through LifeManager / EcosystemLifeBridge.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
from research_core.ecosystem.organism_memory import OrganismMemoryStore
from research_core.ecosystem.organisms import (
    CONTEXT_ORGANISM_NAME,
    EVIDENCE_ORGANISM_NAME,
    MOMENTUM_ORGANISM_NAME,
    ContextOrganism,
    EvidenceOrganism,
    MomentumOrganism,
)
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import BridgeRecordSummary, EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import build_cognitive_stack
from tae_sprint4_multi_organism_demo import _register_knowledge_patterns

SUMMARY_TXT = "tae_sprint4_organism_memory_summary.txt"


def _next_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint4_organism_memory_cycle_")
    )
    return f"sprint4_organism_memory_cycle_{existing + 1}"


def _record_memory_life_events(life: LifeManager, memory_store: OrganismMemoryStore) -> None:
    if not life.timeline.has_title("Organism Memory Tracking"):
        life.record_event(
            "research_experiment",
            "Organism Memory Tracking",
            "Sprint 4.2 — per-organism packet memory persisted to tae_organism_memory.json.",
            milestone_importance=8,
        )
        life.record_event(
            "milestone",
            "Organism Memory Tracking",
            "TAE organisms now accumulate confidence, trust, and action history.",
            milestone_importance=8,
        )

    for memory in memory_store.all_memories():
        life.record_event(
            "knowledge_item",
            f"Organism Memory: {memory.organism_name}",
            (
                f"cycles={memory.cycles_seen} packets={memory.packets_produced} "
                f"avg_conf={memory.avg_confidence:.1f} avg_trust={memory.avg_trust:.1f}"
            ),
            add_timeline=False,
        )


def build_report(
    organism_names: list[str],
    result: CognitiveCycleResult,
    bridge_summary: BridgeRecordSummary,
    life: LifeManager,
    memory_store: OrganismMemoryStore,
    cycle_label: str,
    memory_path: Path,
) -> str:
    packet_lines = []
    for packet in result.packets:
        packet_lines.append(
            f"  • {packet.organism_name}: confidence={packet.confidence:.1f} "
            f"trust={packet.trust:.1f} action={packet.recommended_action}"
        )

    lines = [
        "===== TAE SPRINT 4.2 — ORGANISM MEMORY =====",
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
            "",
            "===== PACKETS THIS CYCLE =====",
            *packet_lines,
            "",
            f"Cognitive Status: {result.cognitive_status}",
            f"Collective Confidence: {result.decision.collective_confidence:.2f}",
            f"Agreement: {result.decision.agreement:.2f}",
            f"Disagreement: {result.decision.disagreement:.2f}",
            f"Life Events Recorded (bridge): {bridge_summary.events_recorded}",
            "",
            memory_store.format_summary(),
            f"Organism Memory Loaded At Startup: {memory_store.loaded_at_startup}",
            f"Organism Memory Persisted: {memory_path}",
            f"Life State Persisted: {life.state_path}",
            f"Life Loaded From Storage: {life.loaded_from_storage}",
            "",
            f"TAE Generation: {life.generation.current_generation()}",
            f"Journal Entries: {life.journal.count()}",
            f"Timeline Events: {life.timeline.count()}",
            "",
        ]
    )
    return "\n".join(lines)


def run_organism_memory_demo() -> tuple[CognitiveCycleResult, OrganismMemoryStore]:
    print("===== TAE SPRINT 4.2 — ORGANISM MEMORY & PERFORMANCE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — per-organism memory across cognitive cycles.")
    print("No broker. No order execution. No live bot changes.")
    print()

    memory_store = OrganismMemoryStore()
    if memory_store.loaded_from_storage:
        print(f"Loaded organism memory from: {memory_store.path}")
        for memory in memory_store.all_memories():
            print(
                f"  {memory.organism_name}: cycles={memory.cycles_seen} "
                f"packets={memory.packets_produced} avg_conf={memory.avg_confidence:.2f}"
            )
    else:
        print(f"No prior organism memory — will persist to {memory_store.path}")
    print()

    life = LifeManager(start_generation=4)
    if life.loaded_from_storage:
        print(f"Loaded life state from: {life.state_path}")
    else:
        print(f"No prior life state — will persist to {life.state_path}")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Organism memory — track packet performance over time")

    cognitive = build_cognitive_stack()
    _register_knowledge_patterns(cognitive)

    evidence = EvidenceOrganism()
    context = ContextOrganism()
    momentum = MomentumOrganism()
    organisms = [evidence, context, momentum]
    organism_names = [EVIDENCE_ORGANISM_NAME, CONTEXT_ORGANISM_NAME, MOMENTUM_ORGANISM_NAME]

    for organism in organisms:
        cognitive.register_organism(organism)

    bridge = EcosystemLifeBridge(life)
    cycle_label = _next_cycle_label(life)

    print("Running cognitive cycle with memory tracking...")
    result = cognitive.process_cycle(organisms)

    memory_store.record_cycle(result.packets, result.decision)
    memory_path = memory_store.persist()

    bridge_summary = bridge.record_cognitive_cycle(
        result,
        cycle_label=cycle_label,
        write_journal=True,
    )
    life.persist()

    _record_memory_life_events(life, memory_store)
    life.persist()

    report = build_report(
        organism_names,
        result,
        bridge_summary,
        life,
        memory_store,
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

    return result, memory_store


def main() -> None:
    run_organism_memory_demo()


if __name__ == "__main__":
    main()
