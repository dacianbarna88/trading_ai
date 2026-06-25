"""
Context Edge Robustness Validation V1.9

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Validates V1.8 candidate context: RSI_14 < 40 + Market_Regime = BEAR
"""

from __future__ import annotations

import warnings
from datetime import timedelta
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

MATRIX_CSV = "context_v19_robustness_matrix.csv"
TIME_CSV = "context_v19_time_windows.csv"
SPLITS_CSV = "context_v19_ticker_splits.csv"
SECTOR_CSV = "context_v19_sector_validation.csv"
SUMMARY_TXT = "context_v19_summary.txt"

THRESHOLD = 5.0
FILTER_MODE = "NO_FILTER"
HOLD_PERIODS = [30, 45, 60, 90]
MAX_HOLD = max(HOLD_PERIODS)
TIME_WINDOWS_YEARS = [10, 5, 3, 2, 1]
VALIDATION_HOLD = 60

MIN_CANDIDATE_TRADES = 100
MIN_AVG_LIFT_PCT = 5.0
MIN_WIN_LIFT_PCT = 10.0
MAX_TOP_TICKER_SHARE = 0.35
MIN_SECTORS_WITH_EDGE = 2
MIN_SECTOR_CANDIDATE_TRADES = 10

CONTEXTS = {
    "BASELINE": lambda r: True,
    "CANDIDATE_RSI40_BEAR": lambda r: (
        r["RSI_14"] is not None
        and not pd.isna(r["RSI_14"])
        and r["RSI_14"] < 40
        and r["Market_Regime"] == "BEAR"
    ),
    "NEAR_CONTROL_RSI40_50_BEAR": lambda r: (
        r["RSI_14"] is not None
        and not pd.isna(r["RSI_14"])
        and 40 <= r["RSI_14"] < 50
        and r["Market_Regime"] == "BEAR"
    ),
    "OPPOSITE_RSI70_BULL": lambda r: (
        r["RSI_14"] is not None
        and not pd.isna(r["RSI_14"])
        and r["RSI_14"] > 70
        and r["Market_Regime"] == "BULL"
    ),
}

SECTOR_GROUPS: dict[str, list[str]] = {
    "Technology": [
        "AAPL", "MSFT", "GOOGL", "GOOG", "META", "ORCL", "CRM", "ADBE", "NOW", "INTU",
        "IBM", "CSCO", "PANW", "SNPS", "CDNS", "ANET", "FTNT", "CRWD", "DDOG", "SNOW",
        "PLTR", "TEAM", "WDAY", "ADSK", "HPQ", "DELL",
    ],
    "Semiconductors": [
        "NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC",
        "MRVL", "ON", "ADI", "NXPI", "MCHP", "MPWR", "SWKS", "QRVO", "TER", "ENTG",
    ],
    "Financials": [
        "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "V", "MA", "COF",
        "USB", "PNC", "TFC", "BK", "STT", "CB", "MMC", "AIG", "MET", "PRU", "ALL",
        "TRV", "AFL", "CME", "ICE", "SPGI", "MCO",
    ],
    "Industrials": [
        "CAT", "DE", "HON", "GE", "RTX", "LMT", "BA", "UPS", "FDX", "UNP", "CSX",
        "NSC", "WM", "RSG", "EMR", "ETN", "ITW", "PH", "ROK", "CMI", "PCAR", "GD",
        "NOC", "JCI", "TT", "FAST",
    ],
    "Healthcare": [
        "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR", "BMY", "AMGN",
        "GILD", "VRTX", "REGN", "ISRG", "SYK", "BSX", "MDT", "ELV", "CI", "HUM",
        "CVS", "MCK", "ZTS", "BDX", "EW", "IDXX", "DXCM", "HCA",
    ],
    "Consumer": [
        "PG", "KO", "PEP", "WMT", "COST", "HD", "LOW", "MCD", "NKE", "SBUX", "TGT",
        "TJX", "ROST", "DG", "DLTR", "YUM", "CMG", "BKNG", "MAR", "HLT", "ORLY",
        "AZO", "F", "GM", "RIVN", "LULU", "EL", "CL", "KMB", "GIS", "KHC",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES",
        "DVN", "HAL", "BKR", "KMI", "WMB", "OKE", "TRGP", "FANG", "APA",
    ],
    "Communications": [
        "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS", "CHTR", "WBD", "OMC", "IPG",
        "EA", "TTWO", "LYV", "MTCH",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "WEC",
        "ES", "AWK", "PEG", "DTE", "FE", "ETR", "AEE", "CMS", "NI",
    ],
}


