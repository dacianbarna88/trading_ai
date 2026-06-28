"""
Regional Validation Integration Report — Phase IX Sprint IX.5C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER
from research_core.strategy_evolution.promotion_gate_report import DEFAULT_JSON_PATH
from research_core.strategy_evolution.regional_validation_integration import (
    REGIONAL_VALIDATION_REPORT_PATH,
    build_regional_validation_registration,
    is_regional_validation_integration_resolved,
    is_regional_validation_wired_in_promotion_gate,
    load_canonical_regional_validation_report,
)

INTEGRATION_JSON = Path("tae_regional_validation_integration.json")
INTEGRATION_TXT = Path("tae_regional_validation_integration.txt")


def _load_promotion_gate_report(root: Path) -> dict[str, Any] | None:
    path = root / DEFAULT_JSON_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class RegionalValidationIntegrationReport:
    safety_banner: str
    before_connection_status: str
    after_connection_status: str
    regional_validation_source: str
    regional_validation_source_available: bool
    promotion_gate_registration_status: dict[str, Any]
    promotion_gate_includes_regional: bool
    runtime_backlog_resolved: bool
    quick_health_backlog_resolved: bool
    missing_optional_reports: list[str]
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_regional_validation_integration",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "before_connection_status": self.before_connection_status,
            "after_connection_status": self.after_connection_status,
            "regional_validation_source": self.regional_validation_source,
            "regional_validation_source_available": self.regional_validation_source_available,
            "promotion_gate_registration_status": dict(
                self.promotion_gate_registration_status
            ),
            "promotion_gate_includes_regional": self.promotion_gate_includes_regional,
            "runtime_backlog_resolved": self.runtime_backlog_resolved,
            "quick_health_backlog_resolved": self.quick_health_backlog_resolved,
            "missing_optional_reports": list(self.missing_optional_reports),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        reg = self.promotion_gate_registration_status
        lines = [
            "===== TAE REGIONAL VALIDATION INTEGRATION — SPRINT IX.5C =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CONNECTION STATUS =====",
            f"Before: {self.before_connection_status}",
            f"After:  {self.after_connection_status}",
            "",
            f"Regional validation source: {self.regional_validation_source}",
            f"Source report available: {self.regional_validation_source_available}",
            "",
            "===== PROMOTION GATE REGISTRATION =====",
            f"  regional_validation_registered: {reg.get('regional_validation_registered')}",
            f"  regional_validation_status: {reg.get('regional_validation_status')}",
            f"  regional_validation_source: {reg.get('regional_validation_source')}",
            f"  regional_validation_last_refresh: {reg.get('regional_validation_last_refresh')}",
            "",
            f"Promotion gate report includes regional state: "
            f"{self.promotion_gate_includes_regional}",
            f"Runtime backlog resolved: {self.runtime_backlog_resolved}",
            f"Quick Health backlog resolved: {self.quick_health_backlog_resolved}",
            "",
            "===== MISSING OPTIONAL REPORTS =====",
        ]
        if self.missing_optional_reports:
            for item in self.missing_optional_reports:
                lines.append(f"  • {item}")
        else:
            lines.append("  none")
        lines.append("")
        return "\n".join(lines)


class RegionalValidationIntegrationAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        before_wired: bool,
        protected_ok: bool,
    ) -> RegionalValidationIntegrationReport:
        after_wired = is_regional_validation_wired_in_promotion_gate(self._root)
        regional_payload = load_canonical_regional_validation_report(self._root)
        regional_available = regional_payload is not None
        registration = build_regional_validation_registration(
            self._root,
            regional_payload,
        )

        promotion_payload = _load_promotion_gate_report(self._root)
        gate_includes = False
        if promotion_payload:
            reg = promotion_payload.get("regional_validation_registration")
            gate_includes = isinstance(reg, dict) and bool(
                reg.get("regional_validation_registered")
            )

        backlog_resolved = is_regional_validation_integration_resolved(
            self._root,
            promotion_payload,
        )

        missing_optional: list[str] = []
        if not regional_available:
            missing_optional.append(
                f"{REGIONAL_VALIDATION_REPORT_PATH.name} — run regional validation demo"
            )

        before_status = "WIRED_TO_PROMOTION_GATE" if before_wired else "NOT_WIRED"
        after_status = "WIRED_TO_PROMOTION_GATE" if after_wired else "NOT_WIRED"

        if not protected_ok:
            verdict = "REGIONAL_VALIDATION_INTEGRATION_FAILED_PROTECTED_FILE_MODIFIED"
        elif not after_wired or not gate_includes:
            verdict = "REGIONAL_VALIDATION_INTEGRATION_INCOMPLETE"
        elif not regional_available:
            verdict = (
                "REGIONAL_VALIDATION_INTEGRATION_COMPLETE_WITH_MISSING_SOURCE_REPORT"
            )
        elif backlog_resolved:
            verdict = "REGIONAL_VALIDATION_INTEGRATION_COMPLETE"
        else:
            verdict = "REGIONAL_VALIDATION_INTEGRATION_INCOMPLETE"

        return RegionalValidationIntegrationReport(
            safety_banner=SAFETY_BANNER,
            before_connection_status=before_status,
            after_connection_status=after_status,
            regional_validation_source=str(REGIONAL_VALIDATION_REPORT_PATH.name),
            regional_validation_source_available=regional_available,
            promotion_gate_registration_status=registration,
            promotion_gate_includes_regional=gate_includes,
            runtime_backlog_resolved=backlog_resolved,
            quick_health_backlog_resolved=backlog_resolved,
            missing_optional_reports=missing_optional,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )

    def persist(self, report: RegionalValidationIntegrationReport) -> dict[str, Path]:
        json_path = self._root / INTEGRATION_JSON
        txt_path = self._root / INTEGRATION_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"integration_json": json_path, "integration_txt": txt_path}


def protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def verify_protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file() or full.stat().st_mtime != mtime:
            return False
    return True
