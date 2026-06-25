"""
TAE Phase IV Sprint D2 — Discovery-to-Hypothesis Bridge

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Converts NEW discoveries into UNTESTED hypotheses — does not run experiments.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.discovery_registry import DEFAULT_REGISTRY_PATH as DISCOVERIES_PATH
from research_core.discovery.discovery_to_hypothesis import DiscoveryToHypothesisBridge
from research_core.hypothesis.hypothesis_registry import DEFAULT_REGISTRY_PATH as HYPOTHESIS_PATH
from research_core.life import LifeManager

SUMMARY_TXT = "tae_phase4_discovery_to_hypothesis_summary.txt"


def format_report(result, bridge: DiscoveryToHypothesisBridge) -> str:
    discovery_reg = bridge.discovery_registry
    hypothesis_reg = bridge.hypothesis_registry

    lines = [
        "===== TAE PHASE IV SPRINT D2 — DISCOVERY-TO-HYPOTHESIS BRIDGE =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "Converts discoveries into UNTESTED hypotheses — not trade signals.",
        "",
        f"Discoveries loaded: {result.discoveries_loaded}",
        f"Eligible discoveries (NEW, conf>=60, novelty>=50): {result.eligible_count}",
        f"Hypotheses created this run: {result.created_count}",
        f"Skipped duplicates: {result.skipped_duplicate_count}",
        f"Discoveries status updated: {len(result.discoveries_updated)}",
        f"Hypothesis registry total: {hypothesis_reg.count()}",
        "",
    ]

    if result.skipped_ineligible:
        lines.append("===== INELIGIBLE / SKIPPED DISCOVERIES =====")
        for item in result.skipped_ineligible:
            lines.append(f"  {item}")
        lines.append("")

    if result.skipped_duplicates:
        lines.append("===== DUPLICATE SKIPS (hypothesis already exists) =====")
        for did in result.skipped_duplicates:
            lines.append(f"  {did}")
        lines.append("")

    if result.discoveries_updated:
        lines.append("===== DISCOVERY STATUS UPDATES =====")
        for did in result.discoveries_updated:
            disc = discovery_reg.get(did)
            status = disc.status.value if disc else "?"
            lines.append(f"  {did} → {status}")
        lines.append("")

    if result.hypotheses_created:
        lines.append("===== NEW HYPOTHESES CREATED =====")
        for hyp in result.hypotheses_created:
            lines.extend(
                [
                    f"  {hyp.hypothesis_id}: {hyp.title}",
                    f"    source_cycle (discovery_id): {hyp.source_cycle}",
                    f"    source_organisms: {', '.join(hyp.source_organisms) or '(none)'}",
                    f"    confidence: {hyp.confidence:.1f}",
                    f"    horizon: {hyp.horizon}",
                    f"    status: {hyp.status.value}",
                    f"    conditions: {list(hyp.conditions.keys())}",
                    f"    prediction: {hyp.prediction[:120]}...",
                    "",
                ]
            )
    else:
        lines.append("No new hypotheses created this run.")
        lines.append("")

    lines.extend(
        [
            discovery_reg.format_summary(),
            hypothesis_reg.format_summary(),
            f"Discoveries persisted: {discovery_reg.path}",
            f"Hypothesis registry persisted: {hypothesis_reg.path}",
            "",
            "Experiments not run — bridge only. No broker. No execution.",
            "",
        ]
    )
    return "\n".join(lines)


def run_bridge_demo() -> DiscoveryToHypothesisBridge:
    print("===== TAE PHASE IV SPRINT D2 — DISCOVERY-TO-HYPOTHESIS BRIDGE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Converts discoveries → UNTESTED hypotheses — not trading.")
    print("No broker. No live bot. No order execution.")
    print()

    bridge = DiscoveryToHypothesisBridge()
    print(f"Discoveries: {DISCOVERIES_PATH}")
    print(f"Hypothesis registry: {HYPOTHESIS_PATH}")
    print()

    result = bridge.convert()

    discovery_path = bridge.discovery_registry.persist()
    hypothesis_path = bridge.hypothesis_registry.persist()

    print(f"Bridge complete: {result.created_count} created, {result.skipped_duplicate_count} skipped")
    print(f"Persisted discoveries: {discovery_path}")
    print(f"Persisted hypotheses: {hypothesis_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Discovery-to-hypothesis bridge — research pipeline")
    if not life.timeline.has_title("Discovery-to-Hypothesis Bridge"):
        life.record_event(
            "milestone",
            "Discovery-to-Hypothesis Bridge",
            "Phase IV D2 — discoveries converted to UNTESTED hypotheses.",
            milestone_importance=7,
        )
    if result.created_count > 0:
        ids = ", ".join(h.hypothesis_id for h in result.hypotheses_created)
        life.record_event(
            "hypothesis_bridge",
            "Phase IV D2 Discovery Bridge",
            f"Created {result.created_count} hypothesis(es): {ids}. Not experiments yet.",
            add_timeline=False,
        )
    life.persist()

    report = format_report(result, bridge)
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

    return bridge


def main() -> None:
    run_bridge_demo()


if __name__ == "__main__":
    main()
