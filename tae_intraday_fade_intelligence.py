#!/usr/bin/env python3
"""
TAE Intraday Fade Intelligence — SHADOW_ONLY / PAPER_ONLY research module.

Observes intraday high/fade for open portfolio positions.
Does NOT execute trades or modify live_bot.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from tae_artifact_paths import generated_report
from typing import Any, Callable

import pandas as pd
import yfinance as yf

PORTFOLIO_FILE = Path("portfolio.csv")
OUTPUT_JSON = generated_report("tae_intraday_fade_intelligence.json")
OUTPUT_MD = generated_report("tae_intraday_fade_intelligence.md")

TAKE_PROFIT_PCT = 5.0
STOP_LOSS_PCT = -3.0

SIGNIFICANT_MISSED_USD = 50.0
SIGNIFICANT_HIGH_PCT = 1.0
PARTIAL_TP_HIGH_PCT = 3.0
PARTIAL_TP_FADE_PCT = 1.0
RISK_INTRADAY_LOW_PCT = -2.5
WATCH_MISSED_MIN_USD = 25.0


@dataclass
class OpenPosition:
    ticker: str
    shares: float
    avg_price: float


@dataclass
class IntradayQuote:
    open_price: float
    low: float
    high: float
    current: float
    interval: str


@dataclass
class ShadowSimulation:
    sell_20_at_high_pnl: float
    sell_30_at_high_pnl: float
    trailing_1pct_pnl: float
    trailing_1_5pct_pnl: float


def fifo_open_positions(portfolio: pd.DataFrame) -> dict[str, OpenPosition]:
    """Reconstruct net open positions with FIFO cost basis."""
    lots: dict[str, list[list[float]]] = {}

    for _, row in portfolio.iterrows():
        ticker = str(row.get("Ticker", "")).upper()
        action = str(row.get("Action", "")).upper()
        if not ticker or ticker == "CASH":
            continue

        price = pd.to_numeric(row.get("Price"), errors="coerce")
        shares = pd.to_numeric(row.get("Shares"), errors="coerce")
        if pd.isna(price) or pd.isna(shares) or shares <= 0:
            continue

        lots.setdefault(ticker, [])

        if action == "BUY":
            lots[ticker].append([float(shares), float(price)])
        elif action == "SELL":
            remaining = float(shares)
            new_lots: list[list[float]] = []
            for lot_shares, lot_price in lots[ticker]:
                if remaining <= 0:
                    new_lots.append([lot_shares, lot_price])
                    continue
                used = min(lot_shares, remaining)
                lot_shares -= used
                remaining -= used
                if lot_shares > 1e-8:
                    new_lots.append([lot_shares, lot_price])
            lots[ticker] = new_lots

    open_positions: dict[str, OpenPosition] = {}
    for ticker, ticker_lots in lots.items():
        total_shares = sum(lot[0] for lot in ticker_lots)
        if total_shares <= 1e-8:
            continue
        cost = sum(lot[0] * lot[1] for lot in ticker_lots)
        open_positions[ticker] = OpenPosition(
            ticker=ticker,
            shares=total_shares,
            avg_price=cost / total_shares,
        )
    return open_positions


def fetch_intraday_quote(
    ticker: str,
    download_fn: Callable[..., pd.DataFrame] | None = None,
) -> IntradayQuote | None:
    """Fetch today's intraday OHLC via 1m/5m/15m fallback."""
    download = download_fn or yf.download
    for interval in ("1m", "5m", "15m"):
        try:
            data = download(
                ticker,
                period="1d",
                interval=interval,
                auto_adjust=False,
                progress=False,
            )
        except Exception:
            continue
        if data is None or data.empty:
            continue
        if len(data.columns.names) > 1:
            data = data.copy()
            data.columns = data.columns.droplevel(1)
        return IntradayQuote(
            open_price=float(data["Open"].dropna().iloc[0]),
            low=float(data["Low"].min()),
            high=float(data["High"].max()),
            current=float(data["Close"].dropna().iloc[-1]),
            interval=interval,
        )
    return None


def missed_opportunity_usd(shares: float, avg: float, high: float, current: float) -> float:
    return (high - current) * shares


def classify_position(
    *,
    high_pct: float,
    current_pct: float,
    low_pct: float,
    missed_usd: float,
) -> str:
    if high_pct >= TAKE_PROFIT_PCT and current_pct < TAKE_PROFIT_PCT:
        return "POTENTIAL_PARTIAL_TAKE_PROFIT"
    if high_pct >= PARTIAL_TP_HIGH_PCT and current_pct < high_pct - PARTIAL_TP_FADE_PCT:
        return "POTENTIAL_PARTIAL_TAKE_PROFIT"
    if (
        missed_usd > SIGNIFICANT_MISSED_USD
        and high_pct > SIGNIFICANT_HIGH_PCT
    ):
        return "SIGNIFICANT_INTRADAY_FADE"
    if low_pct <= RISK_INTRADAY_LOW_PCT:
        return "RISK_INTRADAY_LOW"
    if missed_usd > max(WATCH_MISSED_MIN_USD, 1.0):
        return "WATCH_INTRADAY_FADE"
    return "HOLD"


