"""
Evidence Gap Registration Report — Phase IX Sprint IX.5B

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Connect-only registration of Evidence Gap as canonical Evidence Registry feeder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.evidence_engine.evidence_gap_registration import (
    EVIDENCE_GAP_REPORT_PATH,
    build_evidence_gap_registration,
    is_evidence_gap_registration_resolved,
    is_evidence_gap_wired_in_registry,
    load_canonical_evidence_gap_report,
)
from research_core.evidence_engine.evidence_report import (
    DEFAULT_JSON_PATH,
    SAFETY_BANNER,
)


REGISTRATION_JSON = Path("tae_evidence_gap_registration.json")
REGISTRATION_TXT = Path("tae_evidence_gap_registration.txt")


def _load_evidence_engine_report(root: Path) -> dict[str, Any] | None:
    path = root / DEFAULT_JSON_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class EvidenceGapRegistrationReport:
    safety_banner: str
    before_connection_status: str
    after_connection_status: str
    evidence_gap_source_report: str
    evidence_gap_source_available: bool
    registry_registration_status: dict[str, Any]
    evidence_engine_includes_gap: bool
    runtime_backlog_resolved: bool
    quick_health_backlog_resolved: bool
    missing_optional_reports: list[str]
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_evidence_gap_registration",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "before_connection_status": self.before_connection_status,
            "after_connection_status": self.after_connection_status,
            "evidence_gap_source_report": self.evidence_gap_source_report,
            "evidence_gap_source_available": self.evidence_gap_source_available,
            "registry_registration_status": dict(self.registry_registration_status),
            "evidence_engine_includes_gap": self.evidence_engine_includes_gap,
            "runtime_backlog_resolved": self.runtime_backlog_resolved,
            "quick_health_backlog_resolved": self.quick_health_backlog_resolved,
            "missing_optional_reports": list(self.missing_optional_reports),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        reg = self.registry_registration_status
        lines = [
            "===== TAE EVIDENCE GAP REGISTRATION — SPRINT IX.5B =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CONNECTION STATUS =====",
            f"Before: {self.before_connection_status}",
            f"After:  {self.after_connection_status}",
            "",
            f"Evidence Gap source report: {self.evidence_gap_source_report}",
            f"Source report available: {self.evidence_gap_source_available}",
            "",
            "===== REGISTRY REGISTRATION =====",
            f"  evidence_gap_registered: {reg.get('evidence_gap_registered')}",
            f"  evidence_gap_status: {reg.get('evidence_gap_status')}",
            f"  evidence_gap_last_loaded: {reg.get('evidence_gap_last_loaded')}",
            f"  evidence_gap_warning_count: {reg.get('evidence_gap_warning_count')}",
            "",
            f"Evidence Engine report includes gap state: {self.evidence_engine_includes_gap}",
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


class EvidenceGapRegistrationAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        before_wired: bool,
        protected_ok: bool,
    ) -> EvidenceGapRegistrationReport:
        after_wired = is_evidence_gap_wired_in_registry(self._root)
        gap_payload = load_canonical_evidence_gap_report(self._root)
        gap_available = gap_payload is not None
        registration = build_evidence_gap_registration(self._root, gap_payload)

        evidence_payload = _load_evidence_engine_report(self._root)
        engine_includes = False
        if evidence_payload:
            reg = evidence_payload.get("evidence_gap_registration")
            engine_includes = isinstance(reg, dict) and bool(reg.get("evidence_gap_registered"))

        backlog_resolved = is_evidence_gap_registration_resolved(
            self._root,
            evidence_payload,
        )

        missing_optional: list[str] = []
        if not gap_available:
            missing_optional.append(
                f"{EVIDENCE_GAP_REPORT_PATH.name} — run evidence gap analyzer demo"
            )

        before_status = "WIRED_TO_REGISTRY" if before_wired else "NOT_WIRED_TO_REGISTRY"
        after_status = "WIRED_TO_REGISTRY" if after_wired else "NOT_WIRED_TO_REGISTRY"

        if not protected_ok:
            verdict = "EVIDENCE_GAP_REGISTRATION_FAILED_PROTECTED_FILE_MODIFIED"
        elif not after_wired or not engine_includes:
            verdict = "EVIDENCE_GAP_REGISTRATION_INCOMPLETE"
        elif not gap_available:
            verdict = "EVIDENCE_GAP_REGISTRATION_COMPLETE_WITH_MISSING_SOURCE_REPORT"
        elif backlog_resolved:
            verdict = "EVIDENCE_GAP_REGISTRATION_COMPLETE"
        else:
            verdict = "EVIDENCE_GAP_REGISTRATION_INCOMPLETE"

        return EvidenceGapRegistrationReport(
            safety_banner=SAFETY_BANNER,
            before_connection_status=before_status,
            after_connection_status=after_status,
            evidence_gap_source_report=str(EVIDENCE_GAP_REPORT_PATH.name),
            evidence_gap_source_available=gap_available,
            registry_registration_status=registration,
            evidence_engine_includes_gap=engine_includes,
            runtime_backlog_resolved=backlog_resolved,
            quick_health_backlog_resolved=backlog_resolved,
            missing_optional_reports=missing_optional,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )

    def persist(self, report: EvidenceGapRegistrationReport) -> dict[str, Path]:
        json_path = self._root / REGISTRATION_JSON
        txt_path = self._root / REGISTRATION_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"registration_json": json_path, "registration_txt": txt_path}


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
