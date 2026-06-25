"""
TAE Phase IV Sprint D5 — Promote Discovery Knowledge Candidates

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Promotes discovery-derived hypotheses that outperform prior knowledge.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis.hypothesis_ranking import DEFAULT_DISCOVERY_RANKINGS_PATH
from research_core.hypothesis.knowledge_candidate import (
    DEFAULT_CANDIDATES_PATH,
    KnowledgeCandidatePromoter,
    KnowledgeCandidateRegistry,
)

SUMMARY_TXT = "tae_phase4_promote_discovery_knowledge_summary.txt"


def format_report(result, registry: KnowledgeCandidateRegistry) -> str:
    lines = [
        "===== TAE PHASE IV SPRINT D5 — DISCOVERY KNOWLEDGE PROMOTION =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Discovery-derived knowledge candidates — NOT trading signals.",
        "",
        f"Discovery rankings loaded: {result.rankings_loaded}",
        f"Discovery rankings in file: {result.rankings_count}",
        f"Eligible for promotion: {result.eligible_from_rankings}",
        f"Candidates created this run: {result.promoted_count}",
        f"Skipped duplicates: {result.skipped_count}",
        f"Total knowledge candidates: {registry.count()}",
        f"Knowledge base improved: {result.knowledge_base_improved}",
        "",
    ]

    if result.skipped_ineligible:
        lines.append("===== INELIGIBLE (below thresholds) =====")
        for item in result.skipped_ineligible:
            lines.append(f"  {item}")
        lines.append("")

    if result.skipped_duplicates:
        lines.append("===== SKIPPED DUPLICATES =====")
        for hid in result.skipped_duplicates:
            existing = registry.get_by_source(hid)
            cid = existing.candidate_id if existing else "?"
            lines.append(f"  {hid} → existing {cid}")
        lines.append("")

    if result.promoted:
        lines.append("===== NEW DISCOVERY KNOWLEDGE CANDIDATES =====")
        for candidate in result.promoted:
            lines.extend(
                [
                    f"  candidate_id: {candidate.candidate_id}",
                    f"    source_hypothesis_id: {candidate.source_hypothesis_id}",
                    f"    title: {candidate.title}",
                    f"    quality_score: {candidate.quality_score:.2f}",
                    f"    accuracy: {candidate.accuracy:.2%}",
                    f"    sample_size: {candidate.sample_size}",
                    f"    avg_forward_return: {candidate.avg_forward_return:.4f}%",
                    f"    evidence_summary: {candidate.evidence_summary[:120]}...",
                    f"    promotion_reason: {candidate.promotion_reason[:120]}...",
                    "",
                ]
            )
    else:
        lines.append("No new discovery knowledge candidates this run.")
        lines.append("")

    if result.comparison_summary:
        lines.append(f"Comparison note: {result.comparison_summary}")
        lines.append("")

    lines.extend(
        [
            registry.format_summary(),
            f"Rankings source: {DEFAULT_DISCOVERY_RANKINGS_PATH}",
            f"Candidates persisted: {registry.path}",
            "",
            "No broker. No execution. No live bot.",
            "",
        ]
    )
    return "\n".join(lines)


def run_promotion_demo() -> KnowledgeCandidatePromoter:
    print("===== TAE PHASE IV SPRINT D5 — PROMOTE DISCOVERY KNOWLEDGE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Promotes discovery-derived hypotheses to knowledge candidates.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = KnowledgeCandidateRegistry()
    promoter = KnowledgeCandidatePromoter(candidate_registry=registry)

    print(f"Discovery rankings: {DEFAULT_DISCOVERY_RANKINGS_PATH}")
    print(
        f"Knowledge candidates: {DEFAULT_CANDIDATES_PATH} "
        f"({registry.count()} existing, loaded={registry.loaded_at_startup})"
    )
    print()

    result = promoter.promote_from_discovery_rankings(
        min_quality_score=65.0,
        min_sample_size=500,
        min_accuracy=0.60,
    )
    candidates_path = registry.persist()

    print(
        f"Promotion complete: {result.promoted_count} created, "
        f"{result.skipped_count} skipped duplicates"
    )
    print(f"Knowledge base improved: {result.knowledge_base_improved}")
    print(f"Persisted: {candidates_path}")
    print()

    from research_core.life import LifeManager

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Discovery knowledge promotion — research intelligence")
    if not life.timeline.has_title("Discovery Knowledge Promotion"):
        life.record_event(
            "milestone",
            "Discovery Knowledge Promotion",
            "Phase IV D5 — discovery-derived hypotheses promoted to knowledge candidates.",
            milestone_importance=7,
        )
    if result.promoted_count > 0:
        ids = ", ".join(c.candidate_id for c in result.promoted)
        life.record_event(
            "knowledge_candidate",
            "Phase IV D5 Discovery Knowledge Promotion",
            f"Promoted {result.promoted_count} discovery candidate(s): {ids}. Not live signals.",
            add_timeline=False,
        )
    elif result.skipped_count > 0:
        life.record_event(
            "knowledge_candidate",
            "Phase IV D5 Discovery Knowledge Promotion",
            f"No new promotions — {result.skipped_count} duplicate(s) skipped.",
            add_timeline=False,
        )
    life.persist()

    report = format_report(result, registry)
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
    print(f"Saved: {DEFAULT_CANDIDATES_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return promoter


def main() -> None:
    run_promotion_demo()


if __name__ == "__main__":
    main()
