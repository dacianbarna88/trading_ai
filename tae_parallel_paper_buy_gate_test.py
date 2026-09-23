"""Regression coverage for the 2026-09-23 parallel-paper price incident.

Three causes, one test class each:
1. Every arm's BUY goes through one shared gate (V3 shipped without V1's
   closed-market check and bought on closed markets for a month).
2. default_mark_provider verifies a price's age instead of stamping every
   price fresh (Yahoo dropped the 2026-09-22 bar; Monday's close was traded
   as Tuesday's).
3. No silent fallbacks: the retired June signals.csv is never read, and a
   market-hours error means closed, not open.
"""

from __future__ import annotations

import ast
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import tae_parallel_paper_runtime as ppr

ROOT = Path(__file__).resolve().parent

# Modules whose arms place paper BUYs, and the only functions in them allowed
# to call the raw executors. Anything else must use gated_buy_shares /
# _execute_v2_buy.
GATED_MODULES = (
    "tae_parallel_paper_runtime.py",
    "tae_parallel_paper_mean_reversion.py",
    "tae_parallel_paper_quality_longterm.py",
    "tae_parallel_paper_short_margin.py",
)
ALLOWED_RAW_CALLERS = {
    "_buy_shares": {
        "gated_buy_shares",
        # Replays already-journaled fills to rebuild a book; places no new BUY.
        "reconstruct_isolated_portfolio_from_trades",
    },
    "execute_decision": {"_execute_v2_buy", "_execute_v2_close"},
}

OPEN_SNAP = {
    "mark_price": 100.0,
    "mark_freshness": "FRESH",
    "mark_status": "FRESH",
    "market_session": "OPEN",
    "data_fresh": True,
}
CLOSED_SNAP = dict(OPEN_SNAP, mark_freshness="MARKET_CLOSED", mark_status="MARKET_CLOSED", market_session="CLOSED")
STALE_SNAP = dict(OPEN_SNAP, mark_freshness="MARK_STALE", mark_status="MARK_STALE", data_fresh=False)


