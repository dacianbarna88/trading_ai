#!/usr/bin/env python3
"""PAPER-only lineage and evolution glue over existing TAE components.

This module owns no trading runtime.  It records immutable strategy ancestry,
validates a bounded mutation vocabulary, and exposes the Strategy Lab autonomy
kill switch.  LIVE and broker mutation paths are always rejected.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
SELF_IMPROVE_ROOT = (
    PROJECT_ROOT / "runtime_outputs" / "learning_to_profit" / "self_improve"
)
LINEAGE_PATH = SELF_IMPROVE_ROOT / "strategy_lineage.jsonl"
PROMOTION_STATE_PATH = PROJECT_ROOT / "runtime_outputs" / "strategy_lab" / "promotion_state.json"

IMMUTABLE_BASELINES = frozenset({"V1", "V2"})
MAX_ACTIVE_CHALLENGERS = 3
EXPERIMENT_COOLDOWN_HOURS = 24
MAX_AUTONOMOUS_PROMOTIONS_PER_DAY = 1
MAX_NEW_HYPOTHESES_PER_POST_CLOSE = 1

MUTATION_ALLOWLIST: dict[str, frozenset[str]] = {
    "ENTRY": frozenset(
        {
            "ENTRY_THRESHOLD",
            "ENTRY_TIMING",
            "ENTRY_QUALITY",
            "REENTRY_COOLDOWN",
            "MARKET_SESSION_FILTER",
        }
    ),
    "EXIT": frozenset(
        {
            "EXIT_THRESHOLD",
            "EXIT_TIMING",
            "STOP_THRESHOLD",
            "TAKE_PROFIT_THRESHOLD",
            "TRAILING_THRESHOLD",
        }
    ),
    "ACCUMULATION": frozenset(
        {
            "ADD_THRESHOLD",
            "ADD_TIMING",
            "ADD_SIZE",
            "MAX_ADDS",
            "ACCUMULATION_INTERVAL",
        }
    ),
    "CAPITAL": frozenset(
        {
            "POSITION_SIZE",
            "MAX_POSITION_NOTIONAL",
            "MAX_POSITIONS",
            "CASH_RESERVE",
            "CAPITAL_ALLOCATION",
        }
    ),
    "CONTEXT": frozenset(
        {
            "VOLATILITY_FILTER",
            "MARKET_REGIME",
            "LIQUIDITY_FILTER",
            "TREND_FILTER",
            "CONTEXT_CONFIDENCE",
        }
    ),
}

_ACTION_ALIASES = {
    "TIGHTEN_ONE_EXIT_RULE": ("EXIT", "EXIT_THRESHOLD"),
    "TIGHTEN_EXIT": ("EXIT", "EXIT_THRESHOLD"),
    "ONE_CHANGE": ("EXIT", "EXIT_THRESHOLD"),
    "OBSERVE_ONLY": ("CONTEXT", "CONTEXT_CONFIDENCE"),
}
_FORBIDDEN_TOKENS = (
    "LIVE",
    "BROKER",
    "ALPACA",
    "IBKR",
    "ORDER_SUBMIT",
    "PLACE_ORDER",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _normal(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")


def _declared_mutations(value: Any) -> tuple[list[Any], bool]:
    if not isinstance(value, dict):
        return ([value] if value not in (None, "") else []), False
    ablation = bool(value.get("ablation") or value.get("ablation_flag"))
    changes = value.get("changes") or value.get("mutations")
    if isinstance(changes, list):
        return [row for row in changes if row not in (None, "")], ablation
    overlay = value.get("config_overlay")
    if isinstance(overlay, dict) and overlay is not value:
        nested, nested_ablation = _declared_mutations(overlay)
        if nested:
            return nested, ablation or nested_ablation
    proposed = value.get("proposed_solution")
    if isinstance(proposed, dict) and proposed is not value:
        nested, nested_ablation = _declared_mutations(proposed)
        if nested:
            return nested, ablation or nested_ablation
    single = value.get("single_change")
    if isinstance(single, (list, tuple, set)):
        return [row for row in single if row not in (None, "")], ablation
    if single not in (None, ""):
        return [single], ablation
    if value.get("dimension") or value.get("family"):
        return [value], ablation
    return [], ablation


def _classify_mutation(change: Any) -> tuple[str | None, str | None]:
    if isinstance(change, dict):
        family = _normal(change.get("family") or change.get("mutation_family"))
        dimension = _normal(
            change.get("dimension")
            or change.get("mutation_dimension")
            or change.get("name")
            or change.get("key")
        )
        if family == "MARKET_CONTEXT":
            family = "CONTEXT"
        if family and dimension:
            return family, dimension
        change = change.get("action") or change.get("single_change") or dimension
    token = _normal(change)
    if token in _ACTION_ALIASES:
        return _ACTION_ALIASES[token]
    for family, dimensions in MUTATION_ALLOWLIST.items():
        for dimension in dimensions:
            if token == dimension or token.endswith("_" + dimension):
                return family, dimension
    inferred = next(
        (
            family
            for family in MUTATION_ALLOWLIST
            if token.startswith(family + "_")
            or (family == "CONTEXT" and token.startswith("MARKET_CONTEXT_"))
        ),
        None,
    )
    dimension = token.removeprefix("MARKET_") if inferred == "CONTEXT" else token
    return inferred, dimension or None


def validate_single_mutation(overlay: Any) -> dict[str, Any]:
    """Validate one allowlisted PAPER mutation; ablations may declare many."""
    serialized = json.dumps(overlay, sort_keys=True, default=str).upper()
    if any(token in serialized for token in _FORBIDDEN_TOKENS):
        return {
            "ok": False,
            "single_change": None,
            "family": None,
            "dimension": None,
            "reason": "LIVE_OR_BROKER_MUTATION_FORBIDDEN",
        }
    changes, ablation = _declared_mutations(overlay)
    if not changes:
        return {
            "ok": False,
            "single_change": None,
            "family": None,
            "dimension": None,
            "reason": "MUTATION_REQUIRED",
        }
    if len(changes) != 1 and not ablation:
        return {
            "ok": False,
            "single_change": None,
            "family": None,
            "dimension": None,
            "reason": "MULTI_CHANGE_REJECTED",
        }
    classified = [_classify_mutation(change) for change in changes]
    invalid = [
        (family, dimension)
        for family, dimension in classified
        if family not in MUTATION_ALLOWLIST
        or dimension not in MUTATION_ALLOWLIST.get(str(family), frozenset())
    ]
    if invalid:
        family, dimension = invalid[0]
        return {
            "ok": False,
            "single_change": changes[0] if len(changes) == 1 else changes,
            "family": family,
            "dimension": dimension,
            "reason": "UNSUPPORTED_MUTATION_DIMENSION",
        }
    family, dimension = classified[0]
    return {
        "ok": True,
        "single_change": changes[0] if len(changes) == 1 else changes,
        "family": family,
        "dimension": dimension,
        "reason": "ABLATION_VALIDATED" if len(changes) > 1 else "SINGLE_MUTATION_VALIDATED",
        "ablation": ablation,
    }


def immutable_baseline_guard(strategy_id: Any) -> bool:
    """Return True only for mutable descendants."""
    return _normal(strategy_id) not in IMMUTABLE_BASELINES


def load_lineage(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or LINEAGE_PATH
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def allocate_strategy_id(parent_strategy_id: Any, generation: int) -> str:
    """Allocate a never-reused autonomous strategy ID from lineage SSOT."""
    generation = max(1, int(generation))
    used = {str(row.get("strategy_id")) for row in load_lineage()}
    candidates = [
        int(match.group(1))
        for sid in used
        if (match := re.match(r"^V(\d+)-GEN\d+$", sid))
    ]
    number = max([2, *candidates]) + 1
    candidate = f"V{number}-GEN{generation}"
    while candidate in used:
        number += 1
        candidate = f"V{number}-GEN{generation}"
    return candidate


def build_strategy_lineage_record(
    parent: Any,
    generation: int,
    single_change: Any,
    cycle: dict[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    cycle = dict(cycle or {})
    parent_id = str(parent or "V1")
    strategy_id = str(
        fields.pop("strategy_id", None)
        or cycle.get("strategy_id")
        or allocate_strategy_id(parent_id, generation)
    )
    if not immutable_baseline_guard(strategy_id):
        raise ValueError("IMMUTABLE_BASELINE_MUTATION_FORBIDDEN")
    mutation = validate_single_mutation(single_change)
    if not mutation.get("ok"):
        raise ValueError(str(mutation.get("reason")))
    record = {
        "schema": "tae.self_improve.strategy_lineage.v1",
        "lineage_event_id": fields.pop(
            "lineage_event_id",
            "LIN-" + _hash([strategy_id, parent_id, generation, single_change, _now()])[:16].upper(),
        ),
        "strategy_id": strategy_id,
        "strategy_version": strategy_id,
        "parent_strategy_id": parent_id,
        "generation": int(generation),
        "single_change": mutation["single_change"],
        "mutation_family": mutation["family"],
        "mutation_dimension": mutation["dimension"],
        "learning_cycle_id": cycle.get("learning_cycle_id"),
        "hypothesis_id": cycle.get("hypothesis_id"),
        "experiment_id": cycle.get("experiment_id"),
        "economic_experiment_uid": cycle.get("economic_experiment_uid"),
        "parent_hash": fields.pop("parent_hash", cycle.get("parent_hash")),
        "config_hash": fields.pop("config_hash", cycle.get("config_hash")),
        "strategy_hash": fields.pop(
            "strategy_hash",
            _hash({"parent": parent_id, "generation": generation, "change": single_change}),
        ),
        "evidence_hash": fields.pop("evidence_hash", cycle.get("evidence_hash")),
        "status": fields.pop("status", cycle.get("status") or "PROPOSED"),
        "execution_mode": "PAPER",
        "live_allowed": False,
        "created_at": fields.pop("created_at", _now()),
        **fields,
    }
    return record


def append_lineage(record: dict[str, Any], path: Path | None = None) -> Path:
    target = path or LINEAGE_PATH
    sid = str(record.get("strategy_id") or "")
    if not sid or not immutable_baseline_guard(sid):
        raise ValueError("IMMUTABLE_BASELINE_MUTATION_FORBIDDEN")
    if record.get("live_allowed") is True or str(record.get("execution_mode") or "PAPER").upper() != "PAPER":
        raise ValueError("LIVE_OR_BROKER_MUTATION_FORBIDDEN")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, sort_keys=True, default=str) + "\n").encode()
    fd = os.open(target, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    return target


def current_paper_champion() -> dict[str, Any] | None:
    latest: dict[str, dict[str, Any]] = {}
    for row in load_lineage():
        sid = str(row.get("strategy_id") or "")
        if sid:
            latest[sid] = row
    champions = [
        row
        for row in latest.values()
        if row.get("status") == "PAPER_CHAMPION_ACTIVE"
        and row.get("live_allowed") is not True
    ]
    return champions[-1] if champions else None


def get_evolution_control_strategy() -> str:
    champion = current_paper_champion()
    return str((champion or {}).get("strategy_id") or "V1")


def _failed_integrity(value: dict[str, Any]) -> str | None:
    if value.get("live_allowed") is True or str(value.get("execution_mode") or "PAPER").upper() != "PAPER":
        return "LIVE_OR_BROKER_PATH_DETECTED"
    if value.get("contamination") not in (None, False, "", "NONE", "PASS"):
        return "CONTAMINATION_DETECTED"
    groups = {
        "ACCOUNTING_INTEGRITY_FAILED": (
            "accounting_integrity",
            "accounting_status",
            "reconciliation_pass",
        ),
        "DATA_INTEGRITY_FAILED": ("data_integrity", "data_integrity_status"),
        "EXECUTION_INTEGRITY_FAILED": ("execution_integrity", "execution_status"),
    }
    for reason, keys in groups.items():
        for key in keys:
            if key not in value:
                continue
            item = value.get(key)
            if item is False or str(item).upper() in {
                "FAIL",
                "FAILED",
                "INVALID",
                "REJECTED",
            }:
                return reason
            if isinstance(item, dict) and (
                item.get("ok") is False
                or item.get("pass") is False
                or str(item.get("status") or "").upper()
                in {"FAIL", "FAILED", "INVALID", "REJECTED"}
            ):
                return reason
    return None


def evaluate_autonomous_champion(
    champion: dict[str, Any],
    *,
    control_pnl: float | None = None,
) -> dict[str, Any]:
    """Reuse integrity, expectancy, PnL, and the existing 10% drawdown gate."""
    immediate = _failed_integrity(champion)
    if immediate:
        return {"ok": False, "degraded": True, "reason": immediate}
    metrics = champion.get("economic_attribution") or champion.get("metrics") or champion
    expectancy = metrics.get(
        "expectancy_per_closed_cycle", champion.get("expectancy")
    )
    if expectancy is not None and float(expectancy) < 0:
        return {"ok": False, "degraded": True, "reason": "NEGATIVE_EXPECTANCY"}
    pnl = float(
        champion.get("total_pnl")
        or champion.get("realized_pnl")
        or metrics.get("net_realized_pnl")
        or 0
    )
    if control_pnl is not None and pnl < float(control_pnl):
        return {"ok": False, "degraded": True, "reason": "PNL_UNDER_CONTROL"}
    starting = float(champion.get("starting_cash") or champion.get("starting_capital") or 0)
    drawdown = float(champion.get("drawdown") or 0)
    max_drawdown_pct = float(champion.get("max_drawdown_pct") or 0.10)
    if starting > 0 and drawdown / starting < -max_drawdown_pct:
        return {"ok": False, "degraded": True, "reason": "DRAWDOWN_GATE_FAILED"}
    return {"ok": True, "degraded": False, "reason": "PAPER_CHAMPION_HEALTHY"}


def rollback_autonomous_champion(
    reason: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deactivate a degraded autonomous champion and restore prior PAPER state."""
    from tae_strategy_lab_promotion import (
        load_champion_archive,
        load_promotion_state,
        save_promotion_state,
    )

    state = load_promotion_state(create_if_missing=True)
    current = str(
        state.get("autonomous_paper_champion_id")
        or state.get("champion_strategy_id")
        or ""
    )
    if not current or current in IMMUTABLE_BASELINES:
        return {"ok": False, "reason": "NO_AUTONOMOUS_CHAMPION"}
    prior = next(
        (
            str(row.get("strategy_id"))
            for row in reversed(load_lineage())
            if row.get("strategy_id") != current
            and row.get("status")
            in {"PAPER_CHAMPION_ACTIVE", "PAPER_CHAMPION_ARCHIVED"}
        ),
        "",
    )
    if not prior:
        archive = load_champion_archive()
        prior = next(
            (
                str(row.get("strategy_id"))
                for row in reversed(archive.get("entries") or [])
                if row.get("strategy_id") != current
            ),
            "V1",
        )
    strategies = dict(state.get("strategies") or {})
    current_row = dict(strategies.get(current) or {})
    current_row.update(
        {
            "lifecycle_state": "REJECTED",
            "paper_champion_status": "AUTO_ROLLED_BACK",
            "rollback_reason": str(reason),
            "rolled_back_at": _now(),
            "live_allowed": False,
        }
    )
    prior_row = dict(strategies.get(prior) or {"strategy_id": prior})
    prior_row.update(
        {
            "lifecycle_state": "CHAMPION",
            "paper_champion_status": "PAPER_CHAMPION_ACTIVE",
            "reactivated_at": _now(),
            "execution_mode": "PAPER",
            "live_allowed": False,
        }
    )
    strategies[current] = current_row
    strategies[prior] = prior_row
    state["strategies"] = strategies
    state["champion_strategy_id"] = prior
    state["autonomous_paper_champion_id"] = (
        prior if prior not in IMMUTABLE_BASELINES else None
    )
    state["last_autonomous_rollback"] = {
        "from": current,
        "to": prior,
        "reason": str(reason),
        "at": _now(),
    }
    save_promotion_state(state)
    append_lineage(
        {
            **current_row,
            "strategy_id": current,
            "lineage_event_id": "LIN-ROLLBACK-" + _hash([current, prior, reason, _now()])[:12].upper(),
            "status": "AUTO_ROLLED_BACK",
            "rollback_to_strategy_id": prior,
            "evidence": evidence or {},
            "execution_mode": "PAPER",
            "live_allowed": False,
        }
    )
    if prior not in IMMUTABLE_BASELINES:
        append_lineage(
            {
                **prior_row,
                "strategy_id": prior,
                "lineage_event_id": "LIN-REACTIVATE-"
                + _hash([prior, current, reason, _now()])[:12].upper(),
                "status": "PAPER_CHAMPION_ACTIVE",
                "reactivated_from_strategy_id": current,
                "execution_mode": "PAPER",
                "live_allowed": False,
            }
        )
    try:
        from tae_self_improve_lifecycle import append_cycle, load_cycles

        cycle = next(
            (
                row
                for row in reversed(load_cycles(limit=10000))
                if row.get("strategy_id") == current
            ),
            None,
        )
        if cycle:
            append_cycle(
                {
                    **cycle,
                    "status": "AUTO_ROLLED_BACK",
                    "rollback_reason": str(reason),
                    "rollback_to_strategy_id": prior,
                    "rollback_evidence": evidence or {},
                    "updated_at": _now(),
                }
            )
    except Exception:
        pass
    return {
        "ok": True,
        "status": "AUTO_ROLLED_BACK",
        "deactivated_strategy_id": current,
        "reactivated_strategy_id": prior,
        "reason": str(reason),
        "evidence_preserved": True,
        "live_allowed": False,
    }


