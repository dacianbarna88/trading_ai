"""
Momentum Continuation Engine v1 — ANALYSIS ONLY / PAPER ONLY / NO_EXECUTION

Detects explosive daily momentum with trend, volume, and RSI alignment.
Does not modify live bot, dashboard, or portfolio.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from daily_gainers_strategy_research import (
    HISTORY_PERIOD,
    build_ticker_universe,
    compute_daily_gain_pct,
)
from daily_gainers_momentum_filter_research import (
    compute_rsi,
    RSI_PERIOD,
)

warnings.filterwarnings("ignore", category=FutureWarning)

SIGNALS_CSV = "momentum_continuation_signals.csv"
SUMMARY_TXT = "momentum_continuation_summary.txt"
BACKTEST_RESULTS = "daily_gainers_momentum_filter_results.csv"

MIN_HISTORY_BARS = 200
GAIN_THRESHOLD_PCT = 5.0
RSI_LOW = 50.0
RSI_HIGH = 80.0
SUGGESTED_HOLD_DAYS = 30
MODE = "ANALYSIS_ONLY"

# Matches engine signal stack in momentum filter research
RESEARCH_FILTER = "ABOVE_SMA200_AND_VOLUME_AND_RSI"
RESEARCH_THRESHOLD = 5.0
RESEARCH_HOLD = 30


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


def enrich_latest_bar(df: pd.DataFrame) -> pd.Series | None:
    if len(df) < MIN_HISTORY_BARS:
        return None

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)
    row = df.iloc[-1].copy()
    row["Daily_Gain_Pct"] = float(compute_daily_gain_pct(close).iloc[-1])
    row["SMA50"] = float(close.rolling(50, min_periods=50).mean().iloc[-1])
    row["SMA200"] = float(close.rolling(200, min_periods=200).mean().iloc[-1])
    row["Avg20Volume"] = float(volume.rolling(20, min_periods=20).mean().iloc[-1])
    row["RSI"] = float(compute_rsi(close, RSI_PERIOD).iloc[-1])
    row["Price"] = float(close.iloc[-1])
    row["Volume"] = float(volume.iloc[-1])
    return row


def compute_momentum_score(row: pd.Series) -> int:
    score = 0
    gain = row.get("Daily_Gain_Pct", np.nan)
    close = row.get("Close", row.get("Price", np.nan))
    sma50 = row.get("SMA50", np.nan)
    sma200 = row.get("SMA200", np.nan)
    vol = row.get("Volume", np.nan)
    avg_vol = row.get("Avg20Volume", np.nan)
    rsi = row.get("RSI", np.nan)

    if not pd.isna(gain) and gain >= GAIN_THRESHOLD_PCT:
        score += 40
    if not pd.isna(close) and not pd.isna(sma200) and close > sma200:
        score += 20
    if not pd.isna(close) and not pd.isna(sma50) and close > sma50:
        score += 15
    if not pd.isna(vol) and not pd.isna(avg_vol) and vol > avg_vol:
        score += 15
    if not pd.isna(rsi) and RSI_LOW <= rsi <= RSI_HIGH:
        score += 10

    return min(score, 100)


def is_candidate(row: pd.Series) -> bool:
    if row is None:
        return False

    gain = row.get("Daily_Gain_Pct")
    close = row.get("Price")
    sma200 = row.get("SMA200")
    vol = row.get("Volume")
    avg_vol = row.get("Avg20Volume")
    rsi = row.get("RSI")

    if any(pd.isna(v) for v in (gain, close, sma200, vol, avg_vol, rsi)):
        return False

    return (
        gain >= GAIN_THRESHOLD_PCT
        and close > sma200
        and vol > avg_vol
        and RSI_LOW <= rsi <= RSI_HIGH
    )


def load_research_edge_by_region() -> dict[str, str]:
    """Load backtest edge labels from momentum filter research results."""
    path = Path(BACKTEST_RESULTS)
    if not path.exists():
        return {}

    try:
        df = pd.read_csv(path)
    except Exception:
        return {}

    mask = (
        (df["Filter"] == RESEARCH_FILTER)
        & (df["Threshold_Pct"] == RESEARCH_THRESHOLD)
        & (df["Hold_Days"] == RESEARCH_HOLD)
    )
    subset = df[mask]
    edges: dict[str, str] = {}

    for region in ("US", "EU", "UK", "ALL"):
        regional = subset[subset["Region"] == region]
        if regional.empty:
            continue
        row = regional.iloc[0]
        edges[region] = (
            f"AvgReturn={row['Avg_Return_Pct']}% | "
            f"WinRate={row['Win_Rate_Pct']}% | "
            f"Trades={int(row['Num_Trades'])} | "
            f"Hold={RESEARCH_HOLD}d"
        )

    return edges


def research_edge_for_region(region: str, edges: dict[str, str]) -> str:
    if region in edges:
        return edges[region]
    if "ALL" in edges:
        return edges["ALL"]
    return "NO_BACKTEST_DATA"


def scan_universe(ticker_regions: dict[str, str]) -> tuple[list[dict], int, list[str]]:
    candidates: list[dict] = []
    failed: list[str] = []
    checked = 0
    edges = load_research_edge_by_region()

    for ticker, region in sorted(ticker_regions.items()):
        df = download_history(ticker)
        if df.empty or len(df) < MIN_HISTORY_BARS:
            failed.append(ticker)
            continue

        checked += 1
        row = enrich_latest_bar(df)
        if not is_candidate(row):
            continue

        score = compute_momentum_score(row)
        candidates.append(
            {
                "Ticker": ticker,
                "Region": region,
                "Price": round(float(row["Price"]), 4),
                "Daily_Gain_%": round(float(row["Daily_Gain_Pct"]), 4),
                "RSI": round(float(row["RSI"]), 2),
                "SMA50": round(float(row["SMA50"]), 4),
                "SMA200": round(float(row["SMA200"]), 4),
                "Volume": int(row["Volume"]),
                "Avg20Volume": int(row["Avg20Volume"]),
                "Momentum_Score": score,
                "Suggested_Hold_Days": SUGGESTED_HOLD_DAYS,
                "Research_Edge": research_edge_for_region(region, edges),
                "Mode": MODE,
            }
        )

    return candidates, checked, failed


def write_summary(
    ticker_count: int,
    checked: int,
    failed: list[str],
    candidates: list[dict],
    edges: dict[str, str],
) -> str:
    lines = [
        "===== MOMENTUM CONTINUATION ENGINE v1 =====",
        "",
        f"Mode: {MODE}",
        "NO_EXECUTION",
        "NO_BROKER",
        "NO_PORTFOLIO_CHANGES",
        "PAPER_ONLY / RESEARCH_ONLY",
        "",
        f"Total tickers in universe: {ticker_count}",
        f"Tickers checked (sufficient history): {checked}",
        f"Tickers skipped (insufficient data): {len(failed)}",
        f"MOMENTUM_CONTINUATION_CANDIDATES: {len(candidates)}",
        "",
        "Signal rules:",
        f"  - Daily gain >= {GAIN_THRESHOLD_PCT}%",
        "  - Close > SMA200",
        "  - Volume > 20-day average",
        f"  - RSI between {RSI_LOW} and {RSI_HIGH}",
        f"  - Minimum history: {MIN_HISTORY_BARS} bars",
        "",
        "WARNING: No execution. Research and paper analysis only.",
        "Do not place live or paper orders from this file alone.",
        "",
    ]

    if edges:
        lines.append("Backtest reference (filter research, 30d hold, 5% threshold):")
        for region, label in sorted(edges.items()):
            lines.append(f"  {region}: {label}")
        lines.append("")

    if failed:
        lines.append("Skipped tickers: " + ", ".join(failed))
        lines.append("")

    if candidates:
        ranked = sorted(candidates, key=lambda x: x["Momentum_Score"], reverse=True)
        lines.append("--- Best candidates (by Momentum_Score) ---")
        for c in ranked[:15]:
            lines.append(
                f"{c['Ticker']} ({c['Region']}) score={c['Momentum_Score']} "
                f"gain={c['Daily_Gain_%']}% RSI={c['RSI']} "
                f"edge={c['Research_Edge']}"
            )
    else:
        lines.append("No candidates matched all momentum continuation filters today.")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    print("===== MOMENTUM CONTINUATION ENGINE v1 =====")
    print(f"Mode: {MODE} | NO_EXECUTION")
    print()

    ticker_regions = build_ticker_universe()
    if not ticker_regions:
        Path(SUMMARY_TXT).write_text(
            "No tickers in universe.\nWARNING: No execution.\n",
            encoding="utf-8",
        )
        pd.DataFrame().to_csv(SIGNALS_CSV, index=False)
        print("No tickers loaded.")
        return

    candidates, checked, failed = scan_universe(ticker_regions)
    edges = load_research_edge_by_region()

    df = pd.DataFrame(candidates)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "Ticker", "Region", "Price", "Daily_Gain_%", "RSI",
                "SMA50", "SMA200", "Volume", "Avg20Volume", "Momentum_Score",
                "Suggested_Hold_Days", "Research_Edge", "Mode",
            ]
        )
    else:
        df = df.sort_values("Momentum_Score", ascending=False)

    df.to_csv(SIGNALS_CSV, index=False)

    summary = write_summary(len(ticker_regions), checked, failed, candidates, edges)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")

    print(summary)
    print(f"Saved: {SIGNALS_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
