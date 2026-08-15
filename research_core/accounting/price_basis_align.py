#!/usr/bin/env python3
"""
Price-basis / split alignment for exit replay vs execution fills.

Does NOT mutate portfolio.csv fill prices. Aligns ReplayPosition into bar units
when a split-like ratio is detected so notional is preserved.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

SPLIT_CANDIDATES = (2.0, 3.0, 4.0, 5.0, 10.0)


def _bar_near_entry(bars: pd.DataFrame, entry_ts: Any) -> pd.Series | None:
    if bars is None or bars.empty or entry_ts is None:
        return None
    start = pd.Timestamp(entry_ts).tz_localize(None).normalize()
    idx = bars.index
    exact = idx[idx == start]
    if len(exact):
        return bars.loc[exact[0]]
    later = idx[idx >= start]
    if len(later):
        return bars.loc[later[0]]
    earlier = idx[idx < start]
    if len(earlier):
        return bars.loc[earlier[-1]]
    return None


def detect_split_ratio(entry_price: float, bars: pd.DataFrame, entry_ts: Any) -> dict[str, Any]:
    row = _bar_near_entry(bars, entry_ts)
    if row is None:
        return {
            "ratio": 1.0,
            "method": "NO_BAR",
            "status": "DATA_INVALID",
            "reason": "ENTRY_BAR_NOT_FOUND",
            "bar_close": None,
        }
    o = float(row["Open"])
    h = float(row["High"])
    l = float(row["Low"])
    c = float(row["Close"])
    px = float(entry_price)
    lo, hi = min(o, h, l, c) * 0.98, max(o, h, l, c) * 1.02
    if lo <= px <= hi:
        return {
            "ratio": 1.0,
            "method": "IN_BAR_RANGE",
            "status": "PRICE_BASIS_CONSISTENT",
            "reason": None,
            "bar_close": c,
        }
    if c <= 0 or px <= 0:
        return {
            "ratio": 1.0,
            "method": "INVALID_PRICE",
            "status": "DATA_INVALID",
            "reason": "NON_POSITIVE_PRICE",
            "bar_close": c,
        }
    # Execution in pre-split units vs post-split bars → ratio ≈ entry/close
    r = px / c
    for cand in SPLIT_CANDIDATES:
        if abs(r - cand) / cand <= 0.08:
            return {
                "ratio": float(cand),
                "method": f"SPLIT_RATIO_{cand:g}",
                "status": "SPLIT_ALIGNMENT_APPLIED",
                "reason": f"entry/close≈{r:.3f}",
                "bar_close": c,
            }
    # Reverse: bars still pre-split (rare)
    r_inv = c / px
    for cand in SPLIT_CANDIDATES:
        if abs(r_inv - cand) / cand <= 0.08:
            return {
                "ratio": 1.0 / float(cand),
                "method": f"REVERSE_SPLIT_RATIO_{cand:g}",
                "status": "SPLIT_ALIGNMENT_APPLIED",
                "reason": f"close/entry≈{r_inv:.3f}",
                "bar_close": c,
            }
    return {
        "ratio": 1.0,
        "method": "OUTSIDE_RANGE_NO_SPLIT",
        "status": "PRICE_ADJUSTMENT_WARNING",
        "reason": f"entry={px} bar=[{l},{h}] close={c}",
        "bar_close": c,
    }


def align_position_to_bars(pos: Any, bars: pd.DataFrame) -> tuple[Any, dict[str, Any]]:
    """
    Return a ReplayPosition whose entry/shares/(actual exit) are in bar units.
    Notional entry_price*shares is preserved.
    """
    info = detect_split_ratio(float(pos.entry_price), bars, pos.entry_timestamp)
    ratio = float(info["ratio"])
    meta = {
        **info,
        "original_entry_price": float(pos.entry_price),
        "original_shares": float(pos.shares),
        "original_actual_exit_price": getattr(pos, "actual_exit_price", None),
    }
    if abs(ratio - 1.0) < 1e-12:
        return pos, meta

    new_entry = float(pos.entry_price) / ratio
    new_shares = float(pos.shares) * ratio
    # Preserve notional
    if abs(new_entry * new_shares - float(pos.entry_price) * float(pos.shares)) > 1e-4:
        meta["status"] = "DATA_INVALID"
        meta["reason"] = "NOTIONAL_DRIFT_AFTER_SPLIT_ALIGN"
        return pos, meta

    new_exit = getattr(pos, "actual_exit_price", None)
    if new_exit is not None:
        new_exit = float(new_exit) / ratio

    aligned = replace(
        pos,
        entry_price=new_entry,
        shares=new_shares,
        actual_exit_price=new_exit,
        data_quality=str(info["status"]),
    )
    meta["aligned_entry_price"] = new_entry
    meta["aligned_shares"] = new_shares
    meta["aligned_actual_exit_price"] = new_exit
    return aligned, meta
