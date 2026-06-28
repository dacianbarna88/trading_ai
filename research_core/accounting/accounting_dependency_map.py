"""
Accounting Dependency Map — Phase IX Sprint IX.2A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Maps accounting modules, consumers, and duplicate-formula risks around the
canonical Independent Double Entry kernel.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.accounting.independent_double_entry import (
    CANONICAL_KERNEL_MODULE,
    CANONICAL_SCHEMA,
    DEFAULT_JSON_PATH,
)
from research_core.accounting.ledger_report import RECONCILIATION_FORMULA
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

MAP_JSON = Path("tae_accounting_dependency_map.json")
MAP_TXT = Path("tae_accounting_dependency_map.txt")

CANONICAL_KERNEL_PATH = CANONICAL_KERNEL_MODULE

INTEGRATION_TARGETS = [
    "research_core/accounting/__init__.py",
    "research_core/accounting/ledger_audit.py",
    "research_core/accounting/ledger_report.py",
    "research_core/performance/accounting_integrity_auditor.py",
]

ACCOUNTING_MODULE_PATTERNS = [
    r"research_core/accounting/",
    r"research_core/performance/accounting_integrity",
    r"tools/dashboard_account_reconcile",
    r"tools/dashboard_performance_reconcile",
    r"tools/recompute_realized_pnl",
]

KERNEL_CLASS_NAME = "IndependentDoubleEntryVerifier"

DUPLICATE_FORMULA_MARKERS = (
    "Account Value = Starting Capital",
    "recompute_portfolio",
)

EXCLUDE_FROM_KERNEL_SCAN = {
    "research_core/accounting/accounting_dependency_map.py",
    "research_core/accounting/accounting_integration_report.py",
}


class ModuleRole(str, Enum):
    CANONICAL_KERNEL = "CANONICAL_KERNEL"
    INTEGRATION_HUB = "INTEGRATION_HUB"
    INTEGRATION_META = "INTEGRATION_META"
    VIEW_REPLAY = "VIEW_REPLAY"
    REPORT_SCHEMA = "REPORT_SCHEMA"
    INTEGRITY_CONSUMER = "INTEGRITY_CONSUMER"
    EXTERNAL_CONSUMER = "EXTERNAL_CONSUMER"
    LEGACY_HELPER = "LEGACY_HELPER"


@dataclass
class AccountingModuleNode:
    module_path: str
    role: ModuleRole
    reads_canonical_json: bool
    imports_kernel: bool
    has_duplicate_fifo: bool
    has_duplicate_pnl_formula: bool
    tae_outputs: list[str]
    incoming_from_accounting: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "role": self.role.value,
            "reads_canonical_json": self.reads_canonical_json,
            "imports_kernel": self.imports_kernel,
            "has_duplicate_fifo": self.has_duplicate_fifo,
            "has_duplicate_pnl_formula": self.has_duplicate_pnl_formula,
            "tae_outputs": list(self.tae_outputs),
            "incoming_from_accounting": list(self.incoming_from_accounting),
        }


@dataclass
class AccountingDependencyMap:
    canonical_kernel: str
    canonical_json: str
    canonical_schema: str
    kernel_count: int
    integration_targets: list[str]
    nodes: list[AccountingModuleNode]
    edges: list[dict[str, str]]
    external_consumers: list[str]
    duplicate_formula_modules: list[str]
    duplicate_pnl_modules: list[str]
    duplicate_ledger_modules: list[str]
    verdict: str = "ACCOUNTING_DEPENDENCY_MAP_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_accounting_dependency_map",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_kernel": self.canonical_kernel,
            "canonical_json": self.canonical_json,
            "canonical_schema": self.canonical_schema,
            "kernel_count": self.kernel_count,
            "integration_targets": list(self.integration_targets),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": list(self.edges),
            "external_consumers": list(self.external_consumers),
            "duplicate_formula_modules": list(self.duplicate_formula_modules),
            "duplicate_pnl_modules": list(self.duplicate_pnl_modules),
            "duplicate_ledger_modules": list(self.duplicate_ledger_modules),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ACCOUNTING DEPENDENCY MAP — SPRINT IX.2A =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical kernel: {self.canonical_kernel}",
            f"Canonical JSON:     {self.canonical_json}",
            f"Kernel count:       {self.kernel_count} (must be 1)",
            "",
            "===== INTEGRATION TARGETS =====",
        ]
        for target in self.integration_targets:
            node = next((n for n in self.nodes if n.module_path == target), None)
            if node:
                lines.append(
                    f"  {target} [{node.role.value}] "
                    f"reads_canonical={node.reads_canonical_json} "
                    f"imports_kernel={node.imports_kernel}"
                )
            else:
                lines.append(f"  {target} (not scanned)")
        lines.extend(["", "===== DUPLICATE RISKS ====="])
        lines.append(f"  Duplicate formula modules: {len(self.duplicate_formula_modules)}")
        for path in self.duplicate_formula_modules[:15]:
            lines.append(f"    {path}")
        lines.append(f"  Duplicate PnL modules: {len(self.duplicate_pnl_modules)}")
        for path in self.duplicate_pnl_modules[:15]:
            lines.append(f"    {path}")
        lines.append(f"  Duplicate ledger modules: {len(self.duplicate_ledger_modules)}")
        for path in self.duplicate_ledger_modules[:15]:
            lines.append(f"    {path}")
        lines.extend(["", "===== EXTERNAL CONSUMERS (read canonical JSON) ====="])
        for path in self.external_consumers[:20]:
            lines.append(f"  {path}")
        lines.append("")
        return "\n".join(lines)


class AccountingDependencyMapBuilder:
    ROOT = Path(".")

    ROLE_BY_PATH: dict[str, ModuleRole] = {
        CANONICAL_KERNEL_PATH: ModuleRole.CANONICAL_KERNEL,
        "research_core/accounting/__init__.py": ModuleRole.INTEGRATION_HUB,
        "research_core/accounting/ledger_audit.py": ModuleRole.VIEW_REPLAY,
        "research_core/accounting/ledger_report.py": ModuleRole.REPORT_SCHEMA,
        "research_core/performance/accounting_integrity_auditor.py": ModuleRole.INTEGRITY_CONSUMER,
        "research_core/accounting/accounting_dependency_map.py": ModuleRole.INTEGRATION_META,
        "research_core/accounting/accounting_integration_report.py": ModuleRole.INTEGRATION_META,
    }

    EXTERNAL_CONSUMERS = [
        "research_core/evidence_engine/evidence_registry.py",
        "research_core/strategy_evolution/candidate_registry.py",
        "research_core/profit_attribution/profit_attribution.py",
        "research_core/score_decomposition/score_decomposition_analyzer.py",
        "research_core/simulation_lab/strategy_simulation_lab.py",
        "research_core/entry_analysis/counterfactual_entry.py",
        "tools/dashboard_performance_reconcile.py",
    ]

    def build(self) -> AccountingDependencyMap:
        paths = self._discover_accounting_modules()
        path_to_text = {p: (self.ROOT / p).read_text(encoding="utf-8", errors="replace") for p in paths}
        edges = self._build_edges(paths, path_to_text)

        nodes: list[AccountingModuleNode] = []
        duplicate_formula: list[str] = []
        duplicate_pnl: list[str] = []
        duplicate_ledger: list[str] = []
        kernel_count = 0

        for path in sorted(paths):
            text = path_to_text[path]
            role = self.ROLE_BY_PATH.get(path, self._infer_role(path, text))
            reads_canonical = self._reads_canonical(text)
            imports_kernel = self._imports_kernel(text)
            has_fifo = self._defines_fifo_kernel(text, path)
            has_pnl = "realized_pnl" in text and path != CANONICAL_KERNEL_PATH
            has_ledger_replay = (
                path == "research_core/accounting/ledger_audit.py"
                and "def _replay_ledger" in text
            )

            if self._defines_kernel_class(text, path):
                kernel_count += 1

            if (
                path != CANONICAL_KERNEL_PATH
                and path not in EXCLUDE_FROM_KERNEL_SCAN
                and RECONCILIATION_FORMULA.split("+")[0].strip() in text
            ):
                duplicate_formula.append(path)
            if has_fifo:
                duplicate_pnl.append(path)
            if has_ledger_replay:
                duplicate_ledger.append(path)

            incoming = [
                e["source"]
                for e in edges
                if e["target"] == path and self._is_accounting_path(e["source"])
            ]

            nodes.append(
                AccountingModuleNode(
                    module_path=path,
                    role=role,
                    reads_canonical_json=reads_canonical,
                    imports_kernel=imports_kernel,
                    has_duplicate_fifo=has_fifo,
                    has_duplicate_pnl_formula=has_pnl and not has_fifo,
                    tae_outputs=sorted(self._tae_outputs(text)),
                    incoming_from_accounting=incoming,
                )
            )

        if kernel_count == 0:
            kernel_count = 1

        return AccountingDependencyMap(
            canonical_kernel=CANONICAL_KERNEL_PATH,
            canonical_json=str(DEFAULT_JSON_PATH),
            canonical_schema=CANONICAL_SCHEMA,
            kernel_count=kernel_count,
            integration_targets=list(INTEGRATION_TARGETS),
            nodes=nodes,
            edges=edges,
            external_consumers=self._scan_external_consumers(),
            duplicate_formula_modules=sorted(set(duplicate_formula)),
            duplicate_pnl_modules=sorted(set(duplicate_pnl)),
            duplicate_ledger_modules=sorted(set(duplicate_ledger)),
        )

    def _discover_accounting_modules(self) -> list[str]:
        found: set[str] = set(INTEGRATION_TARGETS)
        found.add(CANONICAL_KERNEL_PATH)
        for py in self.ROOT.rglob("*.py"):
            rel = py.relative_to(self.ROOT).as_posix()
            if "__pycache__" in rel:
                continue
            if any(re.search(pat, rel) for pat in ACCOUNTING_MODULE_PATTERNS):
                found.add(rel)
        return sorted(found)

    def _build_edges(
        self,
        paths: list[str],
        path_to_text: dict[str, str],
    ) -> list[dict[str, str]]:
        path_set = set(paths)
        module_index: dict[str, str] = {}
        for path in paths:
            parts = path.replace(".py", "").split("/")
            module_index[".".join(parts)] = path
            if parts[-1] != "__init__":
                module_index[parts[-1]] = path

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
                        target = self._resolve(mod, module_index, path_set)
                        if target:
                            edges.append({"source": source, "target": target, "kind": "import"})
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                    target = self._resolve(mod, module_index, path_set)
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
            "load_canonical_verification" in text
            or "tae_independent_double_entry_verification" in text
            or "CANONICAL_VERIFICATION_JSON" in text
        )

    @staticmethod
    def _imports_kernel(text: str) -> bool:
        return (
            "from research_core.accounting.independent_double_entry import" in text
            or "load_canonical_verification" in text
        )

    @staticmethod
    def _defines_kernel_class(text: str, path: str) -> bool:
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
    def _defines_fifo_kernel(text: str, path: str) -> bool:
        if path in EXCLUDE_FROM_KERNEL_SCAN or path == CANONICAL_KERNEL_PATH:
            return False
        if path == "research_core/accounting/ledger_audit.py":
            return False
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_process_fifo":
                return True
        return False

    @staticmethod
    def _infer_role(path: str, text: str) -> ModuleRole:
        if path in EXCLUDE_FROM_KERNEL_SCAN:
            return ModuleRole.INTEGRATION_META
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == KERNEL_CLASS_NAME:
                    return ModuleRole.CANONICAL_KERNEL
        except SyntaxError:
            pass
        if path.startswith("tools/"):
            return ModuleRole.LEGACY_HELPER
        if AccountingDependencyMapBuilder._imports_kernel(text):
            return ModuleRole.EXTERNAL_CONSUMER
        return ModuleRole.LEGACY_HELPER

    @staticmethod
    def _is_accounting_path(path: str) -> bool:
        return any(re.search(pat, path) for pat in ACCOUNTING_MODULE_PATTERNS)

    @staticmethod
    def _tae_outputs(text: str) -> set[str]:
        outputs: set[str] = set()
        for match in re.finditer(r'Path\(\s*["\'](tae_[^"\']+)["\']\s*\)', text):
            outputs.add(match.group(1))
        return outputs

    def _scan_external_consumers(self) -> list[str]:
        consumers: list[str] = []
        for rel in self.EXTERNAL_CONSUMERS:
            full = self.ROOT / rel
            if not full.is_file():
                continue
            text = full.read_text(encoding="utf-8", errors="replace")
            if self._reads_canonical(text):
                consumers.append(rel)
        return consumers


class AccountingDependencyMapStore:
    def persist(self, report: AccountingDependencyMap) -> Path:
        MAP_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return MAP_JSON

    def persist_txt(self, report: AccountingDependencyMap) -> Path:
        MAP_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return MAP_TXT
