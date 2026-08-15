#!/usr/bin/env python3
"""
Canonical PAPER transaction cost model — SSOT for V1/V2 paper fills.

PAPER_ONLY | NO_BROKER | DETERMINISTIC | NO_LIVE_SIDE_EFFECTS

Reuses the economic semantics demonstrated by
``tae_strategy_v2_reentry_policy.apply_transaction_costs`` (bps drag + optional USD)
and the ablation bps vocabulary (commission_bps / slippage_bps), unified into one
pure function for BUY and SELL fills.
"""

from __future__ import annotations

import os
from typing import Any

COST_MODEL_VERSION = "paper_tx_cost.v1"

# Canonical defaults: match existing V2 reentry helper (5 bps slippage, $0 commission).
# Ablation's extra commission_bps=2 remains available via config (not forced).
DEFAULT_CONFIG: dict[str, Any] = {
    "PAPER_TX_COST_ENABLED": True,
    "PAPER_SLIPPAGE_BPS": 5.0,
    "PAPER_SPREAD_BPS": 0.0,
    "PAPER_COMMISSION_BPS": 0.0,
    "PAPER_COMMISSION_USD": 0.0,
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if out != out or out in (float("inf"), float("-inf")):  # NaN/Inf
        return float(default)
    return out


def load_paper_tx_cost_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge defaults ← parallel paper config (if present) ← overrides ← env kill-switch."""
    cfg = dict(DEFAULT_CONFIG)
    try:
        from tae_parallel_paper_config import load_parallel_paper_config

        file_cfg = load_parallel_paper_config() or {}
        for key in DEFAULT_CONFIG:
            if key in file_cfg:
                cfg[key] = file_cfg[key]
        # Map legacy V2 reentry keys when paper keys absent
        if "PAPER_SLIPPAGE_BPS" not in (file_cfg or {}) and "REENTRY_SLIPPAGE_BPS" in file_cfg:
            cfg["PAPER_SLIPPAGE_BPS"] = file_cfg["REENTRY_SLIPPAGE_BPS"]
        if "PAPER_COMMISSION_USD" not in (file_cfg or {}) and "REENTRY_COMMISSION_USD" in file_cfg:
            cfg["PAPER_COMMISSION_USD"] = file_cfg["REENTRY_COMMISSION_USD"]
    except Exception:
        pass
    if overrides:
        cfg.update({k: overrides[k] for k in overrides if k in DEFAULT_CONFIG or k.startswith("PAPER_") or k.startswith("REENTRY_")})
        # Allow callers to pass REENTRY_* directly
        if "REENTRY_SLIPPAGE_BPS" in overrides and "PAPER_SLIPPAGE_BPS" not in overrides:
            cfg["PAPER_SLIPPAGE_BPS"] = overrides["REENTRY_SLIPPAGE_BPS"]
        if "REENTRY_COMMISSION_USD" in overrides and "PAPER_COMMISSION_USD" not in overrides:
            cfg["PAPER_COMMISSION_USD"] = overrides["REENTRY_COMMISSION_USD"]
    env = os.getenv("PAPER_TX_COST_ENABLED")
    if env is not None:
        cfg["PAPER_TX_COST_ENABLED"] = env.strip().lower() not in {"0", "false", "no", "off"}
    return cfg


def total_bps(cfg: dict[str, Any] | None = None) -> float:
    cfg = cfg or load_paper_tx_cost_config()
    return (
        max(0.0, _f(cfg.get("PAPER_SLIPPAGE_BPS")))
        + max(0.0, _f(cfg.get("PAPER_SPREAD_BPS")))
        + max(0.0, _f(cfg.get("PAPER_COMMISSION_BPS")))
    )


def compute_transaction_cost(
    notional: float,
    *,
    side: str | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Pure deterministic cost breakdown for one fill (BUY or SELL).

    total = |notional| * (slippage+spread+commission)_bps / 10000 + commission_usd
    """
    cfg = load_paper_tx_cost_config(cfg)
    enabled = bool(cfg.get("PAPER_TX_COST_ENABLED", True))
    gross = abs(_f(notional))
    slip_bps = max(0.0, _f(cfg.get("PAPER_SLIPPAGE_BPS")))
    spread_bps = max(0.0, _f(cfg.get("PAPER_SPREAD_BPS")))
    commission_bps = max(0.0, _f(cfg.get("PAPER_COMMISSION_BPS")))
    commission_usd = max(0.0, _f(cfg.get("PAPER_COMMISSION_USD")))
    if not enabled or gross <= 0:
        slip_bps = spread_bps = commission_bps = commission_usd = 0.0
    slip_cost = round(gross * (slip_bps / 10000.0), 6)
    spread_cost = round(gross * (spread_bps / 10000.0), 6)
    commission_bps_cost = round(gross * (commission_bps / 10000.0), 6)
    total = round(slip_cost + spread_cost + commission_bps_cost + commission_usd, 6)
    if total < 0:
        total = 0.0
    return {
        "cost_model_version": COST_MODEL_VERSION,
        "side": (side or "").upper() or None,
        "enabled": enabled,
        "gross_notional": round(gross, 6),
        "slippage_bps": slip_bps,
        "spread_bps": spread_bps,
        "commission_bps": commission_bps,
        "commission_usd": commission_usd,
        "slippage_cost": slip_cost,
        "spread_cost": spread_cost,
        "commission_cost": round(commission_bps_cost + commission_usd, 6),
        "total_transaction_cost": total,
        "cost_configuration": {
            "PAPER_TX_COST_ENABLED": enabled,
            "PAPER_SLIPPAGE_BPS": slip_bps,
            "PAPER_SPREAD_BPS": spread_bps,
            "PAPER_COMMISSION_BPS": commission_bps,
            "PAPER_COMMISSION_USD": commission_usd,
        },
    }


def apply_transaction_costs(
    notional: float,
    *,
    cfg: dict[str, Any] | None = None,
    side: str | None = None,
) -> float:
    """Compatibility alias — same contract as V2 reentry helper (float total)."""
    return float(compute_transaction_cost(notional, side=side, cfg=cfg)["total_transaction_cost"])


def max_affordable_notional(cash: float, *, cfg: dict[str, Any] | None = None) -> float:
    """Largest gross notional such that notional + cost(notional) <= cash."""
    cfg = load_paper_tx_cost_config(cfg)
    cash = max(0.0, _f(cash))
    if not bool(cfg.get("PAPER_TX_COST_ENABLED", True)):
        return cash
    commission_usd = max(0.0, _f(cfg.get("PAPER_COMMISSION_USD")))
    rate = total_bps(cfg) / 10000.0
    investable = cash - commission_usd
    if investable <= 0:
        return 0.0
    if rate <= 0:
        return round(investable, 6)
    return round(investable / (1.0 + rate), 6)


def buy_cash_debit(gross_notional: float, *, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    detail = compute_transaction_cost(gross_notional, side="BUY", cfg=cfg)
    debit = round(_f(gross_notional) + _f(detail["total_transaction_cost"]), 6)
    detail["net_cash_movement"] = -debit
    detail["cash_debit"] = debit
    return detail


def sell_cash_credit(gross_proceeds: float, *, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    detail = compute_transaction_cost(gross_proceeds, side="SELL", cfg=cfg)
    credit = round(_f(gross_proceeds) - _f(detail["total_transaction_cost"]), 6)
    detail["net_cash_movement"] = credit
    detail["cash_credit"] = credit
    detail["net_proceeds"] = credit
    return detail
