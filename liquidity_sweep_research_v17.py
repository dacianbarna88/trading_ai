"""
Liquidity Sweep / Stop Hunt Research V1.7

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Tests observable OHLCV patterns at round stop/take-profit levels vs controls.
Does NOT claim market manipulation — pattern statistics only.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from momentum_continuation_research_v11 import (
    HISTORY_PERIOD,
    MIN_HISTORY_BARS,
    download_history,
)

warnings.filterwarnings("ignore", category=FutureWarning)

UNIVERSE_FILE = "us_expanded_universe.txt"
EVENTS_CSV = "liquidity_sweep_events_v17.csv"
LEVEL_STATS_CSV = "liquidity_sweep_level_stats_v17.csv"
CONTROL_CSV = "liquidity_sweep_control_comparison_v17.csv"
SUMMARY_TXT = "liquidity_sweep_summary_v17.txt"

FORWARD_HORIZONS = [1, 3, 7, 14, 30, 60]
MIN_EDGE_EVENTS = 100
RETURN_EDGE_THRESHOLD = 0.20
WIN_RATE_EDGE_THRESHOLD = 2.0
RATE_EDGE_THRESHOLD = 0.05

POPULAR_STOP_LEVELS = [-3, -5, -7, -10, -12, -15, -20]
CONTROL_STOP_LEVELS = [
    -2.6, -3.4, -4.6, -5.4, -6.6, -7.4, -9.4, -10.6,
    -11.4, -12.6, -14.4, -15.6, -19.4, -20.6,
]
POPULAR_TP_LEVELS = [3, 5, 7, 10, 15, 20]
CONTROL_TP_LEVELS = [
    2.6, 3.4, 4.6, 5.4, 6.6, 7.4, 9.4, 10.6, 14.4, 15.6, 19.4, 20.6,
]

VOLUME_FILTERS = [
    ("NONE", None),
    ("Volume_Ratio_1.5", ("Volume_Ratio", 1.5)),
    ("DollarVolume_Ratio_1.5", ("DollarVolume_Ratio", 1.5)),
    ("Volume_Ratio_2.0", ("Volume_Ratio", 2.0)),
    ("DollarVolume_Ratio_2.0", ("DollarVolume_Ratio", 2.0)),
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


def enrich_daily(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    o = out["Open"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)
    c = out["Close"].astype(float)
    v = out["Volume"].astype(float)

    out["Prev_Close"] = c.shift(1)
    out["Dollar_Volume"] = c * v
    out["Avg20Volume"] = v.rolling(20, min_periods=20).mean()
    out["Avg20DollarVolume"] = out["Dollar_Volume"].rolling(20, min_periods=20).mean()
    out["Volume_Ratio"] = v / out["Avg20Volume"]
    out["DollarVolume_Ratio"] = out["Dollar_Volume"] / out["Avg20DollarVolume"]
    out["Daily_Return"] = (c / out["Prev_Close"] - 1.0) * 100.0
    out["Intraday_Range_Pct"] = ((h - l) / c.replace(0, np.nan)) * 100.0
    span = h - l
    out["Close_Location"] = np.where(span > 0, (c - l) / span, np.nan)

    for n in FORWARD_HORIZONS:
        out[f"Fwd_Close_{n}d"] = c.shift(-n)
        out[f"Fwd_Return_{n}d"] = ((out[f"Fwd_Close_{n}d"] - c) / c.replace(0, np.nan)) * 100.0

    return out


def level_category(level: float, event_type: str) -> str:
    if event_type == "STOP_SWEEP":
        return "POPULAR" if level in POPULAR_STOP_LEVELS else "CONTROL"
    return "POPULAR" if level in POPULAR_TP_LEVELS else "CONTROL"


def is_stop_sweep(row: pd.Series, stop_pct: float) -> bool:
    prev = row["Prev_Close"]
    if pd.isna(prev) or prev <= 0:
        return False
    threshold = prev * (1 + stop_pct / 100.0)
    return row["Low"] <= threshold and row["Close"] > threshold


def is_failed_take_profit(row: pd.Series, profit_pct: float) -> bool:
    prev = row["Prev_Close"]
    if pd.isna(prev) or prev <= 0:
        return False
    if pd.isna(row["Close_Location"]):
        return False
    target = prev * (1 + profit_pct / 100.0)
    near_target = prev * (1 + profit_pct / 100.0 * 0.95)
    return (
        row["High"] >= near_target
        and row["High"] < target
        and row["Close"] < row["High"]
        and row["Close_Location"] < 0.5
    )


def passes_volume_filter(row: pd.Series, filter_spec: tuple[str, float] | None) -> bool:
    if filter_spec is None:
        return True
    field, minimum = filter_spec
    val = row[field]
    return not pd.isna(val) and val >= minimum


def collect_ticker_events(ticker: str, df: pd.DataFrame) -> tuple[list[dict], int]:
    events: list[dict] = []
    max_fwd = max(FORWARD_HORIZONS)
    start = 20
    end = len(df) - max_fwd
    if end <= start:
        return events, 0

    analysis_days = end - start
    enriched = enrich_daily(df)

    stop_levels = [(lv, "STOP_SWEEP") for lv in POPULAR_STOP_LEVELS + CONTROL_STOP_LEVELS]
    tp_levels = [(lv, "FAILED_TAKE_PROFIT") for lv in POPULAR_TP_LEVELS + CONTROL_TP_LEVELS]

    for i in range(start, end):
        row = enriched.iloc[i]
        if pd.isna(row["Prev_Close"]) or row["Prev_Close"] <= 0:
            continue

        base = {
            "Ticker": ticker,
            "Date": enriched.index[i].strftime("%Y-%m-%d"),
            "Open": round(float(row["Open"]), 4),
            "High": round(float(row["High"]), 4),
            "Low": round(float(row["Low"]), 4),
            "Close": round(float(row["Close"]), 4),
            "Volume": round(float(row["Volume"]), 2),
            "Dollar_Volume": round(float(row["Dollar_Volume"]), 2),
            "Avg20Volume": round(float(row["Avg20Volume"]), 2) if not pd.isna(row["Avg20Volume"]) else None,
            "Avg20DollarVolume": round(float(row["Avg20DollarVolume"]), 2)
            if not pd.isna(row["Avg20DollarVolume"])
            else None,
            "Volume_Ratio": round(float(row["Volume_Ratio"]), 4)
            if not pd.isna(row["Volume_Ratio"])
            else None,
            "DollarVolume_Ratio": round(float(row["DollarVolume_Ratio"]), 4)
            if not pd.isna(row["DollarVolume_Ratio"])
            else None,
            "Daily_Return": round(float(row["Daily_Return"]), 4)
            if not pd.isna(row["Daily_Return"])
            else None,
            "Intraday_Range_Pct": round(float(row["Intraday_Range_Pct"]), 4)
            if not pd.isna(row["Intraday_Range_Pct"])
            else None,
            "Close_Location": round(float(row["Close_Location"]), 4)
            if not pd.isna(row["Close_Location"])
            else None,
            "Prev_Close": round(float(row["Prev_Close"]), 4),
        }
        for n in FORWARD_HORIZONS:
            fwd = row[f"Fwd_Return_{n}d"]
            base[f"Forward_Return_{n}d"] = round(float(fwd), 4) if not pd.isna(fwd) else None

        for level, event_type in stop_levels + tp_levels:
            if event_type == "STOP_SWEEP":
                if not is_stop_sweep(row, level):
                    continue
            else:
                if not is_failed_take_profit(row, level):
                    continue

            evt = dict(base)
            evt["Event_Type"] = event_type
            evt["Level_Pct"] = level
            evt["Level_Category"] = level_category(level, event_type)
            events.append(evt)

    return events, analysis_days


def aggregate_level_stats(
    events_df: pd.DataFrame,
    total_analysis_days: int,
    event_type: str,
    level: float,
    filter_name: str,
    filter_spec: tuple[str, float] | None,
) -> dict | None:
    subset = events_df[
        (events_df["Event_Type"] == event_type) & (events_df["Level_Pct"] == level)
    ]
    if filter_spec is not None:
        field, minimum = filter_spec
        subset = subset[subset[field] >= minimum]

    if subset.empty:
        return None

    count = len(subset)
    rate = round(count / total_analysis_days * 100.0, 6)
    row: dict = {
        "Event_Type": event_type,
        "Level_Pct": level,
        "Level_Category": level_category(level, event_type),
        "Filter": filter_name,
        "Event_Count": count,
        "Sweep_Count": count if event_type == "STOP_SWEEP" else None,
        "Sweep_Rate": rate if event_type == "STOP_SWEEP" else None,
        "Event_Rate": rate,
        "Avg_Volume_Ratio": round(float(subset["Volume_Ratio"].mean()), 4),
        "Avg_DollarVolume_Ratio": round(float(subset["DollarVolume_Ratio"].mean()), 4),
        "Avg_Close_Location": round(float(subset["Close_Location"].mean()), 4),
    }
    for n in FORWARD_HORIZONS:
        col = f"Forward_Return_{n}d"
        vals = subset[col].dropna()
        row[f"Forward_Return_{n}d"] = round(float(vals.mean()), 4) if len(vals) else None
        row[f"Win_Rate_{n}d"] = round(float((vals > 0).mean() * 100.0), 2) if len(vals) else None
    return row


def build_control_comparison(
    events_df: pd.DataFrame,
    total_analysis_days: int,
    event_type: str,
    popular_levels: list[float],
    control_levels: list[float],
) -> list[dict]:
    rows: list[dict] = []
    pop = events_df[
        (events_df["Event_Type"] == event_type)
        & (events_df["Level_Pct"].isin(popular_levels))
    ]
    ctrl = events_df[
        (events_df["Event_Type"] == event_type)
        & (events_df["Level_Pct"].isin(control_levels))
    ]

    pop_count = len(pop)
    ctrl_count = len(ctrl)
    pop_rate = pop_count / total_analysis_days * 100.0
    ctrl_rate = ctrl_count / total_analysis_days * 100.0

    for n in FORWARD_HORIZONS:
        col = f"Forward_Return_{n}d"
        pop_vals = pop[col].dropna()
        ctrl_vals = ctrl[col].dropna()
        pop_avg = float(pop_vals.mean()) if len(pop_vals) else None
        ctrl_avg = float(ctrl_vals.mean()) if len(ctrl_vals) else None
        pop_wr = float((pop_vals > 0).mean() * 100.0) if len(pop_vals) else None
        ctrl_wr = float((ctrl_vals > 0).mean() * 100.0) if len(ctrl_vals) else None
        diff_ret = None
        diff_wr = None
        if pop_avg is not None and ctrl_avg is not None:
            diff_ret = pop_avg - ctrl_avg
        if pop_wr is not None and ctrl_wr is not None:
            diff_wr = pop_wr - ctrl_wr

        rows.append(
            {
                "Event_Type": event_type,
                "Forward_Horizon_Days": n,
                "Popular_Event_Count": pop_count,
                "Control_Event_Count": ctrl_count,
                "Popular_Event_Rate": round(pop_rate, 6),
                "Control_Event_Rate": round(ctrl_rate, 6),
                "Event_Rate_Difference": round(pop_rate - ctrl_rate, 6),
                "Popular_Avg_Forward_Return": round(pop_avg, 4) if pop_avg is not None else None,
                "Control_Avg_Forward_Return": round(ctrl_avg, 4) if ctrl_avg is not None else None,
                "Forward_Return_Difference": round(diff_ret, 4) if diff_ret is not None else None,
                "Popular_Win_Rate": round(pop_wr, 2) if pop_wr is not None else None,
                "Control_Win_Rate": round(ctrl_wr, 2) if ctrl_wr is not None else None,
                "Win_Rate_Difference": round(diff_wr, 2) if diff_wr is not None else None,
            }
        )
    return rows


def format_setup_row(row: pd.Series, horizon: int) -> str:
    ret_col = f"Forward_Return_{horizon}d"
    wr_col = f"Win_Rate_{horizon}d"
    return (
        f"{row['Event_Type']} level={row['Level_Pct']}% filter={row['Filter']} | "
        f"count={int(row['Event_Count'])} | "
        f"{horizon}d avg={row[ret_col]}% win={row[wr_col]}%"
    )


def determine_verdict(
    control_df: pd.DataFrame,
    level_stats_df: pd.DataFrame,
) -> str:
    stop_sweep_edge = False
    failed_tp_edge = False
    round_effect = False

    stop_cmp = control_df[control_df["Event_Type"] == "STOP_SWEEP"]
    tp_cmp = control_df[control_df["Event_Type"] == "FAILED_TAKE_PROFIT"]

    for horizon in [30, 60]:
        row = stop_cmp[stop_cmp["Forward_Horizon_Days"] == horizon]
        if row.empty:
            continue
        r = row.iloc[0]
        if (
            r["Popular_Event_Count"] >= MIN_EDGE_EVENTS
            and r["Control_Event_Count"] >= MIN_EDGE_EVENTS
            and r["Forward_Return_Difference"] is not None
            and r["Win_Rate_Difference"] is not None
            and r["Forward_Return_Difference"] > RETURN_EDGE_THRESHOLD
            and r["Win_Rate_Difference"] > WIN_RATE_EDGE_THRESHOLD
        ):
            stop_sweep_edge = True

        row_tp = tp_cmp[tp_cmp["Forward_Horizon_Days"] == horizon]
        if row_tp.empty:
            continue
        rt = row_tp.iloc[0]
        # Failed TP edge: negative forward continuation (short bias) or positive if betting reversal
        if (
            rt["Popular_Event_Count"] >= MIN_EDGE_EVENTS
            and rt["Control_Event_Count"] >= MIN_EDGE_EVENTS
            and rt["Forward_Return_Difference"] is not None
            and rt["Win_Rate_Difference"] is not None
            and rt["Forward_Return_Difference"] < -RETURN_EDGE_THRESHOLD
            and rt["Win_Rate_Difference"] < -WIN_RATE_EDGE_THRESHOLD
        ):
            failed_tp_edge = True

    for _, r in stop_cmp[stop_cmp["Forward_Horizon_Days"] == 30].iterrows():
        if (
            r["Popular_Event_Count"] >= MIN_EDGE_EVENTS
            and r["Event_Rate_Difference"] is not None
            and abs(r["Event_Rate_Difference"]) > RATE_EDGE_THRESHOLD
        ):
            round_effect = True
            break

    tp30 = tp_cmp[tp_cmp["Forward_Horizon_Days"] == 30]
    if not tp30.empty:
        r = tp30.iloc[0]
        if (
            r["Popular_Event_Count"] >= MIN_EDGE_EVENTS
            and r["Event_Rate_Difference"] is not None
            and abs(r["Event_Rate_Difference"]) > RATE_EDGE_THRESHOLD
        ):
            round_effect = True

    if stop_sweep_edge and failed_tp_edge:
        return "STOP_SWEEP_EDGE_FOUND"
    if stop_sweep_edge:
        return "STOP_SWEEP_EDGE_FOUND"
    if failed_tp_edge:
        return "FAILED_TAKE_PROFIT_EDGE_FOUND"
    if round_effect and not stop_sweep_edge and not failed_tp_edge:
        return "ROUND_LEVEL_EFFECT_FOUND"
    return "NO_CLEAR_EDGE"


def main() -> None:
    print("===== LIQUIDITY SWEEP RESEARCH V1.7 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_EXECUTION")
    print("Observable OHLCV patterns only — no manipulation claims.")
    print()

    universe = load_universe()
    print(f"Universe: {len(universe)} symbols")

    all_events: list[dict] = []
    tickers_loaded = 0
    total_analysis_days = 0
    skipped: list[tuple[str, str]] = []

    for ticker in universe:
        raw = download_history(ticker)
        if raw.empty:
            skipped.append((ticker, "DOWNLOAD_FAILED"))
            continue
        if len(raw) < MIN_HISTORY_BARS + max(FORWARD_HORIZONS):
            skipped.append((ticker, f"INSUFFICIENT_HISTORY_{len(raw)}"))
            continue

        events, days = collect_ticker_events(ticker, raw)
        if days > 0:
            tickers_loaded += 1
            total_analysis_days += days
            all_events.extend(events)

    if not all_events:
        Path(SUMMARY_TXT).write_text("INSUFFICIENT_DATA\n", encoding="utf-8")
        print("No events detected.")
        return

    events_df = pd.DataFrame(all_events)
    events_df.to_csv(EVENTS_CSV, index=False)

    level_rows: list[dict] = []
    for level in POPULAR_STOP_LEVELS:
        for filter_name, filter_spec in VOLUME_FILTERS:
            row = aggregate_level_stats(
                events_df, total_analysis_days, "STOP_SWEEP", level, filter_name, filter_spec
            )
            if row:
                level_rows.append(row)

    for level in POPULAR_TP_LEVELS:
        row = aggregate_level_stats(
            events_df, total_analysis_days, "FAILED_TAKE_PROFIT", level, "NONE", None
        )
        if row:
            level_rows.append(row)

    level_stats_df = pd.DataFrame(level_rows)
    level_stats_df.to_csv(LEVEL_STATS_CSV, index=False)

    control_rows = build_control_comparison(
        events_df,
        total_analysis_days,
        "STOP_SWEEP",
        POPULAR_STOP_LEVELS,
        CONTROL_STOP_LEVELS,
    )
    control_rows.extend(
        build_control_comparison(
            events_df,
            total_analysis_days,
            "FAILED_TAKE_PROFIT",
            POPULAR_TP_LEVELS,
            CONTROL_TP_LEVELS,
        )
    )
    control_df = pd.DataFrame(control_rows)
    control_df.to_csv(CONTROL_CSV, index=False)

    verdict = determine_verdict(control_df, level_stats_df)

    stop_stats = level_stats_df[
        (level_stats_df["Event_Type"] == "STOP_SWEEP") & (level_stats_df["Filter"] == "NONE")
    ]
    top30_stop = stop_stats.sort_values("Forward_Return_30d", ascending=False).head(20)
    top60_stop = stop_stats.sort_values("Forward_Return_60d", ascending=False).head(20)

    tp_stats = level_stats_df[level_stats_df["Event_Type"] == "FAILED_TAKE_PROFIT"]
    top_neg30_tp = tp_stats.sort_values("Forward_Return_30d", ascending=True).head(20)

    filtered_stop = level_stats_df[
        (level_stats_df["Event_Type"] == "STOP_SWEEP") & (level_stats_df["Filter"] != "NONE")
    ]
    best_filtered = None
    if not filtered_stop.empty and filtered_stop["Forward_Return_30d"].notna().any():
        best_filtered = filtered_stop.loc[filtered_stop["Forward_Return_30d"].idxmax()]

    lines = [
        "===== LIQUIDITY SWEEP RESEARCH V1.7 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "Observable OHLCV pattern statistics — not evidence of manipulation.",
        "",
        f"Universe size: {len(universe)}",
        f"Tickers loaded: {tickers_loaded}",
        f"Tickers skipped: {len(skipped)}",
        f"Total trading days analyzed: {total_analysis_days}",
        f"Total events recorded: {len(events_df)}",
        f"History: {HISTORY_PERIOD}",
        "",
        "--- Top 20 stop-sweep setups by 30d forward return (popular levels, no filter) ---",
    ]
    for _, row in top30_stop.iterrows():
        lines.append("  " + format_setup_row(row, 30))
    lines.append("")

    lines.append("--- Top 20 stop-sweep setups by 60d forward return (popular levels, no filter) ---")
    for _, row in top60_stop.iterrows():
        lines.append("  " + format_setup_row(row, 60))
    lines.append("")

    lines.append("--- Top 20 failed-take-profit setups by negative 30d forward return ---")
    for _, row in top_neg30_tp.iterrows():
        lines.append("  " + format_setup_row(row, 30))
    lines.append("")

    lines.append("--- Popular vs control comparison (30d and 60d highlights) ---")
    for etype in ["STOP_SWEEP", "FAILED_TAKE_PROFIT"]:
        lines.append(f"  {etype}:")
        sub = control_df[
            (control_df["Event_Type"] == etype)
            & (control_df["Forward_Horizon_Days"].isin([30, 60]))
        ]
        for _, r in sub.iterrows():
            lines.append(
                f"    {int(r['Forward_Horizon_Days'])}d | "
                f"pop_n={int(r['Popular_Event_Count'])} ctrl_n={int(r['Control_Event_Count'])} | "
                f"pop_rate={r['Popular_Event_Rate']:.4f}% ctrl_rate={r['Control_Event_Rate']:.4f}% | "
                f"ret_diff={r['Forward_Return_Difference']}% wr_diff={r['Win_Rate_Difference']}%"
            )
    lines.append("")

    lines.append("--- Best volume/dollar-volume filtered stop-sweep setup (30d avg) ---")
    if best_filtered is not None:
        lines.append("  " + format_setup_row(best_filtered, 30))
    else:
        lines.append("  None")
    lines.append("")

    lines.append(
        "Edge criteria: event count >= 100, return diff > 0.20%, win-rate diff > 2% "
        "(30d or 60d); round-level effect uses event-rate diff > 0.05%."
    )
    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {EVENTS_CSV}")
    print(f"Saved: {LEVEL_STATS_CSV}")
    print(f"Saved: {CONTROL_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
