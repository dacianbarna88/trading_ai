#!/usr/bin/env python3
"""
Recompute realized PnL for SELL rows in portfolio.csv — repair tool.

Default: dry-run (no writes).
Use --apply to write corrected portfolio.csv (backup created first).

PAPER_ONLY | NO_BROKER | NO_EXECUTION — accounting repair only.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.trades import (
    annotate_reason_accounting_check,
    compute_realized_pnl,
    compute_realized_pnl_pct,
)

PORTFOLIO_PATH = ROOT / "portfolio.csv"
PNL_TOLERANCE = 0.01
MIN_SHARES = 0.0001
FOCUS_TICKERS = {"GS", "AAPL", "SIE.DE", "ULVR.L"}


@dataclass
class LotState:
    shares: float = 0.0
    total_cost: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.shares if self.shares > 0 else 0.0


@dataclass
class RowChange:
    row_index: int
    ticker: str
    date: str
    old_pnl: float
    new_pnl: float
    old_pnl_pct: float
    new_pnl_pct: float
    old_reason: str
    new_reason: str
    avg_cost: float
    sell_price: float
    shares: float
    notes: list[str] = field(default_factory=list)


def _safe_float(val: str | None, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _is_repairable_sell(row: dict[str, str]) -> bool:
    if row.get("Action", "").upper() != "SELL":
        return False
    reason = row.get("Reason", "").upper()
    signal = row.get("Signal", "").upper()
    if "REBALANCE" in reason or signal == "REBALANCE":
        return False
    if row.get("Ticker", "").upper() == "CASH":
        return False
    return True


def recompute_portfolio(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[RowChange]]:
    lots: dict[str, LotState] = defaultdict(LotState)
    changes: list[RowChange] = []
    updated_rows: list[dict[str, str]] = []

    for idx, row in enumerate(rows):
        row = dict(row)
        ticker = row.get("Ticker", "").strip()
        action = row.get("Action", "").upper()
        shares = _safe_float(row.get("Shares"))
        price = _safe_float(row.get("Price"))

        if action == "BUY" and ticker and ticker != "CASH":
            invested = _safe_float(row.get("Invested"))
            cost = invested if invested > 0 else price * shares
            lots[ticker].shares += shares
            lots[ticker].total_cost += cost
            updated_rows.append(row)
            continue

        if action == "SELL" and _is_repairable_sell(row):
            lot = lots[ticker]
            avg_cost = lot.avg_cost if lot.shares > 0 else 0.0
            old_pnl = _safe_float(row.get("PnL"))
            old_pnl_pct = _safe_float(row.get("PnL_%"))
            old_reason = row.get("Reason", "")

            notes: list[str] = []
            if avg_cost <= 0:
                notes.append("avg_cost missing — row left unchanged")
                updated_rows.append(row)
                if lot.shares > 0 and shares > 0:
                    fraction = min(1.0, shares / lot.shares)
                    lot.total_cost *= max(0.0, 1.0 - fraction)
                    lot.shares = max(0.0, lot.shares - shares)
                continue

            new_pnl = round(compute_realized_pnl(price, avg_cost, shares), 4)
            new_pnl_pct = round(compute_realized_pnl_pct(price, avg_cost), 4)
            cost_basis = round(avg_cost * shares, 4)
            proceeds = round(price * shares, 4)
            new_reason = annotate_reason_accounting_check(
                old_reason,
                row.get("Signal", ""),
                new_pnl,
            )

            if abs(old_pnl - new_pnl) > PNL_TOLERANCE or old_reason != new_reason:
                notes.append(
                    f"PnL {old_pnl:.2f} → {new_pnl:.2f} "
                    f"(avg_cost={avg_cost:.2f}, sell={price:.2f})"
                )
                if old_reason != new_reason:
                    notes.append("reason annotated with accounting check")

                row["Invested"] = str(cost_basis)
                row["Current_Value"] = str(proceeds)
                row["Current_Price"] = str(round(price, 2))
                row["PnL"] = str(new_pnl)
                row["PnL_%"] = str(new_pnl_pct)
                row["Reason"] = new_reason

                changes.append(
                    RowChange(
                        row_index=idx,
                        ticker=ticker,
                        date=row.get("Date", ""),
                        old_pnl=old_pnl,
                        new_pnl=new_pnl,
                        old_pnl_pct=old_pnl_pct,
                        new_pnl_pct=new_pnl_pct,
                        old_reason=old_reason,
                        new_reason=new_reason,
                        avg_cost=avg_cost,
                        sell_price=price,
                        shares=shares,
                        notes=notes,
                    )
                )

            updated_rows.append(row)

            if lot.shares > 0 and shares > 0:
                fraction = min(1.0, shares / lot.shares)
                lot.total_cost *= max(0.0, 1.0 - fraction)
                lot.shares = max(0.0, lot.shares - shares)
            continue

        if action == "SELL" and ticker in lots and shares > 0:
            lot = lots[ticker]
            if lot.shares > 0:
                fraction = min(1.0, shares / lot.shares)
                lot.total_cost *= max(0.0, 1.0 - fraction)
                lot.shares = max(0.0, lot.shares - shares)

        updated_rows.append(row)

    return updated_rows, changes


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute SELL realized PnL in portfolio.csv")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write corrected portfolio.csv (creates timestamped backup first)",
    )
    parser.add_argument(
        "--portfolio",
        type=Path,
        default=PORTFOLIO_PATH,
        help="Path to portfolio.csv",
    )
    args = parser.parse_args()

    portfolio_path = args.portfolio
    if not portfolio_path.is_file():
        print(f"ERROR: {portfolio_path} not found")
        return 1

    with portfolio_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    updated_rows, changes = recompute_portfolio(rows)

    print("===== RECOMPUTE REALIZED PnL =====")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN (default)")
    print(f"Portfolio: {portfolio_path}")
    print(f"Rows corrected: {len(changes)}")
    print()

    focus_changes = [c for c in changes if c.ticker in FOCUS_TICKERS]
    if changes:
        print("===== CHANGES =====")
        for change in changes:
            print(
                f"  {change.date[:10]} {change.ticker}: "
                f"PnL {change.old_pnl:.2f} → {change.new_pnl:.2f} | "
                f"reason updated={change.old_reason != change.new_reason}"
            )
            for note in change.notes:
                print(f"      {note}")
        print()

    for ticker in sorted(FOCUS_TICKERS):
        ticker_changes = [c for c in changes if c.ticker == ticker]
        if ticker_changes:
            c = ticker_changes[-1]
            print(f"--- {ticker} ---")
            print(f"  PnL: {c.old_pnl:.2f} → {c.new_pnl:.2f}")
            print(f"  PnL %: {c.old_pnl_pct:.2f} → {c.new_pnl_pct:.2f}")
            if c.old_reason != c.new_reason:
                print(f"  Reason: {c.old_reason[:60]}...")
                print(f"       → {c.new_reason[:80]}...")
            else:
                print(f"  Reason (unchanged): {c.old_reason[:80]}")
            print()
        else:
            print(f"--- {ticker} --- no PnL correction needed")
            print()

    backup_path: Path | None = None
    if args.apply:
        if not changes:
            print("No changes to apply.")
            return 0
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = portfolio_path.with_name(f"portfolio.csv.bak_{ts}")
        shutil.copy2(portfolio_path, backup_path)
        _write_csv(portfolio_path, updated_rows, fieldnames)
        print(f"Backup created: {backup_path}")
        print(f"Updated: {portfolio_path}")
    else:
        print("Dry-run complete — use --apply to write changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
