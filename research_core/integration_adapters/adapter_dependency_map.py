"""Adapter-layer dependency analysis — Phase IX Sprint IX.3."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.contract_dependency_map import (
    EXCLUDE_PATH_FRAGMENTS,
    FORBIDDEN_PAIRS,
    SCAN_ROOTS,
    SUBSYSTEM_PREFIXES,
)
from research_core.integration_adapters.base_adapter import ADAPTER_RULE, AdapterStatus, SAFETY_BANNER
from research_core.integration_adapters.adapter_registry import all_adapters

MAP_JSON = "tae_adapter_dependency_map.json"
MAP_TXT = "tae_adapter_dependency_map.txt"

MIGRATION_TARGETS: dict[tuple[str, str], str] = {
    (
        "research_core/orchestrator/ecosystem_orchestrator.py",
        "research_core/strategy_evolution/daily_runner.py",
    ): (
        "Orchestrator must consume strategy state via StrategyAdapter "
        "(tae.adapter.strategy_evolution.v1) — not direct daily_runner import"
    ),
}

ADAPTER_PACKAGE = "research_core.integration_adapters"


@dataclass
class AdapterDependencyEdge:
    source_module: str
    source_subsystem: str
    target_module: str
    target_subsystem: str
    classification: AdapterStatus
    rationale: str
    recommended_adapter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source_module": self.source_module,
            "source_subsystem": self.source_subsystem,
            "target_module": self.target_module,
            "target_subsystem": self.target_subsystem,
            "classification": self.classification.value,
            "rationale": self.rationale,
        }
        if self.recommended_adapter:
            out["recommended_adapter"] = self.recommended_adapter
        return out


@dataclass
class AdapterDependencyMapReport:
    edges: list[AdapterDependencyEdge]
    adapter_compliant_count: int
    needs_migration_count: int
    legacy_direct_link_count: int
    forbidden_count: int
    missing_report_count: int
    validation_failed_count: int
    duplicate_adapter_check: list[str]
    missing_adapter_coverage: list[str]
    adapter_migration_recommendations: list[str]
    forbidden_dependencies: list[dict[str, str]]
    missing_canonical_reports: list[dict[str, str]]
    verdict: str = "ADAPTER_DEPENDENCY_MAP_READY"
    safety_mode: str = SAFETY_BANNER
    integration_rule: str = ADAPTER_RULE
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_adapter_dependency_map",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "integration_rule": self.integration_rule,
            "verdict": self.verdict,
            "adapter_compliant_count": self.adapter_compliant_count,
            "needs_migration_count": self.needs_migration_count,
            "legacy_direct_link_count": self.legacy_direct_link_count,
            "forbidden_count": self.forbidden_count,
            "missing_report_count": self.missing_report_count,
            "validation_failed_count": self.validation_failed_count,
            "edges": [e.to_dict() for e in self.edges],
            "duplicate_adapter_check": list(self.duplicate_adapter_check),
            "missing_adapter_coverage": list(self.missing_adapter_coverage),
            "adapter_migration_recommendations": list(self.adapter_migration_recommendations),
            "forbidden_dependencies": list(self.forbidden_dependencies),
            "missing_canonical_reports": list(self.missing_canonical_reports),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ADAPTER DEPENDENCY MAP — SPRINT IX.3 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Integration rule: {self.integration_rule}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Adapter-compliant paths: {self.adapter_compliant_count}",
            f"Needs adapter migration: {self.needs_migration_count}",
            f"Legacy direct links: {self.legacy_direct_link_count}",
            f"Forbidden dependencies: {self.forbidden_count}",
            f"Missing canonical reports: {self.missing_report_count}",
            f"Contract validation failed: {self.validation_failed_count}",
            "",
            "===== DIRECT DEPENDENCY WARNINGS =====",
        ]
        for edge in self.edges:
            if edge.classification != AdapterStatus.ADAPTER_COMPLIANT:
                lines.append(
                    f"  [{edge.classification.value}] "
                    f"{edge.source_subsystem} → {edge.target_subsystem}"
                )
                lines.append(f"    {edge.source_module} → {edge.target_module}")
                lines.append(f"    {edge.rationale}")
                if edge.recommended_adapter:
                    lines.append(f"    Recommended: {edge.recommended_adapter}")
        lines.extend(["", "===== ADAPTER MIGRATION RECOMMENDATIONS ====="])
        for rec in self.adapter_migration_recommendations:
            lines.append(f"  • {rec}")
        lines.extend(["", "===== MISSING CANONICAL REPORTS ====="])
        if self.missing_canonical_reports:
            for item in self.missing_canonical_reports:
                lines.append(f"  {item['adapter_id']}: {item['report']}")
        else:
            lines.append("  None — all primary reports present")
        lines.extend(["", "===== FORBIDDEN DEPENDENCIES ====="])
        if self.forbidden_dependencies:
            for item in self.forbidden_dependencies:
                lines.append(
                    f"  {item['source_module']} → {item['target_module']}: {item['rationale']}"
                )
        else:
            lines.append("  None detected")
        lines.append("")
        return "\n".join(lines)


class AdapterDependencyMapBuilder:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def build(self) -> AdapterDependencyMapReport:
        paths = self._discover_modules()
        path_to_text = {
            p: (self._root / p).read_text(encoding="utf-8", errors="replace")
            for p in paths
        }
        index = self._module_index(paths)
        edges: list[AdapterDependencyEdge] = []

        for source, text in path_to_text.items():
            src_sub = self._subsystem(source)
            if src_sub == "contracts" or ADAPTER_PACKAGE.replace("/", ".") in source:
                continue
            uses_adapter = ADAPTER_PACKAGE.replace("/", ".") in text
            for target in self._import_targets(text, index, set(paths)):
                tgt_sub = self._subsystem(target)
                if src_sub == tgt_sub or tgt_sub == "unknown":
                    continue

                migration_key = (source, target)
                recommended = self._recommended_adapter(tgt_sub)

                if migration_key in MIGRATION_TARGETS:
                    classification = AdapterStatus.NEEDS_ADAPTER_MIGRATION
                    rationale = MIGRATION_TARGETS[migration_key]
                elif uses_adapter and tgt_sub != "contracts":
                    classification = AdapterStatus.ADAPTER_COMPLIANT
                    rationale = "Consumes subsystem via integration adapter layer"
                elif ADAPTER_PACKAGE in target:
                    classification = AdapterStatus.ADAPTER_COMPLIANT
                    rationale = "Uses integration adapter layer"
                elif (src_sub, tgt_sub) in FORBIDDEN_PAIRS and migration_key not in MIGRATION_TARGETS:
                    classification = AdapterStatus.FORBIDDEN_DIRECT_DEPENDENCY
                    rationale = FORBIDDEN_PAIRS[(src_sub, tgt_sub)]
                elif "research_core.contracts" in text:
                    classification = AdapterStatus.NEEDS_ADAPTER_MIGRATION
                    rationale = (
                        "Contract import without adapter — prefer adapter "
                        "to_contract_payload() for cross-subsystem reads"
                    )
                else:
                    classification = AdapterStatus.LEGACY_DIRECT_LINK
                    rationale = "Direct subsystem import — route through adapter boundary"

                edges.append(
                    AdapterDependencyEdge(
                        source_module=source,
                        source_subsystem=src_sub,
                        target_module=target,
                        target_subsystem=tgt_sub,
                        classification=classification,
                        rationale=rationale,
                        recommended_adapter=recommended,
                    )
                )

        unique_edges = self._dedupe_edges(edges)
        missing_reports = self._missing_canonical_reports()
        dup_check = self._duplicate_adapter_check()
        missing_coverage = self._missing_adapter_coverage()

        forbidden_deps = [
            e.to_dict()
            for e in unique_edges
            if e.classification == AdapterStatus.FORBIDDEN_DIRECT_DEPENDENCY
        ]
        migration_recs = self._migration_recommendations(unique_edges, missing_reports)

        return AdapterDependencyMapReport(
            edges=unique_edges,
            adapter_compliant_count=sum(
                1 for e in unique_edges if e.classification == AdapterStatus.ADAPTER_COMPLIANT
            ),
            needs_migration_count=sum(
                1 for e in unique_edges if e.classification == AdapterStatus.NEEDS_ADAPTER_MIGRATION
            ),
            legacy_direct_link_count=sum(
                1 for e in unique_edges if e.classification == AdapterStatus.LEGACY_DIRECT_LINK
            ),
            forbidden_count=len(forbidden_deps),
            missing_report_count=len(missing_reports),
            validation_failed_count=sum(
                1
                for a in all_adapters(self._root)
                if a.adapter_status() == AdapterStatus.CONTRACT_VALIDATION_FAILED
            ),
            duplicate_adapter_check=dup_check,
            missing_adapter_coverage=missing_coverage,
            adapter_migration_recommendations=migration_recs,
            forbidden_dependencies=forbidden_deps,
            missing_canonical_reports=missing_reports,
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
                if ADAPTER_PACKAGE in rel and not rel.endswith("_adapter.py") and "adapter_" in rel:
                    if rel.endswith(("adapter_registry.py", "adapter_dependency_map.py", "adapter_report.py", "base_adapter.py", "__init__.py")):
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
        if ADAPTER_PACKAGE in path:
            return "adapters"
        for name, prefixes in SUBSYSTEM_PREFIXES.items():
            if any(path.startswith(p) for p in prefixes):
                return name
        return "unknown"

    @staticmethod
    def _dedupe_edges(edges: list[AdapterDependencyEdge]) -> list[AdapterDependencyEdge]:
        seen: set[tuple[str, str, str]] = set()
        out: list[AdapterDependencyEdge] = []
        for edge in edges:
            key = (edge.source_module, edge.target_module, edge.classification.value)
            if key not in seen:
                seen.add(key)
                out.append(edge)
        return sorted(out, key=lambda e: (e.classification.value, e.source_module))

    @staticmethod
    def _recommended_adapter(target_subsystem: str) -> str | None:
        mapping = {
            "accounting": "tae.adapter.accounting.v1",
            "evidence": "tae.adapter.evidence.v1",
            "simulation": "tae.adapter.simulation.v1",
            "strategy": "tae.adapter.strategy_evolution.v1",
            "integration_gate": "tae.adapter.integration_gate.v1",
            "orchestrator": "tae.adapter.orchestrator.v1",
            "runtime": "tae.adapter.runtime.v1",
        }
        return mapping.get(target_subsystem)

    def _missing_canonical_reports(self) -> list[dict[str, str]]:
        missing: list[dict[str, str]] = []
        for adapter in all_adapters(self._root):
            loaded = adapter.load_source()
            for report in loaded.missing_reports:
                missing.append({"adapter_id": adapter.ADAPTER_ID, "report": report})
        return missing

    @staticmethod
    def _duplicate_adapter_check() -> list[str]:
        ids = [a.ADAPTER_ID for a in all_adapters()]
        seen: set[str] = set()
        dups: list[str] = []
        for aid in ids:
            if aid in seen:
                dups.append(aid)
            seen.add(aid)
        contract_ids = [a.CONTRACT_ID for a in all_adapters()]
        seen_c: set[str] = set()
        for cid in contract_ids:
            if cid in seen_c:
                dups.append(f"contract:{cid}")
            seen_c.add(cid)
        return dups

    @staticmethod
    def _missing_adapter_coverage() -> list[str]:
        required_contracts = {
            "tae.contract.accounting.v1",
            "tae.contract.evidence.v1",
            "tae.contract.simulation.v1",
            "tae.contract.strategy_evolution.v1",
            "tae.contract.integration_gate.v1",
            "tae.contract.orchestrator.v1",
            "tae.contract.runtime.v1",
        }
        covered = {a.CONTRACT_ID for a in all_adapters()}
        return sorted(required_contracts - covered)

    @staticmethod
    def _migration_recommendations(
        edges: list[AdapterDependencyEdge],
        missing_reports: list[dict[str, str]],
    ) -> list[str]:
        recs: list[str] = []
        for edge in edges:
            if edge.classification in (
                AdapterStatus.LEGACY_DIRECT_LINK,
                AdapterStatus.NEEDS_ADAPTER_MIGRATION,
                AdapterStatus.FORBIDDEN_DIRECT_DEPENDENCY,
            ):
                adapter_hint = edge.recommended_adapter or "matching adapter"
                recs.append(
                    f"Migrate {edge.source_module} → {edge.target_module}: "
                    f"use {adapter_hint} ({edge.classification.value})"
                )
        for item in missing_reports:
            recs.append(
                f"Generate missing report {item['report']} for {item['adapter_id']}"
            )
        recs.append(
            "Orchestrator: replace StrategyEvolutionDailyRunner direct import with "
            "StrategyAdapter.load_strategy_state_for_orchestrator() (read-only JSON path)"
        )
        return list(dict.fromkeys(recs))[:30]


class AdapterDependencyMapStore:
    def persist(self, report: AdapterDependencyMapReport, root: Path | str = Path(".")) -> Path:
        path = Path(root) / MAP_JSON
        path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path

    def persist_txt(self, report: AdapterDependencyMapReport, root: Path | str = Path(".")) -> Path:
        path = Path(root) / MAP_TXT
        path.write_text(report.format_text() + "\n")
        return path
