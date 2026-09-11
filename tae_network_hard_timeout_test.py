#!/usr/bin/env python3
"""Regression test for the shared SIGALRM hard timeout (2026-09-09): after
fixing the same bug class in live_bot.py (a stalled yfinance call hanging
the whole hourly cycle), an audit found three more unprotected network
calls in the same hourly critical path -- research/market_scanner.py's
get_sp500_tickers() (raw urllib.request.urlopen, no bound), tae_paper_
execution.py's _fetch_atr_pct_for_sizing (yf.Ticker().history()), and
core/market_data_layer.py's _fetch_yf_download (yf.download()) -- any one
of which could reproduce the 2+ hour hang. This covers the shared helper
they were all wired onto.
"""

from __future__ import annotations

import time
import unittest

from tae_network_hard_timeout import NetworkCallTimedOut, hard_timeout


class HardTimeoutTest(unittest.TestCase):
    def test_fast_call_completes_normally(self) -> None:
        with hard_timeout(5):
            time.sleep(0.1)

    def test_slow_call_is_interrupted_within_bound(self) -> None:
        started = time.monotonic()
        with self.assertRaises(NetworkCallTimedOut):
            with hard_timeout(1):
                time.sleep(30)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0)

    def test_timeout_is_cleared_after_normal_exit_no_leftover_alarm(self) -> None:
        with hard_timeout(1):
            pass
        time.sleep(1.5)

    def test_exception_inside_the_block_still_clears_the_alarm(self) -> None:
        with self.assertRaises(ValueError):
            with hard_timeout(1):
                raise ValueError("some other real error")
        time.sleep(1.5)


class WiringSmokeTest(unittest.TestCase):
    def test_market_scanner_imports_hard_timeout(self) -> None:
        import inspect

        import research.market_scanner as ms

        source = inspect.getsource(ms.get_sp500_tickers)
        self.assertIn("hard_timeout", source)

    def test_paper_execution_atr_sizing_imports_hard_timeout(self) -> None:
        import inspect

        import tae_paper_execution as pe

        source = inspect.getsource(pe._fetch_atr_pct_for_sizing)
        self.assertIn("hard_timeout", source)

    def test_market_data_layer_fetch_imports_hard_timeout(self) -> None:
        import inspect

        import core.market_data_layer as mdl

        source = inspect.getsource(mdl._fetch_yf_download)
        self.assertIn("hard_timeout", source)


if __name__ == "__main__":
    unittest.main()
