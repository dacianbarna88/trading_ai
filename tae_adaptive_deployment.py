#!/usr/bin/env python3
"""
TAE Adaptive Deployment SSOT — CONNECT existing PAPER deployment pieces.

PAPER_ONLY | NO_BROKER | NO_LIVE | live_allowed=false always

Single canonical owner for Adaptive Deployment state, LKG, transitions, and
BUY-sizing challenger resolution. Reuses shadow formula evals, ROI lifecycle,
LIVE lock, atomic persistence, and existing configs — does not rewrite PDE/DPE/
risk/learning/economic engines.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_learning_persistence import atomic_write_json
from tae_paper_entry_risk_snapshot import FORMULA_V1_DEPLOYABLE_25PCT
from tae_paper_shadow_sizing import (
    EXPERIMENT_ID as SHADOW_EXPERIMENT_ID,
    FORMULA_CANON_PAPER_CONF,
    FORMULA_LIVE_EQUAL_SPLIT,
    FORMULA_VERSION as SHADOW_FORMULA_VERSION,
    PAPER_MIN_ORDER_USD,
    PAPER_MAX_POSITION_NOTIONAL,
    eval_canonical_paper_confidence,
    eval_live_equal_split,
    eval_v1_deployable,
    paper_confidence_notional,
    paper_deployable_notional,
)

SCHEMA = "tae.adaptive_deployment.v1"
EXPERIMENT_SCHEMA = "tae.adaptive_deployment.experiment.v1"
LKG_SCHEMA = "tae.adaptive_deployment.lkg.v1"
TRANSITION_SCHEMA = "tae.adaptive_deployment.transition.v1"

MODE = "PAPER_ONLY"
FAIL_CLOSED_POLICY = "FAIL_CLOSED_TO_NO_NEW_BUY"

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ROOT = PROJECT_ROOT / "runtime_outputs" / "adaptive_deployment"
STATE_NAME = "deployment_state.json"
LKG_NAME = "last_known_good.json"
HISTORY_NAME = "transitions.jsonl"
EXPERIMENT_NAME = "experiment_registry.json"

# States
ST_DRAFT = "DRAFT"
ST_PAPER_CHALLENGER = "PAPER_CHALLENGER"
ST_PAPER_ACTIVE = "PAPER_ACTIVE"
ST_PAUSED = "PAUSED"
ST_ROLLED_BACK = "ROLLED_BACK"
ST_REJECTED = "REJECTED"
ST_LIVE_ELIGIBLE = "LIVE_ELIGIBLE"  # informational only — never activates LIVE

SUPPORTED_STATES = frozenset(
    {
        ST_DRAFT,
        ST_PAPER_CHALLENGER,
        ST_PAPER_ACTIVE,
        ST_PAUSED,
        ST_ROLLED_BACK,
        ST_REJECTED,
        ST_LIVE_ELIGIBLE,
    }
)

ACTIVE_BUY_STATES = frozenset({ST_PAPER_CHALLENGER, ST_PAPER_ACTIVE})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ST_DRAFT: frozenset({ST_PAPER_CHALLENGER}),
    ST_PAPER_CHALLENGER: frozenset({ST_PAPER_ACTIVE, ST_PAUSED, ST_ROLLED_BACK, ST_REJECTED}),
    ST_PAPER_ACTIVE: frozenset({ST_PAUSED, ST_ROLLED_BACK}),
    ST_PAUSED: frozenset({ST_PAPER_CHALLENGER, ST_ROLLED_BACK, ST_REJECTED}),
    ST_ROLLED_BACK: frozenset({ST_DRAFT}),
    ST_REJECTED: frozenset(),
    ST_LIVE_ELIGIBLE: frozenset(),  # dead-end informational
}

# Reason codes
BLOCKED_HARD_RISK = "BLOCKED_HARD_RISK"
BLOCKED_RECONCILIATION = "BLOCKED_RECONCILIATION"
BLOCKED_DATA_QUALITY = "BLOCKED_DATA_QUALITY"
BLOCKED_NO_VALID_LKG = "BLOCKED_NO_VALID_LKG"
BLOCKED_LIVE_LOCK = "BLOCKED_LIVE_LOCK"
BLOCKED_INVALID_CONFIG = "BLOCKED_INVALID_CONFIG"
BLOCKED_UNKNOWN_FORMULA = "BLOCKED_UNKNOWN_FORMULA"
BLOCKED_ACTIVE_DEPLOYMENT = "BLOCKED_ACTIVE_DEPLOYMENT"
BLOCKED_INVALID_TRANSITION = "BLOCKED_INVALID_TRANSITION"
BLOCKED_NON_FINITE_QTY = "BLOCKED_NON_FINITE_QTY"
BLOCKED_TICKER_SCOPE = "BLOCKED_TICKER_SCOPE"
BLOCKED_CAPITAL_CAP = "BLOCKED_CAPITAL_CAP"
CONTROL_FALLBACK_OUT_OF_SCOPE = "CONTROL_FALLBACK_OUT_OF_SCOPE"
CONTROL_FALLBACK_CAPITAL_EXHAUSTED = "CONTROL_FALLBACK_CHALLENGER_CAP_EXHAUSTED"
CONTROL_FALLBACK_CANONICAL_UNIVERSE = "CONTROL_FALLBACK_CANONICAL_LIQUID_UNIVERSE"
SCOPE_RESULT_IN_SCOPE = "IN_SCOPE"

_CANONICAL_LIQUID_UNIVERSE: frozenset[str] | None = None

REGISTERED_FORMULAS: dict[str, dict[str, Any]] = {
    FORMULA_V1_DEPLOYABLE_25PCT: {
        "version": SHADOW_FORMULA_VERSION,
        "eval": "eval_v1_deployable",
        "role": "CONTROL_OR_CHALLENGER",
    },
    FORMULA_CANON_PAPER_CONF: {
        "version": SHADOW_FORMULA_VERSION,
        "eval": "eval_canonical_paper_confidence",
        "role": "CONTROL_OR_CHALLENGER",
    },
    FORMULA_LIVE_EQUAL_SPLIT: {
        "version": SHADOW_FORMULA_VERSION,
        "eval": "eval_live_equal_split",
        "role": "CHALLENGER_CANDIDATE",
    },
}

CONTROL_FORMULA_BY_ARM = {
    "V1": FORMULA_V1_DEPLOYABLE_25PCT,
    "V2": FORMULA_V1_DEPLOYABLE_25PCT,  # control identity for V2 is still path tranche; formula id stamp only
    "CANONICAL_PAPER": FORMULA_CANON_PAPER_CONF,
    "PAPER": FORMULA_CANON_PAPER_CONF,
}

ENTRY_SCOPE_NEW_BUY_ONLY = "NEW_BUY_ONLY"
ENTRY_SCOPE_V2_ADD_ONLY = "ELIGIBLE_V2_ADD_ONLY"
ENTRY_SCOPE_NEW_AND_V2_ADD = "NEW_BUY_AND_ELIGIBLE_V2_ADD"

VALID_CURRENT_DEPLOYMENT = "VALID_CURRENT_DEPLOYMENT"
BLOCKED_NEW_ACTIVATION_ACTIVE_DEPLOYMENT = "BLOCKED_NEW_ACTIVATION_ACTIVE_DEPLOYMENT"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _s(v: Any, default: str = "") -> str:
    return str(v if v is not None else default).strip()


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _b(v: Any, default: bool = False) -> bool:
    if v is True or v == 1:
        return True
    if isinstance(v, str) and v.strip().lower() in {"true", "1", "yes", "on"}:
        return True
    if v is False or v == 0:
        return False
    return default


def resolve_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    env = os.environ.get("TAE_ADAPTIVE_DEPLOYMENT_ROOT")
    if env:
        return Path(env)
    return DEFAULT_ROOT


def paths(root: Path | None = None) -> dict[str, Path]:
    r = resolve_root(root)
    return {
        "root": r,
        "state": r / STATE_NAME,
        "lkg": r / LKG_NAME,
        "history": r / HISTORY_NAME,
        "experiment": r / EXPERIMENT_NAME,
    }


def git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or "UNKNOWN"
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def default_state(*, created_by: str = "migrate_default") -> dict[str, Any]:
    ts = _now()
    did = f"DEP-{uuid.uuid4().hex[:12].upper()}"
    return {
        "schema": SCHEMA,
        "deployment_id": did,
        "deployment_version": "1",
        "experiment_id": SHADOW_EXPERIMENT_ID,
        "experiment_arm": "CONTROL",
        "deployment_state": ST_DRAFT,
        "mode": "PAPER_CANARY",
        "active_formula_id": FORMULA_V1_DEPLOYABLE_25PCT,
        "active_formula_version": SHADOW_FORMULA_VERSION,
        "challenger_formula_id": None,
        "challenger_formula_version": None,
        "activation_timestamp": None,
        "updated_timestamp": ts,
        "capital_allocation_pct": 0.0,
        "capital_limit": 0.0,
        "ticker_scope": ["*"],
        "entry_scope": "NEW_BUY_ONLY",
        "previous_deployment_version": None,
        "last_known_good_version": None,
        "last_known_good_snapshot": None,
        "rollback_reason": None,
        "rollback_timestamp": None,
        "promotion_reason": None,
        "demotion_reason": None,
        "live_allowed": False,
        "paper_only": True,
        "created_by": created_by,
        "git_head": git_head(),
        "fail_closed_policy": FAIL_CLOSED_POLICY,
        "recommendation": None,
        "recommendation_confidence": None,
        "recommendation_reason": None,
        "recommendation_timestamp": None,
        "config_refs": {
            "parallel_paper_config": "tae_parallel_paper_config.json",
            "strategy_v2_config": "tae_strategy_v2_config.json",
            "shadow_experiment_id": SHADOW_EXPERIMENT_ID,
        },
        "veto_last": {},
        "one_challenger_max": True,
        "challenger_exposure_usd": 0.0,
        "automatic_critical_rollback": True,
    }


def default_experiment() -> dict[str, Any]:
    return {
        "schema": EXPERIMENT_SCHEMA,
        "experiment_id": SHADOW_EXPERIMENT_ID,
        "experiment_version": "1",
        "hypothesis": (
            "Shadow-observed alternate BUY sizing formulas can be activated as a "
            "limited PAPER canary without changing SELL or LIVE."
        ),
        "control_formula": FORMULA_V1_DEPLOYABLE_25PCT,
        "challenger_formula": None,
        "status": ST_DRAFT,
        "start_time": None,
        "end_time": None,
        "capital_limit": 0.0,
        "ticker_scope": ["*"],
        "acceptance_metrics": ["net_pnl", "drawdown", "expectancy", "profit_factor", "trade_count"],
        "rollback_metrics": ["hard_risk_critical", "reconciliation_fail", "non_finite_sizing"],
        "current_arm": "CONTROL",
        "result_summary": None,
        "updated_timestamp": _now(),
        "git_head": git_head(),
    }


def validate_state(state: dict[str, Any] | None) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(state, dict):
        return False, ["state_not_dict"]
    if _s(state.get("schema")) != SCHEMA:
        errors.append("bad_schema")
    st = _s(state.get("deployment_state"))
    if st not in SUPPORTED_STATES:
        errors.append("unknown_state")
    if _b(state.get("live_allowed"), False) is True:
        errors.append("live_allowed_must_be_false")
    if _b(state.get("paper_only"), True) is not True:
        errors.append("paper_only_must_be_true")
    if st in ACTIVE_BUY_STATES:
        cf = _s(state.get("challenger_formula_id"))
        if not cf:
            errors.append("active_requires_challenger_formula")
        elif cf not in REGISTERED_FORMULAS:
            errors.append("unknown_challenger_formula")
    af = _s(state.get("active_formula_id"))
    if af and af not in REGISTERED_FORMULAS:
        # allow unknown active only in DRAFT as control label from path
        if st in ACTIVE_BUY_STATES:
            errors.append("unknown_active_formula")
    pct = _f(state.get("capital_allocation_pct"))
    if pct < 0 or pct > 100:
        errors.append("capital_allocation_pct_out_of_range")
    return len(errors) == 0, errors


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_state(*, root: Path | None = None, create_default: bool = True) -> dict[str, Any]:
    p = paths(root)
    raw = _load_json(p["state"])
    if raw is None:
        if not create_default:
            raise FileNotFoundError(str(p["state"]))
        state = default_state()
        save_state(state, root=root)
        ensure_experiment_registry(root=root)
        return state
    # Hard safety clamps — never trust disk for LIVE
    raw["live_allowed"] = False
    raw["paper_only"] = True
    ok, errs = validate_state(raw)
    if not ok and "live_allowed_must_be_false" in errs:
        raw["live_allowed"] = False
    if not ok and create_default and ("bad_schema" in errs or "state_not_dict" in errs):
        # fail-closed migrate to safe draft without wiping id if present
        safe = default_state(created_by="corrupt_ssot_fail_closed")
        safe["demotion_reason"] = "CORRUPT_SSOT:" + ",".join(errs)
        save_state(safe, root=root)
        return safe
    return raw


def save_state(state: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    state = dict(state)
    state["live_allowed"] = False
    state["paper_only"] = True
    state["updated_timestamp"] = _now()
    state["git_head"] = git_head()
    state["schema"] = SCHEMA
    ok, errs = validate_state(state)
    if not ok and any(e.startswith("live_") or e.startswith("paper_") for e in errs):
        state["live_allowed"] = False
        state["paper_only"] = True
        ok, errs = validate_state(state)
    if not ok and "unknown_state" in errs:
        raise ValueError(f"BLOCKED_INVALID_CONFIG:{','.join(errs)}")
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)
    atomic_write_json(p["state"], state)
    return state


def ensure_experiment_registry(*, root: Path | None = None) -> dict[str, Any]:
    p = paths(root)
    raw = _load_json(p["experiment"])
    if raw and _s(raw.get("schema")) == EXPERIMENT_SCHEMA:
        return raw
    doc = default_experiment()
    p["root"].mkdir(parents=True, exist_ok=True)
    atomic_write_json(p["experiment"], doc)
    return doc


def save_experiment(doc: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    doc = dict(doc)
    doc["schema"] = EXPERIMENT_SCHEMA
    doc["updated_timestamp"] = _now()
    doc["git_head"] = git_head()
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)
    atomic_write_json(p["experiment"], doc)
    return doc


def build_lkg_snapshot(state: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "schema": LKG_SCHEMA,
        "lkg_version": _s(state.get("deployment_version")) or "1",
        "deployment_id": state.get("deployment_id"),
        "deployment_version": state.get("deployment_version"),
        "deployment_state": state.get("deployment_state"),
        "active_formula_id": state.get("active_formula_id"),
        "active_formula_version": state.get("active_formula_version"),
        "challenger_formula_id": state.get("challenger_formula_id"),
        "challenger_formula_version": state.get("challenger_formula_version"),
        "capital_allocation_pct": state.get("capital_allocation_pct"),
        "capital_limit": state.get("capital_limit"),
        "ticker_scope": list(state.get("ticker_scope") or ["*"]),
        "entry_scope": state.get("entry_scope"),
        "experiment_id": state.get("experiment_id"),
        "experiment_arm": state.get("experiment_arm"),
        "config_refs": dict(state.get("config_refs") or {}),
        "risk_configuration_reference": "hard_risk_guardian+fill_time_recheck",
        "effective_parameters": {
            "mode": state.get("mode"),
            "fail_closed_policy": state.get("fail_closed_policy"),
            "paper_only": True,
            "live_allowed": False,
        },
        "timestamp": _now(),
        "git_head": git_head(),
        "reason": reason,
        "validation_status": "VALID",
    }


def validate_lkg(lkg: dict[str, Any] | None) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(lkg, dict):
        return False, ["lkg_missing"]
    if _s(lkg.get("schema")) != LKG_SCHEMA:
        errors.append("bad_lkg_schema")
    if not _s(lkg.get("lkg_version")):
        errors.append("missing_lkg_version")
    if not _s(lkg.get("active_formula_id")):
        errors.append("missing_active_formula")
    if _s(lkg.get("validation_status")).upper() != "VALID":
        errors.append("lkg_not_valid")
    return len(errors) == 0, errors


def save_lkg(lkg: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    ok, errs = validate_lkg(lkg)
    if not ok:
        raise ValueError(f"BLOCKED_NO_VALID_LKG:{','.join(errs)}")
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)
    atomic_write_json(p["lkg"], lkg)
    return lkg


def load_lkg(*, root: Path | None = None) -> dict[str, Any] | None:
    return _load_json(paths(root)["lkg"])


def append_transition(rec: dict[str, Any], *, root: Path | None = None) -> None:
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, default=str) + "\n"
    with p["history"].open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def transition_allowed(from_state: str, to_state: str) -> bool:
    if to_state == ST_LIVE_ELIGIBLE:
        return False  # informational only; never transition into LIVE path
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def evaluate_vetoes(
    *,
    state: dict[str, Any] | None = None,
    target_state: str | None = None,
    require_lkg: bool = False,
    hard_risk_ok: bool = True,
    reconciliation_ok: bool = True,
    data_quality_ok: bool = True,
    live_requested: bool = False,
    formula_id: str | None = None,
    root: Path | None = None,
    validation_mode: str = "transition",
) -> dict[str, Any]:
    """Connect existing gates into activation veto results (fail-closed).

    validation_mode:
      - \"transition\" / \"activation\": gates for activating or transitioning
      - \"current\": health of an already-active (or inactive) deployment
    """
    state = state or load_state(root=root)
    mode = _s(validation_mode).lower() or "transition"
    if mode in {"activation", "activate"}:
        mode = "transition"
    results: dict[str, Any] = {
        "HARD_RISK_VETO": "PASS" if hard_risk_ok else "FAIL",
        "RECONCILIATION_VETO": "PASS" if reconciliation_ok else "FAIL",
        "DATA_QUALITY_VETO": "PASS" if data_quality_ok else "FAIL",
        "LKG_VALIDATION": "PASS",
        "LIVE_LOCK": "PASS",
        "CONFIG_VALIDATION": "PASS",
        "FORMULA_REGISTERED": "PASS",
        "ACTIVE_DEPLOYMENT": "PASS",
        "TRANSITION": "PASS",
        "blocked": False,
        "reason_codes": [],
        "validation_mode": mode,
    }

    # LIVE lock — always enforce
    try:
        from tae_live_promotion_lock import enforce_promotion_gate

        gate = enforce_promotion_gate({"live_promotion_allowed": False})
        if gate.get("live_promotion_allowed") is True or gate.get("machine_live_promotion_allowed") is True:
            results["LIVE_LOCK"] = "FAIL"
            results["reason_codes"].append(BLOCKED_LIVE_LOCK)
    except Exception:
        # fail-closed: if lock module breaks, still deny LIVE
        pass

    if live_requested or _b(state.get("live_allowed")) or _s(os.environ.get("TAE_DEPLOYMENT_ENV")).upper() == "LIVE":
        results["LIVE_LOCK"] = "FAIL"
        results["reason_codes"].append(BLOCKED_LIVE_LOCK)

    ok_cfg, cfg_errs = validate_state(state)
    if not ok_cfg:
        results["CONFIG_VALIDATION"] = "FAIL"
        results["reason_codes"].append(BLOCKED_INVALID_CONFIG)

    if require_lkg or (target_state in ACTIVE_BUY_STATES):
        lkg = load_lkg(root=root)
        lok, lerrs = validate_lkg(lkg)
        if not lok:
            results["LKG_VALIDATION"] = "FAIL"
            results["reason_codes"].append(BLOCKED_NO_VALID_LKG)

    if not hard_risk_ok:
        results["reason_codes"].append(BLOCKED_HARD_RISK)
    if not reconciliation_ok:
        results["reason_codes"].append(BLOCKED_RECONCILIATION)
    if not data_quality_ok:
        results["reason_codes"].append(BLOCKED_DATA_QUALITY)

    fid = _s(formula_id or state.get("challenger_formula_id"))
    if target_state in ACTIVE_BUY_STATES:
        if not fid or fid not in REGISTERED_FORMULAS:
            results["FORMULA_REGISTERED"] = "FAIL"
            results["reason_codes"].append(BLOCKED_UNKNOWN_FORMULA)

    cur = _s(state.get("deployment_state"))
    # Transition/activation collision checks — NOT for current-health validation.
    if target_state and mode != "current":
        if not transition_allowed(cur, target_state):
            results["TRANSITION"] = "FAIL"
            results["reason_codes"].append(BLOCKED_INVALID_TRANSITION)
        # one active challenger deployment at a time
        if cur in ACTIVE_BUY_STATES and target_state in ACTIVE_BUY_STATES and cur != target_state:
            # PAPER_CHALLENGER → PAPER_ACTIVE is allowed
            pass
        elif cur in ACTIVE_BUY_STATES and target_state == ST_PAPER_CHALLENGER:
            results["ACTIVE_DEPLOYMENT"] = "FAIL"
            results["reason_codes"].append(BLOCKED_ACTIVE_DEPLOYMENT)
            results["activation_status"] = BLOCKED_NEW_ACTIVATION_ACTIVE_DEPLOYMENT

    # Current-mode formula registration: require challenger when already active
    if mode == "current" and cur in ACTIVE_BUY_STATES:
        fid_cur = _s(state.get("challenger_formula_id"))
        if not fid_cur or fid_cur not in REGISTERED_FORMULAS:
            results["FORMULA_REGISTERED"] = "FAIL"
            results["reason_codes"].append(BLOCKED_UNKNOWN_FORMULA)

    results["reason_codes"] = sorted(set(results["reason_codes"]))
    results["blocked"] = bool(results["reason_codes"])
    results["config_errors"] = cfg_errs if not ok_cfg else []
    if mode == "current" and not results["blocked"]:
        results["current_status"] = VALID_CURRENT_DEPLOYMENT
    return results


def _bump_version(state: dict[str, Any]) -> str:
    try:
        n = int(_s(state.get("deployment_version")) or "1")
    except ValueError:
        n = 1
    return str(n + 1)


def transition(
    to_state: str,
    *,
    reason: str,
    actor: str = "cli",
    root: Path | None = None,
    hard_risk_ok: bool = True,
    reconciliation_ok: bool = True,
    data_quality_ok: bool = True,
    live_requested: bool = False,
    skip_veto: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_state(root=root)
    from_state = _s(state.get("deployment_state"))
    to_state = _s(to_state).upper()

    if to_state == ST_LIVE_ELIGIBLE or live_requested:
        return {
            "ok": False,
            "reason_codes": [BLOCKED_LIVE_LOCK],
            "state": state,
            "transition": None,
        }

    if not transition_allowed(from_state, to_state):
        return {
            "ok": False,
            "reason_codes": [BLOCKED_INVALID_TRANSITION],
            "from_state": from_state,
            "to_state": to_state,
            "state": state,
            "transition": None,
        }

    require_lkg = to_state in ACTIVE_BUY_STATES
    # For first activation, LKG must already be saved by activate() before transition
    vetoes = (
        {"blocked": False, "reason_codes": []}
        if skip_veto
        else evaluate_vetoes(
            state=state,
            target_state=to_state,
            require_lkg=require_lkg and to_state != ST_PAPER_CHALLENGER,
            hard_risk_ok=hard_risk_ok,
            reconciliation_ok=reconciliation_ok,
            data_quality_ok=data_quality_ok,
            live_requested=False,
            root=root,
        )
    )
    # PAPER_CHALLENGER activation: LKG required but may have just been written
    if to_state in ACTIVE_BUY_STATES and not skip_veto:
        lok, _ = validate_lkg(load_lkg(root=root))
        if not lok:
            vetoes = dict(vetoes)
            vetoes["blocked"] = True
            codes = list(vetoes.get("reason_codes") or [])
            if BLOCKED_NO_VALID_LKG not in codes:
                codes.append(BLOCKED_NO_VALID_LKG)
            vetoes["reason_codes"] = codes
            vetoes["LKG_VALIDATION"] = "FAIL"

    if vetoes.get("blocked"):
        return {
            "ok": False,
            "reason_codes": vetoes.get("reason_codes"),
            "vetoes": vetoes,
            "state": state,
            "transition": None,
        }

    prev_ver = _s(state.get("deployment_version"))
    new_ver = _bump_version(state)
    state["previous_deployment_version"] = prev_ver
    state["deployment_version"] = new_ver
    state["deployment_state"] = to_state
    if to_state in ACTIVE_BUY_STATES:
        state["activation_timestamp"] = _now()
        state["experiment_arm"] = "CHALLENGER"
        state["promotion_reason"] = reason if to_state == ST_PAPER_ACTIVE else state.get("promotion_reason")
    if to_state == ST_PAUSED:
        state["demotion_reason"] = reason
    if to_state in {ST_ROLLED_BACK, ST_REJECTED}:
        state["rollback_reason"] = reason
        state["rollback_timestamp"] = _now()
        state["demotion_reason"] = reason
        state["experiment_arm"] = "CONTROL"
    if to_state == ST_DRAFT:
        state["challenger_formula_id"] = None
        state["challenger_formula_version"] = None
        state["capital_allocation_pct"] = 0.0
        state["experiment_arm"] = "CONTROL"
    if extra:
        for k, v in extra.items():
            if k in {"live_allowed", "paper_only", "schema"}:
                continue
            state[k] = v

    state["veto_last"] = vetoes
    state = save_state(state, root=root)

    # Sync experiment registry status
    exp = ensure_experiment_registry(root=root)
    exp["challenger_formula"] = state.get("challenger_formula_id")
    exp["control_formula"] = state.get("active_formula_id")
    exp["capital_limit"] = state.get("capital_limit")
    exp["ticker_scope"] = state.get("ticker_scope")
    exp["current_arm"] = state.get("experiment_arm")
    if to_state in ACTIVE_BUY_STATES:
        exp["status"] = "ACTIVE_PAPER"
        exp["start_time"] = exp.get("start_time") or _now()
    elif to_state == ST_PAUSED:
        exp["status"] = "PAUSED"
    elif to_state == ST_ROLLED_BACK:
        exp["status"] = "ROLLED_BACK"
        exp["end_time"] = _now()
    elif to_state == ST_REJECTED:
        exp["status"] = "REJECTED"
        exp["end_time"] = _now()
    elif to_state == ST_DRAFT:
        exp["status"] = "DRAFT"
    save_experiment(exp, root=root)

    trec = {
        "schema": TRANSITION_SCHEMA,
        "transition_id": f"TR-{uuid.uuid4().hex[:12].upper()}",
        "timestamp": _now(),
        "from_state": from_state,
        "to_state": to_state,
        "reason": reason,
        "actor": actor,
        "veto_results": vetoes,
        "deployment_id": state.get("deployment_id"),
        "deployment_version": new_ver,
        "git_head": git_head(),
    }
    append_transition(trec, root=root)
    return {"ok": True, "state": state, "transition": trec, "vetoes": vetoes, "reason_codes": []}


def activate_challenger(
    *,
    experiment_id: str,
    challenger_formula: str,
    capital_allocation_pct: float,
    capital_limit: float = 0.0,
    ticker_scope: list[str] | str | None = None,
    reason: str = "cli_activate",
    actor: str = "cli",
    root: Path | None = None,
    hard_risk_ok: bool = True,
    reconciliation_ok: bool = True,
    data_quality_ok: bool = True,
    live_requested: bool = False,
) -> dict[str, Any]:
    if live_requested:
        return {"ok": False, "reason_codes": [BLOCKED_LIVE_LOCK], "state": load_state(root=root)}

    state = load_state(root=root)
    cf = _s(challenger_formula)
    if cf not in REGISTERED_FORMULAS:
        return {"ok": False, "reason_codes": [BLOCKED_UNKNOWN_FORMULA], "state": state}

    if _s(state.get("deployment_state")) in ACTIVE_BUY_STATES:
        return {"ok": False, "reason_codes": [BLOCKED_ACTIVE_DEPLOYMENT], "state": state}

    # Normalize from ROLLED_BACK → DRAFT first if needed
    if _s(state.get("deployment_state")) == ST_ROLLED_BACK:
        tr = transition(ST_DRAFT, reason="prep_activate", actor=actor, root=root, skip_veto=True)
        if not tr.get("ok"):
            return tr
        state = tr["state"]

    if _s(state.get("deployment_state")) == ST_PAUSED:
        # PAUSED → PAPER_CHALLENGER allowed
        pass
    elif _s(state.get("deployment_state")) not in {ST_DRAFT, ST_PAUSED}:
        return {
            "ok": False,
            "reason_codes": [BLOCKED_INVALID_TRANSITION],
            "state": state,
        }

    scope: list[str]
    if ticker_scope is None:
        scope = ["*"]
    elif isinstance(ticker_scope, str):
        scope = [t.strip().upper() for t in ticker_scope.split(",") if t.strip()] or ["*"]
    else:
        scope = [str(t).strip().upper() for t in ticker_scope if str(t).strip()] or ["*"]

    pct = float(capital_allocation_pct)
    if pct <= 0 or pct > 100:
        return {"ok": False, "reason_codes": [BLOCKED_INVALID_CONFIG], "state": state}

    # Save LKG *before* activation (required)
    lkg = build_lkg_snapshot(state, reason=f"pre_activate:{reason}")
    try:
        save_lkg(lkg, root=root)
    except ValueError as exc:
        return {"ok": False, "reason_codes": [BLOCKED_NO_VALID_LKG], "detail": str(exc), "state": state}

    state["challenger_formula_id"] = cf
    state["challenger_formula_version"] = REGISTERED_FORMULAS[cf]["version"]
    state["capital_allocation_pct"] = pct
    state["capital_limit"] = float(capital_limit) if capital_limit else 0.0
    state["ticker_scope"] = scope
    state["entry_scope"] = "NEW_BUY_ONLY"
    state["experiment_id"] = _s(experiment_id) or SHADOW_EXPERIMENT_ID
    state["last_known_good_version"] = lkg.get("lkg_version")
    state["last_known_good_snapshot"] = lkg.get("lkg_version")
    state["mode"] = "PAPER_CANARY"
    # Keep control formula as path default active_formula_id (control identity)
    if not _s(state.get("active_formula_id")):
        state["active_formula_id"] = FORMULA_V1_DEPLOYABLE_25PCT
        state["active_formula_version"] = SHADOW_FORMULA_VERSION
    state = save_state(state, root=root)

    return transition(
        ST_PAPER_CHALLENGER,
        reason=reason,
        actor=actor,
        root=root,
        hard_risk_ok=hard_risk_ok,
        reconciliation_ok=reconciliation_ok,
        data_quality_ok=data_quality_ok,
        live_requested=False,
    )


def pause_deployment(*, reason: str, actor: str = "cli", root: Path | None = None) -> dict[str, Any]:
    return transition(ST_PAUSED, reason=reason, actor=actor, root=root, skip_veto=True)


def rollback_deployment(
    *,
    reason: str,
    actor: str = "cli",
    root: Path | None = None,
    automatic: bool = False,
) -> dict[str, Any]:
    """Restore LKG formula settings and move to ROLLED_BACK. Does not liquidate positions."""
    state = load_state(root=root)
    lkg = load_lkg(root=root)
    lok, lerrs = validate_lkg(lkg)
    if not lok:
        # Still force stop challenger BUY even if LKG corrupt — fail closed to DRAFT-like control
        state["challenger_formula_id"] = None
        state["challenger_formula_version"] = None
        state["capital_allocation_pct"] = 0.0
        state["experiment_arm"] = "CONTROL"
        state["rollback_reason"] = reason + "|LKG_INVALID:" + ",".join(lerrs)
        state["rollback_timestamp"] = _now()
        state = save_state(state, root=root)
        cur = _s(state.get("deployment_state"))
        if cur in ACTIVE_BUY_STATES or cur == ST_PAUSED:
            return transition(
                ST_ROLLED_BACK,
                reason=state["rollback_reason"],
                actor=actor,
                root=root,
                skip_veto=True,
                extra={"challenger_formula_id": None, "capital_allocation_pct": 0.0},
            )
        return {"ok": False, "reason_codes": [BLOCKED_NO_VALID_LKG], "state": state, "lkg_errors": lerrs}

    assert lkg is not None
    # Restore control from LKG
    extra = {
        "active_formula_id": lkg.get("active_formula_id"),
        "active_formula_version": lkg.get("active_formula_version"),
        "challenger_formula_id": None,
        "challenger_formula_version": None,
        "capital_allocation_pct": 0.0,
        "capital_limit": 0.0,
        "ticker_scope": list(lkg.get("ticker_scope") or ["*"]),
        "experiment_arm": "CONTROL",
        "last_known_good_version": lkg.get("lkg_version"),
    }
    cur = _s(state.get("deployment_state"))
    if cur not in ACTIVE_BUY_STATES and cur != ST_PAUSED:
        # Already inactive — still clear challenger fields
        state.update(extra)
        state["rollback_reason"] = reason
        state["rollback_timestamp"] = _now()
        state = save_state(state, root=root)
        return {"ok": True, "state": state, "restored_lkg": lkg, "note": "already_inactive"}

    return transition(
        ST_ROLLED_BACK,
        reason=reason if not automatic else f"AUTO:{reason}",
        actor=actor,
        root=root,
        skip_veto=True,
        extra=extra,
    )


def sync_dpe_recommendation(*, root: Path | None = None) -> dict[str, Any]:
    """CONNECT advisory only — does not transition state."""
    state = load_state(root=root)
    adaptive_path = PROJECT_ROOT / "runtime_outputs" / "dpe" / "adaptive" / "adaptive.json"
    rec = None
    conf = None
    reason = "dpe_adaptive_missing"
    if adaptive_path.is_file():
        try:
            raw = json.loads(adaptive_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                rec = raw.get("recommended_philosophy") or raw.get("recommendation") or raw.get("winner")
                conf = raw.get("confidence") or raw.get("recommendation_confidence")
                reason = "dpe_adaptive_advisory"
        except (OSError, json.JSONDecodeError):
            reason = "dpe_adaptive_unreadable"
    state["recommendation"] = rec
    state["recommendation_confidence"] = conf
    state["recommendation_reason"] = reason
    state["recommendation_timestamp"] = _now()
    state = save_state(state, root=root)
    return {"ok": True, "state": state, "advisory_only": True}


def map_roi_status_to_deployment(
    roi_status: str,
    *,
    root: Path | None = None,
    actor: str = "roi_connect",
    apply: bool = False,
) -> dict[str, Any]:
    """CONNECT ROI lifecycle vocabulary → deployment states (optional apply)."""
    st = _s(roi_status).upper()
    mapping = {
        "PROMOTED_PAPER": ST_PAPER_ACTIVE,
        "RETIRED": ST_PAUSED,
        "REJECTED": ST_REJECTED,
        "ACTIVE_CHALLENGER": ST_PAPER_CHALLENGER,
        "WAITING": ST_DRAFT,
        "ECONOMICALLY_POSITIVE": ST_PAPER_CHALLENGER,
    }
    target = mapping.get(st)
    out: dict[str, Any] = {
        "roi_status": st,
        "mapped_deployment_state": target,
        "applied": False,
    }
    if not target or not apply:
        return out
    state = load_state(root=root)
    cur = _s(state.get("deployment_state"))
    if cur == target:
        out["applied"] = False
        out["note"] = "already_in_mapped_state"
        return out
    if target == ST_PAPER_ACTIVE and cur == ST_PAPER_CHALLENGER:
        res = transition(ST_PAPER_ACTIVE, reason=f"roi_map:{st}", actor=actor, root=root, skip_veto=True)
        out["applied"] = bool(res.get("ok"))
        out["result"] = res
        return out
    if target == ST_PAUSED and cur in ACTIVE_BUY_STATES:
        res = pause_deployment(reason=f"roi_map:{st}", actor=actor, root=root)
        out["applied"] = bool(res.get("ok"))
        out["result"] = res
        return out
    if target == ST_REJECTED and cur in {ST_PAPER_CHALLENGER, ST_PAUSED}:
        res = transition(ST_REJECTED, reason=f"roi_map:{st}", actor=actor, root=root, skip_veto=True)
        out["applied"] = bool(res.get("ok"))
        out["result"] = res
        return out
    if target == ST_ROLLED_BACK:
        res = rollback_deployment(reason=f"roi_map:{st}", actor=actor, root=root)
        out["applied"] = bool(res.get("ok"))
        out["result"] = res
        return out
    out["note"] = "mapping_requires_manual_or_compatible_state"
    return out


def sync_roi_connection(*, root: Path | None = None, apply: bool = False) -> dict[str, Any]:
    try:
        from tae_roi001_challenger import load_roi_queue_ssot, _queue_items, _roi_id
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    doc = load_roi_queue_ssot()
    active = next((i for i in _queue_items(doc) if i.get("active")), None)
    status = _s((active or {}).get("status"))
    mapped = map_roi_status_to_deployment(status, root=root, apply=apply)
    return {
        "ok": True,
        "active_roi_id": _roi_id(active) if active else None,
        "roi_status": status or None,
        "mapping": mapped,
    }


def formula_notional(formula_id: str, inputs: dict[str, Any]) -> tuple[float | None, str]:
    fid = _s(formula_id)
    if fid not in REGISTERED_FORMULAS:
        return None, BLOCKED_UNKNOWN_FORMULA
    if fid == FORMULA_V1_DEPLOYABLE_25PCT:
        n, missing, invalid = eval_v1_deployable(inputs)
    elif fid == FORMULA_CANON_PAPER_CONF:
        n, missing, invalid = eval_canonical_paper_confidence(inputs)
    elif fid == FORMULA_LIVE_EQUAL_SPLIT:
        n, missing, invalid = eval_live_equal_split(inputs)
    else:
        return None, BLOCKED_UNKNOWN_FORMULA
    if missing or invalid:
        return None, BLOCKED_INVALID_CONFIG
    if n is None or not math.isfinite(float(n)) or float(n) < 0:
        return None, BLOCKED_NON_FINITE_QTY
    return float(n), "OK"


def ticker_in_scope(ticker: str, scope: list[str] | None) -> bool:
    t = _s(ticker).upper()
    sc = scope or ["*"]
    if "*" in sc:
        return True
    return t in {s.upper() for s in sc}


def load_canonical_liquid_universe() -> frozenset[str]:
    """EU/UK/US watchlists already in repo — no new watchlist."""
    global _CANONICAL_LIQUID_UNIVERSE
    if _CANONICAL_LIQUID_UNIVERSE is not None:
        return _CANONICAL_LIQUID_UNIVERSE
    try:
        from daily_gainers_strategy_research import build_ticker_universe

        _CANONICAL_LIQUID_UNIVERSE = frozenset(build_ticker_universe().keys())
    except Exception:
        _CANONICAL_LIQUID_UNIVERSE = frozenset()
    return _CANONICAL_LIQUID_UNIVERSE


def ticker_in_canonical_liquid_universe(ticker: str) -> bool:
    return _s(ticker).upper() in load_canonical_liquid_universe()


def effective_ticker_in_scope(ticker: str, scope: list[str] | None) -> bool:
    return ticker_in_scope(ticker, scope) or ticker_in_canonical_liquid_universe(ticker)


def common_control_buy_notional(
    control_notional: float,
    inputs: dict[str, Any],
    *,
    arm: str,
) -> float:
    """
    Shared control-path notional for V1 / V2 / Vx.

    V2 never exceeds the authorized tranche (control_notional). Other arms may
    lift conservative caller estimates toward the common deployable band.
    """
    arm_u = _s(arm).upper()
    cash = _f(inputs.get("cash_available"))
    reserve = _f(inputs.get("cash_reserve"), 500.0)
    max_pos = _f(inputs.get("maximum_position_notional"), PAPER_MAX_POSITION_NOTIONAL)
    investable = max(0.0, cash - reserve)
    if investable <= 0:
        return 0.0
    if arm_u == "V2":
        return round(min(float(control_notional), investable, max_pos), 6)
    conf_raw = inputs.get("confidence")
    conf = _f(conf_raw, 0.5) if conf_raw is not None else None
    deploy_target = paper_deployable_notional(cash, cash_reserve=reserve, cap=max_pos)
    if conf is not None:
        conf_target = paper_confidence_notional(cash, conf, cash_reserve=reserve, max_pos=max_pos)
        deploy_target = max(deploy_target, conf_target)
    lifted = max(float(control_notional), deploy_target)
    return round(min(lifted, investable, max_pos), 6)


def _control_fallback_response(
    out: dict[str, Any],
    *,
    state: dict[str, Any],
    control_notional: float,
    inputs: dict[str, Any],
    arm: str,
    selection_reason: str,
    scope_result: str,
    ticker_scope_match: bool | None,
) -> dict[str, Any]:
    executed = common_control_buy_notional(control_notional, inputs, arm=arm)
    if executed < PAPER_MIN_ORDER_USD:
        out["ok"] = False
        out["blocked"] = True
        out["reason_code"] = BLOCKED_CAPITAL_CAP if executed <= 0 else BLOCKED_NON_FINITE_QTY
        out["executed_notional"] = 0.0
        out["decision"] = "BLOCK"
        out["deployment"] = deployment_metadata(state, selection_reason=out["reason_code"])
        return out
    out["ok"] = True
    out["blocked"] = False
    out["reason_code"] = None
    out["executed_notional"] = round(float(executed), 6)
    out["used_arm"] = "CONTROL"
    out["decision"] = "USE_CONTROL"
    out["selection_note"] = selection_reason
    out["scope_result"] = scope_result
    out["ticker_scope_match"] = ticker_scope_match
    out["challenger_exposure"] = False
    out["adaptive_arm"] = "CONTROL"
    out["adaptive_reason"] = selection_reason
    out["deployment"] = deployment_metadata(state, selection_reason=selection_reason)
    out["deployment"]["experiment_arm"] = "CONTROL"
    return out


def deployment_metadata(state: dict[str, Any] | None = None, *, selection_reason: str | None = None) -> dict[str, Any]:
    state = state or load_state()
    arm = "CHALLENGER" if _s(state.get("deployment_state")) in ACTIVE_BUY_STATES else "CONTROL"
    return {
        "deployment_id": state.get("deployment_id"),
        "deployment_version": state.get("deployment_version"),
        "deployment_state": state.get("deployment_state"),
        "experiment_id": state.get("experiment_id"),
        "experiment_arm": state.get("experiment_arm") or arm,
        "formula_id": (
            state.get("challenger_formula_id")
            if _s(state.get("deployment_state")) in ACTIVE_BUY_STATES
            else state.get("active_formula_id")
        ),
        "formula_version": (
            state.get("challenger_formula_version")
            if _s(state.get("deployment_state")) in ACTIVE_BUY_STATES
            else state.get("active_formula_version")
        ),
        "config_version": (state.get("config_refs") or {}).get("parallel_paper_config"),
        "git_head": state.get("git_head") or git_head(),
        "selection_reason": selection_reason or "deployment_ssot",
        "paper_only": True,
        "live_allowed": False,
    }


def residual_capital_limit(state: dict[str, Any] | None = None, *, root: Path | None = None) -> float | None:
    state = state or load_state(root=root)
    limit = _f(state.get("capital_limit"))
    if limit <= 0:
        return None
    return max(0.0, limit - max(0.0, _f(state.get("challenger_exposure_usd"))))


def record_challenger_exposure(
    notional: float,
    *,
    root: Path | None = None,
    arm: str = "",
    ticker: str = "",
) -> dict[str, Any]:
    """Increment shared deployment challenger exposure after a successful BUY fill."""
    state = load_state(root=root)
    if _s(state.get("deployment_state")) not in ACTIVE_BUY_STATES:
        return state
    add = max(0.0, float(notional))
    if add <= 0:
        return state
    state["challenger_exposure_usd"] = round(_f(state.get("challenger_exposure_usd")) + add, 6)
    state["challenger_exposure_last"] = {
        "notional": add,
        "arm": _s(arm),
        "ticker": _s(ticker).upper(),
        "timestamp": _now(),
    }
    return save_state(state, root=root)


def migrate_active_entry_scope(
    *,
    entry_scope: str = ENTRY_SCOPE_NEW_AND_V2_ADD,
    reason: str = "extend_v2_add_into_canary",
    actor: str = "runtime_fix",
    root: Path | None = None,
) -> dict[str, Any]:
    """Versioned migrate of an active deployment without invalid state transition."""
    state = load_state(root=root)
    if _s(state.get("deployment_state")) not in ACTIVE_BUY_STATES:
        return {"ok": False, "reason_codes": [BLOCKED_INVALID_TRANSITION], "state": state}
    if _b(state.get("live_allowed")):
        return {"ok": False, "reason_codes": [BLOCKED_LIVE_LOCK], "state": state}

    lkg = build_lkg_snapshot(state, reason=f"pre_migrate:{reason}")
    try:
        save_lkg(lkg, root=root)
    except ValueError as exc:
        return {"ok": False, "reason_codes": [BLOCKED_NO_VALID_LKG], "detail": str(exc), "state": state}

    prev = _s(state.get("deployment_version"))
    new_ver = _bump_version(state)
    state["previous_deployment_version"] = prev
    state["deployment_version"] = new_ver
    state["entry_scope"] = _s(entry_scope) or ENTRY_SCOPE_NEW_AND_V2_ADD
    state["last_known_good_version"] = lkg.get("lkg_version")
    state["last_known_good_snapshot"] = lkg.get("lkg_version")
    state.setdefault("challenger_exposure_usd", 0.0)
    state["live_allowed"] = False
    state["paper_only"] = True
    state = save_state(state, root=root)

    trec = {
        "schema": TRANSITION_SCHEMA,
        "transition_id": f"TR-{uuid.uuid4().hex[:12].upper()}",
        "timestamp": _now(),
        "from_state": state.get("deployment_state"),
        "to_state": state.get("deployment_state"),
        "reason": reason,
        "actor": actor,
        "veto_results": {"blocked": False, "reason_codes": [], "note": "scope_migrate"},
        "deployment_id": state.get("deployment_id"),
        "deployment_version": new_ver,
        "git_head": git_head(),
        "entry_scope": state.get("entry_scope"),
    }
    append_transition(trec, root=root)
    return {"ok": True, "state": state, "transition": trec, "lkg": lkg}


def resolve_buy_notional(
    *,
    control_notional: float,
    inputs: dict[str, Any],
    ticker: str,
    arm: str = "V1",
    root: Path | None = None,
    state: dict[str, Any] | None = None,
    v2_add_authorized: bool = False,
) -> dict[str, Any]:
    """
    Canonical BUY quantity path helper.

    When deployment inactive → control unchanged.
    When PAPER_CHALLENGER/PAPER_ACTIVE → challenger formula + caps; FAIL_CLOSED on invalid.
    Never mutates SELL. Does not resize open positions.

    V2 ADD exception: when ``v2_add_authorized`` and ticker is outside canary
    ``ticker_scope``, return CONTROL fallback (not BLOCKED_TICKER_SCOPE) so an
    already-authorized accumulation tranche is not vetoed by challenger whitelist.
    V1/canonical NEW_BUY and V2 OPEN keep fail-closed on out-of-scope.
    """
    state = state or load_state(root=root)
    meta = deployment_metadata(state, selection_reason="control_default")
    control_fid = CONTROL_FORMULA_BY_ARM.get(_s(arm).upper(), FORMULA_V1_DEPLOYABLE_25PCT)
    # Prefer state's active formula as control identity when set
    if _s(state.get("active_formula_id")):
        control_fid = _s(state.get("active_formula_id"))

    out: dict[str, Any] = {
        "ok": True,
        "blocked": False,
        "reason_code": None,
        "control_notional": round(float(control_notional), 6),
        "challenger_notional_raw": None,
        "executed_notional": round(float(control_notional), 6),
        "control_formula_id": control_fid,
        "challenger_formula_id": state.get("challenger_formula_id"),
        "used_arm": "CONTROL",
        "deployment": meta,
        "fail_closed_policy": FAIL_CLOSED_POLICY,
        "decision": "USE_CONTROL",
        "scope_result": None,
        "ticker_scope_match": None,
        "challenger_exposure": False,
        "adaptive_arm": "CONTROL",
        "adaptive_reason": "control_default",
        "v2_add_authorized": bool(v2_add_authorized),
    }

    st = _s(state.get("deployment_state"))
    arm_u = _s(arm).upper()
    if st not in ACTIVE_BUY_STATES:
        enriched = common_control_buy_notional(control_notional, inputs, arm=arm_u)
        out["executed_notional"] = round(float(enriched), 6)
        if enriched != float(control_notional):
            out["adaptive_reason"] = "common_control_notional_enriched"
        return out

    # Auto critical rollback conditions
    if _b(state.get("live_allowed")):
        rollback_deployment(reason="LIVE_LOCK_VIOLATION", actor="runtime", root=root, automatic=True)
        out["ok"] = False
        out["blocked"] = True
        out["reason_code"] = BLOCKED_LIVE_LOCK
        out["executed_notional"] = 0.0
        out["deployment"] = deployment_metadata(load_state(root=root), selection_reason="auto_rollback_live")
        return out

    in_scope = ticker_in_scope(ticker, list(state.get("ticker_scope") or ["*"]))
    if not in_scope:
        # Authorized V2 ADD: challenger whitelist must not veto control accumulation.
        if arm_u == "V2" and v2_add_authorized:
            return _control_fallback_response(
                out,
                state=state,
                control_notional=control_notional,
                inputs=inputs,
                arm=arm_u,
                selection_reason=CONTROL_FALLBACK_OUT_OF_SCOPE,
                scope_result=CONTROL_FALLBACK_OUT_OF_SCOPE,
                ticker_scope_match=False,
            )
        if ticker_in_canonical_liquid_universe(ticker):
            return _control_fallback_response(
                out,
                state=state,
                control_notional=control_notional,
                inputs=inputs,
                arm=arm_u,
                selection_reason=CONTROL_FALLBACK_CANONICAL_UNIVERSE,
                scope_result=CONTROL_FALLBACK_CANONICAL_UNIVERSE,
                ticker_scope_match=False,
            )
        out["ok"] = False
        out["blocked"] = True
        out["reason_code"] = BLOCKED_TICKER_SCOPE
        out["executed_notional"] = 0.0
        out["decision"] = "BLOCK"
        out["scope_result"] = BLOCKED_TICKER_SCOPE
        out["ticker_scope_match"] = False
        out["challenger_exposure"] = False
        out["adaptive_arm"] = "NONE"
        out["adaptive_reason"] = BLOCKED_TICKER_SCOPE
        out["deployment"] = deployment_metadata(state, selection_reason=BLOCKED_TICKER_SCOPE)
        return out

    entry_scope = _s(state.get("entry_scope")) or ENTRY_SCOPE_NEW_BUY_ONLY
    if arm_u == "V2":
        if entry_scope not in {ENTRY_SCOPE_V2_ADD_ONLY, ENTRY_SCOPE_NEW_AND_V2_ADD, "*"}:
            # V2 ADD not in deployment entry scope — leave control path to caller
            out["selection_note"] = "V2_OUT_OF_ENTRY_SCOPE_USE_CONTROL"
            out["scope_result"] = SCOPE_RESULT_IN_SCOPE
            out["ticker_scope_match"] = True
            out["decision"] = "USE_CONTROL"
            out["adaptive_reason"] = "V2_OUT_OF_ENTRY_SCOPE_USE_CONTROL"
            return out
    elif arm_u in {"V1", "CANONICAL_PAPER", "PAPER"}:
        if entry_scope == ENTRY_SCOPE_V2_ADD_ONLY:
            out["selection_note"] = "NEW_BUY_OUT_OF_ENTRY_SCOPE_USE_CONTROL"
            out["decision"] = "USE_CONTROL"
            out["adaptive_reason"] = "NEW_BUY_OUT_OF_ENTRY_SCOPE_USE_CONTROL"
            return out

    cf = _s(state.get("challenger_formula_id"))
    raw, code = formula_notional(cf, inputs)
    out["challenger_notional_raw"] = raw
    if raw is None or code != "OK":
        out["ok"] = False
        out["blocked"] = True
        out["reason_code"] = code or BLOCKED_NON_FINITE_QTY
        out["executed_notional"] = 0.0
        out["deployment"] = deployment_metadata(state, selection_reason=out["reason_code"])
        return out

    pct = _f(state.get("capital_allocation_pct"))
    limit = _f(state.get("capital_limit"))
    exposed = max(0.0, _f(state.get("challenger_exposure_usd")))
    residual = max(0.0, limit - exposed) if limit > 0 else None
    capped = raw * (pct / 100.0)
    if residual is not None:
        capped = min(capped, residual)
    # Also never exceed control cash envelope already reflected in inputs
    cash = inputs.get("cash_available")
    reserve = inputs.get("cash_reserve")
    if cash is not None:
        investable = max(0.0, _f(cash) - _f(reserve))
        capped = min(capped, investable)
    max_pos = inputs.get("maximum_position_notional")
    if max_pos is not None:
        capped = min(capped, _f(max_pos))
    # V2 tranche: control_notional is already the tranche cap — never exceed it
    if _s(arm).upper() == "V2":
        capped = min(capped, float(control_notional))

    if not math.isfinite(capped) or capped <= 0:
        fallback = _control_fallback_response(
            out,
            state=state,
            control_notional=control_notional,
            inputs=inputs,
            arm=arm_u,
            selection_reason=CONTROL_FALLBACK_CAPITAL_EXHAUSTED,
            scope_result=SCOPE_RESULT_IN_SCOPE,
            ticker_scope_match=True,
        )
        if not fallback.get("blocked"):
            fallback["capital_limit"] = limit
            fallback["challenger_exposure_usd"] = exposed
            fallback["residual_capital_limit"] = residual
            return fallback
        out["ok"] = False
        out["blocked"] = True
        out["reason_code"] = BLOCKED_CAPITAL_CAP if capped <= 0 else BLOCKED_NON_FINITE_QTY
        out["executed_notional"] = 0.0
        out["deployment"] = deployment_metadata(state, selection_reason=out["reason_code"])
        out["capital_limit"] = limit
        out["challenger_exposure_usd"] = exposed
        out["residual_capital_limit"] = residual
        return out

    out["executed_notional"] = round(float(capped), 6)
    out["used_arm"] = "CHALLENGER"
    out["decision"] = "USE_CHALLENGER"
    out["scope_result"] = SCOPE_RESULT_IN_SCOPE
    out["ticker_scope_match"] = True
    out["challenger_exposure"] = True
    out["adaptive_arm"] = "CHALLENGER"
    out["adaptive_reason"] = f"challenger:{cf}:pct={pct}:cap={limit}:residual={residual}"
    out["capital_limit"] = limit
    out["challenger_exposure_usd"] = exposed
    out["residual_capital_limit"] = residual
    out["deployment"] = deployment_metadata(
        state,
        selection_reason=f"challenger:{cf}:pct={pct}:cap={limit}:residual={residual}",
    )
    # Ensure formula fields reflect challenger
    out["deployment"]["formula_id"] = cf
    out["deployment"]["formula_version"] = state.get("challenger_formula_version")
    out["deployment"]["experiment_arm"] = "CHALLENGER"
    return out


def maybe_auto_rollback_critical(
    *,
    reason: str,
    root: Path | None = None,
) -> dict[str, Any] | None:
    state = load_state(root=root)
    if _s(state.get("deployment_state")) not in ACTIVE_BUY_STATES | {ST_PAUSED}:
        return None
    return rollback_deployment(reason=reason, actor="auto_critical", root=root, automatic=True)


def status_report(*, root: Path | None = None) -> dict[str, Any]:
    state = load_state(root=root)
    lkg = load_lkg(root=root)
    lok, lerrs = validate_lkg(lkg)
    exp = ensure_experiment_registry(root=root)
    ok, errs = validate_state(state)
    return {
        "schema": "tae.adaptive_deployment.status.v1",
        "mode": MODE,
        "paper_only": True,
        "live_allowed": False,
        "state_ok": ok,
        "state_errors": errs,
        "deployment": state,
        "lkg_ok": lok,
        "lkg_errors": lerrs,
        "lkg": lkg,
        "experiment": exp,
        "registered_formulas": sorted(REGISTERED_FORMULAS.keys()),
        "supported_states": sorted(SUPPORTED_STATES),
        "active_buy_states": sorted(ACTIVE_BUY_STATES),
        "paths": {k: str(v) for k, v in paths(root).items()},
    }


def history(*, root: Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    p = paths(root)["history"]
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-limit:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def validate_only(*, root: Path | None = None, mode: str = "current") -> dict[str, Any]:
    """Validate deployment.

    mode=current — is the existing deployment coherent/healthy?
    mode=activation — can a *new* PAPER_CHALLENGER activation proceed?
    """
    st = status_report(root=root)
    dep = st["deployment"]
    mode_n = _s(mode).lower() or "current"
    if mode_n in {"activate", "new", "transition"}:
        mode_n = "activation"

    if mode_n == "activation":
        vetoes = evaluate_vetoes(
            state=dep,
            target_state=ST_PAPER_CHALLENGER,
            require_lkg=True,
            formula_id=_s(dep.get("challenger_formula_id")) or None,
            validation_mode="transition",
            root=root,
        )
        ok = not vetoes.get("blocked")
        status_label = (
            BLOCKED_NEW_ACTIVATION_ACTIVE_DEPLOYMENT
            if BLOCKED_ACTIVE_DEPLOYMENT in (vetoes.get("reason_codes") or [])
            else ("ACTIVATION_ALLOWED" if ok else "ACTIVATION_BLOCKED")
        )
        return {
            "ok": ok,
            "mode": "activation",
            "status_label": status_label,
            "status": st,
            "vetoes": vetoes,
        }

    # current health
    cur = _s(dep.get("deployment_state"))
    require_lkg = cur in ACTIVE_BUY_STATES
    # Detect raw disk LIVE flag before load_state clamps it (fail closed).
    raw_disk = _load_json(paths(root)["state"]) or {}
    raw_live = _b(raw_disk.get("live_allowed")) if isinstance(raw_disk, dict) else False
    vetoes = evaluate_vetoes(
        state=dep,
        target_state=cur if cur in ACTIVE_BUY_STATES else None,
        require_lkg=require_lkg,
        formula_id=_s(dep.get("challenger_formula_id")) or None,
        validation_mode="current",
        live_requested=raw_live,
        root=root,
    )
    if raw_live and BLOCKED_LIVE_LOCK not in (vetoes.get("reason_codes") or []):
        vetoes = dict(vetoes)
        codes = list(vetoes.get("reason_codes") or [])
        codes.append(BLOCKED_LIVE_LOCK)
        vetoes["reason_codes"] = sorted(set(codes))
        vetoes["LIVE_LOCK"] = "FAIL"
        vetoes["blocked"] = True
    ok = bool(st["state_ok"]) and not vetoes.get("blocked")
    if cur == ST_DRAFT and BLOCKED_LIVE_LOCK in (vetoes.get("reason_codes") or []):
        ok = False
    return {
        "ok": ok,
        "mode": "current",
        "status_label": VALID_CURRENT_DEPLOYMENT if ok else "INVALID_CURRENT_DEPLOYMENT",
        "status": st,
        "vetoes": vetoes,
    }


def economic_monitor_stub(
    *,
    control_metrics: dict[str, Any] | None = None,
    challenger_metrics: dict[str, Any] | None = None,
    pre_deployment: dict[str, Any] | None = None,
    post_deployment: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """
    REUSE existing economic monitors — structure only.
    Does not invent superiority; separates CONTROL vs CHALLENGER buckets.
    """
    state = load_state(root=root)
    return {
        "schema": "tae.adaptive_deployment.economic_monitor.v1",
        "deployment_id": state.get("deployment_id"),
        "deployment_version": state.get("deployment_version"),
        "formula_version_active": (
            state.get("challenger_formula_version")
            if _s(state.get("deployment_state")) in ACTIVE_BUY_STATES
            else state.get("active_formula_version")
        ),
        "CONTROL": control_metrics or {},
        "CHALLENGER": challenger_metrics or {},
        "PRE_DEPLOYMENT": pre_deployment or {},
        "POST_DEPLOYMENT": post_deployment or {},
        "note": "Populate from tae_paper_economic_attribution / ROI queue — measurement only",
        "statistical_superiority_declared": False,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="TAE Adaptive Deployment SSOT (PAPER_ONLY)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    p_val = sub.add_parser("validate")
    p_val.add_argument(
        "--mode",
        choices=["current", "activation"],
        default="current",
        help="current=health of existing deployment; activation=can a new challenger be activated",
    )
    sub.add_parser("history")

    p_act = sub.add_parser("activate")
    p_act.add_argument("--experiment-id", default=SHADOW_EXPERIMENT_ID)
    p_act.add_argument("--challenger-formula", required=True)
    p_act.add_argument("--capital-allocation-pct", type=float, required=True)
    p_act.add_argument("--capital-limit", type=float, default=0.0)
    p_act.add_argument("--ticker-scope", default="*")
    p_act.add_argument("--reason", default="cli_activate")
    p_act.add_argument("--data-quality-ok", action="store_true", default=True)
    p_act.add_argument("--data-quality-fail", action="store_true")
    p_act.add_argument("--reconciliation-fail", action="store_true")
    p_act.add_argument("--hard-risk-fail", action="store_true")

    p_pause = sub.add_parser("pause")
    p_pause.add_argument("--reason", required=True)

    p_rb = sub.add_parser("rollback")
    p_rb.add_argument("--reason", required=True)

    sub.add_parser("sync-dpe")
    p_roi = sub.add_parser("sync-roi")
    p_roi.add_argument("--apply", action="store_true")

    args = parser.parse_args(argv)
    root = resolve_root()

    if args.cmd == "status":
        rep = status_report(root=root)
        print(json.dumps(rep, indent=2, default=str))
        d = rep["deployment"]
        print(
            f"\nSTATE={d.get('deployment_state')} VER={d.get('deployment_version')} "
            f"ACTIVE={d.get('active_formula_id')} CHALLENGER={d.get('challenger_formula_id')} "
            f"LKG={rep.get('lkg', {}).get('lkg_version') if rep.get('lkg') else None} "
            f"LIVE_ALLOWED=false"
        )
        return 0

    if args.cmd == "validate":
        rep = validate_only(root=root, mode=getattr(args, "mode", "current"))
        print(json.dumps(rep, indent=2, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "history":
        print(json.dumps(history(root=root), indent=2, default=str))
        return 0

    if args.cmd == "activate":
        res = activate_challenger(
            experiment_id=args.experiment_id,
            challenger_formula=args.challenger_formula,
            capital_allocation_pct=args.capital_allocation_pct,
            capital_limit=args.capital_limit,
            ticker_scope=args.ticker_scope,
            reason=args.reason,
            hard_risk_ok=not args.hard_risk_fail,
            reconciliation_ok=not args.reconciliation_fail,
            data_quality_ok=not args.data_quality_fail,
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1

    if args.cmd == "pause":
        res = pause_deployment(reason=args.reason)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1

    if args.cmd == "rollback":
        res = rollback_deployment(reason=args.reason)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1

    if args.cmd == "sync-dpe":
        print(json.dumps(sync_dpe_recommendation(root=root), indent=2, default=str))
        return 0

    if args.cmd == "sync-roi":
        print(json.dumps(sync_roi_connection(root=root, apply=bool(args.apply)), indent=2, default=str))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
