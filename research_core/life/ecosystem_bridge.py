"""
Life ↔ Ecosystem Bridge — Sprint 3.6

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Records cognitive/ecosystem cycle outcomes into TAE Life via LifeManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_core.ecosystem.cognitive_layer import CognitiveCycleResult, CognitiveLayer
from research_core.ecosystem.organism import Organism
from research_core.life.life_manager import LifeManager


@dataclass
class BridgeRecordSummary:
    """Audit trail of life events recorded from one ecosystem cycle."""

    cycle_label: str
    events_recorded: int
    event_titles: list[str] = field(default_factory=list)
    cognitive_status: str = ""
    collective_confidence: float = 0.0
    decision_level: str = ""
    journal_written: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_label": self.cycle_label,
            "events_recorded": self.events_recorded,
            "event_titles": self.event_titles,
            "cognitive_status": self.cognitive_status,
            "collective_confidence": self.collective_confidence,
            "decision_level": self.decision_level,
            "journal_written": self.journal_written,
        }


class EcosystemLifeBridge:
    """
    Connects ecosystem/cognitive runs to TAE Life biography.
    Every recorded event flows through LifeManager.record_event().
    """

    def __init__(self, life_manager: LifeManager) -> None:
        self._life = life_manager
        self._bridge_history: list[BridgeRecordSummary] = []

    @property
    def life(self) -> LifeManager:
        return self._life

    def record_cognitive_cycle(
        self,
        result: CognitiveCycleResult,
        cycle_label: str = "cognitive_cycle",
        write_journal: bool = True,
    ) -> BridgeRecordSummary:
        recorded_titles: list[str] = []
        decision = result.decision

        for packet in result.packets:
            event = self._life.record_event(
                "evidence_packet",
                f"Evidence: {packet.organism_name}",
                (
                    f"{packet.observation_summary} | confidence={packet.confidence:.1f} "
                    f"trust={packet.trust:.1f} | {packet.recommended_action}"
                ),
                add_timeline=False,
            )
            recorded_titles.append(event.title)
            if packet.knowledge_reference:
                self._life.record_event(
                    "knowledge_item",
                    f"Knowledge: {packet.knowledge_reference}",
                    packet.explanation[:200],
                    add_timeline=False,
                )
                recorded_titles.append(f"Knowledge: {packet.knowledge_reference}")

        collective_event = self._life.record_event(
            "collective_decision",
            f"Collective Decision: {decision.confidence_level.value}",
            (
                f"Confidence={decision.collective_confidence:.1f} agreement={decision.agreement:.1f} "
                f"disagreement={decision.disagreement:.1f} organisms={decision.organism_participation} "
                f"status={result.cognitive_status}"
            ),
            milestone_importance=7,
        )
        recorded_titles.append(collective_event.title)

        if result.feedback:
            self._life.record_event(
                "self_correction",
                "Feedback Loop Applied",
                f"{len(result.feedback)} organism feedback record(s) delivered.",
                add_timeline=False,
            )
            recorded_titles.append("Feedback Loop Applied")

        for question in result.curiosity_questions:
            q_event = self._life.record_event(
                "curiosity_question",
                "Curiosity Question",
                f"{question.question} (priority={question.priority_score:.0f})",
                add_timeline=False,
            )
            recorded_titles.append(q_event.title)

        graph_nodes = result.graph_stats.get("node_count", 0)
        if graph_nodes > 0:
            graph_event = self._life.record_event(
                "research_experiment",
                "Knowledge Graph Updated",
                f"Nodes={graph_nodes} edges={result.graph_stats.get('edge_count', 0)}",
                add_timeline=False,
            )
            recorded_titles.append(graph_event.title)

        cycle_event = self._life.record_event(
            "research_experiment",
            f"Cognitive Cycle: {cycle_label}",
            (
                f"Packets={len(result.packets)} feedback={len(result.feedback)} "
                f"curiosity={len(result.curiosity_questions)} memory_records="
                f"{result.memory_stats.get('total_records', 0)}"
            ),
        )
        recorded_titles.append(cycle_event.title)

        journal_written = False
        if write_journal:
            open_questions = [q.question for q in result.curiosity_questions[:5]]
            lessons = [
                f"Collective {decision.confidence_level.value} at confidence {decision.collective_confidence:.1f}",
                f"Cognitive status: {result.cognitive_status}",
            ]
            if result.feedback:
                lessons.append(f"Feedback delivered to {len(result.feedback)} organisms")

            self._life.write_journal_entry(
                todays_mission=f"Ecosystem cognitive cycle: {cycle_label}",
                todays_evolution="Life bridge recorded ecosystem run into TAE biography.",
                new_organisms=list(decision.contributing_organisms),
                major_decisions=[decision.confidence_level.value],
                lessons_learned=lessons,
                open_questions=open_questions,
                next_mission="Continue ecosystem cognition and life recording.",
            )
            journal_written = True
            recorded_titles.append("Journal entry written")

        summary = BridgeRecordSummary(
            cycle_label=cycle_label,
            events_recorded=len(recorded_titles),
            event_titles=recorded_titles,
            cognitive_status=result.cognitive_status,
            collective_confidence=decision.collective_confidence,
            decision_level=decision.confidence_level.value,
            journal_written=journal_written,
        )
        self._bridge_history.append(summary)
        return summary

    def run_and_record(
        self,
        cognitive: CognitiveLayer,
        organisms: list[Organism],
        cycle_label: str = "cognitive_cycle",
        write_journal: bool = True,
        persist: bool = False,
    ) -> tuple[CognitiveCycleResult, BridgeRecordSummary]:
        result = cognitive.process_cycle(organisms)
        summary = self.record_cognitive_cycle(result, cycle_label=cycle_label, write_journal=write_journal)
        if persist:
            self._life.persist()
        return result, summary

    def history(self) -> list[BridgeRecordSummary]:
        return list(self._bridge_history)

    def format_summary(self, bridge_summary: BridgeRecordSummary, result: CognitiveCycleResult) -> str:
        lines = [
            "===== LIFE ↔ ECOSYSTEM BRIDGE RECORD =====",
            f"Cycle: {bridge_summary.cycle_label}",
            f"Cognitive Status: {bridge_summary.cognitive_status}",
            f"Collective Confidence: {bridge_summary.collective_confidence:.2f}",
            f"Decision Level: {bridge_summary.decision_level}",
            f"Agreement: {result.decision.agreement:.2f}",
            f"Disagreement: {result.decision.disagreement:.2f}",
            f"Packets: {len(result.packets)}",
            f"Feedback: {len(result.feedback)}",
            f"Curiosity Questions: {len(result.curiosity_questions)}",
            f"Life Events Recorded: {bridge_summary.events_recorded}",
            f"Journal Written: {bridge_summary.journal_written}",
            "",
            "Recorded event titles:",
        ]
        for title in bridge_summary.event_titles:
            lines.append(f"  • {title}")
        lines.extend(
            [
                "",
                f"TAE Age: {self._life.age.age_one_line()}",
                f"TAE Generation: {self._life.generation.current_generation()}",
                f"Milestones: {self._life.milestones.count()}",
                f"Achievements Unlocked: {self._life.achievements.count_unlocked()}",
                f"Timeline Events: {self._life.timeline.count()}",
                "",
            ]
        )
        return "\n".join(lines)
