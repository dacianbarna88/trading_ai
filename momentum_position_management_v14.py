"""
Momentum Position Management Research V1.4 — Stop + Re-entry Optimization Audit

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
PATHS_CSV = "momentum_v14_trade_paths.csv"
MATRIX_CSV = "momentum_v14_stop_reentry_matrix.csv"
SUMMARY_TXT = "momentum_v14_summary.txt"

THRESHOLD = 5.0
HOLD_DAYS = 60
FILTER_MODE = "NO_FILTER"
REGION = "US"

STOP_LEVELS = [-2, -3, -4, -5, -6, -7, -8, -9, -10, -12, -15, -20]
REENTRY_LEVELS = [-3, -4, -5, -6, -7, -8, -9, -10, -12, -15, -20, -25]
TOUCH_LEVELS = [-3, -5, -7, -10, -15, -20]


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
        day_mfe = 0
        day_mae = 0
        touch_flags = {lvl: False for lvl in TOUCH_LEVELS}

        for offset, d in enumerate(range(entry_idx, exit_idx + 1), start=0):
            lo = float(low.iloc[d])
            hi = float(high.iloc[d])
            fav = ((hi - entry_price) / entry_price) * 100.0
            adv = ((lo - entry_price) / entry_price) * 100.0
            if fav > mfe:
                mfe = fav
                day_mfe = offset
            if adv < mae:
                mae = adv
                day_mae = offset
            for lvl in TOUCH_LEVELS:
                touch_price = entry_price * (1 + lvl / 100.0)
                if lo <= touch_price:
                    touch_flags[lvl] = True

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
                "Day_Of_MFE": day_mfe,
                "Day_Of_MAE": day_mae,
                "Did_Touch_-3%": touch_flags[-3],
                "Did_Touch_-5%": touch_flags[-5],
                "Did_Touch_-7%": touch_flags[-7],
                "Did_Touch_-10%": touch_flags[-10],
                "Did_Touch_-15%": touch_flags[-15],
                "Did_Touch_-20%": touch_flags[-20],
                "_entry_idx": entry_idx,
                "_exit_idx": exit_idx,
                "_baseline_dd": trade_max_drawdown(close, entry_idx, exit_idx, entry_price),
            }
        )
        last_exit_idx = exit_idx

    return trades


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


def simulate_stop_reentry(
    trade: dict,
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
    stop_pct: float,
    reentry_pct: float,
) -> dict:
    entry_idx = trade["_entry_idx"]
    exit_idx = trade["_exit_idx"]
    entry = trade["Entry_Price"]
    exit_close = trade["Baseline_Exit_Price"]
    baseline_ret = trade["Baseline_Return"]

    stop_price = entry * (1 + stop_pct / 100.0)
    reentry_price = entry * (1 + reentry_pct / 100.0)

    stopped = False
    reentered = False
    stop_day = -1
    stop_return = 0.0
    final_return = baseline_ret

    for d in range(entry_idx, exit_idx + 1):
        lo = lows[d]

        if not stopped:
            if lo <= stop_price:
                stopped = True
                stop_day = d
                stop_return = ((stop_price - entry) / entry) * 100.0
                final_return = stop_return
            continue

        if stopped and not reentered and d > stop_day:
            if lo <= reentry_price:
                reentered = True
                reentry_ret = ((exit_close - reentry_price) / reentry_price) * 100.0
                final_return = stop_return + reentry_ret
                break

    if stopped and reentered:
        reentry_day_offset = None
        for d in range(stop_day + 1, exit_idx + 1):
            if lows[d] <= reentry_price:
                reentry_day_offset = d - entry_idx
                break
        if reentry_day_offset is not None:
            seg_lows = lows[entry_idx:entry_idx + reentry_day_offset + 1]
            seg_highs = highs[entry_idx:entry_idx + reentry_day_offset + 1]
            dd1 = path_drawdown(seg_lows, seg_highs, entry)
            seg2_lows = lows[reentry_day_offset + entry_idx:exit_idx + 1]
            seg2_highs = highs[reentry_day_offset + entry_idx:exit_idx + 1]
            dd2 = path_drawdown(seg2_lows, seg2_highs, reentry_price)
            approx_dd = min(dd1, dd2)
        else:
            approx_dd = trade["_baseline_dd"]
    elif stopped:
        approx_dd = stop_pct
    else:
        approx_dd = trade["_baseline_dd"]

    return {
        "Final_Return": round(final_return, 4),
        "Stopped": stopped,
        "Reentered": reentered,
        "Approx_DD": round(approx_dd, 4),
    }


def valid_stop_reentry_pairs() -> list[tuple[float, float]]:
    pairs = []
    for stop in STOP_LEVELS:
        for reentry in REENTRY_LEVELS:
            if reentry < stop:
                pairs.append((stop, reentry))
    return pairs


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
    )
    if row["Profit_Factor"] < baseline["Profit_Factor"]:
        score -= 8.0
    if row["Total_Return"] < baseline["Total_Return"]:
        score -= 5.0
    if row["Trades"] < 30:
        score *= 0.65
    if row["Reentered_Trades"] < 5:
        score -= 3.0
    if row["Worst_Trade"] < baseline["Worst_Trade"]:
        score -= 4.0
    return round(score, 4)


def mae_distribution(lines: list[str], label: str, maes: np.ndarray) -> None:
    lines.append(f"--- MAE distribution: {label} (n={len(maes)}) ---")
    if len(maes) == 0:
        lines.append("  No trades")
        lines.append("")
        return
    lines.append(f"  Mean MAE: {round(float(maes.mean()), 4)}%")
    lines.append(f"  Median MAE: {round(float(np.median(maes)), 4)}%")
    lines.append(f"  P25: {round(float(np.percentile(maes, 25)), 4)}%")
    lines.append(f"  P75: {round(float(np.percentile(maes, 75)), 4)}%")
    lines.append(f"  Min MAE: {round(float(maes.min()), 4)}%")
    lines.append("")


def determine_verdict(
    matrix: pd.DataFrame,
    baseline: dict,
    conservative: pd.Series | None,
) -> str:
    if matrix.empty:
        return "NO_CLEAR_ADVANTAGE"

    improves_both = matrix[
        (matrix["Avg_Return"] > baseline["Avg_Return"])
        & (matrix["Worst_Trade"] > baseline["Worst_Trade"])
    ]
    hurts = matrix[
        (matrix["Avg_Return"] < baseline["Avg_Return"])
        & (matrix["Total_Return"] < baseline["Total_Return"])
    ]

    if conservative is not None:
        if (
            conservative["Avg_Return"] > baseline["Avg_Return"]
            and conservative["Worst_Trade"] > baseline["Worst_Trade"]
            and conservative["Profit_Factor"] >= baseline["Profit_Factor"]
            and conservative["Total_Return"] >= baseline["Total_Return"]
        ):
            return "STOP_REENTRY_IMPROVES_EDGE"

    top = matrix.sort_values("Objective_Score", ascending=False).head(20)
    if len(top) >= 10 and len(hurts) > len(top) * 0.6:
        return "STOP_REENTRY_HURTS_EDGE"

    risk_only = matrix[
        (matrix["Worst_Trade"] > baseline["Worst_Trade"] + 1.0)
        & (
            (matrix["Avg_Return"] < baseline["Avg_Return"])
            | (matrix["Total_Return"] < baseline["Total_Return"])
        )
    ]
    if not risk_only.empty and conservative is None:
        return "STOP_REENTRY_REDUCES_RISK_ONLY"

    if conservative is not None:
        if (
            conservative["Worst_Trade"] > baseline["Worst_Trade"]
            and (
                conservative["Avg_Return"] < baseline["Avg_Return"]
                or conservative["Total_Return"] < baseline["Total_Return"]
            )
        ):
            return "STOP_REENTRY_REDUCES_RISK_ONLY"

    return "NO_CLEAR_ADVANTAGE"


def format_combo(row: pd.Series) -> str:
    return (
        f"Stop={row['Stop_Level']}% Reentry={row['Reentry_Level']}% | "
        f"trades={int(row['Trades'])} stopped={int(row['Stopped_Trades'])} "
        f"reentered={int(row['Reentered_Trades'])} | "
        f"avg={row['Avg_Return']}% total={row['Total_Return']}% | "
        f"worst={row['Worst_Trade']}% PF={row['Profit_Factor']} | "
        f"score={row['Objective_Score']}"
    )


def main() -> None:
    print("===== MOMENTUM POSITION MANAGEMENT V1.4 =====")
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
                "low": df["Low"].astype(float).values,
                "high": df["High"].astype(float).values,
                "close": df["Close"].astype(float).values,
            }

    if not all_trades:
        Path(SUMMARY_TXT).write_text("INSUFFICIENT_DATA\n", encoding="utf-8")
        print("No baseline trades collected.")
        return

    path_export = pd.DataFrame(all_trades).drop(
        columns=["_entry_idx", "_exit_idx", "_baseline_dd"]
    )
    path_export.to_csv(PATHS_CSV, index=False)

    baseline_returns = np.array([t["Baseline_Return"] for t in all_trades], dtype=float)
    baseline_dds = np.array([t["_baseline_dd"] for t in all_trades], dtype=float)
    baseline = aggregate_metrics(baseline_returns, baseline_dds)

    matrix_rows: list[dict] = []
    pairs = valid_stop_reentry_pairs()

    for stop_pct, reentry_pct in pairs:
        finals: list[float] = []
        dds: list[float] = []
        stopped_count = 0
        reentered_count = 0

        for trade in all_trades:
            arrays = ticker_arrays[trade["Ticker"]]
            sim = simulate_stop_reentry(
                trade,
                arrays["low"],
                arrays["high"],
                arrays["close"],
                stop_pct,
                reentry_pct,
            )
            finals.append(sim["Final_Return"])
            dds.append(sim["Approx_DD"])
            if sim["Stopped"]:
                stopped_count += 1
            if sim["Reentered"]:
                reentered_count += 1

        rets = np.array(finals, dtype=float)
        dd_arr = np.array(dds, dtype=float)
        agg = aggregate_metrics(rets, dd_arr)
        row = {
            "Stop_Level": stop_pct,
            "Reentry_Level": reentry_pct,
            "Stopped_Trades": stopped_count,
            "Reentered_Trades": reentered_count,
            "Stop_Rate": round(stopped_count / len(rets) * 100.0, 2),
            "Reentry_Rate": round(reentered_count / len(rets) * 100.0, 2),
            "Improvement_vs_Baseline_Avg": round(
                agg["Avg_Return"] - baseline["Avg_Return"], 4
            ),
            "Improvement_vs_Baseline_Total": round(
                agg["Total_Return"] - baseline["Total_Return"], 4
            ),
            **agg,
        }
        matrix_rows.append(row)

    matrix = pd.DataFrame(matrix_rows)
    matrix["Objective_Score"] = matrix.apply(
        lambda r: objective_score(r, baseline), axis=1
    )
    matrix.to_csv(MATRIX_CSV, index=False)

    maes = np.array([t["MAE"] for t in all_trades], dtype=float)
    win_maes = np.array(
        [t["MAE"] for t in all_trades if t["Baseline_Return"] > 0], dtype=float
    )
    lose_maes = np.array(
        [t["MAE"] for t in all_trades if t["Baseline_Return"] <= 0], dtype=float
    )

    improves_both = matrix[
        (matrix["Avg_Return"] > baseline["Avg_Return"])
        & (matrix["Worst_Trade"] > baseline["Worst_Trade"])
    ].sort_values("Objective_Score", ascending=False)

    conservative = matrix[
        (matrix["Worst_Trade"] > baseline["Worst_Trade"])
        & (matrix["Profit_Factor"] >= baseline["Profit_Factor"])
        & (matrix["Avg_Return"] >= baseline["Avg_Return"])
    ].sort_values("Objective_Score", ascending=False)

    conservative_best = conservative.iloc[0] if not conservative.empty else None
    verdict = determine_verdict(matrix, baseline, conservative_best)

    lines = [
        "===== MOMENTUM POSITION MANAGEMENT V1.4 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "",
        f"Universe size: {len(universe)}",
        f"Tickers with baseline trades: {len(ticker_arrays)}",
        f"Tickers skipped: {len(skipped)}",
        f"Total baseline trades: {len(all_trades)}",
        f"Stop/re-entry pairs tested: {len(pairs)}",
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
        f"Avg_Winner: {baseline['Avg_Winner']}%",
        f"Avg_Loser: {baseline['Avg_Loser']}%",
        f"Return_Stdev: {baseline['Return_Stdev']}%",
        f"Approx_Max_Drawdown: {baseline['Approx_Max_Drawdown']}%",
        "",
    ]

    mae_distribution(lines, "all trades", maes)
    mae_distribution(lines, "winning trades only", win_maes)
    mae_distribution(lines, "losing trades only", lose_maes)

    lines.append("--- Top 20 by Objective_Score ---")
    for _, row in matrix.sort_values("Objective_Score", ascending=False).head(20).iterrows():
        lines.append("  " + format_combo(row))
    lines.append("")

    lines.append("--- Top 20 by Total_Return ---")
    for _, row in matrix.sort_values("Total_Return", ascending=False).head(20).iterrows():
        lines.append("  " + format_combo(row))
    lines.append("")

    lines.append("--- Top 20 by lowest Worst_Trade (least negative) ---")
    for _, row in matrix.sort_values("Worst_Trade", ascending=False).head(20).iterrows():
        lines.append("  " + format_combo(row))
    lines.append("")

    lines.append("--- Best improving Avg_Return AND Worst_Trade vs baseline ---")
    if improves_both.empty:
        lines.append("  None")
    else:
        lines.append("  " + format_combo(improves_both.iloc[0]))
    lines.append("")

    lines.append("--- Best conservative combination ---")
    if conservative_best is None:
        lines.append("  None met Worst_Trade + PF + Avg_Return >= baseline")
    else:
        lines.append("  " + format_combo(conservative_best))
    lines.append("")

    lines.append("--- Contribution concentration (baseline MAE touch rates) ---")
    for lvl in TOUCH_LEVELS:
        key = f"Did_Touch_{lvl}%"
        rate = sum(1 for t in all_trades if t[key]) / len(all_trades) * 100.0
        lines.append(f"  Touch {lvl}%: {round(rate, 2)}% of trades")
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
