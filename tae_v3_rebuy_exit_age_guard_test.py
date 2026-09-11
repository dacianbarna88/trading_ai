#!/usr/bin/env python3
"""
Regression coverage for V3's rebuy-check exit age guard (2026-09-10).

Root cause found via real trades.jsonl history: CRM/DE/ENTG were bought
and sold within 16-31 minutes at the EXACT same price on 2026-09-08/09 --
pure transaction-cost bleed, no real price movement. decide_v3's BUY gate
uses a pool-calibrated threshold (top 1-calibration_quantile of *today's*
candidates), while the "would I still buy this" rebuy-check SELL gate
used a flat p_rebuy<0.5 cutoff -- a borderline candidate could clear the
relative BUY bar one hour and fail the flat rebuy bar the very next
evaluation from ordinary model-refit noise alone, with price unchanged.

Fix: sell_via_rebuy_check now also requires the position to be at least
V3_MIN_REBUY_EXIT_AGE_HOURS old (mirrors tae_strategy_v2_concentration.
V2_TRIM_MIN_AGE_HOURS's precedent). sell_via_exit_model (a genuine
learned SELL signal, not a portfolio-review heuristic) is deliberately
NOT gated by this and must keep firing on a fresh position.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

import tae_strategy_v3_learning_policy as v3pol


def _cycle_id(ticker: str, hours_ago: float) -> str:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y%m%dT%H%M%S")
    return f"PPC-{ticker}-{ts}-DEADBEEF"


@dataclass
class _FakeModel:
    action: str
    weights: object
    mean: object
    std: object
    base_rate: float
    n_train: int


class _FakeScorer:
    """Deterministic stand-in for LearningScorer.predict_proba, so tests
    control p_exit/p_rebuy directly without needing a real fitted model."""

    def __init__(self, *, p_exit: float, p_rebuy: float, exit_signal: bool, rebuy_signal: bool) -> None:
        self._p_exit = p_exit
        self._p_rebuy = p_rebuy
        self._exit_signal = exit_signal
        self._rebuy_signal = rebuy_signal

    def predict_proba(self, action: str, record: dict) -> tuple[float, dict]:
        if action == "SELL_PAPER":
            w = v3pol.MIN_EXIT_SHRINKAGE + 0.1 if self._exit_signal else 0.0
            return self._p_exit, {"shrinkage_weight": w}
        if action == "BUY_PAPER":
            w = v3pol.MIN_EXIT_SHRINKAGE + 0.1 if self._rebuy_signal else 0.0
            return self._p_rebuy, {"shrinkage_weight": w}
        raise AssertionError(f"unexpected action {action}")


def _regime() -> v3pol.RegimeGrid:
    return v3pol.RegimeGrid(trend="BULL", vol_tercile="MED", realized_vol_annualized=0.2)


def _snap() -> dict:
    return {"score": 80.0, "confidence": 0.6}


class RebuyExitAgeGuardTest(unittest.TestCase):
    def test_fresh_position_does_not_sell_on_rebuy_check_alone(self) -> None:
        scorer = _FakeScorer(p_exit=0.5, p_rebuy=0.3, exit_signal=False, rebuy_signal=True)
        pos = {"position_cycle_id": _cycle_id("ZZZ", 1.0)}  # 1h old, below the 4h guard
        decision = v3pol.decide_v3(
            ticker="ZZZ", snap=_snap(), scorer=scorer, regime=_regime(),
            has_position=True, cash_available=1000.0, open_positions=1, pos=pos,
        )
        self.assertEqual(decision.action, "HOLD")

    def test_old_enough_position_sells_on_rebuy_check(self) -> None:
        scorer = _FakeScorer(p_exit=0.5, p_rebuy=0.3, exit_signal=False, rebuy_signal=True)
        pos = {"position_cycle_id": _cycle_id("ZZZ", 5.0)}  # past the 4h guard
        decision = v3pol.decide_v3(
            ticker="ZZZ", snap=_snap(), scorer=scorer, regime=_regime(),
            has_position=True, cash_available=1000.0, open_positions=1, pos=pos,
        )
        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.reason, "V3_NO_LONGER_BUY_WORTHY")

    def test_missing_pos_never_fires_rebuy_check(self) -> None:
        """Fail-safe default: no position/age data means decline the
        (weaker) rebuy-check exit rather than assume it's old enough."""
        scorer = _FakeScorer(p_exit=0.5, p_rebuy=0.3, exit_signal=False, rebuy_signal=True)
        decision = v3pol.decide_v3(
            ticker="ZZZ", snap=_snap(), scorer=scorer, regime=_regime(),
            has_position=True, cash_available=1000.0, open_positions=1, pos=None,
        )
        self.assertEqual(decision.action, "HOLD")

    def test_genuine_exit_model_signal_still_fires_on_a_fresh_position(self) -> None:
        """sell_via_exit_model is a real learned SELL signal, not the
        "would I still buy this" review -- must NOT be gated by age."""
        scorer = _FakeScorer(p_exit=0.9, p_rebuy=0.6, exit_signal=True, rebuy_signal=False)
        pos = {"position_cycle_id": _cycle_id("ZZZ", 0.1)}  # 6 minutes old
        decision = v3pol.decide_v3(
            ticker="ZZZ", snap=_snap(), scorer=scorer, regime=_regime(),
            has_position=True, cash_available=1000.0, open_positions=1, pos=pos,
        )
        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.reason, "V3_LEARNED_EXIT_SIGNAL")

    def test_reproduces_the_real_crm_churn_shape_when_fixed(self) -> None:
        """CRM: bought, then re-evaluated ~31 minutes later with a
        marginally-below-0.5 rebuy score and no real exit signal -- must
        now HOLD instead of the historical immediate same-price SELL."""
        scorer = _FakeScorer(p_exit=0.5, p_rebuy=0.49, exit_signal=False, rebuy_signal=True)
        pos = {"position_cycle_id": _cycle_id("CRM", 31.0 / 60.0)}
        decision = v3pol.decide_v3(
            ticker="CRM", snap=_snap(), scorer=scorer, regime=_regime(),
            has_position=True, cash_available=1000.0, open_positions=1, pos=pos,
        )
        self.assertEqual(decision.action, "HOLD")


class RuntimeWiringSmokeTest(unittest.TestCase):
    def test_run_v3_arm_passes_pos_into_decide_v3(self) -> None:
        import inspect

        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr)
        self.assertIn("decide_v3(", source)
        # At least one call site must pass pos=pos (the has_position=True path).
        idx = source.index("has_position=True,")
        window = source[idx: idx + 400]
        self.assertIn("pos=pos", window)


if __name__ == "__main__":
    unittest.main()
