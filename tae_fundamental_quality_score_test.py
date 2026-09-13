#!/usr/bin/env python3
"""Regression coverage for tae_fundamental_quality_score.py — Sprint 3 Phase 4."""

from __future__ import annotations

import unittest

import tae_fundamental_quality_score as fq


class ComputeQualityScoresTest(unittest.TestCase):
    def test_single_ticker_universe_is_unscoreable(self) -> None:
        snapshot = {"AAA": {"returnOnEquity": 0.3}}
        scores = fq.compute_quality_scores(snapshot)
        self.assertIsNone(scores["AAA"])

    def test_higher_roe_scores_better_than_lower(self) -> None:
        snapshot = {
            "GOOD": {"returnOnEquity": 0.30, "profitMargins": 0.25},
            "BAD": {"returnOnEquity": 0.02, "profitMargins": 0.01},
        }
        scores = fq.compute_quality_scores(snapshot)
        self.assertGreater(scores["GOOD"], scores["BAD"])

    def test_lower_peg_and_debt_score_better_than_higher(self) -> None:
        snapshot = {
            "CHEAP_SAFE": {"pegRatio": 0.5, "debtToEquity": 10.0},
            "EXPENSIVE_LEVERED": {"pegRatio": 4.0, "debtToEquity": 300.0},
        }
        scores = fq.compute_quality_scores(snapshot)
        self.assertGreater(scores["CHEAP_SAFE"], scores["EXPENSIVE_LEVERED"])

    def test_missing_fields_for_one_ticker_does_not_crash(self) -> None:
        snapshot = {
            "FULL": {"returnOnEquity": 0.2, "pegRatio": 1.5, "debtToEquity": 50.0},
            "SPARSE": {"returnOnEquity": 0.1},
        }
        scores = fq.compute_quality_scores(snapshot)
        self.assertIsNotNone(scores["FULL"])
        self.assertIsNotNone(scores["SPARSE"])

    def test_ticker_with_no_usable_fields_is_none(self) -> None:
        snapshot = {
            "A": {"returnOnEquity": 0.2},
            "B": {"returnOnEquity": 0.1},
            "C": {"sector": "Technology"},  # no scoreable numeric fields at all
        }
        scores = fq.compute_quality_scores(snapshot)
        self.assertIsNone(scores["C"])


if __name__ == "__main__":
    unittest.main()
