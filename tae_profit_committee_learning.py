#!/usr/bin/env python3
"""
TAE Profit Committee Learning v2 — SHADOW_ONLY / NO_BROKER.

Adaptive weighted committee: tracks member accuracy, updates weights,
and produces weighted committee recommendations. No live execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

COMMITTEE_JSON = Path("tae_profit_decision_committee.json")
COMMITTEE_MD = Path("tae_profit_decision_committee.md")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
BRAIN_JSON = Path("tae_profit_intelligence_brain.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")

OUTPUT_JSON = Path("tae_profit_committee_learning.json")
OUTPUT_MD = Path("tae_profit_committee_learning.md")

MEMBER_KEYS = (
    ("Rules", "protection_rules"),
    ("PIB", "profit_intelligence"),
    ("PSP", "profit_survival"),
    ("Memory", "profit_memory"),
    ("Validation", "validation"),
)

RECOMMENDATIONS = (
    "NO_ACTION",
    "HOLD",
    "OBSERVE",
    "WATCH",
    "TRAIL_PROTECT_SHADOW",
    "PARTIAL_PROTECT_SHADOW",
    "EXIT_PROTECT_SHADOW",
)

REC_SCORE = {
    "NO_ACTION": 0,
    "HOLD": 1,
    "OBSERVE": 2,
    "WATCH": 3,
    "TRAIL_PROTECT_SHADOW": 4,
    "PARTIAL_PROTECT_SHADOW": 5,
    "EXIT_PROTECT_SHADOW": 6,
}

ACTION_BUCKET = {
    "NO_ACTION": "passive",
    "HOLD": "passive",
    "OBSERVE": "monitor",
    "WATCH": "monitor",
    "TRAIL_PROTECT_SHADOW": "protect",
    "PARTIAL_PROTECT_SHADOW": "protect",
    "EXIT_PROTECT_SHADOW": "protect",
}

LABEL_BUCKET = {
    "PROFIT_COLLAPSED": "protect",
    "PROFIT_DECAYED": "monitor",
    "PROFIT_SURVIVED": "passive",
    "UNKNOWN_OUTCOME": "monitor",
}

WEIGHT_MIN = 0.40
WEIGHT_MAX = 2.50


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def default_member_stats() -> dict[str, dict[str, Any]]:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        name: {
            "name": name,
            "member_key": key,
            "total_votes": 0,
            "correct_votes": 0,
            "incorrect_votes": 0,
            "accuracy": 0.0,
            "weight": 1.0,
            "prior_accuracy": 0.0,
            "trend": "STABLE",
            "last_update": now,
            "recommended_bias": "NEUTRAL",
        }
        for name, key in MEMBER_KEYS
    }


def accuracy_to_weight(accuracy: float) -> float:
    pct = accuracy * 100.0
    if pct < 40:
        weight = 0.60
    elif pct < 55:
        weight = 0.80
    elif pct < 70:
        weight = 1.00
    elif pct < 85:
        weight = 1.40
    elif pct < 95:
        weight = 1.80
    else:
        weight = 2.20
    return max(WEIGHT_MIN, min(WEIGHT_MAX, round(weight, 2)))


def trend_from_delta(delta: float) -> str:
    if delta >= 0.05:
        return "IMPROVING"
    if delta <= -0.05:
        return "DECLINING"
    return "STABLE"


def vote_to_recommendation(member_name: str, vote: str) -> str:
    vote = str(vote or "").upper()
    if member_name == "Rules":
        if vote == "PROTECT_URGENT":
            return "EXIT_PROTECT_SHADOW"
        if vote in {"PROTECT_SHADOW", "PROTECT_WATCH"}:
            return "PARTIAL_PROTECT_SHADOW"
        if vote == "OBSERVE":
            return "OBSERVE"
        return "NO_ACTION"
    if member_name == "PIB":
        if vote in RECOMMENDATIONS:
            return vote
        return "OBSERVE"
    if member_name == "PSP":
        if vote == "PSP_CRITICAL":
            return "EXIT_PROTECT_SHADOW"
        if vote == "PSP_ELEVATED":
            return "WATCH"
        if vote == "PSP_STABLE":
            return "HOLD"
        return "OBSERVE"
    if member_name == "Memory":
        if vote in {"MEMORY_PROTECT_EARLY", "EPISODE_COLLAPSED"}:
            return "EXIT_PROTECT_SHADOW"
        if vote == "EPISODE_DECAYED":
            return "WATCH"
        if vote in {"MEMORY_HOLD_WINNERS", "EPISODE_SURVIVED"}:
            return "HOLD"
        return "OBSERVE"
    if member_name == "Validation":
        if vote == "VALIDATION_PROTECT":
            return "PARTIAL_PROTECT_SHADOW"
        if vote in {"VALIDATION_AVOID", "VALIDATION_SHADOW_ONLY"}:
            return "HOLD"
        return "OBSERVE"
    return "OBSERVE"


def ground_truth_from_label(label: str) -> str:
    label = str(label or "UNKNOWN_OUTCOME").upper()
    if label == "PROFIT_COLLAPSED":
        return "EXIT_PROTECT_SHADOW"
    if label == "PROFIT_DECAYED":
        return "WATCH"
    if label == "PROFIT_SURVIVED":
        return "HOLD"
    return "OBSERVE"


def is_vote_correct(predicted: str, ground_truth_rec: str, label: str) -> bool:
    if predicted == ground_truth_rec:
        return True
    pred_bucket = ACTION_BUCKET.get(predicted, "monitor")
    truth_bucket = LABEL_BUCKET.get(label, ACTION_BUCKET.get(ground_truth_rec, "monitor"))
    return pred_bucket == truth_bucket


def bootstrap_validation_accuracy(validation: dict[str, Any] | None) -> float:
    if not validation:
        return 0.55
    best = (validation.get("best_strategy") or {})
    win_rate = float(best.get("win_rate") or 0)
    if win_rate > 0:
        return round(min(0.95, max(0.40, win_rate)), 3)
    rows = validation.get("ticker_breakdown") or []
    rates = [float(r.get("best_strategy_win_rate") or 0) for r in rows if r.get("best_strategy_win_rate")]
    if rates:
        return round(min(0.95, max(0.40, sum(rates) / len(rates))), 3)
    return 0.55


def observation_key(ticker: str, episode: dict[str, Any]) -> str:
    """Stable key — independent of committee run timestamp."""
    episode_key = episode.get("episode_key")
    if episode_key:
        return f"{ticker.upper()}|{episode_key}"
    return (
        f"{ticker.upper()}|{episode.get('memory_label')}|"
        f"{round(float(episode.get('high_pct') or 0), 2)}|"
        f"{round(float(episode.get('current_pct') or 0), 2)}|"
        f"{round(float(episode.get('missed_usd') or 0), 2)}"
    )


def update_member_stats(
    members: dict[str, dict[str, Any]],
    *,
    member_name: str,
    correct: bool,
) -> None:
    row = members[member_name]
    row["total_votes"] = int(row.get("total_votes", 0)) + 1
    if correct:
        row["correct_votes"] = int(row.get("correct_votes", 0)) + 1
    else:
        row["incorrect_votes"] = int(row.get("incorrect_votes", 0)) + 1
    total = row["total_votes"]
    accuracy = row["correct_votes"] / total if total else 0.0
    prior = float(row.get("accuracy") or 0.0)
    row["prior_accuracy"] = prior
    row["accuracy"] = round(accuracy, 3)
    row["weight"] = accuracy_to_weight(accuracy)
    row["trend"] = trend_from_delta(accuracy - prior) if total > 1 else "STABLE"
    row["last_update"] = datetime.now().isoformat(timespec="seconds")
    if accuracy >= 0.70:
        row["recommended_bias"] = "TRUST"
    elif accuracy < 0.45:
        row["recommended_bias"] = "DISCOUNT"
    else:
        row["recommended_bias"] = "NEUTRAL"


def weighted_recommendation(
    weighted_votes: list[dict[str, Any]],
    *,
    current_pct: float,
    high_pct: float,
    missed_usd: float,
) -> tuple[str, str, float]:
    if not weighted_votes:
        return "NO_ACTION", "LOW", 0.0

    total_weight = sum(v["weight"] for v in weighted_votes)
    if total_weight <= 0:
        return "NO_ACTION", "LOW", 0.0

    score_sum = sum(v["weight"] * REC_SCORE.get(v["recommendation"], 2) for v in weighted_votes)
    avg_score = score_sum / total_weight
    best_rec = min(REC_SCORE, key=lambda k: abs(REC_SCORE[k] - avg_score))

    if current_pct <= 0:
        if best_rec in {"PARTIAL_PROTECT_SHADOW", "EXIT_PROTECT_SHADOW", "TRAIL_PROTECT_SHADOW"}:
            best_rec = "WATCH" if high_pct >= 4.0 or missed_usd >= 50 else "NO_ACTION"

    spread = max(REC_SCORE.values()) - min(REC_SCORE.values())
    agreement = 1.0 - (max(v["weight"] * abs(REC_SCORE.get(v["recommendation"], 2) - avg_score) for v in weighted_votes) / max(spread, 1))
    if agreement >= 0.75 and total_weight >= 4:
        confidence = "HIGH"
    elif agreement >= 0.50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return best_rec, confidence, round(avg_score, 2)


def build_weighted_ticker_row(
    ticker_row: dict[str, Any],
    members: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    votes = ticker_row.get("committee_votes") or {}
    weighted_lines: list[dict[str, Any]] = []
    for name, key in MEMBER_KEYS:
        raw_vote = votes.get(key, "DATA_MISSING")
        rec = vote_to_recommendation(name, raw_vote)
        weight = float(members[name]["weight"])
        weighted_lines.append(
            {
                "member": name,
                "raw_vote": raw_vote,
                "recommendation": rec,
                "weight": weight,
                "weighted_expression": f"{weight} × {rec}",
            }
        )

    final_rec, confidence, avg_score = weighted_recommendation(
        weighted_lines,
        current_pct=float(ticker_row.get("current_pct") or 0),
        high_pct=float(ticker_row.get("high_pct") or 0),
        missed_usd=float(ticker_row.get("missed_usd") or 0),
    )

    return {
        "ticker": ticker_row.get("ticker"),
        "current_pct": ticker_row.get("current_pct"),
        "v1_recommendation": ticker_row.get("final_committee_recommendation"),
        "weighted_member_votes": weighted_lines,
        "weighted_average_score": avg_score,
        "weighted_committee_recommendation": final_rec,
        "weighted_confidence": confidence,
        "explanation": (
            f"SHADOW_ONLY weighted committee: "
            + "; ".join(v["weighted_expression"] for v in weighted_lines)
            + f" → {final_rec} ({confidence})."
        ),
    }


def process_observations(
    members: dict[str, dict[str, Any]],
    *,
    committee: dict[str, Any],
    memory: dict[str, Any] | None,
    seen_observations: set[str],
) -> int:
    episode_by: dict[str, dict[str, Any]] = {}
    for ep in (memory or {}).get("episodes") or []:
        ticker = str(ep.get("ticker", "")).upper()
        if ticker:
            episode_by[ticker] = ep

    added = 0
    for ticker_row in committee.get("tickers") or []:
        ticker = str(ticker_row.get("ticker", "")).upper()
        episode = episode_by.get(ticker) or {}
        label = str(episode.get("memory_label") or "UNKNOWN_OUTCOME")
        ground_truth = ground_truth_from_label(label)
        obs_key = observation_key(ticker, episode)
        if obs_key in seen_observations:
            continue

        votes = ticker_row.get("committee_votes") or {}
        for name, key in MEMBER_KEYS:
            raw = votes.get(key, "DATA_MISSING")
            if raw == "DATA_MISSING":
                continue
            predicted = vote_to_recommendation(name, raw)
            correct = is_vote_correct(predicted, ground_truth, label)
            update_member_stats(members, member_name=name, correct=correct)

        seen_observations.add(obs_key)
        added += 1
    return added


def finalize_member_weights(members: dict[str, dict[str, Any]], validation: dict[str, Any] | None) -> None:
    val_acc = bootstrap_validation_accuracy(validation)
    val_row = members["Validation"]
    if int(val_row.get("total_votes") or 0) == 0:
        val_row["accuracy"] = val_acc
        val_row["weight"] = accuracy_to_weight(val_acc)
        val_row["recommended_bias"] = "BOOTSTRAP"
        val_row["trend"] = "STABLE"

    for row in members.values():
        if int(row.get("total_votes") or 0) == 0:
            row["weight"] = 1.0
            row["accuracy"] = 0.0
            row["trend"] = "STABLE"
            continue
        row["weight"] = accuracy_to_weight(float(row.get("accuracy") or 0))


def enrich_committee_outputs(
    committee: dict[str, Any],
    weighted_tickers: list[dict[str, Any]],
    members: dict[str, dict[str, Any]],
) -> None:
    committee["version"] = "v2_weighted"
    committee["adaptive_learning"] = {
        "enabled": True,
        "member_weights": {name: members[name]["weight"] for name, _ in MEMBER_KEYS},
        "learning_source": str(OUTPUT_JSON),
    }
    committee["weighted_tickers"] = weighted_tickers
    committee["global_summary"]["weighted_final_verdict"] = committee["global_summary"].get("final_verdict")
    committee["global_summary"]["average_member_weight"] = round(
        sum(members[n]["weight"] for n, _ in MEMBER_KEYS) / len(MEMBER_KEYS),
        2,
    )


def build_learning_report(
    *,
    committee_path: Path = COMMITTEE_JSON,
    memory_path: Path = MEMORY_JSON,
    brain_path: Path = BRAIN_JSON,
    validation_path: Path = VALIDATION_JSON,
    learning_path: Path = OUTPUT_JSON,
) -> dict[str, Any]:
    prior, prior_ok = load_json(learning_path)
    committee, committee_ok = load_json(committee_path)
    memory, memory_ok = load_json(memory_path)
    brain, brain_ok = load_json(brain_path)
    validation, validation_ok = load_json(validation_path)

    members = default_member_stats()
    seen_observations: set[str] = set()
    observation_log: list[str] = list((prior or {}).get("processed_observations") or [])

    if prior_ok and prior:
        for name, _ in MEMBER_KEYS:
            saved = (prior.get("members") or {}).get(name)
            if saved:
                members[name].update(saved)

    seen_observations.update(observation_log)
    new_obs = 0
    if committee_ok and committee:
        new_obs = process_observations(
            members,
            committee=committee,
            memory=memory if memory_ok else None,
            seen_observations=seen_observations,
        )
        observation_log = sorted(seen_observations)

    finalize_member_weights(members, validation if validation_ok else None)

    weighted_tickers: list[dict[str, Any]] = []
    if committee_ok and committee:
        for ticker_row in committee.get("tickers") or []:
            weighted_tickers.append(build_weighted_ticker_row(ticker_row, members))

    if committee_ok and committee:
        enrich_committee_outputs(committee, weighted_tickers, members)
        committee_path.write_text(json.dumps(committee, indent=2), encoding="utf-8")

    report = {
        "schema": "tae_profit_committee_learning",
        "version": "v2",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": {
            str(committee_path): committee_ok,
            str(memory_path): memory_ok,
            str(brain_path): brain_ok,
            str(validation_path): validation_ok,
        },
        "weight_policy": {
            "min_weight": WEIGHT_MIN,
            "max_weight": WEIGHT_MAX,
            "bands": [
                {"accuracy_lt_pct": 40, "weight": 0.60},
                {"accuracy_lt_pct": 55, "weight": 0.80},
                {"accuracy_lt_pct": 70, "weight": 1.00},
                {"accuracy_lt_pct": 85, "weight": 1.40},
                {"accuracy_lt_pct": 95, "weight": 1.80},
                {"accuracy_else": True, "weight": 2.20},
            ],
        },
        "members": members,
        "processed_observations": observation_log,
        "last_learning_run": {
            "new_observations_processed": new_obs,
            "total_observations": len(observation_log),
        },
        "weighted_tickers": weighted_tickers,
        "global_summary": {
            "members_tracked": len(members),
            "average_weight": round(sum(m["weight"] for m in members.values()) / len(members), 2),
            "top_weighted_member": max(members.values(), key=lambda m: m["weight"])["name"],
            "lowest_weighted_member": min(members.values(), key=lambda m: m["weight"])["name"],
            "final_verdict": "PDC_V2_SHADOW_READY_FOR_OBSERVATION"
            if committee_ok and weighted_tickers
            else "PDC_V2_SHADOW_NEEDS_MORE_DATA",
        },
    }
    return report


def _refresh_committee_md(committee: dict[str, Any], members: dict[str, dict[str, Any]]) -> None:
    summary = committee.get("global_summary") or {}
    lines = [
        "# TAE Profit Decision Committee v2 (Adaptive Weighted)",
        "",
        f"**Generated:** {committee.get('generated_at')}",
        f"**Mode:** {committee.get('mode')} — {committee.get('live_trading_impact')}",
        f"**Final verdict:** {summary.get('final_verdict')}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Adaptive member weights",
        "",
        "| member | accuracy | weight | trend | votes | correct | incorrect |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    adaptive = committee.get("adaptive_learning") or {}
    member_rows = members or {}

    for name in ["Rules", "PIB", "PSP", "Memory", "Validation"]:
        m = (member_rows or {}).get(name, {})
        if m:
            lines.append(
                f"| {name} | {round(float(m.get('accuracy', 0)) * 100, 1)}% | {m.get('weight')} | "
                f"{m.get('trend')} | {m.get('total_votes')} | {m.get('correct_votes')} | {m.get('incorrect_votes')} |"
            )

    lines.extend(
        [
            "",
            "## Weighted recommendations",
            "",
            "| ticker | v1 rec | weighted rec | confidence |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in committee.get("weighted_tickers") or []:
        lines.append(
            f"| {row.get('ticker')} | {row.get('v1_recommendation')} | "
            f"{row.get('weighted_committee_recommendation')} | {row.get('weighted_confidence')} |"
        )

    COMMITTEE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    members = report.get("members") or {}
    lines = [
        "# TAE Profit Committee Learning v2",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {report['global_summary']['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY adaptive learning**",
        "",
        "## Committee member weights",
        "",
        "| member | accuracy | weight | trend | votes | correct | incorrect | bias |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name in ["Rules", "PIB", "PSP", "Memory", "Validation"]:
        m = members.get(name, {})
        acc_pct = round(float(m.get("accuracy", 0)) * 100, 1)
        lines.append(
            f"| {name} | {acc_pct}% | {m.get('weight')} | {m.get('trend')} | "
            f"{m.get('total_votes')} | {m.get('correct_votes')} | {m.get('incorrect_votes')} | "
            f"{m.get('recommended_bias')} |"
        )

    lines.extend(
        [
            "",
            "## Member summary",
            "",
        ]
    )
    for name in ["Rules", "PIB", "PSP", "Memory", "Validation"]:
        m = members.get(name, {})
        acc_pct = round(float(m.get("accuracy", 0)) * 100, 1)
        lines.append(
            f"### {name}\n"
            f"- accuracy: **{acc_pct}%**\n"
            f"- weight: **{m.get('weight')}**\n"
            f"- trend: **{m.get('trend')}**\n"
            f"- votes: **{m.get('total_votes')}** "
            f"(correct {m.get('correct_votes')}, incorrect {m.get('incorrect_votes')})\n"
        )

    lines.extend(
        [
            "## Weighted ticker decisions",
            "",
            "| ticker | weighted result | confidence | member votes |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report.get("weighted_tickers") or []:
        vote_str = "; ".join(
            f"{v['member']} {v['weighted_expression']}" for v in row.get("weighted_member_votes") or []
        )
        lines.append(
            f"| {row.get('ticker')} | {row.get('weighted_committee_recommendation')} | "
            f"{row.get('weighted_confidence')} | {vote_str} |"
        )

    lines.extend(["", "## Example weighted decision", ""])
    if report.get("weighted_tickers"):
        ex = report["weighted_tickers"][0]
        lines.append(f"**{ex.get('ticker')}**")
        for v in ex.get("weighted_member_votes") or []:
            lines.append(f"- {v['member']}: {v['weighted_expression']}")
        lines.append(
            f"- **Weighted result:** {ex.get('weighted_committee_recommendation')} "
            f"({ex.get('weighted_confidence')})"
        )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    members = report.get("members") or {}
    print("===== TAE PROFIT COMMITTEE LEARNING v2 =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", report["global_summary"]["final_verdict"])
    for name in ["Rules", "PIB", "PSP", "Memory", "Validation"]:
        m = members.get(name, {})
        acc = round(float(m.get("accuracy", 0)) * 100, 1)
        print(f"  {name}: accuracy {acc}% weight {m.get('weight')} trend {m.get('trend')}")
    if report.get("weighted_tickers"):
        ex = report["weighted_tickers"][0]
        print(
            "Example weighted:",
            ex.get("ticker"),
            "→",
            ex.get("weighted_committee_recommendation"),
            f"({ex.get('weighted_confidence')})",
        )


def main() -> int:
    report = build_learning_report()
    write_outputs(report)
    committee, committee_ok = load_json(COMMITTEE_JSON)
    if committee_ok and committee:
        _refresh_committee_md(committee, report.get("members") or {})
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