def build_sector_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for sector, tickers in SECTOR_GROUPS.items():
        for t in tickers:
            mapping[t.upper()] = sector
    return mapping


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def compute_metrics(
    returns: np.ndarray,
    baseline: dict | None = None,
) -> dict:
    if len(returns) == 0:
        out = {
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
        return out

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


def collect_signals_for_ticker(
    ticker: str,
    df: pd.DataFrame,
    spy_ctx: pd.DataFrame,
    sector: str,
) -> list[dict]:
    min_bars = MIN_HISTORY_BARS + MAX_HOLD
    if len(df) < min_bars:
        return []

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float)
    trades: list[dict] = []
    last_exit_idx = -1

    for i in range(1, len(df) - MAX_HOLD):
        row = df.iloc[i]
        if not filter_passes(FILTER_MODE, row, THRESHOLD):
            continue

        entry_idx = i + 1
        max_exit_idx = entry_idx + MAX_HOLD - 1
        if max_exit_idx >= len(df):
            break
        if entry_idx <= last_exit_idx:
            continue

        entry_price = float(open_.iloc[entry_idx])
        if pd.isna(entry_price) or entry_price <= 0:
            continue

        signal_date = df.index[i]
        spy_row = spy_ctx.loc[signal_date] if signal_date in spy_ctx.index else None
        regime = "NEUTRAL"
        if spy_row is not None:
            regime = spy_row.get("Market_Regime", "NEUTRAL")

        rsi = row["RSI_14"]
        record: dict = {
            "Ticker": ticker,
            "Sector": sector,
            "Signal_Date": signal_date,
            "Signal_Date_Str": signal_date.strftime("%Y-%m-%d"),
            "RSI_14": float(rsi) if not pd.isna(rsi) else np.nan,
            "Market_Regime": regime,
            "Entry_Price": entry_price,
        }

        valid_holds = True
        for hold in HOLD_PERIODS:
            exit_idx = entry_idx + hold - 1
            exit_price = float(close.iloc[exit_idx])
            if pd.isna(exit_price):
                valid_holds = False
                break
            record[f"Return_{hold}d"] = ((exit_price - entry_price) / entry_price) * 100.0

        if not valid_holds:
            continue

        trades.append(record)
        last_exit_idx = entry_idx + VALIDATION_HOLD - 1

    return trades


def filter_context(df: pd.DataFrame, context_name: str) -> pd.DataFrame:
    fn = CONTEXTS[context_name]
    mask = df.apply(fn, axis=1)
    return df[mask]


def metrics_row(
    df: pd.DataFrame,
    context_name: str,
    hold_days: int,
    baseline: dict | None,
    extra: dict | None = None,
) -> dict:
    col = f"Return_{hold_days}d"
    rets = df[col].astype(float).values
    row = compute_metrics(rets, baseline)
    row["Context"] = context_name
    row["Hold_Days"] = hold_days
    if extra:
        row.update(extra)
    return row


def format_metrics_row(row: dict) -> str:
    return (
        f"{row.get('Context', 'n/a')} hold={row.get('Hold_Days', 'n/a')}d | "
        f"trades={row.get('Trades', 0)} win={row.get('Win_Rate')}% "
        f"avg={row.get('Avg_Return')}% PF={row.get('Profit_Factor')} | "
        f"lift_avg={row.get('Lift_vs_Baseline_Avg')}% lift_win={row.get('Lift_vs_Baseline_WinRate')}%"
    )


