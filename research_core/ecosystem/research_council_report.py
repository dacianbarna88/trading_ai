"""
Research Council Report — Sprint 4.5

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Readable council-style narrative explaining collective research decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.collective_intelligence import OrganismContribution

if TYPE_CHECKING:
    from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
    from research_core.ecosystem.organism_memory import OrganismMemoryStore
    from research_core.life.life_manager import LifeManager

DEFAULT_REPORT_PATH = Path("tae_research_council_report.txt")


@dataclass
class CouncilOrganismSummary:
    name: str
    confidence: float
    trust: float
    packet_trust: float
    weight: float
    weighted_contribution: float
    observation: str = ""

    @classmethod
    def from_contribution(
        cls,
        contrib: OrganismContribution,
        observation: str = "",
    ) -> CouncilOrganismSummary:
        return cls(
            name=contrib.organism_name,
            confidence=contrib.confidence,
            trust=contrib.trust_used,
            packet_trust=contrib.packet_trust,
            weight=contrib.weight,
            weighted_contribution=contrib.weighted_contribution,
            observation=observation[:120],
        )


class ResearchCouncilReporter:
    """Builds human-readable Research Council reports from cognitive cycle outcomes."""

    def build(
        self,
        result: CognitiveCycleResult,
        memory_store: OrganismMemoryStore | None = None,
        life: LifeManager | None = None,
        cycle_label: str = "council_session",
    ) -> str:
        decision = result.decision
        summaries = {
            name: summary
            for name, summary in zip(decision.contributing_organisms, decision.packet_summaries)
        }

        organisms: list[CouncilOrganismSummary] = []
        for contrib in decision.organism_contributions:
            organisms.append(
                CouncilOrganismSummary.from_contribution(
                    contrib,
                    summaries.get(contrib.organism_name, ""),
                )
            )

        if not organisms and result.packets:
            for packet in result.packets:
                organisms.append(
                    CouncilOrganismSummary(
                        name=packet.organism_name,
                        confidence=packet.confidence,
                        trust=packet.trust,
                        packet_trust=packet.trust,
                        weight=packet.trust / 100.0,
                        weighted_contribution=packet.confidence * packet.trust / 100.0,
                        observation=packet.observation_summary[:120],
                    )
                )

        strongest = self._pick_strongest(organisms)
        weakest = self._pick_weakest(organisms)
        narrative = self._narrative(decision, organisms, strongest, weakest)

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║           TAE RESEARCH COUNCIL — SESSION REPORT              ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            RESEARCH_SAFETY_BANNER,
            "ANALYSIS_ONLY — council deliberation, not trade execution.",
            "",
            f"Session: {cycle_label}",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Cognitive Status: {result.cognitive_status}",
            "",
            "──────────────────────────────────────────────────────────────",
            "COUNCIL ROSTER",
            "──────────────────────────────────────────────────────────────",
            f"Active organisms: {len(organisms)}",
        ]
        for org in organisms:
            lines.append(f"  • {org.name}")
        lines.extend(
            [
                "",
                "──────────────────────────────────────────────────────────────",
                "ORGANISM POSITIONS (confidence · trust · weighted contribution)",
                "──────────────────────────────────────────────────────────────",
            ]
        )
        for org in sorted(organisms, key=lambda o: o.weighted_contribution, reverse=True):
            lines.extend(
                [
                    f"  {org.name}",
                    f"    confidence: {org.confidence:.2f}",
                    f"    trust (weighting): {org.trust:.2f}  (packet trust: {org.packet_trust:.2f})",
                    f"    weight: {org.weight:.4f}",
                    f"    weighted contribution: {org.weighted_contribution:.2f}",
                ]
            )
            if org.observation:
                lines.append(f"    observation: {org.observation}")
            lines.append("")

        lines.extend(
            [
                "──────────────────────────────────────────────────────────────",
                "COLLECTIVE VERDICT",
                "──────────────────────────────────────────────────────────────",
                f"  Decision level: {decision.confidence_level.value}",
                f"  Unweighted confidence: {decision.unweighted_confidence:.2f}",
                f"  Trust-weighted confidence: {decision.trust_weighted_confidence:.2f}",
                f"  Collective confidence (reported): {decision.collective_confidence:.2f}",
                f"  Agreement: {decision.agreement:.2f}%",
                f"  Disagreement: {decision.disagreement:.2f}%",
                f"  Trust weighting applied: {decision.trust_weighting_applied}",
                "",
                "──────────────────────────────────────────────────────────────",
                "COUNCIL ASSESSMENT",
                "──────────────────────────────────────────────────────────────",
                f"  Strongest organism: {strongest.name} "
                f"(weighted contribution {strongest.weighted_contribution:.2f}, "
                f"confidence {strongest.confidence:.2f})",
                f"  Weakest organism: {weakest.name} "
                f"(weighted contribution {weakest.weighted_contribution:.2f}, "
                f"confidence {weakest.confidence:.2f})",
                "",
                "──────────────────────────────────────────────────────────────",
                "COUNCIL EXPLANATION",
                "──────────────────────────────────────────────────────────────",
                narrative,
                "",
            ]
        )

        if memory_store is not None:
            lines.extend(self._memory_status(memory_store))
        if life is not None:
            lines.extend(self._life_status(life))

        lines.extend(
            [
                "──────────────────────────────────────────────────────────────",
                "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
                "The council advises research — it does not execute trades.",
                "──────────────────────────────────────────────────────────────",
                "",
            ]
        )
        return "\n".join(lines)

    def write(
        self,
        content: str,
        path: Path | None = None,
    ) -> Path:
        output = path or DEFAULT_REPORT_PATH
        output.write_text(content, encoding="utf-8")
        return output

    def _pick_strongest(self, organisms: list[CouncilOrganismSummary]) -> CouncilOrganismSummary:
        if not organisms:
            return CouncilOrganismSummary("none", 0, 0, 0, 0, 0)
        return max(organisms, key=lambda o: o.weighted_contribution)

    def _pick_weakest(self, organisms: list[CouncilOrganismSummary]) -> CouncilOrganismSummary:
        if not organisms:
            return CouncilOrganismSummary("none", 0, 0, 0, 0, 0)
        return min(organisms, key=lambda o: o.weighted_contribution)

    def _narrative(
        self,
        decision,
        organisms: list[CouncilOrganismSummary],
        strongest: CouncilOrganismSummary,
        weakest: CouncilOrganismSummary,
    ) -> str:
        if not organisms:
            return (
                "The Research Council could not deliberate — no organism evidence was presented. "
                "Insufficient evidence for a collective research view."
            )

        count = len(organisms)
        level = decision.confidence_level.value.replace("_", " ").lower()
        weight_note = (
            "Calibrated organism memory trust shaped each vote."
            if decision.trust_weighting_applied
            else "Packet-level trust shaped each vote."
        )

        parts = [
            f"The Research Council convened {count} research organisms for deliberation.",
            weight_note,
            (
                f"Trust-weighted confidence reached {decision.trust_weighted_confidence:.1f} "
                f"({level}), while the unweighted mean was {decision.unweighted_confidence:.1f}."
            ),
            (
                f"Council agreement registered at {decision.agreement:.1f}% "
                f"with {decision.disagreement:.1f}% disagreement among organism confidences."
            ),
            (
                f"{strongest.name} carried the strongest weighted contribution "
                f"({strongest.weighted_contribution:.1f}) at confidence {strongest.confidence:.1f}."
            ),
            (
                f"{weakest.name} contributed the least weighted influence "
                f"({weakest.weighted_contribution:.1f}) at confidence {weakest.confidence:.1f}."
            ),
        ]

        if decision.agreement >= 85:
            parts.append("The council reached broad alignment — organisms largely agreed on signal strength.")
        elif decision.disagreement >= 40:
            parts.append(
                "Material disagreement remains — the council recommends caution and further research."
            )
        else:
            parts.append("Moderate alignment — the council supports continued observation with selective weighting.")

        parts.append("This verdict is for research prioritization only — not live execution.")
        return " ".join(parts)

    def _memory_status(self, memory_store: OrganismMemoryStore) -> list[str]:
        lines = [
            "──────────────────────────────────────────────────────────────",
            "ORGANISM MEMORY PERSISTENCE",
            "──────────────────────────────────────────────────────────────",
            f"  Path: {memory_store.path}",
            f"  Loaded at startup: {memory_store.loaded_at_startup}",
            f"  Organisms tracked: {len(memory_store.all_memories())}",
        ]
        for memory in sorted(memory_store.all_memories(), key=lambda m: m.organism_name):
            lines.append(
                f"    {memory.organism_name}: cycles={memory.cycles_seen} "
                f"trust_score={memory.trust_score:.2f} "
                f"avg_conf={memory.avg_confidence:.2f}"
            )
        lines.append("")
        return lines

    def _life_status(self, life: LifeManager) -> list[str]:
        lines = [
            "──────────────────────────────────────────────────────────────",
            "TAE LIFE PERSISTENCE",
            "──────────────────────────────────────────────────────────────",
            f"  Path: {life.state_path}",
            f"  Loaded from storage: {life.loaded_from_storage}",
            f"  Generation: {life.generation.current_generation()}",
            f"  Current mission: {life.current_mission}",
            f"  Journal entries: {life.journal.count()}",
            f"  Timeline events: {life.timeline.count()}",
            f"  Milestones: {life.milestones.count()}",
            "",
        ]
        return lines
