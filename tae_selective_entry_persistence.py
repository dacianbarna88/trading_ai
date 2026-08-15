#!/usr/bin/env python3
"""
SELECTIVE_ENTRY_PERSISTENCE GATE — last allowed B1 sprint.

Applies unchanged decide_b1 only when an ex-ante gate says the BUY looks premature.
Uses chronological portfolio replay. Does NOT modify B1, live_bot, stops, trailing, FX, sizing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from research_core.accounting.accounting_snapshot import build_accounting_snapshot
from research_core.accounting.fx_normalize import instrument_currency
from tae_chronological_portfolio_replay import (
    STARTING_CAPITAL,
    build_features,
    capital_stats,
    compare_b1_to_a,
    evaluate_reliability,
    excl_tickers,
    excl_top_n_trades,
    load_portfolio_events,
    metrics_from_variant,
    reconcile_control_a,
    run_variant,
    temporal_split_metrics,
)
from tae_entry_quality_ab import (
    B1_CONFIRMATIONS,
    B3_EXT_ATR,
    _bar_index_for,
    decide_b1,
)
from tae_exit_strategy_bar_replay import volatility_bucket

SCHEMA = "tae.selective_entry_persistence.v1"
OUTPUT_JSON = Path("tae_selective_entry_persistence_results.json")
OUTPUT_MD = Path("TAE_SELECTIVE_ENTRY_PERSISTENCE_RESULTS.md")
DESIGN_MD = Path("TAE_SELECTIVE_ENTRY_PERSISTENCE_DESIGN.md")
PROTECTED = ("live_bot.py", "core/trailing.py")
BAN = {"MU", "AMAT", "SIE.DE"}

# Neighbor thresholds (dev-defined, frozen on validation)
G1_STREAK_MAX = (1, 2)          # apply B1 if eligible_streak <= k
G2_DELTA_MAX = (0, 10)          # apply B1 if score_delta <= k (0=stagnant/down; 10=not improved by 10)
G3_EXT_THETA = (1.5, 2.0, 2.5)  # apply B1 if ext_atr > theta

# Primary thresholds chosen on development only (see diagnose + freeze)
PRIMARY = {
    "G1": {"streak_max": 1},
    "G2": {"delta_max": 0},
    "G3": {"ext_theta": 2.0},
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(path: str) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"


def enrich_features_with_bars(
    features: dict[str, pd.DataFrame],
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    """Join causal ATR_Pct / Trend_State onto feat when bars available. No new indicators."""
    out: dict[str, pd.DataFrame] = {}
    bars_by_ticker = bars_by_ticker or {}
    for t, feat in features.items():
        if feat.empty:
            out[t] = feat
            continue
        f = feat.copy()
        bars = bars_by_ticker.get(t)
        if bars is not None and not bars.empty:
            for col in ("ATR_Pct", "Trend_State", "High", "Low"):
                if col in bars.columns and col not in f.columns:
                    f[col] = bars[col].reindex(f.index)
        out[t] = f
    return out


@dataclass
class SignalSnapshot:
    ticker: str
    ts: str
    score: float | None
    rsi: float | None
    eligible: bool | None
    eligible_streak: int
    score_delta: float | None
    score_trend: str
    ext_atr: float | None
    pct_from_20h: float | None
    atr_pct: float | None
    trend_state: str | None
    vol_bucket: str | None
    currency: str
    first_day_signal: bool
    already_persistent_for_b1: bool


def signal_snapshot(
    feat: pd.DataFrame,
    ts,
    ticker: str,
    *,
    b1_confirmations: int = 1,
    vol_p33: float | None = None,
    vol_p66: float | None = None,
) -> SignalSnapshot:
    """Ex-ante features only — no confirmation-bar / outcome fields."""
    cur = instrument_currency(ticker)
    empty = SignalSnapshot(
        ticker=ticker, ts=str(ts), score=None, rsi=None, eligible=None,
        eligible_streak=0, score_delta=None, score_trend="UNKNOWN",
        ext_atr=None, pct_from_20h=None, atr_pct=None, trend_state=None,
        vol_bucket=None, currency=cur, first_day_signal=True,
        already_persistent_for_b1=False,
    )
    if feat is None or feat.empty:
        return empty
    i0 = _bar_index_for(ts, feat.index)
    if i0 is None:
        return empty
    row = feat.iloc[i0]
    score = float(row["Score"]) if "Score" in feat.columns and pd.notna(row.get("Score")) else None
    rsi = float(row["RSI"]) if "RSI" in feat.columns and pd.notna(row.get("RSI")) else None
    eligible = bool(row["eligible"]) if "eligible" in feat.columns else None
    # streak of eligible ending at i0 (causal)
    streak = 0
    if "eligible" in feat.columns:
        for j in range(i0, -1, -1):
            if bool(feat.iloc[j]["eligible"]):
                streak += 1
            else:
                break
    score_delta = None
    score_trend = "UNKNOWN"
    if i0 > 0 and "Score" in feat.columns:
        prev = float(feat.iloc[i0 - 1]["Score"])
        if score is not None:
            score_delta = score - prev
            if score_delta > 1e-9:
                score_trend = "UP"
            elif score_delta < -1e-9:
                score_trend = "DOWN"
            else:
                score_trend = "FLAT"
    ext = float(row["ext_atr"]) if "ext_atr" in feat.columns and pd.notna(row.get("ext_atr")) else None
    pct20 = float(row["pct_from_20h"]) if "pct_from_20h" in feat.columns and pd.notna(row.get("pct_from_20h")) else None
    atr_pct = float(row["ATR_Pct"]) if "ATR_Pct" in feat.columns and pd.notna(row.get("ATR_Pct")) else None
    trend = str(row["Trend_State"]) if "Trend_State" in feat.columns and pd.notna(row.get("Trend_State")) else None
    vb = None
    if atr_pct is not None and vol_p33 is not None and vol_p66 is not None:
        vb = volatility_bucket(atr_pct, p33=vol_p33, p66=vol_p66)
    return SignalSnapshot(
        ticker=ticker,
        ts=str(ts),
        score=score,
        rsi=rsi,
        eligible=eligible,
        eligible_streak=streak,
        score_delta=score_delta,
        score_trend=score_trend,
        ext_atr=ext,
        pct_from_20h=pct20,
        atr_pct=atr_pct,
        trend_state=trend,
        vol_bucket=vb,
        currency=cur,
        first_day_signal=streak <= 1,
        already_persistent_for_b1=streak > b1_confirmations,
    )


def gate_g1(snap: SignalSnapshot, *, streak_max: int) -> tuple[bool, str]:
    """Apply B1 iff signal lacks prior persistence (first / short eligible streak)."""
    if snap.eligible_streak <= streak_max:
        return True, f"G1_STREAK_{snap.eligible_streak}<={streak_max}"
    return False, f"G1_BYPASS_STREAK_{snap.eligible_streak}"


def gate_g2(snap: SignalSnapshot, *, delta_max: float) -> tuple[bool, str]:
    """Apply B1 iff score stagnant/deteriorating / not improved beyond delta_max."""
    if snap.score_delta is None:
        return True, "G2_INSUFFICIENT_SCORE_DELTA_APPLY"  # conservative: apply B1
    if snap.score_delta <= delta_max:
        return True, f"G2_DELTA_{snap.score_delta}<={delta_max}"
    return False, f"G2_BYPASS_IMPROVING_{snap.score_delta}"


def gate_g3(snap: SignalSnapshot, *, ext_theta: float) -> tuple[bool, str]:
    """Apply B1 iff price extended beyond canonical ext_atr OR high-vol bucket."""
    if snap.ext_atr is None:
        # missing extension → do not invent; treat as non-extended bypass (insufficient)
        if snap.vol_bucket == "HIGH":
            return True, "G3_HIGH_VOL_NO_EXT"
        return False, "G3_BYPASS_NO_EXT"
    if float(snap.ext_atr) > ext_theta:
        return True, f"G3_EXT_{float(snap.ext_atr):.2f}>{ext_theta}"
    if snap.vol_bucket == "HIGH":
        return True, f"G3_HIGH_VOL_EXT_{float(snap.ext_atr):.2f}"
    return False, f"G3_BYPASS_EXT_{float(snap.ext_atr):.2f}"


def make_gate_fn(
    name: str,
    features: dict[str, pd.DataFrame],
    params: dict[str, Any],
    *,
    vol_p33: float | None,
    vol_p66: float | None,
    b1_confirmations: int = 1,
) -> Callable:
    def _fn(ev, feat, state) -> bool:
        snap = signal_snapshot(
            feat if feat is not None and not feat.empty else features.get(ev["ticker"], pd.DataFrame()),
            ev["ts"],
            ev["ticker"],
            b1_confirmations=b1_confirmations,
            vol_p33=vol_p33,
            vol_p66=vol_p66,
        )
        if name == "G1":
            apply, _ = gate_g1(snap, streak_max=int(params["streak_max"]))
        elif name == "G2":
            apply, _ = gate_g2(snap, delta_max=float(params["delta_max"]))
        elif name == "G3":
            apply, _ = gate_g3(snap, ext_theta=float(params["ext_theta"]))
        else:
            apply = True
        return apply

    return _fn


def _vol_thresholds(features: dict[str, pd.DataFrame]) -> tuple[float | None, float | None]:
    samples: list[float] = []
    for feat in features.values():
        if feat.empty or "ATR_Pct" not in feat.columns:
            continue
        samples.extend([float(x) for x in feat["ATR_Pct"].dropna().tail(60).tolist()])
    if len(samples) < 10:
        return None, None
    return float(np.percentile(samples, 33)), float(np.percentile(samples, 66))


def diagnose_winner_miss(
    *,
    base_events: list[dict[str, Any]],
    features: dict[str, pd.DataFrame],
    variant_a: dict[str, Any],
    variant_b1: dict[str, Any],
    vol_p33: float | None,
    vol_p66: float | None,
) -> dict[str, Any]:
    cmp_ = compare_b1_to_a(variant_a, variant_b1, metrics_from_variant(variant_a), metrics_from_variant(variant_b1))
    a_entries = {
        (t["ticker"], str(pd.Timestamp(t["entry_ts"]).normalize().date())): t
        for t in variant_a["trades"]
    }
    b_entries = {
        (t["ticker"], str(pd.Timestamp(t["entry_ts"]).normalize().date())): t
        for t in variant_b1["trades"]
    }
    # Classify each A closed trade
    rows = []
    for k, t in a_entries.items():
        in_b = k in b_entries
        pnl = float(t["pnl_usd"])
        if pnl > 0 and not in_b:
            label = "WINNER_MISSED"
        elif pnl < 0 and not in_b:
            label = "LOSS_AVOIDED"
        elif pnl > 0 and in_b:
            label = "WINNER_KEPT"
        elif pnl < 0 and in_b:
            label = "LOSS_KEPT"
        else:
            label = "FLAT_OR_OTHER"
        feat = features.get(t["ticker"], pd.DataFrame())
        snap = signal_snapshot(
            feat, t["entry_ts"], t["ticker"],
            b1_confirmations=B1_CONFIRMATIONS, vol_p33=vol_p33, vol_p66=vol_p66,
        )
        dec = decide_b1(feat, t["entry_ts"], 1000.0, B1_CONFIRMATIONS)
        rows.append({
            "label": label,
            "ticker": t["ticker"],
            "entry_ts": t["entry_ts"],
            "pnl_usd": pnl,
            "b1_status": dec.status,
            "b1_reason": dec.reason,
            "eligible_streak": snap.eligible_streak,
            "first_day_signal": snap.first_day_signal,
            "score": snap.score,
            "score_delta": snap.score_delta,
            "score_trend": snap.score_trend,
            "ext_atr": snap.ext_atr,
            "pct_from_20h": snap.pct_from_20h,
            "vol_bucket": snap.vol_bucket,
            "trend_state": snap.trend_state,
            "currency": snap.currency,
        })

    def subset(lab: str) -> list[dict]:
        return [r for r in rows if r["label"] == lab]

    missed = subset("WINNER_MISSED")
    avoided = subset("LOSS_AVOIDED")

    def mean_field(rs: list[dict], field: str) -> float | None:
        vals = [r[field] for r in rs if r.get(field) is not None and not (isinstance(r[field], float) and np.isnan(r[field]))]
        return round(float(np.mean(vals)), 4) if vals else None

    def rate(rs: list[dict], pred) -> float | None:
        if not rs:
            return None
        return round(sum(1 for r in rs if pred(r)) / len(rs), 4)

    separation = {
        "n_winner_missed": len(missed),
        "n_loss_avoided": len(avoided),
        "missed_mean_streak": mean_field(missed, "eligible_streak"),
        "avoided_mean_streak": mean_field(avoided, "eligible_streak"),
        "missed_first_day_rate": rate(missed, lambda r: r["first_day_signal"]),
        "avoided_first_day_rate": rate(avoided, lambda r: r["first_day_signal"]),
        "missed_mean_score_delta": mean_field(missed, "score_delta"),
        "avoided_mean_score_delta": mean_field(avoided, "score_delta"),
        "missed_down_or_flat_rate": rate(missed, lambda r: r["score_trend"] in {"DOWN", "FLAT"}),
        "avoided_down_or_flat_rate": rate(avoided, lambda r: r["score_trend"] in {"DOWN", "FLAT"}),
        "missed_mean_ext_atr": mean_field(missed, "ext_atr"),
        "avoided_mean_ext_atr": mean_field(avoided, "ext_atr"),
        "missed_ext_gt_2_rate": rate(missed, lambda r: r.get("ext_atr") is not None and float(r["ext_atr"]) > 2.0),
        "avoided_ext_gt_2_rate": rate(avoided, lambda r: r.get("ext_atr") is not None and float(r["ext_atr"]) > 2.0),
        "missed_b1_cancelled_rate": rate(missed, lambda r: r["b1_status"] == "CANCELLED"),
        "avoided_b1_cancelled_rate": rate(avoided, lambda r: r["b1_status"] == "CANCELLED"),
        "missed_b1_delayed_rate": rate(missed, lambda r: r["b1_status"] == "DELAYED"),
        "avoided_b1_delayed_rate": rate(avoided, lambda r: r["b1_status"] == "DELAYED"),
    }

    # Separating power flags (ex-ante observable direction expected for useful gate)
    feature_power = {
        "eligible_streak": {
            "direction_expected": "avoided streak shorter than missed",
            "observed_delta_avoided_minus_missed": (
                None if separation["avoided_mean_streak"] is None or separation["missed_mean_streak"] is None
                else round(separation["avoided_mean_streak"] - separation["missed_mean_streak"], 4)
            ),
            "useful_if": "negative delta (losses shorter streak)",
        },
        "score_delta": {
            "direction_expected": "avoided delta lower (worse) than missed",
            "observed_delta_avoided_minus_missed": (
                None if separation["avoided_mean_score_delta"] is None or separation["missed_mean_score_delta"] is None
                else round(separation["avoided_mean_score_delta"] - separation["missed_mean_score_delta"], 4)
            ),
            "useful_if": "negative",
        },
        "ext_atr": {
            "direction_expected": "avoided more extended than missed",
            "observed_delta_avoided_minus_missed": (
                None if separation["avoided_mean_ext_atr"] is None or separation["missed_mean_ext_atr"] is None
                else round(separation["avoided_mean_ext_atr"] - separation["missed_mean_ext_atr"], 4)
            ),
            "useful_if": "positive",
        },
    }

    # Winner-miss diagnostics (frozen classification; no gate retune from this list)
    winner_diag = []
    for r in missed:
        if r["b1_status"] == "CANCELLED":
            cls = "confirmation timing" if "SIGNAL_LOST" in str(r["b1_reason"]) else "gate too broad"
        elif r["b1_status"] == "DELAYED":
            cls = "confirmation timing"
        else:
            cls = "indistinguishable ex ante"
        # If features look like "safe" (persistent, improving, non-extended) — gate too broad if we still applied B1 full
        if r["eligible_streak"] > 1 and r["score_trend"] == "UP" and (r.get("ext_atr") is None or float(r["ext_atr"]) <= 2.0):
            cls = "indistinguishable ex ante"
        winner_diag.append({
            "ticker": r["ticker"],
            "timestamp": r["entry_ts"],
            "features": {
                "eligible_streak": r["eligible_streak"],
                "score": r["score"],
                "score_delta": r["score_delta"],
                "score_trend": r["score_trend"],
                "ext_atr": r["ext_atr"],
                "vol_bucket": r["vol_bucket"],
            },
            "b1_status": r["b1_status"],
            "b1_reason": r["b1_reason"],
            "profit_missed_usd": r["pnl_usd"],
            "classification": cls,
            "note": "Classification frozen; gates not retuned from this list",
        })

    return {
        "compare_b1_full": cmp_,
        "separation": separation,
        "feature_power": feature_power,
        "winner_miss_diagnostics": winner_diag,
        "sample_rows": rows,
    }


def evaluate_gate_economic(
    a_m: dict[str, Any],
    g_m: dict[str, Any],
    cmp_: dict[str, Any],
    *,
    temporal: dict[str, Any],
    excl: dict[str, Any],
    excl_top2: dict[str, Any],
    capital_a: dict[str, Any],
    capital_g: dict[str, Any],
    gate_apply_frac: float,
    sensitivity_ok: bool,
) -> dict[str, Any]:
    flags: list[str] = []
    ok = True
    if cmp_["winner_miss_rate"] >= 0.25:
        ok = False
        flags.append("WINNER_MISS_GE_25PCT")
    if g_m["net_pnl_usd"] <= a_m["net_pnl_usd"]:
        ok = False
        flags.append("PNL_NOT_IMPROVED")
    if g_m["expectancy"] <= a_m["expectancy"]:
        ok = False
        flags.append("EXPECTANCY_NOT_IMPROVED")
    if g_m["account_value"] <= a_m["account_value"]:
        ok = False
        flags.append("ACCOUNT_VALUE_NOT_IMPROVED")
    if abs(g_m["max_drawdown_account"]) > abs(a_m["max_drawdown_account"]) + 1e-9:
        ok = False
        flags.append("MAXDD_WORSE")
    if cmp_["losses_avoided_usd"] <= cmp_["profits_missed_usd"]:
        ok = False
        flags.append("AVOIDED_NOT_GT_MISSED")
    if temporal["val"]["net_pnl_usd"] < temporal["val_a"]["net_pnl_usd"] - 1e-9:
        ok = False
        flags.append("VALIDATION_WORSE")
    if temporal["dev"]["net_pnl_usd"] <= temporal["dev_a"]["net_pnl_usd"]:
        ok = False
        flags.append("DEV_NOT_IMPROVED")
    if excl["g"]["net_pnl_usd"] <= excl["a"]["net_pnl_usd"]:
        ok = False
        flags.append("NO_EDGE_WITHOUT_MU_AMAT_SIE")
    if excl_top2["g"]["net_pnl_usd"] <= excl_top2["a"]["net_pnl_usd"]:
        ok = False
        flags.append("EDGE_DEPENDS_ON_TOP2")
    ccy_pos = sum(
        1 for c in ("USD", "EUR", "GBp", "GBP")
        if (g_m.get("by_currency_usd") or {}).get(c, 0) - (a_m.get("by_currency_usd") or {}).get(c, 0) > 0
    )
    if ccy_pos < 2:
        ok = False
        flags.append("FEWER_THAN_TWO_CURRENCY_BOOKS")
    # utilization not disproportionately lower
    ua = capital_a.get("avg_utilization")
    ug = capital_g.get("avg_utilization")
    if ua is not None and ug is not None and ug < ua - 0.25:
        ok = False
        flags.append("UTILIZATION_COLLAPSE")
    # targeted fraction: not almost all, not almost none
    if gate_apply_frac >= 0.85:
        ok = False
        flags.append("GATE_TOO_BROAD")
    if gate_apply_frac <= 0.05:
        ok = False
        flags.append("GATE_TOO_NARROW")
    if not sensitivity_ok:
        ok = False
        flags.append("SENSITIVITY_UNSTABLE")
    return {"passes": ok and not flags, "flags": sorted(set(flags)), **cmp_, "gate_apply_frac": gate_apply_frac}


def _pack_temporal(trades: list[dict], trades_a: list[dict]) -> dict[str, Any]:
    dev, val, mid = temporal_split_metrics(trades)
    dev_a, val_a, mid_a = temporal_split_metrics(trades_a)
    return {"dev": dev, "val": val, "mid": mid, "dev_a": dev_a, "val_a": val_a, "mid_a": mid_a}


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
    # Join causal ATR_Pct / Trend_State from enriched bars (no new indicators).
    if bars_by_ticker is None:
        from tae_exit_strategy_bar_replay import download_enriched_bars, enrich_bars_causal
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
    vol_p33, vol_p66 = _vol_thresholds(features)

    def rv(mode, conf=0, gate=None, gname=None, params=None):
        gfn = None
        if gate is not None and params is not None:
            gfn = make_gate_fn(gate, features, params, vol_p33=vol_p33, vol_p66=vol_p66, b1_confirmations=1)
        return run_variant(
            mode=mode,
            b1_confirmations=conf,
            base_events=base_events,
            features=features,
            marks=marks,
            fx_fetcher=fx_fetcher,
            apply_b1_gate=gfn,
            gate_name=gname,
        )

    raw: dict[str, Any] = {
        "A": rv("A", 0),
        "B1_FULL": rv("B1", 1),  # unchanged B1-1 on all BUYs
        "G1": rv("B1", 1, "G1", "G1", PRIMARY["G1"]),
        "G2": rv("B1", 1, "G2", "G2", PRIMARY["G2"]),
        "G3": rv("B1", 1, "G3", "G3", PRIMARY["G3"]),
    }
    metrics = {k: metrics_from_variant(v) for k, v in raw.items()}
    snapshot = build_accounting_snapshot(Path("."), portfolio_path=portfolio_path)
    recon_a = reconcile_control_a(raw["A"], snapshot)
    reliability = evaluate_reliability(recon_a, {"A": raw["A"], "B1_FULL": raw["B1_FULL"]})

    diagnosis = diagnose_winner_miss(
        base_events=base_events,
        features=features,
        variant_a=raw["A"],
        variant_b1=raw["B1_FULL"],
        vol_p33=vol_p33,
        vol_p66=vol_p66,
    )

    comparisons = {
        k: compare_b1_to_a(raw["A"], raw[k], metrics["A"], metrics[k])
        for k in ("B1_FULL", "G1", "G2", "G3")
    }
    capital = {k: capital_stats(raw[k]) for k in raw}
    exclusions = {k: excl_tickers(raw[k]["trades"], BAN) for k in raw}
    excl_top2 = {k: excl_top_n_trades(raw[k]["trades"], 2) for k in raw}
    # worst two (most negative)
    excl_worst2 = {}
    for k in raw:
        ranked = sorted(raw[k]["trades"], key=lambda t: float(t["pnl_usd"]))
        ban_ids = {t["lot_id"] for t in ranked[:2]}
        sel = [t for t in raw[k]["trades"] if t["lot_id"] not in ban_ids]
        excl_worst2[k] = {
            "net_pnl_usd": round(sum(float(t["pnl_usd"]) for t in sel), 4) if sel else 0.0,
            "n": len(sel),
            "excluded": [{"ticker": t["ticker"], "pnl_usd": float(t["pnl_usd"])} for t in ranked[:2]],
        }

    # Sensitivity: neighbor thresholds must also beat A on PnL (stable zone)
    sensitivity: dict[str, Any] = {"G1": [], "G2": [], "G3": []}
    for k in G1_STREAK_MAX:
        v = rv("B1", 1, "G1", f"G1_s{k}", {"streak_max": k})
        m = metrics_from_variant(v)
        sensitivity["G1"].append({
            "streak_max": k,
            "net_pnl_usd": m["net_pnl_usd"],
            "winner_miss_rate": compare_b1_to_a(raw["A"], v, metrics["A"], m)["winner_miss_rate"],
            "beats_a_pnl": m["net_pnl_usd"] > metrics["A"]["net_pnl_usd"],
        })
    for d in G2_DELTA_MAX:
        v = rv("B1", 1, "G2", f"G2_d{d}", {"delta_max": d})
        m = metrics_from_variant(v)
        sensitivity["G2"].append({
            "delta_max": d,
            "net_pnl_usd": m["net_pnl_usd"],
            "winner_miss_rate": compare_b1_to_a(raw["A"], v, metrics["A"], m)["winner_miss_rate"],
            "beats_a_pnl": m["net_pnl_usd"] > metrics["A"]["net_pnl_usd"],
        })
    for th in G3_EXT_THETA:
        v = rv("B1", 1, "G3", f"G3_e{th}", {"ext_theta": th})
        m = metrics_from_variant(v)
        sensitivity["G3"].append({
            "ext_theta": th,
            "net_pnl_usd": m["net_pnl_usd"],
            "winner_miss_rate": compare_b1_to_a(raw["A"], v, metrics["A"], m)["winner_miss_rate"],
            "beats_a_pnl": m["net_pnl_usd"] > metrics["A"]["net_pnl_usd"],
        })

    def sens_ok(name: str) -> bool:
        rows = sensitivity[name]
        # at least 2 neighbors beat A on PnL
        return sum(1 for r in rows if r["beats_a_pnl"]) >= 2

    econ = {}
    for name in ("G1", "G2", "G3"):
        temporal = _pack_temporal(raw[name]["trades"], raw["A"]["trades"])
        econ[name] = evaluate_gate_economic(
            metrics["A"], metrics[name], comparisons[name],
            temporal=temporal,
            excl={"a": exclusions["A"], "g": exclusions[name]},
            excl_top2={"a": excl_top2["A"], "g": excl_top2[name]},
            capital_a=capital["A"],
            capital_g=capital[name],
            gate_apply_frac=float(metrics[name].get("gate_apply_frac") or 0),
            sensitivity_ok=sens_ok(name),
        )

    # Determinism smoke
    a2 = rv("A", 0)
    deterministic = abs(a2["ending_cash"] - raw["A"]["ending_cash"]) < 1e-6
    if not deterministic:
        reliability["reliable_for_promotion"] = False
        reliability["flags"] = list(reliability["flags"]) + ["NON_DETERMINISTIC"]

    any_pass = any(econ[g]["passes"] for g in ("G1", "G2", "G3"))
    if not reliability["reliable_for_promotion"]:
        verdict = "ENTRY_PERSISTENCE_EDGE_NON_TRANSFERABLE"
        recommendation = (
            "Replay reliability failed during selective sprint; do not PAPER. "
            "Close B1 direction — no further B1 variations."
        )
    elif any_pass:
        best = max(("G1", "G2", "G3"), key=lambda g: comparisons[g]["delta_net_pnl_usd"] if econ[g]["passes"] else -1e18)
        verdict = "SELECTIVE_ENTRY_PERSISTENCE_CANDIDATE_FOUND"
        recommendation = (
            f"{best} passes selective acceptance under chronological replay. "
            "Keep promotion_eligibility=false until explicit PAPER wiring sprint."
        )
    else:
        verdict = "ENTRY_PERSISTENCE_EDGE_NON_TRANSFERABLE"
        recommendation = (
            "No selective gate (G1/G2/G3) simultaneously cuts winner-miss <25% with robust "
            "economic edge. Close B1 / entry-persistence hypothesis. Do not combine gates, "
            "do not retune thresholds, do not PAPER. Reopen only with new forward data."
        )

    def slim(v: dict[str, Any]) -> dict[str, Any]:
        out = {k: v[k] for k in v if k not in {"events", "equity_curve", "trades"}}
        out["events_n"] = len(v["events"])
        out["trades"] = v["trades"]
        out["equity_curve_n"] = len(v["equity_curve"])
        return out

    hashes_after = {f: _sha(f) for f in PROTECTED}
    report = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "source_commit_expected": "5847af4",
        "experiment": "SELECTIVE_ENTRY_PERSISTENCE_GATE",
        "promotion_eligibility": False,
        "paper_ab_active": False,
        "verdict": verdict,
        "recommendation": recommendation,
        "reliable_for_promotion": reliability["reliable_for_promotion"],
        "reliability": reliability,
        "control_a_reconciliation": recon_a,
        "b1_definition_modified": False,
        "confirmations_used": 1,
        "primary_params": PRIMARY,
        "diagnosis": {
            "separation": diagnosis["separation"],
            "feature_power": diagnosis["feature_power"],
            "winner_miss_diagnostics": diagnosis["winner_miss_diagnostics"],
            "compare_b1_full": diagnosis["compare_b1_full"],
        },
        "metrics": metrics,
        "comparisons": comparisons,
        "economic_evaluations": econ,
        "sensitivity": sensitivity,
        "capital_utilization": capital,
        "exclusions_mu_amat_sie": exclusions,
        "exclusions_top2_abs_pnl": excl_top2,
        "exclusions_worst2": excl_worst2,
        "temporal": {k: _pack_temporal(raw[k]["trades"], raw["A"]["trades"]) for k in raw},
        "variants": {k: slim(v) for k, v in raw.items()},
        "protected_hashes": {"before": hashes_before, "after": hashes_after, "unchanged": hashes_before == hashes_after},
        "live_bot_modified": False,
        "hypothesis_closure_required": verdict == "ENTRY_PERSISTENCE_EDGE_NON_TRANSFERABLE",
    }
    if write:
        OUTPUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        OUTPUT_MD.write_text(render_md(report), encoding="utf-8")
        DESIGN_MD.write_text(render_design(report), encoding="utf-8")
    return report


def render_design(report: dict[str, Any]) -> str:
    sep = report["diagnosis"]["separation"]
    power = report["diagnosis"]["feature_power"]
    return "\n".join([
        "# TAE Selective Entry Persistence Design",
        "",
        f"Baseline: `{report['source_commit_expected']}` · B1-1 unchanged · last allowed B1 sprint",
        "",
        "## Winner-miss diagnosis (ex ante only)",
        f"```json\n{json.dumps(sep, indent=2)}\n```",
        "",
        "## Feature separating power",
        f"```json\n{json.dumps(power, indent=2)}\n```",
        "",
        "## Observable differences (winners missed vs losses avoided)",
        f"- First-day rate missed={sep.get('missed_first_day_rate')} vs avoided={sep.get('avoided_first_day_rate')}",
        f"- Mean eligible streak missed={sep.get('missed_mean_streak')} vs avoided={sep.get('avoided_mean_streak')}",
        f"- Mean score_delta missed={sep.get('missed_mean_score_delta')} vs avoided={sep.get('avoided_mean_score_delta')}",
        f"- Mean ext_atr missed={sep.get('missed_mean_ext_atr')} vs avoided={sep.get('avoided_mean_ext_atr')}",
        f"- B1 CANCELLED rate missed={sep.get('missed_b1_cancelled_rate')} vs avoided={sep.get('avoided_b1_cancelled_rate')}",
        "",
        "## Candidate rules (max 3, independent)",
        "1. **G1 ACTION/STABILITY** — apply B1 iff `eligible_streak <= k` (k∈{1,2}); persistent signals execute as A.",
        "2. **G2 QUALITY-DIRECTION** — apply B1 iff `score_delta <= d` (d∈{0,10}); clear score improvement executes as A.",
        "3. **G3 PRICE/REGIME** — apply B1 iff `ext_atr > θ` (θ∈{1.5,2.0,2.5}) or HIGH vol bucket; otherwise A.",
        "",
        "## Retrospective-only correlations (not used as gates)",
        "- MFE/MAE, hold duration, SELL reason, confirmation-bar Open/Close after signal.",
        "- Per-ticker hard bans (MU/AMAT/SIE) — exclusion stress only.",
        "",
        "## Overfitting risk",
        "- Small N of missed winners (~14) / avoided losses (~12) → any threshold easily overfit.",
        "- Neighbor sensitivity + temporal split + MU/AMAT/SIE and top-2 exclusions mandatory.",
        "- Gates not retuned after inspecting winner-miss ticker list.",
        "",
        "## Protected",
        "`decide_b1`, `live_bot.py`, trailing/hard-risk, FX/split, sizing/capacity, executive-review.",
        "",
    ])


def render_md(report: dict[str, Any]) -> str:
    m = report["metrics"]
    lines = [
        "# TAE Selective Entry Persistence Results",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Verdict: **`{report['verdict']}`**",
        f"reliable_for_promotion: `{report['reliable_for_promotion']}`",
        f"promotion_eligibility: `{report['promotion_eligibility']}`",
        "",
        "## A vs B1-FULL vs G1/G2/G3",
        "",
        "| Variant | net PnL | AV | cash | expectancy | maxDD | fills | delayed | cancel | miss% | apply_frac |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k in ("A", "B1_FULL", "G1", "G2", "G3"):
        x = m[k]
        miss = report["comparisons"].get(k, {}).get("winner_miss_rate", 0.0) if k != "A" else 0.0
        lines.append(
            f"| {k} | {x['net_pnl_usd']} | {x['account_value']} | {x['ending_cash']} | {x['expectancy']} | "
            f"{x['max_drawdown_account']} | {x['fills']} | {x['delayed']} | {x['cancelled']} | "
            f"{miss} | {x.get('gate_apply_frac', 0)} |"
        )
    lines += [
        "",
        "## Economic evaluations",
        f"```json\n{json.dumps(report['economic_evaluations'], indent=2)}\n```",
        "",
        "## Comparisons",
        f"```json\n{json.dumps(report['comparisons'], indent=2)}\n```",
        "",
        "## Sensitivity",
        f"```json\n{json.dumps(report['sensitivity'], indent=2)}\n```",
        "",
        "## Diagnosis separation",
        f"```json\n{json.dumps(report['diagnosis']['separation'], indent=2)}\n```",
        "",
        "## Recommendation",
        report["recommendation"],
        "",
        "NO LIVE CHANGE · B1 UNCHANGED · NO GATE COMBINATIONS · NO FURTHER B1 SPRINTS IF NON_TRANSFERABLE",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    report = run_experiment(write=not args.no_write)
    print("=== SELECTIVE ENTRY PERSISTENCE ===")
    print("verdict", report["verdict"])
    print("reliable", report["reliable_for_promotion"])
    for k, v in report["metrics"].items():
        c = report["comparisons"].get(k, {})
        print(
            k, "pnl", v["net_pnl_usd"], "AV", v["account_value"],
            "miss", c.get("winner_miss_rate"), "apply", v.get("gate_apply_frac"),
            "delayed", v["delayed"], "cancel", v["cancelled"],
        )
    print("econ", {k: {"passes": v["passes"], "flags": v["flags"]} for k, v in report["economic_evaluations"].items()})
    print("protected", report["protected_hashes"]["unchanged"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
