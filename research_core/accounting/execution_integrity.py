"""
TAE Execution Integrity — portfolio SELL row reconciliation (read-only).

Reconstructs expected realized PnL at sell time using average-cost accounting
matching live_bot.get_open_positions / sell_position logic.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_PORTFOLIO_PATH = Path("portfolio.csv")
PNL_TOLERANCE = 0.05
PCT_TOLERANCE = 0.15


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_cash_flow_row(row: dict[str, str]) -> bool:
    ticker = str(row.get("Ticker", "")).strip().upper()
    action = str(row.get("Action", "")).upper()
    return ticker == "CASH" or action == "DEPOSIT"


def _reason_implies_profit(reason: str) -> bool:
    text = reason.upper()
    return "PROFIT" in text or "TAKE PROFIT" in text


def _reason_implies_loss(reason: str) -> bool:
    text = reason.upper()
    return "STOP LOSS" in text or "LOSS" in text


def _extract_pct_from_reason(reason: str) -> float | None:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", reason)
    if match:
        return float(match.group(1))
    return None


@dataclass
class SellAuditRow:
    ticker: str
    sell_date: str
    sell_price: float
    shares: float
    reason: str
    signal: str
    reported_pnl: float | None
    reported_pnl_pct: float | None
    expected_entry_price: float | None
    expected_invested: float | None
    expected_exit_value: float | None
    expected_realized_pnl: float | None
    expected_realized_pnl_pct: float | None
    consistency_status: str
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sell_date": self.sell_date,
            "sell_price": self.sell_price,
            "shares": self.shares,
            "reason": self.reason,
            "signal": self.signal,
            "reported_pnl": self.reported_pnl,
            "reported_pnl_pct": self.reported_pnl_pct,
            "expected_entry_price": self.expected_entry_price,
            "expected_invested": self.expected_invested,
            "expected_exit_value": self.expected_exit_value,
            "expected_realized_pnl": self.expected_realized_pnl,
            "expected_realized_pnl_pct": self.expected_realized_pnl_pct,
            "consistency_status": self.consistency_status,
            "notes": self.notes,
        }


def load_portfolio_rows(path: Path | str | None = None) -> list[dict[str, str]]:
    portfolio_path = Path(path or DEFAULT_PORTFOLIO_PATH)
    if not portfolio_path.is_file():
        return []
    with portfolio_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def _sort_key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("Date", "")), str(row.get("Action", "")))


def audit_sell_rows(rows: list[dict[str, str]]) -> list[SellAuditRow]:
    """Audit each SELL using average-cost state walk (matches sell_position)."""
    ordered = sorted(rows, key=_sort_key)
    audits: list[SellAuditRow] = []

    positions: dict[str, dict[str, float]] = {}

    for row in ordered:
        if _is_cash_flow_row(row):
            continue

        ticker = str(row.get("Ticker", "")).strip()
        action = str(row.get("Action", "")).upper()
        price = _parse_float(row.get("Price"))
        shares = _parse_float(row.get("Shares"))
        if not ticker or price is None or shares is None:
            continue

        if action == "BUY":
            bucket = positions.setdefault(ticker, {"buy_shares": 0.0, "buy_value": 0.0})
            bucket["buy_shares"] += shares
            bucket["buy_value"] += price * shares
            continue

        if action != "SELL":
            continue

        notes: list[str] = []
        reported_pnl = _parse_float(row.get("PnL"))
        reported_pnl_pct = _parse_float(row.get("PnL_%"))
        reason = str(row.get("Reason", ""))
        signal = str(row.get("Signal", ""))

        if ticker not in positions or positions[ticker]["buy_shares"] <= 0:
            audits.append(
                SellAuditRow(
                    ticker=ticker,
                    sell_date=str(row.get("Date", "")),
                    sell_price=price,
                    shares=shares,
                    reason=reason,
                    signal=signal,
                    reported_pnl=reported_pnl,
                    reported_pnl_pct=reported_pnl_pct,
                    expected_entry_price=None,
                    expected_invested=None,
                    expected_exit_value=None,
                    expected_realized_pnl=None,
                    expected_realized_pnl_pct=None,
                    consistency_status="MISSING_ENTRY",
                    notes=["No open BUY position found before this SELL"],
                )
            )
            continue

        bucket = positions[ticker]
        avg_entry = bucket["buy_value"] / bucket["buy_shares"] if bucket["buy_shares"] else 0.0
        expected_invested = avg_entry * shares
        expected_exit = price * shares
        expected_pnl = expected_exit - expected_invested
        expected_pnl_pct = (expected_pnl / expected_invested * 100) if expected_invested else 0.0

        status = "OK"
        pnl_delta = (
            abs(reported_pnl - expected_pnl)
            if reported_pnl is not None
            else float("inf")
        )
        pct_delta = (
            abs(reported_pnl_pct - expected_pnl_pct)
            if reported_pnl_pct is not None
            else float("inf")
        )

        reason_profit = _reason_implies_profit(reason)
        reason_loss = _reason_implies_loss(reason)
        reason_pct = _extract_pct_from_reason(reason)

        if pnl_delta > PNL_TOLERANCE or pct_delta > PCT_TOLERANCE:
            status = "POSSIBLE_ACCOUNTING_BUG"
            notes.append(
                f"Reported PnL {reported_pnl} vs expected {round(expected_pnl, 4)} "
                f"(delta {round((reported_pnl or 0) - expected_pnl, 4)})"
            )

        if reason_profit and expected_pnl < -PNL_TOLERANCE:
            status = "MISMATCH_REASON_PNL"
            notes.append("Reason implies profit but expected realized PnL is negative")
        elif reason_loss and expected_pnl > PNL_TOLERANCE:
            status = "MISMATCH_REASON_PNL"
            notes.append("Reason implies loss but expected realized PnL is positive")

        if reason_pct is not None and abs(reason_pct - expected_pnl_pct) > 1.0:
            notes.append(
                f"Reason pct {reason_pct}% vs expected realized {round(expected_pnl_pct, 2)}%"
            )
            if status == "OK":
                status = "MISMATCH_REASON_PNL"

        if reported_pnl is not None and (
            (reported_pnl > PNL_TOLERANCE and expected_pnl < -PNL_TOLERANCE)
            or (reported_pnl < -PNL_TOLERANCE and expected_pnl > PNL_TOLERANCE)
        ):
            status = "MISMATCH_REASON_PNL"
            notes.append("Reported PnL sign differs from expected realized PnL")

        audits.append(
            SellAuditRow(
                ticker=ticker,
                sell_date=str(row.get("Date", "")),
                sell_price=price,
                shares=shares,
                reason=reason,
                signal=signal,
                reported_pnl=reported_pnl,
                reported_pnl_pct=reported_pnl_pct,
                expected_entry_price=round(avg_entry, 4),
                expected_invested=round(expected_invested, 4),
                expected_exit_value=round(expected_exit, 4),
                expected_realized_pnl=round(expected_pnl, 4),
                expected_realized_pnl_pct=round(expected_pnl_pct, 4),
                consistency_status=status,
                notes=notes,
            )
        )

        # Apply sell to running position state
        bucket["buy_shares"] -= shares
        if bucket["buy_shares"] <= 1e-9:
            positions.pop(ticker, None)
        else:
            bucket["buy_value"] = bucket["buy_shares"] * avg_entry

    return audits


def build_execution_integrity_report(
    rows: list[dict[str, str]] | None = None,
    *,
    portfolio_path: Path | str | None = None,
) -> dict[str, Any]:
    if rows is None:
        rows = load_portfolio_rows(portfolio_path)

    audits = audit_sell_rows(rows)
    ok = [a for a in audits if a.consistency_status == "OK"]
    mismatched = [a for a in audits if a.consistency_status != "OK"]

    reported_realized = sum(a.reported_pnl or 0.0 for a in audits)
    corrected_realized = sum(a.expected_realized_pnl or 0.0 for a in audits)
    delta = round(reported_realized - corrected_realized, 4)

    biggest = sorted(
        mismatched,
        key=lambda a: abs((a.reported_pnl or 0.0) - (a.expected_realized_pnl or 0.0)),
        reverse=True,
    )

    root_cause = (
        "update_portfolio_prices() in live_bot.py rewrites PnL on ALL rows including SELL, "
        "using live Current_Price vs row Price*Shares instead of freezing realized PnL at sell time. "
        "sell_position() computes correct realized PnL at execution; subsequent mark-to-market pass corrupts it."
    )

    return {
        "schema": "tae.execution_integrity_audit.v1",
        "mode": "ACCOUNTING_INTEGRITY_READ_ONLY",
        "live_trading_impact": "NONE",
        "root_cause": root_cause,
        "fix_applied": "update_portfolio_prices skips SELL/DEPOSIT/CASH and closed BUY rows",
        "portfolio_path": str(portfolio_path or DEFAULT_PORTFOLIO_PATH),
        "summary": {
            "total_sell_rows": len(audits),
            "sell_ok": len(ok),
            "sell_mismatched": len(mismatched),
            "total_reported_realized_pnl": round(reported_realized, 4),
            "corrected_realized_pnl": round(corrected_realized, 4),
            "realized_pnl_delta": delta,
            "execution_integrity_status": "OK" if not mismatched else "MISMATCH_DETECTED",
            "recommended_next_action": (
                "PORTFOLIO_HISTORICAL_REWRITE_OPTIONAL"
                if mismatched
                else "NONE"
            ),
        },
        "biggest_mismatches": [a.to_dict() for a in biggest[:10]],
        "sell_audits": [a.to_dict() for a in audits],
    }


def build_reconciliation_report(
    integrity: dict[str, Any] | None = None,
    *,
    portfolio_path: Path | str | None = None,
) -> dict[str, Any]:
    integrity = integrity or build_execution_integrity_report(portfolio_path=portfolio_path)
    summary = integrity["summary"]
    return {
        "schema": "tae.portfolio_reconciliation.v1",
        "mode": "READ_ONLY_RECONCILIATION",
        "live_trading_impact": "NONE",
        "source_integrity_audit": "tae_execution_integrity_audit.json",
        "summary": summary,
        "biggest_mismatches": integrity.get("biggest_mismatches", []),
        "root_cause": integrity.get("root_cause"),
        "recommended_next_action": summary.get("recommended_next_action"),
    }
