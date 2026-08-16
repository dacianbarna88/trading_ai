#!/usr/bin/env python3
"""PAPER-only glue between self-improvement and existing Strategy Lab/runtime."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
STRATEGY_LAB_ROOT = PROJECT_ROOT / "runtime_outputs" / "strategy_lab"
EXPERIMENTAL_REGISTRY_PATH = STRATEGY_LAB_ROOT / "experimental_challengers.json"
EXPERIMENTAL_REGISTRATION_AUDIT_PATH = (
    STRATEGY_LAB_ROOT / "experimental_registration_audit.jsonl"
)
EXPERIMENTAL_ARMS_PATH = (
    PROJECT_ROOT
    / "runtime_outputs"
    / "learning_to_profit"
    / "self_improve"
    / "experimental_arms.json"
)
PARALLEL_PAPER_ROOT = PROJECT_ROOT / "runtime_outputs" / "parallel_paper"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_id(value: Any) -> str:
    text = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(value or ""))
    return text.strip("-_") or "UNKNOWN"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _audit(event: str, payload: dict[str, Any]) -> None:
    EXPERIMENTAL_REGISTRATION_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, "payload": payload, "live_allowed": False}
    with EXPERIMENTAL_REGISTRATION_AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _integrity_ok(cycle: dict[str, Any]) -> bool:
    for key in ("accounting_integrity", "accounting_status", "data_integrity", "data_integrity_status"):
        if key not in cycle:
            continue
        value = cycle.get(key)
        if value is False or str(value).upper() in {"FAIL", "FAILED", "INVALID", "REJECTED"}:
            return False
        if isinstance(value, dict) and (
            value.get("ok") is False
            or value.get("pass") is False
            or str(value.get("status") or "").upper() in {"FAIL", "FAILED", "INVALID", "REJECTED"}
        ):
            return False
    return True


def _registration_row(cycle: dict[str, Any]) -> dict[str, Any]:
    cycle_id = str(cycle.get("learning_cycle_id") or "")
    strategy_id = str(cycle.get("strategy_id") or cycle.get("challenger_strategy") or "")
    arm_id = str(cycle.get("arm_id") or f"exp_{_safe_id(strategy_id).lower()}")
    parent = str(cycle.get("parent_strategy") or cycle.get("control_strategy") or "")
    hypothesis_id = str(cycle.get("hypothesis_id") or "")
    experiment_id = str(cycle.get("experiment_id") or "")
    return {
        "strategy_id": strategy_id,
        "strategy_version": cycle.get("strategy_version") or strategy_id,
        "arm_id": arm_id,
        "runtime_arm": arm_id,
        "book_relpath": f"runtime_outputs/parallel_paper/{arm_id}",
        "learning_cycle_id": cycle_id,
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "economic_experiment_uid": cycle.get("economic_experiment_uid"),
        "parent_strategy": parent,
        "parent_strategy_id": cycle.get("parent_strategy_id") or parent,
        "generation": cycle.get("generation"),
        "lineage": cycle.get("lineage"),
        "single_change": (cycle.get("proposed_solution") or {}).get("single_change"),
        "config_overlay": cycle.get("config_overlay") or {},
        "replay_status": "REPLAY_SUPPORTED",
        "strategy_class": "EXPERIMENTAL_CHALLENGER",
        "status": "CANDIDATE",
        "lifecycle_state": "CANDIDATE",
        "mode": "PAPER",
        "execution_mode": "PAPER",
        "experimental_only": True,
        "live_allowed": False,
        "enabled_in_parallel_paper": False,
        "registered_at": _now(),
    }


def register_experimental_challenger(
    cycle: dict, *, force_supported: bool = False
) -> dict[str, Any]:
    """Register a replay-supported isolated challenger in Strategy Lab's runtime SSOT."""
    if not isinstance(cycle, dict):
        return {"ok": False, "status": "REGISTRATION_REJECTED", "reason": "INVALID_CYCLE"}
    replay_status = str((cycle.get("replay_summary") or {}).get("status") or cycle.get("status") or "")
    if replay_status == "REPLAY_REJECTED":
        result = {"ok": False, "status": "REGISTRATION_REJECTED", "reason": "REPLAY_REJECTED"}
        _audit("REGISTRATION_REJECTED", result)
        return result
    if replay_status != "REPLAY_SUPPORTED" and not force_supported:
        result = {"ok": False, "status": "REGISTRATION_REJECTED", "reason": "REPLAY_NOT_SUPPORTED"}
        _audit("REGISTRATION_REJECTED", result)
        return result
    if not _integrity_ok(cycle):
        result = {"ok": False, "status": "REGISTRATION_REJECTED", "reason": "INTEGRITY_GATE_FAILED"}
        _audit("REGISTRATION_REJECTED", result)
        return result

    row = _registration_row(cycle)
    missing = [
        key
        for key in ("strategy_id", "arm_id", "learning_cycle_id", "hypothesis_id", "experiment_id", "parent_strategy")
        if not row.get(key)
    ]
    reason = None
    if missing:
        reason = "MISSING_REQUIRED:" + ",".join(missing)
    elif str(row["execution_mode"]).upper() != "PAPER":
        reason = "NON_PAPER"
    elif cycle.get("live_allowed") is True or cycle.get("live_enabled") is True:
        reason = "LIVE_FORBIDDEN"
    elif row["arm_id"].lower() in {"v1", "v2"}:
        reason = "SHARED_ARM_FORBIDDEN"
    elif row["book_relpath"] in {
        "runtime_outputs/parallel_paper/v1",
        "runtime_outputs/parallel_paper/v2",
    }:
        reason = "SHARED_BOOK_FORBIDDEN"
    if reason:
        result = {"ok": False, "status": "REGISTRATION_REJECTED", "reason": reason}
        _audit("REGISTRATION_REJECTED", result)
        return result

    registry = _read_json(EXPERIMENTAL_REGISTRY_PATH) or {
        "schema": "tae.strategy_lab.experimental_challengers.v1",
        "strategies": [],
    }
    strategies = [item for item in registry.get("strategies") or [] if isinstance(item, dict)]
    for existing in strategies:
        same_cycle = existing.get("learning_cycle_id") == row["learning_cycle_id"]
        if existing.get("strategy_id") == row["strategy_id"] or existing.get("arm_id") == row["arm_id"]:
            if same_cycle and existing.get("strategy_id") == row["strategy_id"] and existing.get("arm_id") == row["arm_id"]:
                return {"ok": True, "status": "REGISTERED_EXPERIMENTAL", "idempotent": True, "strategy": existing}
            result = {
                "ok": False,
                "status": "REGISTRATION_REJECTED",
                "reason": "DUPLICATE_STRATEGY_OR_ARM",
            }
            _audit("REGISTRATION_REJECTED", result)
            return result
    registry["strategies"] = [*strategies, row]
    registry["updated_at"] = _now()
    registry["live_allowed"] = False
    _atomic_write_json(EXPERIMENTAL_REGISTRY_PATH, registry)
    _audit(
        "REGISTERED_EXPERIMENTAL",
        {
            "learning_cycle_id": row["learning_cycle_id"],
            "strategy_id": row["strategy_id"],
            "arm_id": row["arm_id"],
        },
    )
    return {"ok": True, "status": "REGISTERED_EXPERIMENTAL", "idempotent": False, "strategy": row}


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _declared_changes(cycle: dict[str, Any]) -> list[Any]:
    overlay = cycle.get("config_overlay") or {}
    changes = overlay.get("changes", cycle.get("changes"))
    if isinstance(changes, list):
        return [item for item in changes if item not in (None, "")]
    single = (
        overlay.get("single_change")
        or cycle.get("single_change")
        or (cycle.get("proposed_solution") or {}).get("single_change")
    )
    if isinstance(single, (list, tuple, set)):
        return [item for item in single if item not in (None, "")]
    return [single] if single not in (None, "") else []


