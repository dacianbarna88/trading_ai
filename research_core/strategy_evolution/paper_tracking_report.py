"""
Paper Tracking Log report — Phase VIII B5

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


DEFAULT_JSON_PATH = Path("tae_paper_tracking_log.json")
DEFAULT_TXT_PATH = Path("tae_paper_tracking_log.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_paper_tracking_log"

MIN_REQUIRED_TRADES = 20


class TrackingStatus(str, Enum):
    TRACKING_ACTIVE = "TRACKING_ACTIVE"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    BLOCKED = "BLOCKED"
    BASELINE_REFERENCE = "BASELINE_REFERENCE"


class PaperTrackingVerdict(str, Enum):
    PAPER_TRACKING_LOG_READY = "PAPER_TRACKING_LOG_READY"


@dataclass
class PaperTrackingEntry:
    candidate_id: str
    current_trades: int
    closed_trades: int
    open_trades: int
    min_required_trades: int
    trades_needed: int
    validation_status: str
    promotion_gate_decision: str
    ranking_score: float
    current_total_pnl: float
    profit_factor: float
    expectancy: float
    tracking_status: TrackingStatus
    sample_insufficient: bool
    tracking_note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "current_trades": self.current_trades,
            "closed_trades": self.closed_trades,
            "open_trades": self.open_trades,
            "min_required_trades": self.min_required_trades,
            "trades_needed": self.trades_needed,
            "validation_status": self.validation_status,
            "promotion_gate_decision": self.promotion_gate_decision,
            "ranking_score": _round_num(self.ranking_score, 4),
            "current_total_pnl": _round_num(self.current_total_pnl, 2),
            "profit_factor": _round_num(self.profit_factor, 4),
            "expectancy": _round_num(self.expectancy, 2),
            "tracking_status": self.tracking_status.value,
            "sample_insufficient": self.sample_insufficient,
            "tracking_note": self.tracking_note,
        }


@dataclass
class PaperTrackingLogReport:
    verdict: PaperTrackingVerdict
    entries: list[PaperTrackingEntry]
    baseline_candidate_id: str
    promotion_gate_verdict: str | None
    ranking_verdict: str | None
    validation_verdict: str | None
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
            "promotion_gate_verdict": self.promotion_gate_verdict,
            "ranking_verdict": self.ranking_verdict,
            "validation_verdict": self.validation_verdict,
            "sources_loaded": dict(self.sources_loaded),
            "pipeline_reference": self.pipeline_reference,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE PAPER TRACKING LOG — FAZA VIII B5 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Baseline: {self.baseline_candidate_id}",
            f"Promotion Gate: {self.promotion_gate_verdict or 'N/A'}",
            f"Ranking: {self.ranking_verdict or 'N/A'}",
            f"Validation: {self.validation_verdict or 'N/A'}",
            "",
            "===== PAPER TRACKING =====",
        ]
        for entry in self.entries:
            lines.extend([
                f"--- {entry.candidate_id} ---",
                f"  Status: {entry.tracking_status.value} | "
                f"Validation: {entry.validation_status}",
                f"  Promotion gate: {entry.promotion_gate_decision}",
                f"  Trades: {entry.current_trades} "
                f"({entry.closed_trades} închise, {entry.open_trades} deschise) | "
                f"Need {entry.trades_needed} more to reach {entry.min_required_trades}",
                f"  Ranking score: {entry.ranking_score:.4f} | "
                f"PnL ${entry.current_total_pnl:,.2f} | "
                f"PF {entry.profit_factor:.4f} | expectancy ${entry.expectancy:,.2f}",
            ])
            if entry.sample_insufficient:
                lines.append("  Sample insufficient — below minimum validation threshold.")
            lines.append(f"  Note: {entry.tracking_note}")
            lines.append("")
        lines.extend([
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Paper tracking log is read-only — no trade execution.",
            "",
        ])
        return "\n".join(lines)


class PaperTrackingLogReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: PaperTrackingLogReport) -> Path:
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

    def persist_txt(self, report: PaperTrackingLogReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