def simulate_shadow_strategies(
    shares: float,
    avg: float,
    high: float,
    current: float,
) -> ShadowSimulation:
    """Theoretical partial/trailing outcomes (no execution)."""
    full_hold_pnl = (current - avg) * shares
    high_pnl = (high - avg) * shares

    sell_20 = (high - avg) * (shares * 0.20) + (current - avg) * (shares * 0.80)
    sell_30 = (high - avg) * (shares * 0.30) + (current - avg) * (shares * 0.70)

    trail_1 = (high * 0.99 - avg) * shares
    trail_1_5 = (high * 0.985 - avg) * shares

    # If current is above trail exit, hold current is better than trail trigger
    trail_1_exit = high * 0.99
    trail_1_5_exit = high * 0.985
    if current >= trail_1_exit:
        trail_1 = full_hold_pnl
    else:
        trail_1 = (trail_1_exit - avg) * shares

    if current >= trail_1_5_exit:
        trail_1_5 = full_hold_pnl
    else:
        trail_1_5 = (trail_1_5_exit - avg) * shares

    _ = high_pnl  # retained for clarity in reports
    return ShadowSimulation(
        sell_20_at_high_pnl=round(sell_20, 2),
        sell_30_at_high_pnl=round(sell_30, 2),
        trailing_1pct_pnl=round(trail_1, 2),
        trailing_1_5pct_pnl=round(trail_1_5, 2),
    )


def analyze_position(
    position: OpenPosition,
    quote: IntradayQuote | None,
) -> dict[str, Any]:
    if quote is None:
        return {
            "ticker": position.ticker,
            "shares": round(position.shares, 4),
            "avg_price": round(position.avg_price, 2),
            "classification": "DATA_UNAVAILABLE",
        }

    avg = position.avg_price
    shares = position.shares
    current = quote.current
    high = quote.high
    low = quote.low

    current_pnl = (current - avg) * shares
    high_pnl = (high - avg) * shares
    missed = missed_opportunity_usd(shares, avg, high, current)

    current_pct = (current / avg - 1) * 100
    high_pct = (high / avg - 1) * 100
    low_pct = (low / avg - 1) * 100
    drawdown_from_high_pct = (current / high - 1) * 100 if high else 0.0

    classification = classify_position(
        high_pct=high_pct,
        current_pct=current_pct,
        low_pct=low_pct,
        missed_usd=missed,
    )
    shadow = simulate_shadow_strategies(shares, avg, high, current)

    return {
        "ticker": position.ticker,
        "shares": round(shares, 4),
        "avg_price": round(avg, 2),
        "open_price": round(quote.open_price, 2),
        "low": round(low, 2),
        "high": round(high, 2),
        "current": round(current, 2),
        "interval": quote.interval,
        "current_pnl_usd": round(current_pnl, 2),
        "high_pnl_usd": round(high_pnl, 2),
        "missed_opportunity_usd": round(missed, 2),
        "fade_from_high_usd": round(missed, 2),
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "low_pct": round(low_pct, 2),
        "drawdown_from_high_pct": round(drawdown_from_high_pct, 2),
        "take_profit_5_hit_at_high": high_pct >= TAKE_PROFIT_PCT,
        "stop_loss_3_hit_at_low": low_pct <= STOP_LOSS_PCT,
        "classification": classification,
        "shadow": asdict(shadow),
    }


def build_report(
    portfolio_path: Path = PORTFOLIO_FILE,
    download_fn: Callable[..., pd.DataFrame] | None = None,
) -> dict[str, Any]:
    portfolio = pd.read_csv(portfolio_path)
    positions = fifo_open_positions(portfolio)

    rows: list[dict[str, Any]] = []
    for ticker in sorted(positions.keys()):
        quote = fetch_intraday_quote(ticker, download_fn=download_fn)
        rows.append(analyze_position(positions[ticker], quote))

    valid = [r for r in rows if r.get("classification") != "DATA_UNAVAILABLE"]

    totals = {
        "total_current_unrealized_usd": round(
            sum(r.get("current_pnl_usd", 0) for r in valid), 2
        ),
        "total_at_high_usd": round(sum(r.get("high_pnl_usd", 0) for r in valid), 2),
        "total_missed_opportunity_usd": round(
            sum(r.get("missed_opportunity_usd", 0) for r in valid), 2
        ),
        "total_shadow_sell_20_at_high_usd": round(
            sum(r.get("shadow", {}).get("sell_20_at_high_pnl", 0) for r in valid), 2
        ),
        "total_shadow_sell_30_at_high_usd": round(
            sum(r.get("shadow", {}).get("sell_30_at_high_pnl", 0) for r in valid), 2
        ),
        "total_shadow_trailing_1pct_usd": round(
            sum(r.get("shadow", {}).get("trailing_1pct_pnl", 0) for r in valid), 2
        ),
        "total_shadow_trailing_1_5pct_usd": round(
            sum(r.get("shadow", {}).get("trailing_1_5pct_pnl", 0) for r in valid), 2
        ),
    }

    significant = [
        r["ticker"]
        for r in valid
        if r.get("classification") == "SIGNIFICANT_INTRADAY_FADE"
    ]
    take_profit_hits = [
        r["ticker"] for r in valid if r.get("take_profit_5_hit_at_high")
    ]
    stop_hits = [r["ticker"] for r in valid if r.get("stop_loss_3_hit_at_low")]

    missed_total = totals["total_missed_opportunity_usd"]
    if missed_total > 100:
        verdict = "TAE missed meaningful intraday opportunity."
    elif significant:
        verdict = "Significant intraday fade detected — shadow review recommended."
    else:
        verdict = "No major intraday missed opportunity today."

    return {
        "schema": "tae_intraday_fade_intelligence",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "portfolio_file": str(portfolio_path),
        "open_position_count": len(rows),
        "positions": rows,
        "totals": totals,
        "significant_intraday_fade_tickers": significant,
        "take_profit_5_hit_at_high": take_profit_hits,
        "stop_loss_3_hit_at_low": stop_hits,
        "daily_verdict": verdict,
    }


