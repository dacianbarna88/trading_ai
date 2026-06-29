"""
TAE Canonical Accounting Snapshot — single source of truth (read-only).

Does not modify portfolio.csv, live_bot.py, or execute trades.
Uses execution_integrity reconciliation for corrected SELL realized PnL.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.accounting.capital_base_integrity import build_capital_base_analysis
from research_core.accounting.execution_integrity import (
    DEFAULT_PORTFOLIO_PATH,
    _is_cash_flow_row,
    _parse_float,
    audit_sell_rows,
    build_execution_integrity_report,
    load_portfolio_rows,
)

SCHEMA = "tae.accounting_snapshot.v1"
MODE = "CANONICAL_ACCOUNTING_READ_ONLY"
LIVE_TRADING_IMPACT = "NONE"
DEFAULT_STARTING_CAPITAL = 30000.0
DEFAULT_SNAPSHOT_JSON = Path("tae_accounting_snapshot.json")
DEFAULT_SNAPSHOT_MD = Path("tae_accounting_snapshot.md")
ACCOUNT_VALUE_FORMULA = (
    "account_value = effective_contributed_capital + corrected_total_trading_pnl "
    "= cash_available + open_positions_value"
)


def resolve_starting_capital(root: Path | str = ".") -> float:
    """Match live_bot.py STARTING_CAPITAL when present."""
    root = Path(root)
    live_bot = root / "live_bot.py"
    if live_bot.is_file():
        try:
            text = live_bot.read_text(encoding="utf-8")
            match = re.search(r"^STARTING_CAPITAL\s*=\s*([0-9.]+)", text, re.MULTILINE)
            if match:
                return float(match.group(1))
        except OSError:
            pass
    return DEFAULT_STARTING_CAPITAL


def _trade_from_audit(audit: dict[str, Any]) -> dict[str, Any]:
    pnl = audit.get("expected_realized_pnl")
    return {
        "date": audit.get("sell_date"),
        "ticker": audit.get("ticker"),
        "pnl": round(float(pnl), 4) if pnl is not None else None,
        "pnl_pct": audit.get("expected_realized_pnl_pct"),
        "reported_pnl": audit.get("reported_pnl"),
        "reason": audit.get("reason"),
        "signal": audit.get("signal"),
        "consistency_status": audit.get("consistency_status"),
    }


def _open_unrealized_and_value(
    rows: list[dict[str, str]],
) -> tuple[float, float, int, list[dict[str, Any]]]:
    positions: dict[str, dict[str, Any]] = {}
    for row in rows:
        if _is_cash_flow_row(row):
            continue
        ticker = str(row.get("Ticker", "")).strip()
        if not ticker or ticker.upper() == "CASH":
            continue
        action = str(row.get("Action", "")).upper()
        price = _parse_float(row.get("Price")) or 0.0
        shares = _parse_float(row.get("Shares")) or 0.0
        if action == "BUY":
            bucket = positions.setdefault(
                ticker, {"buy_shares": 0.0, "sell_shares": 0.0, "last_buy_row": None}
            )
            bucket["buy_shares"] += shares
            bucket["last_buy_row"] = row
        elif action == "SELL":
            bucket = positions.setdefault(
                ticker, {"buy_shares": 0.0, "sell_shares": 0.0, "last_buy_row": None}
            )
            bucket["sell_shares"] += shares

    unrealized = 0.0
    positions_value = 0.0
    open_positions: list[dict[str, Any]] = []

    for ticker, bucket in positions.items():
        open_shares = bucket["buy_shares"] - bucket["sell_shares"]
        if open_shares <= 1e-9:
            continue
        last = bucket["last_buy_row"] or {}
        invested = _parse_float(last.get("Invested"))
        current_value = _parse_float(last.get("Current_Value"))
        pnl = _parse_float(last.get("PnL"))
        pnl_pct = _parse_float(last.get("PnL_%"))
        current_price = _parse_float(last.get("Current_Price"))

        if pnl is not None:
            unrealized += pnl
        elif invested is not None and current_value is not None:
            unrealized += current_value - invested

        if current_value is not None:
            positions_value += current_value
        elif invested is not None:
            positions_value += invested

        open_positions.append(
            {
                "ticker": ticker,
                "shares": round(open_shares, 4),
                "pnl": round(pnl, 4) if pnl is not None else None,
                "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
                "current_price": current_price,
            }
        )

    return round(unrealized, 4), round(positions_value, 4), len(open_positions), open_positions


def _cash_flow_totals(
    rows: list[dict[str, str]], starting_capital: float
) -> tuple[float, float, float, float, float]:
    spent = received = deposited = 0.0
    raw_pnl_sum = 0.0
    cash_flow_pnl_sum = 0.0

    for row in rows:
        action = str(row.get("Action", "")).upper()
        price = _parse_float(row.get("Price")) or 0.0
        shares = _parse_float(row.get("Shares")) or 0.0
        pnl = _parse_float(row.get("PnL"))
        is_cash_flow = _is_cash_flow_row(row)

        if pnl is not None:
            raw_pnl_sum += pnl
            if is_cash_flow:
                cash_flow_pnl_sum += pnl

        if is_cash_flow:
            if action == "DEPOSIT":
                deposited += price * shares
            continue

        ticker = str(row.get("Ticker", "")).upper()
        if ticker == "CASH":
            continue

        if action == "BUY":
            spent += price * shares
        elif action == "SELL":
            received += price * shares

    cash = starting_capital + deposited - spent + received
    return (
        round(deposited, 4),
        round(cash, 2),
        round(raw_pnl_sum, 4),
        round(cash_flow_pnl_sum, 4),
        round(spent, 4),
    )


def build_accounting_snapshot(
    root: Path | str = ".",
    *,
    rows: list[dict[str, str]] | None = None,
    portfolio_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    portfolio_path = Path(portfolio_path or root / DEFAULT_PORTFOLIO_PATH)

    if rows is None:
        rows = load_portfolio_rows(portfolio_path)

    starting_capital = resolve_starting_capital(root)
    warnings: list[str] = []
    notes: list[str] = [
        "DEPOSIT/CASH rows are capital flow only — excluded from trading PnL",
        "SELL realized PnL uses reconciliation (expected_realized_pnl), not stale PnL column",
        "Open BUY rows contribute unrealized via latest mark in portfolio.csv",
        ACCOUNT_VALUE_FORMULA,
    ]

    if not rows:
        return {
            "schema": SCHEMA,
            "mode": MODE,
            "live_trading_impact": LIVE_TRADING_IMPACT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "portfolio_path": str(portfolio_path),
            "portfolio_readable": False,
            "starting_capital": starting_capital,
            "data_quality_status": "NO_DATA",
            "warnings": ["portfolio.csv missing or empty"],
            "calculation_notes": notes,
        }

    integrity = build_execution_integrity_report(rows, portfolio_path=portfolio_path)
    summary = integrity.get("summary") or {}
    audits = integrity.get("sell_audits") or []

    corrected_realized = float(summary.get("corrected_realized_pnl") or 0.0)
    reported_realized = float(summary.get("total_reported_realized_pnl") or 0.0)
    sell_mismatch_count = int(summary.get("sell_mismatched") or 0)
    corrected_vs_reported_delta = round(reported_realized - corrected_realized, 4)

    unrealized, open_positions_value, open_count, open_positions = _open_unrealized_and_value(rows)
    deposits, _cash_legacy, raw_pnl, accounting_adj, _spent = _cash_flow_totals(rows, starting_capital)

    corrected_total = round(corrected_realized + unrealized, 4)

    capital_base = build_capital_base_analysis(
        rows,
        starting_capital_config=starting_capital,
        corrected_total_trading_pnl=corrected_total,
        open_positions_value=open_positions_value,
        root=root,
    )

    cash = capital_base["cash_available"]
    account_value = capital_base["account_value_cash_based"]
    account_value_capital = capital_base["account_value_capital_based"]
    account_value_delta = capital_base["account_value_reconciliation_delta"]

    if abs(account_value_delta) > 1.0:
        warnings.append(
            f"Account value paths differ by {account_value_delta}: "
            f"cash_based={account_value} vs capital_based={account_value_capital}"
        )

    if capital_base.get("capital_base_status") == "NEEDS_OPERATOR_CONFIRMATION":
        warnings.append("CAPITAL BASE NEEDS CONFIRMATION — see capital_base_explanation")
    elif capital_base.get("capital_base_status") == "DOUBLE_COUNT_RISK":
        warnings.append("CAPITAL BASE DOUBLE COUNT RISK — virtual/duplicate deposit detected")

    if capital_base.get("capital_deposits_excluded_as_duplicate", 0) > 0:
        notes.append(
            f"Excluded {capital_base['capital_deposits_excluded_as_duplicate']} from "
            "effective_contributed_capital (NON_TRADING_VIRTUAL / unclassified DEPOSIT)"
        )

    corrected_trades = [_trade_from_audit(a) for a in audits if a.get("expected_realized_pnl") is not None]
    winners = sorted(
        [t for t in corrected_trades if (t.get("pnl") or 0) > 0],
        key=lambda x: x["pnl"],
        reverse=True,
    )
    losers = sorted(
        [t for t in corrected_trades if (t.get("pnl") or 0) < 0],
        key=lambda x: x["pnl"],
    )

    biggest_mismatch = None
    mismatches = integrity.get("biggest_mismatches") or []
    if mismatches:
        biggest_mismatch = mismatches[0]

    if sell_mismatch_count > 0:
        data_quality = "HISTORICAL_RECONCILIATION_REQUIRED"
        warnings.append(
            f"{sell_mismatch_count} historical SELL row(s) have stale reported PnL — "
            "corrected values used for all canonical metrics"
        )
    elif not audits:
        data_quality = "NO_SELLS"
    else:
        data_quality = "OK"

    profit_pct = (
        round(
            (corrected_total / capital_base["effective_contributed_capital"]) * 100,
            4,
        )
        if capital_base["effective_contributed_capital"]
        else None
    )

    return {
        "schema": SCHEMA,
        "mode": MODE,
        "live_trading_impact": LIVE_TRADING_IMPACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portfolio_path": str(portfolio_path),
        "portfolio_readable": True,
        "starting_capital_config": capital_base["starting_capital_config"],
        "starting_capital": capital_base["starting_capital_config"],
        "capital_deposits_detected": capital_base["capital_deposits_detected"],
        "capital_deposits_counted": capital_base["capital_deposits_counted"],
        "capital_deposits_excluded_as_duplicate": capital_base["capital_deposits_excluded_as_duplicate"],
        "capital_deposits": capital_base["capital_deposits_counted"],
        "effective_contributed_capital": capital_base["effective_contributed_capital"],
        "cash_available": cash,
        "open_positions_value": open_positions_value,
        "open_positions_count": open_count,
        "open_positions": open_positions,
        "corrected_realized_pnl": round(corrected_realized, 4),
        "corrected_unrealized_pnl": unrealized,
        "corrected_total_trading_pnl": corrected_total,
        "account_value_corrected": account_value,
        "account_value_cash_based": account_value,
        "account_value_capital_based": account_value_capital,
        "account_value_cash_plus_open": account_value,
        "account_value_reconciliation_delta": account_value_delta,
        "capital_base_status": capital_base["capital_base_status"],
        "capital_base_explanation": capital_base["capital_base_explanation"],
        "capital_base": capital_base,
        "raw_pnl_including_cash_rows": raw_pnl,
        "accounting_adjustments_excluded": accounting_adj,
        "reported_realized_pnl_stale": round(reported_realized, 4),
        "corrected_vs_reported_delta": corrected_vs_reported_delta,
        "sell_mismatch_count": sell_mismatch_count,
        "sell_row_count": int(summary.get("total_sell_rows") or len(audits)),
        "biggest_historical_mismatch": biggest_mismatch,
        "top_winners_corrected": winners[:10],
        "top_losers_corrected": losers[:10],
        "top_drag_corrected": losers[0] if losers else None,
        "data_quality_status": data_quality,
        "account_value_formula": ACCOUNT_VALUE_FORMULA,
        "execution_integrity_status": summary.get("execution_integrity_status"),
        "profit_pct_on_starting_capital": profit_pct,
        "warnings": warnings,
        "calculation_notes": notes,
    }


def load_accounting_snapshot(
    path: Path | str | None = None,
    root: Path | str = ".",
) -> tuple[dict[str, Any] | None, str]:
    snapshot_path = Path(path or Path(root) / DEFAULT_SNAPSHOT_JSON)
    if not snapshot_path.is_file():
        return None, "MISSING"
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "INVALID_JSON"
    except OSError:
        return None, "READ_ERROR"
    if not isinstance(payload, dict):
        return None, "INVALID_ROOT"
    return payload, "OK"


def ensure_accounting_snapshot(root: Path | str = ".") -> dict[str, Any]:
    """Load snapshot JSON or build in-memory if missing/stale optional - always rebuild for review."""
    root = Path(root)
    snapshot = build_accounting_snapshot(root)
    return snapshot


def persist_accounting_snapshot(
    snapshot: dict[str, Any],
    root: Path | str = ".",
) -> tuple[Path, Path]:
    root = Path(root)
    json_path = root / DEFAULT_SNAPSHOT_JSON
    md_path = root / DEFAULT_SNAPSHOT_MD
    json_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_snapshot_markdown(snapshot), encoding="utf-8")
    return json_path, md_path


def render_snapshot_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# TAE Accounting Snapshot",
        "",
        f"**Generated:** {snapshot.get('generated_at')}  ",
        f"**Mode:** {snapshot.get('mode')}  ",
        f"**Data quality:** **{snapshot.get('data_quality_status')}**",
        "",
        "## Canonical metrics",
        "",
        f"- Starting capital (config): {snapshot.get('starting_capital_config')}",
        f"- Deposits detected / counted / excluded: "
        f"{snapshot.get('capital_deposits_detected')} / "
        f"{snapshot.get('capital_deposits_counted')} / "
        f"{snapshot.get('capital_deposits_excluded_as_duplicate')}",
        f"- **Effective contributed capital:** {snapshot.get('effective_contributed_capital')}",
        f"- Cash available: {snapshot.get('cash_available')}",
        f"- Open positions value: {snapshot.get('open_positions_value')}",
        f"- **Corrected realized PnL:** {snapshot.get('corrected_realized_pnl')}",
        f"- **Corrected unrealized PnL:** {snapshot.get('corrected_unrealized_pnl')}",
        f"- **Corrected total trading PnL:** {snapshot.get('corrected_total_trading_pnl')}",
        f"- **Account value (corrected):** {snapshot.get('account_value_corrected')}",
        f"- Account value cash-based: {snapshot.get('account_value_cash_based')}",
        f"- Account value capital-based: {snapshot.get('account_value_capital_based')}",
        f"- Capital base status: **{snapshot.get('capital_base_status')}**",
        f"- Raw PnL (incl. CASH rows): {snapshot.get('raw_pnl_including_cash_rows')}",
        f"- Accounting adjustments excluded: {snapshot.get('accounting_adjustments_excluded')}",
        f"- Reported realized (stale): {snapshot.get('reported_realized_pnl_stale')}",
        f"- SELL mismatches: {snapshot.get('sell_mismatch_count')}",
        "",
        f"Formula: {snapshot.get('account_value_formula')}",
        "",
    ]
    drag = snapshot.get("top_drag_corrected")
    if drag:
        lines.extend(
            [
                "## Top drag (corrected)",
                "",
                f"- **{drag.get('ticker')}** PnL {drag.get('pnl')} ({drag.get('reason')})",
                "",
            ]
        )
    biggest = snapshot.get("biggest_historical_mismatch")
    if biggest:
        lines.extend(
            [
                "## Biggest historical mismatch",
                "",
                f"- {biggest.get('ticker')}: reported {biggest.get('reported_pnl')} vs "
                f"expected {biggest.get('expected_realized_pnl')}",
                "",
            ]
        )
    for title, key in (
        ("Top winners (corrected)", "top_winners_corrected"),
        ("Top losers (corrected)", "top_losers_corrected"),
    ):
        items = snapshot.get(key) or []
        if items:
            lines.append(f"## {title}")
            lines.append("")
            for item in items[:5]:
                lines.append(
                    f"- {item.get('ticker')} | {item.get('pnl')} | {item.get('reason')}"
                )
            lines.append("")
    for w in snapshot.get("warnings") or []:
        lines.append(f"- ⚠️ {w}")
    lines.append("")
    return "\n".join(lines)


def financial_dict_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Map snapshot to tae_full_ecosystem_review B_financial_status shape."""
    return {
        "portfolio_readable": snapshot.get("portfolio_readable", False),
        "cash_available": snapshot.get("cash_available"),
        "open_positions_count": snapshot.get("open_positions_count", 0),
        "open_positions": snapshot.get("open_positions") or [],
        "portfolio_value_estimated": snapshot.get("account_value_corrected"),
        "capital_deposits": snapshot.get("capital_deposits_counted"),
        "capital_deposits_detected": snapshot.get("capital_deposits_detected"),
        "capital_deposits_counted": snapshot.get("capital_deposits_counted"),
        "capital_deposits_excluded_as_duplicate": snapshot.get(
            "capital_deposits_excluded_as_duplicate"
        ),
        "effective_contributed_capital": snapshot.get("effective_contributed_capital"),
        "starting_capital_config": snapshot.get("starting_capital_config"),
        "account_value_cash_based": snapshot.get("account_value_cash_based"),
        "account_value_capital_based": snapshot.get("account_value_capital_based"),
        "open_positions_value": snapshot.get("open_positions_value"),
        "capital_base_status": snapshot.get("capital_base_status"),
        "trading_realized_pnl": snapshot.get("reported_realized_pnl_stale"),
        "trading_unrealized_pnl": snapshot.get("corrected_unrealized_pnl"),
        "trading_total_pnl": snapshot.get("corrected_total_trading_pnl"),
        "accounting_adjustments": snapshot.get("accounting_adjustments_excluded"),
        "raw_total_pnl_including_cash_rows": snapshot.get("raw_pnl_including_cash_rows"),
        "corrected_total_pnl_excluding_cash_deposits": snapshot.get("corrected_total_trading_pnl"),
        "realized_pnl": snapshot.get("corrected_realized_pnl"),
        "unrealized_pnl": snapshot.get("corrected_unrealized_pnl"),
        "total_pnl": snapshot.get("corrected_total_trading_pnl"),
        "corrected_realized_pnl": snapshot.get("corrected_realized_pnl"),
        "account_value_corrected": snapshot.get("account_value_corrected"),
        "profit_pct": snapshot.get("profit_pct_on_starting_capital"),
        "data_quality_status": snapshot.get("data_quality_status"),
        "accounting_snapshot_generated_at": snapshot.get("generated_at"),
        "warnings": list(snapshot.get("warnings") or []),
        "calculation_notes": list(snapshot.get("calculation_notes") or [])
        + ["Source: tae_accounting_snapshot.json (canonical)"],
    }


