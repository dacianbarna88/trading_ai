#!/usr/bin/env python3
"""
TAE Opportunity Cost Ledger — SHADOW_ONLY / READ_ONLY.

Classifies why profit was missed per ticker using existing SSOT inputs.
Does NOT modify live_bot, portfolio, advisory, or execution.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

GROWTH_JSON = Path("tae_profit_growth_analytics.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
FADE_SUMMARY_MD = Path("tae_intraday_fade_history_summary.md")
SHADOW_EVENTS_CSV = Path("tae_shadow_validation_events.csv")
BOT_LOG = Path("bot_output.log")

OUTPUT_JSON = Path("tae_opportunity_cost_ledger.json")
OUTPUT_MD = Path("tae_opportunity_cost_ledger.md")

MISSED_USD_MEDIUM = 25.0
MISSED_USD_HIGH = 75.0
MISSED_USD_CRITICAL = 200.0
DRAWDOWN_SEVERE = -5.0

CATEGORIES = frozenset(
    {
        "PROFIT_GIVEBACK",
        "LATE_PROTECTION",
        "NO_PARTIAL_TAKE_PROFIT",
        "TRAILING_TOO_LOOSE",
        "EXIT_TOO_EARLY",
        "HOLD_TOO_LONG",
        "REENTRY_MISSED",
        "CAPITAL_LOCKED",
        "POSITION_LIMIT_CONSTRAINT",
        "CASH_CONSTRAINT",
        "MARKET_CONTEXT_REVERSAL",
        "UNKNOWN",
    }
)

SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})

CATEGORY_TO_FIX: dict[str, str] = {
    "PROFIT_GIVEBACK": "TEST_EARLIER_PROFIT_LOCK",
    "LATE_PROTECTION": "TEST_FASTER_PDG_ESCALATION",
    "NO_PARTIAL_TAKE_PROFIT": "TEST_PARTIAL_TP_AT_DYNAMIC_THRESHOLD",
    "TRAILING_TOO_LOOSE": "TEST_TIGHTER_TRAILING",
    "EXIT_TOO_EARLY": "TEST_HOLD_EXTENSION",
    "HOLD_TOO_LONG": "TEST_EARLIER_EXIT_GOVERNOR",
    "REENTRY_MISSED": "TEST_REENTRY_POLICY",
    "CAPITAL_LOCKED": "TEST_CAPITAL_ROTATION",
    "POSITION_LIMIT_CONSTRAINT": "TEST_POSITION_SLOT_POLICY",
    "CASH_CONSTRAINT": "TEST_CASH_RESERVE_POLICY",
    "MARKET_CONTEXT_REVERSAL": "TEST_CONTEXT_WEIGHT_ADJUSTMENT",
    "UNKNOWN": "COLLECT_MORE_DATA",
}


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


def severity_for_missed(missed_usd: float) -> str:
    if missed_usd >= MISSED_USD_CRITICAL:
        return "CRITICAL"
    if missed_usd >= MISSED_USD_HIGH:
        return "HIGH"
    if missed_usd >= MISSED_USD_MEDIUM:
        return "MEDIUM"
    return "LOW"


def governor_is_protect_action(governor_rec: str) -> bool:
    upper = governor_rec.upper()
    return any(token in upper for token in ("PARTIAL", "TRAIL", "PROTECT"))


def pce_is_reversal(pce_verdict: str) -> bool:
    return pce_verdict in {"PROTECT_NOW", "CONTEXT_WEAKENING"}


def has_partial_capture_evidence(shadow_pos: dict[str, Any] | None) -> bool:
    if not shadow_pos:
        return False
    rules = shadow_pos.get("rules_v1") or {}
    advisories = rules.get("partial_take_profit_advisories") or []
    if advisories:
        return True
    classification = _s(shadow_pos.get("classification"), "")
    if "PARTIAL" in classification.upper() and "POTENTIAL" not in classification.upper():
        return True
    signal = _s(shadow_pos.get("protection_signal"), "")
    if signal.startswith("PARTIAL_TAKE_PROFIT") and shadow_pos.get("suggested_shadow_action"):
        # Shadow suggested partial but advisories empty → no captured partial
        return False
    return False


def detect_portfolio_constraints(
    ppg: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    accounting: dict[str, Any] | None,
) -> dict[str, str]:
    """Return ticker -> constraint hint from portfolio-level signals."""
    hints: dict[str, str] = {}
    if not ppg and not validation and not accounting:
        return hints

    ppg_text = json.dumps(ppg or {}, default=str).upper()
    val_text = json.dumps(validation or {}, default=str).upper()

    if "CASH" in ppg_text and "CONSTRAINT" in ppg_text:
        for ticker in (ppg or {}).get("top_risky_tickers") or []:
            hints[_s(ticker)] = "CASH_CONSTRAINT"
    if "POSITION" in val_text and ("LIMIT" in val_text or "SLOT" in val_text):
        for item in (validation or {}).get("findings") or []:
            ticker = _s((item or {}).get("ticker"), "")
            if ticker != "UNKNOWN":
                hints[ticker] = "POSITION_LIMIT_CONSTRAINT"
    if "CAPITAL" in ppg_text and ("LOCK" in ppg_text or "ROTATION" in ppg_text):
        for ticker in (ppg or {}).get("top_risky_tickers") or []:
            hints.setdefault(_s(ticker), "CAPITAL_LOCKED")

    cash_pct = _f((accounting or {}).get("cash_pct"))
    if 0 < cash_pct < 5.0:
        for ticker in (ppg or {}).get("top_risky_tickers") or []:
            hints.setdefault(_s(ticker), "CASH_CONSTRAINT")
    return hints


def classify_opportunity_cost(
    *,
    ticker: str,
    missed_usd: float,
    high_pct: float,
    current_pct: float,
    drawdown: float,
    governor_rec: str,
    pce_verdict: str,
    memory_label: str,
    shadow_pos: dict[str, Any] | None,
    portfolio_constraint: str | None,
) -> tuple[str, list[str], float]:
    """Return primary category, contributing causes, confidence 0-1."""
    causes: list[str] = []
    missed_high = missed_usd >= MISSED_USD_HIGH
    missed_material = missed_usd >= MISSED_USD_MEDIUM

    if portfolio_constraint in CATEGORIES:
        causes.append(portfolio_constraint)

    if pce_is_reversal(pce_verdict) and missed_high:
        causes.append("MARKET_CONTEXT_REVERSAL")

    if high_pct >= 6.0 and missed_high and governor_is_protect_action(governor_rec):
        causes.append("LATE_PROTECTION")

    if high_pct >= 6.0 and missed_material and not has_partial_capture_evidence(shadow_pos):
        causes.append("NO_PARTIAL_TAKE_PROFIT")

    if drawdown <= DRAWDOWN_SEVERE and missed_high:
        causes.append("TRAILING_TOO_LOOSE")

    if current_pct <= 0.0 and high_pct >= 4.0 and missed_material:
        causes.append("HOLD_TOO_LONG")

    if high_pct >= 6.0 and current_pct <= 1.0:
        causes.append("PROFIT_GIVEBACK")

    rules = (shadow_pos or {}).get("rules_v1") or {}
    if rules.get("reentry_cooldown_required"):
        causes.append("REENTRY_MISSED")

    if (
        missed_material
        and high_pct >= 3.0
        and current_pct > 0
        and (high_pct - current_pct) >= 2.0
        and memory_label in {"PROFIT_COLLAPSED", "UNKNOWN_OUTCOME"}
        and "PROFIT_GIVEBACK" not in causes
    ):
        causes.append("EXIT_TOO_EARLY")

    if not causes:
        if missed_usd <= 0:
            return "UNKNOWN", [], 0.3
        return "UNKNOWN", ["UNKNOWN"], 0.35

    priority = [
        "CASH_CONSTRAINT",
        "POSITION_LIMIT_CONSTRAINT",
        "CAPITAL_LOCKED",
        "MARKET_CONTEXT_REVERSAL",
        "LATE_PROTECTION",
        "NO_PARTIAL_TAKE_PROFIT",
        "TRAILING_TOO_LOOSE",
        "HOLD_TOO_LONG",
        "PROFIT_GIVEBACK",
        "REENTRY_MISSED",
        "EXIT_TOO_EARLY",
    ]
    primary = next((c for c in priority if c in causes), causes[0])
    confidence = min(0.95, 0.45 + 0.1 * len(causes))
    if primary in {"MARKET_CONTEXT_REVERSAL", "LATE_PROTECTION", "NO_PARTIAL_TAKE_PROFIT"}:
        confidence = min(0.95, confidence + 0.1)
    if primary == "UNKNOWN":
        confidence = 0.35
    return primary, causes, round(confidence, 2)


def build_explanation(
    *,
    ticker: str,
    category: str,
    missed_usd: float,
    high_pct: float,
    current_pct: float,
    drawdown: float,
    governor_rec: str,
    pce_verdict: str,
    memory_label: str,
    growth_status: str,
    contributing: list[str],
) -> str:
    parts = [
        f"{ticker}: missed ${missed_usd:.2f} (peak {high_pct:.2f}%, now {current_pct:.2f}%, "
        f"drawdown {drawdown:.2f}%)."
    ]
    reason_map = {
        "PROFIT_GIVEBACK": "Peak profit faded back near flat — gains were not locked before giveback.",
        "LATE_PROTECTION": (
            f"Governor recommended `{governor_rec}` after peak, but protection arrived too late "
            f"to preserve ${missed_usd:.2f}."
        ),
        "NO_PARTIAL_TAKE_PROFIT": (
            f"High peak ({high_pct:.2f}%) without evidence of partial take-profit capture "
            f"before fade."
        ),
        "TRAILING_TOO_LOOSE": (
            f"Severe drawdown ({drawdown:.2f}%) from peak suggests trailing stop was too loose."
        ),
        "HOLD_TOO_LONG": "Position held through reversal until PnL turned negative after a strong peak.",
        "EXIT_TOO_EARLY": "Partial exit or early trim may have capped upside before full peak capture.",
        "REENTRY_MISSED": "Re-entry cooldown or policy blocked reclaiming upside after exit.",
        "CAPITAL_LOCKED": "Capital rotation constraints limited profit-protection actions.",
        "POSITION_LIMIT_CONSTRAINT": "Position slot limits constrained protective sizing or rotation.",
        "CASH_CONSTRAINT": "Low cash reserve limited ability to hedge or rotate capital.",
        "MARKET_CONTEXT_REVERSAL": (
            f"PCE `{pce_verdict}` signaled context weakening while ${missed_usd:.2f} remained at risk."
        ),
        "UNKNOWN": "Insufficient SSOT signals to classify root cause confidently.",
    }
    parts.append(f"Primary cause: **{category}** — {reason_map.get(category, reason_map['UNKNOWN'])}")
    if len(contributing) > 1:
        others = [c for c in contributing if c != category]
        parts.append(f"Contributing factors: {', '.join(others)}.")
    parts.append(f"Growth status: {growth_status}; memory: {memory_label}.")
    return " ".join(parts)


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


def global_verdict(growth_loaded: bool, missed_tickers: int) -> str:
    if not growth_loaded:
        return "OPPORTUNITY_LEDGER_NOT_READY"
    if missed_tickers >= 1:
        return "OPPORTUNITY_LEDGER_READY"
    return "OPPORTUNITY_LEDGER_NEEDS_MORE_DATA"


def build_ledger() -> dict[str, Any]:
    source_paths = {
        "tae_profit_growth_analytics.json": GROWTH_JSON,
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
        "tae_intraday_fade_history_summary.md": FADE_SUMMARY_MD,
        "tae_shadow_validation_events.csv": SHADOW_EVENTS_CSV,
        "bot_output.log": BOT_LOG,
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
    shadow = payloads["tae_profit_protection_shadow.json"]
    ppg = payloads["tae_portfolio_profit_governor.json"]
    appe = payloads["tae_adaptive_profit_policy_engine.json"]
    accounting = payloads["tae_accounting_snapshot.json"]
    validation = payloads["tae_profit_protection_validation.json"]

    shadow_by = {
        _s(p.get("ticker")).upper(): p
        for p in (shadow or {}).get("positions") or []
        if p.get("ticker")
    }
    policy = policy_context(appe, ppg)
    portfolio_verdict = _s(policy.get("portfolio_verdict"))
    policy_state = _s(policy.get("policy_state"), "UNKNOWN")

    constraint_hints = detect_portfolio_constraints(ppg, validation, accounting)

    growth_tickers = (growth or {}).get("tickers") or []
    if not growth_tickers and shadow_by:
        growth_tickers = [
            {
                "ticker": t,
                "current_pct": _f(p.get("current_pct")),
                "high_pct": _f(p.get("high_pct")),
                "drawdown": _f(p.get("drawdown_from_high_pct")),
                "missed_usd": round(_f(p.get("missed_opportunity_usd")), 2),
                "governor_recommendation": "UNKNOWN",
                "pce_verdict": "UNKNOWN",
                "memory_label": "UNKNOWN",
                "growth_status": "UNKNOWN",
            }
            for t, p in sorted(shadow_by.items())
        ]

    entries: list[dict[str, Any]] = []
    for row in growth_tickers:
        ticker = _s(row.get("ticker")).upper()
        missed_usd = round(_f(row.get("missed_usd")), 2)
        high_pct = _f(row.get("high_pct"))
        current_pct = _f(row.get("current_pct"))
        drawdown = _f(row.get("drawdown"))
        governor_rec = _s(row.get("governor_recommendation"))
        pce_verdict = _s(row.get("pce_verdict"))
        memory_label = _s(row.get("memory_label"))
        growth_status = _s(row.get("growth_status"))

        category, contributing, confidence = classify_opportunity_cost(
            ticker=ticker,
            missed_usd=missed_usd,
            high_pct=high_pct,
            current_pct=current_pct,
            drawdown=drawdown,
            governor_rec=governor_rec,
            pce_verdict=pce_verdict,
            memory_label=memory_label,
            shadow_pos=shadow_by.get(ticker),
            portfolio_constraint=constraint_hints.get(ticker),
        )
        severity = severity_for_missed(missed_usd)
        fix = CATEGORY_TO_FIX.get(category, "COLLECT_MORE_DATA")
        explanation = build_explanation(
            ticker=ticker,
            category=category,
            missed_usd=missed_usd,
            high_pct=high_pct,
            current_pct=current_pct,
            drawdown=drawdown,
            governor_rec=governor_rec,
            pce_verdict=pce_verdict,
            memory_label=memory_label,
            growth_status=growth_status,
            contributing=contributing,
        )
        entries.append(
            {
                "ticker": ticker,
                "missed_usd": missed_usd,
                "high_pct": round(high_pct, 2),
                "current_pct": round(current_pct, 2),
                "drawdown": round(drawdown, 2),
                "growth_status": growth_status,
                "governor_recommendation": governor_rec,
                "pce_verdict": pce_verdict,
                "memory_label": memory_label,
                "portfolio_verdict": portfolio_verdict,
                "policy_state": policy_state,
                "opportunity_cost_category": category,
                "contributing_causes": contributing,
                "opportunity_cost_severity": severity,
                "recommended_shadow_fix": fix,
                "confidence": confidence,
                "explanation": explanation,
            }
        )

    entries.sort(key=lambda e: e.get("missed_usd", 0), reverse=True)
    missed_entries = [e for e in entries if e.get("missed_usd", 0) > 0]

    cost_by_category: dict[str, float] = defaultdict(float)
    cost_by_severity: dict[str, float] = defaultdict(float)
    fix_impact: dict[str, float] = defaultdict(float)
    for entry in missed_entries:
        cat = entry["opportunity_cost_category"]
        sev = entry["opportunity_cost_severity"]
        usd = _f(entry.get("missed_usd"))
        cost_by_category[cat] += usd
        cost_by_severity[sev] += usd
        fix_impact[entry["recommended_shadow_fix"]] += usd

    total_cost = round(sum(_f(e.get("missed_usd")) for e in missed_entries), 2)
    critical_cost = round(
        sum(_f(e.get("missed_usd")) for e in missed_entries if e.get("opportunity_cost_severity") == "CRITICAL"),
        2,
    )
    top_5 = [e["ticker"] for e in missed_entries[:5]]
    recommended_top_fix = max(fix_impact, key=fix_impact.get) if fix_impact else "COLLECT_MORE_DATA"

    verdict = global_verdict(sources_loaded.get("tae_profit_growth_analytics.json", False), len(missed_entries))
    recommended_next = (
        "X.PROFIT-GROWTH-3 — Winner DNA Profiler"
        if verdict == "OPPORTUNITY_LEDGER_READY"
        else "Refresh growth analytics and protection shadow inputs before Winner DNA Profiler"
    )

    growth_metrics = (growth or {}).get("core_metrics") or {}

    return {
        "schema": "tae_opportunity_cost_ledger",
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
        "global_summary": {
            "total_opportunity_cost_usd": total_cost,
            "critical_cost_usd": critical_cost,
            "top_5_cost_tickers": top_5,
            "cost_by_category": {k: round(v, 2) for k, v in sorted(cost_by_category.items(), key=lambda x: -x[1])},
            "cost_by_severity": {k: round(v, 2) for k, v in sorted(cost_by_severity.items(), key=lambda x: -x[1])},
            "recommended_top_fix": recommended_top_fix,
            "portfolio_policy_context": policy,
            "growth_capture_rate": growth_metrics.get("profit_capture_rate"),
            "growth_missed_usd": growth_metrics.get("aggregate_missed_usd"),
        },
        "classification_model": {
            "categories": sorted(CATEGORIES),
            "severities": sorted(SEVERITIES),
            "category_to_fix": CATEGORY_TO_FIX,
            "thresholds": {
                "missed_usd_medium": MISSED_USD_MEDIUM,
                "missed_usd_high": MISSED_USD_HIGH,
                "missed_usd_critical": MISSED_USD_CRITICAL,
                "drawdown_severe": DRAWDOWN_SEVERE,
            },
        },
        "ledger": entries,
        "top_missed_opportunities": missed_entries[:5],
        "recommended_next_sprint": recommended_next,
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    lines = [
        "# TAE Opportunity Cost Ledger",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Global verdict:** {report['global_verdict']}",
        "",
        "> **SHADOW_ONLY read-only ledger — explains why profit was missed**",
        "",
        "## Executive summary",
        "",
        f"- Total opportunity cost: **${summary.get('total_opportunity_cost_usd')}**",
        f"- Critical-tier cost: **${summary.get('critical_cost_usd')}**",
        f"- Growth capture rate (upstream): **{summary.get('growth_capture_rate')}**",
        f"- Recommended top shadow fix: **{summary.get('recommended_top_fix')}**",
        f"- Ledger entries: **{len(report.get('ledger') or [])}** ({len(report.get('top_missed_opportunities') or [])} top missed)",
        "",
        "## Opportunity cost total",
        "",
        f"**${summary.get('total_opportunity_cost_usd')}** aggregate missed USD across "
        f"{len([e for e in report.get('ledger') or [] if e.get('missed_usd', 0) > 0])} tickers with material miss.",
        "",
        "## Cost by category",
        "",
        "| category | missed USD |",
        "| --- | --- |",
    ]
    for cat, usd in (summary.get("cost_by_category") or {}).items():
        lines.append(f"| {cat} | ${usd:.2f} |")

    lines.extend(
        [
            "",
            "## Cost by severity",
            "",
            "| severity | missed USD |",
            "| --- | --- |",
        ]
    )
    for sev, usd in (summary.get("cost_by_severity") or {}).items():
        lines.append(f"| {sev} | ${usd:.2f} |")

    lines.extend(
        [
            "",
            "## Top missed opportunities",
            "",
            "| ticker | missed USD | category | severity | fix | confidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("top_missed_opportunities") or []:
        lines.append(
            f"| {row['ticker']} | ${row.get('missed_usd')} | {row.get('opportunity_cost_category')} | "
            f"{row.get('opportunity_cost_severity')} | {row.get('recommended_shadow_fix')} | "
            f"{row.get('confidence')} |"
        )

    lines.extend(
        [
            "",
            "## Per-ticker ledger",
            "",
            "| ticker | missed | high% | cur% | category | severity | fix | growth |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("ledger") or []:
        lines.append(
            f"| {row['ticker']} | ${row.get('missed_usd')} | {row.get('high_pct')} | {row.get('current_pct')} | "
            f"{row.get('opportunity_cost_category')} | {row.get('opportunity_cost_severity')} | "
            f"{row.get('recommended_shadow_fix')} | {row.get('growth_status')} |"
        )

    lines.extend(["", "### Explanations", ""])
    for row in report.get("top_missed_opportunities") or []:
        lines.append(f"- **{row['ticker']}:** {row.get('explanation')}")

    pol = summary.get("portfolio_policy_context") or {}
    lines.extend(
        [
            "",
            "## Recommended shadow fixes",
            "",
            f"- Top portfolio-wide fix: **{summary.get('recommended_top_fix')}**",
            "",
            "| category | shadow fix |",
            "| --- | --- |",
        ]
    )
    for cat, fix in sorted(CATEGORY_TO_FIX.items()):
        lines.append(f"| {cat} | {fix} |")

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
    summary = report["global_summary"]
    print("===== TAE OPPORTUNITY COST LEDGER =====")
    print("Mode: SHADOW_ONLY — read-only")
    print("Global verdict:", report["global_verdict"])
    print("Total opportunity cost USD:", summary.get("total_opportunity_cost_usd"))
    print("Critical cost USD:", summary.get("critical_cost_usd"))
    print("Top fix:", summary.get("recommended_top_fix"))
    print("Top tickers:", ", ".join(summary.get("top_5_cost_tickers") or []))


def main() -> int:
    report = build_ledger()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
