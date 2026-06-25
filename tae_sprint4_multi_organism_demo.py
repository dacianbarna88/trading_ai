"""
TAE Sprint 4.1 — Multi-Organism Research Bus

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Runs Evidence, Context, and Momentum research organisms together on the cognitive bus.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
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

SUMMARY_TXT = "tae_sprint4_multi_organism_summary.txt"


def _next_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint4_multi_organism_cycle_")
    )
    return f"sprint4_multi_organism_cycle_{existing + 1}"


def _register_knowledge_patterns(cognitive) -> None:
    cognitive.knowledge.store_validated_pattern(
        pattern_id="context_v18_bear_oversold",
        description="V1.8 context candidate RSI < 40 in BEAR regime",
        confidence=72.0,
        trust=62.0,
        success_conditions=["Market_Regime BEAR", "RSI_14 < 40"],
        failure_conditions=["BULL regime mismatch"],
    )
    cognitive.knowledge.store_validated_pattern(
        pattern_id="momentum_impulse_burst",
        description="Momentum impulse with elevated daily gain and volume",
        confidence=76.0,
        trust=65.0,
        success_conditions=["Daily_Gain_Pct >= 7", "Volume_Ratio >= 2"],
        failure_conditions=["weak impulse below 5% gain"],
    )
    cognitive.knowledge.store_validated_pattern(
        pattern_id="evidence_v40_paper_candidate",
        description="Evidence Engine V4.0 PAPER_CANDIDATE dossier threshold",
        confidence=68.0,
        trust=70.0,
        success_conditions=["Overall_Evidence_Score >= 60"],
        failure_conditions=["Decision_LABEL IGNORE"],
    )


def _record_multi_organism_life_events(life: LifeManager, organism_names: list[str]) -> None:
    if not life.timeline.has_title("Multi-Organism Research Bus"):
        life.record_event(
            "organism_registered",
            "Multi-Organism Research Bus Live",
            f"Active organisms: {', '.join(organism_names)}",
            milestone_importance=9,
        )
        life.record_event(
            "milestone",
            "Multi-Organism Research Bus",
            "Three research organisms running collective cognition on TAE bus.",
            milestone_importance=9,
        )
        life.record_event(
            "research_experiment",
            "Sprint 4.1 Multi-Organism Demo",
            "tae_sprint4_multi_organism_demo — evidence + context + momentum bus.",
        )


def build_report(
    organism_names: list[str],
    result: CognitiveCycleResult,
    bridge_summary: BridgeRecordSummary,
    life: LifeManager,
    cycle_label: str,
) -> str:
    packet_lines = []
    for packet in result.packets:
        packet_lines.append(
            f"  • {packet.organism_name}: confidence={packet.confidence:.1f} "
            f"trust={packet.trust:.1f} action={packet.recommended_action}"
        )
        packet_lines.append(f"    {packet.observation_summary}")

    curiosity_lines = []
    for question in result.curiosity_questions:
        curiosity_lines.append(f"  [{question.priority_score:.0f}] {question.question}")

    lines = [
        "===== TAE SPRINT 4.1 — MULTI-ORGANISM RESEARCH BUS =====",
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
            "===== PACKETS BY ORGANISM =====",
            *packet_lines,
            "",
            f"Cognitive Status: {result.cognitive_status}",
            f"Collective Confidence: {result.decision.collective_confidence:.2f}",
            f"Decision Level: {result.decision.confidence_level.value}",
            f"Agreement: {result.decision.agreement:.2f}",
            f"Disagreement: {result.decision.disagreement:.2f}",
            f"Feedback Generated: {len(result.feedback)}",
            "",
            "===== CURIOSITY QUESTIONS =====",
        ]
    )
    if curiosity_lines:
        lines.extend(curiosity_lines)
    else:
        lines.append("  None generated.")
    lines.extend(
        [
            "",
            f"Life Events Recorded (bridge): {bridge_summary.events_recorded}",
            f"State Persisted: {life.state_path}",
            f"Loaded From Storage: {life.loaded_from_storage}",
            "",
            "===== BRIDGE EVENT TITLES =====",
        ]
    )
    for title in bridge_summary.event_titles:
        lines.append(f"  • {title}")
    lines.extend(
        [
            "",
            f"TAE Generation: {life.generation.current_generation()}",
            f"Journal Entries: {life.journal.count()}",
            f"Timeline Events: {life.timeline.count()}",
            f"Achievements Unlocked: {life.achievements.count_unlocked()}",
            "",
        ]
    )
    return "\n".join(lines)


def run_multi_organism_demo() -> tuple[CognitiveCycleResult, BridgeRecordSummary]:
    print("===== TAE SPRINT 4.1 — MULTI-ORGANISM RESEARCH BUS =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — evidence + context + momentum on cognitive bus.")
    print("No broker. No order execution. No live bot changes.")
    print()

    life = LifeManager(start_generation=4)
    if life.loaded_from_storage:
        print(f"Loaded prior life state from: {life.state_path}")
        print(
            f"  journal={life.journal.count()} milestones={life.milestones.count()} "
            f"timeline={life.timeline.count()} events={len(life.events())}"
        )
    else:
        print(f"No prior life state — will persist to {life.state_path}")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Multi-Organism Research Bus — collective cognition")

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

    print("Registered organisms:")
    for name in organism_names:
        print(f"  • {name}")
    print()
    print(f"Running cognitive cycle ({cycle_label})...")

    result, bridge_summary = bridge.run_and_record(
        cognitive,
        organisms,
        cycle_label=cycle_label,
        write_journal=True,
        persist=True,
    )

    _record_multi_organism_life_events(life, organism_names)
    persisted_path = life.persist()

    report = build_report(organism_names, result, bridge_summary, life, cycle_label)
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
    print(f"Persisted: {persisted_path}")

    return result, bridge_summary


def main() -> None:
    run_multi_organism_demo()


if __name__ == "__main__":
    main()
