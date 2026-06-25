"""
TAE Sprint 5.2 — Hypothesis Quality Ranking

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Ranks tested hypotheses by research quality — not raw accuracy alone.
Does not convert hypotheses into live signals or execution paths.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis import HypothesisRegistry, ExperimentResultsStore
from research_core.hypothesis.hypothesis_ranking import (
    DEFAULT_RANKINGS_PATH,
    HypothesisRanker,
    HypothesisRankingsStore,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_sprint5_hypothesis_ranking_summary.txt"


def format_report(
    rankings_store: HypothesisRankingsStore,
    meta: dict,
) -> str:
    rankings = rankings_store.list_all()
    groups = rankings_store.duplicate_groups()

    lines = [
        "===== TAE SPRINT 5.2 — HYPOTHESIS QUALITY RANKING =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Research quality ranking — NOT live signal promotion or trading.",
        "",
        f"Total tested hypotheses: {meta.get('total_tested', 0)}",
        f"Ranked hypotheses: {meta.get('ranked_count', len(rankings))}",
        f"Duplicate groups flagged: {len(groups)}",
        "",
    ]

    if rankings:
        top = rankings[0]
        lines.extend(
            [
                "===== TOP HYPOTHESIS =====",
                f"  rank: #{top.rank}",
                f"  hypothesis_id: {top.hypothesis_id}",
                f"  title: {top.title}",
                f"  quality_score: {top.quality_score:.2f}",
                f"  accuracy: {top.accuracy:.2%}",
                f"  sample_size: {top.sample_size}",
                f"  avg_forward_return: {top.avg_forward_return:.4f}%",
                f"  robustness: {top.robustness_label}",
                f"  recommendation: {top.recommendation}",
                "",
            ]
        )
    else:
        lines.append("No rankable tested hypotheses found.")
        lines.append("")

    if groups:
        lines.append("===== DUPLICATE GROUPS =====")
        for group in groups:
            lines.append(f"  group: {group.group_id}")
            lines.append(f"    title: {group.title}")
            lines.append(f"    members ({len(group.member_ids)}): {', '.join(group.member_ids)}")
            lines.append(f"    best_representative: {group.best_hypothesis_id}")
        lines.append("")

    lines.append("===== FULL RANKING (quality score, not raw accuracy) =====")
    if not rankings:
        lines.append("  (empty)")
    else:
        for entry in rankings:
            lines.extend(
                [
                    f"  #{entry.rank} {entry.hypothesis_id}",
                    f"    title: {entry.title}",
                    f"    quality_score: {entry.quality_score:.2f}",
                    f"    accuracy: {entry.accuracy:.2%}",
                    f"    sample_size: {entry.sample_size}",
                    f"    avg_forward_return: {entry.avg_forward_return:.4f}%",
                    f"    robustness_label: {entry.robustness_label}",
                    f"    duplicate_group: {entry.duplicate_group}",
                    f"    recommendation: {entry.recommendation}",
                    "",
                ]
            )

    lines.extend(
        [
            rankings_store.format_summary(),
            f"Rankings persisted: {rankings_store.path}",
            "",
        ]
    )
    return "\n".join(lines)


def run_ranking_demo() -> list:
    print("===== TAE SPRINT 5.2 — HYPOTHESIS QUALITY RANKING =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Ranks tested hypotheses by research quality — not trading signals.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = HypothesisRegistry()
    results_store = ExperimentResultsStore()
    rankings_store = HypothesisRankingsStore(auto_load=False)

    print(f"Hypothesis registry: {registry.path} ({registry.count()} hypotheses)")
    print(
        f"Experiment results: {results_store.path} "
        f"({results_store.count()} results, loaded={results_store.loaded_at_startup})"
    )
    print()

    ranker = HypothesisRanker(registry=registry, results_store=results_store)
    rankings, duplicate_groups, meta = ranker.rank()

    rankings_store.set_rankings(rankings, duplicate_groups, meta)
    rankings_path = rankings_store.persist()

    print(f"Computed {len(rankings)} ranking(s)")
    print(f"Persisted rankings: {rankings_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Hypothesis quality ranking — research intelligence")
    if not life.timeline.has_title("Hypothesis Quality Ranking"):
        life.record_event(
            "milestone",
            "Hypothesis Quality Ranking",
            "Sprint 5.2 — tested hypotheses ranked by quality, sample, and return.",
            milestone_importance=7,
        )
    if rankings:
        top_id = meta.get("top_hypothesis_id", "")
        life.record_event(
            "research_ranking",
            "Sprint 5.2 Hypothesis Ranking",
            f"Ranked {len(rankings)} tested hypotheses; top={top_id}. Not live signals.",
            add_timeline=False,
        )
    life.persist()

    report = format_report(rankings_store, meta)
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
    print(f"Saved: {DEFAULT_RANKINGS_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return rankings


def main() -> None:
    run_ranking_demo()


if __name__ == "__main__":
    main()
