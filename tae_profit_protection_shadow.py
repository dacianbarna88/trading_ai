#!/usr/bin/env python3
"""
TAE Profit Protection Shadow Engine — SHADOW_ONLY / PAPER_ONLY.

Compares hypothetical profit protection strategies without live execution.
Does NOT modify live_bot, portfolio, or signals.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tae_intraday_fade_intelligence import fifo_open_positions

PORTFOLIO_FILE = Path("portfolio.csv")
FADE_INTELLIGENCE_JSON = Path("tae_intraday_fade_intelligence.json")
FADE_HISTORY_CSV = Path("runtime_outputs/tae_intraday_fade_history.csv")
DISCOVERY_JSON = Path("tae_intraday_discovery_engine.json")
KNOWLEDGE_BASE_JSON = Path("tae_knowledge_base.json")

OUTPUT_JSON = Path("tae_profit_protection_shadow.json")
OUTPUT_MD = Path("tae_profit_protection_shadow.md")
COOLDOWN_AUDIT_JSON = Path("tae_stop_reentry_cooldown_audit.json")

RULES_VERSION = "v1"
PROFIT_LOCK_PCT = 4.0
PEAK_FADE_ALERT_PCT = 1.5
PARTIAL_ADVISORY_LEVELS: tuple[tuple[float, str], ...] = (
    (6.0, "TAKE_PROFIT_PARTIAL_25"),
    (8.0, "TAKE_PROFIT_PARTIAL_33"),
    (10.0, "TAKE_PROFIT_PARTIAL_50"),
)
COOLDOWN_HOURS_AFTER_PROFIT_SELL = 24.0

SHADOW_ACTIONS = frozenset(
    {
        "OBSERVE",
        "TEST_SELL_20",
        "TEST_SELL_30",
        "TEST_TRAILING_1",
        "TEST_TRAILING_1_5",
    }
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def confidence_from_observations(observations: int) -> str:
    if observations >= 100:
        return "HIGH"
    if observations >= 30:
        return "MEDIUM"
    return "LOW"


def observation_counts(history_csv: Path) -> dict[str, int]:
    if not history_csv.is_file():
        return {}
    try:
        df = pd.read_csv(history_csv)
    except (OSError, pd.errors.EmptyDataError):
        return {}
    if df.empty or "ticker" not in df.columns:
        return {}
    valid = df[df.get("classification", pd.Series(dtype=str)) != "DATA_UNAVAILABLE"]
    return valid.groupby(valid["ticker"].astype(str).str.upper()).size().to_dict()


def knowledge_prefers_trailing(knowledge: dict[str, Any] | None) -> bool:
    if not knowledge:
        return False
    for rec in knowledge.get("recommendations") or []:
        if rec.get("recommendation") == "TEST_TRAILING_SHADOW":
            return True
    for entry in knowledge.get("entries") or []:
        if entry.get("recommendation") == "TEST_TRAILING_SHADOW":
            return True
        if entry.get("pattern_type") == "BEST_SHADOW_TRAILING":
            return True
    return False


def discovery_best_shadow_by_ticker(discovery: dict[str, Any] | None) -> dict[str, str]:
    if not discovery:
        return {}
    return {
        str(row.get("ticker", "")).upper(): str(row.get("best_shadow_strategy", ""))
        for row in discovery.get("ticker_learning") or []
        if row.get("ticker")
    }


def _shadow_values(position: dict[str, Any]) -> dict[str, float]:
    shadow = position.get("shadow") or {}
    return {
        "sell_20": float(shadow.get("sell_20_at_high_pnl") or 0),
        "sell_30": float(shadow.get("sell_30_at_high_pnl") or 0),
        "trailing_1": float(shadow.get("trailing_1pct_pnl") or 0),
        "trailing_1_5": float(shadow.get("trailing_1_5pct_pnl") or 0),
    }


def trailing_is_best_shadow(
    shadow: dict[str, float],
    discovery_strategy: str | None,
    knowledge_trailing: bool,
) -> bool:
    if discovery_strategy in {"shadow_trailing_1", "shadow_trailing_1_5"}:
        return True
    best_key = max(shadow, key=lambda k: shadow.get(k, float("-inf")))
    if best_key.startswith("trailing"):
        return True
    if knowledge_trailing and shadow.get("trailing_1", 0) > 0:
        return True
    return False


def preferred_trailing_action(shadow: dict[str, float]) -> str:
    if shadow.get("trailing_1", float("-inf")) >= shadow.get("trailing_1_5", float("-inf")):
        return "TEST_TRAILING_1"
    return "TEST_TRAILING_1_5"


def load_peak_state(path: Path = OUTPUT_JSON) -> dict[str, float]:
    """Highest observed PnL % per ticker from prior shadow run (read-only)."""
    data, ok = load_json(path)
    if not ok or not data:
        return {}
    peaks: dict[str, float] = {}
    for row in data.get("positions") or []:
        ticker = str(row.get("ticker", "")).upper()
        if not ticker:
            continue
        rules = row.get("rules_v1") or {}
        peak = rules.get("peak_pnl_pct")
        if peak is not None:
            peaks[ticker] = float(peak)
    return peaks


def portfolio_latest_metrics(portfolio: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Latest PnL_% and Current_Price per ticker from portfolio rows (read-only)."""
    if portfolio.empty:
        return {}
    df = portfolio.copy()
    df["Ticker"] = df["Ticker"].astype(str).str.upper()
    metrics: dict[str, dict[str, float]] = {}
    for ticker, group in df.groupby("Ticker"):
        if ticker == "CASH":
            continue
        last = group.iloc[-1]
        pnl_pct = pd.to_numeric(last.get("PnL_%"), errors="coerce")
        current_price = pd.to_numeric(last.get("Current_Price"), errors="coerce")
        entry: dict[str, float] = {}
        if pd.notna(pnl_pct):
            entry["current_pnl_pct"] = float(pnl_pct)
        if pd.notna(current_price):
            entry["current_price"] = float(current_price)
        if entry:
            metrics[ticker] = entry
    return metrics


