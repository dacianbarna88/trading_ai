#!/usr/bin/env python3
"""
Strategy V2 feature-flag SSOT.

Owner: tae_strategy_v2_config.py (+ tae_strategy_v2_config.json)
Default: STRATEGY_V2_ENABLED = false

Environment variables are intentionally ignored so unknown envs cannot
accidentally activate V2. Tests may pass override=True explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("tae_strategy_v2_config.json")
CONFIG_SCHEMA = "tae.strategy_v2.config.v1"

_DEFAULTS: dict[str, Any] = {
    "schema": CONFIG_SCHEMA,
    "STRATEGY_V2_ENABLED": False,
    "MIN_CASH_RESERVE_USD": 500.0,
    "MONEY_TOLERANCE_USD": 0.01,
    "MARK_MAX_AGE_SECONDS": 3600.0,
    "DEFAULT_MAX_TRANCHES": 5,
    "policy_version": "buy_policy.v2_price_driven",
    "exit_policy_version": "exit_policy.v1",
    "tranche_fraction": 0.20,
    "max_tranches": 5,
    "add_tranche_drop_pct": 0.03,
    "minimum_company_budget": 500.0,
    "maximum_company_budget": 2500.0,
    "min_order_value_usd": 250.0,
    "max_order_value_usd": 2500.0,
    "thesis_unknown_blocks_entry": True,
    "minimum_cycle_profit_pct": 0.10,
    "profit_reference": "aggregate_average_cost",
    "close_fraction": 1.0,
    "thesis_invalid_exit": True,
    "hard_risk_exit": True,
    "REENTRY_PULLBACK_PCT": 3.0,
    "REENTRY_BREAKOUT_PCT": 1.0,
    "REENTRY_COOLDOWN_SECONDS": 3600,
    "REENTRY_SLIPPAGE_BPS": 5.0,
    "REENTRY_COMMISSION_USD": 0.0,
}


def load_strategy_v2_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    payload = dict(_DEFAULTS)
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    # Hard-normalize: never trust accidental truthy strings from malformed files
    # without explicit boolean true.
    enabled = payload.get("STRATEGY_V2_ENABLED", False)
    if enabled is True or enabled == 1:
        payload["STRATEGY_V2_ENABLED"] = True
    elif isinstance(enabled, str) and enabled.strip().lower() in {"true", "1", "yes", "on"}:
        # File-explicit string only (still requires the config file). Not env.
        payload["STRATEGY_V2_ENABLED"] = True
    else:
        payload["STRATEGY_V2_ENABLED"] = False
    payload["MIN_CASH_RESERVE_USD"] = float(payload.get("MIN_CASH_RESERVE_USD") or 500.0)
    payload["MONEY_TOLERANCE_USD"] = float(payload.get("MONEY_TOLERANCE_USD") or 0.01)
    payload["MARK_MAX_AGE_SECONDS"] = float(payload.get("MARK_MAX_AGE_SECONDS") or 3600.0)
    payload["DEFAULT_MAX_TRANCHES"] = int(payload.get("DEFAULT_MAX_TRANCHES") or 5)
    payload["policy_version"] = str(payload.get("policy_version") or "buy_policy.v1")
    payload["tranche_fraction"] = float(payload.get("tranche_fraction") or 0.20)
    payload["max_tranches"] = int(payload.get("max_tranches") or payload["DEFAULT_MAX_TRANCHES"])
    payload["add_tranche_drop_pct"] = float(payload.get("add_tranche_drop_pct") or 0.03)
    payload["minimum_company_budget"] = float(payload.get("minimum_company_budget") or 500.0)
    payload["maximum_company_budget"] = float(payload.get("maximum_company_budget") or 2500.0)
    payload["min_order_value_usd"] = float(payload.get("min_order_value_usd") or 250.0)
    payload["max_order_value_usd"] = float(payload.get("max_order_value_usd") or 2500.0)
    unk = payload.get("thesis_unknown_blocks_entry", True)
    payload["thesis_unknown_blocks_entry"] = bool(unk is True or unk == 1 or str(unk).lower() in {"true", "1", "yes"})
    payload["exit_policy_version"] = str(payload.get("exit_policy_version") or "exit_policy.v1")
    payload["minimum_cycle_profit_pct"] = float(payload.get("minimum_cycle_profit_pct") if payload.get("minimum_cycle_profit_pct") is not None else 0.10)
    payload["profit_reference"] = str(payload.get("profit_reference") or "aggregate_average_cost")
    payload["close_fraction"] = float(payload.get("close_fraction") if payload.get("close_fraction") is not None else 1.0)
    tiv = payload.get("thesis_invalid_exit", True)
    payload["thesis_invalid_exit"] = bool(tiv is True or tiv == 1 or str(tiv).lower() in {"true", "1", "yes"})
    hre = payload.get("hard_risk_exit", True)
    payload["hard_risk_exit"] = bool(hre is True or hre == 1 or str(hre).lower() in {"true", "1", "yes"})
    return payload


def is_strategy_v2_enabled(
    *,
    path: Path | None = None,
    override: bool | None = None,
) -> bool:
    """Return enablement. Env vars are ignored. Tests use override=."""
    if override is not None:
        return bool(override)
    return bool(load_strategy_v2_config(path).get("STRATEGY_V2_ENABLED") is True)


def feature_flag_owner() -> str:
    return "tae_strategy_v2_config.py / tae_strategy_v2_config.json"
