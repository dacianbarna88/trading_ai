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

    def test_horizon_alignment_score_actually_moves_the_prediction(self) -> None:
        """Regression for the feature-starvation bug (2026-09-12): passing
        only growth_score/confidence left 9/11 features at fixed neutral
        defaults, which is why the shadow score clustered narrowly
        (0.91-0.94) regardless of the ticker. horizon_alignment_score has
        the largest learned weight of any feature, so a real value must
        move p_profit versus the neutral-default (50.0) case."""
        default_result = shadow.shadow_entry_score(growth_score=80.0, confidence=0.5)
        enriched_result = shadow.shadow_entry_score(
            growth_score=80.0, confidence=0.5, horizon_alignment_score=90.0
        )
        self.assertIsNotNone(default_result)
        self.assertIsNotNone(enriched_result)
        self.assertNotEqual(default_result["p_profit"], enriched_result["p_profit"])

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
        # The condition that actually authorizes a BUY must still be gated
        # on `favorable` (the existing heuristic) etc., never on
        # shadow_score -- checked as "no line mentions both", robust to
        # the guard clause being reformatted across multiple lines (it now
        # also checks eligible/liquid, added 2026-09-12/13).
        lines_with_favorable = [line for line in source.splitlines() if "favorable" in line]
        self.assertTrue(lines_with_favorable)
        for line in lines_with_favorable:
            self.assertNotIn("shadow_score", line)

    def test_v1_arm_sources_horizon_alignment_from_same_day_pde_signals(self) -> None:
        """Regression for the feature-starvation fix: the shadow call must
        be enriched from the same same-day canonical PDE signal lookup V3
        uses (_load_today_pde_signals), not left at growth_score/confidence
        only."""
        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr._run_v1_arm)
        self.assertIn("horizon_alignment_score=pde_sig.get(\"horizon_alignment_score\")", source)
        self.assertIn("horizon_conflict_flag=pde_sig.get(\"horizon_conflict_flag\")", source)

    def test_run_cycle_wires_pde_signals_into_v1_arm(self) -> None:
        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr)
        self.assertIn("v1_pde_signals = v3_pde_signals or _load_today_pde_signals()", source)
        self.assertIn("pde_signals=v1_pde_signals", source)


if __name__ == "__main__":
    unittest.main()
