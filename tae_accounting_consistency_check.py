#!/usr/bin/env python3
"""
TAE Accounting Consistency Check — verify single SSOT across UI and reports.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.accounting.accounting_snapshot import (
    build_accounting_snapshot,
    load_accounting_snapshot,
)

OUT_JSON = Path("tae_accounting_consistency_check.json")
OUT_MD = Path("tae_accounting_consistency_check.md")


def _load_review(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _approx_equal(a: Any, b: Any, tol: float = 0.02) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def run_checks(root: Path = Path(".")) -> dict[str, Any]:
    snapshot_file, file_status = load_accounting_snapshot(root=root)
    snapshot_live = build_accounting_snapshot(root)
    snapshot = snapshot_file if snapshot_file else snapshot_live

    review = _load_review(root / "tae_full_ecosystem_review.json")
    fin = (review or {}).get("B_financial_status") or {}
    drag = (review or {}).get("Performance_Drag_Analysis") or {}

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str, **extra: Any) -> None:
        checks.append({"check_id": check_id, "passed": passed, "detail": detail, **extra})

    corrected_total = snapshot.get("corrected_total_trading_pnl")
    review_corrected = fin.get("corrected_total_pnl_excluding_cash_deposits") or fin.get("total_pnl")
    add(
        "review_corrected_pnl_matches_snapshot",
        _approx_equal(review_corrected, corrected_total),
        f"review={review_corrected} snapshot={corrected_total}",
    )

    add(
        "review_realized_matches_snapshot",
        _approx_equal(fin.get("corrected_realized_pnl"), snapshot.get("corrected_realized_pnl")),
        f"review={fin.get('corrected_realized_pnl')} snapshot={snapshot.get('corrected_realized_pnl')}",
    )

    effective = float(snapshot.get("effective_contributed_capital") or 0)
    cash = float(snapshot.get("cash_available") or 0)
    open_val = float(snapshot.get("open_positions_value") or 0)
    av_cash = float(snapshot.get("account_value_cash_based") or snapshot.get("account_value_corrected") or 0)
    av_capital = float(snapshot.get("account_value_capital_based") or 0)

    add(
        "cash_plus_open_equals_account_value",
        _approx_equal(cash + open_val, av_cash),
        f"cash({cash})+open({open_val})={round(cash+open_val,2)} vs account_value={av_cash}",
    )

    add(
        "effective_capital_plus_pnl_equals_account_value",
        _approx_equal(effective + float(corrected_total or 0), av_capital),
        f"effective({effective})+pnl({corrected_total})={round(effective+float(corrected_total or 0),2)} "
        f"vs account_value={av_capital}",
    )

    add(
        "account_value_dual_path_reconciles",
        _approx_equal(av_cash, av_capital),
        f"cash_based={av_cash} capital_based={av_capital} delta={round(av_cash-av_capital,4)}",
    )

    excluded = float(snapshot.get("capital_deposits_excluded_as_duplicate") or 0)
    detected = float(snapshot.get("capital_deposits_detected") or 0)
    add(
        "virtual_deposit_not_double_counted",
        excluded == 0 or excluded == detected,
        f"detected={detected} excluded={excluded} counted={snapshot.get('capital_deposits_counted')} — "
        + (
            f"virtual ${excluded} excluded from effective capital; "
            f"account value does NOT add deposit on top of $30k base"
            if excluded > 0
            else "no deposits to classify"
        ),
    )

    add(
        "capital_base_status_documented",
        bool(snapshot.get("capital_base_status")),
        f"status={snapshot.get('capital_base_status')}",
    )

    top_losers = drag.get("top_losing_trades") or snapshot.get("top_losers_corrected") or []
    gs_in_losers = any(
        t.get("ticker") == "GS" and (t.get("pnl") or 0) < -100
        for t in top_losers[:3]
    )
    gs_audit = None
    for t in snapshot.get("top_winners_corrected") or []:
        if t.get("ticker") == "GS":
            gs_audit = t
            break
    if not gs_audit:
        for a in (snapshot.get("biggest_historical_mismatch") or {},):
            if isinstance(a, dict) and a.get("ticker") == "GS":
                gs_audit = {"pnl": a.get("expected_realized_pnl")}
    gs_positive = gs_audit and (gs_audit.get("pnl") or 0) > 0
    add(
        "gs_not_negative_top_drag",
        not gs_in_losers and gs_positive,
        f"GS in top losers with stale negative={gs_in_losers} corrected GS pnl={gs_audit.get('pnl') if gs_audit else 'N/A'}",
    )

    add(
        "snapshot_file_present",
        file_status == "OK",
        f"snapshot file status={file_status}",
    )

    add(
        "data_quality_documented",
        bool(snapshot.get("data_quality_status")),
        f"status={snapshot.get('data_quality_status')}",
    )

    all_pass = all(c["passed"] for c in checks)
    return {
        "schema": "tae.accounting_consistency_check.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS" if all_pass else "FAIL",
        "snapshot_source": "file" if snapshot_file else "live_build",
        "canonical_metrics": {
            "starting_capital_config": snapshot.get("starting_capital_config"),
            "effective_contributed_capital": snapshot.get("effective_contributed_capital"),
            "capital_deposits_detected": snapshot.get("capital_deposits_detected"),
            "capital_deposits_counted": snapshot.get("capital_deposits_counted"),
            "capital_deposits_excluded": snapshot.get("capital_deposits_excluded_as_duplicate"),
            "account_value_corrected": snapshot.get("account_value_corrected"),
            "account_value_cash_based": snapshot.get("account_value_cash_based"),
            "account_value_capital_based": snapshot.get("account_value_capital_based"),
            "corrected_total_trading_pnl": corrected_total,
            "corrected_realized_pnl": snapshot.get("corrected_realized_pnl"),
            "corrected_unrealized_pnl": snapshot.get("corrected_unrealized_pnl"),
            "cash_available": snapshot.get("cash_available"),
            "open_positions_value": snapshot.get("open_positions_value"),
            "capital_base_status": snapshot.get("capital_base_status"),
            "data_quality_status": snapshot.get("data_quality_status"),
            "top_drag_corrected": snapshot.get("top_drag_corrected"),
        },
        "checks": checks,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# TAE Accounting Consistency Check",
        "",
        f"**Verdict:** **{report.get('verdict')}**",
        f"**Generated:** {report.get('generated_at')}",
        "",
        "## Canonical metrics",
        "",
    ]
    for k, v in (report.get("canonical_metrics") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Checks", ""])
    for c in report.get("checks") or []:
        mark = "PASS" if c.get("passed") else "FAIL"
        lines.append(f"- [{mark}] **{c.get('check_id')}** — {c.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    report = run_checks()
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(report), encoding="utf-8")
    print(f"Verdict: {report['verdict']}")
    for c in report["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check_id']}: {c['detail']}")
    print(f"Wrote: {OUT_JSON}, {OUT_MD}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
