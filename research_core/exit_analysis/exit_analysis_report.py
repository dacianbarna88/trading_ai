"""
Exit counterfactual analysis report — Phase VII Sprint A2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only counterfactual exit analysis — no strategy or portfolio changes.
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

DEFAULT_EXIT_JSON_PATH = Path("tae_exit_counterfactual.json")
DEFAULT_EXIT_TXT_PATH = Path("tae_exit_counterfactual.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_exit_counterfactual"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"
HORIZONS = (1, 3, 5, 10, 20)


class ExitVerdict(str, Enum):
    EXITS_TOO_EARLY = "EXITS_TOO_EARLY"
    EXITS_TOO_LATE = "EXITS_TOO_LATE"
    EXITS_APPROXIMATELY_OPTIMAL = "EXITS_APPROXIMATELY_OPTIMAL"


class RecommendationRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGHER = "HIGHER"


@dataclass
class HorizonCounterfactual:
    horizon_days: int
    exit_date: str
    exit_price: float
    counterfactual_pnl: float
    delta_vs_actual: float
    data_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon_days": self.horizon_days,
            "exit_date": self.exit_date,
            "exit_price": _round_num(self.exit_price, 4),
            "counterfactual_pnl": _round_num(self.counterfactual_pnl, 2),
            "delta_vs_actual": _round_num(self.delta_vs_actual, 2),
            "data_complete": self.data_complete,
        }


@dataclass
class ClosedSellAnalysis:
    ticker: str
    region: str
    exit_category: str
    signal: str
    reason: str
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    shares: float
    actual_execution_pnl: float
    counterfactuals: list[HorizonCounterfactual]
    price_fetch_ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "region": self.region,
            "exit_category": self.exit_category,
            "signal": self.signal,
            "reason": self.reason,
            "buy_date": self.buy_date,
            "sell_date": self.sell_date,
            "buy_price": round(self.buy_price, 4),
            "sell_price": round(self.sell_price, 4),
            "shares": round(self.shares, 6),
            "actual_execution_pnl": round(self.actual_execution_pnl, 2),
            "counterfactuals": [c.to_dict() for c in self.counterfactuals],
            "price_fetch_ok": self.price_fetch_ok,
        }


@dataclass
class HorizonAggregate:
    horizon_days: int
    total_extra_profit: float
    avg_extra_return_pct: float
    median_extra_return_pct: float
    pct_improved: float
    pct_worse: float
    analyzed_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon_days": self.horizon_days,
            "total_extra_profit": round(self.total_extra_profit, 2),
            "avg_extra_return_pct": round(self.avg_extra_return_pct, 4),
            "median_extra_return_pct": round(self.median_extra_return_pct, 4),
            "pct_improved": round(self.pct_improved, 2),
            "pct_worse": round(self.pct_worse, 2),
            "analyzed_count": self.analyzed_count,
        }


@dataclass
class BucketDelta:
    bucket: str
    horizon_days: int
    total_delta: float
    trade_count: int
    avg_delta: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "horizon_days": self.horizon_days,
            "total_delta": round(self.total_delta, 2),
            "trade_count": self.trade_count,
            "avg_delta": round(self.avg_delta, 2),
        }


@dataclass
class RankedExit:
    ticker: str
    sell_date: str
    exit_category: str
    actual_pnl: float
    delta_at_5d: float
    sell_price: float
    price_at_5d: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sell_date": self.sell_date,
            "exit_category": self.exit_category,
            "actual_pnl": _round_num(self.actual_pnl, 2),
            "delta_at_5d": _round_num(self.delta_at_5d, 2),
            "sell_price": _round_num(self.sell_price, 4),
            "price_at_5d": _round_num(self.price_at_5d, 4),
            "reason": self.reason,
        }


@dataclass
class ExitRecommendation:
    risk_level: RecommendationRisk
    title: str
    description: str
    implementation_status: str = "NOT_IMPLEMENTED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "title": self.title,
            "description": self.description,
            "implementation_status": self.implementation_status,
        }


@dataclass
class ExitCounterfactualReport:
    verdict: ExitVerdict
    sells_analyzed: int
    sells_with_price_data: int
    horizon_aggregates: list[HorizonAggregate]
    by_exit_reason: list[BucketDelta]
    by_region: list[BucketDelta]
    by_ticker: list[BucketDelta]
    top_left_money_on_table: list[RankedExit]
    top_protected_capital: list[RankedExit]
    sells: list[ClosedSellAnalysis]
    recommendations: list[ExitRecommendation]
    primary_horizon_days: int
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "sells_analyzed": self.sells_analyzed,
            "sells_with_price_data": self.sells_with_price_data,
            "primary_horizon_days": self.primary_horizon_days,
            "horizon_aggregates": [h.to_dict() for h in self.horizon_aggregates],
            "by_exit_reason": [b.to_dict() for b in self.by_exit_reason],
            "by_region": [b.to_dict() for b in self.by_region],
            "by_ticker": [b.to_dict() for b in self.by_ticker],
            "top_left_money_on_table": [r.to_dict() for r in self.top_left_money_on_table],
            "top_protected_capital": [r.to_dict() for r in self.top_protected_capital],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "sells": [s.to_dict() for s in self.sells],
        }

    def format_text(self) -> str:
        lines = [
            "===== ANALIZĂ CONTRAFACTUALĂ IEȘIRI — TAE FAZA VII A2 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"SELL-uri analizate: {self.sells_analyzed} ({self.sells_with_price_data} cu date preț)",
            "",
            "===== PROFIT SUPLIMENTAR TOTAL (delta vs SELL real) =====",
        ]
        for h in self.horizon_aggregates:
            lines.append(
                f"  +{h.horizon_days:2d} zile: ${h.total_extra_profit:>10,.2f} | "
                f"avg {h.avg_extra_return_pct:+.2f}% | "
                f"median {h.median_extra_return_pct:+.2f}% | "
                f"îmbunătățit {h.pct_improved:.1f}% | "
                f"mai rău {h.pct_worse:.1f}%"
            )
        lines.extend(["", "===== PE MOTIV IEȘIRE (+5 zile) ====="])
        for b in sorted(
            [x for x in self.by_exit_reason if x.horizon_days == self.primary_horizon_days],
            key=lambda x: x.total_delta,
            reverse=True,
        ):
            lines.append(
                f"  {b.bucket:18s} ${b.total_delta:>10,.2f} "
                f"({b.trade_count} tranzacții, avg ${b.avg_delta:,.2f})"
            )
        lines.extend(["", "===== PE REGIUNE (+5 zile) ====="])
        for b in sorted(
            [x for x in self.by_region if x.horizon_days == self.primary_horizon_days],
            key=lambda x: x.total_delta,
            reverse=True,
        ):
            lines.append(
                f"  {b.bucket:8s} ${b.total_delta:>10,.2f} "
                f"({b.trade_count} tranzacții, avg ${b.avg_delta:,.2f})"
            )
        lines.extend(["", "===== TOP 10 — BANI LĂSAȚI PE MASĂ (+5 zile) ====="])
        for idx, r in enumerate(self.top_left_money_on_table, start=1):
            lines.append(
                f"  {idx:2d}. {r.sell_date[:10]} {r.ticker:8s} [{r.exit_category}] "
                f"delta +${r.delta_at_5d:,.2f} (PnL real ${r.actual_pnl:,.2f})"
            )
        lines.extend(["", "===== TOP 10 — CAPITAL PROTEJAT (+5 zile) ====="])
        for idx, r in enumerate(self.top_protected_capital, start=1):
            lines.append(
                f"  {idx:2d}. {r.sell_date[:10]} {r.ticker:8s} [{r.exit_category}] "
                f"delta ${r.delta_at_5d:,.2f} (PnL real ${r.actual_pnl:,.2f})"
            )
        lines.extend(["", "===== RECOMANDĂRI (NOT IMPLEMENTED — human review) ====="])
        for rec in self.recommendations:
            lines.append(f"  [{rec.risk_level.value}] {rec.title}")
            lines.append(f"      {rec.description}")
            lines.append(f"      Status: {rec.implementation_status}")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "NO LIVE FILES MODIFIED",
            "Fără instrucțiuni BUY/SELL — analiză contrafactuală read-only.",
            "",
        ])
        return "\n".join(lines)


class ExitAnalysisReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_EXIT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_EXIT_TXT_PATH

    def persist(self, report: ExitCounterfactualReport) -> Path:
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

    def persist_txt(self, report: ExitCounterfactualReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
