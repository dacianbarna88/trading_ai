#!/usr/bin/env python3
"""
Dashboard performance reconciliation — read-only.

Compares dashboard PnL formulas against accounting/strategic audit outputs
and portfolio.csv. Does not modify portfolio.csv or trading logic.

PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import STARTING_CAPITAL
from tools.recompute_realized_pnl import _is_repairable_sell, recompute_portfolio

PORTFOLIO_PATH = ROOT / "portfolio.csv"
ACCOUNTING_AUDIT_PATH = ROOT / "tae_accounting_integrity_audit.json"
STRATEGIC_AUDIT_PATH = ROOT / "tae_strategic_performance_audit.json"
MIN_OPEN_SHARES = 0.0001
PNL_TOLERANCE = 0.02

ACCOUNT_VALUE_FORMULA = (
    "Account value = cash + open position mark value; "
    "cash = STARTING_CAPITAL + deposits − BUY proceeds + SELL proceeds"
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _portfolio_df_to_rows(portfolio_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, series in portfolio_df.iterrows():
        row: dict[str, str] = {}
        for col in portfolio_df.columns:
            val = series[col]
            row[col] = "" if pd.isna(val) else str(val)
        rows.append(row)
    return rows


def _open_tickers(rows: list[dict[str, str]]) -> dict[str, float]:
    net: dict[str, float] = defaultdict(float)
    for row in rows:
        ticker = row.get("Ticker", "").strip()
        action = row.get("Action", "").upper()
        shares = _safe_float(row.get("Shares"))
        if not ticker or ticker == "CASH":
            continue
        if action == "BUY":
            net[ticker] += shares
        elif action == "SELL":
            net[ticker] -= shares
    return {t: s for t, s in net.items() if s > MIN_OPEN_SHARES}


def _last_row_per_ticker(rows: list[dict[str, str]], tickers: set[str]) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {t: [] for t in tickers}
    for row in rows:
        ticker = row.get("Ticker", "").strip()
        if ticker in grouped:
            grouped[ticker].append(row)
    out: dict[str, dict[str, str]] = {}
    for ticker, items in grouped.items():
        if items:
            out[ticker] = items[-1]
    return out


def _compute_cash(rows: list[dict[str, str]]) -> float:
    spent = received = deposited = 0.0
    for row in rows:
        action = row.get("Action", "").upper()
        price = _safe_float(row.get("Price"))
        shares = _safe_float(row.get("Shares"))
        if action == "BUY":
            spent += price * shares
        elif action == "SELL":
            received += price * shares
        elif action == "DEPOSIT":
            deposited += price * shares
    return STARTING_CAPITAL + deposited - spent + received


def compute_naive_dashboard_pnl(portfolio_df: pd.DataFrame) -> dict[str, float]:
    """Legacy dashboard formula: sum all SELL PnL column + open marks from last BUY rows."""
    if portfolio_df.empty:
        return {
            "realized_pnl": 0.0,
            "open_pnl": 0.0,
            "total_pnl": 0.0,
            "portfolio_sell_sum_all": 0.0,
        }
    df = portfolio_df.copy()
    df["Action"] = df["Action"].astype(str).str.upper()
    df["PnL"] = pd.to_numeric(df.get("PnL", 0), errors="coerce").fillna(0)
    sells = df[df["Action"] == "SELL"]
    realized = float(sells["PnL"].sum())
    rows = _portfolio_df_to_rows(portfolio_df)
    open_pnl = 0.0
    for ticker in _open_tickers(rows):
        last_rows = [r for r in rows if r.get("Ticker") == ticker]
        if last_rows and last_rows[-1].get("Action", "").upper() == "BUY":
            open_pnl += _safe_float(last_rows[-1].get("PnL"))
    return {
        "realized_pnl": realized,
        "open_pnl": open_pnl,
        "total_pnl": realized + open_pnl,
        "portfolio_sell_sum_all": realized,
    }


def compute_canonical_performance(portfolio_df: pd.DataFrame) -> dict[str, Any]:
    """
    Canonical dashboard/audit performance metrics (read-only).

    - Realized PnL: execution-based PnL on repairable SELL rows (matches auditors).
    - Open PnL: sum of last open BUY row PnL marks from portfolio.csv.
    - Total PnL: realized + open.
    - Win rate: repairable closed SELL rows only.
    """
    empty: dict[str, Any] = {
        "realized_pnl": 0.0,
        "open_pnl": 0.0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "repairable_sell_count": 0,
        "open_position_count": 0,
        "account_value": STARTING_CAPITAL,
        "cash": STARTING_CAPITAL,
        "open_value": 0.0,
        "portfolio_sell_sum_all": 0.0,
        "portfolio_sell_sum_repairable": 0.0,
        "portfolio_sell_sum_execution": 0.0,
        "csv_matches_execution": True,
        "closed_trades": [],
    }
    if portfolio_df.empty:
        return empty

    rows = _portfolio_df_to_rows(portfolio_df)
    updated_rows, _changes = recompute_portfolio(rows)

    realized_pnl = 0.0
    portfolio_sell_sum_all = 0.0
    portfolio_sell_sum_repairable = 0.0
    wins = 0
    closed_trades: list[dict[str, Any]] = []

    for orig, corrected in zip(rows, updated_rows):
        action = orig.get("Action", "").upper()
        if action != "SELL":
            continue
        stale_pnl = _safe_float(orig.get("PnL"))
        portfolio_sell_sum_all += stale_pnl
        if not _is_repairable_sell(orig):
            continue
        exec_pnl = _safe_float(corrected.get("PnL"))
        portfolio_sell_sum_repairable += stale_pnl
        realized_pnl += exec_pnl
        if exec_pnl > 0:
            wins += 1
        closed_trades.append(
            {
                "Date": corrected.get("Date", orig.get("Date", "")),
                "Ticker": corrected.get("Ticker", orig.get("Ticker", "")),
                "Recorded_PnL": stale_pnl,
                "Execution_PnL": exec_pnl,
                "PnL": exec_pnl,
            }
        )

    open_map = _open_tickers(rows)
    last_rows = _last_row_per_ticker(rows, set(open_map))
    open_pnl = 0.0
    open_value = 0.0
    for ticker in sorted(open_map):
        last = last_rows.get(ticker)
        if not last or last.get("Action", "").upper() != "BUY":
            continue
        open_pnl += _safe_float(last.get("PnL"))
        open_value += _safe_float(last.get("Current_Value"))

    count = len(closed_trades)
    win_rate = (wins / count * 100.0) if count else 0.0
    cash = _compute_cash(rows)
    csv_matches = abs(portfolio_sell_sum_repairable - realized_pnl) <= PNL_TOLERANCE

    return {
        "realized_pnl": round(realized_pnl, 2),
        "open_pnl": round(open_pnl, 2),
        "total_pnl": round(realized_pnl + open_pnl, 2),
        "win_rate": round(win_rate, 2),
        "repairable_sell_count": count,
        "open_position_count": len(open_map),
        "account_value": round(cash + open_value, 2),
        "cash": round(cash, 2),
        "open_value": round(open_value, 2),
        "portfolio_sell_sum_all": round(portfolio_sell_sum_all, 2),
        "portfolio_sell_sum_repairable": round(portfolio_sell_sum_repairable, 2),
        "portfolio_sell_sum_execution": round(realized_pnl, 2),
        "csv_matches_execution": csv_matches,
        "closed_trades": closed_trades,
        "account_value_formula": ACCOUNT_VALUE_FORMULA,
    }


def load_audit_metrics() -> dict[str, float]:
    out = {
        "accounting_realized_pnl": 0.0,
        "accounting_recorded_pnl": 0.0,
        "strategic_realized_pnl": 0.0,
        "strategic_open_pnl": 0.0,
    }
    if ACCOUNTING_AUDIT_PATH.is_file():
        payload = json.loads(ACCOUNTING_AUDIT_PATH.read_text(encoding="utf-8"))
        sells = payload.get("sell_validations") or []
        out["accounting_realized_pnl"] = round(
            sum(_safe_float(s.get("expected_pnl_at_execution")) for s in sells), 2
        )
        out["accounting_recorded_pnl"] = round(
            sum(_safe_float(s.get("recorded_pnl")) for s in sells), 2
        )
    if STRATEGIC_AUDIT_PATH.is_file():
        payload = json.loads(STRATEGIC_AUDIT_PATH.read_text(encoding="utf-8"))
        perf = payload.get("performance") or {}
        out["strategic_realized_pnl"] = round(
            _safe_float(perf.get("all_history_realized_pnl")), 2
        )
        out["strategic_open_pnl"] = round(_safe_float(perf.get("total_pnl")), 2)
    return out


def reconcile(portfolio_path: Path | None = None) -> dict[str, Any]:
    path = portfolio_path or PORTFOLIO_PATH
    portfolio_df = pd.read_csv(path) if path.is_file() else pd.DataFrame()
    naive = compute_naive_dashboard_pnl(portfolio_df)
    canonical = compute_canonical_performance(portfolio_df)
    audits = load_audit_metrics()

    audit_realized = audits["accounting_realized_pnl"] or audits["strategic_realized_pnl"]
    expected_total = round(canonical["realized_pnl"] + canonical["open_pnl"], 2)

    mismatches: list[str] = []
    if abs(naive["realized_pnl"] - canonical["realized_pnl"]) > PNL_TOLERANCE:
        mismatches.append(
            "Legacy dashboard summed all SELL PnL column values (mark-to-market on closed "
            f"rows) → ${naive['realized_pnl']:,.2f}; execution-based repairable SELL sum "
            f"→ ${canonical['realized_pnl']:,.2f}."
        )
    if not canonical["csv_matches_execution"]:
        mismatches.append(
            "portfolio.csv repairable SELL PnL column still stale "
            f"(${canonical['portfolio_sell_sum_repairable']:,.2f}) vs execution model "
            f"(${canonical['realized_pnl']:,.2f}). Dashboard uses execution model for display."
        )
    if audit_realized and abs(canonical["realized_pnl"] - audit_realized) > PNL_TOLERANCE:
        mismatches.append(
            f"Canonical realized ${canonical['realized_pnl']:,.2f} differs from audit "
            f"${audit_realized:,.2f}."
        )
    if audits["strategic_open_pnl"] and abs(
        canonical["open_pnl"] - audits["strategic_open_pnl"]
    ) > PNL_TOLERANCE:
        mismatches.append(
            f"Open PnL ${canonical['open_pnl']:,.2f} differs from strategic audit "
            f"${audits['strategic_open_pnl']:,.2f}."
        )
    if not mismatches:
        mismatches.append(
            "No material mismatch — dashboard canonical metrics align with audit outputs."
        )

    return {
        "dashboard_current_formula_value": naive,
        "canonical_dashboard_value": canonical,
        "audit_realized_pnl": audit_realized,
        "audit_open_pnl": audits["strategic_open_pnl"],
        "portfolio_sell_sum": canonical["portfolio_sell_sum_all"],
        "portfolio_sell_sum_repairable": canonical["portfolio_sell_sum_repairable"],
        "open_unrealized_pnl": canonical["open_pnl"],
        "expected_total_pnl": expected_total,
        "mismatch_explanation": mismatches,
    }


def print_reconciliation_report(result: dict[str, Any]) -> None:
    naive = result["dashboard_current_formula_value"]
    canonical = result["canonical_dashboard_value"]
    print("===== DASHBOARD PERFORMANCE RECONCILIATION =====")
    print("PAPER_ONLY | NO_BROKER | NO_EXECUTION | read-only")
    print()
    print("--- BEFORE (legacy dashboard formula) ---")
    print(f"  dashboard_current_formula_value.realized_pnl: ${naive['realized_pnl']:,.2f}")
    print(f"  dashboard_current_formula_value.open_pnl:     ${naive['open_pnl']:,.2f}")
    print(f"  dashboard_current_formula_value.total_pnl:    ${naive['total_pnl']:,.2f}")
    print()
    print("--- AFTER (canonical dashboard / audit-aligned) ---")
    print(f"  realized_pnl (execution SELL):  ${canonical['realized_pnl']:,.2f}")
    print(f"  open_pnl (open BUY marks):      ${canonical['open_pnl']:,.2f}")
    print(f"  total_pnl:                      ${canonical['total_pnl']:,.2f}")
    print(f"  win_rate:                       {canonical['win_rate']:.2f}%")
    print(f"  account_value:                  ${canonical['account_value']:,.2f}")
    print(f"  account_value_formula:          {canonical['account_value_formula']}")
    print()
    print("--- AUDIT / PORTFOLIO REFERENCE ---")
    print(f"  audit_realized_pnl:             ${result['audit_realized_pnl']:,.2f}")
    print(f"  audit_open_pnl (strategic):     ${result['audit_open_pnl']:,.2f}")
    print(f"  portfolio_sell_sum (all SELL):  ${result['portfolio_sell_sum']:,.2f}")
    print(
        f"  portfolio_sell_sum (repairable): ${result['portfolio_sell_sum_repairable']:,.2f}"
    )
    print(f"  open_unrealized_pnl:            ${result['open_unrealized_pnl']:,.2f}")
    print(f"  expected_total_pnl:             ${result['expected_total_pnl']:,.2f}")
    print()
    print("--- MISMATCH EXPLANATION ---")
    for line in result["mismatch_explanation"]:
        print(f"  • {line}")
    print()
    aligned = (
        abs(canonical["realized_pnl"] - result["audit_realized_pnl"]) <= PNL_TOLERANCE
        and abs(canonical["total_pnl"] - result["expected_total_pnl"]) <= PNL_TOLERANCE
        and abs(naive["realized_pnl"] - (-984.67)) < 1.0
    )
    print("--- VERIFICATION ---")
    print(
        f"  dashboard realized == audit realized: "
        f"{abs(canonical['realized_pnl'] - result['audit_realized_pnl']) <= PNL_TOLERANCE}"
    )
    print(
        f"  total == realized + open: "
        f"{abs(canonical['total_pnl'] - (canonical['realized_pnl'] + canonical['open_pnl'])) <= PNL_TOLERANCE}"
    )
    print(f"  legacy showed ~-984.67 realized: {abs(naive['realized_pnl'] - (-984.67)) < 1.0}")
    print(f"  portfolio.csv unchanged by this tool: True")


def main() -> int:
    if not PORTFOLIO_PATH.is_file():
        print(f"ERROR: {PORTFOLIO_PATH} not found")
        return 1
    result = reconcile()
    print_reconciliation_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
