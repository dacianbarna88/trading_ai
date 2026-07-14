#!/usr/bin/env python3
"""Tests for profit target promotion replay."""

from __future__ import annotations

import unittest

from tae_profit_target_promotion import integrated_would_apply, run_promotion_replay


class ProfitTargetPromotionTest(unittest.TestCase):
    def test_integrated_would_apply_critical(self) -> None:
        self.assertTrue(
            integrated_would_apply(
                {"exit_window_urgency": "CRITICAL", "recommended_shadow_strategy": "REDUCE_EXPOSURE_SHADOW"}
            )
        )

    def test_replay_returns_verdict(self) -> None:
        replay = run_promotion_replay()
        self.assertIn(replay["verdict"], {"PROFIT_TARGET_PROMOTED", "PROFIT_TARGET_REJECTED"})
        self.assertIn("baseline", replay)
        self.assertIn("integrated", replay)


if __name__ == "__main__":
    unittest.main()
