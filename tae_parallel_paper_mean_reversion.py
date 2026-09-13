"""New, isolated parallel-paper arm: mean-reversion (long-only).

Context (2026-09-13): V1/V2/V3/exp_short_margin all decide off one shared
trend-following technical score (see tae_score_decile_backtest.py /
tae_cross_arm_overlap_report.py) — running four of them isn't four sources
of alpha, it's four risk-management flavors on the same bet. This arm
trades a genuinely different, backtested signal instead: buy when a
ticker is statistically oversold relative to its own recent mean (see
tae_mean_reversion_signal.py for the exact rule and backtest results —
230 trades/1y, 58.7% win rate, PF 1.81, 0% overlap with the existing
score's buy days).

Isolation, same pattern as tae_parallel_paper_short_margin.py: this
module owns its own portfolio/journals under
runtime_outputs/parallel_paper/exp_mean_reversion/, is never imported by
V1/V2/V3/exp_short_margin, and never imports their decision code. It DOES
reuse three kinds of already-generic, arm-agnostic shared infrastructure
(same as every other arm): tae_parallel_paper_runtime's
default_mark_provider/portfolio_mtm/empty_portfolio for market data and
valuation, and tae_paper_execution's _buy_shares/_sell_shares for the
actual fill mechanics (long-only, no new accounting primitives needed —
unlike exp_short_margin, this arm never holds a negative position).

PAPER_ONLY / NO_BROKER / NO_EXECUTION, same as every other arm.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import tae_mean_reversion_signal as mrsig
import tae_paper_execution as pe
import tae_parallel_paper_runtime as ppr
from tae_network_hard_timeout import hard_timeout

ARM_ID = "exp_mean_reversion"
ARM_DIR = Path("runtime_outputs/parallel_paper") / ARM_ID
STARTING_CAPITAL = 30000.0
MIN_CASH_RESERVE = 500.0
MIN_TRADE_USD = 250.0
MAX_TRADE_USD = 2500.0
MAX_POSITIONS = 12

HISTORY_PERIOD = "3mo"
HISTORY_FETCH_TIMEOUT_SECONDS = 90.0

BUY_REASON = "MEAN_REVERSION_OVERSOLD"


def _paths() -> dict[str, Path]:
    j = ARM_DIR / "journals"
    return {
        "dir": ARM_DIR,
        "portfolio": ARM_DIR / "portfolio.json",
        "decisions": j / "decisions.jsonl",
        "trades": j / "trades.jsonl",
        "errors": j / "errors.jsonl",
    }


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _load_watchlist() -> list[str]:
    path = Path("watchlist.txt")
    if path.exists():
        tickers = [line.strip().upper() for line in path.read_text().splitlines() if line.strip()]
        if tickers:
            return tickers
    return ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


def _load_or_create_portfolio(path: Path) -> dict[str, Any]:
    portfolio = ppr.load_portfolio(path, starting=STARTING_CAPITAL, arm=ARM_ID)
    portfolio.setdefault("mode", "MEAN_REVERSION_EXPERIMENTAL")
    return portfolio


def _open_position_count(portfolio: dict[str, Any]) -> int:
    return len([x for x in (portfolio.get("positions") or {}).values() if pe._f((x or {}).get("shares")) > 0])


def fetch_batch_closes(tickers: list[str]) -> dict[str, list[float]]:
    """One batched multi-ticker yf.download call rather than one call per
    ticker — the same "slow hourly cycle from serial network calls" class
    of bug already found and fixed elsewhere this session
    (tae_network_hard_timeout.py's own docstring). Returns only tickers
    with usable data; callers must treat a missing ticker as "no signal
    today", not an error."""
    import yfinance as yf

    if not tickers:
        return {}
    try:
        with hard_timeout(HISTORY_FETCH_TIMEOUT_SECONDS):
            data = yf.download(
                tickers, period=HISTORY_PERIOD, interval="1d", group_by="ticker", auto_adjust=True, progress=False
            )
    except Exception:
        return {}
    out: dict[str, list[float]] = {}
    for t in tickers:
        try:
            df = data[t].dropna(how="all") if len(tickers) > 1 else data.dropna(how="all")
        except (KeyError, TypeError):
            continue
        if df is None or df.empty or "Close" not in df:
            continue
        closes = [float(c) for c in df["Close"].dropna().tolist()]
        if closes:
            out[t] = closes
    return out


def _decide_and_execute_ticker(
    *,
    portfolio: dict[str, Any],
    ticker: str,
    closes: list[float] | None,
    mark_price: float | None,
    p: dict[str, Path],
    decision_id: str,
    liquid: bool = True,
) -> dict[str, Any]:
    positions = portfolio.get("positions") or {}
    pos = positions.get(ticker)
    has_pos = bool(pos and pe._f(pos.get("shares")) > 0)
    action = "HOLD"
    reason = "MR_HOLD"
    qty = 0.0
    value = 0.0
    realized_pnl_fill: float | None = None
    diag: dict[str, Any] = {}

    price = mark_price if mark_price and mark_price > 0 else (closes[-1] if closes else None)

    if has_pos:
        if not price:
            dec = {
                "ts": ppr._now(),
                "decision_id": decision_id,
                "arm": ARM_ID,
                "ticker": ticker,
                "action": "HOLD",
                "reason": "MR_MARK_UNAVAILABLE",
            }
            _append_jsonl(p["decisions"], dec)
            return dec

        entry_price = pe._f(pos.get("avg_price"))
        days_held = int(pos.get("days_held", 0)) + 1
        _, sma20 = mrsig.zscore_vs_sma(closes) if closes else (None, pos.get("last_sma20"))
        out = mrsig.exit_signal(
            current_price=price,
            sma20=sma20 if sma20 is not None else pos.get("last_sma20", entry_price),
            entry_price=entry_price,
            days_held=days_held,
        )
        diag = out
        pos["days_held"] = days_held
        if sma20 is not None:
            pos["last_sma20"] = sma20
        pos["current_price"] = price
        if out["exit"]:
            shares = pe._f(pos.get("shares"))
            cash_before = pe._f(portfolio.get("cash"))
            realized, gross, after = pe._sell_shares(portfolio, ticker, shares, price)
            action = "SELL"
            reason = f"MEAN_REVERSION_{out['reason']}"
            qty = shares
            value = gross
            realized_pnl_fill = realized
            execution_id = f"MREX-{uuid.uuid4().hex[:16].upper()}"
            _append_jsonl(
                p["trades"],
                {
                    "ts": ppr._now(),
                    "ticker": ticker,
                    "action": "SELL_PAPER",
                    "reason": reason,
                    "shares": qty,
                    "price": price,
                    "decision_id": decision_id,
                    "arm": ARM_ID,
                    "execution_id": execution_id,
                    "realized_pnl": realized_pnl_fill,
                    "gross_proceeds": gross,
                    "cash_before": cash_before,
                    "cash_after": pe._f(portfolio.get("cash")),
                    "days_held": days_held,
                },
            )
        else:
            reason = "MR_HOLD_POSITION_OPEN"
    else:
        if closes and price:
            diag = mrsig.entry_signal(closes)
            if diag.get("entry") and not liquid:
                # Sprint 3 Phase 2 (2026-09-13): same liquidity floor
                # gating V1/V2/V3 (LOW-liquidity PF 0.39 vs HIGH PF 0.92,
                # tae_liquidity_backtest.py) -- a market-microstructure
                # risk independent of which entry signal found the trade.
                reason = "MR_BLOCKED_ILLIQUID"
            elif (
                diag.get("entry")
                and _open_position_count(portfolio) < MAX_POSITIONS
                and pe._f(portfolio.get("cash")) - MIN_CASH_RESERVE >= MIN_TRADE_USD
            ):
                cash = pe._f(portfolio.get("cash"))
                investable = max(0.0, cash - MIN_CASH_RESERVE)
                notional = min(MAX_TRADE_USD, investable * 0.25)
                if notional >= MIN_TRADE_USD:
                    cash_before = cash
                    shares, after = pe._buy_shares(portfolio, ticker, notional, price)
                    if shares > 0:
                        action = "BUY"
                        reason = BUY_REASON
                        qty = shares
                        value = notional
                        after["days_held"] = 0
                        after["last_sma20"] = diag.get("sma20")
                        execution_id = f"MREX-{uuid.uuid4().hex[:16].upper()}"
                        _append_jsonl(
                            p["trades"],
                            {
                                "ts": ppr._now(),
                                "ticker": ticker,
                                "action": "BUY_PAPER",
                                "reason": reason,
                                "shares": qty,
                                "price": price,
                                "decision_id": decision_id,
                                "arm": ARM_ID,
                                "execution_id": execution_id,
                                "cash_before": cash_before,
                                "cash_after": pe._f(portfolio.get("cash")),
                                "entry_z": diag.get("z"),
                                "entry_rsi": diag.get("rsi"),
                            },
                        )

    dec = {
        "ts": ppr._now(),
        "decision_id": decision_id,
        "arm": ARM_ID,
        "ticker": ticker,
        "action": action,
        "reason": reason,
        "quantity": qty,
        "value": value,
        "mark_price": price,
        "realized_pnl": realized_pnl_fill,
        "signal_diagnostics": diag,
    }
    _append_jsonl(p["decisions"], dec)
    return dec


def run_mean_reversion_cycle() -> dict[str, Any]:
    """Runs one full cycle for the isolated mean-reversion arm. Returns a
    summary dict (account_value, cash, open_positions, reconciliation_pass)
    — same shape spirit as exp_short_margin's cycle summary."""
    p = _paths()
    portfolio = _load_or_create_portfolio(p["portfolio"])
    tickers = _load_watchlist()

    held_tickers = list((portfolio.get("positions") or {}).keys())
    all_tickers = sorted(set(tickers) | set(held_tickers))

    marks = ppr.default_mark_provider(all_tickers)
    history = fetch_batch_closes(all_tickers)
    try:
        liquidity_flags = ppr._fetch_liquidity_flags(all_tickers)
    except Exception:
        liquidity_flags = {}

    for ticker in all_tickers:
        snap = marks.get(ticker) or {}
        mark_price = pe._f(snap.get("mark_price")) if snap.get("mark_price") else None
        closes = history.get(ticker)
        decision_id = f"MR-{ticker}-{uuid.uuid4().hex[:12].upper()}"
        _decide_and_execute_ticker(
            portfolio=portfolio,
            ticker=ticker,
            closes=closes,
            mark_price=mark_price,
            p=p,
            decision_id=decision_id,
            liquid=liquidity_flags.get(ticker, True),
        )

    mark_prices = {t: pe._f(s.get("mark_price")) for t, s in marks.items()}
    mark_meta = {
        t: {"mark_freshness": s.get("mark_freshness"), "mark_timestamp": s.get("mark_timestamp")}
        for t, s in marks.items()
    }
    account_value, invested = ppr.portfolio_mtm(portfolio, mark_prices, mark_meta=mark_meta)
    portfolio["account_value"] = account_value
    portfolio["open_positions_value"] = invested
    portfolio["updated_at"] = ppr._now()

    cash = pe._f(portfolio.get("cash"))
    realized_pnl = pe._f(portfolio.get("realized_pnl"))
    expected = pe._f(portfolio.get("starting_capital"), STARTING_CAPITAL) + realized_pnl
    actual = cash + invested
    reconciliation_pass = abs(expected - actual) < 0.01

    p["portfolio"].parent.mkdir(parents=True, exist_ok=True)
    p["portfolio"].write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")

    return {
        "arm": ARM_ID,
        "account_value": account_value,
        "cash": cash,
        "open_positions": _open_position_count(portfolio),
        "realized_pnl": realized_pnl,
        "unrealized_pnl": pe._f(portfolio.get("unrealized_pnl")),
        "reconciliation_pass": reconciliation_pass,
        "reconciliation_expected": round(expected, 4),
        "reconciliation_actual": round(actual, 4),
    }


if __name__ == "__main__":
    import pprint

    pprint.pprint(run_mean_reversion_cycle())