def detect_reentry_cooldown(
    ticker: str,
    portfolio: pd.DataFrame,
    *,
    cooldown_hours: float = COOLDOWN_HOURS_AFTER_PROFIT_SELL,
) -> tuple[bool, str]:
    """
    REENTRY_COOLDOWN_REQUIRED when a profitable SELL was followed by a BUY
    within the cooldown window (read-only portfolio scan).
    """
    if portfolio.empty:
        return False, ""

    df = portfolio.copy()
    df["Ticker"] = df["Ticker"].astype(str).str.upper()
    df = df[df["Ticker"] == ticker.upper()].copy()
    if df.empty:
        return False, ""

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date")

    last_profit_sell: pd.Timestamp | None = None
    last_profit_reason = ""
    for _, row in df.iterrows():
        action = str(row.get("Action", "")).upper()
        reason = str(row.get("Reason", ""))
        if action == "SELL" and "PROFIT" in reason.upper():
            ts = row["Date"]
            if pd.notna(ts):
                last_profit_sell = ts
                last_profit_reason = reason

    if last_profit_sell is None:
        return False, ""

    buys_after = df[
        (df["Action"].astype(str).str.upper() == "BUY")
        & (df["Date"] > last_profit_sell)
    ]
    if buys_after.empty:
        return False, ""

    first_rebuy = buys_after.iloc[0]
    rebuy_ts = first_rebuy["Date"]
    if pd.isna(rebuy_ts):
        return False, ""

    hours = (rebuy_ts - last_profit_sell).total_seconds() / 3600.0
    if hours <= cooldown_hours:
        return (
            True,
            f"SHADOW_ONLY: profitable SELL then BUY within {hours:.1f}h "
            f"(cooldown {cooldown_hours:.0f}h); last sell reason: {last_profit_reason}",
        )
    return False, ""


