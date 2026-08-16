#!/usr/bin/env python3
"""PAPER-only lifecycle glue for learning-to-profit hypotheses.

This module extends the existing learning-to-profit SSOT.  It does not own a
learning runtime and must never write canonical or parallel PAPER books.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
LTP_ROOT = PROJECT_ROOT / "runtime_outputs" / "learning_to_profit"
SELF_IMPROVE_ROOT = LTP_ROOT / "self_improve"
CYCLES_PATH = SELF_IMPROVE_ROOT / "learning_cycles.jsonl"
EXPERIMENTS_ROOT = SELF_IMPROVE_ROOT / "experiments"

LIVE_AUTONOMY = False
CONTROL_STRATEGY = "V1"
MAX_ACTIVE_CHALLENGERS = 3
EXPERIMENT_COOLDOWN_HOURS = 24


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_id(value: Any) -> str:
    text = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(value or ""))
    return text.strip("-_") or "UNKNOWN"


def _experiment_dir(cycle_id: str) -> Path:
    return EXPERIMENTS_ROOT / _safe_id(cycle_id)


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def append_cycle(cycle: dict) -> Path:
    """Append a lifecycle snapshot and update its experiment manifest."""
    payload = dict(cycle)
    payload.setdefault("updated_at", _now())
    payload.setdefault("live_autonomy", False)
    payload.setdefault("mode", "PAPER_ONLY")
    SELF_IMPROVE_ROOT.mkdir(parents=True, exist_ok=True)
    with CYCLES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    cycle_id = _safe_id(payload.get("learning_cycle_id"))
    _json_write(_experiment_dir(cycle_id) / "manifest.json", payload)
    return CYCLES_PATH


def load_cycles(limit: int = 200) -> list[dict[str, Any]]:
    """Load the latest snapshot for each cycle, newest updates last."""
    if not CYCLES_PATH.is_file():
        return []
    latest: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    try:
        lines = CYCLES_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        cycle_id = str(row.get("learning_cycle_id") or "")
        if not cycle_id:
            continue
        if cycle_id not in latest:
            order.append(cycle_id)
        latest[cycle_id] = row
    rows = [latest[cycle_id] for cycle_id in order]
    return rows[-max(0, int(limit)) :] if limit else []


def _hypothesis_fingerprint(hyp: dict[str, Any]) -> str:
    basis = {
        "hypothesis_type": hyp.get("hypothesis_type"),
        "evidence_summary": hyp.get("evidence_summary") or hyp.get("observation"),
        "target_metric": hyp.get("target_metric"),
        "paper_experiment": hyp.get("paper_experiment"),
    }
    return hashlib.sha256(json.dumps(basis, sort_keys=True, default=str).encode()).hexdigest()[:16]


def create_cycle_from_hypothesis(hyp: dict) -> dict:
    hypothesis_id = _safe_id(hyp.get("hypothesis_id"))
    experiment = hyp.get("paper_experiment") or {}
    proposed_solution = {
        "single_change": experiment.get("action") or "OBSERVE_ONLY",
        "description": experiment.get("description") or hyp.get("expected_profit_mechanism"),
    }
    cycle_id = f"LC-{hypothesis_id}"
    from tae_self_improve_wiring import economic_experiment_uid, stable_hash
    from tae_self_improve_evolution import (
        allocate_strategy_id,
        build_strategy_lineage_record,
        current_paper_champion,
        validate_single_mutation,
    )

    cohort_key = hyp.get("behavior_cohort_key")
    champion = current_paper_champion()
    parent_strategy = str(
        hyp.get("parent_strategy")
        or (champion or {}).get("strategy_id")
        or CONTROL_STRATEGY
    )
    parent_generation = int((champion or {}).get("generation") or 0)
    generation = int(hyp.get("generation") or parent_generation + 1)
    mutation_validation = validate_single_mutation(
        hyp.get("config_overlay")
        or hyp.get("single_change")
        or proposed_solution
    )
    strategy_id = str(
        hyp.get("strategy_id")
        or allocate_strategy_id(parent_strategy, generation)
    )
    config_hash = hyp.get("config_hash") or stable_hash(
        {"paper_experiment": experiment, "single_change": hyp.get("single_change")}
    )
    uid = hyp.get("economic_experiment_uid") or economic_experiment_uid(
        hypothesis_id,
        parent_strategy,
        hyp.get("single_change") or proposed_solution["single_change"],
        cohort_key,
        config_hash,
    )
    cycle = {
        "learning_cycle_id": cycle_id,
        "hypothesis_id": hypothesis_id,
        "experiment_id": f"EXP-{hypothesis_id}",
        "hypothesis_fingerprint": _hypothesis_fingerprint(hyp),
        "economic_experiment_uid": uid,
        "config_hash": config_hash,
        "status": "READY_FOR_EXPERIMENT" if experiment else "SOLUTION_PROPOSED",
        "status_history": [
            "HYPOTHESIS_GENERATED",
            "SOLUTION_PROPOSED",
            *(["READY_FOR_EXPERIMENT"] if experiment else []),
        ],
        "observation": hyp.get("evidence_summary") or hyp.get("observation") or "No observation supplied",
        "hypothesis": hyp.get("hypothesis") or hyp.get("expected_profit_mechanism") or hyp.get("evidence_summary"),
        "proposed_solution": proposed_solution,
        "control_strategy": parent_strategy,
        "challenger_strategy": strategy_id,
        "strategy_id": strategy_id,
        "strategy_version": strategy_id,
        "parent_strategy_id": parent_strategy,
        "generation": generation,
        "mutation_validation": mutation_validation,
        "target_metric": hyp.get("target_metric"),
        "validation_rule": hyp.get("validation_rule"),
        "rejection_rule": hyp.get("rejection_rule"),
        "required_paper_duration": hyp.get("required_paper_duration"),
        "confidence": hyp.get("confidence"),
        "mode": "PAPER_ONLY",
        "live_autonomy": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    for key in (
        "behavior_class",
        "behavior_family",
        "behavior_cohort_key",
        "generalization_scope",
        "root_cause",
        "affected_tickers",
        "affected_rule",
        "parent_strategy",
        "validation_requirements_parsed",
        "single_change",
    ):
        if key in hyp:
            cycle[key] = hyp.get(key)
    if mutation_validation.get("ok"):
        lineage = build_strategy_lineage_record(
            parent_strategy,
            generation,
            mutation_validation["single_change"],
            cycle,
            strategy_id=strategy_id,
            status="PROPOSED",
        )
        cycle["lineage"] = lineage
    return cycle


def link_hypotheses_to_cycles(hypotheses_doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Create cycles for new LOSS_PATTERN hypotheses, deduped by hypothesis id."""
    existing = {str(row.get("hypothesis_id")) for row in load_cycles(limit=10000)}
    created: list[dict[str, Any]] = []
    for hyp in (hypotheses_doc or {}).get("hypotheses") or []:
        hypothesis_id = str(hyp.get("hypothesis_id") or "")
        hypothesis_type = str(hyp.get("hypothesis_type") or "")
        if not hypothesis_type.startswith("LOSS_PATTERN_") or not hypothesis_id or hypothesis_id in existing:
            continue
        cycle = create_cycle_from_hypothesis(hyp)
        append_cycle(cycle)
        if cycle.get("lineage"):
            from tae_self_improve_evolution import append_lineage

            append_lineage(cycle["lineage"])
        created.append(cycle)
        existing.add(hypothesis_id)
    return created


