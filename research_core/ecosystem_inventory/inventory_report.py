"""
Ecosystem Inventory Audit report — Phase VIII B7

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)


def _round_num(value: float, digits: int = 2) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


DEFAULT_JSON_PATH = Path("tae_ecosystem_inventory_audit.json")
DEFAULT_TXT_PATH = Path("tae_ecosystem_inventory_audit.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_ecosystem_inventory_audit"


class MaturityLevel(str, Enum):
    L0_IDEA = "L0_IDEA"
    L1_PROTOTYPE = "L1_PROTOTYPE"
    L2_FUNCTIONAL = "L2_FUNCTIONAL"
    L3_VALIDATED = "L3_VALIDATED"
    L4_PAPER_TRACKING = "L4_PAPER_TRACKING"
    L5_INTEGRATION_READY = "L5_INTEGRATION_READY"
    L6_PRODUCTION_CANDIDATE = "L6_PRODUCTION_CANDIDATE"
    LEGACY = "LEGACY"


class RecommendedAction(str, Enum):
    KEEP = "KEEP"
    CONSOLIDATE = "CONSOLIDATE"
    CONNECT_TO_PIPELINE = "CONNECT_TO_PIPELINE"
    ARCHIVE_LATER = "ARCHIVE_LATER"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    DO_NOT_TOUCH = "DO_NOT_TOUCH"


class InventoryVerdict(str, Enum):
    ECOSYSTEM_INVENTORY_AUDIT_READY = "ECOSYSTEM_INVENTORY_AUDIT_READY"


@dataclass
class ModuleInventoryEntry:
    module_name: str
    path: str
    purpose: str
    maturity_level: MaturityLevel
    inputs: list[str]
    outputs: list[str]
    related_reports: list[str]
    possible_duplicates: list[str]
    overlaps_with: list[str]
    recommended_action: RecommendedAction
    is_active: bool
    is_legacy: bool
    research_only: bool
    integration_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "path": self.path,
            "purpose": self.purpose,
            "maturity_level": self.maturity_level.value,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "related_reports": list(self.related_reports),
            "possible_duplicates": list(self.possible_duplicates),
            "overlaps_with": list(self.overlaps_with),
            "recommended_action": self.recommended_action.value,
            "is_active": self.is_active,
            "is_legacy": self.is_legacy,
            "research_only": self.research_only,
            "integration_ready": self.integration_ready,
        }


@dataclass
class DuplicateGroup:
    group_id: str
    theme: str
    module_paths: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "theme": self.theme,
            "module_paths": list(self.module_paths),
            "recommendation": self.recommendation,
        }


@dataclass
class ConsolidationRecommendation:
    rank: int
    title: str
    modules: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "title": self.title,
            "modules": list(self.modules),
            "rationale": self.rationale,
        }


@dataclass
class EcosystemInventoryReport:
    verdict: InventoryVerdict
    modules: list[ModuleInventoryEntry]
    total_modules_scanned: int
    active_modules: int
    legacy_modules: int
    duplicate_groups: list[DuplicateGroup]
    top_consolidation_recommendations: list[ConsolidationRecommendation]
    do_not_rewrite: list[str]
    next_best_implementation: str
    missing_connections: list[str]
    protected_files_unchanged: bool
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "total_modules_scanned": self.total_modules_scanned,
            "active_modules": self.active_modules,
            "legacy_modules": self.legacy_modules,
            "duplicate_groups": [group.to_dict() for group in self.duplicate_groups],
            "top_consolidation_recommendations": [
                item.to_dict() for item in self.top_consolidation_recommendations
            ],
            "do_not_rewrite": list(self.do_not_rewrite),
            "next_best_implementation": self.next_best_implementation,
            "missing_connections": list(self.missing_connections),
            "protected_files_unchanged": self.protected_files_unchanged,
            "modules": [module.to_dict() for module in self.modules],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ECOSYSTEM INVENTORY & DUPLICATION AUDIT — FAZA VIII B7 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Total modules scanned: {self.total_modules_scanned}",
            f"Active modules: {self.active_modules}",
            f"Legacy modules: {self.legacy_modules}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== DUPLICATE GROUPS =====",
        ]
        for group in self.duplicate_groups:
            lines.append(f"- {group.group_id}: {group.theme}")
            for path in group.module_paths:
                lines.append(f"    {path}")
            lines.append(f"  → {group.recommendation}")
        lines.extend(["", "===== TOP CONSOLIDATION RECOMMENDATIONS ====="])
        for item in self.top_consolidation_recommendations:
            lines.append(f"{item.rank}. {item.title}")
            lines.append(f"   Modules: {', '.join(item.modules)}")
            lines.append(f"   {item.rationale}")
        lines.extend(["", "===== DO NOT REWRITE ====="])
        for path in self.do_not_rewrite:
            lines.append(f"  - {path}")
        lines.extend([
            "",
            f"Next best implementation: {self.next_best_implementation}",
            "",
            "===== MISSING CONNECTIONS =====",
        ])
        for conn in self.missing_connections:
            lines.append(f"  - {conn}")
        lines.extend(["", "===== MODULE INVENTORY (sample) ====="])
        for module in self.modules[:25]:
            lines.append(
                f"- {module.path} [{module.maturity_level.value}] "
                f"{module.recommended_action.value}"
            )
            lines.append(f"    {module.purpose[:120]}")
        if len(self.modules) > 25:
            lines.append(f"  ... and {len(self.modules) - 25} more modules (see JSON)")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "Read-only audit — no files deleted or rewritten.",
            "",
        ])
        return "\n".join(lines)


class EcosystemInventoryReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: EcosystemInventoryReport) -> Path:
        self._json_path.write_text(
            json.dumps(
                report.to_dict(),
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: EcosystemInventoryReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