def _positions_table_md(positions: list[dict[str, Any]]) -> str:
    if not positions:
        return "_No open positions._\n"
    cols = [
        "ticker",
        "shares",
        "avg_price",
        "high",
        "current",
        "current_pct",
        "high_pct",
        "missed_opportunity_usd",
        "classification",
    ]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in positions:
        if row.get("classification") == "DATA_UNAVAILABLE":
            lines.append(
                f"| {row['ticker']} | {row.get('shares','')} | {row.get('avg_price','')} | — | — | — | — | — | DATA_UNAVAILABLE |"
            )
            continue
        lines.append(
            "| "
            + " | ".join(str(row.get(c, "")) for c in cols)
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    totals = report["totals"]
    md = "\n".join(
        [
            "# TAE Intraday Fade Intelligence",
            "",
            f"**Generated:** {report['generated_at']}",
            f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
            "",
            "## Daily verdict",
            report["daily_verdict"],
            "",
            "## Totals",
            f"- Current unrealized: **{totals['total_current_unrealized_usd']} USD**",
            f"- Theoretical at high: **{totals['total_at_high_usd']} USD**",
            f"- Missed intraday opportunity: **{totals['total_missed_opportunity_usd']} USD**",
            f"- Shadow SELL 20% at high: **{totals['total_shadow_sell_20_at_high_usd']} USD**",
            f"- Shadow SELL 30% at high: **{totals['total_shadow_sell_30_at_high_usd']} USD**",
            f"- Shadow trailing 1% from high: **{totals['total_shadow_trailing_1pct_usd']} USD**",
            f"- Shadow trailing 1.5% from high: **{totals['total_shadow_trailing_1_5pct_usd']} USD**",
            "",
            "## Significant intraday fade",
            ", ".join(report["significant_intraday_fade_tickers"]) or "None",
            "",
            "## Positions",
            _positions_table_md(report["positions"]),
        ]
    )
    OUTPUT_MD.write_text(md, encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    print("===== TAE INTRADAY FADE INTELLIGENCE (SHADOW) =====")
    print("Generated:", report["generated_at"])
    print()

    df = pd.DataFrame(report["positions"])
    if not df.empty:
        display_cols = [
            c
            for c in [
                "ticker",
                "shares",
                "avg_price",
                "high",
                "current",
                "current_pct",
                "high_pct",
                "missed_opportunity_usd",
                "drawdown_from_high_pct",
                "classification",
            ]
            if c in df.columns
        ]
        print(df[display_cols].to_string(index=False))

    totals = report["totals"]
    print()
    print("===== TOTALS =====")
    print("Total current unrealized:", totals["total_current_unrealized_usd"])
    print("Total at high:", totals["total_at_high_usd"])
    print("Total missed opportunity:", totals["total_missed_opportunity_usd"])
    print("Shadow SELL 20% at high:", totals["total_shadow_sell_20_at_high_usd"])
    print("Shadow SELL 30% at high:", totals["total_shadow_sell_30_at_high_usd"])
    print(
        "SIGNIFICANT_INTRADAY_FADE:",
        report["significant_intraday_fade_tickers"] or "None",
    )
    print("Verdict:", report["daily_verdict"])


def main() -> int:
    from tae_intraday_fade_history import record_fade_report

    report = build_report()
    write_outputs(report)
    history_result = record_fade_report(report)
    print_summary(report)
    print()
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    if history_result.get("appended"):
        print(
            "History recorded:",
            history_result["run_id"],
            f"({history_result['records_added']} positions)",
        )
    else:
        print("History:", history_result.get("reason", "skipped"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
