#!/usr/bin/env python3
"""
TAE DPE-6 — Learning Engine — READ_ONLY / PAPER_ONLY / SHADOW_ONLY.

Learns from DPE-5 evaluation results. Appends to learning history only.
Does NOT modify executors, evaluator, or live paths.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dpe.learning.v1"
MODE = "READ_ONLY"
SOURCE = "tae_dpe_learning_engine"

EVALUATION_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
OUTPUT_DIR = Path("runtime_outputs/dpe/learning")
LEARNING_JSON = OUTPUT_DIR / "learning.json"
LEARNING_MD = OUTPUT_DIR / "learning.md"
ROOT_REPORT = Path("TAE_DPE6_LEARNING_ENGINE_REPORT.md")


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


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def evaluation_id(evaluation: dict[str, Any]) -> str:
    raw = f"{evaluation.get('generated_at')}|{evaluation.get('overall', {}).get('winner')}|{evaluation.get('schema_version')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def classify_market_regime(comp: dict[str, Any]) -> str:
    capture = _f(comp.get("profit_capture_rate"))
    opp = _f(comp.get("opportunity_cost"))
    ref_capture = _f(comp.get("market_profit_capture_rate_reference"))
    if opp >= 700:
        return "HIGH_OPPORTUNITY_COST"
    if capture < ref_capture * 0.5:
        return "DEFENSIVE"
    if capture >= ref_capture:
        return "EFFICIENT"
    return "MIXED"


def classify_volatility(comp: dict[str, Any]) -> str:
    dd = _f(comp.get("max_drawdown"))
    if dd >= 8.0:
        return "HIGH"
    if dd >= 4.0:
        return "MODERATE"
    return "LOW"


def classify_portfolio_regime(comp: dict[str, Any]) -> str:
    dd = _f(comp.get("max_drawdown"))
    paper_opp = _f(comp.get("paper_opportunity_cost"))
    starting = _f(comp.get("starting_value"))
    if dd >= 7.0 or (starting and paper_opp / starting > 0.07):
        return "HIGH_RISK"
    if dd >= 3.0:
        return "MODERATE_RISK"
    return "LOW_RISK"


def classify_drawdown_profile(comp: dict[str, Any]) -> str:
    dd = _f(comp.get("max_drawdown"))
    if dd >= 8.0:
        return "ELEVATED"
    if dd >= 4.0:
        return "MODERATE"
    return "CONTROLLED"


def build_context_label(market_regime: str, volatility: str, portfolio_regime: str) -> str:
    market = market_regime.replace("_", " ")
    vol = f"{volatility} VOLATILITY" if volatility in {"HIGH", "MODERATE", "LOW"} else volatility
    port = portfolio_regime.replace("_", " ")
    return f"{port} + {vol}"


def build_learning_record(evaluation: dict[str, Any]) -> dict[str, Any]:
    overall = evaluation.get("overall") or {}
    comp = evaluation.get("competitive") or {}
    collab = evaluation.get("collaborative") or {}

    market_regime = classify_market_regime(comp)
    volatility = classify_volatility(comp)
    portfolio_regime = classify_portfolio_regime(comp)
    drawdown_profile = classify_drawdown_profile(comp)

    return {
        "timestamp": _now(),
        "evaluation_id": evaluation_id(evaluation),
        "evaluation_generated_at": evaluation.get("generated_at"),
        "winner": overall.get("winner"),
        "confidence": _f(overall.get("confidence_pct")),
        "reason": overall.get("reason"),
        "market_context": {
            "regime": market_regime,
            "volatility": volatility,
            "opportunity_cost": comp.get("opportunity_cost"),
            "profit_capture_rate": comp.get("profit_capture_rate"),
            "market_capture_reference": comp.get("market_profit_capture_rate_reference"),
        },
        "portfolio_context": {
            "regime": portfolio_regime,
            "drawdown_profile": drawdown_profile,
            "max_drawdown_pct": comp.get("max_drawdown"),
            "capital_efficiency": comp.get("capital_efficiency"),
            "paper_opportunity_cost": comp.get("paper_opportunity_cost"),
        },
        "context_label": build_context_label(market_regime, volatility, portfolio_regime),
        "key_metrics": {
            "competitive_total_pnl": comp.get("total_pnl"),
            "collaborative_total_pnl": collab.get("total_pnl"),
            "competitive_realized_pnl": comp.get("realized_pnl"),
            "collaborative_realized_pnl": collab.get("realized_pnl"),
            "competitive_unrealized_pnl": comp.get("unrealized_pnl"),
            "collaborative_unrealized_pnl": collab.get("unrealized_pnl"),
            "competitive_win_rate": comp.get("win_rate"),
            "collaborative_win_rate": collab.get("win_rate"),
            "profit_factor_competitive": comp.get("profit_factor"),
            "profit_factor_collaborative": collab.get("profit_factor"),
            "competitive_metric_wins": overall.get("competitive_metric_wins"),
            "collaborative_metric_wins": overall.get("collaborative_metric_wins"),
            "ties": overall.get("ties"),
        },
        "recommendation": overall.get("recommendation"),
    }


def load_learning_store() -> dict[str, Any]:
    store = load_json(LEARNING_JSON)
    if store and isinstance(store.get("records"), list):
        return store
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "source": SOURCE,
        "created_at": _now(),
        "updated_at": _now(),
        "records": [],
    }


def append_record(store: dict[str, Any], record: dict[str, Any]) -> bool:
    existing_ids = {_s(r.get("evaluation_id")) for r in store.get("records") or []}
    eid = record.get("evaluation_id")
    if eid in existing_ids:
        return False
    store.setdefault("records", []).append(record)
    store["updated_at"] = _now()
    return True


def compute_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "total_records": 0,
            "winning_frequency": {},
            "confidence_evolution": [],
            "dominant_philosophy": None,
            "average_confidence": 0.0,
            "latest_winner": None,
            "latest_confidence": 0.0,
        }

    freq: dict[str, int] = {}
    confidences: list[float] = []
    evolution: list[dict[str, Any]] = []
    context_patterns: dict[str, dict[str, int]] = {}

    for rec in records:
        winner = _s(rec.get("winner")) or "UNKNOWN"
        freq[winner] = freq.get(winner, 0) + 1
        conf = _f(rec.get("confidence"))
        confidences.append(conf)
        evolution.append(
            {
                "timestamp": rec.get("timestamp"),
                "evaluation_id": rec.get("evaluation_id"),
                "winner": winner,
                "confidence": conf,
            }
        )
        label = _s(rec.get("context_label")) or "UNKNOWN"
        ctx = context_patterns.setdefault(label, {})
        ctx[winner] = ctx.get(winner, 0) + 1

    dominant = max(freq.items(), key=lambda x: x[1])[0] if freq else None
    latest = records[-1]

    emerging = []
    for label, winners in context_patterns.items():
        top = max(winners.items(), key=lambda x: x[1])
        emerging.append({"context": label, "dominant_winner": top[0], "count": top[1]})

    return {
        "total_records": len(records),
        "winning_frequency": freq,
        "confidence_evolution": evolution,
        "dominant_philosophy": dominant,
        "average_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        "latest_winner": latest.get("winner"),
        "latest_confidence": _f(latest.get("confidence")),
        "emerging_patterns": emerging,
    }


def write_learning_md(store: dict[str, Any], new_record: dict[str, Any] | None, appended: bool) -> None:
    summary = store.get("summary") or {}
    records = store.get("records") or []

    lines = [
        "# TAE DPE-6 Learning Engine",
        "",
        f"**Generated:** {_now()}",
        f"**Mode:** {MODE} · PAPER_ONLY · SHADOW_ONLY",
        f"**Schema:** {SCHEMA_VERSION}",
        "",
        "> Append-only learning from DPE-5 evaluation results",
        "",
        "## Current recommendation",
        "",
    ]
    if records:
        latest = records[-1]
        lines.extend(
            [
                "```text",
                "Context:",
                latest.get("context_label", "UNKNOWN"),
                "",
                "Winner:",
                str(latest.get("winner")),
                "",
                f"Confidence:",
                f"{latest.get('confidence')}%",
                "```",
                "",
                f"**Reason:** {latest.get('reason')}",
                "",
                f"**Action:** {latest.get('recommendation')}",
            ]
        )
    else:
        lines.append("_No learning records yet._")

    lines.extend(
        [
            "",
            "## Learning history",
            "",
            "| # | timestamp | evaluation_id | context | winner | confidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for idx, rec in enumerate(records[-20:], start=max(1, len(records) - 19)):
        lines.append(
            f"| {idx} | {rec.get('timestamp')} | {rec.get('evaluation_id')} | "
            f"{rec.get('context_label')} | {rec.get('winner')} | {rec.get('confidence')}% |"
        )

    lines.extend(
        [
            "",
            "## Winning frequency",
            "",
            "| philosophy | wins |",
            "| --- | --- |",
        ]
    )
    for phil, count in sorted((summary.get("winning_frequency") or {}).items()):
        lines.append(f"| {phil} | {count} |")

    lines.extend(
        [
            "",
            f"- **Dominant philosophy:** {summary.get('dominant_philosophy')}",
            f"- **Average confidence:** {summary.get('average_confidence')}%",
            f"- **Total records:** {summary.get('total_records')}",
            "",
            "## Confidence evolution",
            "",
            "| timestamp | winner | confidence |",
            "| --- | --- | --- |",
        ]
    )
    for row in (summary.get("confidence_evolution") or [])[-10:]:
        lines.append(f"| {row.get('timestamp')} | {row.get('winner')} | {row.get('confidence')}% |")

    lines.extend(["", "## Emerging patterns", ""])
    for pattern in summary.get("emerging_patterns") or []:
        lines.append(
            f"- **{pattern.get('context')}** → {pattern.get('dominant_winner')} "
            f"({pattern.get('count')} observation(s))"
        )

    if new_record and appended:
        lines.extend(
            [
                "",
                "## Latest learning record",
                "",
                "```text",
                "Context:",
                new_record.get("context_label", ""),
                "",
                "Winner:",
                str(new_record.get("winner")),
                "",
                f"Confidence:",
                f"{new_record.get('confidence')}%",
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## Safety confirmation",
            "",
            "- READ_ONLY: **true**",
            "- History append-only: **true**",
            "- Executors not modified: **true**",
            "- Evaluator not modified: **true**",
            "",
            "## Next sprint",
            "",
            "**TAE DPE-7 — Adaptive Philosophy Selector**",
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LEARNING_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_report(
    *,
    store: dict[str, Any],
    appended: bool,
    new_record: dict[str, Any] | None,
    validation_pass: bool,
) -> None:
    summary = store.get("summary") or {}
    lines = [
        "# TAE DPE-6 — Learning Engine Sprint Report",
        "",
        f"**Date:** {_now()}",
        f"**Mode:** READ_ONLY · PAPER_ONLY · SHADOW_ONLY · NO_BROKER",
        f"**Status:** {'PASS' if validation_pass else 'FAIL'}",
        "",
        "## Executions learned",
        "",
        f"- Evaluation processed this run: **{'yes' if new_record else 'no'}**",
        f"- New record appended: **{'yes' if appended else 'no (duplicate skipped)'}**",
        f"- Total historical records: **{summary.get('total_records', 0)}**",
        "",
        "## Historical records",
        "",
        f"- Store path: `{LEARNING_JSON}`",
        f"- Append-only policy: **enforced**",
        "",
        "## Dominant philosophy",
        "",
        f"- **{summary.get('dominant_philosophy')}**",
        f"- Winning frequency: {summary.get('winning_frequency')}",
        "",
        "## Confidence trend",
        "",
        f"- Latest confidence: **{summary.get('latest_confidence')}%**",
        f"- Average confidence: **{summary.get('average_confidence')}%**",
        f"- Latest winner: **{summary.get('latest_winner')}**",
        "",
        "## Safety confirmation",
        "",
        "| Rule | Status |",
        "| --- | --- |",
        "| READ_ONLY | ✅ |",
        "| PAPER_ONLY | ✅ |",
        "| SHADOW_ONLY | ✅ |",
        "| NO_BROKER | ✅ |",
        "| NO_LIVE_BOT_CHANGE | ✅ |",
        "| NO_PORTFOLIO_CSV_CHANGE | ✅ |",
        "| NO_COMMIT | ✅ |",
        "| Executors unchanged | ✅ |",
        "| Evaluator unchanged | ✅ |",
        "",
        "## Recommended next sprint",
        "",
        "**TAE DPE-7 — Adaptive Philosophy Selector**",
    ]
    ROOT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(store: dict[str, Any], appended: bool) -> None:
    summary = store.get("summary") or {}
    print("===== TAE DPE-6 LEARNING ENGINE =====")
    print("Mode: READ_ONLY — learn from evaluation only")
    print("Input:", EVALUATION_JSON)
    print("Output:", LEARNING_JSON)
    print("Total records:", summary.get("total_records", 0))
    print("New record appended:", appended)
    print("Dominant philosophy:", summary.get("dominant_philosophy"))
    print("Latest winner:", summary.get("latest_winner"), f"@ {summary.get('latest_confidence')}%")


def main() -> int:
    evaluation = load_json(EVALUATION_JSON)
    if not evaluation:
        print(f"ERROR: missing {EVALUATION_JSON}", file=__import__("sys").stderr)
        return 1

    store = load_learning_store()
    record = build_learning_record(evaluation)
    appended = append_record(store, record)
    store["summary"] = compute_summary(store.get("records") or [])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LEARNING_JSON.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    write_learning_md(store, record if appended else None, appended)

    validation_pass = (
        LEARNING_JSON.is_file()
        and LEARNING_MD.is_file()
        and len(store.get("records") or []) > 0
        and store.get("summary", {}).get("total_records", 0) > 0
    )
    write_root_report(store=store, appended=appended, new_record=record, validation_pass=validation_pass)
    print_summary(store, appended)
    print("Wrote:", LEARNING_JSON, LEARNING_MD, ROOT_REPORT)
    return 0 if validation_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
