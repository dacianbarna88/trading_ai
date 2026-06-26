"""
Strategic performance audit report model — V1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only portfolio performance audit — no execution or strategy changes.
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

DEFAULT_AUDIT_JSON_PATH = Path("tae_strategic_performance_audit.json")
DEFAULT_AUDIT_TXT_PATH = Path("tae_strategic_performance_audit.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategic_performance_audit"
ANALYSIS_SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class RecommendationRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGHER = "HIGHER"


@dataclass
class PortfolioActivity:
    total_buy_count: int
    total_sell_count: int
    buy_last_2_days: int
    sell_last_2_days: int
    open_positions: int
    closed_positions: int
    open_tickers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_buy_count": self.total_buy_count,
            "total_sell_count": self.total_sell_count,
            "buy_last_2_days": self.buy_last_2_days,
            "sell_last_2_days": self.sell_last_2_days,
            "open_positions": self.open_positions,
            "closed_positions": self.closed_positions,
            "open_tickers": list(self.open_tickers),
        }


@dataclass
class PerformanceMetrics:
    total_current_value: float
    total_invested: float
    total_pnl: float
    total_pnl_pct: float
    last_2_days_realized_pnl: float
    last_2_days_unrealized_pnl: float
    prior_7_days_realized_pnl: float
    all_history_realized_pnl: float
    max_drawdown_pct: float | None
    reference_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_current_value": round(self.total_current_value, 2),
            "total_invested": round(self.total_invested, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "last_2_days_realized_pnl": round(self.last_2_days_realized_pnl, 2),
            "last_2_days_unrealized_pnl": round(self.last_2_days_unrealized_pnl, 2),
            "prior_7_days_realized_pnl": round(self.prior_7_days_realized_pnl, 2),
            "all_history_realized_pnl": round(self.all_history_realized_pnl, 2),
            "max_drawdown_pct": (
                round(self.max_drawdown_pct, 2) if self.max_drawdown_pct is not None else None
            ),
            "reference_date": self.reference_date,
        }


@dataclass
class TradeQuality:
    win_rate: float
    average_winner: float
    average_loser: float
    profit_factor: float | None
    biggest_loser: dict[str, Any]
    biggest_winner: dict[str, Any]
    closed_trades: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "win_rate": round(self.win_rate, 2),
            "average_winner": round(self.average_winner, 2),
            "average_loser": round(self.average_loser, 2),
            "profit_factor": (
                round(self.profit_factor, 2) if self.profit_factor is not None else None
            ),
            "biggest_loser": dict(self.biggest_loser),
            "biggest_winner": dict(self.biggest_winner),
            "closed_trades": self.closed_trades,
        }


@dataclass
class PeriodComparison:
    period: str
    realized_pnl: float
    trade_count: int
    win_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "realized_pnl": round(self.realized_pnl, 2),
            "trade_count": self.trade_count,
            "win_rate": round(self.win_rate, 2),
        }


@dataclass
class SignalQuality:
    strong_buy_tickers: list[str]
    take_profit_tickers: list[str]
    zero_score_tickers: list[str]
    repeated_weak_signals: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strong_buy_tickers": list(self.strong_buy_tickers),
            "take_profit_tickers": list(self.take_profit_tickers),
            "zero_score_tickers": list(self.zero_score_tickers),
            "repeated_weak_signals": list(self.repeated_weak_signals),
        }


@dataclass
class Anomaly:
    anomaly_type: str
    severity: str
    description: str
    ticker: str = ""
    date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "ticker": self.ticker,
            "date": self.date,
        }


@dataclass
class RegionalPnL:
    region: str
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "trade_count": self.trade_count,
        }


@dataclass
class Recommendation:
    risk_level: RecommendationRisk
    action: str
    rationale: str
    implementation_status: str = "NOT_IMPLEMENTED"

    def __post_init__(self) -> None:
        if isinstance(self.risk_level, str):
            self.risk_level = RecommendationRisk(self.risk_level)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "action": self.action,
            "rationale": self.rationale,
            "implementation_status": self.implementation_status,
        }


@dataclass
class StrategicPerformanceAudit:
    portfolio_activity: PortfolioActivity
    performance: PerformanceMetrics
    trade_quality: TradeQuality
    period_comparisons: list[PeriodComparison]
    signal_quality: SignalQuality
    anomalies: list[Anomaly]
    regional_pnl: list[RegionalPnL]
    root_cause_hypotheses: list[str]
    recommendations: list[Recommendation]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = ANALYSIS_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "portfolio_activity": self.portfolio_activity.to_dict(),
            "performance": self.performance.to_dict(),
            "trade_quality": self.trade_quality.to_dict(),
            "period_comparisons": [p.to_dict() for p in self.period_comparisons],
            "signal_quality": self.signal_quality.to_dict(),
            "anomalies": [a.to_dict() for a in self.anomalies],
            "regional_pnl": [r.to_dict() for r in self.regional_pnl],
            "root_cause_hypotheses": list(self.root_cause_hypotheses),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "sources_loaded": dict(self.sources_loaded),
        }

    def format_text(self) -> str:
        pa = self.portfolio_activity
        perf = self.performance
        tq = self.trade_quality
        sq = self.signal_quality

        lines = [
            "===== AUDIT PERFORMANȚĂ STRATEGICĂ — TRADING AI V1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Dată referință: {perf.reference_date}",
            "",
            "===== 1. ACTIVITATE PORTOFOLIU =====",
            f"Total tranzacții BUY: {pa.total_buy_count}",
            f"Total tranzacții SELL: {pa.total_sell_count}",
            f"BUY ultimele 2 zile: {pa.buy_last_2_days}",
            f"SELL ultimele 2 zile: {pa.sell_last_2_days}",
            f"Poziții deschise: {pa.open_positions}",
            f"Poziții închise: {pa.closed_positions}",
            f"Ticker-e deschise: {', '.join(pa.open_tickers) if pa.open_tickers else '—'}",
            "",
            "===== 2. PERFORMANȚĂ =====",
            f"Valoare curentă totală: {perf.total_current_value:,.2f}",
            f"Capital investit (deschis): {perf.total_invested:,.2f}",
            f"PnL total (nerealizat deschis): {perf.total_pnl:,.2f} ({perf.total_pnl_pct:.2f}%)",
            f"PnL realizat ultimele 2 zile: {perf.last_2_days_realized_pnl:,.2f}",
            f"PnL nerealizat schimbat ultimele 2 zile: {perf.last_2_days_unrealized_pnl:,.2f}",
            f"PnL realizat 7 zile anterioare: {perf.prior_7_days_realized_pnl:,.2f}",
            f"PnL realizat total istoric: {perf.all_history_realized_pnl:,.2f}",
        ]
        if perf.max_drawdown_pct is not None:
            lines.append(f"Drawdown maxim estimat: {perf.max_drawdown_pct:.2f}%")
        pf = f"{tq.profit_factor:.2f}" if tq.profit_factor is not None else "N/A"
        lines.extend([
            "",
            "===== 3. CALITATE TRANZACȚII =====",
            f"Rata de câștig (win rate): {tq.win_rate:.1f}%",
            f"Câștig mediu: {tq.average_winner:,.2f}",
            f"Pierdere medie: {tq.average_loser:,.2f}",
            f"Profit factor: {pf}",
            f"Tranzacții închise analizate: {tq.closed_trades}",
        ])
        if tq.biggest_winner:
            lines.append(
                f"Cel mai mare câștig: {tq.biggest_winner.get('ticker', '?')} "
                f"({tq.biggest_winner.get('pnl', 0):,.2f})"
            )
        if tq.biggest_loser:
            lines.append(
                f"Cea mai mare pierdere: {tq.biggest_loser.get('ticker', '?')} "
                f"({tq.biggest_loser.get('pnl', 0):,.2f})"
            )
        lines.extend([
            "",
            "===== 4. COMPARAȚIE PERIOADE =====",
        ])
        for pc in self.period_comparisons:
            lines.append(
                f"  {pc.period}: PnL realizat={pc.realized_pnl:,.2f}, "
                f"tranzacții={pc.trade_count}, win rate={pc.win_rate:.1f}%"
            )
        lines.extend([
            "",
            "===== 5. CALITATE SEMNALE =====",
            f"STRONG BUY curent: {', '.join(sq.strong_buy_tickers) or '—'}",
            f"TAKE PROFIT curent: {', '.join(sq.take_profit_tickers) or '—'}",
            f"Score 0 (WAIT): {', '.join(sq.zero_score_tickers) or '—'}",
            f"Semnale slabe repetate: {', '.join(sq.repeated_weak_signals) or '—'}",
            "",
            "===== 6. ANOMALII DETECTATE =====",
        ])
        if self.anomalies:
            for an in self.anomalies:
                lines.append(f"  [{an.severity}] {an.anomaly_type}: {an.description}")
        else:
            lines.append("  Nicio anomalie detectată.")
        lines.extend([
            "",
            "===== 7. PnL PE REGIUNE (aproximare) =====",
        ])
        for reg in self.regional_pnl:
            lines.append(
                f"  {reg.region}: realizat={reg.realized_pnl:,.2f}, "
                f"nerealizat={reg.unrealized_pnl:,.2f}, tranzacții={reg.trade_count}"
            )
        lines.extend([
            "",
            "===== 8. IPOTEZE CAUZĂ RĂDĂCINĂ =====",
        ])
        for idx, hyp in enumerate(self.root_cause_hypotheses, start=1):
            lines.append(f"  {idx}. {hyp}")
        lines.extend([
            "",
            "===== 9. RECOMANDĂRI (3) =====",
        ])
        for rec in self.recommendations:
            lines.append(f"  [{rec.risk_level.value}] {rec.action}")
            lines.append(f"      Motiv: {rec.rationale}")
            lines.append(f"      Status: {rec.implementation_status}")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
            "No live trading files were modified",
            "",
            "Audit read-only — nu autorizează tranzacții sau modificări de strategie.",
            "",
        ])
        return "\n".join(lines)


class PerformanceAuditStore:
    """JSON persistence for performance audits — stdlib only."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_AUDIT_JSON_PATH

    @property
    def path(self) -> Path:
        return self._path

    def persist(self, audit: StrategicPerformanceAudit) -> Path:
        self._path.write_text(
            json.dumps(audit.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def persist_txt(self, audit: StrategicPerformanceAudit) -> Path:
        DEFAULT_AUDIT_TXT_PATH.write_text(audit.format_text() + "\n", encoding="utf-8")
        return DEFAULT_AUDIT_TXT_PATH
