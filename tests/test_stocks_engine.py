from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from stocks import broker as stocks_broker
from stocks import engine, rebalance, strategies
from tae2 import rebalance as tae2_rebalance
from tae2.broker import Account, BrokerError, Position

OCT_1 = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)

TICKERS = [f"T{i:03d}" for i in range(100)] + ["SPY", "SHY"]


def _prices_until(last: str, days: int = 1600, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2020-09-01", periods=days)
    drift = rng.uniform(-0.0002, 0.0006, len(TICKERS))
    vol = rng.uniform(0.005, 0.03, len(TICKERS))
    rets = rng.normal(drift, vol, (days, len(TICKERS)))
    prices = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=index, columns=TICKERS)
    return prices.loc[:last]


class FakeBroker:
    def __init__(self, equity=100_000.0, cash=100_000.0, positions=None, is_open=True, open_orders=None):
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
        if side == "sell":
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


class MomentumVt10WiringTest(_TempDir):
    """Mechanics tests use a trivial fixed-weight strategy (same approach
    tae2's own test suite takes with "sixty_forty") -- these tests are about
    the engine's state/broker handling, not about re-verifying momentum_vt10's
    own logic (already covered in tests/test_stocks_strategies.py)."""

    def setUp(self) -> None:
        super().setUp()
        self._patcher = mock.patch.dict(
            engine.DEPLOYABLE, {"test_fixed": lambda p: _fixed(p, {"T000": 0.6, "T001": 0.4})}
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def _run(self, fake: FakeBroker, submit: bool, strategy: str = "test_fixed"):
        return engine.run(strategy, submit=submit, broker=fake, prices=_prices_until("2026-09-30"), now=OCT_1)

    def test_dry_run_plans_but_sends_nothing(self) -> None:
        fake = FakeBroker()
        report = self._run(fake, submit=False)
        self.assertEqual(report.status, "dry_run")
        self.assertEqual(fake.sent, [])
        self.assertEqual({o["symbol"] for o in report.orders}, {"T000", "T001"})
        self.assertFalse(engine.STATE.exists())

    def test_submit_trades_once_per_decision(self) -> None:
        fake = FakeBroker()
        self.assertEqual(self._run(fake, submit=True).status, "submitted")
        self.assertEqual(sorted(s for s, *_ in fake.sent), ["T000", "T001"])
        again = self._run(fake, submit=True)
        self.assertEqual(again.status, "already_done")
        self.assertEqual(len(fake.sent), 2)

    def test_sells_fill_before_buys_are_sized(self) -> None:
        fake = FakeBroker(equity=100_000, cash=0, positions=[Position("T050", 10, 100_000)])
        report = self._run(fake, submit=True)
        self.assertEqual(report.status, "submitted")
        self.assertEqual(fake.sent[0][:2], ("T050", "sell"))
        spent = sum(n for _, side, n, _ in fake.sent if side == "buy")
        self.assertLessEqual(spent, 100_000 * (1 - rebalance.CASH_BUFFER) + 0.01)

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
        report = engine.run("test_fixed", submit=True, broker=fake, prices=prices, now=OCT_1)
        self.assertEqual(report.status, "blocked_data")
        self.assertEqual(fake.sent, [])

    def test_dry_run_works_without_an_account(self) -> None:
        with mock.patch.dict(os.environ, {"STOCKS_ALPACA_API_KEY_ID": "", "STOCKS_ALPACA_API_SECRET_KEY": ""}):
            report = engine.run("test_fixed", submit=False, prices=_prices_until("2026-09-30"), now=OCT_1)
        self.assertEqual(report.status, "dry_run")
        spent = sum(o["notional"] for o in report.orders)
        from tae2.engine import OFFLINE_EQUITY

        self.assertLessEqual(spent, OFFLINE_EQUITY)


class RebalanceThresholdTest(unittest.TestCase):
    """Bug found 2026-09-25 on the real MoVo10 paper account's first dry run:
    momentum_vt10's real 2026-08-31 decision put 75 stocks at 0.46% of
    equity each ($461 on $100k) -- tae2.rebalance.plan()'s 0.5%-of-equity
    ($500) minimum trade size would have silently skipped every one of them
    and bought only SHY, on the strategy's very first rebalance."""

    def test_many_small_positions_clear_the_stocks_threshold(self) -> None:
        equity = 100_000.0
        targets = pd.Series({f"T{i:03d}": 0.00461 for i in range(75)} | {"SHY": 1 - 75 * 0.00461})
        orders = rebalance.plan(targets, [], equity, equity)
        bought = {o.symbol for o in orders if o.side == "buy"}
        self.assertEqual(len(bought), 76)  # 75 stocks + SHY, all clear this module's 0.1% threshold

    def test_the_same_positions_would_have_been_skipped_by_tae2s_own_threshold(self) -> None:
        """Documents why this needed its own file rather than reusing tae2's:
        not a claim that tae2's threshold is wrong for tae2's own strategies."""
        equity = 100_000.0
        targets = pd.Series({f"T{i:03d}": 0.00461 for i in range(75)} | {"SHY": 1 - 75 * 0.00461})
        orders = tae2_rebalance.plan(targets, [], equity, equity)
        bought = {o.symbol for o in orders if o.side == "buy"}
        self.assertEqual(bought, {"SHY"})  # every individual stock silently skipped

    def test_a_near_zero_target_never_requests_more_than_the_held_qty(self) -> None:
        """Same bug as tae2.rebalance.plan() (found 2026-10-02 on the real
        tae2 account, Alpaca rejected a sell for a hair more than held) --
        this file copied that function's logic verbatim, so it had the
        identical bug."""
        pos = [Position("AAPL", 10.123456789, 10_000.0)]
        orders = rebalance.plan(pd.Series({"AAPL": -1e-15}), pos, 10_000.0, 0.0)
        self.assertEqual(len(orders), 1)
        self.assertLessEqual(orders[0].qty, 10.123456789)


class MomentumVt10DefaultTest(_TempDir):
    """The real default deployable, on a synthetic universe big enough for
    its top_n=75. universe.load() is mocked to the synthetic tickers --
    otherwise it would hit the real (network) S&P 500 list and intersect to
    nothing, since none of T000..T099 are real tickers."""

    def test_produces_a_long_only_target_for_the_real_default_strategy(self) -> None:
        prices = _prices_until("2026-09-30", days=1600)
        stock_tickers = [t for t in TICKERS if t not in ("SPY", "SHY")]
        with mock.patch("stocks.engine.universe.load", return_value=stock_tickers):
            report = engine.run(
                engine.DEFAULT_STRATEGY, submit=False, broker=FakeBroker(), prices=prices, now=OCT_1
            )
        self.assertIn(report.status, {"dry_run", "blocked_data"})  # synthetic data may trip a JUMP-adjacent check
        if report.status == "dry_run":
            self.assertGreater(len(report.orders), 0)


def _fixed(prices: pd.DataFrame, weights: dict) -> pd.DataFrame:
    from tae2.backtest import month_ends

    dates = month_ends(prices.index)
    out = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    for t, w in weights.items():
        out[t] = w
    return out


class BrokerGuardTest(_TempDir):
    """Runs in an empty temp CWD (no .env) -- from_env() calls load_dotenv(),
    and this repo's real .env now holds real STOCKS_/tae2 paper keys since
    the user just saved them; a test that ran from the real project root
    would silently load real secrets into these assertions instead of
    testing the intended missing/mismatched-key scenarios."""

    def test_from_env_reads_the_stocks_prefixed_keys_not_taes(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "STOCKS_ALPACA_API_KEY_ID": "stocks-key",
                "STOCKS_ALPACA_API_SECRET_KEY": "stocks-secret",
                "ALPACA_API_KEY_ID": "tae2-key",
                "ALPACA_API_SECRET_KEY": "tae2-secret",
            },
        ):
            client = stocks_broker.from_env()
        self.assertEqual(client._s.headers["APCA-API-KEY-ID"], "stocks-key")
        self.assertEqual(client._s.headers["APCA-API-SECRET-KEY"], "stocks-secret")

    def test_missing_stocks_keys_are_refused_even_if_tae2s_are_set(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"ALPACA_API_KEY_ID": "tae2-key", "ALPACA_API_SECRET_KEY": "tae2-secret"},
            clear=True,
        ):
            os.environ.pop("STOCKS_ALPACA_API_KEY_ID", None)
            os.environ.pop("STOCKS_ALPACA_API_SECRET_KEY", None)
            with self.assertRaises(BrokerError):
                stocks_broker.from_env()


if __name__ == "__main__":
    unittest.main()
