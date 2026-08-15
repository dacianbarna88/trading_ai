#!/usr/bin/env python3
"""
TAE Exit Replay Horizon / Attribution Audit — READ_ONLY / SHADOW.

Fair-horizon comparisons for exit strategy counterfactuals.
Does NOT modify live_bot, core/trailing, portfolio.csv, strategy formulas, or PAPER execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from tae_exit_strategy_bar_replay import (
    actual_closed_benchmark,
    download_enriched_bars,
    load_replay_lots,
    lots_to_positions,
    native_currency_for_ticker,
    reconstruct_fifo_lots,
    reconcile_fifo_quantities,
    reset_replay_context,
    run_bar_replay,
)

SCHEMA = "tae_exit_strategy_horizon_audit"
SCHEMA_VERSION = "1.0"
SOURCE_COMMIT_EXPECTED = "161531b"
PROTECTED_FILES = ("live_bot.py", "core/trailing.py", "portfolio.csv")

OUTPUT_JSON = Path("tae_exit_strategy_horizon_audit.json")
OUTPUT_MD = Path("TAE_EXIT_REPLAY_HORIZON_AUDIT.md")
LOT_ATTR_CSV = Path("tae_exit_strategy_lot_attribution.csv")
EXTREME_TRACES_JSON = Path("tae_exit_strategy_extreme_lot_traces.json")

METHOD_UNBOUNDED = "UNBOUNDED_AVAILABLE_HISTORY"
METHOD_ACTUAL_CAP = "ACTUAL_EXIT_CAPPED"
METHOD_H20 = "HORIZON_20_BARS"
METHOD_H60 = "HORIZON_60_BARS"
METHOD_H120 = "HORIZON_120_BARS"
METHOD_H252 = "HORIZON_252_BARS"

HORIZON_SPECS: list[tuple[str, int | None, bool]] = [
    (METHOD_UNBOUNDED, None, False),
    (METHOD_ACTUAL_CAP, None, True),
    (METHOD_H20, 20, False),
    (METHOD_H60, 60, False),
    (METHOD_H120, 120, False),
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except (TypeError, ValueError):
        return default


def sha256_file(path: Path | str) -> str:
    p = Path(path)
    if not p.is_file():
        return "MISSING"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return SOURCE_COMMIT_EXPECTED


def git_diff_protected() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in PROTECTED_FILES:
        try:
            d = subprocess.check_output(["git", "diff", "--", f], text=True)
            out[f] = "CLEAN" if not d.strip() else "DIRTY"
        except Exception:
            out[f] = "UNKNOWN"
    return out


def _pctile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    return float(np.percentile(np.asarray(xs, dtype=float), q))


def _median(xs: list[float]) -> float | None:
    return _pctile(xs, 50)


def _mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return float(np.mean(xs))


def _trimmed_mean(xs: list[float], trim_frac: float) -> float | None:
    if not xs:
        return None
    arr = np.sort(np.asarray(xs, dtype=float))
    n = len(arr)
    k = int(math.floor(n * trim_frac))
    if 2 * k >= n:
        return float(np.mean(arr))
    return float(np.mean(arr[k : n - k]))


def _skewness(xs: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    arr = np.asarray(xs, dtype=float)
    m = float(arr.mean())
    s = float(arr.std(ddof=1))
    if s <= 1e-12:
        return 0.0
    return float(np.mean(((arr - m) / s) ** 3))


def concentration_audit(pnls: list[float]) -> dict[str, Any]:
    if not pnls:
        return {
            "total_pnl": 0.0,
            "n": 0,
            "concentration_verdict": "BROAD_BASED_RESULT",
            "top_5_positive": [],
            "top_5_negative": [],
        }
    indexed = sorted(enumerate(pnls), key=lambda t: t[1])
    total = float(sum(pnls))
    losers = [p for p in pnls if p < 0]
    winners = [p for p in pnls if p > 0]
    worst = min(pnls)
    worst5 = sorted(pnls)[:5]
    best = max(pnls)
    abs_sum = sum(abs(p) for p in pnls) or 1.0
    top10_abs = sorted(pnls, key=lambda x: abs(x), reverse=True)[:10]
    top10_share = sum(abs(x) for x in top10_abs) / abs_sum
    worst_share = abs(worst) / abs_sum if worst < 0 else 0.0
    worst5_share = sum(abs(x) for x in worst5 if x < 0) / abs_sum
    downside = sum(abs(x) for x in losers) or 1.0
    downside_conc = abs(worst) / downside if losers else 0.0

    if worst_share >= 0.40 or top10_share >= 0.85:
        verdict = "DOMINATED_BY_OUTLIERS"
    elif worst5_share >= 0.50 or top10_share >= 0.70:
        verdict = "HIGHLY_CONCENTRATED"
    elif top10_share >= 0.45 or worst5_share >= 0.30:
        verdict = "MODERATELY_CONCENTRATED"
    else:
        verdict = "BROAD_BASED_RESULT"

    return {
        "total_pnl": round(total, 4),
        "n": len(pnls),
        "median_pnl": _median(pnls),
        "trimmed_mean_5pct": _trimmed_mean(pnls, 0.05),
        "trimmed_mean_10pct": _trimmed_mean(pnls, 0.10),
        "pnl_without_best": round(total - best, 4),
        "pnl_without_worst": round(total - worst, 4),
        "pnl_without_worst_5": round(total - sum(worst5), 4),
        "dispersion_std": float(np.std(pnls, ddof=1)) if len(pnls) > 1 else 0.0,
        "skewness": _skewness(pnls),
        "pct_from_worst_lot": round(100.0 * worst_share, 2),
        "pct_from_worst_5": round(100.0 * worst5_share, 2),
        "top10_abs_share": round(top10_share, 4),
        "downside_concentration": round(downside_conc, 4),
        "top_5_positive": sorted(winners, reverse=True)[:5],
        "top_5_negative": sorted(losers)[:5],
        "concentration_verdict": verdict,
        "dominated_by_extremes": verdict in ("HIGHLY_CONCENTRATED", "DOMINATED_BY_OUTLIERS"),
    }


def forced_close_audit(trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    n = len(closed)
    reasons = defaultdict(int)
    forced_rows = []
    for t in closed:
        r = str(t.get("exit_reason") or "")
        reasons[r] += 1
        if r.startswith("FORCED"):
            forced_rows.append(t)
    forced_n = len(forced_rows)
    forced_pnl = [_f(t.get("pnl")) for t in forced_rows]
    hold = [_f(t.get("bars_held")) for t in forced_rows]
    by_label = {
        "FORCED_END_OF_AVAILABLE_HISTORY": 0,
        "FORCED_MAX_HORIZON": 0,
        "FORCED_CURRENT_DATE_OPEN_POSITION": 0,
        "FORCED_ACTUAL_EXIT_CAP": 0,
        "OTHER_FORCED_CLOSE": 0,
    }
    for t in forced_rows:
        r = str(t.get("exit_reason") or "")
        if r in by_label:
            by_label[r] += 1
        else:
            by_label["OTHER_FORCED_CLOSE"] += 1
    rate = (forced_n / n) if n else 0.0
    if rate > 0.25:
        flag = "FORCED_CLOSE_DOMINATES_RESULT"
    elif rate > 0.10:
        flag = "FORCED_CLOSE_MATERIALLY_AFFECTS_RESULT"
    else:
        flag = "FORCED_CLOSE_IMMATERIAL"
    return {
        "simulated_exits": n,
        "stop_loss": sum(1 for t in closed if "STOP" in str(t.get("exit_reason") or "") and "TRAIL" not in str(t.get("exit_reason") or "")),
        "trailing_stop": sum(1 for t in closed if "TRAILING" in str(t.get("exit_reason") or "")),
        "trend_exits": sum(1 for t in closed if "TREND" in str(t.get("exit_reason") or "")),
        "forced_close": forced_n,
        "forced_close_pct": round(100.0 * rate, 2),
        "forced_pnl_total": round(sum(forced_pnl), 4),
        "forced_pnl_mean": _mean(forced_pnl),
        "forced_holding_bars_mean": _mean(hold),
        "forced_holding_bars_max": max(hold) if hold else None,
        "forced_tickers": sorted({str(t.get("ticker")) for t in forced_rows}),
        "forced_reason_breakdown": by_label,
        "exit_reason_counts": dict(reasons),
        "forced_close_flag": flag,
    }


def holding_bucket(days: float) -> str:
    if days <= 5:
        return "0_5"
    if days <= 20:
        return "6_20"
    if days <= 60:
        return "21_60"
    if days <= 120:
        return "61_120"
    return "120_plus"


def holding_period_audit(trades: list[dict[str, Any]], actual_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    bars = [_f(t.get("bars_held")) for t in closed]
    days = [_f(t.get("hold_days")) for t in closed]
    dist = defaultdict(int)
    for d in days:
        dist[holding_bucket(d)] += 1
    vs = {"earlier": 0, "later": 0, "same_day": 0, "forced": 0, "no_actual": 0, "deltas_days": []}
    for t in closed:
        rel = t.get("exit_vs_actual")
        if rel == "EARLIER":
            vs["earlier"] += 1
        elif rel == "LATER":
            vs["later"] += 1
        elif rel == "SAME_DAY":
            vs["same_day"] += 1
        elif rel == "FORCED":
            vs["forced"] += 1
        else:
            vs["no_actual"] += 1
        act = t.get("actual_exit_timestamp")
        sim = t.get("exit_timestamp")
        if act and sim:
            delta = (pd.Timestamp(sim).normalize() - pd.Timestamp(act).normalize()).days
            vs["deltas_days"].append(float(delta))
    med_days = _median(days) or 0.0
    act_med = None
    if actual_rows:
        act_days = [_f(r.get("hold_days")) for r in actual_rows if r.get("hold_days") is not None]
        act_med = _median(act_days)
    if act_med is not None and med_days > act_med * 2.0 + 10:
        verdict = "HOLDING_NOT_COMPARABLE"
    elif act_med is not None and med_days > act_med * 1.5 + 5:
        verdict = "HOLDING_MATERIALLY_LONGER"
    elif act_med is not None and med_days > act_med * 1.15:
        verdict = "HOLDING_LONGER_THAN_ACTUAL"
    else:
        verdict = "HOLDING_COMPARABLE"
    return {
        "avg_holding_bars": _mean(bars),
        "median_holding_bars": _median(bars),
        "p75_holding_bars": _pctile(bars, 75),
        "p90_holding_bars": _pctile(bars, 90),
        "max_holding_bars": max(bars) if bars else None,
        "avg_calendar_days": _mean(days),
        "median_calendar_days": _median(days),
        "distribution_days": dict(dist),
        "vs_actual": {
            "earlier_exit_count": vs["earlier"],
            "later_exit_count": vs["later"],
            "same_day_exit_count": vs["same_day"],
            "forced_count": vs["forced"],
            "mean_delta_days": _mean(vs["deltas_days"]),
            "median_delta_days": _median(vs["deltas_days"]),
        },
        "holding_verdict": verdict,
    }


def horizon_distribution(positions: list[Any], bars_by_ticker: dict[str, pd.DataFrame]) -> dict[str, Any]:
    avail_list: list[float] = []
    buckets = {"lt_20": 0, "20_59": 0, "60_119": 0, "120_251": 0, "252_plus": 0}
    old_vs_new: list[tuple[float, float]] = []  # (entry_ordinal, avail)
    for pos in positions:
        bars = bars_by_ticker.get(pos.ticker, pd.DataFrame())
        if bars is None or bars.empty:
            continue
        start = pd.Timestamp(pos.entry_timestamp).normalize()
        avail = int((bars.index >= start).sum())
        avail_list.append(float(avail))
        if avail < 20:
            buckets["lt_20"] += 1
        elif avail < 60:
            buckets["20_59"] += 1
        elif avail < 120:
            buckets["60_119"] += 1
        elif avail < 252:
            buckets["120_251"] += 1
        else:
            buckets["252_plus"] += 1
        old_vs_new.append((float(start.value), float(avail)))
    corr = None
    if len(old_vs_new) >= 3:
        a = np.asarray([x[0] for x in old_vs_new], dtype=float)
        b = np.asarray([x[1] for x in old_vs_new], dtype=float)
        if a.std() > 0 and b.std() > 0:
            corr = float(np.corrcoef(a, b)[0, 1])
    # older entries (smaller timestamp) should have more bars → negative corr expected if unbalanced
    if corr is not None and corr < -0.55 and (_pctile(avail_list, 90) or 0) > 3 * (_pctile(avail_list, 25) or 1):
        verdict = "HORIZONS_SEVERELY_UNBALANCED"
    elif corr is not None and corr < -0.25:
        verdict = "HORIZONS_UNBALANCED"
    elif avail_list and (_pctile(avail_list, 90) or 0) > 5 * max(1.0, _pctile(avail_list, 10) or 1.0):
        verdict = "HORIZONS_UNBALANCED"
    else:
        verdict = "HORIZONS_COMPARABLE"
    return {
        "n": len(avail_list),
        "min": min(avail_list) if avail_list else None,
        "p25": _pctile(avail_list, 25),
        "median": _median(avail_list),
        "p75": _pctile(avail_list, 75),
        "p90": _pctile(avail_list, 90),
        "max": max(avail_list) if avail_list else None,
        "buckets": buckets,
        "corr_entry_time_vs_available_bars": corr,
        "horizon_verdict": verdict,
        "note": "Negative corr(entry_time, available_bars) means older lots receive longer horizons.",
    }


def classify_entry_alignment(pos: Any, bars: pd.DataFrame) -> dict[str, Any]:
    if bars is None or bars.empty:
        return {
            "entry_alignment_method": "ENTRY_BAR_NOT_FOUND",
            "alignment_delta_days": None,
            "entry_price_vs_ohlc": "NO_BARS",
            "price_in_bar_range": False,
        }
    entry_ts = pd.Timestamp(pos.entry_timestamp)
    entry_n = entry_ts.normalize()
    idx = bars.index
    exact = idx[idx == entry_n]
    method = "ENTRY_BAR_NOT_FOUND"
    bar_ts = None
    if len(exact):
        bar_ts = exact[0]
        method = "EXACT_BAR_MATCH"
    else:
        later = idx[idx > entry_n]
        if len(later):
            bar_ts = later[0]
            method = "NEXT_BAR_ALIGNMENT"
            if (pd.Timestamp(bar_ts).normalize() - entry_n).days == 0:
                method = "SAME_DAY_FALLBACK"
        else:
            same_day = idx[(idx >= entry_n) & (idx < entry_n + pd.Timedelta(days=1))]
            if len(same_day):
                bar_ts = same_day[0]
                method = "SAME_DAY_FALLBACK"
    if bar_ts is None:
        return {
            "entry_alignment_method": "ENTRY_BAR_NOT_FOUND",
            "alignment_delta_days": None,
            "entry_price_vs_ohlc": "NO_BAR",
            "price_in_bar_range": False,
            "bar_open": None,
            "bar_high": None,
            "bar_low": None,
            "bar_close": None,
        }
    row = bars.loc[bar_ts]
    o, h, l, c = _f(row["Open"]), _f(row["High"]), _f(row["Low"]), _f(row["Close"])
    px = _f(pos.entry_price)
    # tolerate 2% for adjusted/unadjusted noise
    lo = min(o, h, l, c) * 0.98
    hi = max(o, h, l, c) * 1.02
    in_range = lo <= px <= hi
    if not in_range:
        method_flag = "ENTRY_PRICE_OUTSIDE_BAR_RANGE"
    else:
        method_flag = method
    return {
        "entry_alignment_method": method_flag if not in_range else method,
        "alignment_delta_days": (pd.Timestamp(bar_ts).normalize() - entry_n).days,
        "entry_price_vs_ohlc": {
            "entry_price": px,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
        },
        "price_in_bar_range": in_range,
        "bar_timestamp": str(bar_ts),
        "timezone_note": "portfolio timestamps treated as naive/exchange-local; bars from yfinance normalized daily",
    }


def price_basis_audit(pos: Any, bars: pd.DataFrame) -> dict[str, Any]:
    align = classify_entry_alignment(pos, bars)
    verdict = "PRICE_BASIS_CONSISTENT"
    flags: list[str] = []
    split_like = False
    if bars is None or bars.empty:
        return {"verdict": "PRICE_BASIS_INVALID", "flags": ["HISTORY_EMPTY"], "download_mode": "auto_adjust=True"}
    # look for large overnight jumps near entry
    start = pd.Timestamp(pos.entry_timestamp).normalize()
    window = bars[(bars.index >= start - pd.Timedelta(days=10)) & (bars.index <= start + pd.Timedelta(days=10))]
    ratios = []
    closes = window["Close"].astype(float).tolist()
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            ratios.append(closes[i] / closes[i - 1])
    for r in ratios:
        for cand in (2.0, 3.0, 4.0, 5.0, 10.0, 0.5, 1 / 3, 0.25, 0.2, 0.1):
            if abs(r - cand) / cand < 0.05:
                split_like = True
                flags.append(f"SPLIT_LIKE_RATIO_{cand}")
                break
    if not align.get("price_in_bar_range", True):
        flags.append("ENTRY_PRICE_MISMATCH_VS_ADJUSTED_OHLC")
        verdict = "PRICE_ADJUSTMENT_WARNING"
        # large mismatch may indicate split
        px = _f(pos.entry_price)
        c = _f((align.get("entry_price_vs_ohlc") or {}).get("close"))
        if c > 0 and (px / c > 1.8 or c / px > 1.8):
            verdict = "SPLIT_ADJUSTMENT_REQUIRED"
            split_like = True
    if split_like and verdict == "PRICE_BASIS_CONSISTENT":
        verdict = "PRICE_ADJUSTMENT_WARNING"
    return {
        "verdict": verdict,
        "flags": flags,
        "split_like_discontinuity": split_like,
        "download_mode": "yfinance auto_adjust=True (adjusted)",
        "alignment": align,
    }


def currency_audit(lots: list[Any]) -> dict[str, Any]:
    by_ccy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lot in lots:
        ccy = native_currency_for_ticker(lot.ticker)
        pnl = None
        if lot.status == "CLOSED" and lot.exit_price is not None:
            pnl = (float(lot.exit_price) - float(lot.entry_price)) * float(lot.entry_quantity)
        by_ccy[ccy].append({
            "ticker": lot.ticker,
            "region": lot.region,
            "native_currency": ccy,
            "pnl_native": pnl,
            "conversion_status": "NO_CANONICAL_HISTORICAL_FX",
            "conversion_source": None,
            "pnl_base_currency": None,
        })
    currencies = sorted(by_ccy.keys())
    mixed = len(currencies) > 1
    # Aggregates previously summed native units as if USD
    flags = []
    if mixed:
        flags.append("CRITICAL_MIXED_CURRENCY_AGGREGATION")
    return {
        "currencies_present": currencies,
        "mixed_currency": mixed,
        "flags": flags,
        "conversion_available": False,
        "note": "No canonical historical FX in exit-replay path; do not treat sum(native) as USD.",
        "by_currency": {
            ccy: {
                "n_lots": len(rows),
                "closed_pnl_native_sum": round(sum(_f(r["pnl_native"]) for r in rows if r["pnl_native"] is not None), 4),
                "tickers": sorted({r["ticker"] for r in rows}),
            }
            for ccy, rows in by_ccy.items()
        },
        "native_unnormalized_warning": mixed,
        "verdict": "CRITICAL_MIXED_CURRENCY_AGGREGATION" if mixed else "SINGLE_CURRENCY_NATIVE",
    }


def capital_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    if not closed:
        return {"n": 0}
    rets = [_f(t.get("pnl_pct")) for t in closed]
    capitals = [abs(_f(t.get("entry_price")) * _f(t.get("shares"))) for t in closed]
    pnls = [_f(t.get("pnl")) for t in closed]
    cap_sum = sum(capitals) or 1.0
    cap_w = sum(r * c for r, c in zip(rets, capitals)) / cap_sum
    pnl_per_1k = (sum(pnls) / cap_sum) * 1000.0
    mfe = [_f(t.get("mfe_pct")) for t in closed]
    mae = [_f(t.get("mae_pct")) for t in closed]
    capture = [t.get("profit_capture_rate") for t in closed if t.get("profit_capture_rate") is not None]
    return {
        "n": len(closed),
        "equal_weight_avg_return_pct": _mean(rets),
        "median_return_pct": _median(rets),
        "capital_weighted_return_pct": round(cap_w, 4),
        "pnl_per_1000_capital": round(pnl_per_1k, 4),
        "expectancy_pct": _mean(rets),
        "avg_mfe_pct": _mean(mfe),
        "avg_mae_pct": _mean(mae),
        "avg_capture_ratio": _mean([_f(x) for x in capture]) if capture else None,
        "nominal_pnl": round(sum(pnls), 4),
    }


def subgroup_results(trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t.get("status") == "CLOSED"]

    def group(key_fn: Callable[[dict[str, Any]], str]) -> dict[str, dict[str, Any]]:
        g: dict[str, list[float]] = defaultdict(list)
        for t in closed:
            g[key_fn(t)].append(_f(t.get("pnl")))
        return {k: {"n": len(v), "pnl": round(sum(v), 4), "median": _median(v)} for k, v in sorted(g.items())}

    def actual_bucket(t: dict[str, Any]) -> str:
        ap = t.get("actual_realized_pnl")
        if ap is None:
            return "NO_ACTUAL"
        if ap > 0:
            return "ACTUAL_WINNER"
        if ap < 0:
            return "ACTUAL_LOSER"
        return "ACTUAL_FLAT"

    def hold_bucket(t: dict[str, Any]) -> str:
        d = _f(t.get("hold_days"))
        if d <= 20:
            return "SHORT"
        if d <= 60:
            return "MEDIUM"
        return "LONG"

    def year_key(t: dict[str, Any]) -> str:
        try:
            return str(pd.Timestamp(t.get("entry_timestamp")).year)
        except Exception:
            return "UNKNOWN"

    def exit_reason_bucket(t: dict[str, Any]) -> str:
        r = str(t.get("actual_exit_reason") or "OTHER").upper()
        if "TAKE" in r or "TP" in r or "PROFIT" in r:
            return "TAKE_PROFIT"
        if "STOP" in r:
            return "STOP_LOSS"
        if "TRAIL" in r:
            return "TRAILING"
        return "OTHER"

    return {
        "REGION": group(lambda t: str(t.get("region") or "OTHER")),
        "CURRENCY": group(lambda t: native_currency_for_ticker(str(t.get("ticker") or ""))),
        "ENTRY_YEAR": group(year_key),
        "VOLATILITY": group(lambda t: str(t.get("volatility_bucket") or "UNKNOWN")),
        "ACTUAL_RESULT": group(actual_bucket),
        "ACTUAL_EXIT_REASON": group(exit_reason_bucket),
        "HOLDING_PERIOD": group(hold_bucket),
    }


def summarize_method_result(replay: dict[str, Any], actual_bench: dict[str, Any] | None = None) -> dict[str, Any]:
    strategies = {}
    leaders = []
    for s in replay.get("strategies", []):
        arm = s["strategy_id"]
        trades = s.get("trades") or []
        closed = [t for t in trades if t.get("status") == "CLOSED"]
        pnls = [_f(t.get("pnl")) for t in closed]
        conc = concentration_audit(pnls)
        forced = forced_close_audit(trades)
        holding = holding_period_audit(trades, (actual_bench or {}).get("lots"))
        cap = capital_metrics(trades)
        cost_pnls = []
        for t in closed:
            if t.get("exit_price") is None:
                continue
            entry = _f(t.get("entry_price")) * (1.0 + 5.0 / 10_000.0)
            exit_px = _f(t.get("exit_price")) * (1.0 - 5.0 / 10_000.0)
            cost_pnls.append((exit_px - entry) * _f(t.get("shares")))
        cost = {
            "net_pnl": round(sum(cost_pnls), 4) if cost_pnls else 0.0,
            "sample_size": len(cost_pnls),
        }
        strategies[arm] = {
            "metrics": s.get("metrics"),
            "concentration": conc,
            "forced_close": forced,
            "holding_period": holding,
            "capital_metrics": cap,
            "realistic_cost_metrics": cost,
            "subgroups": subgroup_results(trades),
            "eligible": replay.get("positions"),
            "attempted": replay.get("positions_attempted"),
            "exclusions": (replay.get("data_quality") or {}).get("exclusion_reasons"),
        }
        leaders.append((arm, _f((s.get("metrics") or {}).get("net_pnl")), _f(cost.get("net_pnl"))))
    leaders_sorted = sorted(leaders, key=lambda x: x[1], reverse=True)
    cost_sorted = sorted(leaders, key=lambda x: x[2], reverse=True)
    eligible_n = int(replay.get("positions") or 0)
    if eligible_n <= 0:
        return {
            "methodology_id": replay.get("methodology_id"),
            "cohort": replay.get("cohort"),
            "eligible_lots": 0,
            "attempted_lots": replay.get("positions_attempted"),
            "exclusions": (replay.get("data_quality") or {}).get("exclusion_reasons"),
            "strategies": strategies,
            "leader_zero_cost": None,
            "leader_realistic_cost": None,
            "rankings_zero_cost": [],
            "rankings_realistic_cost": [],
            "sample_status": "INSUFFICIENT_HORIZON_NO_ELIGIBLE_LOTS",
            "note": "No lots have enough post-entry bars for this fixed horizon; rankings are not interpretable.",
        }
    return {
        "methodology_id": replay.get("methodology_id"),
        "cohort": replay.get("cohort"),
        "eligible_lots": replay.get("positions"),
        "attempted_lots": replay.get("positions_attempted"),
        "exclusions": (replay.get("data_quality") or {}).get("exclusion_reasons"),
        "strategies": strategies,
        "leader_zero_cost": leaders_sorted[0][0] if leaders_sorted else None,
        "leader_realistic_cost": cost_sorted[0][0] if cost_sorted else None,
        "rankings_zero_cost": [{"strategy": a, "net_pnl": p} for a, p, _ in leaders_sorted],
        "rankings_realistic_cost": [{"strategy": a, "net_pnl": c} for a, _, c in cost_sorted],
        "sample_status": "OK",
    }


def build_lot_attribution(
    *,
    methodology: str,
    replay: dict[str, Any],
    positions: list[Any],
    bars_by_ticker: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    pos_by_lot = {getattr(p, "lot_id", ""): p for p in positions}
    rows: list[dict[str, Any]] = []
    for s in replay.get("strategies", []):
        arm = s["strategy_id"]
        for t in s.get("trades") or []:
            lot_id = t.get("lot_id") or ""
            pos = pos_by_lot.get(lot_id)
            bars = bars_by_ticker.get(t.get("ticker"), pd.DataFrame())
            start = pd.Timestamp(t.get("entry_timestamp")).normalize() if t.get("entry_timestamp") else None
            avail = int((bars.index >= start).sum()) if start is not None and bars is not None and not bars.empty else 0
            hist_start = str(bars.index.min()) if bars is not None and not bars.empty else None
            hist_end = str(bars.index.max()) if bars is not None and not bars.empty else None
            align = classify_entry_alignment(pos, bars) if pos is not None else {}
            price_a = price_basis_audit(pos, bars) if pos is not None else {}
            ccy = native_currency_for_ticker(str(t.get("ticker") or ""))
            reason = str(t.get("exit_reason") or "")
            forced = reason.startswith("FORCED")
            rows.append({
                "methodology": methodology,
                "strategy": arm,
                "lot_id": lot_id,
                "ticker": t.get("ticker"),
                "region": t.get("region"),
                "currency": ccy,
                "entry_timestamp": t.get("entry_timestamp"),
                "entry_price": t.get("entry_price"),
                "quantity": t.get("shares"),
                "lot_status": t.get("lot_status"),
                "actual_exit_timestamp": t.get("actual_exit_timestamp"),
                "actual_exit_price": t.get("actual_exit_price"),
                "actual_exit_reason": t.get("actual_exit_reason"),
                "actual_realized_pnl_native": t.get("actual_realized_pnl"),
                "actual_realized_pnl_base_currency": None,
                "simulated_exit_timestamp": t.get("exit_timestamp"),
                "simulated_exit_price": t.get("exit_price"),
                "simulated_exit_reason": t.get("exit_reason"),
                "simulated_pnl_native": t.get("pnl"),
                "simulated_pnl_base_currency": None,
                "holding_bars": t.get("bars_held"),
                "holding_calendar_days": t.get("hold_days"),
                "MFE": t.get("mfe_pct"),
                "MAE": t.get("mae_pct"),
                "peak_price": None,
                "maximum_trailing_stop": None,
                "forced_close": forced,
                "warmup_status": "ATR_WARMUP_IF_INDICATED_IN_STRATEGY",
                "history_start": hist_start,
                "history_end": hist_end,
                "available_post_entry_bars": avail,
                "replay_horizon_bars": replay.get("max_bars"),
                "replay_end_reason": t.get("exit_reason"),
                "entry_alignment_method": align.get("entry_alignment_method"),
                "price_adjustment_mode": price_a.get("download_mode"),
                "data_quality": t.get("data_quality") or (pos.data_quality if pos else None),
                "exclusion_reason": None if t.get("status") == "CLOSED" else t.get("exit_reason"),
                "return_pct": t.get("pnl_pct"),
                "exit_vs_actual": t.get("exit_vs_actual"),
            })
    return rows


def build_extreme_traces(
    *,
    replay: dict[str, Any],
    bars_by_ticker: dict[str, pd.DataFrame],
    max_bars_trace: int = 40,
) -> dict[str, Any]:
    """Compact chronological traces for extreme negative lots (gitignored artifact)."""
    out: dict[str, Any] = {}
    for s in replay.get("strategies", []):
        arm = s["strategy_id"]
        closed = [t for t in (s.get("trades") or []) if t.get("status") == "CLOSED"]
        worst = sorted(closed, key=lambda t: _f(t.get("pnl")))[:5]
        traces = []
        for t in worst:
            bars = bars_by_ticker.get(t.get("ticker"), pd.DataFrame())
            if bars is None or bars.empty:
                continue
            start = pd.Timestamp(t["entry_timestamp"]).normalize()
            post = bars[bars.index >= start].iloc[:max_bars_trace]
            steps = []
            entry = _f(t.get("entry_price"))
            peak = entry
            for ts, row in post.iterrows():
                close = _f(row["Close"])
                high = _f(row["High"])
                peak = max(peak, high)
                gain = ((close - entry) / entry) * 100.0 if entry else 0.0
                peak_gain = ((peak - entry) / entry) * 100.0 if entry else 0.0
                steps.append({
                    "date": str(ts.date()) if hasattr(ts, "date") else str(ts),
                    "open": _f(row["Open"]),
                    "high": high,
                    "low": _f(row["Low"]),
                    "close": close,
                    "atr_pct": None if pd.isna(row.get("ATR_Pct")) else _f(row.get("ATR_Pct")),
                    "ema20": None if pd.isna(row.get("EMA20")) else _f(row.get("EMA20")),
                    "ema50": None if pd.isna(row.get("EMA50")) else _f(row.get("EMA50")),
                    "gain_from_entry_pct": round(gain, 4),
                    "peak_gain_pct": round(peak_gain, 4),
                })
            traces.append({
                "lot_id": t.get("lot_id"),
                "ticker": t.get("ticker"),
                "pnl": t.get("pnl"),
                "exit_reason": t.get("exit_reason"),
                "exit_timestamp": t.get("exit_timestamp"),
                "exit_price": t.get("exit_price"),
                "bars": steps,
                "note": "Indicators shown for audit; exit trigger levels are strategy-internal.",
            })
        out[arm] = traces
    # top diffs vs actual
    diffs = []
    for s in replay.get("strategies", []):
        for t in s.get("trades") or []:
            if t.get("actual_realized_pnl") is None or t.get("status") != "CLOSED":
                continue
            diffs.append({
                "strategy": s["strategy_id"],
                "lot_id": t.get("lot_id"),
                "ticker": t.get("ticker"),
                "delta_vs_actual": _f(t.get("pnl")) - _f(t.get("actual_realized_pnl")),
                "sim_pnl": t.get("pnl"),
                "actual_pnl": t.get("actual_realized_pnl"),
            })
    out["top_negative_vs_actual"] = sorted(diffs, key=lambda r: r["delta_vs_actual"])[:5]
    return out


def methodology_flags_from_audits(
    *,
    currency: dict[str, Any],
    quantity: dict[str, Any],
    price: dict[str, Any],
    horizon: dict[str, Any],
    methods: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if "CRITICAL_MIXED_CURRENCY_AGGREGATION" in (currency.get("flags") or []):
        flags.append("REPLAY_RESULT_DISTORTED_BY_CURRENCY")
    if quantity.get("ok") is False:
        flags.append("REPLAY_RESULT_NOT_INTERPRETABLE")
    if price.get("worst_verdict") in ("SPLIT_ADJUSTMENT_REQUIRED", "PRICE_BASIS_INVALID"):
        flags.append("REPLAY_RESULT_DISTORTED_BY_PRICE_BASIS")
    if horizon.get("horizon_verdict") == "HORIZONS_SEVERELY_UNBALANCED":
        flags.append("REPLAY_RESULT_DISTORTED_BY_HORIZON")
    elif horizon.get("horizon_verdict") == "HORIZONS_UNBALANCED":
        flags.append("REPLAY_RESULT_DISTORTED_BY_HORIZON")
    # forced / outliers from unbounded
    unb = methods.get(METHOD_UNBOUNDED) or {}
    forced_rates = []
    conc_flags = []
    for arm, block in (unb.get("strategies") or {}).items():
        fr = _f((block.get("forced_close") or {}).get("forced_close_pct"))
        forced_rates.append(fr)
        if (block.get("forced_close") or {}).get("forced_close_flag") == "FORCED_CLOSE_DOMINATES_RESULT":
            flags.append("REPLAY_RESULT_DISTORTED_BY_FORCED_CLOSE")
        if (block.get("concentration") or {}).get("concentration_verdict") in (
            "HIGHLY_CONCENTRATED",
            "DOMINATED_BY_OUTLIERS",
        ):
            conc_flags.append(True)
    if conc_flags:
        flags.append("REPLAY_RESULT_DISTORTED_BY_OUTLIERS")
    # leader stability across horizons
    leaders = []
    for mid in (METHOD_UNBOUNDED, METHOD_ACTUAL_CAP, METHOD_H20, METHOD_H60, METHOD_H120):
        m = methods.get(mid) or {}
        if m.get("leader_zero_cost"):
            leaders.append(m["leader_zero_cost"])
    if len(set(leaders)) > 1:
        # economic flag handled separately
        pass
    if not flags:
        if horizon.get("horizon_verdict") != "HORIZONS_COMPARABLE" or currency.get("mixed_currency"):
            flags.append("REPLAY_VALID_WITH_LIMITATIONS")
        else:
            flags.append("REPLAY_METHOD_VALID")
    elif "REPLAY_RESULT_NOT_INTERPRETABLE" not in flags:
        if "REPLAY_VALID_WITH_LIMITATIONS" not in flags:
            flags.append("REPLAY_VALID_WITH_LIMITATIONS")
    return sorted(set(flags))


def economic_verdict(methods: dict[str, Any], actual_bench: dict[str, Any]) -> str:
    leaders = []
    for mid in (METHOD_UNBOUNDED, METHOD_ACTUAL_CAP, METHOD_H20, METHOD_H60, METHOD_H120):
        m = methods.get(mid)
        if m and m.get("leader_zero_cost"):
            leaders.append(m["leader_zero_cost"])
    actual_pnl = _f(actual_bench.get("actual_net_pnl"))
    # compare actual vs best challenger on closed unbounded if available
    unb = methods.get(METHOD_UNBOUNDED) or {}
    best_challenger = None
    best_pnl = None
    for arm, block in (unb.get("strategies") or {}).items():
        p = _f((block.get("metrics") or {}).get("net_pnl"))
        if best_pnl is None or p > best_pnl:
            best_pnl = p
            best_challenger = arm
    if len(set(leaders)) > 1:
        return "LEADER_UNSTABLE_ACROSS_HORIZONS"
    if best_pnl is not None and actual_pnl > best_pnl:
        return "ACTUAL_EXIT_BENCHMARK_REMAINS_SUPERIOR"
    if leaders and all(x == leaders[0] for x in leaders):
        mapping = {
            "BASELINE_FIXED": "BASELINE_REMAINS_RESEARCH_LEADER",
            "ATR_ADAPTIVE": "ATR_ADAPTIVE_RESEARCH_LEADER",
            "TREND_FOLLOWER": "TREND_FOLLOWER_RESEARCH_LEADER",
            "HYBRID_ATR_TREND": "HYBRID_RESEARCH_LEADER",
        }
        # Still not economically proven for promotion
        return "NO_STRATEGY_ECONOMICALLY_PROVEN"
    return "NO_STRATEGY_ECONOMICALLY_PROVEN"


def preload_bars(positions: list[Any], fetcher: Callable | None = None) -> dict[str, pd.DataFrame]:
    cache: dict[str, pd.DataFrame] = {}
    for pos in positions:
        if pos.ticker in cache:
            continue
        try:
            cache[pos.ticker] = download_enriched_bars(pos.ticker, fetcher=fetcher)
        except Exception:
            cache[pos.ticker] = pd.DataFrame()
    return cache


def run_audit(
    *,
    portfolio_path: Path = Path("portfolio.csv"),
    cohort: str = "CLOSED_ONLY",
    fetcher: Callable | None = None,
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
    write_artifacts: bool = True,
    include_h252: bool = False,
) -> dict[str, Any]:
    hashes_before = {f: sha256_file(f) for f in PROTECTED_FILES}
    lots_all = reconstruct_fifo_lots(portfolio_path)
    lots = load_replay_lots(cohort=cohort, portfolio_path=portfolio_path)
    positions = lots_to_positions(lots)
    fifo = reconcile_fifo_quantities(portfolio_path)
    qty_verdict = (
        "QUANTITY_RECONCILED" if fifo.get("ok")
        else ("QUANTITY_RECONCILIATION_FAILED" if fifo.get("ok") is False else "QUANTITY_RECONCILIATION_WARNING")
    )
    ccy = currency_audit(lots_all)
    cache = dict(bars_by_ticker or {})
    if not cache:
        cache = preload_bars(positions, fetcher=fetcher)

    horizon = horizon_distribution(positions, cache)

    # Price / entry alignment across lots
    price_verdicts = []
    align_counts: dict[str, int] = defaultdict(int)
    for pos in positions:
        pb = price_basis_audit(pos, cache.get(pos.ticker, pd.DataFrame()))
        price_verdicts.append(pb.get("verdict"))
        align_counts[str((pb.get("alignment") or {}).get("entry_alignment_method"))] += 1
    worst_price = "PRICE_BASIS_CONSISTENT"
    for v in ("PRICE_BASIS_INVALID", "SPLIT_ADJUSTMENT_REQUIRED", "PRICE_ADJUSTMENT_WARNING", "PRICE_BASIS_CONSISTENT"):
        if v in price_verdicts:
            worst_price = v
            break

    actual_bench = actual_closed_benchmark(load_replay_lots("CLOSED_ONLY", portfolio_path))
    actual_lots_rows = actual_bench.get("lots") or actual_bench.get("rows")
    if actual_lots_rows is None:
        # reconstruct lightweight rows for holding compare
        actual_lots_rows = []
        for lot in load_replay_lots("CLOSED_ONLY", portfolio_path):
            if lot.status != "CLOSED":
                continue
            actual_lots_rows.append({
                "hold_days": (
                    (pd.Timestamp(lot.exit_timestamp) - pd.Timestamp(lot.entry_timestamp)).total_seconds() / 86400.0
                    if lot.exit_timestamp is not None else None
                ),
                "pnl": (float(lot.exit_price) - float(lot.entry_price)) * float(lot.entry_quantity)
                if lot.exit_price is not None else None,
            })
        actual_bench = {**actual_bench, "lots": actual_lots_rows}

    specs = list(HORIZON_SPECS)
    if include_h252:
        specs.append((METHOD_H252, 252, False))

    methods: dict[str, Any] = {}
    all_attr: list[dict[str, Any]] = []
    extreme_traces = {}

    for mid, max_bars, capped in specs:
        # For ACTUAL_EXIT_CAPPED use closed lots only even if cohort=ALL
        run_cohort = "CLOSED_ONLY" if capped else cohort
        run_positions = lots_to_positions(load_replay_lots(run_cohort, portfolio_path)) if capped else positions
        replay = run_bar_replay(
            portfolio_path=portfolio_path,
            positions=run_positions,
            bars_by_ticker=cache,
            cohort=run_cohort,
            max_bars=max_bars,
            methodology=mid,
            actual_exit_capped=capped,
            min_bars_required=max_bars,
            fetcher=fetcher,
        )
        # strip heavy _trades_by_arm before summarize uses trades in strategies
        summary = summarize_method_result(replay, actual_bench)
        methods[mid] = summary
        attr = build_lot_attribution(
            methodology=mid, replay=replay, positions=run_positions, bars_by_ticker=cache
        )
        all_attr.extend(attr)
        if mid == METHOD_UNBOUNDED:
            extreme_traces = build_extreme_traces(replay=replay, bars_by_ticker=cache)

    flags = methodology_flags_from_audits(
        currency=ccy,
        quantity=fifo,
        price={"worst_verdict": worst_price},
        horizon=horizon,
        methods=methods,
    )
    e_verdict = economic_verdict(methods, actual_bench)
    if "LEADER_UNSTABLE_ACROSS_HORIZONS" not in [e_verdict] and len({
        (methods.get(m) or {}).get("leader_zero_cost")
        for m in (METHOD_UNBOUNDED, METHOD_ACTUAL_CAP, METHOD_H20, METHOD_H60, METHOD_H120)
        if (methods.get(m) or {}).get("leader_zero_cost")
    }) > 1:
        e_verdict = "LEADER_UNSTABLE_ACROSS_HORIZONS"

    # Top negative contributors from unbounded BASELINE/ATR
    top_neg = {}
    for arm, block in ((methods.get(METHOD_UNBOUNDED) or {}).get("strategies") or {}).items():
        top_neg[arm] = (block.get("concentration") or {}).get("top_5_negative")

    hashes_after = {f: sha256_file(f) for f in PROTECTED_FILES}
    protected_ok = hashes_before == hashes_after
    diffs = git_diff_protected()

    report = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "source_commit": git_head(),
        "source_commit_expected": SOURCE_COMMIT_EXPECTED,
        "protected_file_hashes": {"before": hashes_before, "after": hashes_after, "unchanged": protected_ok},
        "protected_git_diff": diffs,
        "universe": {
            "total_buy_lots": len(lots_all),
            "open": sum(1 for l in lots_all if l.status == "OPEN"),
            "closed": sum(1 for l in lots_all if l.status == "CLOSED"),
            "audit_cohort": cohort,
            "audit_lots": len(positions),
            "coverage": 1.0 if lots_all else 0.0,
        },
        "fifo_reconciliation": {**fifo, "verdict": qty_verdict},
        "currency_audit": ccy,
        "price_basis_audit": {
            "download_mode": "yfinance auto_adjust=True",
            "worst_verdict": worst_price,
            "verdict_counts": {v: price_verdicts.count(v) for v in sorted(set(price_verdicts))},
        },
        "entry_alignment_audit": {
            "counts": dict(align_counts),
            "verdict": (
                "ENTRY_ALIGNMENT_FALLBACK_HEAVY"
                if align_counts.get("ENTRY_PRICE_OUTSIDE_BAR_RANGE", 0) + align_counts.get("ENTRY_BAR_NOT_FOUND", 0)
                > max(3, len(positions) * 0.2)
                else "ENTRY_ALIGNMENT_ACCEPTABLE"
            ),
        },
        "quantity_audit": {"verdict": qty_verdict, "detail": fifo},
        "horizon_distribution": horizon,
        "forced_close_audit": {
            mid: {
                arm: (block.get("forced_close") or {})
                for arm, block in (methods.get(mid) or {}).get("strategies", {}).items()
            }
            for mid in methods
        },
        "holding_period_audit": {
            mid: {
                arm: (block.get("holding_period") or {})
                for arm, block in (methods.get(mid) or {}).get("strategies", {}).items()
            }
            for mid in methods
        },
        "pnl_concentration": {
            mid: {
                arm: (block.get("concentration") or {})
                for arm, block in (methods.get(mid) or {}).get("strategies", {}).items()
            }
            for mid in methods
        },
        "methodologies": methods,
        "strategy_results": {
            mid: (methods[mid].get("rankings_zero_cost") if mid in methods else None) for mid in methods
        },
        "actual_benchmark": {
            "sample_size": actual_bench.get("sample_size"),
            "actual_net_pnl_native_unnormalized": actual_bench.get("actual_net_pnl"),
            "note": "Native-currency unnormalized if mixed FX; not USD unless single-currency.",
            "currency_warning": ccy.get("verdict"),
        },
        "lot_attribution": {
            "rows": len(all_attr),
            "artifact": str(LOT_ATTR_CSV),
        },
        "extreme_lots": {
            "artifact": str(EXTREME_TRACES_JSON),
            "top_negative_by_strategy": top_neg,
        },
        "subgroup_results": {
            mid: {
                arm: (block.get("subgroups") or {})
                for arm, block in (methods.get(mid) or {}).get("strategies", {}).items()
            }
            for mid in methods
        },
        "cost_sensitivity": {
            mid: {
                "leader_zero_cost": (methods.get(mid) or {}).get("leader_zero_cost"),
                "leader_realistic_cost": (methods.get(mid) or {}).get("leader_realistic_cost"),
                "rankings_realistic_cost": (methods.get(mid) or {}).get("rankings_realistic_cost"),
            }
            for mid in methods
        },
        "methodology_flags": flags,
        "economic_verdict": e_verdict,
        "promotion_eligibility": False,
        "orders_executed": 0,
        "limitations": [
            "UNBOUNDED_AVAILABLE_HISTORY IS NOT THE SOLE PROMOTION BASIS",
            "NO LIVE CHANGE IS AUTHORIZED",
            "Mixed native currencies may be present; aggregates are not FX-normalized.",
            "download_history uses auto_adjust=True; entry prices may disagree with adjusted OHLC.",
            "Counterfactual replay remains path-dependent and not a live promotion basis.",
            "Closed-lot post-entry bar availability is short (often << 60/120); HORIZON_60/120 may have zero eligible lots.",
        ],
        "next_action": (
            "Interpret fair-horizon and actual-exit-capped results before any economic ranking; "
            "keep promotion_eligibility=false; reconcile FX/price-basis before capital claims."
        ),
    }

    if write_artifacts:
        if all_attr:
            pd.DataFrame(all_attr).to_csv(LOT_ATTR_CSV, index=False)
        EXTREME_TRACES_JSON.write_text(json.dumps(extreme_traces, indent=2, default=str), encoding="utf-8")
        OUTPUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")

    reset_replay_context()
    return report


def render_markdown(report: dict[str, Any]) -> str:
    u = report.get("universe") or {}
    methods = report.get("methodologies") or {}
    lines = [
        "# TAE Exit Replay Horizon Audit",
        "",
        f"Generated: `{report.get('generated_at')}`  ",
        f"Source commit: `{report.get('source_commit')}`  ",
        "",
        "## 1. Executive verdict",
        "",
        f"- Methodology flags: `{', '.join(report.get('methodology_flags') or [])}`",
        f"- Economic verdict: `{report.get('economic_verdict')}`",
        f"- promotion_eligibility: `{report.get('promotion_eligibility')}`",
        "",
        "**UNBOUNDED AVAILABLE HISTORY IS NOT THE SOLE PROMOTION BASIS**",
        "",
        "**NO LIVE CHANGE IS AUTHORIZED**",
        "",
        "## 2. Protected files",
        "",
        f"```json\n{json.dumps(report.get('protected_file_hashes'), indent=2)}\n```",
        f"Git diff status: `{json.dumps(report.get('protected_git_diff'))}`",
        "",
        "## 3. Universe and FIFO",
        "",
        f"- Total BUY lots: **{u.get('total_buy_lots')}** (OPEN {u.get('open')} / CLOSED {u.get('closed')})",
        f"- Audit cohort: `{u.get('audit_cohort')}` n={u.get('audit_lots')}",
        f"- FIFO: `{json.dumps(report.get('fifo_reconciliation'))}`",
        "",
        "## 4. Current unbounded result",
        "",
    ]
    unb = methods.get(METHOD_UNBOUNDED) or {}
    lines.append(f"- Leader (zero cost): `{unb.get('leader_zero_cost')}`")
    lines.append(f"- Rankings: `{json.dumps(unb.get('rankings_zero_cost'))}`")
    lines += ["", "## 5. Forced-close audit", "", f"```json\n{json.dumps(report.get('forced_close_audit', {}).get(METHOD_UNBOUNDED), indent=2, default=str)}\n```"]
    lines += ["", "## 6. Holding-period audit", "", f"```json\n{json.dumps(report.get('holding_period_audit', {}).get(METHOD_UNBOUNDED), indent=2, default=str)}\n```"]
    lines += ["", "## 7. Horizon imbalance", "", f"```json\n{json.dumps(report.get('horizon_distribution'), indent=2, default=str)}\n```"]
    lines += ["", "## 8. Currency audit", "", f"```json\n{json.dumps(report.get('currency_audit'), indent=2, default=str)}\n```"]
    lines += ["", "## 9. Quantity audit", "", f"- Verdict: `{report.get('quantity_audit', {}).get('verdict')}`"]
    lines += ["", "## 10. Price adjustment audit", "", f"```json\n{json.dumps(report.get('price_basis_audit'), indent=2, default=str)}\n```"]
    lines += ["", "## 11. Entry alignment", "", f"```json\n{json.dumps(report.get('entry_alignment_audit'), indent=2, default=str)}\n```"]
    lines += ["", "## 12. PnL concentration", "", f"```json\n{json.dumps(report.get('pnl_concentration', {}).get(METHOD_UNBOUNDED), indent=2, default=str)}\n```"]
    lines += ["", "## 13. Top negative contributors", "", f"```json\n{json.dumps(report.get('extreme_lots', {}).get('top_negative_by_strategy'), indent=2, default=str)}\n```"]

    for title, mid in [
        ("14. Actual-exit-capped results", METHOD_ACTUAL_CAP),
        ("15. 20-bar results", METHOD_H20),
        ("16. 60-bar results", METHOD_H60),
        ("17. 120-bar results", METHOD_H120),
    ]:
        m = methods.get(mid) or {}
        lines += [
            "",
            f"## {title}",
            "",
            f"- Eligible: `{m.get('eligible_lots')}` / attempted `{m.get('attempted_lots')}`",
            f"- Exclusions: `{m.get('exclusions')}`",
            f"- Leader zero-cost: `{m.get('leader_zero_cost')}`",
            f"- Leader realistic-cost: `{m.get('leader_realistic_cost')}`",
            f"- Rankings: `{json.dumps(m.get('rankings_zero_cost'))}`",
        ]

    lines += [
        "",
        "## 18. Zero-cost vs realistic-cost",
        "",
        f"```json\n{json.dumps(report.get('cost_sensitivity'), indent=2, default=str)}\n```",
        "",
        "## 19. Subgroup stability",
        "",
        "See JSON `subgroup_results` (region/currency/year/vol/actual/hold).",
        "",
        "## 20. Actual benchmark vs challengers",
        "",
        f"```json\n{json.dumps(report.get('actual_benchmark'), indent=2, default=str)}\n```",
        "",
        "## 21. Methodology flags",
        "",
        f"`{report.get('methodology_flags')}`",
        "",
        "## 22. Economic verdict",
        "",
        f"`{report.get('economic_verdict')}`",
        "",
        "## 23. Limitations",
        "",
    ]
    for lim in report.get("limitations") or []:
        lines.append(f"- {lim}")
    lines += [
        "",
        "## 24. Next action",
        "",
        str(report.get("next_action")),
        "",
        "---",
        "",
        "UNBOUNDED AVAILABLE HISTORY IS NOT THE SOLE PROMOTION BASIS",
        "",
        "NO LIVE CHANGE IS AUTHORIZED",
        "",
    ]
    return "\n".join(lines)


def print_terminal_summary(report: dict[str, Any]) -> None:
    u = report.get("universe") or {}
    methods = report.get("methodologies") or {}
    print("=== TAE EXIT REPLAY HORIZON AUDIT ===")
    print(f"universe: {u.get('total_buy_lots')} lots (OPEN {u.get('open')} / CLOSED {u.get('closed')})")
    print(f"currency: {report.get('currency_audit', {}).get('verdict')}")
    print(f"quantity: {report.get('quantity_audit', {}).get('verdict')}")
    print(f"price_basis: {report.get('price_basis_audit', {}).get('worst_verdict')}")
    print(f"entry_alignment: {report.get('entry_alignment_audit', {}).get('verdict')}")
    print(f"horizon: {report.get('horizon_distribution', {}).get('horizon_verdict')}")
    for mid in (METHOD_UNBOUNDED, METHOD_ACTUAL_CAP, METHOD_H20, METHOD_H60, METHOD_H120):
        m = methods.get(mid) or {}
        print(f"{mid}: leader={m.get('leader_zero_cost')} cost_leader={m.get('leader_realistic_cost')} rankings={m.get('rankings_zero_cost')}")
    print(f"actual_benchmark: {report.get('actual_benchmark')}")
    print(f"methodology_flags: {report.get('methodology_flags')}")
    print(f"economic_verdict: {report.get('economic_verdict')}")
    print(f"promotion_eligibility: {report.get('promotion_eligibility')}")
    print(f"orders_executed: {report.get('orders_executed')}")
    print(f"next_action: {report.get('next_action')}")
    print("UNBOUNDED AVAILABLE HISTORY IS NOT THE SOLE PROMOTION BASIS")
    print("NO LIVE CHANGE IS AUTHORIZED")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TAE exit replay horizon / attribution audit (READ_ONLY)")
    p.add_argument("--cohort", choices=["open", "closed", "all", "OPEN_ONLY", "CLOSED_ONLY", "ALL"], default="closed")
    p.add_argument("--include-h252", action="store_true")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    cohort_map = {"open": "OPEN_ONLY", "closed": "CLOSED_ONLY", "all": "ALL"}
    cohort = cohort_map.get(str(args.cohort).lower(), str(args.cohort).upper())
    report = run_audit(
        cohort=cohort,
        write_artifacts=not args.no_write,
        include_h252=bool(args.include_h252),
    )
    print_terminal_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
