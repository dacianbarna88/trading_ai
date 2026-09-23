"""New, isolated parallel-paper arm: long-horizon accounting quality.

Context (roadmap item 2, 2026-09-14): Sprint 3 found the Piotroski
F-Score adaptation (tae_accounting_quality_score.py, fed by real
multi-quarter statements via tae_financial_statements_snapshot.py) has
NO correlation with outcomes at V1/V2/V3's ~7-day holding period
(Spearman -0.05), but a real, monotonic +0.24 to +0.26 correlation at
6-12 month horizons (tae_accounting_quality_horizon_backtest.py: HIGH-
quality tercile avg return 111% vs LOW's 43% at 365 days). The signal is
real; V1/V2/V3 just can't express a 6-12 month thesis. This arm can.

Strategy: top-10 equal-weight F-Score portfolio, monthly rebalance,
low turnover (sell what falls out of the top 10, buy new entrants,
leave continuing holdings alone rather than force-rebalancing weights —
nothing in the Sprint 3 backtest justifies precise weight maintenance
over simple in/out membership).

Cadence: no new scheduler. Piggybacks on the same hourly launchd job
every other arm uses (tae_hourly_refresh.sh) — self-gates on its own
`last_rebalance_at` timestamp, stored on portfolio.json, and only runs
the real selection+trade logic once REBALANCE_INTERVAL_DAYS have
passed; every other hourly invocation is mark-to-market only.

Isolation, same pattern as tae_parallel_paper_mean_reversion.py /
tae_parallel_paper_short_margin.py: this module owns its own portfolio/
journals under runtime_outputs/parallel_paper/exp_quality_longterm/, is
never imported by V1/V2/V3/exp_short_margin/exp_mean_reversion, and
never imports their decision code. Reuses only already-generic shared
infra (tae_parallel_paper_runtime's default_mark_provider/portfolio_mtm/
load_portfolio, tae_paper_execution's _buy_shares/_sell_shares).

PAPER_ONLY / NO_BROKER / NO_EXECUTION, same as every other arm.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import tae_accounting_quality_score as fscore
import tae_financial_statements_snapshot as fss
import tae_paper_execution as pe
import tae_parallel_paper_runtime as ppr
import tae_slow_call_guard as slow_call_guard

ARM_ID = "exp_quality_longterm"
ARM_DIR = Path("runtime_outputs/parallel_paper") / ARM_ID
STARTING_CAPITAL = 30000.0
MIN_CASH_RESERVE = 500.0

TARGET_HOLDINGS = 10
MIN_SCOREABLE = 6  # of 9 F-Score criteria — excludes ETFs and data-sparse tickers
REBALANCE_INTERVAL_DAYS = 30.0

BUY_REASON = "QLT_TOP_N_ENTRY"
SELL_REASON = "QLT_FELL_OUT_OF_TOP_N"


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
    return ["AAPL", "MSFT", "JPM", "XOM", "KO"]


def _load_or_create_portfolio(path: Path) -> dict[str, Any]:
    portfolio = ppr.load_portfolio(path, starting=STARTING_CAPITAL, arm=ARM_ID)
    portfolio.setdefault("mode", "QUALITY_LONGTERM_EXPERIMENTAL")
    portfolio.setdefault("last_rebalance_at", None)
    return portfolio


def select_top_n(
    scores: dict[str, float | None], *, n: int = TARGET_HOLDINGS
) -> list[str]:
    """Pure selection function: highest-`score` tickers first, ties broken
    by ticker name for determinism. None scores are never eligible
    (unscoreable, e.g. ETFs or too little statement data) — never treated
    as worst-but-included."""
    eligible = [(t, s) for t, s in scores.items() if s is not None]
    ranked = sorted(eligible, key=lambda ts: (-ts[1], ts[0]))
    return [t for t, _ in ranked[:n]]


def _is_rebalance_due(portfolio: dict[str, Any], *, now: str) -> bool:
    last = portfolio.get("last_rebalance_at")
    if not last:
        return True
    try:
        from datetime import datetime

        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (now_dt - last_dt).total_seconds() >= REBALANCE_INTERVAL_DAYS * 86400.0


def compute_eligible_scores(tickers: list[str]) -> dict[str, float]:
    """F-Score for every ticker with enough real statement data to trust
    (scoreable >= MIN_SCOREABLE of 9 criteria) — excludes ETFs (no
    financial statements at all, e.g. SPY/QQQ/DIA, confirmed in Sprint 3)
    and any ticker too data-sparse. Pure filtering logic over one
    snapshot fetch, kept separate from the fetch itself for testability."""
    snapshot = fss.fetch_statements(tickers)
    filtered: dict[str, float] = {}
    for t in tickers:
        with slow_call_guard.warn_if_slow(f"[quality_longterm] SLOW compute_f_score ticker={t}"):
            result = fscore.compute_f_score(snapshot.get(t) or {})
        if result["score"] is not None and result["scoreable"] >= MIN_SCOREABLE:
            filtered[t] = result["score"]
    return filtered


def _rebalance(portfolio: dict[str, Any], marks: dict[str, dict[str, Any]], p: dict[str, Path]) -> None:
    tickers = _load_watchlist()
    filtered = compute_eligible_scores(tickers)

    target_tickers = set(select_top_n(filtered, n=TARGET_HOLDINGS))
    held_tickers = {t for t, pos in (portfolio.get("positions") or {}).items() if pe._f(pos.get("shares")) > 0}

    for ticker in held_tickers - target_tickers:
        snap = marks.get(ticker) or {}
        mark_ok, mark_status, mark = ppr._mark_is_usable(snap)
        if not mark_ok:
            continue
        pos = portfolio["positions"][ticker]
        shares = pe._f(pos.get("shares"))
        cash_before = pe._f(portfolio.get("cash"))
        realized, gross, _after = pe._sell_shares(portfolio, ticker, shares, mark)
        execution_id = f"QLTEX-{uuid.uuid4().hex[:16].upper()}"
        _append_jsonl(
            p["trades"],
            {
                "ts": ppr._now(),
                "ticker": ticker,
                "action": "SELL_PAPER",
                "reason": SELL_REASON,
                "shares": shares,
                "price": mark,
                "arm": ARM_ID,
                "execution_id": execution_id,
                "realized_pnl": realized,
                "gross_proceeds": gross,
                "cash_before": cash_before,
                "cash_after": pe._f(portfolio.get("cash")),
            },
        )

    account_value = pe._f(portfolio.get("account_value"), pe._f(portfolio.get("cash")))
    new_entries = target_tickers - held_tickers
    blocked_entries: dict[str, str] = {}
    if new_entries:
        target_notional = account_value / TARGET_HOLDINGS if TARGET_HOLDINGS else 0.0
        for ticker in new_entries:
            snap = marks.get(ticker) or {}
            mark_ok, mark_status, mark = ppr._mark_is_usable(snap)
            if not mark_ok or mark <= 0:
                continue
            cash = pe._f(portfolio.get("cash"))
            notional = min(target_notional, max(0.0, cash - MIN_CASH_RESERVE))
            if notional <= 0:
                continue
            cash_before = cash
            shares, _after, gate_reason = ppr.gated_buy_shares(portfolio, ticker, notional, mark, snap=snap)
            if gate_reason != "OK":
                blocked_entries[ticker] = gate_reason
                continue
            if shares > 0:
                execution_id = f"QLTEX-{uuid.uuid4().hex[:16].upper()}"
                _append_jsonl(
                    p["trades"],
                    {
                        "ts": ppr._now(),
                        "ticker": ticker,
                        "action": "BUY_PAPER",
                        "reason": BUY_REASON,
                        "shares": shares,
                        "price": mark,
                        "arm": ARM_ID,
                        "execution_id": execution_id,
                        "cash_before": cash_before,
                        "cash_after": pe._f(portfolio.get("cash")),
                        "f_score": filtered.get(ticker),
                    },
                )

    # An entry the shared buy gate blocked (closed session / stale mark) must
    # not wait a whole REBALANCE_INTERVAL_DAYS: leave the rebalance due so the
    # next hourly run retries it.
    if not blocked_entries:
        portfolio["last_rebalance_at"] = ppr._now()
    _append_jsonl(
        p["decisions"],
        {
            "ts": ppr._now(),
            "arm": ARM_ID,
            "action": "REBALANCE",
            "target_tickers": sorted(target_tickers),
            "sold": sorted(held_tickers - target_tickers),
            "bought": sorted(new_entries - set(blocked_entries)),
            "blocked_entries": blocked_entries,
            "scoreable_universe": len(filtered),
            "watchlist_size": len(tickers),
        },
    )


def run_quality_longterm_cycle() -> dict[str, Any]:
    """Runs one cycle for the isolated long-horizon quality arm. Most
    hourly invocations are mark-to-market only (see _is_rebalance_due) —
    the real selection+trade logic only runs once REBALANCE_INTERVAL_DAYS
    have passed since the last rebalance."""
    p = _paths()
    portfolio = _load_or_create_portfolio(p["portfolio"])
    tickers = _load_watchlist()
    held_tickers = list((portfolio.get("positions") or {}).keys())
    all_tickers = sorted(set(tickers) | set(held_tickers))

    marks = ppr.default_mark_provider(all_tickers)
    now = ppr._now()

    rebalanced = False
    if _is_rebalance_due(portfolio, now=now):
        _rebalance(portfolio, marks, p)
        rebalanced = True
    else:
        _append_jsonl(
            p["decisions"],
            {"ts": now, "arm": ARM_ID, "action": "HOLD", "reason": "QLT_NOT_DUE_FOR_REBALANCE"},
        )

    mark_prices = {t: pe._f(s.get("mark_price")) for t, s in marks.items()}
    mark_meta = {
        t: {"mark_freshness": s.get("mark_freshness"), "mark_timestamp": s.get("mark_timestamp")}
        for t, s in marks.items()
    }
    account_value, invested = ppr.portfolio_mtm(portfolio, mark_prices, mark_meta=mark_meta)
    portfolio["account_value"] = account_value
    portfolio["open_positions_value"] = invested
    portfolio["updated_at"] = now

    cash = pe._f(portfolio.get("cash"))
    realized_pnl = pe._f(portfolio.get("realized_pnl"))
    expected = pe._f(portfolio.get("starting_capital"), STARTING_CAPITAL) + realized_pnl
    actual = cash + invested
    reconciliation_pass = abs(expected - actual) < 0.01

    p["portfolio"].parent.mkdir(parents=True, exist_ok=True)
    p["portfolio"].write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")

    return {
        "arm": ARM_ID,
        "rebalanced": rebalanced,
        "account_value": account_value,
        "cash": cash,
        "open_positions": len([x for x in (portfolio.get("positions") or {}).values() if pe._f(x.get("shares")) > 0]),
        "realized_pnl": realized_pnl,
        "unrealized_pnl": pe._f(portfolio.get("unrealized_pnl")),
        "reconciliation_pass": reconciliation_pass,
        "reconciliation_expected": round(expected, 4),
        "reconciliation_actual": round(actual, 4),
    }


if __name__ == "__main__":
    import pprint

    pprint.pprint(run_quality_longterm_cycle())