def check_ticker_concentration(candidate_df: pd.DataFrame) -> tuple[bool, str, float]:
    if candidate_df.empty:
        return False, "no candidate trades", 1.0
    counts = candidate_df["Ticker"].value_counts()
    top_ticker = counts.index[0]
    share = counts.iloc[0] / len(candidate_df)
    ok = share <= MAX_TOP_TICKER_SHARE
    detail = f"top_ticker={top_ticker} share={round(share * 100, 2)}%"
    return ok, detail, float(share)


def check_sector_diversity(
    candidate_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    hold_col: str,
) -> tuple[bool, str, int]:
    sectors_with_trades = 0
    sectors_beating_baseline = 0
    baseline_avg = float(baseline_df[hold_col].mean()) if len(baseline_df) else 0.0

    for sector in candidate_df["Sector"].unique():
        sub = candidate_df[candidate_df["Sector"] == sector]
        if len(sub) < MIN_SECTOR_CANDIDATE_TRADES:
            continue
        sectors_with_trades += 1
        if float(sub[hold_col].mean()) > baseline_avg:
            sectors_beating_baseline += 1

    ok = sectors_with_trades >= MIN_SECTORS_WITH_EDGE
    detail = (
        f"sectors_with>={MIN_SECTOR_CANDIDATE_TRADES}_trades={sectors_with_trades} "
        f"sectors_beating_baseline_avg={sectors_beating_baseline}"
    )
    return ok, detail, sectors_with_trades


def determine_verdict(
    checks: dict[str, bool],
    weaknesses: list[str],
) -> str:
    required = [
        "min_trades",
        "avg_lift",
        "win_lift",
        "pf_above_baseline",
        "ticker_not_concentrated",
        "sector_diversity",
        "time_windows",
        "split_a",
        "split_b",
    ]
    passed = sum(1 for k in required if checks.get(k, False))
    failed = len(required) - passed

    if all(checks.get(k, False) for k in required):
        return "CONTEXT_EDGE_ROBUST"

    if passed >= 7 and checks.get("min_trades") and checks.get("avg_lift"):
        return "CONTEXT_EDGE_PROMISING_BUT_FRAGILE"

    if passed >= 4 and (checks.get("avg_lift") or checks.get("win_lift")):
        return "CONTEXT_EDGE_OVERFIT_RISK"

    if weaknesses:
        return "CONTEXT_EDGE_FAILED"
    return "CONTEXT_EDGE_OVERFIT_RISK"


