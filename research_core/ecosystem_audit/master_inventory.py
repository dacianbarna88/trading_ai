"""
Master Module Inventory — Phase IX Sprint IX.1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
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

from research_core.ecosystem_audit.audit_constants import (
    CANONICAL_MODULES,
    DUPLICATE_THEMES,
    OWNERSHIP_MATRIX,
    PRIMARY_RUNNERS,
    PROTECTED_PATHS,
    SCAN_FILES,
    SCAN_ROOTS,
    EXCLUDE_DIR_NAMES,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

INVENTORY_JSON = Path("tae_ecosystem_inventory.json")
INVENTORY_TXT = Path("tae_ecosystem_inventory.txt")


class ModuleRole(str, Enum):
    CANONICAL = "CANONICAL"
    PRIMARY_RUNNER = "PRIMARY_RUNNER"
    COMPETING_RUNNER = "COMPETING_RUNNER"
    VIEW_ONLY = "VIEW_ONLY"
    REPORT_ONLY = "REPORT_ONLY"
    DEMO = "DEMO"
    LIVE_CORE = "LIVE_CORE"
    STANDARD = "STANDARD"
    UNUSED = "UNUSED"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class ModuleRecord:
    module_path: str
    module_name: str
    purpose: str
    layer: str
    ownership: str
    role: ModuleRole
    canonical_for: str | None
    duplicate_group_ids: list[str]
    tae_outputs: list[str]
    is_runner: bool
    is_demo: bool
    incoming_refs: int
    outgoing_refs: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "module_name": self.module_name,
            "purpose": self.purpose,
            "layer": self.layer,
            "ownership": self.ownership,
            "role": self.role.value,
            "canonical_for": self.canonical_for,
            "duplicate_group_ids": list(self.duplicate_group_ids),
            "tae_outputs": list(self.tae_outputs),
            "is_runner": self.is_runner,
            "is_demo": self.is_demo,
            "incoming_refs": self.incoming_refs,
            "outgoing_refs": self.outgoing_refs,
        }


@dataclass
class DuplicateGroup:
    group_id: str
    theme: str
    module_paths: list[str]
    canonical_module: str
    connect_recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "theme": self.theme,
            "module_paths": list(self.module_paths),
            "canonical_module": self.canonical_module,
            "connect_recommendation": self.connect_recommendation,
        }


@dataclass
class OwnershipEntry:
    domain: str
    owner: str
    module_count: int
    canonical_modules: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "owner": self.owner,
            "module_count": self.module_count,
            "canonical_modules": list(self.canonical_modules),
        }


@dataclass
class MasterInventoryReport:
    modules: list[ModuleRecord]
    duplicate_groups: list[DuplicateGroup]
    ownership_matrix: list[OwnershipEntry]
    canonical_modules: dict[str, str]
    competing_runners: list[str]
    unused_modules: list[str]
    disconnected_modules: list[str]
    unreferenced_modules: list[str]
    total_modules: int
    verdict: str = "ECOSYSTEM_INTEGRATION_AUDIT_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_ecosystem_inventory",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "total_modules": self.total_modules,
            "canonical_modules": dict(self.canonical_modules),
            "competing_runners": list(self.competing_runners),
            "unused_modules": list(self.unused_modules),
            "disconnected_modules": list(self.disconnected_modules),
            "unreferenced_modules": list(self.unreferenced_modules),
            "duplicate_groups": [g.to_dict() for g in self.duplicate_groups],
            "ownership_matrix": [o.to_dict() for o in self.ownership_matrix],
            "modules": [m.to_dict() for m in self.modules],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE MASTER MODULE INVENTORY — SPRINT IX.1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            f"Total modules: {self.total_modules}",
            "",
            "===== CANONICAL MODULES =====",
        ]
        for resp, path in self.canonical_modules.items():
            lines.append(f"  {resp}: {path}")
        lines.extend(["", "===== OWNERSHIP MATRIX ====="])
        for entry in self.ownership_matrix:
            lines.append(
                f"  {entry.domain} ({entry.owner}): {entry.module_count} modules"
            )
        lines.extend(["", "===== DUPLICATE GROUPS ====="])
        for group in self.duplicate_groups:
            lines.append(f"  {group.group_id}: {group.theme} → {group.canonical_module}")
        lines.extend(["", "===== COMPETING RUNNERS ====="])
        for path in self.competing_runners:
            lines.append(f"  {path}")
        lines.extend(["", "===== UNUSED MODULES ====="])
        for path in self.unused_modules[:30]:
            lines.append(f"  {path}")
        if len(self.unused_modules) > 30:
            lines.append(f"  ... and {len(self.unused_modules) - 30} more")
        lines.extend(["", "===== DISCONNECTED MODULES ====="])
        for path in self.disconnected_modules[:30]:
            lines.append(f"  {path}")
        if len(self.disconnected_modules) > 30:
            lines.append(f"  ... and {len(self.disconnected_modules) - 30} more")
        lines.extend(["", "===== UNREFERENCED MODULES (zero incoming imports) ====="])
        for path in self.unreferenced_modules[:30]:
            lines.append(f"  {path}")
        if len(self.unreferenced_modules) > 30:
            lines.append(f"  ... and {len(self.unreferenced_modules) - 30} more")
        lines.append("")
        return "\n".join(lines)


class MasterInventoryBuilder:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def build(
        self,
        incoming_counts: dict[str, int] | None = None,
        outgoing_counts: dict[str, int] | None = None,
        connected_paths: set[str] | None = None,
    ) -> MasterInventoryReport:
        paths = self._discover_python_files()
        incoming = incoming_counts or {}
        outgoing = outgoing_counts or {}
        connected = connected_paths or set()

        canonical_reverse = {v: k for k, v in CANONICAL_MODULES.items()}
        duplicate_groups = self._duplicate_groups(paths)

        modules: list[ModuleRecord] = []
        for path in paths:
            rel = path.relative_to(self._root).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            group_ids = self._groups_for(rel, duplicate_groups)
            canonical_for = canonical_reverse.get(rel)
            layer = self._layer(rel)
            role = self._role(rel, canonical_for, group_ids, incoming.get(rel, 0), connected)
            modules.append(
                ModuleRecord(
                    module_path=rel,
                    module_name=path.stem,
                    purpose=self._purpose(text, path.stem),
                    layer=layer,
                    ownership=self._ownership(layer),
                    role=role,
                    canonical_for=canonical_for,
                    duplicate_group_ids=group_ids,
                    tae_outputs=sorted(self._tae_outputs(text)),
                    is_runner=self._is_runner(rel, text),
                    is_demo=rel.startswith("tae_phase") and rel.endswith("_demo.py"),
                    incoming_refs=incoming.get(rel, 0),
                    outgoing_refs=outgoing.get(rel, 0),
                )
            )

        unused = sorted(m.module_path for m in modules if m.role == ModuleRole.UNUSED)
        disconnected = sorted(
            m.module_path for m in modules if m.role == ModuleRole.DISCONNECTED
        )
        unreferenced = sorted(
            m.module_path
            for m in modules
            if m.incoming_refs == 0
            and not m.is_demo
            and m.role != ModuleRole.LIVE_CORE
            and not m.module_path.endswith("__init__.py")
        )
        competing = sorted(
            {
                m.module_path
                for m in modules
                if m.role == ModuleRole.COMPETING_RUNNER
                or (m.is_runner and m.module_path not in PRIMARY_RUNNERS)
            }
        )

        return MasterInventoryReport(
            modules=sorted(modules, key=lambda m: m.module_path),
            duplicate_groups=duplicate_groups,
            ownership_matrix=self._ownership_matrix(modules),
            canonical_modules=dict(CANONICAL_MODULES),
            competing_runners=competing,
            unused_modules=unused,
            disconnected_modules=disconnected,
            unreferenced_modules=unreferenced,
            total_modules=len(modules),
        )

    def _discover_python_files(self) -> list[Path]:
        found: set[Path] = set()
        for rel_root in SCAN_ROOTS:
            root_path = self._root / rel_root
            if root_path.is_dir():
                for py in root_path.rglob("*.py"):
                    if not any(part in EXCLUDE_DIR_NAMES for part in py.parts):
                        found.add(py)
        for rel_file in SCAN_FILES:
            full = self._root / rel_file
            if full.is_file():
                found.add(full)
        for demo in self._root.glob("tae_phase*.py"):
            found.add(demo)
        return sorted(found)

    @staticmethod
    def _purpose(text: str, fallback: str) -> str:
        doc = ast.get_docstring(ast.parse(text)) or ""
        doc = " ".join(line.strip() for line in doc.splitlines() if line.strip())
        return doc[:200] if doc else fallback.replace("_", " ")

    @staticmethod
    def _tae_outputs(text: str) -> set[str]:
        outputs: set[str] = set()
        for match in re.finditer(r'Path\(\s*["\'](tae_[^"\']+)["\']\s*\)', text):
            outputs.add(match.group(1))
        for match in re.finditer(r'["\'](tae_[^"\']+\.(?:json|txt))["\']', text):
            outputs.add(match.group(1))
        return outputs

    @staticmethod
    def _layer(rel_path: str) -> str:
        if rel_path.startswith("core/"):
            return "live_core"
        if rel_path.startswith("integration_layer/"):
            return "integration_layer"
        if rel_path.startswith("research_core/runtime/"):
            return "runtime"
        if rel_path.startswith("research_core/orchestrator/"):
            return "orchestrator"
        if rel_path.startswith("research_core/strategy_evolution/"):
            return "strategy_evolution"
        if rel_path.startswith("research_core/evidence_engine/"):
            return "evidence_engine"
        if rel_path.startswith("research_core/accounting/"):
            return "accounting"
        if rel_path.startswith("research_core/simulation_lab/"):
            return "simulation_lab"
        if rel_path.startswith("research_core/discovery/") or rel_path.startswith(
            "research_core/hypothesis/"
        ):
            return "discovery_hypothesis"
        if rel_path.startswith("research_core/governance/"):
            return "governance"
        if rel_path.startswith("research_core/entry_analysis/") or rel_path.startswith(
            "research_core/exit_analysis/"
        ) or rel_path.startswith("research_core/profit_attribution/") or rel_path.startswith(
            "research_core/score_decomposition/"
        ) or rel_path.startswith("research_core/statistical_validation/"):
            return "analysis_phases"
        if rel_path.startswith("tools/"):
            return "tools"
        if rel_path.startswith("config/"):
            return "config"
        if rel_path.endswith("_demo.py"):
            return "demo"
        return "research_other"

    @staticmethod
    def _ownership(layer: str) -> str:
        return OWNERSHIP_MATRIX.get(layer, "Research Pipeline")

    @staticmethod
    def _is_runner(rel_path: str, text: str) -> bool:
        if "def run(" in text or "def build(" in text or "def evaluate(" in text:
            if any(
                token in rel_path
                for token in ("runner", "orchestrator", "workflow", "engine", "demo")
            ):
                return True
        return bool(re.search(r"(Runner|Orchestrator|WorkflowEngine)", text))

    def _duplicate_groups(self, paths: list[Path]) -> list[DuplicateGroup]:
        rel_paths = [p.relative_to(self._root).as_posix() for p in paths]
        groups: list[DuplicateGroup] = []
        for group_id, spec in DUPLICATE_THEMES.items():
            patterns = spec["patterns"]
            matched = [
                rel
                for rel in rel_paths
                if any(re.search(pat, rel) for pat in patterns)
            ]
            if len(matched) >= 2:
                groups.append(
                    DuplicateGroup(
                        group_id=group_id,
                        theme=str(spec["theme"]),
                        module_paths=sorted(matched),
                        canonical_module=str(spec["canonical"]),
                        connect_recommendation=str(spec["connect"]),
                    )
                )
        return groups

    @staticmethod
    def _groups_for(rel_path: str, groups: list[DuplicateGroup]) -> list[str]:
        return [g.group_id for g in groups if rel_path in g.module_paths]

    def _role(
        self,
        rel_path: str,
        canonical_for: str | None,
        group_ids: list[str],
        incoming: int,
        connected: set[str],
    ) -> ModuleRole:
        if canonical_for:
            return ModuleRole.CANONICAL
        if rel_path in PRIMARY_RUNNERS:
            return ModuleRole.PRIMARY_RUNNER
        if rel_path.endswith("_demo.py") and rel_path.startswith("tae_phase"):
            if rel_path not in (
                "tae_phase8_ecosystem_orchestrator_demo.py",
                "tae_phase9_runtime_foundation_demo.py",
            ):
                return ModuleRole.COMPETING_RUNNER
            return ModuleRole.DEMO
        if rel_path.startswith("core/") and "_before_" not in rel_path:
            return ModuleRole.LIVE_CORE
        if rel_path.endswith("_report.py"):
            return ModuleRole.REPORT_ONLY
        if rel_path.endswith("__init__.py"):
            return ModuleRole.STANDARD
        if incoming == 0 and "demo" not in rel_path and not rel_path.startswith("core/"):
            if rel_path not in connected:
                return ModuleRole.DISCONNECTED
            return ModuleRole.UNUSED
        if rel_path not in connected and incoming == 0:
            return ModuleRole.DISCONNECTED
        if canonical_for is None and group_ids and rel_path not in PRIMARY_RUNNERS:
            for gid in group_ids:
                spec = DUPLICATE_THEMES.get(gid, {})
                if rel_path != spec.get("canonical"):
                    return ModuleRole.VIEW_ONLY
        return ModuleRole.STANDARD

    @staticmethod
    def _ownership_matrix(modules: list[ModuleRecord]) -> list[OwnershipEntry]:
        by_layer: dict[str, list[ModuleRecord]] = {}
        for module in modules:
            by_layer.setdefault(module.layer, []).append(module)
        entries: list[OwnershipEntry] = []
        for layer in sorted(by_layer):
            group = by_layer[layer]
            entries.append(
                OwnershipEntry(
                    domain=layer,
                    owner=group[0].ownership if group else "Unknown",
                    module_count=len(group),
                    canonical_modules=sorted(
                        m.module_path for m in group if m.role == ModuleRole.CANONICAL
                    ),
                )
            )
        return entries


class MasterInventoryStore:
    def persist(self, report: MasterInventoryReport) -> Path:
        INVENTORY_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return INVENTORY_JSON

    def persist_txt(self, report: MasterInventoryReport) -> Path:
        INVENTORY_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return INVENTORY_TXT