def evaluate_rules_v1(
    *,
    current_pnl_pct: float,
    peak_pnl_pct: float,
    reentry_cooldown: bool = False,
    reentry_reason: str = "",
) -> dict[str, Any]:
    """
    TAE Profit Protection Rules v1 — advisory flags only (SHADOW_ONLY).
    """
    flags: list[str] = []
    partial_advisories: list[str] = []

    profit_lock_active = current_pnl_pct >= PROFIT_LOCK_PCT or peak_pnl_pct >= PROFIT_LOCK_PCT
    if profit_lock_active:
        flags.append("PROFIT_LOCK_ACTIVE")

    fade_from_peak = peak_pnl_pct - current_pnl_pct
    profit_at_risk = (
        profit_lock_active
        and peak_pnl_pct >= PROFIT_LOCK_PCT
        and fade_from_peak >= PEAK_FADE_ALERT_PCT
    )
    if profit_at_risk:
        flags.append("PROFIT_AT_RISK")

    if current_pnl_pct > 0:
        for threshold, advisory in PARTIAL_ADVISORY_LEVELS:
            if current_pnl_pct >= threshold:
                partial_advisories.append(advisory)
                flags.append(advisory)

    if reentry_cooldown:
        flags.append("REENTRY_COOLDOWN_REQUIRED")

    primary = flags[-1] if flags else "NO_RULES_V1_FLAG"

    reason_parts: list[str] = ["SHADOW_ONLY: rules v1 evaluation."]
    if profit_lock_active:
        reason_parts.append(f"Profit lock at >= {PROFIT_LOCK_PCT}%.")
    if profit_at_risk:
        reason_parts.append(
            f"Peak {peak_pnl_pct:.2f}% faded {fade_from_peak:.2f}% from peak."
        )
    if partial_advisories:
        reason_parts.append(f"Partial TP advisories: {', '.join(partial_advisories)}.")
    if reentry_cooldown and reentry_reason:
        reason_parts.append(reentry_reason)

    return {
        "rules_version": RULES_VERSION,
        "flags": flags,
        "primary_flag": primary if flags else "NO_RULES_V1_FLAG",
        "profit_lock_active": profit_lock_active,
        "profit_at_risk": profit_at_risk,
        "peak_pnl_pct": round(peak_pnl_pct, 2),
        "current_pnl_pct": round(current_pnl_pct, 2),
        "fade_from_peak_pct": round(fade_from_peak, 2),
        "partial_take_profit_advisories": partial_advisories,
        "reentry_cooldown_required": reentry_cooldown,
        "reason": " ".join(reason_parts),
    }


def evaluate_protection_signal(
    *,
    high_pct: float,
    current_pct: float,
    drawdown_from_high_pct: float,
    missed_opportunity_usd: float,
    shadow: dict[str, float],
    discovery_strategy: str | None = None,
    knowledge_trailing: bool = False,
) -> tuple[str, str, str]:
    """
    Returns (protection_signal, suggested_shadow_action, reason).
    Priority: PARTIAL_30 > PARTIAL_20 > TRAILING > WATCH > NO_PROTECTION.
    """
    if (
        high_pct >= 5
        and drawdown_from_high_pct <= -1
        and current_pct > -1.5
    ):
        return (
            "PARTIAL_TAKE_PROFIT_SHADOW_30",
            "TEST_SELL_30",
            "SHADOW_ONLY: high_pct>=5 with fade from high; test 30% partial at intraday peak.",
        )

    if (
        high_pct >= 3
        and drawdown_from_high_pct <= -1.5
        and current_pct > -1
    ):
        return (
            "PARTIAL_TAKE_PROFIT_SHADOW_20",
            "TEST_SELL_20",
            "SHADOW_ONLY: high_pct>=3 with >=1.5% fade; test 20% partial at intraday peak.",
        )

    if (
        high_pct >= 2
        and drawdown_from_high_pct <= -1
        and trailing_is_best_shadow(shadow, discovery_strategy, knowledge_trailing)
    ):
        action = preferred_trailing_action(shadow)
        return (
            "TRAILING_PROTECTION_SHADOW",
            action,
            "SHADOW_ONLY: intraday fade with trailing as best shadow strategy.",
        )

    if (
        high_pct >= 2
        and drawdown_from_high_pct <= -1
        and missed_opportunity_usd > 25
    ):
        return (
            "PROFIT_PROTECTION_WATCH",
            "OBSERVE",
            "SHADOW_ONLY: meaningful intraday fade detected; continue observation.",
        )

    return (
        "NO_PROTECTION",
        "OBSERVE",
        "SHADOW_ONLY: no profit protection shadow rule matched.",
    )


