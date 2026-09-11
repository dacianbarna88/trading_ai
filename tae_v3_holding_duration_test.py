#!/usr/bin/env python3
"""
Regression coverage for the holding_duration_hours feature (2026-09-09).

Two-part fix: (1) tae_parallel_paper_runtime.py's V3 SELL execution path
never computed holding_duration_sec -- the parameter existed on
record_execution_learning_feedback() but every caller omitted it, so the
field was always None in V3's own learning_events.jsonl despite being in
the schema. (2) tae_strategy_v3_learning_policy._extract_features() didn't
use it as a feature at all. This covers both: the feature-extraction math,
and a static check that the runtime fix is actually wired in (without
running a real network-dependent cycle).
"""

from __future__ import annotations

import inspect
import unittest

import tae_strategy_v3_learning_policy as pol


class HoldingDurationFeatureTest(unittest.TestCase):
    def _idx(self) -> int:
        return pol.FEATURE_NAMES.index("holding_duration_hours")

    def test_real_value_is_used_directly(self) -> None:
        features = pol._extract_features({"holding_duration_hours": 5.0})
        self.assertEqual(features[self._idx()], 5.0)

    def test_missing_value_falls_back_to_empirical_neutral_default(self) -> None:
        features = pol._extract_features({})
        self.assertEqual(features[self._idx()], pol.HOLDING_DURATION_NEUTRAL_DEFAULT_HOURS)

    def test_zero_is_a_real_value_not_treated_as_missing(self) -> None:
        features = pol._extract_features({"holding_duration_hours": 0.0})
        self.assertEqual(features[self._idx()], 0.0)

    def test_feature_names_and_vector_length_match(self) -> None:
        features = pol._extract_features({})
        self.assertEqual(len(features), len(pol.FEATURE_NAMES))


class RuntimeWiringSmokeTest(unittest.TestCase):
    """Confirms tae_parallel_paper_runtime.py's V3 SELL path computes a
    real holding_duration_sec instead of always passing None -- without
    running a full network-dependent parallel-paper cycle."""

    def test_v3_sell_path_computes_holding_duration_from_position_age(self) -> None:
        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr)
        self.assertIn("_position_age_hours", source)
        self.assertIn("holding_duration_sec=holding_duration_sec", source)


if __name__ == "__main__":
    unittest.main()