def evolve_autonomous_paper() -> dict[str, Any]:
    """One bounded post-close evolution pass over existing cycles and arms."""
    if not is_autonomy_enabled():
        return {
            "ok": True,
            "status": "AUTONOMY_PAUSED",
            "reason": "AUTONOMOUS_PAPER_EVOLUTION_DISABLED",
        }
    from tae_self_improve_lifecycle import load_cycles, monitor_and_gate

    cycles = load_cycles(limit=10000)
    active = [
        row
        for row in cycles
        if row.get("status") in {"PAPER_RUNNING", "PAPER_CHAMPION_ACTIVE"}
    ]
    if len([row for row in active if row.get("status") == "PAPER_RUNNING"]) > MAX_ACTIVE_CHALLENGERS:
        return {"ok": False, "status": "BLOCKED", "reason": "MAX_ACTIVE_CHALLENGERS"}
    today = datetime.now(timezone.utc).date().isoformat()
    promotions_today = sum(
        1
        for row in load_lineage()
        if row.get("status") == "PAPER_CHAMPION_ACTIVE"
        and str(row.get("promoted_at") or row.get("created_at") or "").startswith(today)
    )
    results: list[dict[str, Any]] = []
    for cycle in active:
        if (
            cycle.get("status") == "PAPER_RUNNING"
            and promotions_today >= MAX_AUTONOMOUS_PROMOTIONS_PER_DAY
        ):
            results.append(
                {
                    "ok": True,
                    "status": "KEEP_RUNNING",
                    "cycle_id": cycle.get("learning_cycle_id"),
                    "reason": "MAX_AUTONOMOUS_PROMOTIONS_PER_DAY",
                }
            )
            continue
        result = monitor_and_gate(str(cycle.get("learning_cycle_id")))
        results.append(result)
        if result.get("status") == "AUTO_PAPER_PROMOTED":
            promotions_today += 1
    return {
        "ok": all(row.get("ok", False) for row in results) if results else True,
        "status": "EVOLUTION_PASS_COMPLETE",
        "control_strategy": get_evolution_control_strategy(),
        "checked": len(results),
        "results": results,
        "promotions_today": promotions_today,
        "max_promotions_per_day": MAX_AUTONOMOUS_PROMOTIONS_PER_DAY,
        "max_new_hypotheses_per_post_close": MAX_NEW_HYPOTHESES_PER_POST_CLOSE,
        "next_cycle_prepared": promotions_today < MAX_AUTONOMOUS_PROMOTIONS_PER_DAY,
        "live_allowed": False,
    }


