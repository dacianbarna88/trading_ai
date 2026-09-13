#!/usr/bin/env python3
"""Regression coverage for tae_macro_regime.py's pure signal math.

Context: Sprint 3, Phase 1 — testing whether VIX/market-trend/yield-curve
regime actually splits the existing technical score's real win rate
before wiring anything into V3's RegimeGrid (currently hard-coded
UNKNOWN in production).
"""

from __future__ import annotations

import unittest

import tae_macro_regime as macro


class ClassifyTrendTest(unittest.TestCase):
    def test_insufficient_history_is_unknown(self) -> None:
        self.assertEqual(macro.classify_trend([100.0] * 5, window=200), "UNKNOWN")

    def test_price_above_sma_is_bull(self) -> None:
        closes = [100.0] * 199 + [110.0]
        self.assertEqual(macro.classify_trend(closes, window=200), "BULL")

    def test_price_below_sma_is_bear(self) -> None:
        closes = [100.0] * 199 + [90.0]
        self.assertEqual(macro.classify_trend(closes, window=200), "BEAR")


class VixTercileTest(unittest.TestCase):
    def test_insufficient_history_is_unknown(self) -> None:
        self.assertEqual(macro.vix_tercile([15.0] * 10), "UNKNOWN")

    def test_low_current_vix_vs_history_is_low(self) -> None:
        hist = list(range(15, 45)) + [10.0]  # trailing history 15-44, then a low print
        self.assertEqual(macro.vix_tercile(hist), "LOW")

    def test_high_current_vix_vs_history_is_high(self) -> None:
        hist = list(range(15, 45)) + [60.0]
        self.assertEqual(macro.vix_tercile(hist), "HIGH")

    def test_mid_range_current_vix_is_med(self) -> None:
        hist = [float(x) for x in range(15, 45)] + [29.5]
        self.assertEqual(macro.vix_tercile(hist), "MED")


class YieldCurveTest(unittest.TestCase):
    def test_missing_inputs_is_unknown_slope_and_regime(self) -> None:
        self.assertIsNone(macro.yield_curve_slope(None, 4.0))
        self.assertEqual(macro.curve_regime(None), "UNKNOWN")

    def test_positive_slope_is_normal(self) -> None:
        slope = macro.yield_curve_slope(4.5, 4.0)
        self.assertEqual(macro.curve_regime(slope), "NORMAL")

    def test_negative_slope_is_inverted(self) -> None:
        slope = macro.yield_curve_slope(3.5, 4.0)
        self.assertEqual(macro.curve_regime(slope), "INVERTED")


if __name__ == "__main__":
    unittest.main()
