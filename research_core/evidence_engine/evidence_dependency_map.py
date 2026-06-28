"""
Evidence Dependency Map — Phase IX Sprint IX.2B

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.evidence_engine.evidence_registry import (
    CANONICAL_REGISTRY_MODULE,
    CANONICAL_REPORT_PATH,
)
from research_core.evidence_engine.evidence_report import SCHEMA_NAME as CANONICAL_SCHEMA
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

MAP_JSON = Path("tae_evidence_dependency_map.json")
MAP_TXT = Path("tae_evidence_dependency_map.txt")

CANONICAL_REGISTRY_PATH = CANONICAL_REGISTRY_MODULE

INTEGRATION_TARGETS = [
    "research_core/evidence_gap/evidence_gap.py",
    "research_core/evidence_gap/evidence_gap_report.py",
    "research_core/evidence_history/evidence_accumulator.py",
    "research_core/evidence_history/evidence_record.py",
    "research_core/evidence_engine/evidence_report.py",
]

INTEGRATION_GATE_PATH = "integration_layer/evidence_gate.py"

PHASE_VII_SOURCE_REPORTS = [
    "tae_closed_freeze_statistical_audit.json",
    "tae_closed_freeze_root_cause.json",
    "tae_score_decomposition_anomaly.json",
    "tae_independent_double_entry_verification.json",
    "tae_exit_counterfactual.json",
    "tae_profit_attribution.json",
    "tae_continuous_strategy_simulation_lab.json",
]

OPTIONAL_PHASE_REPORTS = [
    "tae_confidence_recalibration.json",
    "tae_evidence_gap_report.json",
    "tae_evidence_history.json",
]

KERNEL_CLASS_NAME = "EvidenceRegistry"
FACADE_CLASS_NAME = "EvidenceEngine"

EXCLUDE_FROM_KERNEL_SCAN = {
    "research_core/evidence_engine/evidence_dependency_map.py",
    "research_core/evidence_engine/evidence_integration_report.py",
}

EVIDENCE_MODULE_PATTERNS = [
    r"research_core/evidence_engine/",
    r"research_core/evidence_gap/",
    r"research_core/evidence_history/",
    r"integration_layer/evidence_gate",
]


class ModuleRole(str, Enum):
    CANONICAL_REGISTRY = "CANONICAL_REGISTRY"
    REGISTRY_FACADE = "REGISTRY_FACADE"
    REPORT_SERIALIZER = "REPORT_SERIALIZER"
    VIEW_READER = "VIEW_READER"
    FEEDER_READER = "FEEDER_READER"
    RECORD_MODEL = "RECORD_MODEL"
    INTEGRATION_GATE = "INTEGRATION_GATE"
    INTEGRATION_META = "INTEGRATION_META"
    EXTERNAL_CONSUMER = "EXTERNAL_CONSUMER"


@dataclass
class EvidenceModuleNode:
    module_path: str
    role: ModuleRole
    reads_canonical_json: bool
    imports_registry: bool
    has_competing_registry: bool
    tae_outputs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "role": self.role.value,
            "reads_canonical_json": self.reads_canonical_json,
            "imports_registry": self.imports_registry,
            "has_competing_registry": self.has_competing_registry,
            "tae_outputs": list(self.tae_outputs),
        }


@dataclass
class EvidenceDependencyMap:
    canonical_registry: str
    canonical_json: str
    canonical_schema: str
    registry_count: int
    integration_targets: list[str]
    nodes: list[EvidenceModuleNode]
    edges: list[dict[str, str]]
    phase_vii_sources: list[str]
    optional_sources: list[str]
    integration_gate_reads_canonical: bool
    bypass_risks: list[str]
    verdict: str = "EVIDENCE_DEPENDENCY_MAP_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_evidence_dependency_map",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_registry": self.canonical_registry,
            "canonical_json": self.canonical_json,
            "canonical_schema": self.canonical_schema,
            "registry_count": self.registry_count,
            "integration_targets": list(self.integration_targets),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": list(self.edges),
            "phase_vii_sources": list(self.phase_vii_sources),
            "optional_sources": list(self.optional_sources),
            "integration_gate_reads_canonical": self.integration_gate_reads_canonical,
            "bypass_risks": list(self.bypass_risks),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE EVIDENCE DEPENDENCY MAP — SPRINT IX.2B =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical registry: {self.canonical_registry}",
            f"Canonical JSON:       {self.canonical_json}",
            f"Registry count:       {self.registry_count} (must be 1)",
            "",
            "===== INTEGRATION TARGETS =====",
        ]
        for target in self.integration_targets:
            node = next((n for n in self.nodes if n.module_path == target), None)
            if node:
                lines.append(
                    f"  {target} [{node.role.value}] "
                    f"reads_canonical={node.reads_canonical_json}"
                )
        lines.extend(["", "===== INTEGRATION GATE ====="])
        lines.append(f"  Reads canonical JSON: {self.integration_gate_reads_canonical}")
        lines.extend(["", "===== BYPASS RISKS ====="])
        for risk in self.bypass_risks:
            lines.append(f"  • {risk}")
        lines.append("")
        return "\n".join(lines)


class EvidenceDependencyMapBuilder:
    ROOT = Path(".")

    ROLE_BY_PATH: dict[str, ModuleRole] = {
        CANONICAL_REGISTRY_PATH: ModuleRole.CANONICAL_REGISTRY,
        "research_core/evidence_engine/evidence_report.py": ModuleRole.REPORT_SERIALIZER,
        "research_core/evidence_gap/evidence_gap.py": ModuleRole.VIEW_READER,
        "research_core/evidence_gap/evidence_gap_report.py": ModuleRole.VIEW_READER,
        "research_core/evidence_history/evidence_accumulator.py": ModuleRole.FEEDER_READER,
        "research_core/evidence_history/evidence_record.py": ModuleRole.RECORD_MODEL,
        INTEGRATION_GATE_PATH: ModuleRole.INTEGRATION_GATE,
        "research_core/evidence_engine/evidence_dependency_map.py": ModuleRole.INTEGRATION_META,
        "research_core/evidence_engine/evidence_integration_report.py": ModuleRole.INTEGRATION_META,
    }

    def build(self) -> EvidenceDependencyMap:
        paths = self._discover_modules()
        path_to_text = {
            p: (self.ROOT / p).read_text(encoding="utf-8", errors="replace") for p in paths
        }
        edges = self._build_edges(paths, path_to_text)
        registry_count = sum(
            1
            for path in paths
            if self._defines_registry_class(path_to_text[path], path)
        )
        nodes: list[EvidenceModuleNode] = []
        bypass_risks: list[str] = []

        for path in sorted(paths):
            text = path_to_text[path]
            role = self.ROLE_BY_PATH.get(path, self._infer_role(path, text))
            reads = self._reads_canonical(text)
            imports_reg = self._imports_registry(text)
            competing = self._defines_registry_class(text, path)
            if path == "research_core/evidence_gap/evidence_gap.py" and not reads:
                bypass_risks.append("evidence_gap not reading canonical registry JSON")
            if path == "research_core/evidence_history/evidence_accumulator.py" and not reads:
                bypass_risks.append("evidence_accumulator not reading canonical registry JSON")
            nodes.append(
                EvidenceModuleNode(
                    module_path=path,
                    role=role,
                    reads_canonical_json=reads,
                    imports_registry=imports_reg,
                    has_competing_registry=competing,
                    tae_outputs=sorted(self._tae_outputs(text)),
                )
            )

        gate_text = (self.ROOT / INTEGRATION_GATE_PATH).read_text(encoding="utf-8", errors="replace")
        gate_reads = "tae_evidence_engine_report.json" in gate_text

        if not gate_reads:
            bypass_risks.append("Integration gate not reading Evidence Engine report")

        return EvidenceDependencyMap(
            canonical_registry=CANONICAL_REGISTRY_PATH,
            canonical_json=str(CANONICAL_REPORT_PATH),
            canonical_schema=CANONICAL_SCHEMA,
            registry_count=registry_count,
            integration_targets=list(INTEGRATION_TARGETS),
            nodes=nodes,
            edges=edges,
            phase_vii_sources=[p for p in PHASE_VII_SOURCE_REPORTS if (self.ROOT / p).is_file()],
            optional_sources=[p for p in OPTIONAL_PHASE_REPORTS if (self.ROOT / p).is_file()],
            integration_gate_reads_canonical=gate_reads,
            bypass_risks=bypass_risks,
        )

    def _discover_modules(self) -> list[str]:
        found: set[str] = set(INTEGRATION_TARGETS)
        found.add(CANONICAL_REGISTRY_PATH)
        found.add("research_core/evidence_engine/__init__.py")
        found.add(INTEGRATION_GATE_PATH)
        for py in self.ROOT.rglob("*.py"):
            rel = py.relative_to(self.ROOT).as_posix()
            if "__pycache__" in rel:
                continue
            if any(re.search(pat, rel) for pat in EVIDENCE_MODULE_PATTERNS):
                found.add(rel)
        return sorted(found)

    def _build_edges(
        self,
        paths: list[str],
        path_to_text: dict[str, str],
    ) -> list[dict[str, str]]:
        path_set = set(paths)
        index: dict[str, str] = {}
        for path in paths:
            parts = path.replace(".py", "").split("/")
            index[".".join(parts)] = path
            if parts[-1] != "__init__":
                index[parts[-1]] = path

        edges: list[dict[str, str]] = []
        for source, text in path_to_text.items():
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                mod: str | None = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                        target = self._resolve(mod, index, path_set)
                        if target:
                            edges.append({"source": source, "target": target, "kind": "import"})
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                    target = self._resolve(mod, index, path_set)
                    if target:
                        edges.append({"source": source, "target": target, "kind": "from"})
        return edges

    @staticmethod
    def _resolve(module: str, index: dict[str, str], path_set: set[str]) -> str | None:
        for cand in (module, module.split(".")[0]):
            if cand in index and index[cand] in path_set:
                return index[cand]
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            sub = ".".join(parts[:i])
            if sub in index and index[sub] in path_set:
                return index[sub]
        return None

    @staticmethod
    def _reads_canonical(text: str) -> bool:
        return (
            "load_canonical_evidence_report" in text
            or "tae_evidence_engine_report.json" in text
            or "CANONICAL_REPORT_PATH" in text
        )

    @staticmethod
    def _imports_registry(text: str) -> bool:
        return (
            "from research_core.evidence_engine.evidence_registry import" in text
            or "from research_core.evidence_engine import" in text
        )

    @staticmethod
    def _defines_registry_class(text: str, path: str) -> bool:
        if path in EXCLUDE_FROM_KERNEL_SCAN:
            return False
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == KERNEL_CLASS_NAME:
                return True
        return False

    @staticmethod
    def _infer_role(path: str, text: str) -> ModuleRole:
        if "class EvidenceEngine" in text and path.endswith("evidence_registry.py"):
            return ModuleRole.REGISTRY_FACADE
        if path.startswith("integration_layer/"):
            return ModuleRole.INTEGRATION_GATE
        return ModuleRole.EXTERNAL_CONSUMER

    @staticmethod
    def _tae_outputs(text: str) -> set[str]:
        outputs: set[str] = set()
        for match in re.finditer(r'Path\(\s*["\'](tae_[^"\']+)["\']\s*\)', text):
            outputs.add(match.group(1))
        return outputs


class EvidenceDependencyMapStore:
    def persist(self, report: EvidenceDependencyMap) -> Path:
        MAP_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return MAP_JSON

    def persist_txt(self, report: EvidenceDependencyMap) -> Path:
        MAP_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return MAP_TXT
