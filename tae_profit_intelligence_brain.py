#!/usr/bin/env python3
"""
TAE Profit Intelligence Brain v2 — SHADOW_ONLY / NO_BROKER.

Multi-factor shadow recommendation engine with Profit Survival Probability (PSP).
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

PSP_URGENCY_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
REC_RANK = {
    "NO_ACTION": 0,
    "HOLD": 1,
    "WATCH": 2,
    "TRAIL_SHADOW": 3,
    "PARTIAL_PROTECT_SHADOW": 4,
    "EXIT_PROTECT_SHADOW": 5,
}
SMALL_PROFIT_PCT = 2.0
SEVERE_DRAWDOWN_PCT = 5.0
HIGH_PEAK_PCT = 6.0


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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_psp(
    *,
    current_pct: float,
    high_pct: float,
    drawdown: float,
    missed_usd: float,
    votes: dict[str, str],
) -> dict[str, Any]:
    """
    Shadow-only Profit Survival Probability model.
    Returns survival prob, giveback risk prob, and protection urgency.
    """
    fade_from_peak = max(high_pct - current_pct, abs(drawdown))

    if current_pct <= 0:
        giveback = 1.0 if high_pct > 0 else 0.0
        urgency = "CRITICAL" if high_pct >= HIGH_PEAK_PCT and fade_from_peak >= SEVERE_DRAWDOWN_PCT else "HIGH"
        if high_pct < 2.0:
            urgency = "MEDIUM"
        return {
            "psp_survival_probability": 0.0,
            "psp_giveback_risk": round(giveback, 3),
            "psp_protection_urgency": urgency,
        }

    retention = current_pct / high_pct if high_pct > 0 else 1.0
    survival = 0.30 + 0.50 * _clamp(retention)

    trend = votes.get("trend_defender", "")
    decay = votes.get("profit_decay", "")
    vol = votes.get("volatility_context", "")
    memory = votes.get("profit_memory", "")

    if trend == "HOLD_TREND_HEALTHY":
        survival += 0.12
    elif trend == "WEAKENING_TREND":
        survival -= 0.15

    if decay == "PROFIT_STABLE":
        survival += 0.10
    elif decay == "PROFIT_DECAY":
        survival -= 0.12
    elif decay == "PROFIT_AT_RISK":
        survival -= 0.22

    if vol == "NORMAL_VOLATILITY" and drawdown > -1.5:
        survival += 0.06
    elif vol == "HIGH_VOLATILITY_RISK":
        survival -= 0.10

    if current_pct < SMALL_PROFIT_PCT:
        survival -= 0.05

    survival = round(_clamp(survival), 3)

    if retention <= 0.5:
        giveback = 0.85
    else:
        giveback = 0.25 + 0.55 * (fade_from_peak / max(high_pct, 0.01))
        if decay == "PROFIT_AT_RISK":
            giveback += 0.15
        if vol == "HIGH_VOLATILITY_RISK":
            giveback += 0.10
        if high_pct >= HIGH_PEAK_PCT and fade_from_peak >= SEVERE_DRAWDOWN_PCT:
            giveback += 0.20
        giveback = _clamp(giveback)

    if memory == "MEMORY_SUPPORTS_PROTECTION" and decay in {"PROFIT_DECAY", "PROFIT_AT_RISK"}:
        giveback = _clamp(giveback + 0.05)
        survival = round(_clamp(survival - 0.05), 3)

    giveback = round(giveback, 3)

    if high_pct >= HIGH_PEAK_PCT and fade_from_peak >= SEVERE_DRAWDOWN_PCT + 2:
        urgency = "CRITICAL"
    elif giveback >= 0.75 or (survival <= 0.25 and decay == "PROFIT_AT_RISK"):
        urgency = "CRITICAL"
    elif giveback >= 0.55 or survival <= 0.40:
        urgency = "HIGH"
    elif giveback >= 0.35 or survival <= 0.60:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    if memory == "MEMORY_SUPPORTS_PROTECTION" and decay in {"PROFIT_DECAY", "PROFIT_AT_RISK"}:
        idx = PSP_URGENCY_LEVELS.index(urgency)
        urgency = PSP_URGENCY_LEVELS[min(idx + 1, len(PSP_URGENCY_LEVELS) - 1)]

    return {
        "psp_survival_probability": survival,
        "psp_giveback_risk": giveback,
        "psp_protection_urgency": urgency,
    }


def adjust_recommendation_with_psp(
    *,
    pib_recommendation: str,
    current_pct: float,
    psp: dict[str, Any],
    votes: dict[str, str],
) -> tuple[str, str]:
    """
    Adjust v1 PIB recommendation using PSP metrics (shadow-only).
    Returns (adjusted_recommendation, explanation_suffix).
    """
    survival = float(psp["psp_survival_probability"])
    giveback = float(psp["psp_giveback_risk"])
    urgency = str(psp["psp_protection_urgency"])
    decay = votes.get("profit_decay", "")

    adjusted = pib_recommendation
    notes: list[str] = []

    if current_pct <= 0:
        if pib_recommendation in {"EXIT_PROTECT_SHADOW", "PARTIAL_PROTECT_SHADOW", "TRAIL_SHADOW"}:
            adjusted = "WATCH"
            notes.append("PSP: PnL ≤ 0 — downgraded to WATCH (no take-profit).")
        elif pib_recommendation == "HOLD" and urgency in {"HIGH", "CRITICAL"}:
            adjusted = "WATCH"
            notes.append("PSP: profit already faded — observe recovery.")
        else:
            notes.append("PSP: survival=0 with non-positive PnL.")
        return adjusted, " ".join(notes)

    rank = REC_RANK.get(adjusted, 0)

    if current_pct > 0 and current_pct < SMALL_PROFIT_PCT:
        if adjusted == "EXIT_PROTECT_SHADOW":
            adjusted = "WATCH"
            notes.append("PSP: small positive profit — WATCH instead of EXIT.")
        elif urgency == "CRITICAL" and adjusted in {"HOLD", "NO_ACTION"}:
            adjusted = "WATCH"
            notes.append("PSP: small profit but elevated giveback risk — WATCH.")
        rank = REC_RANK.get(adjusted, rank)

    if urgency == "CRITICAL" and current_pct >= SMALL_PROFIT_PCT:
        target = "EXIT_PROTECT_SHADOW" if giveback >= 0.70 and decay == "PROFIT_AT_RISK" else "PARTIAL_PROTECT_SHADOW"
        if REC_RANK[target] > rank:
            adjusted = target
            notes.append(f"PSP: CRITICAL urgency (giveback={giveback:.2f}) — escalated to {target}.")
    elif urgency == "HIGH":
        target = "PARTIAL_PROTECT_SHADOW" if decay == "PROFIT_AT_RISK" else "TRAIL_SHADOW"
        if REC_RANK[target] > rank and current_pct >= 1.0:
            adjusted = target
            notes.append(f"PSP: HIGH urgency — escalated to {target}.")
        elif adjusted in {"HOLD", "NO_ACTION"} and decay in {"PROFIT_DECAY", "PROFIT_AT_RISK"}:
            adjusted = "WATCH"
            notes.append("PSP: HIGH giveback risk — WATCH.")
    elif urgency == "MEDIUM" and adjusted in {"HOLD", "NO_ACTION"} and decay != "PROFIT_STABLE":
        adjusted = "WATCH"
        notes.append("PSP: MEDIUM urgency with decay — WATCH.")

    if survival >= 0.70 and urgency == "LOW" and adjusted in {"EXIT_PROTECT_SHADOW", "PARTIAL_PROTECT_SHADOW"}:
        adjusted = "TRAIL_SHADOW" if decay == "PROFIT_DECAY" else "WATCH"
        notes.append(f"PSP: strong survival ({survival:.2f}) — de-escalated protection.")

    if not notes:
        notes.append(
            f"PSP: survival={survival:.2f}, giveback={giveback:.2f}, urgency={urgency} — "
            f"confirms {pib_recommendation}."
        )

    return adjusted, " ".join(notes)


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

    psp = compute_psp(
        current_pct=current_pct,
        high_pct=high_pct,
        drawdown=drawdown,
        missed_usd=missed_usd,
        votes=votes,
    )
    psp_adjusted, psp_note = adjust_recommendation_with_psp(
        pib_recommendation=final_rec,
        current_pct=current_pct,
        psp=psp,
        votes=votes,
    )
    full_explanation = f"{explanation} {psp_note}"

    return {
        "ticker": ticker,
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown": round(drawdown, 2),
        "missed_usd": round(missed_usd, 2),
        "votes": votes,
        "safety_guard": safety,
        "final_recommendation": final_rec,
        "existing_pib_recommendation": final_rec,
        "confidence": confidence,
        "explanation": full_explanation,
        "psp_survival_probability": psp["psp_survival_probability"],
        "psp_giveback_risk": psp["psp_giveback_risk"],
        "psp_protection_urgency": psp["psp_protection_urgency"],
        "psp_adjusted_recommendation": psp_adjusted,
        "shadow_protection_signal": row.get("protection_signal"),
        "shadow_only": True,
    }


def build_global_verdict(
    positions: list[dict[str, Any]],
    *,
    shadow_loaded: bool,
    validation_loaded: bool,
) -> str:
    if not shadow_loaded or not positions:
        return "PSP_NOT_READY"
    unknown_votes = sum(
        1
        for p in positions
        for v in (p.get("votes") or {}).values()
        if str(v).startswith("UNKNOWN")
    )
    urgent = sum(
        1
        for p in positions
        if p.get("psp_protection_urgency") in {"HIGH", "CRITICAL"}
    )
    if unknown_votes > len(positions) * 3:
        return "PSP_SHADOW_NEEDS_MORE_DATA"
    if shadow_loaded and validation_loaded and (urgent > 0 or len(positions) >= 3):
        return "PSP_SHADOW_READY_FOR_OBSERVATION"
    if len(positions) >= 1:
        return "PSP_SHADOW_READY_FOR_OBSERVATION"
    return "PSP_SHADOW_NEEDS_MORE_DATA"


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
    psp_rec_counts = {k: 0 for k in FINAL_RECOMMENDATIONS}
    for p in positions:
        rec = p.get("final_recommendation", "NO_ACTION")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1
        psp_rec = p.get("psp_adjusted_recommendation", rec)
        psp_rec_counts[psp_rec] = psp_rec_counts.get(psp_rec, 0) + 1

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
            "psp_adjusted_recommendation": p.get("psp_adjusted_recommendation"),
        }
        for p in profit_at_risk[:5]
    ]

    by_giveback = sorted(positions, key=lambda p: p.get("psp_giveback_risk", 0), reverse=True)
    top5_giveback = [
        {
            "ticker": p["ticker"],
            "psp_giveback_risk": p.get("psp_giveback_risk"),
            "psp_survival_probability": p.get("psp_survival_probability"),
            "psp_protection_urgency": p.get("psp_protection_urgency"),
            "current_pct": p["current_pct"],
            "high_pct": p["high_pct"],
            "psp_adjusted_recommendation": p.get("psp_adjusted_recommendation"),
        }
        for p in by_giveback[:5]
    ]

    survivals = [p.get("psp_survival_probability", 0) for p in positions]
    givebacks = [p.get("psp_giveback_risk", 0) for p in positions]
    urgent_count = sum(
        1 for p in positions if p.get("psp_protection_urgency") in {"HIGH", "CRITICAL"}
    )

    total_missed = round(sum(p.get("missed_usd", 0) for p in positions), 2)
    final_verdict = build_global_verdict(
        positions,
        shadow_loaded=shadow_loaded,
        validation_loaded=validation_loaded,
    )

    return {
        "schema": "tae_profit_intelligence_brain",
        "version": "v2",
        "psp_enabled": True,
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
            "psp_adjusted_recommendation_counts": psp_rec_counts,
            "total_missed_usd": total_missed,
            "average_survival_probability": round(sum(survivals) / len(survivals), 3)
            if survivals
            else 0.0,
            "average_giveback_risk": round(sum(givebacks) / len(givebacks), 3)
            if givebacks
            else 0.0,
            "urgent_positions": urgent_count,
            "top_5_profit_at_risk": top5_at_risk,
            "top_5_highest_giveback_risk": top5_giveback,
            "final_verdict": final_verdict,
        },
        "psp_config": {
            "small_profit_pct": SMALL_PROFIT_PCT,
            "high_peak_pct": HIGH_PEAK_PCT,
            "severe_drawdown_pct": SEVERE_DRAWDOWN_PCT,
            "urgency_levels": list(PSP_URGENCY_LEVELS),
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    counts = summary["recommendation_counts"]
    psp_counts = summary.get("psp_adjusted_recommendation_counts") or {}
    lines = [
        "# TAE Profit Intelligence Brain v2 (PSP)",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Global summary",
        f"- Total positions: **{summary['total_positions']}**",
        f"- Avg survival probability: **{summary.get('average_survival_probability', 0)}**",
        f"- Avg giveback risk: **{summary.get('average_giveback_risk', 0)}**",
        f"- Urgent positions (HIGH/CRITICAL): **{summary.get('urgent_positions', 0)}**",
        f"- Total missed USD: **{summary['total_missed_usd']}**",
        "",
        "### PIB v1 recommendations",
        f"- HOLD: **{counts.get('HOLD', 0)}** | WATCH: **{counts.get('WATCH', 0)}** | "
        f"TRAIL: **{counts.get('TRAIL_SHADOW', 0)}** | "
        f"PARTIAL: **{counts.get('PARTIAL_PROTECT_SHADOW', 0)}** | "
        f"EXIT: **{counts.get('EXIT_PROTECT_SHADOW', 0)}** | "
        f"NO_ACTION: **{counts.get('NO_ACTION', 0)}**",
        "",
        "### PSP-adjusted recommendations",
        f"- HOLD: **{psp_counts.get('HOLD', 0)}** | WATCH: **{psp_counts.get('WATCH', 0)}** | "
        f"TRAIL: **{psp_counts.get('TRAIL_SHADOW', 0)}** | "
        f"PARTIAL: **{psp_counts.get('PARTIAL_PROTECT_SHADOW', 0)}** | "
        f"EXIT: **{psp_counts.get('EXIT_PROTECT_SHADOW', 0)}** | "
        f"NO_ACTION: **{psp_counts.get('NO_ACTION', 0)}**",
        "",
        "## Top 5 highest giveback risk",
        "",
        "| ticker | giveback | survival | urgency | current% | high% | psp_rec |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary.get("top_5_highest_giveback_risk") or []:
        lines.append(
            f"| {row['ticker']} | {row['psp_giveback_risk']} | {row['psp_survival_probability']} | "
            f"{row['psp_protection_urgency']} | {row['current_pct']} | {row['high_pct']} | "
            f"{row['psp_adjusted_recommendation']} |"
        )

    lines.extend(
        [
            "",
            "## Top 5 profit-at-risk",
            "",
            "| ticker | missed_usd | current_pct | high_pct | pib_rec | psp_rec |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("top_5_profit_at_risk") or []:
        lines.append(
            f"| {row['ticker']} | {row['missed_usd']} | {row['current_pct']} | "
            f"{row['high_pct']} | {row['final_recommendation']} | "
            f"{row.get('psp_adjusted_recommendation', '—')} |"
        )

    lines.extend(
        [
            "",
            "## Positions",
            "",
            "| ticker | current% | high% | drawdown | missed | survival | giveback | urgency | pib_rec | psp_rec |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for p in report.get("positions") or []:
        lines.append(
            f"| {p['ticker']} | {p['current_pct']} | {p['high_pct']} | {p['drawdown']} | "
            f"{p['missed_usd']} | {p.get('psp_survival_probability')} | {p.get('psp_giveback_risk')} | "
            f"{p.get('psp_protection_urgency')} | {p.get('existing_pib_recommendation')} | "
            f"{p.get('psp_adjusted_recommendation')} |"
        )

    lines.extend(["", "## Explanations", ""])
    for p in report.get("positions") or []:
        lines.append(
            f"### {p['ticker']} — {p.get('psp_adjusted_recommendation')} "
            f"(PIB: {p.get('existing_pib_recommendation')})"
        )
        lines.append(p.get("explanation", ""))
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["global_summary"]
    psp_counts = summary.get("psp_adjusted_recommendation_counts") or {}
    print("===== TAE PROFIT INTELLIGENCE BRAIN v2 (PSP) =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", summary["final_verdict"])
    print("Positions:", summary["total_positions"])
    print("Avg survival:", summary.get("average_survival_probability"))
    print("Avg giveback risk:", summary.get("average_giveback_risk"))
    print("Urgent positions:", summary.get("urgent_positions"))
    print(
        "PSP-adjusted HOLD / WATCH / TRAIL / PARTIAL / EXIT / NO_ACTION:",
        psp_counts.get("HOLD", 0),
        psp_counts.get("WATCH", 0),
        psp_counts.get("TRAIL_SHADOW", 0),
        psp_counts.get("PARTIAL_PROTECT_SHADOW", 0),
        psp_counts.get("EXIT_PROTECT_SHADOW", 0),
        psp_counts.get("NO_ACTION", 0),
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
