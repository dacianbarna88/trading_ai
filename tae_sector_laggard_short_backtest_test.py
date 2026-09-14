#!/usr/bin/env python3
"""Regression coverage for tae_sector_laggard_short_backtest.py's pure
collection logic — roadmap item 6, second candidate (2026-09-14)."""

from __future__ import annotations

import unittest

import pandas as pd

import tae_sector_laggard_short_backtest as laggard_bt


def _df(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes})


class CollectLaggardForwardReturnsTest(unittest.TestCase):
    def test_no_sector_peers_yields_no_entries(self) -> None:
        closes = [100.0] * 60
        history = {"A": _df(closes)}
        sector_of = {"A": "Tech"}  # no peers at all
        result = laggard_bt.collect_laggard_forward_returns(history, sector_of)
        self.assertEqual(result, [])

    def test_true_laggard_produces_an_entry_and_measurable_forward_return(self) -> None:
        # A drops 20% and stays down while peer B stays flat -- A's
        # trailing-20d window is still deep in the drop at i=40..44.
        a_closes = [100.0] * 30 + [80.0] * 20
        b_closes = [100.0] * 50
        history = {"A": _df(a_closes), "B": _df(b_closes)}
        sector_of = {"A": "Tech", "B": "Tech"}
        result = laggard_bt.collect_laggard_forward_returns(history, sector_of, hold_days=5)
        self.assertTrue(len(result) > 0)

    def test_non_laggard_is_excluded(self) -> None:
        # A and B move identically -- never a laggard vs its own peer.
        closes = [100.0 + i * 0.1 for i in range(60)]
        history = {"A": _df(closes), "B": _df(closes)}
        sector_of = {"A": "Tech", "B": "Tech"}
        result = laggard_bt.collect_laggard_forward_returns(history, sector_of)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