def enable_experimental_arm(cycle_id: str) -> dict[str, Any]:
    """Enable only an already registered, replay-supported experimental arm."""
    registry = _read_json(EXPERIMENTAL_REGISTRY_PATH)
    row = next(
        (
            item
            for item in registry.get("strategies") or []
            if isinstance(item, dict) and item.get("learning_cycle_id") == cycle_id
        ),
        None,
    )
    if not row or row.get("replay_status") != "REPLAY_SUPPORTED":
        return {"ok": False, "status": "ENABLE_REJECTED", "reason": "NOT_REGISTERED_OR_REPLAY_SUPPORTED"}
    arm_id = str(row.get("arm_id") or "")
    book = str(row.get("book_relpath") or "")
    if not arm_id.startswith("exp_") or not book.startswith("runtime_outputs/parallel_paper/exp_"):
        return {"ok": False, "status": "ENABLE_REJECTED", "reason": "BOOK_ISOLATION_FAILED"}
    sidecar = _read_json(EXPERIMENTAL_ARMS_PATH) or {
        "schema": "tae.self_improve.experimental_arms.v1",
        "arms": [],
    }
    arms = [item for item in sidecar.get("arms") or [] if isinstance(item, dict)]
    payload = {
        **row,
        "enabled": True,
        "policy_binding": "experimental",
        "execution_mode": "PAPER",
        "live_allowed": False,
        "enabled_at": _now(),
    }
    replaced = False
    for index, existing in enumerate(arms):
        if existing.get("learning_cycle_id") == cycle_id:
            arms[index] = {**existing, **payload}
            replaced = True
            break
    if not replaced:
        arms.append(payload)
    sidecar["arms"] = arms
    sidecar["updated_at"] = _now()
    sidecar["live_allowed"] = False
    _atomic_write_json(EXPERIMENTAL_ARMS_PATH, sidecar)
    root = _book_root(payload)
    if not (root / "account.json").exists():
        starting = float(payload.get("starting_capital") or 30000.0)
        _atomic_write_json(
            root / "account.json",
            {
                "starting_cash": starting,
                "cash": starting,
                "market_value": 0.0,
                "account_value": starting,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "fees": 0.0,
                "fills": 0,
                "reconciliation_pass": True,
                "mode": "ISOLATED_EXPERIMENTAL_PAPER",
                "live_allowed": False,
            },
        )
    if not (root / "portfolio.json").exists():
        _atomic_write_json(
            root / "portfolio.json",
            {"positions": {}, "mode": "PAPER_ONLY", "live_allowed": False},
        )
    for name in ("decisions.jsonl", "executions.jsonl", "trades.jsonl"):
        path = root / "journals" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
    return {
        "ok": True,
        "status": "EXPERIMENTAL_ARM_ENABLED",
        "arm": payload,
        "book_path": str(root),
    }