def _raw_executor_calls(path: Path) -> list[tuple[str, str, int]]:
    """(executor, enclosing function, line) for every raw executor call."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, str, int]] = []

    def visit(node: ast.AST, fn: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = fn
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            if isinstance(child, ast.Call):
                func = child.func
                attr = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if attr in ALLOWED_RAW_CALLERS:
                    found.append((attr, fn, child.lineno))
            visit(child, name)

    visit(tree, "<module>")
    return found


class SharedBuyGateTest(unittest.TestCase):
    def test_no_arm_calls_a_raw_executor_outside_the_gate(self) -> None:
        offenders = []
        for mod in GATED_MODULES:
            for executor, fn, line in _raw_executor_calls(ROOT / mod):
                if fn not in ALLOWED_RAW_CALLERS[executor]:
                    offenders.append(f"{mod}:{line} {fn}() calls {executor} directly")
        self.assertEqual(offenders, [], "route BUYs through gated_buy_shares / _execute_v2_buy")

    def test_gate_allows_only_a_fresh_mark_in_an_open_session(self) -> None:
        self.assertEqual(ppr.buy_allowed(OPEN_SNAP), (True, "OK"))
        self.assertEqual(ppr.buy_allowed(CLOSED_SNAP), (False, "MARKET_CLOSED"))
        self.assertEqual(ppr.buy_allowed(STALE_SNAP)[0], False)
        self.assertEqual(ppr.buy_allowed(None), (False, "MARK_UNAVAILABLE"))

    def test_blocked_gated_buy_never_touches_the_book(self) -> None:
        portfolio = {"cash": 10000.0, "positions": {}}
        with mock.patch.object(ppr.pe, "_buy_shares") as raw:
            shares, after, reason = ppr.gated_buy_shares(portfolio, "AMD", 1000.0, 100.0, snap=CLOSED_SNAP)
        raw.assert_not_called()
        self.assertEqual((shares, after, reason), (0.0, None, "MARKET_CLOSED"))
        self.assertEqual(portfolio, {"cash": 10000.0, "positions": {}})

    def test_open_gated_buy_reaches_the_executor(self) -> None:
        with mock.patch.object(ppr.pe, "_buy_shares", return_value=(10.0, {"shares": 10.0})) as raw:
            shares, _after, reason = ppr.gated_buy_shares({}, "AMD", 1000.0, 100.0, snap=OPEN_SNAP)
        raw.assert_called_once()
        self.assertEqual((shares, reason), (10.0, "OK"))

    def test_blocked_v2_buy_reports_the_reason_as_status(self) -> None:
        with mock.patch.object(ppr.pe, "execute_decision") as raw:
            order = ppr._execute_v2_buy(CLOSED_SNAP, {"action": "OPEN_CYCLE"}, {})
        raw.assert_not_called()
        # _run_v2_arm records reason = order["status"] for non-EXECUTED orders.
        self.assertEqual(order["status"], "MARKET_CLOSED")


class QualityRebalanceRetryTest(unittest.TestCase):
    def _rebalance(self, snap: dict) -> dict:
        import tae_parallel_paper_quality_longterm as qlt

        portfolio = {"cash": 10000.0, "account_value": 10000.0, "positions": {}, "last_rebalance_at": None}
        with mock.patch.object(qlt, "_load_watchlist", return_value=["AMD"]), mock.patch.object(
            qlt, "compute_eligible_scores", return_value={"AMD": 9.0}
        ), mock.patch.object(qlt, "_append_jsonl"):
            qlt._rebalance(portfolio, {"AMD": snap}, {"decisions": None, "trades": None})
        return portfolio

    def test_gate_blocked_entry_keeps_the_rebalance_due(self) -> None:
        # Otherwise a closed-market rebalance would skip the entry for a whole month.
        portfolio = self._rebalance(CLOSED_SNAP)
        self.assertEqual(portfolio["positions"], {})
        self.assertIsNone(portfolio["last_rebalance_at"])

    def test_completed_rebalance_is_stamped(self) -> None:
        portfolio = self._rebalance(OPEN_SNAP)
        self.assertIn("AMD", portfolio["positions"])
        self.assertIsNotNone(portfolio["last_rebalance_at"])


class _ProviderCase(unittest.TestCase):
    """default_mark_provider against a temp live_signals.csv."""

    # 2026-09-23 07:27 New York: US pre-open, the moment V1/V3 traded on Monday's close.
    PRE_OPEN = datetime(2026, 9, 23, 11, 27, tzinfo=timezone.utc)
    # 2026-09-23 11:00 New York: US session open.
    IN_SESSION = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)

    def setUp(self) -> None:
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        ppr._PRICE_BAR_DATE_CACHE.clear()

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        self._tmp.cleanup()
        ppr._PRICE_BAR_DATE_CACHE.clear()

    def _write_signals(self, written_at: datetime, rows: list[tuple[str, float]]) -> None:
        stamp = written_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        lines = ["Time,Ticker,Price,SMA50,RSI,Score,Signal"]
        lines += [f"{stamp},{t},{px},1,50,100,STRONG BUY" for t, px in rows]
        Path("live_signals.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _marks(self, now: datetime, bar_dates: dict[str, date | None], tickers: list[str]):
        return ppr.default_mark_provider(tickers, now=now, price_bar_date_fetcher=lambda _t: bar_dates)


class PriceFreshnessTest(_ProviderCase):
    def test_missing_previous_session_bar_is_stale_and_unusable(self) -> None:
        # The 2026-09-23 incident: pre-open, Yahoo's newest bar was Monday 09-21.
        self._write_signals(self.PRE_OPEN - timedelta(minutes=5), [("AMD", 615.52)])
        snap = self._marks(self.PRE_OPEN, {"AMD": date(2026, 9, 21)}, ["AMD"])["AMD"]
        self.assertEqual(snap["mark_stale_reason"], "PRICE_BAR_MISSING")
        self.assertEqual(snap["expected_session_date"], "2026-09-22")
        self.assertFalse(ppr._mark_is_usable(snap)[0])  # blocks exits too
        self.assertFalse(ppr.buy_allowed(snap)[0])

    def test_real_previous_close_before_the_open_is_market_closed_not_stale(self) -> None:
        self._write_signals(self.PRE_OPEN - timedelta(minutes=5), [("AMD", 624.0)])
        snap = self._marks(self.PRE_OPEN, {"AMD": date(2026, 9, 22)}, ["AMD"])["AMD"]
        self.assertIsNone(snap["mark_stale_reason"])
        self.assertEqual(snap["mark_freshness"], "MARKET_CLOSED")
        self.assertEqual(ppr._mark_is_usable(snap)[:2], (True, "MARKET_CLOSED"))
        self.assertEqual(ppr.buy_allowed(snap), (False, "MARKET_CLOSED"))

    def test_todays_bar_in_session_is_fresh(self) -> None:
        self._write_signals(self.IN_SESSION - timedelta(minutes=5), [("AMD", 618.0)])
        snap = self._marks(self.IN_SESSION, {"AMD": date(2026, 9, 23)}, ["AMD"])["AMD"]
        self.assertEqual(snap["mark_freshness"], "FRESH")
        self.assertEqual(ppr.buy_allowed(snap), (True, "OK"))

    def test_pre_open_row_read_after_the_open_is_stale(self) -> None:
        # 2026-09-23 16:37 local: the 16:00 file (written pre-open) still held
        # Monday's close, while Yahoo's bar date fetched after the open was today's.
        self._write_signals(datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc), [("AMD", 615.52)])
        now = datetime(2026, 9, 23, 13, 37, tzinfo=timezone.utc)
        snap = self._marks(now, {"AMD": date(2026, 9, 23)}, ["AMD"])["AMD"]
        self.assertEqual(snap["mark_stale_reason"], "SIGNAL_ROW_BEFORE_SESSION")
        self.assertFalse(ppr.buy_allowed(snap)[0])

    def test_old_signal_row_is_stale_even_with_a_current_bar(self) -> None:
        self._write_signals(self.IN_SESSION - timedelta(hours=5), [("AMD", 618.0)])
        snap = self._marks(self.IN_SESSION, {"AMD": date(2026, 9, 23)}, ["AMD"])["AMD"]
        self.assertEqual(snap["mark_stale_reason"], "SIGNAL_ROW_TOO_OLD")
        self.assertFalse(snap["data_fresh"])

    def test_unverifiable_price_date_fails_closed(self) -> None:
        self._write_signals(self.IN_SESSION - timedelta(minutes=5), [("AMD", 618.0)])
        snap = self._marks(self.IN_SESSION, {}, ["AMD"])["AMD"]
        self.assertEqual(snap["mark_stale_reason"], "PRICE_DATE_UNVERIFIED")
        self.assertFalse(ppr._mark_is_usable(snap)[0])

    def test_expected_session_skips_the_weekend(self) -> None:
        monday_pre_open = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(ppr._expected_session_date("SPY", monday_pre_open), date(2026, 9, 18))
        # London is already open at the same instant.
        self.assertEqual(ppr._expected_session_date("BP.L", monday_pre_open), date(2026, 9, 21))


class NoSilentFallbackTest(_ProviderCase):
    def test_retired_signals_csv_is_never_read(self) -> None:
        self._write_signals(self.IN_SESSION - timedelta(minutes=5), [("AMD", 618.0)])
        Path("signals.csv").write_text("Ticker,Price,SMA50,RSI,Score,Signal\nNVDA,212.56,198.7,51.0,100,wait\n")
        snap = self._marks(self.IN_SESSION, {"AMD": date(2026, 9, 23)}, ["AMD", "NVDA"])["NVDA"]
        self.assertIsNone(snap["mark_price"])
        self.assertEqual(snap["mark_freshness"], "MARK_UNAVAILABLE")

    def test_market_hours_error_means_closed(self) -> None:
        self._write_signals(self.IN_SESSION - timedelta(minutes=5), [("AMD", 618.0)])
        with mock.patch("markets.market_hours.is_ticker_market_open", side_effect=RuntimeError("boom")):
            snap = self._marks(self.IN_SESSION, {"AMD": date(2026, 9, 23)}, ["AMD"])["AMD"]
        self.assertEqual(snap["market_session"], "CLOSED")
        self.assertEqual(ppr.buy_allowed(snap), (False, "MARKET_CLOSED"))


if __name__ == "__main__":
    unittest.main()