def analyze_position(
    position: dict[str, Any],
    *,
    fifo_shares: float | None,
    fifo_avg: float | None,
    obs_count: int,
    discovery_strategy: str | None,
    knowledge_trailing: bool,
    prior_peak_pnl_pct: float | None = None,
    portfolio_pnl_pct: float | None = None,
    reentry_cooldown: bool = False,
    reentry_reason: str = "",
) -> dict[str, Any]:
    ticker = str(position.get("ticker", "")).upper()
    shares = float(fifo_shares if fifo_shares is not None else position.get("shares") or 0)
    avg_price = float(fifo_avg if fifo_avg is not None else position.get("avg_price") or 0)

    high_pct = float(position.get("high_pct") or 0)
    current_pct = float(position.get("current_pct") or 0)
    drawdown = float(position.get("drawdown_from_high_pct") or 0)
    missed = float(position.get("missed_opportunity_usd") or 0)
    shadow = _shadow_values(position)

    signal, action, reason = evaluate_protection_signal(
        high_pct=high_pct,
        current_pct=current_pct,
        drawdown_from_high_pct=drawdown,
        missed_opportunity_usd=missed,
        shadow=shadow,
        discovery_strategy=discovery_strategy,
        knowledge_trailing=knowledge_trailing,
    )

    if knowledge_trailing and signal == "PROFIT_PROTECTION_WATCH":
        if trailing_is_best_shadow(shadow, discovery_strategy, knowledge_trailing):
            signal = "TRAILING_PROTECTION_SHADOW"
            action = preferred_trailing_action(shadow)
            reason = "SHADOW_ONLY: knowledge base prioritizes trailing shadow testing."

    effective_current = float(
        portfolio_pnl_pct if portfolio_pnl_pct is not None else current_pct
    )
    peak_pnl = max(
        effective_current,
        high_pct,
        float(prior_peak_pnl_pct or 0),
    )
    rules_v1 = evaluate_rules_v1(
        current_pnl_pct=effective_current,
        peak_pnl_pct=peak_pnl,
        reentry_cooldown=reentry_cooldown,
        reentry_reason=reentry_reason,
    )

    return {
        "ticker": ticker,
        "shares": round(shares, 4),
        "avg_price": round(avg_price, 2),
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown_from_high_pct": round(drawdown, 2),
        "missed_opportunity_usd": round(missed, 2),
        "classification": position.get("classification", "UNKNOWN"),
        "protection_signal": signal,
        "suggested_shadow_action": action,
        "confidence": confidence_from_observations(obs_count),
        "reason": reason,
        "estimated_protected_value_20": round(shadow["sell_20"], 2),
        "estimated_protected_value_30": round(shadow["sell_30"], 2),
        "estimated_trailing_value_1": round(shadow["trailing_1"], 2),
        "estimated_trailing_value_1_5": round(shadow["trailing_1_5"], 2),
        "rules_v1": rules_v1,
        "shadow_only": True,
    }


def build_daily_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "total_positions": len(positions),
        "num_watch": sum(1 for p in positions if p["protection_signal"] == "PROFIT_PROTECTION_WATCH"),
        "num_partial20": sum(
            1 for p in positions if p["protection_signal"] == "PARTIAL_TAKE_PROFIT_SHADOW_20"
        ),
        "num_partial30": sum(
            1 for p in positions if p["protection_signal"] == "PARTIAL_TAKE_PROFIT_SHADOW_30"
        ),
        "num_trailing": sum(
            1 for p in positions if p["protection_signal"] == "TRAILING_PROTECTION_SHADOW"
        ),
        "total_missed_opportunity": round(
            sum(p.get("missed_opportunity_usd", 0) for p in positions), 2
        ),
        "estimated_total_protected_20": round(
            sum(p.get("estimated_protected_value_20", 0) for p in positions), 2
        ),
        "estimated_total_protected_30": round(
            sum(p.get("estimated_protected_value_30", 0) for p in positions), 2
        ),
        "estimated_total_trailing_1": round(
            sum(p.get("estimated_trailing_value_1", 0) for p in positions), 2
        ),
        "estimated_total_trailing_1_5": round(
            sum(p.get("estimated_trailing_value_1_5", 0) for p in positions), 2
        ),
        "num_profit_lock_active": sum(
            1 for p in positions if (p.get("rules_v1") or {}).get("profit_lock_active")
        ),
        "num_profit_at_risk": sum(
            1 for p in positions if (p.get("rules_v1") or {}).get("profit_at_risk")
        ),
        "num_partial_tp_advisories": sum(
            len((p.get("rules_v1") or {}).get("partial_take_profit_advisories") or [])
            for p in positions
        ),
        "num_reentry_cooldown": sum(
            1 for p in positions if (p.get("rules_v1") or {}).get("reentry_cooldown_required")
        ),
    }

    method_totals = {
        "TEST_SELL_20": totals["estimated_total_protected_20"],
        "TEST_SELL_30": totals["estimated_total_protected_30"],
        "TEST_TRAILING_1": totals["estimated_total_trailing_1"],
        "TEST_TRAILING_1_5": totals["estimated_total_trailing_1_5"],
    }
    best_method = max(method_totals, key=method_totals.get) if positions else "OBSERVE"
    totals["best_shadow_protection_method"] = best_method

    actionable = totals["num_watch"] + totals["num_partial20"] + totals["num_partial30"] + totals["num_trailing"]
    v1_actionable = (
        totals["num_profit_at_risk"]
        + totals["num_partial_tp_advisories"]
        + totals["num_reentry_cooldown"]
    )
    if totals["total_missed_opportunity"] > 300:
        verdict = "SHADOW_ONLY: TAE missed major intraday profit — protection shadow review recommended."
    elif actionable > 0 or v1_actionable > 0:
        verdict = "SHADOW_ONLY: profit protection signals active — paper simulation only."
    else:
        verdict = "SHADOW_ONLY: no profit protection shadow triggers today."

    totals["rules_v1_verdict"] = (
        f"SHADOW_ONLY rules v1: {totals['num_profit_lock_active']} lock, "
        f"{totals['num_profit_at_risk']} at-risk, "
        f"{totals['num_partial_tp_advisories']} partial TP advisories, "
        f"{totals['num_reentry_cooldown']} reentry cooldown."
    )
    totals["verdict"] = verdict
    return totals


