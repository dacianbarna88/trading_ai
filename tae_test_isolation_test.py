#!/usr/bin/env python3
"""Regression for a real cross-test-pollution bug found 2026-09-09.

tae_paper_execution.execute_decision() tracks same-run SELL->BUY churn in
a process-global dict (_RECENT_SELL_AT) that is never cleared -- fine in
production (one hourly cycle = one fresh subprocess) but not in `tae.py
test`, which runs every test class in one process. A SELL_PAPER for
ticker X in one test silently made a later, unrelated test's BUY_PAPER
for ticker X get deferred as DEFERRED_RECENT_SELL_SAME_RUN, surfacing as
an unrelated-looking assertion failure -- this was misdiagnosed across
several sessions as a "long-standing pre-existing flaky cluster"
(CanonicalOpeningNoiseDeferTest, CanonicalE3ProfitDecayGateTest,
PaperProfitProtectionWiringTest) rather than root-caused. Fix: every
affected class already calls isolate_adaptive_deployment() in setUp, so
that helper now also clears _RECENT_SELL_AT on entry and exit.
"""

from __future__ import annotations

import unittest

import tae_paper_execution as pe
from tae_test_isolation import isolate_adaptive_deployment


class RecentSellCooldownIsolationTest(unittest.TestCase):
    def test_pollution_from_a_prior_sell_does_not_leak_into_this_test(self) -> None:
        pe._RECENT_SELL_AT["ZZZZ"] = pe._now()
        self.assertIn("ZZZZ", pe._RECENT_SELL_AT)

        isolate_adaptive_deployment(self)

        self.assertNotIn(
            "ZZZZ",
            pe._RECENT_SELL_AT,
            "a leftover _RECENT_SELL_AT entry from an earlier test/decision "
            "must not survive into a test that calls isolate_adaptive_deployment()",
        )

    def test_this_test_does_not_leak_into_the_next_one(self) -> None:
        isolate_adaptive_deployment(self)
        pe._RECENT_SELL_AT["ZZZZ"] = pe._now()
        # addCleanup (registered by isolate_adaptive_deployment) runs after
        # this test method returns -- unittest invokes cleanups itself, so
        # simulate that here to prove the registration, not just the entry-state clear.
        self.doCleanups()
        self.assertNotIn("ZZZZ", pe._RECENT_SELL_AT)


if __name__ == "__main__":
    unittest.main()
