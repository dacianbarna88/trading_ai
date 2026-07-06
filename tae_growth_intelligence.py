#!/usr/bin/env python3
"""
TAE Growth Intelligence Integrator (GII) — SHADOW_ONLY / READ_ONLY.

Unified Profit Growth Intelligence view aggregating existing GA, ledger,
lifecycle, memory, context, governor, and policy SSOT outputs.
Does NOT modify live_bot, portfolio, advisory, or execution.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
GROWTH_JSON = Path("tae_profit_growth_analytics.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
LIFECYCLE_JSON = Path("tae_winner_lifecycle_profiler.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
SHADOW_EVENTS_CSV = Path("tae_shadow_validation_events.csv")
BOT_LOG = Path("bot_output.log")

OUTPUT_JSON = Path("tae_growth_intelligence.json")
OUTPUT_MD = Path("tae_growth_intelligence.md")

SHADOW_STRATEGIES = frozenset(
    {
        "KEEP_GROWING_SHADOW",
        "HOLD_AND_MONITOR_SHADOW",
        "PROTECT_PROFIT_SHADOW",
        "TIGHTEN_TRAIL_SHADOW",
        "REDUCE_EXPOSURE_SHADOW",
        "COLLECT_MORE_DATA",
    }
)

HEALTHY_LIFECYCLE = frozenset({"SURVIVED", "EARLY_WINNER", "MATURE_WINNER", "PEAK_WINNER"})
DECAY_LIFECYCLE = frozenset({"PROFIT_DECAY", "COLLAPSED", "WEAKENING"})

UPSTREAM_REUSE = [
    {
        "artifact": "tae_profit_growth_analytics.json",
        "role": "Captured vs missed metrics, growth_status, per-ticker PnL peaks",
        "not_duplicated": "GII reads JSON only; does not recompute capture rate formulas",
    },
    {
        "artifact": "tae_opportunity_cost_ledger.json",
        "role": "Opportunity cost category, severity, shadow fix mapping",
        "not_duplicated": "GII does not re-classify root causes",
    },
    {
        "artifact": "tae_winner_lifecycle_profiler.json",
        "role": "Lifecycle stage, collapse/survival, lifecycle_score",
        "not_duplicated": "GII does not re-run stage heuristics",
    },
    {
        "artifact": "tae_profit_memory_engine.json",
        "role": "Memory labels and episode enrichment",
        "not_duplicated": "GII does not write or dedupe episodes",
    },
    {
        "artifact": "tae_profit_context_engine.json",
        "role": "PCE verdicts and trend context",
        "not_duplicated": "GII does not score adaptive context",
    },
    {
        "artifact": "tae_profit_decision_governor.json",
        "role": "Governor recommendations",
        "not_duplicated": "GII does not run PDG posture logic",
    },
    {
        "artifact": "tae_portfolio_profit_governor.json / tae_adaptive_profit_policy_engine.json",
        "role": "Portfolio verdict and policy state",
        "not_duplicated": "GII does not evaluate portfolio policy transitions",
    },
]


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


def context_support_score(pce_verdict: str, trend_context: str) -> float:
    score = 50.0
    if pce_verdict in {"KEEP_WINNER", "NORMAL_PULLBACK"}:
        score += 30.0
    elif pce_verdict in {"PROTECT_NOW", "CONTEXT_WEAKENING"}:
        score -= 25.0
    if trend_context == "TREND_HEALTHY":
        score += 15.0
    elif trend_context in {"TREND_WEAK", "TREND_BROKEN"}:
        score -= 20.0
    return clamp(score)


def governor_posture_score(governor_rec: str) -> float:
    upper = governor_rec.upper()
    if upper in {"HOLD", "KEEP"} or "KEEP" in upper:
        return 85.0
    if upper in {"WATCH", "OBSERVE"}:
        return 65.0
    if "PARTIAL" in upper:
        return 45.0
    if "TRAIL" in upper:
        return 35.0
    if "PROTECT" in upper or "EXIT" in upper:
        return 20.0
    return 50.0


def winner_quality_score(
    *,
    lifecycle_stage: str,
    missed_usd: float,
    collapse_probability: float,
    pce_verdict: str,
    growth_status: str,
) -> float:
    stage_base = {
        "SURVIVED": 88.0,
        "EARLY_WINNER": 78.0,
        "MATURE_WINNER": 82.0,
        "PEAK_WINNER": 90.0,
        "DISCOVERY": 55.0,
        "WEAKENING": 38.0,
        "PROFIT_DECAY": 15.0,
        "COLLAPSED": 5.0,
        "UNKNOWN": 40.0,
    }.get(lifecycle_stage, 40.0)
    score = stage_base
    if missed_usd < 25:
        score += 8.0
    elif missed_usd >= 200:
        score -= 25.0
    elif missed_usd >= 75:
        score -= 15.0
    score -= collapse_probability * 30.0
    if pce_verdict in {"KEEP_WINNER", "NORMAL_PULLBACK"}:
        score += 10.0
    if growth_status == "CAPTURED_WINNER":
        score += 8.0
    if growth_status == "MISSED_WINNER":
        score -= 20.0
    return round(clamp(score), 1)


def opportunity_score_value(
    *,
    missed_usd: float,
    opportunity_category: str,
    opportunity_severity: str,
    growth_status: str,
    lifecycle_stage: str,
) -> float:
    score = min(70.0, missed_usd / 4.0)
    if opportunity_severity == "CRITICAL":
        score += 25.0
    elif opportunity_severity == "HIGH":
        score += 15.0
    elif opportunity_severity == "MEDIUM":
        score += 8.0
    if opportunity_category not in {"", "UNKNOWN"}:
        score += 10.0
    if growth_status == "MISSED_WINNER":
        score += 15.0
    if lifecycle_stage in DECAY_LIFECYCLE:
        score += 12.0
    return round(clamp(score), 1)


def capital_efficiency_score(
    *,
    current_pct: float,
    missed_usd: float,
    lifecycle_score: float,
    governor_rec: str,
) -> float:
    score = 40.0
    if current_pct > 0:
        score += min(25.0, current_pct * 4.0)
    else:
        score -= 20.0
    if missed_usd < 25:
        score += 15.0
    elif missed_usd >= 200:
        score -= 30.0
    score += lifecycle_score * 0.25
    score += (governor_posture_score(governor_rec) - 50.0) * 0.3
    return round(clamp(score), 1)


def profit_capture_efficiency(
    *,
    current_pct: float,
    high_pct: float,
    missed_usd: float,
    portfolio_capture_rate: float | None,
) -> float:
    if high_pct > 0 and current_pct >= 0:
        retention = clamp((current_pct / high_pct) * 100.0)
    else:
        retention = 0.0
    theoretical = current_pct + (missed_usd / 100.0) if missed_usd else current_pct
    if theoretical > 0 and high_pct > 0:
        inferred = clamp((current_pct / max(high_pct, theoretical)) * 100.0)
    else:
        inferred = retention
    base = max(retention, inferred)
    if portfolio_capture_rate is not None:
        base = base * 0.7 + portfolio_capture_rate * 100.0 * 0.3
    return round(clamp(base), 1)


def future_growth_potential_score(
    *,
    lifecycle_score: float,
    survival_probability: float,
    collapse_probability: float,
    pce_verdict: str,
    lifecycle_stage: str,
) -> float:
    score = lifecycle_score * 0.45 + survival_probability * 100.0 * 0.35
    score -= collapse_probability * 35.0
    if pce_verdict in {"KEEP_WINNER", "NORMAL_PULLBACK"}:
        score += 12.0
    if lifecycle_stage in DECAY_LIFECYCLE:
        score -= 25.0
    elif lifecycle_stage in HEALTHY_LIFECYCLE:
        score += 8.0
    return round(clamp(score), 1)


def growth_score_composite(
    *,
    lifecycle_score: float,
    winner_quality: float,
    opportunity_score: float,
    capital_efficiency: float,
    profit_capture_efficiency: float,
    future_growth_potential: float,
    context_support: float,
    governor_posture: float,
) -> float:
    raw = (
        lifecycle_score * 0.22
        + winner_quality * 0.18
        + (100.0 - opportunity_score) * 0.14
        + capital_efficiency * 0.14
        + profit_capture_efficiency * 0.12
        + future_growth_potential * 0.12
        + context_support * 0.04
        + governor_posture * 0.04
    )
    return round(clamp(raw), 1)


def growth_confidence(source_hits: int, max_sources: int = 8) -> float:
    return round(clamp(source_hits / max_sources * 100.0, 0.0, 100.0) / 100.0, 2)


def recommended_shadow_strategy(
    *,
    growth_score: float,
    future_growth_potential: float,
    opportunity_score: float,
    lifecycle_stage: str,
    current_pct: float,
    high_pct: float,
    source_hits: int,
) -> str:
    if source_hits < 3:
        return "COLLECT_MORE_DATA"
    if lifecycle_stage == "COLLAPSED" or (current_pct <= 0 and high_pct > 6.0):
        return "REDUCE_EXPOSURE_SHADOW"
    if lifecycle_stage == "PROFIT_DECAY" and current_pct > 0:
        return "TIGHTEN_TRAIL_SHADOW"
    if opportunity_score >= 70 or (
        lifecycle_stage in DECAY_LIFECYCLE and opportunity_score >= 50
    ):
        return "PROTECT_PROFIT_SHADOW"
    if growth_score >= 70 and future_growth_potential >= 65:
        return "KEEP_GROWING_SHADOW"
    if 45 <= growth_score < 70:
        return "HOLD_AND_MONITOR_SHADOW"
    if growth_score < 45 and lifecycle_stage not in DECAY_LIFECYCLE:
        return "HOLD_AND_MONITOR_SHADOW"
    return "PROTECT_PROFIT_SHADOW"


def build_explanation(
    *,
    ticker: str,
    growth_score: float,
    winner_quality: float,
    opportunity_score: float,
    lifecycle_stage: str,
    growth_status: str,
    opportunity_category: str,
    strategy: str,
) -> str:
    return (
        f"{ticker}: growth_score={growth_score:.1f}, winner_quality={winner_quality:.1f}, "
        f"opportunity_score={opportunity_score:.1f}. "
        f"Lifecycle={lifecycle_stage}, growth_status={growth_status}, "
        f"opportunity_category={opportunity_category}. "
        f"Recommended shadow strategy (no execution): {strategy}."
    )


def global_verdict(sources: dict[str, bool]) -> str:
    ga = sources.get("tae_profit_growth_analytics.json", False)
    ledger = sources.get("tae_opportunity_cost_ledger.json", False)
    lifecycle = sources.get("tae_winner_lifecycle_profiler.json", False)
    if ga and ledger and lifecycle:
        return "GROWTH_INTELLIGENCE_READY"
    if ga or ledger or lifecycle:
        return "GROWTH_INTELLIGENCE_NEEDS_MORE_DATA"
    return "GROWTH_INTELLIGENCE_NOT_READY"


def portfolio_shadow_strategy(tickers: list[dict[str, Any]], policy_state: str) -> str:
    if not tickers:
        return "COLLECT_MORE_DATA"
    strategies = [t.get("recommended_shadow_strategy") for t in tickers]
    protect_count = sum(1 for s in strategies if s in {"PROTECT_PROFIT_SHADOW", "REDUCE_EXPOSURE_SHADOW"})
    keep_count = sum(1 for s in strategies if s == "KEEP_GROWING_SHADOW")
    if protect_count >= len(tickers) // 3 or policy_state == "HIGH_RISK":
        return "PROTECT_PROFIT_SHADOW"
    if keep_count >= len(tickers) // 2:
        return "KEEP_GROWING_SHADOW"
    return "HOLD_AND_MONITOR_SHADOW"


def discover_gaps(sources: dict[str, bool], tickers: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    if not sources.get("tae_opportunity_cost_ledger.json"):
        gaps.append("Opportunity ledger missing — opportunity_category degraded")
    if not sources.get("tae_winner_lifecycle_profiler.json"):
        gaps.append("Lifecycle profiler missing — lifecycle fields unavailable")
    low_conf = sum(1 for t in tickers if t.get("growth_confidence", 0) < 0.5)
    if low_conf >= 3:
        gaps.append(f"{low_conf} tickers with low growth_confidence — upstream SSOT sparse")
    if not gaps:
        gaps.append("No critical integration gaps — all three growth layers present")
    return gaps


def build_intelligence() -> dict[str, Any]:
    source_paths = {
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
        "tae_profit_growth_analytics.json": GROWTH_JSON,
        "tae_opportunity_cost_ledger.json": LEDGER_JSON,
        "tae_winner_lifecycle_profiler.json": LIFECYCLE_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
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

    growth = payloads["tae_profit_growth_analytics.json"]
    ledger = payloads["tae_opportunity_cost_ledger.json"]
    lifecycle = payloads["tae_winner_lifecycle_profiler.json"]
    memory = payloads["tae_profit_memory_engine.json"]
    context = payloads["tae_profit_context_engine.json"]
    pdg = payloads["tae_profit_decision_governor.json"]
    appe = payloads["tae_adaptive_profit_policy_engine.json"]
    ppg = payloads["tae_portfolio_profit_governor.json"]

    growth_by = {
        _s(r.get("ticker")).upper(): r for r in (growth or {}).get("tickers") or [] if r.get("ticker")
    }
    ledger_by = {
        _s(e.get("ticker")).upper(): e for e in (ledger or {}).get("ledger") or [] if e.get("ticker")
    }
    lifecycle_by = {
        _s(p.get("ticker")).upper(): p for p in (lifecycle or {}).get("profiles") or [] if p.get("ticker")
    }
    memory_by = {
        _s(e.get("ticker")).upper(): e for e in (memory or {}).get("episodes") or [] if e.get("ticker")
    }
    context_by = {
        _s(r.get("ticker")).upper(): r for r in (context or {}).get("tickers") or [] if r.get("ticker")
    }
    pdg_by = {
        _s(r.get("ticker")).upper(): r for r in (pdg or {}).get("ticker_postures") or [] if r.get("ticker")
    }

    tickers_universe = sorted(
        set(growth_by) | set(ledger_by) | set(lifecycle_by) | set(pdg_by)
    )

    core = (growth or {}).get("core_metrics") or {}
    portfolio_capture = core.get("profit_capture_rate")
    opportunity_total = _f((ledger or {}).get("global_summary", {}).get("total_opportunity_cost_usd"))
    if not opportunity_total:
        opportunity_total = _f(core.get("aggregate_missed_usd"))

    policy = (appe or {}).get("latest_observation") or {}
    policy_state = _s(policy.get("policy_state"), _s((ppg or {}).get("portfolio_verdict")))

    ticker_rows: list[dict[str, Any]] = []
    for ticker in tickers_universe:
        ga = growth_by.get(ticker) or {}
        led = ledger_by.get(ticker) or {}
        lc = lifecycle_by.get(ticker) or {}
        mem = memory_by.get(ticker) or {}
        ctx = context_by.get(ticker) or {}
        gov = pdg_by.get(ticker) or {}

        source_hits = sum(
            1 for src in (ga, led, lc, mem, ctx, gov) if src
        ) + (1 if growth else 0) + (1 if ledger else 0) + (1 if lifecycle else 0)

        current_pct = _f(ga.get("current_pct"), _f(lc.get("current_pct")))
        high_pct = _f(ga.get("high_pct"), _f(lc.get("highest_pct")))
        drawdown = _f(ga.get("drawdown"), _f(lc.get("drawdown_pct")))
        missed_usd = round(_f(ga.get("missed_usd"), _f(lc.get("missed_usd"))), 2)
        growth_status = _s(ga.get("growth_status"), _s((lc.get("enrichment") or {}).get("growth_status")))
        opportunity_category = _s(led.get("opportunity_cost_category"))
        opportunity_severity = _s(led.get("opportunity_cost_severity"))
        lifecycle_stage = _s(lc.get("lifecycle_stage"))
        lifecycle_score = _f(lc.get("lifecycle_score"))
        collapse_probability = _f(lc.get("collapse_probability"))
        survival_probability = _f(lc.get("survival_probability"))
        governor_rec = _s(ga.get("governor_recommendation"), _s(gov.get("final_shadow_recommendation")))
        pce_verdict = _s(ga.get("pce_verdict"), _s(ctx.get("context_verdict")))
        memory_label = _s(ga.get("memory_label"), _s(mem.get("memory_label")))
        trend_context = _s((ctx.get("components") or {}).get("trend_context"))

        ctx_support = context_support_score(pce_verdict, trend_context)
        gov_posture = governor_posture_score(governor_rec)
        wq = winner_quality_score(
            lifecycle_stage=lifecycle_stage,
            missed_usd=missed_usd,
            collapse_probability=collapse_probability,
            pce_verdict=pce_verdict,
            growth_status=growth_status,
        )
        opp = opportunity_score_value(
            missed_usd=missed_usd,
            opportunity_category=opportunity_category,
            opportunity_severity=opportunity_severity,
            growth_status=growth_status,
            lifecycle_stage=lifecycle_stage,
        )
        cap_eff = capital_efficiency_score(
            current_pct=current_pct,
            missed_usd=missed_usd,
            lifecycle_score=lifecycle_score,
            governor_rec=governor_rec,
        )
        pce_eff = profit_capture_efficiency(
            current_pct=current_pct,
            high_pct=high_pct,
            missed_usd=missed_usd,
            portfolio_capture_rate=portfolio_capture if portfolio_capture is not None else None,
        )
        future_pot = future_growth_potential_score(
            lifecycle_score=lifecycle_score,
            survival_probability=survival_probability,
            collapse_probability=collapse_probability,
            pce_verdict=pce_verdict,
            lifecycle_stage=lifecycle_stage,
        )
        g_score = growth_score_composite(
            lifecycle_score=lifecycle_score,
            winner_quality=wq,
            opportunity_score=opp,
            capital_efficiency=cap_eff,
            profit_capture_efficiency=pce_eff,
            future_growth_potential=future_pot,
            context_support=ctx_support,
            governor_posture=gov_posture,
        )
        confidence = growth_confidence(source_hits)
        strategy = recommended_shadow_strategy(
            growth_score=g_score,
            future_growth_potential=future_pot,
            opportunity_score=opp,
            lifecycle_stage=lifecycle_stage,
            current_pct=current_pct,
            high_pct=high_pct,
            source_hits=source_hits,
        )
        explanation = build_explanation(
            ticker=ticker,
            growth_score=g_score,
            winner_quality=wq,
            opportunity_score=opp,
            lifecycle_stage=lifecycle_stage,
            growth_status=growth_status,
            opportunity_category=opportunity_category,
            strategy=strategy,
        )

        ticker_rows.append(
            {
                "ticker": ticker,
                "current_pct": round(current_pct, 2),
                "high_pct": round(high_pct, 2),
                "drawdown": round(drawdown, 2),
                "missed_usd": missed_usd,
                "growth_status": growth_status,
                "opportunity_category": opportunity_category,
                "lifecycle_stage": lifecycle_stage,
                "lifecycle_score": round(lifecycle_score, 1),
                "collapse_probability": round(collapse_probability, 3),
                "survival_probability": round(survival_probability, 3),
                "governor_recommendation": governor_rec,
                "pce_verdict": pce_verdict,
                "memory_label": memory_label,
                "growth_score": g_score,
                "growth_confidence": confidence,
                "winner_quality": wq,
                "opportunity_score": opp,
                "capital_efficiency": cap_eff,
                "profit_capture_efficiency": pce_eff,
                "future_growth_potential": future_pot,
                "recommended_shadow_strategy": strategy,
                "explanation": explanation,
            }
        )

    ticker_rows.sort(key=lambda r: r.get("growth_score", 0), reverse=True)
    n = len(ticker_rows) or 1

    avg_growth = round(sum(t["growth_score"] for t in ticker_rows) / n, 1)
    avg_wq = round(sum(t["winner_quality"] for t in ticker_rows) / n, 1)
    avg_cap = round(sum(t["capital_efficiency"] for t in ticker_rows) / n, 1)
    avg_opp = round(sum(t["opportunity_score"] for t in ticker_rows) / n, 1)
    avg_collapse = round(sum(t["collapse_probability"] for t in ticker_rows) / n, 3)
    healthy_count = sum(1 for t in ticker_rows if t["lifecycle_stage"] in HEALTHY_LIFECYCLE)
    winner_concentration = round(healthy_count / n * 100.0, 1)
    mature_count = sum(
        1
        for t in ticker_rows
        if t["lifecycle_stage"] in {"MATURE_WINNER", "PEAK_WINNER", "SURVIVED"}
    )
    growth_maturity = round(mature_count / n * 100.0, 1)
    growth_risk = round(avg_opp * 0.4 + avg_collapse * 100.0 * 0.6, 1)

    top_growth = sorted(ticker_rows, key=lambda t: t["growth_score"], reverse=True)[:5]
    top_risk = sorted(
        ticker_rows,
        key=lambda t: (t["opportunity_score"], t["collapse_probability"]),
        reverse=True,
    )[:5]
    top_missed = sorted(ticker_rows, key=lambda t: t["missed_usd"], reverse=True)[:5]

    portfolio_strategy = portfolio_shadow_strategy(ticker_rows, policy_state)
    verdict = global_verdict(sources_loaded)
    gaps = discover_gaps(sources_loaded, ticker_rows)

    return {
        "schema": "tae_growth_intelligence",
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
        "duplicate_audit": {
            "phase0_commands_run": True,
            "similar_files_found": [
                "tae_profit_growth_analytics.py",
                "tae_opportunity_cost_ledger.py",
                "tae_winner_lifecycle_profiler.py",
                "tae_profit_intelligence_brain.py",
                "missed_winners_audit.py",
            ],
            "no_existing_integrator": True,
            "reuse_decision": "Read upstream JSON artifacts only; no re-import of upstream Python modules",
            "why_not_duplicate": (
                "GII is a meta-aggregator over GA + ledger + lifecycle outputs. "
                "It does not recompute capture rates, opportunity categories, or lifecycle stages."
            ),
        },
        "integration_model": {
            "layers": ["Accounting", "Growth Analytics", "Opportunity Ledger", "Winner Lifecycle", "Memory", "Context", "PDG", "PPG", "APPE"],
            "upstream_reuse": UPSTREAM_REUSE,
            "shadow_strategies": sorted(SHADOW_STRATEGIES),
        },
        "scoring_model": {
            "growth_score": "Weighted blend of lifecycle, winner_quality, inverse opportunity, capital/capture efficiency, future potential, context, governor",
            "winner_quality": "Lifecycle stage + low missed + low collapse + supportive PCE",
            "opportunity_score": "Missed USD + severity + MISSED_WINNER + decay lifecycle",
            "capital_efficiency": "Positive current + low missed + lifecycle + governor HOLD/KEEP",
            "profit_capture_efficiency": "Peak retention inferred from current/high/missed + portfolio capture rate",
            "future_growth_potential": "Lifecycle score + survival − collapse + PCE support",
        },
        "global_verdict": verdict,
        "portfolio": {
            "global_growth_score": avg_growth,
            "portfolio_growth_quality": round((avg_wq + _f(core.get("profit_quality_score"))) / 2.0, 1),
            "capital_efficiency": avg_cap,
            "opportunity_index": avg_opp,
            "winner_concentration_pct": winner_concentration,
            "growth_risk": growth_risk,
            "growth_maturity_pct": growth_maturity,
            "profit_capture_rate": portfolio_capture,
            "opportunity_cost_total": round(opportunity_total, 2),
            "top_growth_candidates": [t["ticker"] for t in top_growth],
            "top_risk_candidates": [t["ticker"] for t in top_risk],
            "top_missed_winners": [t["ticker"] for t in top_missed],
            "recommended_portfolio_shadow_strategy": portfolio_strategy,
            "portfolio_verdict": core.get("portfolio_verdict") or (ppg or {}).get("portfolio_verdict"),
            "policy_state": policy_state,
            "suggested_shadow_policy": policy.get("suggested_shadow_policy") or core.get("suggested_shadow_policy"),
        },
        "tickers": ticker_rows,
        "top_growth_candidates": top_growth,
        "top_risk_candidates": top_risk,
        "top_missed_winners": top_missed,
        "true_remaining_gaps": gaps,
        "recommended_next_sprint": "X.PROFIT-GROWTH-5 — Dynamic Profit Target Optimizer",
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    p = report["portfolio"]
    lines = [
        "# TAE Growth Intelligence Integrator",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Global verdict:** {report['global_verdict']}",
        "",
        "> **SHADOW_ONLY unified Profit Growth Intelligence — read-only aggregation**",
        "",
        "## Executive summary",
        "",
        f"- Global growth score: **{p.get('global_growth_score')}** / 100",
        f"- Portfolio growth quality: **{p.get('portfolio_growth_quality')}**",
        f"- Profit capture rate: **{p.get('profit_capture_rate')}**",
        f"- Opportunity cost total: **${p.get('opportunity_cost_total')}**",
        f"- Growth risk index: **{p.get('growth_risk')}**",
        f"- Recommended portfolio strategy: **{p.get('recommended_portfolio_shadow_strategy')}**",
        f"- Tickers integrated: **{len(report.get('tickers') or [])}**",
        "",
        "## Sources loaded",
        "",
    ]
    for key, loaded in sorted((report.get("sources_loaded") or {}).items()):
        mark = "✅" if loaded else "❌"
        lines.append(f"- {mark} {key}")

    lines.extend(
        [
            "",
            "## Portfolio growth metrics",
            "",
            "| metric | value |",
            "| --- | --- |",
        ]
    )
    for key, value in p.items():
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Top growth candidates", "", "| ticker | growth_score | winner_quality | strategy |", "| --- | --- | --- | --- |"])
    for row in report.get("top_growth_candidates") or []:
        lines.append(
            f"| {row['ticker']} | {row['growth_score']} | {row['winner_quality']} | "
            f"{row['recommended_shadow_strategy']} |"
        )

    lines.extend(["", "## Top risk candidates", "", "| ticker | opportunity | collapse | lifecycle | strategy |", "| --- | --- | --- | --- | --- |"])
    for row in report.get("top_risk_candidates") or []:
        lines.append(
            f"| {row['ticker']} | {row['opportunity_score']} | {row['collapse_probability']} | "
            f"{row['lifecycle_stage']} | {row['recommended_shadow_strategy']} |"
        )

    lines.extend(["", "## Top missed winners", "", "| ticker | missed USD | category | growth_status |", "| --- | --- | --- | --- |"])
    for row in report.get("top_missed_winners") or []:
        lines.append(
            f"| {row['ticker']} | ${row['missed_usd']} | {row['opportunity_category']} | {row['growth_status']} |"
        )

    lines.extend(
        [
            "",
            "## Per-ticker growth intelligence table",
            "",
            "| ticker | growth | winner Q | opp | lifecycle | stage | strategy | conf |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("tickers") or []:
        lines.append(
            f"| {row['ticker']} | {row['growth_score']} | {row['winner_quality']} | {row['opportunity_score']} | "
            f"{row['lifecycle_score']} | {row['lifecycle_stage']} | {row['recommended_shadow_strategy']} | "
            f"{row['growth_confidence']} |"
        )

    lines.extend(["", "## Recommended shadow strategies", ""])
    strat_counts: dict[str, int] = defaultdict(int)
    for row in report.get("tickers") or []:
        strat_counts[row["recommended_shadow_strategy"]] += 1
    lines.append("| strategy | count |")
    lines.append("| --- | --- |")
    for strat, count in sorted(strat_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {strat} | {count} |")

    lines.extend(["", "## What this reuses", ""])
    for item in report.get("integration_model", {}).get("upstream_reuse") or UPSTREAM_REUSE:
        lines.append(f"- **{item['artifact']}** — {item['role']}")

    audit = report.get("duplicate_audit") or {}
    lines.extend(
        [
            "",
            "## What this does not duplicate",
            "",
            f"- {audit.get('why_not_duplicate', '')}",
            "",
            "**Reuse decision:** " + _s(audit.get("reuse_decision")),
            "",
            "## True remaining gaps",
            "",
        ]
    )
    for gap in report.get("true_remaining_gaps") or []:
        lines.append(f"- {gap}")

    lines.extend(
        [
            "",
            "## Recommended next sprint",
            "",
            f"**{report.get('recommended_next_sprint')}**",
            "",
            "## Safety confirmation",
            "",
            "- SHADOW_ONLY: **true**",
            "- READ_ONLY: **true**",
            "- NO_BROKER: **true**",
            "- NO_LIVE_EXECUTION_CHANGE: **true**",
            "- NO_ADVISORY_CHANGE: **true**",
            "- portfolio.csv modified: **false**",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    p = report["portfolio"]
    print("===== TAE GROWTH INTELLIGENCE INTEGRATOR =====")
    print("Mode: SHADOW_ONLY — read-only aggregation")
    print("Global verdict:", report["global_verdict"])
    print("Global growth score:", p.get("global_growth_score"))
    print("Portfolio strategy:", p.get("recommended_portfolio_shadow_strategy"))
    print("Top growth:", ", ".join(p.get("top_growth_candidates") or []))
    print("Top risk:", ", ".join(p.get("top_risk_candidates") or []))
    print("Tickers:", len(report.get("tickers") or []))


def main() -> int:
    report = build_intelligence()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
