"""
TAE Sprint 4.0 — First Real Research Organism

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Wires Evidence Engine V4.0 as a live organism on the cognitive bus,
records the cycle through LifeManager / EcosystemLifeBridge, and persists state.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
from research_core.ecosystem.organisms import EvidenceOrganism, ORGANISM_NAME
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import BridgeRecordSummary, EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import build_cognitive_stack

SUMMARY_TXT = "tae_sprint4_real_organism_summary.txt"


def _next_sprint4_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint4_real_organism_cycle_")
    )
    return f"sprint4_real_organism_cycle_{existing + 1}"


def _register_evidence_patterns(cognitive) -> None:
    cognitive.knowledge.store_validated_pattern(
        pattern_id="evidence_v40_paper_candidate",
        description="Evidence Engine V4.0 PAPER_CANDIDATE dossier threshold",
        confidence=68.0,
        trust=70.0,
        success_conditions=["Overall_Evidence_Score >= 60", "low conflict penalty"],
        failure_conditions=["Decision_LABEL IGNORE", "high conflict"],
    )
    cognitive.knowledge.store_validated_pattern(
        pattern_id="evidence_v40_high_conviction",
        description="Evidence Engine V4.0 HIGH_CONVICTION_PAPER_CANDIDATE dossier",
        confidence=82.0,
        trust=75.0,
        success_conditions=["Overall_Evidence_Score >= 80", "regime alignment"],
        failure_conditions=["conflict score < 50"],
    )


def _record_sprint4_life_events(life: LifeManager, organism: EvidenceOrganism) -> None:
    if not life.timeline.has_title("First Real Research Organism"):
        life.record_event(
            "organism_registered",
            "Evidence Engine Organism Live",
            f"{ORGANISM_NAME} registered on ecosystem communication bus.",
            milestone_importance=9,
        )
        life.record_event(
            "milestone",
            "First Real Research Organism",
            "Evidence Engine V4.0 wired as Generation 4 live research organism.",
            milestone_importance=10,
        )
        life.record_event(
            "research_experiment",
            "Sprint 4 Real Organism Demo",
            "tae_sprint4_real_organism_demo executed — first live research module on bus.",
        )

    dossier = organism.last_dossier()
    if dossier:
        life.record_event(
            "knowledge_item",
            f"Evidence Dossier: {dossier.get('Ticker')}",
            (
                f"Decision={dossier.get('Decision_Label')} "
                f"score={dossier.get('Overall_Evidence_Score')} "
                f"consensus={dossier.get('Edge_Consensus_Score')}"
            ),
            add_timeline=False,
        )


def build_report(
    organism: EvidenceOrganism,
    result: CognitiveCycleResult,
    bridge_summary: BridgeRecordSummary,
    life: LifeManager,
    cycle_label: str,
) -> str:
    dossier = organism.last_dossier() or {}
    lines = [
        "===== TAE SPRINT 4.0 — FIRST REAL RESEARCH ORGANISM =====",
        "",
        f"Organism: {organism.name}",
        f"Cycle Label: {cycle_label}",
        f"Signals Available: {organism.health_status().get('signals_available', 0)}",
        f"Packets Produced: {len(result.packets)}",
        f"Cognitive Status: {result.cognitive_status}",
        f"Collective Confidence: {result.decision.collective_confidence:.2f}",
        f"Decision Level: {result.decision.confidence_level.value}",
        f"Agreement: {result.decision.agreement:.2f}",
        f"Disagreement: {result.decision.disagreement:.2f}",
        f"Life Events Recorded (bridge): {bridge_summary.events_recorded}",
        f"State Persisted: {life.state_path}",
        f"Loaded From Storage: {life.loaded_from_storage}",
        "",
        "===== EVIDENCE DOSSIER (latest signal) =====",
        f"  Ticker: {dossier.get('Ticker', 'n/a')}",
        f"  Signal Date: {dossier.get('Signal_Date', 'n/a')}",
        f"  Decision Label: {dossier.get('Decision_Label', 'n/a')}",
        f"  Overall Score: {dossier.get('Overall_Evidence_Score', 'n/a')}",
        f"  Edge Consensus: {dossier.get('Edge_Consensus_Score', 'n/a')}",
        f"  Risk Level: {dossier.get('Risk_Level', 'n/a')}",
        "",
        "===== PACKETS =====",
    ]
    for packet in result.packets:
        lines.append(
            f"  • {packet.organism_name}: confidence={packet.confidence:.1f} "
            f"action={packet.recommended_action}"
        )
        lines.append(f"    {packet.observation_summary}")
    lines.extend(
        [
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


def run_sprint4_demo() -> tuple[EvidenceOrganism, CognitiveCycleResult, BridgeRecordSummary]:
    print("===== TAE SPRINT 4.0 — FIRST REAL RESEARCH ORGANISM =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — Evidence Engine V4.0 on ecosystem bus.")
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
    life.set_current_mission("First Real Research Organism — Evidence Engine Live")

    cognitive = build_cognitive_stack()
    _register_evidence_patterns(cognitive)

    organism = EvidenceOrganism()
    cognitive.register_organism(organism, initial_trust=72.0)

    bridge = EcosystemLifeBridge(life)
    cycle_label = _next_sprint4_cycle_label(life)

    print(f"Running cognitive cycle with {organism.name}...")
    result, bridge_summary = bridge.run_and_record(
        cognitive,
        [organism],
        cycle_label=cycle_label,
        write_journal=True,
        persist=True,
    )

    _record_sprint4_life_events(life, organism)
    persisted_path = life.persist()

    report = build_report(organism, result, bridge_summary, life, cycle_label)
    print()
    print(report)

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(
        report + "\n" + RESEARCH_SAFETY_BANNER + "\nANALYSIS_ONLY\n",
        encoding="utf-8",
    )

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

    return organism, result, bridge_summary


def main() -> None:
    run_sprint4_demo()


if __name__ == "__main__":
    main()
