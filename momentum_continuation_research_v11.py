"""
Momentum Continuation Research V1.1 — Robustness Audit

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Stress-tests momentum continuation edge across thresholds, holds, and filters.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from daily_gainers_strategy_research import (
    build_ticker_universe,
    compute_daily_gain_pct,
)

warnings.filterwarnings("ignore", category=FutureWarning)

HISTORY_PERIOD = "10y"
MIN_HISTORY_BARS = 260
RSI_PERIOD = 14
RSI_LOW = 50.0
RSI_HIGH = 80.0
ENTRY_MODE = "next_open"
MIN_ROBUST_TRADES = 30

THRESHOLDS = [3.0, 5.0, 8.0, 10.0]
HOLD_DAYS = [3, 7, 14, 30, 60]
FILTER_MODES = [
    "NO_FILTER",
    "TREND_ONLY",
    "TREND_VOLUME",
    "FULL_FILTER",
    "STRONG_TREND",
]

ALL_TRADES_CSV = "momentum_v11_all_trades.csv"
MATRIX_CSV = "momentum_v11_matrix.csv"
SUMMARY_TXT = "momentum_v11_summary.txt"


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


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


def download_history(ticker: str) -> pd.DataFrame:
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


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"].astype(float)
    out["Daily_Gain_Pct"] = compute_daily_gain_pct(close)
    out["SMA50"] = close.rolling(50, min_periods=50).mean()
    out["SMA200"] = close.rolling(200, min_periods=200).mean()
    out["Avg20Volume"] = out["Volume"].astype(float).rolling(20, min_periods=20).mean()
    out["RSI"] = compute_rsi(close)
    return out


def filter_passes(mode: str, row: pd.Series, threshold: float) -> bool:
    gain = row.get("Daily_Gain_Pct")
    if pd.isna(gain) or gain < threshold:
        return False

    close = row.get("Close")
    sma50 = row.get("SMA50")
    sma200 = row.get("SMA200")
    vol = row.get("Volume")
    avg_vol = row.get("Avg20Volume")
    rsi = row.get("RSI")

    if mode == "NO_FILTER":
        return True
    if mode == "TREND_ONLY":
        return not pd.isna(close) and not pd.isna(sma200) and close > sma200
    if mode == "TREND_VOLUME":
        return (
            not pd.isna(close) and not pd.isna(sma200) and close > sma200
            and not pd.isna(vol) and not pd.isna(avg_vol) and vol > avg_vol
        )
    if mode == "FULL_FILTER":
        return (
            not pd.isna(close) and not pd.isna(sma200) and close > sma200
            and not pd.isna(vol) and not pd.isna(avg_vol) and vol > avg_vol
            and not pd.isna(rsi) and RSI_LOW <= rsi <= RSI_HIGH
        )
    if mode == "STRONG_TREND":
        return (
            not pd.isna(close) and not pd.isna(sma50) and not pd.isna(sma200)
            and close > sma50 and close > sma200
            and not pd.isna(vol) and not pd.isna(avg_vol) and vol > avg_vol
            and not pd.isna(rsi) and RSI_LOW <= rsi <= RSI_HIGH
        )
    return False


def trade_max_drawdown(close: pd.Series, entry_idx: int, exit_idx: int, entry_price: float) -> float:
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


def simulate_ticker(
    df: pd.DataFrame,
    region: str,
    threshold: float,
    hold_days: int,
    filter_mode: str,
) -> list[dict]:
    if len(df) < MIN_HISTORY_BARS + hold_days:
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
    ticker = df["Ticker"].iloc[0]
    trades: list[dict] = []
    last_exit_idx = -1

    for i in range(1, len(df) - hold_days):
        row = df.iloc[i]
        if not filter_passes(filter_mode, row, threshold):
            continue

        entry_idx = i + 1
        exit_idx = entry_idx + hold_days - 1
        if exit_idx >= len(df):
            break
        if entry_idx <= last_exit_idx:
            continue

        entry_price = float(open_.iloc[entry_idx])
        exit_price = float(close.iloc[exit_idx])
        if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
            continue

        ret = ((exit_price - entry_price) / entry_price) * 100.0
        mdd = trade_max_drawdown(close, entry_idx, exit_idx, entry_price)

        trades.append(
            {
                "Region": region,
                "Ticker": ticker,
                "Threshold": threshold,
                "Hold_Days": hold_days,
                "Filter_Mode": filter_mode,
                "Entry_Mode": ENTRY_MODE,
                "Signal_Date": df.index[i].strftime("%Y-%m-%d"),
                "Entry_Date": df.index[entry_idx].strftime("%Y-%m-%d"),
                "Exit_Date": df.index[exit_idx].strftime("%Y-%m-%d"),
                "Signal_Gain_Pct": round(float(row["Daily_Gain_Pct"]), 4),
                "Return_Pct": round(ret, 4),
                "Max_Drawdown_Pct": round(mdd, 4),
            }
        )
        last_exit_idx = exit_idx

    return trades


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def warning_flags(row: dict) -> str:
    flags = []
    if row["Trades"] < MIN_ROBUST_TRADES:
        flags.append("TOO_FEW_TRADES")
    if row["Avg_Return"] < 5.0:
        flags.append("WEAK_EDGE")
    if row["Avg_Return"] - row["Median_Return"] > 3.0:
        flags.append("UNSTABLE")
    if row["Worst_Trade"] < -15.0:
        flags.append("HIGH_RISK")
    return "|".join(flags) if flags else "OK"


def compute_score(row: dict) -> float:
    trades = row["Trades"]
    avg_ret = row["Avg_Return"]
    win_rate = row["Win_Rate"]
    worst = row["Worst_Trade"]
    median = row["Median_Return"]
    instability = abs(avg_ret - median)

    sample_bonus = min(trades, 120) / 12.0
    worst_penalty = abs(worst) * 0.25 if worst < 0 else 0.0
    instability_penalty = instability * 0.6

    score = (
        avg_ret * 2.0
        + win_rate * 0.12
        + sample_bonus
        - worst_penalty
        - instability_penalty
    )
    if trades < MIN_ROBUST_TRADES:
        score *= 0.55
    return round(score, 4)


def aggregate_trades(trades: list[dict], region: str) -> dict | None:
    if not trades:
        return None

    returns = np.array([t["Return_Pct"] for t in trades], dtype=float)
    drawdowns = np.array([t["Max_Drawdown_Pct"] for t in trades], dtype=float)
    winners = returns[returns > 0]
    losers = returns[returns < 0]

    row = {
        "Region": region,
        "Threshold": trades[0]["Threshold"],
        "Hold_Days": trades[0]["Hold_Days"],
        "Filter_Mode": trades[0]["Filter_Mode"],
        "Trades": len(trades),
        "Win_Rate": round(float((returns > 0).mean() * 100.0), 2),
        "Avg_Return": round(float(returns.mean()), 4),
        "Median_Return": round(float(np.median(returns)), 4),
        "Best_Trade": round(float(returns.max()), 4),
        "Worst_Trade": round(float(returns.min()), 4),
        "Profit_Factor": round(profit_factor(returns), 4),
        "Avg_Winner": round(float(winners.mean()), 4) if len(winners) else 0.0,
        "Avg_Loser": round(float(losers.mean()), 4) if len(losers) else 0.0,
        "Max_Drawdown_Approx": round(float(drawdowns.mean()), 4),
    }
    row["Score"] = compute_score(row)
    row["Warnings"] = warning_flags(row)
    return row


def determine_conclusion(matrix_df: pd.DataFrame) -> str:
    if matrix_df.empty:
        return "NO_EDGE"

    robust = matrix_df[matrix_df["Trades"] >= MIN_ROBUST_TRADES].copy()
    if robust.empty:
        best_any = matrix_df.sort_values("Score", ascending=False).iloc[0]
        if best_any["Avg_Return"] >= 3.0 and best_any["Win_Rate"] >= 50.0:
            return "PROMISING_BUT_SMALL_SAMPLE"
        return "NO_EDGE"

    best = robust.sort_values("Score", ascending=False).iloc[0]
    if (
        best["Avg_Return"] >= 5.0
        and best["Win_Rate"] >= 52.0
        and best["Profit_Factor"] >= 1.15
        and "HIGH_RISK" not in best["Warnings"]
    ):
        return "ROBUST_EDGE"
    if best["Avg_Return"] >= 3.0:
        return "WEAK_EDGE"
    return "NO_EDGE"


def format_config(row: pd.Series) -> str:
    return (
        f"{row['Filter_Mode']} | {row['Region']} | thr>={row['Threshold']}% | "
        f"hold={row['Hold_Days']}d | trades={row['Trades']} | "
        f"win={row['Win_Rate']}% | avg={row['Avg_Return']}% | "
        f"PF={row['Profit_Factor']} | score={row['Score']} | {row['Warnings']}"
    )


def main() -> None:
    print("===== MOMENTUM CONTINUATION RESEARCH V1.1 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION")
    print()

    ticker_regions = build_ticker_universe()
    skipped: list[tuple[str, str]] = []
    all_trades: list[dict] = []
    checked = 0

    for ticker, region in sorted(ticker_regions.items()):
        raw = download_history(ticker)
        if raw.empty:
            skipped.append((ticker, "DOWNLOAD_FAILED"))
            continue
        if len(raw) < MIN_HISTORY_BARS:
            skipped.append((ticker, f"INSUFFICIENT_HISTORY_{len(raw)}_bars"))
            continue

        df = enrich(raw)
        checked += 1

        for threshold in THRESHOLDS:
            for hold in HOLD_DAYS:
                for mode in FILTER_MODES:
                    all_trades.extend(
                        simulate_ticker(df, region, threshold, hold, mode)
                    )

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        trades_df.to_csv(ALL_TRADES_CSV, index=False)
    else:
        trades_df = pd.DataFrame()
        trades_df.to_csv(ALL_TRADES_CSV, index=False)

    matrix_rows: list[dict] = []
    if not trades_df.empty:
        for region in ("US", "EU", "UK", "ALL"):
            for threshold in THRESHOLDS:
                for hold in HOLD_DAYS:
                    for mode in FILTER_MODES:
                        subset = trades_df[
                            (trades_df["Threshold"] == threshold)
                            & (trades_df["Hold_Days"] == hold)
                            & (trades_df["Filter_Mode"] == mode)
                        ]
                        if region != "ALL":
                            subset = subset[subset["Region"] == region]
                        agg = aggregate_trades(subset.to_dict("records"), region)
                        if agg:
                            matrix_rows.append(agg)

    matrix_df = pd.DataFrame(matrix_rows)
    matrix_df.to_csv(MATRIX_CSV, index=False)

    conclusion = determine_conclusion(matrix_df)

    lines = [
        "===== MOMENTUM CONTINUATION RESEARCH V1.1 — ROBUSTNESS AUDIT =====",
        "",
        "RESEARCH_ONLY",
        "PAPER_ONLY",
        "NO_BROKER",
        "NO_EXECUTION",
        "",
        f"History period: {HISTORY_PERIOD}",
        f"Min history bars: {MIN_HISTORY_BARS}",
        f"Entry: {ENTRY_MODE} | Exit: close after hold",
        "",
        f"Total tickers loaded: {len(ticker_regions)}",
        f"Tickers checked: {checked}",
        f"Tickers skipped: {len(skipped)}",
        f"Total simulated trades: {len(all_trades)}",
        "",
        f"Thresholds: {THRESHOLDS}",
        f"Hold days: {HOLD_DAYS}",
        f"Filter modes: {FILTER_MODES}",
        "",
    ]

    if skipped:
        lines.append("--- Skipped tickers ---")
        for ticker, reason in skipped:
            lines.append(f"  {ticker}: {reason}")
        lines.append("")

    if not matrix_df.empty:
        top = matrix_df.sort_values("Score", ascending=False)

        lines.append("--- Top 10 configurations (ALL regions, by Score) ---")
        for _, row in top.head(10).iterrows():
            lines.append(format_config(row))
        lines.append("")

        for label in ("US", "EU", "UK"):
            regional = matrix_df[matrix_df["Region"] == label].sort_values(
                "Score", ascending=False
            )
            lines.append(f"--- Top 10 {label} configurations ---")
            if regional.empty:
                lines.append("  No data")
            else:
                for _, row in regional.head(10).iterrows():
                    lines.append(format_config(row))
            lines.append("")

        robust = matrix_df[matrix_df["Trades"] >= MIN_ROBUST_TRADES].sort_values(
            "Score", ascending=False
        )
        lines.append(f"--- Best robust configuration (>= {MIN_ROBUST_TRADES} trades) ---")
        if robust.empty:
            lines.append("  None met minimum trade count.")
        else:
            lines.append(format_config(robust.iloc[0]))
        lines.append("")

    lines.append(f"CONCLUSION: {conclusion}")

    summary = "\n".join(lines) + "\n"
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {ALL_TRADES_CSV}")
    print(f"Saved: {MATRIX_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
