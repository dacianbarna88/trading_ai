"""
Full Ecosystem Run Report — Phase X Sprint X.1

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

DEFAULT_JSON_PATH = Path("tae_full_ecosystem_run.json")
DEFAULT_TXT_PATH = Path("tae_full_ecosystem_run.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_full_ecosystem_run"


class FullEcosystemRunVerdict(str, Enum):
    FULL_ECOSYSTEM_RUN_READY = "FULL_ECOSYSTEM_RUN_READY"
    FULL_ECOSYSTEM_RUN_READY_WITH_WARNINGS = "FULL_ECOSYSTEM_RUN_READY_WITH_WARNINGS"
    FULL_ECOSYSTEM_RUN_BLOCKED = "FULL_ECOSYSTEM_RUN_BLOCKED"


@dataclass
class FullEcosystemStepResult:
    step_number: int
    step_name: str
    module: str
    mode: str
    verdict: str | None
    succeeded: bool
    output_json: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "module": self.module,
            "mode": self.mode,
            "verdict": self.verdict,
            "succeeded": self.succeeded,
            "output_json": self.output_json,
            "error": self.error,
        }


@dataclass
class FullEcosystemRunReport:
    verdict: FullEcosystemRunVerdict
    steps: list[FullEcosystemStepResult]
    modules_invoked: list[str]
    modules_read_only: list[str]
    canonical_reports_generated: list[str]
    canonical_reports_read: list[str]
    portfolio_status: dict[str, Any]
    live_signals_freshness: str | None
    open_positions_summary: list[dict[str, Any]]
    integration_health: dict[str, Any]
    quick_health_pre_verdict: str | None
    quick_health_post_verdict: str | None
    protected_files_unchanged: bool
    warnings: list[str] = field(default_factory=list)
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "steps": [step.to_dict() for step in self.steps],
            "modules_invoked": list(self.modules_invoked),
            "modules_read_only": list(self.modules_read_only),
            "canonical_reports_generated": list(self.canonical_reports_generated),
            "canonical_reports_read": list(self.canonical_reports_read),
            "portfolio_status": dict(self.portfolio_status),
            "live_signals_freshness": self.live_signals_freshness,
            "open_positions_summary": list(self.open_positions_summary),
            "integration_health": dict(self.integration_health),
            "quick_health_pre_verdict": self.quick_health_pre_verdict,
            "quick_health_post_verdict": self.quick_health_post_verdict,
            "protected_files_unchanged": self.protected_files_unchanged,
            "warnings": list(self.warnings),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE FULL ECOSYSTEM RUN — SPRINT X.1 =====",
            "",
            f"Safety banner: {self.safety_mode}",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== QUICK HEALTH =====",
            f"Pre-check:  {self.quick_health_pre_verdict or 'N/A'}",
            f"Post-check: {self.quick_health_post_verdict or 'N/A'}",
            "",
            "===== INTEGRATION HEALTH =====",
        ]
        for key, value in self.integration_health.items():
            lines.append(f"  {key}: {value}")
        lines.extend([
            "",
            "===== PORTFOLIO & LIVE OPS (READ-ONLY) =====",
            f"Portfolio status: {self.portfolio_status}",
            f"Live signals: {self.live_signals_freshness or 'N/A'}",
            "",
            "Open positions summary:",
        ])
        if self.open_positions_summary:
            for pos in self.open_positions_summary[:15]:
                lines.append(
                    f"  • {pos.get('ticker', '?')} "
                    f"shares={pos.get('shares', '?')} "
                    f"value={pos.get('market_value', '?')}"
                )
        else:
            lines.append("  (none or unavailable)")
        lines.extend([
            "",
            "===== PIPELINE STEPS =====",
        ])
        for step in self.steps:
            status = "OK" if step.succeeded else "FAIL"
            lines.append(
                f"  {step.step_number}. [{status}] {step.step_name} "
                f"({step.mode}) — {step.verdict or step.error or 'N/A'}"
            )
        lines.extend([
            "",
            "===== MODULES INVOKED =====",
        ])
        for module in self.modules_invoked:
            lines.append(f"  • {module}")
        lines.extend([
            "",
            "===== MODULES READ-ONLY =====",
        ])
        for module in self.modules_read_only:
            lines.append(f"  • {module}")
        lines.extend([
            "",
            "===== CANONICAL REPORTS GENERATED =====",
        ])
        for path in self.canonical_reports_generated:
            lines.append(f"  • {path}")
        lines.extend([
            "",
            "===== CANONICAL REPORTS READ =====",
        ])
        for path in self.canonical_reports_read:
            lines.append(f"  • {path}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        lines.append("")
        return "\n".join(lines)


class FullEcosystemRunReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: FullEcosystemRunReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
