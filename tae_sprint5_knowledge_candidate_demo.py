"""
TAE Sprint 5.3 — Knowledge Candidate Registry

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Promotes high-quality ranked hypotheses into a knowledge candidate registry.
Does not convert candidates into trading signals or execution paths.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis.knowledge_candidate import (
    DEFAULT_CANDIDATES_PATH,
    KnowledgeCandidatePromoter,
    KnowledgeCandidateRegistry,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_sprint5_knowledge_candidate_summary.txt"


def format_report(result, registry: KnowledgeCandidateRegistry) -> str:
    lines = [
        "===== TAE SPRINT 5.3 — KNOWLEDGE CANDIDATE REGISTRY =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Knowledge candidates are research objects — NOT trading signals.",
        "",
        f"Rankings loaded: {result.rankings_loaded}",
        f"Rankings in file: {result.rankings_count}",
        f"Eligible for promotion: {result.eligible_from_rankings}",
        f"Promoted this run: {result.promoted_count}",
        f"Skipped duplicates: {result.skipped_count}",
        f"Registry total: {registry.count()}",
        "",
    ]

    if result.skipped_duplicates:
        lines.append("===== SKIPPED (already registered) =====")
        for hid in result.skipped_duplicates:
            existing = registry.get_by_source(hid)
            cid = existing.candidate_id if existing else "?"
            lines.append(f"  {hid} → existing candidate {cid}")
        lines.append("")

    if result.promoted:
        lines.append("===== NEWLY PROMOTED CANDIDATES =====")
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
                    f"    robustness_label: {candidate.robustness_label}",
                    f"    status: {candidate.status.value}",
                    f"    evidence_summary: {candidate.evidence_summary}",
                    f"    promotion_reason: {candidate.promotion_reason}",
                    "",
                ]
            )
    elif not result.skipped_duplicates:
        lines.append("No candidates promoted this run.")
        lines.append("")

    lines.extend(
        [
            registry.format_summary(),
            f"Registry persisted: {registry.path}",
            "",
        ]
    )
    return "\n".join(lines)


def run_knowledge_candidate_demo() -> KnowledgeCandidatePromoter:
    print("===== TAE SPRINT 5.3 — KNOWLEDGE CANDIDATE REGISTRY =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Promotes ranked hypotheses to knowledge candidates — not trading.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = KnowledgeCandidateRegistry()
    promoter = KnowledgeCandidatePromoter(candidate_registry=registry)

    print(
        f"Candidate registry: {registry.path} "
        f"({registry.count()} existing, loaded={registry.loaded_at_startup})"
    )
    print(f"Rankings source: {promoter.rankings_store.path}")
    print()

    result = promoter.promote_from_rankings()
    registry_path = registry.persist()

    print(f"Promotion complete — {result.promoted_count} new, {result.skipped_count} skipped")
    print(f"Persisted registry: {registry_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Knowledge candidate registry — research intelligence")
    if not life.timeline.has_title("Knowledge Candidate Registry"):
        life.record_event(
            "milestone",
            "Knowledge Candidate Registry",
            "Sprint 5.3 — high-quality hypotheses promoted to knowledge candidates.",
            milestone_importance=7,
        )
    if result.promoted_count > 0:
        ids = ", ".join(c.candidate_id for c in result.promoted)
        life.record_event(
            "knowledge_candidate",
            "Sprint 5.3 Knowledge Promotion",
            f"Promoted {result.promoted_count} candidate(s): {ids}. Not live signals.",
            add_timeline=False,
        )
    elif result.skipped_count > 0:
        life.record_event(
            "knowledge_candidate",
            "Sprint 5.3 Knowledge Promotion",
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
    run_knowledge_candidate_demo()


if __name__ == "__main__":
    main()
