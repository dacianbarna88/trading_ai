#!/usr/bin/env python3
"""Regression coverage for tae_sector_relative_strength.py — Sprint 3 Phase 3."""

from __future__ import annotations

import unittest

import tae_sector_relative_strength as srs


class TrailingReturnTest(unittest.TestCase):
    def test_insufficient_history_is_none(self) -> None:
        self.assertIsNone(srs.trailing_return_pct([100.0] * 5))

    def test_computes_pct_change_over_window(self) -> None:
        closes = [100.0] * 20 + [110.0]
        self.assertAlmostEqual(srs.trailing_return_pct(closes), 10.0)

    def test_zero_start_price_is_none_not_a_crash(self) -> None:
        closes = [0.0] * 20 + [10.0]
        self.assertIsNone(srs.trailing_return_pct(closes))


class RelativeStrengthTest(unittest.TestCase):
    def test_none_ticker_return_is_none(self) -> None:
        self.assertIsNone(srs.relative_strength(None, [1.0, 2.0]))

    def test_no_peer_data_is_none(self) -> None:
        self.assertIsNone(srs.relative_strength(5.0, []))
        self.assertIsNone(srs.relative_strength(5.0, [None, None]))

    def test_outpacing_sector_is_positive(self) -> None:
        rel = srs.relative_strength(10.0, [2.0, 3.0, 4.0])
        self.assertAlmostEqual(rel, 7.0)

    def test_lagging_sector_is_negative(self) -> None:
        rel = srs.relative_strength(1.0, [5.0, 6.0, 7.0])
        self.assertAlmostEqual(rel, -5.0)

    def test_none_values_in_peer_list_are_ignored(self) -> None:
        rel = srs.relative_strength(10.0, [None, 4.0, None, 6.0])
        self.assertAlmostEqual(rel, 5.0)


if __name__ == "__main__":
    unittest.main()
