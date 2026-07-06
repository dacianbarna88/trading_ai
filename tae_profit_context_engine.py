#!/usr/bin/env python3
"""
TAE Profit Context Engine v2 — SHADOW_ONLY / NO_BROKER.

Adaptive weighted context model distinguishing pullback vs profit decay.
Does NOT modify live_bot, portfolio, broker, or execution.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

COMMITTEE_JSON = Path("tae_profit_decision_committee.json")
COMMITTEE_LEARNING_JSON = Path("tae_profit_committee_learning.json")
BRAIN_JSON = Path("tae_profit_intelligence_brain.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
LIVE_SIGNALS_CSV = Path("live_signals.csv")
REGIME_SUMMARY = Path("runtime_outputs/regime_intelligence_summary.txt")
CROSS_MARKET_SUMMARY = Path("runtime_outputs/cross_market_regime_summary.txt")
SECTOR_SUMMARY = Path("runtime_outputs/sector_intelligence_summary.txt")

OUTPUT_JSON = Path("tae_profit_context_engine.json")
OUTPUT_MD = Path("tae_profit_context_engine.md")
LEARNING_JSON = Path("tae_profit_context_learning.json")
LEARNING_MD = Path("tae_profit_context_learning.md")

COMPONENT_KEYS = (
    "market_context",
    "sector_context",
    "trend_context",
    "momentum_context",
    "volatility_context",
    "psp_context",
    "memory_context",
    "committee_context",
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "market_context": 0.15,
    "sector_context": 0.15,
    "trend_context": 0.15,
    "momentum_context": 0.15,
    "volatility_context": 0.10,
    "psp_context": 0.15,
    "memory_context": 0.10,
    "committee_context": 0.05,
}

WEIGHT_MIN = 0.03
WEIGHT_MAX = 0.30

VERDICTS = frozenset(
    {
        "KEEP_WINNER",
        "NORMAL_PULLBACK",
        "CONTEXT_WEAKENING",
        "PROTECT_NOW",
        "UNKNOWN_CONTEXT",
    }
)

COMPONENT_SUBSCORES: dict[str, dict[str, float]] = {
    "market_context": {
        "MARKET_SUPPORTIVE": 72.0,
        "MARKET_NEUTRAL": 50.0,
        "MARKET_HEADWIND": 32.0,
    },
    "sector_context": {
        "SECTOR_LEADING": 76.0,
        "SECTOR_NEUTRAL": 54.0,
        "SECTOR_LAGGING": 34.0,
        "UNKNOWN_SECTOR": 46.0,
    },
    "trend_context": {
        "TREND_HEALTHY": 82.0,
        "TREND_NEUTRAL": 50.0,
        "TREND_WEAK": 26.0,
        "UNKNOWN_TREND": 46.0,
    },
    "momentum_context": {
        "MOMENTUM_STRONG": 78.0,
        "MOMENTUM_NEUTRAL": 52.0,
        "MOMENTUM_WEAK": 28.0,
        "UNKNOWN_MOMENTUM": 46.0,
    },
    "volatility_context": {
        "VOLATILITY_NORMAL": 74.0,
        "VOLATILITY_MODERATE": 56.0,
        "VOLATILITY_ELEVATED": 38.0,
        "VOLATILITY_HIGH": 24.0,
    },
    "psp_context": {
        "PSP_STRONG": 80.0,
        "PSP_NEUTRAL": 52.0,
        "PSP_AT_RISK": 36.0,
        "PSP_UNKNOWN": 46.0,
    },
    "memory_context": {
        "MEMORY_SURVIVED": 82.0,
        "MEMORY_NEUTRAL": 50.0,
        "MEMORY_PROTECT": 42.0,
        "MEMORY_DECAYED": 34.0,
        "MEMORY_COLLAPSED": 28.0,
    },
    "committee_context": {
        "COMMITTEE_HOLD": 74.0,
        "COMMITTEE_NEUTRAL": 50.0,
        "COMMITTEE_WATCH": 44.0,
        "COMMITTEE_PROTECT": 30.0,
    },
}


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_live_signals(path: Path = LIVE_SIGNALS_CSV) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ticker = str(row.get("Ticker", "")).upper()
                if not ticker:
                    continue
                rsi = _f(row.get("RSI"), default=-1.0)
                score = _f(row.get("Score"), default=-1.0)
                price = _f(row.get("Price"), default=-1.0)
                sma50 = _f(row.get("SMA50"), default=-1.0)
                out[ticker] = {
                    "signal": str(row.get("Signal", "")).upper(),
                    "rsi": rsi if rsi >= 0 else None,
                    "score": score if score >= 0 else None,
                    "price": price if price >= 0 else None,
                    "sma50": sma50 if sma50 >= 0 else None,
                }
    except OSError:
        return {}
    return out


def parse_market_regime(text: str) -> dict[str, Any]:
    regime = "UNKNOWN"
    profile = "UNKNOWN"
    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        if line.startswith("Current Market Regime:"):
            inline = line.split(":", 1)[1].strip()
            regime = inline.upper() if inline else (lines[i + 1].upper() if i + 1 < len(lines) else "UNKNOWN")
        if line.startswith("Regime Profile:"):
            inline = line.split(":", 1)[1].strip()
            profile = inline.upper() if inline else (lines[i + 1].upper() if i + 1 < len(lines) else "UNKNOWN")
    return {"regime": regime, "profile": profile}


def parse_cross_market(text: str) -> dict[str, Any]:
    clean = text.replace("\\n", "\n")
    global_state = "UNKNOWN"
    regions: dict[str, str] = {}
    for line in clean.splitlines():
        if line.startswith("Global State:"):
            global_state = line.split(":", 1)[1].strip().upper()
        match = re.match(r"^(US|UK|EU):\s*(\w+)", line.strip())
        if match:
            regions[match.group(1)] = match.group(2).upper()
    return {"global_state": global_state, "regions": regions}


def parse_sector_leader(text: str) -> dict[str, Any]:
    leader = "UNKNOWN"
    score = 0.0
    for line in text.splitlines():
        if line.startswith("Sector Leader:"):
            leader = line.split(":", 1)[1].strip().upper()
        if line.startswith("Sector Score:"):
            score = _f(line.split(":", 1)[1].strip())
    return {"leader": leader, "score": score}


def regional_hint(ticker: str) -> str:
    if ticker.endswith(".L"):
        return "UK"
    if ticker.endswith((".DE", ".PA")):
        return "EU"
    return "US"


def trend_context(signal_row: dict[str, Any] | None) -> str:
    if not signal_row:
        return "UNKNOWN_TREND"
    signal = str(signal_row.get("signal", "")).upper()
    rsi = signal_row.get("rsi")
    price = signal_row.get("price")
    sma50 = signal_row.get("sma50")
    if signal in {"STRONG BUY", "BUY"} and rsi is not None and rsi >= 50:
        return "TREND_HEALTHY"
    if price is not None and sma50 is not None and price >= sma50:
        return "TREND_HEALTHY"
    if signal in {"WAIT", "TAKE PROFIT"}:
        return "TREND_WEAK"
    return "TREND_NEUTRAL"


def market_context_for_ticker(ticker: str, regime: dict[str, Any], cross: dict[str, Any]) -> str:
    region = regional_hint(ticker)
    region_state = (cross.get("regions") or {}).get(region, "UNKNOWN")
    base = str(regime.get("regime", "UNKNOWN"))
    if base == "BULL" and region_state in {"STRONG", "NEUTRAL", "UNKNOWN"}:
        return "MARKET_SUPPORTIVE"
    if str(cross.get("global_state", "")).endswith("RISK_OFF") or region_state == "WEAK":
        return "MARKET_HEADWIND"
    if base in {"BEAR", "RISK_OFF"}:
        return "MARKET_HEADWIND"
    return "MARKET_NEUTRAL"


def sector_context(sector_info: dict[str, Any]) -> str:
    if sector_info.get("leader") == "UNKNOWN":
        return "UNKNOWN_SECTOR"
    if _f(sector_info.get("score")) >= 10:
        return "SECTOR_LEADING"
    if _f(sector_info.get("score")) >= 3:
        return "SECTOR_NEUTRAL"
    return "SECTOR_LAGGING"


def momentum_context(signal_row: dict[str, Any] | None) -> str:
    if not signal_row:
        return "UNKNOWN_MOMENTUM"
    rsi = signal_row.get("rsi")
    score = signal_row.get("score")
    if rsi is not None and rsi >= 55 and (score is None or score >= 60):
        return "MOMENTUM_STRONG"
    if rsi is not None and rsi < 45:
        return "MOMENTUM_WEAK"
    return "MOMENTUM_NEUTRAL"


def volatility_context(drawdown: float) -> str:
    dd = abs(drawdown)
    if dd >= 5:
        return "VOLATILITY_HIGH"
    if dd >= 2:
        return "VOLATILITY_ELEVATED"
    if dd < 1:
        return "VOLATILITY_NORMAL"
    return "VOLATILITY_MODERATE"


def memory_context(memory_row: dict[str, Any] | None, episode: dict[str, Any] | None) -> str:
    label = str((episode or {}).get("memory_label") or "")
    bias = str((memory_row or {}).get("recommended_memory_bias") or "MEMORY_NEUTRAL")
    if label == "PROFIT_SURVIVED" or bias == "MEMORY_HOLD_WINNERS":
        return "MEMORY_SURVIVED"
    if label == "PROFIT_COLLAPSED":
        return "MEMORY_COLLAPSED"
    if label == "PROFIT_DECAYED":
        return "MEMORY_DECAYED"
    if bias == "MEMORY_PROTECT_EARLY":
        return "MEMORY_PROTECT"
    return "MEMORY_NEUTRAL"


def psp_context(brain_row: dict[str, Any] | None) -> str:
    if not brain_row:
        return "PSP_UNKNOWN"
    survival = _f(brain_row.get("psp_survival_probability"))
    giveback = _f(brain_row.get("psp_giveback_risk"))
    urgency = str(brain_row.get("psp_protection_urgency", "")).upper()
    if survival >= 0.70 and giveback < 0.40:
        return "PSP_STRONG"
    if urgency in {"CRITICAL", "HIGH"} or giveback >= 0.70:
        return "PSP_AT_RISK"
    return "PSP_NEUTRAL"


def committee_context(pdc_rec: str, pdc_score: float) -> str:
    if pdc_rec in {"HOLD", "NO_ACTION"} and pdc_score <= 40:
        return "COMMITTEE_HOLD"
    if pdc_rec in {"EXIT_PROTECT_SHADOW", "PARTIAL_PROTECT_SHADOW"} or pdc_score >= 80:
        return "COMMITTEE_PROTECT"
    if pdc_rec in {"WATCH", "OBSERVE", "TRAIL_PROTECT_SHADOW"}:
        return "COMMITTEE_WATCH"
    return "COMMITTEE_NEUTRAL"


def component_subscore(component: str, label: str) -> float:
    table = COMPONENT_SUBSCORES.get(component, {})
    if label in table:
        return table[label]
    if str(label).startswith("UNKNOWN"):
        return 46.0
    return 50.0


def normalize_weights(
    weights: dict[str, float],
    *,
    min_w: float = WEIGHT_MIN,
    max_w: float = WEIGHT_MAX,
) -> dict[str, float]:
    clamped = {k: max(min_w, min(max_w, float(weights.get(k, 0)))) for k in COMPONENT_KEYS}
    total = sum(clamped.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    normalized = {k: round(clamped[k] / total, 4) for k in COMPONENT_KEYS}
    return normalized


def build_adaptive_weights(
    committee_learning: dict[str, Any] | None,
    prior_learning: dict[str, Any] | None,
) -> tuple[dict[str, float], list[str]]:
    """Conservative weight adjustment from committee learning signals."""
    weights = dict(DEFAULT_WEIGHTS)
    notes: list[str] = ["Initialized from PCE v2 default weights."]

    if prior_learning and prior_learning.get("component_weights"):
        weights = dict(prior_learning["component_weights"])
        notes.append("Loaded prior context weights from tae_profit_context_learning.json.")

    members = (committee_learning or {}).get("members") or {}
    memory_acc = _f(members.get("Memory", {}).get("accuracy"))
    validation_acc = _f(members.get("Validation", {}).get("accuracy"))
    psp_acc = _f(members.get("PSP", {}).get("accuracy"))

    if committee_learning:
        notes.append("Applied conservative adjustments from tae_profit_committee_learning.json.")
        if memory_acc >= 0.85:
            weights["memory_context"] += 0.02
            notes.append(f"Memory accuracy {memory_acc:.1%} → memory_context +0.02.")
        elif memory_acc >= 0.70:
            weights["memory_context"] += 0.01
            notes.append(f"Memory accuracy {memory_acc:.1%} → memory_context +0.01.")

        if validation_acc < 0.40:
            weights["committee_context"] -= 0.02
            notes.append(f"Validation accuracy {validation_acc:.1%} → committee_context -0.02.")

        if psp_acc < 0.45:
            weights["psp_context"] -= 0.01
            weights["trend_context"] += 0.005
            weights["sector_context"] += 0.005
            notes.append(f"PSP accuracy {psp_acc:.1%} → slight shift from PSP to trend/sector.")

    normalized = normalize_weights(weights)
    notes.append(f"Normalized to sum={round(sum(normalized.values()), 4)} with min={WEIGHT_MIN}, max={WEIGHT_MAX}.")
    return normalized, notes


def compute_weighted_context_score(
    *,
    factors: dict[str, str],
    weights: dict[str, float],
    current_pct: float,
    high_pct: float,
    drawdown: float,
    giveback: float,
    survival: float,
) -> tuple[float, list[dict[str, Any]], dict[str, float]]:
    subscores: dict[str, float] = {
        component: component_subscore(component, factors.get(component, ""))
        for component in COMPONENT_KEYS
    }

    contributions: list[dict[str, Any]] = []
    weighted_sum = 0.0
    for component in COMPONENT_KEYS:
        w = weights[component]
        sub = subscores[component]
        contrib = round(w * sub, 2)
        weighted_sum += contrib
        contributions.append(
            {
                "component": component,
                "label": factors.get(component),
                "weight": w,
                "subscore": sub,
                "contribution": contrib,
                "expression": f"{w} × {sub} = {contrib}",
            }
        )

    structure_keys = ("trend_context", "sector_context", "momentum_context")
    strong_structure = sum(1 for k in structure_keys if subscores[k] >= 70.0)
    structural_bonus = 0.0
    if strong_structure >= 2:
        structural_bonus = min(12.0, strong_structure * 4.0)
        weighted_sum += structural_bonus

    if current_pct > 0 and drawdown > -1.5:
        weighted_sum += 3.0
    if current_pct > 0 and survival >= 0.70:
        weighted_sum += 2.0

    score = max(0.0, min(100.0, round(weighted_sum, 1)))

    if strong_structure >= 2:
        score = max(score, round(18.0 + strong_structure * 5.0 + structural_bonus * 0.5, 1))

    if giveback >= 0.75:
        score = min(score, max(score * 0.92, 22.0 if strong_structure >= 2 else 12.0))

    score = max(0.0, min(100.0, round(score, 1)))
    return score, contributions, subscores


def derive_verdict(
    *,
    context_score: float,
    current_pct: float,
    high_pct: float,
    drawdown: float,
    pdc_score: float,
    giveback: float,
    factors: dict[str, str],
    sources_present: int,
) -> str:
    if sources_present <= 1:
        return "UNKNOWN_CONTEXT"

    if current_pct <= 0 and high_pct >= 4.0:
        if context_score >= 55:
            return "CONTEXT_WEAKENING"
        if pdc_score >= 70 or giveback >= 0.65 or factors.get("memory_context") == "MEMORY_COLLAPSED":
            return "PROTECT_NOW"
        return "CONTEXT_WEAKENING"

    if context_score >= 70 and current_pct > 0 and drawdown > -1.5:
        return "KEEP_WINNER"
    if context_score >= 55 and current_pct > 0 and drawdown > -2.5:
        return "NORMAL_PULLBACK"
    if context_score >= 40:
        return "CONTEXT_WEAKENING"
    if pdc_score >= 75 and giveback >= 0.70 and factors.get("memory_context") == "MEMORY_COLLAPSED":
        return "PROTECT_NOW"
    if context_score < 35 and giveback >= 0.65:
        return "PROTECT_NOW"
    if context_score < 40:
        return "PROTECT_NOW"
    return "UNKNOWN_CONTEXT"


def derive_confidence(sources_present: int, factors: dict[str, str]) -> str:
    unknowns = sum(1 for v in factors.values() if str(v).startswith("UNKNOWN"))
    if sources_present >= 5 and unknowns <= 2:
        return "HIGH"
    if sources_present >= 3 and unknowns <= 4:
        return "MEDIUM"
    return "LOW"


def build_explanation(
    *,
    ticker: str,
    verdict: str,
    context_score: float,
    contributions: list[dict[str, Any]],
    pdc_rec: str,
) -> str:
    top = sorted(contributions, key=lambda c: abs(c["contribution"]), reverse=True)[:3]
    top_str = "; ".join(f"{c['component']}={c['contribution']}" for c in top)
    return (
        f"SHADOW_ONLY adaptive context for {ticker}: score={context_score} → {verdict}. "
        f"PDC={pdc_rec}. Top contributions: {top_str}."
    )


def analyze_ticker(
    ticker: str,
    *,
    committee_row: dict[str, Any],
    weighted_row: dict[str, Any] | None,
    brain_row: dict[str, Any] | None,
    memory_row: dict[str, Any] | None,
    episode: dict[str, Any] | None,
    signal_row: dict[str, Any] | None,
    regime: dict[str, Any],
    cross: dict[str, Any],
    sector_info: dict[str, Any],
    weights: dict[str, float],
    sources_present: int,
) -> dict[str, Any]:
    current_pct = _f(committee_row.get("current_pct"))
    high_pct = _f(committee_row.get("high_pct"))
    drawdown = _f(committee_row.get("drawdown"))
    pdc_score = _f(committee_row.get("protection_score"))
    pdc_rec = str(
        (weighted_row or {}).get("weighted_committee_recommendation")
        or committee_row.get("final_committee_recommendation")
        or "NO_ACTION"
    )
    survival = _f((brain_row or {}).get("psp_survival_probability"))
    giveback = _f((brain_row or {}).get("psp_giveback_risk"))
    memory_bias = str((memory_row or {}).get("recommended_memory_bias") or "MEMORY_NEUTRAL")

    factors = {
        "trend_context": trend_context(signal_row),
        "market_context": market_context_for_ticker(ticker, regime, cross),
        "sector_context": sector_context(sector_info),
        "momentum_context": momentum_context(signal_row),
        "volatility_context": volatility_context(drawdown),
        "memory_context": memory_context(memory_row, episode),
        "psp_context": psp_context(brain_row),
        "committee_context": committee_context(pdc_rec, pdc_score),
    }

    context_score, contributions, subscores = compute_weighted_context_score(
        factors=factors,
        weights=weights,
        current_pct=current_pct,
        high_pct=high_pct,
        drawdown=drawdown,
        giveback=giveback,
        survival=survival,
    )

    verdict = derive_verdict(
        context_score=context_score,
        current_pct=current_pct,
        high_pct=high_pct,
        drawdown=drawdown,
        pdc_score=pdc_score,
        giveback=giveback,
        factors=factors,
        sources_present=sources_present,
    )
    if verdict == "KEEP_WINNER" and current_pct <= 0 and high_pct >= 4.0:
        verdict = "CONTEXT_WEAKENING"

    confidence = derive_confidence(sources_present, factors)
    explanation = build_explanation(
        ticker=ticker,
        verdict=verdict,
        context_score=context_score,
        contributions=contributions,
        pdc_rec=pdc_rec,
    )

    return {
        "ticker": ticker,
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown": round(drawdown, 2),
        "pdc_recommendation": pdc_rec,
        "pdc_score": round(pdc_score, 1),
        "psp_survival_probability": round(survival, 3),
        "psp_giveback_risk": round(giveback, 3),
        "memory_bias": memory_bias,
        "context_factors": factors,
        "component_subscores": {k: subscores[k] for k in COMPONENT_KEYS},
        "component_contributions": contributions,
        "profit_context_score": context_score,
        "context_verdict": verdict,
        "confidence": confidence,
        "explanation": explanation,
        "shadow_only": True,
    }


def build_learning_artifact(
    weights: dict[str, float],
    adjustment_notes: list[str],
    committee_learning: dict[str, Any] | None,
) -> dict[str, Any]:
    members = (committee_learning or {}).get("members") or {}
    return {
        "schema": "tae_profit_context_learning",
        "version": "v2",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_of_weights": {
            "defaults": DEFAULT_WEIGHTS,
            "committee_learning_loaded": committee_learning is not None,
            "memory_accuracy": members.get("Memory", {}).get("accuracy"),
            "validation_accuracy": members.get("Validation", {}).get("accuracy"),
            "psp_accuracy": members.get("PSP", {}).get("accuracy"),
        },
        "default_weights": DEFAULT_WEIGHTS,
        "component_weights": weights,
        "weight_sum": round(sum(weights.values()), 4),
        "constraints": {
            "min_weight": WEIGHT_MIN,
            "max_weight": WEIGHT_MAX,
            "normalized": True,
            "conservative_learning": True,
        },
        "adjustment_notes": adjustment_notes,
        "notes": [
            "SHADOW_ONLY — no live or advisory integration.",
            "Weight updates are conservative; true outcome learning deferred.",
        ],
    }


def write_learning_outputs(learning: dict[str, Any]) -> tuple[Path, Path]:
    LEARNING_JSON.write_text(json.dumps(learning, indent=2), encoding="utf-8")

    weights = learning.get("component_weights") or {}
    lines = [
        "# TAE Profit Context Learning v2",
        "",
        f"**Generated:** {learning['generated_at']}",
        f"**Mode:** {learning['mode']} — {learning['live_trading_impact']}",
        "",
        "> **SHADOW_ONLY — no live or advisory integration**",
        "",
        "## Component weights",
        "",
        "| component | weight | default |",
        "| --- | --- | --- |",
    ]
    defaults = learning.get("default_weights") or DEFAULT_WEIGHTS
    for component in COMPONENT_KEYS:
        lines.append(
            f"| {component} | {weights.get(component)} | {defaults.get(component)} |"
        )

    lines.extend(
        [
            "",
            "## Source of weights",
            f"- Committee learning loaded: **{learning.get('source_of_weights', {}).get('committee_learning_loaded')}**",
            f"- Memory accuracy: **{learning.get('source_of_weights', {}).get('memory_accuracy')}**",
            f"- Validation accuracy: **{learning.get('source_of_weights', {}).get('validation_accuracy')}**",
            f"- PSP accuracy: **{learning.get('source_of_weights', {}).get('psp_accuracy')}**",
            "",
            "## Normalization",
            f"- Weight sum: **{learning.get('weight_sum')}**",
            f"- Min weight: **{learning.get('constraints', {}).get('min_weight')}**",
            f"- Max weight: **{learning.get('constraints', {}).get('max_weight')}**",
            "",
            "## Constraints applied",
            "- Weights normalized to sum 1.0",
            "- No component below 0.03 or above 0.30",
            "- Conservative adjustments only (+/- 0.01 to 0.02)",
            "",
            "## Adjustment notes",
        ]
    )
    for note in learning.get("adjustment_notes") or []:
        lines.append(f"- {note}")
    for note in learning.get("notes") or []:
        lines.append(f"- {note}")

    LEARNING_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return LEARNING_JSON, LEARNING_MD


def build_context_report() -> tuple[dict[str, Any], dict[str, Any]]:
    committee, committee_ok = load_json(COMMITTEE_JSON)
    committee_learning, _ = load_json(COMMITTEE_LEARNING_JSON)
    prior_context_learning, _ = load_json(LEARNING_JSON)
    brain, brain_ok = load_json(BRAIN_JSON)
    memory, memory_ok = load_json(MEMORY_JSON)
    shadow, shadow_ok = load_json(SHADOW_JSON)

    weights, adjustment_notes = build_adaptive_weights(committee_learning, prior_context_learning)
    learning_artifact = build_learning_artifact(weights, adjustment_notes, committee_learning)

    signals = load_live_signals()
    regime = parse_market_regime(read_text(REGIME_SUMMARY))
    cross = parse_cross_market(read_text(CROSS_MARKET_SUMMARY))
    sector_info = parse_sector_leader(read_text(SECTOR_SUMMARY))

    sources_loaded = {
        str(COMMITTEE_JSON): committee_ok,
        str(COMMITTEE_LEARNING_JSON): committee_learning is not None,
        str(BRAIN_JSON): brain_ok,
        str(MEMORY_JSON): memory_ok,
        str(SHADOW_JSON): shadow_ok,
        str(LIVE_SIGNALS_CSV): LIVE_SIGNALS_CSV.is_file(),
        str(REGIME_SUMMARY): REGIME_SUMMARY.is_file(),
        str(CROSS_MARKET_SUMMARY): CROSS_MARKET_SUMMARY.is_file(),
        str(SECTOR_SUMMARY): SECTOR_SUMMARY.is_file(),
    }
    sources_present = sum(1 for v in sources_loaded.values() if v)

    brain_by = {
        str(r.get("ticker", "")).upper(): r for r in (brain or {}).get("positions") or [] if r.get("ticker")
    }
    memory_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (memory or {}).get("ticker_memory") or []
        if r.get("ticker")
    }
    episode_by: dict[str, dict[str, Any]] = {}
    for ep in (memory or {}).get("episodes") or []:
        t = str(ep.get("ticker", "")).upper()
        if t:
            episode_by[t] = ep
    weighted_by = {
        str(r.get("ticker", "")).upper(): r for r in (committee or {}).get("weighted_tickers") or [] if r.get("ticker")
    }

    tickers: list[dict[str, Any]] = []
    for row in (committee or {}).get("tickers") or []:
        ticker = str(row.get("ticker", "")).upper()
        if not ticker:
            continue
        tickers.append(
            analyze_ticker(
                ticker,
                committee_row=row,
                weighted_row=weighted_by.get(ticker),
                brain_row=brain_by.get(ticker),
                memory_row=memory_by.get(ticker),
                episode=episode_by.get(ticker),
                signal_row=signals.get(ticker),
                regime=regime,
                cross=cross,
                sector_info=sector_info,
                weights=weights,
                sources_present=sources_present,
            )
        )

    tickers.sort(key=lambda t: t.get("profit_context_score", 0))

    counts = {v: 0 for v in VERDICTS}
    for t in tickers:
        counts[t.get("context_verdict", "UNKNOWN_CONTEXT")] = counts.get(t.get("context_verdict"), 0) + 1

    scores = [t.get("profit_context_score", 0) for t in tickers]
    protect_now = [t for t in tickers if t.get("context_verdict") == "PROTECT_NOW"]
    keep_winner = [t for t in reversed(tickers) if t.get("context_verdict") == "KEEP_WINNER"]

    if not committee_ok or not tickers:
        final_verdict = "PCE_NOT_READY"
    elif len(tickers) >= 3:
        final_verdict = "PCE_SHADOW_READY_FOR_OBSERVATION"
    else:
        final_verdict = "PCE_SHADOW_NEEDS_MORE_DATA"

    report = {
        "schema": "tae_profit_context_engine",
        "version": "v2",
        "adaptive_weighted": True,
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "component_weights": weights,
        "learning_source": str(LEARNING_JSON),
        "market_snapshot": {
            "regime": regime,
            "cross_market": cross,
            "sector_leader": sector_info,
        },
        "tickers": tickers,
        "global_summary": {
            "total_tickers": len(tickers),
            "keep_winner_count": counts.get("KEEP_WINNER", 0),
            "normal_pullback_count": counts.get("NORMAL_PULLBACK", 0),
            "weakening_count": counts.get("CONTEXT_WEAKENING", 0),
            "protect_now_count": counts.get("PROTECT_NOW", 0),
            "unknown_count": counts.get("UNKNOWN_CONTEXT", 0),
            "average_context_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "top_5_protect_now": [
                {
                    "ticker": t["ticker"],
                    "profit_context_score": t["profit_context_score"],
                    "pdc_recommendation": t["pdc_recommendation"],
                    "context_verdict": t["context_verdict"],
                }
                for t in protect_now[:5]
            ],
            "top_5_keep_winner": [
                {
                    "ticker": t["ticker"],
                    "profit_context_score": t["profit_context_score"],
                    "pdc_recommendation": t["pdc_recommendation"],
                    "context_verdict": t["context_verdict"],
                }
                for t in keep_winner[:5]
            ],
            "final_verdict": final_verdict,
        },
    }
    return report, learning_artifact


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    weights = report.get("component_weights") or {}
    lines = [
        "# TAE Profit Context Engine v2 (Adaptive Weighted)",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY context research**",
        "",
        "## Global summary",
        f"- Total tickers: **{summary['total_tickers']}**",
        f"- Average context score: **{summary['average_context_score']}**",
        f"- KEEP_WINNER: **{summary['keep_winner_count']}**",
        f"- NORMAL_PULLBACK: **{summary['normal_pullback_count']}**",
        f"- CONTEXT_WEAKENING: **{summary['weakening_count']}**",
        f"- PROTECT_NOW: **{summary['protect_now_count']}**",
        f"- UNKNOWN: **{summary['unknown_count']}**",
        "",
        "## Component weights",
        "",
        "| component | weight |",
        "| --- | --- |",
    ]
    for component in COMPONENT_KEYS:
        lines.append(f"| {component} | {weights.get(component)} |")

    lines.extend(
        [
            "",
            "## Top 5 PROTECT_NOW",
            "",
            "| ticker | context score | PDC rec | verdict |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("top_5_protect_now") or []:
        lines.append(
            f"| {row['ticker']} | {row['profit_context_score']} | {row['pdc_recommendation']} | {row['context_verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Top 5 KEEP_WINNER",
            "",
            "| ticker | context score | PDC rec | verdict |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("top_5_keep_winner") or []:
        lines.append(
            f"| {row['ticker']} | {row['profit_context_score']} | {row['pdc_recommendation']} | {row['context_verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Tickers",
            "",
            "| ticker | ctx score | verdict | confidence | PDC |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for t in report.get("tickers") or []:
        lines.append(
            f"| {t['ticker']} | {t['profit_context_score']} | {t['context_verdict']} | "
            f"{t['confidence']} | {t['pdc_recommendation']} |"
        )

    lines.extend(["", "## Per-ticker component contributions", ""])
    for t in report.get("tickers") or []:
        lines.append(f"### {t['ticker']} — {t['context_verdict']} (score {t['profit_context_score']})")
        lines.append(t.get("explanation", ""))
        lines.append("")
        lines.append("| component | label | weight | subscore | contribution |")
        lines.append("| --- | --- | --- | --- | --- |")
        for c in t.get("component_contributions") or []:
            lines.append(
                f"| {c['component']} | {c['label']} | {c['weight']} | {c['subscore']} | {c['contribution']} |"
            )
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["global_summary"]
    print("===== TAE PROFIT CONTEXT ENGINE v2 (Adaptive) =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", summary["final_verdict"])
    print("Tickers:", summary["total_tickers"])
    print("Avg context score:", summary["average_context_score"])
    print(
        "KEEP / PULLBACK / WEAKEN / PROTECT / UNKNOWN:",
        summary["keep_winner_count"],
        summary["normal_pullback_count"],
        summary["weakening_count"],
        summary["protect_now_count"],
        summary["unknown_count"],
    )


def main() -> int:
    report, learning = build_context_report()
    write_learning_outputs(learning)
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD, LEARNING_JSON, LEARNING_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
