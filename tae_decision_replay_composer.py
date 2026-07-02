#!/usr/bin/env python3
"""
TAE Decision Replay Composer — X.REPLAY-1.

SHADOW_ONLY consolidation VIEW over existing performance SSOT outputs.
Does NOT rebuild attribution, protection validation, or cooldown logic.
Does NOT modify live_bot, portfolio, or signals.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PORTFOLIO_FILE = Path("portfolio.csv")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
PROTECT_JSON = Path("tae_profit_protection_validation.json")
COOLDOWN_JSON = Path("tae_stop_reentry_cooldown_audit.json")
KNOWLEDGE_JSON = Path("tae_knowledge_base.json")
ATTRIBUTION_JSON = Path("tae_profit_attribution.json")
PIPELINE_JSON = Path("tae_performance_pipeline_report.json")
DECISION_REGISTRY = Path("decision_registry.csv")
LEGACY_REPLAY_TXT = Path("decision_replay_summary.txt")

OUTPUT_JSON = Path("tae_decision_replay.json")
OUTPUT_MD = Path("tae_decision_replay.md")

FAILURE_MODES = frozenset(
    {
        "MISSED_PROFIT_PROTECTION",
        "STOP_REENTRY_CHURN",
        "SCORE_PERSISTENCE_AFTER_STOP",
        "LEGACY_CLOSED_FREEZE_DRAG",
        "ENTRY_QUALITY_ISSUE",
        "EXIT_TIMING_ISSUE",
        "DATA_ISSUE",
        "UNCLASSIFIED",
    }
)

SHADOW_RECOMMENDATIONS = frozenset(
    {
        "CONTINUE_OBSERVATION",
        "TEST_TRAILING_SHADOW",
        "TEST_15M_COOLDOWN_SHADOW",
        "DO_NOT_PROMOTE_TO_LIVE",
        "DO_NOT_PROMOTE_TO_ADVISORY_YET",
        "INSUFFICIENT_DATA",
    }
)

FORBIDDEN = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT"})

READINESS_ORDER = {"NOT_READY": 0, "WATCH": 1, "READY_FOR_SHADOW_ADVISORY": 2}


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def normalize_accounting(data: dict[str, Any] | None, *, loaded: bool) -> dict[str, Any]:
    if not loaded or not data:
        return {
            "loaded": False,
            "total_pnl": None,
            "realized_pnl": None,
            "unrealized_pnl": None,
            "open_positions_count": 0,
        }
    return {
        "loaded": True,
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "total_pnl": data.get("corrected_total_trading_pnl"),
        "realized_pnl": data.get("corrected_realized_pnl"),
        "unrealized_pnl": data.get("corrected_unrealized_pnl"),
        "account_value": data.get("account_value_corrected"),
        "open_positions_count": data.get("open_positions_count", 0),
        "data_quality": data.get("data_quality_status"),
    }


def normalize_protect(data: dict[str, Any] | None, *, loaded: bool) -> dict[str, Any]:
    if not loaded or not data:
        return {"loaded": False}
    best = data.get("best_strategy") or {}
    hold = data.get("hold_baseline") or {}
    gates = data.get("gates") or {}
    return {
        "loaded": True,
        "generated_at": data.get("generated_at"),
        "verdict": data.get("verdict"),
        "observations": (data.get("dataset_health") or {}).get("observations"),
        "confidence": (data.get("dataset_health") or {}).get("confidence"),
        "best_strategy_id": best.get("strategy_id"),
        "best_strategy_total": best.get("total_value"),
        "hold_baseline_total": hold.get("total_value"),
        "protection_delta_vs_hold": best.get("delta_vs_hold_total"),
        "advisory_readiness": gates.get("advisory_readiness", "NOT_READY"),
        "gates_passed": gates.get("gates_passed", False),
        "failed_gates": gates.get("failed_gates", []),
        "ticker_breakdown": data.get("ticker_breakdown") or [],
        "daily_breakdown": data.get("daily_breakdown") or [],
        "recommendations": data.get("recommendations") or [],
    }


def normalize_cooldown(data: dict[str, Any] | None, *, loaded: bool) -> dict[str, Any]:
    if not loaded or not data:
        return {"loaded": False}
    gates = data.get("gates") or {}
    summary = data.get("summary") or {}
    sims = (data.get("cooldown_simulation") or {}).get("simulations") or {}
    best_name = (data.get("cooldown_simulation") or {}).get("best_cooldown")
    best_sim = sims.get(best_name or "", {})
    return {
        "loaded": True,
        "generated_at": data.get("generated_at"),
        "verdict": data.get("verdict"),
        "stop_reentry_cases": (data.get("dataset_health") or {}).get("stop_reentry_cases"),
        "immediate_reentries": summary.get("immediate_reentries"),
        "second_stop_count": summary.get("second_stop_count"),
        "best_cooldown_policy": best_name,
        "cooldown_net_effect": best_sim.get("net_effect_usd"),
        "avoided_loss_usd": best_sim.get("avoided_loss_usd"),
        "missed_gain_usd": best_sim.get("missed_gain_usd"),
        "advisory_readiness": gates.get("advisory_readiness", "NOT_READY"),
        "gates_passed": gates.get("gates_passed", False),
        "failed_gates": gates.get("failed_gates", []),
        "sequences": data.get("stop_reentry_sequences") or [],
        "score_persistence": data.get("score_persistence") or {},
        "recommendations": data.get("recommendations") or [],
    }


def filter_knowledge_entries(data: dict[str, Any] | None, *, loaded: bool) -> list[dict[str, Any]]:
    if not loaded or not data:
        return []
    keywords = (
        "fade",
        "trailing",
        "partial",
        "protection",
        "reentry",
        "stop",
        "intraday",
        "shadow",
    )
    relevant: list[dict[str, Any]] = []
    for entry in data.get("entries") or []:
        blob = " ".join(
            str(entry.get(k, ""))
            for k in ("title", "description", "pattern_type", "recommendation", "category", "subject")
        ).lower()
        if any(k in blob for k in keywords):
            relevant.append(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "pattern_type": entry.get("pattern_type"),
                    "status": entry.get("status"),
                    "confidence": entry.get("confidence"),
                    "recommendation": entry.get("recommendation"),
                    "subject": entry.get("subject"),
                }
            )
    return relevant[:20]


def scan_legacy_freeze_drag(portfolio_path: Path) -> dict[str, Any]:
    if not portfolio_path.is_file():
        return {"loaded": False, "total_drag_usd": 0.0, "count": 0}
    try:
        df = pd.read_csv(portfolio_path)
    except (OSError, pd.errors.EmptyDataError):
        return {"loaded": False, "total_drag_usd": 0.0, "count": 0}
    if df.empty or "Reason" not in df.columns:
        return {"loaded": True, "total_drag_usd": 0.0, "count": 0}
    mask = df["Reason"].astype(str).str.contains("CLOSED_FREEZE", case=False, na=False)
    subset = df[mask]
    pnl = pd.to_numeric(subset.get("PnL"), errors="coerce").fillna(0)
    negative = pnl[pnl < 0]
    return {
        "loaded": True,
        "total_drag_usd": round(float(negative.sum()), 2),
        "count": int(len(subset)),
        "negative_row_count": int(len(negative)),
    }


def merge_advisory_readiness(protect: dict[str, Any], cooldown: dict[str, Any]) -> dict[str, Any]:
    p = protect.get("advisory_readiness", "NOT_READY") if protect.get("loaded") else "NOT_READY"
    c = cooldown.get("advisory_readiness", "NOT_READY") if cooldown.get("loaded") else "NOT_READY"
    if p == "READY_FOR_SHADOW_ADVISORY" and c == "READY_FOR_SHADOW_ADVISORY":
        final = "READY_FOR_SHADOW_ADVISORY"
    elif p == "NOT_READY" or c == "NOT_READY":
        final = "NOT_READY"
    elif p == "WATCH" or c == "WATCH":
        final = "WATCH"
    else:
        final = "NOT_READY"
    return {
        "protect_readiness": p if protect.get("loaded") else None,
        "cooldown_readiness": c if cooldown.get("loaded") else None,
        "final_status": final,
        "protect_gates_passed": protect.get("gates_passed"),
        "cooldown_gates_passed": cooldown.get("gates_passed"),
    }


def build_counterfactual_comparison(protect: dict[str, Any], cooldown: dict[str, Any]) -> dict[str, Any]:
    hold = protect.get("hold_baseline_total") if protect.get("loaded") else None
    protection_delta = protect.get("protection_delta_vs_hold")
    cooldown_net = cooldown.get("cooldown_net_effect")
    combined = None
    methodology = "UNAVAILABLE"
    double_count_warning = True
    if protection_delta is not None and cooldown_net is not None:
        combined = round(float(protection_delta) + float(cooldown_net), 2)
        methodology = "ESTIMATED"
        double_count_warning = True
    return {
        "hold_baseline_usd": hold,
        "best_protection_strategy": protect.get("best_strategy_id"),
        "protection_strategy_total_usd": protect.get("best_strategy_total"),
        "protection_delta_vs_hold_usd": protection_delta,
        "best_cooldown_policy": cooldown.get("best_cooldown_policy"),
        "cooldown_net_effect_usd": cooldown_net,
        "combined_theoretical_effect_usd": combined,
        "combined_methodology": methodology,
        "double_count_warning": double_count_warning,
        "double_count_note": (
            "Protection and cooldown effects may overlap on same tickers (e.g. MU, PM, LLY). "
            "Combined total is indicative only — not additive proof."
            if double_count_warning
            else ""
        ),
    }


def classify_failure_modes(
    protect: dict[str, Any],
    cooldown: dict[str, Any],
    legacy: dict[str, Any],
    sources: dict[str, bool],
) -> list[dict[str, Any]]:
    modes: list[dict[str, Any]] = []

    if not sources.get("tae_profit_protection_validation.json"):
        modes.append(
            {
                "mode": "DATA_ISSUE",
                "severity": "HIGH",
                "detail": "PROTECT-2 validation output missing",
                "evidence_source": "tae_profit_protection_validation.json",
            }
        )
    elif protect.get("protection_delta_vs_hold") and protect["protection_delta_vs_hold"] > 100:
        modes.append(
            {
                "mode": "MISSED_PROFIT_PROTECTION",
                "severity": "HIGH",
                "detail": f"Shadow trailing delta vs HOLD +{protect['protection_delta_vs_hold']} USD",
                "evidence_source": "tae_profit_protection_validation.json",
                "confidence": protect.get("confidence", "LOW"),
            }
        )

    if cooldown.get("loaded"):
        if cooldown.get("immediate_reentries", 0) >= 3:
            modes.append(
                {
                    "mode": "STOP_REENTRY_CHURN",
                    "severity": "HIGH",
                    "detail": f"{cooldown['immediate_reentries']} immediate reentries after STOP",
                    "evidence_source": "tae_stop_reentry_cooldown_audit.json",
                    "confidence": "MEDIUM" if cooldown.get("stop_reentry_cases", 0) >= 5 else "LOW",
                }
            )
        sp = cooldown.get("score_persistence") or {}
        if sp.get("count", 0) >= 3:
            modes.append(
                {
                    "mode": "SCORE_PERSISTENCE_AFTER_STOP",
                    "severity": "MEDIUM",
                    "detail": f"{sp['count']} reentries with score≥80 + STRONG BUY after STOP",
                    "evidence_source": "tae_stop_reentry_cooldown_audit.json",
                    "confidence": "MEDIUM",
                }
            )

    if legacy.get("loaded") and legacy.get("total_drag_usd", 0) < -50:
        modes.append(
            {
                "mode": "LEGACY_CLOSED_FREEZE_DRAG",
                "severity": "MEDIUM",
                "detail": f"CLOSED_FREEZE rows cumulative drag {legacy['total_drag_usd']} USD",
                "evidence_source": "portfolio.csv",
                "confidence": "MEDIUM",
            }
        )

    if protect.get("loaded") and not modes:
        modes.append(
            {
                "mode": "UNCLASSIFIED",
                "severity": "LOW",
                "detail": "Insufficient cross-source attribution",
                "evidence_source": "composer",
                "confidence": "LOW",
            }
        )

    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(modes, key=lambda m: severity_rank.get(m.get("severity", "LOW"), 9))


def build_top_costly_decisions(
    protect: dict[str, Any],
    cooldown: dict[str, Any],
    accounting: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []

    for seq in cooldown.get("sequences") or []:
        leg_pnl = float(seq.get("leg_pnl") or 0)
        if seq.get("outcome") == "REENTRY_SECOND_STOP" or (
            seq.get("second_stop") and leg_pnl < 0
        ):
            cost = abs(leg_pnl)
            decisions.append(
                {
                    "ticker": seq.get("ticker"),
                    "event_type": "STOP_REENTRY",
                    "timestamp": seq.get("reentry_timestamp"),
                    "real_outcome_usd": leg_pnl,
                    "best_counterfactual": f"Apply {cooldown.get('best_cooldown_policy', 'cooldown_15m')}",
                    "estimated_delta_usd": cost,
                    "failure_mode": "STOP_REENTRY_CHURN",
                    "confidence": seq.get("pnl_methodology", "ESTIMATED"),
                    "evidence_source": "tae_stop_reentry_cooldown_audit.json",
                    "detail": (
                        f"STOP→BUY after {seq.get('minutes_after_stop')}m; "
                        f"outcome={seq.get('outcome')}"
                    ),
                }
            )

    for row in protect.get("ticker_breakdown") or []:
        missed = float(row.get("total_missed_opportunity") or 0)
        if missed < 50:
            continue
        hold_implied_cost = missed
        decisions.append(
            {
                "ticker": row.get("ticker"),
                "event_type": "INTRADAY_FADE",
                "timestamp": None,
                "real_outcome_usd": None,
                "best_counterfactual": row.get("best_strategy", "shadow_trailing_1"),
                "estimated_delta_usd": round(hold_implied_cost, 2),
                "failure_mode": "MISSED_PROFIT_PROTECTION",
                "confidence": row.get("confidence", "LOW"),
                "evidence_source": "tae_profit_protection_validation.json",
                "detail": f"Missed opportunity {missed} USD; fade observations={row.get('observations')}",
            }
        )

    decisions.sort(key=lambda d: d.get("estimated_delta_usd", 0), reverse=True)
    return decisions[:15]


def build_final_verdict(
    failure_modes: list[dict[str, Any]],
    counterfactual: dict[str, Any],
    readiness: dict[str, Any],
    protect: dict[str, Any],
    cooldown: dict[str, Any],
    sources: dict[str, bool],
) -> dict[str, Any]:
    primary = failure_modes[0]["mode"] if failure_modes else "UNCLASSIFIED"
    secondary = failure_modes[1]["mode"] if len(failure_modes) > 1 else None
    best_hypothesis = protect.get("best_strategy_id") or "shadow_trailing_1"
    needs_data = []
    if protect.get("observations", 0) < 30:
        needs_data.append(">=30 fade history observations (PROTECT-2 G1)")
    if cooldown.get("stop_reentry_cases", 0) < 10:
        needs_data.append(">=10 stop-reentry cases (COOLDOWN-1 G1)")
    do_not_promote = []
    if readiness["final_status"] != "READY_FOR_SHADOW_ADVISORY":
        do_not_promote.append("Shadow advisory — gates not passed")
    do_not_promote.extend(
        r
        for r in (protect.get("recommendations") or []) + (cooldown.get("recommendations") or [])
        if "DO_NOT_PROMOTE" in str(r)
    )

    if readiness["final_status"] == "READY_FOR_SHADOW_ADVISORY":
        next_module = "X.KNOWLEDGE-1B Confidence Evolution"
    elif primary == "SCORE_PERSISTENCE_AFTER_STOP":
        next_module = "X.KNOWLEDGE-1B Confidence Evolution"
    elif not sources.get("tae_profit_protection_validation.json") or not sources.get("tae_stop_reentry_cooldown_audit.json"):
        next_module = "Continue observation — refresh SSOT inputs"
    else:
        next_module = "Continue observation until >=30 PROTECT-2 samples; then X.KNOWLEDGE-1B"

    return {
        "primary_cause": primary,
        "secondary_cause": secondary,
        "best_shadow_hypothesis": best_hypothesis,
        "needs_more_data": needs_data,
        "do_not_promote_yet": list(dict.fromkeys(do_not_promote)),
        "recommended_next_module": next_module,
        "profit_stagnation_summary": (
            "Intraday gains evaporate (exit/protection gap) while rapid STOP→reentry churn "
            "compounds losses on high-score names."
            if primary == "MISSED_PROFIT_PROTECTION"
            else "Mixed performance drivers — see failure mode attribution."
        ),
    }


def build_replay_report(
    *,
    portfolio_path: Path = PORTFOLIO_FILE,
    accounting_path: Path = ACCOUNTING_JSON,
    protect_path: Path = PROTECT_JSON,
    cooldown_path: Path = COOLDOWN_JSON,
    knowledge_path: Path = KNOWLEDGE_JSON,
    attribution_path: Path = ATTRIBUTION_JSON,
    pipeline_path: Path = PIPELINE_JSON,
) -> dict[str, Any]:
    acct_raw, acct_ok = load_json(accounting_path)
    protect_raw, protect_ok = load_json(protect_path)
    cooldown_raw, cooldown_ok = load_json(cooldown_path)
    knowledge_raw, knowledge_ok = load_json(knowledge_path)
    attribution_raw, attribution_ok = load_json(attribution_path)
    pipeline_raw, pipeline_ok = load_json(pipeline_path)

    sources = {
        "portfolio.csv": portfolio_path.is_file(),
        "tae_accounting_snapshot.json": acct_ok,
        "tae_profit_protection_validation.json": protect_ok,
        "tae_stop_reentry_cooldown_audit.json": cooldown_ok,
        "tae_knowledge_base.json": knowledge_ok,
        "tae_profit_attribution.json": attribution_ok,
        "tae_performance_pipeline_report.json": pipeline_ok,
        "decision_registry.csv": DECISION_REGISTRY.is_file(),
        "decision_replay_summary.txt": LEGACY_REPLAY_TXT.is_file(),
    }

    accounting = normalize_accounting(acct_raw, loaded=acct_ok)
    protect = normalize_protect(protect_raw, loaded=protect_ok)
    cooldown = normalize_cooldown(cooldown_raw, loaded=cooldown_ok)
    knowledge_entries = filter_knowledge_entries(knowledge_raw, loaded=knowledge_ok)
    legacy = scan_legacy_freeze_drag(portfolio_path)

    counterfactual = build_counterfactual_comparison(protect, cooldown)
    failure_modes = classify_failure_modes(protect, cooldown, legacy, sources)
    top_decisions = build_top_costly_decisions(protect, cooldown, accounting)
    readiness = merge_advisory_readiness(protect, cooldown)
    verdict = build_final_verdict(
        failure_modes, counterfactual, readiness, protect, cooldown, sources
    )

    recommendations = list(
        dict.fromkeys(
            (protect.get("recommendations") or [])
            + (cooldown.get("recommendations") or [])
            + ["CONTINUE_OBSERVATION", "DO_NOT_PROMOTE_TO_LIVE"]
        )
    )
    recommendations = [r for r in recommendations if r in SHADOW_RECOMMENDATIONS or "SHADOW" in r or "PROMOTE" in r]
    assert not (set(recommendations) & FORBIDDEN)

    return {
        "schema": "tae_decision_replay",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "composer_note": "Consolidation VIEW — does not replace upstream SSOT files.",
        "sources_loaded": sources,
        "replay_summary": {
            "accounting": accounting,
            "profit_protection": {
                "best_strategy": protect.get("best_strategy_id"),
                "best_strategy_total_usd": protect.get("best_strategy_total"),
                "protection_delta_vs_hold_usd": protect.get("protection_delta_vs_hold"),
                "advisory_readiness": protect.get("advisory_readiness"),
            },
            "cooldown": {
                "best_policy": cooldown.get("best_cooldown_policy"),
                "net_effect_usd": cooldown.get("cooldown_net_effect"),
                "advisory_readiness": cooldown.get("advisory_readiness"),
            },
            "legacy_closed_freeze": legacy,
            "knowledge_relevant_entries": knowledge_entries,
            "optional_attribution_loaded": attribution_ok,
            "optional_pipeline_loaded": pipeline_ok,
        },
        "failure_mode_attribution": failure_modes,
        "counterfactual_comparison": counterfactual,
        "top_costly_decisions": top_decisions,
        "promotion_readiness": readiness,
        "final_verdict": verdict,
        "recommendations": recommendations,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("replay_summary") or {}
    acct = summary.get("accounting") or {}
    prot = summary.get("profit_protection") or {}
    cool = summary.get("cooldown") or {}
    cf = report.get("counterfactual_comparison") or {}
    verdict = report.get("final_verdict") or {}
    readiness = report.get("promotion_readiness") or {}

    lines = [
        "# TAE Decision Replay (X.REPLAY-1 Composer)",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} | **Live impact:** {report['live_trading_impact']}",
        "",
        "> SHADOW_ONLY — This report composes existing validation outputs. "
        "It does not execute trades or modify live_bot.",
        "",
        "## Executive summary",
        "",
        f"- **Primary cause:** {verdict.get('primary_cause')}",
        f"- **Secondary cause:** {verdict.get('secondary_cause') or 'n/a'}",
        f"- **Best shadow hypothesis:** {verdict.get('best_shadow_hypothesis')}",
        f"- **Promotion readiness:** {readiness.get('final_status')}",
        "",
        verdict.get("profit_stagnation_summary", ""),
        "",
        "## Sources loaded",
        "",
    ]
    for name, ok in (report.get("sources_loaded") or {}).items():
        lines.append(f"- {'✅' if ok else '❌'} {name}")
    lines.extend(
        [
            "",
            "## PnL summary (accounting SSOT)",
            f"- Total trading PnL: **{acct.get('total_pnl')} USD**",
            f"- Realized: {acct.get('realized_pnl')} USD",
            f"- Unrealized: {acct.get('unrealized_pnl')} USD",
            "",
            "## Failure mode attribution",
            "",
        ]
    )
    for fm in report.get("failure_mode_attribution") or []:
        lines.append(
            f"- **{fm['mode']}** ({fm['severity']}) — {fm['detail']} "
            f"[{fm.get('evidence_source')}]"
        )
    lines.extend(
        [
            "",
            "## Counterfactual comparison",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| HOLD baseline (shadow book) | {cf.get('hold_baseline_usd')} USD |",
            f"| Best protection ({cf.get('best_protection_strategy')}) | {cf.get('protection_strategy_total_usd')} USD |",
            f"| Protection Δ vs HOLD | **{cf.get('protection_delta_vs_hold_usd')} USD** |",
            f"| Best cooldown ({cf.get('best_cooldown_policy')}) net | **{cf.get('cooldown_net_effect_usd')} USD** |",
            f"| Combined (ESTIMATED) | {cf.get('combined_theoretical_effect_usd')} USD |",
            "",
        ]
    )
    if cf.get("double_count_warning"):
        lines.append(f"⚠️ {cf.get('double_count_note')}")
        lines.append("")
    lines.extend(["## Top costly decisions", ""])
    for i, d in enumerate(report.get("top_costly_decisions") or [], 1):
        lines.append(
            f"{i}. **{d['ticker']}** — {d['event_type']}: {d.get('detail', '')} "
            f"| Δ est. **{d.get('estimated_delta_usd')} USD** | "
            f"counterfactual: {d.get('best_counterfactual')} | {d.get('failure_mode')}"
        )
    lines.extend(
        [
            "",
            "## Promotion readiness",
            f"- PROTECT-2: {readiness.get('protect_readiness')} (gates passed: {readiness.get('protect_gates_passed')})",
            f"- COOLDOWN-1: {readiness.get('cooldown_readiness')} (gates passed: {readiness.get('cooldown_gates_passed')})",
            f"- **Final:** {readiness.get('final_status')}",
            "",
            "## Final recommendation",
            f"- Next module: **{verdict.get('recommended_next_module')}**",
            f"- Needs more data: {', '.join(verdict.get('needs_more_data') or []) or 'none'}",
            f"- Do NOT promote yet: {', '.join(verdict.get('do_not_promote_yet') or [])}",
            "",
            "## Recommendations (SHADOW_ONLY)",
            "",
        ]
    )
    for r in report.get("recommendations") or []:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("*Composer VIEW only. Upstream SSOT files remain authoritative.*")
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    verdict = report.get("final_verdict") or {}
    readiness = report.get("promotion_readiness") or {}
    cf = report.get("counterfactual_comparison") or {}
    print("===== TAE DECISION REPLAY COMPOSER (X.REPLAY-1) =====")
    print("Mode: SHADOW_ONLY")
    print("Primary cause:", verdict.get("primary_cause"))
    print("Best shadow hypothesis:", verdict.get("best_shadow_hypothesis"))
    print("Protection delta:", cf.get("protection_delta_vs_hold_usd"))
    print("Cooldown net:", cf.get("cooldown_net_effect_usd"))
    print("Combined (ESTIMATED):", cf.get("combined_theoretical_effect_usd"))
    print("Promotion readiness:", readiness.get("final_status"))
    print("Next:", verdict.get("recommended_next_module"))


def main() -> int:
    report = build_replay_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
