#!/usr/bin/env python3
"""
TAE Profit Growth Analytics SSOT — SHADOW_ONLY / READ_ONLY.

Read-only analytics layer joining accounting, protection shadow, governors,
and policy memory. Does NOT modify live_bot, portfolio, advisory, or execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
FADE_SUMMARY_MD = Path("tae_intraday_fade_history_summary.md")
SHADOW_EVENTS_CSV = Path("tae_shadow_validation_events.csv")

OUTPUT_JSON = Path("tae_profit_growth_analytics.json")
OUTPUT_MD = Path("tae_profit_growth_analytics.md")

GROWTH_STATUSES = frozenset(
    {
        "CAPTURED_WINNER",
        "MISSED_WINNER",
        "ACTIVE_WINNER",
        "PROFIT_DECAY",
        "WATCHLIST_GROWTH",
        "UNKNOWN",
    }
)

MISSED_USD_LOW = 25.0
MISSED_USD_HIGH = 80.0
DRAWDOWN_SEVERE = -5.0


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


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def classify_growth_status(
    *,
    current_pct: float,
    high_pct: float,
    drawdown: float,
    missed_usd: float,
    pce_verdict: str,
    governor_posture: str,
) -> str:
    if high_pct >= 6.0 and current_pct <= 1.0:
        return "MISSED_WINNER"
    if missed_usd >= MISSED_USD_HIGH and drawdown <= DRAWDOWN_SEVERE:
        return "PROFIT_DECAY"
    if current_pct > 0 and high_pct >= 4.0 and drawdown > -2.0:
        return "ACTIVE_WINNER"
    if current_pct > 0 and missed_usd < MISSED_USD_LOW:
        return "CAPTURED_WINNER"
    if pce_verdict == "KEEP_WINNER" or governor_posture == "KEEP_WINNER_SHADOW":
        return "WATCHLIST_GROWTH"
    return "UNKNOWN"


def growth_opportunity_score(
    *,
    current_pct: float,
    high_pct: float,
    drawdown: float,
    missed_usd: float,
    growth_status: str,
) -> float:
    peak_gap = max(0.0, high_pct - current_pct)
    missed_component = min(40.0, missed_usd / 15.0)
    gap_component = min(30.0, peak_gap * 3.0)
    drawdown_penalty = min(20.0, abs(min(0.0, drawdown)) * 2.0)
    status_bonus = {
        "MISSED_WINNER": 15.0,
        "PROFIT_DECAY": 10.0,
        "ACTIVE_WINNER": 8.0,
        "WATCHLIST_GROWTH": 5.0,
        "CAPTURED_WINNER": 0.0,
        "UNKNOWN": 2.0,
    }.get(growth_status, 0.0)
    score = missed_component + gap_component + status_bonus - drawdown_penalty * 0.5
    if growth_status == "CAPTURED_WINNER":
        score = max(0.0, min(25.0, score))
    return round(max(0.0, min(100.0, score)), 1)


def global_verdict(sources: dict[str, bool]) -> str:
    accounting_ok = sources.get("tae_accounting_snapshot.json", False)
    shadow_ok = sources.get("tae_profit_protection_shadow.json", False)
    if not accounting_ok:
        return "GROWTH_ANALYTICS_NOT_READY"
    if accounting_ok and shadow_ok:
        return "GROWTH_ANALYTICS_READY"
    return "GROWTH_ANALYTICS_NEEDS_MORE_DATA"


def discover_growth_gaps(
    metrics: dict[str, Any],
    tickers: list[dict[str, Any]],
    sources: dict[str, bool],
) -> list[str]:
    gaps: list[str] = []
    if metrics.get("profit_capture_rate") is not None and metrics["profit_capture_rate"] < 0.5:
        gaps.append("Low profit capture rate — missed opportunity dominates captured PnL")
    missed_count = sum(1 for t in tickers if t.get("growth_status") == "MISSED_WINNER")
    decay_count = sum(1 for t in tickers if t.get("growth_status") == "PROFIT_DECAY")
    if missed_count >= 2:
        gaps.append(f"{missed_count} tickers classified as MISSED_WINNER")
    if decay_count >= 2:
        gaps.append(f"{decay_count} tickers in PROFIT_DECAY")
    if not sources.get("tae_adaptive_profit_policy_engine.json"):
        gaps.append("APPE policy history unavailable — portfolio policy context limited")
    if not sources.get("tae_profit_memory_engine.json"):
        gaps.append("Profit memory episodes unavailable for ticker enrichment")
    if metrics.get("corrected_total_trading_pnl", 0) <= 0:
        gaps.append("Non-positive corrected total trading PnL — capture ratios null")
    return gaps


def build_ticker_rows(
    shadow: dict[str, Any] | None,
    pdg: dict[str, Any] | None,
    context: dict[str, Any] | None,
    memory: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    shadow_by = {
        str(p.get("ticker", "")).upper(): p
        for p in (shadow or {}).get("positions") or []
        if p.get("ticker")
    }
    pdg_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (pdg or {}).get("ticker_postures") or []
        if r.get("ticker")
    }
    context_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (context or {}).get("tickers") or []
        if r.get("ticker")
    }
    memory_by: dict[str, str] = {}
    for ep in (memory or {}).get("episodes") or []:
        ticker = str(ep.get("ticker", "")).upper()
        if ticker:
            memory_by[ticker] = str(ep.get("memory_label") or "UNKNOWN")

    tickers = sorted(set(shadow_by) | set(pdg_by))
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        sh = shadow_by.get(ticker) or {}
        gov = pdg_by.get(ticker) or {}
        ctx = context_by.get(ticker) or {}

        current_pct = _f(gov.get("current_pct"), _f(sh.get("current_pct")))
        high_pct = _f(gov.get("high_pct"), _f(sh.get("high_pct")))
        drawdown = _f(gov.get("drawdown"), _f(sh.get("drawdown_from_high_pct")))
        missed_usd = round(_f(sh.get("missed_opportunity_usd")), 2)
        pce_verdict = str(gov.get("pce_context_verdict") or ctx.get("context_verdict") or "UNKNOWN")
        governor_rec = str(gov.get("final_shadow_recommendation") or "UNKNOWN")
        governor_posture = str(gov.get("governor_posture") or "UNKNOWN")
        memory_label = memory_by.get(ticker, "UNKNOWN")

        status = classify_growth_status(
            current_pct=current_pct,
            high_pct=high_pct,
            drawdown=drawdown,
            missed_usd=missed_usd,
            pce_verdict=pce_verdict,
            governor_posture=governor_posture,
        )
        opp_score = growth_opportunity_score(
            current_pct=current_pct,
            high_pct=high_pct,
            drawdown=drawdown,
            missed_usd=missed_usd,
            growth_status=status,
        )
        rows.append(
            {
                "ticker": ticker,
                "current_pct": round(current_pct, 2),
                "high_pct": round(high_pct, 2),
                "drawdown": round(drawdown, 2),
                "missed_usd": missed_usd,
                "governor_recommendation": governor_rec,
                "pce_verdict": pce_verdict,
                "memory_label": memory_label,
                "growth_status": status,
                "growth_opportunity_score": opp_score,
            }
        )
    return rows


def policy_context(appe: dict[str, Any] | None, ppg: dict[str, Any] | None) -> dict[str, Any]:
    latest = (appe or {}).get("latest_observation") or {}
    if not latest and ppg:
        metrics = ppg.get("metrics") or {}
        return {
            "portfolio_verdict": ppg.get("portfolio_verdict"),
            "policy_state": None,
            "suggested_shadow_policy": None,
            "profit_quality_score": metrics.get("portfolio_profit_quality_score"),
            "source": "tae_portfolio_profit_governor.json",
        }
    return {
        "portfolio_verdict": latest.get("portfolio_verdict") or (ppg or {}).get("portfolio_verdict"),
        "policy_state": latest.get("policy_state"),
        "suggested_shadow_policy": latest.get("suggested_shadow_policy"),
        "profit_quality_score": latest.get("profit_quality_score")
        or ((ppg or {}).get("metrics") or {}).get("portfolio_profit_quality_score"),
        "source": "tae_adaptive_profit_policy_engine.json" if latest else "tae_portfolio_profit_governor.json",
    }


def build_report() -> dict[str, Any]:
    source_paths = {
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
        "tae_intraday_fade_history_summary.md": FADE_SUMMARY_MD,
        "tae_shadow_validation_events.csv": SHADOW_EVENTS_CSV,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        if key.endswith((".md", ".csv")):
            sources_loaded[key] = path.is_file()
            payloads[key] = None
            continue
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data

    accounting = payloads["tae_accounting_snapshot.json"]
    shadow = payloads["tae_profit_protection_shadow.json"]
    ppg = payloads["tae_portfolio_profit_governor.json"]
    appe = payloads["tae_adaptive_profit_policy_engine.json"]
    pdg = payloads["tae_profit_decision_governor.json"]
    context = payloads["tae_profit_context_engine.json"]
    memory = payloads["tae_profit_memory_engine.json"]
    validation = payloads["tae_profit_protection_validation.json"]

    corrected_total = _f((accounting or {}).get("corrected_total_trading_pnl"))
    corrected_realized = _f((accounting or {}).get("corrected_realized_pnl"))
    corrected_unrealized = _f((accounting or {}).get("corrected_unrealized_pnl"))
    account_value = _f((accounting or {}).get("account_value_corrected"))

    shadow_summary = (shadow or {}).get("global_summary") or {}
    aggregate_missed = _f(shadow_summary.get("total_missed_opportunity"))
    if not aggregate_missed:
        aggregate_missed = sum(
            _f(p.get("missed_opportunity_usd")) for p in (shadow or {}).get("positions") or []
        )

    capture_denom = corrected_total + aggregate_missed
    profit_capture_rate = safe_ratio(corrected_total, capture_denom)
    missed_to_captured = safe_ratio(aggregate_missed, corrected_total)
    opportunity_cost_ratio = safe_ratio(aggregate_missed, capture_denom)

    policy = policy_context(appe, ppg)
    profit_quality = _f(policy.get("profit_quality_score"))

    tickers = build_ticker_rows(shadow, pdg, context, memory)
    verdict = global_verdict(sources_loaded)

    status_counts: dict[str, int] = {s: 0 for s in GROWTH_STATUSES}
    for row in tickers:
        status_counts[row.get("growth_status", "UNKNOWN")] = status_counts.get(row.get("growth_status"), 0) + 1

    missed_winners = sorted(
        [t for t in tickers if t.get("growth_status") == "MISSED_WINNER"],
        key=lambda r: r.get("missed_usd", 0),
        reverse=True,
    )
    active_winners = sorted(
        [t for t in tickers if t.get("growth_status") in {"ACTIVE_WINNER", "CAPTURED_WINNER"}],
        key=lambda r: r.get("current_pct", 0),
        reverse=True,
    )

    core_metrics = {
        "corrected_total_trading_pnl": round(corrected_total, 4),
        "corrected_realized_pnl": round(corrected_realized, 4),
        "corrected_unrealized_pnl": round(corrected_unrealized, 4),
        "account_value_corrected": round(account_value, 2),
        "aggregate_missed_usd": round(aggregate_missed, 2),
        "profit_capture_rate": profit_capture_rate,
        "opportunity_cost_ratio": opportunity_cost_ratio,
        "missed_to_captured_ratio": missed_to_captured,
        "profit_quality_score": round(profit_quality, 1) if profit_quality else None,
        "portfolio_verdict": policy.get("portfolio_verdict"),
        "policy_state": policy.get("policy_state"),
        "suggested_shadow_policy": policy.get("suggested_shadow_policy"),
        "profit_captured_usd": round(corrected_total, 2),
        "profit_missed_usd": round(aggregate_missed, 2),
        "theoretical_total_usd": round(capture_denom, 2) if capture_denom > 0 else None,
    }

    gaps = discover_growth_gaps(core_metrics, tickers, sources_loaded)
    recommended_next = (
        "X.PROFIT-GROWTH-2 — Opportunity Cost Ledger"
        if verdict == "GROWTH_ANALYTICS_READY"
        else "Refresh upstream SSOT inputs (accounting + protect shadow) before Opportunity Cost Ledger"
    )

    return {
        "schema": "tae_profit_growth_analytics",
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
        "core_metrics": core_metrics,
        "growth_status_counts": status_counts,
        "portfolio_policy_context": policy,
        "validation_verdict": (validation or {}).get("verdict") if validation else None,
        "top_missed_winners": missed_winners[:5],
        "top_active_winners": active_winners[:5],
        "tickers": tickers,
        "true_growth_gaps": gaps,
        "recommended_next_sprint": recommended_next,
        "formulas": {
            "profit_capture_rate": "corrected_total_trading_pnl / (corrected_total_trading_pnl + aggregate_missed_usd)",
            "missed_to_captured_ratio": "aggregate_missed_usd / corrected_total_trading_pnl",
            "opportunity_cost_ratio": "aggregate_missed_usd / (corrected_total_trading_pnl + aggregate_missed_usd)",
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    m = report["core_metrics"]
    lines = [
        "# TAE Profit Growth Analytics SSOT",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Global verdict:** {report['global_verdict']}",
        "",
        "> **SHADOW_ONLY read-only analytics — no live or advisory change**",
        "",
        "## Executive summary",
        "",
        f"- Profit captured (corrected total): **${m.get('profit_captured_usd')}**",
        f"- Profit missed (aggregate): **${m.get('profit_missed_usd')}**",
        f"- Profit capture rate: **{m.get('profit_capture_rate')}**",
        f"- Portfolio verdict: **{m.get('portfolio_verdict')}**",
        f"- Policy state: **{m.get('policy_state')}** → `{m.get('suggested_shadow_policy')}`",
        f"- Tickers analyzed: **{len(report.get('tickers') or [])}**",
        "",
        "## Core metrics",
        "",
        "| metric | value |",
        "| --- | --- |",
    ]
    for key, value in m.items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Profit capture rate",
            "",
            f"**{m.get('profit_capture_rate')}** = ${m.get('corrected_total_trading_pnl')} / "
            f"(${m.get('corrected_total_trading_pnl')} + ${m.get('aggregate_missed_usd')})",
            "",
            f"- Opportunity cost ratio: **{m.get('opportunity_cost_ratio')}**",
            f"- Missed-to-captured ratio: **{m.get('missed_to_captured_ratio')}**",
            "",
            "## Captured vs missed profit",
            "",
            f"| Captured (corrected total) | Missed (shadow) | Theoretical total |",
            f"| --- | --- | --- |",
            f"| ${m.get('profit_captured_usd')} | ${m.get('profit_missed_usd')} | ${m.get('theoretical_total_usd')} |",
            "",
            "## Top missed winners",
            "",
            "| ticker | high % | current % | missed USD | growth status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("top_missed_winners") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('high_pct')} | {row.get('current_pct')} | "
            f"{row.get('missed_usd')} | {row.get('growth_status')} |"
        )

    lines.extend(
        [
            "",
            "## Top active winners",
            "",
            "| ticker | current % | high % | missed USD | growth status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("top_active_winners") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('current_pct')} | {row.get('high_pct')} | "
            f"{row.get('missed_usd')} | {row.get('growth_status')} |"
        )

    pol = report.get("portfolio_policy_context") or {}
    lines.extend(
        [
            "",
            "## Portfolio policy context",
            "",
            f"- Source: `{pol.get('source')}`",
            f"- Portfolio verdict: **{pol.get('portfolio_verdict')}**",
            f"- Policy state: **{pol.get('policy_state')}**",
            f"- Suggested shadow policy: **{pol.get('suggested_shadow_policy')}**",
            f"- Profit quality score: **{pol.get('profit_quality_score')}**",
            "",
            "## Per-ticker growth table",
            "",
            "| ticker | current % | high % | drawdown | missed USD | governor | PCE | memory | status | opp score |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("tickers") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('current_pct')} | {row.get('high_pct')} | {row.get('drawdown')} | "
            f"{row.get('missed_usd')} | {row.get('governor_recommendation')} | {row.get('pce_verdict')} | "
            f"{row.get('memory_label')} | {row.get('growth_status')} | {row.get('growth_opportunity_score')} |"
        )

    lines.extend(["", "## True growth gaps discovered", ""])
    for gap in report.get("true_growth_gaps") or []:
        lines.append(f"- {gap}")
    if not report.get("true_growth_gaps"):
        lines.append("- None critical — analytics inputs sufficient for observation.")

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
    m = report["core_metrics"]
    print("===== TAE PROFIT GROWTH ANALYTICS SSOT =====")
    print("Mode: SHADOW_ONLY — read-only")
    print("Global verdict:", report["global_verdict"])
    print("Capture rate:", m.get("profit_capture_rate"))
    print("Captured / missed USD:", m.get("profit_captured_usd"), "/", m.get("profit_missed_usd"))
    print("Portfolio verdict:", m.get("portfolio_verdict"))
    print("Policy:", m.get("policy_state"), "→", m.get("suggested_shadow_policy"))
    print("Tickers:", len(report.get("tickers") or []))


def main() -> int:
    report = build_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
