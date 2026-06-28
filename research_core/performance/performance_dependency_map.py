"""
Performance Dependency Map — Phase IX Sprint IX.5A

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

from research_core.performance.performance_pipeline_integration import (
    CANONICAL_INTEGRITY_MODULE,
    CANONICAL_STRATEGIC_MODULE,
    INTEGRITY_REPORT_PATH,
    STRATEGIC_REPORT_PATH,
)
from research_core.performance.performance_report import SCHEMA_NAME as STRATEGIC_SCHEMA
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

MAP_JSON = Path("tae_performance_dependency_map.json")
MAP_TXT = Path("tae_performance_dependency_map.txt")

INTEGRATION_TARGETS = [
    CANONICAL_STRATEGIC_MODULE,
    CANONICAL_INTEGRITY_MODULE,
    "research_core/performance/performance_report.py",
    "research_core/performance/__init__.py",
    "research_core/accounting/ledger_audit.py",
    "research_core/recalibration/confidence_recalibration.py",
    "research_core/profit_attribution/profit_attribution.py",
    "tools/dashboard_performance_reconcile.py",
    "research_core/runtime/ecosystem_state.py",
    "research_core/runtime/runtime_health.py",
    "research_core/runtime/quick_health_wrapper.py",
]

PERFORMANCE_MODULE_PATTERNS = [
    r"research_core/performance/",
    r"research_core/metrics/performance",
    r"tools/dashboard_performance_reconcile",
    r"tae_strategic_performance",
    r"tae_accounting_integrity",
]

RUNTIME_CONSUMERS = [
    "research_core/runtime/ecosystem_state.py",
    "research_core/runtime/runtime_health.py",
    "research_core/runtime/workflow_engine.py",
    "research_core/runtime/quick_health_wrapper.py",
]

EXCLUDE_FROM_SCAN = {
    "research_core/performance/performance_dependency_map.py",
    "research_core/performance/performance_pipeline_report.py",
    "research_core/performance/accounting_adapter_migration_report.py",
}


class ModuleClassification(str, Enum):
    CANONICAL = "CANONICAL"
    VIEW = "VIEW"
    AUDIT = "AUDIT"
    REPORTER = "REPORTER"
    LEGACY = "LEGACY"
    UNUSED = "UNUSED"
    DUPLICATE = "DUPLICATE"
    INTEGRATION_META = "INTEGRATION_META"
    HELPER = "HELPER"
    RUNTIME_CONSUMER = "RUNTIME_CONSUMER"


INVENTORY: list[dict[str, str]] = [
    {
        "module_path": CANONICAL_STRATEGIC_MODULE,
        "classification": ModuleClassification.CANONICAL.value,
        "notes": "Primary strategic performance audit — tae_strategic_performance_audit.json",
    },
    {
        "module_path": CANONICAL_INTEGRITY_MODULE,
        "classification": ModuleClassification.AUDIT.value,
        "notes": "CSV/accounting integrity audit — consumes AccountingAdapter JSON",
    },
    {
        "module_path": "research_core/performance/performance_report.py",
        "classification": ModuleClassification.REPORTER.value,
        "notes": "Strategic performance report schema and persistence",
    },
    {
        "module_path": "research_core/performance/performance_pipeline_integration.py",
        "classification": ModuleClassification.INTEGRATION_META.value,
        "notes": "Pipeline stage reference loader",
    },
    {
        "module_path": "research_core/performance/accounting_adapter_migration_report.py",
        "classification": ModuleClassification.INTEGRATION_META.value,
        "notes": "IX.3B adapter migration audit",
    },
    {
        "module_path": "research_core/metrics/performance.py",
        "classification": ModuleClassification.HELPER.value,
        "notes": "Research candidate metrics — not portfolio performance engine",
    },
    {
        "module_path": "tools/dashboard_performance_reconcile.py",
        "classification": ModuleClassification.VIEW.value,
        "notes": "Dashboard reconciliation view — reads canonical audit JSON",
    },
    {
        "module_path": "tae_strategic_performance_audit_demo.py",
        "classification": ModuleClassification.VIEW.value,
        "notes": "Demo runner for strategic audit",
    },
    {
        "module_path": "tae_accounting_integrity_audit_demo.py",
        "classification": ModuleClassification.VIEW.value,
        "notes": "Demo runner for integrity audit",
    },
    {
        "module_path": "research_core/accounting/ledger_audit.py",
        "classification": ModuleClassification.VIEW.value,
        "notes": "Cross-check reader of performance audit JSON",
    },
    {
        "module_path": "research_core/recalibration/confidence_recalibration.py",
        "classification": ModuleClassification.VIEW.value,
        "notes": "Reads performance JSON as evidence input",
    },
    {
        "module_path": "research_core/profit_attribution/profit_attribution.py",
        "classification": ModuleClassification.VIEW.value,
        "notes": "Reads strategic performance JSON",
    },
]


@dataclass
class PerformanceModuleNode:
    module_path: str
    classification: str
    reads_strategic_json: bool
    reads_integrity_json: bool
    writes_strategic_json: bool
    writes_integrity_json: bool
    imports_performance_package: bool
    runtime_consumer: bool
    tae_outputs: list[str]
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "classification": self.classification,
            "reads_strategic_json": self.reads_strategic_json,
            "reads_integrity_json": self.reads_integrity_json,
            "writes_strategic_json": self.writes_strategic_json,
            "writes_integrity_json": self.writes_integrity_json,
            "imports_performance_package": self.imports_performance_package,
            "runtime_consumer": self.runtime_consumer,
            "tae_outputs": list(self.tae_outputs),
            "notes": self.notes,
        }


@dataclass
class PerformanceDependencyMap:
    canonical_strategic_module: str
    canonical_integrity_module: str
    strategic_json: str
    integrity_json: str
    inventory: list[dict[str, str]]
    nodes: list[PerformanceModuleNode]
    edges: list[dict[str, str]]
    runtime_consumers: list[str]
    direct_runtime_bypasses: list[str]
    duplicate_engine_candidates: list[str]
    verdict: str = "PERFORMANCE_DEPENDENCY_MAP_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_performance_dependency_map",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_strategic_module": self.canonical_strategic_module,
            "canonical_integrity_module": self.canonical_integrity_module,
            "strategic_json": self.strategic_json,
            "integrity_json": self.integrity_json,
            "inventory": list(self.inventory),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": list(self.edges),
            "runtime_consumers": list(self.runtime_consumers),
            "direct_runtime_bypasses": list(self.direct_runtime_bypasses),
            "duplicate_engine_candidates": list(self.duplicate_engine_candidates),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE PERFORMANCE DEPENDENCY MAP — SPRINT IX.5A =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical strategic: {self.canonical_strategic_module}",
            f"Canonical integrity: {self.canonical_integrity_module}",
            f"Strategic JSON: {self.strategic_json}",
            f"Integrity JSON: {self.integrity_json}",
            "",
            "===== INVENTORY =====",
        ]
        for item in self.inventory:
            lines.append(
                f"  [{item['classification']}] {item['module_path']}"
            )
            lines.append(f"      {item['notes']}")
        lines.extend(["", "===== RUNTIME CONSUMERS ====="])
        for path in self.runtime_consumers:
            lines.append(f"  {path}")
        if self.direct_runtime_bypasses:
            lines.extend(["", "===== DIRECT RUNTIME BYPASSES ====="])
            for bypass in self.direct_runtime_bypasses:
                lines.append(f"  • {bypass}")
        if self.duplicate_engine_candidates:
            lines.extend(["", "===== DUPLICATE ENGINE CANDIDATES ====="])
            for dup in self.duplicate_engine_candidates:
                lines.append(f"  • {dup}")
        lines.extend(["", "===== EDGES (sample) ====="])
        for edge in self.edges[:25]:
            lines.append(
                f"  {edge['source']} → {edge['target']} [{edge.get('edge_type', '')}]"
            )
        lines.append("")
        return "\n".join(lines)


class PerformanceDependencyMapBuilder:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def build(self) -> PerformanceDependencyMap:
        paths = self._discover_modules()
        path_to_text = {
            p: (self._root / p).read_text(encoding="utf-8", errors="replace")
            for p in paths
        }
        index = self._module_index(paths)

        inv_by_path = {item["module_path"]: item for item in INVENTORY}
        nodes: list[PerformanceModuleNode] = []
        for path in sorted(set(paths) | set(inv_by_path)):
            if path not in path_to_text and path in inv_by_path:
                text = ""
            else:
                text = path_to_text.get(path, "")
            inv = inv_by_path.get(path, {})
            nodes.append(
                PerformanceModuleNode(
                    module_path=path,
                    classification=inv.get(
                        "classification", ModuleClassification.UNUSED.value
                    ),
                    reads_strategic_json=self._reads_json(text, STRATEGIC_REPORT_PATH.name),
                    reads_integrity_json=self._reads_json(text, INTEGRITY_REPORT_PATH.name),
                    writes_strategic_json=STRATEGIC_REPORT_PATH.name in text
                    and "write_text" in text
                    and path == CANONICAL_STRATEGIC_MODULE,
                    writes_integrity_json=INTEGRITY_REPORT_PATH.name in text
                    and "persist" in text
                    and "Integrity" in path,
                    imports_performance_package="research_core.performance" in text,
                    runtime_consumer=path in RUNTIME_CONSUMERS,
                    tae_outputs=self._tae_outputs(text),
                    notes=inv.get("notes", ""),
                )
            )

        edges = self._build_edges(path_to_text, index, set(paths))
        bypasses = self._detect_runtime_bypasses(path_to_text)
        duplicates = self._duplicate_candidates(path_to_text)

        return PerformanceDependencyMap(
            canonical_strategic_module=CANONICAL_STRATEGIC_MODULE,
            canonical_integrity_module=CANONICAL_INTEGRITY_MODULE,
            strategic_json=STRATEGIC_REPORT_PATH.name,
            integrity_json=INTEGRITY_REPORT_PATH.name,
            inventory=list(INVENTORY),
            nodes=nodes,
            edges=edges,
            runtime_consumers=list(RUNTIME_CONSUMERS),
            direct_runtime_bypasses=bypasses,
            duplicate_engine_candidates=duplicates,
        )

    def _discover_modules(self) -> list[str]:
        found: set[str] = set()
        for pattern in PERFORMANCE_MODULE_PATTERNS:
            if pattern.startswith("research_core"):
                root = self._root / pattern.split("/")[0] / pattern.split("/")[1]
                if "metrics" in pattern:
                    p = self._root / "research_core/metrics/performance.py"
                    if p.is_file():
                        found.add(p.relative_to(self._root).as_posix())
                elif root.is_dir():
                    for py in root.rglob("*.py"):
                        rel = py.relative_to(self._root).as_posix()
                        if any(x in rel for x in EXCLUDE_FROM_SCAN):
                            continue
                        found.add(rel)
        for target in INTEGRATION_TARGETS:
            if (self._root / target).is_file():
                found.add(target)
        for demo in (
            "tae_strategic_performance_audit_demo.py",
            "tae_accounting_integrity_audit_demo.py",
        ):
            if (self._root / demo).is_file():
                found.add(demo)
        return sorted(found)

    @staticmethod
    def _module_index(paths: list[str]) -> dict[str, str]:
        index: dict[str, str] = {}
        for path in paths:
            parts = path.replace(".py", "").split("/")
            index[".".join(parts)] = path
            if parts[-1] != "__init__":
                index[parts[-1]] = path
        return index

    @staticmethod
    def _reads_json(text: str, filename: str) -> bool:
        return filename in text

    @staticmethod
    def _tae_outputs(text: str) -> list[str]:
        return sorted(set(re.findall(r"tae_[a-z0-9_]+\.json", text)))

    def _build_edges(
        self,
        path_to_text: dict[str, str],
        index: dict[str, str],
        path_set: set[str],
    ) -> list[dict[str, str]]:
        edges: list[dict[str, str]] = []
        for source, text in path_to_text.items():
            for target in self._import_targets(text, index, path_set):
                edge_type = "import"
                if STRATEGIC_REPORT_PATH.name in text and target in (
                    CANONICAL_STRATEGIC_MODULE,
                    "research_core/performance/performance_report.py",
                ):
                    edge_type = "json_consumer"
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "edge_type": edge_type,
                    }
                )
            if STRATEGIC_REPORT_PATH.name in text:
                edges.append(
                    {
                        "source": source,
                        "target": STRATEGIC_REPORT_PATH.name,
                        "edge_type": "reads_json",
                    }
                )
            if INTEGRITY_REPORT_PATH.name in text:
                edges.append(
                    {
                        "source": source,
                        "target": INTEGRITY_REPORT_PATH.name,
                        "edge_type": "reads_json",
                    }
                )
        return edges

    def _import_targets(
        self,
        text: str,
        index: dict[str, str],
        path_set: set[str],
    ) -> list[str]:
        targets: list[str] = []
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return targets
        for node in ast.walk(tree):
            mod: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    resolved = self._resolve(mod, index, path_set)
                    if resolved:
                        targets.append(resolved)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                resolved = self._resolve(mod, index, path_set)
                if resolved:
                    targets.append(resolved)
        return targets

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
    def _detect_runtime_bypasses(path_to_text: dict[str, str]) -> list[str]:
        bypasses: list[str] = []
        state_loader = path_to_text.get("research_core/runtime/ecosystem_state.py", "")
        if "tae_strategic_performance_audit.json" not in state_loader:
            bypasses.append(
                "EcosystemStateLoader missing strategic performance JSON source"
            )
        if "tae_accounting_integrity_audit.json" not in state_loader:
            bypasses.append(
                "EcosystemStateLoader missing accounting integrity JSON source"
            )
        health = path_to_text.get("research_core/runtime/runtime_health.py", "")
        if "_check_performance_pipeline" not in health:
            bypasses.append("RuntimeHealth missing performance pipeline check")
        return bypasses

    @staticmethod
    def _duplicate_candidates(path_to_text: dict[str, str]) -> list[str]:
        candidates: list[str] = []
        strategic_defs = sum(
            1
            for path, text in path_to_text.items()
            if "class StrategicPerformanceAuditor" in text
        )
        if strategic_defs > 1:
            candidates.append("Multiple StrategicPerformanceAuditor definitions")
        if "research_core/metrics/performance.py" in path_to_text:
            candidates.append(
                "research_core/metrics/performance.py is research metrics helper — "
                "not duplicate portfolio engine if used only for candidate evaluation"
            )
        return candidates


class PerformanceDependencyMapStore:
    def persist(self, report: PerformanceDependencyMap, root: Path | str = Path(".")) -> Path:
        path = Path(root) / MAP_JSON
        path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path

    def persist_txt(self, report: PerformanceDependencyMap, root: Path | str = Path(".")) -> Path:
        path = Path(root) / MAP_TXT
        path.write_text(report.format_text() + "\n", encoding="utf-8")
        return path
