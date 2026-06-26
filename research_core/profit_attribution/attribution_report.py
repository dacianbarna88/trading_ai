"""
Profit attribution report — Phase VII Sprint A1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only profit attribution report — no strategy or portfolio changes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ATTRIBUTION_JSON_PATH = Path("tae_profit_attribution.json")
DEFAULT_ATTRIBUTION_TXT_PATH = Path("tae_profit_attribution.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_profit_attribution"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class AttributionVerdict(str, Enum):
    PROFIT_LOW_DUE_TO_LOSS_DRAG = "PROFIT_LOW_DUE_TO_LOSS_DRAG"
    PROFIT_LOW_DUE_TO_SMALL_WINNERS = "PROFIT_LOW_DUE_TO_SMALL_WINNERS"
    PROFIT_LOW_DUE_TO_LOW_WIN_RATE = "PROFIT_LOW_DUE_TO_LOW_WIN_RATE"
    PROFIT_LOW_DUE_TO_CONCENTRATION = "PROFIT_LOW_DUE_TO_CONCENTRATION"
    PROFIT_HEALTHY_BUT_SMALL_SAMPLE = "PROFIT_HEALTHY_BUT_SMALL_SAMPLE"


class RecommendationRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGHER = "HIGHER"


@dataclass
class CoreMetrics:
    gross_profit: float
    gross_loss: float
    net_realized_profit: float
    open_unrealized_pnl: float
    total_pnl: float
    win_rate: float
    average_win: float
    average_loss: float
    median_win: float
    median_loss: float
    payoff_ratio: float
    profit_factor: float
    expectancy_per_trade: float
    closed_trade_count: int
    winning_trades: int
    losing_trades: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "net_realized_profit": round(self.net_realized_profit, 2),
            "open_unrealized_pnl": round(self.open_unrealized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "win_rate": round(self.win_rate, 2),
            "average_win": round(self.average_win, 2),
            "average_loss": round(self.average_loss, 2),
            "median_win": round(self.median_win, 2),
            "median_loss": round(self.median_loss, 2),
            "payoff_ratio": round(self.payoff_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
            "expectancy_per_trade": round(self.expectancy_per_trade, 2),
            "closed_trade_count": self.closed_trade_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
        }


@dataclass
class BucketContribution:
    bucket: str
    pnl: float
    trade_count: int
    win_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "pnl": round(self.pnl, 2),
            "trade_count": self.trade_count,
            "win_rate": round(self.win_rate, 2),
        }


@dataclass
class TickerContribution:
    ticker: str
    realized_pnl: float
    trade_count: int
    region: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "realized_pnl": round(self.realized_pnl, 2),
            "trade_count": self.trade_count,
            "region": self.region,
        }


@dataclass
class ProfitConcentration:
    top_5_winners_pnl: float
    top_5_winners_contribution_pct: float
    top_5_losers_pnl: float
    top_5_losers_drag_pct: float
    top_20pct_winners_share_of_gross_profit: float
    bottom_20pct_losers_share_of_gross_loss: float
    pareto_summary: str
    top_winners: list[dict[str, Any]]
    top_losers: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_5_winners_pnl": round(self.top_5_winners_pnl, 2),
            "top_5_winners_contribution_pct": round(self.top_5_winners_contribution_pct, 2),
            "top_5_losers_pnl": round(self.top_5_losers_pnl, 2),
            "top_5_losers_drag_pct": round(self.top_5_losers_drag_pct, 2),
            "top_20pct_winners_share_of_gross_profit": round(
                self.top_20pct_winners_share_of_gross_profit, 2
            ),
            "bottom_20pct_losers_share_of_gross_loss": round(
                self.bottom_20pct_losers_share_of_gross_loss, 2
            ),
            "pareto_summary": self.pareto_summary,
            "top_winners": self.top_winners,
            "top_losers": self.top_losers,
        }


@dataclass
class AttributionRecommendation:
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
class ExternalReference:
    source: str
    available: bool
    total_pnl: float | None = None
    realized_pnl: float | None = None
    open_pnl: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "available": self.available,
            "total_pnl": round(self.total_pnl, 2) if self.total_pnl is not None else None,
            "realized_pnl": (
                round(self.realized_pnl, 2) if self.realized_pnl is not None else None
            ),
            "open_pnl": round(self.open_pnl, 2) if self.open_pnl is not None else None,
            "notes": self.notes,
        }


@dataclass
class ProfitAttributionReport:
    verdict: AttributionVerdict
    core: CoreMetrics
    pnl_by_ticker: list[TickerContribution]
    pnl_by_region: list[BucketContribution]
    pnl_by_exit_reason: list[BucketContribution]
    pnl_by_holding_period: list[BucketContribution]
    pnl_by_position_size: list[BucketContribution]
    pnl_by_score: list[BucketContribution]
    concentration: ProfitConcentration
    mathematical_explanation: list[str]
    recommendations: list[AttributionRecommendation]
    external_references: list[ExternalReference]
    starting_capital: float
    deposits: float
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "starting_capital": round(self.starting_capital, 2),
            "deposits": round(self.deposits, 2),
            "core": self.core.to_dict(),
            "pnl_by_ticker": [t.to_dict() for t in self.pnl_by_ticker],
            "pnl_by_region": [b.to_dict() for b in self.pnl_by_region],
            "pnl_by_exit_reason": [b.to_dict() for b in self.pnl_by_exit_reason],
            "pnl_by_holding_period": [b.to_dict() for b in self.pnl_by_holding_period],
            "pnl_by_position_size": [b.to_dict() for b in self.pnl_by_position_size],
            "pnl_by_score": [b.to_dict() for b in self.pnl_by_score],
            "concentration": self.concentration.to_dict(),
            "mathematical_explanation": list(self.mathematical_explanation),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "external_references": [e.to_dict() for e in self.external_references],
        }

    def format_text(self) -> str:
        c = self.core
        lines = [
            "===== ATRIBUIRE PROFIT — TAE FAZA VII A1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            "",
            "===== MATEMATICĂ DE BAZĂ =====",
            f"Profit brut (câștiguri):     ${c.gross_profit:,.2f}",
            f"Pierdere brută (pierderi):   ${abs(c.gross_loss):,.2f}",
            f"Profit net realizat:           ${c.net_realized_profit:,.2f}",
            f"PnL nerealizat deschis:        ${c.open_unrealized_pnl:,.2f}",
            f"PnL total:                     ${c.total_pnl:,.2f}",
            f"Win rate:                      {c.win_rate:.2f}% ({c.winning_trades}/{c.closed_trade_count})",
            f"Câștig mediu:                  ${c.average_win:,.2f}",
            f"Pierdere medie:                ${c.average_loss:,.2f}",
            f"Câștig median:                 ${c.median_win:,.2f}",
            f"Pierdere mediană:              ${c.median_loss:,.2f}",
            f"Payoff ratio:                  {c.payoff_ratio:.4f}",
            f"Profit factor:                 {c.profit_factor:.4f}",
            f"Așteptare/tranzacție:          ${c.expectancy_per_trade:,.2f}",
            "",
            "===== CONCENTRARE PROFIT =====",
            f"Top 5 câștigători:             ${self.concentration.top_5_winners_pnl:,.2f} "
            f"({self.concentration.top_5_winners_contribution_pct:.1f}% din profit net)",
            f"Top 5 pierzători:              ${self.concentration.top_5_losers_pnl:,.2f} "
            f"({self.concentration.top_5_losers_drag_pct:.1f}% din pierdere brută)",
            f"Pareto: {self.concentration.pareto_summary}",
            "",
            "===== PnL PE TICKER (realizat FIFO) =====",
        ]
        for t in sorted(self.pnl_by_ticker, key=lambda x: x.realized_pnl, reverse=True)[:15]:
            lines.append(
                f"  {t.ticker:8s} [{t.region:7s}] ${t.realized_pnl:>10,.2f}  ({t.trade_count} SELL)"
            )
        lines.extend(["", "===== PnL PE REGIUNE ====="])
        for b in self.pnl_by_region:
            lines.append(
                f"  {b.bucket:8s} ${b.pnl:>10,.2f}  ({b.trade_count} tranzacții, WR {b.win_rate:.1f}%)"
            )
        lines.extend(["", "===== PnL PE MOTIV IEȘIRE ====="])
        for b in self.pnl_by_exit_reason:
            lines.append(
                f"  {b.bucket:14s} ${b.pnl:>10,.2f}  ({b.trade_count} tranzacții, WR {b.win_rate:.1f}%)"
            )
        lines.extend(["", "===== PnL PE PERIOADĂ DEȚINERE ====="])
        for b in self.pnl_by_holding_period:
            lines.append(
                f"  {b.bucket:8s} ${b.pnl:>10,.2f}  ({b.trade_count} tranzacții, WR {b.win_rate:.1f}%)"
            )
        lines.extend(["", "===== PnL PE MĂrime POZIȚIE ====="])
        for b in self.pnl_by_position_size:
            lines.append(
                f"  {b.bucket:10s} ${b.pnl:>10,.2f}  ({b.trade_count} tranzacții, WR {b.win_rate:.1f}%)"
            )
        if self.pnl_by_score:
            lines.extend(["", "===== PnL PE SCOR SEMNAL ====="])
            for b in self.pnl_by_score:
                lines.append(
                    f"  {b.bucket:10s} ${b.pnl:>10,.2f}  ({b.trade_count} tranzacții, WR {b.win_rate:.1f}%)"
                )
        lines.extend(["", "===== EXPLICAȚIE MATEMATICĂ (10 puncte) ====="])
        for idx, bullet in enumerate(self.mathematical_explanation, start=1):
            lines.append(f"  {idx}. {bullet}")
        lines.extend(["", "===== RECOMANDĂRI (NOT IMPLEMENTED) ====="])
        for rec in self.recommendations:
            lines.append(f"  [{rec.risk_level.value}] {rec.title}")
            lines.append(f"      {rec.description}")
            lines.append(f"      Status: {rec.implementation_status}")
        lines.extend(["", "===== REFERINȚE EXTERNE ====="])
        for ref in self.external_references:
            if ref.available:
                parts = [f"[{ref.source}]"]
                if ref.total_pnl is not None:
                    parts.append(f"total=${ref.total_pnl:,.2f}")
                if ref.realized_pnl is not None:
                    parts.append(f"realized=${ref.realized_pnl:,.2f}")
                if ref.open_pnl is not None:
                    parts.append(f"open=${ref.open_pnl:,.2f}")
                if ref.notes:
                    parts.append(ref.notes)
                lines.append("  " + " | ".join(parts))
            else:
                lines.append(f"  [{ref.source}] indisponibil — {ref.notes}")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "Nu s-au modificat fișierele de trading live.",
            "Fără instrucțiuni BUY/SELL — analiză read-only.",
            "",
        ])
        return "\n".join(lines)


class AttributionReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_ATTRIBUTION_JSON_PATH
        self._txt_path = txt_path or DEFAULT_ATTRIBUTION_TXT_PATH

    def persist(self, report: ProfitAttributionReport) -> Path:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: ProfitAttributionReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
