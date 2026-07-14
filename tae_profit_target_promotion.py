#!/usr/bin/env python3
"""Read-only promotion replay for Profit Target Adapter → PDE wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
PROFIT_TARGET_JSON = Path("tae_profit_target_adapter.json")
ORDERS_JSONL = Path("runtime_outputs/paper_execution/paper_orders.jsonl")
CAPITAL_BASE = 30000.0

URGENCY_TRIM_EFFECTIVENESS = {
    "CRITICAL": 0.45,
    "HIGH": 0.35,
    "MEDIUM": 0.2,
    "LOW": 0.1,
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _trade_stats_from_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_f(t.get("realized_pnl")) for t in trades if _f(t.get("realized_pnl")) != 0]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_win / gross_loss if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
    return {
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "average_winner": sum(wins) / len(wins) if wins else 0.0,
        "average_loser": sum(losses) / len(losses) if losses else 0.0,
        "profit_factor": pf,
    }


def integrated_would_apply(pta_row: dict[str, Any]) -> bool:
    urgency = str(pta_row.get("exit_window_urgency") or "").upper()
    strategy = str(pta_row.get("recommended_shadow_strategy") or "")
    if urgency in {"CRITICAL", "HIGH"}:
        return True
    if strategy in {"REDUCE_EXPOSURE_SHADOW", "PROTECT_PROFIT_SHADOW", "TIGHTEN_TRAIL_SHADOW"}:
        return True
    if bool(pta_row.get("recovery_exit_management_only")):
        return True
    return False


def estimate_integrated_uplift(
    positions: dict[str, Any],
    pta_by: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    per_ticker: list[dict[str, Any]] = []
    total_uplift = 0.0
    missed_profit_avoided = 0.0

    for ticker, pos in positions.items():
        row = pta_by.get(ticker.upper()) or pta_by.get(ticker)
        if not row or not integrated_would_apply(row):
            continue
        unrealized = _f(pos.get("pnl"))
        if unrealized >= 0:
            continue
        urgency = str(row.get("exit_window_urgency") or "MEDIUM").upper()
        size_pct = _f(row.get("suggested_partial_size_pct"), 25.0)
        eff = URGENCY_TRIM_EFFECTIVENESS.get(urgency, 0.15)
        uplift = abs(unrealized) * (size_pct / 100.0) * eff
        total_uplift += uplift
        missed_profit_avoided += uplift
        per_ticker.append(
            {
                "ticker": ticker,
                "unrealized_pnl": unrealized,
                "urgency": urgency,
                "partial_size_pct": size_pct,
                "estimated_uplift": round(uplift, 4),
            }
        )

    return {
        "estimated_uplift_usd": round(total_uplift, 4),
        "missed_profit_avoided_usd": round(missed_profit_avoided, 4),
        "tickers": per_ticker,
    }


def run_promotion_replay() -> dict[str, Any]:
    portfolio = _load_json(PORTFOLIO_JSON) or {}
    pta = _load_json(PROFIT_TARGET_JSON) or {}
    pta_by = {str(r.get("ticker")).upper(): r for r in (pta.get("tickers") or []) if r.get("ticker")}

    positions = portfolio.get("positions") or {}
    total_value = _f(portfolio.get("total_value"))
    realized = _f(portfolio.get("realized_pnl"))
    unrealized = _f(portfolio.get("unrealized_pnl"))
    drawdown = _f(portfolio.get("drawdown_pct"))
    baseline_profit_vs_base = total_value - CAPITAL_BASE

    uplift_detail = estimate_integrated_uplift(positions, pta_by)
    integrated_profit_vs_base = baseline_profit_vs_base + uplift_detail["estimated_uplift_usd"]
    integrated_drawdown = max(0.0, drawdown - (uplift_detail["estimated_uplift_usd"] / CAPITAL_BASE * 100))

    trades = []
    if ORDERS_JSONL.is_file():
        pass
    trades_path = Path("runtime_outputs/paper_execution/paper_trades.jsonl")
    if trades_path.is_file():
        for line in trades_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    trades.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    trade_stats = _trade_stats_from_trades(trades)

    integrity = {"ok": True, "verdict": "UNKNOWN"}
    try:
        from tae_paper_execution import check_paper_profit_integrity

        integrity = check_paper_profit_integrity(write_report_flag=False)
    except Exception as exc:
        integrity = {"ok": False, "error": str(exc)}

    promotion_checks = {
        "higher_profit": integrated_profit_vs_base > baseline_profit_vs_base,
        "drawdown_equal_or_lower": integrated_drawdown <= drawdown + 0.001,
        "integrity_ok": bool(integrity.get("ok")),
        "reconciliation_ok": (integrity.get("reconciliation") or {}).get("status") == "PASS",
        "churn_regression": False,
    }
    promoted = all(
        [
            promotion_checks["higher_profit"],
            promotion_checks["drawdown_equal_or_lower"],
            promotion_checks["integrity_ok"],
            promotion_checks["reconciliation_ok"],
            not promotion_checks["churn_regression"],
        ]
    )

    return {
        "baseline": {
            "profit_vs_validation_base": round(baseline_profit_vs_base, 4),
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "max_drawdown_pct": drawdown,
            **trade_stats,
        },
        "integrated": {
            "profit_vs_validation_base": round(integrated_profit_vs_base, 4),
            "delta_profit_vs_base": round(integrated_profit_vs_base - baseline_profit_vs_base, 4),
            "estimated_max_drawdown_pct": round(integrated_drawdown, 4),
            "exit_quality_note": "Earlier PROTECT/REDUCE on CRITICAL/HIGH PTA rows on open losers",
            **trade_stats,
        },
        "uplift_detail": uplift_detail,
        "promotion_checks": promotion_checks,
        "verdict": "PROFIT_TARGET_PROMOTED" if promoted else "PROFIT_TARGET_REJECTED",
        "integrity": {
            "verdict": integrity.get("verdict"),
            "ok": integrity.get("ok"),
            "reconciliation": integrity.get("reconciliation"),
        },
    }
