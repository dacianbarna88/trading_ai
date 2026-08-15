#!/usr/bin/env python3
"""TAE CLI — Strategy Lab Sprint 1–4 (SSOT façade + human-gated promotion)."""

from __future__ import annotations

import json
from typing import Any


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def _arg_value(argv: list[str], flag: str, default: str = "") -> str:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def run(args: list[str] | None = None) -> int:
    """
    strategy-lab [status|scoreboard|registry|reconcile|explain|health|research|metrics|
                  recommend|promotion|ticket|approve|reject|apply|rollback]

    Promotion commands are human-gated lab state changes only.
    Never mutates parallel books or LIVE.
    """
    from tae_strategy_lab_facade import StrategyLabFacade, build_scoreboard, load_registry

    argv = list(args or [])
    sub = (argv[0].lower() if argv else "status").strip()
    rest = argv[1:]
    print("===== TAE STRATEGY-LAB — SSOT / HUMAN-GATED PROMOTION =====")
    print("Mode: ORCHESTRATION_OVER_PARALLEL_PAPER | NO_BROKER | NO_LIVE | NO_AUTO_PROMOTE")

    facade = StrategyLabFacade()
    if sub in {"status", "st"}:
        _print(facade.status())
        return 0
    if sub in {"registry", "reg"}:
        _print(
            {
                "identity": load_registry(),
                "lifecycle": facade.list_strategies_with_lifecycle(),
            }
        )
        return 0
    if sub in {"scoreboard", "board", "sb"}:
        doc = build_scoreboard(persist=True)
        _print(
            {
                "generated_at": doc.get("generated_at"),
                "scoreboard_path": doc.get("scoreboard_path"),
                "reconciliation_pass": (doc.get("reconciliation") or {}).get("pass"),
                "strategies": [
                    {
                        "strategy_id": r.get("strategy_id"),
                        "account_value": r.get("account_value"),
                        "pnl": r.get("pnl"),
                        "return_pct": r.get("return_pct"),
                        "sharpe": r.get("sharpe"),
                        "sortino": r.get("sortino"),
                        "expectancy": r.get("expectancy"),
                        "roi": r.get("roi"),
                        "accounting_integrity": r.get("accounting_integrity"),
                    }
                    for r in doc.get("strategies") or []
                ],
            }
        )
        return 0 if (doc.get("reconciliation") or {}).get("pass") else 1
    if sub in {"reconcile", "recon"}:
        doc = build_scoreboard(persist=True)
        _print(doc.get("reconciliation"))
        return 0 if (doc.get("reconciliation") or {}).get("pass") else 1
    if sub in {"explain", "explanation", "explanations"}:
        doc = facade.build_strategy_explanation(persist=True)
        _print(
            {
                "path": doc.get("path"),
                "deterministic": doc.get("deterministic"),
                "strategies": doc.get("strategies"),
            }
        )
        return 0
    if sub in {"health", "hp"}:
        doc = facade.build_strategy_health(persist=True)
        _print(
            {
                "path": doc.get("path"),
                "reconciliation_pass": doc.get("reconciliation_pass"),
                "strategies": doc.get("strategies"),
            }
        )
        return 0 if doc.get("reconciliation_pass") else 1
    if sub in {"research", "res"}:
        doc = facade.build_research_summary(persist=True)
        _print(
            {
                "path": doc.get("path"),
                "strategy_evolution": doc.get("strategy_evolution"),
                "candidate_registry": doc.get("candidate_registry"),
                "promotion_gate": doc.get("promotion_gate"),
                "replay": doc.get("replay"),
                "strategies": doc.get("strategies"),
            }
        )
        return 0
    if sub in {"metrics", "econ", "economics"}:
        doc = facade.build_economic_metrics(persist=True)
        _print(
            {
                "path": doc.get("path"),
                "reconciliation_pass": doc.get("reconciliation_pass"),
                "roi_global": {
                    "roi_id": (doc.get("roi_global") or {}).get("roi_id"),
                    "verdict": (doc.get("roi_global") or {}).get("verdict"),
                }
                if doc.get("roi_global")
                else None,
                "strategies": doc.get("strategies"),
            }
        )
        return 0 if doc.get("reconciliation_pass") else 1

    # ---- Sprint 4 human-gated promotion ----
    if sub in {"recommend", "recommendation"}:
        _print(facade.build_promotion_recommendation())
        return 0
    if sub in {"promotion", "promotion-status", "promo"}:
        _print(facade.promotion_status())
        return 0
    if sub in {"ticket", "create-ticket"}:
        # ticket TYPE STRATEGY TARGET --by USER [--note TEXT]
        if len(rest) < 3:
            print("Usage: strategy-lab ticket TYPE STRATEGY TARGET --by USER [--note TEXT]")
            return 2
        res = facade.create_promotion_ticket(
            ticket_type=rest[0],
            strategy_id=rest[1],
            target_state=rest[2],
            requested_by=_arg_value(rest, "--by", "operator"),
            rationale=_arg_value(rest, "--note", ""),
        )
        _print(res)
        return 0 if res.get("ok") else 1
    if sub in {"approve"}:
        if not rest:
            print("Usage: strategy-lab approve TICKET_ID --by APPROVER [--note TEXT]")
            return 2
        res = facade.approve_promotion(
            ticket_id=rest[0],
            approver=_arg_value(rest, "--by", ""),
            note=_arg_value(rest, "--note", ""),
        )
        _print(res)
        return 0 if res.get("ok") else 1
    if sub in {"reject"}:
        if not rest:
            print("Usage: strategy-lab reject TICKET_ID --by APPROVER [--note TEXT]")
            return 2
        res = facade.reject_promotion(
            ticket_id=rest[0],
            approver=_arg_value(rest, "--by", ""),
            note=_arg_value(rest, "--note", ""),
        )
        _print(res)
        return 0 if res.get("ok") else 1
    if sub in {"apply"}:
        if not rest:
            print("Usage: strategy-lab apply TICKET_ID")
            return 2
        res = facade.apply_human_promotion(ticket_id=rest[0])
        _print(res)
        return 0 if res.get("ok") else 1
    if sub in {"rollback"}:
        if not rest:
            print("Usage: strategy-lab rollback ARCHIVED_STRATEGY_ID --by USER [--note TEXT]")
            return 2
        res = facade.request_rollback(
            to_strategy_id=rest[0],
            requested_by=_arg_value(rest, "--by", "operator"),
            rationale=_arg_value(rest, "--note", ""),
        )
        _print(res)
        return 0 if res.get("ok") else 1

    print(
        "Unknown subcommand. Use: status | registry | scoreboard | reconcile | "
        "explain | health | research | metrics | recommend | promotion | "
        "ticket | approve | reject | apply | rollback"
    )
    return 2


def run_status(args: list[str] | None = None) -> int:
    return run(["status", *(args or [])])


def run_scoreboard(args: list[str] | None = None) -> int:
    return run(["scoreboard", *(args or [])])


def run_explain(args: list[str] | None = None) -> int:
    return run(["explain", *(args or [])])


def run_health(args: list[str] | None = None) -> int:
    return run(["health", *(args or [])])


def run_research(args: list[str] | None = None) -> int:
    return run(["research", *(args or [])])


def run_metrics(args: list[str] | None = None) -> int:
    return run(["metrics", *(args or [])])


def run_recommend(args: list[str] | None = None) -> int:
    return run(["recommend", *(args or [])])


def run_promotion(args: list[str] | None = None) -> int:
    return run(["promotion", *(args or [])])
