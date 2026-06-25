"""
Daily Gainers Strategy Research — ANALYSIS ONLY / NO_EXECUTION

Simulates buying after strong daily gains (signal at close, entry next session).
Does not modify portfolio, live bot, or execute trades.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

WATCHLIST_FILES = {
    "US": "watchlist_us.txt",
    "EU": "watchlist_eu.txt",
    "UK": "watchlist_uk.txt",
}
MASTER_WATCHLIST = "watchlist.txt"
LIVE_SIGNALS_FILE = "live_signals.csv"

RESULTS_CSV = "daily_gainers_strategy_results.csv"
SUMMARY_TXT = "daily_gainers_strategy_summary.txt"

HOLD_DAYS = [1, 3, 5, 7, 14, 30]
THRESHOLDS_PCT = [3.0, 5.0, 8.0, 10.0]
HISTORY_PERIOD = "5y"
MIN_TRADES_STRATEGY = 10
MIN_TRADES_OVERALL = 30
ENTRY_MODE = "next_open"  # signal known after prior close; enter next bar open


def load_tickers_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    tickers = []
    for line in lines:
        t = line.strip().upper()
        if t and not t.startswith("#"):
            tickers.append(t)
    return tickers


def infer_region(ticker: str) -> str:
    if ticker.endswith(".L"):
        return "UK"
    for suffix in (".DE", ".PA", ".AS", ".MI", ".SW", ".BR"):
        if ticker.endswith(suffix):
            return "EU"
    return "US"


def build_ticker_universe() -> dict[str, str]:
    """Map ticker -> region (US / EU / UK)."""
    region_map: dict[str, str] = {}

    for region, filename in WATCHLIST_FILES.items():
        for ticker in load_tickers_from_file(Path(filename)):
            region_map[ticker] = region

    for ticker in load_tickers_from_file(Path(MASTER_WATCHLIST)):
        if ticker not in region_map:
            region_map[ticker] = infer_region(ticker)

    if Path(LIVE_SIGNALS_FILE).exists():
        try:
            df = pd.read_csv(LIVE_SIGNALS_FILE)
            if "Ticker" in df.columns:
                for raw in df["Ticker"].dropna().astype(str):
                    ticker = raw.strip().upper()
                    if ticker and ticker not in region_map:
                        region_map[ticker] = infer_region(ticker)
        except Exception:
            pass

    return region_map


def normalize_ohlc(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()

    out = df[list(required)].copy()
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out["Ticker"] = ticker
    return out


def download_daily_history(ticker: str) -> pd.DataFrame:
    try:
        raw = yf.download(
            ticker,
            period=HISTORY_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        return normalize_ohlc(raw, ticker)
    except Exception:
        return pd.DataFrame()


def compute_daily_gain_pct(close: pd.Series) -> pd.Series:
    prev = close.shift(1)
    return ((close - prev) / prev) * 100.0


def simulate_trades(
    df: pd.DataFrame,
    threshold_pct: float,
    hold_days: int,
    region: str,
) -> list[dict]:
    if len(df) < hold_days + 2:
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
    daily_gain = compute_daily_gain_pct(close)
    ticker = df["Ticker"].iloc[0]

    trades: list[dict] = []
    last_exit_idx = -1

    for i in range(1, len(df) - hold_days):
        gain = daily_gain.iloc[i]
        if pd.isna(gain) or gain < threshold_pct:
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
        signal_date = df.index[i]
        entry_date = df.index[entry_idx]
        exit_date = df.index[exit_idx]

        trades.append(
            {
                "Region": region,
                "Ticker": ticker,
                "Threshold_Pct": threshold_pct,
                "Hold_Days": hold_days,
                "Entry_Mode": ENTRY_MODE,
                "Signal_Date": signal_date.strftime("%Y-%m-%d"),
                "Entry_Date": entry_date.strftime("%Y-%m-%d"),
                "Exit_Date": exit_date.strftime("%Y-%m-%d"),
                "Signal_Daily_Gain_Pct": round(float(gain), 4),
                "Entry_Price": round(entry_price, 4),
                "Exit_Price": round(exit_price, 4),
                "Return_Pct": round(ret_pct, 4),
            }
        )
        last_exit_idx = exit_idx

    return trades


def aggregate_strategy(trades: list[dict]) -> dict | None:
    if not trades:
        return None

    returns = np.array([t["Return_Pct"] for t in trades], dtype=float)
    wins = returns > 0

    return {
        "Region": trades[0]["Region"],
        "Threshold_Pct": trades[0]["Threshold_Pct"],
        "Hold_Days": trades[0]["Hold_Days"],
        "Entry_Mode": trades[0]["Entry_Mode"],
        "Num_Trades": len(trades),
        "Win_Rate_Pct": round(float(wins.mean() * 100.0), 2),
        "Avg_Return_Pct": round(float(returns.mean()), 4),
        "Median_Return_Pct": round(float(np.median(returns)), 4),
        "Max_Loss_Pct": round(float(returns.min()), 4),
        "Max_Gain_Pct": round(float(returns.max()), 4),
        "Total_Return_Pct": round(float(returns.sum()), 4),
    }


def determine_conclusion(summary_df: pd.DataFrame, trade_count: int) -> str:
    if trade_count < MIN_TRADES_OVERALL:
        return "INSUFFICIENT_DATA"

    viable = summary_df[summary_df["Num_Trades"] >= MIN_TRADES_STRATEGY].copy()
    if viable.empty:
        return "INSUFFICIENT_DATA"

    best = viable.sort_values("Avg_Return_Pct", ascending=False).iloc[0]
    if (
        best["Avg_Return_Pct"] > 0.25
        and best["Win_Rate_Pct"] >= 50.0
        and best["Num_Trades"] >= MIN_TRADES_STRATEGY
    ):
        return "BEST_STRATEGY"

    return "NO_EDGE"


def format_best_strategy_row(row: pd.Series) -> str:
    return (
        f"Region={row['Region']} | Threshold>={row['Threshold_Pct']}% | "
        f"Hold={row['Hold_Days']}d | Trades={row['Num_Trades']} | "
        f"WinRate={row['Win_Rate_Pct']}% | AvgReturn={row['Avg_Return_Pct']}%"
    )


def main() -> None:
    print("===== DAILY GAINERS STRATEGY RESEARCH (ANALYSIS ONLY) =====")
    print("Mode: NO_EXECUTION | NO_BROKER | NO_PORTFOLIO_CHANGES")
    print()

    ticker_regions = build_ticker_universe()
    if not ticker_regions:
        print("No tickers found in watchlists.")
        Path(SUMMARY_TXT).write_text("CONCLUSION: INSUFFICIENT_DATA\nNo tickers loaded.\n")
        return

    print(f"Universe: {len(ticker_regions)} tickers")
    for region in ("US", "EU", "UK"):
        count = sum(1 for r in ticker_regions.values() if r == region)
        print(f"  {region}: {count}")

    all_trades: list[dict] = []
    downloaded = 0
    failed = []

    for ticker, region in sorted(ticker_regions.items()):
        df = download_daily_history(ticker)
        if df.empty or len(df) < max(HOLD_DAYS) + 2:
            failed.append(ticker)
            continue
        downloaded += 1

        for threshold in THRESHOLDS_PCT:
            for hold in HOLD_DAYS:
                all_trades.extend(simulate_trades(df, threshold, hold, region))

    trade_df = pd.DataFrame(all_trades)
    summary_rows: list[dict] = []

    if not trade_df.empty:
        for region in ("US", "EU", "UK", "ALL"):
            for threshold in THRESHOLDS_PCT:
                for hold in HOLD_DAYS:
                    subset = trade_df[
                        (trade_df["Threshold_Pct"] == threshold)
                        & (trade_df["Hold_Days"] == hold)
                    ]
                    if region != "ALL":
                        subset = subset[subset["Region"] == region]
                    agg = aggregate_strategy(subset.to_dict("records"))
                    if agg:
                        if region == "ALL":
                            agg["Region"] = "ALL"
                        summary_rows.append(agg)

    summary_df = pd.DataFrame(summary_rows)
    conclusion = determine_conclusion(summary_df, len(all_trades))

    if summary_df.empty:
        summary_df = pd.DataFrame(
            columns=[
                "Region", "Threshold_Pct", "Hold_Days", "Entry_Mode",
                "Num_Trades", "Win_Rate_Pct", "Avg_Return_Pct", "Median_Return_Pct",
                "Max_Loss_Pct", "Max_Gain_Pct", "Total_Return_Pct",
            ]
        )
    summary_df.to_csv(RESULTS_CSV, index=False)

    lines = [
        "===== DAILY GAINERS STRATEGY RESEARCH =====",
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
        f"Entry timing: {ENTRY_MODE} (signal after prior close)",
        f"History period: {HISTORY_PERIOD}",
        "",
        "Thresholds tested: " + ", ".join(f"{t}%" for t in THRESHOLDS_PCT),
        "Hold days tested: " + ", ".join(str(h) for h in HOLD_DAYS),
        "",
    ]

    if failed:
        lines.append("Failed/short tickers: " + ", ".join(failed[:30]))
        if len(failed) > 30:
            lines.append(f"  ... and {len(failed) - 30} more")
        lines.append("")

    if not trade_df.empty:
        unique_signals = trade_df.drop_duplicates(
            subset=["Ticker", "Signal_Date", "Threshold_Pct"]
        )
        lines.append(
            f"Unique ticker-day signals (min threshold {THRESHOLDS_PCT[0]}%): "
            f"{len(unique_signals[unique_signals['Threshold_Pct'] == THRESHOLDS_PCT[0]])}"
        )
        lines.append("")

    if not summary_df.empty:
        lines.append("--- Top strategies by average return (min 10 trades) ---")
        viable = summary_df[summary_df["Num_Trades"] >= MIN_TRADES_STRATEGY]
        if not viable.empty:
            top = viable.sort_values("Avg_Return_Pct", ascending=False).head(10)
            for _, row in top.iterrows():
                lines.append(format_best_strategy_row(row))
        else:
            lines.append("No strategy reached minimum trade count.")
        lines.append("")

        lines.append("--- Regional breakdown (best per region) ---")
        for region in ("US", "EU", "UK"):
            regional = viable[viable["Region"] == region]
            if regional.empty:
                lines.append(f"{region}: insufficient trades")
                continue
            best = regional.sort_values("Avg_Return_Pct", ascending=False).iloc[0]
            lines.append(f"{region}: {format_best_strategy_row(best)}")
        lines.append("")

    lines.append(f"CONCLUSION: {conclusion}")
    if conclusion == "BEST_STRATEGY" and not summary_df.empty:
        viable = summary_df[summary_df["Num_Trades"] >= MIN_TRADES_STRATEGY]
        best = viable.sort_values("Avg_Return_Pct", ascending=False).iloc[0]
        lines.append(f"BEST: {format_best_strategy_row(best)}")
    elif conclusion == "NO_EDGE":
        lines.append(
            "No threshold/hold combination showed consistent positive edge "
            f"(min trades={MIN_TRADES_STRATEGY}, min avg return > 0.25%, win rate >= 50%)."
        )
    else:
        lines.append(
            f"Need at least {MIN_TRADES_OVERALL} total trades and "
            f"{MIN_TRADES_STRATEGY} per strategy for a reliable read."
        )

    summary_text = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary_text + "\n", encoding="utf-8")

    print(summary_text)
    print()
    print(f"Saved: {RESULTS_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
