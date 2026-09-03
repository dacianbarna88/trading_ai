"""New, isolated parallel-paper arm: short-selling + margin.

Self-contained runner — deliberately NOT threaded through the shared
run_cycle()/parallel-paper-run-once dispatcher that drives V1/V2/V3. That
dispatcher is a large, tightly-interdependent function; wiring a genuinely
new capability (negative shares, margin accounting) through it would touch
far more surface than this new arm needs. Instead this module owns its own
full cycle: load/create its portfolio, decide per ticker, execute via
tae_paper_execution_short.py's new opt-in primitives, mark-to-market, save,
log — reusing tae_parallel_paper_runtime's generic helpers
(default_mark_provider, portfolio_mtm, empty_portfolio) exactly as V1/V2/V3
do, so it observes the same market data and safety posture without any
cross-wiring into their portfolios. V1/V2/V3 code never imports or calls
anything in this module, and vice versa (aside from those shared, already
arm-agnostic helpers) — zero cross-contamination risk.

PAPER_ONLY / NO_BROKER / NO_EXECUTION, same as every other arm. There is no
code path here that calls a broker or sets live_allowed=True.

Entry signal (intentionally simple, first cut): short a ticker whose score
is clearly on the bearish end of live_bot.py's own 0-100 scale (score <= 20,
the mirror of MIN_SCORE_TO_BUY's "clearly bullish" bar). live_bot.py's
scoring system has no dedicated bearish/SELL signal today — this reuses
what's already computed rather than inventing a second scoring model. Like
V1's original mechanical bracket, this is meant to be refined once real
data accumulates, not treated as a finished signal.
"""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any

import tae_paper_execution_short as pes
import tae_parallel_paper_runtime as ppr

ARM_ID = "exp_short_margin"
ARM_DIR = Path("runtime_outputs/parallel_paper") / ARM_ID
STARTING_CAPITAL = 30000.0
MIN_CASH_RESERVE = 500.0
MIN_TRADE_USD = 250.0
MAX_TRADE_USD = 2500.0
MAX_SHORT_POSITIONS = 12

MARGIN_REQUIREMENT_PCT = 0.5
MAINTENANCE_MARGIN_PCT = 0.25
MAX_MARGIN_UTILIZATION_PCT = 0.5

SHORT_ENTRY_MAX_SCORE = 20.0

STOP_LOSS_PCT = 3.0
TRAILING_ACTIVATE_PCT = 5.0
TRAILING_DISTANCE_PCT = 2.0

SHORT_OPEN_REASON = "SHORT_BEARISH_SCORE"
COVER_STOP_LOSS_REASON = "SHORT_STOP_LOSS"
COVER_TRAILING_REASON = "SHORT_PROFIT_TRAILING_5_2"
COVER_MARGIN_CALL_REASON = "MARGIN_CALL_LIQUIDATION"


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
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "cash" in raw:
                raw.setdefault("margin_reserved", 0.0)
                return raw
        except (OSError, json.JSONDecodeError):
            pass
    pf = ppr.empty_portfolio(STARTING_CAPITAL, arm=ARM_ID)
    pf["margin_reserved"] = 0.0
    pf["mode"] = "SHORT_MARGIN_EXPERIMENTAL"
    return pf


def _open_short_position_count(portfolio: dict[str, Any]) -> int:
    return sum(
        1 for pos in (portfolio.get("positions") or {}).values() if pes._f(pos.get("shares")) < 0
    )