def _autonomy_block(state: dict[str, Any]) -> dict[str, Any]:
    block = state.get("autonomous_paper_evolution")
    return block if isinstance(block, dict) else {}


def is_autonomy_enabled() -> bool:
    try:
        state = json.loads(PROMOTION_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    block = _autonomy_block(state if isinstance(state, dict) else {})
    return (
        block.get("enabled") is True
        and block.get("live_allowed") is False
        and block.get("domain") == "AUTONOMOUS_PAPER_EVOLUTION"
    )


def _set_autonomy(enabled: bool, reason: str | None = None) -> dict[str, Any]:
    from tae_strategy_lab_promotion import load_promotion_state, save_promotion_state

    state = load_promotion_state(create_if_missing=True)
    state["autonomous_paper_evolution"] = {
        "enabled": bool(enabled),
        "domain": "AUTONOMOUS_PAPER_EVOLUTION",
        "live_allowed": False,
        "paused_at": None if enabled else _now(),
        "pause_reason": None if enabled else str(reason or "OPERATOR_PAUSE"),
    }
    save_promotion_state(state)
    return dict(state["autonomous_paper_evolution"])


def pause_autonomy(reason: str = "OPERATOR_PAUSE") -> dict[str, Any]:
    return _set_autonomy(False, reason)


def resume_autonomy() -> dict[str, Any]:
    return _set_autonomy(True)


__all__ = [
    "EXPERIMENT_COOLDOWN_HOURS",
    "IMMUTABLE_BASELINES",
    "LINEAGE_PATH",
    "MAX_ACTIVE_CHALLENGERS",
    "MAX_AUTONOMOUS_PROMOTIONS_PER_DAY",
    "MAX_NEW_HYPOTHESES_PER_POST_CLOSE",
    "MUTATION_ALLOWLIST",
    "allocate_strategy_id",
    "append_lineage",
    "build_strategy_lineage_record",
    "current_paper_champion",
    "evaluate_autonomous_champion",
    "evolve_autonomous_paper",
    "get_evolution_control_strategy",
    "immutable_baseline_guard",
    "is_autonomy_enabled",
    "load_lineage",
    "pause_autonomy",
    "resume_autonomy",
    "rollback_autonomous_champion",
    "validate_single_mutation",
]
