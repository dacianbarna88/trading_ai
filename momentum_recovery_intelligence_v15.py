"""
Momentum Recovery Intelligence V1.5 — Drawdown Recovery Pattern Research

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from momentum_continuation_research_v11 import (
    ENTRY_MODE,
    HISTORY_PERIOD,
    MIN_HISTORY_BARS,
    download_history,
    enrich,
    filter_passes,
    trade_max_drawdown,
)

warnings.filterwarnings("ignore", category=FutureWarning)

UNIVERSE_FILE = "us_expanded_universe.txt"
PATHS_CSV = "momentum_v15_trade_recovery_paths.csv"
MATRIX_CSV = "momentum_v15_recovery_matrix.csv"
SUMMARY_TXT = "momentum_v15_summary.txt"

THRESHOLD = 5.0
HOLD_DAYS = 60
FILTER_MODE = "NO_FILTER"

DRAWDOWN_LEVELS = [-3, -5, -7, -10, -12, -15, -20]

RECOVERY_TRIGGERS = [
    "FIRST_GREEN_DAY",
    "CLOSE_ABOVE_PREV_CLOSE",
    "TWO_GREEN_DAYS",
    "CLOSE_ABOVE_3DAY_HIGH",
    "CLOSE_ABOVE_5DAY_HIGH",
    "RSI_RECOVERY_40",
    "RSI_RECOVERY_50",
    "VOLUME_GREEN_RECOVERY",
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


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def aggregate_metrics(returns: np.ndarray, drawdowns: np.ndarray) -> dict:
    winners = returns[returns > 0]
    losers = returns[returns < 0]
    return {
        "Trades": len(returns),
        "Win_Rate": round(float((returns > 0).mean() * 100.0), 2),
        "Avg_Return": round(float(returns.mean()), 4),
        "Median_Return": round(float(np.median(returns)), 4),
        "Total_Return": round(float(returns.sum()), 4),
        "Best_Trade": round(float(returns.max()), 4),
        "Worst_Trade": round(float(returns.min()), 4),
        "Profit_Factor": round(profit_factor(returns), 4),
        "Avg_Winner": round(float(winners.mean()), 4) if len(winners) else 0.0,
        "Avg_Loser": round(float(losers.mean()), 4) if len(losers) else 0.0,
        "Return_Stdev": round(float(returns.std(ddof=0)), 4) if len(returns) > 1 else 0.0,
        "Approx_Max_Drawdown": round(float(drawdowns.mean()), 4),
    }


def path_drawdown(lows: np.ndarray, highs: np.ndarray, entry: float) -> float:
    peak = entry
    max_dd = 0.0
    for lo, hi in zip(lows, highs, strict=True):
        if hi > peak:
            peak = hi
        dd = ((lo - peak) / peak) * 100.0
        if dd < max_dd:
            max_dd = dd
    return float(max_dd)


def find_drawdown_touch_day(
    lows: np.ndarray,
    entry_idx: int,
    exit_idx: int,
    entry_price: float,
    dd_pct: float,
) -> int | None:
    dd_price = entry_price * (1 + dd_pct / 100.0)
    for d in range(entry_idx, exit_idx + 1):
        if lows[d] <= dd_price:
            return d
    return None


def trigger_fires(
    trigger: str,
    d: int,
    touch_day: int,
    opens: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    avg_vols: np.ndarray,
    rsi: np.ndarray,
) -> bool:
    if d <= touch_day:
        return False

    o, h, c = opens[d], highs[d], closes[d]
    if pd.isna(o) or pd.isna(c):
        return False

    if trigger == "FIRST_GREEN_DAY":
        return c > o

    if trigger == "CLOSE_ABOVE_PREV_CLOSE":
        prev_c = closes[d - 1]
        return not pd.isna(prev_c) and c > prev_c

    if trigger == "TWO_GREEN_DAYS":
        if d - 1 <= touch_day:
            return False
        o1, c1 = opens[d - 1], closes[d - 1]
        if pd.isna(o1) or pd.isna(c1):
            return False
        return c > o and c1 > o1

    if trigger == "CLOSE_ABOVE_3DAY_HIGH":
        if d - 3 < 0:
            return False
        prior_high = np.nanmax(highs[d - 3:d])
        return not pd.isna(prior_high) and c > prior_high

    if trigger == "CLOSE_ABOVE_5DAY_HIGH":
        if d - 5 < 0:
            return False
        prior_high = np.nanmax(highs[d - 5:d])
        return not pd.isna(prior_high) and c > prior_high

    if trigger == "RSI_RECOVERY_40":
        r_now, r_prev = rsi[d], rsi[d - 1]
        return not pd.isna(r_now) and not pd.isna(r_prev) and r_prev < 40.0 and r_now >= 40.0

    if trigger == "RSI_RECOVERY_50":
        r_now, r_prev = rsi[d], rsi[d - 1]
        return not pd.isna(r_now) and not pd.isna(r_prev) and r_prev < 50.0 and r_now >= 50.0

    if trigger == "VOLUME_GREEN_RECOVERY":
        vol, avg_vol = volumes[d], avg_vols[d]
        return (
            c > o
            and not pd.isna(vol)
            and not pd.isna(avg_vol)
            and vol > avg_vol
        )

    return False


def find_recovery_trigger_day(
    trigger: str,
    touch_day: int,
    exit_idx: int,
    arrays: dict[str, np.ndarray],
) -> int | None:
    """First trigger day t where re-entry at t+1 open is still on/before exit_idx."""
    opens = arrays["open"]
    highs = arrays["high"]
    closes = arrays["close"]
    volumes = arrays["volume"]
    avg_vols = arrays["avg20vol"]
    rsi = arrays["rsi"]

    for d in range(touch_day + 1, exit_idx):
        if trigger_fires(
            trigger, d, touch_day, opens, highs, closes, volumes, avg_vols, rsi
        ):
            return d
    return None


def simulate_recovery(
    trade: dict,
    arrays: dict[str, np.ndarray],
    dd_pct: float,
    trigger: str,
) -> dict:
    entry_idx = trade["_entry_idx"]
    exit_idx = trade["_exit_idx"]
    entry = trade["Entry_Price"]
    exit_close = trade["Baseline_Exit_Price"]
    baseline_ret = trade["Baseline_Return"]

    lows = arrays["low"]
    highs = arrays["high"]
    opens = arrays["open"]

    touch_day = find_drawdown_touch_day(
        lows, entry_idx, exit_idx, entry, dd_pct
    )

    if touch_day is None:
        return {
            "Final_Return": baseline_ret,
            "Stopped": False,
            "Recovered": False,
            "Approx_DD": trade["_baseline_dd"],
        }

    dd_price = entry * (1 + dd_pct / 100.0)
    stop_return = ((dd_price - entry) / entry) * 100.0
    trigger_day = find_recovery_trigger_day(trigger, touch_day, exit_idx, arrays)

    if trigger_day is None:
        return {
            "Final_Return": round(stop_return, 4),
            "Stopped": True,
            "Recovered": False,
            "Approx_DD": round(dd_pct, 4),
        }

    reentry_idx = trigger_day + 1
    reentry_open = float(opens[reentry_idx])
    if pd.isna(reentry_open) or reentry_open <= 0:
        return {
            "Final_Return": round(stop_return, 4),
            "Stopped": True,
            "Recovered": False,
            "Approx_DD": round(dd_pct, 4),
        }

    recovery_return = ((exit_close - reentry_open) / reentry_open) * 100.0
    final_return = stop_return + recovery_return

    seg1_lows = lows[entry_idx:touch_day + 1]
    seg1_highs = highs[entry_idx:touch_day + 1]
    dd1 = path_drawdown(seg1_lows, seg1_highs, entry)
    seg2_lows = lows[reentry_idx:exit_idx + 1]
    seg2_highs = highs[reentry_idx:exit_idx + 1]
    dd2 = path_drawdown(seg2_lows, seg2_highs, reentry_open)
    approx_dd = min(dd1, dd2)

    return {
        "Final_Return": round(final_return, 4),
        "Stopped": True,
        "Recovered": True,
        "Approx_DD": round(approx_dd, 4),
    }


def collect_baseline_trades(df: pd.DataFrame) -> list[dict]:
    if len(df) < MIN_HISTORY_BARS + HOLD_DAYS:
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    ticker = df["Ticker"].iloc[0]
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

        baseline_return = ((exit_price - entry_price) / entry_price) * 100.0

        mfe = -np.inf
        mae = np.inf
        for d in range(entry_idx, exit_idx + 1):
            lo = float(low.iloc[d])
            hi = float(high.iloc[d])
            fav = ((hi - entry_price) / entry_price) * 100.0
            adv = ((lo - entry_price) / entry_price) * 100.0
            if fav > mfe:
                mfe = fav
            if adv < mae:
                mae = adv

        trades.append(
            {
                "Ticker": ticker,
                "Signal_Date": df.index[i].strftime("%Y-%m-%d"),
                "Entry_Date": df.index[entry_idx].strftime("%Y-%m-%d"),
                "Entry_Price": round(entry_price, 4),
                "Baseline_Exit_Date": df.index[exit_idx].strftime("%Y-%m-%d"),
                "Baseline_Exit_Price": round(exit_price, 4),
                "Baseline_Return": round(baseline_return, 4),
                "MFE": round(float(mfe), 4),
                "MAE": round(float(mae), 4),
                "_entry_idx": entry_idx,
                "_exit_idx": exit_idx,
                "_baseline_dd": trade_max_drawdown(close, entry_idx, exit_idx, entry_price),
            }
        )
        last_exit_idx = exit_idx

    return trades


def build_recovery_path_row(trade: dict, arrays: dict[str, np.ndarray]) -> dict:
    row = {
        "Ticker": trade["Ticker"],
        "Signal_Date": trade["Signal_Date"],
        "Entry_Date": trade["Entry_Date"],
        "Entry_Price": trade["Entry_Price"],
        "Baseline_Exit_Date": trade["Baseline_Exit_Date"],
        "Baseline_Exit_Price": trade["Baseline_Exit_Price"],
        "Baseline_Return": trade["Baseline_Return"],
        "MFE": trade.get("MFE"),
        "MAE": trade.get("MAE"),
    }
    entry_idx = trade["_entry_idx"]
    exit_idx = trade["_exit_idx"]
    entry = trade["Entry_Price"]
    lows = arrays["low"]

    for dd_pct in DRAWDOWN_LEVELS:
        touch_day = find_drawdown_touch_day(
            lows, entry_idx, exit_idx, entry, dd_pct
        )
        row[f"Did_Touch_{dd_pct}%"] = touch_day is not None
        if touch_day is not None:
            row[f"Touch_Day_{dd_pct}%"] = touch_day - entry_idx
        else:
            row[f"Touch_Day_{dd_pct}%"] = -1

        for trigger in RECOVERY_TRIGGERS:
            col = f"Trigger_Day_{dd_pct}%_{trigger}"
            if touch_day is None:
                row[col] = -1
            else:
                tday = find_recovery_trigger_day(trigger, touch_day, exit_idx, arrays)
                row[col] = (tday - entry_idx) if tday is not None else -1

    return row


def objective_score(row: pd.Series, baseline: dict) -> float:
    instability = abs(row["Avg_Return"] - row["Median_Return"])
    score = (
        row["Avg_Return"] * 2.0
        + row["Median_Return"] * 1.5
        + row["Profit_Factor"] * 4.0
        - abs(row["Worst_Trade"]) * 0.35
        - abs(row["Approx_Max_Drawdown"]) * 0.45
        + min(row["Trades"], 300) / 25.0
        - instability * 0.5
        + row["Improvement_vs_Baseline_Worst"] * 0.25
    )
    if row["Profit_Factor"] < baseline["Profit_Factor"]:
        score -= 8.0
    if row["Total_Return"] < baseline["Total_Return"]:
        score -= 5.0
    if row["Trades"] < 30:
        score *= 0.65
    if row["Recovery_Reentries"] < 5:
        score -= 3.0
    if row["Worst_Trade"] < baseline["Worst_Trade"]:
        score -= 4.0
    return round(score, 4)


def determine_verdict(
    matrix: pd.DataFrame,
    baseline: dict,
    conservative: pd.Series | None,
    quad_best: pd.Series | None,
) -> str:
    if matrix.empty:
        return "NO_CLEAR_ADVANTAGE"

    if quad_best is not None:
        return "RECOVERY_IMPROVES_EDGE"

    if conservative is not None:
        if (
            conservative["Avg_Return"] > baseline["Avg_Return"]
            and conservative["Total_Return"] >= baseline["Total_Return"]
        ):
            return "RECOVERY_IMPROVES_EDGE"
        return "RECOVERY_REDUCES_RISK_ONLY"

    hurts = matrix[
        (matrix["Avg_Return"] < baseline["Avg_Return"])
        & (matrix["Total_Return"] < baseline["Total_Return"])
    ]
    top = matrix.sort_values("Objective_Score", ascending=False).head(20)
    if len(top) >= 10 and len(hurts) > len(top) * 0.6:
        return "RECOVERY_HURTS_EDGE"

    return "NO_CLEAR_ADVANTAGE"


def format_system(row: pd.Series) -> str:
    return (
        f"DD={row['Drawdown_Level']}% Trigger={row['Recovery_Trigger']} | "
        f"trades={int(row['Trades'])} stopped={int(row['Stopped_Trades'])} "
        f"recovery={int(row['Recovery_Reentries'])} | "
        f"avg={row['Avg_Return']}% total={row['Total_Return']}% | "
        f"worst={row['Worst_Trade']}% PF={row['Profit_Factor']} | "
        f"score={row['Objective_Score']}"
    )


def main() -> None:
    print("===== MOMENTUM RECOVERY INTELLIGENCE V1.5 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_EXECUTION")
    print()

    universe = load_universe()
    print(f"Universe: {len(universe)} symbols")

    all_trades: list[dict] = []
    ticker_arrays: dict[str, dict[str, np.ndarray]] = {}
    skipped: list[tuple[str, str]] = []

    for ticker in universe:
        raw = download_history(ticker)
        if raw.empty:
            skipped.append((ticker, "DOWNLOAD_FAILED"))
            continue
        if len(raw) < MIN_HISTORY_BARS + HOLD_DAYS:
            skipped.append((ticker, f"INSUFFICIENT_HISTORY_{len(raw)}"))
            continue

        df = enrich(raw)
        trades = collect_baseline_trades(df)
        if trades:
            all_trades.extend(trades)
            ticker_arrays[ticker] = {
                "open": df["Open"].astype(float).values,
                "high": df["High"].astype(float).values,
                "low": df["Low"].astype(float).values,
                "close": df["Close"].astype(float).values,
                "volume": df["Volume"].astype(float).values,
                "avg20vol": df["Avg20Volume"].astype(float).values,
                "rsi": df["RSI"].astype(float).values,
            }

    if not all_trades:
        Path(SUMMARY_TXT).write_text("INSUFFICIENT_DATA\n", encoding="utf-8")
        print("No baseline trades collected.")
        return

    path_rows = [
        build_recovery_path_row(t, ticker_arrays[t["Ticker"]]) for t in all_trades
    ]
    pd.DataFrame(path_rows).to_csv(PATHS_CSV, index=False)

    baseline_returns = np.array([t["Baseline_Return"] for t in all_trades], dtype=float)
    baseline_dds = np.array([t["_baseline_dd"] for t in all_trades], dtype=float)
    baseline = aggregate_metrics(baseline_returns, baseline_dds)

    matrix_rows: list[dict] = []
    combos = [(dd, trig) for dd in DRAWDOWN_LEVELS for trig in RECOVERY_TRIGGERS]

    for dd_pct, trigger in combos:
        finals: list[float] = []
        dds: list[float] = []
        stopped_count = 0
        recovery_count = 0

        for trade in all_trades:
            arrays = ticker_arrays[trade["Ticker"]]
            sim = simulate_recovery(trade, arrays, dd_pct, trigger)
            finals.append(sim["Final_Return"])
            dds.append(sim["Approx_DD"])
            if sim["Stopped"]:
                stopped_count += 1
            if sim["Recovered"]:
                recovery_count += 1

        rets = np.array(finals, dtype=float)
        dd_arr = np.array(dds, dtype=float)
        agg = aggregate_metrics(rets, dd_arr)
        row = {
            "Drawdown_Level": dd_pct,
            "Recovery_Trigger": trigger,
            "Stopped_Trades": stopped_count,
            "Recovery_Reentries": recovery_count,
            "Recovery_Rate": round(recovery_count / len(rets) * 100.0, 2),
            "Improvement_vs_Baseline_Avg": round(
                agg["Avg_Return"] - baseline["Avg_Return"], 4
            ),
            "Improvement_vs_Baseline_Total": round(
                agg["Total_Return"] - baseline["Total_Return"], 4
            ),
            "Improvement_vs_Baseline_Worst": round(
                agg["Worst_Trade"] - baseline["Worst_Trade"], 4
            ),
            **agg,
        }
        matrix_rows.append(row)

    matrix = pd.DataFrame(matrix_rows)
    matrix["Objective_Score"] = matrix.apply(
        lambda r: objective_score(r, baseline), axis=1
    )
    matrix.to_csv(MATRIX_CSV, index=False)

    improves_all = matrix[
        (matrix["Avg_Return"] > baseline["Avg_Return"])
        & (matrix["Total_Return"] > baseline["Total_Return"])
        & (matrix["Worst_Trade"] > baseline["Worst_Trade"])
        & (matrix["Profit_Factor"] > baseline["Profit_Factor"])
    ].sort_values("Objective_Score", ascending=False)

    conservative = matrix[
        (matrix["Worst_Trade"] > baseline["Worst_Trade"])
        & (matrix["Profit_Factor"] >= baseline["Profit_Factor"])
        & (matrix["Avg_Return"] >= baseline["Avg_Return"] * 0.95)
    ].sort_values("Objective_Score", ascending=False)

    conservative_best = conservative.iloc[0] if not conservative.empty else None
    quad_best = improves_all.iloc[0] if not improves_all.empty else None
    verdict = determine_verdict(matrix, baseline, conservative_best, quad_best)

    lines = [
        "===== MOMENTUM RECOVERY INTELLIGENCE V1.5 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "",
        f"Universe size: {len(universe)}",
        f"Tickers with baseline trades: {len(ticker_arrays)}",
        f"Tickers skipped: {len(skipped)}",
        f"Total baseline trades: {len(all_trades)}",
        f"Drawdown/recovery systems tested: {len(combos)}",
        f"History: {HISTORY_PERIOD} | Threshold>={THRESHOLD}% | Hold={HOLD_DAYS}d",
        f"Entry: {ENTRY_MODE}",
        "",
        "--- Baseline (Hold 60, NO_FILTER) ---",
        f"Trades: {baseline['Trades']}",
        f"Win_Rate: {baseline['Win_Rate']}%",
        f"Avg_Return: {baseline['Avg_Return']}%",
        f"Median_Return: {baseline['Median_Return']}%",
        f"Total_Return: {baseline['Total_Return']}%",
        f"Best_Trade: {baseline['Best_Trade']}%",
        f"Worst_Trade: {baseline['Worst_Trade']}%",
        f"Profit_Factor: {baseline['Profit_Factor']}",
        f"Approx_Max_Drawdown: {baseline['Approx_Max_Drawdown']}%",
        "",
        "--- Top 20 recovery systems by Objective_Score ---",
    ]
    for _, row in matrix.sort_values("Objective_Score", ascending=False).head(20).iterrows():
        lines.append("  " + format_system(row))
    lines.append("")

    lines.append("--- Top 20 by Total_Return ---")
    for _, row in matrix.sort_values("Total_Return", ascending=False).head(20).iterrows():
        lines.append("  " + format_system(row))
    lines.append("")

    lines.append("--- Top 20 by Worst_Trade improvement ---")
    for _, row in matrix.sort_values(
        "Improvement_vs_Baseline_Worst", ascending=False
    ).head(20).iterrows():
        lines.append("  " + format_system(row))
    lines.append("")

    lines.append("--- Best system improving Avg, Total, Worst, Profit_Factor ---")
    if quad_best is None:
        lines.append("  None")
    else:
        lines.append("  " + format_system(quad_best))
    lines.append("")

    lines.append("--- Best conservative system ---")
    if conservative_best is None:
        lines.append(
            "  None met Worst_Trade + PF + Avg_Return >= 95% baseline"
        )
    else:
        lines.append("  " + format_system(conservative_best))
    lines.append("")

    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {PATHS_CSV}")
    print(f"Saved: {MATRIX_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
