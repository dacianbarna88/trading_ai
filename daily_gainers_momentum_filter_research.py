"""
Daily Gainers Momentum Filter Research — ANALYSIS ONLY / NO_EXECUTION

Tests whether trend/volume/RSI filters improve forward returns after strong daily gains.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yfinance as yf

from daily_gainers_strategy_research import (
    ENTRY_MODE,
    HISTORY_PERIOD,
    MIN_TRADES_STRATEGY,
    build_ticker_universe,
    compute_daily_gain_pct,
)

warnings.filterwarnings("ignore", category=FutureWarning)

RESULTS_CSV = "daily_gainers_momentum_filter_results.csv"
SUMMARY_TXT = "daily_gainers_momentum_filter_summary.txt"

THRESHOLDS_PCT = [5.0, 8.0, 10.0]
HOLD_DAYS = [7, 14, 30]
MIN_TRADES_OVERALL = 30
RSI_PERIOD = 14

FILTERS: dict[str, Callable[[pd.Series, int], bool]] = {}


def _register_filters() -> None:
    global FILTERS
    FILTERS = {
        "NO_FILTER": lambda row, _i: True,
        "ABOVE_SMA50": lambda row, _i: row["Close"] > row["SMA50"],
        "ABOVE_SMA200": lambda row, _i: row["Close"] > row["SMA200"],
        "ABOVE_SMA50_AND_SMA200": lambda row, _i: (
            row["Close"] > row["SMA50"] and row["Close"] > row["SMA200"]
        ),
        "VOLUME_ABOVE_20D_AVG": lambda row, _i: row["Volume"] > row["Vol_SMA20"],
        "ABOVE_SMA200_AND_VOLUME": lambda row, _i: (
            row["Close"] > row["SMA200"] and row["Volume"] > row["Vol_SMA20"]
        ),
        "RSI_50_TO_80": lambda row, _i: 50.0 <= row["RSI"] <= 80.0,
        "ABOVE_SMA200_AND_VOLUME_AND_RSI": lambda row, _i: (
            row["Close"] > row["SMA200"]
            and row["Volume"] > row["Vol_SMA20"]
            and 50.0 <= row["RSI"] <= 80.0
        ),
    }


def normalize_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    cols = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in cols):
        return pd.DataFrame()

    out = df[cols].copy()
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out["Ticker"] = ticker
    return out


def download_daily_history_with_volume(ticker: str) -> pd.DataFrame:
    try:
        raw = yf.download(
            ticker,
            period=HISTORY_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        return normalize_ohlcv(raw, ticker)
    except Exception:
        return pd.DataFrame()


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def enrich_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"].astype(float)
    out["Daily_Gain_Pct"] = compute_daily_gain_pct(close)
    out["SMA50"] = close.rolling(50, min_periods=50).mean()
    out["SMA200"] = close.rolling(200, min_periods=200).mean()
    out["Vol_SMA20"] = out["Volume"].astype(float).rolling(20, min_periods=20).mean()
    out["RSI"] = compute_rsi(close)
    return out


def trade_drawdown_pct(
    close: pd.Series,
    entry_idx: int,
    exit_idx: int,
    entry_price: float,
) -> float:
    """Max peak-to-trough drawdown during hold (%), from entry open."""
    window = close.iloc[entry_idx:exit_idx + 1].astype(float)
    if window.empty or entry_price <= 0:
        return 0.0
    peak = entry_price
    max_dd = 0.0
    for price in window:
        if price > peak:
            peak = price
        dd = ((price - peak) / peak) * 100.0
        if dd < max_dd:
            max_dd = dd
    return float(max_dd)


def passes_filter(row: pd.Series, filter_name: str) -> bool:
    if filter_name == "NO_FILTER":
        return True

    fn = FILTERS.get(filter_name)
    if fn is None:
        return False

    required = {
        "ABOVE_SMA50": ["Close", "SMA50"],
        "ABOVE_SMA200": ["Close", "SMA200"],
        "ABOVE_SMA50_AND_SMA200": ["Close", "SMA50", "SMA200"],
        "VOLUME_ABOVE_20D_AVG": ["Volume", "Vol_SMA20"],
        "ABOVE_SMA200_AND_VOLUME": ["Close", "SMA200", "Volume", "Vol_SMA20"],
        "RSI_50_TO_80": ["RSI"],
        "ABOVE_SMA200_AND_VOLUME_AND_RSI": [
            "Close", "SMA200", "Volume", "Vol_SMA20", "RSI",
        ],
    }
    for col in required.get(filter_name, []):
        if pd.isna(row.get(col)):
            return False

    return bool(fn(row, 0))


def simulate_filtered_trades(
    df: pd.DataFrame,
    threshold_pct: float,
    hold_days: int,
    region: str,
    filter_name: str,
) -> list[dict]:
    if len(df) < max(hold_days + 2, 200):
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
    ticker = df["Ticker"].iloc[0]
    trades: list[dict] = []
    last_exit_idx = -1

    for i in range(1, len(df) - hold_days):
        gain = df["Daily_Gain_Pct"].iloc[i]
        if pd.isna(gain) or gain < threshold_pct:
            continue

        row = df.iloc[i]
        if not passes_filter(row, filter_name):
            continue

        entry_idx = i + 1
        exit_idx = entry_idx + hold_days - 1
        if exit_idx >= len(df):
            break
        if entry_idx <= last_exit_idx:
            continue

        entry_price = float(open_.iloc[entry_idx])
        exit_price = float(close.iloc[exit_idx])
        if entry_price <= 0 or pd.isna(entry_price) or pd.isna(exit_price):
            continue

        ret_pct = ((exit_price - entry_price) / entry_price) * 100.0
        dd_pct = trade_drawdown_pct(close, entry_idx, exit_idx, entry_price)

        trades.append(
            {
                "Region": region,
                "Ticker": ticker,
                "Filter": filter_name,
                "Threshold_Pct": threshold_pct,
                "Hold_Days": hold_days,
                "Entry_Mode": ENTRY_MODE,
                "Return_Pct": round(ret_pct, 4),
                "Max_Drawdown_Pct": round(dd_pct, 4),
            }
        )
        last_exit_idx = exit_idx

    return trades


def aggregate_trades(trades: list[dict]) -> dict | None:
    if not trades:
        return None

    returns = np.array([t["Return_Pct"] for t in trades], dtype=float)
    drawdowns = np.array([t["Max_Drawdown_Pct"] for t in trades], dtype=float)
    wins = returns > 0

    return {
        "Filter": trades[0]["Filter"],
        "Threshold_Pct": trades[0]["Threshold_Pct"],
        "Hold_Days": trades[0]["Hold_Days"],
        "Region": trades[0]["Region"],
        "Entry_Mode": trades[0]["Entry_Mode"],
        "Num_Trades": len(trades),
        "Win_Rate_Pct": round(float(wins.mean() * 100.0), 2),
        "Avg_Return_Pct": round(float(returns.mean()), 4),
        "Median_Return_Pct": round(float(np.median(returns)), 4),
        "Max_Loss_Pct": round(float(returns.min()), 4),
        "Max_Gain_Pct": round(float(returns.max()), 4),
        "Total_Return_Pct": round(float(returns.sum()), 4),
        "Avg_Drawdown_Pct": round(float(drawdowns.mean()), 4),
    }


def add_best_region(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df

    best_map: dict[tuple, str] = {}
    for key, group in summary_df.groupby(["Filter", "Threshold_Pct", "Hold_Days"]):
        regional = group[group["Region"].isin(["US", "EU", "UK"])]
        if regional.empty:
            best_map[key] = "ALL"
        else:
            best_map[key] = regional.sort_values(
                "Avg_Return_Pct", ascending=False
            ).iloc[0]["Region"]

    out = summary_df.copy()
    out["Best_Region"] = out.apply(
        lambda r: best_map[(r["Filter"], r["Threshold_Pct"], r["Hold_Days"])],
        axis=1,
    )
    return out


def filter_improves_vs_baseline(filter_row: pd.Series, baseline_row: pd.Series) -> bool:
    if filter_row["Filter"] == "NO_FILTER":
        return False
    if filter_row["Num_Trades"] < MIN_TRADES_STRATEGY:
        return False
    if baseline_row["Num_Trades"] < MIN_TRADES_STRATEGY:
        return False

    return (
        filter_row["Avg_Return_Pct"] > baseline_row["Avg_Return_Pct"]
        and filter_row["Win_Rate_Pct"] > baseline_row["Win_Rate_Pct"]
        and filter_row["Max_Loss_Pct"] >= baseline_row["Max_Loss_Pct"]
    )


def determine_conclusion(summary_df: pd.DataFrame, total_trades: int) -> tuple[str, pd.Series | None]:
    if total_trades < MIN_TRADES_OVERALL or summary_df.empty:
        return "INSUFFICIENT_DATA", None

    improved_rows = []
    for region in ("US", "EU", "UK", "ALL"):
        for threshold in THRESHOLDS_PCT:
            for hold in HOLD_DAYS:
                subset = summary_df[
                    (summary_df["Region"] == region)
                    & (summary_df["Threshold_Pct"] == threshold)
                    & (summary_df["Hold_Days"] == hold)
                ]
                if subset.empty:
                    continue
                baseline = subset[subset["Filter"] == "NO_FILTER"]
                if baseline.empty:
                    continue
                base_row = baseline.iloc[0]
                for _, row in subset.iterrows():
                    if filter_improves_vs_baseline(row, base_row):
                        improved_rows.append(row)

    if not improved_rows:
        viable = summary_df[summary_df["Num_Trades"] >= MIN_TRADES_STRATEGY]
        if viable.empty:
            return "INSUFFICIENT_DATA", None
        return "FILTERS_DO_NOT_IMPROVE", None

    best = pd.DataFrame(improved_rows).sort_values(
        "Avg_Return_Pct", ascending=False
    ).iloc[0]
    return "BEST_FILTERED_STRATEGY", best


def format_row(row: pd.Series) -> str:
    return (
        f"Filter={row['Filter']} | Region={row['Region']} | "
        f"Threshold>={row['Threshold_Pct']}% | Hold={row['Hold_Days']}d | "
        f"Trades={row['Num_Trades']} | WinRate={row['Win_Rate_Pct']}% | "
        f"AvgReturn={row['Avg_Return_Pct']}% | MaxLoss={row['Max_Loss_Pct']}% | "
        f"AvgDD={row.get('Avg_Drawdown_Pct', 'N/A')}%"
    )


def main() -> None:
    _register_filters()

    print("===== DAILY GAINERS MOMENTUM FILTER RESEARCH (ANALYSIS ONLY) =====")
    print("Mode: NO_EXECUTION | NO_BROKER | NO_PORTFOLIO_CHANGES")
    print()

    ticker_regions = build_ticker_universe()
    if not ticker_regions:
        Path(SUMMARY_TXT).write_text(
            "CONCLUSION: INSUFFICIENT_DATA\nNo tickers loaded.\n", encoding="utf-8"
        )
        print("No tickers found.")
        return

    all_trades: list[dict] = []
    downloaded = 0
    failed: list[str] = []

    for ticker, region in sorted(ticker_regions.items()):
        raw = download_daily_history_with_volume(ticker)
        if raw.empty or len(raw) < max(HOLD_DAYS) + 200:
            failed.append(ticker)
            continue
        df = enrich_features(raw)
        downloaded += 1

        for filter_name in FILTERS:
            for threshold in THRESHOLDS_PCT:
                for hold in HOLD_DAYS:
                    all_trades.extend(
                        simulate_filtered_trades(
                            df, threshold, hold, region, filter_name
                        )
                    )

    summary_rows: list[dict] = []
    trade_df = pd.DataFrame(all_trades)

    if not trade_df.empty:
        for region in ("US", "EU", "UK", "ALL"):
            for filter_name in FILTERS:
                for threshold in THRESHOLDS_PCT:
                    for hold in HOLD_DAYS:
                        subset = trade_df[
                            (trade_df["Filter"] == filter_name)
                            & (trade_df["Threshold_Pct"] == threshold)
                            & (trade_df["Hold_Days"] == hold)
                        ]
                        if region != "ALL":
                            subset = subset[subset["Region"] == region]
                        agg = aggregate_trades(subset.to_dict("records"))
                        if agg:
                            if region == "ALL":
                                agg["Region"] = "ALL"
                            summary_rows.append(agg)

    summary_df = pd.DataFrame(summary_rows)
    if summary_df.empty:
        summary_df = pd.DataFrame(
            columns=[
                "Filter", "Threshold_Pct", "Hold_Days", "Region", "Entry_Mode",
                "Num_Trades", "Win_Rate_Pct", "Avg_Return_Pct", "Median_Return_Pct",
                "Max_Loss_Pct", "Max_Gain_Pct", "Total_Return_Pct", "Avg_Drawdown_Pct",
                "Best_Region",
            ]
        )
    else:
        summary_df = add_best_region(summary_df)

    summary_df.to_csv(RESULTS_CSV, index=False)

    conclusion, best_row = determine_conclusion(summary_df, len(all_trades))

    lines = [
        "===== DAILY GAINERS MOMENTUM FILTER RESEARCH =====",
        "",
        "Mode: ANALYSIS_ONLY",
        "NO_EXECUTION",
        "NO_BROKER",
        "NO_PORTFOLIO_CHANGES",
        "",
        f"Tickers loaded: {len(ticker_regions)}",
        f"Tickers with data: {downloaded}",
        f"Tickers failed/short history: {len(failed)}",
        f"Total simulated trades: {len(all_trades)}",
        f"Entry timing: {ENTRY_MODE}",
        f"History period: {HISTORY_PERIOD}",
        "",
        "Thresholds: " + ", ".join(f"{t}%" for t in THRESHOLDS_PCT),
        "Hold days: " + ", ".join(str(h) for h in HOLD_DAYS),
        "Filters: " + ", ".join(FILTERS.keys()),
        "",
        "Filter improvement rules vs NO_FILTER (same region/threshold/hold):",
        f"  - Num_Trades >= {MIN_TRADES_STRATEGY}",
        "  - Avg return higher",
        "  - Win rate higher",
        "  - Max loss not worse (less negative)",
        "",
    ]

    if failed:
        lines.append("Failed/short tickers: " + ", ".join(failed[:25]))
        if len(failed) > 25:
            lines.append(f"  ... and {len(failed) - 25} more")
        lines.append("")

    if not summary_df.empty:
        viable = summary_df[summary_df["Num_Trades"] >= MIN_TRADES_STRATEGY]
        lines.append("--- Top combinations by avg return (min 10 trades) ---")
        if not viable.empty:
            for _, row in viable.sort_values("Avg_Return_Pct", ascending=False).head(10).iterrows():
                lines.append(format_row(row))
        else:
            lines.append("No combination reached minimum trade count.")
        lines.append("")

        lines.append("--- Best region per filter (threshold 8%, hold 14d) ---")
        sample = summary_df[
            (summary_df["Threshold_Pct"] == 8.0)
            & (summary_df["Hold_Days"] == 14)
            & (summary_df["Region"].isin(["US", "EU", "UK"]))
        ]
        for filt in FILTERS:
            sub = sample[sample["Filter"] == filt]
            if sub.empty:
                lines.append(f"{filt}: no data")
                continue
            best = sub.sort_values("Avg_Return_Pct", ascending=False).iloc[0]
            lines.append(f"{filt}: best={best['Region']} avg={best['Avg_Return_Pct']}%")
        lines.append("")

    lines.append(f"CONCLUSION: {conclusion}")
    if best_row is not None:
        lines.append(f"BEST_FILTERED: {format_row(best_row)}")
    elif conclusion == "FILTERS_DO_NOT_IMPROVE":
        lines.append("No filter beat NO_FILTER on all improvement criteria.")
    else:
        lines.append(
            f"Need at least {MIN_TRADES_OVERALL} total trades and "
            f"{MIN_TRADES_STRATEGY} per strategy."
        )

    text = "\n".join(lines) + "\n"
    Path(SUMMARY_TXT).write_text(text, encoding="utf-8")
    print(text)
    print(f"Saved: {RESULTS_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
