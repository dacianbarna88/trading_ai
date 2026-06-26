"""
Entry counterfactual analysis report — Phase VII Sprint A3

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only counterfactual entry analysis — no strategy or portfolio changes.
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


DEFAULT_ENTRY_JSON_PATH = Path("tae_entry_counterfactual.json")
DEFAULT_ENTRY_TXT_PATH = Path("tae_entry_counterfactual.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_entry_counterfactual"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"

SCORE_BUCKETS = (
    ("0-39", 0, 39),
    ("40-59", 40, 59),
    ("60-79", 60, 79),
    ("80-89", 80, 89),
    ("90-99", 90, 99),
    ("100+", 100, 9999),
)


class EntryVerdict(str, Enum):
    ENTRY_FILTER_TOO_WEAK = "ENTRY_FILTER_TOO_WEAK"
    ENTRY_FILTER_TOO_STRICT = "ENTRY_FILTER_TOO_STRICT"
    ENTRY_SIZING_SUBOPTIMAL = "ENTRY_SIZING_SUBOPTIMAL"
    ENTRY_LOGIC_APPROXIMATELY_OK = "ENTRY_LOGIC_APPROXIMATELY_OK"


class RecommendationRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGHER = "HIGHER"


@dataclass
class BaselineMetrics:
    realized_pnl: float
    open_pnl: float
    total_pnl: float
    win_rate: float
    profit_factor: float
    expectancy: float
    buy_count: int
    closed_buy_count: int
    open_buy_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "realized_pnl": _round_num(self.realized_pnl, 2),
            "open_pnl": _round_num(self.open_pnl, 2),
            "total_pnl": _round_num(self.total_pnl, 2),
            "win_rate": _round_num(self.win_rate, 2),
            "profit_factor": _round_num(self.profit_factor, 4),
            "expectancy": _round_num(self.expectancy, 2),
            "buy_count": self.buy_count,
            "closed_buy_count": self.closed_buy_count,
            "open_buy_count": self.open_buy_count,
        }


@dataclass
class EntryBuyRecord:
    buy_id: int
    ticker: str
    buy_date: str
    buy_price: float
    shares: float
    invested: float
    score: float
    signal: str
    reason: str
    region: str
    closed: bool
    had_stop_loss_exit: bool
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "buy_id": self.buy_id,
            "ticker": self.ticker,
            "buy_date": self.buy_date,
            "buy_price": _round_num(self.buy_price, 4),
            "shares": _round_num(self.shares, 6),
            "invested": _round_num(self.invested, 2),
            "score": _round_num(self.score, 2),
            "signal": self.signal,
            "reason": self.reason,
            "region": self.region,
            "closed": self.closed,
            "had_stop_loss_exit": self.had_stop_loss_exit,
            "realized_pnl": _round_num(self.realized_pnl, 2),
            "unrealized_pnl": _round_num(self.unrealized_pnl, 2),
            "total_pnl": _round_num(self.total_pnl, 2),
        }


@dataclass
class ScenarioResult:
    scenario_id: str
    label: str
    hypothetical_realized_pnl: float
    hypothetical_open_pnl: float
    hypothetical_total_pnl: float
    delta_vs_baseline: float
    trades_skipped: int
    capital_avoided: float
    winners_lost: float
    losers_avoided: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "hypothetical_realized_pnl": _round_num(self.hypothetical_realized_pnl, 2),
            "hypothetical_open_pnl": _round_num(self.hypothetical_open_pnl, 2),
            "hypothetical_total_pnl": _round_num(self.hypothetical_total_pnl, 2),
            "delta_vs_baseline": _round_num(self.delta_vs_baseline, 2),
            "trades_skipped": self.trades_skipped,
            "capital_avoided": _round_num(self.capital_avoided, 2),
            "winners_lost": _round_num(self.winners_lost, 2),
            "losers_avoided": _round_num(self.losers_avoided, 2),
        }


@dataclass
class BucketPnL:
    bucket: str
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    buy_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "realized_pnl": _round_num(self.realized_pnl, 2),
            "unrealized_pnl": _round_num(self.unrealized_pnl, 2),
            "total_pnl": _round_num(self.total_pnl, 2),
            "buy_count": self.buy_count,
        }


@dataclass
class EntryRecommendation:
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
class ExternalRefs:
    profit_attribution_total_pnl: float | None
    independent_verification_total_pnl: float | None
    baseline_delta_vs_attribution: float | None
    live_signals_rows: int
    alerts_log_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "profit_attribution_total_pnl": _round_num(self.profit_attribution_total_pnl or 0, 2)
            if self.profit_attribution_total_pnl is not None
            else None,
            "independent_verification_total_pnl": _round_num(
                self.independent_verification_total_pnl or 0, 2
            )
            if self.independent_verification_total_pnl is not None
            else None,
            "baseline_delta_vs_attribution": _round_num(
                self.baseline_delta_vs_attribution or 0, 2
            )
            if self.baseline_delta_vs_attribution is not None
            else None,
            "live_signals_rows": self.live_signals_rows,
            "alerts_log_rows": self.alerts_log_rows,
        }


@dataclass
class EntryCounterfactualReport:
    verdict: EntryVerdict
    baseline: BaselineMetrics
    scenarios: list[ScenarioResult]
    best_scenario_id: str
    worst_scenario_id: str
    buys: list[EntryBuyRecord]
    pnl_by_score_bucket: list[BucketPnL]
    pnl_by_signal: list[BucketPnL]
    pnl_by_reason: list[BucketPnL]
    pnl_by_region: list[BucketPnL]
    pnl_by_size_bucket: list[BucketPnL]
    recommendations: list[EntryRecommendation]
    external_refs: ExternalRefs
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "baseline": self.baseline.to_dict(),
            "scenarios": [s.to_dict() for s in self.scenarios],
            "best_scenario_id": self.best_scenario_id,
            "worst_scenario_id": self.worst_scenario_id,
            "pnl_by_score_bucket": [b.to_dict() for b in self.pnl_by_score_bucket],
            "pnl_by_signal": [b.to_dict() for b in self.pnl_by_signal],
            "pnl_by_reason": [b.to_dict() for b in self.pnl_by_reason],
            "pnl_by_region": [b.to_dict() for b in self.pnl_by_region],
            "pnl_by_size_bucket": [b.to_dict() for b in self.pnl_by_size_bucket],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "external_refs": self.external_refs.to_dict(),
            "buys": [b.to_dict() for b in self.buys],
        }

    def format_text(self) -> str:
        b = self.baseline
        lines = [
            "===== ANALIZĂ CONTRAFACTUALĂ INTRĂRI — TAE FAZA VII A3 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Intrări BUY analizate: {b.buy_count} ({b.closed_buy_count} închise, {b.open_buy_count} deschise)",
            "",
            "===== BASELINE (portofoliu actual) =====",
            f"  Realized PnL:   ${b.realized_pnl:>10,.2f}",
            f"  Open PnL:       ${b.open_pnl:>10,.2f}",
            f"  Total PnL:      ${b.total_pnl:>10,.2f}",
            f"  Win rate:       {b.win_rate:.1f}% (intrări închise)",
            f"  Profit factor:  {b.profit_factor:.4f}",
            f"  Expectancy:     ${b.expectancy:,.2f} / intrare închisă",
            "",
            "===== SCENARII CONTRAFACTUALE =====",
        ]
        for s in self.scenarios:
            lines.append(
                f"  {s.label}"
            )
            lines.append(
                f"    Total PnL: ${s.hypothetical_total_pnl:>10,.2f} | "
                f"delta ${s.delta_vs_baseline:+,.2f} | "
                f"sărite {s.trades_skipped} | "
                f"capital evitat ${s.capital_avoided:,.2f}"
            )
            lines.append(
                f"    Câștigători pierduți: ${s.winners_lost:,.2f} | "
                f"Pierzători evitați: ${s.losers_avoided:,.2f}"
            )
        lines.extend([
            "",
            f"Cel mai bun scenariu: {self.best_scenario_id}",
            f"Cel mai slab scenariu: {self.worst_scenario_id}",
            "",
            "===== PnL PE SCOR INTRARE =====",
        ])
        for row in self.pnl_by_score_bucket:
            lines.append(
                f"  {row.bucket:8s} ${row.total_pnl:>10,.2f} "
                f"(real ${row.realized_pnl:,.2f}, open ${row.unrealized_pnl:,.2f}, n={row.buy_count})"
            )
        lines.extend(["", "===== PnL PE SIGNAL ====="])
        for row in self.pnl_by_signal:
            lines.append(
                f"  {row.bucket:14s} ${row.total_pnl:>10,.2f} (n={row.buy_count})"
            )
        lines.extend(["", "===== PnL PE REGIUNE ====="])
        for row in self.pnl_by_region:
            lines.append(
                f"  {row.bucket:8s} ${row.total_pnl:>10,.2f} (n={row.buy_count})"
            )
        lines.extend(["", "===== PnL PE MĂrime POZIȚIE ====="])
        for row in self.pnl_by_size_bucket:
            lines.append(
                f"  {row.bucket:8s} ${row.total_pnl:>10,.2f} (n={row.buy_count})"
            )
        lines.extend(["", "===== RECOMANDĂRI (NOT IMPLEMENTED — human review) ====="])
        for rec in self.recommendations:
            lines.append(f"  [{rec.risk_level.value}] {rec.title}")
            lines.append(f"      {rec.description}")
            lines.append(f"      Status: {rec.implementation_status}")
        refs = self.external_refs
        lines.extend([
            "",
            "===== REFERINȚE EXTERNE =====",
            f"  Profit attribution total PnL: "
            f"${refs.profit_attribution_total_pnl:,.2f}"
            if refs.profit_attribution_total_pnl is not None
            else "  Profit attribution: N/A",
            f"  Independent verification total PnL: "
            f"${refs.independent_verification_total_pnl:,.2f}"
            if refs.independent_verification_total_pnl is not None
            else "  Independent verification: N/A",
            f"  live_signals.csv rânduri: {refs.live_signals_rows}",
            f"  alerts_log.csv rânduri: {refs.alerts_log_rows}",
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — analiză contrafactuală read-only.",
            "",
        ])
        return "\n".join(lines)


class EntryAnalysisReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_ENTRY_JSON_PATH
        self._txt_path = txt_path or DEFAULT_ENTRY_TXT_PATH

    def persist(self, report: EntryCounterfactualReport) -> Path:
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

    def persist_txt(self, report: EntryCounterfactualReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
