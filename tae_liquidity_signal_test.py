#!/usr/bin/env python3
"""Regression coverage for tae_liquidity_signal.py — Sprint 3 Phase 2."""

from __future__ import annotations

import unittest

import tae_liquidity_signal as liq


class AverageVolumeTest(unittest.TestCase):
    def test_insufficient_history_is_none(self) -> None:
        self.assertIsNone(liq.average_volume([100.0] * 5))

    def test_excludes_the_latest_bar_from_its_own_average(self) -> None:
        volumes = [100.0] * 20 + [10000.0]  # a huge spike on the latest bar
        avg = liq.average_volume(volumes)
        self.assertAlmostEqual(avg, 100.0)


class RelativeVolumeTest(unittest.TestCase):
    def test_empty_series_is_none(self) -> None:
        self.assertIsNone(liq.relative_volume([]))

    def test_double_average_volume_gives_relative_two(self) -> None:
        volumes = [100.0] * 20 + [200.0]
        self.assertAlmostEqual(liq.relative_volume(volumes), 2.0)

    def test_zero_average_is_none_not_a_divide_by_zero_crash(self) -> None:
        volumes = [0.0] * 20 + [50.0]
        self.assertIsNone(liq.relative_volume(volumes))


if __name__ == "__main__":
    unittest.main()
