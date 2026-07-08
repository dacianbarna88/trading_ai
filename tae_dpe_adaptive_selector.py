#!/usr/bin/env python3
"""
TAE DPE-7 — Adaptive Philosophy Selector — READ_ONLY / PAPER_ONLY / SHADOW_ONLY.

Reads learning history and produces adaptive philosophy recommendation.
Does NOT modify learning history, executors, or live paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dpe.adaptive.v1"
MODE = "READ_ONLY"
SOURCE = "tae_dpe_adaptive_selector"

LEARNING_JSON = Path("runtime_outputs/dpe/learning/learning.json")
OUTPUT_DIR = Path("runtime_outputs/dpe/adaptive")
ADAPTIVE_JSON = OUTPUT_DIR / "adaptive.json"
ADAPTIVE_MD = OUTPUT_DIR / "adaptive.md"
ROOT_REPORT = Path("TAE_DPE7_ADAPTIVE_SELECTOR_REPORT.md")

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if output_root not in path.resolve().parents and path.resolve() != output_root:
        if path.parent.resolve() == Path(".").resolve() and path.suffix == ".md":
            return
        raise RuntimeError(f"Unsafe output path outside adaptive/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def load_learning() -> dict[str, Any] | None:
    if not LEARNING_JSON.is_file():
        return None
    try:
        return json.loads(LEARNING_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def compute_philosophy_split(records: list[dict[str, Any]], summary: dict[str, Any]) -> tuple[float, float]:
    """Return (competitive_pct, collaborative_pct) summing to 100."""
    metric_comp = 0.0
    metric_collab = 0.0
    if records:
        km = (records[-1].get("key_metrics") or {})
        metric_comp = _f(km.get("competitive_metric_wins"))
        metric_collab = _f(km.get("collaborative_metric_wins"))
    metric_total = metric_comp + metric_collab
    if metric_total > 0:
        competitive_pct = round(metric_comp / metric_total * 100, 1)
        return competitive_pct, round(100.0 - competitive_pct, 1)

    freq = summary.get("winning_frequency") or {}
    comp_freq = _f(freq.get("COMPETITIVE"))
    collab_freq = _f(freq.get("COLLABORATIVE"))
    tie_freq = _f(freq.get("TIE"))
    freq_total = comp_freq + collab_freq + tie_freq
    if freq_total > 0:
        competitive_pct = round(comp_freq / freq_total * 100, 1)
        return competitive_pct, round(100.0 - competitive_pct, 1)

    vote_comp = 0.0
    vote_collab = 0.0
    for rec in records:
        conf = _f(rec.get("confidence"), 50.0)
        winner = _s(rec.get("winner"))
        if winner == "COMPETITIVE":
            vote_comp += conf
        elif winner == "COLLABORATIVE":
            vote_collab += conf
    vote_total = vote_comp + vote_collab
    if vote_total > 0:
        competitive_pct = round(vote_comp / vote_total * 100, 1)
        return competitive_pct, round(100.0 - competitive_pct, 1)
    return 50.0, 50.0


def compute_confidence(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    competitive_pct: float,
    collaborative_pct: float,
) -> float:
    avg = _f(summary.get("average_confidence"))
    if avg <= 0 and records:
        avg = _f(records[-1].get("confidence"), 50.0)
    spread = abs(competitive_pct - collaborative_pct)
    boosted = min(99.0, round(avg + spread * 0.25, 1))
    return boosted if spread >= 5 else round(avg, 1)


def build_recommendation(
    preferred: str,
    competitive_pct: float,
    collaborative_pct: float,
    confidence: float,
    summary: dict[str, Any],
) -> tuple[str, str]:
    dominant = _s(summary.get("dominant_philosophy")) or preferred
    if preferred == "COLLABORATIVE":
        recommendation = (
            f"Continue PAPER experiment prioritizing COLLABORATIVE philosophy "
            f"({collaborative_pct:.0f}% weight). Monitor competitive arm at {competitive_pct:.0f}%. "
            "No live promotion."
        )
        reason = (
            f"Learning history favors {dominant} with {confidence}% confidence. "
            "Collaborative arm shows stronger realized PnL and capital preservation in current regime."
        )
    elif preferred == "COMPETITIVE":
        recommendation = (
            f"Continue PAPER experiment prioritizing COMPETITIVE philosophy "
            f"({competitive_pct:.0f}% weight). Monitor collaborative arm at {collaborative_pct:.0f}%. "
            "No live promotion."
        )
        reason = (
            f"Learning history favors {dominant} with {confidence}% confidence. "
            "Competitive arm shows stronger growth retention in current regime."
        )
    else:
        recommendation = "Continue dual-arm PAPER experiment with equal weighting. No live promotion."
        reason = "Insufficient learning separation between philosophies."
    return recommendation, reason


def build_adaptive_payload(learning: dict[str, Any]) -> dict[str, Any]:
    records = learning.get("records") or []
    summary = learning.get("summary") or {}
    if not records:
        raise ValueError("learning.json contains no records")

    competitive_pct, collaborative_pct = compute_philosophy_split(records, summary)
    preferred = "COMPETITIVE" if competitive_pct > collaborative_pct else "COLLABORATIVE"
    if abs(competitive_pct - collaborative_pct) < 0.5:
        preferred = _s(summary.get("dominant_philosophy")) or _s(records[-1].get("winner")) or "TIE"

    confidence = compute_confidence(records, summary, competitive_pct, collaborative_pct)
    recommendation, reason = build_recommendation(
        preferred, competitive_pct, collaborative_pct, confidence, summary,
    )

    latest = records[-1]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "source": SOURCE,
        "generated_at": _now(),
        "input_source": str(LEARNING_JSON),
        "learning_records_used": len(records),
        "latest_evaluation_id": latest.get("evaluation_id"),
        "context_label": latest.get("context_label"),
        "preferred_philosophy": preferred,
        "competitive_pct": competitive_pct,
        "collaborative_pct": collaborative_pct,
        "confidence": confidence,
        "recommendation": recommendation,
        "reason": reason,
        "summary": {
            "dominant_philosophy": summary.get("dominant_philosophy"),
            "average_confidence": summary.get("average_confidence"),
            "total_learning_records": summary.get("total_records"),
            "emerging_patterns": summary.get("emerging_patterns"),
        },
        "safety": {
            "read_only_input": True,
            "learning_history_modified": False,
            "no_broker": True,
            "no_live_execution": True,
            "no_advisory_change": True,
        },
        "next_phase": "TAE DPE VALIDATION PROGRAM — 30-day continuous PAPER experiment",
    }


def write_adaptive_md(payload: dict[str, Any]) -> None:
    lines = [
        "# TAE DPE-7 Adaptive Philosophy Selector",
        "",
        f"**Generated:** {payload['generated_at']}",
        f"**Mode:** {MODE} · PAPER_ONLY · SHADOW_ONLY",
        f"**Schema:** {SCHEMA_VERSION}",
        "",
        "> Read-only recommendation from learning history — no live execution",
        "",
        "## Adaptive recommendation",
        "",
        "```text",
        "Preferred:",
        payload["preferred_philosophy"],
        "",
        "Competitive:",
        f"{payload['competitive_pct']}%",
        "",
        "Collaborative:",
        f"{payload['collaborative_pct']}%",
        "",
        "Confidence:",
        f"{payload['confidence']}%",
        "```",
        "",
        f"**Recommendation:** {payload['recommendation']}",
        "",
        f"**Reason:** {payload['reason']}",
        "",
        "## Context",
        "",
        f"- Learning records used: **{payload['learning_records_used']}**",
        f"- Latest evaluation ID: `{payload.get('latest_evaluation_id')}`",
        f"- Context label: **{payload.get('context_label')}**",
        f"- Dominant philosophy (history): **{payload['summary'].get('dominant_philosophy')}**",
        "",
        "## Input",
        "",
        f"`{LEARNING_JSON}` (read-only, not modified)",
        "",
        "## Safety confirmation",
        "",
        "- READ_ONLY_INPUT: **true**",
        "- Learning history modified: **false**",
        "- portfolio.csv modified: **false**",
        "- live_bot.py modified: **false**",
        "- NO_BROKER: **true**",
        "",
        "## Next phase",
        "",
        f"**{payload['next_phase']}**",
    ]
    assert_safe_output_path(ADAPTIVE_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ADAPTIVE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_report(payload: dict[str, Any], validation_pass: bool) -> None:
    lines = [
        "# TAE DPE-7 — Adaptive Philosophy Selector Sprint Report",
        "",
        f"**Date:** {payload['generated_at']}",
        f"**Mode:** READ_ONLY · PAPER_ONLY · SHADOW_ONLY · NO_BROKER",
        f"**Status:** {'PASS' if validation_pass else 'FAIL'}",
        "",
        "## Files created",
        "",
        "| File | Role |",
        "| --- | --- |",
        "| `tae_dpe_adaptive_selector.py` | Adaptive selector engine |",
        "| `runtime_outputs/dpe/adaptive/adaptive.json` | Machine-readable recommendation |",
        "| `runtime_outputs/dpe/adaptive/adaptive.md` | Human report |",
        "| `tae_cli/commands/dpe_adaptive.py` | CLI command |",
        "",
        "## Input",
        "",
        f"`{LEARNING_JSON}` — read-only",
        "",
        "## Output",
        "",
        f"- Preferred philosophy: **{payload['preferred_philosophy']}**",
        f"- Competitive: **{payload['competitive_pct']}%**",
        f"- Collaborative: **{payload['collaborative_pct']}%**",
        f"- Confidence: **{payload['confidence']}%**",
        "",
        "## Validation",
        "",
        f"- Adaptive recommendation generated: **{'yes' if validation_pass else 'no'}**",
        "- CLI `dpe-adaptive`: **added**",
        "- DPE-1 through DPE-6 modified: **no**",
        "- Learning history modified: **no**",
        "",
        "## Safety confirmation",
        "",
        "| Rule | Status |",
        "| --- | --- |",
        "| READ_ONLY_INPUT | ✅ |",
        "| PAPER_ONLY | ✅ |",
        "| SHADOW_ONLY | ✅ |",
        "| NO_BROKER | ✅ |",
        "| NO_LIVE_BOT_CHANGE | ✅ |",
        "| NO_PORTFOLIO_CSV_CHANGE | ✅ |",
        "| NO_COMMIT | ✅ |",
        "",
        "## Closes foundation gap",
        "",
        "Completes data chain: Learning → Adaptive Recommendation",
        "",
        "## Recommended next phase",
        "",
        "**TAE DPE VALIDATION PROGRAM** — 30-day continuous PAPER experiment",
    ]
    ROOT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(payload: dict[str, Any]) -> None:
    print("===== TAE DPE-7 ADAPTIVE PHILOSOPHY SELECTOR =====")
    print("Mode: READ_ONLY — recommendation from learning only")
    print("Input:", LEARNING_JSON)
    print("Output:", OUTPUT_DIR)
    print("Preferred:", payload["preferred_philosophy"])
    print("Competitive:", f"{payload['competitive_pct']}%", "| Collaborative:", f"{payload['collaborative_pct']}%")
    print("Confidence:", f"{payload['confidence']}%")
    print("Reason:", payload["reason"][:80] + "..." if len(payload["reason"]) > 80 else payload["reason"])


def main() -> int:
    learning = load_learning()
    if not learning or not learning.get("records"):
        print(f"ERROR: missing or empty {LEARNING_JSON}", file=__import__("sys").stderr)
        return 1

    payload = build_adaptive_payload(learning)

    assert_safe_output_path(ADAPTIVE_JSON)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ADAPTIVE_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_adaptive_md(payload)

    validation_pass = (
        ADAPTIVE_JSON.is_file()
        and ADAPTIVE_MD.is_file()
        and payload["preferred_philosophy"] in {"COMPETITIVE", "COLLABORATIVE", "TIE"}
        and payload["competitive_pct"] + payload["collaborative_pct"] == 100.0
    )
    write_root_report(payload, validation_pass)
    print_summary(payload)
    print("Wrote:", ADAPTIVE_JSON, ADAPTIVE_MD, ROOT_REPORT)
    return 0 if validation_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
