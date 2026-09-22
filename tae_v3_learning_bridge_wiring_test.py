#!/usr/bin/env python3
"""Wiring regression: load_training_data() must pool the V1/V2 cross-arm
bridge in by default, and must be able to turn it off for a bridge-free
read (comparison, or when the bridge itself is under test)."""

from __future__ import annotations

import unittest

from tae_strategy_v3_learning_policy import load_training_data


class BridgeToggleTest(unittest.TestCase):
    def test_bridge_on_by_default_adds_sell_paper_samples(self) -> None:
        with_bridge = load_training_data()
        without_bridge = load_training_data(include_cross_arm_bridge=False)
        n_with = len(with_bridge["SELL_PAPER"].y) if "SELL_PAPER" in with_bridge else 0
        n_without = len(without_bridge["SELL_PAPER"].y) if "SELL_PAPER" in without_bridge else 0
        if n_with == 0:
            # No real SELL_PAPER samples at all (fresh checkout, runtime_
            # outputs/ missing) -- nothing to compare (CI hygiene fix, 2026-09-22).
            self.skipTest("no real SELL_PAPER training samples available (fresh checkout, runtime_outputs/ missing)")
        self.assertGreater(
            n_with, n_without,
            "default load_training_data() must include more SELL_PAPER "
            "samples than a bridge-free read, via the V1/V2 cross-arm bridge",
        )

    def test_bridge_failure_does_not_break_the_canonical_read(self) -> None:
        import tae_strategy_v3_learning_policy as pol
        import unittest.mock as mock

        with mock.patch(
            "tae_v3_cross_arm_training_bridge.all_bridged_training_records",
            side_effect=RuntimeError("boom"),
        ):
            # Must not raise -- bridge is best-effort enrichment only.
            result = pol.load_training_data()
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
