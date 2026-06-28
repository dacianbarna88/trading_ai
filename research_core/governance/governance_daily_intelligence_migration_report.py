"""
Governance Daily Intelligence Migration Report — Phase IX Sprint IX.5G

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.governance.governance_daily_intelligence_migration import (
    GOVERNANCE_MIGRATION_STATUS_REGISTERED,
    build_governance_modern_inputs_registration,
    is_governance_migration_resolved,
    is_governance_modern_inputs_wired,
)
from research_core.governance.governance_report import DEFAULT_JSON_PATH
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

MIGRATION_JSON = Path("tae_governance_daily_intelligence_migration.json")
MIGRATION_TXT = Path("tae_governance_daily_intelligence_migration.txt")


def _load_governance_report(root: Path) -> dict[str, Any] | None:
    path = root / DEFAULT_JSON_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class GovernanceDailyIntelligenceMigrationReport:
    safety_banner: str
    before_connection_status: str
    after_connection_status: str
    governance_modern_inputs: dict[str, Any]
    governance_report_includes_modern: bool
    runtime_backlog_resolved: bool
    quick_health_backlog_resolved: bool
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_governance_daily_intelligence_migration",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "before_connection_status": self.before_connection_status,
            "after_connection_status": self.after_connection_status,
            "governance_modern_inputs": dict(self.governance_modern_inputs),
            "governance_report_includes_modern": self.governance_report_includes_modern,
            "runtime_backlog_resolved": self.runtime_backlog_resolved,
            "quick_health_backlog_resolved": self.quick_health_backlog_resolved,
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        reg = self.governance_modern_inputs
        lines = [
            "===== TAE GOVERNANCE DAILY INTELLIGENCE MIGRATION — SPRINT IX.5G =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CONNECTION STATUS =====",
            f"Before: {self.before_connection_status}",
            f"After:  {self.after_connection_status}",
            "",
            "===== GOVERNANCE MODERN INPUTS =====",
            f"  governance_modern_inputs_registered: {reg.get('governance_modern_inputs_registered')}",
            f"  governance_modern_input_count: {reg.get('governance_modern_input_count')}",
            f"  governance_legacy_input_count: {reg.get('governance_legacy_input_count')}",
            f"  governance_legacy_fallback_only: {reg.get('governance_legacy_fallback_only')}",
            f"  governance_strategy_evolution_source: {reg.get('governance_strategy_evolution_source')}",
            f"  canonical_pipeline: {reg.get('canonical_pipeline')}",
            "",
            "Modern inputs loaded:",
        ]
        for name, loaded in (reg.get("modern_inputs_loaded") or {}).items():
            lines.append(f"  • {name}: {'yes' if loaded else 'no'}")
        lines.extend([
            "",
            f"Governance report includes modern registration: {self.governance_report_includes_modern}",
            f"Runtime backlog resolved: {self.runtime_backlog_resolved}",
            f"Quick Health backlog resolved: {self.quick_health_backlog_resolved}",
            "",
        ])
        return "\n".join(lines)


class GovernanceDailyIntelligenceMigrationAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        before_wired: bool,
        protected_ok: bool,
        sources_loaded: dict[str, bool] | None = None,
    ) -> GovernanceDailyIntelligenceMigrationReport:
        after_wired = is_governance_modern_inputs_wired(self._root)
        registration = build_governance_modern_inputs_registration(
            self._root,
            sources_loaded=sources_loaded,
        )

        governance_payload = _load_governance_report(self._root)
        report_includes = False
        if governance_payload:
            modern = governance_payload.get("governance_modern_inputs")
            report_includes = isinstance(modern, dict) and bool(
                modern.get("governance_modern_inputs_registered")
            )

        backlog_resolved = is_governance_migration_resolved(
            self._root,
            governance_payload,
        )

        before_status = "WIRED_TO_GOVERNANCE" if before_wired else "NOT_WIRED"
        after_status = "WIRED_TO_GOVERNANCE" if after_wired else "NOT_WIRED"

        if not protected_ok:
            verdict = "GOVERNANCE_DAILY_INTELLIGENCE_MIGRATION_FAILED_PROTECTED_FILE_MODIFIED"
        elif not after_wired or not report_includes:
            verdict = "GOVERNANCE_DAILY_INTELLIGENCE_MIGRATION_INCOMPLETE"
        elif (
            registration.get("governance_modern_inputs_registered")
            and registration.get("governance_modern_input_count", 0) > 0
            and backlog_resolved
        ):
            verdict = "GOVERNANCE_DAILY_INTELLIGENCE_MIGRATION_COMPLETE"
        else:
            verdict = "GOVERNANCE_DAILY_INTELLIGENCE_MIGRATION_INCOMPLETE"

        if (
            verdict == "GOVERNANCE_DAILY_INTELLIGENCE_MIGRATION_COMPLETE"
            and registration.get("governance_modern_inputs_registered")
        ):
            registration = {
                **registration,
                "governance_migration_status": GOVERNANCE_MIGRATION_STATUS_REGISTERED,
            }

        return GovernanceDailyIntelligenceMigrationReport(
            safety_banner=SAFETY_BANNER,
            before_connection_status=before_status,
            after_connection_status=after_status,
            governance_modern_inputs=registration,
            governance_report_includes_modern=report_includes,
            runtime_backlog_resolved=backlog_resolved,
            quick_health_backlog_resolved=backlog_resolved,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )

    def persist(
        self,
        report: GovernanceDailyIntelligenceMigrationReport,
    ) -> dict[str, Path]:
        json_path = self._root / MIGRATION_JSON
        txt_path = self._root / MIGRATION_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"migration_json": json_path, "migration_txt": txt_path}


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
