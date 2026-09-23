from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tae2 import gates, stats


def _series(values, start="2010-01-01") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


class StatsTest(unittest.TestCase):
    def test_max_drawdown(self) -> None:
        r = _series([0.10, -0.50, 0.20])  # 1.1 -> 0.55 -> 0.66
        self.assertAlmostEqual(stats.max_drawdown(r), -0.5)

    def test_cagr_of_a_year_of_flat_growth(self) -> None:
        r = _series([(1.10) ** (1 / 252) - 1] * 252)
        self.assertAlmostEqual(stats.cagr(r), 0.10, places=6)

    def test_summary_splits_halves_at_the_date(self) -> None:
        r = _series(np.r_[np.full(300, 0.001), np.full(300, -0.001)] + np.tile([0.002, -0.002], 300))
        s = stats.summary(r, split=str(r.index[300].date()))
        self.assertGreater(s["sharpe_first_half"], 0)
        self.assertLess(s["sharpe_second_half"], 0)

    def test_deflated_sharpe_falls_as_more_variants_are_tried(self) -> None:
        rng = np.random.default_rng(1)
        r = _series(rng.normal(0.0004, 0.01, 2500))
        one = stats.deflated_sharpe(r, n_trials=1)
        many = stats.deflated_sharpe(r, n_trials=200, trial_sharpes=list(rng.normal(0.3, 0.3, 200)))
        self.assertTrue(0 <= many < one <= 1)


class GatesTest(unittest.TestCase):
    BENCH = {"years": 18, "sharpe_first_half": 0.6, "sharpe_second_half": 0.9, "max_dd": -0.3}

    def test_strong_candidate_passes(self) -> None:
        cand = {"years": 18, "sharpe_first_half": 0.8, "sharpe_second_half": 1.0, "max_dd": -0.2}
        self.assertTrue(gates.passed(gates.evaluate(cand, self.BENCH, 0.99, 10)))

    def test_winning_only_one_half_fails(self) -> None:
        cand = {"years": 18, "sharpe_first_half": 1.2, "sharpe_second_half": 0.5, "max_dd": -0.2}
        failed = {c.gate for c in gates.evaluate(cand, self.BENCH, 0.99, 10) if not c.passed}
        self.assertEqual(failed, {"beats benchmark, both halves"})

    def test_short_history_low_costs_and_luck_fail(self) -> None:
        cand = {"years": 5, "sharpe_first_half": 0.8, "sharpe_second_half": 1.0, "max_dd": -0.2}
        failed = {c.gate for c in gates.evaluate(cand, self.BENCH, 0.5, 2) if not c.passed}
        self.assertEqual(failed, {"history", "costs", "deflated Sharpe"})


if __name__ == "__main__":
    unittest.main()
