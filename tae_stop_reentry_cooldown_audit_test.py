#!/usr/bin/env python3
"""Tests for tae_stop_reentry_cooldown_audit.py (X.COOLDOWN-1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tae_stop_reentry_cooldown_audit import (
    FORBIDDEN_RECOMMENDATIONS,
    SHADOW_RECOMMENDATIONS,
    build_audit_report,
    classify_reentry_timing,
    detect_stop_reentries,
    evaluate_gates,
    load_portfolio,
    render_markdown,
    simulate_cooldowns,
    write_outputs,
)


def _portfolio_csv(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


SAMPLE_ROWS = [
    {
        "Date": "2026-07-01 16:31:02",
        "Ticker": "MU",
        "Action": "SELL",
        "Price": 1086.94,
        "Shares": 2.0,
        "Score": 100,
        "Signal": "STRONG BUY",
        "Reason": "STOP LOSS -5.09%",
        "Current_Price": 1086.94,
        "Invested": 2500.0,
        "Current_Value": 2173.88,
        "PnL": -127.35,
        "PnL_%": -5.09,
    },
    {
        "Date": "2026-07-01 16:32:22",
        "Ticker": "MU",
        "Action": "BUY",
        "Price": 1074.75,
        "Shares": 2.0,
        "Score": 100,
        "Signal": "STRONG BUY",
        "Reason": "AUTO STRONG BUY",
        "Current_Price": 1032.0,
        "Invested": 2149.5,
        "Current_Value": 2064.0,
        "PnL": -85.5,
        "PnL_%": -3.98,
    },
    {
        "Date": "2026-07-01 20:48:20",
        "Ticker": "MU",
        "Action": "SELL",
        "Price": 1042.2,
        "Shares": 2.0,
        "Score": 100,
        "Signal": "STRONG BUY",
        "Reason": "STOP LOSS -3.03%",
        "Current_Price": 1042.2,
        "Invested": 2149.5,
        "Current_Value": 2084.4,
        "PnL": -65.1,
        "PnL_%": -3.03,
    },
]


class StopReentryCooldownAuditTest(unittest.TestCase):
    def test_missing_input_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_audit_report(portfolio_path=Path(tmp) / "missing.csv")
            self.assertEqual(report["verdict"], "NO_PORTFOLIO_DATA")
            self.assertIn("INSUFFICIENT_DATA", report["recommendations"])

    def test_stop_buy_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            df = load_portfolio(path)
            sequences, stops = detect_stop_reentries(df, pd.DataFrame())
            self.assertEqual(len(stops), 2)
            self.assertEqual(len(sequences), 1)
            self.assertEqual(sequences[0]["ticker"], "MU")

    def test_immediate_reentry_classification(self) -> None:
        tags = classify_reentry_timing(1.5, same_day=True)
        self.assertIn("IMMEDIATE_REENTRY", tags)
        self.assertIn("FAST_REENTRY", tags)
        self.assertIn("SAME_SESSION_REENTRY", tags)

    def test_fast_reentry_classification(self) -> None:
        tags = classify_reentry_timing(20.0, same_day=True)
        self.assertNotIn("IMMEDIATE_REENTRY", tags)
        self.assertIn("FAST_REENTRY", tags)

    def test_same_session_reentry(self) -> None:
        tags = classify_reentry_timing(120.0, same_day=True)
        self.assertIn("SAME_SESSION_REENTRY", tags)
        self.assertNotIn("IMMEDIATE_REENTRY", tags)

    def test_second_stop_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            df = load_portfolio(path)
            sequences, _ = detect_stop_reentries(df, pd.DataFrame())
            self.assertTrue(sequences[0]["second_stop"])
            self.assertEqual(sequences[0]["outcome"], "REENTRY_SECOND_STOP")

    def test_reentry_loss_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            df = load_portfolio(path)
            sequences, _ = detect_stop_reentries(df, pd.DataFrame())
            self.assertLess(sequences[0]["leg_pnl"], 0)

    def test_cooldown_blocks_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            df = load_portfolio(path)
            sequences, _ = detect_stop_reentries(df, pd.DataFrame())
            cooldown = simulate_cooldowns(sequences, df)
            sim15 = cooldown["simulations"]["cooldown_15m"]
            self.assertEqual(sim15["blocked_reentries"], 1)

    def test_cooldown_net_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            df = load_portfolio(path)
            sequences, _ = detect_stop_reentries(df, pd.DataFrame())
            cooldown = simulate_cooldowns(sequences, df)
            sim15 = cooldown["simulations"]["cooldown_15m"]
            self.assertGreater(sim15["net_effect_usd"], 0)

    def test_score_persistence_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            df = load_portfolio(path)
            sequences, _ = detect_stop_reentries(df, pd.DataFrame())
            self.assertTrue(sequences[0]["score_persistence_after_stop"])

    def test_small_sample_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            report = build_audit_report(portfolio_path=path)
            self.assertEqual(report["gates"]["advisory_readiness"], "NOT_READY")
            self.assertIn("DO_NOT_PROMOTE_TO_LIVE", report["recommendations"])

    def test_no_live_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            report = build_audit_report(portfolio_path=path)
            for rec in report["recommendations"]:
                self.assertIn(rec, SHADOW_RECOMMENDATIONS)
                self.assertNotIn(rec, FORBIDDEN_RECOMMENDATIONS)

    def test_gates_g1_g5(self) -> None:
        sequences = [{"second_stop": True, "leg_pnl": -10, "minutes_after_stop": 1, "same_session": True,
                      "stop_timestamp": "2026-07-01 16:31:02", "reentry_timestamp": "2026-07-01 16:32:22",
                      "ticker": "MU", "score_persistence_after_stop": True}] * 10
        cooldown = {
            "simulations": {
                "cooldown_30m": {
                    "net_effect_usd": 50,
                    "missed_gain_usd": 5,
                    "avoided_loss_usd": 55,
                    "second_stop_rate_reduction": 0.5,
                    "blocked_second_stops": 5,
                }
            },
            "best_cooldown": "cooldown_30m",
        }
        persistence = {"loss_rate": 0.8}
        gates = evaluate_gates(sequences, cooldown, persistence)
        self.assertTrue(gates["gates"]["G1"])
        self.assertTrue(gates["gates"]["G5"])

    def test_markdown_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / "portfolio.csv"
            _portfolio_csv(path, SAMPLE_ROWS)
            report = build_audit_report(portfolio_path=path)
            out_json = base / "out.json"
            out_md = base / "out.md"
            import tae_stop_reentry_cooldown_audit as mod

            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD)
            mod.OUTPUT_JSON, mod.OUTPUT_MD = out_json, out_md
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD = orig
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_stop_reentry_cooldown_audit")
            self.assertIn("Cooldown simulations", out_md.read_text(encoding="utf-8"))

    def test_render_markdown(self) -> None:
        report = build_audit_report(portfolio_path=Path("/nonexistent/portfolio.csv"))
        md = render_markdown(report)
        self.assertIn("Summary", md)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
