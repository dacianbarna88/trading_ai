#!/usr/bin/env python3
"""
TAE Entry Quality / Anti-Churn SHADOW A/B.

Control A = actual FIFO lots (canonical −733.72 USD closed).
B1 signal persistence · B2 score stable/improve · B3 anti-extension.
Does NOT modify live_bot, stops, trailing, FX, split, or sizing engines.
promotion_eligibility = false.
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

from core.indicators import calculate_rsi
from research_core.accounting.fx_normalize import build_lot_usd_ledger, instrument_currency
from research_core.accounting.price_basis_align import detect_split_ratio
from tae_exit_strategy_bar_replay import (
    ReplayLot,
    download_enriched_bars,
    enrich_bars_causal,
    reconstruct_fifo_lots,
    volatility_bucket,
)

SCHEMA = "tae.entry_quality_ab.v1"
OUTPUT_JSON = Path("tae_entry_quality_ab_results.json")
OUTPUT_MD = Path("TAE_ENTRY_QUALITY_AB_RESULTS.md")
PROTECTED = ("live_bot.py", "core/trailing.py")

MIN_SCORE = 80
B1_CONFIRMATIONS = 1
B2_MODE = "stable"  # stable | improve_10 | improve_20
B3_EXT_ATR = 2.0

SENS_B1 = (1, 2)
SENS_B2 = ("stable", "improve_10", "improve_20")
SENS_B3 = (1.5, 2.0, 2.5)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(path: str) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"


def live_score_from_close(close: pd.Series) -> pd.DataFrame:
    """Causal reconstruction of live_bot score/signal (SMA50 + RSI). No look-ahead."""
    c = close.astype(float)
    sma50 = c.rolling(window=50, min_periods=50).mean()
    rsi = calculate_rsi(c)
    score = pd.Series(0.0, index=c.index)
    score = score + np.where(c > sma50, 40.0, 0.0)
    score = score + np.where((rsi > 40) & (rsi < 65), 40.0, 0.0)
    score = score + np.where((rsi > 50) & (rsi < 60), 20.0, 0.0)
    signal = np.where(score >= MIN_SCORE, "STRONG BUY", np.where(rsi > 70, "TAKE PROFIT", "WAIT"))
    return pd.DataFrame({
        "Close": c,
        "SMA50": sma50,
        "RSI": rsi,
        "Score": score,
        "Signal": signal,
        "eligible": score >= MIN_SCORE,
    }, index=c.index)


def attach_extension(bars: pd.DataFrame, score_df: pd.DataFrame) -> pd.DataFrame:
    out = score_df.copy()
    atr = bars["ATR14"] if "ATR14" in bars.columns else pd.Series(np.nan, index=bars.index)
    out["ATR14"] = atr.reindex(out.index)
    out["ext_atr"] = (out["Close"] - out["SMA50"]) / out["ATR14"].replace(0, np.nan)
    if "High" in bars.columns:
        roll_high = bars["High"].rolling(20, min_periods=5).max()
        out["pct_from_20h"] = (out["Close"] / roll_high.reindex(out.index) - 1.0) * 100.0
    else:
        out["pct_from_20h"] = np.nan
    return out


@dataclass
class EntryDecision:
    status: str  # SAME | DELAYED | CANCELLED | ALLOW_INSUFFICIENT_DATA
    reason: str
    entry_timestamp: pd.Timestamp | None
    entry_price: float | None
    quantity: float | None
    score_at_decision: float | None = None
    delay_bars: int = 0


def _bar_index_for(ts, index: pd.DatetimeIndex) -> int | None:
    t = pd.Timestamp(ts).tz_localize(None).normalize()
    idx = index.tz_localize(None) if getattr(index, "tz", None) is not None else index
    # exact or first bar on/after
    pos = idx.searchsorted(t)
    if pos >= len(idx):
        return None
    return int(pos)


def decide_b1(feat: pd.DataFrame, entry_ts, invested: float, confirmations: int) -> EntryDecision:
    if feat.empty:
        return EntryDecision("CANCELLED", "NO_BARS", None, None, None)
    i0 = _bar_index_for(entry_ts, feat.index)
    if i0 is None:
        return EntryDecision("CANCELLED", "ENTRY_AFTER_HISTORY", None, None, None)
    elig = feat["eligible"].astype(bool)

    def window_ok(i: int) -> bool:
        if i < confirmations:
            return False
        w = elig.iloc[i - confirmations : i + 1]
        return bool(len(w) == confirmations + 1 and w.all())

    for i in range(i0, len(feat)):
        if not bool(elig.iloc[i]):
            if i == i0:
                # not eligible on entry day in reconstructed series — cancel (data conflict)
                return EntryDecision("CANCELLED", "NOT_ELIGIBLE_ON_ENTRY_BAR", None, None, None, float(feat.iloc[i]["Score"]))
            return EntryDecision("CANCELLED", "SIGNAL_LOST_BEFORE_CONFIRM", None, None, None, float(feat.iloc[i]["Score"]))
        if window_ok(i):
            px = float(feat.iloc[i]["Close"] if i == i0 else feat.iloc[i]["Close"])
            # delayed entries use that day's open if available via Close proxy already in feat;
            # prefer Open from underlying if present
            if i != i0 and "Open" in feat.columns and pd.notna(feat.iloc[i].get("Open")):
                px = float(feat.iloc[i]["Open"])
            qty = float(invested) / px if px > 0 else None
            if qty is None:
                return EntryDecision("CANCELLED", "BAD_PRICE", None, None, None)
            status = "SAME" if i == i0 else "DELAYED"
            return EntryDecision(
                status,
                "PERSISTENCE_MET" if status == "SAME" else f"DELAYED_{i - i0}_BARS",
                pd.Timestamp(feat.index[i]),
                px,
                qty,
                float(feat.iloc[i]["Score"]),
                delay_bars=i - i0,
            )
    return EntryDecision("CANCELLED", "NEVER_CONFIRMED", None, None, None)


def decide_b2(feat: pd.DataFrame, entry_ts, invested: float, mode: str) -> EntryDecision:
    if feat.empty:
        return EntryDecision("ALLOW_INSUFFICIENT_DATA", "NO_BARS", pd.Timestamp(entry_ts), None, None)
    i0 = _bar_index_for(entry_ts, feat.index)
    if i0 is None or i0 == 0:
        return EntryDecision("ALLOW_INSUFFICIENT_DATA", "NO_PRIOR_SCORE_BAR", pd.Timestamp(entry_ts), None, None)
    cur = float(feat.iloc[i0]["Score"])
    prev = float(feat.iloc[i0 - 1]["Score"])
    if mode == "stable":
        ok = cur >= prev
        reason_fail = "SCORE_DETERIORATED"
    elif mode == "improve_10":
        ok = cur >= prev + 10
        reason_fail = "SCORE_NOT_IMPROVED_10"
    else:
        ok = cur >= prev + 20
        reason_fail = "SCORE_NOT_IMPROVED_20"
    if not ok:
        return EntryDecision("CANCELLED", reason_fail, None, None, None, cur)
    px = float(feat.iloc[i0]["Close"])
    return EntryDecision("SAME", "SCORE_GATE_PASS", pd.Timestamp(feat.index[i0]), px, float(invested) / px, cur)


def decide_b3(feat: pd.DataFrame, entry_ts, invested: float, theta: float) -> EntryDecision:
    if feat.empty:
        return EntryDecision("ALLOW_INSUFFICIENT_DATA", "NO_BARS", pd.Timestamp(entry_ts), None, None)
    i0 = _bar_index_for(entry_ts, feat.index)
    if i0 is None:
        return EntryDecision("CANCELLED", "ENTRY_AFTER_HISTORY", None, None, None)
    ext = feat.iloc[i0].get("ext_atr")
    if ext is None or (isinstance(ext, float) and np.isnan(ext)):
        return EntryDecision("ALLOW_INSUFFICIENT_DATA", "NO_ATR_EXTENSION", pd.Timestamp(entry_ts), None, None)
    if float(ext) > theta:
        return EntryDecision("CANCELLED", f"EXTENDED_ATR_{float(ext):.2f}>{theta}", None, None, None, float(feat.iloc[i0]["Score"]))
    px = float(feat.iloc[i0]["Close"])
    return EntryDecision("SAME", "EXTENSION_OK", pd.Timestamp(feat.index[i0]), px, float(invested) / px, float(feat.iloc[i0]["Score"]))


@dataclass
class LotView:
    lot: ReplayLot
    invested_usd: float
    score_portfolio: float | None
    pnl_usd_a: float | None
    pnl_pct_a: float | None
    hold_days_a: float | None
    bars_held_proxy: int | None
    instrument_currency: str
    volatility_bucket: str
    feat: pd.DataFrame
    entry_month: str


def build_lot_views(
    lots: list[ReplayLot],
    portfolio_path: Path,
    *,
    fx_fetcher=None,
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
    fetcher: Callable | None = None,
) -> list[LotView]:
    pf = pd.read_csv(portfolio_path)
    invested_by_row: dict[int, float] = {}
    score_by_row: dict[int, float] = {}
    for idx, row in pf.iterrows():
        if str(row.get("Action", "")).upper() != "BUY":
            continue
        inv = pd.to_numeric(row.get("Invested"), errors="coerce")
        sc = pd.to_numeric(row.get("Score"), errors="coerce")
        invested_by_row[int(idx)] = float(inv) if pd.notna(inv) else float(row.get("Price", 0) or 0) * float(row.get("Shares", 0) or 0)
        if pd.notna(sc):
            score_by_row[int(idx)] = float(sc)

    cache: dict[str, pd.DataFrame] = dict(bars_by_ticker or {})
    atr_samples: list[float] = []
    for lot in lots:
        if lot.ticker not in cache:
            try:
                cache[lot.ticker] = download_enriched_bars(lot.ticker, fetcher=fetcher)
            except Exception:
                cache[lot.ticker] = pd.DataFrame()
        b = cache[lot.ticker]
        if not b.empty and "ATR_Pct" in b.columns:
            atr_samples.extend([float(x) for x in b["ATR_Pct"].dropna().tail(40).tolist()])
    vol_p33 = float(np.percentile(atr_samples, 33)) if atr_samples else 1.5
    vol_p66 = float(np.percentile(atr_samples, 66)) if atr_samples else 3.0

    views: list[LotView] = []
    for lot in lots:
        bars = cache.get(lot.ticker, pd.DataFrame())
        feat = pd.DataFrame()
        bucket = "UNKNOWN"
        if not bars.empty:
            # split awareness for feature alignment only
            _ = detect_split_ratio(float(lot.entry_price), bars, lot.entry_timestamp)
            if "ATR14" not in bars.columns:
                bars = enrich_bars_causal(bars[["Open", "High", "Low", "Close", "Volume"]])
            score_df = live_score_from_close(bars["Close"])
            score_df["Open"] = bars["Open"]
            feat = attach_extension(bars, score_df)
            start = pd.Timestamp(lot.entry_timestamp).tz_localize(None).normalize()
            prior = feat[feat.index <= start]
            if not prior.empty and "ATR_Pct" in bars.columns:
                atr_row = bars.loc[prior.index[-1]] if prior.index[-1] in bars.index else None
                if atr_row is not None and pd.notna(atr_row.get("ATR_Pct")):
                    bucket = volatility_bucket(float(atr_row["ATR_Pct"]), p33=vol_p33, p66=vol_p66)

        pnl_usd = None
        pnl_pct = None
        hold_days = None
        bars_held = None
        if lot.status == "CLOSED" and lot.exit_price is not None and lot.exit_timestamp is not None:
            led = build_lot_usd_ledger(
                lot_id=lot.lot_id,
                ticker=lot.ticker,
                entry_timestamp=lot.entry_timestamp,
                exit_timestamp=lot.exit_timestamp,
                entry_price_local=float(lot.entry_price),
                exit_price_local=float(lot.exit_price),
                quantity=float(lot.entry_quantity),
                fetcher=fx_fetcher,
            )
            pnl_usd = led.realized_pnl_usd
            pnl_pct = ((float(lot.exit_price) - float(lot.entry_price)) / float(lot.entry_price)) * 100.0
            hold_days = max(
                0.0,
                (pd.Timestamp(lot.exit_timestamp) - pd.Timestamp(lot.entry_timestamp)).total_seconds() / 86400.0,
            )
            if not feat.empty:
                i0 = _bar_index_for(lot.entry_timestamp, feat.index)
                i1 = _bar_index_for(lot.exit_timestamp, feat.index)
                if i0 is not None and i1 is not None:
                    bars_held = max(1, i1 - i0 + 1)

        invested = invested_by_row.get(int(lot.buy_row), float(lot.entry_price) * float(lot.entry_quantity))
        # Prefer USD cost basis when available
        if pnl_usd is not None:
            try:
                led0 = build_lot_usd_ledger(
                    lot_id=lot.lot_id,
                    ticker=lot.ticker,
                    entry_timestamp=lot.entry_timestamp,
                    exit_timestamp=lot.exit_timestamp,
                    entry_price_local=float(lot.entry_price),
                    exit_price_local=float(lot.exit_price),
                    quantity=float(lot.entry_quantity),
                    fetcher=fx_fetcher,
                )
                if led0.cost_basis_usd is not None:
                    invested = abs(float(led0.cost_basis_usd))
            except Exception:
                pass

        views.append(
            LotView(
                lot=lot,
                invested_usd=float(invested),
                score_portfolio=score_by_row.get(int(lot.buy_row)),
                pnl_usd_a=pnl_usd,
                pnl_pct_a=pnl_pct,
                hold_days_a=hold_days,
                bars_held_proxy=bars_held,
                instrument_currency=instrument_currency(lot.ticker),
                volatility_bucket=bucket,
                feat=feat,
                entry_month=str(pd.Timestamp(lot.entry_timestamp).to_period("M")),
            )
        )
    return views


def counterfactual_pnl_usd(
    view: LotView,
    dec: EntryDecision,
    *,
    fx_fetcher=None,
) -> dict[str, Any]:
    """Isolated outcome for a B decision vs actual A lot."""
    lot = view.lot
    if dec.status in {"CANCELLED"}:
        return {
            "status": "CANCELLED",
            "executed": False,
            "pnl_usd": None,
            "pnl_pct": None,
            "entry_timestamp": None,
            "entry_price": None,
            "quantity": None,
            "exit_timestamp": str(lot.exit_timestamp) if lot.exit_timestamp is not None else None,
            "exit_price": lot.exit_price,
            "bars_held": None,
            "net_effect_vs_a": None if view.pnl_usd_a is None else round(-float(view.pnl_usd_a), 4),
            "loss_avoided": abs(view.pnl_usd_a) if view.pnl_usd_a is not None and view.pnl_usd_a < 0 else 0.0,
            "profit_missed": float(view.pnl_usd_a) if view.pnl_usd_a is not None and view.pnl_usd_a > 0 else 0.0,
        }

    # ALLOW_INSUFFICIENT_DATA or SAME with None price → use A as-is
    if dec.status == "ALLOW_INSUFFICIENT_DATA" or dec.entry_price is None or dec.quantity is None:
        return {
            "status": lot.status,
            "executed": True,
            "pnl_usd": view.pnl_usd_a,
            "pnl_pct": view.pnl_pct_a,
            "entry_timestamp": str(lot.entry_timestamp),
            "entry_price": float(lot.entry_price),
            "quantity": float(lot.entry_quantity),
            "exit_timestamp": str(lot.exit_timestamp) if lot.exit_timestamp is not None else None,
            "exit_price": lot.exit_price,
            "bars_held": view.bars_held_proxy,
            "net_effect_vs_a": 0.0,
            "loss_avoided": 0.0,
            "profit_missed": 0.0,
            "same_as_a": True,
        }

    entry_ts = pd.Timestamp(dec.entry_timestamp)
    entry_px = float(dec.entry_price)
    qty = float(dec.quantity)

    if lot.status == "OPEN":
        return {
            "status": "OPEN",
            "executed": True,
            "pnl_usd": None,
            "pnl_pct": None,
            "entry_timestamp": str(entry_ts),
            "entry_price": entry_px,
            "quantity": qty,
            "exit_timestamp": None,
            "exit_price": None,
            "bars_held": None,
            "net_effect_vs_a": 0.0,
            "loss_avoided": 0.0,
            "profit_missed": 0.0,
            "delayed": dec.status == "DELAYED",
        }

    # CLOSED
    exit_ts = pd.Timestamp(lot.exit_timestamp)
    if entry_ts.normalize() > exit_ts.normalize():
        # missed the actual exit window → treat as cancelled for isolated effect
        return {
            "status": "CANCELLED",
            "executed": False,
            "pnl_usd": None,
            "reason": "DELAY_PAST_ACTUAL_EXIT",
            "net_effect_vs_a": None if view.pnl_usd_a is None else round(-float(view.pnl_usd_a), 4),
            "loss_avoided": abs(view.pnl_usd_a) if view.pnl_usd_a is not None and view.pnl_usd_a < 0 else 0.0,
            "profit_missed": float(view.pnl_usd_a) if view.pnl_usd_a is not None and view.pnl_usd_a > 0 else 0.0,
        }

    led = build_lot_usd_ledger(
        lot_id=lot.lot_id + "|B",
        ticker=lot.ticker,
        entry_timestamp=entry_ts,
        exit_timestamp=exit_ts,
        entry_price_local=entry_px,
        exit_price_local=float(lot.exit_price),
        quantity=qty,
        fetcher=fx_fetcher,
    )
    pnl = led.realized_pnl_usd
    pnl_pct = ((float(lot.exit_price) - entry_px) / entry_px) * 100.0 if entry_px else None
    bars_held = view.bars_held_proxy
    if not view.feat.empty:
        i0 = _bar_index_for(entry_ts, view.feat.index)
        i1 = _bar_index_for(exit_ts, view.feat.index)
        if i0 is not None and i1 is not None:
            bars_held = max(1, i1 - i0 + 1)
    delta = None if view.pnl_usd_a is None or pnl is None else round(float(pnl) - float(view.pnl_usd_a), 4)
    return {
        "status": "CLOSED",
        "executed": True,
        "pnl_usd": pnl,
        "pnl_pct": pnl_pct,
        "entry_timestamp": str(entry_ts),
        "entry_price": entry_px,
        "quantity": qty,
        "exit_timestamp": str(exit_ts),
        "exit_price": float(lot.exit_price),
        "bars_held": bars_held,
        "net_effect_vs_a": delta,
        "loss_avoided": 0.0,
        "profit_missed": 0.0,
        "delayed": dec.status == "DELAYED",
        "same_as_a": dec.status == "SAME" and abs(entry_px - float(lot.entry_price)) < 1e-9,
    }


def classify_case(view: LotView, outcome: dict[str, Any]) -> str:
    a = view.pnl_usd_a
    if not outcome.get("executed"):
        if a is not None and a < 0:
            return "LOSS_AVOIDED"
        if a is not None and a > 0:
            return "WIN_MISSED"
        return "TRADE_CANCELLED"
    if outcome.get("same_as_a"):
        if a is not None and a > 0:
            return "WIN_KEPT"
        return "UNCHANGED"
    b = outcome.get("pnl_usd")
    if a is None or b is None:
        return "OPEN_OR_INCOMPLETE"
    if b > a and a < 0:
        return "ENTRY_IMPROVED"
    if b < a and a > 0:
        return "ENTRY_WORSE_ON_WIN"
    if outcome.get("delayed") and b < a:
        return "ENTRY_MORE_EXPENSIVE"
    if a < 0 and b < 0 and b < a:
        return "LOSS_ONLY_DELAYED"
    if b > a:
        return "ENTRY_IMPROVED"
    return "ENTRY_WORSE"


def apply_variant(
    views: list[LotView],
    *,
    mode: str,
    b1_confirmations: int = B1_CONFIRMATIONS,
    b2_mode: str = B2_MODE,
    b3_theta: float = B3_EXT_ATR,
    fx_fetcher=None,
) -> dict[str, Any]:
    rows = []
    cfs = []
    for view in sorted(views, key=lambda v: (pd.Timestamp(v.lot.entry_timestamp), v.lot.ticker, v.lot.seq)):
        lot = view.lot
        invested = view.invested_usd
        if mode == "A":
            dec = EntryDecision("SAME", "CONTROL", pd.Timestamp(lot.entry_timestamp), float(lot.entry_price), float(lot.entry_quantity), view.score_portfolio)
            outcome = {
                "status": lot.status,
                "executed": True,
                "pnl_usd": view.pnl_usd_a,
                "pnl_pct": view.pnl_pct_a,
                "entry_timestamp": str(lot.entry_timestamp),
                "entry_price": float(lot.entry_price),
                "quantity": float(lot.entry_quantity),
                "exit_timestamp": str(lot.exit_timestamp) if lot.exit_timestamp is not None else None,
                "exit_price": lot.exit_price,
                "bars_held": view.bars_held_proxy,
                "net_effect_vs_a": 0.0,
                "loss_avoided": 0.0,
                "profit_missed": 0.0,
                "same_as_a": True,
            }
        else:
            if mode == "B1":
                dec = decide_b1(view.feat, lot.entry_timestamp, invested, b1_confirmations)
            elif mode == "B2":
                dec = decide_b2(view.feat, lot.entry_timestamp, invested, b2_mode)
            elif mode == "B3":
                dec = decide_b3(view.feat, lot.entry_timestamp, invested, b3_theta)
            else:
                raise ValueError(mode)
            # For SAME/DELAYED that reused Close≈A price path with SAME, prefer actual A fill if SAME
            if dec.status == "SAME" and dec.entry_price is not None:
                dec = EntryDecision(
                    "SAME",
                    dec.reason,
                    pd.Timestamp(lot.entry_timestamp),
                    float(lot.entry_price),
                    float(lot.entry_quantity),
                    dec.score_at_decision,
                    0,
                )
            outcome = counterfactual_pnl_usd(view, dec, fx_fetcher=fx_fetcher)

        row = {
            "lot_id": lot.lot_id,
            "ticker": lot.ticker,
            "region": lot.region,
            "entry_month": view.entry_month,
            "instrument_currency": view.instrument_currency,
            "volatility_bucket": view.volatility_bucket,
            "A_status": lot.status,
            "A_pnl_usd": view.pnl_usd_a,
            "A_bars_held": view.bars_held_proxy,
            "A_score": view.score_portfolio,
            "decision_status": dec.status,
            "decision_reason": dec.reason,
            "delay_bars": dec.delay_bars,
            "B_executed": bool(outcome.get("executed")),
            "B_status": outcome.get("status"),
            "B_pnl_usd": outcome.get("pnl_usd"),
            "B_pnl_pct": outcome.get("pnl_pct"),
            "B_entry_timestamp": outcome.get("entry_timestamp"),
            "B_entry_price": outcome.get("entry_price"),
            "B_quantity": outcome.get("quantity"),
            "B_bars_held": outcome.get("bars_held"),
            "class": classify_case(view, outcome),
            "loss_avoided": outcome.get("loss_avoided") or 0.0,
            "profit_missed": outcome.get("profit_missed") or 0.0,
            "net_effect_vs_a": outcome.get("net_effect_vs_a"),
        }
        rows.append(row)
        if mode != "A" and (dec.status != "SAME" or not outcome.get("same_as_a") or not outcome.get("executed")):
            cfs.append({
                **row,
                "price_A": float(lot.entry_price),
                "qty_A": float(lot.entry_quantity),
                "timestamp_A": str(lot.entry_timestamp),
                "reason_A": "EXECUTED",
                "reason_B": dec.reason,
            })
    return {"rows": rows, "counterfactuals": cfs}


def metrics_from_rows(rows: list[dict[str, Any]], *, counterfactuals: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    executed = [r for r in rows if r.get("B_executed")]
    closed = [r for r in executed if r.get("B_status") == "CLOSED" and r.get("B_pnl_usd") is not None]
    cancelled = [r for r in rows if not r.get("B_executed")]
    delayed = [r for r in rows if int(r.get("delay_bars") or 0) > 0 and r.get("B_executed")]
    pnls = pd.Series([float(r["B_pnl_usd"]) for r in closed], dtype=float) if closed else pd.Series(dtype=float)
    rets = pd.Series([float(r.get("B_pnl_pct") or 0.0) for r in closed], dtype=float) if closed else pd.Series(dtype=float)
    if len(pnls):
        ordered = sorted(closed, key=lambda r: pd.Timestamp(r.get("B_entry_timestamp") or "1970-01-01"))
        # drawdown by exit order using A exit when present
        cum = pd.Series([float(r["B_pnl_usd"]) for r in sorted(closed, key=lambda r: pd.Timestamp(str(r.get("B_entry_timestamp"))))], dtype=float).cumsum()
        mdd = float((cum - cum.cummax()).min())
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        gp = float(wins.sum()) if len(wins) else 0.0
        gl = float(abs(losses.sum())) if len(losses) else 0.0
        pf = None if gl == 0 and gp == 0 else (float("inf") if gl == 0 else round(gp / gl, 4))
        downside = pnls[pnls < 0]
        dd = float(np.sqrt((downside ** 2).mean())) if len(downside) else 0.0
    else:
        mdd = 0.0
        wins = pnls
        losses = pnls
        pf = None
        dd = 0.0

    fast = [r for r in closed if r.get("B_bars_held") is not None and int(r["B_bars_held"]) <= 3]
    fast_loss = sum(float(r["B_pnl_usd"]) for r in fast if float(r["B_pnl_usd"]) < 0)
    by_ccy: dict[str, float] = {}
    by_reg: dict[str, float] = {}
    by_t: dict[str, float] = {}
    for r in closed:
        by_ccy[r["instrument_currency"]] = by_ccy.get(r["instrument_currency"], 0.0) + float(r["B_pnl_usd"])
        by_reg[r["volatility_bucket"]] = by_reg.get(r["volatility_bucket"], 0.0) + float(r["B_pnl_usd"])
        by_t[r["ticker"]] = by_t.get(r["ticker"], 0.0) + float(r["B_pnl_usd"])

    a_wins = [r for r in rows if r.get("A_pnl_usd") is not None and float(r["A_pnl_usd"]) > 0]
    winners_kept = sum(1 for r in a_wins if r.get("B_executed") and r.get("B_pnl_usd") is not None and float(r["B_pnl_usd"]) > 0)
    winners_missed = sum(1 for r in a_wins if not r.get("B_executed"))
    a_losses = [r for r in rows if r.get("A_pnl_usd") is not None and float(r["A_pnl_usd"]) < 0]
    losses_avoided_n = sum(1 for r in a_losses if not r.get("B_executed"))
    losses_kept = sum(1 for r in a_losses if r.get("B_executed") and r.get("B_pnl_usd") is not None and float(r["B_pnl_usd"]) < 0)

    cfs = counterfactuals or []
    avoided = sum(float(r.get("loss_avoided") or 0) for r in rows)
    missed = sum(float(r.get("profit_missed") or 0) for r in rows)
    net_effect = sum(float(r["net_effect_vs_a"]) for r in rows if r.get("net_effect_vs_a") is not None)

    return {
        "n": len(closed),
        "signals": len(rows),
        "trades_executed": len(executed),
        "buys_delayed": len(delayed),
        "buys_cancelled": len(cancelled),
        "open_positions": sum(1 for r in executed if r.get("B_status") == "OPEN"),
        "net_pnl_usd": round(float(pnls.sum()), 4) if len(pnls) else 0.0,
        "return_pct_ew": round(float(rets.mean()), 4) if len(rets) else 0.0,
        "expectancy": round(float(pnls.mean()), 4) if len(pnls) else 0.0,
        "profit_factor": pf,
        "win_rate": round(float((pnls > 0).mean()), 4) if len(pnls) else 0.0,
        "average_win": round(float(wins.mean()), 4) if len(wins) else 0.0,
        "average_loss": round(float(losses.mean()), 4) if len(losses) else 0.0,
        "median_trade": round(float(pnls.median()), 4) if len(pnls) else 0.0,
        "max_drawdown": round(mdd, 4),
        "downside_deviation": round(dd, 4),
        "avg_delay_bars": round(float(np.mean([int(r.get("delay_bars") or 0) for r in rows])), 4) if rows else 0.0,
        "avg_holding_bars": round(float(np.mean([int(r["B_bars_held"]) for r in closed if r.get("B_bars_held") is not None])), 4) if any(r.get("B_bars_held") is not None for r in closed) else 0.0,
        "exits_0_2_bars": len(fast),
        "loss_usd_exits_0_2_bars": round(fast_loss, 4),
        "winners_kept": winners_kept,
        "winners_missed": winners_missed,
        "losses_avoided_n": losses_avoided_n,
        "losses_kept": losses_kept,
        "losses_avoided_usd": round(avoided, 4),
        "profits_missed_usd": round(missed, 4),
        "net_economic_effect_usd": round(net_effect, 4),
        "winner_block_rate": round(winners_missed / max(1, len(a_wins)), 4),
        "by_currency_usd": {k: round(v, 4) for k, v in sorted(by_ccy.items())},
        "by_regime_usd": {k: round(v, 4) for k, v in sorted(by_reg.items())},
        "by_ticker_usd": {k: round(v, 4) for k, v in sorted(by_t.items())},
        "capital_utilization_proxy": round(len(executed) / max(1, len(rows)), 4),
    }


def portfolio_replay_approx(views: list[LotView], variant_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Lightweight chronological replay: max concurrent slots = peak concurrent in A.
    Not a full live capacity engine — promotion requires reliability flag.
    """
    # peak concurrent in A
    events = []
    for v in views:
        events.append((pd.Timestamp(v.lot.entry_timestamp), 1, v.lot.lot_id))
        if v.lot.status == "CLOSED" and v.lot.exit_timestamp is not None:
            events.append((pd.Timestamp(v.lot.exit_timestamp), -1, v.lot.lot_id))
    events.sort(key=lambda x: (x[0], -x[1]))
    cur = peak = 0
    for _, d, _ in events:
        cur += d
        peak = max(peak, cur)

    by_id = {r["lot_id"]: r for r in variant_rows}
    slots = 0
    blocked_capacity = 0
    pnl = 0.0
    executed = 0
    for v in sorted(views, key=lambda x: pd.Timestamp(x.lot.entry_timestamp)):
        r = by_id[v.lot.lot_id]
        # free slots for exits that occurred before this entry among previously executed
        # (approximate: count closed A exits before entry among executed B)
        if r.get("B_executed"):
            if slots >= peak > 0:
                blocked_capacity += 1
                continue
            slots += 1
            executed += 1
            if r.get("B_pnl_usd") is not None:
                pnl += float(r["B_pnl_usd"])
            if v.lot.status == "CLOSED":
                slots = max(0, slots - 1)
    return {
        "status": "LIMITED_CHRONOLOGICAL_SLOTS",
        "reliable_for_promotion": False,
        "max_concurrent_slots_from_A": peak,
        "executed": executed,
        "blocked_by_capacity": blocked_capacity,
        "net_pnl_usd": round(pnl, 4),
        "note": "Approximation only — not full cash/capacity live engine; cannot alone justify PAPER.",
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
    lots = reconstruct_fifo_lots(portfolio_path)
    views = build_lot_views(
        lots,
        portfolio_path,
        fx_fetcher=fx_fetcher,
        bars_by_ticker=bars_by_ticker,
        fetcher=fetcher,
    )

    configs = {
        "A": dict(mode="A"),
        "B1": dict(mode="B1", b1_confirmations=B1_CONFIRMATIONS),
        "B2": dict(mode="B2", b2_mode=B2_MODE),
        "B3": dict(mode="B3", b3_theta=B3_EXT_ATR),
    }
    applied = {k: apply_variant(views, fx_fetcher=fx_fetcher, **cfg) for k, cfg in configs.items()}
    metrics = {k: metrics_from_rows(v["rows"], counterfactuals=v["counterfactuals"]) for k, v in applied.items()}

    # diagnosis buckets on A
    diagnosis = build_entry_diagnosis(views)

    months = sorted({v.entry_month for v in views})
    mid = months[len(months) // 2] if months else None

    def slice_m(var: str, which: str) -> dict[str, Any]:
        rows = applied[var]["rows"]
        if mid is None:
            return metrics_from_rows(rows)
        if which == "dev":
            sel = [r for r in rows if r["entry_month"] <= mid]
        else:
            sel = [r for r in rows if r["entry_month"] > mid]
        return metrics_from_rows(sel)

    temporal = {
        "split_month_inclusive_dev_max": mid,
        "dev": {k: slice_m(k, "dev") for k in configs},
        "val": {k: slice_m(k, "val") for k in configs},
    }

    def excl(var: str, tickers: set[str]) -> dict[str, Any]:
        rows = [r for r in applied[var]["rows"] if r["ticker"] not in tickers]
        return metrics_from_rows(rows)

    exclusions = {
        "exclude_MU_AMAT_SIE": {k: excl(k, {"MU", "AMAT", "SIE.DE"}) for k in configs},
        "exclude_CRWD": {k: excl(k, {"CRWD"}) for k in configs},
    }

    # drop best/worst 2 by A pnl contribution for robustness of B delta
    def excl_extreme(var: str, which: str) -> dict[str, Any]:
        closed_a = [r for r in applied["A"]["rows"] if r.get("A_pnl_usd") is not None]
        ranked = sorted(closed_a, key=lambda r: float(r["A_pnl_usd"]))
        drop = set()
        if which == "best2":
            drop = {r["lot_id"] for r in ranked[-2:]}
        else:
            drop = {r["lot_id"] for r in ranked[:2]}
        rows = [r for r in applied[var]["rows"] if r["lot_id"] not in drop]
        return metrics_from_rows(rows)

    extremes = {
        "without_best2": {k: excl_extreme(k, "best2") for k in configs},
        "without_worst2": {k: excl_extreme(k, "worst2") for k in configs},
    }

    sensitivity = {"B1": {}, "B2": {}, "B3": {}}
    for c in SENS_B1:
        app = apply_variant(views, mode="B1", b1_confirmations=c, fx_fetcher=fx_fetcher)
        sensitivity["B1"][str(c)] = metrics_from_rows(app["rows"], counterfactuals=app["counterfactuals"])
    for m in SENS_B2:
        app = apply_variant(views, mode="B2", b2_mode=m, fx_fetcher=fx_fetcher)
        sensitivity["B2"][m] = metrics_from_rows(app["rows"], counterfactuals=app["counterfactuals"])
    for th in SENS_B3:
        app = apply_variant(views, mode="B3", b3_theta=th, fx_fetcher=fx_fetcher)
        sensitivity["B3"][str(th)] = metrics_from_rows(app["rows"], counterfactuals=app["counterfactuals"])

    portfolio_replay = {k: portfolio_replay_approx(views, applied[k]["rows"]) for k in configs}

    def evaluate(name: str) -> dict[str, Any]:
        a, b = metrics["A"], metrics[name]
        flags = []
        ok = True
        if b["net_pnl_usd"] <= a["net_pnl_usd"]:
            ok = False
            flags.append("PNL_NOT_IMPROVED")
        if (b.get("expectancy") or -1e9) <= (a.get("expectancy") or 0):
            ok = False
            flags.append("EXPECTANCY_NOT_IMPROVED")
        if abs(b.get("max_drawdown") or 0) > abs(a.get("max_drawdown") or 0) + 1e-9:
            ok = False
            flags.append("MAXDD_WORSE")
        if b["loss_usd_exits_0_2_bars"] < a["loss_usd_exits_0_2_bars"] - 1e-9:
            ok = False
            flags.append("FAST_EXIT_LOSS_NOT_REDUCED")
        if b["losses_avoided_usd"] + max(0.0, b["net_pnl_usd"] - a["net_pnl_usd"]) <= b["profits_missed_usd"]:
            # prefer explicit avoided>missed when cancellations dominate
            if b["losses_avoided_usd"] <= b["profits_missed_usd"]:
                ok = False
                flags.append("AVOIDED_NOT_GT_MISSED")
        if temporal["val"][name]["net_pnl_usd"] < temporal["val"]["A"]["net_pnl_usd"] - 1e-9:
            ok = False
            flags.append("VALIDATION_WORSE")
        if temporal["dev"][name]["net_pnl_usd"] <= temporal["dev"]["A"]["net_pnl_usd"]:
            ok = False
            flags.append("DEV_NOT_IMPROVED")
        if exclusions["exclude_MU_AMAT_SIE"][name]["net_pnl_usd"] <= exclusions["exclude_MU_AMAT_SIE"]["A"]["net_pnl_usd"]:
            ok = False
            flags.append("NO_EDGE_WITHOUT_MU_AMAT_SIE")
        if exclusions["exclude_CRWD"][name]["net_pnl_usd"] <= exclusions["exclude_CRWD"]["A"]["net_pnl_usd"]:
            ok = False
            flags.append("NO_EDGE_WITHOUT_CRWD")
        if b.get("winner_block_rate", 0) > 0.25:
            ok = False
            flags.append("BLOCKS_GT_25PCT_WINNERS")
        if b.get("capital_utilization_proxy", 1) < a.get("capital_utilization_proxy", 1) * 0.6:
            ok = False
            flags.append("CAPITAL_UTILIZATION_COLLAPSE")

        # concentration of positive net effects
        pos = [r for r in applied[name]["rows"] if r.get("net_effect_vs_a") is not None and float(r["net_effect_vs_a"]) > 0]
        by_t: dict[str, float] = {}
        for r in pos:
            by_t[r["ticker"]] = by_t.get(r["ticker"], 0.0) + float(r["net_effect_vs_a"])
        total = sum(by_t.values()) or 1.0
        top_share = max(by_t.values()) / total if by_t else 1.0
        if top_share > 0.5:
            ok = False
            flags.append("TOO_CONCENTRATED_ONE_TICKER")
        top2 = sorted(pos, key=lambda r: -float(r["net_effect_vs_a"]))[:2]
        top2_sum = sum(float(r["net_effect_vs_a"]) for r in top2)
        pos_sum = sum(float(r["net_effect_vs_a"]) for r in pos) or 1.0
        if top2_sum / pos_sum > 0.85 and b["net_pnl_usd"] > a["net_pnl_usd"]:
            ok = False
            flags.append("TOP2_TRADES_DOMINATE")

        ccy_pos = sum(
            1 for c in ("USD", "EUR", "GBp", "GBP")
            if (b.get("by_currency_usd") or {}).get(c, 0) - (a.get("by_currency_usd") or {}).get(c, 0) > 0
        )
        reg_pos = sum(
            1 for reg, bv in (b.get("by_regime_usd") or {}).items()
            if bv - (a.get("by_regime_usd") or {}).get(reg, 0) > 0
        )
        if ccy_pos < 2 and reg_pos < 2:
            ok = False
            flags.append("FEWER_THAN_TWO_MARKETS_OR_REGIMES")

        # portfolio replay reliability is a PAPER gate, not an isolated economic fail
        paper_flags = []
        if not portfolio_replay[name].get("reliable_for_promotion"):
            paper_flags.append("PORTFOLIO_REPLAY_NOT_RELIABLE")
        elif portfolio_replay[name]["net_pnl_usd"] <= portfolio_replay["A"]["net_pnl_usd"]:
            paper_flags.append("PORTFOLIO_REPLAY_DOES_NOT_CONFIRM")

        return {
            "variant": name,
            "passes_economic": ok and not flags,
            "passes_paper": ok and not flags and not paper_flags,
            "passes": ok and not flags and not paper_flags,  # full accept = PAPER bar
            "flags": sorted(set(flags + paper_flags)),
            "economic_flags": sorted(set(flags)),
            "paper_flags": paper_flags,
            "delta_pnl_usd": round(b["net_pnl_usd"] - a["net_pnl_usd"], 4),
            "delta_expectancy": round((b.get("expectancy") or 0) - (a.get("expectancy") or 0), 4),
            "delta_maxdd": round(abs(b.get("max_drawdown") or 0) - abs(a.get("max_drawdown") or 0), 4),
            "buys_cancelled": b["buys_cancelled"],
            "buys_delayed": b["buys_delayed"],
            "winner_block_rate": b.get("winner_block_rate"),
            "top_ticker_pos_share": round(top_share, 4),
        }

    def sens_stable(name: str) -> bool:
        if name == "B1":
            vals = [sensitivity["B1"][str(c)]["net_pnl_usd"] for c in SENS_B1]
        elif name == "B2":
            vals = [sensitivity["B2"][m]["net_pnl_usd"] for m in SENS_B2]
        else:
            vals = [sensitivity["B3"][str(t)]["net_pnl_usd"] for t in SENS_B3]
        better = sum(1 for v in vals if v > metrics["A"]["net_pnl_usd"])
        spread = max(vals) - min(vals) if vals else 0
        if better < max(1, len(vals) - 1):
            return False
        if spread > abs(metrics["A"]["net_pnl_usd"]) * 0.4 + 50:
            return False
        return True

    evals = {n: evaluate(n) for n in ("B1", "B2", "B3")}
    economic_candidates = []
    paper_candidates = []
    for e in evals.values():
        stable = sens_stable(e["variant"])
        if e["passes_economic"] and stable:
            economic_candidates.append(e)
        elif e["passes_economic"] and not stable:
            e["passes_economic"] = False
            e["economic_flags"] = sorted(set(e["economic_flags"] + ["SENSITIVITY_UNSTABLE"]))
            e["flags"] = sorted(set(e["flags"] + ["SENSITIVITY_UNSTABLE"]))
        if e.get("passes_paper") and stable:
            paper_candidates.append(e)

    if paper_candidates:
        # Full PAPER accept met economically+replay — still no live splitter in this sprint
        verdict = "ENTRY_QUALITY_REPLAY_CANDIDATE_FOUND"
        paper = False
        candidates = paper_candidates
        recommendation = (
            f"Candidate {paper_candidates[0]['variant']} passes economic+replay gates in SHADOW form. "
            "Do NOT wire live_bot; no safe PAPER A/B splitter. promotion_eligibility=false."
        )
    elif economic_candidates:
        verdict = "ENTRY_QUALITY_REPLAY_CANDIDATE_FOUND"
        paper = False
        candidates = economic_candidates
        recommendation = (
            f"SHADOW economic candidate {economic_candidates[0]['variant']} "
            f"(ΔPnL={economic_candidates[0]['delta_pnl_usd']} USD). "
            "Do NOT wire PAPER: portfolio-replay engine not reliable enough to confirm. "
            "promotion_eligibility=false. Next: proper chronological portfolio replay before any PAPER."
        )
    else:
        verdict = "ENTRY_QUALITY_NO_EDGE"
        paper = False
        candidates = []
        recommendation = (
            "Reject B1/B2/B3 for PAPER. Do not start position sizing/capacity sprint. "
            "Stops and cooldown remain NO_EDGE."
        )

    hashes_after = {f: _sha(f) for f in PROTECTED}
    report = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "source_commit_expected": "45450a6",
        "promotion_eligibility": False,
        "paper_ab_active": paper,
        "verdict": verdict,
        "recommendation": recommendation,
        "universe": {
            "total_buy_lots": len(lots),
            "open": sum(1 for l in lots if l.status == "OPEN"),
            "closed": sum(1 for l in lots if l.status == "CLOSED"),
        },
        "parameters": {
            "B1_confirmations": B1_CONFIRMATIONS,
            "B2_mode": B2_MODE,
            "B3_ext_atr": B3_EXT_ATR,
            "min_score": MIN_SCORE,
        },
        "diagnosis": diagnosis,
        "metrics": metrics,
        "temporal": temporal,
        "exclusions": exclusions,
        "extremes": extremes,
        "sensitivity": sensitivity,
        "portfolio_replay": portfolio_replay,
        "evaluations": evals,
        "candidates": candidates,
        "economic_candidates": [e["variant"] for e in economic_candidates],
        "paper_candidates": [e["variant"] for e in paper_candidates],
        "counterfactuals": {k: applied[k]["counterfactuals"] for k in ("B1", "B2", "B3")},
        "scenario_primary": "isolated-entry-effect",
        "protected_hashes": {"before": hashes_before, "after": hashes_after, "unchanged": hashes_before == hashes_after},
        "live_bot_modified": False,
        "stops_modified": False,
        "baseline_control_net_pnl_usd": metrics["A"]["net_pnl_usd"],
    }
    if write:
        OUTPUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        OUTPUT_MD.write_text(render_results_md(report), encoding="utf-8")
    return report


def build_entry_diagnosis(views: list[LotView]) -> dict[str, Any]:
    rows = []
    for v in views:
        lot = v.lot
        first_day = None
        score_trend = "UNKNOWN"
        extended = None
        if not v.feat.empty:
            i0 = _bar_index_for(lot.entry_timestamp, v.feat.index)
            if i0 is not None:
                elig = v.feat["eligible"].astype(bool)
                # streak length ending at i0
                streak = 0
                j = i0
                while j >= 0 and bool(elig.iloc[j]):
                    streak += 1
                    j -= 1
                first_day = streak <= 1
                if i0 > 0:
                    d = float(v.feat.iloc[i0]["Score"]) - float(v.feat.iloc[i0 - 1]["Score"])
                    score_trend = "UP" if d > 0 else ("DOWN" if d < 0 else "FLAT")
                ext = v.feat.iloc[i0].get("ext_atr")
                extended = None if ext is None or (isinstance(ext, float) and np.isnan(ext)) else float(ext) > 2.0
        rows.append({
            "win": v.pnl_usd_a is not None and v.pnl_usd_a > 0,
            "loss": v.pnl_usd_a is not None and v.pnl_usd_a < 0,
            "open": lot.status == "OPEN",
            "fast": v.bars_held_proxy is not None and v.bars_held_proxy <= 3,
            "first_day_signal": first_day,
            "score_trend": score_trend,
            "extended": extended,
        })
    def cnt(pred):
        return sum(1 for r in rows if pred(r))
    return {
        "n": len(rows),
        "wins": cnt(lambda r: r["win"]),
        "losses": cnt(lambda r: r["loss"]),
        "open": cnt(lambda r: r["open"]),
        "exit_0_2_bars": cnt(lambda r: r["fast"]),
        "first_day_signal": cnt(lambda r: r["first_day_signal"] is True),
        "persistent_signal": cnt(lambda r: r["first_day_signal"] is False),
        "score_up": cnt(lambda r: r["score_trend"] == "UP"),
        "score_flat": cnt(lambda r: r["score_trend"] == "FLAT"),
        "score_down": cnt(lambda r: r["score_trend"] == "DOWN"),
        "extended_gt_2atr": cnt(lambda r: r["extended"] is True),
    }


def render_results_md(report: dict[str, Any]) -> str:
    m = report["metrics"]
    lines = [
        "# TAE Entry Quality / Anti-Churn A/B Results",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Verdict: **`{report['verdict']}`**",
        f"promotion_eligibility: `{report['promotion_eligibility']}`",
        f"Control A net PnL USD: `{report['baseline_control_net_pnl_usd']}` (target −733.72)",
        "",
        "## Diagnosis",
        f"`{report['diagnosis']}`",
        "",
        "## Isolated entry effect",
        "",
        "| Variant | net PnL | expectancy | maxDD | executed | delayed | cancelled | avoided | missed | fast-loss |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k in ("A", "B1", "B2", "B3"):
        x = m[k]
        lines.append(
            f"| {k} | {x['net_pnl_usd']} | {x['expectancy']} | {x['max_drawdown']} | {x['trades_executed']} | "
            f"{x['buys_delayed']} | {x['buys_cancelled']} | {x['losses_avoided_usd']} | {x['profits_missed_usd']} | "
            f"{x['loss_usd_exits_0_2_bars']} |"
        )
    lines += [
        "",
        "## Portfolio replay (limited)",
        f"```json\n{json.dumps(report['portfolio_replay'], indent=2)}\n```",
        "",
        "## Evaluations",
        f"```json\n{json.dumps(report['evaluations'], indent=2)}\n```",
        "",
        "## Temporal",
        f"Dev max month: `{report['temporal']['split_month_inclusive_dev_max']}`",
        f"- A: {report['temporal']['dev']['A']['net_pnl_usd']} / {report['temporal']['val']['A']['net_pnl_usd']}",
        f"- B1: {report['temporal']['dev']['B1']['net_pnl_usd']} / {report['temporal']['val']['B1']['net_pnl_usd']}",
        f"- B2: {report['temporal']['dev']['B2']['net_pnl_usd']} / {report['temporal']['val']['B2']['net_pnl_usd']}",
        f"- B3: {report['temporal']['dev']['B3']['net_pnl_usd']} / {report['temporal']['val']['B3']['net_pnl_usd']}",
        "",
        "## Recommendation",
        report["recommendation"],
        "",
        "NO LIVE CHANGE · NO SIZING/CAPACITY SPRINT",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    report = run_experiment(write=not args.no_write)
    print("=== TAE ENTRY QUALITY A/B ===")
    print("verdict", report["verdict"])
    print("control_A", report["baseline_control_net_pnl_usd"])
    print("diagnosis", report["diagnosis"])
    for k, v in report["metrics"].items():
        print(
            k, "pnl", v["net_pnl_usd"], "exp", v["expectancy"], "dd", v["max_drawdown"],
            "delayed", v["buys_delayed"], "cancelled", v["buys_cancelled"],
            "avoided", v["losses_avoided_usd"], "missed", v["profits_missed_usd"],
            "fast_loss", v["loss_usd_exits_0_2_bars"],
        )
    print("evals", report["evaluations"])
    print("portfolio_replay", report["portfolio_replay"])
    print("candidates", report["candidates"])
    print("protected", report["protected_hashes"]["unchanged"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
