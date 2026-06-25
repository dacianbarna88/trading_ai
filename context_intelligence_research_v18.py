"""
Context Intelligence Research V1.8 — Momentum Signal Context Analysis

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import itertools
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from momentum_continuation_research_v11 import (
    ENTRY_MODE,
    HISTORY_PERIOD,
    MIN_HISTORY_BARS,
    compute_rsi,
    download_history,
    filter_passes,
)

warnings.filterwarnings("ignore", category=FutureWarning)

UNIVERSE_FILE = "us_expanded_universe.txt"
FEATURES_CSV = "context_v18_signal_features.csv"
BINS_CSV = "context_v18_feature_bins.csv"
PATTERNS_CSV = "context_v18_pattern_rankings.csv"
SUMMARY_TXT = "context_v18_summary.txt"

THRESHOLD = 5.0
HOLD_DAYS = 60
FILTER_MODE = "NO_FILTER"
ATR_PERIOD = 14
MIN_PATTERN_TRADES = 100
EDGE_AVG_LIFT = 2.0
EDGE_WIN_LIFT = 5.0
AVOID_AVG_DROP = 2.0
AVOID_WIN_DROP = 5.0
UNSTABLE_GAP = 3.0
HIGH_RISK_WORST = -40.0

BIN_FEATURES = [
    "Daily_Gain_Pct",
    "Volume_Ratio",
    "DollarVolume_Ratio",
    "Close_Location",
    "Gap_Pct",
    "Intraday_Return_Pct",
    "RSI_14",
    "ATR_14_Pct",
    "Close_vs_SMA200_Pct",
    "Market_Regime",
]


def load_universe() -> list[str]:
    path = Path(UNIVERSE_FILE)
    if path.exists():
        tickers = [
            line.strip().upper()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if tickers:
            return tickers
    from momentum_universe_expansion_v13 import dedupe_universe, EXPANDED_US_UNIVERSE

    return dedupe_universe(EXPANDED_US_UNIVERSE)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def enrich_ticker(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    o = out["Open"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)
    c = out["Close"].astype(float)
    v = out["Volume"].astype(float)
    prev_c = c.shift(1)

    out["Daily_Gain_Pct"] = (c / prev_c - 1.0) * 100.0
    out["Dollar_Volume"] = c * v
    out["Avg20Volume"] = v.rolling(20, min_periods=20).mean()
    out["Avg20DollarVolume"] = out["Dollar_Volume"].rolling(20, min_periods=20).mean()
    out["Volume_Ratio"] = v / out["Avg20Volume"]
    out["DollarVolume_Ratio"] = out["Dollar_Volume"] / out["Avg20DollarVolume"]
    span = h - l
    out["Close_Location"] = np.where(span > 0, (c - l) / span, np.nan)
    out["Gap_Pct"] = ((o - prev_c) / prev_c.replace(0, np.nan)) * 100.0
    out["Intraday_Return_Pct"] = ((c - o) / o.replace(0, np.nan)) * 100.0
    out["Range_Pct"] = ((h - l) / prev_c.replace(0, np.nan)) * 100.0
    out["RSI_14"] = compute_rsi(c, ATR_PERIOD)
    out["ATR_14"] = compute_atr(h, l, c, ATR_PERIOD)
    out["ATR_14_Pct"] = (out["ATR_14"] / c.replace(0, np.nan)) * 100.0
    out["SMA50"] = c.rolling(50, min_periods=50).mean()
    out["SMA200"] = c.rolling(200, min_periods=200).mean()
    out["Close_vs_SMA50_Pct"] = ((c / out["SMA50"] - 1.0) * 100.0)
    out["Close_vs_SMA200_Pct"] = ((c / out["SMA200"] - 1.0) * 100.0)
    return out


def enrich_spy(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)
    out["SMA200"] = c.rolling(200, min_periods=200).mean()
    out["SPY_Close_vs_SMA200_Pct"] = (c / out["SMA200"] - 1.0) * 100.0
    out["SPY_20d_Return_Pct"] = (c / c.shift(20) - 1.0) * 100.0
    out["SPY_60d_Return_Pct"] = (c / c.shift(60) - 1.0) * 100.0
    out["ATR_14"] = compute_atr(h, l, c, ATR_PERIOD)
    out["SPY_ATR_14_Pct"] = (out["ATR_14"] / c.replace(0, np.nan)) * 100.0

    regime = []
    for i in range(len(out)):
        row = out.iloc[i]
        spy_c, sma200, ret60 = row["Close"], row["SMA200"], row["SPY_60d_Return_Pct"]
        if pd.isna(sma200) or pd.isna(ret60):
            regime.append("NEUTRAL")
        elif spy_c > sma200 and ret60 > 0:
            regime.append("BULL")
        elif spy_c < sma200 and ret60 < 0:
            regime.append("BEAR")
        else:
            regime.append("NEUTRAL")
    out["Market_Regime"] = regime
    return out


def assign_bin(feature: str, value: float | str) -> str:
    if feature == "Market_Regime":
        return str(value)

    if pd.isna(value):
        return "MISSING"

    v = float(value)
    if feature == "Daily_Gain_Pct":
        if v < 7:
            return "5-7%"
        if v < 10:
            return "7-10%"
        if v < 15:
            return "10-15%"
        return "15%+"

    if feature in ("Volume_Ratio", "DollarVolume_Ratio"):
        if v < 1.0:
            return "<1.0"
        if v < 1.5:
            return "1.0-1.5"
        if v < 2.0:
            return "1.5-2.0"
        return "2.0+"

    if feature == "Close_Location":
        if v < 0.33:
            return "0.00-0.33"
        if v < 0.66:
            return "0.33-0.66"
        return "0.66-1.00"

    if feature == "Gap_Pct":
        if v < 0:
            return "negative"
        if v < 2:
            return "0-2%"
        if v < 5:
            return "2-5%"
        return "5%+"

    if feature == "Intraday_Return_Pct":
        if v < 0:
            return "negative"
        if v < 3:
            return "0-3%"
        if v < 7:
            return "3-7%"
        return "7%+"

    if feature == "RSI_14":
        if v < 40:
            return "<40"
        if v < 50:
            return "40-50"
        if v < 60:
            return "50-60"
        if v < 70:
            return "60-70"
        return "70+"

    if feature == "ATR_14_Pct":
        if v < 2:
            return "<2%"
        if v < 3:
            return "2-3%"
        if v < 4:
            return "3-4%"
        return "4%+"

    if feature == "Close_vs_SMA200_Pct":
        if v < -5:
            return "<-5%"
        if v < 0:
            return "-5% to 0%"
        if v < 10:
            return "0-10%"
        return "10%+"

    return "OTHER"


def compute_mfe_mae(
    high: pd.Series,
    low: pd.Series,
    entry_idx: int,
    exit_idx: int,
    entry_price: float,
) -> tuple[float, float]:
    mfe = -np.inf
    mae = np.inf
    for d in range(entry_idx, exit_idx + 1):
        hi = float(high.iloc[d])
        lo = float(low.iloc[d])
        fav = ((hi - entry_price) / entry_price) * 100.0
        adv = ((lo - entry_price) / entry_price) * 100.0
        if fav > mfe:
            mfe = fav
        if adv < mae:
            mae = adv
    return float(mfe), float(mae)


def collect_signals(
    ticker: str,
    df: pd.DataFrame,
    spy_ctx: pd.DataFrame,
) -> list[dict]:
    if len(df) < MIN_HISTORY_BARS + HOLD_DAYS:
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    trades: list[dict] = []
    last_exit_idx = -1

    for i in range(1, len(df) - HOLD_DAYS):
        row = df.iloc[i]
        if not filter_passes(FILTER_MODE, row, THRESHOLD):
            continue

        entry_idx = i + 1
        exit_idx = entry_idx + HOLD_DAYS - 1
        if exit_idx >= len(df):
            break
        if entry_idx <= last_exit_idx:
            continue

        entry_price = float(open_.iloc[entry_idx])
        exit_price = float(close.iloc[exit_idx])
        if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
            continue

        fwd_ret = ((exit_price - entry_price) / entry_price) * 100.0
        mfe, mae = compute_mfe_mae(high, low, entry_idx, exit_idx, entry_price)
        signal_date = df.index[i]
        spy_row = spy_ctx.loc[signal_date] if signal_date in spy_ctx.index else None

        spy_vs_sma200 = None
        spy_20d = None
        spy_60d = None
        spy_atr = None
        regime = "NEUTRAL"
        if spy_row is not None:
            spy_vs_sma200 = spy_row.get("SPY_Close_vs_SMA200_Pct")
            spy_20d = spy_row.get("SPY_20d_Return_Pct")
            spy_60d = spy_row.get("SPY_60d_Return_Pct")
            spy_atr = spy_row.get("SPY_ATR_14_Pct")
            regime = spy_row.get("Market_Regime", "NEUTRAL")

        trades.append(
            {
                "Ticker": ticker,
                "Signal_Date": signal_date.strftime("%Y-%m-%d"),
                "Daily_Gain_Pct": round(float(row["Daily_Gain_Pct"]), 4),
                "Volume_Ratio": round(float(row["Volume_Ratio"]), 4)
                if not pd.isna(row["Volume_Ratio"])
                else None,
                "DollarVolume_Ratio": round(float(row["DollarVolume_Ratio"]), 4)
                if not pd.isna(row["DollarVolume_Ratio"])
                else None,
                "Close_Location": round(float(row["Close_Location"]), 4)
                if not pd.isna(row["Close_Location"])
                else None,
                "Gap_Pct": round(float(row["Gap_Pct"]), 4)
                if not pd.isna(row["Gap_Pct"])
                else None,
                "Intraday_Return_Pct": round(float(row["Intraday_Return_Pct"]), 4)
                if not pd.isna(row["Intraday_Return_Pct"])
                else None,
                "Range_Pct": round(float(row["Range_Pct"]), 4)
                if not pd.isna(row["Range_Pct"])
                else None,
                "RSI_14": round(float(row["RSI_14"]), 4)
                if not pd.isna(row["RSI_14"])
                else None,
                "ATR_14_Pct": round(float(row["ATR_14_Pct"]), 4)
                if not pd.isna(row["ATR_14_Pct"])
                else None,
                "Close_vs_SMA50_Pct": round(float(row["Close_vs_SMA50_Pct"]), 4)
                if not pd.isna(row["Close_vs_SMA50_Pct"])
                else None,
                "Close_vs_SMA200_Pct": round(float(row["Close_vs_SMA200_Pct"]), 4)
                if not pd.isna(row["Close_vs_SMA200_Pct"])
                else None,
                "SPY_Close_vs_SMA200_Pct": round(float(spy_vs_sma200), 4)
                if spy_vs_sma200 is not None and not pd.isna(spy_vs_sma200)
                else None,
                "SPY_20d_Return_Pct": round(float(spy_20d), 4)
                if spy_20d is not None and not pd.isna(spy_20d)
                else None,
                "SPY_60d_Return_Pct": round(float(spy_60d), 4)
                if spy_60d is not None and not pd.isna(spy_60d)
                else None,
                "SPY_ATR_14_Pct": round(float(spy_atr), 4)
                if spy_atr is not None and not pd.isna(spy_atr)
                else None,
                "Market_Regime": regime,
                "Forward_Return_60d": round(fwd_ret, 4),
                "Win": fwd_ret > 0,
                "MAE": round(mae, 4),
                "MFE": round(mfe, 4),
            }
        )
        last_exit_idx = exit_idx

    return trades


def baseline_metrics(signals: pd.DataFrame) -> dict:
    rets = signals["Forward_Return_60d"].astype(float).values
    return {
        "Trades": len(rets),
        "Win_Rate": round(float((rets > 0).mean() * 100.0), 2),
        "Avg_Return": round(float(rets.mean()), 4),
        "Median_Return": round(float(np.median(rets)), 4),
        "Profit_Factor": round(profit_factor(rets), 4),
        "Worst_Trade": round(float(rets.min()), 4),
    }


def robustness_flags(
    trades: int,
    avg_ret: float,
    median_ret: float,
    worst: float,
    lift_avg: float,
    baseline: dict,
) -> str:
    flags: list[str] = []
    if trades < MIN_PATTERN_TRADES:
        flags.append("TOO_FEW_TRADES")
    if lift_avg < 1.0:
        flags.append("WEAK_LIFT")
    if avg_ret - median_ret > UNSTABLE_GAP:
        flags.append("UNSTABLE")
    if worst < HIGH_RISK_WORST:
        flags.append("HIGH_RISK")
    return "|".join(flags) if flags else "OK"


def aggregate_group(signals: pd.DataFrame, baseline: dict) -> dict:
    rets = signals["Forward_Return_60d"].astype(float)
    maes = signals["MAE"].astype(float)
    mfes = signals["MFE"].astype(float)
    avg_ret = float(rets.mean())
    median_ret = float(np.median(rets))
    worst = float(rets.min())
    win_rate = float((rets > 0).mean() * 100.0)
    lift_avg = avg_ret - baseline["Avg_Return"]
    lift_win = win_rate - baseline["Win_Rate"]
    trades = len(rets)
    return {
        "Trade_Count": trades,
        "Trades": trades,
        "Win_Rate": round(win_rate, 2),
        "Avg_Return": round(avg_ret, 4),
        "Median_Return": round(median_ret, 4),
        "Total_Return": round(float(rets.sum()), 4),
        "Profit_Factor": round(profit_factor(rets.values), 4),
        "Worst_Trade": round(worst, 4),
        "MAE_Median": round(float(maes.median()), 4),
        "MFE_Median": round(float(mfes.median()), 4),
        "Lift_vs_Baseline_Avg": round(lift_avg, 4),
        "Lift_vs_Baseline_WinRate": round(lift_win, 2),
        "Robustness_Flag": robustness_flags(
            trades, avg_ret, median_ret, worst, lift_avg, baseline
        ),
    }


def build_single_bins(signals: pd.DataFrame, baseline: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for feature in BIN_FEATURES:
        bins = signals[feature].apply(lambda v, f=feature: assign_bin(f, v))
        signals_with_bin = signals.copy()
        signals_with_bin["_bin"] = bins
        for bin_val, grp in signals_with_bin.groupby("_bin", dropna=False):
            if bin_val == "MISSING":
                continue
            agg = aggregate_group(grp, baseline)
            rows.append(
                {
                    "Feature": feature,
                    "Bin": bin_val,
                    "Pattern_Type": "SINGLE",
                    **agg,
                }
            )
    return pd.DataFrame(rows)


def build_two_feature_patterns(signals: pd.DataFrame, baseline: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for f1, f2 in itertools.combinations(BIN_FEATURES, 2):
        b1 = signals[f1].apply(lambda v, f=f1: assign_bin(f, v))
        b2 = signals[f2].apply(lambda v, f=f2: assign_bin(f, v))
        mask = (b1 != "MISSING") & (b2 != "MISSING")
        sub = signals[mask].copy()
        if sub.empty:
            continue
        b1_sub = b1[mask]
        b2_sub = b2[mask]
        for bv1 in b1_sub.unique():
            for bv2 in b2_sub.unique():
                grp_mask = (b1_sub == bv1) & (b2_sub == bv2)
                grp = sub[grp_mask]
                if grp.empty:
                    continue
                condition = f"{f1}={bv1} | {f2}={bv2}"
                agg = aggregate_group(grp, baseline)
                rows.append(
                    {
                        "Pattern_Name": condition,
                        "Condition": condition,
                        "Feature_1": f1,
                        "Bin_1": bv1,
                        "Feature_2": f2,
                        "Bin_2": bv2,
                        "Pattern_Type": "TWO_FEATURE",
                        **agg,
                    }
                )
    return pd.DataFrame(rows)


def is_context_edge(row: pd.Series, baseline: dict) -> bool:
    return (
        row["Trades"] >= MIN_PATTERN_TRADES
        and row["Lift_vs_Baseline_Avg"] >= EDGE_AVG_LIFT
        and row["Lift_vs_Baseline_WinRate"] >= EDGE_WIN_LIFT
        and row["Profit_Factor"] > baseline["Profit_Factor"]
        and row["Worst_Trade"] >= baseline["Worst_Trade"]
    )


def is_avoidance_filter(row: pd.Series, baseline: dict) -> bool:
    return (
        row["Trades"] >= MIN_PATTERN_TRADES
        and row["Lift_vs_Baseline_Avg"] <= -AVOID_AVG_DROP
        and row["Lift_vs_Baseline_WinRate"] <= -AVOID_WIN_DROP
    )


def format_bin_row(row: pd.Series) -> str:
    label = row.get("Pattern_Name") or f"{row['Feature']}={row['Bin']}"
    return (
        f"{label} | trades={int(row['Trades'])} | "
        f"avg={row['Avg_Return']}% win={row['Win_Rate']}% | "
        f"lift_avg={row['Lift_vs_Baseline_Avg']}% lift_win={row['Lift_vs_Baseline_WinRate']}% | "
        f"{row['Robustness_Flag']}"
    )


def determine_verdict(
    bins_df: pd.DataFrame,
    patterns_df: pd.DataFrame,
    baseline: dict,
) -> str:
    all_patterns = pd.concat([bins_df, patterns_df], ignore_index=True)
    if all_patterns.empty:
        return "NO_CLEAR_CONTEXT_EDGE"

    context_edges = all_patterns[all_patterns.apply(lambda r: is_context_edge(r, baseline), axis=1)]
    avoidances = all_patterns[all_patterns.apply(lambda r: is_avoidance_filter(r, baseline), axis=1)]

    if not context_edges.empty:
        return "CONTEXT_EDGE_FOUND"
    if not avoidances.empty:
        return "AVOIDANCE_FILTER_FOUND"
    return "NO_CLEAR_CONTEXT_EDGE"


def main() -> None:
    print("===== CONTEXT INTELLIGENCE RESEARCH V1.8 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_EXECUTION")
    print()

    universe = load_universe()
    print(f"Universe: {len(universe)} symbols")

    spy_raw = download_history("SPY")
    if spy_raw.empty:
        Path(SUMMARY_TXT).write_text("SPY_DOWNLOAD_FAILED\n", encoding="utf-8")
        print("Failed to download SPY context data.")
        return
    spy_ctx = enrich_spy(spy_raw)

    all_signals: list[dict] = []
    tickers_loaded = 0
    skipped: list[tuple[str, str]] = []

    for ticker in universe:
        raw = download_history(ticker)
        if raw.empty:
            skipped.append((ticker, "DOWNLOAD_FAILED"))
            continue
        if len(raw) < MIN_HISTORY_BARS + HOLD_DAYS:
            skipped.append((ticker, f"INSUFFICIENT_HISTORY_{len(raw)}"))
            continue

        df = enrich_ticker(raw)
        signals = collect_signals(ticker, df, spy_ctx)
        if signals:
            tickers_loaded += 1
            all_signals.extend(signals)

    if not all_signals:
        Path(SUMMARY_TXT).write_text("INSUFFICIENT_DATA\n", encoding="utf-8")
        print("No signals collected.")
        return

    signals_df = pd.DataFrame(all_signals)
    signals_df.to_csv(FEATURES_CSV, index=False)

    baseline = baseline_metrics(signals_df)
    bins_df = build_single_bins(signals_df, baseline)
    bins_df.to_csv(BINS_CSV, index=False)

    patterns_df = build_two_feature_patterns(signals_df, baseline)
    patterns_df.to_csv(PATTERNS_CSV, index=False)

    verdict = determine_verdict(bins_df, patterns_df, baseline)

    top_bins = bins_df.sort_values("Lift_vs_Baseline_Avg", ascending=False).head(20)
    bottom_bins = bins_df.sort_values("Lift_vs_Baseline_Avg", ascending=True).head(20)
    top_patterns = patterns_df.sort_values("Lift_vs_Baseline_Avg", ascending=False).head(20)
    bottom_patterns = patterns_df.sort_values("Lift_vs_Baseline_Avg", ascending=True).head(20)

    useful = pd.concat([bins_df, patterns_df])
    useful = useful[
        useful.apply(lambda r: is_context_edge(r, baseline), axis=1)
    ].sort_values("Lift_vs_Baseline_Avg", ascending=False)

    avoid = pd.concat([bins_df, patterns_df])
    avoid = avoid[
        avoid.apply(lambda r: is_avoidance_filter(r, baseline), axis=1)
    ].sort_values("Lift_vs_Baseline_Avg", ascending=True)

    lines = [
        "===== CONTEXT INTELLIGENCE RESEARCH V1.8 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "",
        f"Universe size: {len(universe)}",
        f"Tickers loaded: {tickers_loaded}",
        f"Tickers skipped: {len(skipped)}",
        f"History: {HISTORY_PERIOD} | Threshold>={THRESHOLD}% | Hold={HOLD_DAYS}d",
        f"Entry: {ENTRY_MODE} | Filter: {FILTER_MODE}",
        "",
        "--- Baseline (all signals) ---",
        f"Trades: {baseline['Trades']}",
        f"Win_Rate: {baseline['Win_Rate']}%",
        f"Avg_Return: {baseline['Avg_Return']}%",
        f"Median_Return: {baseline['Median_Return']}%",
        f"Profit_Factor: {baseline['Profit_Factor']}",
        f"Worst_Trade: {baseline['Worst_Trade']}%",
        "",
        "--- Top 20 single-feature bins (by avg lift) ---",
    ]
    for _, row in top_bins.iterrows():
        lines.append("  " + format_bin_row(row))
    lines.append("")

    lines.append("--- Bottom 20 single-feature bins ---")
    for _, row in bottom_bins.iterrows():
        lines.append("  " + format_bin_row(row))
    lines.append("")

    lines.append("--- Top 20 two-feature patterns ---")
    for _, row in top_patterns.iterrows():
        lines.append("  " + format_bin_row(row))
    lines.append("")

    lines.append("--- Bottom 20 two-feature patterns ---")
    for _, row in bottom_patterns.iterrows():
        lines.append("  " + format_bin_row(row))
    lines.append("")

    lines.append("--- Most useful context filters (strict edge criteria) ---")
    if useful.empty:
        lines.append("  None met trades>=100, avg lift>=2%, win lift>=5%, PF>baseline, worst>=baseline")
    else:
        for _, row in useful.head(10).iterrows():
            lines.append("  " + format_bin_row(row))
    lines.append("")

    lines.append("--- Contexts to avoid (strict avoidance criteria) ---")
    if avoid.empty:
        lines.append("  None met trades>=100, avg<=-2% vs baseline, win<=-5% vs baseline")
    else:
        for _, row in avoid.head(10).iterrows():
            lines.append("  " + format_bin_row(row))
    lines.append("")

    lines.append(
        "Edge criteria: trades>=100, avg lift>=2%, win lift>=5%, PF>baseline, worst>=baseline."
    )
    lines.append(
        "Avoidance criteria: trades>=100, avg lift<=-2%, win lift<=-5%."
    )
    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {FEATURES_CSV}")
    print(f"Saved: {BINS_CSV}")
    print(f"Saved: {PATTERNS_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
