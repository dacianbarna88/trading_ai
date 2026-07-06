#!/usr/bin/env python3
"""
TAE Profit Decision Committee v1 — SHADOW_ONLY / NO_BROKER.

Consolidates profit protection, PIB/PSP, memory, and validation into
one explainable recommendation per ticker. No live execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

SHADOW_JSON = Path("tae_profit_protection_shadow.json")
BRAIN_JSON = Path("tae_profit_intelligence_brain.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")

OUTPUT_JSON = Path("tae_profit_decision_committee.json")
OUTPUT_MD = Path("tae_profit_decision_committee.md")

COMMITTEE_RECOMMENDATIONS = frozenset(
    {
        "HOLD",
        "OBSERVE",
        "WATCH",
        "TRAIL_PROTECT_SHADOW",
        "PARTIAL_PROTECT_SHADOW",
        "EXIT_PROTECT_SHADOW",
        "NO_ACTION",
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


def score_to_band(score: float) -> str:
    if score <= 20:
        return "NO_ACTION"
    if score <= 40:
        return "OBSERVE"
    if score <= 60:
        return "WATCH"
    if score <= 80:
        return "PARTIAL_PROTECT_SHADOW"
    return "EXIT_PROTECT_SHADOW"


def protection_rules_vote(shadow_row: dict[str, Any] | None) -> str:
    if not shadow_row:
        return "DATA_MISSING"
    rules = shadow_row.get("rules_v1") or {}
    if rules.get("profit_at_risk"):
        return "PROTECT_URGENT"
    if rules.get("profit_lock_active"):
        return "PROTECT_WATCH"
    signal = str(shadow_row.get("protection_signal", ""))
    if "PARTIAL" in signal or "TRAILING" in signal:
        return "PROTECT_SHADOW"
    if signal == "PROFIT_PROTECTION_WATCH":
        return "OBSERVE"
    return "NEUTRAL"


def intelligence_vote(brain_row: dict[str, Any] | None) -> str:
    if not brain_row:
        return "DATA_MISSING"
    rec = str(
        brain_row.get("psp_adjusted_recommendation")
        or brain_row.get("final_recommendation")
        or "NO_ACTION"
    )
    return rec


def psp_vote(brain_row: dict[str, Any] | None) -> str:
    if not brain_row:
        return "DATA_MISSING"
    urgency = str(brain_row.get("psp_protection_urgency", "UNKNOWN"))
    giveback = _f(brain_row.get("psp_giveback_risk"))
    survival = _f(brain_row.get("psp_survival_probability"))
    if urgency == "CRITICAL" or giveback >= 0.75:
        return "PSP_CRITICAL"
    if urgency == "HIGH" or giveback >= 0.55 or survival <= 0.25:
        return "PSP_ELEVATED"
    if survival >= 0.70:
        return "PSP_STABLE"
    return "PSP_NEUTRAL"


def memory_vote(memory_row: dict[str, Any] | None, episode: dict[str, Any] | None) -> str:
    if memory_row:
        bias = str(memory_row.get("recommended_memory_bias", "MEMORY_NEUTRAL"))
        if bias == "MEMORY_PROTECT_EARLY":
            return "MEMORY_PROTECT_EARLY"
        if bias == "MEMORY_HOLD_WINNERS":
            return "MEMORY_HOLD_WINNERS"
    if episode:
        label = str(episode.get("memory_label", ""))
        if label == "PROFIT_COLLAPSED":
            return "EPISODE_COLLAPSED"
        if label == "PROFIT_DECAYED":
            return "EPISODE_DECAYED"
        if label == "PROFIT_SURVIVED":
            return "EPISODE_SURVIVED"
    if not memory_row and not episode:
        return "DATA_MISSING"
    return "MEMORY_NEUTRAL"


def validation_vote(validation: dict[str, Any] | None, ticker: str) -> str:
    if not validation:
        return "DATA_MISSING"
    for row in validation.get("ticker_breakdown") or []:
        if str(row.get("ticker", "")).upper() == ticker:
            rec = str(row.get("recommendation", ""))
            if rec in {"AVOID_PROTECTION_FOR_NOW", "DO_NOT_PROMOTE_TO_ADVISORY_YET"}:
                return "VALIDATION_AVOID"
            if rec in {"TEST_TRAILING_SHADOW", "TEST_PARTIAL_SELL_SHADOW"}:
                return "VALIDATION_PROTECT"
            return "VALIDATION_OBSERVE"
    verdict = str(validation.get("verdict", ""))
    if verdict == "PROMISING_BUT_NOT_READY":
        return "VALIDATION_SHADOW_ONLY"
    return "VALIDATION_NEUTRAL"


def compute_protection_score(
    *,
    current_pct: float,
    high_pct: float,
    drawdown: float,
    missed_usd: float,
    votes: dict[str, str],
    shadow_row: dict[str, Any] | None,
    brain_row: dict[str, Any] | None,
    memory_row: dict[str, Any] | None,
    episode: dict[str, Any] | None,
) -> float:
    score = 35.0

    rules = (shadow_row or {}).get("rules_v1") or {}
    if rules.get("profit_at_risk"):
        score += 15
    if rules.get("profit_lock_active"):
        score += 5

    label = str((episode or {}).get("memory_label", ""))
    if label == "PROFIT_COLLAPSED":
        score += 20
    elif label == "PROFIT_DECAYED":
        score += 12
    elif label == "PROFIT_SURVIVED":
        score -= 10

    giveback = _f((brain_row or {}).get("psp_giveback_risk"))
    survival = _f((brain_row or {}).get("psp_survival_probability"))
    urgency = str((brain_row or {}).get("psp_protection_urgency", ""))

    if giveback >= 0.75:
        score += 15
    elif giveback >= 0.55:
        score += 10
    if survival <= 0.20:
        score += 12
    elif survival >= 0.80:
        score -= 12
    if urgency == "CRITICAL":
        score += 10
    elif urgency == "HIGH":
        score += 6

    memory_bias = str((memory_row or {}).get("recommended_memory_bias", ""))
    if memory_bias == "MEMORY_PROTECT_EARLY":
        score += 15
    elif memory_bias == "MEMORY_HOLD_WINNERS":
        score -= 15

    if votes.get("profit_intelligence") in {"EXIT_PROTECT_SHADOW", "PARTIAL_PROTECT_SHADOW"}:
        score += 8
    if votes.get("protection_rules") == "PROTECT_URGENT":
        score += 8

    decay = str(((brain_row or {}).get("votes") or {}).get("profit_decay", ""))
    trend = str(((brain_row or {}).get("votes") or {}).get("trend_defender", ""))
    if decay == "PROFIT_AT_RISK":
        score += 10
    elif decay == "PROFIT_STABLE" and trend == "HOLD_TREND_HEALTHY":
        score -= 15

    if high_pct >= 6.0 and drawdown <= -5.0:
        score += 10
    if missed_usd >= 100:
        score += 8
    elif missed_usd >= 50:
        score += 4

    if current_pct > 0 and current_pct < 2.0:
        score -= 8

    return max(0.0, min(100.0, round(score, 1)))


def derive_confidence(
    *,
    sources_present: int,
    brain_row: dict[str, Any] | None,
    shadow_row: dict[str, Any] | None,
    memory_row: dict[str, Any] | None,
) -> str:
    if sources_present >= 4 and brain_row and shadow_row and memory_row:
        return "HIGH"
    if sources_present >= 3 and (brain_row or shadow_row):
        return "MEDIUM"
    return "LOW"


def apply_safety_and_overrides(
    *,
    score: float,
    band_rec: str,
    current_pct: float,
    high_pct: float,
    missed_usd: float,
    shadow_row: dict[str, Any] | None,
    brain_row: dict[str, Any] | None,
    memory_row: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    rec = band_rec

    signal = str((shadow_row or {}).get("protection_signal", ""))
    decay = str(((brain_row or {}).get("votes") or {}).get("profit_decay", ""))
    survival = _f((brain_row or {}).get("psp_survival_probability"))
    memory_bias = str((memory_row or {}).get("recommended_memory_bias", ""))

    if (
        score <= 40
        and survival >= 0.70
        and decay == "PROFIT_STABLE"
        and memory_bias == "MEMORY_HOLD_WINNERS"
    ):
        rec = "HOLD"
        notes.append("Strong hold evidence from memory + stable profit.")
    elif score <= 35 and survival >= 0.75 and decay == "PROFIT_STABLE":
        rec = "HOLD"
        notes.append("Stable profit with high survival — hold bias.")

    if 45 <= score <= 70 and ("TRAILING" in signal or "TRAIL" in str((brain_row or {}).get("psp_adjusted_recommendation", ""))):
        if rec in {"WATCH", "OBSERVE"}:
            rec = "TRAIL_PROTECT_SHADOW"
            notes.append("Trailing shadow favored by protection signal.")

    if current_pct <= 0:
        if rec in {"PARTIAL_PROTECT_SHADOW", "EXIT_PROTECT_SHADOW", "TRAIL_PROTECT_SHADOW"}:
            notes.append("Safety override: PnL ≤ 0 blocks take-profit style actions.")
        if high_pct >= 4.0 or missed_usd >= 50:
            rec = "WATCH"
            notes.append("Significant historical profit fade — watch only.")
        else:
            rec = "NO_ACTION"
            notes.append("Non-positive PnL with limited fade — no action.")

    return rec, notes


def build_explanation(
    *,
    ticker: str,
    score: float,
    rec: str,
    votes: dict[str, str],
    override_notes: list[str],
) -> str:
    parts = [
        f"SHADOW_ONLY committee for {ticker}: score={score:.1f} → {rec}.",
        f"Votes: rules={votes.get('protection_rules')}, "
        f"pib={votes.get('profit_intelligence')}, "
        f"psp={votes.get('profit_survival')}, "
        f"memory={votes.get('profit_memory')}, "
        f"validation={votes.get('validation')}.",
    ]
    parts.extend(override_notes)
    return " ".join(parts)


def analyze_ticker(
    ticker: str,
    *,
    shadow_row: dict[str, Any] | None,
    brain_row: dict[str, Any] | None,
    memory_row: dict[str, Any] | None,
    episode: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    sources_present: int,
) -> dict[str, Any]:
    current_pct = _f((brain_row or shadow_row or {}).get("current_pct"))
    high_pct = _f((brain_row or shadow_row or {}).get("high_pct"))
    drawdown = _f((brain_row or {}).get("drawdown") or (shadow_row or {}).get("drawdown_from_high_pct"))
    missed_usd = _f((brain_row or {}).get("missed_usd") or (shadow_row or {}).get("missed_opportunity_usd"))

    votes = {
        "protection_rules": protection_rules_vote(shadow_row),
        "profit_intelligence": intelligence_vote(brain_row),
        "profit_survival": psp_vote(brain_row),
        "profit_memory": memory_vote(memory_row, episode),
        "validation": validation_vote(validation, ticker),
    }

    score = compute_protection_score(
        current_pct=current_pct,
        high_pct=high_pct,
        drawdown=drawdown,
        missed_usd=missed_usd,
        votes=votes,
        shadow_row=shadow_row,
        brain_row=brain_row,
        memory_row=memory_row,
        episode=episode,
    )
    band_rec = score_to_band(score)
    final_rec, override_notes = apply_safety_and_overrides(
        score=score,
        band_rec=band_rec,
        current_pct=current_pct,
        high_pct=high_pct,
        missed_usd=missed_usd,
        shadow_row=shadow_row,
        brain_row=brain_row,
        memory_row=memory_row,
    )
    confidence = derive_confidence(
        sources_present=sources_present,
        brain_row=brain_row,
        shadow_row=shadow_row,
        memory_row=memory_row,
    )
    explanation = build_explanation(
        ticker=ticker,
        score=score,
        rec=final_rec,
        votes=votes,
        override_notes=override_notes,
    )

    return {
        "ticker": ticker,
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown": round(drawdown, 2),
        "missed_usd": round(missed_usd, 2),
        "protection_score": score,
        "confidence": confidence,
        "committee_votes": votes,
        "score_band_recommendation": band_rec,
        "final_committee_recommendation": final_rec,
        "explanation": explanation,
        "shadow_only": True,
    }


def build_global_verdict(
    tickers: list[dict[str, Any]],
    *,
    sources_loaded: dict[str, bool],
) -> str:
    if not any(
        [
            sources_loaded.get(str(SHADOW_JSON), False),
            sources_loaded.get(str(BRAIN_JSON), False),
        ]
    ):
        return "PDC_NOT_READY"
    if len(tickers) >= 3:
        return "PDC_SHADOW_READY_FOR_OBSERVATION"
    if len(tickers) >= 1:
        return "PDC_SHADOW_NEEDS_MORE_DATA"
    return "PDC_NOT_READY"


def build_committee_report(
    *,
    shadow_path: Path = SHADOW_JSON,
    brain_path: Path = BRAIN_JSON,
    memory_path: Path = MEMORY_JSON,
    validation_path: Path = VALIDATION_JSON,
) -> dict[str, Any]:
    shadow, shadow_ok = load_json(shadow_path)
    brain, brain_ok = load_json(brain_path)
    memory, memory_ok = load_json(memory_path)
    validation, validation_ok = load_json(validation_path)

    sources_loaded = {
        str(shadow_path): shadow_ok,
        str(brain_path): brain_ok,
        str(memory_path): memory_ok,
        str(validation_path): validation_ok,
    }
    sources_present = sum(1 for v in sources_loaded.values() if v)

    shadow_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (shadow or {}).get("positions") or []
        if r.get("ticker")
    }
    brain_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (brain or {}).get("positions") or []
        if r.get("ticker")
    }
    memory_by = {
        str(r.get("ticker", "")).upper(): r
        for r in (memory or {}).get("ticker_memory") or []
        if r.get("ticker")
    }
    episode_by: dict[str, dict[str, Any]] = {}
    for ep in (memory or {}).get("episodes") or []:
        ticker = str(ep.get("ticker", "")).upper()
        if ticker and ticker not in episode_by:
            episode_by[ticker] = ep

    all_tickers = sorted(set(shadow_by) | set(brain_by) | set(memory_by))
    tickers: list[dict[str, Any]] = []
    for ticker in all_tickers:
        tickers.append(
            analyze_ticker(
                ticker,
                shadow_row=shadow_by.get(ticker),
                brain_row=brain_by.get(ticker),
                memory_row=memory_by.get(ticker),
                episode=episode_by.get(ticker),
                validation=validation if validation_ok else None,
                sources_present=sources_present,
            )
        )

    tickers.sort(key=lambda t: t.get("protection_score", 0), reverse=True)

    scores = [t.get("protection_score", 0) for t in tickers]
    critical = sum(
        1
        for t in tickers
        if t.get("final_committee_recommendation") in {"EXIT_PROTECT_SHADOW", "PARTIAL_PROTECT_SHADOW"}
    )
    watch = sum(
        1 for t in tickers if t.get("final_committee_recommendation") in {"WATCH", "OBSERVE", "TRAIL_PROTECT_SHADOW"}
    )
    hold_no_action = sum(
        1
        for t in tickers
        if t.get("final_committee_recommendation") in {"HOLD", "NO_ACTION"}
    )

    return {
        "schema": "tae_profit_decision_committee",
        "version": "v1",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "validation_verdict": (validation or {}).get("verdict") if validation_ok else None,
        "score_bands": {
            "0-20": "NO_ACTION",
            "21-40": "OBSERVE",
            "41-60": "WATCH",
            "61-80": "PARTIAL_PROTECT_SHADOW",
            "81-100": "EXIT_PROTECT_SHADOW",
        },
        "tickers": tickers,
        "global_summary": {
            "total_tickers": len(tickers),
            "average_protection_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "critical_count": critical,
            "watch_count": watch,
            "hold_no_action_count": hold_no_action,
            "top_5_highest_protection_score": [
                {
                    "ticker": t["ticker"],
                    "protection_score": t["protection_score"],
                    "final_committee_recommendation": t["final_committee_recommendation"],
                    "confidence": t["confidence"],
                }
                for t in tickers[:5]
            ],
            "final_verdict": build_global_verdict(tickers, sources_loaded=sources_loaded),
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    lines = [
        "# TAE Profit Decision Committee v1",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Global summary",
        f"- Total tickers: **{summary['total_tickers']}**",
        f"- Average protection score: **{summary['average_protection_score']}**",
        f"- Critical (partial/exit): **{summary['critical_count']}**",
        f"- Watch/observe/trail: **{summary['watch_count']}**",
        f"- Hold / no action: **{summary['hold_no_action_count']}**",
        "",
        "## Top 5 highest protection score",
        "",
        "| ticker | score | recommendation | confidence |",
        "| --- | --- | --- | --- |",
    ]
    for row in summary.get("top_5_highest_protection_score") or []:
        lines.append(
            f"| {row['ticker']} | {row['protection_score']} | "
            f"{row['final_committee_recommendation']} | {row['confidence']} |"
        )

    lines.extend(
        [
            "",
            "## Tickers",
            "",
            "| ticker | current% | high% | missed | score | confidence | recommendation |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for t in report.get("tickers") or []:
        lines.append(
            f"| {t['ticker']} | {t['current_pct']} | {t['high_pct']} | {t['missed_usd']} | "
            f"{t['protection_score']} | {t['confidence']} | {t['final_committee_recommendation']} |"
        )

    lines.extend(["", "## Explanations", ""])
    for t in report.get("tickers") or []:
        lines.append(f"### {t['ticker']} — {t['final_committee_recommendation']} (score {t['protection_score']})")
        lines.append(t.get("explanation", ""))
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["global_summary"]
    print("===== TAE PROFIT DECISION COMMITTEE v1 =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", summary["final_verdict"])
    print("Tickers:", summary["total_tickers"])
    print("Avg protection score:", summary["average_protection_score"])
    print("Critical / watch / hold+no_action:", summary["critical_count"], summary["watch_count"], summary["hold_no_action_count"])
    for row in (summary.get("top_5_highest_protection_score") or [])[:3]:
        print(f"  {row['ticker']}: {row['protection_score']} → {row['final_committee_recommendation']}")


def main() -> int:
    report = build_committee_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
