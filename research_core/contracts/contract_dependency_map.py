"""Cross-subsystem dependency analysis for contract compliance."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import (
    DependencyClassification,
    SAFETY_BANNER,
)
from research_core.contracts.contract_registry import all_contracts

MAP_JSON = "tae_contract_dependency_map.json"
MAP_TXT = "tae_contract_dependency_map.txt"

SUBSYSTEM_PREFIXES: dict[str, list[str]] = {
    "accounting": ["research_core/accounting/"],
    "evidence": [
        "research_core/evidence_engine/",
        "research_core/evidence_gap/",
        "research_core/evidence_history/",
    ],
    "simulation": ["research_core/simulation_lab/"],
    "strategy": ["research_core/strategy_evolution/"],
    "integration_gate": ["integration_layer/"],
    "orchestrator": ["research_core/orchestrator/"],
    "runtime": ["research_core/runtime/"],
    "contracts": ["research_core/contracts/"],
}

FORBIDDEN_PAIRS = {
    ("runtime", "strategy"): "Runtime must read strategy via contract JSON only",
    ("integration_gate", "evidence"): "Gate must consume evidence via contract JSON",
    ("orchestrator", "strategy"): "Orchestrator must invoke strategy via pipeline contract",
}

SCAN_ROOTS = [
    "research_core",
    "integration_layer",
]

EXCLUDE_PATH_FRAGMENTS = {
    "research_core/contracts/",
    "__pycache__",
    "_report.py",
    "strategy_dependency_map.py",
    "evidence_dependency_map.py",
    "accounting_dependency_map.py",
}


@dataclass
class DependencyEdge:
    source_module: str
    source_subsystem: str
    target_module: str
    target_subsystem: str
    classification: DependencyClassification
    rationale: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_module": self.source_module,
            "source_subsystem": self.source_subsystem,
            "target_module": self.target_module,
            "target_subsystem": self.target_subsystem,
            "classification": self.classification.value,
            "rationale": self.rationale,
        }


@dataclass
class ContractDependencyMapReport:
    edges: list[DependencyEdge]
    contract_compliant_count: int
    legacy_direct_link_count: int
    needs_adapter_count: int
    forbidden_count: int
    duplicate_contract_check: list[str]
    missing_contract_check: list[str]
    adapter_recommendations: list[str]
    verdict: str = "CONTRACT_DEPENDENCY_MAP_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_contract_dependency_map",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "contract_compliant_count": self.contract_compliant_count,
            "legacy_direct_link_count": self.legacy_direct_link_count,
            "needs_adapter_count": self.needs_adapter_count,
            "forbidden_count": self.forbidden_count,
            "edges": [e.to_dict() for e in self.edges],
            "duplicate_contract_check": list(self.duplicate_contract_check),
            "missing_contract_check": list(self.missing_contract_check),
            "adapter_recommendations": list(self.adapter_recommendations),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE CONTRACT DEPENDENCY MAP — SPRINT IX.2D =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Contract-compliant: {self.contract_compliant_count}",
            f"Legacy direct links: {self.legacy_direct_link_count}",
            f"Needs adapter: {self.needs_adapter_count}",
            f"Forbidden: {self.forbidden_count}",
            "",
            "===== DIRECT DEPENDENCY WARNINGS =====",
        ]
        for edge in self.edges:
            if edge.classification != DependencyClassification.INTERNAL:
                lines.append(
                    f"  [{edge.classification.value}] "
                    f"{edge.source_subsystem} → {edge.target_subsystem}"
                )
                lines.append(f"    {edge.source_module} → {edge.target_module}")
                lines.append(f"    {edge.rationale}")
        lines.extend(["", "===== ADAPTER RECOMMENDATIONS ====="])
        for rec in self.adapter_recommendations:
            lines.append(f"  • {rec}")
        lines.append("")
        return "\n".join(lines)


class ContractDependencyMapBuilder:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def build(self) -> ContractDependencyMapReport:
        paths = self._discover_modules()
        path_to_text = {
            p: (self._root / p).read_text(encoding="utf-8", errors="replace")
            for p in paths
        }
        index = self._module_index(paths)
        edges: list[DependencyEdge] = []

        for source, text in path_to_text.items():
            src_sub = self._subsystem(source)
            if src_sub == "contracts":
                continue
            uses_contract = "research_core.contracts" in text
            for target in self._import_targets(text, index, set(paths)):
                tgt_sub = self._subsystem(target)
                if src_sub == tgt_sub or tgt_sub == "unknown":
                    continue
                if tgt_sub == "contracts":
                    classification = DependencyClassification.CONTRACT_COMPLIANT
                    rationale = "Uses contract layer"
                elif (src_sub, tgt_sub) in FORBIDDEN_PAIRS:
                    classification = DependencyClassification.FORBIDDEN_DIRECT_DEPENDENCY
                    rationale = FORBIDDEN_PAIRS[(src_sub, tgt_sub)]
                elif uses_contract:
                    classification = DependencyClassification.NEEDS_CONTRACT_ADAPTER
                    rationale = "Partial contract usage — replace direct import with contract validate()"
                else:
                    classification = DependencyClassification.LEGACY_DIRECT_LINK
                    rationale = "Direct subsystem import — route through contract boundary"

                edges.append(
                    DependencyEdge(
                        source_module=source,
                        source_subsystem=src_sub,
                        target_module=target,
                        target_subsystem=tgt_sub,
                        classification=classification,
                        rationale=rationale,
                    )
                )

        unique_edges = self._dedupe_edges(edges)
        adapter_recs = self._adapter_recommendations(unique_edges)

        return ContractDependencyMapReport(
            edges=unique_edges,
            contract_compliant_count=sum(
                1
                for e in unique_edges
                if e.classification == DependencyClassification.CONTRACT_COMPLIANT
            ),
            legacy_direct_link_count=sum(
                1
                for e in unique_edges
                if e.classification == DependencyClassification.LEGACY_DIRECT_LINK
            ),
            needs_adapter_count=sum(
                1
                for e in unique_edges
                if e.classification == DependencyClassification.NEEDS_CONTRACT_ADAPTER
            ),
            forbidden_count=sum(
                1
                for e in unique_edges
                if e.classification == DependencyClassification.FORBIDDEN_DIRECT_DEPENDENCY
            ),
            duplicate_contract_check=self._duplicate_contract_check(),
            missing_contract_check=self._missing_contract_check(),
            adapter_recommendations=adapter_recs,
        )

    def _discover_modules(self) -> list[str]:
        found: set[str] = set()
        for rel_root in SCAN_ROOTS:
            root_path = self._root / rel_root
            if not root_path.is_dir():
                continue
            for py in root_path.rglob("*.py"):
                rel = py.relative_to(self._root).as_posix()
                if any(frag in rel for frag in EXCLUDE_PATH_FRAGMENTS):
                    continue
                found.add(rel)
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
    def _subsystem(path: str) -> str:
        for name, prefixes in SUBSYSTEM_PREFIXES.items():
            if any(path.startswith(p) for p in prefixes):
                return name
        return "unknown"

    @staticmethod
    def _dedupe_edges(edges: list[DependencyEdge]) -> list[DependencyEdge]:
        seen: set[tuple[str, str, str]] = set()
        out: list[DependencyEdge] = []
        for edge in edges:
            key = (edge.source_module, edge.target_module, edge.classification.value)
            if key not in seen:
                seen.add(key)
                out.append(edge)
        return sorted(out, key=lambda e: (e.classification.value, e.source_module))

    @staticmethod
    def _adapter_recommendations(edges: list[DependencyEdge]) -> list[str]:
        recs: list[str] = []
        for edge in edges:
            if edge.classification in (
                DependencyClassification.LEGACY_DIRECT_LINK,
                DependencyClassification.FORBIDDEN_DIRECT_DEPENDENCY,
                DependencyClassification.NEEDS_CONTRACT_ADAPTER,
            ):
                recs.append(
                    f"Replace {edge.source_module} → {edge.target_module} with "
                    f"contract validate/normalize for {edge.target_subsystem} "
                    f"({edge.classification.value})"
                )
        canonical = {c.describe().subsystem_name: c.CONTRACT_ID for c in all_contracts()}
        for subsystem, contract_id in canonical.items():
            recs.append(
                f"Subsystem {subsystem}: consume only via {contract_id} at JSON boundary"
            )
        return list(dict.fromkeys(recs))[:25]

    @staticmethod
    def _duplicate_contract_check() -> list[str]:
        ids = [c.CONTRACT_ID for c in all_contracts()]
        seen: set[str] = set()
        dups: list[str] = []
        for cid in ids:
            if cid in seen:
                dups.append(cid)
            seen.add(cid)
        return dups

    @staticmethod
    def _missing_contract_check() -> list[str]:
        required = {
            "Accounting",
            "Evidence Registry",
            "Simulation Lab",
            "Strategy Evolution Daily Runner",
            "Integration Gate",
            "Ecosystem Orchestrator",
            "Runtime Workflow",
        }
        present = {c.SUBSYSTEM_NAME for c in all_contracts()}
        return sorted(required - present)


class ContractDependencyMapStore:
    def persist(self, report: ContractDependencyMapReport, root: Path | str = Path(".")) -> Path:
        path = Path(root) / MAP_JSON
        path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path

    def persist_txt(self, report: ContractDependencyMapReport, root: Path | str = Path(".")) -> Path:
        path = Path(root) / MAP_TXT
        path.write_text(report.format_text() + "\n")
        return path
