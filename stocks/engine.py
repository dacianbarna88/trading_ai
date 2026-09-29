"""Paper execution: bring the stocks lab's OWN Alpaca paper account
("MoVo10") to momentum_vt10's latest targets.

Same path as tae2/engine.py (decide at a completed month-end close, trade
one session later, each decision executed at most once, so running daily
is safe and a missed day catches up on the next run). This file owns its
own state/journal files and DEPLOYABLE dict so it never touches tae2's --
same separation stocks/broker.py's own keys already guarantee.

KNOWN LIMITATION carried over from stocks/research.py: momentum_vt10 passed
every gate (2026-09-24, see output/stock_research_2026-09-24.md) on TODAY's
S&P 500 membership, not point-in-time membership -- see stocks/universe.py's
docstring. Paper trading here validates EXECUTION mechanics (order sizing,
sell-before-buy, fill handling), the same as tae2's own principle 5 ("Paper
validates execution, not edge") -- it does not retroactively resolve that
open question. No real money can ever be involved either way: tae2.broker
refuses any non-paper URL outright.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from tae2.broker import BrokerError
from tae2.engine import OfflineAccount, RunReport, _wait_for_fills, latest_decision  # noqa: F401 (re-exported)

from stocks import config, data, rebalance, strategies, universe
from stocks.broker import AlpacaPaper, from_env

STATE = Path("state/stocks_engine.json")
JOURNAL = Path("state/stocks_runs.jsonl")
TRADING_DAYS_PER_MONTH = 21

# The exact winning variant from the 2026-09-24 research run (63 variants
# tried, walk-forward on 2008-2016, judged on 2017-2026): lookback=9mo,
# top_n=75, vol target=10%/yr, 3-month vol window. Passed all 5 gates:
# Sharpe 0.92 (vs benchmark 0.84), MaxDD -27.0% (vs -43.2%), deflated
# Sharpe 1.00. Not re-derived from stocks.research.PLAN here on purpose --
# the deployed strategy is a fixed, reviewed choice, not whatever a rerun
# of the grid search happens to prefer (tae2's own core_gtaa_50 makes the
# same choice, for the same reason).
MOMENTUM_VT10_LOOKBACK_MONTHS = 9
MOMENTUM_VT10_TOP_N = 75
MOMENTUM_VT10_VOL_TARGET = 0.10
MOMENTUM_VT10_VOL_WINDOW_MONTHS = 3


def _momentum_vt10(prices: pd.DataFrame) -> pd.DataFrame:
    tickers = [t for t in universe.load(refresh=False) if t in prices.columns]
    base = strategies.momentum(
        prices,
        assets=tickers,
        cash=config.CASH,
        lookback_months=MOMENTUM_VT10_LOOKBACK_MONTHS,
        top_n=MOMENTUM_VT10_TOP_N,
    )
    return strategies.vol_target(
        prices,
        base,
        cash=config.CASH,
        target=MOMENTUM_VT10_VOL_TARGET,
        window=MOMENTUM_VT10_VOL_WINDOW_MONTHS * TRADING_DAYS_PER_MONTH,
    )


DEPLOYABLE: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {"momentum_vt10": _momentum_vt10}
DEFAULT_STRATEGY = "momentum_vt10"


def _broker_or_offline(submit: bool):
    try:
        return from_env()
    except BrokerError:
        if submit:
            raise
        return OfflineAccount()


def targets_for(name: str, prices: pd.DataFrame, decision: pd.Timestamp) -> pd.Series:
    weights = DEPLOYABLE[name](prices)
    if decision not in weights.index:
        raise ValueError(f"{name} has no decision for {decision.date()}")
    row = weights.loc[decision]
    return row[row > 1e-9]


def _read_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.is_file() else {}


def _write_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def _journal(report: RunReport) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(report)) + "\n")


def run(
    strategy: str,
    submit: bool,
    broker: AlpacaPaper | None = None,
    prices: pd.DataFrame | None = None,
    now: datetime | None = None,
) -> RunReport:
    """One engine pass. Fails closed: any data or broker problem stops before trading."""
    now = now or datetime.now(timezone.utc)
    if strategy not in DEPLOYABLE:
        raise ValueError(f"unknown strategy {strategy!r}; choose from {sorted(DEPLOYABLE)}")
    if prices is None:
        prices, issues = data.load(refresh=True, now=now)
    else:
        issues = data.validate(prices, now)
    blocking = [i for i in issues if i.kind != "JUMP"]
    decision = latest_decision(prices, now)
    report = RunReport(strategy, str(decision.date()), submit, "planned")
    if blocking:
        report.status = "blocked_data"
        report.detail = "; ".join(f"{i.ticker} {i.kind}: {i.detail}" for i in blocking)
        _journal(report)
        return report

    targets = targets_for(strategy, prices, decision)
    state = _read_state()
    if state.get(strategy) == str(decision.date()):
        report.status = "already_done"
        report.detail = f"decision {decision.date()} already executed"
        _journal(report)
        return report

    broker = broker or _broker_or_offline(submit)
    acct = broker.account()
    if acct.trading_blocked:
        report.status = "blocked_account"
        _journal(report)
        return report
    if broker.open_orders():
        report.status = "blocked_open_orders"
        report.detail = "orders from an earlier run are still open"
        _journal(report)
        return report
    orders = rebalance.plan(targets, broker.positions(), acct.equity, acct.cash)
    report.orders = [asdict(o) for o in orders]
    if not submit:
        report.status = "dry_run"
        _journal(report)
        return report
    if not broker.clock().get("is_open"):
        report.status = "blocked_market_closed"
        _journal(report)
        return report

    sells = [o for o in orders if o.side == "sell"]
    ids = [broker.submit(o.symbol, "sell", qty=o.qty)["id"] for o in sells]
    if ids:
        _wait_for_fills(broker, ids)
        acct = broker.account()
        orders = sells + [
            o for o in rebalance.plan(targets, broker.positions(), acct.equity, acct.cash) if o.side == "buy"
        ]
        report.orders = [asdict(o) for o in orders]
    for o in orders:
        if o.side == "buy":
            broker.submit(o.symbol, "buy", notional=o.notional)
    state[strategy] = str(decision.date())
    _write_state(state)
    report.status = "submitted"
    _journal(report)
    return report
