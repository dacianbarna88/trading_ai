"""
Context Edge Expanded Walk-Forward Validation V2.1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Expanded rolling walk-forward for V1.9 candidate: RSI_14 < 40 + BEAR
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from context_intelligence_research_v18 import (
    enrich_spy,
    enrich_ticker,
    load_universe,
)
from momentum_continuation_research_v11 import (
    ENTRY_MODE,
    HISTORY_PERIOD,
    MIN_HISTORY_BARS,
    download_history,
    filter_passes,
)

warnings.filterwarnings("ignore", category=FutureWarning)

EXPANDED_CSV = "context_v21_walkforward_expanded.csv"
SUMMARY_TXT = "context_v21_summary.txt"

THRESHOLD = 5.0
FILTER_MODE = "NO_FILTER"
HOLD_DAYS = 60
MIN_VALID_TRADES = 10
MIN_WIN_RATE_PCT = 60.0
ROLL_STEP_MONTHS = 6

CONTEXT_BASELINE = "BASELINE"
CONTEXT_CANDIDATE = "CANDIDATE_RSI40_BEAR"

ROLLING_CONFIGS: list[tuple[str, float, float]] = [
    ("Rolling_3y_Train_6m_Test", 3.0, 0.5),
    ("Rolling_3y_Train_1y_Test", 3.0, 1.0),
    ("Rolling_4y_Train_1y_Test", 4.0, 1.0),
    ("Rolling_5y_Train_1y_Test", 5.0, 1.0),
    ("Rolling_5y_Train_2y_Test", 5.0, 2.0),
]


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def compute_metrics(returns: np.ndarray, baseline: dict | None = None) -> dict:
    if len(returns) == 0:
        return {
            "Trades": 0,
            "Win_Rate": None,
            "Avg_Return": None,
            "Median_Return": None,
            "Total_Return": None,
            "Profit_Factor": None,
            "Worst_Trade": None,
            "Avg_Winner": None,
            "Avg_Loser": None,
            "Return_Stdev": None,
            "Lift_vs_Baseline_Avg": None,
            "Lift_vs_Baseline_WinRate": None,
        }

    winners = returns[returns > 0]
    losers = returns[returns < 0]
    avg_ret = float(returns.mean())
    win_rate = float((returns > 0).mean() * 100.0)
    row = {
        "Trades": len(returns),
        "Win_Rate": round(win_rate, 2),
        "Avg_Return": round(avg_ret, 4),
        "Median_Return": round(float(np.median(returns)), 4),
        "Total_Return": round(float(returns.sum()), 4),
        "Profit_Factor": round(profit_factor(returns), 4),
        "Worst_Trade": round(float(returns.min()), 4),
        "Avg_Winner": round(float(winners.mean()), 4) if len(winners) else 0.0,
        "Avg_Loser": round(float(losers.mean()), 4) if len(losers) else 0.0,
        "Return_Stdev": round(float(returns.std(ddof=0)), 4) if len(returns) > 1 else 0.0,
        "Lift_vs_Baseline_Avg": None,
        "Lift_vs_Baseline_WinRate": None,
    }
    if baseline and baseline.get("Avg_Return") is not None:
        row["Lift_vs_Baseline_Avg"] = round(avg_ret - baseline["Avg_Return"], 4)
        row["Lift_vs_Baseline_WinRate"] = round(win_rate - baseline["Win_Rate"], 2)
    return row


def collect_signals(
    ticker: str,
    df: pd.DataFrame,
    spy_ctx: pd.DataFrame,
) -> list[dict]:
    min_bars = MIN_HISTORY_BARS + HOLD_DAYS
    if len(df) < min_bars:
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
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

        signal_date = df.index[i]
        spy_row = spy_ctx.loc[signal_date] if signal_date in spy_ctx.index else None
        regime = spy_row.get("Market_Regime", "NEUTRAL") if spy_row is not None else "NEUTRAL"
        rsi = row["RSI_14"]
        ret = ((exit_price - entry_price) / entry_price) * 100.0

        trades.append(
            {
                "Ticker": ticker,
                "Signal_Date": signal_date,
                "RSI_14": float(rsi) if not pd.isna(rsi) else np.nan,
                "Market_Regime": regime,
                "Return_60d": ret,
                "Is_Candidate": not pd.isna(rsi) and rsi < 40 and regime == "BEAR",
            }
        )
        last_exit_idx = exit_idx

    return trades


def years_offset(base: pd.Timestamp, years: float) -> pd.Timestamp:
    return base + pd.Timedelta(days=int(years * 365.25))


def months_offset(base: pd.Timestamp, months: float) -> pd.Timestamp:
    return base + pd.Timedelta(days=int(months * 30.4375))


def check_pass(candidate_m: dict, baseline_m: dict) -> bool:
    if candidate_m["Trades"] < MIN_VALID_TRADES:
        return False
    if candidate_m["Avg_Return"] is None or baseline_m["Avg_Return"] is None:
        return False
    if candidate_m["Win_Rate"] is None or baseline_m["Win_Rate"] is None:
        return False
    if candidate_m["Profit_Factor"] is None or baseline_m["Profit_Factor"] is None:
        return False
    return (
        candidate_m["Avg_Return"] > baseline_m["Avg_Return"]
        and candidate_m["Win_Rate"] > baseline_m["Win_Rate"]
        and candidate_m["Profit_Factor"] > baseline_m["Profit_Factor"]
        and candidate_m["Avg_Return"] > 0
        and candidate_m["Win_Rate"] > MIN_WIN_RATE_PCT
    )


def generate_rolling_folds(
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
    train_years: float,
    test_years: float,
) -> list[dict]:
    folds: list[dict] = []
    cursor = min_date
    fold_num = 0
    step_delta = months_offset(min_date, ROLL_STEP_MONTHS) - min_date

    while True:
        train_start = cursor
        train_end = years_offset(train_start, train_years)
        test_start = train_end
        test_end = years_offset(train_end, test_years)

        if train_end >= max_date:
            break

        actual_test_end = min(test_end, max_date)
        if test_start >= actual_test_end:
            cursor = cursor + step_delta
            if cursor >= max_date:
                break
            continue

        test_days = (actual_test_end - test_start).days
        if test_days < 30:
            cursor = cursor + step_delta
            if cursor + step_delta > max_date and train_end >= max_date:
                break
            continue

        fold_num += 1
        folds.append(
            {
                "fold_num": fold_num,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": actual_test_end,
                "test_length_days": test_days,
            }
        )

        cursor = cursor + step_delta
        if cursor >= max_date:
            break

    return folds


def evaluate_test_window(
    signals_df: pd.DataFrame,
    config_name: str,
    fold: dict,
) -> tuple[dict, dict]:
    test_mask = (
        (signals_df["Signal_Date"] > fold["test_start"])
        & (signals_df["Signal_Date"] <= fold["test_end"])
    )
    test_df = signals_df[test_mask]

    baseline_rets = test_df["Return_60d"].astype(float).values
    candidate_rets = test_df[test_df["Is_Candidate"]]["Return_60d"].astype(float).values

    baseline_m = compute_metrics(baseline_rets)
    candidate_m = compute_metrics(candidate_rets, baseline_m)

    split_id = f"{config_name}_F{fold['fold_num']:03d}"
    low_sample = candidate_m["Trades"] < MIN_VALID_TRADES
    passed = check_pass(candidate_m, baseline_m) if not low_sample else False

    common = {
        "Split_ID": split_id,
        "Config_Name": config_name,
        "Train_Start": fold["train_start"].strftime("%Y-%m-%d"),
        "Train_End": fold["train_end"].strftime("%Y-%m-%d"),
        "Test_Start": fold["test_start"].strftime("%Y-%m-%d"),
        "Test_End": fold["test_end"].strftime("%Y-%m-%d"),
        "Test_Length": fold["test_length_days"],
        "Low_Sample": low_sample,
    }

    baseline_row = {
        **common,
        "Context": CONTEXT_BASELINE,
        "Pass_Flag": None,
        **baseline_m,
    }
    candidate_row = {
        **common,
        "Context": CONTEXT_CANDIDATE,
        "Pass_Flag": passed,
        **candidate_m,
    }
    return baseline_row, candidate_row


def determine_verdict(
    candidate_valid: pd.DataFrame,
    valid_pass_rate: float,
    avg_cand: float,
    avg_base: float,
    underperform_count: int,
) -> str:
    n_valid = len(candidate_valid)
    if n_valid == 0:
        return "WALKFORWARD_FAIL"

    if avg_cand <= 0:
        return "WALKFORWARD_FAIL"

    if underperform_count > n_valid * 0.5:
        return "WALKFORWARD_FAIL"

    if valid_pass_rate >= 0.70 and avg_cand > avg_base:
        return "WALKFORWARD_STRONG_PASS"

    if valid_pass_rate >= 0.50:
        return "WALKFORWARD_PARTIAL_PASS"

    if avg_cand > 0:
        return "WALKFORWARD_WEAK"

    return "WALKFORWARD_FAIL"


def main() -> None:
    print("===== CONTEXT EDGE EXPANDED WALK-FORWARD V2.1 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_EXECUTION")
    print()

    universe = load_universe()
    spy_raw = download_history("SPY")
    if spy_raw.empty:
        Path(SUMMARY_TXT).write_text("SPY_DOWNLOAD_FAILED\n", encoding="utf-8")
        return
    spy_ctx = enrich_spy(spy_raw)

    all_trades: list[dict] = []
    loaded = 0
    for ticker in universe:
        raw = download_history(ticker)
        if raw.empty or len(raw) < MIN_HISTORY_BARS + HOLD_DAYS:
            continue
        df = enrich_ticker(raw)
        trades = collect_signals(ticker, df, spy_ctx)
        if trades:
            loaded += 1
            all_trades.extend(trades)

    if not all_trades:
        Path(SUMMARY_TXT).write_text("INSUFFICIENT_DATA\n", encoding="utf-8")
        return

    signals_df = pd.DataFrame(all_trades)
    signals_df["Signal_Date"] = pd.to_datetime(signals_df["Signal_Date"])
    min_date = signals_df["Signal_Date"].min()
    max_date = signals_df["Signal_Date"].max()

    all_rows: list[dict] = []
    for config_name, train_y, test_y in ROLLING_CONFIGS:
        folds = generate_rolling_folds(min_date, max_date, train_y, test_y)
        for fold in folds:
            b_row, c_row = evaluate_test_window(signals_df, config_name, fold)
            all_rows.append(b_row)
            all_rows.append(c_row)

    expanded_df = pd.DataFrame(all_rows)
    expanded_df.to_csv(EXPANDED_CSV, index=False)

    candidate_rows = expanded_df[expanded_df["Context"] == CONTEXT_CANDIDATE].copy()
    total_splits = len(candidate_rows)
    low_sample_count = int(candidate_rows["Low_Sample"].sum())
    valid_candidate = candidate_rows[~candidate_rows["Low_Sample"]].copy()
    valid_count = len(valid_candidate)

    pass_count = int(valid_candidate["Pass_Flag"].fillna(False).sum())
    pass_rate = pass_count / valid_count if valid_count else 0.0

    avg_cand = float(valid_candidate["Avg_Return"].mean()) if valid_count else 0.0
    avg_base = float(
        expanded_df[
            (expanded_df["Context"] == CONTEXT_BASELINE)
            & expanded_df["Split_ID"].isin(valid_candidate["Split_ID"])
        ]["Avg_Return"].mean()
    ) if valid_count else 0.0

    med_cand = float(valid_candidate["Avg_Return"].median()) if valid_count else 0.0
    med_base = float(
        expanded_df[
            (expanded_df["Context"] == CONTEXT_BASELINE)
            & expanded_df["Split_ID"].isin(valid_candidate["Split_ID"])
        ]["Avg_Return"].median()
    ) if valid_count else 0.0

    avg_cand_win = float(valid_candidate["Win_Rate"].mean()) if valid_count else 0.0
    avg_base_win = float(
        expanded_df[
            (expanded_df["Context"] == CONTEXT_BASELINE)
            & expanded_df["Split_ID"].isin(valid_candidate["Split_ID"])
        ]["Win_Rate"].mean()
    ) if valid_count else 0.0

    avg_cand_pf = float(valid_candidate["Profit_Factor"].mean()) if valid_count else 0.0
    avg_base_pf = float(
        expanded_df[
            (expanded_df["Context"] == CONTEXT_BASELINE)
            & expanded_df["Split_ID"].isin(valid_candidate["Split_ID"])
        ]["Profit_Factor"].mean()
    ) if valid_count else 0.0

    negative_splits = int((valid_candidate["Avg_Return"] < 0).sum()) if valid_count else 0
    underperform = int((valid_candidate["Lift_vs_Baseline_Avg"] < 0).sum()) if valid_count else 0

    best_row = None
    worst_row = None
    if valid_count:
        best_idx = valid_candidate["Avg_Return"].idxmax()
        worst_idx = valid_candidate["Avg_Return"].idxmin()
        best_row = valid_candidate.loc[best_idx]
        worst_row = valid_candidate.loc[worst_idx]

    verdict = determine_verdict(
        valid_candidate, pass_rate, avg_cand, avg_base, underperform
    )

    weaknesses: list[str] = []
    if low_sample_count > 0:
        weaknesses.append(
            f"{low_sample_count}/{total_splits} splits have candidate trades < {MIN_VALID_TRADES}"
        )
    if underperform > 0:
        weaknesses.append(
            f"{underperform}/{valid_count} valid splits: candidate avg below baseline"
        )
    if negative_splits > 0:
        weaknesses.append(
            f"{negative_splits}/{valid_count} valid splits: negative candidate avg return"
        )
    if pass_rate < 0.5 and valid_count:
        weaknesses.append(f"Pass rate {round(pass_rate * 100, 1)}% below 50%")

    lines = [
        "===== CONTEXT EDGE EXPANDED WALK-FORWARD V2.1 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "Candidate: RSI_14 < 40 + Market_Regime = BEAR",
        "NOT FOR PRODUCTION — expanded walk-forward research only.",
        "",
        f"Universe: {len(universe)} | Tickers loaded: {loaded}",
        f"Total signals: {len(signals_df)} | Hold: {HOLD_DAYS}d | Entry: {ENTRY_MODE}",
        f"Signal range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}",
        f"Rolling step: {ROLL_STEP_MONTHS} months",
        "",
        "--- Summary statistics ---",
        f"Total test splits (candidate rows): {total_splits}",
        f"Low-sample splits (candidate trades < {MIN_VALID_TRADES}): {low_sample_count}",
        f"Valid splits (candidate trades >= {MIN_VALID_TRADES}): {valid_count}",
        f"Pass rate among valid splits: {round(pass_rate * 100, 2)}% ({pass_count}/{valid_count})",
        f"Average candidate Avg_Return (valid): {round(avg_cand, 4)}%",
        f"Average baseline Avg_Return (valid): {round(avg_base, 4)}%",
        f"Median candidate Avg_Return (valid): {round(med_cand, 4)}%",
        f"Median baseline Avg_Return (valid): {round(med_base, 4)}%",
        f"Average candidate Win_Rate (valid): {round(avg_cand_win, 2)}%",
        f"Average baseline Win_Rate (valid): {round(avg_base_win, 2)}%",
        f"Average candidate Profit_Factor (valid): {round(avg_cand_pf, 4)}",
        f"Average baseline Profit_Factor (valid): {round(avg_base_pf, 4)}",
        f"Negative candidate splits (valid): {negative_splits}",
        f"Splits candidate underperformed baseline (valid): {underperform}",
        "",
        "--- Best candidate split (valid) ---",
    ]
    if best_row is not None:
        lines.append(
            f"  {best_row['Split_ID']} | avg={best_row['Avg_Return']}% "
            f"win={best_row['Win_Rate']}% trades={int(best_row['Trades'])} "
            f"test={best_row['Test_Start']} to {best_row['Test_End']}"
        )
    else:
        lines.append("  None")
    lines.append("")

    lines.append("--- Worst candidate split (valid) ---")
    if worst_row is not None:
        lines.append(
            f"  {worst_row['Split_ID']} | avg={worst_row['Avg_Return']}% "
            f"win={worst_row['Win_Rate']}% trades={int(worst_row['Trades'])} "
            f"test={worst_row['Test_Start']} to {worst_row['Test_End']}"
        )
    else:
        lines.append("  None")
    lines.append("")

    lines.append("--- Per-config pass rates (valid splits only) ---")
    for config_name, _, _ in ROLLING_CONFIGS:
        sub = valid_candidate[valid_candidate["Config_Name"] == config_name]
        if sub.empty:
            lines.append(f"  {config_name}: no valid splits")
        else:
            cfg_pass = int(sub["Pass_Flag"].fillna(False).sum())
            lines.append(
                f"  {config_name}: {cfg_pass}/{len(sub)} pass "
                f"({round(cfg_pass / len(sub) * 100, 1)}%)"
            )
    lines.append("")

    lines.append("--- Weaknesses found ---")
    if weaknesses:
        for w in weaknesses:
            lines.append(f"  - {w}")
    else:
        lines.append("  None")
    lines.append("")

    lines.append(
        f"Pass criteria (valid splits): trades>={MIN_VALID_TRADES}, "
        "avg>baseline, win>baseline, PF>baseline, avg>0, win>60%."
    )
    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {EXPANDED_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
