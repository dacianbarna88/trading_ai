#!/usr/bin/env python3
"""
TAE Profit Decision Governor v1 — SHADOW_ONLY / NO_BROKER.

Read-only materialized VIEW over the profit protect pipeline.
Consumes existing JSON outputs only — does not re-run upstream engines.
Does NOT modify live_bot, portfolio, broker, or execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

SHADOW_JSON = Path("tae_profit_protection_shadow.json")
BRAIN_JSON = Path("tae_profit_intelligence_brain.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
COMMITTEE_JSON = Path("tae_profit_decision_committee.json")
LEARNING_JSON = Path("tae_profit_committee_learning.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
CONTEXT_LEARNING_JSON = Path("tae_profit_context_learning.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")

OUTPUT_JSON = Path("tae_profit_decision_governor.json")
OUTPUT_MD = Path("tae_profit_decision_governor.md")

REC_RANK: dict[str, float] = {
    "EXIT_PROTECT_SHADOW": 5.0,
    "PARTIAL_PROTECT_SHADOW": 4.0,
    "TRAIL_PROTECT_SHADOW": 3.0,
    "WATCH": 2.0,
    "OBSERVE": 1.0,
    "HOLD": 0.0,
    "NO_ACTION": 0.0,
}

CONTEXT_RANK: dict[str, float] = {
    "PROTECT_NOW": 5.0,
    "CONTEXT_WEAKENING": 3.0,
    "NORMAL_PULLBACK": 2.0,
    "KEEP_WINNER": 0.0,
    "UNKNOWN_CONTEXT": 1.0,
}

RANK_TO_REC = (
    (4.5, "EXIT_PROTECT_SHADOW"),
    (3.5, "PARTIAL_PROTECT_SHADOW"),
    (2.5, "TRAIL_PROTECT_SHADOW"),
    (1.5, "WATCH"),
    (0.5, "OBSERVE"),
    (-1.0, "HOLD"),
)

POSTURES = frozenset(
    {
        "KEEP_WINNER_SHADOW",
        "TRAIL_SHADOW",
        "PROTECT_SHADOW",
        "WATCH_SHADOW",
        "OBSERVE_SHADOW",
        "INSUFFICIENT_DATA",
    }
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


def rank_to_recommendation(combined_rank: float) -> str:
    for threshold, rec in RANK_TO_REC:
        if combined_rank >= threshold:
            return rec
    return "HOLD"


def recommendation_to_posture(rec: str) -> str:
    if rec in {"EXIT_PROTECT_SHADOW", "PARTIAL_PROTECT_SHADOW"}:
        return "PROTECT_SHADOW"
    if rec == "TRAIL_PROTECT_SHADOW":
        return "TRAIL_SHADOW"
    if rec == "WATCH":
        return "WATCH_SHADOW"
    if rec in {"OBSERVE", "NO_ACTION"}:
        return "OBSERVE_SHADOW"
    if rec == "HOLD":
        return "KEEP_WINNER_SHADOW"
    return "WATCH_SHADOW"


def compute_alignment(pdc_rank: float, ctx_rank: float) -> str:
    delta = ctx_rank - pdc_rank
    if abs(delta) <= 1.0:
        return "ALIGNED"
    if delta < -1.0:
        return "CONTEXT_SOFTENS"
    if delta > 1.0:
        return "CONTEXT_ESCALATES"
    return "DIVERGENT"


def compute_confidence(
    alignment: str,
    pdc_confidence: str,
    context_confidence: str,
    sources_present: int,
) -> str:
    if sources_present < 4:
        return "LOW"
    if alignment == "DIVERGENT":
        return "MEDIUM" if pdc_confidence == "HIGH" or context_confidence == "HIGH" else "LOW"
    if pdc_confidence == "HIGH" and context_confidence == "HIGH":
        return "HIGH"
    if pdc_confidence == "HIGH" or context_confidence == "HIGH":
        return "MEDIUM"
    return "LOW"


def reconcile_ticker(
    *,
    ticker: str,
    committee_row: dict[str, Any] | None,
    weighted_row: dict[str, Any] | None,
    context_row: dict[str, Any] | None,
    shadow_row: dict[str, Any] | None,
    sources_present: int,
) -> dict[str, Any]:
    if not committee_row and not context_row:
        return {
            "ticker": ticker,
            "governor_posture": "INSUFFICIENT_DATA",
            "final_shadow_recommendation": "NO_ACTION",
            "governor_score": 0.0,
            "alignment": "INSUFFICIENT_DATA",
            "confidence": "LOW",
            "explanation": f"SHADOW_ONLY governor for {ticker}: insufficient upstream data.",
            "sources": [],
            "shadow_only": True,
        }

    pdc_v1 = str((committee_row or {}).get("final_committee_recommendation") or "NO_ACTION")
    pdc_weighted = str(
        (weighted_row or {}).get("weighted_committee_recommendation")
        or pdc_v1
    )
    pdc_score = _f((committee_row or {}).get("protection_score"))
    pdc_confidence = str((committee_row or {}).get("confidence") or "LOW")

    context_verdict = str((context_row or {}).get("context_verdict") or "UNKNOWN_CONTEXT")
    context_score = _f((context_row or {}).get("profit_context_score"))
    context_confidence = str((context_row or {}).get("confidence") or "LOW")

    current_pct = _f((committee_row or context_row or {}).get("current_pct"))
    high_pct = _f((committee_row or context_row or {}).get("high_pct"))
    drawdown = _f((committee_row or context_row or {}).get("drawdown"))

    pdc_rank = REC_RANK.get(pdc_weighted, REC_RANK.get(pdc_v1, 2.0))
    ctx_rank = CONTEXT_RANK.get(context_verdict, 1.0)
    combined_rank = pdc_rank * 0.55 + ctx_rank * 0.45

    inv_protect = max(0.0, 100.0 - pdc_score)
    governor_score = round(context_score * 0.5 + inv_protect * 0.5, 1)

    final_rec = rank_to_recommendation(combined_rank)
    posture = recommendation_to_posture(final_rec)
    alignment = compute_alignment(pdc_rank, ctx_rank)
    confidence = compute_confidence(alignment, pdc_confidence, context_confidence, sources_present)

    notes: list[str] = []
    rules = (shadow_row or {}).get("rules_v1") or {}
    if rules.get("profit_at_risk"):
        notes.append("Profit-at-risk rule active")
        if REC_RANK.get(final_rec, 0) < REC_RANK["WATCH"]:
            final_rec = "WATCH"
            posture = "WATCH_SHADOW"
    if rules.get("profit_lock_active"):
        notes.append("Profit lock active")

    if current_pct <= 0 and high_pct >= 4.0:
        notes.append("Safety: PnL ≤ 0 with large prior peak — cannot keep winner posture")
        if posture == "KEEP_WINNER_SHADOW":
            posture = "WATCH_SHADOW"
            if REC_RANK.get(final_rec, 0) < REC_RANK["WATCH"]:
                final_rec = "WATCH"

    if alignment == "CONTEXT_SOFTENS" and final_rec != pdc_weighted:
        notes.append(f"Context softens committee ({pdc_weighted} → {final_rec})")
    elif alignment == "CONTEXT_ESCALATES" and final_rec != pdc_weighted:
        notes.append(f"Context escalates committee ({pdc_weighted} → {final_rec})")

    sources = []
    if committee_row:
        sources.append("tae_profit_decision_committee.json")
    if context_row:
        sources.append("tae_profit_context_engine.json")
    if shadow_row:
        sources.append("tae_profit_protection_shadow.json")

    explanation = (
        f"SHADOW_ONLY governor for {ticker}: PDC={pdc_weighted} (v1={pdc_v1}), "
        f"PCE={context_verdict} (score={context_score}), "
        f"combined_rank={combined_rank:.2f} → {final_rec} ({posture}). "
        f"Alignment={alignment}, governor_score={governor_score}."
    )
    if notes:
        explanation += " " + "; ".join(notes) + "."

    return {
        "ticker": ticker,
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown": round(drawdown, 2),
        "pdc_v1_recommendation": pdc_v1,
        "pdc_weighted_recommendation": pdc_weighted,
        "pdc_protection_score": round(pdc_score, 1),
        "pce_context_verdict": context_verdict,
        "profit_context_score": round(context_score, 1),
        "governor_score": governor_score,
        "governor_posture": posture,
        "final_shadow_recommendation": final_rec,
        "alignment": alignment,
        "confidence": confidence,
        "combined_rank": round(combined_rank, 2),
        "advisory_notes": notes,
        "explanation": explanation,
        "sources": sources,
        "shadow_only": True,
    }


def build_blockers(
    sources_loaded: dict[str, bool],
    validation: dict[str, Any] | None,
    committee: dict[str, Any] | None,
    context: dict[str, Any] | None,
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    required = ("tae_profit_decision_committee.json", "tae_profit_context_engine.json")
    for key in required:
        if not sources_loaded.get(key):
            blockers.append(
                {
                    "code": "MISSING_SOURCE",
                    "detail": key,
                    "source": "tae_profit_decision_governor.py",
                }
            )

    gates = (validation or {}).get("gates") or {}
    if gates.get("failed_gates"):
        blockers.append(
            {
                "code": "VALIDATION_GATES_FAILED",
                "detail": ", ".join(str(g) for g in gates.get("failed_gates") or []),
                "source": "tae_profit_protection_validation.json",
            }
        )
    if (validation or {}).get("verdict") == "PROMISING_BUT_NOT_READY":
        blockers.append(
            {
                "code": "VALIDATION_NOT_READY",
                "detail": str((validation or {}).get("verdict")),
                "source": "tae_profit_protection_validation.json",
            }
        )

    committee_verdict = ((committee or {}).get("global_summary") or {}).get("final_verdict")
    if committee_verdict and "NOT_READY" in str(committee_verdict):
        blockers.append(
            {
                "code": "COMMITTEE_NOT_READY",
                "detail": str(committee_verdict),
                "source": "tae_profit_decision_committee.json",
            }
        )

    context_verdict = ((context or {}).get("global_summary") or {}).get("final_verdict")
    if context_verdict and "NOT_READY" in str(context_verdict):
        blockers.append(
            {
                "code": "CONTEXT_NOT_READY",
                "detail": str(context_verdict),
                "source": "tae_profit_context_engine.json",
            }
        )

    blockers.append(
        {
            "code": "SHADOW_ONLY",
            "detail": "No live or advisory integration — observation VIEW only",
            "source": "tae_profit_decision_governor.py",
        }
    )
    return blockers


def build_governor_report() -> dict[str, Any]:
    source_paths = {
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_profit_intelligence_brain.json": BRAIN_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_decision_committee.json": COMMITTEE_JSON,
        "tae_profit_committee_learning.json": LEARNING_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_context_learning.json": CONTEXT_LEARNING_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data

    committee = payloads["tae_profit_decision_committee.json"]
    context = payloads["tae_profit_context_engine.json"]
    learning = payloads["tae_profit_committee_learning.json"]
    context_learning = payloads["tae_profit_context_learning.json"]
    validation = payloads["tae_profit_protection_validation.json"]
    shadow = payloads["tae_profit_protection_shadow.json"]

    committee_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (committee or {}).get("tickers") or []
        if r.get("ticker")
    }
    weighted_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (committee or {}).get("weighted_tickers") or []
        if r.get("ticker")
    }
    context_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (context or {}).get("tickers") or []
        if r.get("ticker")
    }
    shadow_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (shadow or {}).get("positions") or []
        if r.get("ticker")
    }

    tickers_set = set(committee_by) | set(context_by)
    sources_present = sum(1 for v in sources_loaded.values() if v)

    ticker_postures: list[dict[str, Any]] = []
    for ticker in sorted(tickers_set):
        ticker_postures.append(
            reconcile_ticker(
                ticker=ticker,
                committee_row=committee_by.get(ticker),
                weighted_row=weighted_by.get(ticker),
                context_row=context_by.get(ticker),
                shadow_row=shadow_by.get(ticker),
                sources_present=sources_present,
            )
        )

    ticker_postures.sort(key=lambda r: (REC_RANK.get(r.get("final_shadow_recommendation", ""), 0), -r.get("governor_score", 0)))

    posture_counts = {p: 0 for p in POSTURES}
    alignment_counts: dict[str, int] = {}
    for row in ticker_postures:
        posture = row.get("governor_posture", "INSUFFICIENT_DATA")
        posture_counts[posture] = posture_counts.get(posture, 0) + 1
        align = row.get("alignment", "UNKNOWN")
        alignment_counts[align] = alignment_counts.get(align, 0) + 1

    scores = [r.get("governor_score", 0) for r in ticker_postures]
    protect_rows = [r for r in ticker_postures if r.get("governor_posture") == "PROTECT_SHADOW"]
    keep_rows = sorted(
        [r for r in ticker_postures if r.get("governor_posture") == "KEEP_WINNER_SHADOW"],
        key=lambda r: r.get("governor_score", 0),
        reverse=True,
    )

    gates = (validation or {}).get("gates") or {}
    validation_readiness = gates.get("advisory_readiness") or (validation or {}).get("verdict") or "UNKNOWN"

    committee_ok = sources_loaded["tae_profit_decision_committee.json"]
    context_ok = sources_loaded["tae_profit_context_engine.json"]
    if not committee_ok or not context_ok:
        final_verdict = "PDG_NOT_READY"
        overall_posture = "INSUFFICIENT_DATA"
    elif len(ticker_postures) >= 3:
        final_verdict = "PDG_SHADOW_READY_FOR_OBSERVATION"
        if gates.get("gates_passed"):
            overall_posture = "WATCH"
        elif validation_readiness == "WATCH":
            overall_posture = "WATCH"
        else:
            overall_posture = "NOT_READY"
    else:
        final_verdict = "PDG_SHADOW_NEEDS_MORE_DATA"
        overall_posture = "INSUFFICIENT_DATA"

    member_weights = {
        name: m.get("weight") for name, m in ((learning or {}).get("members") or {}).items()
    }
    context_weights = (context_learning or {}).get("component_weights") or (context or {}).get("component_weights")

    return {
        "schema": "tae_profit_decision_governor",
        "version": "v1",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "no_execution": True,
        "view_type": "MATERIALIZED_VIEW",
        "governor_note": "Profit protect pipeline VIEW — reconciles PDC + PCE; live execution remains live_bot.py",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "validation_readiness": validation_readiness,
        "validation_verdict": (validation or {}).get("verdict"),
        "committee_verdict": ((committee or {}).get("global_summary") or {}).get("final_verdict"),
        "context_verdict": ((context or {}).get("global_summary") or {}).get("final_verdict"),
        "committee_member_weights": member_weights,
        "context_component_weights": context_weights,
        "overall_profit_posture": overall_posture,
        "blocker_summary": build_blockers(sources_loaded, validation, committee, context),
        "global_summary": {
            "total_tickers": len(ticker_postures),
            "average_governor_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "posture_counts": posture_counts,
            "alignment_counts": alignment_counts,
            "top_5_protect_shadow": [
                {
                    "ticker": r["ticker"],
                    "governor_score": r["governor_score"],
                    "final_shadow_recommendation": r["final_shadow_recommendation"],
                    "alignment": r["alignment"],
                }
                for r in protect_rows[:5]
            ],
            "top_5_keep_winner_shadow": [
                {
                    "ticker": r["ticker"],
                    "governor_score": r["governor_score"],
                    "final_shadow_recommendation": r["final_shadow_recommendation"],
                    "pce_context_verdict": r.get("pce_context_verdict"),
                }
                for r in keep_rows[:5]
            ],
            "final_verdict": final_verdict,
        },
        "ticker_postures": ticker_postures,
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    posture_counts = summary.get("posture_counts") or {}
    alignment_counts = summary.get("alignment_counts") or {}

    lines = [
        "# TAE Profit Decision Governor v1",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY profit decision VIEW**",
        "",
        report.get("governor_note", ""),
        "",
        "## Executive summary",
        "",
        f"- **Overall profit posture:** {report.get('overall_profit_posture')}",
        f"- **Validation readiness:** {report.get('validation_readiness')}",
        f"- **Committee verdict:** {report.get('committee_verdict')}",
        f"- **Context verdict:** {report.get('context_verdict')}",
        f"- **Total tickers:** {summary['total_tickers']}",
        f"- **Average governor score:** {summary['average_governor_score']}",
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
            "## Posture counts",
            "",
        ]
    )
    for posture, count in sorted(posture_counts.items()):
        lines.append(f"- **{posture}:** {count}")

    lines.extend(["", "## Alignment counts", ""])
    for align, count in sorted(alignment_counts.items()):
        lines.append(f"- **{align}:** {count}")

    lines.extend(
        [
            "",
            "## Blocker summary",
            "",
        ]
    )
    for blocker in report.get("blocker_summary") or []:
        lines.append(
            f"- **{blocker.get('code')}** — {blocker.get('detail')} [{blocker.get('source')}]"
        )

    lines.extend(
        [
            "",
            "## Top 5 PROTECT_SHADOW",
            "",
            "| ticker | governor score | final rec | alignment |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("top_5_protect_shadow") or []:
        lines.append(
            f"| {row['ticker']} | {row['governor_score']} | {row['final_shadow_recommendation']} | {row['alignment']} |"
        )

    lines.extend(
        [
            "",
            "## Top 5 KEEP_WINNER_SHADOW",
            "",
            "| ticker | governor score | final rec | PCE verdict |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("top_5_keep_winner_shadow") or []:
        lines.append(
            f"| {row['ticker']} | {row['governor_score']} | {row['final_shadow_recommendation']} | {row.get('pce_context_verdict')} |"
        )

    lines.extend(
        [
            "",
            "## Per-ticker governor view",
            "",
            "| ticker | governor score | posture | final rec | PDC weighted | PCE verdict | alignment | conf |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("ticker_postures") or []:
        lines.append(
            f"| {row['ticker']} | {row['governor_score']} | {row['governor_posture']} | "
            f"{row['final_shadow_recommendation']} | {row.get('pdc_weighted_recommendation')} | "
            f"{row.get('pce_context_verdict')} | {row['alignment']} | {row['confidence']} |"
        )

    lines.extend(["", "## Per-ticker explanations", ""])
    for row in report.get("ticker_postures") or []:
        lines.append(f"### {row['ticker']} — {row['governor_posture']}")
        lines.append(row.get("explanation", ""))
        if row.get("advisory_notes"):
            lines.append("")
            lines.append("Notes: " + "; ".join(row["advisory_notes"]))
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["global_summary"]
    posture_counts = summary.get("posture_counts") or {}
    print("===== TAE PROFIT DECISION GOVERNOR v1 =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", summary["final_verdict"])
    print("Overall posture:", report.get("overall_profit_posture"))
    print("Tickers:", summary["total_tickers"])
    print("Avg governor score:", summary["average_governor_score"])
    print(
        "KEEP / TRAIL / PROTECT / WATCH / OBSERVE / INSUFF:",
        posture_counts.get("KEEP_WINNER_SHADOW", 0),
        posture_counts.get("TRAIL_SHADOW", 0),
        posture_counts.get("PROTECT_SHADOW", 0),
        posture_counts.get("WATCH_SHADOW", 0),
        posture_counts.get("OBSERVE_SHADOW", 0),
        posture_counts.get("INSUFFICIENT_DATA", 0),
    )


def main() -> int:
    report = build_governor_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
