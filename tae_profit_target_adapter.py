#!/usr/bin/env python3
"""
TAE Dynamic Profit Target Adapter — SHADOW_ONLY / READ_ONLY.

Converts Growth Intelligence into numeric dynamic profit target guidance.
Does NOT recalculate PSP, lifecycle, opportunity cost, capture rate, or shadow sims.
Does NOT modify live_bot, portfolio, advisory, or upstream engines.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

GII_JSON = Path("tae_growth_intelligence.json")
LIFECYCLE_JSON = Path("tae_winner_lifecycle_profiler.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
GROWTH_JSON = Path("tae_profit_growth_analytics.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")

OUTPUT_JSON = Path("tae_profit_target_adapter.json")
OUTPUT_MD = Path("tae_profit_target_adapter.md")

BASELINE_PARTIAL_LEVELS = (6.0, 8.0, 10.0)
BASELINE_PROFIT_LOCK_PCT = 4.0
BASELINE_TRAILING_PCT = 1.0
BASELINE_TRAILING_ALT_PCT = 1.5

URGENCY_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
PARTIAL_SIZES = (20, 25, 30, 33, 50)

UPSTREAM_REUSE = [
    "tae_growth_intelligence.json — primary per-ticker scores and recommended_shadow_strategy",
    "tae_winner_lifecycle_profiler.json — lifecycle confirmation (read-only fallback)",
    "tae_opportunity_cost_ledger.json — opportunity category/severity context",
    "tae_profit_protection_shadow.json — static rules_v1_config baseline anchors",
    "tae_profit_protection_validation.json — portfolio best shadow method bias",
    "tae_profit_growth_analytics.json — portfolio capture rate for improvement hint",
    "tae_adaptive_profit_policy_engine.json — portfolio target policy bias",
    "tae_profit_decision_governor.json — governor alignment context",
    "tae_accounting_snapshot.json — accounting context flag",
]

NOT_DUPLICATED = (
    "Does not recompute growth_score, lifecycle_stage, opportunity categories, "
    "capture rate, PSP, or shadow PnL simulation. Translates existing SSOT into numeric targets only."
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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def load_baselines(shadow: dict[str, Any] | None) -> dict[str, Any]:
    cfg = (shadow or {}).get("rules_v1_config") or {}
    partials = [
        _f(p.get("threshold_pct"))
        for p in cfg.get("partial_levels") or []
        if p.get("threshold_pct") is not None
    ]
    if not partials:
        partials = list(BASELINE_PARTIAL_LEVELS)
    return {
        "partial_tp_levels": partials,
        "primary_partial_tp_pct": partials[0],
        "profit_lock_pct": _f(cfg.get("profit_lock_pct"), BASELINE_PROFIT_LOCK_PCT),
        "trailing_pct": BASELINE_TRAILING_PCT,
        "trailing_alt_pct": BASELINE_TRAILING_ALT_PCT,
        "peak_fade_alert_pct": _f(cfg.get("peak_fade_alert_pct"), 1.5),
    }


def validation_trailing_bias(validation: dict[str, Any] | None) -> float:
    """Negative = prefer tighter trailing."""
    if not validation:
        return 0.0
    text = json.dumps(validation, default=str).lower()
    if "trailing_1_5" in text and "best" in text:
        return 0.1
    if "trailing_1" in text or "test_trailing" in text:
        return -0.05
    return 0.0


def policy_trailing_bias(appe: dict[str, Any] | None) -> float:
    latest = (appe or {}).get("latest_observation") or {}
    policy = _s(latest.get("suggested_shadow_policy"))
    if "TIGHTEN" in policy.upper() or latest.get("policy_state") == "HIGH_RISK":
        return -0.15
    return 0.0


def adapt_targets(
    *,
    strategy: str,
    lifecycle_stage: str,
    growth_score: float,
    survival_probability: float,
    collapse_probability: float,
    opportunity_score: float,
    current_pct: float,
    high_pct: float,
    baselines: dict[str, Any],
    trailing_bias: float,
) -> dict[str, Any]:
    primary_partial = baselines["primary_partial_tp_pct"]
    profit_lock = baselines["profit_lock_pct"]
    trailing = baselines["trailing_pct"]
    hold_ceiling = high_pct if high_pct > 0 else primary_partial + 2.0
    min_capture = clamp(current_pct / high_pct * 100.0 if high_pct > 0 else 50.0, 0.0, 100.0)
    partial_size = 25
    urgency = "MEDIUM"
    recovery_only = False

    if lifecycle_stage == "COLLAPSED" or (current_pct <= 0 and high_pct > 6.0):
        recovery_only = True
        return {
            "dynamic_partial_tp_pct": None,
            "dynamic_trailing_pct": round(clamp(trailing - 0.25 + trailing_bias, 0.5, 2.0), 2),
            "dynamic_profit_lock_pct": round(clamp(profit_lock - 1.0, 2.0, 6.0), 2),
            "hold_ceiling_pct": round(current_pct, 2),
            "min_capture_pct": 0.0,
            "exit_window_urgency": "CRITICAL",
            "suggested_partial_size_pct": 50,
            "recovery_exit_management_only": True,
        }

    if strategy == "KEEP_GROWING_SHADOW" and survival_probability >= 0.6:
        primary_partial = primary_partial + 1.5
        profit_lock = profit_lock + 0.5
        trailing = trailing + 0.25 + trailing_bias
        hold_ceiling = max(hold_ceiling, high_pct + 2.0, primary_partial + 4.0)
        min_capture = max(min_capture, 70.0)
        partial_size = 20
        urgency = "LOW"
    elif strategy == "HOLD_AND_MONITOR_SHADOW":
        urgency = "MEDIUM" if opportunity_score < 40 else "HIGH"
        trailing = trailing + trailing_bias
        hold_ceiling = max(hold_ceiling, high_pct + 1.0)
        partial_size = 25
    elif strategy == "PROTECT_PROFIT_SHADOW":
        primary_partial = primary_partial - 1.5
        profit_lock = profit_lock - 0.5
        trailing = trailing - 0.25 + trailing_bias
        hold_ceiling = min(hold_ceiling, max(current_pct + 1.0, primary_partial))
        min_capture = max(40.0, min_capture - 10.0)
        partial_size = 33
        urgency = "HIGH"
    elif strategy == "TIGHTEN_TRAIL_SHADOW":
        primary_partial = primary_partial - 1.0
        profit_lock = profit_lock - 0.75
        trailing = trailing - 0.35 + trailing_bias
        hold_ceiling = min(hold_ceiling, max(current_pct, primary_partial))
        partial_size = 30
        urgency = "HIGH"
    elif strategy == "REDUCE_EXPOSURE_SHADOW":
        primary_partial = primary_partial - 2.0
        profit_lock = profit_lock - 1.0
        trailing = trailing - 0.5 + trailing_bias
        hold_ceiling = current_pct
        min_capture = 0.0
        partial_size = 50
        urgency = "CRITICAL"
    elif strategy == "COLLECT_MORE_DATA":
        urgency = "MEDIUM"
        partial_size = 25
    else:
        trailing = trailing + trailing_bias

    if collapse_probability >= 0.75:
        urgency = "CRITICAL" if urgency != "LOW" else "HIGH"
        primary_partial -= 0.5
        partial_size = max(partial_size, 33)
    if opportunity_score >= 70:
        primary_partial -= 1.0
        partial_size = max(partial_size, 33)
        if urgency == "LOW":
            urgency = "MEDIUM"

    primary_partial = round(clamp(primary_partial, 3.0, 12.0), 2)
    trailing = round(clamp(trailing, 0.5, 2.5), 2)
    profit_lock = round(clamp(profit_lock, 2.0, 6.0), 2)
    hold_ceiling = round(clamp(hold_ceiling, current_pct, 15.0), 2)
    min_capture = round(clamp(min_capture, 0.0, 100.0), 1)

    return {
        "dynamic_partial_tp_pct": primary_partial,
        "dynamic_trailing_pct": trailing,
        "dynamic_profit_lock_pct": profit_lock,
        "hold_ceiling_pct": hold_ceiling,
        "min_capture_pct": min_capture,
        "exit_window_urgency": urgency,
        "suggested_partial_size_pct": partial_size,
        "recovery_exit_management_only": recovery_only,
    }


def target_confidence(
    *,
    growth_confidence: float,
    strategy: str,
    lifecycle_stage: str,
    gii_loaded: bool,
    shadow_loaded: bool,
) -> float:
    score = _f(growth_confidence, 0.5)
    if gii_loaded:
        score += 0.15
    if shadow_loaded:
        score += 0.1
    if strategy == "COLLECT_MORE_DATA":
        score -= 0.2
    if lifecycle_stage == "UNKNOWN":
        score -= 0.1
    return round(clamp(score, 0.0, 1.0), 2)


def build_explanation(
    *,
    ticker: str,
    strategy: str,
    targets: dict[str, Any],
    baselines: dict[str, Any],
    recovery_only: bool,
) -> str:
    if recovery_only:
        return (
            f"{ticker}: COLLAPSED/recovery mode — no growth profit target. "
            f"Exit management only: urgency={targets['exit_window_urgency']}, "
            f"partial_size={targets['suggested_partial_size_pct']}% shadow guidance only."
        )
    return (
        f"{ticker}: strategy={strategy}. "
        f"Dynamic partial TP {targets['dynamic_partial_tp_pct']}% "
        f"(baseline {baselines['primary_partial_tp_pct']}%), "
        f"trailing {targets['dynamic_trailing_pct']}% (baseline {baselines['trailing_pct']}%), "
        f"lock {targets['dynamic_profit_lock_pct']}% (baseline {baselines['profit_lock_pct']}%). "
        f"Hold ceiling {targets['hold_ceiling_pct']}%, min capture {targets['min_capture_pct']}%, "
        f"urgency {targets['exit_window_urgency']}, partial size {targets['suggested_partial_size_pct']}%."
    )


def global_verdict(sources: dict[str, bool], ticker_count: int) -> str:
    if not sources.get("tae_growth_intelligence.json"):
        return "PROFIT_TARGET_ADAPTER_NOT_READY"
    if ticker_count >= 1 and sources.get("tae_profit_protection_shadow.json"):
        return "PROFIT_TARGET_ADAPTER_READY"
    if ticker_count >= 1:
        return "PROFIT_TARGET_ADAPTER_NEEDS_MORE_DATA"
    return "PROFIT_TARGET_ADAPTER_NOT_READY"


def build_adapter() -> dict[str, Any]:
    source_paths = {
        "tae_growth_intelligence.json": GII_JSON,
        "tae_winner_lifecycle_profiler.json": LIFECYCLE_JSON,
        "tae_opportunity_cost_ledger.json": LEDGER_JSON,
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
        "tae_profit_growth_analytics.json": GROWTH_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data

    gii = payloads["tae_growth_intelligence.json"]
    shadow = payloads["tae_profit_protection_shadow.json"]
    validation = payloads["tae_profit_protection_validation.json"]
    growth = payloads["tae_profit_growth_analytics.json"]
    appe = payloads["tae_adaptive_profit_policy_engine.json"]

    baselines = load_baselines(shadow)
    trailing_bias = validation_trailing_bias(validation) + policy_trailing_bias(appe)

    gii_tickers = (gii or {}).get("tickers") or []
    if not gii_tickers and payloads["tae_winner_lifecycle_profiler.json"]:
        gii_tickers = [
            {
                "ticker": p.get("ticker"),
                "current_pct": p.get("current_pct"),
                "high_pct": p.get("highest_pct"),
                "lifecycle_stage": p.get("lifecycle_stage"),
                "growth_score": p.get("lifecycle_score"),
                "winner_quality": 50.0,
                "opportunity_score": 50.0,
                "collapse_probability": p.get("collapse_probability"),
                "survival_probability": p.get("survival_probability"),
                "recommended_shadow_strategy": "COLLECT_MORE_DATA",
                "growth_confidence": 0.4,
            }
            for p in (payloads["tae_winner_lifecycle_profiler.json"] or {}).get("profiles") or []
        ]

    portfolio_policy = _s(
        ((appe or {}).get("latest_observation") or {}).get("suggested_shadow_policy"),
        _s(((gii or {}).get("portfolio") or {}).get("suggested_shadow_policy")),
    )

    capture_rate = _f(((growth or {}).get("core_metrics") or {}).get("profit_capture_rate"))
    opportunity_total = _f(((gii or {}).get("portfolio") or {}).get("opportunity_cost_total"))

    targets_list: list[dict[str, Any]] = []
    for row in gii_tickers:
        ticker = _s(row.get("ticker")).upper()
        strategy = _s(row.get("recommended_shadow_strategy"))
        lifecycle_stage = _s(row.get("lifecycle_stage"))
        current_pct = _f(row.get("current_pct"))
        high_pct = _f(row.get("high_pct"))

        adapted = adapt_targets(
            strategy=strategy,
            lifecycle_stage=lifecycle_stage,
            growth_score=_f(row.get("growth_score")),
            survival_probability=_f(row.get("survival_probability")),
            collapse_probability=_f(row.get("collapse_probability")),
            opportunity_score=_f(row.get("opportunity_score")),
            current_pct=current_pct,
            high_pct=high_pct,
            baselines=baselines,
            trailing_bias=trailing_bias,
        )

        confidence = target_confidence(
            growth_confidence=_f(row.get("growth_confidence"), 0.5),
            strategy=strategy,
            lifecycle_stage=lifecycle_stage,
            gii_loaded=sources_loaded["tae_growth_intelligence.json"],
            shadow_loaded=sources_loaded["tae_profit_protection_shadow.json"],
        )

        explanation = build_explanation(
            ticker=ticker,
            strategy=strategy,
            targets=adapted,
            baselines=baselines,
            recovery_only=adapted.get("recovery_exit_management_only", False),
        )

        targets_list.append(
            {
                "ticker": ticker,
                "current_pct": round(current_pct, 2),
                "high_pct": round(high_pct, 2),
                "lifecycle_stage": lifecycle_stage,
                "growth_score": round(_f(row.get("growth_score")), 1),
                "winner_quality": round(_f(row.get("winner_quality")), 1),
                "opportunity_score": round(_f(row.get("opportunity_score")), 1),
                "collapse_probability": round(_f(row.get("collapse_probability")), 3),
                "survival_probability": round(_f(row.get("survival_probability")), 3),
                "recommended_shadow_strategy": strategy,
                "dynamic_partial_tp_pct": adapted.get("dynamic_partial_tp_pct"),
                "dynamic_trailing_pct": adapted["dynamic_trailing_pct"],
                "dynamic_profit_lock_pct": adapted["dynamic_profit_lock_pct"],
                "hold_ceiling_pct": adapted["hold_ceiling_pct"],
                "min_capture_pct": adapted["min_capture_pct"],
                "exit_window_urgency": adapted["exit_window_urgency"],
                "suggested_partial_size_pct": adapted["suggested_partial_size_pct"],
                "target_confidence": confidence,
                "recovery_exit_management_only": adapted.get("recovery_exit_management_only", False),
                "explanation": explanation,
            }
        )

    active = [t for t in targets_list if not t.get("recovery_exit_management_only")]
    n_active = len(active) or 1

    strategy_counts = Counter(t["recommended_shadow_strategy"] for t in targets_list)
    dominant_mode = strategy_counts.most_common(1)[0][0] if strategy_counts else "COLLECT_MORE_DATA"

    avg_partial = round(
        sum(_f(t["dynamic_partial_tp_pct"]) for t in active if t["dynamic_partial_tp_pct"] is not None)
        / max(1, sum(1 for t in active if t["dynamic_partial_tp_pct"] is not None)),
        2,
    )
    avg_trailing = round(sum(t["dynamic_trailing_pct"] for t in active) / n_active, 2)
    avg_lock = round(sum(t["dynamic_profit_lock_pct"] for t in active) / n_active, 2)

    if capture_rate > 0 and capture_rate < 0.5 and opportunity_total > 300:
        capture_hint = (
            f"Portfolio capture rate {capture_rate:.1%} with ${opportunity_total:.0f} missed — "
            "earlier partial TP (−1%) on high-opportunity tickers may improve capture (shadow hypothesis)."
        )
    elif capture_rate >= 0.5:
        capture_hint = "Capture rate moderate — current dynamic targets aligned with baseline extension."
    else:
        capture_hint = "Insufficient capture context — refresh growth analytics before policy learning."

    keep_growing = [t for t in targets_list if t["recommended_shadow_strategy"] == "KEEP_GROWING_SHADOW"]
    protect = [
        t
        for t in targets_list
        if t["recommended_shadow_strategy"]
        in {"PROTECT_PROFIT_SHADOW", "TIGHTEN_TRAIL_SHADOW", "REDUCE_EXPOSURE_SHADOW"}
    ]

    verdict = global_verdict(sources_loaded, len(targets_list))

    return {
        "schema": "tae_profit_target_adapter",
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
        "anti_duplication": {
            "prebuild_audit": "TAE_DPTI_PREBUILD_AUDIT.md",
            "verdict": "EXTEND + SMALL ADAPTER",
            "not_duplicated": NOT_DUPLICATED,
            "upstream_reuse": UPSTREAM_REUSE,
        },
        "baseline_anchors": {
            "partial_tp_levels_pct": baselines["partial_tp_levels"],
            "primary_partial_tp_pct": baselines["primary_partial_tp_pct"],
            "profit_lock_pct": baselines["profit_lock_pct"],
            "trailing_pct": baselines["trailing_pct"],
            "trailing_alt_pct": baselines["trailing_alt_pct"],
            "source": "tae_profit_protection_shadow.json rules_v1_config",
        },
        "target_adaptation_model": {
            "KEEP_GROWING_SHADOW": "raise partial TP, widen trailing, low urgency",
            "HOLD_AND_MONITOR_SHADOW": "neutral targets, medium urgency if opportunity elevated",
            "PROTECT_PROFIT_SHADOW": "lower partial TP, tighter trailing, larger partial size",
            "TIGHTEN_TRAIL_SHADOW": "tighter trailing, earlier lock, high urgency",
            "REDUCE_EXPOSURE_SHADOW": "lowest partial threshold, max partial size, critical urgency",
            "COLLAPSED": "recovery/exit management only — no growth target",
        },
        "global_verdict": verdict,
        "portfolio": {
            "portfolio_target_policy": portfolio_policy,
            "dominant_target_mode": dominant_mode,
            "average_dynamic_partial_tp_pct": avg_partial,
            "average_dynamic_trailing_pct": avg_trailing,
            "average_profit_lock_pct": avg_lock,
            "expected_capture_improvement_hint": capture_hint,
            "strategy_distribution": dict(strategy_counts),
            "profit_capture_rate": capture_rate if capture_rate else None,
            "opportunity_cost_total": opportunity_total if opportunity_total else None,
        },
        "top_keep_growing_targets": sorted(keep_growing, key=lambda t: t["growth_score"], reverse=True)[:5],
        "top_protection_targets": sorted(
            protect,
            key=lambda t: (t["opportunity_score"], t["collapse_probability"]),
            reverse=True,
        )[:5],
        "tickers": targets_list,
        "recommended_next_sprint": "X.PROFIT-GROWTH-6 — Profit Target Policy Learning",
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    p = report["portfolio"]
    baselines = report["baseline_anchors"]
    lines = [
        "# TAE Dynamic Profit Target Adapter",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Global verdict:** {report['global_verdict']}",
        "",
        "> **SHADOW_ONLY numeric target guidance — no execution, no upstream recompute**",
        "",
        "## Executive summary",
        "",
        f"- Tickers with targets: **{len(report.get('tickers') or [])}**",
        f"- Dominant target mode: **{p.get('dominant_target_mode')}**",
        f"- Portfolio target policy: **{p.get('portfolio_target_policy')}**",
        f"- Avg dynamic partial TP: **{p.get('average_dynamic_partial_tp_pct')}%**",
        f"- Avg dynamic trailing: **{p.get('average_dynamic_trailing_pct')}%**",
        f"- Avg profit lock: **{p.get('average_profit_lock_pct')}%**",
        f"- Capture improvement hint: {p.get('expected_capture_improvement_hint')}",
        "",
        "## Baseline target anchors",
        "",
        f"- Source: `{baselines.get('source')}`",
        f"- Partial TP levels: **{baselines.get('partial_tp_levels_pct')}**",
        f"- Primary partial TP: **{baselines.get('primary_partial_tp_pct')}%**",
        f"- Profit lock: **{baselines.get('profit_lock_pct')}%**",
        f"- Trailing: **{baselines.get('trailing_pct')}%** / **{baselines.get('trailing_alt_pct')}%**",
        "",
        "## Portfolio target policy",
        "",
        f"- Policy: **{p.get('portfolio_target_policy')}**",
        f"- Dominant mode: **{p.get('dominant_target_mode')}**",
        "",
        "| metric | value |",
        "| --- | --- |",
    ]
    for key, value in p.items():
        if key != "strategy_distribution":
            lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Top keep-growing targets", "", "| ticker | partial TP | trailing | hold ceiling | urgency |", "| --- | --- | --- | --- | --- |"])
    for row in report.get("top_keep_growing_targets") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('dynamic_partial_tp_pct')}% | {row.get('dynamic_trailing_pct')}% | "
            f"{row.get('hold_ceiling_pct')}% | {row.get('exit_window_urgency')} |"
        )

    lines.extend(["", "## Top protection targets", "", "| ticker | partial TP | partial size | trailing | urgency |", "| --- | --- | --- | --- | --- |"])
    for row in report.get("top_protection_targets") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('dynamic_partial_tp_pct')} | {row.get('suggested_partial_size_pct')}% | "
            f"{row.get('dynamic_trailing_pct')}% | {row.get('exit_window_urgency')} |"
        )

    lines.extend(
        [
            "",
            "## Per-ticker target table",
            "",
            "| ticker | strategy | partial TP | trailing | lock | ceiling | min cap | size | urgency | conf |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("tickers") or []:
        partial = row.get("dynamic_partial_tp_pct")
        partial_disp = "—" if partial is None else f"{partial}%"
        lines.append(
            f"| {row['ticker']} | {row.get('recommended_shadow_strategy')} | {partial_disp} | "
            f"{row.get('dynamic_trailing_pct')}% | {row.get('dynamic_profit_lock_pct')}% | "
            f"{row.get('hold_ceiling_pct')}% | {row.get('min_capture_pct')}% | "
            f"{row.get('suggested_partial_size_pct')}% | {row.get('exit_window_urgency')} | "
            f"{row.get('target_confidence')} |"
        )

    lines.extend(["", "## What this reuses", ""])
    for item in report.get("anti_duplication", {}).get("upstream_reuse") or UPSTREAM_REUSE:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## What this does not duplicate",
            "",
            f"- {report.get('anti_duplication', {}).get('not_duplicated', NOT_DUPLICATED)}",
            "",
            "## Safety confirmation",
            "",
            "- SHADOW_ONLY: **true**",
            "- READ_ONLY: **true**",
            "- NO_BROKER: **true**",
            "- NO_LIVE_EXECUTION_CHANGE: **true**",
            "- NO_ADVISORY_CHANGE: **true**",
            "- portfolio.csv modified: **false**",
            "- Upstream engines modified: **false**",
            "",
            "## Recommended next sprint",
            "",
            f"**{report.get('recommended_next_sprint')}**",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    p = report["portfolio"]
    print("===== TAE PROFIT TARGET ADAPTER =====")
    print("Mode: SHADOW_ONLY — read-only adapter")
    print("Global verdict:", report["global_verdict"])
    print("Dominant mode:", p.get("dominant_target_mode"))
    print("Avg partial / trailing / lock:", p.get("average_dynamic_partial_tp_pct"), "/", p.get("average_dynamic_trailing_pct"), "/", p.get("average_profit_lock_pct"))
    print("Tickers:", len(report.get("tickers") or []))


def main() -> int:
    report = build_adapter()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
