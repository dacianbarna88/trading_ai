#!/usr/bin/env python3
"""
TAE Stop Re-entry Cooldown Shadow Audit — X.COOLDOWN-1.

SHADOW_ONLY / PAPER_ONLY / NO_BROKER.
Measures whether rapid re-entry after STOP hurts performance.
Does NOT modify live_bot, portfolio, or signals.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

PORTFOLIO_FILE = Path("portfolio.csv")
SIGNALS_FILE = Path("live_signals.csv")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")

OUTPUT_JSON = Path("tae_stop_reentry_cooldown_audit.json")
OUTPUT_MD = Path("tae_stop_reentry_cooldown_audit.md")

SHADOW_RECOMMENDATIONS = frozenset(
    {
        "CONTINUE_OBSERVATION",
        "TEST_15M_COOLDOWN_SHADOW",
        "TEST_30M_COOLDOWN_SHADOW",
        "TEST_60M_COOLDOWN_SHADOW",
        "REQUIRE_NEW_CONFIRMATION_SHADOW",
        "DO_NOT_PROMOTE_TO_LIVE",
        "INSUFFICIENT_DATA",
    }
)

FORBIDDEN_RECOMMENDATIONS = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT"})

COOLDOWN_POLICIES = [
    "cooldown_15m",
    "cooldown_30m",
    "cooldown_60m",
    "cooldown_until_next_session",
    "cooldown_until_new_signal_confirmation",
]

GATE_DEFINITIONS: list[tuple[str, str]] = [
    ("G1", "at least 10 stop-reentry cases"),
    ("G2", "cooldown net_effect > 0"),
    ("G3", "second_stop_rate reduced by >= 30%"),
    ("G4", "missed_winner_cost <= avoided_loss * 0.5"),
    ("G5", "score_persistence_loss_rate > 0.5"),
]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def parse_timestamp(value: str) -> datetime | None:
    if not value or pd.isna(value):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def is_stop_loss_row(row: pd.Series) -> bool:
    action = str(row.get("Action", "")).upper()
    reason = str(row.get("Reason", "")).upper()
    return action == "SELL" and "STOP LOSS" in reason


def is_buy_row(row: pd.Series) -> bool:
    return str(row.get("Action", "")).upper() == "BUY"


def load_portfolio(path: Path = PORTFOLIO_FILE) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.copy()
    df["Ticker"] = df["Ticker"].astype(str).str.upper()
    df = df[~df["Ticker"].isin({"", "CASH", "NAN"})]
    df["Action"] = df["Action"].astype(str).str.upper()
    df["_ts"] = df["Date"].apply(parse_timestamp)
    df = df.dropna(subset=["_ts"]).sort_values("_ts").reset_index(drop=True)
    return df


def load_signals(path: Path = SIGNALS_FILE) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.copy()
    ticker_col = next((c for c in df.columns if c.lower() in {"ticker", "symbol"}), None)
    if ticker_col:
        df["Ticker"] = df[ticker_col].astype(str).str.upper()
    ts_col = next((c for c in df.columns if c.lower() in {"date", "timestamp", "time"}), None)
    if ts_col:
        df["_ts"] = df[ts_col].apply(parse_timestamp)
    return df


def classify_reentry_timing(minutes: float, same_day: bool) -> list[str]:
    tags: list[str] = []
    if minutes <= 5:
        tags.append("IMMEDIATE_REENTRY")
    if minutes <= 30:
        tags.append("FAST_REENTRY")
    if same_day:
        tags.append("SAME_SESSION_REENTRY")
    else:
        tags.append("NEXT_SESSION_REENTRY")
    return tags


def _num(row: pd.Series, col: str) -> float | None:
    val = pd.to_numeric(row.get(col), errors="coerce")
    return None if pd.isna(val) else float(val)


def find_signal_at_time(signals: pd.DataFrame, ticker: str, ts: datetime) -> dict[str, Any]:
    if signals.empty or "Ticker" not in signals.columns or "_ts" not in signals.columns:
        return {}
    subset = signals[(signals["Ticker"] == ticker.upper()) & (signals["_ts"] <= ts)]
    if subset.empty:
        return {}
    row = subset.iloc[-1]
    score_col = next((c for c in signals.columns if c.lower() == "score"), None)
    signal_col = next((c for c in signals.columns if c.lower() == "signal"), None)
    return {
        "score": _num(row, score_col) if score_col else _num(row, "Score"),
        "signal": str(row.get(signal_col or "Signal", "")),
    }


def score_at_event(row: pd.Series, signals: pd.DataFrame) -> tuple[float | None, str]:
    score = _num(row, "Score")
    signal = str(row.get("Signal", ""))
    ts = row.get("_ts")
    if ts is not None and (score is None or not signal):
        ext = find_signal_at_time(signals, str(row["Ticker"]), ts)
        score = score if score is not None else ext.get("score")
        signal = signal or str(ext.get("signal", ""))
    return score, signal


def leg_outcome_after_reentry(
    df: pd.DataFrame,
    ticker: str,
    reentry_idx: int,
) -> dict[str, Any]:
    buy_row = df.loc[reentry_idx]
    buy_shares = _num(buy_row, "Shares") or 0.0
    buy_price = _num(buy_row, "Price") or 0.0
    subsequent = df[(df.index > reentry_idx) & (df["Ticker"] == ticker)].copy()

    shares_remaining = buy_shares
    realized_pnl = 0.0
    exit_price: float | None = None
    second_stop = False
    take_profit = False
    exit_reason = ""

    for idx, row in subsequent.iterrows():
        action = str(row["Action"]).upper()
        if action != "SELL":
            continue
        sell_shares = _num(row, "Shares") or 0.0
        sell_pnl = _num(row, "PnL") or 0.0
        allocated = min(shares_remaining, sell_shares)
        if sell_shares > 0 and allocated > 0:
            realized_pnl += sell_pnl * (allocated / sell_shares)
            shares_remaining -= allocated
            exit_price = _num(row, "Price")
            exit_reason = str(row.get("Reason", ""))
            if "STOP LOSS" in exit_reason.upper():
                second_stop = True
            if "TAKE PROFIT" in exit_reason.upper() or "PROFIT" in exit_reason.upper():
                take_profit = True
        if shares_remaining <= 1e-6:
            break

    if shares_remaining > 1e-6:
        last_ticker_rows = df[df["Ticker"] == ticker]
        last_row = last_ticker_rows.iloc[-1]
        open_pnl = _num(last_row, "PnL")
        if open_pnl is not None and last_row.name >= reentry_idx:
            unrealized = open_pnl
            methodology = "ESTIMATED"
            detail = "Open leg PnL from latest portfolio row for ticker."
        else:
            invested = _num(buy_row, "Invested")
            current_value = _num(buy_row, "Current_Value")
            unrealized = (current_value - invested) if invested is not None and current_value is not None else 0.0
            methodology = "ESTIMATED"
            detail = "Open leg PnL from reentry BUY row snapshot."
        outcome = "REENTRY_OPEN_UNREALIZED"
        return {
            "reentry_price": buy_price,
            "shares": buy_shares,
            "exit_price": None,
            "realized_pnl": None,
            "unrealized_pnl": round(unrealized, 2),
            "leg_pnl": round(unrealized, 2),
            "second_stop": False,
            "take_profit": False,
            "outcome": outcome,
            "pnl_methodology": methodology,
            "pnl_detail": detail,
        }

    leg_pnl = round(realized_pnl, 2)
    if second_stop:
        outcome = "REENTRY_SECOND_STOP"
    elif take_profit:
        outcome = "REENTRY_WIN" if leg_pnl >= 0 else "REENTRY_LOSS"
    elif leg_pnl > 0.01:
        outcome = "REENTRY_WIN"
    elif leg_pnl < -0.01:
        outcome = "REENTRY_LOSS"
    else:
        outcome = "REENTRY_UNKNOWN"

    return {
        "reentry_price": buy_price,
        "shares": buy_shares,
        "exit_price": exit_price,
        "realized_pnl": leg_pnl,
        "unrealized_pnl": None,
        "leg_pnl": leg_pnl,
        "second_stop": second_stop,
        "take_profit": take_profit,
        "outcome": outcome,
        "pnl_methodology": "ACTUAL",
        "pnl_detail": "Realized from subsequent SELL row(s) in portfolio.csv.",
    }


def detect_stop_reentries(df: pd.DataFrame, signals: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sequences: list[dict[str, Any]] = []
    stop_events: list[dict[str, Any]] = []

    for ticker in df["Ticker"].unique():
        ticker_df = df[df["Ticker"] == ticker].reset_index(drop=True)
        orig_indices = df[df["Ticker"] == ticker].index.tolist()

        for i, row in ticker_df.iterrows():
            if not is_stop_loss_row(row):
                continue
            stop_ts = row["_ts"]
            stop_idx = orig_indices[i]
            stop_pnl = _num(row, "PnL")
            stop_events.append(
                {
                    "ticker": ticker,
                    "stop_timestamp": stop_ts.isoformat(sep=" "),
                    "stop_pnl": stop_pnl,
                    "stop_score": _num(row, "Score"),
                    "stop_signal": str(row.get("Signal", "")),
                }
            )

            for j in range(i + 1, len(ticker_df)):
                next_row = ticker_df.iloc[j]
                if not is_buy_row(next_row):
                    continue
                reentry_ts = next_row["_ts"]
                minutes = (reentry_ts - stop_ts).total_seconds() / 60.0
                same_day = stop_ts.date() == reentry_ts.date()
                reentry_idx = orig_indices[j]
                reentry_score, reentry_signal = score_at_event(next_row, signals)
                leg = leg_outcome_after_reentry(df, ticker, reentry_idx)

                sequences.append(
                    {
                        "sequence_id": f"{ticker}_{stop_ts.strftime('%Y%m%d%H%M%S')}_{j}",
                        "ticker": ticker,
                        "stop_timestamp": stop_ts.isoformat(sep=" "),
                        "stop_pnl": stop_pnl,
                        "reentry_timestamp": reentry_ts.isoformat(sep=" "),
                        "minutes_after_stop": round(minutes, 2),
                        "same_session": same_day,
                        "timing_tags": classify_reentry_timing(minutes, same_day),
                        "reentry_score": reentry_score,
                        "reentry_signal": reentry_signal,
                        "score_persistence_after_stop": (
                            reentry_score is not None
                            and reentry_score >= 80
                            and "STRONG BUY" in reentry_signal.upper()
                        ),
                        **leg,
                    }
                )
                break

    return sequences, stop_events


def has_new_confirmation(
    df: pd.DataFrame,
    ticker: str,
    stop_ts: datetime,
    reentry_ts: datetime,
    stop_score: float | None,
) -> bool:
    between = df[
        (df["Ticker"] == ticker) & (df["_ts"] > stop_ts) & (df["_ts"] < reentry_ts)
    ]
    if between.empty:
        return False
    scores = pd.to_numeric(between.get("Score"), errors="coerce").dropna()
    if scores.empty or stop_score is None:
        signals = between["Signal"].astype(str).str.upper()
        return any("WAIT" in s or "HOLD" in s for s in signals)
    return float(scores.min()) <= stop_score - 20


def would_block_cooldown(
    policy: str,
    *,
    minutes: float,
    same_day: bool,
    stop_ts: datetime,
    reentry_ts: datetime,
    df: pd.DataFrame,
    ticker: str,
    stop_score: float | None,
) -> bool:
    if policy == "cooldown_15m":
        return minutes <= 15
    if policy == "cooldown_30m":
        return minutes <= 30
    if policy == "cooldown_60m":
        return minutes <= 60
    if policy == "cooldown_until_next_session":
        return same_day
    if policy == "cooldown_until_new_signal_confirmation":
        return not has_new_confirmation(df, ticker, stop_ts, reentry_ts, stop_score)
    return False


def simulate_cooldowns(
    sequences: list[dict[str, Any]],
    df: pd.DataFrame,
) -> dict[str, Any]:
    baseline_second_stops = sum(1 for s in sequences if s.get("second_stop"))
    baseline_rate = baseline_second_stops / len(sequences) if sequences else 0.0

    results: dict[str, Any] = {}
    for policy in COOLDOWN_POLICIES:
        blocked = 0
        avoided_loss = 0.0
        missed_gain = 0.0
        blocked_second_stops = 0
        for seq in sequences:
            stop_ts = parse_timestamp(seq["stop_timestamp"])
            reentry_ts = parse_timestamp(seq["reentry_timestamp"])
            if stop_ts is None or reentry_ts is None:
                continue
            minutes = seq["minutes_after_stop"]
            same_day = seq["same_session"]
            stop_score = seq.get("reentry_score")
            ticker = seq["ticker"]
            stop_row_score = None
            if stop_ts:
                stop_rows = df[(df["Ticker"] == ticker) & (df["_ts"] == stop_ts)]
                if not stop_rows.empty:
                    stop_row_score = _num(stop_rows.iloc[0], "Score")

            if would_block_cooldown(
                policy,
                minutes=minutes,
                same_day=same_day,
                stop_ts=stop_ts,
                reentry_ts=reentry_ts,
                df=df,
                ticker=ticker,
                stop_score=stop_row_score,
            ):
                blocked += 1
                leg_pnl = float(seq.get("leg_pnl") or 0)
                if leg_pnl < 0:
                    avoided_loss += abs(leg_pnl)
                elif leg_pnl > 0:
                    missed_gain += leg_pnl
                if seq.get("second_stop"):
                    blocked_second_stops += 1

        net_effect = round(avoided_loss - missed_gain, 2)
        new_rate = (
            (baseline_second_stops - blocked_second_stops) / max(len(sequences) - blocked, 1)
            if sequences
            else 0.0
        )
        rate_reduction = (
            round((baseline_rate - new_rate) / baseline_rate, 4) if baseline_rate > 0 else 0.0
        )
        results[policy] = {
            "blocked_reentries": blocked,
            "avoided_loss_usd": round(avoided_loss, 2),
            "missed_gain_usd": round(missed_gain, 2),
            "net_effect_usd": net_effect,
            "blocked_second_stops": blocked_second_stops,
            "baseline_second_stop_rate": round(baseline_rate, 4),
            "simulated_second_stop_rate": round(new_rate, 4),
            "second_stop_rate_reduction": rate_reduction,
        }

    best = max(results.items(), key=lambda kv: kv[1]["net_effect_usd"])[0] if results else None
    return {"simulations": results, "best_cooldown": best}


def score_persistence_audit(sequences: list[dict[str, Any]]) -> dict[str, Any]:
    flagged = [s for s in sequences if s.get("score_persistence_after_stop")]
    if not flagged:
        return {
            "count": 0,
            "average_leg_pnl": 0.0,
            "loss_rate": 0.0,
            "second_stop_rate": 0.0,
            "cases": [],
        }
    pnls = [float(s.get("leg_pnl") or 0) for s in flagged]
    losses = sum(1 for p in pnls if p < 0)
    second_stops = sum(1 for s in flagged if s.get("second_stop") or s.get("outcome") == "REENTRY_SECOND_STOP")
    return {
        "count": len(flagged),
        "average_leg_pnl": round(sum(pnls) / len(pnls), 2),
        "loss_rate": round(losses / len(flagged), 4),
        "second_stop_rate": round(second_stops / len(flagged), 4),
        "cases": [
            {
                "ticker": s["ticker"],
                "reentry_score": s.get("reentry_score"),
                "outcome": s.get("outcome"),
                "leg_pnl": s.get("leg_pnl"),
            }
            for s in flagged
        ],
    }


def evaluate_gates(
    sequences: list[dict[str, Any]],
    cooldown: dict[str, Any],
    persistence: dict[str, Any],
) -> dict[str, Any]:
    best_name = cooldown.get("best_cooldown")
    best_sim = (cooldown.get("simulations") or {}).get(best_name or "", {})

    g1 = len(sequences) >= 10
    g2 = best_sim.get("net_effect_usd", 0) > 0
    g3 = best_sim.get("second_stop_rate_reduction", 0) >= 0.30
    missed = best_sim.get("missed_gain_usd", 0)
    avoided = best_sim.get("avoided_loss_usd", 0)
    g4 = missed <= avoided * 0.5 if avoided > 0 else missed == 0
    g5 = persistence.get("loss_rate", 0) > 0.5

    gate_map = {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5}
    failed = [k for k, ok in gate_map.items() if not ok]
    all_pass = not failed and g1

    if len(sequences) < 10:
        readiness = "NOT_READY"
    elif all_pass:
        readiness = "READY_FOR_SHADOW_ADVISORY"
    elif g2 and g5:
        readiness = "WATCH"
    else:
        readiness = "NOT_READY"

    return {
        "gates": gate_map,
        "gate_definitions": {n: d for n, d in GATE_DEFINITIONS},
        "gates_passed": all_pass,
        "failed_gates": failed,
        "advisory_readiness": readiness,
        "best_cooldown_policy": best_name,
    }


def build_recommendations(gates: dict[str, Any], cooldown: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    if gates["advisory_readiness"] == "NOT_READY":
        recs.append("CONTINUE_OBSERVATION")
        recs.append("DO_NOT_PROMOTE_TO_LIVE")
    best = gates.get("best_cooldown_policy")
    mapping = {
        "cooldown_15m": "TEST_15M_COOLDOWN_SHADOW",
        "cooldown_30m": "TEST_30M_COOLDOWN_SHADOW",
        "cooldown_60m": "TEST_60M_COOLDOWN_SHADOW",
        "cooldown_until_new_signal_confirmation": "REQUIRE_NEW_CONFIRMATION_SHADOW",
    }
    if best in mapping and cooldown.get("simulations", {}).get(best, {}).get("net_effect_usd", 0) > 0:
        recs.append(mapping[best])
    if not recs:
        recs.append("INSUFFICIENT_DATA")
    deduped: list[str] = []
    for r in recs:
        if r not in deduped:
            deduped.append(r)
    assert not (set(deduped) & FORBIDDEN_RECOMMENDATIONS)
    return deduped


def build_summary(sequences: list[dict[str, Any]], stop_events: list[dict[str, Any]]) -> dict[str, Any]:
    immediate = sum(1 for s in sequences if "IMMEDIATE_REENTRY" in s.get("timing_tags", []))
    fast = sum(1 for s in sequences if "FAST_REENTRY" in s.get("timing_tags", []))
    same_session = sum(1 for s in sequences if s.get("same_session"))
    wins = sum(1 for s in sequences if s.get("outcome") == "REENTRY_WIN")
    losses = sum(1 for s in sequences if s.get("outcome") in {"REENTRY_LOSS", "REENTRY_SECOND_STOP"})
    second_stops = sum(1 for s in sequences if s.get("second_stop") or s.get("outcome") == "REENTRY_SECOND_STOP")
    total_pnl = round(sum(float(s.get("leg_pnl") or 0) for s in sequences), 2)
    return {
        "total_stop_events": len(stop_events),
        "total_reentries": len(sequences),
        "immediate_reentries": immediate,
        "fast_reentries": fast,
        "same_session_reentries": same_session,
        "reentry_wins": wins,
        "reentry_losses": losses,
        "second_stop_count": second_stops,
        "total_reentry_pnl_usd": total_pnl,
    }


def build_audit_report(
    *,
    portfolio_path: Path = PORTFOLIO_FILE,
    signals_path: Path = SIGNALS_FILE,
    accounting_path: Path = ACCOUNTING_JSON,
) -> dict[str, Any]:
    df = load_portfolio(portfolio_path)
    signals = load_signals(signals_path)
    accounting = load_json(accounting_path)

    if df.empty:
        return {
            "schema": "tae_stop_reentry_cooldown_audit",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "SHADOW_ONLY",
            "live_trading_impact": "NONE",
            "dataset_health": {"portfolio_rows": 0, "signals_loaded": False},
            "summary": build_summary([], []),
            "stop_reentry_sequences": [],
            "cooldown_simulation": {"simulations": {}, "best_cooldown": None},
            "score_persistence": score_persistence_audit([]),
            "gates": evaluate_gates([], {"simulations": {}, "best_cooldown": None}, {}),
            "recommendations": ["INSUFFICIENT_DATA", "DO_NOT_PROMOTE_TO_LIVE"],
            "verdict": "NO_PORTFOLIO_DATA",
            "next_step": "Provide portfolio.csv with STOP/BUY history.",
        }

    sequences, stop_events = detect_stop_reentries(df, signals)
    cooldown = simulate_cooldowns(sequences, df)
    persistence = score_persistence_audit(sequences)
    summary = build_summary(sequences, stop_events)
    summary["best_cooldown"] = cooldown.get("best_cooldown")
    gates = evaluate_gates(sequences, cooldown, persistence)
    recommendations = build_recommendations(gates, cooldown)

    if len(sequences) < 10:
        verdict = "INSUFFICIENT_SAMPLE"
    elif gates["advisory_readiness"] == "READY_FOR_SHADOW_ADVISORY":
        verdict = "COOLDOWN_WORTH_SHADOW_TEST"
    elif gates["gates"]["G2"] and persistence["loss_rate"] > 0.5:
        verdict = "PROMISING_BUT_NOT_READY"
    else:
        verdict = "CONTINUE_OBSERVATION"

    return {
        "schema": "tae_stop_reentry_cooldown_audit",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "dataset_health": {
            "portfolio_rows": len(df),
            "signals_loaded": not signals.empty,
            "accounting_loaded": accounting is not None,
            "stop_reentry_cases": len(sequences),
        },
        "summary": summary,
        "stop_reentry_sequences": sequences,
        "cooldown_simulation": cooldown,
        "score_persistence": persistence,
        "gates": gates,
        "recommendations": recommendations,
        "verdict": verdict,
        "next_step": (
            "Proceed to X.REPLAY-1 to integrate stop-reentry cost with exit protection findings."
            if len(sequences) >= 3
            else "Continue observation until more STOP→BUY sequences accumulate."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    gates = report.get("gates") or {}
    cooldown = report.get("cooldown_simulation") or {}
    persistence = report.get("score_persistence") or {}
    lines = [
        "# TAE Stop Re-entry Cooldown Audit (X.COOLDOWN-1)",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} | **Verdict:** {report['verdict']}",
        "",
        "## Summary",
        f"- Total STOP events: **{summary.get('total_stop_events', 0)}**",
        f"- Total reentries after STOP: **{summary.get('total_reentries', 0)}**",
        f"- Immediate (≤5m): {summary.get('immediate_reentries', 0)}",
        f"- Fast (≤30m): {summary.get('fast_reentries', 0)}",
        f"- Same session: {summary.get('same_session_reentries', 0)}",
        f"- Second STOP after reentry: {summary.get('second_stop_count', 0)}",
        f"- Total reentry PnL: **{summary.get('total_reentry_pnl_usd', 0)} USD**",
        f"- Best cooldown: **{summary.get('best_cooldown', 'n/a')}**",
        "",
        "## Cooldown simulations",
        "",
        "| Policy | Blocked | Avoided loss | Missed gain | Net effect |",
        "|--------|---------|--------------|-------------|------------|",
    ]
    for name, sim in (cooldown.get("simulations") or {}).items():
        lines.append(
            f"| {name} | {sim['blocked_reentries']} | {sim['avoided_loss_usd']} | "
            f"{sim['missed_gain_usd']} | **{sim['net_effect_usd']}** |"
        )
    lines.extend(
        [
            "",
            "## Score persistence after STOP",
            f"- Cases (score≥80 + STRONG BUY): **{persistence.get('count', 0)}**",
            f"- Average leg PnL: {persistence.get('average_leg_pnl', 0)} USD",
            f"- Loss rate: {persistence.get('loss_rate', 0):.0%}",
            f"- Second STOP rate: {persistence.get('second_stop_rate', 0):.0%}",
            "",
            "## Gates G1–G5",
            f"- Advisory readiness: **{gates.get('advisory_readiness', 'NOT_READY')}**",
            f"- Gates passed: {gates.get('gates_passed', False)}",
            f"- Failed: {', '.join(gates.get('failed_gates', [])) or 'none'}",
            "",
        ]
    )
    for name, ok in (gates.get("gates") or {}).items():
        desc = (gates.get("gate_definitions") or {}).get(name, "")
        lines.append(f"- **{name}** ({desc}): {'PASS' if ok else 'FAIL'}")
    lines.extend(["", "## Notable sequences", ""])
    for seq in report.get("stop_reentry_sequences", [])[:12]:
        lines.append(
            f"- **{seq['ticker']}** — {seq['minutes_after_stop']}m after STOP, "
            f"score={seq.get('reentry_score')}, outcome={seq.get('outcome')}, "
            f"leg_pnl={seq.get('leg_pnl')} ({seq.get('pnl_methodology', 'n/a')})"
        )
    lines.extend(["", "## Recommendations (SHADOW_ONLY)", ""])
    for r in report.get("recommendations", []):
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## Next step",
            report.get("next_step", ""),
            "",
            "*No live BUY/SELL. Shadow audit only.*",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report.get("summary") or {}
    gates = report.get("gates") or {}
    print("===== TAE STOP REENTRY COOLDOWN AUDIT (X.COOLDOWN-1) =====")
    print("Mode: SHADOW_ONLY | Verdict:", report.get("verdict"))
    print("STOP events:", summary.get("total_stop_events"), "| Reentries:", summary.get("total_reentries"))
    print("Immediate reentries:", summary.get("immediate_reentries"))
    print("Second stops:", summary.get("second_stop_count"), "| Reentry PnL:", summary.get("total_reentry_pnl_usd"))
    print("Advisory readiness:", gates.get("advisory_readiness"))
    print("Recommendations:", ", ".join(report.get("recommendations", [])))


def main() -> int:
    report = build_audit_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