def main() -> None:
    print("===== CONTEXT EDGE ROBUSTNESS V1.9 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_EXECUTION")
    print()

    universe = load_universe()
    sector_map = build_sector_map()
    spy_raw = download_history("SPY")
    if spy_raw.empty:
        Path(SUMMARY_TXT).write_text("SPY_DOWNLOAD_FAILED\n", encoding="utf-8")
        print("SPY download failed.")
        return
    spy_ctx = enrich_spy(spy_raw)

    all_signals: list[dict] = []
    loaded_tickers: list[str] = []

    for ticker in universe:
        raw = download_history(ticker)
        if raw.empty or len(raw) < MIN_HISTORY_BARS + MAX_HOLD:
            continue
        df = enrich_ticker(raw)
        sector = sector_map.get(ticker, "Other")
        signals = collect_signals_for_ticker(ticker, df, spy_ctx, sector)
        if signals:
            loaded_tickers.append(ticker)
            all_signals.extend(signals)

    if not all_signals:
        Path(SUMMARY_TXT).write_text("INSUFFICIENT_DATA\n", encoding="utf-8")
        return

    signals_df = pd.DataFrame(all_signals)
    signals_df["Signal_Date"] = pd.to_datetime(signals_df["Signal_Date"])

    # --- Task 2: Hold period matrix ---
    matrix_rows: list[dict] = []
    for hold in HOLD_PERIODS:
        baseline_df = signals_df
        baseline_metrics = compute_metrics(
            baseline_df[f"Return_{hold}d"].astype(float).values
        )
        for ctx in CONTEXTS:
            sub = filter_context(signals_df, ctx)
            matrix_rows.append(
                metrics_row(sub, ctx, hold, baseline_metrics, {"Analysis": "HOLD_PERIOD"})
            )

    matrix_df = pd.DataFrame(matrix_rows)
    matrix_df.to_csv(MATRIX_CSV, index=False)

    # --- Task 3: Time windows (hold 60) ---
    max_date = signals_df["Signal_Date"].max()
    time_rows: list[dict] = []
    hold_col = f"Return_{VALIDATION_HOLD}d"
    windows_positive = 0

    for years in TIME_WINDOWS_YEARS:
        cutoff = max_date - pd.Timedelta(days=int(years * 365.25))
        window_df = signals_df[signals_df["Signal_Date"] >= cutoff]
        baseline_m = compute_metrics(window_df[hold_col].astype(float).values)
        candidate_df = filter_context(window_df, "CANDIDATE_RSI40_BEAR")
        cand_m = metrics_row(
            candidate_df,
            "CANDIDATE_RSI40_BEAR",
            VALIDATION_HOLD,
            baseline_m,
            {"Time_Window_Years": years},
        )
        time_rows.append(
            metrics_row(
                window_df,
                "BASELINE",
                VALIDATION_HOLD,
                None,
                {"Time_Window_Years": years},
            )
        )
        time_rows.append(cand_m)
        if cand_m.get("Avg_Return") is not None and cand_m["Avg_Return"] > 0:
            windows_positive += 1

    time_df = pd.DataFrame(time_rows)
    time_df.to_csv(TIME_CSV, index=False)

    # --- Task 4: Ticker splits (hold 60) ---
    sorted_tickers = sorted(loaded_tickers)
    mid = len(sorted_tickers) // 2
    split_a_tickers = set(sorted_tickers[:mid])
    split_b_tickers = set(sorted_tickers[mid:])
    odd_tickers = {t for i, t in enumerate(loaded_tickers) if i % 2 == 0}
    even_tickers = {t for i, t in enumerate(loaded_tickers) if i % 2 == 1}

    split_defs = {
        "Split_A_first_half": split_a_tickers,
        "Split_B_second_half": split_b_tickers,
        "Odd_index_tickers": odd_tickers,
        "Even_index_tickers": even_tickers,
    }

    split_rows: list[dict] = []
    split_a_candidate_beats = False
    split_b_candidate_beats = False

    for split_name, ticker_set in split_defs.items():
        sub = signals_df[signals_df["Ticker"].isin(ticker_set)]
        baseline_m = compute_metrics(sub[hold_col].astype(float).values)
        cand = filter_context(sub, "CANDIDATE_RSI40_BEAR")
        cand_m = metrics_row(
            cand,
            "CANDIDATE_RSI40_BEAR",
            VALIDATION_HOLD,
            baseline_m,
            {"Ticker_Split": split_name},
        )
        split_rows.append(
            metrics_row(
                sub,
                "BASELINE",
                VALIDATION_HOLD,
                None,
                {"Ticker_Split": split_name},
            )
        )
        split_rows.append(cand_m)
        if split_name == "Split_A_first_half":
            if (
                cand_m.get("Lift_vs_Baseline_Avg") is not None
                and cand_m["Lift_vs_Baseline_Avg"] > 0
            ):
                split_a_candidate_beats = True
        if split_name == "Split_B_second_half":
            if (
                cand_m.get("Lift_vs_Baseline_Avg") is not None
                and cand_m["Lift_vs_Baseline_Avg"] > 0
            ):
                split_b_candidate_beats = True

    splits_df = pd.DataFrame(split_rows)
    splits_df.to_csv(SPLITS_CSV, index=False)

    # --- Task 5: Sector validation ---
    baseline_60 = compute_metrics(signals_df[hold_col].astype(float).values)
    sector_rows: list[dict] = []
    for sector in sorted(signals_df["Sector"].unique()):
        sec_df = signals_df[signals_df["Sector"] == sector]
        cand_sec = filter_context(sec_df, "CANDIDATE_RSI40_BEAR")
        base_m = compute_metrics(sec_df[hold_col].astype(float).values)
        cand_m = compute_metrics(
            cand_sec[hold_col].astype(float).values if len(cand_sec) else np.array([]),
            base_m,
        )
        sector_rows.append(
            {
                "Sector": sector,
                "Baseline_Trades": base_m["Trades"],
                "Candidate_Trades": cand_m["Trades"],
                "Baseline_Avg_Return": base_m["Avg_Return"],
                "Baseline_Win_Rate": base_m["Win_Rate"],
                "Candidate_Avg_Return": cand_m["Avg_Return"],
                "Candidate_Win_Rate": cand_m["Win_Rate"],
                "Candidate_Profit_Factor": cand_m["Profit_Factor"],
                "Candidate_Lift_Avg": cand_m["Lift_vs_Baseline_Avg"],
            }
        )

    sector_df = pd.DataFrame(sector_rows)
    sector_df.to_csv(SECTOR_CSV, index=False)

    # --- Robustness checks (10y / 60d) ---
    candidate_full = filter_context(signals_df, "CANDIDATE_RSI40_BEAR")
    baseline_full_m = compute_metrics(signals_df[hold_col].astype(float).values)
    candidate_full_m = compute_metrics(
        candidate_full[hold_col].astype(float).values,
        baseline_full_m,
    )

    ticker_ok, ticker_detail, top_share = check_ticker_concentration(candidate_full)
    sector_ok, sector_detail, sector_count = check_sector_diversity(
        candidate_full, signals_df, hold_col
    )

    checks = {
        "min_trades": candidate_full_m["Trades"] >= MIN_CANDIDATE_TRADES,
        "avg_lift": (
            candidate_full_m.get("Lift_vs_Baseline_Avg") is not None
            and candidate_full_m["Lift_vs_Baseline_Avg"] >= MIN_AVG_LIFT_PCT
        ),
        "win_lift": (
            candidate_full_m.get("Lift_vs_Baseline_WinRate") is not None
            and candidate_full_m["Lift_vs_Baseline_WinRate"] >= MIN_WIN_LIFT_PCT
        ),
        "pf_above_baseline": (
            candidate_full_m.get("Profit_Factor") is not None
            and baseline_full_m.get("Profit_Factor") is not None
            and candidate_full_m["Profit_Factor"] > baseline_full_m["Profit_Factor"]
        ),
        "ticker_not_concentrated": ticker_ok,
        "sector_diversity": sector_ok,
        "time_windows": windows_positive >= 3,
        "split_a": split_a_candidate_beats,
        "split_b": split_b_candidate_beats,
    }

    weaknesses: list[str] = []
    if not checks["min_trades"]:
        weaknesses.append(f"Candidate trades {candidate_full_m['Trades']} < {MIN_CANDIDATE_TRADES}")
    if not checks["avg_lift"]:
        weaknesses.append(
            f"Avg lift {candidate_full_m.get('Lift_vs_Baseline_Avg')}% < {MIN_AVG_LIFT_PCT}%"
        )
    if not checks["win_lift"]:
        weaknesses.append(
            f"Win lift {candidate_full_m.get('Lift_vs_Baseline_WinRate')}% < {MIN_WIN_LIFT_PCT}%"
        )
    if not checks["pf_above_baseline"]:
        weaknesses.append("Candidate PF not above baseline PF")
    if not ticker_ok:
        weaknesses.append(f"Ticker concentration: {ticker_detail}")
    if not sector_ok:
        weaknesses.append(f"Sector diversity weak: {sector_detail}")
    if not checks["time_windows"]:
        weaknesses.append(
            f"Only {windows_positive}/5 time windows with positive candidate avg return"
        )
    if not checks["split_a"]:
        weaknesses.append("Candidate did not beat baseline on Split_A")
    if not checks["split_b"]:
        weaknesses.append("Candidate did not beat baseline on Split_B")

    verdict = determine_verdict(checks, weaknesses)

    # Summary sections
    hold60_matrix = matrix_df[matrix_df["Hold_Days"] == 60]
    lines = [
        "===== CONTEXT EDGE ROBUSTNESS V1.9 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "Candidate: RSI_14 < 40 + Market_Regime = BEAR",
        "NOT FOR PRODUCTION — research validation only.",
        "",
        f"Universe: {len(universe)} | Tickers loaded: {len(loaded_tickers)}",
        f"Total signals: {len(signals_df)} | History: {HISTORY_PERIOD}",
        f"Entry: {ENTRY_MODE}",
        "",
        "--- 1. Baseline vs candidate at 30/45/60/90 days ---",
    ]
    for hold in HOLD_PERIODS:
        sub = matrix_df[matrix_df["Hold_Days"] == hold]
        for ctx in ["BASELINE", "CANDIDATE_RSI40_BEAR"]:
            row = sub[sub["Context"] == ctx].iloc[0].to_dict()
            lines.append("  " + format_metrics_row(row))
    lines.append("")

    lines.append("--- 2. Candidate vs near-control and opposite (60d) ---")
    for ctx in [
        "CANDIDATE_RSI40_BEAR",
        "NEAR_CONTROL_RSI40_50_BEAR",
        "OPPOSITE_RSI70_BULL",
    ]:
        row = hold60_matrix[hold60_matrix["Context"] == ctx].iloc[0].to_dict()
        lines.append("  " + format_metrics_row(row))
    lines.append("")

    lines.append("--- 3. Time-window robustness (hold 60d) ---")
    for years in TIME_WINDOWS_YEARS:
        sub = time_df[time_df["Time_Window_Years"] == years]
        for _, row in sub.iterrows():
            lines.append(
                f"  {years}y {row['Context']}: trades={int(row['Trades'])} "
                f"avg={row['Avg_Return']}% win={row['Win_Rate']}%"
            )
    lines.append(f"  Positive candidate windows: {windows_positive}/5")
    lines.append("")

    lines.append("--- 4. Ticker split robustness (hold 60d) ---")
    for split_name in split_defs:
        sub = splits_df[splits_df["Ticker_Split"] == split_name]
        for _, row in sub.iterrows():
            lines.append(
                f"  {split_name} {row['Context']}: trades={int(row['Trades'])} "
                f"avg={row['Avg_Return']}% lift_avg={row['Lift_vs_Baseline_Avg']}%"
            )
    lines.append("")

    lines.append("--- 5. Sector/cohort robustness (hold 60d) ---")
    for _, row in sector_df.sort_values("Candidate_Trades", ascending=False).iterrows():
        lines.append(
            f"  {row['Sector']}: baseline_n={int(row['Baseline_Trades'])} "
            f"candidate_n={int(row['Candidate_Trades'])} "
            f"cand_avg={row['Candidate_Avg_Return']}% cand_win={row['Candidate_Win_Rate']}% "
            f"cand_PF={row['Candidate_Profit_Factor']}"
        )
    lines.append("")

    lines.append("--- 6. Weaknesses found ---")
    if weaknesses:
        for w in weaknesses:
            lines.append(f"  - {w}")
    else:
        lines.append("  None")
    lines.append("")

    lines.append("--- Robustness checklist ---")
    for key, ok in checks.items():
        lines.append(f"  {key}: {'PASS' if ok else 'FAIL'}")
    lines.append("")

    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {MATRIX_CSV}")
    print(f"Saved: {TIME_CSV}")
    print(f"Saved: {SPLITS_CSV}")
    print(f"Saved: {SECTOR_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
