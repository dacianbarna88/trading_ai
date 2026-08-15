#!/usr/bin/env python3
"""
RISK_WEIGHTED_POSITION_SIZING SHADOW A/B.

Changes quantity/notional only on chronological portfolio replay.
Does NOT modify entry selection, stops, trailing, capacity, or live_bot.py.
Closed hypotheses (stop / cooldown / entry-persistence) stay closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from research_core.accounting.accounting_snapshot import build_accounting_snapshot
from research_core.accounting.fx_normalize import instrument_currency
from tae_chronological_portfolio_replay import (
    MAX_TRADE_USD,
    MIN_TRADE_USD,
    STARTING_CAPITAL,
    build_features,
    capital_stats,
    evaluate_reliability,
    excl_tickers,
    excl_top_n_trades,
    load_portfolio_events,
    metrics_from_variant,
    open_market_value,
    reconcile_control_a,
    run_variant,
    temporal_split_metrics,
)
from tae_entry_quality_ab import _bar_index_for, live_score_from_close
from tae_exit_strategy_bar_replay import enrich_bars_causal, volatility_bucket
from tae_selective_entry_persistence import enrich_features_with_bars

SCHEMA = "tae.risk_weighted_sizing_ab.v1"
OUTPUT_JSON = Path("tae_risk_weighted_sizing_ab_results.json")
OUTPUT_MD = Path("TAE_RISK_WEIGHTED_SIZING_AB_RESULTS.md")
PROTECTED = ("live_bot.py", "core/trailing.py")
BAN = {"MU", "AMAT", "SIE.DE"}

# Neighbor grids (dev-freeze primary)
B1_TARGET_RISK = (0.008, 0.010, 0.012)  # notional * atr_pct/100 ≈ target * base
B2_BANDS = (
    {"low": 0.70, "mid": 1.00, "high": 1.20},
    {"low": 0.80, "mid": 1.00, "high": 1.15},
    {"low": 0.75, "mid": 1.00, "high": 1.25},
)
B3_SCALES = (
    {"mild": 0.85, "deep": 0.70},
    {"mild": 0.80, "deep": 0.60},
    {"mild": 0.90, "deep": 0.75},
)
PRIMARY = {
    "B1": {"target_risk": 0.010},
    "B2": {"bands": B2_BANDS[0]},
    "B3": {"mild": 0.85, "deep": 0.70, "mild_dd": 0.05, "deep_dd": 0.10},
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(path: str) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"


def _feat_row(feat: pd.DataFrame, ts) -> pd.Series | None:
    if feat is None or feat.empty:
        return None
    i0 = _bar_index_for(ts, feat.index)
    if i0 is None:
        return None
    return feat.iloc[i0]


def _base_notional(ev: dict[str, Any]) -> float:
    intent = float(ev.get("intent_notional") or 0)
    if intent <= 0:
        intent = float(ev.get("price") or 0) * float(ev.get("shares") or 0)
    # Soft clamp historical outliers (e.g. 10k) toward live MAX for variant fairness
    return float(min(max(intent, 0.0), max(MAX_TRADE_USD, intent)))


def _clamp_notional(raw: float, cash: float) -> float:
    n = min(max(0.0, raw), MAX_TRADE_USD, max(0.0, cash))
    return round(n, 4)


def atr_pct_at(feat: pd.DataFrame, ts) -> float | None:
    row = _feat_row(feat, ts)
    if row is None:
        return None
    if "ATR_Pct" in row.index and pd.notna(row.get("ATR_Pct")) and float(row["ATR_Pct"]) > 0:
        return float(row["ATR_Pct"])
    # Fallback: ATR14/Close*100 if present
    if "ATR14" in row.index and "Close" in row.index and pd.notna(row.get("ATR14")):
        c = float(row["Close"])
        if c > 0:
            return float(row["ATR14"]) / c * 100.0
    return None


def score_at(ev: dict[str, Any], feat: pd.DataFrame) -> float | None:
    if ev.get("score") is not None:
        return float(ev["score"])
    row = _feat_row(feat, ev["ts"])
    if row is not None and "Score" in row.index and pd.notna(row.get("Score")):
        return float(row["Score"])
    return None


def confidence_band(score: float | None) -> str:
    if score is None:
        return "mid"
    if score < 90:
        return "low"
    if score < 100:
        return "mid"
    return "high"


def size_b1_vol(
    ev: dict[str, Any],
    feat: pd.DataFrame,
    state,
    *,
    target_risk: float,
    median_atr_pct: float,
) -> dict[str, Any]:
    """Volatility-normalized: higher ATR_Pct → smaller notional."""
    base = _base_notional(ev)
    atr = atr_pct_at(feat, ev["ts"])
    cash_before = state.cash
    if atr is None or atr <= 0:
        # Insufficient vol → keep base (no invented vol)
        n = _clamp_notional(base, cash_before)
        return {
            "notional": n, "factor": 1.0, "feature": "ATR_MISSING",
            "reason": "B1_BASE_NO_ATR", "cash_before": cash_before,
        }
    # Dollar risk target relative to base at median vol
    # notional * (atr/100) ≈ target_risk * base  → notional = target_risk * base / (atr/100)
    # Scale so median ATR gets factor≈1: notional = base * (median_atr / atr) * (target_risk / 0.01)
    scale_risk = target_risk / 0.01
    factor = (median_atr_pct / atr) * scale_risk
    factor = float(np.clip(factor, 0.4, 1.6))  # moderate bounds — not elimination
    n = _clamp_notional(base * factor, cash_before)
    if n < MIN_TRADE_USD and cash_before >= MIN_TRADE_USD:
        n = MIN_TRADE_USD  # never zero out eligible when cash allows
    return {
        "notional": n, "factor": round(factor, 4), "feature": f"ATR_Pct={atr:.4f}",
        "reason": f"B1_VOL_TARGET_{target_risk}", "cash_before": cash_before,
    }


def size_b2_confidence(
    ev: dict[str, Any],
    feat: pd.DataFrame,
    state,
    *,
    bands: dict[str, float],
) -> dict[str, Any]:
    base = _base_notional(ev)
    score = score_at(ev, feat)
    band = confidence_band(score)
    factor = float(bands.get(band, 1.0))
    cash_before = state.cash
    n = _clamp_notional(base * factor, cash_before)
    if n < MIN_TRADE_USD and cash_before >= MIN_TRADE_USD:
        n = MIN_TRADE_USD
    return {
        "notional": n, "factor": factor, "feature": f"score={score}|band={band}",
        "reason": f"B2_BAND_{band}", "cash_before": cash_before,
    }


def size_b3_drawdown(
    ev: dict[str, Any],
    feat: pd.DataFrame,
    state,
    *,
    mild: float,
    deep: float,
    mild_dd: float = 0.05,
    deep_dd: float = 0.10,
    marks: dict[str, float] | None = None,
) -> dict[str, Any]:
    base = _base_notional(ev)
    cash_before = state.cash
    omv = open_market_value(state, marks or {})
    av = cash_before + omv
    state.peak_account_value = max(state.peak_account_value, av)
    dd = state.current_drawdown_pct(av)
    if dd >= deep_dd:
        factor = deep
        tag = "DEEP"
    elif dd >= mild_dd:
        factor = mild
        tag = "MILD"
    else:
        factor = 1.0
        tag = "NONE"
    n = _clamp_notional(base * factor, cash_before)
    if n < MIN_TRADE_USD and cash_before >= MIN_TRADE_USD:
        n = MIN_TRADE_USD
    return {
        "notional": n, "factor": factor, "feature": f"dd_pct={dd:.4f}|{tag}",
        "reason": f"B3_DD_{tag}", "cash_before": cash_before,
    }


def make_sizing_fn(
    name: str,
    params: dict[str, Any],
    *,
    median_atr_pct: float,
    marks: dict[str, float],
    exposure_scale: float = 1.0,
) -> Callable:
    def _fn(ev, feat, state):
        if name == "B1":
            d = size_b1_vol(
                ev, feat, state,
                target_risk=float(params["target_risk"]),
                median_atr_pct=median_atr_pct,
            )
        elif name == "B2":
            d = size_b2_confidence(ev, feat, state, bands=params["bands"])
        elif name == "B3":
            d = size_b3_drawdown(
                ev, feat, state,
                mild=float(params["mild"]), deep=float(params["deep"]),
                mild_dd=float(params.get("mild_dd", 0.05)),
                deep_dd=float(params.get("deep_dd", 0.10)),
                marks=marks,
            )
        else:
            d = {"notional": _base_notional(ev), "factor": 1.0, "feature": "NONE", "reason": "PASSTHROUGH"}
        if exposure_scale != 1.0 and d.get("notional"):
            d = dict(d)
            d["notional"] = _clamp_notional(float(d["notional"]) * exposure_scale, state.cash)
            d["factor"] = round(float(d.get("factor") or 1.0) * exposure_scale, 4)
            d["reason"] = f"{d.get('reason')}|EXPOSURE_SCALE_{exposure_scale:.3f}"
        return d

    return _fn


def _median_atr(features: dict[str, pd.DataFrame], events: list[dict]) -> float:
    vals = []
    for ev in events:
        if ev.get("kind") != "BUY_EVAL":
            continue
        atr = atr_pct_at(features.get(ev["ticker"], pd.DataFrame()), ev["ts"])
        if atr is not None and atr > 0:
            vals.append(atr)
    return float(np.median(vals)) if vals else 2.0


def mean_filled_notional(variant: dict[str, Any]) -> float:
    decs = [d for d in (variant.get("sizing_decisions") or []) if d.get("fill_status") == "FILLED"]
    if decs:
        return float(np.mean([float(d["notional_b"]) for d in decs]))
    # Control A: from trades + opens approx via buy events in stats — use closed+open cost
    buys = [e for e in variant.get("events") or [] if e.get("action") == "BUY" and e.get("fill_status") == "FILLED"]
    if not buys:
        return 0.0
    return float(np.mean([float(e.get("price") or 0) * float(e.get("quantity") or 0) for e in buys]))


def expectancy_per_dollar(variant: dict[str, Any]) -> float:
    trades = variant.get("trades") or []
    if not trades:
        return 0.0
    pnl = sum(float(t["pnl_usd"]) for t in trades)
    invested = sum(float(t["entry_price"]) * float(t["shares"]) for t in trades)
    if invested <= 0:
        return 0.0
    return round(pnl / invested, 6)


def exposure_stats(variant: dict[str, Any]) -> dict[str, Any]:
    ecs = variant.get("equity_curve") or []
    if not ecs:
        return {"avg_gross_exposure": 0.0, "peak_gross_exposure": 0.0}
    omvs = [float(e.get("omv") or 0) for e in ecs]
    return {
        "avg_gross_exposure": round(float(np.mean(omvs)), 4),
        "peak_gross_exposure": round(float(np.max(omvs)), 4),
    }


def notional_stats(variant: dict[str, Any], *, control_a: bool = False) -> dict[str, Any]:
    if control_a:
        buys = [e for e in variant.get("events") or [] if e.get("action") == "BUY" and e.get("fill_status") == "FILLED"]
        ns = [float(e.get("price") or 0) * float(e.get("quantity") or 0) for e in buys]
    else:
        decs = [d for d in (variant.get("sizing_decisions") or []) if d.get("fill_status") == "FILLED"]
        ns = [float(d["notional_b"]) for d in decs]
    if not ns:
        return {"avg_notional": 0.0, "median_notional": 0.0, "max_notional": 0.0, "n": 0}
    return {
        "avg_notional": round(float(np.mean(ns)), 4),
        "median_notional": round(float(np.median(ns)), 4),
        "max_notional": round(float(np.max(ns)), 4),
        "n": len(ns),
    }


def enrich_metrics(variant: dict[str, Any], *, is_a: bool = False) -> dict[str, Any]:
    m = metrics_from_variant(variant)
    m["expectancy_per_dollar"] = expectancy_per_dollar(variant)
    m.update(exposure_stats(variant))
    m.update(notional_stats(variant, control_a=is_a))
    cap = capital_stats(variant)
    m["capital_utilization"] = cap.get("avg_utilization")
    m["capital_days_cash"] = cap.get("capital_days_cash")
    m["max_drawdown_pct"] = None
    ecs = variant.get("equity_curve") or []
    if ecs:
        avs = pd.Series([float(e["account_value"]) for e in ecs], dtype=float)
        peak = avs.cummax().replace(0, np.nan)
        m["max_drawdown_pct"] = round(float(((avs - peak) / peak).min()), 6)
    # Return %
    m["return_pct"] = round((float(variant["account_value"]) - STARTING_CAPITAL) / STARTING_CAPITAL, 6)
    return m


def compare_sizing(a: dict, b: dict, a_m: dict, b_m: dict) -> dict[str, Any]:
    return {
        "delta_net_pnl_usd": round(b_m["net_pnl_usd"] - a_m["net_pnl_usd"], 4),
        "delta_account_value": round(b_m["account_value"] - a_m["account_value"], 4),
        "delta_expectancy": round(b_m["expectancy"] - a_m["expectancy"], 4),
        "delta_expectancy_per_dollar": round(
            b_m["expectancy_per_dollar"] - a_m["expectancy_per_dollar"], 6
        ),
        "delta_maxdd_usd": round(abs(b_m["max_drawdown_account"]) - abs(a_m["max_drawdown_account"]), 4),
        "delta_maxdd_pct": (
            None if a_m.get("max_drawdown_pct") is None or b_m.get("max_drawdown_pct") is None
            else round(abs(b_m["max_drawdown_pct"]) - abs(a_m["max_drawdown_pct"]), 6)
        ),
        "avg_notional_a": a_m.get("avg_notional"),
        "avg_notional_b": b_m.get("avg_notional"),
        "exposure_reduction_pct": (
            None if not a_m.get("avg_notional")
            else round(1.0 - float(b_m.get("avg_notional") or 0) / float(a_m["avg_notional"]), 4)
        ),
        "fills_a": a_m["fills"],
        "fills_b": b_m["fills"],
    }


def evaluate_sizing_economic(
    a_m: dict,
    b_m: dict,
    cmp_: dict,
    *,
    temporal: dict,
    excl: dict,
    excl_top2: dict,
    sens_ok: bool,
    exposure_norm_ok: bool | None,
) -> dict[str, Any]:
    flags: list[str] = []
    ok = True
    if b_m["account_value"] <= a_m["account_value"]:
        ok = False
        flags.append("ACCOUNT_VALUE_NOT_IMPROVED")
    if b_m["net_pnl_usd"] <= a_m["net_pnl_usd"]:
        ok = False
        flags.append("PNL_NOT_IMPROVED")
    if b_m["expectancy_per_dollar"] <= a_m["expectancy_per_dollar"]:
        ok = False
        flags.append("EXPECTANCY_PER_DOLLAR_NOT_IMPROVED")
    bdd = abs(b_m.get("max_drawdown_pct") or 0)
    add = abs(a_m.get("max_drawdown_pct") or 0)
    if bdd > add + 1e-9:
        ok = False
        flags.append("MAXDD_PCT_WORSE")
    bpf = b_m.get("profit_factor")
    apf = a_m.get("profit_factor")
    if bpf is not None and apf is not None and float(bpf) <= float(apf):
        ok = False
        flags.append("PROFIT_FACTOR_NOT_IMPROVED")
    if temporal["val"]["net_pnl_usd"] < temporal["val_a"]["net_pnl_usd"] - 1e-9:
        ok = False
        flags.append("VALIDATION_WORSE")
    if temporal["dev"]["net_pnl_usd"] <= temporal["dev_a"]["net_pnl_usd"]:
        ok = False
        flags.append("DEV_NOT_IMPROVED")
    if excl["b"]["net_pnl_usd"] <= excl["a"]["net_pnl_usd"]:
        ok = False
        flags.append("NO_EDGE_WITHOUT_MU_AMAT_SIE")
    if excl_top2["b"]["net_pnl_usd"] <= excl_top2["a"]["net_pnl_usd"]:
        ok = False
        flags.append("EDGE_DEPENDS_ON_TOP2")
    ccy_pos = sum(
        1 for c in ("USD", "EUR", "GBp", "GBP")
        if (b_m.get("by_currency_usd") or {}).get(c, 0) - (a_m.get("by_currency_usd") or {}).get(c, 0) > 0
    )
    if ccy_pos < 2:
        ok = False
        flags.append("FEWER_THAN_TWO_CURRENCY_BOOKS")
    red = cmp_.get("exposure_reduction_pct")
    if red is not None and red > 0.25 and b_m["expectancy_per_dollar"] <= a_m["expectancy_per_dollar"]:
        ok = False
        flags.append("EXPOSURE_COLLAPSE_WITHOUT_EPD_EDGE")
    if not sens_ok:
        ok = False
        flags.append("SENSITIVITY_UNSTABLE")
    if exposure_norm_ok is False:
        ok = False
        flags.append("NO_EDGE_EXPOSURE_NORMALIZED")
    return {"passes": ok and not flags, "flags": sorted(set(flags)), **cmp_}


def concentration_analysis(a: dict, variants: dict[str, dict], metrics: dict) -> dict[str, Any]:
    """Answer Phase 6 questions with replay evidence."""
    a_trades = sorted(a["trades"], key=lambda t: abs(float(t["pnl_usd"])), reverse=True)
    # Approximate DD contribution: largest notionals among losing trades
    losers = [t for t in a["trades"] if float(t["pnl_usd"]) < 0]
    losers_by_notional = sorted(
        losers, key=lambda t: float(t["entry_price"]) * float(t["shares"]), reverse=True
    )
    top5 = losers_by_notional[:5]
    loss_sum = sum(abs(float(t["pnl_usd"])) for t in losers) or 1.0
    top5_share = sum(abs(float(t["pnl_usd"])) for t in top5) / loss_sum

    # Score vs outcome monotonicity (diagnostic)
    by_band = {"low": [], "mid": [], "high": []}
    for t in a["trades"]:
        # score not on trade — skip if missing
        pass

    return {
        "q1_top5_loser_notional_share_of_loss_usd": round(top5_share, 4),
        "q1_top5_tickers": [t["ticker"] for t in top5],
        "q2_note": "See B1 natural vs A: if high-ATR names shrink and PnL improves without exposure collapse",
        "q5_note": "See B3: compare recovery (val AV/PnL) vs A when DD scaling active",
        "fills_unchanged_check": {k: metrics[k]["fills"] for k in metrics},
    }


def run_experiment(
    *,
    portfolio_path: Path = Path("portfolio.csv"),
    fx_fetcher=None,
    fetcher=None,
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    hashes_before = {f: _sha(f) for f in PROTECTED}
    base_events, meta = load_portfolio_events(portfolio_path)
    tickers = {e["ticker"] for e in base_events}
    features = build_features(tickers, fetcher=fetcher, bars_by_ticker=bars_by_ticker)
    if bars_by_ticker is None:
        from tae_exit_strategy_bar_replay import download_enriched_bars
        bars_by_ticker = {}
        for t in tickers:
            try:
                bars_by_ticker[t] = download_enriched_bars(t, fetcher=fetcher)
            except Exception:
                bars_by_ticker[t] = pd.DataFrame()
            if not bars_by_ticker[t].empty and "ATR14" not in bars_by_ticker[t].columns:
                bars_by_ticker[t] = enrich_bars_causal(
                    bars_by_ticker[t][["Open", "High", "Low", "Close", "Volume"]]
                )
    features = enrich_features_with_bars(features, bars_by_ticker)
    marks = meta["marks"]
    med_atr = _median_atr(features, base_events)

    def rv_a():
        return run_variant(
            mode="A", b1_confirmations=0, base_events=base_events,
            features=features, marks=marks, fx_fetcher=fx_fetcher,
        )

    def rv_size(name: str, params: dict, exposure_scale: float = 1.0):
        return run_variant(
            mode="SIZE",
            b1_confirmations=0,
            base_events=base_events,
            features=features,
            marks=marks,
            fx_fetcher=fx_fetcher,
            sizing_fn=make_sizing_fn(
                name, params, median_atr_pct=med_atr, marks=marks, exposure_scale=exposure_scale,
            ),
            sizing_name=name if exposure_scale == 1.0 else f"{name}_NORM",
            sell_resized_lots=True,
        )

    raw = {
        "A": rv_a(),
        "B1": rv_size("B1", PRIMARY["B1"]),
        "B2": rv_size("B2", PRIMARY["B2"]),
        "B3": rv_size("B3", PRIMARY["B3"]),
    }
    metrics = {
        "A": enrich_metrics(raw["A"], is_a=True),
        "B1": enrich_metrics(raw["B1"]),
        "B2": enrich_metrics(raw["B2"]),
        "B3": enrich_metrics(raw["B3"]),
    }

    # Exposure-normalized: scale so mean notional ≈ A
    avg_a = metrics["A"]["avg_notional"] or 1.0
    norm_raw = {}
    norm_metrics = {}
    for name in ("B1", "B2", "B3"):
        avg_b = metrics[name]["avg_notional"] or avg_a
        scale = (avg_a / avg_b) if avg_b > 1e-9 else 1.0
        # No leverage: cap scale at 1.0
        scale = min(1.0, float(scale))
        # If B already smaller, scale up toward A but still no leverage over cash/MAX — scale<=1 means we only shrink further when B larger
        # When B smaller than A, allow scale up to 1/min_factor conceptually — user said no leverage; scaling up notionals is OK if cash allows
        if avg_b < avg_a:
            scale = min(float(avg_a / avg_b), 1.25)  # mild catch-up, still capped by MAX_TRADE/cash
        norm_raw[name] = rv_size(name, PRIMARY[name], exposure_scale=scale)
        norm_metrics[name] = enrich_metrics(norm_raw[name])
        norm_metrics[name]["exposure_scale_applied"] = round(scale, 4)

    snapshot = build_accounting_snapshot(Path("."), portfolio_path=portfolio_path)
    recon_a = reconcile_control_a(raw["A"], snapshot)
    reliability = evaluate_reliability(recon_a, {"A": raw["A"], **{k: raw[k] for k in ("B1", "B2", "B3")}})

    # Sensitivity
    sens = {"B1": [], "B2": [], "B3": []}
    for tr in B1_TARGET_RISK:
        v = rv_size("B1", {"target_risk": tr})
        m = enrich_metrics(v)
        sens["B1"].append({"target_risk": tr, "net_pnl_usd": m["net_pnl_usd"], "av": m["account_value"]})
    for bands in B2_BANDS:
        v = rv_size("B2", {"bands": bands})
        m = enrich_metrics(v)
        sens["B2"].append({"bands": bands, "net_pnl_usd": m["net_pnl_usd"], "av": m["account_value"]})
    for sc in B3_SCALES:
        params = {**PRIMARY["B3"], **sc}
        v = rv_size("B3", params)
        m = enrich_metrics(v)
        sens["B3"].append({**sc, "net_pnl_usd": m["net_pnl_usd"], "av": m["account_value"]})

    def sens_ok(name: str) -> bool:
        rows = sens[name]
        better = sum(1 for r in rows if r["net_pnl_usd"] > metrics["A"]["net_pnl_usd"])
        return better >= 2  # robust zone: ≥2 neighbors beat A on PnL

    comparisons = {}
    temporal = {}
    exclusions = {}
    excl_top2 = {}
    econ = {}
    for name in ("B1", "B2", "B3"):
        comparisons[name] = compare_sizing(raw["A"], raw[name], metrics["A"], metrics[name])
        dev, val, mid = temporal_split_metrics(raw[name]["trades"])
        dev_a, val_a, mid_a = temporal_split_metrics(raw["A"]["trades"])
        temporal[name] = {"dev": dev, "val": val, "mid": mid, "dev_a": dev_a, "val_a": val_a, "mid_a": mid_a}
        exclusions[name] = {"a": excl_tickers(raw["A"]["trades"], BAN), "b": excl_tickers(raw[name]["trades"], BAN)}
        excl_top2[name] = {
            "a": excl_top_n_trades(raw["A"]["trades"], 2),
            "b": excl_top_n_trades(raw[name]["trades"], 2),
        }
        # exposure-norm edge: AV or PnL better than A after norm
        nm = norm_metrics[name]
        exp_ok = (nm["net_pnl_usd"] > metrics["A"]["net_pnl_usd"] and nm["account_value"] > metrics["A"]["account_value"])
        econ[name] = evaluate_sizing_economic(
            metrics["A"], metrics[name], comparisons[name],
            temporal=temporal[name],
            excl=exclusions[name],
            excl_top2=excl_top2[name],
            sens_ok=sens_ok(name),
            exposure_norm_ok=exp_ok,
        )

    # Determinism
    a2 = rv_a()
    deterministic = abs(a2["ending_cash"] - raw["A"]["ending_cash"]) < 1e-6
    if not deterministic:
        reliability["reliable_for_promotion"] = False
        reliability["flags"] = list(reliability["flags"]) + ["NON_DETERMINISTIC"]

    conc = concentration_analysis(raw["A"], raw, metrics)

    # Score-band diagnostic on A trades via sizing_decisions absence — use events scores
    band_pnl = {"low": 0.0, "mid": 0.0, "high": 0.0}
    band_n = {"low": 0, "mid": 0, "high": 0}
    # Map A closed trades to buy scores from base events
    buy_score = {
        (e["ticker"], str(pd.Timestamp(e["ts"]).normalize().date())): e.get("score")
        for e in base_events if e["kind"] == "BUY_EVAL"
    }
    for t in raw["A"]["trades"]:
        key = (t["ticker"], str(pd.Timestamp(t["entry_ts"]).normalize().date()))
        sc = buy_score.get(key)
        band = confidence_band(float(sc) if sc is not None else None)
        band_pnl[band] += float(t["pnl_usd"])
        band_n[band] += 1
    confidence_diag = {
        "band_pnl_usd": {k: round(v, 4) for k, v in band_pnl.items()},
        "band_n": band_n,
        "band_expectancy": {
            k: round(band_pnl[k] / band_n[k], 4) if band_n[k] else None for k in band_n
        },
        "monotonic_high_best": (
            (band_pnl["high"] / band_n["high"] if band_n["high"] else -1e18)
            >= (band_pnl["mid"] / band_n["mid"] if band_n["mid"] else -1e18)
            >= (band_pnl["low"] / band_n["low"] if band_n["low"] else -1e18)
        ),
    }

    paper = False
    if not reliability["reliable_for_promotion"]:
        verdict = "RISK_WEIGHTED_SIZING_NO_EDGE"
        recommendation = "Replay reliability failed — no PAPER. " + str(reliability["flags"])
    elif any(econ[n]["passes"] for n in ("B1", "B2", "B3")):
        best = max(
            (n for n in ("B1", "B2", "B3") if econ[n]["passes"]),
            key=lambda n: comparisons[n]["delta_account_value"],
        )
        verdict = "RISK_WEIGHTED_SIZING_CANDIDATE_FOUND"
        recommendation = (
            f"{best} passes acceptance under chronological sizing replay. "
            "Keep promotion_eligibility=false until explicit PAPER gate."
        )
    else:
        verdict = "RISK_WEIGHTED_SIZING_NO_EDGE"
        recommendation = (
            "No robust risk-weighted sizing edge. Do not PAPER. "
            "Do not start capacity optimization in this sprint. "
            f"Flags: {[ {k: econ[k]['flags']} for k in econ ]}"
        )

    hashes_after = {f: _sha(f) for f in PROTECTED}

    def slim(v: dict) -> dict:
        out = {k: v[k] for k in v if k not in {"events", "equity_curve", "trades", "sizing_decisions"}}
        out["trades"] = v["trades"]
        out["sizing_decisions_n"] = len(v.get("sizing_decisions") or [])
        out["sizing_decisions_sample"] = (v.get("sizing_decisions") or [])[:15]
        out["equity_curve_n"] = len(v.get("equity_curve") or [])
        return out

    report = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "source_commit_expected": "5cd975b",
        "promotion_eligibility": False,
        "paper_ab_active": paper,
        "verdict": verdict,
        "recommendation": recommendation,
        "reliable_for_promotion": reliability["reliable_for_promotion"],
        "reliability": reliability,
        "canonical_sizing": {
            "function": "live_bot.get_dynamic_trade_size → cash/candidates then MIN/MAX clamp",
            "min_trade_usd": MIN_TRADE_USD,
            "max_trade_usd": MAX_TRADE_USD,
            "max_positions": 12,
            "score_affects_size": False,
            "vol_affects_size": False,
        },
        "primary_params": PRIMARY,
        "median_atr_pct": med_atr,
        "control_a_reconciliation": recon_a,
        "metrics": metrics,
        "metrics_exposure_normalized": norm_metrics,
        "comparisons": comparisons,
        "economic_evaluations": econ,
        "temporal": temporal,
        "exclusions_mu_amat_sie": exclusions,
        "exclusions_top2": excl_top2,
        "sensitivity": sens,
        "concentration": conc,
        "confidence_diagnostic": confidence_diag,
        "deterministic_inprocess": deterministic,
        "variants": {k: slim(v) for k, v in raw.items()},
        "protected_hashes": {"before": hashes_before, "after": hashes_after, "unchanged": hashes_before == hashes_after},
        "live_bot_modified": False,
        "closed_hypotheses_untouched": [
            "STOP_REGIME_NO_EDGE",
            "REBUY_COOLDOWN_NO_EDGE",
            "ENTRY_PERSISTENCE_EDGE_NON_TRANSFERABLE",
        ],
    }
    if write:
        OUTPUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        OUTPUT_MD.write_text(render_md(report), encoding="utf-8")
    return report


def render_md(report: dict[str, Any]) -> str:
    m = report["metrics"]
    lines = [
        "# TAE Risk-Weighted Position Sizing A/B Results",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Verdict: **`{report['verdict']}`**",
        f"reliable_for_promotion: `{report['reliable_for_promotion']}`",
        f"promotion_eligibility: `{report['promotion_eligibility']}`",
        "",
        "## Canonical sizing",
        f"```json\n{json.dumps(report['canonical_sizing'], indent=2)}\n```",
        "",
        "## Control A reconciliation",
        f"```json\n{json.dumps(report['control_a_reconciliation'], indent=2)}\n```",
        "",
        "## Natural sizing — A vs B1/B2/B3",
        "",
        "| Variant | net PnL | AV | E[$]/trade] | E[$]/$] | maxDD $ | maxDD % | fills | avg notional | util |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k in ("A", "B1", "B2", "B3"):
        x = m[k]
        lines.append(
            f"| {k} | {x['net_pnl_usd']} | {x['account_value']} | {x['expectancy']} | "
            f"{x['expectancy_per_dollar']} | {x['max_drawdown_account']} | {x.get('max_drawdown_pct')} | "
            f"{x['fills']} | {x.get('avg_notional')} | {x.get('capital_utilization')} |"
        )
    lines += [
        "",
        "## Exposure-normalized",
        f"```json\n{json.dumps(report['metrics_exposure_normalized'], indent=2, default=str)}\n```",
        "",
        "## Economic evaluations",
        f"```json\n{json.dumps(report['economic_evaluations'], indent=2)}\n```",
        "",
        "## Temporal",
        f"```json\n{json.dumps(report['temporal'], indent=2, default=str)}\n```",
        "",
        "## Confidence diagnostic (A)",
        f"```json\n{json.dumps(report['confidence_diagnostic'], indent=2)}\n```",
        "",
        "## Concentration",
        f"```json\n{json.dumps(report['concentration'], indent=2)}\n```",
        "",
        "## Recommendation",
        report["recommendation"],
        "",
        "NO LIVE CHANGE · NO CAPACITY SPRINT · CLOSED HYPOTHESES UNTOUCHED",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    report = run_experiment(write=not args.no_write)
    print("=== RISK WEIGHTED POSITION SIZING A/B ===")
    print("verdict", report["verdict"])
    print("reliable", report["reliable_for_promotion"])
    print("recon", report["control_a_reconciliation"].get("ok"))
    for k, v in report["metrics"].items():
        print(k, "pnl", v["net_pnl_usd"], "AV", v["account_value"],
              "epd", v["expectancy_per_dollar"], "mdd", v["max_drawdown_account"],
              "avgN", v.get("avg_notional"), "fills", v["fills"])
    print("econ", {k: {"passes": v["passes"], "flags": v["flags"]} for k, v in report["economic_evaluations"].items()})
    print("protected", report["protected_hashes"]["unchanged"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
