#!/usr/bin/env python3
"""
Regression coverage for the literature-informed prior blend (2026-09-09):
when an action's logistic model can't fit (too few samples), predict_proba
now blends the raw empirical base_rate toward an established-literature
prior (LITERATURE_PRIOR_BY_ACTION) instead of trusting a possibly-noisy
base_rate computed from as few as ~15 samples. Uses the exact same
n/(n+K) shrinkage pattern already used for the model-vs-base_rate blend,
just applied one layer further out.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

import numpy as np

import tae_strategy_v3_learning_policy as pol


@dataclass
class _FakeModel:
    action: str
    weights: object
    mean: object
    std: object
    base_rate: float
    n_train: int


class LiteraturePriorBlendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = pol.LearningScorer()

    def test_unfitted_action_with_prior_blends_toward_literature(self) -> None:
        self.scorer.models["PROTECT_PAPER"] = _FakeModel(
            action="PROTECT_PAPER", weights=None, mean=np.zeros(10), std=np.ones(10),
            base_rate=0.9, n_train=15,
        )
        p, diag = self.scorer.predict_proba("PROTECT_PAPER", {})
        # Pure base_rate would be 0.9; literature prior pulls it down toward 0.65.
        self.assertLess(p, 0.9)
        self.assertGreater(p, 0.65)
        self.assertEqual(diag["source"], "BASE_RATE_BLENDED_WITH_LITERATURE_PRIOR")

    def test_more_samples_trusts_empirical_rate_more(self) -> None:
        low_n = _FakeModel(action="SELL_PAPER", weights=None, mean=np.zeros(10), std=np.ones(10), base_rate=0.9, n_train=5)
        high_n = _FakeModel(action="SELL_PAPER", weights=None, mean=np.zeros(10), std=np.ones(10), base_rate=0.9, n_train=500)
        self.scorer.models["SELL_PAPER"] = low_n
        p_low, _ = self.scorer.predict_proba("SELL_PAPER", {})
        self.scorer.models["SELL_PAPER"] = high_n
        p_high, _ = self.scorer.predict_proba("SELL_PAPER", {})
        # At n=500 the blend should sit much closer to the empirical 0.9
        # than at n=5, which should sit much closer to the 0.40 prior.
        self.assertGreater(p_high, p_low)
        self.assertLess(abs(p_high - 0.9), abs(p_low - 0.9))

    def test_action_without_a_literature_prior_falls_back_unchanged(self) -> None:
        self.scorer.models["HOLD_PAPER"] = _FakeModel(
            action="HOLD_PAPER", weights=None, mean=np.zeros(10), std=np.ones(10),
            base_rate=0.42, n_train=10,
        )
        p, diag = self.scorer.predict_proba("HOLD_PAPER", {})
        self.assertEqual(p, 0.42)
        self.assertEqual(diag["source"], "BASE_RATE_ONLY_INSUFFICIENT_DATA")

    def test_fitted_model_is_never_touched_by_the_prior(self) -> None:
        n_features = len(pol.FEATURE_NAMES)
        weights = np.zeros(n_features + 1)  # +1 for the bias term
        self.scorer.models["SELL_PAPER"] = _FakeModel(
            action="SELL_PAPER", weights=weights, mean=np.zeros(n_features), std=np.ones(n_features),
            base_rate=0.9, n_train=200,
        )
        _, diag = self.scorer.predict_proba("SELL_PAPER", {})
        self.assertEqual(diag["source"], "LOGISTIC_SHRUNK_TO_BASE_RATE")
        self.assertNotIn("literature_prior", diag)

    def test_zero_samples_still_returns_base_rate_only_source(self) -> None:
        self.scorer.models["PROTECT_PAPER"] = _FakeModel(
            action="PROTECT_PAPER", weights=None, mean=np.zeros(10), std=np.ones(10),
            base_rate=0.5, n_train=0,
        )
        p, diag = self.scorer.predict_proba("PROTECT_PAPER", {})
        self.assertEqual(p, 0.5)
        self.assertEqual(diag["source"], "BASE_RATE_ONLY_INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
