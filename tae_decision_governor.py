#!/usr/bin/env python3
"""
TAE Decision Governor — X.DECISION-1.

READ-ONLY materialized advisory VIEW.
Consumes existing JSON outputs only — does not re-run analysis modules.
Does NOT modify live_bot.py, portfolio.csv, live_signals.csv, or place orders.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from research_core.meta_intelligence_runtime.unified_runtime_ssot import UnifiedRuntimeSSOT
from tae_decision_replay_composer import load_json, merge_advisory_readiness
from tae_knowledge_base import FORBIDDEN_RECOMMENDATIONS, sanitize_recommendation

UNIFIED_JSON = Path("tae_unified_runtime.json")
LIVE_ADVISORY_JSON = Path("tae_live_advisory.json")
REPLAY_JSON = Path("tae_decision_replay.json")
PROTECT_JSON = Path("tae_profit_protection_validation.json")
PROTECT_SHADOW_JSON = Path("tae_profit_protection_shadow.json")
COOLDOWN_JSON = Path("tae_stop_reentry_cooldown_audit.json")
KNOWLEDGE_JSON = Path("tae_knowledge_base.json")
CONFIDENCE_JSON = Path("tae_confidence_evolution.json")
COMMITTEE_JSON = Path("tae_committee_runtime.json")
WEIGHTED_DECISION_TXT = Path("weighted_committee_decision.txt")

OUTPUT_JSON = Path("tae_decision_governor.json")
OUTPUT_MD = Path("tae_decision_governor.md")

POSTURES = frozenset({"ALLOWED", "BLOCKED", "WATCH", "INSUFFICIENT_DATA"})
SHADOW_RECOMMENDATIONS = frozenset(
    {
        "CONTINUE_OBSERVATION",
        "TEST_TRAILING_SHADOW",
        "TEST_15M_COOLDOWN_SHADOW",
        "SCORE_DECAY_SHADOW",
        "DO_NOT_PROMOTE_TO_ADVISORY_YET",
        "DO_NOT_PROMOTE_TO_LIVE",
        "INSUFFICIENT_DATA",
        "PRIORITIZE_TRACKING",
    }
)


def _parse_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _readiness_rank(status: str | None) -> int:
    order = {"NOT_READY": 0, "WATCH": 1, "READY_FOR_SHADOW_ADVISORY": 2}
    return order.get(str(status or "NOT_READY"), 0)


def normalize_protect(data: dict[str, Any] | None, *, loaded: bool) -> dict[str, Any]:
    if not loaded or not data:
        return {"loaded": False}
    gates = data.get("gates") or {}
    best = data.get("best_strategy") or {}
    return {
        "loaded": True,
        "advisory_readiness": gates.get("advisory_readiness", "NOT_READY"),
        "gates_passed": gates.get("gates_passed", False),
        "failed_gates": gates.get("failed_gates", []),
        "best_strategy_id": best.get("strategy_id") or gates.get("best_strategy_id"),
        "verdict": data.get("verdict"),
    }


def normalize_cooldown(data: dict[str, Any] | None, *, loaded: bool) -> dict[str, Any]:
    if not loaded or not data:
        return {"loaded": False}
    gates = data.get("gates") or {}
    sim = data.get("cooldown_simulation") or {}
    return {
        "loaded": True,
        "advisory_readiness": gates.get("advisory_readiness", "NOT_READY"),
        "gates_passed": gates.get("gates_passed", False),
        "failed_gates": gates.get("failed_gates", []),
        "best_cooldown_policy": gates.get("best_cooldown_policy") or sim.get("best_cooldown"),
        "verdict": data.get("verdict"),
    }


def extract_decay_tickers(confidence: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not confidence:
        return result
    for cand in confidence.get("score_decay_candidates") or []:
        ticker = str(cand.get("ticker") or "").upper()
        if not ticker:
            continue
        existing = result.get(ticker)
        conf = str(cand.get("confidence", "LOW")).upper()
        if existing is None or conf == "HIGH":
            result[ticker] = {
                "confidence": conf,
                "recommendation": "SCORE_DECAY_SHADOW",
                "reason": cand.get("reason"),
                "source": "tae_confidence_evolution.json",
            }
    return result


def extract_knowledge_decay_tickers(knowledge: dict[str, Any] | None) -> set[str]:
    tickers: set[str] = set()
    if not knowledge:
        return tickers
    for entry in knowledge.get("entries") or []:
        if entry.get("source") != "confidence_evolution":
            continue
        if entry.get("pattern_type") != "SCORE_DECAY_SHADOW":
            continue
        subject = str(entry.get("subject", ""))
        ticker = subject.split("|", 1)[0].upper()
        if ticker:
            tickers.add(ticker)
    return tickers


def extract_churn_tickers(replay: dict[str, Any] | None) -> dict[str, str]:
    churn: dict[str, str] = {}
    if not replay:
        return churn
    for row in replay.get("top_costly_decisions") or []:
        if row.get("failure_mode") != "STOP_REENTRY_CHURN":
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            churn[ticker] = str(row.get("detail") or row.get("failure_mode"))
    return churn


def extract_live_advisory_mirror(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {"loaded": False}
    nested = data.get("advisory") or {}
    return {
        "loaded": True,
        "action": data.get("action") or nested.get("action"),
        "block_new_buy": data.get("block_new_buy", nested.get("block_new_buy")),
        "confidence": data.get("confidence", nested.get("confidence")),
        "generated_at": data.get("generated_at"),
        "blocking_warnings": data.get("blocking_warnings") or nested.get("blocking_warnings") or [],
        "source": "tae_live_advisory.json",
    }


def build_blocker_summary(
    live: dict[str, Any],
    readiness: dict[str, Any],
    replay: dict[str, Any] | None,
    protect: dict[str, Any],
    cooldown: dict[str, Any],
    confidence: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if live.get("loaded") and live.get("block_new_buy"):
        blockers.append(
            {
                "code": "LIVE_ADVISORY_BLOCK_NEW_BUY",
                "detail": live.get("action") or "RISK_ADVISORY",
                "source": "tae_live_advisory.json",
            }
        )

    for warning in live.get("blocking_warnings") or []:
        blockers.append(
            {
                "code": "LIVE_ADVISORY_WARNING",
                "detail": str(warning),
                "source": "tae_live_advisory.json",
            }
        )

    if readiness.get("final_status") == "NOT_READY":
        blockers.append(
            {
                "code": "SHADOW_GATES_NOT_READY",
                "detail": (
                    f"PROTECT={readiness.get('protect_readiness')} "
                    f"COOLDOWN={readiness.get('cooldown_readiness')}"
                ),
                "source": "tae_decision_replay.json",
            }
        )

    if protect.get("loaded") and protect.get("failed_gates"):
        blockers.append(
            {
                "code": "PROTECT_GATES_FAILED",
                "detail": ", ".join(protect.get("failed_gates") or []),
                "source": "tae_profit_protection_validation.json",
            }
        )

    if cooldown.get("loaded") and cooldown.get("failed_gates"):
        blockers.append(
            {
                "code": "COOLDOWN_GATES_FAILED",
                "detail": ", ".join(cooldown.get("failed_gates") or []),
                "source": "tae_stop_reentry_cooldown_audit.json",
            }
        )

    verdict = (replay or {}).get("final_verdict") or {}
    for item in verdict.get("do_not_promote_yet") or []:
        blockers.append(
            {
                "code": "DO_NOT_PROMOTE",
                "detail": str(item),
                "source": "tae_decision_replay.json",
            }
        )

    if confidence and (confidence.get("promotion_readiness") or {}).get("final_status") == "NOT_READY":
        blockers.append(
            {
                "code": "CONFIDENCE_EVOLUTION_NOT_READY",
                "detail": "Confidence evolution promotion readiness NOT_READY",
                "source": "tae_confidence_evolution.json",
            }
        )

    return blockers


def build_ticker_postures(
    ssot: UnifiedRuntimeSSOT,
    *,
    live: dict[str, Any],
    readiness: dict[str, Any],
    decay_by_ticker: dict[str, dict[str, Any]],
    knowledge_decay: set[str],
    churn_tickers: dict[str, str],
    min_buy_score: float = 80.0,
) -> list[dict[str, Any]]:
    records = ssot.records_by_ticker
    postures: list[dict[str, Any]] = []

    if not records:
        return postures

    global_block = bool(live.get("block_new_buy"))
    shadow_not_ready = readiness.get("final_status") == "NOT_READY"

    for ticker in sorted(records.keys()):
        record = records[ticker]
        signal = str(record.get("Signal") or "").upper()
        score = _parse_score(record.get("Score") or record.get("Scanner_Score"))
        sources: list[str] = ["tae_unified_runtime.json"]
        notes: list[str] = []
        posture = "ALLOWED"

        if score is None:
            posture = "INSUFFICIENT_DATA"
            notes.append("Score unavailable in unified runtime record")

        if global_block and signal == "STRONG BUY":
            posture = "BLOCKED"
            sources.append("tae_live_advisory.json")
            notes.append("Live advisory block_new_buy active for STRONG BUY")

        decay = decay_by_ticker.get(ticker) or (
            {"confidence": "MEDIUM", "recommendation": "SCORE_DECAY_SHADOW", "source": "tae_knowledge_base.json"}
            if ticker in knowledge_decay
            else None
        )
        if decay and posture != "BLOCKED":
            if decay.get("confidence") == "HIGH":
                posture = "WATCH"
            else:
                posture = "WATCH" if posture == "ALLOWED" else posture
            sources.append(str(decay.get("source", "tae_confidence_evolution.json")))
            notes.append(f"Shadow score decay candidate ({decay.get('recommendation')})")

        if ticker in churn_tickers and posture == "ALLOWED":
            posture = "WATCH"
            sources.append("tae_decision_replay.json")
            notes.append(f"STOP reentry churn: {churn_tickers[ticker]}")

        if shadow_not_ready and signal == "STRONG BUY" and posture == "ALLOWED":
            posture = "WATCH"
            sources.append("tae_decision_replay.json")
            notes.append("Shadow promotion gates NOT_READY — observation only")

        if signal == "TAKE PROFIT" and posture == "ALLOWED":
            posture = "WATCH"
            notes.append("TAKE PROFIT signal — exit advisory context only")

        if score is not None and score < min_buy_score and signal == "STRONG BUY" and posture == "ALLOWED":
            posture = "WATCH"
            notes.append(f"Signal/score mismatch: STRONG BUY with score {score}")

        postures.append(
            {
                "ticker": ticker,
                "posture": posture,
                "signal": signal or None,
                "score": score,
                "sources": sorted(set(sources)),
                "advisory_notes": notes,
            }
        )

    return postures


def collect_recommendations(
    replay: dict[str, Any] | None,
    confidence: dict[str, Any] | None,
    knowledge: dict[str, Any] | None,
) -> list[str]:
    recs: list[str] = []
    for source in (replay, confidence, knowledge):
        if not source:
            continue
        for rec in source.get("recommendations") or []:
            clean = sanitize_recommendation(str(rec))
            if clean not in recs and clean not in FORBIDDEN_RECOMMENDATIONS:
                recs.append(clean)
    return recs


def build_decision_governor_report(
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    root = root or Path(".")

    def _load(name: Path) -> tuple[dict[str, Any] | None, bool]:
        return load_json(root / name if not name.is_absolute() else name)

    sources_loaded: dict[str, bool] = {}
    source_paths = {
        "tae_unified_runtime.json": UNIFIED_JSON,
        "tae_live_advisory.json": LIVE_ADVISORY_JSON,
        "tae_decision_replay.json": REPLAY_JSON,
        "tae_profit_protection_validation.json": PROTECT_JSON,
        "tae_profit_protection_shadow.json": PROTECT_SHADOW_JSON,
        "tae_stop_reentry_cooldown_audit.json": COOLDOWN_JSON,
        "tae_knowledge_base.json": KNOWLEDGE_JSON,
        "tae_confidence_evolution.json": CONFIDENCE_JSON,
        "tae_committee_runtime.json": COMMITTEE_JSON,
        "weighted_committee_decision.txt": WEIGHTED_DECISION_TXT,
    }

    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        if key.endswith(".txt"):
            sources_loaded[key] = (root / path).is_file()
            payloads[key] = None
            continue
        data, ok = _load(path)
        sources_loaded[key] = ok
        payloads[key] = data

    ssot = UnifiedRuntimeSSOT.load(root)
    live = extract_live_advisory_mirror(payloads["tae_live_advisory.json"])
    replay = payloads["tae_decision_replay.json"]
    protect = normalize_protect(payloads["tae_profit_protection_validation.json"], loaded=sources_loaded["tae_profit_protection_validation.json"])
    cooldown = normalize_cooldown(payloads["tae_stop_reentry_cooldown_audit.json"], loaded=sources_loaded["tae_stop_reentry_cooldown_audit.json"])
    confidence = payloads["tae_confidence_evolution.json"]
    knowledge = payloads["tae_knowledge_base.json"]
    committee = payloads["tae_committee_runtime.json"]

    replay_readiness = (replay or {}).get("promotion_readiness") or {}
    if replay_readiness.get("final_status"):
        readiness = {
            "protect_readiness": replay_readiness.get("protect_readiness"),
            "cooldown_readiness": replay_readiness.get("cooldown_readiness"),
            "final_status": replay_readiness.get("final_status"),
            "protect_gates_passed": replay_readiness.get("protect_gates_passed"),
            "cooldown_gates_passed": replay_readiness.get("cooldown_gates_passed"),
            "source": "tae_decision_replay.json",
        }
    else:
        merged = merge_advisory_readiness(protect, cooldown)
        merged["source"] = "merged_from_protect_cooldown"
        readiness = merged

    decay_by_ticker = extract_decay_tickers(confidence)
    knowledge_decay = extract_knowledge_decay_tickers(knowledge)
    churn_tickers = extract_churn_tickers(replay)

    ticker_postures = build_ticker_postures(
        ssot,
        live=live,
        readiness=readiness,
        decay_by_ticker=decay_by_ticker,
        knowledge_decay=knowledge_decay,
        churn_tickers=churn_tickers,
    )

    posture_counts = {p: 0 for p in POSTURES}
    for row in ticker_postures:
        posture_counts[row["posture"]] = posture_counts.get(row["posture"], 0) + 1

    blockers = build_blocker_summary(live, readiness, replay, protect, cooldown, confidence)
    recommendations = collect_recommendations(replay, confidence, knowledge)

    verdict = (replay or {}).get("final_verdict") or {}
    ce_health = (confidence or {}).get("dataset_health") or {}
    committee_summary = (committee or {}).get("advisory_summary") or {}
    unified_summary = ssot.advisory_summary if ssot.ok else {}

    advisory_notes = [
        verdict.get("profit_stagnation_summary"),
        f"Primary shadow cause: {verdict.get('primary_cause')}" if verdict.get("primary_cause") else None,
        f"Best shadow hypothesis: {verdict.get('best_shadow_hypothesis')}" if verdict.get("best_shadow_hypothesis") else None,
        f"Live advisory action: {live.get('action')}" if live.get("loaded") else "Live advisory unavailable",
        f"Committee: {(committee_summary.get('weighted_decisions') or {}).get('final_decision')}" if committee_summary else None,
    ]
    advisory_notes = [n for n in advisory_notes if n]

    source_attribution = {
        "unified_runtime": {
            "loaded": sources_loaded["tae_unified_runtime.json"],
            "record_count": len(ssot.records_by_ticker),
            "generated_at": (payloads["tae_unified_runtime.json"] or {}).get("generated_at"),
        },
        "live_advisory": {
            "loaded": sources_loaded["tae_live_advisory.json"],
            "action": live.get("action"),
            "block_new_buy": live.get("block_new_buy"),
        },
        "decision_replay": {
            "loaded": sources_loaded["tae_decision_replay.json"],
            "primary_cause": verdict.get("primary_cause"),
            "readiness": readiness.get("final_status"),
        },
        "profit_protection": {
            "loaded": sources_loaded["tae_profit_protection_validation.json"],
            "readiness": protect.get("advisory_readiness"),
            "best_strategy": protect.get("best_strategy_id"),
        },
        "cooldown": {
            "loaded": sources_loaded["tae_stop_reentry_cooldown_audit.json"],
            "readiness": cooldown.get("advisory_readiness"),
            "best_policy": cooldown.get("best_cooldown_policy"),
        },
        "knowledge_base": {
            "loaded": sources_loaded["tae_knowledge_base.json"],
            "entries_total": ((knowledge or {}).get("summary") or {}).get("entries_total"),
        },
        "confidence_evolution": {
            "loaded": sources_loaded["tae_confidence_evolution.json"],
            "score_decay_candidates": len((confidence or {}).get("score_decay_candidates") or []),
            "score_persistence_cases": ce_health.get("score_persistence_cases"),
        },
        "committee": {
            "loaded": sources_loaded["tae_committee_runtime.json"],
            "final_decision": (committee_summary.get("weighted_decisions") or {}).get("final_decision"),
            "consensus": committee_summary.get("committee_consensus"),
        },
    }

    missing_required = [
        k
        for k in (
            "tae_unified_runtime.json",
            "tae_decision_replay.json",
        )
        if not sources_loaded.get(k)
    ]

    overall = "INSUFFICIENT_DATA" if missing_required else "WATCH"
    if readiness.get("final_status") == "NOT_READY":
        overall = "NOT_READY"
    elif live.get("block_new_buy"):
        overall = "BLOCKED"
    elif readiness.get("final_status") == "WATCH":
        overall = "WATCH"

    return {
        "schema": "tae_decision_governor",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "mode": "SHADOW_ONLY",
        "paper_only": True,
        "no_broker": True,
        "no_execution": True,
        "live_trading_impact": "NONE",
        "view_type": "MATERIALIZED_VIEW",
        "governor_note": "Advisory orchestration VIEW only — live execution remains live_bot.py",
        "sources_loaded": sources_loaded,
        "sources_missing_required": missing_required,
        "readiness": readiness,
        "overall_advisory_posture": overall,
        "live_advisory_mirror": live,
        "shadow_verdict": {
            "primary_cause": verdict.get("primary_cause"),
            "secondary_cause": verdict.get("secondary_cause"),
            "best_shadow_hypothesis": verdict.get("best_shadow_hypothesis"),
        },
        "unified_runtime_summary": {
            "ok": ssot.ok,
            "record_count": len(ssot.records_by_ticker),
            "unified_score_summary": unified_summary.get("unified_runtime_score_summary"),
        },
        "committee_summary": committee_summary,
        "blocker_summary": blockers,
        "advisory_notes": advisory_notes,
        "source_attribution": source_attribution,
        "ticker_postures": ticker_postures,
        "posture_counts": posture_counts,
        "recommendations": recommendations,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TAE Decision Governor (X.DECISION-1)",
        "",
        f"**Generated:** {report.get('generated_at')}",
        f"**Mode:** SHADOW_ONLY | **Live impact:** NONE",
        "",
        "> READ-ONLY advisory VIEW. No orders. No portfolio changes.",
        "",
        "## Executive summary",
        "",
        f"- **Overall advisory posture:** {report.get('overall_advisory_posture')}",
        f"- **Shadow readiness:** {(report.get('readiness') or {}).get('final_status')}",
        f"- **Live advisory action:** {(report.get('live_advisory_mirror') or {}).get('action')}",
        f"- **block_new_buy:** {(report.get('live_advisory_mirror') or {}).get('block_new_buy')}",
        "",
        "## Sources loaded",
        "",
    ]
    for src, ok in sorted((report.get("sources_loaded") or {}).items()):
        lines.append(f"- {'✅' if ok else '❌'} {src}")
    if report.get("sources_missing_required"):
        lines.append(f"- Missing required: {', '.join(report['sources_missing_required'])}")

    lines.extend(["", "## Posture counts", ""])
    for posture, count in sorted((report.get("posture_counts") or {}).items()):
        lines.append(f"- **{posture}:** {count}")

    lines.extend(["", "## Blocker summary", ""])
    blockers = report.get("blocker_summary") or []
    if not blockers:
        lines.append("- None")
    for b in blockers:
        lines.append(f"- **{b.get('code')}** — {b.get('detail')} [{b.get('source')}]")

    lines.extend(["", "## Advisory notes", ""])
    for note in report.get("advisory_notes") or []:
        lines.append(f"- {note}")

    lines.extend(["", "## Per-ticker posture (sample)", ""])
    lines.append("| Ticker | Posture | Signal | Score | Notes |")
    lines.append("|--------|---------|--------|-------|-------|")
    for row in (report.get("ticker_postures") or [])[:20]:
        notes = "; ".join(row.get("advisory_notes") or [])[:80]
        lines.append(
            f"| {row.get('ticker')} | **{row.get('posture')}** | {row.get('signal')} | "
            f"{row.get('score')} | {notes or '-'} |"
        )
    total = len(report.get("ticker_postures") or [])
    if total > 20:
        lines.append(f"\n_… and {total - 20} more tickers._")

    lines.extend(["", "## Recommendations (SHADOW_ONLY)", ""])
    for rec in report.get("recommendations") or []:
        lines.append(f"- {rec}")

    lines.extend(["", "*Governor VIEW only. Upstream SSOT files remain authoritative.*", ""])
    return "\n".join(lines)


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def main() -> int:
    report = build_decision_governor_report()
    write_outputs(report)
    counts = report.get("posture_counts") or {}
    print("===== TAE DECISION GOVERNOR (X.DECISION-1) =====")
    print("Mode: SHADOW_ONLY | Live impact: NONE")
    print("Overall:", report.get("overall_advisory_posture"))
    print("Readiness:", (report.get("readiness") or {}).get("final_status"))
    print("Tickers:", len(report.get("ticker_postures") or []), "| Postures:", counts)
    print("Blockers:", len(report.get("blocker_summary") or []))
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
