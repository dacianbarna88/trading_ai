from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pandas as pd

from tae2 import broker as brk
from tae2 import engine, rebalance
from tae2.broker import Account, Position
from tests.helpers import random_prices

# 2026-10-01 11:00 New York: first session after the September month-end.
OCT_1 = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)


def _prices_until(last: str) -> pd.DataFrame:
    p = random_prices(days=1600, start="2020-09-01")
    return p.loc[:last]


class FakeBroker:
    def __init__(self, equity=10_000.0, cash=10_000.0, positions=None, is_open=True, open_orders=None):
        self.acct = Account(equity, cash, cash, "ACTIVE", False)
        self.pos = positions or []
        self.is_open = is_open
        self._open = open_orders or []
        self.sent: list[tuple] = []

    def account(self):
        return self.acct

    def positions(self):
        return self.pos

    def open_orders(self):
        return self._open

    def clock(self):
        return {"is_open": self.is_open}

    def submit(self, symbol, side, notional=None, qty=None):
        self.sent.append((symbol, side, notional, qty))
        if side == "sell":  # fills instantly; cash arrives, position shrinks
            held = {p.symbol: p for p in self.pos}[symbol]
            value = held.market_value * qty / held.qty
            self.pos = [p for p in self.pos if p.symbol != symbol] + (
                [Position(symbol, held.qty - qty, held.market_value - value)] if held.qty - qty > 1e-9 else []
            )
            self.acct = Account(self.acct.equity, self.acct.cash + value, self.acct.cash + value, "ACTIVE", False)
        return {"id": f"{symbol}-{len(self.sent)}"}

    def order(self, oid):
        return {"id": oid, "status": "filled", "symbol": oid.split("-")[0]}


class _TempDir(unittest.TestCase):
    def setUp(self) -> None:
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        self._tmp.cleanup()


class DecisionDateTest(unittest.TestCase):
    def test_uses_only_month_ends_whose_month_is_over(self) -> None:
        # Data through 2026-09-29 read on 2026-09-30: September isn't over yet.
        p = _prices_until("2026-09-29")
        on_sep_30 = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(engine.latest_decision(p, on_sep_30), pd.Timestamp("2026-08-31"))
        p = _prices_until("2026-09-30")
        self.assertEqual(engine.latest_decision(p, OCT_1), pd.Timestamp("2026-09-30"))


class EngineTest(_TempDir):
    def _run(self, fake: FakeBroker, submit: bool, strategy: str = "sixty_forty"):
        return engine.run(strategy, submit=submit, broker=fake, prices=_prices_until("2026-09-30"), now=OCT_1)

    def test_dry_run_plans_but_sends_nothing(self) -> None:
        fake = FakeBroker()
        report = self._run(fake, submit=False)
        self.assertEqual(report.status, "dry_run")
        self.assertEqual(fake.sent, [])
        self.assertEqual({o["symbol"] for o in report.orders}, {"SPY", "IEF"})
        self.assertFalse(Path("state/engine.json").exists())

    def test_submit_trades_once_per_decision(self) -> None:
        fake = FakeBroker()
        self.assertEqual(self._run(fake, submit=True).status, "submitted")
        self.assertEqual(sorted(s for s, *_ in fake.sent), ["IEF", "SPY"])
        again = self._run(fake, submit=True)
        self.assertEqual(again.status, "already_done")
        self.assertEqual(len(fake.sent), 2)

    def test_sells_fill_before_buys_are_sized(self) -> None:
        fake = FakeBroker(equity=10_000, cash=0, positions=[Position("QQQ", 10, 10_000)])
        report = self._run(fake, submit=True)
        self.assertEqual(report.status, "submitted")
        self.assertEqual(fake.sent[0][:2], ("QQQ", "sell"))
        spent = sum(n for _, side, n, _ in fake.sent if side == "buy")
        self.assertLessEqual(spent, 10_000 * (1 - rebalance.CASH_BUFFER) + 0.01)

    def test_market_closed_blocks_submit(self) -> None:
        fake = FakeBroker(is_open=False)
        self.assertEqual(self._run(fake, submit=True).status, "blocked_market_closed")
        self.assertEqual(fake.sent, [])

    def test_open_orders_block_a_new_run(self) -> None:
        fake = FakeBroker(open_orders=[{"id": "x"}])
        self.assertEqual(self._run(fake, submit=True).status, "blocked_open_orders")

    def test_stale_data_blocks_before_touching_the_broker(self) -> None:
        fake = FakeBroker()
        prices = _prices_until("2026-09-29")  # 2026-09-30 bar missing on Oct 1
        report = engine.run("sixty_forty", submit=True, broker=fake, prices=prices, now=OCT_1)
        self.assertEqual(report.status, "blocked_data")
        self.assertEqual(fake.sent, [])

    def test_dry_run_works_without_an_account(self) -> None:
        with mock.patch.dict(os.environ, {"ALPACA_API_KEY_ID": "", "ALPACA_API_SECRET_KEY": ""}):
            report = engine.run("core_gtaa", submit=False, prices=_prices_until("2026-09-30"), now=OCT_1)
        self.assertEqual(report.status, "dry_run")
        spent = sum(o["notional"] for o in report.orders)
        self.assertLessEqual(spent, engine.OFFLINE_EQUITY)


class BrokerGuardTest(unittest.TestCase):
    def test_live_url_is_refused(self) -> None:
        with self.assertRaises(brk.BrokerError):
            brk.AlpacaPaper("k", "s", base_url="https://api.alpaca.markets", session=mock.Mock(headers={}))

    def test_missing_keys_are_refused(self) -> None:
        with self.assertRaises(brk.BrokerError):
            brk.AlpacaPaper("", "", session=mock.Mock(headers={}))

    def test_order_body_is_a_market_day_order(self) -> None:
        session = mock.Mock(headers={})
        session.request.return_value = mock.Mock(status_code=200, text='{"id": "1"}', json=lambda: {"id": "1"})
        client = brk.AlpacaPaper("k", "s", session=session)
        client.submit("SPY", "buy", notional=1234.567)
        method, url = session.request.call_args.args
        body = session.request.call_args.kwargs["json"]
        self.assertEqual((method, url), ("POST", "https://paper-api.alpaca.markets/v2/orders"))
        self.assertEqual(body, {"symbol": "SPY", "side": "buy", "type": "market", "time_in_force": "day", "notional": "1234.57"})


class PlanTest(unittest.TestCase):
    def test_small_differences_are_left_alone(self) -> None:
        pos = [Position("SPY", 1, 6_010), Position("IEF", 1, 3_990)]
        orders = rebalance.plan(pd.Series({"SPY": 0.6, "IEF": 0.4}), pos, 10_000, 0)
        self.assertEqual(orders, [])

    def test_positions_outside_the_targets_are_exited(self) -> None:
        pos = [Position("GLD", 3, 1_000)]
        orders = rebalance.plan(pd.Series({"SPY": 0.5}), pos, 10_000, 9_000)
        self.assertEqual((orders[0].symbol, orders[0].side, orders[0].qty), ("GLD", "sell", 3))
        self.assertEqual(orders[1].symbol, "SPY")

    def test_leverage_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            rebalance.plan(pd.Series({"SPY": 0.8, "IEF": 0.4}), [], 10_000, 10_000)


if __name__ == "__main__":
    unittest.main()
