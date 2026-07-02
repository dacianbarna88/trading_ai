#!/usr/bin/env python3
"""
TAE Confidence Evolution — X.KNOWLEDGE-1B.

SHADOW_ONLY extension VIEW: connects STOP→reentry→score persistence evidence
into confidence evolution. Does NOT modify live_bot, scores, portfolio, or signals.
Does NOT write tae_knowledge_base.json — emits evidence_for_knowledge_base for X.KNOWLEDGE-1C.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

COOLDOWN_JSON = Path("tae_stop_reentry_cooldown_audit.json")
REPLAY_JSON = Path("tae_decision_replay.json")
PROTECT_JSON = Path("tae_profit_protection_validation.json")
KNOWLEDGE_JSON = Path("tae_knowledge_base.json")
PORTFOLIO_FILE = Path("portfolio.csv")

OUTPUT_JSON = Path("tae_confidence_evolution.json")
OUTPUT_MD = Path("tae_confidence_evolution.md")

SCORE_DECAY_ADJUSTMENT = -20
DECAY_WINDOW_MINUTES = 30
IMMEDIATE_REENTRY_MINUTES = 5.0
SCORE_PERSISTENCE_THRESHOLD = 80.0

CONF_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
RANK_CONF = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}

FORBIDDEN = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT"})
SHADOW_RECOMMENDATIONS = frozenset(
    {
        "SCORE_DECAY_SHADOW",
        "TEST_TRAILING_SHADOW",
        "TEST_15M_COOLDOWN_SHADOW",
        "CONTINUE_OBSERVATION",
        "DO_NOT_PROMOTE_TO_ADVISORY_YET",
        "DO_NOT_PROMOTE_TO_LIVE",
        "INSUFFICIENT_DATA",
    }
)

READINESS_ORDER = {"NOT_READY": 0, "WATCH": 1, "READY_FOR_SHADOW_ADVISORY": 2}


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def shift_confidence(before: str, delta: int) -> tuple[str, int]:
    start = CONF_RANK.get(before, 1)
    end = max(1, min(3, start + delta))
    return RANK_CONF[end], end - start


def kb_confidence_for_pattern(knowledge: dict[str, Any] | None, *patterns: str) -> str:
    if not knowledge:
        return "LOW"
    for entry in knowledge.get("entries") or []:
        blob = " ".join(
            str(entry.get(k, ""))
            for k in ("pattern_type", "title", "subject", "id")
        ).upper()
        if any(p.upper() in blob for p in patterns):
            return str(entry.get("confidence", "LOW"))
    return "LOW"


def build_dataset_health(
    cooldown: dict[str, Any] | None,
    cooldown_ok: bool,
    protect: dict[str, Any] | None,
    protect_ok: bool,
    replay: dict[str, Any] | None,
    replay_ok: bool,
    knowledge_ok: bool,
    portfolio_ok: bool,
) -> dict[str, Any]:
    cd_health = (cooldown or {}).get("dataset_health") or {}
    cd_summary = (cooldown or {}).get("summary") or {}
    sp = (cooldown or {}).get("score_persistence") or {}
    pr_health = (protect or {}).get("dataset_health") or {}
    verdict = (replay or {}).get("final_verdict") or {} if replay_ok else {}

    stop_cases = cd_health.get("stop_reentry_cases")
    score_persist = sp.get("count")
    second_stops = cd_summary.get("second_stop_count")
    protect_obs = pr_health.get("observations")

    missing = []
    if not cooldown_ok:
        missing.append("tae_stop_reentry_cooldown_audit.json")
    if not protect_ok:
        missing.append("tae_profit_protection_validation.json")
    if not replay_ok:
        missing.append("tae_decision_replay.json")

    sample_warning = False
    if stop_cases is not None and stop_cases < 10:
        sample_warning = True
    if protect_obs is not None and protect_obs < 30:
        sample_warning = True
    if pr_health.get("minimum_sample_warning"):
        sample_warning = True

    if missing:
        data_quality = "INCOMPLETE"
    elif sample_warning:
        data_quality = "LIMITED"
    else:
        data_quality = pr_health.get("data_quality", "OK")

    return {
        "stop_reentry_cases": stop_cases,
        "score_persistence_cases": score_persist,
        "second_stop_cases": second_stops,
        "protect_observations": protect_obs,
        "replay_primary_cause": verdict.get("primary_cause"),
        "replay_secondary_cause": verdict.get("secondary_cause"),
        "data_quality": data_quality,
        "sample_warning": sample_warning,
        "sources_loaded": {
            "tae_stop_reentry_cooldown_audit.json": cooldown_ok,
            "tae_decision_replay.json": replay_ok,
            "tae_profit_protection_validation.json": protect_ok,
            "tae_knowledge_base.json": knowledge_ok,
            "portfolio.csv": portfolio_ok,
        },
        "missing_required": missing,
    }


def _count_evidence(sequences: list[dict[str, Any]], *, predicate) -> tuple[int, int]:
    pos = neg = 0
    for seq in sequences:
        if predicate(seq):
            pos += 1
        else:
            neg += 1
    return pos, neg


def build_confidence_entries(
    cooldown: dict[str, Any] | None,
    protect: dict[str, Any] | None,
    replay: dict[str, Any] | None,
    knowledge: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    sequences = (cooldown or {}).get("stop_reentry_sequences") or []
    sp = (cooldown or {}).get("score_persistence") or {}
    summary = (cooldown or {}).get("summary") or {}
    best_cooldown = ((cooldown or {}).get("cooldown_simulation") or {}).get("best_cooldown", "cooldown_15m")
    cd_sim = ((cooldown or {}).get("cooldown_simulation") or {}).get("simulations") or {}
    cooldown_net = (cd_sim.get(best_cooldown) or {}).get("net_effect_usd")

    protect_health = (protect or {}).get("dataset_health") or {}
    best_protect = (protect or {}).get("best_strategy") or {}
    protect_delta = best_protect.get("delta_vs_hold_total")
    protect_obs = protect_health.get("observations", 0)
    verdict = (replay or {}).get("final_verdict") or {}

    sp_count = sp.get("count", 0)
    sp_cases = sp.get("cases") or []
    sp_losses = sum(1 for c in sp_cases if (c.get("leg_pnl") or 0) < 0 or "SECOND_STOP" in str(c.get("outcome", "")))
    sp_wins = sp_count - sp_losses

    before_sp = kb_confidence_for_pattern(knowledge, "SCORE", "REENTRY", "STOP")
    delta_sp = 1 if sp_count >= 8 else (0 if sp_count >= 5 else -1)
    after_sp, conf_delta_sp = shift_confidence(before_sp, delta_sp)
    entries.append(
        {
            "id": "ce_score_persistence_after_stop",
            "hypothesis": "SCORE_PERSISTENCE_AFTER_STOP",
            "source": "tae_stop_reentry_cooldown_audit.json",
            "evidence_count": sp_count,
            "positive_evidence": sp_count,
            "negative_evidence": sp_wins,
            "confidence_before": before_sp,
            "confidence_after": after_sp,
            "confidence_delta": conf_delta_sp,
            "trend": "IMPROVING" if sp_count >= 8 else ("STABLE" if sp_count >= 5 else "INSUFFICIENT_DATA"),
            "status": "LEARNING" if sp_count >= 5 else "EXPERIMENTAL",
            "reason": f"{sp_count}/{len(sequences) or sp_count} reentries retained score≥{SCORE_PERSISTENCE_THRESHOLD:.0f} + STRONG BUY after STOP",
            "recommendation": "SCORE_DECAY_SHADOW",
        }
    )

    immediate = summary.get("immediate_reentries", 0)
    second_stops = summary.get("second_stop_count", 0)
    churn_damage = sum(
        abs(s.get("leg_pnl") or 0)
        for s in sequences
        if s.get("second_stop") and (s.get("leg_pnl") or 0) < 0
    )
    before_churn = kb_confidence_for_pattern(knowledge, "REENTRY", "CHURN", "COOLDOWN")
    delta_churn = 1 if immediate >= 5 and second_stops >= 2 else (0 if immediate >= 3 else -1)
    after_churn, conf_delta_churn = shift_confidence(before_churn, delta_churn)
    entries.append(
        {
            "id": "ce_stop_reentry_churn",
            "hypothesis": "STOP_REENTRY_CHURN",
            "source": "tae_stop_reentry_cooldown_audit.json",
            "evidence_count": immediate,
            "positive_evidence": immediate,
            "negative_evidence": max(0, (summary.get("reentry_wins") or 0)),
            "confidence_before": before_churn,
            "confidence_after": after_churn,
            "confidence_delta": conf_delta_churn,
            "trend": "IMPROVING" if second_stops >= 2 else ("STABLE" if immediate >= 3 else "INSUFFICIENT_DATA"),
            "status": "WATCH" if second_stops >= 2 else "LEARNING",
            "reason": (
                f"{immediate} immediate reentries (≤{IMMEDIATE_REENTRY_MINUTES:.0f}m); "
                f"{second_stops} second STOPs; confirmed damage ≈{churn_damage:.2f} USD (MU)"
            ),
            "recommendation": "TEST_15M_COOLDOWN_SHADOW",
        }
    )

    before_mpp = kb_confidence_for_pattern(knowledge, "FADE", "PROTECTION", "TRAILING")
    delta_mpp = 1 if protect_delta and protect_delta > 300 else (0 if protect_delta and protect_delta > 100 else -1)
    after_mpp, conf_delta_mpp = shift_confidence(before_mpp, delta_mpp)
    primary = verdict.get("primary_cause", "MISSED_PROFIT_PROTECTION")
    entries.append(
        {
            "id": "ce_missed_profit_protection",
            "hypothesis": "MISSED_PROFIT_PROTECTION",
            "source": "tae_profit_protection_validation.json",
            "evidence_count": protect_obs,
            "positive_evidence": protect_obs if protect_delta and protect_delta > 0 else 0,
            "negative_evidence": 0,
            "confidence_before": before_mpp,
            "confidence_after": after_mpp,
            "confidence_delta": conf_delta_mpp,
            "trend": "IMPROVING" if protect_delta and protect_delta > 300 else ("STABLE" if protect_obs >= 20 else "INSUFFICIENT_DATA"),
            "status": "LEARNING" if protect_obs >= 20 else "EXPERIMENTAL",
            "reason": f"X.REPLAY-1 primary={primary}; shadow protection Δ vs HOLD +{protect_delta} USD ({protect_obs} obs)",
            "recommendation": "TEST_TRAILING_SHADOW",
        }
    )

    before_trail = kb_confidence_for_pattern(knowledge, "BEST_SHADOW_TRAILING", "shadow_trailing")
    win_rate = best_protect.get("win_rate")
    trail_delta = 1 if protect_delta and protect_delta > 500 else (0 if protect_delta and protect_delta > 200 else 0)
    after_trail, conf_delta_trail = shift_confidence(before_trail, trail_delta)
    entries.append(
        {
            "id": "ce_trailing_1_protection",
            "hypothesis": "TRAILING_1_PROTECTION_HYPOTHESIS",
            "source": "tae_profit_protection_validation.json",
            "evidence_count": protect_obs,
            "positive_evidence": int(round((win_rate or 0) * protect_obs)) if win_rate else 0,
            "negative_evidence": protect_obs - int(round((win_rate or 0) * protect_obs)) if win_rate else 0,
            "confidence_before": before_trail,
            "confidence_after": after_trail,
            "confidence_delta": conf_delta_trail,
            "trend": "IMPROVING" if protect_delta and protect_delta > 500 else ("STABLE" if protect_obs >= 26 else "INSUFFICIENT_DATA"),
            "status": "WATCH" if protect_obs >= 26 else "EXPERIMENTAL",
            "reason": (
                f"Best strategy {best_protect.get('strategy_id', 'shadow_trailing_1')} "
                f"total {best_protect.get('total_value')} USD; win_rate={win_rate}"
            ),
            "recommendation": "TEST_TRAILING_SHADOW",
        }
    )

    before_cd = kb_confidence_for_pattern(knowledge, "COOLDOWN", "REENTRY")
    cd_positive = 1 if cooldown_net and cooldown_net > 0 else 0
    cd_delta = 1 if cooldown_net and cooldown_net > 20 else (0 if cooldown_net and cooldown_net > 0 else -1)
    after_cd, conf_delta_cd = shift_confidence(before_cd, cd_delta)
    entries.append(
        {
            "id": "ce_cooldown_15m",
            "hypothesis": "COOLDOWN_15M_HYPOTHESIS",
            "source": "tae_stop_reentry_cooldown_audit.json",
            "evidence_count": summary.get("total_reentries", 0),
            "positive_evidence": cd_positive,
            "negative_evidence": 1 if cooldown_net and cooldown_net <= 0 else 0,
            "confidence_before": before_cd,
            "confidence_after": after_cd,
            "confidence_delta": conf_delta_cd,
            "trend": "STABLE" if cooldown_net and cooldown_net > 0 else "INSUFFICIENT_DATA",
            "status": "DO_NOT_PROMOTE" if sp_count < 10 else "EXPERIMENTAL",
            "reason": f"{best_cooldown} net effect {cooldown_net} USD; sample {summary.get('total_reentries', 0)} reentries",
            "recommendation": "TEST_15M_COOLDOWN_SHADOW",
        }
    )

    return entries


def compute_score_decay_candidates(sequences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for seq in sequences:
        score = float(seq.get("reentry_score") or 0)
        if score < SCORE_PERSISTENCE_THRESHOLD:
            continue
        minutes = float(seq.get("minutes_after_stop") or 999)
        if minutes > IMMEDIATE_REENTRY_MINUTES:
            continue
        second_stop = bool(seq.get("second_stop"))
        leg_pnl = seq.get("leg_pnl")
        negative_outcome = leg_pnl is not None and float(leg_pnl) < 0
        if not second_stop and not negative_outcome:
            continue
        conf = "HIGH" if second_stop and negative_outcome else ("MEDIUM" if second_stop or negative_outcome else "LOW")
        reason_parts = [
            f"score {score:.0f} persisted after STOP",
            f"reentry in {minutes:.2f}m",
        ]
        if second_stop:
            reason_parts.append("second STOP confirmed")
        if negative_outcome:
            reason_parts.append(f"negative leg PnL {float(leg_pnl):.2f} USD")
        candidates.append(
            {
                "ticker": seq.get("ticker"),
                "stop_time": seq.get("stop_timestamp"),
                "reentry_time": seq.get("reentry_timestamp"),
                "original_score": score,
                "shadow_adjusted_score": max(0.0, score + SCORE_DECAY_ADJUSTMENT),
                "decay_window_minutes": DECAY_WINDOW_MINUTES,
                "reason": "; ".join(reason_parts),
                "outcome": seq.get("outcome"),
                "confidence": conf,
                "recommendation": "SCORE_DECAY_SHADOW",
            }
        )
    candidates.sort(
        key=lambda c: (
            0 if c.get("confidence") == "HIGH" else 1,
            -(float(c.get("original_score") or 0)),
        )
    )
    return candidates


def merge_advisory_readiness(protect: dict[str, Any] | None, cooldown: dict[str, Any] | None) -> dict[str, Any]:
    p_gate = ((protect or {}).get("gates") or {}).get("advisory_readiness", "NOT_READY")
    c_gate = ((cooldown or {}).get("gates") or {}).get("advisory_readiness", "NOT_READY")
    p_pass = ((protect or {}).get("gates") or {}).get("gates_passed", False)
    c_pass = ((cooldown or {}).get("gates") or {}).get("gates_passed", False)

    if p_gate == "READY_FOR_SHADOW_ADVISORY" and c_gate == "READY_FOR_SHADOW_ADVISORY":
        final = "READY_FOR_SHADOW_ADVISORY"
    elif p_gate == "NOT_READY" or c_gate == "NOT_READY":
        final = "NOT_READY"
    elif p_gate == "WATCH" or c_gate == "WATCH":
        final = "WATCH"
    else:
        final = "NOT_READY"

    return {
        "protect_readiness": p_gate,
        "cooldown_readiness": c_gate,
        "final_status": final,
        "protect_gates_passed": p_pass,
        "cooldown_gates_passed": c_pass,
    }


def build_evidence_for_knowledge_base(
    entries: list[dict[str, Any]],
    decay_candidates: list[dict[str, Any]],
    health: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for entry in entries:
        evidence.append(
            {
                "source": "tae_confidence_evolution.json",
                "hypothesis": entry["hypothesis"],
                "pattern_type": entry["hypothesis"],
                "status": entry["status"],
                "confidence": entry["confidence_after"],
                "trend": entry["trend"],
                "evidence_count": entry["evidence_count"],
                "recommendation": entry["recommendation"],
                "reason": entry["reason"],
            }
        )
    for cand in decay_candidates[:5]:
        evidence.append(
            {
                "source": "tae_confidence_evolution.json",
                "hypothesis": "SCORE_DECAY_AFTER_STOP",
                "pattern_type": "SCORE_DECAY_SHADOW",
                "subject": cand.get("ticker"),
                "status": "LEARNING",
                "confidence": cand.get("confidence", "LOW"),
                "recommendation": "SCORE_DECAY_SHADOW",
                "reason": cand.get("reason"),
                "shadow_adjusted_score": cand.get("shadow_adjusted_score"),
                "decay_window_minutes": cand.get("decay_window_minutes"),
            }
        )
    if health.get("sample_warning"):
        evidence.append(
            {
                "source": "tae_confidence_evolution.json",
                "hypothesis": "INSUFFICIENT_SAMPLE",
                "pattern_type": "DATA_QUALITY",
                "status": "EXPERIMENTAL",
                "confidence": "LOW",
                "recommendation": "CONTINUE_OBSERVATION",
                "reason": "Sample below PROTECT-2 (30) or COOLDOWN-1 (10) gates",
            }
        )
    return evidence


def build_final_recommendation(
    entries: list[dict[str, Any]],
    readiness: dict[str, Any],
    health: dict[str, Any],
    decay_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    improving = [e["hypothesis"] for e in entries if e.get("trend") == "IMPROVING"]
    declining = [e["hypothesis"] for e in entries if e.get("trend") == "DECLINING"]
    insufficient = [e["hypothesis"] for e in entries if e.get("trend") == "INSUFFICIENT_DATA"]

    next_step = "Continue observation until >=30 PROTECT-2 and >=10 COOLDOWN-1 samples"
    if readiness.get("final_status") == "READY_FOR_SHADOW_ADVISORY":
        next_step = "X.KNOWLEDGE-1C — ingest evidence_for_knowledge_base into knowledge VIEW"
    elif decay_candidates:
        next_step = "X.KNOWLEDGE-1C — wire SCORE_DECAY_SHADOW into knowledge materialization"

    return {
        "stronger": improving,
        "weaker": declining,
        "insufficient": insufficient,
        "score_decay_candidate_count": len(decay_candidates),
        "promotion_readiness": readiness.get("final_status"),
        "recommended_next_module": next_step,
        "do_not_promote": [
            "DO_NOT_PROMOTE_TO_LIVE",
            "DO_NOT_PROMOTE_TO_ADVISORY_YET",
        ],
    }


def build_confidence_evolution_report(
    cooldown_path: Path = COOLDOWN_JSON,
    replay_path: Path = REPLAY_JSON,
    protect_path: Path = PROTECT_JSON,
    knowledge_path: Path = KNOWLEDGE_JSON,
    portfolio_path: Path = PORTFOLIO_FILE,
) -> dict[str, Any]:
    cooldown, cooldown_ok = load_json(cooldown_path)
    replay, replay_ok = load_json(replay_path)
    protect, protect_ok = load_json(protect_path)
    knowledge, knowledge_ok = load_json(knowledge_path)
    portfolio_ok = portfolio_path.is_file()

    health = build_dataset_health(
        cooldown, cooldown_ok, protect, protect_ok, replay, replay_ok, knowledge_ok, portfolio_ok
    )
    entries = build_confidence_entries(cooldown, protect, replay, knowledge)
    sequences = (cooldown or {}).get("stop_reentry_sequences") or []
    decay_candidates = compute_score_decay_candidates(sequences)
    readiness = merge_advisory_readiness(protect, cooldown)
    evidence = build_evidence_for_knowledge_base(entries, decay_candidates, health)
    final_rec = build_final_recommendation(entries, readiness, health, decay_candidates)

    recommendations: list[str] = []
    for entry in entries:
        rec = entry.get("recommendation")
        if rec and rec not in recommendations:
            recommendations.append(rec)
    if health.get("sample_warning") and "CONTINUE_OBSERVATION" not in recommendations:
        recommendations.append("CONTINUE_OBSERVATION")
    if readiness.get("final_status") == "NOT_READY":
        if "DO_NOT_PROMOTE_TO_ADVISORY_YET" not in recommendations:
            recommendations.append("DO_NOT_PROMOTE_TO_ADVISORY_YET")
        if "INSUFFICIENT_DATA" not in recommendations:
            recommendations.append("INSUFFICIENT_DATA")

    return {
        "schema": "tae_confidence_evolution",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "extension_note": "X.KNOWLEDGE-1B VIEW — does not modify live scores or tae_knowledge_base.json",
        "dataset_health": health,
        "confidence_evolution_entries": entries,
        "score_decay_candidates": decay_candidates,
        "promotion_readiness": readiness,
        "evidence_for_knowledge_base": evidence,
        "final_recommendation": final_rec,
        "recommendations": recommendations,
    }


def render_markdown(report: dict[str, Any]) -> str:
    health = report.get("dataset_health") or {}
    entries = report.get("confidence_evolution_entries") or []
    decay = report.get("score_decay_candidates") or []
    readiness = report.get("promotion_readiness") or {}
    final_rec = report.get("final_recommendation") or {}

    lines = [
        "# TAE Confidence Evolution (X.KNOWLEDGE-1B)",
        "",
        f"**Generated:** {report.get('generated_at')}",
        f"**Mode:** SHADOW_ONLY | **Live impact:** NONE",
        "",
        "> SHADOW_ONLY — Score decay and confidence updates are advisory VIEW only. "
        "Live scores are NOT modified.",
        "",
        "## Executive summary",
        "",
        f"- **Replay primary cause:** {health.get('replay_primary_cause')}",
        f"- **Replay secondary cause:** {health.get('replay_secondary_cause')}",
        f"- **Score persistence cases:** {health.get('score_persistence_cases')}",
        f"- **Second STOP cases:** {health.get('second_stop_cases')}",
        f"- **Score decay candidates:** {len(decay)}",
        f"- **Promotion readiness:** {readiness.get('final_status')}",
        "",
        "## Evidence sources",
        "",
    ]
    for src, ok in (health.get("sources_loaded") or {}).items():
        lines.append(f"- {'✅' if ok else '❌'} {src}")
    if health.get("missing_required"):
        lines.append(f"- Missing: {', '.join(health['missing_required'])}")

    lines.extend(["", "## Dataset health", ""])
    for key in (
        "stop_reentry_cases",
        "score_persistence_cases",
        "second_stop_cases",
        "protect_observations",
        "data_quality",
        "sample_warning",
    ):
        lines.append(f"- {key}: **{health.get(key)}**")

    lines.extend(["", "## Confidence changes", ""])
    for entry in entries:
        lines.append(
            f"- **{entry['hypothesis']}** — {entry['confidence_before']} → **{entry['confidence_after']}** "
            f"(Δ{entry['confidence_delta']:+d}) | trend={entry['trend']} | status={entry['status']}"
        )
        lines.append(f"  - {entry['reason']}")

    lines.extend(["", "## Score decay candidates", ""])
    if not decay:
        lines.append("- None meeting criteria (immediate reentry + score≥80 + second STOP or negative outcome)")
    for i, cand in enumerate(decay, 1):
        lines.append(
            f"{i}. **{cand.get('ticker')}** — score {cand.get('original_score')} → "
            f"shadow {cand.get('shadow_adjusted_score')} for {cand.get('decay_window_minutes')}m | "
            f"{cand.get('outcome')} | {cand.get('reason')}"
        )

    lines.extend(
        [
            "",
            "## What got stronger",
            "",
        ]
    )
    for h in final_rec.get("stronger") or ["(none)"]:
        lines.append(f"- {h}")

    lines.extend(["", "## What got weaker", ""])
    for h in final_rec.get("weaker") or ["(none)"]:
        lines.append(f"- {h}")

    lines.extend(["", "## What remains insufficient", ""])
    for h in final_rec.get("insufficient") or ["(none)"]:
        lines.append(f"- {h}")

    lines.extend(
        [
            "",
            "## Promotion readiness",
            "",
            f"- PROTECT-2: {readiness.get('protect_readiness')}",
            f"- COOLDOWN-1: {readiness.get('cooldown_readiness')}",
            f"- **Final:** {readiness.get('final_status')}",
            "",
            "## Final recommendation",
            "",
            f"- Next module: **{final_rec.get('recommended_next_module')}**",
            f"- Do NOT promote: {', '.join(final_rec.get('do_not_promote') or [])}",
            "",
            "## Recommendations (SHADOW_ONLY)",
            "",
        ]
    )
    for rec in report.get("recommendations") or []:
        lines.append(f"- {rec}")

    lines.extend(["", "*Extension VIEW only. Upstream SSOT files remain authoritative.*", ""])
    return "\n".join(lines)


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def main() -> int:
    report = build_confidence_evolution_report()
    write_outputs(report)
    health = report.get("dataset_health") or {}
    readiness = report.get("promotion_readiness") or {}
    decay = report.get("score_decay_candidates") or []
    print("===== TAE CONFIDENCE EVOLUTION (X.KNOWLEDGE-1B) =====")
    print("Score persistence:", health.get("score_persistence_cases"))
    print("Second STOPs:", health.get("second_stop_cases"))
    print("Score decay candidates:", len(decay))
    print("Promotion readiness:", readiness.get("final_status"))
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
