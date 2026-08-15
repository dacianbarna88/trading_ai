#!/usr/bin/env python3
"""TAE CLI — learning economic attribution (measurement only)."""

from __future__ import annotations

import json
from typing import Any


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def run_run(args: list[str] | None = None) -> int:
    print("===== TAE LEARNING-ATTRIBUTION-RUN — PAPER ONLY / NO SSOT MUTATION =====")
    from tae_learning_economic_attribution_engine import run_attribution

    source_detail = bool(args and "--source-detail" in args)
    result = run_attribution(source_detail=source_detail, write_reports=True)
    _print(
        {
            k: result.get(k)
            for k in (
                "ok",
                "technical_verdict",
                "economic_verdict",
                "status",
                "action_flips",
                "matured_impact_decisions",
                "pending_impact_decisions",
                "net_attributable_pnl",
                "gross_attributable_pnl",
                "sample_sufficient",
                "economically_material",
                "paper_mutated",
                "learning_state_mutated",
                "v1_mutated",
                "v2_mutated",
                "live_mutated",
                "duplicates_skipped",
                "ledger_rows_written",
            )
        }
    )
    return 0 if result.get("ok") else 1


def run_status(_args: list[str] | None = None) -> int:
    print("===== TAE LEARNING-ATTRIBUTION-STATUS =====")
    from tae_learning_economic_attribution_engine import observe_forward_evidence, status_snapshot

    # Refresh observation without requiring new decisions
    try:
        observe_forward_evidence(sync_ledger=True, write_monitor=True)
    except Exception as exc:
        print(f"observation_refresh_error: {type(exc).__name__}: {exc}")
    st = status_snapshot()
    _print(st)
    ok = st.get("status") in {
        "READY",
        "ATTRIBUTION_COMPLETE",
        "NO_MATURED_IMPACT_DECISIONS",
        "PARTIAL_DATA",
        "OBSERVATION_ACTIVE",
        "WAITING_FOR_MATURITY",
        "MATURED_OUTCOMES_AVAILABLE",
        "ATTRIBUTION_PENDING",
        "INSUFFICIENT_SAMPLE",
    } or st.get("observation_status") in {
        "OBSERVATION_ACTIVE",
        "WAITING_FOR_MATURITY",
        "MATURED_OUTCOMES_AVAILABLE",
        "ATTRIBUTION_COMPLETE",
        "INSUFFICIENT_SAMPLE",
    }
    return 0 if ok else 1


def run_report(_args: list[str] | None = None) -> int:
    print("===== TAE LEARNING-ATTRIBUTION-REPORT =====")
    from tae_learning_economic_attribution_engine import paths, run_attribution
    from tae_learning_persistence import load_json_safe

    p = paths()
    data, err = load_json_safe(p["summary"])
    if err or not data:
        # generate
        data = run_attribution(write_reports=True)
    _print(
        {
            "technical_verdict": data.get("technical_verdict"),
            "economic_verdict": data.get("economic_verdict"),
            "status": data.get("status"),
            "net_attributable_pnl": data.get("net_attributable_pnl"),
            "action_flips": data.get("action_flips"),
            "matured_impact_decisions": data.get("matured_impact_decisions"),
            "sample_sufficient": data.get("sample_sufficient"),
            "economically_material": data.get("economically_material"),
            "report": str(p["report_md"]),
            "json": str(p["deliverable_json"]),
        }
    )
    return 0 if data.get("ok", True) else 1


def run_verify(_args: list[str] | None = None) -> int:
    print("===== TAE LEARNING-ATTRIBUTION-VERIFY =====")
    from tae_learning_economic_attribution_engine import verify_attribution

    v = verify_attribution()
    _print(v)
    return 0 if v.get("ok") else 1
