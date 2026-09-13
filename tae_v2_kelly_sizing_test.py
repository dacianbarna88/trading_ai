#!/usr/bin/env python3
"""
Regression coverage for V2's empirical-Kelly tranche sizing and its new-
ticker position cap.

Context: real audit of V2's closed trades (41 days) found profit factor
10.49 (81.5% win rate) diluted across 50 concurrent ~$520 positions because
(a) no MAX_POSITIONS gate existed for V2 at all, and (b) sizing was a flat
0.20 tranche_fraction regardless of V2's own measured edge. This module
adds both without touching V2's entry-signal logic.

Uses the REAL trades.jsonl for the isolated V2 parallel-paper arm when it
exists in this checkout (real-shape data, not a fabricated fixture); falls
back to an explicit synthetic-but-realistic-shaped fixture for the
deterministic boundary-condition tests, since those need exact, known
inputs to assert exact outputs.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tae_strategy_v2_kelly_sizing as v2kelly


def _write_trades(path: Path, pnls: list[float]) -> None:
    with path.open("w") as fh:
        for i, pnl in enumerate(pnls):
            fh.write(
                json.dumps(
                    {
                        "ts": f"2026-08-{(i % 28) + 1:02d}T10:00:00Z",
                        "ticker": "TEST",
                        "action": "CLOSE",
                        "realized_pnl": pnl,
                    }
                )
                + "\n"
            )


class EmptyHistoryTest(unittest.TestCase):
    def test_no_file_returns_prior_defaults(self) -> None:
        p_profit, payoff_ratio, diag = v2kelly.compute_v2_empirical_edge(
            "/nonexistent/path/trades.jsonl"
        )
        self.assertEqual(p_profit, v2kelly.DEFAULT_P_PROFIT)
        self.assertEqual(payoff_ratio, v2kelly.DEFAULT_PAYOFF_RATIO)
        self.assertEqual(diag["source"], "PRIOR_ONLY_NO_DATA")


class ThinSampleShrinkageTest(unittest.TestCase):
    def test_thin_sample_shrinks_toward_prior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            # 2 wins, 1 loss — a tiny sample that should NOT be taken at face value.
            _write_trades(path, [50.0, 30.0, -10.0])
            p_profit, payoff_ratio, diag = v2kelly.compute_v2_empirical_edge(path)
            raw_p = 2 / 3
            # shrunk value must sit strictly between the raw estimate and the prior
            self.assertLess(p_profit, raw_p)
            self.assertGreater(p_profit, v2kelly.DEFAULT_P_PROFIT)
            self.assertEqual(diag["source"], "SHRUNK_TOWARD_PRIOR")


class StrongEmpiricalEdgeTest(unittest.TestCase):
    def test_strong_measured_edge_scales_tranche_fraction_up(self) -> None:
        """Mirrors V2's real audited numbers: 81.5% win rate, ~2.38 payoff ratio."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            wins = [28.03] * 22
            losses = [-11.76] * 5
            _write_trades(path, wins + losses)
            fraction, diag = v2kelly.v2_tranche_fraction_from_edge(path)
            self.assertGreater(
                fraction,
                0.20,
                "a measured edge this strong must size up, not stay at the old flat 0.20",
            )
            self.assertLessEqual(fraction, 0.50, "must respect max_fraction clamp")
            self.assertEqual(diag["source"], "EMPIRICAL")

    def test_weak_or_losing_edge_does_not_exceed_prior_sizing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            # A losing record like V1's real audited numbers (28.6% win rate).
            wins = [75.40] * 10
            losses = [-51.32] * 25
            _write_trades(path, wins + losses)
            fraction, _diag = v2kelly.v2_tranche_fraction_from_edge(path)
            self.assertLessEqual(fraction, 0.20)
            self.assertGreaterEqual(fraction, 0.05, "must respect min_fraction clamp")


class ClampBoundsTest(unittest.TestCase):
    def test_fraction_never_exceeds_configured_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            _write_trades(path, [100.0] * 50)  # unrealistically perfect record
            fraction, _diag = v2kelly.v2_tranche_fraction_from_edge(
                path, min_fraction=0.05, max_fraction=0.50
            )
            self.assertLessEqual(fraction, 0.50)
            self.assertGreaterEqual(fraction, 0.05)


class RealDataSmokeTest(unittest.TestCase):
    """If the real V2 trades journal exists in this checkout, confirm the
    function runs end-to-end on it without raising and returns a fraction
    within the configured bounds — catches any real-shape parsing issue a
    synthetic fixture might not."""

    def test_real_v2_trades_journal_if_present(self) -> None:
        real_path = Path("runtime_outputs/parallel_paper/v2/journals/trades.jsonl")
        if not real_path.exists():
            self.skipTest("no real V2 trades.jsonl in this checkout")
        fraction, diag = v2kelly.v2_tranche_fraction_from_edge(real_path)
        self.assertGreaterEqual(fraction, 0.05)
        self.assertLessEqual(fraction, 0.50)
        self.assertIn("p_profit", diag)
        self.assertIn("payoff_ratio", diag)


