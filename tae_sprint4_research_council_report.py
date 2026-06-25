"""
TAE Sprint 4.5 — Research Council Report

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Runs the research organism council, persists memory/life state, and publishes
a readable explanation of the collective decision.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
from research_core.ecosystem.organism import Organism
from research_core.ecosystem.organism_memory import OrganismMemoryStore
from research_core.ecosystem.organisms import (
    ContextOrganism,
    EvidenceOrganism,
    MomentumOrganism,
)
from research_core.ecosystem.research_council_report import (
    DEFAULT_REPORT_PATH,
    ResearchCouncilReporter,
)
from research_core.ecosystem.trust_calibration import TrustCalibrator
from research_core.life import LifeManager
from research_core.life.ecosystem_bridge import EcosystemLifeBridge

from ecosystem_cognitive_demo_v1 import build_cognitive_stack
from tae_sprint4_multi_organism_demo import _register_knowledge_patterns
from tae_sprint4_trust_calibration_demo import _apply_memory_trust

SUMMARY_TXT = "tae_sprint4_research_council_summary.txt"


def _next_council_cycle_label(life: LifeManager) -> str:
    existing = sum(
        1 for event in life.events()
        if event.title.startswith("Cognitive Cycle: sprint4_research_council_cycle_")
    )
    return f"sprint4_research_council_cycle_{existing + 1}"


def _record_council_life_events(life: LifeManager, cycle_label: str) -> None:
    if not life.timeline.has_title("Research Council Report"):
        life.record_event(
            "milestone",
            "Research Council Report",
            "Sprint 4.5 — readable council report explains collective research decisions.",
            milestone_importance=8,
        )
        life.record_event(
            "research_experiment",
            "Sprint 4.5 Research Council",
            "tae_sprint4_research_council_report — council-style collective deliberation report.",
        )

    life.record_event(
        "journal_entry",
        f"Research Council: {cycle_label}",
        "Council session report generated with organism contributions and verdict.",
        add_timeline=False,
    )


def run_research_council_report() -> tuple[CognitiveCycleResult, str]:
    print("===== TAE SPRINT 4.5 — RESEARCH COUNCIL REPORT =====")
    print(RESEARCH_SAFETY_BANNER)
    print("ANALYSIS_ONLY — council deliberation report, not trade execution.")
    print("No broker. No live bot. No order execution.")
    print()

    memory_store = OrganismMemoryStore()
    life = LifeManager(start_generation=4)

    if memory_store.loaded_at_startup:
        print(f"Organism memory loaded: {memory_store.path}")
    else:
        print(f"Organism memory fresh → {memory_store.path}")

    print(f"Life state: {'loaded' if life.loaded_from_storage else 'fresh'} → {life.state_path}")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("Research Council — explain collective decisions")

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
    cycle_label = _next_council_cycle_label(life)
    calibrator = TrustCalibrator()

    print(f"Convening Research Council ({cycle_label})...")
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

    _record_council_life_events(life, cycle_label)
    life.persist()

    reporter = ResearchCouncilReporter()
    report = reporter.build(
        result,
        memory_store=memory_store,
        life=life,
        cycle_label=cycle_label,
    )
    report_path = reporter.write(report, DEFAULT_REPORT_PATH)

    life.status_generator.generate(
        age=life.age,
        generation=life.generation,
        journal=life.journal,
        milestones=life.milestones,
        achievements=life.achievements,
        metrics=life.metrics,
        current_mission=life.current_mission,
    )

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(report, encoding="utf-8")

    print()
    print(report)
    print(f"Saved council report: {report_path}")
    print(f"Saved summary: {summary_path}")
    print(f"Saved: TAE_STATUS.md")
    print(f"Bridge events recorded: {bridge_summary.events_recorded}")
    print(f"Persisted organism memory: {memory_path}")
    print(f"Persisted life state: {life.state_path}")

    return result, report


def main() -> None:
    run_research_council_report()


if __name__ == "__main__":
    main()
