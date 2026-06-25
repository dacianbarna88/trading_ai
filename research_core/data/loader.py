"""Market data download and feature enrichment."""

from __future__ import annotations

import numpy as np
import pandas as pd

from context_intelligence_research_v18 import compute_atr, enrich_spy
from momentum_continuation_research_v11 import compute_rsi, download_history

from research_core.config.base import BaseResearchConfig


def enrich_ticker(df: pd.DataFrame, config: BaseResearchConfig) -> pd.DataFrame:
    out = df.copy()
    o = out["Open"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)
    c = out["Close"].astype(float)
    v = out["Volume"].astype(float)
    prev_c = c.shift(1)
    period = config.atr_period

    out["Daily_Gain_Pct"] = (c / prev_c - 1.0) * 100.0
    out["Prev_Day_Return_Pct"] = (prev_c / prev_c.shift(1) - 1.0) * 100.0
    out["Return_5d_Pct"] = (c / c.shift(5) - 1.0) * 100.0
    out["Return_20d_Pct"] = (c / c.shift(20) - 1.0) * 100.0
    out["SMA20"] = c.rolling(20, min_periods=20).mean()
    out["SMA50"] = c.rolling(50, min_periods=50).mean()
    out["SMA100"] = c.rolling(100, min_periods=100).mean()
    out["SMA200"] = c.rolling(200, min_periods=200).mean()
    out["Close_Above_SMA20"] = c > out["SMA20"]
    out["Close_Above_SMA50"] = c > out["SMA50"]
    out["Close_Above_SMA100"] = c > out["SMA100"]
    out["Close_Above_SMA200"] = c > out["SMA200"]
    out["Dist_SMA20_Pct"] = (c / out["SMA20"] - 1.0) * 100.0
    out["Dist_SMA50_Pct"] = (c / out["SMA50"] - 1.0) * 100.0
    out["Dist_SMA100_Pct"] = (c / out["SMA100"] - 1.0) * 100.0
    out["Dist_SMA200_Pct"] = (c / out["SMA200"] - 1.0) * 100.0
    out["RSI14"] = compute_rsi(c, period)
    out["ATR14"] = compute_atr(h, l, c, period)
    out["ATR_Pct"] = (out["ATR14"] / c.replace(0, np.nan)) * 100.0
    out["Volume"] = v
    out["Avg20Volume"] = v.rolling(20, min_periods=20).mean()
    out["Volume_Ratio"] = v / out["Avg20Volume"]
    out["Dollar_Volume"] = c * v
    out["Avg20DollarVolume"] = out["Dollar_Volume"].rolling(20, min_periods=20).mean()
    out["Dollar_Volume_Ratio"] = out["Dollar_Volume"] / out["Avg20DollarVolume"]
    span = h - l
    out["Gap_Pct"] = ((o - prev_c) / prev_c.replace(0, np.nan)) * 100.0
    out["Intraday_Return_Pct"] = ((c - o) / o.replace(0, np.nan)) * 100.0
    out["Range_Pct"] = ((h - l) / prev_c.replace(0, np.nan)) * 100.0
    out["Close_Location"] = np.where(span > 0, (c - l) / span, np.nan)
    body_top = np.maximum(o, c)
    body_bot = np.minimum(o, c)
    out["Body_Pct"] = np.where(span > 0, (body_top - body_bot) / span * 100.0, np.nan)
    out["Upper_Wick_Pct"] = np.where(span > 0, (h - body_top) / span * 100.0, np.nan)
    out["Lower_Wick_Pct"] = np.where(span > 0, (body_bot - l) / span * 100.0, np.nan)
    return out


def enrich_spy_market(df: pd.DataFrame) -> pd.DataFrame:
    out = enrich_spy(df)
    c = out["Close"].astype(float)
    out["SPY_Return_20d_Pct"] = (c / c.shift(20) - 1.0) * 100.0
    out["SPY_Return_60d_Pct"] = out["SPY_60d_Return_Pct"]
    out["SPY_Above_SMA200"] = c > out["SMA200"]
    out["SPY_Dist_SMA200_Pct"] = out["SPY_Close_vs_SMA200_Pct"]
    return out


def download_ticker(ticker: str) -> pd.DataFrame:
    return download_history(ticker)
