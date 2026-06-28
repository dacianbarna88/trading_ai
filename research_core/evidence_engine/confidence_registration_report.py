"""
Confidence Registration Report — Phase IX Sprint IX.5D

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.evidence_engine.confidence_registration import (
    CONFIDENCE_RECALIBRATION_REPORT_PATH,
    build_confidence_registration,
    is_confidence_registration_resolved,
    is_confidence_wired_in_registry,
    load_canonical_confidence_recalibration_report,
)
from research_core.evidence_engine.evidence_report import (
    DEFAULT_JSON_PATH,
    SAFETY_BANNER,
)

REGISTRATION_JSON = Path("tae_confidence_registration.json")
REGISTRATION_TXT = Path("tae_confidence_registration.txt")


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
class ConfidenceRegistrationReport:
    safety_banner: str
    before_connection_status: str
    after_connection_status: str
    confidence_source: str
    confidence_source_available: bool
    registry_registration_status: dict[str, Any]
    evidence_engine_includes_confidence: bool
    runtime_backlog_resolved: bool
    quick_health_backlog_resolved: bool
    missing_optional_reports: list[str]
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_confidence_registration",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "before_connection_status": self.before_connection_status,
            "after_connection_status": self.after_connection_status,
            "confidence_source": self.confidence_source,
            "confidence_source_available": self.confidence_source_available,
            "registry_registration_status": dict(self.registry_registration_status),
            "evidence_engine_includes_confidence": self.evidence_engine_includes_confidence,
            "runtime_backlog_resolved": self.runtime_backlog_resolved,
            "quick_health_backlog_resolved": self.quick_health_backlog_resolved,
            "missing_optional_reports": list(self.missing_optional_reports),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        reg = self.registry_registration_status
        report = reg.get("confidence_report") or {}
        lines = [
            "===== TAE CONFIDENCE REGISTRATION — SPRINT IX.5D =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CONNECTION STATUS =====",
            f"Before: {self.before_connection_status}",
            f"After:  {self.after_connection_status}",
            "",
            f"Confidence source: {self.confidence_source}",
            f"Source report available: {self.confidence_source_available}",
            "",
            "===== REGISTRY REGISTRATION =====",
            f"  confidence_registered: {reg.get('confidence_registered')}",
            f"  confidence_status: {reg.get('confidence_status')}",
            f"  confidence_source: {reg.get('confidence_source')}",
            f"  confidence_last_refresh: {reg.get('confidence_last_refresh')}",
            f"  confidence_report.candidates_recalibrated: "
            f"{report.get('candidates_recalibrated')}",
            f"  confidence_report.top_candidate_after: {report.get('top_candidate_after')}",
            "",
            f"Evidence Engine report includes confidence state: "
            f"{self.evidence_engine_includes_confidence}",
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


class ConfidenceRegistrationAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        before_wired: bool,
        protected_ok: bool,
    ) -> ConfidenceRegistrationReport:
        after_wired = is_confidence_wired_in_registry(self._root)
        confidence_payload = load_canonical_confidence_recalibration_report(self._root)
        confidence_available = confidence_payload is not None
        registration = build_confidence_registration(self._root, confidence_payload)

        evidence_payload = _load_evidence_engine_report(self._root)
        engine_includes = False
        if evidence_payload:
            reg = evidence_payload.get("confidence_registration")
            engine_includes = isinstance(reg, dict) and bool(reg.get("confidence_registered"))

        backlog_resolved = is_confidence_registration_resolved(
            self._root,
            evidence_payload,
        )

        missing_optional: list[str] = []
        if not confidence_available:
            missing_optional.append(
                f"{CONFIDENCE_RECALIBRATION_REPORT_PATH.name} — run confidence recalibration demo"
            )

        before_status = "WIRED_TO_REGISTRY" if before_wired else "NOT_WIRED_TO_REGISTRY"
        after_status = "WIRED_TO_REGISTRY" if after_wired else "NOT_WIRED_TO_REGISTRY"

        if not protected_ok:
            verdict = "CONFIDENCE_REGISTRATION_FAILED_PROTECTED_FILE_MODIFIED"
        elif not after_wired or not engine_includes:
            verdict = "CONFIDENCE_REGISTRATION_INCOMPLETE"
        elif not confidence_available:
            verdict = "CONFIDENCE_REGISTRATION_COMPLETE_WITH_MISSING_SOURCE_REPORT"
        elif backlog_resolved:
            verdict = "CONFIDENCE_REGISTRATION_COMPLETE"
        else:
            verdict = "CONFIDENCE_REGISTRATION_INCOMPLETE"

        return ConfidenceRegistrationReport(
            safety_banner=SAFETY_BANNER,
            before_connection_status=before_status,
            after_connection_status=after_status,
            confidence_source=str(CONFIDENCE_RECALIBRATION_REPORT_PATH.name),
            confidence_source_available=confidence_available,
            registry_registration_status=registration,
            evidence_engine_includes_confidence=engine_includes,
            runtime_backlog_resolved=backlog_resolved,
            quick_health_backlog_resolved=backlog_resolved,
            missing_optional_reports=missing_optional,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )

    def persist(self, report: ConfidenceRegistrationReport) -> dict[str, Path]:
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
