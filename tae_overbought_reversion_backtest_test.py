#!/usr/bin/env python3
"""Regression coverage for tae_overbought_reversion_backtest.py's pure
signal function — roadmap item 6 (2026-09-14)."""

from __future__ import annotations

import math
import unittest

import tae_overbought_reversion_backtest as short_bt


def _noisy_baseline(n: int = 34) -> list[float]:
    return [100.0 + 0.5 * math.sin(i * 0.9) for i in range(n)]


class ShortEntrySignalTest(unittest.TestCase):
    def test_insufficient_history_never_enters(self) -> None:
        self.assertFalse(short_bt.short_entry_signal([100.0] * 5)["entry"])

    def test_extreme_spike_up_triggers_short_entry(self) -> None:
        closes = _noisy_baseline() + [110.0, 115.0, 120.0]
        result = short_bt.short_entry_signal(closes)
        self.assertTrue(result["entry"])
        self.assertGreaterEqual(result["z"], short_bt.Z_SHORT_THRESHOLD)
        self.assertGreaterEqual(result["rsi"], short_bt.RSI_OVERBOUGHT)

    def test_mild_rise_within_normal_noise_does_not_trigger(self) -> None:
        closes = _noisy_baseline() + [100.3, 100.5, 100.6]
        self.assertFalse(short_bt.short_entry_signal(closes)["entry"])

    def test_oversold_series_does_not_trigger_a_short(self) -> None:
        """Sanity: this is the mirror of the LONG mean-reversion entry --
        a deep drop must never itself trigger a short (that would be the
        opposite, already-covered signal)."""
        closes = _noisy_baseline() + [95.0, 92.0, 88.0]
        self.assertFalse(short_bt.short_entry_signal(closes)["entry"])


if __name__ == "__main__":
    unittest.main()
