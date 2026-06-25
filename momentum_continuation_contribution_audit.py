"""
Momentum Continuation Contribution Audit V1.2

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Identifies which tickers drive momentum continuation edge (US, 60d hold, NO_FILTER).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from daily_gainers_strategy_research import build_ticker_universe
from momentum_continuation_research_v11 import (
    ENTRY_MODE,
    HISTORY_PERIOD,
    MIN_HISTORY_BARS,
    download_history,
    enrich,
    simulate_ticker,
)

warnings.filterwarnings("ignore", category=FutureWarning)

AUDIT_CSV = "momentum_contribution_audit.csv"
SUMMARY_TXT = "momentum_contribution_summary.txt"

FOCUS_CONFIGS = [
    {"Region": "US", "Threshold": 5.0, "Hold_Days": 60, "Filter_Mode": "NO_FILTER"},
    {"Region": "US", "Threshold": 10.0, "Hold_Days": 60, "Filter_Mode": "NO_FILTER"},
]


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def ticker_stats(ticker: str, trades: list[dict], cfg: dict) -> dict | None:
    if not trades:
        return None

    returns = np.array([t["Return_Pct"] for t in trades], dtype=float)
    winners = returns[returns > 0]
    losers = returns[returns < 0]

    return {
        "Region": cfg["Region"],
        "Threshold": cfg["Threshold"],
        "Hold_Days": cfg["Hold_Days"],
        "Filter_Mode": cfg["Filter_Mode"],
        "Ticker": ticker,
        "Trades": len(trades),
        "Win_Rate": round(float((returns > 0).mean() * 100.0), 2),
        "Avg_Return": round(float(returns.mean()), 4),
        "Median_Return": round(float(np.median(returns)), 4),
        "Best_Trade": round(float(returns.max()), 4),
        "Worst_Trade": round(float(returns.min()), 4),
        "Total_Return_Contribution": round(float(returns.sum()), 4),
        "Profit_Factor": round(profit_factor(returns), 4),
        "Winners": int(len(winners)),
        "Losers": int(len(losers)),
        "Return_Stdev": round(float(returns.std(ddof=0)), 4) if len(returns) > 1 else 0.0,
    }


def concentration_pct(contributions: pd.Series, top_n: int) -> float:
    total = contributions.sum()
    if total == 0:
        return 0.0
    top_sum = contributions.sort_values(ascending=False).head(top_n).sum()
    return round(float(top_sum / total * 100.0), 2)


def determine_verdict(c_top1: float, c_top3: float, c_top5: float, c_top10: float) -> str:
    labels = []
    if c_top5 > 70.0:
        labels.append("EDGE_HIGHLY_CONCENTRATED")
    if c_top3 > 50.0:
        labels.append("EDGE_CONCENTRATED")
    if c_top10 < 60.0:
        labels.append("EDGE_DIVERSIFIED")
    if not labels:
        return "EDGE_MIXED"
    if "EDGE_HIGHLY_CONCENTRATED" in labels:
        return "EDGE_HIGHLY_CONCENTRATED"
    if "EDGE_CONCENTRATED" in labels and "EDGE_DIVERSIFIED" in labels:
        return "EDGE_MIXED"
    if labels:
        return labels[0]
    return "EDGE_MIXED"


def format_ticker_row(row: pd.Series) -> str:
    return (
        f"{row['Ticker']} | trades={row['Trades']} | win={row['Win_Rate']}% | "
        f"avg={row['Avg_Return']}% | total={row['Total_Return_Contribution']}% | "
        f"PF={row['Profit_Factor']}"
    )


def audit_config(us_tickers: dict[str, pd.DataFrame], cfg: dict) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict] = []
    skipped: list[str] = []

    for ticker, df in sorted(us_tickers.items()):
        trades = simulate_ticker(
            df,
            cfg["Region"],
            cfg["Threshold"],
            cfg["Hold_Days"],
            cfg["Filter_Mode"],
        )
        stats = ticker_stats(ticker, trades, cfg)
        if stats:
            rows.append(stats)
        else:
            skipped.append(ticker)

    return pd.DataFrame(rows), skipped


def build_summary_section(
    cfg: dict,
    df: pd.DataFrame,
    skipped: list[str],
) -> list[str]:
    lines = [
        f"--- Config: {cfg['Region']} | Threshold>={cfg['Threshold']}% | "
        f"Hold={cfg['Hold_Days']}d | {cfg['Filter_Mode']} ---",
        f"US tickers with trades: {len(df)}",
        f"US tickers with zero trades: {len(skipped)}",
        "",
    ]

    if df.empty:
        lines.append("No trades for this configuration.")
        lines.append("")
        return lines

    contrib = df["Total_Return_Contribution"]
    c1 = concentration_pct(contrib, 1)
    c3 = concentration_pct(contrib, 3)
    c5 = concentration_pct(contrib, 5)
    c10 = concentration_pct(contrib, 10)
    verdict = determine_verdict(c1, c3, c5, c10)

    lines.extend([
        "Contribution concentration (share of total return sum):",
        f"  Top 1 ticker: {c1}%",
        f"  Top 3 tickers: {c3}%",
        f"  Top 5 tickers: {c5}%",
        f"  Top 10 tickers: {c10}%",
        f"  Verdict: {verdict}",
        "",
        "Top 20 contributors (by Total_Return_Contribution):",
    ])
    top20 = df.sort_values(
        ["Total_Return_Contribution", "Avg_Return", "Win_Rate"],
        ascending=[False, False, False],
    ).head(20)
    for _, row in top20.iterrows():
        lines.append("  " + format_ticker_row(row))

    lines.append("")
    lines.append("Top 10 losers (lowest Total_Return_Contribution):")
    losers = df.sort_values("Total_Return_Contribution", ascending=True).head(10)
    for _, row in losers.iterrows():
        lines.append("  " + format_ticker_row(row))

    lines.append("")
    lines.append("Top 10 most consistent (Win_Rate, min 2 trades):")
    consistent = df[df["Trades"] >= 2].sort_values(
        ["Win_Rate", "Avg_Return", "Total_Return_Contribution"],
        ascending=[False, False, False],
    ).head(10)
    if consistent.empty:
        lines.append("  None with >= 2 trades")
    else:
        for _, row in consistent.iterrows():
            lines.append("  " + format_ticker_row(row))

    lines.append("")
    return lines


def main() -> None:
    print("===== MOMENTUM CONTINUATION CONTRIBUTION AUDIT V1.2 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION")
    print()

    ticker_regions = build_ticker_universe()
    us_map = {t: r for t, r in ticker_regions.items() if r == "US"}

    if not us_map:
        msg = "No US tickers in universe.\n"
        Path(SUMMARY_TXT).write_text(msg, encoding="utf-8")
        pd.DataFrame().to_csv(AUDIT_CSV, index=False)
        print(msg)
        return

    us_data: dict[str, pd.DataFrame] = {}
    load_skipped: list[tuple[str, str]] = []

    for ticker in sorted(us_map):
        raw = download_history(ticker)
        if raw.empty:
            load_skipped.append((ticker, "DOWNLOAD_FAILED"))
            continue
        if len(raw) < MIN_HISTORY_BARS:
            load_skipped.append((ticker, f"INSUFFICIENT_HISTORY_{len(raw)}"))
            continue
        us_data[ticker] = enrich(raw)

    all_rows: list[pd.DataFrame] = []
    summary_parts: list[str] = [
        "===== MOMENTUM CONTINUATION CONTRIBUTION AUDIT V1.2 =====",
        "",
        "RESEARCH_ONLY",
        "PAPER_ONLY",
        "NO_BROKER",
        "NO_EXECUTION",
        "",
        f"History: {HISTORY_PERIOD}",
        f"Entry: {ENTRY_MODE}",
        f"US tickers in universe: {len(us_map)}",
        f"US tickers with history loaded: {len(us_data)}",
        f"US tickers skipped on load: {len(load_skipped)}",
        "",
    ]

    if load_skipped:
        summary_parts.append("Load skipped:")
        for t, reason in load_skipped:
            summary_parts.append(f"  {t}: {reason}")
        summary_parts.append("")

    final_verdicts: list[str] = []

    for cfg in FOCUS_CONFIGS:
        df, zero_trade = audit_config(us_data, cfg)
        if not df.empty:
            all_rows.append(df)
        summary_parts.extend(build_summary_section(cfg, df, zero_trade))

        if not df.empty:
            contrib = df["Total_Return_Contribution"]
            verdict = determine_verdict(
                concentration_pct(contrib, 1),
                concentration_pct(contrib, 3),
                concentration_pct(contrib, 5),
                concentration_pct(contrib, 10),
            )
            final_verdicts.append(verdict)

    audit_df = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    audit_df.to_csv(AUDIT_CSV, index=False)

    if final_verdicts:
        if "EDGE_HIGHLY_CONCENTRATED" in final_verdicts:
            overall = "EDGE_HIGHLY_CONCENTRATED"
        elif all(v == "EDGE_DIVERSIFIED" for v in final_verdicts):
            overall = "EDGE_DIVERSIFIED"
        elif "EDGE_CONCENTRATED" in final_verdicts:
            overall = "EDGE_CONCENTRATED"
        else:
            overall = "EDGE_MIXED"
    else:
        overall = "INSUFFICIENT_DATA"

    summary_parts.extend([
        "===== FINAL VERDICT =====",
        overall,
        "",
        "Rules applied:",
        "  Top 3 > 50%  -> EDGE_CONCENTRATED",
        "  Top 5 > 70%  -> EDGE_HIGHLY_CONCENTRATED",
        "  Top 10 < 60% -> EDGE_DIVERSIFIED",
        "",
    ])

    summary = "\n".join(summary_parts)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {AUDIT_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
