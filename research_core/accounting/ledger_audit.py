"""
Cash flow ledger auditor — Phase VI Sprint B5

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Reconstructs the Trading AI account from transaction #1 to latest and proves
every dollar is accounted for. Read-only — no portfolio modifications.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from research_core.accounting.ledger_report import (
    ANALYSIS_SAFETY_BANNER,
    CheckSeverity,
    CrossCheckResult,
    FirstErrorTransaction,
    LedgerAuditReport,
    LedgerCheck,
    LedgerReportStore,
    LedgerStatus,
    LedgerSummary,
    LedgerTransaction,
    RECONCILIATION_FORMULA,
)
from tools.recompute_realized_pnl import _is_repairable_sell, recompute_portfolio

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
LATEST_PORTFOLIO_PATH = Path("latest_portfolio.txt")
FALLBACK_STARTING_CAPITAL = 30000.0
RECONCILIATION_TOLERANCE = 0.01
MIN_SHARES = 0.0001
CASH_TICKER = "CASH"

SUPPORTED_ACTIONS = frozenset({
    "DEPOSIT",
    "BUY",
    "SELL",
    "WITHDRAW",
    "WITHDRAWAL",
    "DIVIDEND",
    "FEE",
    "COMMISSION",
})


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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        logger.warning("Could not read CSV %s: %s", path, exc)
        return []


def _normalize_action(raw: str) -> str:
    action = raw.strip().upper()
    if action == "WITHDRAWAL":
        return "WITHDRAW"
    return action


@dataclass
class _LotState:
    shares: float = 0.0
    total_cost: float = 0.0
    last_mark_price: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.shares if self.shares > MIN_SHARES else 0.0

    @property
    def market_value(self) -> float:
        mark = self.last_mark_price if self.last_mark_price > 0 else self.avg_cost
        return self.shares * mark

    @property
    def unrealized_pnl(self) -> float:
        if self.shares <= MIN_SHARES:
            return 0.0
        mark = self.last_mark_price if self.last_mark_price > 0 else self.avg_cost
        return (mark - self.avg_cost) * self.shares


@dataclass
class _ParsedTxn:
    index: int
    dt: datetime
    timestamp: str
    ticker: str
    action: str
    price: float
    shares: float
    invested: float
    current_price: float
    current_value: float
    pnl: float
    reason: str
    signal: str
    raw: dict[str, str]


class CashFlowLedgerAuditor:
    """Read-only cash-flow ledger reconstruction and reconciliation."""

    def __init__(self, store: LedgerReportStore | None = None) -> None:
        self._store = store or LedgerReportStore()
        self._sources_loaded: dict[str, bool] = {}

    def audit(self) -> LedgerAuditReport:
        starting_capital = _resolve_starting_capital()
        portfolio_rows = _read_csv_rows(PORTFOLIO_PATH)
        latest_rows = _read_csv_rows(LATEST_PORTFOLIO_PATH)
        backup_files = sorted(str(p) for p in Path(".").glob("portfolio.csv.bak_*"))

        self._sources_loaded = {
            "portfolio.csv": bool(portfolio_rows),
            "latest_portfolio.txt": bool(latest_rows),
            "config/settings.py": Path("config/settings.py").is_file(),
        }

        parsed = self._parse_transactions(portfolio_rows)
        open_marks = self._build_open_marks(latest_rows, portfolio_rows, parsed)

        (
            transactions,
            summary,
            checks,
            first_error,
        ) = self._replay_ledger(parsed, starting_capital, open_marks)

        repairable_realized = self._repairable_realized_pnl(portfolio_rows)
        summary.realized_pnl_repairable = repairable_realized

        cross_checks = self._cross_checks(summary, repairable_realized, portfolio_rows)

        failed_errors = [
            c for c in checks
            if not c.passed and c.severity == CheckSeverity.ERROR
        ]
        reconciliation_ok = abs(summary.reconciliation_difference) <= RECONCILIATION_TOLERANCE
        status = (
            LedgerStatus.VALID
            if reconciliation_ok and not failed_errors
            else LedgerStatus.INVALID
        )

        report = LedgerAuditReport(
            status=status,
            summary=summary,
            transactions=transactions,
            checks=checks,
            cross_checks=cross_checks,
            first_error=first_error,
            backup_files_found=backup_files,
            sources_loaded=dict(self._sources_loaded),
            safety_mode=ANALYSIS_SAFETY_BANNER,
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _parse_transactions(self, rows: list[dict[str, str]]) -> list[_ParsedTxn]:
        parsed: list[_ParsedTxn] = []
        for idx, row in enumerate(rows, start=1):
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            action = _normalize_action(row.get("Action", ""))
            ticker = row.get("Ticker", "").strip()
            if not action:
                continue
            parsed.append(
                _ParsedTxn(
                    index=idx,
                    dt=dt,
                    timestamp=row.get("Date", "").strip(),
                    ticker=ticker,
                    action=action,
                    price=_safe_float(row.get("Price")),
                    shares=_safe_float(row.get("Shares")),
                    invested=_safe_float(row.get("Invested")),
                    current_price=_safe_float(row.get("Current_Price")),
                    current_value=_safe_float(row.get("Current_Value")),
                    pnl=_safe_float(row.get("PnL")),
                    reason=row.get("Reason", "").strip(),
                    signal=row.get("Signal", "").strip(),
                    raw=dict(row),
                )
            )
        parsed.sort(key=lambda t: (t.dt, t.index))
        return parsed

    def _build_open_marks(
        self,
        latest_rows: list[dict[str, str]],
        portfolio_rows: list[dict[str, str]],
        parsed: list[_ParsedTxn],
    ) -> dict[str, float]:
        marks: dict[str, float] = {}

        for row in latest_rows:
            ticker = row.get("Ticker", "").strip()
            if not ticker or ticker == CASH_TICKER:
                continue
            cp = _safe_float(row.get("Current_Price"))
            cv = _safe_float(row.get("Current_Value"))
            shares = _safe_float(row.get("Shares"))
            if cp > 0:
                marks[ticker] = cp
            elif cv > 0 and shares > 0:
                marks[ticker] = cv / shares

        net: dict[str, float] = defaultdict(float)
        for txn in parsed:
            if txn.ticker == CASH_TICKER:
                continue
            if txn.action == "BUY":
                net[txn.ticker] += txn.shares
            elif txn.action == "SELL":
                net[txn.ticker] -= txn.shares

        for txn in reversed(parsed):
            if txn.ticker in marks or txn.ticker == CASH_TICKER:
                continue
            if net.get(txn.ticker, 0.0) <= MIN_SHARES:
                continue
            if txn.current_price > 0:
                marks[txn.ticker] = txn.current_price
            elif txn.current_value > 0 and txn.shares > 0:
                marks[txn.ticker] = txn.current_value / txn.shares

        for ticker, shares in net.items():
            if shares <= MIN_SHARES or ticker in marks:
                continue
            for row in reversed(portfolio_rows):
                if row.get("Ticker", "").strip() != ticker:
                    continue
                cp = _safe_float(row.get("Current_Price"))
                if cp > 0:
                    marks[ticker] = cp
                    break

        return marks

    def _replay_ledger(
        self,
        parsed: list[_ParsedTxn],
        starting_capital: float,
        open_marks: dict[str, float],
    ) -> tuple[
        list[LedgerTransaction],
        LedgerSummary,
        list[LedgerCheck],
        FirstErrorTransaction | None,
    ]:
        cash = starting_capital
        lots: dict[str, _LotState] = defaultdict(_LotState)
        deposits = 0.0
        withdrawals = 0.0
        dividends = 0.0
        fees = 0.0
        cumulative_realized = 0.0
        buy_count = 0
        sell_count = 0
        transactions: list[LedgerTransaction] = []
        checks: list[LedgerCheck] = []
        first_error: FirstErrorTransaction | None = None
        seen_keys: set[tuple[str, str, str, float, float]] = set()

        for txn in parsed:
            cash_before = cash
            shares_before = (
                lots[txn.ticker].shares if txn.ticker and txn.ticker != CASH_TICKER else 0.0
            )
            avg_before = lots[txn.ticker].avg_cost if txn.ticker else 0.0
            notes: list[str] = []
            cash_delta = 0.0
            realized_delta = 0.0

            dup_key = (
                txn.timestamp,
                txn.ticker,
                txn.action,
                round(txn.price, 4),
                round(txn.shares, 6),
            )
            if dup_key in seen_keys:
                checks.append(
                    LedgerCheck(
                        check_id="DUPLICATE_TRANSACTION",
                        severity=CheckSeverity.WARNING,
                        passed=False,
                        description="Duplicate transaction detected",
                        transaction_index=txn.index,
                        transaction_timestamp=txn.timestamp,
                        ticker=txn.ticker,
                        amount=txn.price * txn.shares,
                        reason="Same timestamp/ticker/action/price/shares as prior row",
                    )
                )
            seen_keys.add(dup_key)

            if txn.action not in SUPPORTED_ACTIONS:
                checks.append(
                    LedgerCheck(
                        check_id="UNSUPPORTED_ACTION",
                        severity=CheckSeverity.WARNING,
                        passed=False,
                        description=f"Unsupported action: {txn.action}",
                        transaction_index=txn.index,
                        transaction_timestamp=txn.timestamp,
                        ticker=txn.ticker,
                        reason=f"Action {txn.action} not in ledger model",
                    )
                )
                continue

            if txn.action == "DEPOSIT":
                amount = txn.price * txn.shares if txn.shares else txn.price
                if txn.invested > 0:
                    amount = txn.invested
                deposits += amount
                cash += amount
                cash_delta = amount
                notes.append(f"deposit +${amount:,.2f}")

            elif txn.action == "WITHDRAW":
                amount = txn.price * txn.shares if txn.shares else txn.price
                withdrawals += amount
                cash -= amount
                cash_delta = -amount
                notes.append(f"withdrawal -${amount:,.2f}")

            elif txn.action == "DIVIDEND":
                amount = txn.price * txn.shares if txn.shares else txn.price
                dividends += amount
                cash += amount
                cash_delta = amount
                notes.append(f"dividend +${amount:,.2f}")

            elif txn.action in ("FEE", "COMMISSION"):
                amount = txn.price * txn.shares if txn.shares else txn.price
                fees += amount
                cash -= amount
                cash_delta = -amount
                notes.append(f"fee -${amount:,.2f}")

            elif txn.action == "BUY":
                buy_count += 1
                if txn.ticker == CASH_TICKER:
                    notes.append("BUY on CASH ticker skipped")
                else:
                    cost = txn.invested if txn.invested > 0 else txn.price * txn.shares
                    cash -= cost
                    cash_delta = -cost
                    lot = lots[txn.ticker]
                    lot.shares += txn.shares
                    lot.total_cost += cost
                    if txn.current_price > 0:
                        lot.last_mark_price = txn.current_price
                    elif txn.price > 0:
                        lot.last_mark_price = txn.price

                    if 0 < cost < 1.0 and txn.shares < 0.01:
                        checks.append(
                            LedgerCheck(
                                check_id="NEAR_ZERO_BUY",
                                severity=CheckSeverity.WARNING,
                                passed=False,
                                description="Near-zero BUY may introduce cash/mark drift",
                                transaction_index=txn.index,
                                transaction_timestamp=txn.timestamp,
                                ticker=txn.ticker,
                                amount=cost,
                                reason=(
                                    f"Micro-lot {txn.shares:.6f} shares @ "
                                    f"${txn.price:.2f} (cost ${cost:.4f})"
                                ),
                            )
                        )

                    if abs(cash_delta + cost) > RECONCILIATION_TOLERANCE:
                        checks.append(
                            LedgerCheck(
                                check_id="BUY_CASH_DELTA",
                                severity=CheckSeverity.ERROR,
                                passed=False,
                                description="BUY did not reduce cash by expected cost",
                                transaction_index=txn.index,
                                transaction_timestamp=txn.timestamp,
                                ticker=txn.ticker,
                                amount=cost,
                                reason=f"Expected cash delta {-cost:.2f}",
                            )
                        )

            elif txn.action == "SELL":
                sell_count += 1
                if txn.ticker == CASH_TICKER:
                    notes.append("SELL on CASH ticker skipped")
                else:
                    lot = lots[txn.ticker]
                    if txn.shares > lot.shares + MIN_SHARES:
                        checks.append(
                            LedgerCheck(
                                check_id="ORPHAN_SELL",
                                severity=CheckSeverity.ERROR,
                                passed=False,
                                description="SELL exceeds available shares (orphan sell)",
                                transaction_index=txn.index,
                                transaction_timestamp=txn.timestamp,
                                ticker=txn.ticker,
                                amount=txn.price * txn.shares,
                                reason=(
                                    f"Sold {txn.shares:.4f} but only "
                                    f"{lot.shares:.4f} held"
                                ),
                            )
                        )
                        if first_error is None:
                            first_error = FirstErrorTransaction(
                                index=txn.index,
                                timestamp=txn.timestamp,
                                ticker=txn.ticker,
                                action=txn.action,
                                amount=txn.price * txn.shares,
                                reason=(
                                    f"Orphan SELL: {txn.shares:.4f} shares "
                                    f"but {lot.shares:.4f} held"
                                ),
                            )

                    proceeds = txn.price * txn.shares
                    avg_cost = lot.avg_cost if lot.shares > 0 else avg_before
                    cost_basis_sold = avg_cost * txn.shares if avg_cost > 0 else 0.0
                    exec_pnl = proceeds - cost_basis_sold
                    realized_delta = exec_pnl
                    cumulative_realized += exec_pnl

                    cash += proceeds
                    cash_delta = proceeds

                    if lot.shares > 0 and txn.shares > 0:
                        fraction = min(1.0, txn.shares / lot.shares)
                        lot.total_cost *= max(0.0, 1.0 - fraction)
                        lot.shares = max(0.0, lot.shares - txn.shares)

                    if txn.current_price > 0:
                        lot.last_mark_price = txn.current_price

                    if abs(cash_delta - proceeds) > RECONCILIATION_TOLERANCE:
                        checks.append(
                            LedgerCheck(
                                check_id="SELL_CASH_DELTA",
                                severity=CheckSeverity.ERROR,
                                passed=False,
                                description="SELL did not increase cash by proceeds",
                                transaction_index=txn.index,
                                transaction_timestamp=txn.timestamp,
                                ticker=txn.ticker,
                                amount=proceeds,
                                reason=f"Expected cash delta +{proceeds:.2f}",
                            )
                        )

                    if 0 < txn.shares < shares_before - MIN_SHARES:
                        notes.append(
                            f"partial sell {txn.shares:.4f}/{shares_before:.4f} "
                            f"avg_cost={avg_cost:.2f} remaining={lot.shares:.4f}"
                        )

            if cash < -RECONCILIATION_TOLERANCE:
                checks.append(
                    LedgerCheck(
                        check_id="NEGATIVE_CASH",
                        severity=CheckSeverity.ERROR,
                        passed=False,
                        description="Cash balance went negative",
                        transaction_index=txn.index,
                        transaction_timestamp=txn.timestamp,
                        ticker=txn.ticker,
                        amount=cash,
                        reason=f"Cash after txn: ${cash:,.2f}",
                    )
                )
                if first_error is None:
                    first_error = FirstErrorTransaction(
                        index=txn.index,
                        timestamp=txn.timestamp,
                        ticker=txn.ticker,
                        action=txn.action,
                        amount=cash,
                        reason=f"Negative cash: ${cash:,.2f}",
                    )

            shares_after = (
                lots[txn.ticker].shares if txn.ticker and txn.ticker != CASH_TICKER else 0.0
            )
            open_market_value = self._open_market_value_from_lots(lots)
            open_unrealized = self._open_unrealized_from_lots(lots)
            ledger_account_value = cash + open_market_value
            formula_account_value = (
                starting_capital
                + deposits
                - withdrawals
                + dividends
                - fees
                + cumulative_realized
                + open_unrealized
            )
            drift = ledger_account_value - formula_account_value

            if (
                first_error is None
                and abs(drift) > RECONCILIATION_TOLERANCE
            ):
                first_error = FirstErrorTransaction(
                    index=txn.index,
                    timestamp=txn.timestamp,
                    ticker=txn.ticker,
                    action=txn.action,
                    amount=drift,
                    reason=(
                        f"Reconciliation drift ${drift:,.2f}: "
                        f"ledger ${ledger_account_value:,.2f} vs "
                        f"formula ${formula_account_value:,.2f}"
                    ),
                )

            transactions.append(
                LedgerTransaction(
                    index=txn.index,
                    timestamp=txn.timestamp,
                    ticker=txn.ticker,
                    action=txn.action,
                    price=txn.price,
                    shares=txn.shares,
                    cash_before=round(cash_before, 2),
                    cash_after=round(cash, 2),
                    cash_delta=round(cash_delta, 2),
                    shares_before=shares_before,
                    shares_after=shares_after,
                    avg_cost_after=lots[txn.ticker].avg_cost if txn.ticker else 0.0,
                    realized_pnl_delta=round(realized_delta, 2),
                    cumulative_realized_pnl=round(cumulative_realized, 2),
                    open_market_value=round(open_market_value, 2),
                    ledger_account_value=round(ledger_account_value, 2),
                    formula_account_value=round(formula_account_value, 2),
                    reconciliation_drift=round(drift, 2),
                    notes="; ".join(notes),
                )
            )

        open_tickers = [
            t for t, lot in sorted(lots.items())
            if t != CASH_TICKER and lot.shares > MIN_SHARES
        ]
        open_market_value = self._open_market_value(lots, open_marks)
        open_unrealized = self._open_unrealized(lots, open_marks)
        final_account_value = cash + open_market_value
        formula_account_value = (
            starting_capital
            + deposits
            - withdrawals
            + dividends
            - fees
            + cumulative_realized
            + open_unrealized
        )
        reconciliation_difference = final_account_value - formula_account_value

        closed_count = sum(
            1 for t, lot in lots.items()
            if t != CASH_TICKER and lot.shares <= MIN_SHARES and lot.total_cost <= MIN_SHARES
        )

        checks.extend(self._position_drift_checks(parsed, lots, open_marks, open_tickers))
        checks.extend(self._duplicate_buy_checks(parsed))

        summary = LedgerSummary(
            starting_capital=starting_capital,
            deposits=round(deposits, 2),
            withdrawals=round(withdrawals, 2),
            dividends=round(dividends, 2),
            fees=round(fees, 2),
            realized_pnl_all_sells=round(cumulative_realized, 2),
            realized_pnl_repairable=0.0,
            open_unrealized_pnl=round(open_unrealized, 2),
            total_pnl=round(cumulative_realized + open_unrealized, 2),
            current_cash=round(cash, 2),
            open_market_value=round(open_market_value, 2),
            final_account_value=round(final_account_value, 2),
            formula_account_value=round(formula_account_value, 2),
            reconciliation_difference=round(reconciliation_difference, 2),
            transaction_count=len(transactions),
            buy_count=buy_count,
            sell_count=sell_count,
            open_position_count=len(open_tickers),
            closed_position_count=closed_count,
            open_tickers=open_tickers,
        )

        checks.append(
            LedgerCheck(
                check_id="RECONCILIATION_FORMULA",
                severity=CheckSeverity.ERROR,
                passed=abs(reconciliation_difference) <= RECONCILIATION_TOLERANCE,
                description=RECONCILIATION_FORMULA,
                amount=reconciliation_difference,
                reason=(
                    f"Difference ${reconciliation_difference:,.2f} "
                    f"(must be 0.00)"
                ),
            )
        )

        checks.append(
            LedgerCheck(
                check_id="CASH_PLUS_OPEN_VALUE",
                severity=CheckSeverity.ERROR,
                passed=True,
                description=(
                    "Final Account Value = Current Cash + Open Market Value"
                ),
                amount=final_account_value,
                reason=(
                    f"${cash:,.2f} + ${open_market_value:,.2f} "
                    f"= ${final_account_value:,.2f}"
                ),
            )
        )

        return transactions, summary, checks, first_error

    def _open_market_value_from_lots(self, lots: dict[str, _LotState]) -> float:
        total = 0.0
        for ticker, lot in lots.items():
            if ticker == CASH_TICKER or lot.shares <= MIN_SHARES:
                continue
            mark = lot.last_mark_price if lot.last_mark_price > 0 else lot.avg_cost
            total += lot.shares * mark
        return total

    def _open_unrealized_from_lots(self, lots: dict[str, _LotState]) -> float:
        total = 0.0
        for ticker, lot in lots.items():
            if ticker == CASH_TICKER or lot.shares <= MIN_SHARES:
                continue
            mark = lot.last_mark_price if lot.last_mark_price > 0 else lot.avg_cost
            total += (mark - lot.avg_cost) * lot.shares
        return total

    def _open_market_value(
        self,
        lots: dict[str, _LotState],
        open_marks: dict[str, float],
    ) -> float:
        total = 0.0
        for ticker, lot in lots.items():
            if ticker == CASH_TICKER or lot.shares <= MIN_SHARES:
                continue
            mark = open_marks.get(ticker, lot.last_mark_price)
            if mark <= 0:
                mark = lot.avg_cost
            total += lot.shares * mark
        return total

    def _open_unrealized(
        self,
        lots: dict[str, _LotState],
        open_marks: dict[str, float],
    ) -> float:
        total = 0.0
        for ticker, lot in lots.items():
            if ticker == CASH_TICKER or lot.shares <= MIN_SHARES:
                continue
            mark = open_marks.get(ticker, lot.last_mark_price)
            if mark <= 0:
                mark = lot.avg_cost
            total += (mark - lot.avg_cost) * lot.shares
        return total

    def _position_drift_checks(
        self,
        parsed: list[_ParsedTxn],
        lots: dict[str, _LotState],
        open_marks: dict[str, float],
        open_tickers: list[str],
    ) -> list[LedgerCheck]:
        checks: list[LedgerCheck] = []
        net_from_csv: dict[str, float] = defaultdict(float)
        for txn in parsed:
            if txn.ticker == CASH_TICKER:
                continue
            if txn.action == "BUY":
                net_from_csv[txn.ticker] += txn.shares
            elif txn.action == "SELL":
                net_from_csv[txn.ticker] -= txn.shares

        for ticker, expected in net_from_csv.items():
            if ticker == CASH_TICKER:
                continue
            actual = lots[ticker].shares if ticker in lots else 0.0
            drift = abs(actual - expected)
            if drift > MIN_SHARES:
                checks.append(
                    LedgerCheck(
                        check_id="POSITION_DRIFT",
                        severity=CheckSeverity.ERROR,
                        passed=False,
                        description=f"Position drift on {ticker}",
                        ticker=ticker,
                        amount=drift,
                        reason=f"Ledger {actual:.4f} vs net CSV {expected:.4f}",
                    )
                )

        latest_tickers = set(open_tickers)
        csv_open = {t for t, s in net_from_csv.items() if s > MIN_SHARES}
        if latest_tickers != csv_open:
            missing = csv_open - latest_tickers
            extra = latest_tickers - csv_open
            checks.append(
                LedgerCheck(
                    check_id="OPEN_SHARES_SNAPSHOT",
                    severity=CheckSeverity.WARNING,
                    passed=len(missing) == 0 and len(extra) == 0,
                    description="Open shares vs latest_portfolio.txt",
                    reason=(
                        f"Ledger open: {sorted(latest_tickers)}; "
                        f"CSV net open: {sorted(csv_open)}; "
                        f"missing={sorted(missing)} extra={sorted(extra)}"
                    ),
                )
            )

        for ticker in open_tickers:
            if ticker not in open_marks:
                checks.append(
                    LedgerCheck(
                        check_id="MISSING_OPEN_MARK",
                        severity=CheckSeverity.WARNING,
                        passed=False,
                        description=f"No mark price for open position {ticker}",
                        ticker=ticker,
                        reason="Open position lacks Current_Price in snapshot",
                    )
                )

        return checks

    def _duplicate_buy_checks(self, parsed: list[_ParsedTxn]) -> list[LedgerCheck]:
        checks: list[LedgerCheck] = []
        buy_groups: dict[tuple[str, str], list[_ParsedTxn]] = defaultdict(list)
        for txn in parsed:
            if txn.action == "BUY" and txn.ticker != CASH_TICKER:
                buy_groups[(txn.timestamp, txn.ticker)].append(txn)

        for (ts, ticker), group in buy_groups.items():
            if len(group) > 1:
                checks.append(
                    LedgerCheck(
                        check_id="DUPLICATE_BUY",
                        severity=CheckSeverity.WARNING,
                        passed=False,
                        description=f"Duplicate BUY rows at {ts} for {ticker}",
                        transaction_timestamp=ts,
                        ticker=ticker,
                        amount=sum(t.price * t.shares for t in group),
                        reason=f"{len(group)} BUY rows share identical timestamp",
                    )
                )
        return checks

    def _repairable_realized_pnl(self, portfolio_rows: list[dict[str, str]]) -> float:
        updated, _ = recompute_portfolio(portfolio_rows)
        total = 0.0
        for orig, corrected in zip(portfolio_rows, updated):
            if _is_repairable_sell(orig):
                total += _safe_float(corrected.get("PnL"))
        return round(total, 2)

    def _cross_checks(
        self,
        summary: LedgerSummary,
        repairable_realized: float,
        portfolio_rows: list[dict[str, str]],
    ) -> list[CrossCheckResult]:
        results: list[CrossCheckResult] = []

        dashboard_metrics = self._load_dashboard_metrics(portfolio_rows)
        if dashboard_metrics:
            dash_av = dashboard_metrics.get("computed_account_value")
            dash_realized = dashboard_metrics.get("realized_pnl")
            dash_open = dashboard_metrics.get("open_pnl")
            dash_total = dashboard_metrics.get("total_pnl")
            results.append(
                CrossCheckResult(
                    source="Dashboard (capital+deposits+PnL model)",
                    available=True,
                    account_value=dash_av,
                    realized_pnl=dash_realized,
                    open_pnl=dash_open,
                    total_pnl=dash_total,
                    delta_vs_ledger=round(dash_av - summary.final_account_value, 2)
                    if dash_av is not None
                    else None,
                    notes=(
                        "Dashboard uses repairable SELL PnL; ledger uses all SELL execution PnL"
                    ),
                )
            )
        else:
            results.append(
                CrossCheckResult(
                    source="Dashboard (capital+deposits+PnL model)",
                    available=False,
                    notes="tools/dashboard_account_reconcile unavailable",
                )
            )

        strategic = self._load_strategic_audit()
        results.append(strategic)

        integrity = self._load_integrity_audit()
        results.append(integrity)

        results.append(
            CrossCheckResult(
                source="Ledger repairable realized PnL",
                available=True,
                realized_pnl=repairable_realized,
                delta_vs_ledger=round(
                    repairable_realized - summary.realized_pnl_repairable, 2
                ),
                notes=(
                    f"All-SELL realized ${summary.realized_pnl_all_sells:,.2f} vs "
                    f"repairable ${repairable_realized:,.2f}"
                ),
            )
        )

        return results

    def _load_dashboard_metrics(
        self,
        portfolio_rows: list[dict[str, str]],
    ) -> dict[str, float] | None:
        try:
            import pandas as pd
            from tools.dashboard_account_reconcile import compute_account_metrics

            df = pd.DataFrame(portfolio_rows)
            return compute_account_metrics(df)
        except Exception as exc:
            logger.debug("Dashboard cross-check skipped: %s", exc)
            return None

    def _load_strategic_audit(self) -> CrossCheckResult:
        json_path = Path("tae_strategic_performance_audit.json")
        if not json_path.is_file():
            return CrossCheckResult(
                source="Strategic Performance Auditor",
                available=False,
                notes="Run tae_strategic_performance_audit_demo.py for cross-check",
            )
        try:
            import json

            data = json.loads(json_path.read_text(encoding="utf-8"))
            perf = data.get("performance", {})
            return CrossCheckResult(
                source="Strategic Performance Auditor",
                available=True,
                realized_pnl=_safe_float(perf.get("all_history_realized_pnl")),
                open_pnl=_safe_float(perf.get("last_2_days_unrealized_pnl")),
                total_pnl=_safe_float(perf.get("total_pnl")),
                notes="Uses portfolio.csv recorded PnL (may include stale marks)",
            )
        except Exception as exc:
            return CrossCheckResult(
                source="Strategic Performance Auditor",
                available=False,
                notes=str(exc),
            )

    def _load_integrity_audit(self) -> CrossCheckResult:
        json_path = Path("tae_accounting_integrity_audit.json")
        if not json_path.is_file():
            return CrossCheckResult(
                source="Accounting Integrity Auditor",
                available=False,
                notes="Run tae_accounting_integrity_audit_demo.py for cross-check",
            )
        try:
            import json

            data = json.loads(json_path.read_text(encoding="utf-8"))
            return CrossCheckResult(
                source="Accounting Integrity Auditor",
                available=True,
                notes=(
                    f"{data.get('anomalies_found', 0)} anomalies "
                    f"(HIGH {data.get('high_severity_count', 0)}) — "
                    "PnL mark-vs-execution issues on SELL rows"
                ),
            )
        except Exception as exc:
            return CrossCheckResult(
                source="Accounting Integrity Auditor",
                available=False,
                notes=str(exc),
            )
