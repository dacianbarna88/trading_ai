#!/usr/bin/env python3
"""Shared hermetic isolation helpers for TAE unit tests.

Never point Adaptive Deployment / portfolios at live SSOT from unit tests.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def isolate_adaptive_deployment(
    test_case: unittest.TestCase,
    *,
    extra_env: dict[str, str] | None = None,
) -> Path:
    """Point Adaptive Deployment at a temp DRAFT root — never the live canary SSOT."""
    import tae_adaptive_deployment as adep

    tmp = tempfile.TemporaryDirectory()
    test_case.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    env: dict[str, str] = {
        "TAE_ADAPTIVE_DEPLOYMENT_ROOT": str(root),
        # Hermetic: do not read live longitudinal/paper_decisions for Decision Brain SKIP gate.
        "DECISION_BRAIN_SKIP_GATE_SSOT_LOOKUP": "false",
    }
    if extra_env:
        env.update(extra_env)
    env_patch = mock.patch.dict(os.environ, env)
    env_patch.start()
    test_case.addCleanup(env_patch.stop)
    st = adep.load_state(root=root, create_default=True)
    assert st.get("deployment_state") == adep.ST_DRAFT

    # Bug found 2026-09-09: tae_paper_execution.execute_decision() tracks
    # same-run SELL->BUY churn in a process-global dict (_RECENT_SELL_AT),
    # never cleared. In production that's fine (one hourly cycle = one
    # fresh subprocess), but `tae.py test` runs every test class in the
    # same process, so any earlier test's SELL_PAPER for ticker X silently
    # makes a later, unrelated test's BUY_PAPER for ticker X get deferred
    # as DEFERRED_RECENT_SELL_SAME_RUN -- surfacing as an unrelated-looking
    # assertion failure ("flaky" cluster: CanonicalOpeningNoiseDeferTest,
    # CanonicalE3ProfitDecayGateTest, PaperProfitProtectionWiringTest).
    # Every affected test class already calls this helper in setUp, so
    # resetting here gives them isolation for free.
    import tae_paper_execution as _pe

    _pe._RECENT_SELL_AT.clear()
    test_case.addCleanup(_pe._RECENT_SELL_AT.clear)

    return root
