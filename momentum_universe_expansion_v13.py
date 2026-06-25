"""
Momentum Continuation Research V1.3 — Expanded US Universe Audit

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Tests whether momentum continuation edge survives on a broad US universe.
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
    simulate_ticker,
)

warnings.filterwarnings("ignore", category=FutureWarning)

UNIVERSE_FILE = "us_expanded_universe.txt"
CONTRIBUTION_CSV = "momentum_v13_contribution.csv"
SUMMARY_TXT = "momentum_v13_summary.txt"

REGION = "US"
THRESHOLD = 5.0
HOLD_DAYS = 60
FILTER_MODE = "NO_FILTER"

# Large liquid US names across sectors (100+ symbols, no duplicates)
EXPANDED_US_UNIVERSE: list[str] = [
    # Technology
    "AAPL", "MSFT", "GOOGL", "GOOG", "META", "ORCL", "CRM", "ADBE", "NOW", "INTU",
    "IBM", "CSCO", "PANW", "SNPS", "CDNS", "ANET", "FTNT", "CRWD", "DDOG", "SNOW",
    "PLTR", "TEAM", "WDAY", "ADSK", "HPQ", "DELL",
    # Semiconductors
    "NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC",
    "MRVL", "ON", "ADI", "NXPI", "MCHP", "MPWR", "SWKS", "QRVO", "TER", "ENTG",
    # Financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "V", "MA", "COF",
    "USB", "PNC", "TFC", "BK", "STT", "CB", "MMC", "AIG", "MET", "PRU", "ALL",
    "TRV", "AFL", "CME", "ICE", "SPGI", "MCO",
    # Industrials
    "CAT", "DE", "HON", "GE", "RTX", "LMT", "BA", "UPS", "FDX", "UNP", "CSX",
    "NSC", "WM", "RSG", "EMR", "ETN", "ITW", "PH", "ROK", "CMI", "PCAR", "GD",
    "NOC", "JCI", "TT", "FAST",
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR", "BMY", "AMGN",
    "GILD", "VRTX", "REGN", "ISRG", "SYK", "BSX", "MDT", "ELV", "CI", "HUM",
    "CVS", "MCK", "ZTS", "BDX", "EW", "IDXX", "DXCM", "HCA",
    # Consumer
    "PG", "KO", "PEP", "WMT", "COST", "HD", "LOW", "MCD", "NKE", "SBUX", "TGT",
    "TJX", "ROST", "DG", "DLTR", "YUM", "CMG", "BKNG", "MAR", "HLT", "ORLY",
    "AZO", "F", "GM", "RIVN", "LULU", "EL", "CL", "KMB", "GIS", "KHC",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES",
    "DVN", "HAL", "BKR", "KMI", "WMB", "OKE", "TRGP", "FANG", "APA",
    # Communications
    "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS", "CHTR", "WBD", "OMC", "IPG",
    "EA", "TTWO", "LYV", "MTCH",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "WEC",
    "ES", "AWK", "PEG", "DTE", "FE", "ETR", "AEE", "CMS", "NI",
]


def dedupe_universe(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in symbols:
        t = s.strip().upper()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def concentration_pct(contributions: pd.Series, top_n: int) -> float:
    total = contributions.sum()
    if total == 0:
        return 0.0
    top_sum = contributions.sort_values(ascending=False).head(top_n).sum()
    return round(float(top_sum / total * 100.0), 2)


def ticker_row(ticker: str, trades: list[dict]) -> dict | None:
    if not trades:
        return None
    returns = np.array([t["Return_Pct"] for t in trades], dtype=float)
    return {
        "Ticker": ticker,
        "Trades": len(trades),
        "Win_Rate": round(float((returns > 0).mean() * 100.0), 2),
        "Avg_Return": round(float(returns.mean()), 4),
        "Median_Return": round(float(np.median(returns)), 4),
        "Best_Trade": round(float(returns.max()), 4),
        "Worst_Trade": round(float(returns.min()), 4),
        "Profit_Factor": round(profit_factor(returns), 4),
        "Total_Return_Contribution": round(float(returns.sum()), 4),
    }


def determine_verdict(
    top3: float,
    top5: float,
    top10: float,
    pct_profitable: float,
    avg_ticker_return: float,
) -> str:
    if avg_ticker_return < 5.0:
        return "EDGE_WEAK"
    if top5 > 70.0:
        return "EDGE_HIGHLY_CONCENTRATED"
    if top3 > 50.0:
        return "EDGE_CONCENTRATED"
    if top10 < 60.0 and pct_profitable > 50.0:
        return "EDGE_DIVERSIFIED"
    return "EDGE_MIXED"


def format_row(row: pd.Series) -> str:
    return (
        f"{row['Ticker']} | trades={int(row['Trades'])} | win={row['Win_Rate']}% | "
        f"avg={row['Avg_Return']}% | total={row['Total_Return_Contribution']}% | "
        f"PF={row['Profit_Factor']}"
    )


def main() -> None:
    print("===== MOMENTUM CONTINUATION RESEARCH V1.3 =====")
    print("Expanded US Universe Audit | RESEARCH_ONLY | NO_EXECUTION")
    print()

    universe = dedupe_universe(EXPANDED_US_UNIVERSE)
    Path(UNIVERSE_FILE).write_text("\n".join(universe) + "\n", encoding="utf-8")
    print(f"Universe size: {len(universe)} symbols -> {UNIVERSE_FILE}")

    rows: list[dict] = []
    skipped: list[tuple[str, str]] = []
    all_trades: list[dict] = []

    for ticker in universe:
        raw = download_history(ticker)
        if raw.empty:
            skipped.append((ticker, "DOWNLOAD_FAILED"))
            continue
        if len(raw) < MIN_HISTORY_BARS + HOLD_DAYS:
            skipped.append((ticker, f"INSUFFICIENT_HISTORY_{len(raw)}"))
            continue

        df = enrich(raw)
        trades = simulate_ticker(df, REGION, THRESHOLD, HOLD_DAYS, FILTER_MODE)
        all_trades.extend(trades)
        stats = ticker_row(ticker, trades)
        if stats:
            rows.append(stats)
        else:
            skipped.append((ticker, "ZERO_TRADES"))

    df = pd.DataFrame(rows)
    df.to_csv(CONTRIBUTION_CSV, index=False)

    load_fail = sum(
        1 for _, reason in skipped
        if reason == "DOWNLOAD_FAILED" or reason.startswith("INSUFFICIENT")
    )
    tickers_loaded = len(universe) - load_fail

    lines = [
        "===== MOMENTUM CONTINUATION RESEARCH V1.3 — EXPANDED US UNIVERSE =====",
        "",
        "RESEARCH_ONLY",
        "PAPER_ONLY",
        "NO_BROKER",
        "NO_EXECUTION",
        "",
        f"Configuration: {REGION} | Threshold>={THRESHOLD}% | Hold={HOLD_DAYS}d | {FILTER_MODE}",
        f"History: {HISTORY_PERIOD}",
        f"Entry: {ENTRY_MODE}",
        "",
        f"Universe size (symbols): {len(universe)}",
        f"Tickers loaded with history: {tickers_loaded}",
        f"Tickers with trade stats: {len(df)}",
        f"Tickers skipped: {len(skipped)}",
        f"Total simulated trades: {len(all_trades)}",
        "",
    ]

    if skipped:
        lines.append("--- Skipped tickers (sample) ---")
        for t, reason in skipped[:40]:
            lines.append(f"  {t}: {reason}")
        if len(skipped) > 40:
            lines.append(f"  ... and {len(skipped) - 40} more")
        lines.append("")

    if df.empty:
        lines.append("No ticker results — INSUFFICIENT_DATA")
        Path(SUMMARY_TXT).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return

    contrib = df["Total_Return_Contribution"]
    c1 = concentration_pct(contrib, 1)
    c3 = concentration_pct(contrib, 3)
    c5 = concentration_pct(contrib, 5)
    c10 = concentration_pct(contrib, 10)
    c20 = concentration_pct(contrib, 20)

    profitable = df[df["Total_Return_Contribution"] > 0]
    losing = df[df["Total_Return_Contribution"] < 0]
    flat = df[df["Total_Return_Contribution"] == 0]
    pct_profitable = round(len(profitable) / len(df) * 100.0, 2)
    median_ticker_ret = round(float(df["Avg_Return"].median()), 4)
    avg_ticker_ret = round(float(df["Avg_Return"].mean()), 4)

    verdict = determine_verdict(c3, c5, c10, pct_profitable, avg_ticker_ret)

    lines.extend([
        "--- Contribution concentration (share of total return sum) ---",
        f"Top 1:  {c1}%",
        f"Top 3:  {c3}%",
        f"Top 5:  {c5}%",
        f"Top 10: {c10}%",
        f"Top 20: {c20}%",
        "",
        "--- Distribution statistics ---",
        f"Profitable tickers (total contribution > 0): {len(profitable)}",
        f"Losing tickers (total contribution < 0): {len(losing)}",
        f"Flat tickers: {len(flat)}",
        f"Percent profitable tickers: {pct_profitable}%",
        f"Median ticker Avg_Return: {median_ticker_ret}%",
        f"Average ticker Avg_Return: {avg_ticker_ret}%",
        "",
        "--- Top 20 contributors ---",
    ])
    top20 = df.sort_values(
        ["Total_Return_Contribution", "Avg_Return", "Win_Rate"],
        ascending=[False, False, False],
    ).head(20)
    for _, row in top20.iterrows():
        lines.append("  " + format_row(row))

    lines.append("")
    lines.append("--- Top 20 losers ---")
    bottom20 = df.sort_values("Total_Return_Contribution", ascending=True).head(20)
    for _, row in bottom20.iterrows():
        lines.append("  " + format_row(row))

    lines.extend([
        "",
        "===== FINAL VERDICT =====",
        verdict,
        "",
        "Verdict rules:",
        "  EDGE_DIVERSIFIED: Top10 < 60% AND >50% tickers profitable",
        "  EDGE_CONCENTRATED: Top3 > 50%",
        "  EDGE_HIGHLY_CONCENTRATED: Top5 > 70%",
        "  EDGE_WEAK: Average ticker return < 5%",
        "",
    ])

    summary = "\n".join(lines)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Saved: {UNIVERSE_FILE}")
    print(f"Saved: {CONTRIBUTION_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