def _decide_and_execute_ticker(
    *,
    portfolio: dict[str, Any],
    ticker: str,
    snap: dict[str, Any],
    p: dict[str, Path],
    decision_id: str,
) -> dict[str, Any]:
    mark_ok, mark_status, mark = ppr._mark_is_usable(snap)
    positions = portfolio.get("positions") or {}
    pos = positions.get(ticker)
    is_short = bool(pos and pes._f(pos.get("shares")) < 0)
    action = "HOLD"
    reason = "SM_HOLD"
    qty = 0.0
    value = 0.0
    realized_pnl_fill: float | None = None

    if is_short:
        if not mark_ok:
            dec = {
                "ts": ppr._now(),
                "decision_id": decision_id,
                "arm": ARM_ID,
                "ticker": ticker,
                "action": "HOLD",
                "reason": mark_status,
            }
            _append_jsonl(p["decisions"], dec)
            return dec

        avg_price = pes._f(pos.get("avg_price"))
        margin_call = pes.check_margin_call(
            pos, current_price=mark, maintenance_margin_pct=MAINTENANCE_MARGIN_PCT
        )
        if margin_call:
            act, cover_reason = "SELL_STOP_LOSS", COVER_MARGIN_CALL_REASON
            state = None
        else:
            state = {
                "lowest_price": pos.get("lowest_price"),
                "trailing_armed": pos.get("trailing_armed"),
                "trailing_stop": pos.get("trailing_stop"),
            }
            act, pnl_pct, new_state = pes.evaluate_short_exit(
                avg_price,
                mark,
                state,
                stop_loss_pct=STOP_LOSS_PCT,
                activate_pct=TRAILING_ACTIVATE_PCT,
                trail_distance_pct=TRAILING_DISTANCE_PCT,
            )
            pos.update(new_state)
            pos["current_price"] = mark
            cover_reason = COVER_TRAILING_REASON if act == "SELL_TRAILING" else COVER_STOP_LOSS_REASON
            if act == "HOLD":
                dec = {
                    "ts": ppr._now(),
                    "decision_id": decision_id,
                    "arm": ARM_ID,
                    "ticker": ticker,
                    "action": "HOLD",
                    "reason": "SM_HOLD_SHORT_OPEN",
                    "pnl_pct": round(pnl_pct, 4),
                }
                _append_jsonl(p["decisions"], dec)
                return dec

        shares_to_cover = abs(pes._f(pos.get("shares")))
        cash_before = pes._f(portfolio.get("cash"))
        realized, gross_cost, after = pes._cover_short(portfolio, ticker, shares_to_cover, mark)
        action = "COVER"
        reason = cover_reason
        qty = shares_to_cover
        value = gross_cost
        realized_pnl_fill = realized
        execution_id = f"SMEX-{uuid.uuid4().hex[:16].upper()}"
        _append_jsonl(
            p["trades"],
            {
                "ts": ppr._now(),
                "ticker": ticker,
                "action": "COVER_PAPER",
                "reason": reason,
                "shares": qty,
                "price": mark,
                "decision_id": decision_id,
                "arm": ARM_ID,
                "execution_id": execution_id,
                "realized_pnl": realized_pnl_fill,
                "gross": gross_cost,
                "cash_before": cash_before,
                "cash_after": pes._f(portfolio.get("cash")),
            },
        )
    else:
        score = snap.get("score")
        bearish = score is not None and float(score) <= SHORT_ENTRY_MAX_SCORE
        already_long = bool(pos and pes._f(pos.get("shares")) > 0)
        # Note: deliberately NOT gating on snap["eligible"] here — that flag
        # is computed for the long/BUY path (checked directly: the lowest-
        # score, most bearish-looking tickers in real data all come back
        # eligible=false, which would silently block every short candidate
        # this rule is meant to catch). Its semantics for a short entry are
        # unverified, so it's left out rather than reused on a guess.
        if (
            mark_ok
            and bearish
            and not already_long
            and _open_short_position_count(portfolio) < MAX_SHORT_POSITIONS
            and pes.margin_utilization_pct(portfolio) < MAX_MARGIN_UTILIZATION_PCT
        ):
            cash = pes._f(portfolio.get("cash"))
            investable = max(0.0, cash - MIN_CASH_RESERVE)
            notional = min(MAX_TRADE_USD, investable * 0.25)
            if notional >= MIN_TRADE_USD:
                cash_before = cash
                shares, after = pes._open_short(
                    portfolio, ticker, notional, mark, margin_requirement_pct=MARGIN_REQUIREMENT_PCT
                )
                if shares > 0:
                    action = "SHORT"
                    reason = SHORT_OPEN_REASON
                    qty = shares
                    value = notional
                    execution_id = f"SMEX-{uuid.uuid4().hex[:16].upper()}"
                    _append_jsonl(
                        p["trades"],
                        {
                            "ts": ppr._now(),
                            "ticker": ticker,
                            "action": "SHORT_PAPER",
                            "reason": reason,
                            "shares": qty,
                            "price": mark,
                            "decision_id": decision_id,
                            "arm": ARM_ID,
                            "execution_id": execution_id,
                            "cash_before": cash_before,
                            "cash_after": pes._f(portfolio.get("cash")),
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
        "score": snap.get("score"),
        "mark_price": mark if mark_ok else None,
        "realized_pnl": realized_pnl_fill,
    }
    _append_jsonl(p["decisions"], dec)
    return dec


def run_short_margin_cycle() -> dict[str, Any]:
    """Runs one full cycle for the isolated short/margin arm. Returns a
    summary dict (account_value, cash, margin_reserved, open_shorts,
    reconciliation_pass) — the same shape spirit as V1/V2/V3's cycle
    summaries, so it slots into the same kind of health/reporting check."""
    p = _paths()
    portfolio = _load_or_create_portfolio(p["portfolio"])
    tickers = _load_watchlist()
    marks = ppr.default_mark_provider(tickers)

    held_tickers = list((portfolio.get("positions") or {}).keys())
    all_tickers = sorted(set(tickers) | set(held_tickers))

    for ticker in all_tickers:
        snap = marks.get(ticker) or {"mark_price": None, "score": None, "eligible": None}
        decision_id = f"SM-{ticker}-{uuid.uuid4().hex[:12].upper()}"
        _decide_and_execute_ticker(
            portfolio=portfolio, ticker=ticker, snap=snap, p=p, decision_id=decision_id
        )

    mark_prices = {t: pes._f(s.get("mark_price")) for t, s in marks.items()}
    mark_meta = {
        t: {"mark_freshness": s.get("mark_freshness"), "mark_timestamp": s.get("mark_timestamp")}
        for t, s in marks.items()
    }
    account_value, invested = ppr.portfolio_mtm(portfolio, mark_prices, mark_meta=mark_meta)
    portfolio["account_value"] = account_value
    portfolio["open_positions_value"] = invested
    portfolio["updated_at"] = ppr._now()

    cash = pes._f(portfolio.get("cash"))
    margin_reserved = pes._f(portfolio.get("margin_reserved"))
    realized_pnl = pes._f(portfolio.get("realized_pnl"))
    unrealized_pnl = pes._f(portfolio.get("unrealized_pnl"))
    # Reconciliation: starting_capital + realized == cash + sum(shares*avg_price)
    # (portfolio_mtm's own "invested" aggregate already equals sum(shares*avg_price)).
    expected = pes._f(portfolio.get("starting_capital"), STARTING_CAPITAL) + realized_pnl
    actual = cash + invested
    reconciliation_pass = abs(expected - actual) < 0.01

    p["portfolio"].parent.mkdir(parents=True, exist_ok=True)
    p["portfolio"].write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")

    return {
        "arm": ARM_ID,
        "account_value": account_value,
        "cash": cash,
        "margin_reserved": margin_reserved,
        "margin_utilization_pct": round(pes.margin_utilization_pct(portfolio), 4),
        "open_shorts": _open_short_position_count(portfolio),
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "reconciliation_pass": reconciliation_pass,
        "reconciliation_expected": round(expected, 4),
        "reconciliation_actual": round(actual, 4),
    }


if __name__ == "__main__":
    import pprint

    pprint.pprint(run_short_margin_cycle())
