"""
TAE Phase IV Sprint D4 — Rank Discovery-Derived Hypotheses

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Ranks discovery-derived tested hypotheses and compares to Sprint 5 originals.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis import HypothesisRegistry, ExperimentResultsStore
from research_core.hypothesis.hypothesis_ranking import (
    DEFAULT_DISCOVERY_RANKINGS_PATH,
    DISCOVERY_RANKINGS_SCHEMA_NAME,
    HypothesisRankingEntry,
    HypothesisRanker,
    SCHEMA_VERSION,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_phase4_rank_discovery_hypotheses_summary.txt"
DISCOVERY_PREFIX = "disc_"
SPRINT5_HYPOTHESIS_PREFIX = "hyp_s5_"


def _entry_to_dict(entry: HypothesisRankingEntry) -> dict[str, Any]:
    return entry.to_dict()


def _build_comparison(
    discovery_top: HypothesisRankingEntry | None,
    sprint5_top: HypothesisRankingEntry | None,
) -> dict[str, Any]:
    if discovery_top is None or sprint5_top is None:
        return {
            "knowledge_base_improved": False,
            "summary": "Insufficient data for comparison.",
            "discovery_top_id": discovery_top.hypothesis_id if discovery_top else "",
            "sprint5_top_id": sprint5_top.hypothesis_id if sprint5_top else "",
        }

    quality_delta = discovery_top.quality_score - sprint5_top.quality_score
    accuracy_delta = discovery_top.accuracy - sprint5_top.accuracy
    return_delta = discovery_top.avg_forward_return - sprint5_top.avg_forward_return

    improved = (
        quality_delta > 0
        or (quality_delta >= -2.0 and return_delta > 0.5)
        or (discovery_top.sample_size > sprint5_top.sample_size and accuracy_delta >= 0)
    )

    if improved:
        summary = (
            f"Discovery pipeline contributed new research: top discovery "
            f"({discovery_top.hypothesis_id}) quality {discovery_top.quality_score:.1f} "
            f"vs Sprint 5 best ({sprint5_top.hypothesis_id}) {sprint5_top.quality_score:.1f}. "
            "Knowledge base expanded — not execution authorization."
        )
    else:
        summary = (
            f"Sprint 5 original hypotheses still lead quality "
            f"({sprint5_top.quality_score:.1f} vs discovery {discovery_top.quality_score:.1f}), "
            "but discovery-derived tests add breadth and cross-validation."
        )

    return {
        "knowledge_base_improved": improved,
        "summary": summary,
        "discovery_top_id": discovery_top.hypothesis_id,
        "sprint5_top_id": sprint5_top.hypothesis_id,
        "quality_score_delta": round(quality_delta, 2),
        "accuracy_delta": round(accuracy_delta, 4),
        "avg_forward_return_delta": round(return_delta, 4),
        "discovery_top_quality": discovery_top.quality_score,
        "sprint5_top_quality": sprint5_top.quality_score,
    }


def persist_discovery_rankings_report(
    path: Path,
    discovery_rankings: list[HypothesisRankingEntry],
    discovery_groups: list,
    discovery_meta: dict[str, Any],
    sprint5_rankings: list[HypothesisRankingEntry],
    sprint5_meta: dict[str, Any],
    comparison: dict[str, Any],
) -> Path:
    payload = {
        "version": SCHEMA_VERSION,
        "schema": DISCOVERY_RANKINGS_SCHEMA_NAME,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "safety_mode": RESEARCH_SAFETY_BANNER,
        "discovery_ranked_count": len(discovery_rankings),
        "sprint5_ranked_count": len(sprint5_rankings),
        "top_discovery_hypothesis_id": discovery_meta.get("top_hypothesis_id", ""),
        "top_sprint5_hypothesis_id": sprint5_meta.get("top_hypothesis_id", ""),
        "comparison": comparison,
        "discovery_rankings": [_entry_to_dict(e) for e in discovery_rankings],
        "discovery_duplicate_groups": [g.to_dict() for g in discovery_groups],
        "sprint5_reference_rankings": [_entry_to_dict(e) for e in sprint5_rankings],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def format_report(
    discovery_rankings: list[HypothesisRankingEntry],
    sprint5_rankings: list[HypothesisRankingEntry],
    comparison: dict[str, Any],
    report_path: Path,
) -> str:
    lines = [
        "===== TAE PHASE IV SPRINT D4 — DISCOVERY HYPOTHESIS RANKINGS =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Discovery-derived ranking vs Sprint 5 — NOT trading signals.",
        "",
        f"Discovery hypotheses ranked: {len(discovery_rankings)}",
        f"Sprint 5 reference hypotheses ranked: {len(sprint5_rankings)}",
        "",
    ]

    if discovery_rankings:
        top = discovery_rankings[0]
        lines.extend(
            [
                "===== TOP DISCOVERY HYPOTHESIS =====",
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
        lines.append("No discovery-derived hypotheses to rank.")
        lines.append("")

    lines.append("===== DISCOVERY-DERIVED RANKING =====")
    for entry in discovery_rankings:
        lines.extend(
            [
                f"  #{entry.rank} {entry.hypothesis_id}",
                f"    title: {entry.title[:90]}",
                f"    quality_score: {entry.quality_score:.2f}",
                f"    accuracy: {entry.accuracy:.2%}",
                f"    sample_size: {entry.sample_size}",
                f"    avg_forward_return: {entry.avg_forward_return:.4f}%",
                f"    recommendation: {entry.recommendation}",
                "",
            ]
        )

    if sprint5_rankings:
        ref = sprint5_rankings[0]
        lines.extend(
            [
                "===== SPRINT 5 REFERENCE (best original) =====",
                f"  hypothesis_id: {ref.hypothesis_id}",
                f"  title: {ref.title}",
                f"  quality_score: {ref.quality_score:.2f}",
                f"  accuracy: {ref.accuracy:.2%}",
                f"  sample_size: {ref.sample_size}",
                f"  avg_forward_return: {ref.avg_forward_return:.4f}%",
                "",
            ]
        )

    lines.extend(
        [
            "===== COMPARISON =====",
            f"  Knowledge base improved: {comparison.get('knowledge_base_improved', False)}",
            f"  Quality delta (discovery - sprint5): {comparison.get('quality_score_delta', 'n/a')}",
            f"  Accuracy delta: {comparison.get('accuracy_delta', 'n/a')}",
            f"  Return delta: {comparison.get('avg_forward_return_delta', 'n/a')}",
            f"  {comparison.get('summary', '')}",
            "",
            f"Report persisted: {report_path}",
            "",
            "No broker. No execution. No live bot.",
            "",
        ]
    )
    return "\n".join(lines)


def run_discovery_ranking_demo() -> tuple[list, list, dict]:
    print("===== TAE PHASE IV SPRINT D4 — RANK DISCOVERY HYPOTHESES =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Ranks discovery-derived hypotheses vs Sprint 5 originals.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = HypothesisRegistry()
    results_store = ExperimentResultsStore()
    ranker = HypothesisRanker(registry=registry, results_store=results_store)

    print(f"Hypothesis registry: {registry.path} ({registry.count()} hypotheses)")
    print(f"Experiment results: {results_store.path} ({results_store.count()} results)")
    print()

    discovery_rankings, discovery_groups, discovery_meta = ranker.rank(
        source_cycle_prefix=DISCOVERY_PREFIX,
    )

    # Sprint 5 originals: hyp_s5_* IDs, not discovery-sourced
    sprint5_rankings, _, sprint5_meta = ranker.rank(
        exclude_source_cycle_prefix=DISCOVERY_PREFIX,
    )
    # Keep only hyp_s5 entries for reference comparison
    sprint5_rankings = [e for e in sprint5_rankings if e.hypothesis_id.startswith(SPRINT5_HYPOTHESIS_PREFIX)]
    if sprint5_rankings:
        sprint5_meta["top_hypothesis_id"] = sprint5_rankings[0].hypothesis_id

    discovery_top = discovery_rankings[0] if discovery_rankings else None
    sprint5_top = sprint5_rankings[0] if sprint5_rankings else None
    comparison = _build_comparison(discovery_top, sprint5_top)

    report_path = persist_discovery_rankings_report(
        DEFAULT_DISCOVERY_RANKINGS_PATH,
        discovery_rankings,
        discovery_groups,
        discovery_meta,
        sprint5_rankings,
        sprint5_meta,
        comparison,
    )

    print(f"Ranked {len(discovery_rankings)} discovery-derived hypothesis/hypotheses")
    print(f"Persisted: {report_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Rank discovery-derived hypotheses")
    if not life.timeline.has_title("Discovery Hypothesis Rankings"):
        life.record_event(
            "milestone",
            "Discovery Hypothesis Rankings",
            "Phase IV D4 — discovery-derived hypotheses ranked vs Sprint 5.",
            milestone_importance=7,
        )
    if discovery_top:
        life.record_event(
            "research_ranking",
            "Phase IV D4 Discovery Rankings",
            f"Top discovery={discovery_top.hypothesis_id} "
            f"quality={discovery_top.quality_score:.1f}. Research only.",
            add_timeline=False,
        )
    life.persist()

    report = format_report(discovery_rankings, sprint5_rankings, comparison, report_path)
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
    print(f"Saved: {DEFAULT_DISCOVERY_RANKINGS_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return discovery_rankings, sprint5_rankings, comparison


def main() -> None:
    run_discovery_ranking_demo()


if __name__ == "__main__":
    main()
