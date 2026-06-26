"""
Continuous Strategy Ranking report — Phase VIII B3

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


DEFAULT_JSON_PATH = Path("tae_continuous_strategy_ranking.json")
DEFAULT_TXT_PATH = Path("tae_continuous_strategy_ranking.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_continuous_strategy_ranking"

WEIGHT_TOTAL_PNL_DELTA = 0.35
WEIGHT_PROFIT_FACTOR = 0.25
WEIGHT_EXPECTANCY_DELTA = 0.20
WEIGHT_WIN_RATE = 0.10
WEIGHT_SAMPLE_SIZE = 0.10

PROMOTION_SCORE_THRESHOLD = 0.70
PROMOTION_MIN_TRADES = 20
STRONG_CANDIDATE_SCORE_THRESHOLD = 0.60
STRONG_CANDIDATE_MIN_TRADES = 10
INSUFFICIENT_SAMPLE_MIN_TRADES = 10
SAMPLE_SIZE_CAP_TRADES = 20


class RankingDecision(str, Enum):
    BASELINE_REFERENCE = "BASELINE_REFERENCE"
    KEEP_TRACKING = "KEEP_TRACKING"
    STRONG_PAPER_CANDIDATE = "STRONG_PAPER_CANDIDATE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    PROMOTION_REVIEW_ELIGIBLE = "PROMOTION_REVIEW_ELIGIBLE"


class RankingVerdict(str, Enum):
    CONTINUOUS_STRATEGY_RANKING_READY = "CONTINUOUS_STRATEGY_RANKING_READY"


@dataclass
class StrategyRankingEntry:
    candidate_id: str
    validation_status: str
    trades: int
    total_pnl: float
    delta_vs_baseline_total_pnl: float
    profit_factor: float
    expectancy: float
    win_rate: float
    sample_size_factor: float
    ranking_score: float
    rank: int
    decision: RankingDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "validation_status": self.validation_status,
            "trades": self.trades,
            "total_pnl": _round_num(self.total_pnl, 2),
            "delta_vs_baseline_total_pnl": _round_num(self.delta_vs_baseline_total_pnl, 2),
            "profit_factor": _round_num(self.profit_factor, 4),
            "expectancy": _round_num(self.expectancy, 2),
            "win_rate": _round_num(self.win_rate, 2),
            "sample_size_factor": _round_num(self.sample_size_factor, 4),
            "ranking_score": _round_num(self.ranking_score, 4),
            "rank": self.rank,
            "decision": self.decision.value,
        }


@dataclass
class ContinuousStrategyRankingReport:
    verdict: RankingVerdict
    rankings: list[StrategyRankingEntry]
    baseline_candidate_id: str
    validation_verdict: str | None
    registry_verdict: str | None
    sources_loaded: dict[str, bool]
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
            "validation_verdict": self.validation_verdict,
            "registry_verdict": self.registry_verdict,
            "sources_loaded": dict(self.sources_loaded),
            "rankings": [entry.to_dict() for entry in self.rankings],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE CONTINUOUS STRATEGY RANKING — FAZA VIII B3 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Baseline: {self.baseline_candidate_id}",
            f"Validation: {self.validation_verdict or 'N/A'}",
            f"Registry: {self.registry_verdict or 'N/A'}",
            "",
            "===== CLASAMENT STRATEGII =====",
        ]
        for entry in sorted(self.rankings, key=lambda x: x.rank):
            lines.extend([
                f"#{entry.rank} {entry.candidate_id}",
                f"  Decision: {entry.decision.value} | "
                f"Validation: {entry.validation_status}",
                f"  Score: {entry.ranking_score:.4f} | "
                f"Sample factor: {entry.sample_size_factor:.4f}",
                f"  Trades: {entry.trades} | Total PnL: ${entry.total_pnl:,.2f} | "
                f"delta ${entry.delta_vs_baseline_total_pnl:+,.2f}",
                f"  PF {entry.profit_factor:.4f} | expectancy ${entry.expectancy:,.2f} | "
                f"win rate {entry.win_rate:.1f}%",
                "",
            ])
        lines.extend([
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — ranking read-only.",
            "",
        ])
        return "\n".join(lines)


class ContinuousStrategyRankingReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: ContinuousStrategyRankingReport) -> Path:
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

    def persist_txt(self, report: ContinuousStrategyRankingReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