class EntryScoreFilterTest(unittest.TestCase):
    """2026-09-13: V1_V2_ENTRY_MIN_SCORE was raised 60->100. Without a
    filter, the empirical edge keeps blending old score-60/80 trades
    (weak/noisy, per tae_score_decile_backtest.py) into the sizing input
    forever, silently understating what the CURRENT gate actually
    produces. min_entry_score must exclude pre-regime-change trades."""

    def _write_trade_with_entry(self, fh, *, ticker: str, decision_id: str, ts_buy: str, ts_close: str, pnl: float) -> None:
        fh.write(json.dumps({"ts": ts_buy, "ticker": ticker, "action": "BUY", "decision_id": decision_id}) + "\n")
        fh.write(json.dumps({"ts": ts_close, "ticker": ticker, "action": "CLOSE", "realized_pnl": pnl}) + "\n")

    def test_filters_out_trades_entered_below_the_current_score_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trades_path = Path(tmp) / "trades.jsonl"
            decisions_path = Path(tmp) / "decisions.jsonl"
            with trades_path.open("w") as fh:
                self._write_trade_with_entry(
                    fh, ticker="OLD", decision_id="D-OLD",
                    ts_buy="2026-07-01T10:00:00Z", ts_close="2026-07-05T10:00:00Z", pnl=5.0,
                )
                self._write_trade_with_entry(
                    fh, ticker="NEW", decision_id="D-NEW",
                    ts_buy="2026-09-13T10:00:00Z", ts_close="2026-09-14T10:00:00Z", pnl=50.0,
                )
            with decisions_path.open("w") as fh:
                fh.write(json.dumps({"decision_id": "D-OLD", "score": 80.0}) + "\n")
                fh.write(json.dumps({"decision_id": "D-NEW", "score": 100.0}) + "\n")

            _, _, diag = v2kelly.compute_v2_empirical_edge(
                trades_path, min_entry_score=100.0, decisions_path=decisions_path
            )
            self.assertEqual(diag["n_samples"], 1)

    def test_without_min_entry_score_counts_everything_unfiltered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trades_path = Path(tmp) / "trades.jsonl"
            decisions_path = Path(tmp) / "decisions.jsonl"
            with trades_path.open("w") as fh:
                self._write_trade_with_entry(
                    fh, ticker="OLD", decision_id="D-OLD",
                    ts_buy="2026-07-01T10:00:00Z", ts_close="2026-07-05T10:00:00Z", pnl=5.0,
                )
                self._write_trade_with_entry(
                    fh, ticker="NEW", decision_id="D-NEW",
                    ts_buy="2026-09-13T10:00:00Z", ts_close="2026-09-14T10:00:00Z", pnl=50.0,
                )
            with decisions_path.open("w") as fh:
                fh.write(json.dumps({"decision_id": "D-OLD", "score": 80.0}) + "\n")
                fh.write(json.dumps({"decision_id": "D-NEW", "score": 100.0}) + "\n")

            _, _, diag = v2kelly.compute_v2_empirical_edge(trades_path)
            self.assertEqual(diag["n_samples"], 2)

    def test_zero_qualifying_trades_shrinks_fully_to_prior_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trades_path = Path(tmp) / "trades.jsonl"
            decisions_path = Path(tmp) / "decisions.jsonl"
            with trades_path.open("w") as fh:
                self._write_trade_with_entry(
                    fh, ticker="OLD", decision_id="D-OLD",
                    ts_buy="2026-07-01T10:00:00Z", ts_close="2026-07-05T10:00:00Z", pnl=5.0,
                )
            with decisions_path.open("w") as fh:
                fh.write(json.dumps({"decision_id": "D-OLD", "score": 80.0}) + "\n")

            p_profit, payoff_ratio, diag = v2kelly.compute_v2_empirical_edge(
                trades_path, min_entry_score=100.0, decisions_path=decisions_path
            )
            self.assertEqual(p_profit, v2kelly.DEFAULT_P_PROFIT)
            self.assertEqual(payoff_ratio, v2kelly.DEFAULT_PAYOFF_RATIO)
            self.assertEqual(diag["source"], "PRIOR_ONLY_NO_DATA")


class RuntimeWiringSmokeTest(unittest.TestCase):
    def test_runtime_imports_v2kelly_module_and_max_positions_constant(self) -> None:
        import tae_parallel_paper_runtime as ppr

        self.assertTrue(hasattr(ppr, "v2kelly"))
        self.assertTrue(hasattr(ppr.v2kelly, "v2_tranche_fraction_from_edge"))
        # 2026-09-08: raised from 18 to 55 — the original 18 was set without
        # accounting for V2 already holding 49 positions, which made the cap
        # a permanent freeze on all new entries instead of a growth limit.
        self.assertEqual(ppr.V2_MAX_POSITIONS, 55)

    def test_runtime_passes_min_entry_score_to_kelly_edge_computation(self) -> None:
        import inspect

        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr)
        self.assertIn("v2kelly.v2_tranche_fraction_from_edge(", source)
        self.assertIn("min_entry_score=V1_V2_ENTRY_MIN_SCORE", source)


if __name__ == "__main__":
    unittest.main()
