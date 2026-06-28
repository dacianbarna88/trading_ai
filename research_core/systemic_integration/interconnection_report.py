"""
Systemic Module Interconnection report — Phase IX C1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH = Path("tae_systemic_interconnection_map.json")
DEFAULT_TXT_PATH = Path("tae_systemic_interconnection_map.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_systemic_interconnection_map"


class ModuleRole(str, Enum):
    CANONICAL = "CANONICAL"
    VIEW_ONLY = "VIEW_ONLY"
    LEGACY_PLANNING_ONLY = "LEGACY_PLANNING_ONLY"
    DO_NOT_INVOKE_DIRECTLY = "DO_NOT_INVOKE_DIRECTLY"
    REPORT_ONLY = "REPORT_ONLY"


class ConflictRiskLevel(str, Enum):
    NONE = "NONE"
    CONFLICT_RISK = "CONFLICT_RISK"


class SystemicHarmonyVerdict(str, Enum):
    SYSTEMIC_INTERCONNECTION_READY = "SYSTEMIC_INTERCONNECTION_READY"
    SYSTEMIC_HARMONY_WITH_WARNINGS = "SYSTEMIC_HARMONY_WITH_WARNINGS"


@dataclass
class CanonicalResponsibility:
    responsibility: str
    canonical_module: str
    output_reports: list[str]
    role: ModuleRole = ModuleRole.CANONICAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "responsibility": self.responsibility,
            "canonical_module": self.canonical_module,
            "output_reports": list(self.output_reports),
            "role": self.role.value,
        }


@dataclass
class ModuleClassification:
    module_path: str
    role: ModuleRole
    responsibility: str | None
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "role": self.role.value,
            "responsibility": self.responsibility,
            "rationale": self.rationale,
        }


@dataclass
class ConflictWarning:
    conflict_id: str
    modules: list[str]
    risk_level: ConflictRiskLevel
    precedence: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "modules": list(self.modules),
            "risk_level": self.risk_level.value,
            "precedence": self.precedence,
            "description": self.description,
        }


@dataclass
class SystemicInterconnectionReport:
    verdict: SystemicHarmonyVerdict
    canonical_module_map: list[CanonicalResponsibility]
    module_classifications: list[ModuleClassification]
    duplicate_groups: list[dict[str, Any]]
    missing_connections: list[str]
    integration_rules: list[str]
    forbidden_actions: list[str]
    safe_orchestration_order: list[str]
    conflict_warnings: list[ConflictWarning]
    recommended_orchestration_chain: str
    subsystem_verdicts: dict[str, str | None]
    sources_loaded: dict[str, bool]
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
            "canonical_module_map": [item.to_dict() for item in self.canonical_module_map],
            "module_classifications": [
                item.to_dict() for item in self.module_classifications
            ],
            "duplicate_groups": list(self.duplicate_groups),
            "missing_connections": list(self.missing_connections),
            "integration_rules": list(self.integration_rules),
            "forbidden_actions": list(self.forbidden_actions),
            "safe_orchestration_order": list(self.safe_orchestration_order),
            "conflict_warnings": [item.to_dict() for item in self.conflict_warnings],
            "recommended_orchestration_chain": self.recommended_orchestration_chain,
            "subsystem_verdicts": dict(self.subsystem_verdicts),
            "sources_loaded": dict(self.sources_loaded),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE SYSTEMIC MODULE INTERCONNECTION — FAZA IX C1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CANONICAL MODULE MAP =====",
        ]
        for item in self.canonical_module_map:
            lines.append(f"- {item.responsibility}")
            lines.append(f"    Canonical: {item.canonical_module}")
            if item.output_reports:
                lines.append(f"    Reports: {', '.join(item.output_reports)}")
        lines.extend(["", "===== SAFE ORCHESTRATION ORDER ====="])
        for index, step in enumerate(self.safe_orchestration_order, start=1):
            lines.append(f"{index}. {step}")
        lines.extend([
            "",
            f"Recommended chain: {self.recommended_orchestration_chain}",
            "",
            "===== INTEGRATION RULES =====",
        ])
        for rule in self.integration_rules:
            lines.append(f"  - {rule}")
        lines.extend(["", "===== FORBIDDEN ACTIONS ====="])
        for action in self.forbidden_actions:
            lines.append(f"  - {action}")
        lines.extend(["", "===== CONFLICT WARNINGS ====="])
        for warning in self.conflict_warnings:
            lines.append(
                f"- {warning.conflict_id} [{warning.risk_level.value}]: "
                f"{warning.description}"
            )
            lines.append(f"  Precedence: {warning.precedence}")
        lines.extend(["", "===== MISSING CONNECTIONS ====="])
        for conn in self.missing_connections:
            lines.append(f"  - {conn}")
        lines.extend(["", "===== DUPLICATE GROUPS (from inventory) ====="])
        for group in self.duplicate_groups:
            lines.append(f"- {group.get('group_id')}: {group.get('theme')}")
        lines.extend([
            "",
            "===== VIEW / LEGACY CLASSIFICATIONS (sample) =====",
        ])
        for item in self.module_classifications[:20]:
            lines.append(f"  {item.module_path} → {item.role.value}")
        if len(self.module_classifications) > 20:
            lines.append(f"  ... and {len(self.module_classifications) - 20} more (see JSON)")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "Interconnection map is read-only — no module rewrites.",
            "",
        ])
        return "\n".join(lines)


class SystemicInterconnectionReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: SystemicInterconnectionReport) -> Path:
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

    def persist_txt(self, report: SystemicInterconnectionReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
