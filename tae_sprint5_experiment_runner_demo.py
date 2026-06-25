"""
TAE Sprint 5.1 — Experiment Runner Foundation

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Tests UNTESTED hypotheses against historical research CSVs.
Does not generate trade signals or touch live execution paths.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis import (
    ExperimentRunner,
    ExperimentResultsStore,
    HypothesisRegistry,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_sprint5_experiment_runner_summary.txt"


def _record_experiment_life_events(life: LifeManager, results_count: int) -> None:
    if not life.timeline.has_title("Experiment Runner Foundation"):
        life.record_event(
            "milestone",
            "Experiment Runner Foundation",
            "Sprint 5.1 — UNTESTED hypotheses tested against historical research cohorts.",
            milestone_importance=8,
        )
        life.record_event(
            "research_experiment",
            "Sprint 5.1 Experiment Runner",
            "tae_sprint5_experiment_runner_demo — structured historical tests, not trading.",
        )

    if results_count > 0:
        life.record_event(
            "research_experiment",
            f"Experiment batch: {results_count} hypothesis test(s)",
            "Historical cohort experiments completed — no execution.",
            add_timeline=False,
        )


def format_report(
    registry: HypothesisRegistry,
    results_store: ExperimentResultsStore,
    new_results: list,
    untested_before: int,
    results_path: Path,
    registry_path: Path,
) -> str:
    lines = [
        "===== TAE SPRINT 5.1 — EXPERIMENT RUNNER =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Historical research tests only — NOT trade signals or orders.",
        "",
        f"Hypotheses in registry: {registry.count()}",
        f"Untested before run: {untested_before}",
        f"Hypotheses tested this run: {len(new_results)}",
        f"Results in store (total): {results_store.count()}",
        f"Results loaded at startup: {results_store.loaded_at_startup}",
        "",
        "===== NEW EXPERIMENT RESULTS =====",
    ]

    if not new_results:
        lines.append("  No untested hypotheses — nothing to run.")
    else:
        for result in new_results:
            lines.extend(
                [
                    f"  Experiment: {result.experiment_id}",
                    f"    hypothesis_id: {result.hypothesis_id}",
                    f"    title: {result.hypothesis_title}",
                    f"    sample_size: {result.sample_size}",
                    f"    wins: {result.wins} | losses: {result.losses} | neutral: {result.neutral}",
                    f"    accuracy: {result.accuracy:.2%}",
                    f"    avg_forward_return: {result.avg_forward_return:.4f}%",
                    f"    horizon: {result.horizon}",
                    f"    status: {result.status.value}",
                    f"    notes: {result.notes[:150]}{'...' if len(result.notes) > 150 else ''}",
                    "",
                ]
            )

    lines.extend(
        [
            "===== HYPOTHESIS REGISTRY (status after update) =====",
        ]
    )
    for hypothesis in registry.list_all():
        lines.append(f"  {hypothesis.hypothesis_id}: {hypothesis.title} [{hypothesis.status.value}]")

    lines.extend(
        [
            "",
            results_store.format_summary(),
            f"Registry updated: {registry_path}",
            f"Results persisted: {results_path}",
            "",
        ]
    )
    return "\n".join(lines)


def run_experiment_runner_demo() -> list:
    print("===== TAE SPRINT 5.1 — EXPERIMENT RUNNER FOUNDATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Tests UNTESTED hypotheses on historical research data — not trading.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = HypothesisRegistry()
    results_store = ExperimentResultsStore()
    runner = ExperimentRunner(registry=registry, results_store=results_store)

    untested_before = len(registry.list_untested())
    print(f"Hypothesis registry: {registry.path} ({registry.count()} total, {untested_before} untested)")
    if results_store.loaded_at_startup:
        print(f"Experiment results loaded: {results_store.path} ({results_store.count()} prior)")
    else:
        print(f"Experiment results fresh → {results_store.path}")
    print()

    if untested_before == 0:
        print("No UNTESTED hypotheses — skipping experiments.")
        new_results: list = []
    else:
        print(f"Running experiments for {untested_before} untested hypothesis/hypotheses...")
        new_results = runner.run_untested()
        results_path = results_store.persist()
        registry_path = registry.persist()
        print(f"Persisted results: {results_path}")
        print(f"Updated registry: {registry_path}")

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Experiment Runner — test hypotheses on historical data")
    _record_experiment_life_events(life, len(new_results))
    life.persist()

    results_path = results_store.path
    registry_path = registry.path

    report = format_report(
        registry,
        results_store,
        new_results,
        untested_before,
        results_path,
        registry_path,
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
    print(f"Persisted life state: {life.state_path}")

    return new_results


def main() -> None:
    run_experiment_runner_demo()


if __name__ == "__main__":
    main()
