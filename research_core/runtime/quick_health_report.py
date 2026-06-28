"""
Quick Health Check report — Phase IX Sprint IX.4

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

REPORT_JSON = Path("tae_quick_health_check.json")
REPORT_TXT = Path("tae_quick_health_check.txt")
SCHEMA_NAME = "tae_quick_health_check"


class QuickHealthVerdict(str, Enum):
    TAE_QUICK_HEALTH_READY = "TAE_QUICK_HEALTH_READY"
    TAE_QUICK_HEALTH_READY_WITH_WARNINGS = "TAE_QUICK_HEALTH_READY_WITH_WARNINGS"
    TAE_QUICK_HEALTH_NOT_READY = "TAE_QUICK_HEALTH_NOT_READY"


@dataclass
class QuickHealthCheckItem:
    check_id: str
    status: str
    message: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "check_id": self.check_id,
            "status": self.status,
            "message": self.message,
        }
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class QuickHealthReport:
    safety_banner: str
    verdict: QuickHealthVerdict
    checks: list[QuickHealthCheckItem]
    warnings: list[str]
    runtime_health_status: str
    runtime_verdict: str | None
    runtime_issues: list[str]
    missing_connections: list[str]
    orchestrator_verdict: str | None
    top_ranked_strategy_id: str | None
    paper_tracking_summary: str | None
    accounting_integration_status: str | None
    evidence_integration_status: str | None
    contract_layer_status: str | None
    adapter_layer_status: str | None
    git_status: str
    protected_files_unchanged: bool
    live_ops_summary: dict[str, Any]
    canonical_artifacts: dict[str, bool]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict.value,
            "checks": [check.to_dict() for check in self.checks],
            "warnings": list(self.warnings),
            "runtime_health_status": self.runtime_health_status,
            "runtime_verdict": self.runtime_verdict,
            "runtime_issues": list(self.runtime_issues),
            "missing_connections": list(self.missing_connections),
            "orchestrator_verdict": self.orchestrator_verdict,
            "top_ranked_strategy_id": self.top_ranked_strategy_id,
            "paper_tracking_summary": self.paper_tracking_summary,
            "accounting_integration_status": self.accounting_integration_status,
            "evidence_integration_status": self.evidence_integration_status,
            "contract_layer_status": self.contract_layer_status,
            "adapter_layer_status": self.adapter_layer_status,
            "git_status": self.git_status,
            "protected_files_unchanged": self.protected_files_unchanged,
            "live_ops_summary": dict(self.live_ops_summary),
            "canonical_artifacts": dict(self.canonical_artifacts),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE OFFICIAL QUICK HEALTH CHECK — SPRINT IX.4 =====",
            "",
            f"1. Safety banner: {self.safety_banner}",
            "",
            f"2. Git status: {self.git_status}",
            "",
            f"3. Protected files unchanged: {self.protected_files_unchanged}",
            "",
            f"4. Runtime health verdict: {self.runtime_health_status}"
            + (f" ({self.runtime_verdict})" if self.runtime_verdict else ""),
            "",
            "5. Runtime missing connections / known backlog:",
        ]
        if self.missing_connections or self.runtime_issues:
            for issue in self.runtime_issues[:15]:
                lines.append(f"   - {issue}")
            for conn in self.missing_connections[:15]:
                lines.append(f"   - {conn}")
        else:
            lines.append("   none")
        lines.extend([
            "",
            f"6. Orchestrator verdict: {self.orchestrator_verdict or 'N/A'}",
            f"7. Strategy top-ranked candidate: {self.top_ranked_strategy_id or 'N/A'}",
            f"8. Paper tracking status: {self.paper_tracking_summary or 'N/A'}",
            f"9. Accounting integration status: {self.accounting_integration_status or 'N/A'}",
            f"10. Evidence integration status: {self.evidence_integration_status or 'N/A'}",
            f"11. Contract layer status: {self.contract_layer_status or 'N/A'}",
            f"12. Adapter layer status: {self.adapter_layer_status or 'N/A'}",
            "",
            "13. Bot process status (read-only):",
            f"    {self.live_ops_summary.get('bot_process', 'N/A')}",
            "",
            "14. Dashboard / Streamlit port status (read-only):",
            f"    {self.live_ops_summary.get('dashboard_process', 'N/A')}",
            "",
            "15. Latest live signal freshness:",
            f"    {self.live_ops_summary.get('live_signals_freshness', 'N/A')}",
            "",
            "16. Portfolio file readable:",
            f"    {self.live_ops_summary.get('portfolio_readable', 'N/A')}",
            "",
            "17. Logs readable:",
            f"    {self.live_ops_summary.get('logs_readable', 'N/A')}",
            "",
            "===== CHECK MATRIX =====",
        ])
        for check in self.checks:
            lines.append(f"   [{check.status}] {check.check_id}: {check.message}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"   • {warning}")
        lines.extend([
            "",
            "===== CANONICAL ARTIFACTS =====",
        ])
        for name, present in self.canonical_artifacts.items():
            lines.append(f"   {name}: {'OK' if present else 'MISSING'}")
        lines.extend([
            "",
            f"18. Final quick verdict: {self.verdict.value}",
            "",
            "Read-only quick health wrapper — no bot start/stop, no execution.",
            "",
        ])
        return "\n".join(lines)


class QuickHealthReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or REPORT_JSON
        self._txt_path = txt_path or REPORT_TXT

    def persist(self, report: QuickHealthReport) -> Path:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: QuickHealthReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
