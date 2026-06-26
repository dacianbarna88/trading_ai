"""
Strategy Evolution Daily Runner report — Phase VIII B6

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


DEFAULT_JSON_PATH = Path("tae_strategy_evolution_daily_runner.json")
DEFAULT_TXT_PATH = Path("tae_strategy_evolution_daily_runner.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategy_evolution_daily_runner"


class DailyRunnerVerdict(str, Enum):
    STRATEGY_EVOLUTION_DAILY_RUNNER_READY = "STRATEGY_EVOLUTION_DAILY_RUNNER_READY"
    STRATEGY_EVOLUTION_DAILY_RUNNER_PARTIAL_FAILURE = (
        "STRATEGY_EVOLUTION_DAILY_RUNNER_PARTIAL_FAILURE"
    )


@dataclass
class DailyRunnerStepResult:
    step_name: str
    step_number: int
    verdict: str | None
    succeeded: bool
    output_json: str | None = None
    output_txt: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "step_number": self.step_number,
            "verdict": self.verdict,
            "succeeded": self.succeeded,
            "output_json": self.output_json,
            "output_txt": self.output_txt,
            "error": self.error,
        }


@dataclass
class PaperTrackingNeed:
    candidate_id: str
    tracking_status: str
    current_trades: int
    trades_needed: int
    tracking_note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "tracking_status": self.tracking_status,
            "current_trades": self.current_trades,
            "trades_needed": self.trades_needed,
            "tracking_note": self.tracking_note,
        }


@dataclass
class DailyRunnerReport:
    verdict: DailyRunnerVerdict
    steps: list[DailyRunnerStepResult]
    top_ranked_strategy_id: str | None
    top_ranked_strategy_score: float | None
    promotion_review_candidate_id: str | None
    paper_tracking_needs: list[PaperTrackingNeed]
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
            "steps": [step.to_dict() for step in self.steps],
            "top_ranked_strategy_id": self.top_ranked_strategy_id,
            "top_ranked_strategy_score": _round_num(self.top_ranked_strategy_score, 4)
            if self.top_ranked_strategy_score is not None
            else None,
            "promotion_review_candidate_id": self.promotion_review_candidate_id,
            "paper_tracking_needs": [need.to_dict() for need in self.paper_tracking_needs],
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE STRATEGY EVOLUTION DAILY RUNNER — FAZA VIII B6 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== PIPELINE STEPS =====",
        ]
        for step in self.steps:
            status = "OK" if step.succeeded else "FAILED"
            lines.append(
                f"{step.step_number}. {step.step_name} [{status}] "
                f"verdict={step.verdict or 'N/A'}"
            )
            if step.output_json:
                lines.append(f"   JSON: {step.output_json}")
            if step.output_txt:
                lines.append(f"   TXT:  {step.output_txt}")
            if step.error:
                lines.append(f"   Error: {step.error}")
        lines.extend([
            "",
            "===== SUMMARY =====",
            f"Top ranked strategy: {self.top_ranked_strategy_id or 'N/A'}",
        ])
        if self.top_ranked_strategy_score is not None:
            lines.append(f"Top ranking score: {self.top_ranked_strategy_score:.4f}")
        lines.append(
            f"Promotion review candidate: {self.promotion_review_candidate_id or 'None'}"
        )
        lines.extend(["", "Paper tracking needs:"])
        if self.paper_tracking_needs:
            for need in self.paper_tracking_needs:
                lines.append(
                    f"  {need.candidate_id}: {need.tracking_status} | "
                    f"trades={need.current_trades} need={need.trades_needed} | "
                    f"{need.tracking_note}"
                )
        else:
            lines.append("  None")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Daily runner is read-only — no trade execution.",
            "",
        ])
        return "\n".join(lines)


class DailyRunnerReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: DailyRunnerReport) -> Path:
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

    def persist_txt(self, report: DailyRunnerReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
