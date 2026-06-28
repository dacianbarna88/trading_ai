"""
Continuous Strategy Simulation Lab report — Phase VII

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

logger = logging.getLogger(__name__)


def _round_num(value: float, digits: int = 2) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


DEFAULT_JSON_PATH = Path("tae_continuous_strategy_simulation_lab.json")
DEFAULT_TXT_PATH = Path("tae_continuous_strategy_simulation_lab.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_continuous_strategy_simulation_lab"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class SimulationLabVerdict(str, Enum):
    CONTINUOUS_SIMULATION_LAB_READY = "CONTINUOUS_SIMULATION_LAB_READY"


@dataclass
class StrategyMetrics:
    strategy_id: str
    label: str
    description: str
    trades: int
    closed_trades: int
    total_pnl: float
    avg_pnl: float
    median_pnl: float
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "label": self.label,
            "description": self.description,
            "trades": self.trades,
            "closed_trades": self.closed_trades,
            "total_pnl": _round_num(self.total_pnl, 2),
            "avg_pnl": _round_num(self.avg_pnl, 2),
            "median_pnl": _round_num(self.median_pnl, 2),
            "win_rate": _round_num(self.win_rate, 2),
            "gross_profit": _round_num(self.gross_profit, 2),
            "gross_loss": _round_num(self.gross_loss, 2),
            "profit_factor": _round_num(self.profit_factor, 4),
            "expectancy": _round_num(self.expectancy, 2),
        }


@dataclass
class StrategyRanking:
    rank: int
    strategy_id: str
    metric: str
    metric_value: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "strategy_id": self.strategy_id,
            "metric": self.metric,
            "metric_value": _round_num(self.metric_value, 4),
        }


@dataclass
class SimulationLabReport:
    verdict: SimulationLabVerdict
    strategies: list[StrategyMetrics]
    best_strategy_by_total_pnl: str
    best_strategy_by_profit_factor: str
    strategy_rankings: list[StrategyRanking]
    baseline_total_pnl: float
    buy_rows_total: int
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
            "best_strategy_by_total_pnl": self.best_strategy_by_total_pnl,
            "best_strategy_by_profit_factor": self.best_strategy_by_profit_factor,
            "baseline_total_pnl": _round_num(self.baseline_total_pnl, 2),
            "buy_rows_total": self.buy_rows_total,
            "pipeline_reference": self.pipeline_reference,
            "strategies": [s.to_dict() for s in self.strategies],
            "strategy_rankings": [r.to_dict() for r in self.strategy_rankings],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE CONTINUOUS STRATEGY SIMULATION LAB =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"BUY rows în portfolio.csv: {self.buy_rows_total}",
            f"Baseline total PnL: ${self.baseline_total_pnl:,.2f}",
            "",
            f"Cel mai bun (total PnL): {self.best_strategy_by_total_pnl}",
            f"Cel mai bun (profit factor): {self.best_strategy_by_profit_factor}",
            "",
            "===== STRATEGII SIMULATE =====",
        ]
        for strategy in self.strategies:
            lines.extend([
                f"--- {strategy.strategy_id} ---",
                f"  {strategy.description}",
                f"  Trades: {strategy.trades} ({strategy.closed_trades} închise)",
                f"  Total PnL: ${strategy.total_pnl:,.2f} | "
                f"avg ${strategy.avg_pnl:,.2f} | median ${strategy.median_pnl:,.2f}",
                f"  Win rate: {strategy.win_rate:.1f}% | "
                f"PF {strategy.profit_factor:.4f} | expectancy ${strategy.expectancy:,.2f}",
                f"  Gross +${strategy.gross_profit:,.2f} / -${strategy.gross_loss:,.2f}",
                "",
            ])
        lines.append("===== CLASAMENT =====")
        current_metric = ""
        for row in self.strategy_rankings:
            if row.metric != current_metric:
                current_metric = row.metric
                lines.append(f"  [{current_metric}]")
            lines.append(f"    {row.rank}. {row.strategy_id} ({row.metric_value})")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — simulare read-only.",
            "",
        ])
        return "\n".join(lines)


class SimulationLabReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: SimulationLabReport) -> Path:
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

    def persist_txt(self, report: SimulationLabReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
