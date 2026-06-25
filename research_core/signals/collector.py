"""Signal collection from enriched OHLCV."""

from __future__ import annotations

import numpy as np
import pandas as pd

from momentum_continuation_research_v11 import MIN_HISTORY_BARS, filter_passes

from research_core.config.base import BaseResearchConfig


def _mfe_mae(
    high: pd.Series,
    low: pd.Series,
    entry_idx: int,
    exit_idx: int,
    entry_price: float,
) -> tuple[float, float]:
    mfe, mae = -np.inf, np.inf
    for d in range(entry_idx, exit_idx + 1):
        fav = ((float(high.iloc[d]) - entry_price) / entry_price) * 100.0
        adv = ((float(low.iloc[d]) - entry_price) / entry_price) * 100.0
        mfe = max(mfe, fav)
        mae = min(mae, adv)
    return float(mfe), float(mae)


class SignalCollector:
    """Collects baseline momentum signals with context features at signal day."""

    def __init__(self, config: BaseResearchConfig) -> None:
        self._config = config

    def collect(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_ctx: pd.DataFrame,
        sector: str,
    ) -> list[dict]:
        hold = self._config.hold_days
        if len(df) < MIN_HISTORY_BARS + hold:
            return []

        close = df["Close"].astype(float)
        open_ = df["Open"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        trades: list[dict] = []
        last_exit_idx = -1

        for i in range(1, len(df) - hold):
            row = df.iloc[i]
            if not filter_passes(self._config.filter_mode, row, self._config.threshold_pct):
                continue

            entry_idx = i + 1
            exit_idx = entry_idx + hold - 1
            if exit_idx >= len(df) or entry_idx <= last_exit_idx:
                continue

            entry_price = float(open_.iloc[entry_idx])
            exit_price = float(close.iloc[exit_idx])
            if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
                continue

            ret = ((exit_price - entry_price) / entry_price) * 100.0
            mfe, mae = _mfe_mae(high, low, entry_idx, exit_idx, entry_price)
            signal_date = df.index[i]
            spy_row = spy_ctx.loc[signal_date] if signal_date in spy_ctx.index else None
            regime = spy_row.get("Market_Regime", "NEUTRAL") if spy_row is not None else "NEUTRAL"
            rsi = row["RSI14"]

            trades.append(
                {
                    "Ticker": ticker,
                    "Sector": sector,
                    "Signal_Date": signal_date,
                    "Return_60d": ret,
                    "MAE": mae,
                    "MFE": mfe,
                    "Daily_Gain_Pct": float(row["Daily_Gain_Pct"]),
                    "Prev_Day_Return_Pct": float(row["Prev_Day_Return_Pct"]) if not pd.isna(row["Prev_Day_Return_Pct"]) else np.nan,
                    "Return_5d_Pct": float(row["Return_5d_Pct"]) if not pd.isna(row["Return_5d_Pct"]) else np.nan,
                    "Return_20d_Pct": float(row["Return_20d_Pct"]) if not pd.isna(row["Return_20d_Pct"]) else np.nan,
                    "Close_Above_SMA20": bool(row["Close_Above_SMA20"]),
                    "Close_Above_SMA50": bool(row["Close_Above_SMA50"]),
                    "Close_Above_SMA100": bool(row["Close_Above_SMA100"]),
                    "Close_Above_SMA200": bool(row["Close_Above_SMA200"]),
                    "Dist_SMA20_Pct": float(row["Dist_SMA20_Pct"]) if not pd.isna(row["Dist_SMA20_Pct"]) else np.nan,
                    "Dist_SMA50_Pct": float(row["Dist_SMA50_Pct"]) if not pd.isna(row["Dist_SMA50_Pct"]) else np.nan,
                    "Dist_SMA100_Pct": float(row["Dist_SMA100_Pct"]) if not pd.isna(row["Dist_SMA100_Pct"]) else np.nan,
                    "Dist_SMA200_Pct": float(row["Dist_SMA200_Pct"]) if not pd.isna(row["Dist_SMA200_Pct"]) else np.nan,
                    "RSI14": float(rsi) if not pd.isna(rsi) else np.nan,
                    "ATR14": float(row["ATR14"]) if not pd.isna(row["ATR14"]) else np.nan,
                    "ATR_Pct": float(row["ATR_Pct"]) if not pd.isna(row["ATR_Pct"]) else np.nan,
                    "Volume_Ratio": float(row["Volume_Ratio"]) if not pd.isna(row["Volume_Ratio"]) else np.nan,
                    "Dollar_Volume_Ratio": float(row["Dollar_Volume_Ratio"]) if not pd.isna(row["Dollar_Volume_Ratio"]) else np.nan,
                    "Gap_Pct": float(row["Gap_Pct"]) if not pd.isna(row["Gap_Pct"]) else np.nan,
                    "Intraday_Return_Pct": float(row["Intraday_Return_Pct"]) if not pd.isna(row["Intraday_Return_Pct"]) else np.nan,
                    "Range_Pct": float(row["Range_Pct"]) if not pd.isna(row["Range_Pct"]) else np.nan,
                    "Close_Location": float(row["Close_Location"]) if not pd.isna(row["Close_Location"]) else np.nan,
                    "Body_Pct": float(row["Body_Pct"]) if not pd.isna(row["Body_Pct"]) else np.nan,
                    "Upper_Wick_Pct": float(row["Upper_Wick_Pct"]) if not pd.isna(row["Upper_Wick_Pct"]) else np.nan,
                    "Lower_Wick_Pct": float(row["Lower_Wick_Pct"]) if not pd.isna(row["Lower_Wick_Pct"]) else np.nan,
                    "SPY_Return_20d_Pct": float(spy_row["SPY_Return_20d_Pct"]) if spy_row is not None and not pd.isna(spy_row.get("SPY_Return_20d_Pct")) else np.nan,
                    "SPY_Return_60d_Pct": float(spy_row["SPY_Return_60d_Pct"]) if spy_row is not None and not pd.isna(spy_row.get("SPY_Return_60d_Pct")) else np.nan,
                    "SPY_Above_SMA200": bool(spy_row["SPY_Above_SMA200"]) if spy_row is not None else False,
                    "SPY_Dist_SMA200_Pct": float(spy_row["SPY_Dist_SMA200_Pct"]) if spy_row is not None and not pd.isna(spy_row.get("SPY_Dist_SMA200_Pct")) else np.nan,
                    "Market_Regime": regime,
                }
            )
            last_exit_idx = exit_idx

        return trades
