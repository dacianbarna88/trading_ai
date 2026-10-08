from __future__ import annotations

import unittest

import pandas as pd

from bvb import data as bvb_data


class PatchJumpsTest(unittest.TestCase):
    def test_zeroes_only_the_flagged_day_return(self) -> None:
        idx = pd.bdate_range("2020-01-01", periods=5)
        # A 10x fake jump on day index 2, then real (small) moves either side.
        prices = pd.DataFrame({"X": [100.0, 101.0, 1010.0, 1020.0, 1030.0]}, index=idx)
        patched = bvb_data._patch_jumps(prices, {"X": [idx[2].isoformat()]})
        # Day 1 (100->101, real +1%) is untouched.
        self.assertAlmostEqual(patched["X"].iloc[1] / patched["X"].iloc[0], 1.01, places=4)
        # The flagged day's return is neutralized to 0%.
        self.assertAlmostEqual(patched["X"].iloc[2] / patched["X"].iloc[1], 1.0, places=6)
        # Day 3 (1010->1020, real ~+0.99%) is preserved AFTER the patch, on
        # the post-event scale -- not corrupted by the neutralized day.
        self.assertAlmostEqual(patched["X"].iloc[3] / patched["X"].iloc[2], 1020.0 / 1010.0, places=6)

    def test_untouched_ticker_passes_through_unchanged(self) -> None:
        idx = pd.bdate_range("2020-01-01", periods=3)
        prices = pd.DataFrame({"Y": [50.0, 51.0, 49.0]}, index=idx)
        patched = bvb_data._patch_jumps(prices, {"X": ["2020-01-02"]})
        pd.testing.assert_series_equal(patched["Y"], prices["Y"], check_names=False)

    def test_load_adds_a_zero_return_cash_column(self) -> None:
        prices = bvb_data.load(refresh=False)
        self.assertIn(bvb_data.CASH, prices.columns)
        self.assertTrue((prices[bvb_data.CASH].pct_change().dropna() == 0.0).all())


if __name__ == "__main__":
    unittest.main()
