#!/usr/bin/env python3
"""
TAE Winner Lifecycle Profiler — SHADOW_ONLY / READ_ONLY.

Research layer modeling how winners are born, grow, weaken, and die.
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
MEMORY_JSON = Path("tae_profit_memory_engine.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
FADE_SUMMARY_MD = Path("tae_intraday_fade_history_summary.md")
BOT_LOG = Path("bot_output.log")
SHADOW_EVENTS_CSV = Path("tae_shadow_validation_events.csv")

OUTPUT_JSON = Path("tae_winner_lifecycle_profiler.json")
OUTPUT_MD = Path("tae_winner_lifecycle_profiler.md")

LIFECYCLE_STAGES = frozenset(
    {
        "DISCOVERY",
        "EARLY_WINNER",
        "MATURE_WINNER",
        "PEAK_WINNER",
        "WEAKENING",
        "PROFIT_DECAY",
        "COLLAPSED",
        "SURVIVED",
        "UNKNOWN",
    }
)

SHADOW_ACTIONS = frozenset({"KEEP", "WATCH", "PARTIAL_PROTECT", "TRAIL", "PROTECT", "EXIT", "UNKNOWN"})

HEALTHY_STAGES = frozenset({"DISCOVERY", "EARLY_WINNER", "MATURE_WINNER", "PEAK_WINNER", "SURVIVED"})
WEAKENING_STAGES = frozenset({"WEAKENING"})
COLLAPSING_STAGES = frozenset({"PROFIT_DECAY"})
DEAD_STAGES = frozenset({"COLLAPSED"})


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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def profit_age_days(memory_ep: dict[str, Any] | None, shadow_pos: dict[str, Any] | None) -> float:
    captured = (memory_ep or {}).get("captured_at")
    if captured:
        try:
            ts = datetime.fromisoformat(str(captured))
            delta = datetime.now() - ts
            return max(0.25, delta.total_seconds() / 86400.0)
        except (TypeError, ValueError):
            pass
    rules = (shadow_pos or {}).get("rules_v1") or {}
    fade = _f(rules.get("fade_from_peak_pct"))
    if fade > 0:
        return max(0.5, min(30.0, fade / 2.0))
    high = _f((shadow_pos or {}).get("high_pct"))
    if high >= 6:
        return 14.0
    if high >= 3:
        return 7.0
    return 3.0


def classify_lifecycle_stage(
    *,
    current_pct: float,
    highest_pct: float,
    drawdown_pct: float,
    missed_usd: float,
    memory_label: str,
    growth_status: str,
) -> str:
    dd = abs(drawdown_pct) if drawdown_pct < 0 else drawdown_pct

    if current_pct <= 0 and highest_pct > 6.0:
        return "COLLAPSED"
    if memory_label == "PROFIT_COLLAPSED" and highest_pct > 6.0 and current_pct <= 1.0:
        if current_pct <= 0:
            return "COLLAPSED"
        return "PROFIT_DECAY"
    if dd > 5.0 or drawdown_pct <= -5.0:
        return "PROFIT_DECAY"
    if dd > 2.0 or drawdown_pct <= -2.0:
        return "WEAKENING"
    if (
        memory_label == "PROFIT_SURVIVED"
        or growth_status == "CAPTURED_WINNER"
    ) and highest_pct >= 1.0 and abs(highest_pct - current_pct) <= 0.75 and current_pct > 0:
        return "SURVIVED"
    if current_pct > 6.0:
        return "PEAK_WINNER"
    if 3.0 <= current_pct <= 6.0:
        return "MATURE_WINNER"
    if 1.0 <= current_pct < 3.0:
        return "EARLY_WINNER"
    if highest_pct < 1.0:
        return "DISCOVERY"
    if highest_pct > 6.0 and current_pct <= 1.0:
        return "PROFIT_DECAY"
    if current_pct > 0:
        return "EARLY_WINNER" if current_pct < 3.0 else "MATURE_WINNER"
    return "UNKNOWN"


def collapse_probability(
    *,
    memory_ep: dict[str, Any] | None,
    pce_verdict: str,
    growth_status: str,
    ledger_category: str,
    validation_verdict: str | None,
    drawdown_pct: float,
    missed_usd: float,
    stage: str,
) -> float:
    score = 0.15
    giveback = _f((memory_ep or {}).get("psp_giveback_risk"))
    if giveback:
        score = max(score, giveback * 0.55)

    if memory_ep and _s(memory_ep.get("memory_label")) == "PROFIT_COLLAPSED":
        score += 0.25
    if pce_verdict in {"PROTECT_NOW", "CONTEXT_WEAKENING"}:
        score += 0.15
    if growth_status in {"MISSED_WINNER", "PROFIT_DECAY"}:
        score += 0.12
    if ledger_category in {"MARKET_CONTEXT_REVERSAL", "PROFIT_GIVEBACK", "HOLD_TOO_LONG"}:
        score += 0.1
    if validation_verdict and "NOT_READY" in validation_verdict.upper():
        score += 0.05

    dd = abs(min(0.0, drawdown_pct))
    score += min(0.2, dd / 40.0)
    score += min(0.15, missed_usd / 1500.0)

    if stage in DEAD_STAGES:
        score = max(score, 0.92)
    elif stage in COLLAPSING_STAGES:
        score = max(score, 0.75)
    elif stage in WEAKENING_STAGES:
        score = max(score, 0.45)
    elif stage in HEALTHY_STAGES:
        score = min(score, 0.35)

    return round(clamp(score), 3)


def survival_probability(
    *,
    memory_ep: dict[str, Any] | None,
    pce_verdict: str,
    trend_context: str,
    drawdown_pct: float,
    current_pct: float,
    stage: str,
) -> float:
    base = _f((memory_ep or {}).get("psp_survival_probability"), 0.5)
    score = base if base else 0.5

    if _s(memory_ep.get("memory_label") if memory_ep else "") == "PROFIT_SURVIVED":
        score += 0.2
    if pce_verdict in {"KEEP_WINNER", "NORMAL_PULLBACK"}:
        score += 0.15
    if trend_context == "TREND_HEALTHY":
        score += 0.1
    elif trend_context in {"TREND_WEAK", "TREND_BROKEN"}:
        score -= 0.15

    dd = abs(min(0.0, drawdown_pct))
    score -= min(0.35, dd / 25.0)
    if current_pct <= 0:
        score -= 0.25
    if stage == "SURVIVED":
        score += 0.15
    if stage in DEAD_STAGES:
        score = min(score, 0.08)
    elif stage in COLLAPSING_STAGES:
        score = min(score, 0.25)

    return round(clamp(score), 3)


def lifecycle_score(
    *,
    stage: str,
    current_pct: float,
    highest_pct: float,
    survival: float,
    collapse: float,
) -> float:
    stage_base = {
        "PEAK_WINNER": 92.0,
        "MATURE_WINNER": 80.0,
        "EARLY_WINNER": 68.0,
        "SURVIVED": 75.0,
        "DISCOVERY": 55.0,
        "WEAKENING": 42.0,
        "PROFIT_DECAY": 18.0,
        "COLLAPSED": 5.0,
        "UNKNOWN": 35.0,
    }.get(stage, 35.0)

    peak_retention = (current_pct / highest_pct) if highest_pct > 0 else 0.0
    retention_bonus = clamp(peak_retention, 0.0, 1.0) * 15.0
    score = stage_base + retention_bonus + survival * 20.0 - collapse * 35.0
    return round(clamp(score, 0.0, 100.0), 1)


def map_governor_to_action(governor_rec: str) -> str:
    upper = governor_rec.upper()
    if "PARTIAL" in upper:
        return "PARTIAL_PROTECT"
    if "TRAIL" in upper:
        return "TRAIL"
    if "PROTECT" in upper or "EXIT" in upper:
        return "PROTECT" if "EXIT" not in upper else "EXIT"
    if upper in {"HOLD", "KEEP"} or "KEEP" in upper:
        return "KEEP"
    if upper in {"WATCH", "OBSERVE"}:
        return "WATCH"
    return "UNKNOWN"


def optimal_shadow_action(
    *,
    stage: str,
    governor_rec: str,
    pce_verdict: str,
    collapse: float,
    survival: float,
) -> str:
    gov_action = map_governor_to_action(governor_rec)
    if stage == "COLLAPSED":
        return "EXIT"
    if stage == "PROFIT_DECAY" or collapse >= 0.7:
        return gov_action if gov_action != "UNKNOWN" else "PROTECT"
    if stage == "WEAKENING":
        if gov_action in {"PARTIAL_PROTECT", "TRAIL", "PROTECT"}:
            return gov_action
        return "TRAIL" if pce_verdict == "CONTEXT_WEAKENING" else "WATCH"
    if stage == "PEAK_WINNER":
        return gov_action if gov_action != "UNKNOWN" else "PARTIAL_PROTECT"
    if stage in {"MATURE_WINNER", "EARLY_WINNER", "SURVIVED"}:
        if survival >= 0.6 and pce_verdict == "KEEP_WINNER":
            return "KEEP"
        return gov_action if gov_action != "UNKNOWN" else "WATCH"
    if stage == "DISCOVERY":
        return "WATCH"
    return gov_action


def build_explanation(
    *,
    ticker: str,
    stage: str,
    current_pct: float,
    highest_pct: float,
    drawdown_pct: float,
    growth_velocity: float,
    profit_decay_velocity: float,
    collapse: float,
    survival: float,
    optimal_action: str,
    memory_label: str,
    pce_verdict: str,
) -> str:
    stage_desc = {
        "DISCOVERY": "Winner not yet born — peak below 1%, still in discovery.",
        "EARLY_WINNER": "Winner born — early growth phase (1–3%).",
        "MATURE_WINNER": "Winner growing — mature phase (3–6%).",
        "PEAK_WINNER": "Winner at peak — above 6% and still elevated.",
        "WEAKENING": "Winner weakening — drawdown exceeds 2% from peak.",
        "PROFIT_DECAY": "Winner dying — severe giveback (>5% drawdown from peak).",
        "COLLAPSED": "Winner dead — flat or negative after a >6% peak.",
        "SURVIVED": "Winner survived — peak near current with profit retained.",
        "UNKNOWN": "Lifecycle unclear — insufficient signals.",
    }
    return (
        f"{ticker} lifecycle={stage}: {stage_desc.get(stage, stage_desc['UNKNOWN'])} "
        f"Current {current_pct:.2f}% vs peak {highest_pct:.2f}% (drawdown {drawdown_pct:.2f}%). "
        f"Growth velocity {growth_velocity:.3f}%/day, decay velocity {profit_decay_velocity:.3f}%/day. "
        f"Collapse prob {collapse:.2f}, survival prob {survival:.2f}. "
        f"Memory={memory_label}, PCE={pce_verdict}. "
        f"Optimal shadow action (no execution): {optimal_action}."
    )


def global_verdict(sources: dict[str, bool], ticker_count: int) -> str:
    if not sources.get("tae_profit_growth_analytics.json"):
        return "LIFECYCLE_PROFILER_NOT_READY"
    if ticker_count >= 1:
        return "LIFECYCLE_PROFILER_READY"
    return "LIFECYCLE_PROFILER_NEEDS_MORE_DATA"


def build_profiler() -> dict[str, Any]:
    source_paths = {
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
        "tae_profit_growth_analytics.json": GROWTH_JSON,
        "tae_opportunity_cost_ledger.json": LEDGER_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_intraday_fade_history_summary.md": FADE_SUMMARY_MD,
        "bot_output.log": BOT_LOG,
        "tae_shadow_validation_events.csv": SHADOW_EVENTS_CSV,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        if key.endswith((".md", ".csv", ".log")):
            sources_loaded[key] = path.is_file()
            payloads[key] = None
            continue
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data

    growth = payloads["tae_profit_growth_analytics.json"]
    ledger = payloads["tae_opportunity_cost_ledger.json"]
    memory = payloads["tae_profit_memory_engine.json"]
    context = payloads["tae_profit_context_engine.json"]
    pdg = payloads["tae_profit_decision_governor.json"]
    shadow = payloads["tae_profit_protection_shadow.json"]
    validation = payloads["tae_profit_protection_validation.json"]

    memory_by = {
        _s(e.get("ticker")).upper(): e for e in (memory or {}).get("episodes") or [] if e.get("ticker")
    }
    context_by = {
        _s(r.get("ticker")).upper(): r for r in (context or {}).get("tickers") or [] if r.get("ticker")
    }
    pdg_by = {
        _s(r.get("ticker")).upper(): r for r in (pdg or {}).get("ticker_postures") or [] if r.get("ticker")
    }
    shadow_by = {
        _s(p.get("ticker")).upper(): p for p in (shadow or {}).get("positions") or [] if p.get("ticker")
    }
    ledger_by = {
        _s(e.get("ticker")).upper(): e for e in (ledger or {}).get("ledger") or [] if e.get("ticker")
    }

    growth_tickers = (growth or {}).get("tickers") or []
    validation_verdict = _s((validation or {}).get("verdict"), "")

    profiles: list[dict[str, Any]] = []
    for row in growth_tickers:
        ticker = _s(row.get("ticker")).upper()
        current_pct = _f(row.get("current_pct"))
        highest_pct = _f(row.get("high_pct"))
        drawdown_pct = _f(row.get("drawdown"))
        missed_usd = round(_f(row.get("missed_usd")), 2)
        growth_status = _s(row.get("growth_status"))

        mem = memory_by.get(ticker)
        ctx = context_by.get(ticker) or {}
        gov = pdg_by.get(ticker) or {}
        sh = shadow_by.get(ticker)
        led = ledger_by.get(ticker) or {}

        memory_label = _s(row.get("memory_label"), _s((mem or {}).get("memory_label")))
        pce_verdict = _s(row.get("pce_verdict"), _s(ctx.get("context_verdict")))
        governor_rec = _s(row.get("governor_recommendation"), _s(gov.get("final_shadow_recommendation")))
        ledger_category = _s(led.get("opportunity_cost_category"))
        trend_context = _s((ctx.get("components") or {}).get("trend_context"), "UNKNOWN")

        age = profit_age_days(mem, sh)
        growth_velocity = round(current_pct / age if age > 0 else current_pct, 4)
        profit_decay_velocity = round(abs(min(0.0, drawdown_pct)) / age if age > 0 else 0.0, 4)

        stage = classify_lifecycle_stage(
            current_pct=current_pct,
            highest_pct=highest_pct,
            drawdown_pct=drawdown_pct,
            missed_usd=missed_usd,
            memory_label=memory_label,
            growth_status=growth_status,
        )
        collapse = collapse_probability(
            memory_ep=mem,
            pce_verdict=pce_verdict,
            growth_status=growth_status,
            ledger_category=ledger_category,
            validation_verdict=validation_verdict or None,
            drawdown_pct=drawdown_pct,
            missed_usd=missed_usd,
            stage=stage,
        )
        survival = survival_probability(
            memory_ep=mem,
            pce_verdict=pce_verdict,
            trend_context=trend_context,
            drawdown_pct=drawdown_pct,
            current_pct=current_pct,
            stage=stage,
        )
        lc_score = lifecycle_score(
            stage=stage,
            current_pct=current_pct,
            highest_pct=highest_pct,
            survival=survival,
            collapse=collapse,
        )
        action = optimal_shadow_action(
            stage=stage,
            governor_rec=governor_rec,
            pce_verdict=pce_verdict,
            collapse=collapse,
            survival=survival,
        )
        confidence = round(clamp(0.4 + (1.0 - abs(collapse - survival)) * 0.35 + (0.1 if mem else 0)), 2)
        explanation = build_explanation(
            ticker=ticker,
            stage=stage,
            current_pct=current_pct,
            highest_pct=highest_pct,
            drawdown_pct=drawdown_pct,
            growth_velocity=growth_velocity,
            profit_decay_velocity=profit_decay_velocity,
            collapse=collapse,
            survival=survival,
            optimal_action=action,
            memory_label=memory_label,
            pce_verdict=pce_verdict,
        )

        profiles.append(
            {
                "ticker": ticker,
                "current_pct": round(current_pct, 2),
                "highest_pct": round(highest_pct, 2),
                "drawdown_pct": round(drawdown_pct, 2),
                "missed_usd": missed_usd,
                "profit_age_days": round(age, 2),
                "growth_velocity": growth_velocity,
                "profit_decay_velocity": profit_decay_velocity,
                "lifecycle_stage": stage,
                "lifecycle_score": lc_score,
                "collapse_probability": collapse,
                "survival_probability": survival,
                "optimal_shadow_action": action,
                "confidence": confidence,
                "explanation": explanation,
                "enrichment": {
                    "growth_status": growth_status,
                    "memory_label": memory_label,
                    "pce_verdict": pce_verdict,
                    "governor_recommendation": governor_rec,
                    "ledger_category": ledger_category,
                    "trend_context": trend_context,
                },
            }
        )

    profiles.sort(key=lambda p: p.get("lifecycle_score", 0), reverse=True)

    stage_counts: dict[str, int] = defaultdict(int)
    for p in profiles:
        stage_counts[p["lifecycle_stage"]] += 1

    healthy = [p for p in profiles if p["lifecycle_stage"] in HEALTHY_STAGES]
    weakening = [p for p in profiles if p["lifecycle_stage"] in WEAKENING_STAGES]
    collapsed = [p for p in profiles if p["lifecycle_stage"] in DEAD_STAGES]
    collapsing = [p for p in profiles if p["lifecycle_stage"] in COLLAPSING_STAGES]
    survived = [p for p in profiles if p["lifecycle_stage"] == "SURVIVED"]

    n = len(profiles) or 1
    avg_lc = round(sum(p["lifecycle_score"] for p in profiles) / n, 1)
    avg_survival = round(sum(p["survival_probability"] for p in profiles) / n, 3)
    avg_collapse = round(sum(p["collapse_probability"] for p in profiles) / n, 3)
    portfolio_lc_score = round(avg_lc * (1.0 - avg_collapse * 0.3), 1)

    seen: set[str] = set()
    top_survivors: list[dict[str, Any]] = []
    for p in sorted(survived + healthy, key=lambda x: x["survival_probability"], reverse=True):
        if p["ticker"] in seen:
            continue
        seen.add(p["ticker"])
        top_survivors.append(p)
        if len(top_survivors) >= 5:
            break
    top_collapse = sorted(
        collapsing + collapsed + weakening,
        key=lambda p: p["collapse_probability"],
        reverse=True,
    )[:5]

    verdict = global_verdict(sources_loaded, len(profiles))
    recommended_next = "X.PROFIT-GROWTH-4 — Dynamic Profit Target Optimizer"

    return {
        "schema": "tae_winner_lifecycle_profiler",
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
        "global_verdict": verdict,
        "lifecycle_model": {
            "stages": sorted(LIFECYCLE_STAGES),
            "shadow_actions": sorted(SHADOW_ACTIONS),
            "stage_rules": {
                "DISCOVERY": "highest_pct < 1%",
                "EARLY_WINNER": "current 1–3%",
                "MATURE_WINNER": "current 3–6%",
                "PEAK_WINNER": "current > 6%",
                "WEAKENING": "drawdown > 2% from peak",
                "PROFIT_DECAY": "drawdown > 5% from peak",
                "COLLAPSED": "current <= 0 after highest > 6%",
                "SURVIVED": "peak ≈ current with profit retained",
            },
        },
        "global_analytics": {
            "average_lifecycle_score": avg_lc,
            "average_survival_probability": avg_survival,
            "average_collapse_probability": avg_collapse,
            "portfolio_lifecycle_score": portfolio_lc_score,
            "number_of_healthy_winners": len(healthy),
            "number_of_weakening_winners": len(weakening),
            "number_of_collapsing_winners": len(collapsing),
            "number_of_collapsed_winners": len(collapsed),
            "number_of_survived_winners": len(survived),
            "lifecycle_distribution": dict(sorted(stage_counts.items())),
            "tickers_profiled": len(profiles),
        },
        "healthy_winners": healthy,
        "weakening_winners": weakening,
        "collapsed_winners": collapsed,
        "top_survivors": top_survivors,
        "top_collapse_candidates": top_collapse,
        "recommended_shadow_actions": {
            p["ticker"]: p["optimal_shadow_action"] for p in profiles if p["optimal_shadow_action"] != "UNKNOWN"
        },
        "profiles": profiles,
        "recommended_next_sprint": recommended_next,
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    ga = report["global_analytics"]
    lines = [
        "# TAE Winner Lifecycle Profiler",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Global verdict:** {report['global_verdict']}",
        "",
        "> **SHADOW_ONLY research layer — how winners are born, grow, weaken, and die**",
        "",
        "## Executive summary",
        "",
        f"- Tickers profiled: **{ga.get('tickers_profiled')}**",
        f"- Portfolio lifecycle score: **{ga.get('portfolio_lifecycle_score')}** / 100",
        f"- Average lifecycle score: **{ga.get('average_lifecycle_score')}**",
        f"- Average survival probability: **{ga.get('average_survival_probability')}**",
        f"- Average collapse probability: **{ga.get('average_collapse_probability')}**",
        f"- Healthy winners: **{ga.get('number_of_healthy_winners')}** | "
        f"Weakening: **{ga.get('number_of_weakening_winners')}** | "
        f"Collapsing: **{ga.get('number_of_collapsing_winners')}** | "
        f"Collapsed: **{ga.get('number_of_collapsed_winners')}** | "
        f"Survived: **{ga.get('number_of_survived_winners')}**",
        "",
        "## Lifecycle distribution",
        "",
        "| stage | count |",
        "| --- | --- |",
    ]
    for stage, count in sorted((ga.get("lifecycle_distribution") or {}).items()):
        lines.append(f"| {stage} | {count} |")

    lines.extend(["", "## Healthy winners", "", "| ticker | stage | score | survival | action |", "| --- | --- | --- | --- | --- |"])
    for p in report.get("healthy_winners") or []:
        lines.append(
            f"| {p['ticker']} | {p['lifecycle_stage']} | {p['lifecycle_score']} | "
            f"{p['survival_probability']} | {p['optimal_shadow_action']} |"
        )

    lines.extend(["", "## Weakening winners", "", "| ticker | stage | collapse | decay vel | action |", "| --- | --- | --- | --- | --- |"])
    for p in report.get("weakening_winners") or []:
        lines.append(
            f"| {p['ticker']} | {p['lifecycle_stage']} | {p['collapse_probability']} | "
            f"{p['profit_decay_velocity']} | {p['optimal_shadow_action']} |"
        )

    lines.extend(["", "## Collapsed winners", "", "| ticker | peak % | current % | collapse | missed USD |", "| --- | --- | --- | --- | --- |"])
    for p in report.get("collapsed_winners") or []:
        lines.append(
            f"| {p['ticker']} | {p['highest_pct']} | {p['current_pct']} | "
            f"{p['collapse_probability']} | ${p['missed_usd']} |"
        )
    if not report.get("collapsed_winners"):
        lines.append("| — | — | — | — | — |")

    lines.extend(["", "## Top survivors", "", "| ticker | stage | survival | score |", "| --- | --- | --- | --- |"])
    for p in report.get("top_survivors") or []:
        lines.append(
            f"| {p['ticker']} | {p['lifecycle_stage']} | {p['survival_probability']} | {p['lifecycle_score']} |"
        )

    lines.extend(["", "## Top collapse candidates", "", "| ticker | stage | collapse | missed USD | action |", "| --- | --- | --- | --- | --- |"])
    for p in report.get("top_collapse_candidates") or []:
        lines.append(
            f"| {p['ticker']} | {p['lifecycle_stage']} | {p['collapse_probability']} | "
            f"${p['missed_usd']} | {p['optimal_shadow_action']} |"
        )

    lines.extend(["", "## Portfolio lifecycle score", "", f"**{ga.get('portfolio_lifecycle_score')}** / 100 (portfolio-weighted health index)", ""])

    lines.extend(["", "## Recommended shadow actions", "", "| ticker | action | confidence |", "| --- | --- | --- |"])
    for ticker, action in sorted((report.get("recommended_shadow_actions") or {}).items()):
        conf = next((p["confidence"] for p in report.get("profiles") or [] if p["ticker"] == ticker), "—")
        lines.append(f"| {ticker} | {action} | {conf} |")

    lines.extend(["", "## Per-ticker profiles", "", "| ticker | stage | cur% | peak% | score | collapse | survival | action |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for p in report.get("profiles") or []:
        lines.append(
            f"| {p['ticker']} | {p['lifecycle_stage']} | {p['current_pct']} | {p['highest_pct']} | "
            f"{p['lifecycle_score']} | {p['collapse_probability']} | {p['survival_probability']} | "
            f"{p['optimal_shadow_action']} |"
        )

    lines.extend(["", "### Explanations (top collapse candidates)", ""])
    for p in report.get("top_collapse_candidates") or []:
        lines.append(f"- **{p['ticker']}:** {p['explanation']}")

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
            "",
            "## Sources loaded",
            "",
        ]
    )
    for key, loaded in sorted((report.get("sources_loaded") or {}).items()):
        mark = "✅" if loaded else "❌"
        lines.append(f"- {mark} {key}")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    ga = report["global_analytics"]
    print("===== TAE WINNER LIFECYCLE PROFILER =====")
    print("Mode: SHADOW_ONLY — read-only research")
    print("Global verdict:", report["global_verdict"])
    print("Portfolio lifecycle score:", ga.get("portfolio_lifecycle_score"))
    print("Healthy / collapsing / collapsed:", ga.get("number_of_healthy_winners"), "/", ga.get("number_of_collapsing_winners"), "/", ga.get("number_of_collapsed_winners"))
    print("Tickers profiled:", ga.get("tickers_profiled"))


def main() -> int:
    report = build_profiler()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