def build_profit_protection_report(
    *,
    portfolio_path: Path = PORTFOLIO_FILE,
    fade_intelligence_path: Path = FADE_INTELLIGENCE_JSON,
    history_csv_path: Path = FADE_HISTORY_CSV,
    discovery_path: Path = DISCOVERY_JSON,
    knowledge_path: Path = KNOWLEDGE_BASE_JSON,
) -> dict[str, Any]:
    sources_loaded: dict[str, bool] = {}

    fade_intel, ok = load_json(fade_intelligence_path)
    sources_loaded[str(fade_intelligence_path)] = ok

    discovery, ok_d = load_json(discovery_path)
    sources_loaded[str(discovery_path)] = ok_d

    knowledge, ok_k = load_json(knowledge_path)
    sources_loaded[str(knowledge_path)] = ok_k

    sources_loaded[str(history_csv_path)] = history_csv_path.is_file()
    sources_loaded[str(portfolio_path)] = portfolio_path.is_file()

    fifo_map: dict[str, tuple[float, float]] = {}
    portfolio_metrics: dict[str, dict[str, float]] = {}
    portfolio_df = pd.DataFrame()
    cooldown_by_ticker: dict[str, tuple[bool, str]] = {}
    if portfolio_path.is_file():
        try:
            portfolio_df = pd.read_csv(portfolio_path)
            for ticker, pos in fifo_open_positions(portfolio_df).items():
                fifo_map[ticker] = (pos.shares, pos.avg_price)
            portfolio_metrics = portfolio_latest_metrics(portfolio_df)
            for ticker in fifo_map:
                cooldown_by_ticker[ticker] = detect_reentry_cooldown(ticker, portfolio_df)
        except OSError:
            pass

    prior_peaks = load_peak_state()
    obs_counts = observation_counts(history_csv_path)
    discovery_by_ticker = discovery_best_shadow_by_ticker(discovery)
    knowledge_trailing = knowledge_prefers_trailing(knowledge)

    fade_rows: dict[str, dict[str, Any]] = {}
    for row in (fade_intel or {}).get("positions") or []:
        if row.get("classification") == "DATA_UNAVAILABLE":
            continue
        ticker = str(row.get("ticker", "")).upper()
        if ticker:
            fade_rows[ticker] = row

    all_tickers = sorted(set(fade_rows) | set(fifo_map))
    positions: list[dict[str, Any]] = []
    for ticker in all_tickers:
        row = fade_rows.get(ticker) or {
            "ticker": ticker,
            "shares": fifo_map.get(ticker, (0, 0))[0],
            "avg_price": fifo_map.get(ticker, (0, 0))[1],
            "high_pct": portfolio_metrics.get(ticker, {}).get("current_pnl_pct", 0),
            "current_pct": portfolio_metrics.get(ticker, {}).get("current_pnl_pct", 0),
            "drawdown_from_high_pct": 0,
            "missed_opportunity_usd": 0,
            "classification": "PORTFOLIO_ONLY",
            "shadow": {},
        }
        fifo = fifo_map.get(ticker, (None, None))
        cooldown, cooldown_reason = cooldown_by_ticker.get(ticker, (False, ""))
        pm = portfolio_metrics.get(ticker, {})
        positions.append(
            analyze_position(
                row,
                fifo_shares=fifo[0],
                fifo_avg=fifo[1],
                obs_count=int(obs_counts.get(ticker, 0)),
                discovery_strategy=discovery_by_ticker.get(ticker),
                knowledge_trailing=knowledge_trailing,
                prior_peak_pnl_pct=prior_peaks.get(ticker),
                portfolio_pnl_pct=pm.get("current_pnl_pct"),
                reentry_cooldown=cooldown,
                reentry_reason=cooldown_reason,
            )
        )

    positions.sort(key=lambda p: p.get("missed_opportunity_usd", 0), reverse=True)
    summary = build_daily_summary(positions)

    rules_v1_config = {
        "profit_lock_pct": PROFIT_LOCK_PCT,
        "peak_fade_alert_pct": PEAK_FADE_ALERT_PCT,
        "partial_levels": [
            {"threshold_pct": t, "advisory": a} for t, a in PARTIAL_ADVISORY_LEVELS
        ],
        "cooldown_hours_after_profit_sell": COOLDOWN_HOURS_AFTER_PROFIT_SELL,
        "never_take_profit_when_pnl_lte_zero": True,
    }

    return {
        "schema": "tae_profit_protection_shadow",
        "rules_version": RULES_VERSION,
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "knowledge_trailing_priority": knowledge_trailing,
        "rules_v1_config": rules_v1_config,
        "positions": positions,
        "daily_summary": summary,
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["daily_summary"]
    lines = [
        "# TAE Profit Protection Shadow",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Daily verdict",
        summary["verdict"],
        "",
        "## Summary",
        f"- Positions: **{summary['total_positions']}**",
        f"- Watch: **{summary['num_watch']}** | Partial 20%: **{summary['num_partial20']}** | "
        f"Partial 30%: **{summary['num_partial30']}** | Trailing: **{summary['num_trailing']}**",
        f"- Total missed opportunity: **{summary['total_missed_opportunity']} USD**",
        f"- Best shadow method: **{summary['best_shadow_protection_method']}**",
        "",
        "## Rules v1 summary",
        summary.get("rules_v1_verdict", ""),
        f"- Profit lock active: **{summary.get('num_profit_lock_active', 0)}**",
        f"- Profit at risk: **{summary.get('num_profit_at_risk', 0)}**",
        f"- Partial TP advisories: **{summary.get('num_partial_tp_advisories', 0)}**",
        f"- Reentry cooldown: **{summary.get('num_reentry_cooldown', 0)}**",
        "",
        "## Positions",
        "",
        "| ticker | high_pct | current_pct | drawdown | missed_usd | signal | action | rules_v1 | confidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in report.get("positions") or []:
        rules = row.get("rules_v1") or {}
        v1_flags = ", ".join(rules.get("flags") or []) or "—"
        lines.append(
            f"| {row['ticker']} | {row['high_pct']} | {row['current_pct']} | "
            f"{row['drawdown_from_high_pct']} | {row['missed_opportunity_usd']} | "
            f"{row['protection_signal']} | {row['suggested_shadow_action']} | "
            f"{v1_flags} | {row['confidence']} |"
        )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["daily_summary"]
    print("===== TAE PROFIT PROTECTION SHADOW =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Positions:", summary["total_positions"])
    print("Missed opportunity:", summary["total_missed_opportunity"])
    print("Watch / Partial20 / Partial30 / Trailing:", summary["num_watch"], summary["num_partial20"], summary["num_partial30"], summary["num_trailing"])
    print(
        "Rules v1 lock / at-risk / partial TP / cooldown:",
        summary.get("num_profit_lock_active", 0),
        summary.get("num_profit_at_risk", 0),
        summary.get("num_partial_tp_advisories", 0),
        summary.get("num_reentry_cooldown", 0),
    )
    print("Best shadow method:", summary["best_shadow_protection_method"])
    print("Verdict:", summary["verdict"])


def main() -> int:
    report = build_profit_protection_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
