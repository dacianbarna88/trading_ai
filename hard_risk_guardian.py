#!/usr/bin/env python3
"""
Hard Risk Guardian — STOP -3% / CRITICAL -5% position evaluation.

PAPER mode: evaluates runtime_outputs/paper_execution/paper_portfolio.json
LEGACY mode (__main__): read-only scan of portfolio.csv (unchanged behaviour)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STOP_LIMIT = -3.0
CRITICAL_LIMIT = -5.0

PAPER_PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
PAPER_REPORT_JSON = Path("runtime_outputs/governance/hard_risk.json")
LEGACY_REPORT_CSV = Path("hard_risk_guardian_report.csv")
LEGACY_SUMMARY_TXT = Path("hard_risk_guardian_summary.txt")
LEGACY_PORTFOLIO_CSV = Path("portfolio.csv")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_position_risk(
    ticker: str,
    *,
    avg_price: float,
    current_price: float,
    shares: float = 0.0,
) -> dict[str, Any]:
    """Evaluate one position against hard STOP/CRITICAL limits."""
    ticker = str(ticker).upper()
    if shares <= 0 or avg_price <= 0 or current_price <= 0:
        return {
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
            "current_price": current_price,
            "pnl_pct": 0.0,
            "status": "NO_POSITION",
            "required_action": "NONE",
            "hard_rule": None,
        }

    pnl_pct = round(((current_price - avg_price) / avg_price) * 100, 4)
    status = "OK"
    action = "HOLD"
    hard_rule = None

    if pnl_pct <= CRITICAL_LIMIT:
        status = "CRITICAL_LOSS"
        action = "FORCE_SELL_REQUIRED"
        hard_rule = "HARD_CRITICAL_STOP_-5"
    elif pnl_pct <= STOP_LIMIT:
        status = "STOP_LOSS_BREACHED"
        action = "SELL_REQUIRED"
        hard_rule = "HARD_STOP_LOSS_-3"

    return {
        "ticker": ticker,
        "shares": round(shares, 6),
        "avg_price": round(avg_price, 6),
        "current_price": round(current_price, 6),
        "pnl_pct": pnl_pct,
        "status": status,
        "required_action": action,
        "hard_rule": hard_rule,
    }


def evaluate_paper_portfolio(portfolio: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate PAPER portfolio positions — no broker, no live CSV writes required."""
    portfolio = portfolio if portfolio is not None else _load_json(PAPER_PORTFOLIO_JSON)
    positions = (portfolio or {}).get("positions") or {}
    rows: list[dict[str, Any]] = []

    for ticker, pos in sorted(positions.items()):
        if not isinstance(pos, dict):
            continue
        rows.append(
            evaluate_position_risk(
                ticker,
                avg_price=_f(pos.get("avg_price")),
                current_price=_f(pos.get("current_price")) or _f(pos.get("avg_price")),
                shares=_f(pos.get("shares")),
            )
        )

    breaches = [r for r in rows if r.get("status") not in {"OK", "NO_POSITION"}]
    return {
        "schema": "tae.hard_risk_guardian.v1",
        "mode": "PAPER_ONLY",
        "broker_executed": False,
        "live_money": False,
        "generated_at": _now(),
        "stop_limit_pct": STOP_LIMIT,
        "critical_limit_pct": CRITICAL_LIMIT,
        "positions_checked": len(rows),
        "breach_count": len(breaches),
        "ok": True,
        "status": "PASS" if not breaches else "BREACH",
        "positions": rows,
        "breaches": breaches,
    }


def write_paper_hard_risk_report(result: dict[str, Any], path: Path | None = None) -> Path:
    path = path or PAPER_REPORT_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def run_paper_hard_risk(*, portfolio: dict[str, Any] | None = None, write_report: bool = True) -> dict[str, Any]:
    result = evaluate_paper_portfolio(portfolio)
    if write_report:
        write_paper_hard_risk_report(result)
    return result


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _legacy_portfolio_scan() -> None:
    """Original portfolio.csv script behaviour."""
    import pandas as pd

    if not LEGACY_PORTFOLIO_CSV.exists():
        raise SystemExit("portfolio.csv not found")

    df = pd.read_csv(LEGACY_PORTFOLIO_CSV)
    df["Action"] = df["Action"].astype(str).str.upper()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce")
    df["Current_Price"] = pd.to_numeric(df["Current_Price"], errors="coerce")

    open_rows = []
    for ticker in df["Ticker"].dropna().unique():
        rows = df[df["Ticker"] == ticker]
        buy_shares = rows[rows["Action"] == "BUY"]["Shares"].sum()
        sell_shares = rows[rows["Action"] == "SELL"]["Shares"].sum()
        open_shares = buy_shares - sell_shares
        if open_shares > 0:
            last_buy = rows[rows["Action"] == "BUY"].iloc[-1]
            row = evaluate_position_risk(
                str(ticker),
                avg_price=float(last_buy["Price"]),
                current_price=float(last_buy["Current_Price"]),
                shares=float(open_shares),
            )
            open_rows.append(
                {
                    "Ticker": row["ticker"],
                    "Entry_Price": row["avg_price"],
                    "Current_Price": row["current_price"],
                    "PnL_%": row["pnl_pct"],
                    "Status": row["status"],
                    "Required_Action": row["required_action"],
                }
            )

    risk_df = pd.DataFrame(open_rows)
    risk_df.to_csv(LEGACY_REPORT_CSV, index=False)
    breaches = risk_df[risk_df["Status"] != "OK"] if not risk_df.empty else pd.DataFrame()

    lines = [
        "===== V12.3 HARD RISK GUARDIAN =====",
        "",
        f"Open Positions Checked: {len(risk_df)}",
        f"Risk Breaches: {len(breaches)}",
        "",
    ]
    if not breaches.empty:
        lines.append("Breaches:")
        for _, r in breaches.iterrows():
            lines.append(f"{r['Ticker']} | PnL {r['PnL_%']}% | {r['Status']} | {r['Required_Action']}")
    else:
        lines.append("No open position currently breaches hard risk limits.")
    lines.extend(
        [
            "",
            "Rules:",
            f"STOP_LIMIT: {STOP_LIMIT}%",
            f"CRITICAL_LIMIT: {CRITICAL_LIMIT}%",
            "",
            "Status:",
            "PAPER_ONLY",
            "NO_BROKER",
            "NO_AUTO_EXECUTION",
        ]
    )
    summary = "\n".join(lines)
    LEGACY_SUMMARY_TXT.write_text(summary)
    print(summary)
    print()
    print(risk_df.to_string(index=False))


if __name__ == "__main__":
    _legacy_portfolio_scan()
