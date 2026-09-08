#!/usr/bin/env python3
"""
Regression test for the yfinance hard-timeout fix (2026-09-08): a single
yf.download() call hung the whole hourly cycle for 2+ hours on a stalled
Yahoo Finance TCP connection — yfinance's own timeout= kwarg (default 10s)
did not actually bound the call. _yfinance_hard_timeout() uses SIGALRM to
bound any call regardless of what yfinance/curl_cffi is doing internally.
"""

from __future__ import annotations

import time
import unittest

import live_bot


class HardTimeoutTest(unittest.TestCase):
    def test_fast_call_completes_normally(self) -> None:
        with live_bot._yfinance_hard_timeout(seconds=5):
            time.sleep(0.1)
        # no exception, no hang -- reaching here is the assertion

    def test_slow_call_is_interrupted_within_bound(self) -> None:
        started = time.monotonic()
        with self.assertRaises(live_bot._YfinanceCallTimedOut):
            with live_bot._yfinance_hard_timeout(seconds=1):
                time.sleep(30)  # simulates the real hung network call
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0, "must be interrupted near the configured bound, not run to completion")

    def test_timeout_is_cleared_after_normal_exit_no_leftover_alarm(self) -> None:
        with live_bot._yfinance_hard_timeout(seconds=1):
            pass
        # If the alarm were left armed, this sleep would raise after 1s.
        time.sleep(1.5)

    def test_exception_inside_the_block_still_clears_the_alarm(self) -> None:
        with self.assertRaises(ValueError):
            with live_bot._yfinance_hard_timeout(seconds=1):
                raise ValueError("some other real error")
        time.sleep(1.5)  # would raise _YfinanceCallTimedOut if alarm leaked


if __name__ == "__main__":
    unittest.main()
