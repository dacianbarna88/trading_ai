"""
TAE Capital Base Integrity — read-only audit of contributed capital vs deposits.

Does not modify portfolio.csv or execute trades.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from research_core.accounting.execution_integrity import (
    DEFAULT_PORTFOLIO_PATH,
    _is_cash_flow_row,
    _parse_float,
    load_portfolio_rows,
)

VIRTUAL_DEPOSIT_MARKERS = (
    "VIRTUAL",
    "TEST",
    "SIMULATION",
    "PAPER",
    "MOCK",
    "NON_TRADING",
)

REAL_DEPOSIT_MARKERS = (
    "REAL DEPOSIT",
    "BANK TRANSFER",
    "WIRE",
    "FUNDING",
)


def resolve_starting_capital_config(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    sources: dict[str, Any] = {}

    live_bot = root / "live_bot.py"
    if live_bot.is_file():
        try:
            text = live_bot.read_text(encoding="utf-8")
            match = re.search(r"^STARTING_CAPITAL\s*=\s*([0-9.]+)", text, re.MULTILINE)
            if match:
                sources["live_bot.py"] = float(match.group(1))
        except OSError:
            pass

    settings = root / "config" / "settings.py"
    if settings.is_file():
        try:
            text = settings.read_text(encoding="utf-8")
            match = re.search(r"^STARTING_CAPITAL\s*=\s*([0-9.]+)", text, re.MULTILINE)
            if match:
                sources["config/settings.py"] = float(match.group(1))
        except OSError:
            pass

    canonical = sources.get("live_bot.py") or sources.get("config/settings.py") or 30000.0
    return {
        "starting_capital_config": float(canonical),
        "sources": sources,
        "canonical_source": "live_bot.py" if "live_bot.py" in sources else (
            "config/settings.py" if "config/settings.py" in sources else "default"
        ),
        "live_bot_includes_deposits_in_cash": False,
        "core_portfolio_includes_deposits_in_cash": True,
    }


def _deposit_classification(row: dict[str, str]) -> str:
    """REAL | NON_TRADING_VIRTUAL | UNKNOWN."""
    reason = str(row.get("Reason", "")).upper()
    signal = str(row.get("Signal", "")).upper()
    combined = f"{reason} {signal}"

    if any(marker in combined for marker in VIRTUAL_DEPOSIT_MARKERS):
        return "NON_TRADING_VIRTUAL"
    if any(marker in combined for marker in REAL_DEPOSIT_MARKERS):
        return "REAL"
    if reason == "DEPOSIT" and signal == "DEPOSIT":
        return "UNKNOWN"
    return "UNKNOWN"


def extract_deposit_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    deposits: list[dict[str, Any]] = []
    for row in rows:
        action = str(row.get("Action", "")).upper()
        if action != "DEPOSIT" and not (
            _is_cash_flow_row(row) and action in {"DEPOSIT", "CASH"}
        ):
            continue
        if action != "DEPOSIT":
            continue
        price = _parse_float(row.get("Price")) or 0.0
        shares = _parse_float(row.get("Shares")) or 0.0
        amount = round(price * shares, 4)
        classification = _deposit_classification(row)
        deposits.append(
            {
                "date": row.get("Date"),
                "ticker": row.get("Ticker"),
                "action": action,
                "amount": amount,
                "reason": row.get("Reason"),
                "signal": row.get("Signal"),
                "reported_pnl": _parse_float(row.get("PnL")),
                "classification": classification,
                "count_toward_contributed_capital": classification == "REAL",
            }
        )
    return deposits


def _trade_flow_totals(rows: list[dict[str, str]]) -> tuple[float, float]:
    spent = received = 0.0
    for row in rows:
        if _is_cash_flow_row(row):
            continue
        action = str(row.get("Action", "")).upper()
        price = _parse_float(row.get("Price")) or 0.0
        shares = _parse_float(row.get("Shares")) or 0.0
        if action == "BUY":
            spent += price * shares
        elif action == "SELL":
            received += price * shares
    return round(spent, 4), round(received, 4)


def build_capital_base_analysis(
    rows: list[dict[str, str]],
    *,
    starting_capital_config: float,
    corrected_total_trading_pnl: float,
    open_positions_value: float,
    root: Path | str = ".",
) -> dict[str, Any]:
    config = resolve_starting_capital_config(root)
    starting = float(starting_capital_config or config["starting_capital_config"])

    deposit_rows = extract_deposit_rows(rows)
    detected = round(sum(d["amount"] for d in deposit_rows), 4)
    excluded = round(
        sum(d["amount"] for d in deposit_rows if not d["count_toward_contributed_capital"]),
        4,
    )
    counted = round(detected - excluded, 4)

    spent, received = _trade_flow_totals(rows)

    # live_bot formula: STARTING_CAPITAL - spent + received (no DEPOSIT)
    cash_live_bot_style = round(starting - spent + received, 2)
    # With all detected deposits added (prior snapshot behaviour)
    cash_if_all_deposits_counted = round(starting + detected - spent + received, 2)
    # Canonical: only REAL deposits count
    cash_available = round(starting + counted - spent + received, 2)

    effective_contributed = round(starting + counted, 4)
    account_value_cash_based = round(cash_available + open_positions_value, 2)
    account_value_capital_based = round(
        effective_contributed + corrected_total_trading_pnl, 2
    )

    cash_capital_delta = round(account_value_cash_based - account_value_capital_based, 4)

    explanations: list[str] = [
        f"starting_capital_config={starting} (source: {config['canonical_source']})",
        f"cash_available = starting_capital_config + capital_deposits_counted - spent + received",
        f"  spent={spent}, received={received}",
        f"account_value_cash_based = cash_available + open_positions_value",
        f"account_value_capital_based = effective_contributed_capital + corrected_total_trading_pnl",
        f"effective_contributed_capital = starting_capital_config + capital_deposits_counted",
    ]

    virtual_rows = [d for d in deposit_rows if d["classification"] == "NON_TRADING_VIRTUAL"]
    unknown_rows = [d for d in deposit_rows if d["classification"] == "UNKNOWN"]

    status = "OK"
    if virtual_rows or unknown_rows:
        status = "NEEDS_OPERATOR_CONFIRMATION"
        if virtual_rows:
            explanations.append(
                f"Excluded {excluded} as NON_TRADING_VIRTUAL deposit(s) — not added to "
                "effective_contributed_capital (Reason/Signal contains VIRTUAL/TEST markers)."
            )
        if unknown_rows:
            explanations.append(
                f"{len(unknown_rows)} DEPOSIT row(s) unclassified — excluded from counted capital until confirmed REAL."
            )
    if detected > 0 and abs(cash_if_all_deposits_counted - cash_live_bot_style) > 1.0:
        explanations.append(
            f"Prior double-path risk: adding all detected deposits ({detected}) to starting capital "
            f"raises cash from {cash_live_bot_style} to {cash_if_all_deposits_counted} while "
            "live_bot.py ignores DEPOSIT rows entirely."
        )
        if status == "OK":
            status = "DOUBLE_COUNT_RISK"

    if abs(cash_capital_delta) > 1.0:
        explanations.append(
            f"Account value paths differ by {cash_capital_delta}: "
            f"cash_based={account_value_cash_based} vs capital_based={account_value_capital_based}"
        )
        status = "NEEDS_OPERATOR_CONFIRMATION" if status == "OK" else status

    if abs(cash_capital_delta) <= 1.0 and not virtual_rows and not unknown_rows:
        explanations.append(
            "cash + open_positions_value closes with effective_contributed_capital + trading_pnl."
        )

    return {
        "starting_capital_config": starting,
        "starting_capital_sources": config["sources"],
        "canonical_starting_capital_source": config["canonical_source"],
        "live_bot_cash_formula": "STARTING_CAPITAL - spent + received (DEPOSIT rows ignored)",
        "live_bot_cash_value": cash_live_bot_style,
        "deposit_rows": deposit_rows,
        "capital_deposits_detected": detected,
        "capital_deposits_counted": counted,
        "capital_deposits_excluded_as_duplicate": excluded,
        "capital_deposits_excluded_detail": [
            {k: d[k] for k in ("date", "ticker", "amount", "reason", "signal", "classification")}
            for d in deposit_rows
            if not d["count_toward_contributed_capital"]
        ],
        "effective_contributed_capital": effective_contributed,
        "spent_on_buys": spent,
        "received_from_sells": received,
        "cash_available": cash_available,
        "cash_if_all_deposits_counted": cash_if_all_deposits_counted,
        "open_positions_value": open_positions_value,
        "account_value_cash_based": account_value_cash_based,
        "account_value_capital_based": account_value_capital_based,
        "account_value_reconciliation_delta": cash_capital_delta,
        "corrected_total_trading_pnl": corrected_total_trading_pnl,
        "capital_base_status": status,
        "capital_base_explanation": explanations,
        "double_count_detected": detected > 0 and excluded < detected and status != "OK",
    }


def build_capital_base_integrity_audit(
    root: Path | str = ".",
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from research_core.accounting.accounting_snapshot import build_accounting_snapshot

    root = Path(root)
    rows = load_portfolio_rows(root / DEFAULT_PORTFOLIO_PATH)
    if snapshot is None:
        snapshot = build_accounting_snapshot(root, rows=rows)

    capital = snapshot.get("capital_base") or build_capital_base_analysis(
        rows,
        starting_capital_config=snapshot.get("starting_capital_config"),
        corrected_total_trading_pnl=float(snapshot.get("corrected_total_trading_pnl") or 0),
        open_positions_value=float(snapshot.get("open_positions_value") or 0),
        root=root,
    )

    return {
        "schema": "tae.capital_base_integrity_audit.v1",
        "mode": "CAPITAL_BASE_READ_ONLY",
        "live_trading_impact": "NONE",
        "generated_at": snapshot.get("generated_at"),
        "portfolio_path": str(root / DEFAULT_PORTFOLIO_PATH),
        "starting_capital_config": capital.get("starting_capital_config"),
        "starting_capital_sources": capital.get("starting_capital_sources"),
        "deposit_rows": capital.get("deposit_rows"),
        "capital_deposits_detected": capital.get("capital_deposits_detected"),
        "capital_deposits_counted": capital.get("capital_deposits_counted"),
        "capital_deposits_excluded": capital.get("capital_deposits_excluded_as_duplicate"),
        "effective_contributed_capital": capital.get("effective_contributed_capital"),
        "cash_available": capital.get("cash_available"),
        "cash_live_bot_style": capital.get("live_bot_cash_value"),
        "cash_if_all_deposits_counted": capital.get("cash_if_all_deposits_counted"),
        "open_positions_value": capital.get("open_positions_value"),
        "account_value_cash_based": capital.get("account_value_cash_based"),
        "account_value_capital_based": capital.get("account_value_capital_based"),
        "corrected_total_trading_pnl": capital.get("corrected_total_trading_pnl"),
        "capital_base_status": capital.get("capital_base_status"),
        "capital_base_explanation": capital.get("capital_base_explanation"),
        "formulas": {
            "cash_available": "starting_capital_config + capital_deposits_counted - spent + received",
            "account_value_cash_based": "cash_available + open_positions_value",
            "account_value_capital_based": "effective_contributed_capital + corrected_total_trading_pnl",
            "effective_contributed_capital": "starting_capital_config + capital_deposits_counted",
            "live_bot_cash": "STARTING_CAPITAL - spent + received (ignores DEPOSIT)",
        },
        "verdict": {
            "real_capital_base_for_display": capital.get("effective_contributed_capital"),
            "deposit_double_counted_in_prior_snapshot": (
                capital.get("capital_deposits_excluded_as_duplicate", 0) > 0
                and capital.get("cash_if_all_deposits_counted") != capital.get("cash_available")
            ),
            "account_value_authoritative": capital.get("account_value_cash_based"),
        },
    }


def render_capital_base_audit_md(audit: dict[str, Any]) -> str:
    lines = [
        "# TAE Capital Base Integrity Audit",
        "",
        f"**Status:** **{audit.get('capital_base_status')}**",
        f"**Generated:** {audit.get('generated_at')}",
        "",
        "## Starting capital",
        "",
        f"- Config (canonical): **{audit.get('starting_capital_config')}**",
        f"- Sources: {audit.get('starting_capital_sources')}",
        "",
        "## DEPOSIT / CASH rows",
        "",
    ]
    for row in audit.get("deposit_rows") or []:
        lines.append(
            f"- {row.get('date')} | {row.get('ticker')} | ${row.get('amount')} | "
            f"{row.get('classification')} | {row.get('signal')} | {row.get('reason')}"
        )
    if not audit.get("deposit_rows"):
        lines.append("- (none)")

    lines.extend(
        [
            "",
            "## Capital summary",
            "",
            f"- Deposits detected: {audit.get('capital_deposits_detected')}",
            f"- Deposits counted toward capital: {audit.get('capital_deposits_counted')}",
            f"- Deposits excluded (virtual/unknown): {audit.get('capital_deposits_excluded')}",
            f"- **Effective contributed capital:** {audit.get('effective_contributed_capital')}",
            "",
            "## Cash & account value",
            "",
            f"- Cash (canonical): {audit.get('cash_available')}",
            f"- Cash (live_bot style, no DEPOSIT): {audit.get('cash_live_bot_style')}",
            f"- Cash (if all deposits counted): {audit.get('cash_if_all_deposits_counted')}",
            f"- Open positions value: {audit.get('open_positions_value')}",
            f"- Account value (cash + positions): **{audit.get('account_value_cash_based')}**",
            f"- Account value (capital + trading PnL): **{audit.get('account_value_capital_based')}**",
            f"- Trading PnL (corrected): {audit.get('corrected_total_trading_pnl')}",
            "",
            "## Formulas",
            "",
        ]
    )
    for name, formula in (audit.get("formulas") or {}).items():
        lines.append(f"- `{name}`: {formula}")

    lines.extend(["", "## Explanation", ""])
    for item in audit.get("capital_base_explanation") or []:
        lines.append(f"- {item}")

    verdict = audit.get("verdict") or {}
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            f"- Real capital base for display: **{verdict.get('real_capital_base_for_display')}**",
            f"- Prior snapshot double-counted virtual deposit: **{verdict.get('deposit_double_counted_in_prior_snapshot')}**",
            f"- Authoritative account value: **{verdict.get('account_value_authoritative')}**",
            "",
        ]
    )
    return "\n".join(lines)
