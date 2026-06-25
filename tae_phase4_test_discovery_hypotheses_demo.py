"""
TAE Phase IV Sprint D3 — Test Discovery-Derived Hypotheses

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Uses existing Sprint 5.1 Experiment Runner on UNTESTED hypotheses
bridged from discoveries (source_cycle starts with disc_).
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis import (
    ExperimentRunner,
    ExperimentResultsStore,
    HypothesisRegistry,
)
from research_core.hypothesis.experiment_result import ExperimentStatus as ExpStatus
from research_core.life import LifeManager

SUMMARY_TXT = "tae_phase4_test_discovery_hypotheses_summary.txt"
DISCOVERY_SOURCE_PREFIX = "disc_"


def list_discovery_derived_untested(registry: HypothesisRegistry) -> list:
    return [
        h
        for h in registry.list_untested()
        if str(h.source_cycle).startswith(DISCOVERY_SOURCE_PREFIX)
    ]


def list_discovery_derived_all(registry: HypothesisRegistry) -> list:
    return [
        h
        for h in registry.list_all()
        if str(h.source_cycle).startswith(DISCOVERY_SOURCE_PREFIX)
    ]


def format_report(
    registry: HypothesisRegistry,
    results_store: ExperimentResultsStore,
    new_results: list,
    found_count: int,
    results_path: Path,
    registry_path: Path,
) -> str:
    tested_ids = {r.hypothesis_id for r in new_results if r.status == ExpStatus.TESTED}
    insufficient_ids = {
        r.hypothesis_id for r in new_results if r.status == ExpStatus.INSUFFICIENT_DATA
    }

    lines = [
        "===== TAE PHASE IV SPRINT D3 — DISCOVERY HYPOTHESIS TESTS =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Experiment runner on discovery-derived hypotheses — NOT trading.",
        "",
        f"Discovery-derived hypotheses in registry: {len(list_discovery_derived_all(registry))}",
        f"Discovery-derived UNTESTED found: {found_count}",
        f"Tested this run: {len(tested_ids)}",
        f"Insufficient data this run: {len(insufficient_ids)}",
        f"New experiment results: {len(new_results)}",
        f"Total results in store: {results_store.count()}",
        "",
        "===== EXPERIMENT RESULTS (this run) =====",
    ]

    if not new_results:
        lines.append("  No discovery-derived UNTESTED hypotheses — nothing to run.")
    else:
        for result in new_results:
            lines.extend(
                [
                    f"  {result.experiment_id} → {result.hypothesis_id}",
                    f"    title: {result.hypothesis_title[:80]}",
                    f"    sample_size: {result.sample_size}",
                    f"    accuracy: {result.accuracy:.2%}",
                    f"    avg_forward_return: {result.avg_forward_return:.4f}%",
                    f"    status: {result.status.value}",
                    "",
                ]
            )

    lines.append("===== DISCOVERY-DERIVED HYPOTHESIS STATUS =====")
    for hypothesis in list_discovery_derived_all(registry):
        lines.append(f"  {hypothesis.hypothesis_id} ({hypothesis.source_cycle}): {hypothesis.status.value}")

    lines.extend(
        [
            "",
            f"Results persisted: {results_path}",
            f"Registry persisted: {registry_path}",
            "",
            "No broker. No execution. No live bot.",
            "",
        ]
    )
    return "\n".join(lines)


def run_discovery_hypothesis_tests() -> list:
    print("===== TAE PHASE IV SPRINT D3 — TEST DISCOVERY HYPOTHESES =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Sprint 5.1 experiment runner — discovery-derived UNTESTED only.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = HypothesisRegistry()
    results_store = ExperimentResultsStore()
    runner = ExperimentRunner(registry=registry, results_store=results_store)

    discovery_derived = list_discovery_derived_all(registry)
    to_test = list_discovery_derived_untested(registry)

    print(f"Hypothesis registry: {registry.path} ({registry.count()} total)")
    print(f"Discovery-derived hypotheses: {len(discovery_derived)}")
    print(f"Discovery-derived UNTESTED: {len(to_test)}")
    if results_store.loaded_at_startup:
        print(f"Experiment results loaded: {results_store.count()} prior")
    print()

    if not to_test:
        print("No discovery-derived UNTESTED hypotheses — skipping experiments.")
        new_results: list = []
    else:
        print(f"Running experiments for {len(to_test)} discovery-derived hypothesis/hypotheses...")
        for hyp in to_test:
            print(f"  → {hyp.hypothesis_id} (source_cycle={hyp.source_cycle})")
        new_results = runner.run_hypotheses(to_test)
        print(f"Completed {len(new_results)} experiment(s)")

    results_path = results_store.persist()
    registry_path = registry.persist()
    print(f"Persisted results: {results_path}")
    print(f"Updated registry: {registry_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Test discovery-derived hypotheses — research experiments")
    if not life.timeline.has_title("Discovery Hypothesis Tests"):
        life.record_event(
            "milestone",
            "Discovery Hypothesis Tests",
            "Phase IV D3 — discovery-bridged hypotheses tested via experiment runner.",
            milestone_importance=7,
        )
    if new_results:
        tested = sum(1 for r in new_results if r.status == ExpStatus.TESTED)
        life.record_event(
            "research_experiment",
            "Phase IV D3 Discovery Hypothesis Tests",
            f"Tested {tested} discovery-derived hypothesis/hypotheses — not execution.",
            add_timeline=False,
        )
    life.persist()

    report = format_report(
        registry,
        results_store,
        new_results,
        len(to_test),
        results_path,
        registry_path,
    )
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
    print(f"Persisted life state: {life.state_path}")

    return new_results


def main() -> None:
    run_discovery_hypothesis_tests()


if __name__ == "__main__":
    main()
