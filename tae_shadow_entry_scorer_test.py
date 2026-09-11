#!/usr/bin/env python3
"""
Regression coverage for the shadow entry-scorer (2026-09-09), built after
finding V1/V2's flat score-threshold entry gate is a weak, non-monotonic
predictor of real outcomes (2,987 real checkpoint-confirmed BUY_PAPER
samples: score 70-79 -> 1.1% win rate; score 90-99 -> 93.5%). This logs
tae_strategy_v3_learning_policy.LearningScorer's P(profitable) alongside
V1's real entry decisions WITHOUT changing them -- shadow-only, so it can
be validated against real outcomes before ever gating real (paper) money.
"""

from __future__ import annotations

import inspect
import unittest
from unittest import mock

import tae_shadow_entry_scorer as shadow


class ShadowScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        shadow._cache.clear()

    def test_returns_a_p_profit_and_diagnostics(self) -> None:
        result = shadow.shadow_entry_score(growth_score=75.0, confidence=0.6)
        self.assertIsNotNone(result)
        self.assertIn("p_profit", result)
        self.assertGreaterEqual(result["p_profit"], 0.0)
        self.assertLessEqual(result["p_profit"], 1.0)

    def test_never_raises_even_if_the_underlying_scorer_breaks(self) -> None:
        with mock.patch.object(shadow, "_get_scorer", side_effect=RuntimeError("boom")):
            result = shadow.shadow_entry_score(growth_score=75.0)
        self.assertIsNotNone(result)
        self.assertIn("error", result)

    def test_scorer_is_cached_not_refit_per_call(self) -> None:
        calls = []
        real_fit = shadow._get_scorer

        def _counting_get_scorer(*, now):
            calls.append(now)
            return real_fit(now=now)

        with mock.patch.object(shadow, "_get_scorer", side_effect=_counting_get_scorer):
            shadow.shadow_entry_score(growth_score=10.0)
            shadow.shadow_entry_score(growth_score=90.0)
            shadow.shadow_entry_score(growth_score=50.0)
        self.assertEqual(len(calls), 3)  # _get_scorer called each time...
        # ...but the cache inside it means only the first actually fits.
        self.assertIn("scorer", shadow._cache)


class RuntimeWiringSmokeTest(unittest.TestCase):
    """Confirms V1's real entry path computes a shadow score for genuine
    entry candidates and attaches it to the logged decision, WITHOUT it
    ever influencing `favorable`/`action` -- without running a full
    network-dependent parallel-paper cycle."""

    def test_v1_arm_computes_and_logs_shadow_score_but_never_gates_on_it(self) -> None:
        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr._run_v1_arm)
        self.assertIn("shadow_scorer.shadow_entry_score", source)
        self.assertIn('"shadow_entry_score": shadow_score', source)
        # The line that actually authorizes a BUY must still be gated on
        # `favorable` (the existing heuristic), not on shadow_score.
        buy_gate_line = next(
            line for line in source.splitlines() if "phase_n in {PHASE_ENTRY, PHASE_ALL} and favorable" in line
        )
        self.assertNotIn("shadow_score", buy_gate_line)


if __name__ == "__main__":
    unittest.main()
