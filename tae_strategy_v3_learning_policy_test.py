#!/usr/bin/env python3
"""
Regression coverage for the V3 ("V_learning") silent-degradation bug found
in the Phase 5 soak: horizon_alignment_score defaulted to 0.0 for every
ticker because build_pseudo_record assumed `snap` (the raw market
snapshot V1/V2/V3 all consume) carried PDE-enriched fields
(capital_efficiency, horizon_alignment_score, confidence) it never actually
has — those come from a later pipeline stage. The bug produced no error and
no reconciliation failure; it just quietly suppressed every BUY prediction
below threshold for two days.

These tests exist specifically so that class of bug — "the fixture I wrote
matches my own code's assumption, not the real system's data contract" —
can't silently reappear. Where practical they use the REAL
default_mark_provider() snap shape rather than a hand-built fixture that
happens to already include the enriched fields.
"""

from __future__ import annotations

import unittest

import numpy as np

import tae_parallel_paper_runtime as ppr
import tae_strategy_v3_learning_policy as v3pol


class RealSnapShapeContractTest(unittest.TestCase):
    """
    Locks in what default_mark_provider's snap actually contains. If this
    ever starts failing because the provider grew richer fields, that's
    good news — but build_pseudo_record's neutral-default assumptions
    should be revisited at the same time, not silently bypassed.
    """

    def test_default_mark_provider_snap_has_no_pde_fields(self) -> None:
        marks = ppr.default_mark_provider(["AAPL", "MSFT", "SPY"])
        if not marks:
            self.skipTest("no signals.csv/live_signals.csv rows available in this checkout")
        for ticker, snap in marks.items():
            for pde_field in ("capital_efficiency", "horizon_alignment_score", "confidence"):
                self.assertNotIn(
                    pde_field,
                    snap,
                    f"default_mark_provider snap for {ticker} unexpectedly has "
                    f"'{pde_field}' — if this is now real, build_pseudo_record's "
                    f"reliance on _enrich_snap_for_v3/pde_signals should be revisited.",
                )


class NeutralDefaultRegressionTest(unittest.TestCase):
    """
    Directly reproduces the bug scenario: a snap shaped like the real
    provider's output (no PDE fields) fed through the real V3 scoring path.
    """

    def test_missing_horizon_alignment_defaults_neutral_not_zero(self) -> None:
        raw_snap = {
            "mark_price": 100.0,
            "mark_freshness": "FRESH",
            "score": 60.0,
            "signal": "HOLD",
            # deliberately no capital_efficiency / horizon_alignment_score /
            # confidence — this is the real default_mark_provider contract.
        }
        regime = v3pol.RegimeGrid(trend="UNKNOWN", vol_tercile="UNKNOWN", realized_vol_annualized=None)
        pseudo = v3pol.build_pseudo_record(raw_snap, regime)
        features = v3pol._extract_features(pseudo)
        horizon_idx = v3pol.FEATURE_NAMES.index("horizon_alignment_score")
        self.assertEqual(
            features[horizon_idx],
            v3pol.HORIZON_ALIGNMENT_NEUTRAL_DEFAULT,
            "missing horizon_alignment_score must impute to the documented neutral "
            "default, not 0.0 — 0.0 is ~6.8 std devs off the trained mean and was "
            "enough on its own to suppress every BUY prediction below threshold.",
        )

    def test_enrichment_changes_the_prediction_meaningfully(self) -> None:
        """
        The actual end-to-end regression check: with vs without
        _enrich_snap_for_v3's real PDE signal, p_profit for the same ticker
        must differ — if enrichment ever silently stops wiring through
        (e.g. a future refactor drops the pde_signals param), this catches
        it as "no difference" rather than as a crash.
        """
        raw_snap = {
            "mark_price": 100.0, "mark_freshness": "FRESH",
            "score": 60.0, "signal": "HOLD",
        }
        pde_signals = {
            "AAPL": {"confidence": 0.85, "horizon_alignment_score": 80.0, "horizon_conflict_flag": False},
        }
        scorer = v3pol.LearningScorer().fit()
        regime = v3pol.RegimeGrid(trend="UNKNOWN", vol_tercile="UNKNOWN", realized_vol_annualized=None)

        without = ppr._enrich_snap_for_v3(raw_snap, "AAPL", {})
        self.assertFalse(without.get("_v3_pde_enriched"))
        p_without, _ = scorer.predict_proba("BUY_PAPER", v3pol.build_pseudo_record(without, regime))

        with_signal = ppr._enrich_snap_for_v3(raw_snap, "AAPL", pde_signals)
        self.assertTrue(with_signal.get("_v3_pde_enriched"))
        self.assertEqual(with_signal["horizon_alignment_score"], 80.0)
        p_with, _ = scorer.predict_proba("BUY_PAPER", v3pol.build_pseudo_record(with_signal, regime))

        self.assertNotEqual(
            round(p_without, 6), round(p_with, 6),
            "enrichment made no difference to p_profit — if this is expected "
            "(e.g. the model no longer weighs horizon_alignment_score at all), "
            "update this test deliberately; don't let it pass by accident.",
        )

    def test_enrich_snap_preserves_original_fields_when_no_signal(self) -> None:
        raw_snap = {"mark_price": 100.0, "score": 60.0, "signal": "HOLD"}
        out = ppr._enrich_snap_for_v3(raw_snap, "ZZZZ_NOT_COVERED", {})
        self.assertFalse(out.get("_v3_pde_enriched"))
        self.assertEqual(out["mark_price"], 100.0)
        self.assertEqual(out["score"], 60.0)


class DecisionRecordCarriesFeatureSourceTest(unittest.TestCase):
    """
    The 'don't perpetuate silent gaps' follow-up: every V3 decision record
    must say whether it was scored with real PDE signal, so a future gap of
    this shape is visible in the journal (and to tae_daily_check.sh's
    feature-coverage watchdog) instead of only reachable by reading raw
    feature vectors by hand.
    """

    def test_pde_enriched_flag_present_on_merged_snap(self) -> None:
        enriched = ppr._enrich_snap_for_v3({"score": 1}, "AAPL", {"AAPL": {"confidence": 0.9}})
        self.assertIn("_v3_pde_enriched", enriched)
        self.assertTrue(enriched["_v3_pde_enriched"])

        not_enriched = ppr._enrich_snap_for_v3({"score": 1}, "AAPL", {})
        self.assertIn("_v3_pde_enriched", not_enriched)
        self.assertFalse(not_enriched["_v3_pde_enriched"])


if __name__ == "__main__":
    unittest.main()