def performance_drag_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Corrected top winners/losers for ecosystem review."""
    winners = snapshot.get("top_winners_corrected") or []
    losers = snapshot.get("top_losers_corrected") or []
    accounting_adj = snapshot.get("accounting_adjustments_excluded")

    cash_distortion = None
    if accounting_adj:
        cash_distortion = {
            "is_primary_reported_loss_driver": True,
            "ticker": "CASH",
            "reported_pnl": accounting_adj,
            "explains_raw_vs_corrected_gap": True,
            "message": (
                f"CASH/DEPOSIT row reported PnL {accounting_adj} distorts raw portfolio sums; "
                "excluded from corrected trading PnL."
            ),
        }

    return {
        "top_losing_trades": losers[:10],
        "top_winning_trades": winners[:10],
        "top_drag_corrected": snapshot.get("top_drag_corrected"),
        "biggest_accounting_distortions": (
            [{"reported_pnl": accounting_adj, "ticker": "CASH", "note": "capital flow"}]
            if accounting_adj
            else []
        ),
        "realized_vs_unrealized": {
            "trading_realized_pnl": snapshot.get("corrected_realized_pnl"),
            "trading_unrealized_pnl": snapshot.get("corrected_unrealized_pnl"),
            "trading_total_pnl": snapshot.get("corrected_total_trading_pnl"),
        },
        "trades_that_reduced_profit": losers[:10],
        "cash_row_primary_distortion": cash_distortion,
        "recommended_next_fix": (
            "PORTFOLIO_ACCOUNTING_MIGRATION"
            if snapshot.get("data_quality_status") == "HISTORICAL_RECONCILIATION_REQUIRED"
            else None
        ),
        "source": "tae_accounting_snapshot.json",
    }
