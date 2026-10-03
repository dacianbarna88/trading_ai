from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tae2_ucits import data as ucits_data


def _prices(n: int = 30) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame(index=idx)


class BlendedIndexTest(unittest.TestCase):
    def test_weighted_return_matches_a_hand_computed_example(self) -> None:
        p = _prices(3)
        # Day index 0 has no return (pct_change's first row is NaN and is
        # dropped) -- the output's first element IS day 1's return already
        # applied, not a held-at-100 baseline row.
        # Day 1: A +10%, B +0% -- weighted 0.5/0.5 -> +5% -> 105.
        # Day 2: both flat -> stays 105.
        p["A"] = [100.0, 110.0, 110.0]
        p["B"] = [100.0, 100.0, 100.0]
        idx = ucits_data._blended_index(p, {"A": 0.5, "B": 0.5})
        self.assertEqual(len(idx), 2)
        self.assertAlmostEqual(idx.iloc[0], 105.0)
        self.assertAlmostEqual(idx.iloc[1], 105.0)

    def test_starts_only_once_every_component_has_data(self) -> None:
        p = _prices(4)
        p["A"] = [np.nan, np.nan, 100.0, 101.0]  # A only exists from day 3
        p["B"] = [100.0, 101.0, 102.0, 103.0]
        idx = ucits_data._blended_index(p, {"A": 0.5, "B": 0.5})
        # First two days have no A -> pct_change/dropna excludes them entirely.
        self.assertEqual(len(idx), 1)  # only one return is computable (day3->day4)

    def test_weights_that_sum_to_one_preserve_scale(self) -> None:
        p = _prices(3)
        p["A"] = [100.0, 105.0, 110.0]
        p["B"] = [100.0, 95.0, 90.0]
        idx = ucits_data._blended_index(p, {"A": 0.5, "B": 0.5})
        self.assertAlmostEqual(idx.iloc[0], 100.0)


class SplicedIndexTest(unittest.TestCase):
    def test_uses_early_ticker_before_the_splice_and_late_after(self) -> None:
        p = _prices(5)
        splice = p.index[3]  # EARLY covers day indices 0-2, LATE covers 3-4
        p["EARLY"] = [100.0, 110.0, 121.0, 999.0, 999.0]  # +10%/day; values after the
        p["LATE"] = [50.0, 50.0, 50.0, 60.0, 66.0]  # seam (999, 50) are never read
        idx = ucits_data._spliced_index(p, "EARLY", "LATE", splice.isoformat())
        # day1: EARLY +10% -> 110. day2: EARLY +10% again (still < splice) -> 121.
        # day3 (the splice day itself, index 3, ">= splice"): LATE's own day2->day3
        # return (+20%) -> 121 * 1.20 = 145.2. day4: LATE +10% -> 159.72.
        self.assertAlmostEqual(idx.iloc[0], 110.0, places=4)
        self.assertAlmostEqual(idx.iloc[1], 121.0, places=4)
        self.assertAlmostEqual(idx.iloc[2], 145.2, places=4)
        self.assertAlmostEqual(idx.iloc[3], 159.72, places=4)

    def test_no_jump_at_the_seam(self) -> None:
        """The spliced series must be continuous -- no artificial gap/jump
        in the index level right at the splice date, only in composition."""
        p = _prices(6)
        splice = p.index[3]
        p["EARLY"] = [100.0, 102.0, 104.0, 999.0, 999.0, 999.0]
        p["LATE"] = [10.0, 10.2, 10.4, 10.6, 10.8, 11.0]
        idx = ucits_data._spliced_index(p, "EARLY", "LATE", splice.isoformat())
        # Day-over-day % change across the seam must match LATE's own actual
        # return that day, not some artifact of EARLY's much larger price level.
        late_ret_at_seam = p["LATE"].iloc[3] / p["LATE"].iloc[2] - 1
        actual_ret_at_seam = idx.iloc[2] / idx.iloc[1] - 1
        self.assertAlmostEqual(actual_ret_at_seam, late_ret_at_seam, places=6)


if __name__ == "__main__":
    unittest.main()
