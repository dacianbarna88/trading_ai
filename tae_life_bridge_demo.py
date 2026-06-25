"""
TAE Life Bridge Demo — Sprint 3.6 + 3.7 persistence

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Runs one cognitive/ecosystem cycle and records biography via EcosystemLifeBridge.
State persists to tae_life_state.json across restarts.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import (
    ContextCognitiveOrganism,
    MomentumCognitiveOrganism,
    RiskCognitiveOrganism,
    build_cognitive_stack,
)

SUMMARY_TXT = "tae_life_bridge_summary.txt"


def _next_bridge_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: bridge_demo_cycle_")
    )
    return f"bridge_demo_cycle_{existing + 1}"


def run_bridge_demo() -> EcosystemLifeBridge:
    print("===== TAE SPRINT 3.6 — LIFE ↔ ECOSYSTEM BRIDGE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — records cognitive cycles into TAE biography.")
    print("No broker. No order execution. No live bot changes.")
    print()

    life = LifeManager(start_generation=3)
    if life.loaded_from_storage:
        print(f"Loaded prior state from: {life.state_path}")
        print(
            f"  journal={life.journal.count()} milestones={life.milestones.count()} "
            f"timeline={life.timeline.count()} events={len(life.events())} "
            f"achievements={life.achievements.count_unlocked()}"
        )
    else:
        print(f"No prior state — fresh LifeManager (will persist to {life.state_path})")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Record ecosystem cognition in TAE life story")

    bridge = EcosystemLifeBridge(life)

    cognitive = build_cognitive_stack()
    organisms = [
        ContextCognitiveOrganism(),
        MomentumCognitiveOrganism(),
        RiskCognitiveOrganism(),
    ]
    for organism in organisms:
        cognitive.register_organism(organism)

    cycle_label = _next_bridge_cycle_label(life)
    print(f"Running simulated cognitive cycle ({cycle_label})...")
    result, bridge_summary = bridge.run_and_record(
        cognitive,
        organisms,
        cycle_label=cycle_label,
        write_journal=True,
        persist=True,
    )

    print()
    print(bridge.format_summary(bridge_summary, result))

    snapshot = life.daily_snapshot()
    print("===== LIFE DAILY SNAPSHOT =====")
    for key, value in snapshot.items():
        if key != "metrics":
            print(f"  {key}: {value}")
    print("  metrics:")
    for key, value in snapshot["metrics"].items():
        print(f"    {key}: {value}")

    status_preview = life.status_generator.generate(
        age=life.age,
        generation=life.generation,
        journal=life.journal,
        milestones=life.milestones,
        achievements=life.achievements,
        metrics=snapshot["metrics"],
        current_mission=life.current_mission,
    )
    print()
    print("===== TAE_STATUS.md (regenerated) =====")
    print(status_preview)

    summary_path = Path(SUMMARY_TXT)
    full_output = bridge.format_summary(bridge_summary, result) + "\n" + status_preview
    summary_path.write_text(
        "===== TAE LIFE BRIDGE DEMO =====\n"
        + RESEARCH_SAFETY_BANNER
        + "\nANALYSIS_ONLY\n\n"
        + f"Loaded from storage: {life.loaded_from_storage}\n"
        + f"Cycle: {cycle_label}\n\n"
        + full_output
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved: {summary_path}")
    print(f"Saved: TAE_STATUS.md")
    print(f"Persisted: {life.state_path}")

    return bridge


def main() -> None:
    run_bridge_demo()


if __name__ == "__main__":
    main()
