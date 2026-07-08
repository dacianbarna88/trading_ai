#!/usr/bin/env python3
"""
TAE Market Philosophy Lab v1 — SHADOW_ONLY / READ_ONLY.

Compares COMPETITIVE_MODEL vs COLLABORATIVE_MODEL on the same portfolio state.
Does NOT modify live_bot, portfolio, advisory, or execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

GII_JSON = Path("tae_growth_intelligence.json")
TARGET_JSON = Path("tae_profit_target_adapter.json")
GROWTH_JSON = Path("tae_profit_growth_analytics.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
LIFECYCLE_JSON = Path("tae_winner_lifecycle_profiler.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
SHADOW_EVENTS_CSV = Path("tae_shadow_validation_events.csv")
BOT_LOG = Path("bot_output.log")

OUTPUT_JSON = Path("tae_market_philosophy_lab.json")
OUTPUT_MD = Path("tae_market_philosophy_lab.md")

COMPETITIVE_POSTURES = frozenset(
    {"AGGRESSIVE_GROWTH", "SELECTIVE_GROWTH", "NEUTRAL", "DEFENSIVE", "AVOID"}
)
COLLABORATIVE_POSTURES = frozenset(
    {
        "MARKET_ALIGNED_GROWTH",
        "FOLLOW_TREND",
        "WAIT_FOR_ALIGNMENT",
        "CAPITAL_PRESERVATION",
        "AVOID_FIGHTING_MARKET",
    }
)
PHILOSOPHY_PREFS = frozenset({"COMPETITIVE", "COLLABORATIVE", "MIXED", "AVOID"})
WINNING_PHILOSOPHIES = frozenset(
    {"COMPETITIVE_MODEL", "COLLABORATIVE_MODEL", "MIXED_MODEL", "INCONCLUSIVE"}
)
DECAY_STAGES = frozenset({"PROFIT_DECAY", "COLLAPSED", "WEAKENING"})
HARMONIOUS_PCE = frozenset({"KEEP_WINNER", "NORMAL_PULLBACK"})
ADVERSE_PCE = frozenset({"PROTECT_NOW", "CONTEXT_WEAKENING"})

UPSTREAM_REUSE = [
    "tae_growth_intelligence.json — growth scores, strategies, lifecycle, context verdicts",
    "tae_profit_target_adapter.json — target strategies per ticker",
    "tae_profit_growth_analytics.json — capture rate, portfolio verdict",
    "tae_opportunity_cost_ledger.json — opportunity cost totals and categories",
    "tae_winner_lifecycle_profiler.json — lifecycle health, collapse/survival",
    "tae_portfolio_profit_governor.json — portfolio verdict",
    "tae_adaptive_profit_policy_engine.json — policy state alignment",
    "tae_profit_context_engine.json — context alignment enrichment",
    "tae_profit_memory_engine.json — memory labels",
    "tae_accounting_snapshot.json — corrected PnL context",
]

NOT_DUPLICATED = (
    "Does not recompute growth intelligence, lifecycle, opportunity ledger, or profit targets. "
    "Compares two market philosophies using existing SSOT as referee inputs."
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any, default: str = "UNKNOWN") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def pce_alignment_score(pce_verdict: str) -> float:
    if pce_verdict in HARMONIOUS_PCE:
        return 85.0
    if pce_verdict == "NORMAL_PULLBACK":
        return 75.0
    if pce_verdict in ADVERSE_PCE:
        return 25.0
    return 50.0


def competitive_posture(score: float, keep_count: int, capture_rate: float | None) -> str:
    if score >= 75 and keep_count >= 3:
        return "AGGRESSIVE_GROWTH"
    if score >= 60:
        return "SELECTIVE_GROWTH"
    if score >= 45:
        return "NEUTRAL"
    if score >= 30:
        return "DEFENSIVE"
    return "AVOID"


def collaborative_posture(score: float, harmony: float, policy_state: str) -> str:
    if score >= 75 and harmony >= 65:
        return "MARKET_ALIGNED_GROWTH"
    if score >= 60:
        return "FOLLOW_TREND"
    if score >= 45:
        return "WAIT_FOR_ALIGNMENT"
    if policy_state == "HIGH_RISK" or score >= 30:
        return "CAPITAL_PRESERVATION"
    return "AVOID_FIGHTING_MARKET"


def ticker_competitive_bias(
    *,
    growth_score: float,
    future_growth: float,
    opportunity_score: float,
    strategy: str,
    lifecycle_stage: str,
    missed_usd: float,
) -> float:
    score = growth_score * 0.35 + future_growth * 0.25 + opportunity_score * 0.15
    if strategy == "KEEP_GROWING_SHADOW":
        score += 12.0
    if lifecycle_stage in {"EARLY_WINNER", "MATURE_WINNER", "PEAK_WINNER", "SURVIVED"}:
        score += 8.0
    if lifecycle_stage in DECAY_STAGES:
        score -= 25.0
    if missed_usd >= 200:
        score += 5.0  # competitive sees upside in recovering missed alpha
    return round(clamp(score), 1)


def ticker_collaborative_bias(
    *,
    growth_score: float,
    survival: float,
    collapse: float,
    pce_verdict: str,
    lifecycle_stage: str,
    opportunity_score: float,
    strategy: str,
    policy_state: str,
) -> float:
    score = pce_alignment_score(pce_verdict) * 0.35
    score += survival * 100.0 * 0.25
    score += (1.0 - collapse) * 100.0 * 0.2
    score += (100.0 - opportunity_score) * 0.1
    if lifecycle_stage in {"SURVIVED", "EARLY_WINNER", "MATURE_WINNER"}:
        score += 10.0
    if lifecycle_stage in DECAY_STAGES:
        score -= 20.0
    if strategy in {"PROTECT_PROFIT_SHADOW", "TIGHTEN_TRAIL_SHADOW", "REDUCE_EXPOSURE_SHADOW"}:
        score += 8.0 if policy_state == "HIGH_RISK" else 3.0
    if strategy == "KEEP_GROWING_SHADOW" and pce_verdict in ADVERSE_PCE:
        score -= 15.0
    return round(clamp(score), 1)


def ticker_philosophy_preference(
    competitive: float,
    collaborative: float,
    *,
    pce_verdict: str,
    lifecycle_stage: str,
    strategy: str,
    conflict: bool,
) -> tuple[str, bool]:
    delta = competitive - collaborative
    if lifecycle_stage == "COLLAPSED" or strategy == "REDUCE_EXPOSURE_SHADOW":
        return "AVOID", conflict
    if abs(delta) <= 8.0 and competitive >= 55 and collaborative >= 55:
        return "MIXED", conflict
    if conflict:
        return "MIXED", True
    if collaborative >= competitive + 12:
        return "COLLABORATIVE", conflict
    if competitive >= collaborative + 12:
        return "COMPETITIVE", conflict
    return "MIXED", conflict


def portfolio_competitive_score(
    tickers: list[dict[str, Any]],
    *,
    capture_rate: float | None,
    global_growth: float,
    opportunity_total: float,
    policy_state: str,
) -> tuple[float, list[str], list[str]]:
    n = len(tickers) or 1
    avg_growth = sum(_f(t.get("growth_score")) for t in tickers) / n
    avg_future = sum(_f(t.get("future_growth_potential")) for t in tickers) / n
    avg_opp = sum(_f(t.get("opportunity_score")) for t in tickers) / n
    keep_count = sum(1 for t in tickers if t.get("recommended_shadow_strategy") == "KEEP_GROWING_SHADOW")
    decay_count = sum(1 for t in tickers if t.get("lifecycle_stage") in DECAY_STAGES)

    score = avg_growth * 0.3 + avg_future * 0.25 + avg_opp * 0.15 + global_growth * 0.1
    score += min(15.0, keep_count * 3.0)
    if capture_rate is not None and capture_rate < 0.4:
        score += 8.0  # upside potential narrative for competitive
    else:
        score += capture_rate * 20.0 if capture_rate else 0.0

    strengths: list[str] = []
    risks: list[str] = []

    if keep_count >= 3:
        strengths.append(f"{keep_count} KEEP_GROWING_SHADOW candidates support alpha pursuit")
    if avg_future >= 60:
        strengths.append("Strong average future growth potential")
    if avg_opp >= 50:
        strengths.append("Elevated opportunity score — competitive sees recoverable upside")

    if decay_count >= 2:
        score -= 15.0
        risks.append(f"{decay_count} decay/collapsed positions drag competitive score")
    if capture_rate is not None and capture_rate < 0.35:
        score -= 10.0
        risks.append(f"Low profit capture rate ({capture_rate:.1%}) limits alpha proof")
    if policy_state == "HIGH_RISK":
        score -= 8.0
        risks.append("HIGH_RISK policy constrains aggressive posture")

    return round(clamp(score), 1), strengths, risks


def portfolio_collaborative_score(
    tickers: list[dict[str, Any]],
    *,
    capture_rate: float | None,
    opportunity_total: float,
    policy_state: str,
    portfolio_verdict: str,
) -> tuple[float, list[str], list[str]]:
    n = len(tickers) or 1
    avg_survival = sum(_f(t.get("survival_probability")) for t in tickers) / n
    avg_collapse = sum(_f(t.get("collapse_probability")) for t in tickers) / n
    harmonious = sum(1 for t in tickers if _s(t.get("pce_verdict")) in HARMONIOUS_PCE)
    adverse = sum(1 for t in tickers if _s(t.get("pce_verdict")) in ADVERSE_PCE)
    protect_count = sum(
        1
        for t in tickers
        if t.get("recommended_shadow_strategy")
        in {"PROTECT_PROFIT_SHADOW", "TIGHTEN_TRAIL_SHADOW", "REDUCE_EXPOSURE_SHADOW"}
    )

    score = avg_survival * 100.0 * 0.3 + (1.0 - avg_collapse) * 100.0 * 0.25
    score += harmonious / n * 25.0
    if capture_rate is not None:
        score += capture_rate * 100.0 * 0.15
    if policy_state == "HIGH_RISK" and protect_count >= 2:
        score += 10.0
    if opportunity_total > 500 and protect_count >= 2:
        score += 5.0

    strengths: list[str] = []
    risks: list[str] = []

    if harmonious >= n // 2:
        strengths.append(f"{harmonious}/{n} tickers with harmonious PCE context")
    if avg_survival >= 0.6:
        strengths.append(f"High average survival probability ({avg_survival:.2f})")
    if policy_state == "HIGH_RISK":
        strengths.append("Capital preservation aligned with HIGH_RISK policy")

    if adverse >= 3:
        score -= 12.0
        risks.append(f"{adverse} tickers fighting context weakening")
    if opportunity_total >= 700:
        score -= 10.0
        risks.append(f"High opportunity cost (${opportunity_total:.0f}) — market reversal not adapted")
    if "HIGH_RISK" in portfolio_verdict and protect_count < 2:
        score -= 8.0
        risks.append("Portfolio HIGH_RISK but insufficient protection alignment")

    return round(clamp(score), 1), strengths, risks


def market_harmony_score(
    *,
    tickers: list[dict[str, Any]],
    collaborative_score: float,
    capture_rate: float | None,
    opportunity_total: float,
    policy_state: str,
    portfolio_verdict: str,
    global_growth: float,
) -> float:
    n = len(tickers) or 1
    context_align = sum(pce_alignment_score(_s(t.get("pce_verdict"))) for t in tickers) / n
    lifecycle_health = sum(
        1 for t in tickers if t.get("lifecycle_stage") not in DECAY_STAGES
    ) / n * 100.0
    survival = sum(_f(t.get("survival_probability")) for t in tickers) / n * 100.0
    collapse_inv = (1.0 - sum(_f(t.get("collapse_probability")) for t in tickers) / n) * 100.0
    policy_align = 80.0 if policy_state == "HIGH_RISK" and "HIGH_RISK" in portfolio_verdict else 55.0
    opp_inv = clamp(100.0 - min(100.0, opportunity_total / 10.0))
    capture = capture_rate * 100.0 if capture_rate else 40.0
    consistency = min(global_growth, collaborative_score)

    raw = (
        context_align * 0.2
        + lifecycle_health * 0.15
        + survival * 0.15
        + collapse_inv * 0.15
        + policy_align * 0.1
        + opp_inv * 0.1
        + capture * 0.1
        + consistency * 0.05
    )
    return round(clamp(raw), 1)


def winning_philosophy(competitive: float, collaborative: float) -> str:
    delta = competitive - collaborative
    if abs(delta) <= 5.0:
        if competitive < 40 and collaborative < 40:
            return "INCONCLUSIVE"
        return "MIXED_MODEL"
    if collaborative > competitive:
        return "COLLABORATIVE_MODEL"
    return "COMPETITIVE_MODEL"


def recommended_experiment_mode(winner: str, confidence: float) -> str:
    if confidence < 0.45:
        return "OBSERVE_ONLY"
    if winner == "COMPETITIVE_MODEL":
        return "PAPER_COMPETITIVE"
    if winner == "COLLABORATIVE_MODEL":
        return "PAPER_COLLABORATIVE"
    return "PAPER_MIXED"


def build_lab() -> dict[str, Any]:
    source_paths = {
        "tae_growth_intelligence.json": GII_JSON,
        "tae_profit_target_adapter.json": TARGET_JSON,
        "tae_profit_growth_analytics.json": GROWTH_JSON,
        "tae_opportunity_cost_ledger.json": LEDGER_JSON,
        "tae_winner_lifecycle_profiler.json": LIFECYCLE_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
        "tae_shadow_validation_events.csv": SHADOW_EVENTS_CSV,
        "bot_output.log": BOT_LOG,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        if key.endswith((".csv", ".log")):
            sources_loaded[key] = path.is_file()
            payloads[key] = None
            continue
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data

    gii = payloads["tae_growth_intelligence.json"]
    targets = payloads["tae_profit_target_adapter.json"]
    growth = payloads["tae_profit_growth_analytics.json"]
    ledger = payloads["tae_opportunity_cost_ledger.json"]
    appe = payloads["tae_adaptive_profit_policy_engine.json"]
    ppg = payloads["tae_portfolio_profit_governor.json"]

    gii_tickers = (gii or {}).get("tickers") or []
    target_by = {
        _s(t.get("ticker")).upper(): t for t in (targets or {}).get("tickers") or [] if t.get("ticker")
    }

    portfolio_gii = (gii or {}).get("portfolio") or {}
    core = (growth or {}).get("core_metrics") or {}
    capture_rate = core.get("profit_capture_rate") or portfolio_gii.get("profit_capture_rate")
    opportunity_total = _f(
        (ledger or {}).get("global_summary", {}).get("total_opportunity_cost_usd"),
        _f(portfolio_gii.get("opportunity_cost_total")),
    )
    global_growth = _f(portfolio_gii.get("global_growth_score"))
    policy_state = _s(
        ((appe or {}).get("latest_observation") or {}).get("policy_state"),
        _s(core.get("policy_state")),
    )
    portfolio_verdict = _s(
        core.get("portfolio_verdict") or (ppg or {}).get("portfolio_verdict"),
        portfolio_gii.get("portfolio_verdict"),
    )

    merged_tickers: list[dict[str, Any]] = []
    for row in gii_tickers:
        ticker = _s(row.get("ticker")).upper()
        tgt = target_by.get(ticker) or {}
        strategy = _s(row.get("recommended_shadow_strategy"))
        target_strategy = _s(tgt.get("recommended_shadow_strategy"), strategy)
        pce = _s(row.get("pce_verdict"))
        lifecycle = _s(row.get("lifecycle_stage"))

        competitive = ticker_competitive_bias(
            growth_score=_f(row.get("growth_score")),
            future_growth=_f(row.get("future_growth_potential")),
            opportunity_score=_f(row.get("opportunity_score")),
            strategy=strategy,
            lifecycle_stage=lifecycle,
            missed_usd=_f(row.get("missed_usd")),
        )
        collaborative = ticker_collaborative_bias(
            growth_score=_f(row.get("growth_score")),
            survival=_f(row.get("survival_probability")),
            collapse=_f(row.get("collapse_probability")),
            pce_verdict=pce,
            lifecycle_stage=lifecycle,
            opportunity_score=_f(row.get("opportunity_score")),
            strategy=strategy,
            policy_state=policy_state,
        )

        conflict = (
            competitive >= 60
            and collaborative >= 50
            and pce in ADVERSE_PCE
            and strategy == "KEEP_GROWING_SHADOW"
        ) or (
            competitive >= 55
            and lifecycle in DECAY_STAGES
            and collaborative >= 55
        )

        pref, conflict_flag = ticker_philosophy_preference(
            competitive,
            collaborative,
            pce_verdict=pce,
            lifecycle_stage=lifecycle,
            strategy=strategy,
            conflict=conflict,
        )

        explanation = (
            f"{ticker}: competitive={competitive:.1f}, collaborative={collaborative:.1f}, "
            f"pref={pref}. lifecycle={lifecycle}, PCE={pce}, strategy={target_strategy}."
        )
        if conflict_flag:
            explanation += " Conflict: growth upside vs market alignment tension."

        merged_tickers.append(
            {
                "ticker": ticker,
                "growth_score": round(_f(row.get("growth_score")), 1),
                "lifecycle_stage": lifecycle,
                "opportunity_score": round(_f(row.get("opportunity_score")), 1),
                "collapse_probability": round(_f(row.get("collapse_probability")), 3),
                "survival_probability": round(_f(row.get("survival_probability")), 3),
                "pce_verdict": pce,
                "governor_recommendation": _s(row.get("governor_recommendation")),
                "target_strategy": target_strategy,
                "competitive_bias_score": competitive,
                "collaborative_bias_score": collaborative,
                "philosophy_preference": pref,
                "philosophy_conflict": conflict_flag,
                "explanation": explanation,
            }
        )

    comp_score, comp_strengths, comp_risks = portfolio_competitive_score(
        gii_tickers,
        capture_rate=capture_rate if capture_rate is not None else None,
        global_growth=global_growth,
        opportunity_total=opportunity_total,
        policy_state=policy_state,
    )
    collab_score, collab_strengths, collab_risks = portfolio_collaborative_score(
        gii_tickers,
        capture_rate=capture_rate if capture_rate is not None else None,
        opportunity_total=opportunity_total,
        policy_state=policy_state,
        portfolio_verdict=portfolio_verdict,
    )
    harmony = market_harmony_score(
        tickers=gii_tickers,
        collaborative_score=collab_score,
        capture_rate=capture_rate if capture_rate is not None else None,
        opportunity_total=opportunity_total,
        policy_state=policy_state,
        portfolio_verdict=portfolio_verdict,
        global_growth=global_growth,
    )

    winner = winning_philosophy(comp_score, collab_score)
    delta = round(collab_score - comp_score, 1)
    keep_count = sum(1 for t in gii_tickers if t.get("recommended_shadow_strategy") == "KEEP_GROWING_SHADOW")

    confidence = round(
        clamp(
            0.45
            + (abs(delta) / 100.0) * 0.35
            + (0.15 if sources_loaded.get("tae_growth_intelligence.json") else 0)
            + (0.1 if len(merged_tickers) >= 8 else 0),
            0.0,
            1.0,
        ),
        2,
    )

    why_wins: list[str] = []
    if winner == "COLLABORATIVE_MODEL":
        why_wins.append(
            f"Collaborative score {collab_score} exceeds competitive {comp_score} by {abs(delta):.1f} pts"
        )
        why_wins.append(f"Market harmony {harmony} — alignment beats alpha chase in current regime")
        if policy_state == "HIGH_RISK":
            why_wins.append("HIGH_RISK policy favors harmony-first capital preservation")
        if opportunity_total >= 500:
            why_wins.append(f"${opportunity_total:.0f} missed profit suggests fighting market was costly")
    elif winner == "COMPETITIVE_MODEL":
        why_wins.append(
            f"Competitive score {comp_score} exceeds collaborative {collab_score} by {abs(delta):.1f} pts"
        )
        if keep_count >= 3:
            why_wins.append(f"{keep_count} keep-growing candidates still offer alpha upside")
    elif winner == "MIXED_MODEL":
        why_wins.append(f"Scores within 5 pts (competitive {comp_score}, collaborative {collab_score})")
        why_wins.append("Both philosophies partially valid — ticker-level split recommended")
    else:
        why_wins.append("Insufficient signal strength — both scores below confidence threshold")

    portfolio_explanation = (
        f"Referee verdict: {winner}. Competitive={comp_score}, Collaborative={collab_score}, "
        f"Harmony={harmony}, delta={delta:+.1f}. "
        f"Capture rate={capture_rate}, opportunity=${opportunity_total:.0f}."
    )

    conflicts = [t for t in merged_tickers if t.get("philosophy_conflict")]

    verdict = (
        "PHILOSOPHY_LAB_READY"
        if sources_loaded.get("tae_growth_intelligence.json") and merged_tickers
        else "PHILOSOPHY_LAB_NEEDS_MORE_DATA"
    )
    if not sources_loaded.get("tae_growth_intelligence.json"):
        verdict = "PHILOSOPHY_LAB_NOT_READY"

    return {
        "schema": "tae_market_philosophy_lab",
        "version": "v1",
        "mode": "SHADOW_ONLY",
        "read_only": True,
        "live_trading_impact": "NONE",
        "no_broker": True,
        "no_execution": True,
        "no_advisory_change": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "safety_mode": {
            "shadow_only": True,
            "read_only": True,
            "no_broker": True,
            "no_live_execution_change": True,
            "no_advisory_change": True,
            "portfolio_csv_modified": False,
        },
        "philosophy_definitions": {
            "COMPETITIVE_MODEL": "Beat market — maximize alpha, aggressive profit-first posture",
            "COLLABORATIVE_MODEL": "Adapt to market — harmony-first, profit through alignment",
        },
        "scoring_model": {
            "competitive": "growth_score, future potential, opportunity upside, keep-growing count; penalize decay/low capture",
            "collaborative": "PCE alignment, survival, low collapse, policy preservation; penalize fighting context",
            "market_harmony": "context + lifecycle + survival + policy + inverse opportunity cost + capture",
        },
        "upstream_reuse": UPSTREAM_REUSE,
        "not_duplicated": NOT_DUPLICATED,
        "global_verdict": verdict,
        "comparative": {
            "competitive_score": comp_score,
            "collaborative_score": collab_score,
            "market_harmony_score": harmony,
            "score_delta": delta,
            "current_winning_philosophy": winner,
            "recommended_experiment_mode": recommended_experiment_mode(winner, confidence),
            "confidence": confidence,
            "explanation": portfolio_explanation,
            "why_it_wins": why_wins,
        },
        "competitive_model": {
            "competitive_score": comp_score,
            "competitive_strengths": comp_strengths,
            "competitive_risks": comp_risks,
            "competitive_shadow_posture": competitive_posture(
                comp_score, keep_count, capture_rate if capture_rate is not None else None
            ),
        },
        "collaborative_model": {
            "collaborative_score": collab_score,
            "market_harmony_score": harmony,
            "collaborative_strengths": collab_strengths,
            "collaborative_risks": collab_risks,
            "collaborative_shadow_posture": collaborative_posture(collab_score, harmony, policy_state),
        },
        "portfolio_context": {
            "portfolio_verdict": portfolio_verdict,
            "policy_state": policy_state,
            "profit_capture_rate": capture_rate,
            "opportunity_cost_total": round(opportunity_total, 2),
            "global_growth_score": global_growth,
        },
        "tickers": merged_tickers,
        "conflict_cases": conflicts,
        "recommended_next_sprint": "TAE MARKET PHILOSOPHY LAB v2 — Paper Experiment Design",
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    comp = report["competitive_model"]
    collab = report["collaborative_model"]
    cmp_out = report["comparative"]

    lines = [
        "# TAE Market Philosophy Lab v1",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Global verdict:** {report['global_verdict']}",
        "",
        "> **The market is the referee — COMPETITIVE vs COLLABORATIVE comparison (shadow only)**",
        "",
        "## Executive summary",
        "",
        f"- **Winning philosophy:** {cmp_out.get('current_winning_philosophy')}",
        f"- Competitive score: **{cmp_out.get('competitive_score')}** / 100",
        f"- Collaborative score: **{cmp_out.get('collaborative_score')}** / 100",
        f"- Market Harmony Score: **{cmp_out.get('market_harmony_score')}** / 100",
        f"- Score delta (collab − comp): **{cmp_out.get('score_delta'):+.1f}**",
        f"- Recommended experiment: **{cmp_out.get('recommended_experiment_mode')}**",
        f"- Confidence: **{cmp_out.get('confidence')}**",
        "",
        "## Philosophy scores",
        "",
        "### COMPETITIVE_MODEL",
        "",
        f"- Score: **{comp.get('competitive_score')}**",
        f"- Shadow posture: **{comp.get('competitive_shadow_posture')}**",
        "",
        "**Strengths:**",
    ]
    for s in comp.get("competitive_strengths") or []:
        lines.append(f"- {s}")
    lines.extend(["", "**Risks:**"])
    for r in comp.get("competitive_risks") or []:
        lines.append(f"- {r}")

    lines.extend(
        [
            "",
            "### COLLABORATIVE_MODEL",
            "",
            f"- Score: **{collab.get('collaborative_score')}**",
            f"- Shadow posture: **{collab.get('collaborative_shadow_posture')}**",
            "",
            "**Strengths:**",
        ]
    )
    for s in collab.get("collaborative_strengths") or []:
        lines.append(f"- {s}")
    lines.extend(["", "**Risks:**"])
    for r in collab.get("collaborative_risks") or []:
        lines.append(f"- {r}")

    lines.extend(
        [
            "",
            "## Market Harmony Score",
            "",
            f"**{cmp_out.get('market_harmony_score')}** / 100 — measures alignment with market dynamics "
            "(context, lifecycle, survival, policy, inverse opportunity cost).",
            "",
            "## Which philosophy currently wins",
            "",
            f"**{cmp_out.get('current_winning_philosophy')}**",
            "",
            "## Why it wins",
            "",
        ]
    )
    for w in cmp_out.get("why_it_wins") or []:
        lines.append(f"- {w}")
    lines.append("")
    lines.append(f"> {cmp_out.get('explanation')}")

    lines.extend(
        [
            "",
            "## Per-ticker philosophy table",
            "",
            "| ticker | comp | collab | pref | lifecycle | PCE | strategy | conflict |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("tickers") or []:
        conflict = "yes" if row.get("philosophy_conflict") else "no"
        lines.append(
            f"| {row['ticker']} | {row.get('competitive_bias_score')} | {row.get('collaborative_bias_score')} | "
            f"{row.get('philosophy_preference')} | {row.get('lifecycle_stage')} | {row.get('pce_verdict')} | "
            f"{row.get('target_strategy')} | {conflict} |"
        )

    lines.extend(["", "## Conflict cases", ""])
    if report.get("conflict_cases"):
        for row in report["conflict_cases"]:
            lines.append(f"- **{row['ticker']}:** {row.get('explanation')}")
    else:
        lines.append("- No major philosophy conflicts detected.")

    lines.extend(["", "## What this reuses", ""])
    for item in report.get("upstream_reuse") or UPSTREAM_REUSE:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## What this does not duplicate",
            "",
            f"- {report.get('not_duplicated', NOT_DUPLICATED)}",
            "",
            "## Recommended next sprint",
            "",
            f"**{report.get('recommended_next_sprint')}**",
            "",
            "Define controlled PAPER A/B simulation — not broker live.",
            "",
            "## Safety confirmation",
            "",
            "- READ_ONLY: **true**",
            "- SHADOW_ONLY: **true**",
            "- NO_BROKER: **true**",
            "- NO_LIVE_EXECUTION_CHANGE: **true**",
            "- NO_ADVISORY_CHANGE: **true**",
            "- portfolio.csv modified: **false**",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    cmp_out = report["comparative"]
    print("===== TAE MARKET PHILOSOPHY LAB v1 =====")
    print("Mode: SHADOW_ONLY — read-only comparison")
    print("Global verdict:", report["global_verdict"])
    print("Winner:", cmp_out.get("current_winning_philosophy"))
    print("Competitive / Collaborative / Harmony:", cmp_out.get("competitive_score"), "/", cmp_out.get("collaborative_score"), "/", cmp_out.get("market_harmony_score"))
    print("Experiment mode:", cmp_out.get("recommended_experiment_mode"))
    print("Tickers:", len(report.get("tickers") or []))


def main() -> int:
    report = build_lab()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