def _book_root(arm: dict[str, Any]) -> Path:
    arm_id = str(arm.get("arm_id") or "")
    if not arm_id.startswith("exp_"):
        raise ValueError("EXPERIMENTAL_ARM_PATH_FORBIDDEN")
    root = PARALLEL_PAPER_ROOT / arm_id
    if root.parent != PARALLEL_PAPER_ROOT:
        raise ValueError("EXPERIMENTAL_ARM_PATH_FORBIDDEN")
    return root


def _mark(mark: Any) -> tuple[bool, float, str]:
    if not isinstance(mark, dict):
        return False, 0.0, "SKIPPED_NO_MARK_PRICE"
    try:
        price = float(mark.get("mark_price") or mark.get("price") or 0)
    except (TypeError, ValueError):
        price = 0.0
    freshness = str(mark.get("mark_freshness") or "FRESH").upper()
    if price <= 0 or freshness in {"STALE", "INVALID", "UNAVAILABLE", "MARK_STALE"}:
        return False, 0.0, "SKIPPED_NO_MARK_PRICE"
    return True, price, "OK"


def _fees(notional: float, cfg: dict[str, Any]) -> float:
    bps = sum(
        max(0.0, float(cfg.get(key) or 0))
        for key in ("PAPER_SLIPPAGE_BPS", "PAPER_SPREAD_BPS", "PAPER_COMMISSION_BPS")
    )
    return round(abs(notional) * bps / 10000.0 + max(0.0, float(cfg.get("PAPER_COMMISSION_USD") or 0)), 6)


def _identity(arm: dict[str, Any], *, snapshot_id: str, decision_id: str) -> dict[str, Any]:
    return {
        key: arm.get(key)
        for key in (
            "learning_cycle_id",
            "hypothesis_id",
            "experiment_id",
            "strategy_id",
            "arm_id",
            "parent_strategy",
            "single_change",
            "economic_experiment_uid",
        )
    } | {"decision_id": decision_id, "source_snapshot_id": snapshot_id}


