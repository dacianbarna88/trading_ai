"""
Phase V Legacy Retirement Report — Phase IX Sprint IX.5F

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
from research_core.strategy_evolution.daily_runner_report import DEFAULT_JSON_PATH
from research_core.strategy_evolution.phase_v_legacy_retirement import (
    LEGACY_STATUS_COMPATIBILITY_ONLY,
    build_phase_v_legacy_status,
    is_phase_v_legacy_retirement_resolved,
    is_phase_v_legacy_wired_in_daily_runner,
    scan_phase_v_runtime_consumers,
)

RETIREMENT_JSON = Path("tae_phase_v_legacy_retirement.json")
RETIREMENT_TXT = Path("tae_phase_v_legacy_retirement.txt")


def _load_daily_runner_report(root: Path) -> dict[str, Any] | None:
    path = root / DEFAULT_JSON_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class PhaseVLegacyRetirementReport:
    safety_banner: str
    before_connection_status: str
    after_connection_status: str
    legacy_phase_v_status: dict[str, Any]
    daily_runner_includes_legacy: bool
    runtime_backlog_resolved: bool
    quick_health_backlog_resolved: bool
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_phase_v_legacy_retirement",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "before_connection_status": self.before_connection_status,
            "after_connection_status": self.after_connection_status,
            "legacy_phase_v_status": dict(self.legacy_phase_v_status),
            "daily_runner_includes_legacy": self.daily_runner_includes_legacy,
            "runtime_backlog_resolved": self.runtime_backlog_resolved,
            "quick_health_backlog_resolved": self.quick_health_backlog_resolved,
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        legacy = self.legacy_phase_v_status
        lines = [
            "===== TAE PHASE V LEGACY RETIREMENT — SPRINT IX.5F =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CONNECTION STATUS =====",
            f"Before: {self.before_connection_status}",
            f"After:  {self.after_connection_status}",
            "",
            "===== LEGACY PHASE V STATUS =====",
            f"  legacy_phase_v_status: {legacy.get('legacy_phase_v_status')}",
            f"  legacy_phase_v_runtime_usage: {legacy.get('legacy_phase_v_runtime_usage')}",
            f"  legacy_phase_v_parallel_pipeline: {legacy.get('legacy_phase_v_parallel_pipeline')}",
            f"  canonical_pipeline: {legacy.get('canonical_pipeline')}",
            f"  phase_v_module: {legacy.get('phase_v_module')}",
            "",
            "Documented non-runtime consumers:",
        ]
        for consumer in legacy.get("legacy_phase_v_consumers") or []:
            lines.append(f"  • {consumer}")
        runtime_paths = legacy.get("legacy_phase_v_runtime_consumer_paths") or []
        if runtime_paths:
            lines.extend(["", "Runtime consumer paths (must be empty):"])
            for path in runtime_paths:
                lines.append(f"  • {path}")
        lines.extend([
            "",
            f"Daily runner includes legacy status: {self.daily_runner_includes_legacy}",
            f"Runtime backlog resolved: {self.runtime_backlog_resolved}",
            f"Quick Health backlog resolved: {self.quick_health_backlog_resolved}",
            "",
        ])
        return "\n".join(lines)


class PhaseVLegacyRetirementAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        before_wired: bool,
        protected_ok: bool,
    ) -> PhaseVLegacyRetirementReport:
        after_wired = is_phase_v_legacy_wired_in_daily_runner(self._root)
        legacy_status = build_phase_v_legacy_status(self._root)

        daily_runner_payload = _load_daily_runner_report(self._root)
        runner_includes = False
        if daily_runner_payload:
            legacy = daily_runner_payload.get("phase_v_legacy_status")
            runner_includes = isinstance(legacy, dict) and bool(
                legacy.get("legacy_phase_v_status")
            )

        backlog_resolved = is_phase_v_legacy_retirement_resolved(
            self._root,
            daily_runner_payload,
        )

        before_status = "WIRED_TO_DAILY_RUNNER" if before_wired else "NOT_WIRED"
        after_status = "WIRED_TO_DAILY_RUNNER" if after_wired else "NOT_WIRED"

        if not protected_ok:
            verdict = "PHASE_V_LEGACY_RETIREMENT_FAILED_PROTECTED_FILE_MODIFIED"
        elif not after_wired or not runner_includes:
            verdict = "PHASE_V_LEGACY_RETIREMENT_INCOMPLETE"
        elif legacy_status.get("legacy_phase_v_runtime_usage"):
            verdict = "PHASE_V_LEGACY_RETIREMENT_INCOMPLETE"
        elif (
            legacy_status.get("legacy_phase_v_status") == LEGACY_STATUS_COMPATIBILITY_ONLY
            and backlog_resolved
        ):
            verdict = "PHASE_V_LEGACY_RETIREMENT_COMPLETE"
        else:
            verdict = "PHASE_V_LEGACY_RETIREMENT_INCOMPLETE"

        return PhaseVLegacyRetirementReport(
            safety_banner=SAFETY_BANNER,
            before_connection_status=before_status,
            after_connection_status=after_status,
            legacy_phase_v_status=legacy_status,
            daily_runner_includes_legacy=runner_includes,
            runtime_backlog_resolved=backlog_resolved,
            quick_health_backlog_resolved=backlog_resolved,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )

    def persist(self, report: PhaseVLegacyRetirementReport) -> dict[str, Path]:
        json_path = self._root / RETIREMENT_JSON
        txt_path = self._root / RETIREMENT_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"retirement_json": json_path, "retirement_txt": txt_path}


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
