"""
Score decomposition / Score 100+ anomaly report — Phase VII Sprint A4

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


DEFAULT_JSON_PATH = Path("tae_score_decomposition_anomaly.json")
DEFAULT_TXT_PATH = Path("tae_score_decomposition_anomaly.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_score_decomposition_anomaly"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"

PORTFOLIO_COMPONENT_COLUMNS = (
    "Momentum_Evidence_Score",
    "Trend_Evidence_Score",
    "Volume_Evidence_Score",
    "Risk_Evidence_Score",
    "Conflict_Evidence_Score",
    "Overall_Evidence_Score",
)

DOSSIER_COMPONENT_COLUMNS = PORTFOLIO_COMPONENT_COLUMNS


class ScoreAnomalyVerdict(str, Enum):
    SCORE_100_ANOMALY_CONFIRMED = "SCORE_100_ANOMALY_CONFIRMED"
    DATA_GAP_PREVENTS_ROOT_CAUSE = "DATA_GAP_PREVENTS_ROOT_CAUSE"
    SCORE_COMPONENT_OVERWEIGHT_SUSPECTED = "SCORE_COMPONENT_OVERWEIGHT_SUSPECTED"
    SCORE_100_NOT_STATISTICALLY_RELIABLE = "SCORE_100_NOT_STATISTICALLY_RELIABLE"


@dataclass
class CohortMetrics:
    cohort: str
    buy_count: int
    closed_count: int
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float
    average_pnl: float
    median_pnl: float
    winner_count: int
    loser_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort": self.cohort,
            "buy_count": self.buy_count,
            "closed_count": self.closed_count,
            "total_pnl": _round_num(self.total_pnl, 2),
            "realized_pnl": _round_num(self.realized_pnl, 2),
            "unrealized_pnl": _round_num(self.unrealized_pnl, 2),
            "win_rate": _round_num(self.win_rate, 2),
            "average_pnl": _round_num(self.average_pnl, 2),
            "median_pnl": _round_num(self.median_pnl, 2),
            "winner_count": self.winner_count,
            "loser_count": self.loser_count,
        }


@dataclass
class GroupAggregate:
    dimension: str
    bucket: str
    cohort: str
    buy_count: int
    total_pnl: float
    average_pnl: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "bucket": self.bucket,
            "cohort": self.cohort,
            "buy_count": self.buy_count,
            "total_pnl": _round_num(self.total_pnl, 2),
            "average_pnl": _round_num(self.average_pnl, 2),
        }


@dataclass
class BuyTradeRecord:
    buy_id: int
    ticker: str
    buy_date: str
    buy_price: float
    shares: float
    invested: float
    score: float
    cohort: str
    signal: str
    reason: str
    region: str
    closed: bool
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    dossier_matched: bool
    dossier_signal_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "buy_id": self.buy_id,
            "ticker": self.ticker,
            "buy_date": self.buy_date,
            "buy_price": _round_num(self.buy_price, 4),
            "shares": _round_num(self.shares, 6),
            "invested": _round_num(self.invested, 2),
            "score": _round_num(self.score, 2),
            "cohort": self.cohort,
            "signal": self.signal,
            "reason": self.reason,
            "region": self.region,
            "closed": self.closed,
            "realized_pnl": _round_num(self.realized_pnl, 2),
            "unrealized_pnl": _round_num(self.unrealized_pnl, 2),
            "total_pnl": _round_num(self.total_pnl, 2),
            "dossier_matched": self.dossier_matched,
            "dossier_signal_date": self.dossier_signal_date,
        }


@dataclass
class TraitSummary:
    trait: str
    count: int
    total_pnl: float
    examples: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trait": self.trait,
            "count": self.count,
            "total_pnl": _round_num(self.total_pnl, 2),
            "examples": self.examples,
        }


@dataclass
class ComponentAverages:
    cohort: str
    subset: str
    sample_count: int
    momentum: float | None
    trend: float | None
    volume: float | None
    risk: float | None
    conflict: float | None
    overall: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort": self.cohort,
            "subset": self.subset,
            "sample_count": self.sample_count,
            "Momentum_Evidence_Score": _round_num(self.momentum or 0, 2)
            if self.momentum is not None
            else None,
            "Trend_Evidence_Score": _round_num(self.trend or 0, 2)
            if self.trend is not None
            else None,
            "Volume_Evidence_Score": _round_num(self.volume or 0, 2)
            if self.volume is not None
            else None,
            "Risk_Evidence_Score": _round_num(self.risk or 0, 2)
            if self.risk is not None
            else None,
            "Conflict_Evidence_Score": _round_num(self.conflict or 0, 2)
            if self.conflict is not None
            else None,
            "Overall_Evidence_Score": _round_num(self.overall or 0, 2)
            if self.overall is not None
            else None,
        }


@dataclass
class ScoreDecompositionReport:
    verdict: ScoreAnomalyVerdict
    data_gaps: list[str]
    cohort_90_99: CohortMetrics
    cohort_100_plus: CohortMetrics
    cohort_delta_total_pnl: float
    cohort_delta_median_pnl: float
    dossier_match_count: int
    dossier_match_rate: float
    group_aggregates: list[GroupAggregate]
    score_100_loser_traits: list[TraitSummary]
    component_averages: list[ComponentAverages]
    buys: list[BuyTradeRecord]
    live_signals_reference_rows: int
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "data_gaps": self.data_gaps,
            "cohort_90_99": self.cohort_90_99.to_dict(),
            "cohort_100_plus": self.cohort_100_plus.to_dict(),
            "cohort_delta_total_pnl": _round_num(self.cohort_delta_total_pnl, 2),
            "cohort_delta_median_pnl": _round_num(self.cohort_delta_median_pnl, 2),
            "dossier_match_count": self.dossier_match_count,
            "dossier_match_rate": _round_num(self.dossier_match_rate, 2),
            "group_aggregates": [g.to_dict() for g in self.group_aggregates],
            "score_100_loser_traits": [t.to_dict() for t in self.score_100_loser_traits],
            "component_averages": [c.to_dict() for c in self.component_averages],
            "live_signals_reference_rows": self.live_signals_reference_rows,
            "buys": [b.to_dict() for b in self.buys],
        }

    def format_text(self) -> str:
        c90 = self.cohort_90_99
        c100 = self.cohort_100_plus
        lines = [
            "===== DECOMPUNERE SCOR / ANOMALIE SCORE 100+ — TAE FAZA VII A4 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
        ]
        if self.data_gaps:
            lines.append("Gap-uri date:")
            for gap in self.data_gaps:
                lines.append(f"  • {gap}")
        lines.extend([
            "",
            "===== COMPARAȚIE COORTE INTRARE =====",
            f"  Score 90–99:  n={c90.buy_count} | Total PnL ${c90.total_pnl:,.2f} | "
            f"avg ${c90.average_pnl:,.2f} | median ${c90.median_pnl:,.2f} | "
            f"win rate {c90.win_rate:.1f}%",
            f"  Score 100+:   n={c100.buy_count} | Total PnL ${c100.total_pnl:,.2f} | "
            f"avg ${c100.average_pnl:,.2f} | median ${c100.median_pnl:,.2f} | "
            f"win rate {c100.win_rate:.1f}%",
            f"  Delta (90–99 minus 100+): total ${self.cohort_delta_total_pnl:+,.2f} | "
            f"median ${self.cohort_delta_median_pnl:+,.2f}",
            "",
            f"Dossier match: {self.dossier_match_count}/{c90.buy_count + c100.buy_count} "
            f"({self.dossier_match_rate:.1f}%)",
            "",
            "===== PnL PE REASON (pe coortă) =====",
        ])
        for dim_label, dim in [("Reason", "reason"), ("Ticker", "ticker"), ("Region", "region"), ("Signal", "signal")]:
            lines.append(f"--- {dim_label} ---")
            for cohort in ("90-99", "100+"):
                rows = [
                    g for g in self.group_aggregates
                    if g.dimension == dim and g.cohort == cohort
                ]
                rows.sort(key=lambda x: x.total_pnl)
                for g in rows:
                    lines.append(
                        f"  [{cohort}] {g.bucket}: ${g.total_pnl:,.2f} "
                        f"(n={g.buy_count}, avg ${g.average_pnl:,.2f})"
                    )
            lines.append("")
        lines.append("===== TRĂSĂTURI COMUNE — SCORE 100+ PIERZĂTORI =====")
        if self.score_100_loser_traits:
            for t in self.score_100_loser_traits:
                lines.append(
                    f"  {t.trait}: {t.count}x, PnL total ${t.total_pnl:,.2f} — "
                    f"ex: {', '.join(t.examples[:3])}"
                )
        else:
            lines.append("  (niciun pierzător Score 100+ sau eșantion insuficient)")
        lines.extend(["", "===== MEDII COMPONENTE DOSSIER (dacă disponibile) ====="])
        if self.component_averages:
            for comp in self.component_averages:
                lines.append(
                    f"  [{comp.cohort} / {comp.subset}] n={comp.sample_count} | "
                    f"Momentum {comp.momentum} | Trend {comp.trend} | "
                    f"Volume {comp.volume} | Risk {comp.risk} | "
                    f"Conflict {comp.conflict} | Overall {comp.overall}"
                )
        else:
            lines.append("  Nu există potriviri dossier — componente indisponibile.")
        lines.extend([
            "",
            f"live_signals.csv (referință, nu adevăr istoric): {self.live_signals_reference_rows} rânduri",
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — analiză read-only.",
            "",
        ])
        return "\n".join(lines)


class ScoreDecompositionReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: ScoreDecompositionReport) -> Path:
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

    def persist_txt(self, report: ScoreDecompositionReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