def run_experimental_arm_once(
    arm: dict[str, Any],
    *,
    snapshot_id: str,
    ts: str,
    marks: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
    market_open: bool | None = None,
) -> dict[str, Any]:
    """Run one deterministic fill pass against a frozen shared snapshot."""
    if len(_declared_changes(arm)) != 1:
        return {"ok": False, "status": "MULTI_CHANGE_REJECTED", "arm_id": arm.get("arm_id")}
    root = _book_root(arm)
    journals = root / "journals"
    account_path = root / "account.json"
    portfolio_path = root / "portfolio.json"
    account = _read_json(account_path) or {
        "starting_cash": float(arm.get("starting_capital") or 30000.0),
        "cash": float(arm.get("starting_capital") or 30000.0),
        "realized_pnl": 0.0,
        "fees": 0.0,
        "fills": 0,
        "peak_account_value": float(arm.get("starting_capital") or 30000.0),
    }
    portfolio = _read_json(portfolio_path) or {"positions": {}, "mode": "PAPER_ONLY"}
    positions = portfolio.get("positions")
    if not isinstance(positions, dict):
        positions = {}
        portfolio["positions"] = positions
    ticker = next(iter(sorted(set(marks) | set(positions))), "")
    mark_ok, price, mark_reason = _mark(marks.get(ticker))
    if market_open is None and ticker:
        try:
            from markets.market_hours import is_ticker_market_open

            is_open = bool(is_ticker_market_open(ticker))
        except Exception:
            is_open = False
    else:
        is_open = bool(market_open)
    decision_id = f"EXP-{snapshot_id}-{arm.get('arm_id')}-{ticker or 'NONE'}"
    identity = _identity(arm, snapshot_id=snapshot_id, decision_id=decision_id)
    action = "HOLD"
    reason = "ACTIVE_NOT_TRIGGERED"
    fill: dict[str, Any] | None = None
    position = positions.get(ticker) if ticker else None
    requested = str(
        (arm.get("config_overlay") or {}).get("experimental_action")
        or arm.get("experimental_action")
        or ""
    ).upper()

    if not mark_ok:
        reason = mark_reason
    elif not is_open:
        reason = "MARKET_CLOSED"
    elif position and requested == "SELL":
        qty = float(position.get("quantity") or position.get("shares") or 0)
        gross = round(qty * price, 6)
        fees = _fees(gross, cfg)
        basis = round(qty * float(position.get("avg_price") or 0), 6)
        realized = round(gross - fees - basis, 6)
        account["cash"] = round(float(account.get("cash") or 0) + gross - fees, 6)
        account["realized_pnl"] = round(float(account.get("realized_pnl") or 0) + realized, 6)
        positions.pop(ticker, None)
        action, reason = "SELL", "EXPERIMENTAL_SINGLE_CHANGE_EXIT"
        fill = {"side": "SELL", "ticker": ticker, "quantity": qty, "price": price, "fees": fees, "realized_pnl": realized}
    elif not position and not positions:
        reserve = float(arm.get("min_cash_reserve") or 500.0)
        cash = float(account.get("cash") or 0)
        notional = min(float(arm.get("max_entry_notional") or 1000.0), max(0.0, cash - reserve))
        qty = int(notional / price)
        gross = round(qty * price, 6)
        fees = _fees(gross, cfg) if qty > 0 else 0.0
        if qty > 0 and cash - gross - fees >= reserve:
            account["cash"] = round(cash - gross - fees, 6)
            positions[ticker] = {"quantity": qty, "avg_price": price, "current_price": price}
            action, reason = "BUY", "PARENT_LIKE_ENTRY"
            fill = {"side": "BUY", "ticker": ticker, "quantity": qty, "price": price, "fees": fees}
        else:
            reason = "INSUFFICIENT_CASH"
    elif position:
        position["current_price"] = price
        reason = "STOP_POLICY_REVIEW_HOLD" if "STOP" in str(arm.get("single_change") or "").upper() else "ACTIVE_NOT_TRIGGERED"

    if fill:
        execution_id = f"{decision_id}-EXEC"
        fill.update(identity)
        fill["execution_id"] = execution_id
        fill["ts"] = ts
        account["fills"] = int(account.get("fills") or 0) + 1
        account["fees"] = round(float(account.get("fees") or 0) + float(fill["fees"]), 6)
        _append_jsonl(journals / "executions.jsonl", fill)
        _append_jsonl(journals / "trades.jsonl", fill)
    decision = {**identity, "ts": ts, "ticker": ticker, "action": action, "reason": reason}
    _append_jsonl(journals / "decisions.jsonl", decision)

    market_value = round(
        sum(float(pos.get("quantity") or 0) * float(pos.get("current_price") or pos.get("avg_price") or 0) for pos in positions.values()),
        6,
    )
    basis_value = round(
        sum(float(pos.get("quantity") or 0) * float(pos.get("avg_price") or 0) for pos in positions.values()),
        6,
    )
    unrealized = round(market_value - basis_value, 6)
    account_value = round(float(account.get("cash") or 0) + market_value, 6)
    account.update(
        {
            "market_value": market_value,
            "account_value": account_value,
            "unrealized_pnl": unrealized,
            "total_pnl": round(float(account.get("realized_pnl") or 0) + unrealized, 6),
            "peak_account_value": max(float(account.get("peak_account_value") or account_value), account_value),
            "drawdown": round(account_value - max(float(account.get("peak_account_value") or account_value), account_value), 6),
            "reconciliation_pass": abs(float(account.get("cash") or 0) + market_value - account_value) < 1e-6,
            "mode": "ISOLATED_EXPERIMENTAL_PAPER",
            "live_allowed": False,
            "source_snapshot_id": snapshot_id,
            "updated_at": ts,
        }
    )
    portfolio.update({"positions": positions, "cash": account["cash"], "account_value": account_value, "source_snapshot_id": snapshot_id})
    _atomic_write_json(portfolio_path, portfolio)
    _atomic_write_json(account_path, account)
    _atomic_write_json(root / "accounting_snapshot.json", {"cash": account["cash"], "market_value": market_value, "account_value": account_value, "reconciliation_pass": account["reconciliation_pass"], "ts": ts})
    return {"ok": True, "status": action if fill else reason, "fill_count": 1 if fill else 0, "decision": decision, "account": account, "book_path": str(root)}


