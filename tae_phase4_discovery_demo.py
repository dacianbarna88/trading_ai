"""
TAE Phase IV Sprint D1 — Discovery Engine

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Discovers unexpected statistical relationships worth future research.
Not BUY/SELL signals, not hypotheses, not execution paths.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery import (
    DEFAULT_REGISTRY_PATH,
    ResearchDiscoveryEngine,
    DiscoveryRegistry,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_phase4_discovery_summary.txt"


def format_report(result, registry: DiscoveryRegistry) -> str:
    lines = [
        "===== TAE PHASE IV SPRINT D1 — DISCOVERY ENGINE =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Discoveries are research opportunities — NOT trade signals.",
        "",
        "Sources loaded:",
    ]
    for name, ok in sorted(result.sources_loaded.items()):
        lines.append(f"  {name}: {'yes' if ok else 'no'}")
    lines.extend(
        [
            "",
            f"Discovery candidates evaluated: {result.candidates_evaluated}",
            f"New discoveries this run: {result.new_count}",
            f"Skipped duplicates: {result.skipped_count}",
            f"Registry total: {registry.count()}",
            "",
        ]
    )

    if result.skipped_duplicates:
        lines.append("===== SKIPPED DUPLICATES =====")
        for title in result.skipped_duplicates:
            lines.append(f"  (already registered) {title}")
        lines.append("")

    if result.discovered:
        lines.append("===== NEW DISCOVERIES =====")
        for discovery in result.discovered:
            lines.extend(
                [
                    f"  discovery_id: {discovery.discovery_id}",
                    f"    title: {discovery.title}",
                    f"    category: {discovery.category}",
                    f"    description: {discovery.description}",
                    f"    evidence: {discovery.evidence}",
                    f"    confidence: {discovery.confidence:.1f}",
                    f"    novelty_score: {discovery.novelty_score:.1f}",
                    f"    source_experiments: {', '.join(discovery.source_experiments)}",
                    f"    suggested_next_step: {discovery.suggested_next_step}",
                    f"    status: {discovery.status.value}",
                    "",
                ]
            )
    else:
        lines.append("No new discoveries this run.")
        lines.append("")

    lines.extend(
        [
            registry.format_summary(),
            f"Registry persisted: {registry.path}",
            "",
            "No broker. No execution. No live bot paths.",
            "",
        ]
    )
    return "\n".join(lines)


def run_discovery_demo() -> ResearchDiscoveryEngine:
    print("===== TAE PHASE IV SPRINT D1 — DISCOVERY ENGINE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Unexpected statistical relationships — not BUY/SELL or hypotheses.")
    print("No broker. No live bot. No order execution.")
    print()

    registry = DiscoveryRegistry()
    engine = ResearchDiscoveryEngine(registry=registry)

    print(
        f"Discovery registry: {registry.path} "
        f"({registry.count()} existing, loaded={registry.loaded_at_startup})"
    )
    print()

    result = engine.run()
    registry_path = registry.persist()

    print(f"Run complete: {result.new_count} new, {result.skipped_count} skipped")
    print(f"Persisted: {registry_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Discovery engine — research opportunity detection")
    if not life.timeline.has_title("Discovery Engine"):
        life.record_event(
            "milestone",
            "Discovery Engine",
            "Phase IV D1 — meta-analysis discovers research opportunities, not signals.",
            milestone_importance=8,
        )
    if result.new_count > 0:
        life.record_event(
            "research_discovery",
            "Phase IV D1 Discovery Run",
            f"Found {result.new_count} new research discovery(s). Not trading signals.",
            add_timeline=False,
        )
    elif result.skipped_count > 0:
        life.record_event(
            "research_discovery",
            "Phase IV D1 Discovery Run",
            f"No new discoveries — {result.skipped_count} duplicate(s) skipped.",
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
    print(f"Saved: {DEFAULT_REGISTRY_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return engine


def main() -> None:
    run_discovery_demo()


if __name__ == "__main__":
    main()
