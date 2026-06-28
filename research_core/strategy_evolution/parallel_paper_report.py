"""
Parallel Paper Validator report — Phase VIII B2

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

from research_core.strategy_evolution.candidate_report import (
    CandidateStatus,
    PromotionReadiness,
    SAFETY_BANNER,
)

logger = logging.getLogger(__name__)


def _round_num(value: float, digits: int = 2) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


DEFAULT_JSON_PATH = Path("tae_parallel_paper_validation.json")
DEFAULT_TXT_PATH = Path("tae_parallel_paper_validation.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_parallel_paper_validation"


class ValidationStatus(str, Enum):
    BASELINE_REFERENCE = "BASELINE_REFERENCE"
    PAPER_TRACKING = "PAPER_TRACKING"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    OUTPERFORMS_BASELINE = "OUTPERFORMS_BASELINE"
    UNDERPERFORMS_BASELINE = "UNDERPERFORMS_BASELINE"
    PROMOTION_REVIEW_ELIGIBLE = "PROMOTION_REVIEW_ELIGIBLE"


class ValidatorVerdict(str, Enum):
    PARALLEL_PAPER_VALIDATOR_READY = "PARALLEL_PAPER_VALIDATOR_READY"


@dataclass
class PaperValidationResult:
    candidate_id: str
    status: CandidateStatus
    promotion_readiness: PromotionReadiness
    trades: int
    closed_trades: int
    open_trades: int
    total_pnl: float
    avg_pnl: float
    median_pnl: float
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float
    delta_vs_baseline_total_pnl: float
    delta_vs_baseline_expectancy: float
    beats_baseline_total_pnl: bool
    beats_baseline_profit_factor: bool
    beats_baseline_expectancy: bool
    validation_status: ValidationStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "promotion_readiness": self.promotion_readiness.value,
            "trades": self.trades,
            "closed_trades": self.closed_trades,
            "open_trades": self.open_trades,
            "total_pnl": _round_num(self.total_pnl, 2),
            "avg_pnl": _round_num(self.avg_pnl, 2),
            "median_pnl": _round_num(self.median_pnl, 2),
            "win_rate": _round_num(self.win_rate, 2),
            "gross_profit": _round_num(self.gross_profit, 2),
            "gross_loss": _round_num(self.gross_loss, 2),
            "profit_factor": _round_num(self.profit_factor, 4),
            "expectancy": _round_num(self.expectancy, 2),
            "delta_vs_baseline_total_pnl": _round_num(self.delta_vs_baseline_total_pnl, 2),
            "delta_vs_baseline_expectancy": _round_num(self.delta_vs_baseline_expectancy, 2),
            "beats_baseline_total_pnl": self.beats_baseline_total_pnl,
            "beats_baseline_profit_factor": self.beats_baseline_profit_factor,
            "beats_baseline_expectancy": self.beats_baseline_expectancy,
            "validation_status": self.validation_status.value,
        }


@dataclass
class ParallelPaperValidationReport:
    verdict: ValidatorVerdict
    validations: list[PaperValidationResult]
    baseline_candidate_id: str
    registry_verdict: str | None
    sources_loaded: dict[str, bool]
    pipeline_reference: dict[str, Any] | None = None
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "baseline_candidate_id": self.baseline_candidate_id,
            "registry_verdict": self.registry_verdict,
            "sources_loaded": dict(self.sources_loaded),
            "pipeline_reference": self.pipeline_reference,
            "validations": [v.to_dict() for v in self.validations],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE PARALLEL PAPER VALIDATOR — FAZA VIII B2 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Baseline: {self.baseline_candidate_id}",
            f"Registry: {self.registry_verdict or 'N/A'}",
            "",
            "===== VALIDARE PARALELĂ CANDIDAȚI =====",
        ]
        for result in self.validations:
            lines.extend([
                f"--- {result.candidate_id} ---",
                f"  Status: {result.status.value} | "
                f"Promotion: {result.promotion_readiness.value} | "
                f"Validation: {result.validation_status.value}",
                f"  Trades: {result.trades} ({result.closed_trades} închise, "
                f"{result.open_trades} deschise)",
                f"  Total PnL: ${result.total_pnl:,.2f} | "
                f"delta ${result.delta_vs_baseline_total_pnl:+,.2f}",
                f"  Win rate: {result.win_rate:.1f}% | PF {result.profit_factor:.4f} | "
                f"expectancy ${result.expectancy:,.2f} (delta "
                f"{result.delta_vs_baseline_expectancy:+,.2f})",
                f"  Beats baseline: PnL={result.beats_baseline_total_pnl} | "
                f"PF={result.beats_baseline_profit_factor} | "
                f"Exp={result.beats_baseline_expectancy}",
                "",
            ])
        lines.extend([
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — validare read-only.",
            "",
        ])
        return "\n".join(lines)


class ParallelPaperValidationReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: ParallelPaperValidationReport) -> Path:
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

    def persist_txt(self, report: ParallelPaperValidationReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
