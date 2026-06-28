"""
Independent double-entry verifier — Phase VI Sprint B6

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Standalone FIFO ledger from portfolio.csv — does NOT reuse dashboard, recompute,
ledger_audit, or core/trades accounting helpers.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
LEDGER_JSON_PATH = Path("tae_cash_flow_ledger.json")
STRATEGIC_JSON_PATH = Path("tae_strategic_performance_audit.json")
DEFAULT_JSON_PATH = Path("tae_independent_double_entry_verification.json")
DEFAULT_TXT_PATH = Path("tae_independent_double_entry_verification.txt")
CANONICAL_KERNEL_MODULE = "research_core/accounting/independent_double_entry.py"
CANONICAL_SCHEMA = "tae_independent_double_entry_verification"
FALLBACK_STARTING_CAPITAL = 30000.0
TOLERANCE = 0.05
MIN_SHARES = 0.0001
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class Verdict(str, Enum):
    INDEPENDENTLY_VERIFIED = "INDEPENDENTLY_VERIFIED"
    MISMATCH_FOUND = "MISMATCH_FOUND"


def _parse_dt(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _resolve_starting_capital() -> float:
    try:
        from config.settings import STARTING_CAPITAL

        return float(STARTING_CAPITAL)
    except (ImportError, AttributeError, TypeError, ValueError):
        return FALLBACK_STARTING_CAPITAL


def _read_portfolio_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


@dataclass
class FifoLot:
    shares: float
    cost_per_share: float


@dataclass
class ParsedRow:
    row_num: int
    dt: datetime
    date_str: str
    ticker: str
    action: str
    price: float
    shares: float
    current_price: float


@dataclass
class OpenPosition:
    ticker: str
    shares: float
    cost_basis: float
    market_price: float
    market_value: float
    unrealized_pnl: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "shares": round(self.shares, 6),
            "cost_basis": round(self.cost_basis, 2),
            "market_price": round(self.market_price, 4),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
        }


@dataclass
class MismatchDetail:
    row_num: int
    timestamp: str
    ticker: str
    action: str
    amount: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_num": self.row_num,
            "timestamp": self.timestamp,
            "ticker": self.ticker,
            "action": self.action,
            "amount": round(self.amount, 2),
            "reason": self.reason,
        }


@dataclass
class IndependentVerificationResult:
    starting_capital: float
    deposits: float
    withdrawals: float
    independent_cash: float
    independent_realized_pnl: float
    independent_open_market_value: float
    independent_open_cost_basis: float
    independent_open_unrealized_pnl: float
    independent_account_value: float
    independent_total_pnl: float
    internal_reconciliation_delta: float
    existing_ledger_account_value: float | None
    delta_vs_existing_ledger: float | None
    strategic_audit_realized_pnl: float | None
    dashboard_account_value: float | None
    delta_vs_dashboard_expected: float | None
    verdict: Verdict
    first_mismatch: MismatchDetail | None
    open_positions: list[OpenPosition]
    fifo_realized_by_ticker: dict[str, float]
    closed_trades_count: int
    orphan_sells: list[MismatchDetail]
    negative_cash_events: list[MismatchDetail]
    duplicate_suspicious_rows: list[MismatchDetail]
    micro_lot_warnings: list[MismatchDetail]
    transaction_count: int
    buy_count: int
    sell_count: int
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_independent_double_entry_verification",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "tolerance_usd": TOLERANCE,
            "verdict": self.verdict.value,
            "starting_capital": round(self.starting_capital, 2),
            "deposits": round(self.deposits, 2),
            "withdrawals": round(self.withdrawals, 2),
            "independent_cash": round(self.independent_cash, 2),
            "independent_realized_pnl": round(self.independent_realized_pnl, 2),
            "independent_open_market_value": round(self.independent_open_market_value, 2),
            "independent_open_cost_basis": round(self.independent_open_cost_basis, 2),
            "independent_open_unrealized_pnl": round(self.independent_open_unrealized_pnl, 2),
            "independent_account_value": round(self.independent_account_value, 2),
            "independent_total_pnl": round(self.independent_total_pnl, 2),
            "internal_reconciliation_delta": round(self.internal_reconciliation_delta, 2),
            "existing_ledger_account_value": (
                round(self.existing_ledger_account_value, 2)
                if self.existing_ledger_account_value is not None
                else None
            ),
            "delta_vs_existing_ledger": (
                round(self.delta_vs_existing_ledger, 2)
                if self.delta_vs_existing_ledger is not None
                else None
            ),
            "strategic_audit_realized_pnl": (
                round(self.strategic_audit_realized_pnl, 2)
                if self.strategic_audit_realized_pnl is not None
                else None
            ),
            "dashboard_account_value": (
                round(self.dashboard_account_value, 2)
                if self.dashboard_account_value is not None
                else None
            ),
            "delta_vs_dashboard_expected": (
                round(self.delta_vs_dashboard_expected, 2)
                if self.delta_vs_dashboard_expected is not None
                else None
            ),
            "first_mismatch": self.first_mismatch.to_dict() if self.first_mismatch else None,
            "open_positions": [p.to_dict() for p in self.open_positions],
            "fifo_realized_by_ticker": {
                k: round(v, 2) for k, v in sorted(self.fifo_realized_by_ticker.items())
            },
            "closed_trades_count": self.closed_trades_count,
            "orphan_sells": [m.to_dict() for m in self.orphan_sells],
            "negative_cash_events": [m.to_dict() for m in self.negative_cash_events],
            "duplicate_suspicious_rows": [m.to_dict() for m in self.duplicate_suspicious_rows],
            "micro_lot_warnings": [m.to_dict() for m in self.micro_lot_warnings],
            "transaction_count": self.transaction_count,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
        }

    def format_text(self) -> str:
        lines = [
            "===== VERIFICARE INDEPENDENTĂ DOUBLE-ENTRY — TAE FAZA VI B6 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Toleranță: ${TOLERANCE:.2f}",
            "",
            f"Verdict: {self.verdict.value}",
            "",
            "===== REZUMAT CONT INDEPENDENT (FIFO) =====",
            f"Capital inițial:              ${self.starting_capital:,.2f}",
            f"Depozite:                     ${self.deposits:,.2f}",
            f"Retrageri:                    ${self.withdrawals:,.2f}",
            f"Cash curent:                  ${self.independent_cash:,.2f}",
            f"PnL realizat (FIFO):          ${self.independent_realized_pnl:,.2f}",
            f"Valoare piață deschisă:       ${self.independent_open_market_value:,.2f}",
            f"Cost bază poziții deschise:   ${self.independent_open_cost_basis:,.2f}",
            f"PnL nerealizat deschis:       ${self.independent_open_unrealized_pnl:,.2f}",
            f"Valoare cont:                 ${self.independent_account_value:,.2f}",
            f"  (= cash + valoare piață deschisă)",
            f"PnL total:                    ${self.independent_total_pnl:,.2f}",
            f"Delta reconciliere internă:   ${self.internal_reconciliation_delta:,.2f}",
            "",
            f"Tranzacții: {self.transaction_count} (BUY {self.buy_count} / SELL {self.sell_count})",
            f"Tranzacții închise (SELL):    {self.closed_trades_count}",
            "",
        ]

        if self.first_mismatch:
            m = self.first_mismatch
            lines.extend([
                "===== PRIMA NEconcordanȚĂ =====",
                f"Rând #{m.row_num} | {m.timestamp} | {m.ticker} {m.action}",
                f"Suma: ${m.amount:,.2f}",
                f"Motiv: {m.reason}",
                "",
            ])

        lines.append("===== POZIȚII DESCHISE =====")
        if self.open_positions:
            for pos in self.open_positions:
                lines.append(
                    f"  {pos.ticker:8s} | {pos.shares:8.4f} acțiuni | "
                    f"cost ${pos.cost_basis:,.2f} | piață ${pos.market_value:,.2f} | "
                    f"PnL nerealizat ${pos.unrealized_pnl:,.2f}"
                )
        else:
            lines.append("  Nicio poziție deschisă.")
        lines.append("")

        lines.append("===== PnL REALIZAT FIFO PE TICKER =====")
        for ticker, pnl in sorted(self.fifo_realized_by_ticker.items()):
            lines.append(f"  {ticker:8s}: ${pnl:,.2f}")
        lines.append("")

        lines.append("===== COMPARAȚIE CU RAPOARTE EXISTENTE =====")
        if self.existing_ledger_account_value is not None:
            lines.append(
                f"  Ledger existent (B5):       ${self.existing_ledger_account_value:,.2f} "
                f"(delta ${self.delta_vs_existing_ledger:,.2f})"
            )
        else:
            lines.append("  Ledger existent (B5):       indisponibil")
        if self.dashboard_account_value is not None:
            lines.append(
                f"  Dashboard așteptat:         ${self.dashboard_account_value:,.2f} "
                f"(delta ${self.delta_vs_dashboard_expected:,.2f})"
            )
        else:
            lines.append("  Dashboard așteptat:         indisponibil")
        if self.strategic_audit_realized_pnl is not None:
            lines.append(
                f"  Strategic audit realized:   ${self.strategic_audit_realized_pnl:,.2f} "
                f"(stale portfolio.csv PnL column)"
            )
        lines.append("")

        issues = (
            self.orphan_sells
            + self.negative_cash_events
            + self.duplicate_suspicious_rows
            + self.micro_lot_warnings
        )
        lines.append("===== ALERTE =====")
        if self.orphan_sells:
            lines.append(f"  SELL orfan: {len(self.orphan_sells)}")
            for m in self.orphan_sells:
                lines.append(f"    #{m.row_num} {m.timestamp} {m.ticker} — {m.reason}")
        if self.negative_cash_events:
            lines.append(f"  Cash negativ: {len(self.negative_cash_events)}")
            for m in self.negative_cash_events:
                lines.append(f"    #{m.row_num} {m.timestamp} {m.ticker} — {m.reason}")
        if self.duplicate_suspicious_rows:
            lines.append(f"  Rânduri duplicate suspecte: {len(self.duplicate_suspicious_rows)}")
            for m in self.duplicate_suspicious_rows:
                lines.append(f"    #{m.row_num} {m.timestamp} {m.ticker} — {m.reason}")
        if self.micro_lot_warnings:
            lines.append(f"  Micro-loturi: {len(self.micro_lot_warnings)}")
            for m in self.micro_lot_warnings:
                lines.append(f"    #{m.row_num} {m.timestamp} {m.ticker} — {m.reason}")
        if not issues:
            lines.append("  Nicio alertă critică.")
        lines.extend([
            "",
            "===== NOTĂ METODĂ =====",
            "Calcul independent: FIFO, price×shares pentru cash, fără coloane PnL/Current_Value.",
            "Current_Price folosit doar pentru mark-to-market pe poziții deschise.",
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "Nu s-au modificat fișierele de trading live.",
            "",
        ])
        return "\n".join(lines)


class IndependentDoubleEntryVerifier:
    """Standalone FIFO double-entry reconstruction from portfolio.csv."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def verify(self) -> IndependentVerificationResult:
        starting_capital = _resolve_starting_capital()
        raw_rows = _read_portfolio_rows(PORTFOLIO_PATH)
        parsed = self._parse_rows(raw_rows)

        (
            cash,
            deposits,
            withdrawals,
            realized_pnl,
            realized_by_ticker,
            fifo_lots,
            latest_marks,
            buy_count,
            sell_count,
            closed_count,
            orphan_sells,
            negative_cash,
            duplicates,
            micro_lots,
            first_mismatch,
        ) = self._process_fifo(parsed, starting_capital)

        open_positions = self._build_open_positions(fifo_lots, latest_marks)
        open_market_value = sum(p.market_value for p in open_positions)
        open_cost_basis = sum(p.cost_basis for p in open_positions)
        open_unrealized = open_market_value - open_cost_basis
        account_value = cash + open_market_value
        total_pnl = account_value - starting_capital - deposits + withdrawals

        formula_value = (
            starting_capital + deposits - withdrawals + realized_pnl + open_unrealized
        )
        internal_delta = account_value - formula_value

        ledger_av, strategic_realized, dashboard_av = self._load_external_comparisons()
        delta_ledger = (
            account_value - ledger_av if ledger_av is not None else None
        )
        delta_dashboard = (
            account_value - dashboard_av if dashboard_av is not None else None
        )

        verdict = Verdict.INDEPENDENTLY_VERIFIED
        if orphan_sells or negative_cash:
            verdict = Verdict.MISMATCH_FOUND
        elif abs(internal_delta) > TOLERANCE:
            verdict = Verdict.MISMATCH_FOUND
        elif delta_dashboard is not None and abs(delta_dashboard) > TOLERANCE:
            verdict = Verdict.MISMATCH_FOUND
        elif delta_ledger is not None and abs(delta_ledger) > TOLERANCE:
            verdict = Verdict.MISMATCH_FOUND

        if first_mismatch is None and verdict == Verdict.MISMATCH_FOUND:
            if abs(internal_delta) > TOLERANCE:
                first_mismatch = MismatchDetail(
                    row_num=0,
                    timestamp="",
                    ticker="",
                    action="RECONCILE",
                    amount=internal_delta,
                    reason=(
                        f"Reconciliere internă: cont ${account_value:,.2f} vs "
                        f"formulă ${formula_value:,.2f} (delta ${internal_delta:,.2f})"
                    ),
                )
            elif delta_dashboard is not None and abs(delta_dashboard) > TOLERANCE:
                first_mismatch = MismatchDetail(
                    row_num=0,
                    timestamp="",
                    ticker="",
                    action="COMPARE",
                    amount=delta_dashboard,
                    reason=(
                        f"Delta vs dashboard: ${delta_dashboard:,.2f} "
                        f"(independent ${account_value:,.2f} vs "
                        f"dashboard ${dashboard_av:,.2f})"
                    ),
                )
            elif delta_ledger is not None and abs(delta_ledger) > TOLERANCE:
                first_mismatch = MismatchDetail(
                    row_num=0,
                    timestamp="",
                    ticker="",
                    action="COMPARE",
                    amount=delta_ledger,
                    reason=(
                        f"Delta vs ledger B5: ${delta_ledger:,.2f} "
                        f"(independent ${account_value:,.2f} vs "
                        f"ledger ${ledger_av:,.2f})"
                    ),
                )

        result = IndependentVerificationResult(
            starting_capital=starting_capital,
            deposits=deposits,
            withdrawals=withdrawals,
            independent_cash=cash,
            independent_realized_pnl=realized_pnl,
            independent_open_market_value=open_market_value,
            independent_open_cost_basis=open_cost_basis,
            independent_open_unrealized_pnl=open_unrealized,
            independent_account_value=account_value,
            independent_total_pnl=total_pnl,
            internal_reconciliation_delta=internal_delta,
            existing_ledger_account_value=ledger_av,
            delta_vs_existing_ledger=delta_ledger,
            strategic_audit_realized_pnl=strategic_realized,
            dashboard_account_value=dashboard_av,
            delta_vs_dashboard_expected=delta_dashboard,
            verdict=verdict,
            first_mismatch=first_mismatch,
            open_positions=open_positions,
            fifo_realized_by_ticker=realized_by_ticker,
            closed_trades_count=closed_count,
            orphan_sells=orphan_sells,
            negative_cash_events=negative_cash,
            duplicate_suspicious_rows=duplicates,
            micro_lot_warnings=micro_lots,
            transaction_count=len(parsed),
            buy_count=buy_count,
            sell_count=sell_count,
        )
        self._persist(result)
        return result

    def _parse_rows(self, raw_rows: list[dict[str, str]]) -> list[ParsedRow]:
        parsed: list[ParsedRow] = []
        for idx, row in enumerate(raw_rows, start=1):
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            action = row.get("Action", "").strip().upper()
            if action == "WITHDRAWAL":
                action = "WITHDRAW"
            ticker = row.get("Ticker", "").strip()
            if not action:
                continue
            parsed.append(
                ParsedRow(
                    row_num=idx,
                    dt=dt,
                    date_str=row.get("Date", "").strip(),
                    ticker=ticker,
                    action=action,
                    price=_safe_float(row.get("Price")),
                    shares=_safe_float(row.get("Shares")),
                    current_price=_safe_float(row.get("Current_Price")),
                )
            )
        parsed.sort(key=lambda r: (r.dt, r.row_num))
        return parsed

    def _process_fifo(
        self,
        parsed: list[ParsedRow],
        starting_capital: float,
    ) -> tuple[
        float,
        float,
        float,
        float,
        dict[str, float],
        dict[str, list[FifoLot]],
        dict[str, float],
        int,
        int,
        int,
        list[MismatchDetail],
        list[MismatchDetail],
        list[MismatchDetail],
        list[MismatchDetail],
        MismatchDetail | None,
    ]:
        cash = starting_capital
        deposits = 0.0
        withdrawals = 0.0
        realized_pnl = 0.0
        realized_by_ticker: dict[str, float] = defaultdict(float)
        fifo_lots: dict[str, list[FifoLot]] = defaultdict(list)
        latest_marks: dict[str, float] = {}
        buy_count = 0
        sell_count = 0
        closed_count = 0
        orphan_sells: list[MismatchDetail] = []
        negative_cash: list[MismatchDetail] = []
        duplicates: list[MismatchDetail] = []
        micro_lots: list[MismatchDetail] = []
        first_mismatch: MismatchDetail | None = None
        seen: set[tuple[str, str, str, float, float]] = set()

        def record_first(m: MismatchDetail) -> None:
            nonlocal first_mismatch
            if first_mismatch is None:
                first_mismatch = m

        for row in parsed:
            key = (
                row.date_str,
                row.ticker,
                row.action,
                round(row.price, 4),
                round(row.shares, 6),
            )
            if key in seen:
                dup = MismatchDetail(
                    row_num=row.row_num,
                    timestamp=row.date_str,
                    ticker=row.ticker,
                    action=row.action,
                    amount=row.price * row.shares,
                    reason="Rând duplicat suspect (timestamp/ticker/acțiune/preț/acțiuni identice)",
                )
                duplicates.append(dup)
                record_first(dup)
            seen.add(key)

            if row.current_price > 0 and row.ticker not in ("", "CASH"):
                latest_marks[row.ticker] = row.current_price

            action = row.action

            if action == "DEPOSIT":
                amount = row.price * row.shares if row.shares else row.price
                deposits += amount
                cash += amount

            elif action == "WITHDRAW":
                amount = row.price * row.shares if row.shares else row.price
                withdrawals += amount
                cash -= amount

            elif action == "DIVIDEND":
                amount = row.price * row.shares if row.shares else row.price
                cash += amount

            elif action in ("FEE", "COMMISSION"):
                amount = row.price * row.shares if row.shares else row.price
                cash -= amount

            elif action == "BUY":
                if row.ticker == "CASH":
                    continue
                buy_count += 1
                cost = row.price * row.shares
                cash -= cost
                fifo_lots[row.ticker].append(
                    FifoLot(shares=row.shares, cost_per_share=row.price)
                )
                if 0 < row.shares < 0.01 and cost < 1.0:
                    micro_lots.append(
                        MismatchDetail(
                            row_num=row.row_num,
                            timestamp=row.date_str,
                            ticker=row.ticker,
                            action=action,
                            amount=cost,
                            reason=(
                                f"Micro-lot: {row.shares:.6f} acțiuni @ ${row.price:.2f} "
                                f"(cost ${cost:.4f})"
                            ),
                        )
                    )

            elif action == "SELL":
                if row.ticker == "CASH":
                    continue
                sell_count += 1
                closed_count += 1
                proceeds = row.price * row.shares
                cash += proceeds

                lots = fifo_lots[row.ticker]
                total_held = sum(lot.shares for lot in lots)
                if row.shares > total_held + MIN_SHARES:
                    orphan = MismatchDetail(
                        row_num=row.row_num,
                        timestamp=row.date_str,
                        ticker=row.ticker,
                        action=action,
                        amount=proceeds,
                        reason=(
                            f"SELL orfan: {row.shares:.4f} acțiuni vândute, "
                            f"doar {total_held:.4f} în FIFO"
                        ),
                    )
                    orphan_sells.append(orphan)
                    record_first(orphan)

                remaining = row.shares
                while remaining > MIN_SHARES and lots:
                    lot = lots[0]
                    take = min(remaining, lot.shares)
                    lot_pnl = (row.price - lot.cost_per_share) * take
                    realized_pnl += lot_pnl
                    realized_by_ticker[row.ticker] += lot_pnl
                    lot.shares -= take
                    remaining -= take
                    if lot.shares <= MIN_SHARES:
                        lots.pop(0)

            if cash < -TOLERANCE:
                neg = MismatchDetail(
                    row_num=row.row_num,
                    timestamp=row.date_str,
                    ticker=row.ticker,
                    action=action,
                    amount=cash,
                    reason=f"Cash negativ după tranzacție: ${cash:,.2f}",
                )
                negative_cash.append(neg)
                record_first(neg)

            # Internal drift check after each row
            open_mv = 0.0
            open_cb = 0.0
            for ticker, lots in fifo_lots.items():
                ticker_shares = sum(lot.shares for lot in lots)
                if ticker_shares <= MIN_SHARES:
                    continue
                mark = latest_marks.get(ticker, 0.0)
                if mark <= 0:
                    mark = sum(lot.shares * lot.cost_per_share for lot in lots) / ticker_shares
                open_cb += sum(lot.shares * lot.cost_per_share for lot in lots)
                open_mv += ticker_shares * mark
            open_unreal = open_mv - open_cb
            ledger_av = cash + open_mv
            formula_av = starting_capital + deposits - withdrawals + realized_pnl + open_unreal
            drift = ledger_av - formula_av
            if abs(drift) > TOLERANCE and first_mismatch is None:
                first_mismatch = MismatchDetail(
                    row_num=row.row_num,
                    timestamp=row.date_str,
                    ticker=row.ticker,
                    action=action,
                    amount=drift,
                    reason=(
                        f"Drift reconciliere ${drift:,.2f}: "
                        f"cont ${ledger_av:,.2f} vs formulă ${formula_av:,.2f}"
                    ),
                )

        return (
            cash,
            deposits,
            withdrawals,
            realized_pnl,
            dict(realized_by_ticker),
            fifo_lots,
            latest_marks,
            buy_count,
            sell_count,
            closed_count,
            orphan_sells,
            negative_cash,
            duplicates,
            micro_lots,
            first_mismatch,
        )

    def _build_open_positions(
        self,
        fifo_lots: dict[str, list[FifoLot]],
        latest_marks: dict[str, float],
    ) -> list[OpenPosition]:
        positions: list[OpenPosition] = []
        for ticker in sorted(fifo_lots):
            lots = fifo_lots[ticker]
            shares = sum(lot.shares for lot in lots)
            if shares <= MIN_SHARES:
                continue
            cost_basis = sum(lot.shares * lot.cost_per_share for lot in lots)
            mark = latest_marks.get(ticker, 0.0)
            if mark <= 0:
                mark = cost_basis / shares
            market_value = shares * mark
            positions.append(
                OpenPosition(
                    ticker=ticker,
                    shares=shares,
                    cost_basis=cost_basis,
                    market_price=mark,
                    market_value=market_value,
                    unrealized_pnl=market_value - cost_basis,
                )
            )
        return positions

    def _load_external_comparisons(
        self,
    ) -> tuple[float | None, float | None, float | None]:
        ledger_av: float | None = None
        strategic_realized: float | None = None
        dashboard_av: float | None = None

        if LEDGER_JSON_PATH.is_file():
            try:
                data = json.loads(LEDGER_JSON_PATH.read_text(encoding="utf-8"))
                summary = data.get("summary", {})
                ledger_av = _safe_float(
                    summary.get("account_value_from_portfolio_csv_marks")
                    or summary.get("final_account_value")
                )
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug("Ledger JSON read failed: %s", exc)

        if STRATEGIC_JSON_PATH.is_file():
            try:
                data = json.loads(STRATEGIC_JSON_PATH.read_text(encoding="utf-8"))
                strategic_realized = _safe_float(
                    data.get("performance", {}).get("all_history_realized_pnl")
                )
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug("Strategic JSON read failed: %s", exc)

        try:
            import pandas as pd
            from tools.dashboard_account_reconcile import compute_account_metrics

            df = pd.read_csv(PORTFOLIO_PATH)
            metrics = compute_account_metrics(df)
            dashboard_av = _safe_float(metrics.get("computed_account_value"))
        except Exception as exc:
            logger.debug("Dashboard comparison skipped: %s", exc)

        return ledger_av, strategic_realized, dashboard_av

    def _persist(self, result: IndependentVerificationResult) -> None:
        self._json_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(result.format_text() + "\n", encoding="utf-8")


def load_canonical_verification(
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load canonical accounting verification JSON — read-only, no recalculation."""
    path = json_path or DEFAULT_JSON_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Canonical verification read failed: %s", exc)
        return None
    if data.get("schema") != CANONICAL_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data
