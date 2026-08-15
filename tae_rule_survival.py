#!/usr/bin/env python3
"""
TAE Rule Survival — lifecycle states from PAPER rule outcome attribution.

PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION
Classifies rules from actual outcomes; does not make trading decisions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "PAPER_ONLY"
ATTRIBUTION_JSON = Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
LIFECYCLE_JSON = Path("runtime_outputs/paper_execution/rule_lifecycle.json")
REPORT_MD = Path("TAE_RULE_SURVIVAL_REPORT.md")

STATES = ("NEW", "TESTING", "ACTIVE", "TRUSTED", "WATCHLIST", "DEPRECATED", "DISABLED")
MIN_EVIDENCE = 5
MIN_TRUSTED = 10

LIFECYCLE_INFLUENCE = {
    "NEW": 0.9,
    "TESTING": 0.85,
    "ACTIVE": 1.0,
    "TRUSTED": 1.06,
    "WATCHLIST": 0.45,
    "DEPRECATED": 0.12,
    "DISABLED": 0.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def classify_rule_state(row: dict[str, Any]) -> tuple[str, str]:
    n = int(_f(row.get("total_decisions") or row.get("executions")))
    wins = int(_f(row.get("wins") or row.get("positive_outcomes")))
    win_rate = _f(row.get("win_rate")) or (wins / n if n else 0.0)
    net_pnl = _f(row.get("net_pnl_impact"))
    avg_pnl = _f(row.get("avg_actual_pnl")) or (net_pnl / n if n else 0.0)

    if n == 0:
        return "NEW", "no executions recorded"
    if n < MIN_EVIDENCE:
        return "TESTING", f"insufficient evidence ({n}<{MIN_EVIDENCE})"
    if win_rate >= 0.60 and avg_pnl > 0 and n >= MIN_TRUSTED:
        return "TRUSTED", f"win_rate={win_rate:.1%} avg_pnl=${avg_pnl:.2f} n={n}"
    if win_rate >= 0.45 and net_pnl > 0:
        return "ACTIVE", f"win_rate={win_rate:.1%} net_pnl=${net_pnl:.2f}"
    if win_rate < 0.15 and net_pnl < -100 and n >= MIN_EVIDENCE:
        return "DISABLED", f"win_rate={win_rate:.1%} net_pnl=${net_pnl:.2f} n={n}"
    if win_rate < 0.25 and net_pnl < -50 and n >= 8:
        return "DEPRECATED", f"win_rate={win_rate:.1%} net_pnl=${net_pnl:.2f}"
    if win_rate < 0.35 and net_pnl < 0:
        return "WATCHLIST", f"win_rate={win_rate:.1%} net_pnl=${net_pnl:.2f}"
    return "TESTING", f"mixed evidence win_rate={win_rate:.1%} net_pnl=${net_pnl:.2f}"


def build_rule_lifecycle(attribution: dict[str, Any] | None = None) -> dict[str, Any]:
    attribution = attribution if attribution is not None else load_json(ATTRIBUTION_JSON) or {}
    rules_in: dict[str, dict[str, Any]] = attribution.get("rules") or {}
    rules_out: dict[str, dict[str, Any]] = {}
    by_state: dict[str, list[str]] = {s: [] for s in STATES}

    for rule_id, row in sorted(rules_in.items()):
        state, reason = classify_rule_state(row)
        n = int(_f(row.get("total_decisions") or row.get("executions")))
        entry = {
            "rule_id": rule_id,
            "state": state,
            "reason": reason,
            "influence_multiplier": LIFECYCLE_INFLUENCE[state],
            "total_decisions": n,
            "wins": int(_f(row.get("wins") or row.get("positive_outcomes"))),
            "losses": int(_f(row.get("losses") or row.get("negative_outcomes"))),
            "win_rate": round(_f(row.get("win_rate")) or 0.0, 4),
            "avg_actual_pnl": round(_f(row.get("avg_actual_pnl")), 4),
            "net_pnl_impact": round(_f(row.get("net_pnl_impact")), 4),
            "recommended_influence_delta": _f(row.get("recommended_influence_delta")),
            "last_action": row.get("last_action"),
            "last_updated": row.get("last_updated"),
        }
        rules_out[rule_id] = entry
        by_state[state].append(rule_id)

    return {
        "schema": "tae.rule_lifecycle.v1",
        "mode": MODE,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "source": str(ATTRIBUTION_JSON),
        "rules": rules_out,
        "by_state": by_state,
        "counts": {state: len(ids) for state, ids in by_state.items()},
    }


def write_report(doc: dict[str, Any]) -> None:
    rules = doc.get("rules") or {}
    lines = [
        "# TAE Rule Survival Report",
        "",
        f"**Generated:** {doc.get('generated_at')}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
        f"**Source:** `{doc.get('source')}`",
        "",
        "## State counts",
        "",
    ]
    for state in STATES:
        lines.append(f"- **{state}**: {doc.get('counts', {}).get(state, 0)}")
    lines.extend(["", "## Rules by state", ""])

    for state in STATES:
        ids = (doc.get("by_state") or {}).get(state) or []
        if not ids:
            continue
        lines.append(f"### {state}")
        lines.append("")
        lines.append("| rule | win_rate | net_pnl | avg_pnl | reason |")
        lines.append("| --- | --- | --- | --- | --- |")
        for rid in ids[:15]:
            row = rules.get(rid) or {}
            lines.append(
                f"| {rid} | {row.get('win_rate', 0):.1%} | ${row.get('net_pnl_impact', 0):,.2f} | "
                f"${row.get('avg_actual_pnl', 0):,.2f} | {row.get('reason', '')[:60]} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Lifecycle influence multipliers",
            "",
            "| state | multiplier | effect |",
            "| --- | --- | --- |",
            "| DISABLED | 0.0 | cannot increase action score |",
            "| DEPRECATED | 0.12 | strongly reduced |",
            "| WATCHLIST | 0.45 | reduced |",
            "| TESTING | 0.85 | cautious |",
            "| ACTIVE | 1.0 | neutral |",
            "| TRUSTED | 1.06 | modest boost (capped) |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_rule_survival(*, write_report_flag: bool = True) -> dict[str, Any]:
    doc = build_rule_lifecycle()
    LIFECYCLE_JSON.parent.mkdir(parents=True, exist_ok=True)
    from tae_learning_persistence import atomic_write_json, learning_state_lock

    with learning_state_lock(blocking=True):
        atomic_write_json(LIFECYCLE_JSON, doc)
        if write_report_flag:
            write_report(doc)
    return {"ok": True, "document": doc, "path": str(LIFECYCLE_JSON)}


def main() -> int:
    result = run_rule_survival()
    doc = result.get("document") or {}
    print("===== TAE RULE SURVIVAL =====")
    print(f"Mode: {MODE} | lifecycle from actual PAPER outcomes")
    print(f"Rules classified: {len(doc.get('rules') or {})}")
    for state in STATES:
        print(f"  {state}: {doc.get('counts', {}).get(state, 0)}")
    print(f"Wrote: {LIFECYCLE_JSON} {REPORT_MD}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
