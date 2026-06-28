"""
Integration Gap Report — Phase IX Sprint IX.1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import (
    CANONICAL_MODULES,
    INTEGRATION_GAPS_KNOWN,
    PRIMARY_RUNNERS,
)
from research_core.ecosystem_audit.dependency_graph import (
    DependencyGraphBuilder,
    DependencyGraphReport,
    DependencyGraphStore,
)
from research_core.ecosystem_audit.master_inventory import (
    MasterInventoryBuilder,
    MasterInventoryReport,
    MasterInventoryStore,
    ModuleRole,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

GAP_JSON = Path("tae_integration_gap_report.json")
GAP_TXT = Path("tae_integration_gap_report.txt")


@dataclass
class ConnectRecommendation:
    priority: str
    action: str
    from_module: str
    to_module: str
    rationale: str

    def to_dict(self) -> dict[str, str]:
        return {
            "priority": self.priority,
            "action": self.action,
            "from_module": self.from_module,
            "to_module": self.to_module,
            "rationale": self.rationale,
        }


@dataclass
class SourceOfTruthConflict:
    domain: str
    modules: list[str]
    canonical: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "modules": list(self.modules),
            "canonical": self.canonical,
        }


@dataclass
class IntegrationGapReport:
    integration_gaps: list[str]
    connect_recommendations: list[ConnectRecommendation]
    competing_runners: list[str]
    multiple_sources_of_truth: list[SourceOfTruthConflict]
    unused_modules: list[str]
    disconnected_modules: list[str]
    unreferenced_modules: list[str]
    canonical_modules: dict[str, str]
    primary_runners: list[str]
    verdict: str = "INTEGRATION_GAPS_DOCUMENTED_CONNECT_EXISTING"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_integration_gap_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "integration_gaps": list(self.integration_gaps),
            "connect_recommendations": [r.to_dict() for r in self.connect_recommendations],
            "competing_runners": list(self.competing_runners),
            "multiple_sources_of_truth": [s.to_dict() for s in self.multiple_sources_of_truth],
            "unused_modules": list(self.unused_modules),
            "disconnected_modules": list(self.disconnected_modules),
            "unreferenced_modules": list(self.unreferenced_modules),
            "canonical_modules": dict(self.canonical_modules),
            "primary_runners": list(self.primary_runners),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE INTEGRATION GAP REPORT — SPRINT IX.1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            "===== PRIMARY RUNNERS (use these — do not add new) =====",
        ]
        for path in self.primary_runners:
            lines.append(f"  {path}")
        lines.extend(["", "===== INTEGRATION GAPS ====="])
        for gap in self.integration_gaps:
            lines.append(f"  • {gap}")
        lines.extend(["", "===== CONNECT EXISTING (do not create new modules) ====="])
        for rec in self.connect_recommendations:
            lines.append(f"  [{rec.priority}] {rec.action}")
            lines.append(f"      {rec.from_module} → {rec.to_module}")
            lines.append(f"      {rec.rationale}")
        lines.extend(["", "===== COMPETING RUNNERS ====="])
        for path in self.competing_runners:
            lines.append(f"  {path}")
        lines.extend(["", "===== MULTIPLE SOURCES OF TRUTH ====="])
        for conflict in self.multiple_sources_of_truth:
            lines.append(f"  {conflict.domain}: canonical={conflict.canonical}")
            for mod in conflict.modules[:5]:
                lines.append(f"    - {mod}")
        lines.extend(["", "===== UNUSED MODULES (candidates to wire or archive) ====="])
        for path in self.unused_modules[:25]:
            lines.append(f"  {path}")
        lines.extend(["", "===== DISCONNECTED MODULES ====="])
        for path in self.disconnected_modules[:25]:
            lines.append(f"  {path}")
        lines.extend(["", "===== UNREFERENCED MODULES (zero incoming imports) ====="])
        for path in self.unreferenced_modules[:25]:
            lines.append(f"  {path}")
        lines.append("")
        return "\n".join(lines)


class IntegrationGapAnalyzer:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def analyze(
        self,
        inventory: MasterInventoryReport,
        graph: DependencyGraphReport,
    ) -> IntegrationGapReport:
        gaps = list(INTEGRATION_GAPS_KNOWN)
        gaps.extend(self._graph_gaps(graph))
        gaps = list(dict.fromkeys(gaps))

        sot_conflicts = [
            SourceOfTruthConflict(
                domain=group.theme,
                modules=group.module_paths,
                canonical=group.canonical_module,
            )
            for group in inventory.duplicate_groups
        ]

        recommendations = self._connect_recommendations(inventory, graph, sot_conflicts)

        return IntegrationGapReport(
            integration_gaps=gaps,
            connect_recommendations=recommendations,
            competing_runners=inventory.competing_runners,
            multiple_sources_of_truth=sot_conflicts,
            unused_modules=inventory.unused_modules,
            disconnected_modules=inventory.disconnected_modules,
            unreferenced_modules=inventory.unreferenced_modules,
            canonical_modules=inventory.canonical_modules,
            primary_runners=list(PRIMARY_RUNNERS),
        )

    def _graph_gaps(self, graph: DependencyGraphReport) -> list[str]:
        gaps: list[str] = []
        canonical = set(CANONICAL_MODULES.values())
        connected_pairs = {(e.source, e.target) for e in graph.canonical_subgraph}
        expected = [
            (
                "research_core/orchestrator/ecosystem_orchestrator.py",
                "research_core/strategy_evolution/daily_runner.py",
            ),
            (
                "research_core/strategy_evolution/daily_runner.py",
                "research_core/evidence_engine/evidence_registry.py",
            ),
            (
                "integration_layer/evidence_gate.py",
                "research_core/evidence_engine/evidence_registry.py",
            ),
        ]
        for src, tgt in expected:
            if src in canonical and tgt in canonical:
                if (src, tgt) not in connected_pairs and (tgt, src) not in connected_pairs:
                    gaps.append(f"No direct import edge between {src} and {tgt}")
        runtime = CANONICAL_MODULES.get("runtime_intelligence")
        if runtime and runtime not in graph.anchor_reachable:
            gaps.append("Runtime workflow_engine not reachable from orchestrator anchors")
        return gaps

    def _connect_recommendations(
        self,
        inventory: MasterInventoryReport,
        graph: DependencyGraphReport,
        sot: list[SourceOfTruthConflict],
    ) -> list[ConnectRecommendation]:
        recs: list[ConnectRecommendation] = []

        for group in inventory.duplicate_groups:
            non_canonical = [
                p for p in group.module_paths if p != group.canonical_module
            ]
            for mod in non_canonical[:3]:
                recs.append(
                    ConnectRecommendation(
                        priority="HIGH",
                        action="CONNECT",
                        from_module=mod,
                        to_module=group.canonical_module,
                        rationale=group.connect_recommendation,
                    )
                )

        recs.append(
            ConnectRecommendation(
                priority="HIGH",
                action="CHAIN",
                from_module="research_core/orchestrator/ecosystem_orchestrator.py",
                to_module="integration_layer/evidence_gate.py",
                rationale="Run integration gate after daily runner in orchestrator chain.",
            )
        )
        recs.append(
            ConnectRecommendation(
                priority="HIGH",
                action="READ",
                from_module="research_core/runtime/workflow_engine.py",
                to_module="research_core/orchestrator/ecosystem_orchestrator.py",
                rationale="Runtime should consume orchestrator JSON; do not duplicate runner logic.",
            )
        )
        recs.append(
            ConnectRecommendation(
                priority="MEDIUM",
                action="REGISTER",
                from_module="research_core/evidence_engine/evidence_gap.py",
                to_module="research_core/evidence_engine/evidence_registry.py",
                rationale="Wire evidence gap as registry reader instead of standalone SOT.",
            )
        )
        recs.append(
            ConnectRecommendation(
                priority="MEDIUM",
                action="DEMOTE",
                from_module="research_core/evolution/strategy_evolution_manager.py",
                to_module="research_core/strategy_evolution/daily_runner.py",
                rationale="Phase V evolution is parallel pipeline — connect or archive.",
            )
        )

        for mod in inventory.unreferenced_modules[:10]:
            if mod.endswith("_report.py"):
                continue
            recs.append(
                ConnectRecommendation(
                    priority="LOW",
                    action="WIRE_OR_ARCHIVE",
                    from_module=mod,
                    to_module=PRIMARY_RUNNERS[0],
                    rationale="Unused module — wire into orchestrator chain or mark archived.",
                )
            )

        return recs


class EcosystemIntegrationAudit:
    """Orchestrates full Sprint IX.1 audit pipeline."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(self) -> tuple[MasterInventoryReport, DependencyGraphReport, IntegrationGapReport]:
        graph_builder = DependencyGraphBuilder(self._root)
        graph = graph_builder.build()
        connected = graph_builder.connected_paths(graph)

        inventory_builder = MasterInventoryBuilder(self._root)
        inventory = inventory_builder.build(
            incoming_counts=graph.incoming_counts,
            outgoing_counts=graph.outgoing_counts,
            connected_paths=connected,
        )

        gap_report = IntegrationGapAnalyzer(self._root).analyze(inventory, graph)
        return inventory, graph, gap_report

    def persist_all(
        self,
        inventory: MasterInventoryReport,
        graph: DependencyGraphReport,
        gap: IntegrationGapReport,
    ) -> dict[str, Path]:
        inv_store = MasterInventoryStore()
        graph_store = DependencyGraphStore()
        gap_store = IntegrationGapStore()
        return {
            "inventory_json": inv_store.persist(inventory),
            "inventory_txt": inv_store.persist_txt(inventory),
            "graph_json": graph_store.persist(graph),
            "graph_txt": graph_store.persist_txt(graph),
            "gap_json": gap_store.persist(gap),
            "gap_txt": gap_store.persist_txt(gap),
        }


class IntegrationGapStore:
    def persist(self, report: IntegrationGapReport) -> Path:
        GAP_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return GAP_JSON

    def persist_txt(self, report: IntegrationGapReport) -> Path:
        GAP_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return GAP_TXT