def run_experiment_scoring() -> dict[str, Any]:
    """Run the existing read-only PAPER scoring producer."""
    try:
        import tae_paper_experiment_runner as runner

        queue = runner.load_jsonl(runner.QUEUE_JSONL)
        hypotheses_doc = runner.load_json(runner.HYPOTHESES_JSON)
        if not queue:
            return {"ok": False, "reason": "EMPTY_EXPERIMENT_QUEUE", "experiments_run": 0}
        ctx = runner.build_scoring_context()
        results = runner.run_experiments(queue, hypotheses_doc, ctx)
        report = runner.build_report_payload(queue, results, ctx)
        paths = runner.write_outputs(report)
        return {
            "ok": True,
            "method": "programmatic",
            "experiments_run": len(results),
            "paths": [str(path) for path in paths],
            "report": report,
        }
    except Exception as exc:
        completed = subprocess.run(
            [sys.executable, "tae_paper_experiment_runner.py"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            "ok": completed.returncode == 0,
            "method": "subprocess",
            "exit_code": completed.returncode,
            "error": str(exc),
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }


def evaluate_replay_gate(result: dict[str, Any] | None) -> str:
    """Translate chronological replay evidence into a conservative lifecycle status."""
    if not isinstance(result, dict) or not result:
        return "INSUFFICIENT_EVIDENCE"
    reliability = result.get("reliability") or {}
    accounting = result.get("control_a_reconciliation") or {}
    flags = list(reliability.get("flags") or [])
    reliable = result.get("reliable_for_promotion")
    if reliable is not True or accounting.get("pass") is False or accounting.get("reconciliation_pass") is False:
        if reliable is False and not flags and accounting:
            return "REPLAY_REJECTED"
        return "INSUFFICIENT_EVIDENCE"
    economic = result.get("economic_evaluations") or {}
    economic_rows = [row for row in economic.values() if isinstance(row, dict)]
    if economic_rows:
        return (
            "REPLAY_SUPPORTED"
            if any(bool(row.get("passes")) for row in economic_rows)
            else "REPLAY_REJECTED"
        )
    comparisons = result.get("comparisons") or {}
    if any(float(row.get("delta_net_pnl_usd") or 0) > 0 for row in comparisons.values() if isinstance(row, dict)):
        return "REPLAY_SUPPORTED"
    return "REPLAY_REJECTED"


def run_replay_for_cycle(cycle_id: str, *, write: bool = False) -> dict[str, Any]:
    """Run existing replay fail-soft and persist only a self-improve summary."""
    cycle = next(
        (row for row in load_cycles(limit=10000) if row.get("learning_cycle_id") == cycle_id),
        None,
    )
    if cycle is None:
        return {"ok": False, "cycle_id": cycle_id, "status": "INSUFFICIENT_EVIDENCE", "reason": "CYCLE_NOT_FOUND"}
    try:
        from tae_chronological_portfolio_replay import run_experiment

        result = run_experiment(write=write)
        status = evaluate_replay_gate(result)
        summary = {
            "ok": True,
            "cycle_id": cycle_id,
            "status": status,
            "reliable_for_promotion": result.get("reliable_for_promotion"),
            "verdict": result.get("verdict"),
            "reliability": result.get("reliability"),
            "control_a_reconciliation": result.get("control_a_reconciliation"),
            "comparisons": result.get("comparisons"),
            "economic_evaluations": result.get("economic_evaluations"),
            "replay_write_requested": bool(write),
            "recorded_at": _now(),
        }
    except Exception as exc:
        summary = {
            "ok": False,
            "cycle_id": cycle_id,
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "REPLAY_FAILED",
            "error": str(exc),
            "recorded_at": _now(),
        }
    _json_write(_experiment_dir(cycle_id) / "replay_result.json", summary)
    updated = dict(cycle)
    updated["status"] = summary["status"]
    updated["replay_summary"] = {key: summary.get(key) for key in ("status", "verdict", "reliable_for_promotion", "reason")}
    if summary["status"] == "REPLAY_SUPPORTED":
        try:
            from tae_self_improve_experimental import register_experimental_challenger

            updated["experimental_registration"] = register_experimental_challenger(updated)
        except Exception as exc:
            updated["experimental_registration"] = {
                "ok": False,
                "status": "REGISTRATION_REJECTED",
                "reason": "REGISTRATION_FAILED",
                "error": str(exc),
            }
    updated["updated_at"] = _now()
    append_cycle(updated)
    return summary


def run_replay_batch_for_ready_cycles(*, write: bool = False) -> dict[str, Any]:
    eligible = {"READY_FOR_EXPERIMENT", "SOLUTION_PROPOSED"}
    results = [
        run_replay_for_cycle(str(cycle["learning_cycle_id"]), write=write)
        for cycle in load_cycles(limit=10000)
        if cycle.get("status") in eligible
    ]
    return {"ok": all(row.get("ok") for row in results) if results else True, "replays_run": len(results), "results": results}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _find_cycle(cycle_id: str) -> dict[str, Any] | None:
    return next(
        (row for row in load_cycles(limit=10000) if row.get("learning_cycle_id") == cycle_id),
        None,
    )


def _write_empty_journal(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


def _maybe_create_strategy_lab_ticket(cycle: dict[str, Any]) -> dict[str, Any]:
    """Create only when the EXP strategy is already registered; never create state."""
    try:
        from tae_strategy_lab_promotion import create_ticket, load_promotion_state

        state = load_promotion_state(create_if_missing=False)
        strategy_id = str(cycle.get("challenger_strategy") or "")
        if strategy_id not in (state.get("strategies") or {}):
            return {"ok": False, "reason": "STRATEGY_NOT_REGISTERED"}
        return create_ticket(
            ticket_type="ADVANCE_TO_CHALLENGER",
            strategy_id=strategy_id,
            target_state="CHALLENGER",
            requested_by="tae_self_improve_lifecycle",
            rationale="PAPER-only isolated self-improvement challenger",
        )
    except Exception as exc:
        return {"ok": False, "reason": "STRATEGY_LAB_UNAVAILABLE", "error": str(exc)}


def activate_paper_challenger(cycle_id: str) -> dict[str, Any]:
    """Activate an isolated PAPER monitoring arm without inventing fills or PnL."""
    cycle = _find_cycle(cycle_id)
    if cycle is None:
        return {"ok": False, "status": "PAPER_REJECTED", "reason": "CYCLE_NOT_FOUND"}
    from tae_self_improve_wiring import validate_experiment_joins

    joins = cycle.get("experiment_joins")
    if not isinstance(joins, dict):
        joins = validate_experiment_joins(
            {"cycle": cycle, **(cycle.get("join_artifacts") or {})}
        )
    if joins.get("activation_blocked") or "CONFLICT" in joins.values():
        return {
            "ok": False,
            "status": "PAPER_REJECTED",
            "reason": "EXPERIMENT_JOIN_CONFLICT",
            "experiment_joins": joins,
        }
    status = str(cycle.get("status") or "")
    gate_pass = status == "REPLAY_SUPPORTED" or (
        status == "READY_FOR_EXPERIMENT" and cycle.get("experiment_gate_pass", True) is True
    )
    if status not in {"REPLAY_SUPPORTED", "READY_FOR_EXPERIMENT"} or not gate_pass:
        return {"ok": False, "status": "PAPER_REJECTED", "reason": "EXPERIMENT_GATE_NOT_PASSED"}
    mutation_validation = cycle.get("mutation_validation")
    if isinstance(mutation_validation, dict) and mutation_validation.get("ok") is False:
        return {
            "ok": False,
            "status": "PAPER_REJECTED",
            "reason": mutation_validation.get("reason") or "MUTATION_NOT_ALLOWED",
        }
    cycles = load_cycles(limit=10000)
    active = [row for row in cycles if row.get("status") == "PAPER_RUNNING"]
    if len(active) >= MAX_ACTIVE_CHALLENGERS:
        return {"ok": False, "status": "PAPER_REJECTED", "reason": "MAX_ACTIVE_CHALLENGERS"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=EXPERIMENT_COOLDOWN_HOURS)
    for other in cycles:
        if other.get("learning_cycle_id") == cycle_id:
            continue
        if other.get("hypothesis_fingerprint") != cycle.get("hypothesis_fingerprint"):
            continue
        activated = _parse_time(other.get("activated_at"))
        if activated and activated >= cutoff:
            return {"ok": False, "status": "PAPER_REJECTED", "reason": "HYPOTHESIS_COOLDOWN"}

    try:
        from tae_self_improve_experimental import (
            enable_experimental_arm,
            register_experimental_challenger,
        )

        registration = register_experimental_challenger(cycle)
        enablement = (
            enable_experimental_arm(cycle_id)
            if registration.get("ok")
            else {"ok": False, "reason": "REGISTRATION_FAILED"}
        )
    except Exception as exc:
        registration = {"ok": False, "reason": "REGISTRATION_FAILED", "error": str(exc)}
        enablement = {"ok": False, "reason": "ENABLE_FAILED", "error": str(exc)}
    if not registration.get("ok") or not enablement.get("ok"):
        return {
            "ok": False,
            "status": "PAPER_REJECTED",
            "reason": registration.get("reason")
            or enablement.get("reason")
            or "REGISTRATION_FAILED",
            "experimental_registration": registration,
            "experimental_enablement": enablement,
        }

    arm = Path(str(enablement["book_path"]))

    updated = dict(cycle)
    updated.update(
        status="PAPER_RUNNING",
        activated_at=_now(),
        sandbox_path=str(arm),
        monitoring_status="NO_FILLS_YET",
        live_autonomy=False,
        updated_at=_now(),
    )
    ticket = {"ok": True, "status": "DEFERRED_UNTIL_READY_FOR_HUMAN_PROMOTION"}
    updated["experimental_registration"] = registration
    updated["experimental_enablement"] = enablement
    updated["strategy_lab_ticket"] = ticket
    append_cycle(updated)
    if cycle.get("lineage"):
        from tae_self_improve_evolution import append_lineage

        append_lineage(
            {
                **cycle["lineage"],
                "lineage_event_id": f"{cycle['lineage']['lineage_event_id']}-ACTIVE",
                "status": "PAPER_ACTIVE",
                "activated_at": updated["activated_at"],
            }
        )
    return {
        "ok": True,
        "cycle_id": cycle_id,
        "status": "PAPER_RUNNING",
        "monitoring_status": "NO_FILLS_YET",
        "arm_path": str(arm),
        "strategy_lab_ticket": ticket,
        "live_promotion": False,
    }


def rollback_challenger(cycle_id: str, reason: str) -> dict[str, Any]:
    """Disable the sandbox arm while preserving all evidence."""
    cycle = _find_cycle(cycle_id)
    if cycle is None:
        return {"ok": False, "status": "PAPER_REJECTED", "reason": "CYCLE_NOT_FOUND"}
    manifest = dict(cycle)
    manifest.update(
        status="ROLLED_BACK",
        arm_enabled=False,
        rollback_reason=str(reason),
        rolled_back_at=_now(),
        live_autonomy=False,
        updated_at=_now(),
    )
    append_cycle(manifest)
    try:
        from tae_self_improve_experimental import disable_experimental_arm

        disable_experimental_arm(cycle_id, reason)
    except Exception:
        pass
    return {
        "ok": True,
        "cycle_id": cycle_id,
        "status": "ROLLED_BACK",
        "reason": str(reason),
        "evidence_preserved": True,
        "arm_path": str(cycle.get("sandbox_path") or (_experiment_dir(cycle_id) / "arm")),
    }


def monitor_and_gate(cycle_id: str) -> dict[str, Any]:
    """Conservatively gate an isolated PAPER challenger."""
    cycle = _find_cycle(cycle_id)
    if cycle is None:
        return {"ok": False, "status": "PAPER_REJECTED", "reason": "CYCLE_NOT_FOUND"}
    if cycle.get("status") == "PAPER_CHAMPION_ACTIVE":
        account = _read_json(
            Path(
                str(
                    cycle.get("sandbox_path")
                    or (_experiment_dir(cycle_id) / "arm")
                )
            )
            / "account.json"
        )
        from tae_self_improve_evolution import (
            evaluate_autonomous_champion,
            rollback_autonomous_champion,
        )

        control = _read_json(PROJECT_ROOT / "tae_accounting_snapshot.json")
        control_pnl = float(
            control.get("corrected_realized_pnl")
            or control.get("corrected_total_trading_pnl")
            or 0
        )
        health = evaluate_autonomous_champion(account or cycle, control_pnl=control_pnl)
        if health.get("degraded"):
            return rollback_autonomous_champion(
                str(health.get("reason")), evidence={"cycle_id": cycle_id, "account": account}
            )
        updated = {
            **cycle,
            "champion_health": health,
            "monitoring_status": "PAPER_CHAMPION_HEALTHY",
            "updated_at": _now(),
        }
        append_cycle(updated)
        return {
            "ok": True,
            "cycle_id": cycle_id,
            "status": "PAPER_CHAMPION_ACTIVE",
            "health": health,
        }
    if cycle.get("status") != "PAPER_RUNNING":
        return {"ok": False, "status": "PAPER_REJECTED", "reason": "CHALLENGER_NOT_RUNNING"}
    account = _read_json(Path(str(cycle.get("sandbox_path") or (_experiment_dir(cycle_id) / "arm"))) / "account.json")
    metrics = account.get("economic_attribution") or account.get("metrics") or {}
    fills = int(account.get("fills") or metrics.get("fill_count") or 0)
    closed = int(metrics.get("closed_cycles") or account.get("closed_cycles") or 0)
    observation_days = int(metrics.get("observation_days") or account.get("observation_days") or 0)
    pnl = float(account.get("total_pnl") or account.get("realized_pnl") or metrics.get("net_realized_pnl") or 0)
    expectancy = metrics.get("expectancy_per_closed_cycle", account.get("expectancy"))
    from tae_self_improve_wiring import build_remaining_evidence

    remaining_evidence = build_remaining_evidence(
        {
            "events": fills,
            "closed_cycles": closed,
            "observation_days": observation_days,
            "matured_outcomes": closed,
            "evaluation_at": _now(),
        },
        cycle.get("validation_requirements_parsed"),
    )

    if fills == 0:
        updated = dict(cycle)
        updated["remaining_evidence"] = remaining_evidence
        updated["monitoring_status"] = "NO_FILLS_YET"
        updated["updated_at"] = _now()
        append_cycle(updated)
        return {
            "ok": True,
            "cycle_id": cycle_id,
            "status": "KEEP_RUNNING",
            "evidence": "NO_FILLS_YET",
            "remaining_evidence": remaining_evidence,
        }
    if (expectancy is not None and float(expectancy) < 0) or pnl < 0:
        result = rollback_challenger(cycle_id, "NEGATIVE_EXPECTANCY_OR_PNL")
        result["decision"] = "PAPER_REJECTED"
        return result
    if remaining_evidence["wait_status"] != "READY_FOR_REEVALUATION":
        updated = dict(cycle)
        updated["remaining_evidence"] = remaining_evidence
        updated["monitoring_status"] = "INSUFFICIENT_EVIDENCE"
        updated["updated_at"] = _now()
        append_cycle(updated)
        return {
            "ok": True,
            "cycle_id": cycle_id,
            "status": "KEEP_RUNNING",
            "evidence": "INSUFFICIENT_EVIDENCE",
            "closed_cycles": closed,
            "observation_days": observation_days,
            "remaining_evidence": remaining_evidence,
        }

    control = _read_json(PROJECT_ROOT / "tae_accounting_snapshot.json")
    control_pnl = float(
        control.get("corrected_realized_pnl") or control.get("corrected_total_trading_pnl") or 0
    )
    if pnl <= control_pnl:
        result = rollback_challenger(cycle_id, "WORSE_PNL_THAN_CONTROL")
        result["decision"] = "PAPER_REJECTED"
        return result
    updated = dict(cycle)
    autonomous_candidate = {
        **updated,
        "remaining_evidence": remaining_evidence,
        "closed_cycles": closed,
        "observation_days": observation_days,
        "expectancy": expectancy,
        "pnl_delta": pnl - control_pnl,
        "reconciliation_pass": account.get("reconciliation_pass", True),
        "accounting_integrity": account.get("accounting_integrity", "PASS"),
        "data_integrity": account.get("data_integrity", "PASS"),
        "execution_integrity": account.get("execution_integrity", "PASS"),
    }
    from tae_self_improve_evolution import is_autonomy_enabled

    joins = cycle.get("experiment_joins") or {}
    join_conflict = joins.get("activation_blocked") or "CONFLICT" in joins.values()
    if is_autonomy_enabled() and not join_conflict:
        from tae_strategy_lab_promotion import (
            apply_autonomous_paper_promotion,
            create_autonomous_paper_ticket,
        )

        created = create_autonomous_paper_ticket(autonomous_candidate)
        promoted = (
            apply_autonomous_paper_promotion(created)
            if created.get("ok")
            else created
        )
        if promoted.get("ok"):
            updated.update(
                status="PAPER_CHAMPION_ACTIVE",
                autonomous_promotion_status="AUTO_PAPER_PROMOTED",
                human_approval_required=False,
                live_autonomy=False,
                profit_effect=pnl - control_pnl,
                remaining_evidence=remaining_evidence,
                updated_at=_now(),
            )
            updated["autonomous_promotion"] = promoted
            append_cycle(updated)
            return {
                **promoted,
                "cycle_id": cycle_id,
                "status": "AUTO_PAPER_PROMOTED",
            }
        updated["auto_promotion_blocked"] = promoted.get("reason")
    updated.update(
        status="READY_FOR_HUMAN_PROMOTION",
        human_approval_required=True,
        live_autonomy=False,
        profit_effect=pnl - control_pnl,
        updated_at=_now(),
    )
    updated["strategy_lab_ticket"] = _maybe_create_strategy_lab_ticket(updated)
    append_cycle(updated)
    return {
        "ok": True,
        "cycle_id": cycle_id,
        "status": "READY_FOR_HUMAN_PROMOTION",
        "human_approval_required": True,
        "live_promotion_performed": False,
        "profit_effect": pnl - control_pnl,
        "strategy_lab_ticket": updated["strategy_lab_ticket"],
    }