def run_experimental_arms_on_snapshot(
    snapshot_id: str,
    ts: str,
    marks: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
    *,
    market_open: bool | None = None,
) -> dict[str, Any]:
    sidecar = _read_json(EXPERIMENTAL_ARMS_PATH)
    results = []
    for arm in sidecar.get("arms") or []:
        if isinstance(arm, dict) and arm.get("enabled") is True:
            try:
                results.append(
                    run_experimental_arm_once(
                        arm,
                        snapshot_id=snapshot_id,
                        ts=ts,
                        marks=marks,
                        cfg=cfg,
                        market_open=market_open,
                    )
                )
            except Exception as exc:
                results.append({"ok": False, "arm_id": arm.get("arm_id"), "status": "FAIL_ISOLATED", "error": str(exc)})
    return {"ok": all(row.get("ok") for row in results), "arms_run": len(results), "results": results}


def execute_experimental_paper_cycle(
    cycle_id: str,
    *,
    marks: dict[str, dict[str, Any]],
    market_open: bool | None = None,
) -> dict[str, Any]:
    """Sandbox/test entry point using injected marks; never invokes a broker."""
    from tae_parallel_paper_config import load_parallel_paper_config

    ts = _now()
    digest = json.dumps(marks, sort_keys=True, default=str).encode()
    import hashlib

    snapshot_id = f"EXP-SNAP-{hashlib.sha256(digest).hexdigest()[:12].upper()}"
    sidecar = _read_json(EXPERIMENTAL_ARMS_PATH)
    arms = [
        arm
        for arm in sidecar.get("arms") or []
        if isinstance(arm, dict)
        and arm.get("enabled") is True
        and arm.get("learning_cycle_id") == cycle_id
    ]
    if not arms:
        return {"ok": False, "status": "ARM_NOT_ENABLED", "cycle_id": cycle_id}
    results = [
        run_experimental_arm_once(
            arm,
            snapshot_id=snapshot_id,
            ts=ts,
            marks=marks,
            cfg=load_parallel_paper_config(),
            market_open=market_open,
        )
        for arm in arms
    ]
    return {
        "ok": all(row.get("ok") for row in results),
        "cycle_id": cycle_id,
        "snapshot_id": snapshot_id,
        "fill_count": sum(int(row.get("fill_count") or 0) for row in results),
        "results": results,
    }


def disable_experimental_arm(cycle_id: str, reason: str) -> dict[str, Any]:
    sidecar = _read_json(EXPERIMENTAL_ARMS_PATH)
    found = False
    for arm in sidecar.get("arms") or []:
        if isinstance(arm, dict) and arm.get("learning_cycle_id") == cycle_id:
            arm["enabled"] = False
            arm["disabled_reason"] = str(reason)
            arm["disabled_at"] = _now()
            found = True
    if found:
        sidecar["updated_at"] = _now()
        _atomic_write_json(EXPERIMENTAL_ARMS_PATH, sidecar)
    return {
        "ok": found,
        "status": "EXPERIMENTAL_ARM_DISABLED" if found else "ARM_NOT_FOUND",
        "cycle_id": cycle_id,
        "reason": str(reason),
    }


