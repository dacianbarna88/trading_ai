"""
Cash flow ledger audit report — Phase VI Sprint B5

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only ledger reconstruction report — no portfolio or strategy changes.
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

DEFAULT_LEDGER_JSON_PATH = Path("tae_cash_flow_ledger.json")
DEFAULT_LEDGER_TXT_PATH = Path("tae_cash_flow_ledger.txt")
SCHEMA_VERSION = 2
SCHEMA_NAME = "tae_cash_flow_ledger"
ANALYSIS_SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"
RECONCILIATION_FORMULA = (
    "Account Value = Starting Capital + Deposits - Withdrawals "
    "+ Realized PnL + Open Unrealized PnL"
)
CANONICAL_ACCOUNT_VALUE_SOURCE = "portfolio_csv_marks"
MICRO_LOT_TOLERANCE = 0.05


class LedgerStatus(str, Enum):
    LEDGER_VALID_WITH_MARK_SOURCE_DELTA = "LEDGER_VALID_WITH_MARK_SOURCE_DELTA"
    LEDGER_INVALID = "LEDGER_INVALID"


class CheckSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class LedgerTransaction:
    index: int
    timestamp: str
    ticker: str
    action: str
    price: float
    shares: float
    cash_before: float
    cash_after: float
    cash_delta: float
    shares_before: float
    shares_after: float
    avg_cost_after: float
    realized_pnl_delta: float
    cumulative_realized_pnl: float
    open_market_value: float
    ledger_account_value: float
    formula_account_value: float
    reconciliation_drift: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "ticker": self.ticker,
            "action": self.action,
            "price": round(self.price, 4),
            "shares": round(self.shares, 6),
            "cash_before": round(self.cash_before, 2),
            "cash_after": round(self.cash_after, 2),
            "cash_delta": round(self.cash_delta, 2),
            "shares_before": round(self.shares_before, 6),
            "shares_after": round(self.shares_after, 6),
            "avg_cost_after": round(self.avg_cost_after, 4),
            "realized_pnl_delta": round(self.realized_pnl_delta, 2),
            "cumulative_realized_pnl": round(self.cumulative_realized_pnl, 2),
            "open_market_value": round(self.open_market_value, 2),
            "ledger_account_value": round(self.ledger_account_value, 2),
            "formula_account_value": round(self.formula_account_value, 2),
            "reconciliation_drift": round(self.reconciliation_drift, 2),
            "notes": self.notes,
        }


@dataclass
class LedgerCheck:
    check_id: str
    severity: CheckSeverity
    passed: bool
    description: str
    transaction_index: int | None = None
    transaction_timestamp: str = ""
    ticker: str = ""
    amount: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "severity": self.severity.value,
            "passed": self.passed,
            "description": self.description,
            "transaction_index": self.transaction_index,
            "transaction_timestamp": self.transaction_timestamp,
            "ticker": self.ticker,
            "amount": round(self.amount, 2),
            "reason": self.reason,
        }


@dataclass
class CrossCheckResult:
    source: str
    available: bool
    account_value: float | None = None
    realized_pnl: float | None = None
    open_pnl: float | None = None
    total_pnl: float | None = None
    delta_vs_ledger: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "available": self.available,
            "account_value": (
                round(self.account_value, 2) if self.account_value is not None else None
            ),
            "realized_pnl": (
                round(self.realized_pnl, 2) if self.realized_pnl is not None else None
            ),
            "open_pnl": round(self.open_pnl, 2) if self.open_pnl is not None else None,
            "total_pnl": round(self.total_pnl, 2) if self.total_pnl is not None else None,
            "delta_vs_ledger": (
                round(self.delta_vs_ledger, 2) if self.delta_vs_ledger is not None else None
            ),
            "notes": self.notes,
        }


@dataclass
class MarkSourceTickerDelta:
    ticker: str
    shares: float
    portfolio_csv_mark: float
    latest_portfolio_mark: float
    market_value_csv: float
    market_value_latest: float
    delta: float
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "shares": round(self.shares, 6),
            "portfolio_csv_mark": round(self.portfolio_csv_mark, 4),
            "latest_portfolio_mark": round(self.latest_portfolio_mark, 4),
            "market_value_csv": round(self.market_value_csv, 2),
            "market_value_latest": round(self.market_value_latest, 2),
            "delta": round(self.delta, 2),
            "reason": self.reason,
        }


@dataclass
class LedgerSummary:
    starting_capital: float
    deposits: float
    withdrawals: float
    dividends: float
    fees: float
    realized_pnl_all_sells: float
    realized_pnl_repairable: float
    open_unrealized_pnl: float
    total_pnl: float
    current_cash: float
    open_market_value: float
    final_account_value: float
    formula_account_value: float
    reconciliation_difference: float
    account_value_from_portfolio_csv_marks: float
    account_value_from_latest_portfolio_marks: float
    canonical_account_value_source: str
    mark_source_delta: float
    open_market_value_portfolio_csv: float
    open_market_value_latest_portfolio: float
    open_unrealized_pnl_portfolio_csv: float
    transaction_count: int
    buy_count: int
    sell_count: int
    open_position_count: int
    closed_position_count: int
    open_tickers: list[str] = field(default_factory=list)
    mark_source_ticker_deltas: list[MarkSourceTickerDelta] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "starting_capital": round(self.starting_capital, 2),
            "deposits": round(self.deposits, 2),
            "withdrawals": round(self.withdrawals, 2),
            "dividends": round(self.dividends, 2),
            "fees": round(self.fees, 2),
            "realized_pnl_all_sells": round(self.realized_pnl_all_sells, 2),
            "realized_pnl_repairable": round(self.realized_pnl_repairable, 2),
            "open_unrealized_pnl": round(self.open_unrealized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "current_cash": round(self.current_cash, 2),
            "open_market_value": round(self.open_market_value, 2),
            "final_account_value": round(self.final_account_value, 2),
            "formula_account_value": round(self.formula_account_value, 2),
            "reconciliation_difference": round(self.reconciliation_difference, 2),
            "account_value_from_portfolio_csv_marks": round(
                self.account_value_from_portfolio_csv_marks, 2
            ),
            "account_value_from_latest_portfolio_marks": round(
                self.account_value_from_latest_portfolio_marks, 2
            ),
            "canonical_account_value_source": self.canonical_account_value_source,
            "mark_source_delta": round(self.mark_source_delta, 2),
            "open_market_value_portfolio_csv": round(
                self.open_market_value_portfolio_csv, 2
            ),
            "open_market_value_latest_portfolio": round(
                self.open_market_value_latest_portfolio, 2
            ),
            "open_unrealized_pnl_portfolio_csv": round(
                self.open_unrealized_pnl_portfolio_csv, 2
            ),
            "transaction_count": self.transaction_count,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "open_position_count": self.open_position_count,
            "closed_position_count": self.closed_position_count,
            "open_tickers": list(self.open_tickers),
            "mark_source_ticker_deltas": [
                d.to_dict() for d in self.mark_source_ticker_deltas
            ],
        }


@dataclass
class FirstErrorTransaction:
    index: int
    timestamp: str
    ticker: str
    action: str
    amount: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "ticker": self.ticker,
            "action": self.action,
            "amount": round(self.amount, 2),
            "reason": self.reason,
        }


@dataclass
class LedgerAuditReport:
    status: LedgerStatus
    summary: LedgerSummary
    transactions: list[LedgerTransaction]
    checks: list[LedgerCheck]
    cross_checks: list[CrossCheckResult]
    first_error: FirstErrorTransaction | None
    backup_files_found: list[str] = field(default_factory=list)
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = ANALYSIS_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "status": self.status.value,
            "reconciliation_formula": RECONCILIATION_FORMULA,
            "summary": self.summary.to_dict(),
            "first_error": self.first_error.to_dict() if self.first_error else None,
            "transactions": [t.to_dict() for t in self.transactions],
            "checks": [c.to_dict() for c in self.checks],
            "cross_checks": [c.to_dict() for c in self.cross_checks],
            "backup_files_found": list(self.backup_files_found),
            "sources_loaded": dict(self.sources_loaded),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE CASH FLOW LEDGER AUDIT — PHASE VI B5 =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Ledger {self.status.value}",
            "",
            "===== RECONCILIATION FORMULA =====",
            RECONCILIATION_FORMULA,
            "",
            "===== ACCOUNT SUMMARY (CANONICAL) =====",
            f"Canonical source:           {self.summary.canonical_account_value_source}",
            f"Starting Capital:           ${self.summary.starting_capital:,.2f}",
            f"Deposits:                   ${self.summary.deposits:,.2f}",
            f"Withdrawals:                ${self.summary.withdrawals:,.2f}",
            f"Dividends:                  ${self.summary.dividends:,.2f}",
            f"Fees/Commission:            ${self.summary.fees:,.2f}",
            f"Realized PnL (all SELLs):   ${self.summary.realized_pnl_all_sells:,.2f}",
            f"Realized PnL (repairable):  ${self.summary.realized_pnl_repairable:,.2f}",
            f"Open Unrealized PnL (CSV):  ${self.summary.open_unrealized_pnl_portfolio_csv:,.2f}",
            f"Total PnL:                  ${self.summary.total_pnl:,.2f}",
            "",
            f"Current Cash:               ${self.summary.current_cash:,.2f}",
            f"Open Market Value (CSV):    ${self.summary.open_market_value_portfolio_csv:,.2f}",
            f"Account Value (CSV marks):  ${self.summary.account_value_from_portfolio_csv_marks:,.2f}",
            f"  (= cash + open marks from portfolio.csv Current_Price)",
            "",
            f"Open Market Value (latest): ${self.summary.open_market_value_latest_portfolio:,.2f}",
            f"Account Value (latest):     ${self.summary.account_value_from_latest_portfolio_marks:,.2f}",
            f"  (= cash + open marks from latest_portfolio.txt)",
            f"Mark source delta:          ${self.summary.mark_source_delta:,.2f}",
            "",
            f"Formula Account Value:      ${self.summary.formula_account_value:,.2f}",
            f"Reconciliation Difference:  ${self.summary.reconciliation_difference:,.2f}",
            "",
            "===== MARK SOURCE DELTA BY TICKER =====",
        ]
        if self.summary.mark_source_ticker_deltas:
            for row in self.summary.mark_source_ticker_deltas:
                if abs(row.delta) > 0.005:
                    lines.append(
                        f"  {row.ticker:8s} | CSV ${row.market_value_csv:,.2f} "
                        f"({row.portfolio_csv_mark:.2f}/sh) vs "
                        f"latest ${row.market_value_latest:,.2f} "
                        f"({row.latest_portfolio_mark:.2f}/sh) | "
                        f"delta ${row.delta:,.2f} — {row.reason}"
                    )
            if not any(abs(r.delta) > 0.005 for r in self.summary.mark_source_ticker_deltas):
                lines.append("  No material per-ticker mark delta.")
        else:
            lines.append("  No open positions.")
        lines.extend([
            "",
            f"Transactions: {self.summary.transaction_count} "
            f"(BUY {self.summary.buy_count} / SELL {self.summary.sell_count})",
            f"Open positions: {self.summary.open_position_count} "
            f"{', '.join(self.summary.open_tickers) or '—'}",
            "",
        ])

        if self.first_error:
            fe = self.first_error
            lines.extend([
                "===== FIRST RECONCILIATION ERROR =====",
                f"Transaction #{fe.index}: {fe.timestamp} {fe.ticker} {fe.action}",
                f"Amount: ${fe.amount:,.2f}",
                f"Reason: {fe.reason}",
                "",
            ])

        lines.append("===== TRANSACTION LEDGER =====")
        for txn in self.transactions:
            lines.append(
                f"  #{txn.index:03d} {txn.timestamp} | {txn.ticker:8s} {txn.action:8s} | "
                f"cash ${txn.cash_before:,.2f} → ${txn.cash_after:,.2f} | "
                f"shares {txn.shares_before:.4f} → {txn.shares_after:.4f}"
            )
            if txn.notes:
                lines.append(f"         note: {txn.notes}")
            if abs(txn.reconciliation_drift) > 0.005:
                lines.append(
                    f"         drift: ${txn.reconciliation_drift:,.2f} "
                    f"(ledger ${txn.ledger_account_value:,.2f} vs "
                    f"formula ${txn.formula_account_value:,.2f})"
                )
        lines.append("")

        lines.append("===== EXTRA CHECKS =====")
        failed = [c for c in self.checks if not c.passed]
        if failed:
            for check in failed:
                lines.append(
                    f"  [FAIL {check.severity.value}] {check.check_id}: {check.description}"
                )
                if check.transaction_index is not None:
                    lines.append(
                        f"      txn #{check.transaction_index} {check.transaction_timestamp} "
                        f"{check.ticker} amount=${check.amount:,.2f} — {check.reason}"
                    )
        else:
            lines.append("  All extra checks passed.")
        lines.append("")

        lines.append("===== CROSS-CHECKS =====")
        for cc in self.cross_checks:
            if not cc.available:
                lines.append(f"  [{cc.source}] not available — {cc.notes}")
                continue
            parts = [f"[{cc.source}]"]
            if cc.account_value is not None:
                parts.append(f"account=${cc.account_value:,.2f}")
            if cc.realized_pnl is not None:
                parts.append(f"realized=${cc.realized_pnl:,.2f}")
            if cc.open_pnl is not None:
                parts.append(f"open=${cc.open_pnl:,.2f}")
            if cc.total_pnl is not None:
                parts.append(f"total=${cc.total_pnl:,.2f}")
            if cc.delta_vs_ledger is not None:
                parts.append(f"delta_vs_ledger=${cc.delta_vs_ledger:,.2f}")
            if cc.notes:
                parts.append(cc.notes)
            lines.append("  " + " | ".join(parts))
        lines.append("")

        if self.backup_files_found:
            lines.append("===== PORTFOLIO BACKUPS (read-only) =====")
            for path in self.backup_files_found:
                lines.append(f"  {path}")
            lines.append("")

        lines.extend([
            "===== VERDICT =====",
            f"Ledger {self.status.value}",
            "",
            "===== SAFETY CONFIRMATION =====",
            "No live trading files were modified.",
            "Read-only accounting audit — no portfolio or strategy changes.",
            "",
        ])
        return "\n".join(lines)


class LedgerReportStore:
    """JSON/TXT persistence — stdlib only."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_LEDGER_JSON_PATH
        self._txt_path = txt_path or DEFAULT_LEDGER_TXT_PATH

    def persist(self, report: LedgerAuditReport) -> Path:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: LedgerAuditReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
