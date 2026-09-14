#!/usr/bin/env python3
"""Regression coverage for the long-horizon accounting-quality arm
(roadmap item 2, 2026-09-14).

Context: Sprint 3 found the Piotroski F-Score adaptation has NO
correlation with outcomes at V1/V2/V3's ~7-day holding period, but a
real +0.24 to +0.26 correlation at 6-12 month horizons. This arm
(exp_quality_longterm) trades that signal at the horizon it actually
works at — top-10 equal-weight, monthly rebalance, low turnover — via a
new, isolated module reusing only already-generic shared infra.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import tae_parallel_paper_quality_longterm as qlt


class SelectTopNTest(unittest.TestCase):
    def test_picks_highest_scores_first(self) -> None:
        scores = {"A": 0.9, "B": 0.5, "C": 0.7}
        self.assertEqual(qlt.select_top_n(scores, n=2), ["A", "C"])

    def test_none_scores_are_never_eligible(self) -> None:
        scores = {"A": 0.9, "B": None, "C": 0.7}
        result = qlt.select_top_n(scores, n=5)
        self.assertNotIn("B", result)
        self.assertEqual(len(result), 2)

    def test_fewer_eligible_than_n_returns_all_eligible(self) -> None:
        scores = {"A": 0.9, "B": None}
        self.assertEqual(qlt.select_top_n(scores, n=10), ["A"])

    def test_ties_broken_deterministically_by_ticker_name(self) -> None:
        scores = {"ZZZ": 0.5, "AAA": 0.5}
        self.assertEqual(qlt.select_top_n(scores, n=1), ["AAA"])

    def test_empty_scores_returns_empty_list(self) -> None:
        self.assertEqual(qlt.select_top_n({}, n=10), [])


class IsRebalanceDueTest(unittest.TestCase):
    def test_no_prior_rebalance_is_due(self) -> None:
        self.assertTrue(qlt._is_rebalance_due({"last_rebalance_at": None}, now=qlt.ppr._now()))

    def test_recent_rebalance_is_not_due(self) -> None:
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        portfolio = {"last_rebalance_at": recent}
        self.assertFalse(qlt._is_rebalance_due(portfolio, now=now.strftime("%Y-%m-%dT%H:%M:%SZ")))

    def test_old_rebalance_is_due(self) -> None:
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
        portfolio = {"last_rebalance_at": old}
        self.assertTrue(qlt._is_rebalance_due(portfolio, now=now.strftime("%Y-%m-%dT%H:%M:%SZ")))

    def test_malformed_timestamp_fails_open_to_due(self) -> None:
        portfolio = {"last_rebalance_at": "not-a-real-timestamp"}
        self.assertTrue(qlt._is_rebalance_due(portfolio, now=qlt.ppr._now()))


class ComputeEligibleScoresTest(unittest.TestCase):
    def test_excludes_tickers_below_min_scoreable(self) -> None:
        fake_snapshot = {
            "GOOD": {
                "income": {"Net Income": {"2026-06-30": 10.0}, "Total Revenue": {"2026-06-30": 100.0}},
                "balance_sheet": {"Total Assets": {"2026-06-30": 200.0}},
                "cashflow": {"Operating Cash Flow": {"2026-06-30": 8.0}},
            },
            "SPARSE": {"income": {}, "balance_sheet": {}, "cashflow": {}},
        }
        with mock.patch.object(qlt.fss, "fetch_statements", return_value=fake_snapshot):
            result = qlt.compute_eligible_scores(["GOOD", "SPARSE"])
        self.assertNotIn("SPARSE", result)


class IsolationTest(unittest.TestCase):
    def test_module_not_imported_by_any_existing_arm(self) -> None:
        import inspect

        import tae_parallel_paper_mean_reversion as mr
        import tae_parallel_paper_runtime as ppr
        import tae_parallel_paper_short_margin as sm

        for mod in (ppr, mr, sm):
            self.assertNotIn("tae_parallel_paper_quality_longterm", inspect.getsource(mod))

    def test_real_other_arm_portfolios_untouched_by_import(self) -> None:
        import hashlib

        arms = ("v1", "v2", "v3", "exp_short_margin", "exp_mean_reversion")
        before = {}
        for arm in arms:
            path = Path(f"runtime_outputs/parallel_paper/{arm}/portfolio.json")
            if path.exists():
                before[arm] = hashlib.sha256(path.read_bytes()).hexdigest()

        import tae_parallel_paper_quality_longterm  # noqa: F401

        for arm, digest in before.items():
            path = Path(f"runtime_outputs/parallel_paper/{arm}/portfolio.json")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, f"{arm} portfolio changed on import")


class RuntimeSmokeTest(unittest.TestCase):
    def test_module_exposes_expected_api(self) -> None:
        self.assertTrue(hasattr(qlt, "run_quality_longterm_cycle"))
        self.assertEqual(qlt.STARTING_CAPITAL, 30000.0)
        self.assertEqual(qlt.ARM_ID, "exp_quality_longterm")
        self.assertEqual(qlt.TARGET_HOLDINGS, 10)


if __name__ == "__main__":
    unittest.main()