def monitor_active_challengers() -> dict[str, Any]:
    """Apply accounting and drawdown gates to enabled experimental PAPER arms."""
    sidecar = _read_json(EXPERIMENTAL_ARMS_PATH)
    results: list[dict[str, Any]] = []

    def rollback_if_champion(arm: dict[str, Any], reason: str, account: dict[str, Any]) -> None:
        try:
            from tae_self_improve_evolution import (
                current_paper_champion,
                rollback_autonomous_champion,
            )

            champion = current_paper_champion() or {}
            if champion.get("strategy_id") == arm.get("strategy_id"):
                rollback_autonomous_champion(
                    reason,
                    evidence={
                        "learning_cycle_id": arm.get("learning_cycle_id"),
                        "account": account,
                    },
                )
        except Exception:
            pass

    for arm in sidecar.get("arms") or []:
        if not isinstance(arm, dict) or arm.get("enabled") is not True:
            continue
        cycle_id = str(arm.get("learning_cycle_id") or "")
        try:
            account = _read_json(_book_root(arm) / "account.json")
            fills = int(account.get("fills") or 0)
            starting = float(account.get("starting_cash") or arm.get("starting_capital") or 30000)
            drawdown = float(account.get("drawdown") or 0)
            max_drawdown_pct = float(arm.get("max_drawdown_pct") or 0.10)
            accounting_ok = account.get("reconciliation_pass") is True and abs(
                float(account.get("cash") or 0)
                + float(account.get("market_value") or 0)
                - float(account.get("account_value") or 0)
            ) < 1e-6
            if not accounting_ok:
                disable_experimental_arm(cycle_id, "ACCOUNTING_INTEGRITY_FAILED")
                rollback_if_champion(arm, "ACCOUNTING_INTEGRITY_FAILED", account)
                results.append(
                    {
                        "cycle_id": cycle_id,
                        "status": "ROLLBACK",
                        "reason": "ACCOUNTING_INTEGRITY_FAILED",
                        "accounting_pass": False,
                    }
                )
            elif starting > 0 and drawdown / starting < -max_drawdown_pct:
                disable_experimental_arm(cycle_id, "DRAWDOWN_GATE_FAILED")
                rollback_if_champion(arm, "DRAWDOWN_GATE_FAILED", account)
                results.append(
                    {
                        "cycle_id": cycle_id,
                        "status": "ROLLBACK",
                        "reason": "DRAWDOWN_GATE_FAILED",
                        "accounting_pass": True,
                    }
                )
            else:
                from tae_self_improve_wiring import build_remaining_evidence

                remaining_evidence = build_remaining_evidence(
                    {
                        "events": fills,
                        "closed_cycles": (
                            account.get("economic_attribution") or {}
                        ).get("closed_cycles", account.get("closed_cycles", 0)),
                        "observation_days": (
                            account.get("economic_attribution") or {}
                        ).get("observation_days", account.get("observation_days", 0)),
                        "matured_outcomes": (
                            account.get("economic_attribution") or {}
                        ).get("closed_cycles", account.get("closed_cycles", 0)),
                    },
                    arm.get("validation_requirements_parsed"),
                )
                results.append(
                    {
                        "cycle_id": cycle_id,
                        "status": "KEEP_RUNNING" if fills else "ACTIVE_NOT_TRIGGERED",
                        "reason": "FILL_EVIDENCE_PRESENT" if fills else "NO_FILLS_YET",
                        "fills": fills,
                        "accounting_pass": True,
                        "drawdown": drawdown,
                        "remaining_evidence": remaining_evidence,
                    }
                )
        except Exception as exc:
            disable_experimental_arm(cycle_id, "MONITOR_INTEGRITY_ERROR")
            results.append(
                {
                    "cycle_id": cycle_id,
                    "status": "ROLLBACK",
                    "reason": "MONITOR_INTEGRITY_ERROR",
                    "error": str(exc),
                }
            )
    return {
        "ok": all(row.get("status") != "ROLLBACK" for row in results),
        "checked": len(results),
        "results": results,
        "live_allowed": False,
    }


__all__ = [
    "disable_experimental_arm",
    "enable_experimental_arm",
    "execute_experimental_paper_cycle",
    "monitor_active_challengers",
    "register_experimental_challenger",
    "run_experimental_arm_once",
    "run_experimental_arms_on_snapshot",
]
