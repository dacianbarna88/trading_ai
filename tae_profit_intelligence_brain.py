#!/usr/bin/env python3
"""
TAE Profit Intelligence Brain v1 — SHADOW_ONLY / NO_BROKER.

Multi-factor shadow recommendation engine for profit protection.
Does NOT modify live_bot, portfolio, signals, or broker execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tae_profit_protection_shadow import confidence_from_observations

SHADOW_JSON = Path("tae_profit_protection_shadow.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
LIVE_SIGNALS_CSV = Path("live_signals.csv")
PORTFOLIO_CSV = Path("portfolio.csv")
BOT_OUTPUT_LOG = Path("bot_output.log")

OUTPUT_JSON = Path("tae_profit_intelligence_brain.json")
OUTPUT_MD = Path("tae_profit_intelligence_brain.md")

FINAL_RECOMMENDATIONS = frozenset(
    {
        "HOLD",
        "WATCH",
        "TRAIL_SHADOW",
        "PARTIAL_PROTECT_SHADOW",
        "EXIT_PROTECT_SHADOW",
        "NO_ACTION",
    }
)

MEMORY_AVOID = frozenset({"AVOID_PROTECTION_FOR_NOW", "DO_NOT_PROMOTE_TO_ADVISORY_YET"})
MEMORY_SUPPORT = frozenset(
    {"TEST_TRAILING_SHADOW", "TEST_PARTIAL_SELL_SHADOW", "CONTINUE_OBSERVATION"}
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def load_live_signals(path: Path = LIVE_SIGNALS_CSV) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return {}
    if df.empty or "Ticker" not in df.columns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for ticker, group in df.groupby(df["Ticker"].astype(str).str.upper()):
        row = group.iloc[-1]
        rsi = pd.to_numeric(row.get("RSI"), errors="coerce")
        score = pd.to_numeric(row.get("Score"), errors="coerce")
        signal = str(row.get("Signal", "")).upper()
        out[ticker] = {
            "signal": signal,
            "rsi": float(rsi) if pd.notna(rsi) else None,
            "score": float(score) if pd.notna(score) else None,
        }
    return out


def load_position_entry_dates(path: Path = PORTFOLIO_CSV) -> dict[str, datetime]:
    """Last BUY timestamp per open ticker (read-only portfolio scan)."""
    if not path.is_file():
        return {}
    try:
        df = pd.read_csv(path)
    except OSError:
        return {}
    if df.empty:
        return {}
    df["Ticker"] = df["Ticker"].astype(str).str.upper()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    dates: dict[str, datetime] = {}
    for ticker, group in df.groupby("Ticker"):
        if ticker == "CASH":
            continue
        buys = group[group["Action"].astype(str).str.upper() == "BUY"]
        if buys.empty:
            continue
        last_buy = buys.iloc[-1]["Date"]
        if pd.notna(last_buy):
            dates[ticker] = last_buy.to_pydatetime()
    return dates


def validation_memory_by_ticker(
    validation: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not validation:
        return {}
    return {
        str(row.get("ticker", "")).upper(): row
        for row in validation.get("ticker_breakdown") or []
        if row.get("ticker")
    }


def vote_trend_defender(
    *,
    current_pct: float,
    drawdown: float,
    signal_info: dict[str, Any] | None,
) -> str:
    rsi = (signal_info or {}).get("rsi")
    signal = str((signal_info or {}).get("signal", "")).upper()
    if drawdown <= -3.0 or current_pct <= -2.0:
        return "WEAKENING_TREND"
    if signal in {"STRONG BUY", "BUY"} and rsi is not None and rsi >= 50 and current_pct >= -0.5:
        return "HOLD_TREND_HEALTHY"
    if current_pct >= 0 and drawdown > -1.5:
        return "HOLD_TREND_HEALTHY"
    if drawdown <= -1.0 or current_pct < 0:
        return "WEAKENING_TREND"
    if signal_info:
        return "HOLD_TREND_HEALTHY" if current_pct >= 0 else "WEAKENING_TREND"
    return "UNKNOWN_TREND"


def vote_profit_decay(
    *,
    current_pct: float,
    high_pct: float,
    drawdown: float,
    missed_usd: float,
    rules_v1: dict[str, Any] | None,
) -> str:
    if rules_v1 and rules_v1.get("profit_at_risk"):
        return "PROFIT_AT_RISK"
    fade = float(rules_v1.get("fade_from_peak_pct") if rules_v1 else max(high_pct - current_pct, abs(drawdown)))
    if high_pct < 2.0 and missed_usd < 10:
        return "PROFIT_STABLE"
    if fade >= 4.0 or (missed_usd >= 50 and fade >= 2.0):
        return "PROFIT_AT_RISK"
    if fade >= 1.5 or drawdown <= -1.5:
        return "PROFIT_DECAY"
    return "PROFIT_STABLE"


def vote_volatility_context(*, drawdown: float, classification: str) -> str:
    cls = classification.upper()
    if abs(drawdown) >= 5.0 or cls in {
        "SIGNIFICANT_INTRADAY_FADE",
        "POTENTIAL_PARTIAL_TAKE_PROFIT",
    }:
        return "HIGH_VOLATILITY_RISK"
    if drawdown == 0 and cls == "PORTFOLIO_ONLY":
        return "UNKNOWN_VOLATILITY"
    if abs(drawdown) < 3.0:
        return "NORMAL_VOLATILITY"
    return "HIGH_VOLATILITY_RISK"


def vote_time_intelligence(
    *,
    high_pct: float,
    current_pct: float,
    entry_date: datetime | None,
) -> str:
    if entry_date is None:
        fade = high_pct - current_pct
        if high_pct >= 4.0 and fade < 1.0:
            return "EARLY_PROFIT"
        if high_pct >= 4.0 and fade >= 1.5:
            return "MATURE_PROFIT"
        return "UNKNOWN_TIME"
    age_hours = (datetime.now() - entry_date).total_seconds() / 3600.0
    if age_hours <= 48 and high_pct >= 3.0:
        return "EARLY_PROFIT"
    if age_hours > 48 or (high_pct >= 4.0 and high_pct - current_pct >= 2.0):
        return "MATURE_PROFIT"
    return "UNKNOWN_TIME"


def vote_profit_memory(
    *,
    ticker: str,
    memory_row: dict[str, Any] | None,
    validation_verdict: str | None,
) -> str:
    if not memory_row:
        return "MEMORY_NEUTRAL"
    rec = str(memory_row.get("recommendation", "")).upper()
    win_rate = float(memory_row.get("best_strategy_win_rate") or 0)
    value = float(memory_row.get("best_strategy_value") or 0)
    if rec in MEMORY_AVOID or win_rate < 0.35:
        return "MEMORY_AVOID_PROTECTION"
    if (
        rec in MEMORY_SUPPORT
        and value > 0
        and win_rate >= 0.5
    ) or (validation_verdict == "PROMISING_BUT_NOT_READY" and value > 100):
        return "MEMORY_SUPPORTS_PROTECTION"
    return "MEMORY_NEUTRAL"


def vote_safety_guard(
    *,
    current_pct: float,
    profit_decay_vote: str,
    partial_advisories: list[str],
) -> dict[str, Any]:
    take_profit_allowed = current_pct > 0
    trail_or_partial_allowed = (
        current_pct > 0
        and profit_decay_vote in {"PROFIT_DECAY", "PROFIT_AT_RISK"}
    )
    blocked_partial = [a for a in partial_advisories if not take_profit_allowed]
    return {
        "take_profit_allowed": take_profit_allowed,
        "trail_or_partial_allowed": trail_or_partial_allowed,
        "blocked_partial_advisories": blocked_partial,
        "shadow_only_enforced": True,
    }


def synthesize_recommendation(
    *,
    votes: dict[str, str],
    safety: dict[str, Any],
    protection_signal: str,
    suggested_shadow_action: str,
    missed_usd: float,
    current_pct: float,
) -> tuple[str, str, str]:
    trend = votes["trend_defender"]
    decay = votes["profit_decay"]
    vol = votes["volatility_context"]
    memory = votes["profit_memory"]
    reentry = votes.get("reentry_cooldown") == "REENTRY_COOLDOWN"

    if reentry and decay not in {"PROFIT_AT_RISK"}:
        return (
            "WATCH",
            "LOW",
            "SHADOW_ONLY: reentry after profitable sell — observe before adding protection.",
        )

    if not safety["take_profit_allowed"]:
        if decay == "PROFIT_AT_RISK" and missed_usd >= 80:
            return (
                "WATCH",
                "MEDIUM",
                "SHADOW_ONLY: profit faded from peak but current PnL ≤ 0 — no take-profit advisory; monitor recovery.",
            )
        if trend == "WEAKENING_TREND":
            return (
                "NO_ACTION",
                "LOW",
                "SHADOW_ONLY: negative PnL with weakening trend — safety guard blocks profit-taking.",
            )
        return (
            "NO_ACTION",
            "LOW",
            "SHADOW_ONLY: safety guard — no profit protection when PnL ≤ 0.",
        )

    score = 0
    if decay == "PROFIT_AT_RISK":
        score += 3
    elif decay == "PROFIT_DECAY":
        score += 2
    if vol == "HIGH_VOLATILITY_RISK":
        score += 2
    if trend == "WEAKENING_TREND":
        score += 2
    elif trend == "HOLD_TREND_HEALTHY":
        score -= 1
    if memory == "MEMORY_SUPPORTS_PROTECTION":
        score += 1
    elif memory == "MEMORY_AVOID_PROTECTION":
        score -= 2

    trailing_signal = protection_signal == "TRAILING_PROTECTION_SHADOW" or "TRAILING" in suggested_shadow_action
    partial_signal = "PARTIAL" in protection_signal or "SELL" in suggested_shadow_action

    if score >= 6 and missed_usd >= 100:
        return (
            "EXIT_PROTECT_SHADOW",
            "MEDIUM",
            "SHADOW_ONLY: severe profit decay, high volatility, large missed opportunity — simulated exit protection.",
        )
    if score >= 4 and partial_signal and safety["trail_or_partial_allowed"]:
        return (
            "PARTIAL_PROTECT_SHADOW",
            "MEDIUM",
            "SHADOW_ONLY: profit decay with historical partial protection edge — paper partial only.",
        )
    if (score >= 3 or trailing_signal) and memory != "MEMORY_AVOID_PROTECTION":
        if trailing_signal or "TRAILING" in suggested_shadow_action:
            return (
                "TRAIL_SHADOW",
                "MEDIUM" if memory == "MEMORY_SUPPORTS_PROTECTION" else "LOW",
                "SHADOW_ONLY: trailing protection favored by fade + validation memory.",
            )
        if safety["trail_or_partial_allowed"]:
            return (
                "TRAIL_SHADOW",
                "LOW",
                "SHADOW_ONLY: elevated decay — test trailing stop in paper mode.",
            )
    if score >= 2 or decay in {"PROFIT_DECAY", "PROFIT_AT_RISK"}:
        return (
            "WATCH",
            "LOW",
            "SHADOW_ONLY: profit erosion detected — continue observation.",
        )
    if trend == "HOLD_TREND_HEALTHY" and decay == "PROFIT_STABLE":
        return (
            "HOLD",
            "MEDIUM" if current_pct > 0 else "LOW",
            "SHADOW_ONLY: trend healthy and profit stable — no protection action needed.",
        )
    return (
        "NO_ACTION",
        "LOW",
        "SHADOW_ONLY: insufficient signal consensus for protection action.",
    )


def analyze_position(
    row: dict[str, Any],
    *,
    signal_info: dict[str, Any] | None,
    memory_row: dict[str, Any] | None,
    entry_date: datetime | None,
    validation_verdict: str | None,
    obs_count: int,
) -> dict[str, Any]:
    ticker = str(row.get("ticker", "")).upper()
    current_pct = float(row.get("current_pct") or 0)
    high_pct = float(row.get("high_pct") or 0)
    drawdown = float(row.get("drawdown_from_high_pct") or 0)
    missed_usd = float(row.get("missed_opportunity_usd") or 0)
    rules_v1 = row.get("rules_v1") or {}
    partial_advisories = list(rules_v1.get("partial_take_profit_advisories") or [])

    votes = {
        "trend_defender": vote_trend_defender(
            current_pct=current_pct,
            drawdown=drawdown,
            signal_info=signal_info,
        ),
        "profit_decay": vote_profit_decay(
            current_pct=current_pct,
            high_pct=high_pct,
            drawdown=drawdown,
            missed_usd=missed_usd,
            rules_v1=rules_v1,
        ),
        "volatility_context": vote_volatility_context(
            drawdown=drawdown,
            classification=str(row.get("classification", "")),
        ),
        "time_intelligence": vote_time_intelligence(
            high_pct=high_pct,
            current_pct=current_pct,
            entry_date=entry_date,
        ),
        "profit_memory": vote_profit_memory(
            ticker=ticker,
            memory_row=memory_row,
            validation_verdict=validation_verdict,
        ),
    }
    if rules_v1.get("reentry_cooldown_required"):
        votes["reentry_cooldown"] = "REENTRY_COOLDOWN"

    safety = vote_safety_guard(
        current_pct=current_pct,
        profit_decay_vote=votes["profit_decay"],
        partial_advisories=partial_advisories,
    )
    final_rec, conf_level, explanation = synthesize_recommendation(
        votes=votes,
        safety=safety,
        protection_signal=str(row.get("protection_signal", "")),
        suggested_shadow_action=str(row.get("suggested_shadow_action", "")),
        missed_usd=missed_usd,
        current_pct=current_pct,
    )
    confidence = conf_level if conf_level else confidence_from_observations(obs_count)

    return {
        "ticker": ticker,
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown": round(drawdown, 2),
        "missed_usd": round(missed_usd, 2),
        "votes": votes,
        "safety_guard": safety,
        "final_recommendation": final_rec,
        "confidence": confidence,
        "explanation": explanation,
        "shadow_protection_signal": row.get("protection_signal"),
        "shadow_only": True,
    }


def build_global_verdict(
    positions: list[dict[str, Any]],
    *,
    shadow_loaded: bool,
    validation_loaded: bool,
    validation_verdict: str | None,
) -> str:
    if not shadow_loaded or not positions:
        return "NOT_READY"
    unknown_votes = sum(
        1
        for p in positions
        for v in (p.get("votes") or {}).values()
        if str(v).startswith("UNKNOWN")
    )
    actionable = sum(
        1
        for p in positions
        if p.get("final_recommendation") not in {"NO_ACTION", "HOLD"}
    )
    if unknown_votes > len(positions) * 3:
        return "SHADOW_ONLY_NEEDS_MORE_DATA"
    if shadow_loaded and validation_loaded and validation_verdict == "PROMISING_BUT_NOT_READY":
        return "SHADOW_ONLY_READY_FOR_OBSERVATION"
    if actionable > 0 or len(positions) >= 3:
        return "SHADOW_ONLY_READY_FOR_OBSERVATION"
    return "SHADOW_ONLY_NEEDS_MORE_DATA"


def build_brain_report(
    *,
    shadow_path: Path = SHADOW_JSON,
    validation_path: Path = VALIDATION_JSON,
    signals_path: Path = LIVE_SIGNALS_CSV,
    portfolio_path: Path = PORTFOLIO_CSV,
) -> dict[str, Any]:
    shadow, shadow_loaded = load_json(shadow_path)
    validation, validation_loaded = load_json(validation_path)
    signals = load_live_signals(signals_path)
    entry_dates = load_position_entry_dates(portfolio_path)
    memory_map = validation_memory_by_ticker(validation)
    validation_verdict = (validation or {}).get("verdict")

    obs_counts: dict[str, int] = {}
    for row in (validation or {}).get("ticker_breakdown") or []:
        ticker = str(row.get("ticker", "")).upper()
        obs_counts[ticker] = int(row.get("observations") or 0)

    positions: list[dict[str, Any]] = []
    for row in (shadow or {}).get("positions") or []:
        ticker = str(row.get("ticker", "")).upper()
        positions.append(
            analyze_position(
                row,
                signal_info=signals.get(ticker),
                memory_row=memory_map.get(ticker),
                entry_date=entry_dates.get(ticker),
                validation_verdict=validation_verdict,
                obs_count=obs_counts.get(ticker, 0),
            )
        )

    positions.sort(key=lambda p: p.get("missed_usd", 0), reverse=True)

    rec_counts = {k: 0 for k in FINAL_RECOMMENDATIONS}
    for p in positions:
        rec = p.get("final_recommendation", "NO_ACTION")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

    profit_at_risk = [
        p for p in positions if (p.get("votes") or {}).get("profit_decay") == "PROFIT_AT_RISK"
    ]
    top5_at_risk = [
        {
            "ticker": p["ticker"],
            "missed_usd": p["missed_usd"],
            "current_pct": p["current_pct"],
            "high_pct": p["high_pct"],
            "final_recommendation": p["final_recommendation"],
        }
        for p in profit_at_risk[:5]
    ]

    total_missed = round(sum(p.get("missed_usd", 0) for p in positions), 2)
    final_verdict = build_global_verdict(
        positions,
        shadow_loaded=shadow_loaded,
        validation_loaded=validation_loaded,
        validation_verdict=validation_verdict,
    )

    return {
        "schema": "tae_profit_intelligence_brain",
        "version": "v1",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": {
            str(shadow_path): shadow_loaded,
            str(validation_path): validation_loaded,
            str(signals_path): signals_path.is_file(),
            str(portfolio_path): portfolio_path.is_file(),
            str(BOT_OUTPUT_LOG): BOT_OUTPUT_LOG.is_file(),
        },
        "validation_verdict": validation_verdict,
        "validation_mode": "SHADOW_ONLY"
        if validation_verdict == "PROMISING_BUT_NOT_READY"
        else "OBSERVE",
        "positions": positions,
        "global_summary": {
            "total_positions": len(positions),
            "recommendation_counts": rec_counts,
            "total_missed_usd": total_missed,
            "top_5_profit_at_risk": top5_at_risk,
            "final_verdict": final_verdict,
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    counts = summary["recommendation_counts"]
    lines = [
        "# TAE Profit Intelligence Brain v1",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Global summary",
        f"- Total positions: **{summary['total_positions']}**",
        f"- HOLD: **{counts.get('HOLD', 0)}** | WATCH: **{counts.get('WATCH', 0)}** | "
        f"TRAIL_SHADOW: **{counts.get('TRAIL_SHADOW', 0)}** | "
        f"PARTIAL: **{counts.get('PARTIAL_PROTECT_SHADOW', 0)}** | "
        f"EXIT: **{counts.get('EXIT_PROTECT_SHADOW', 0)}** | "
        f"NO_ACTION: **{counts.get('NO_ACTION', 0)}**",
        f"- Total missed USD: **{summary['total_missed_usd']}**",
        "",
        "## Top 5 profit-at-risk",
        "",
        "| ticker | missed_usd | current_pct | high_pct | recommendation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in summary.get("top_5_profit_at_risk") or []:
        lines.append(
            f"| {row['ticker']} | {row['missed_usd']} | {row['current_pct']} | "
            f"{row['high_pct']} | {row['final_recommendation']} |"
        )

    lines.extend(
        [
            "",
            "## Positions",
            "",
            "| ticker | current% | high% | drawdown | missed | recommendation | confidence | trend | decay | vol | time | memory |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for p in report.get("positions") or []:
        v = p.get("votes") or {}
        lines.append(
            f"| {p['ticker']} | {p['current_pct']} | {p['high_pct']} | {p['drawdown']} | "
            f"{p['missed_usd']} | {p['final_recommendation']} | {p['confidence']} | "
            f"{v.get('trend_defender', '—')} | {v.get('profit_decay', '—')} | "
            f"{v.get('volatility_context', '—')} | {v.get('time_intelligence', '—')} | "
            f"{v.get('profit_memory', '—')} |"
        )

    lines.extend(["", "## Explanations", ""])
    for p in report.get("positions") or []:
        lines.append(f"### {p['ticker']} — {p['final_recommendation']}")
        lines.append(p.get("explanation", ""))
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["global_summary"]
    counts = summary["recommendation_counts"]
    print("===== TAE PROFIT INTELLIGENCE BRAIN v1 =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", summary["final_verdict"])
    print("Positions:", summary["total_positions"])
    print(
        "HOLD / WATCH / TRAIL / PARTIAL / EXIT / NO_ACTION:",
        counts.get("HOLD", 0),
        counts.get("WATCH", 0),
        counts.get("TRAIL_SHADOW", 0),
        counts.get("PARTIAL_PROTECT_SHADOW", 0),
        counts.get("EXIT_PROTECT_SHADOW", 0),
        counts.get("NO_ACTION", 0),
    )
    print("Total missed USD:", summary["total_missed_usd"])


def main() -> int:
    report = build_brain_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
