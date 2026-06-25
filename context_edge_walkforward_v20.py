"""
Context Edge Walk-Forward Validation V2.0

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Out-of-sample validation of V1.9 candidate: RSI_14 < 40 + Market_Regime = BEAR
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

SPLITS_CSV = "context_v20_walkforward_splits.csv"
TRADES_CSV = "context_v20_trade_results.csv"
SUMMARY_TXT = "context_v20_summary.txt"

THRESHOLD = 5.0
FILTER_MODE = "NO_FILTER"
HOLD_DAYS = 60
MIN_VALIDATION_TRADES = 20
MIN_WIN_RATE_PCT = 60.0

CONTEXT_BASELINE = "BASELINE"
CONTEXT_CANDIDATE = "CANDIDATE_RSI40_BEAR"


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


def is_candidate(row: pd.Series) -> bool:
    rsi = row["RSI_14"]
    return (
        not pd.isna(rsi)
        and rsi < 40
        and row["Market_Regime"] == "BEAR"
    )


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
                "Signal_Date_Str": signal_date.strftime("%Y-%m-%d"),
                "Entry_Date": df.index[entry_idx].strftime("%Y-%m-%d"),
                "Exit_Date": df.index[exit_idx].strftime("%Y-%m-%d"),
                "RSI_14": round(float(rsi), 4) if not pd.isna(rsi) else None,
                "Market_Regime": regime,
                "Daily_Gain_Pct": round(float(row["Daily_Gain_Pct"]), 4),
                "Return_60d": round(ret, 4),
                "Win": ret > 0,
                "Is_Candidate": (
                    not pd.isna(rsi) and rsi < 40 and regime == "BEAR"
                ),
            }
        )
        last_exit_idx = exit_idx

    return trades


def years_offset(base: pd.Timestamp, years: float) -> pd.Timestamp:
    return base + pd.Timedelta(days=int(years * 365.25))


def evaluate_phase(
    df: pd.DataFrame,
    split_name: str,
    phase: str,
    date_start: pd.Timestamp,
    date_end: pd.Timestamp,
    inclusive_end: bool = True,
    exclusive_start: bool = False,
) -> tuple[dict, dict, bool]:
    if exclusive_start:
        start_ok = df["Signal_Date"] > date_start
    else:
        start_ok = df["Signal_Date"] >= date_start
    if inclusive_end:
        end_ok = df["Signal_Date"] <= date_end
    else:
        end_ok = df["Signal_Date"] < date_end
    mask = start_ok & end_ok

    sub = df[mask]
    baseline_rets = sub["Return_60d"].astype(float).values
    candidate_sub = sub[sub["Is_Candidate"]]
    cand_rets = candidate_sub["Return_60d"].astype(float).values

    baseline_m = compute_metrics(baseline_rets)
    candidate_m = compute_metrics(cand_rets, baseline_m)

    passed = check_validation_pass(candidate_m, baseline_m)

    baseline_row = {
        "Split_Name": split_name,
        "Phase": phase,
        "Context": CONTEXT_BASELINE,
        "Date_Start": date_start.strftime("%Y-%m-%d"),
        "Date_End": date_end.strftime("%Y-%m-%d"),
        "Validation_Pass": None,
        **baseline_m,
    }
    candidate_row = {
        "Split_Name": split_name,
        "Phase": phase,
        "Context": CONTEXT_CANDIDATE,
        "Date_Start": date_start.strftime("%Y-%m-%d"),
        "Date_End": date_end.strftime("%Y-%m-%d"),
        "Validation_Pass": passed if phase in ("VALIDATION", "TEST") else None,
        **candidate_m,
    }
    return baseline_row, candidate_row, passed


def check_validation_pass(candidate_m: dict, baseline_m: dict) -> bool:
    if candidate_m["Trades"] < MIN_VALIDATION_TRADES:
        return False
    if candidate_m["Avg_Return"] is None or baseline_m["Avg_Return"] is None:
        return False
    if candidate_m["Win_Rate"] is None or baseline_m["Win_Rate"] is None:
        return False
    if candidate_m["Profit_Factor"] is None or baseline_m["Profit_Factor"] is None:
        return False
    return (
        candidate_m["Trades"] >= MIN_VALIDATION_TRADES
        and candidate_m["Avg_Return"] > baseline_m["Avg_Return"]
        and candidate_m["Win_Rate"] > baseline_m["Win_Rate"]
        and candidate_m["Profit_Factor"] > baseline_m["Profit_Factor"]
        and candidate_m["Avg_Return"] > 0
        and candidate_m["Win_Rate"] > MIN_WIN_RATE_PCT
    )


def format_row(row: dict) -> str:
    return (
        f"{row['Split_Name']} {row['Phase']} {row['Context']}: "
        f"trades={row['Trades']} win={row['Win_Rate']}% avg={row['Avg_Return']}% "
        f"PF={row['Profit_Factor']} pass={row.get('Validation_Pass')}"
    )


def determine_verdict(test_passes: dict[str, bool]) -> str:
    main_pass = test_passes.get("Chronological_70_30", False)
    rolling_keys = [k for k in test_passes if k.startswith("Rolling_")]
    rolling_passed = sum(1 for k in rolling_keys if test_passes[k])
    total_tests = len(test_passes)
    total_passed = sum(1 for v in test_passes.values() if v)

    if main_pass and all(test_passes[k] for k in rolling_keys):
        return "CONTEXT_EDGE_WALKFORWARD_PASS"
    if main_pass and rolling_passed >= 2:
        return "CONTEXT_EDGE_WALKFORWARD_PARTIAL"
    if total_passed >= total_tests * 0.75:
        return "CONTEXT_EDGE_WALKFORWARD_PARTIAL"
    if main_pass:
        return "CONTEXT_EDGE_WALKFORWARD_PARTIAL"
    return "CONTEXT_EDGE_WALKFORWARD_FAIL"


def main() -> None:
    print("===== CONTEXT EDGE WALK-FORWARD V2.0 =====")
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

    split_rows: list[dict] = []
    test_passes: dict[str, bool] = {}
    weaknesses: list[str] = []

    # --- Chronological 70/30 ---
    span = max_date - min_date
    cutoff_70 = min_date + span * 0.7

    b_disc, c_disc, _ = evaluate_phase(
        signals_df,
        "Chronological_70_30",
        "DISCOVERY",
        min_date,
        cutoff_70,
        inclusive_end=True,
    )
    b_val, c_val, val_pass = evaluate_phase(
        signals_df,
        "Chronological_70_30",
        "VALIDATION",
        cutoff_70,
        max_date,
        inclusive_end=True,
    )
    split_rows.extend([b_disc, c_disc, b_val, c_val])
    test_passes["Chronological_70_30"] = val_pass
    if not val_pass:
        weaknesses.append("Chronological 70/30 validation window failed candidate checks")

    # --- Rolling walk-forward splits ---
    rolling_defs = [
        ("Rolling_Train5y_Test1y", 5.0, 6.0),
        ("Rolling_Train5y_Test2y", 5.0, 7.0),
        ("Rolling_Train3y_Test1y", 3.0, 4.0),
    ]

    for split_name, train_years, test_end_years in rolling_defs:
        train_end = years_offset(min_date, train_years)
        test_end = years_offset(min_date, test_end_years)
        if test_end > max_date:
            test_end = max_date
        if train_end >= max_date:
            weaknesses.append(f"{split_name}: train window exceeds data range")
            test_passes[split_name] = False
            continue

        b_train, c_train, _ = evaluate_phase(
            signals_df,
            split_name,
            "TRAIN",
            min_date,
            train_end,
            inclusive_end=True,
        )
        b_test, c_test, test_pass = evaluate_phase(
            signals_df,
            split_name,
            "TEST",
            train_end,
            test_end,
            inclusive_end=True,
            exclusive_start=True,
        )
        split_rows.extend([b_train, c_train, b_test, c_test])
        test_passes[split_name] = test_pass
        if not test_pass:
            weaknesses.append(f"{split_name} test window failed candidate checks")

    splits_df = pd.DataFrame(split_rows)
    splits_df.to_csv(SPLITS_CSV, index=False)

    # --- Trade results with split membership flags ---
    signals_df["In_Discovery_70pct"] = signals_df["Signal_Date"] <= cutoff_70
    signals_df["In_Validation_30pct"] = signals_df["Signal_Date"] > cutoff_70

    for split_name, train_years, test_end_years in rolling_defs:
        train_end = years_offset(min_date, train_years)
        test_end = years_offset(min_date, test_end_years)
        if test_end > max_date:
            test_end = max_date
        col_train = f"In_{split_name}_TRAIN"
        col_test = f"In_{split_name}_TEST"
        signals_df[col_train] = signals_df["Signal_Date"] <= train_end
        signals_df[col_test] = (
            (signals_df["Signal_Date"] > train_end)
            & (signals_df["Signal_Date"] <= test_end)
        )

    export_cols = [
        "Ticker",
        "Signal_Date_Str",
        "Entry_Date",
        "Exit_Date",
        "Daily_Gain_Pct",
        "RSI_14",
        "Market_Regime",
        "Return_60d",
        "Win",
        "Is_Candidate",
        "In_Discovery_70pct",
        "In_Validation_30pct",
    ]
    for split_name, _, _ in rolling_defs:
        export_cols.extend([f"In_{split_name}_TRAIN", f"In_{split_name}_TEST"])

    signals_df[export_cols].to_csv(TRADES_CSV, index=False)

    verdict = determine_verdict(test_passes)

    lines = [
        "===== CONTEXT EDGE WALK-FORWARD V2.0 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "Candidate: RSI_14 < 40 + Market_Regime = BEAR (unchanged from V1.9)",
        "NOT FOR PRODUCTION — walk-forward research only.",
        "",
        f"Universe: {len(universe)} | Tickers loaded: {loaded}",
        f"Total signals: {len(signals_df)} | Hold: {HOLD_DAYS}d | Entry: {ENTRY_MODE}",
        f"Signal date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}",
        f"70/30 cutoff: {cutoff_70.strftime('%Y-%m-%d')}",
        "",
        "--- 1. Discovery window (first 70% of dates) ---",
    ]
    for row in [b_disc, c_disc]:
        lines.append("  " + format_row(row))
    lines.append("")

    lines.append("--- 2. Validation window (last 30% of dates) ---")
    for row in [b_val, c_val]:
        lines.append("  " + format_row(row))
    lines.append("")

    lines.append("--- 3. Rolling walk-forward results ---")
    for split_name, _, _ in rolling_defs:
        sub = splits_df[splits_df["Split_Name"] == split_name]
        for _, row in sub.iterrows():
            lines.append("  " + format_row(row.to_dict()))
    lines.append("")

    lines.append("--- 4. Pass/fail per validation/test split ---")
    for name, passed in test_passes.items():
        lines.append(f"  {name}: {'PASS' if passed else 'FAIL'}")
    lines.append("")

    lines.append("--- 5. Weaknesses found ---")
    if weaknesses:
        for w in weaknesses:
            lines.append(f"  - {w}")
    else:
        lines.append("  None")
    lines.append("")

    lines.append(
        "Validation pass requires: trades>=20, avg>baseline, win>baseline, "
        "PF>baseline, avg>0, win>60%."
    )
    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {SPLITS_CSV}")
    print(f"Saved: {TRADES_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
