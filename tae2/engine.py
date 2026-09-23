"""Paper execution: bring the Alpaca paper account to the strategy's targets.

Same path as the backtest: the same strategy function, on the same validated
prices, decides at a completed month-end close, and the engine trades on a
later session. Each decision date is executed at most once (recorded in
state/engine.json), so running the engine daily is safe and a missed day
catches up on the next run. Without --submit nothing is sent.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from tae2 import data, rebalance, strategies
from tae2.backtest import month_ends
from tae2.broker import Account, AlpacaPaper, BrokerError, Position

STATE = Path("state/engine.json")
JOURNAL = Path("state/runs.jsonl")
FILL_TIMEOUT_S = 120

# Strategies that passed the gates, plus the benchmark. All rebalance at month-end:
# every-other-week results depended on which weeks were picked (Sharpe 0.88 vs
# 0.76 shifted by one week) and weekly matched monthly, so faster adds only turnover.
# The dual-momentum blend was dropped: only one lookback beats 60/40.
DEPLOYABLE: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "core_gtaa_50": lambda p: strategies.core_plus_sleeve(p, strategies.gtaa(p, sma_months=6), core_weight=0.5),
    "core_gtaa": lambda p: strategies.core_plus_sleeve(p, strategies.gtaa(p, sma_months=6), core_weight=0.7),
    "sixty_forty": lambda p: strategies.fixed_mix(p, {"SPY": 0.6, "IEF": 0.4}),
}
DEFAULT_STRATEGY = "core_gtaa_50"


OFFLINE_EQUITY = 30_000.0


class OfflineAccount:
    """Stand-in for a dry run before an Alpaca account exists: an empty $30k book."""

    def account(self) -> Account:
        return Account(OFFLINE_EQUITY, OFFLINE_EQUITY, OFFLINE_EQUITY, "OFFLINE", False)

    def positions(self) -> list[Position]:
        return []

    def open_orders(self) -> list[dict]:
        return []


def _broker_or_offline(submit: bool):
    try:
        return AlpacaPaper.from_env()
    except BrokerError:
        if submit:
            raise
        return OfflineAccount()


def latest_decision(prices: pd.DataFrame, now: datetime) -> pd.Timestamp:
    """Most recent month-end whose month is over.

    The newest row of live data is always the latest closed session, so the
    last "month-end" in it is only real once a later month has started.
    """
    today = now.astimezone(data.NY).date()
    ends = month_ends(prices.index)
    complete = [d for d in ends if (d.year, d.month) < (today.year, today.month)]
    if not complete:
        raise ValueError("no completed month-end in the data")
    return complete[-1]


def targets_for(name: str, prices: pd.DataFrame, decision: pd.Timestamp) -> pd.Series:
    weights = DEPLOYABLE[name](prices)
    if decision not in weights.index:
        raise ValueError(f"{name} has no decision for {decision.date()}")
    row = weights.loc[decision]
    return row[row > 1e-9]


@dataclass
class RunReport:
    strategy: str
    decision_date: str
    submitted: bool
    status: str
    orders: list[dict] = field(default_factory=list)
    detail: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


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


def _wait_for_fills(broker: AlpacaPaper, ids: list[str]) -> list[dict]:
    deadline = time.monotonic() + FILL_TIMEOUT_S
    pending = set(ids)
    done: list[dict] = []
    while pending and time.monotonic() < deadline:
        for oid in list(pending):
            o = broker.order(oid)
            if o["status"] in {"filled", "canceled", "rejected", "expired"}:
                done.append(o)
                pending.discard(oid)
        if pending:
            time.sleep(2)
    if pending:
        raise BrokerError(f"{len(pending)} sell orders not filled within {FILL_TIMEOUT_S}s")
    bad = [o for o in done if o["status"] != "filled"]
    if bad:
        raise BrokerError(f"sell orders not filled: {[(o['symbol'], o['status']) for o in bad]}")
    return done


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
