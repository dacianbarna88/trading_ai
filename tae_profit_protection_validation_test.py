#!/usr/bin/env python3
"""Tests for tae_profit_protection_validation.py (X.PROTECT-2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tae_profit_protection_validation import (
    FORBIDDEN_RECOMMENDATIONS,
    SHADOW_RECOMMENDATIONS,
    aggregate_classifications,
    aggregate_daily,
    aggregate_strategy,
    aggregate_tickers,
    build_recommendations,
    build_validation_report,
    dataset_health,
    enrich_observations,
    evaluate_gates,
    load_history,
    render_markdown,
    select_best_strategy,
    write_outputs,
)


SAMPLE_ROWS = [
    {
        "date": "2026-07-01",
        "timestamp": "2026-07-01T10:00:00",
        "run_id": "run1",
        "ticker": "MU",
        "shares": 2.0,
        "avg_price": 100.0,
        "current": 105.0,
        "missed_opportunity_usd": 50.0,
        "classification": "SIGNIFICANT_INTRADAY_FADE",
        "shadow_sell_20": 12.0,
        "shadow_sell_30": 15.0,
        "shadow_trailing_1": 20.0,
        "shadow_trailing_1_5": 18.0,
    },
    {
        "date": "2026-07-01",
        "timestamp": "2026-07-01T10:00:00",
        "run_id": "run1",
        "ticker": "PM",
        "shares": 10.0,
        "avg_price": 180.0,
        "current": 181.0,
        "missed_opportunity_usd": 70.0,
        "classification": "SIGNIFICANT_INTRADAY_FADE",
        "shadow_sell_20": 60.0,
        "shadow_sell_30": 65.0,
        "shadow_trailing_1": 58.0,
        "shadow_trailing_1_5": 55.0,
    },
]


def _make_df(rows: list[dict] | None = None) -> pd.DataFrame:
    data = rows if rows is not None else SAMPLE_ROWS
    return enrich_observations(pd.DataFrame(data))


class ProfitProtectionValidationTest(unittest.TestCase):
    def test_missing_history_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_validation_report(history_path=Path(tmp) / "missing.csv")
            self.assertEqual(report["verdict"], "NO_HISTORY")
            self.assertEqual(report["dataset_health"]["observations"], 0)
            self.assertEqual(report["gates"]["advisory_readiness"], "NOT_READY")
            self.assertIn("INSUFFICIENT_DATA", report["recommendations"])

    def test_dataset_health(self) -> None:
        df = _make_df()
        health = dataset_health(df)
        self.assertEqual(health["observations"], 2)
        self.assertEqual(health["unique_tickers"], 2)
        self.assertTrue(health["minimum_sample_warning"])
        self.assertEqual(health["confidence"], "LOW")

    def test_strategy_aggregation(self) -> None:
        df = _make_df()
        trailing = aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1")
        self.assertEqual(trailing["total_value"], 78.0)
        self.assertGreater(trailing["avg_value"], 0)

    def test_win_rate_calculation(self) -> None:
        df = _make_df()
        trailing = aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1")
        self.assertEqual(trailing["win_count"], 2)
        self.assertEqual(trailing["win_rate"], 1.0)

    def test_best_strategy_selection(self) -> None:
        df = _make_df()
        stats = [
            aggregate_strategy(df, sid, col)
            for sid, col in [
                ("HOLD", "hold_pnl"),
                ("shadow_sell_20", "shadow_sell_20"),
                ("shadow_trailing_1", "shadow_trailing_1"),
            ]
        ]
        best = select_best_strategy(stats)
        self.assertEqual(best["strategy_id"], "shadow_trailing_1")

    def test_protection_efficiency(self) -> None:
        df = _make_df()
        trailing = aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1")
        self.assertGreater(trailing["protection_efficiency"], 0)

    def test_risk_of_cutting_winners(self) -> None:
        rows = [
            {
                **SAMPLE_ROWS[0],
                "shadow_trailing_1": 5.0,
            }
        ]
        df = _make_df(rows)
        trailing = aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1")
        self.assertEqual(trailing["risk_of_cutting_winners"], 1)
        self.assertEqual(trailing["risk_of_cutting_winners_rate"], 1.0)

    def test_ticker_aggregation(self) -> None:
        df = _make_df()
        stats = [aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1")]
        tickers = aggregate_tickers(df, stats)
        self.assertEqual(len(tickers), 2)
        self.assertEqual(tickers[0]["ticker"], "PM")

    def test_classification_aggregation(self) -> None:
        df = _make_df()
        classes = aggregate_classifications(df)
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]["classification"], "SIGNIFICANT_INTRADAY_FADE")

    def test_daily_aggregation(self) -> None:
        df = _make_df()
        best = select_best_strategy(
            [
                aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1"),
                aggregate_strategy(df, "shadow_sell_20", "shadow_sell_20"),
            ]
        )
        daily = aggregate_daily(df, best)
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["verdict"], "SHADOW_OUTPERFORMS_HOLD")

    def test_gates_g1_g6(self) -> None:
        df = _make_df()
        health = dataset_health(df)
        stats = [
            aggregate_strategy(df, "HOLD", "hold_pnl"),
            aggregate_strategy(df, "shadow_trailing_1", "shadow_trailing_1"),
        ]
        best = select_best_strategy(stats)
        hold = stats[0]
        tickers = aggregate_tickers(df, stats)
        gates = evaluate_gates(df, health, best, hold, tickers)
        self.assertFalse(gates["gates"]["G1"])
        self.assertIn("G1", gates["failed_gates"])

    def test_not_ready_small_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "history.csv"
            _make_df().to_csv(csv_path, index=False)
            report = build_validation_report(history_path=csv_path)
            self.assertEqual(report["gates"]["advisory_readiness"], "NOT_READY")
            self.assertIn("DO_NOT_PROMOTE_TO_ADVISORY_YET", report["recommendations"])

    def test_markdown_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_path = base / "history.csv"
            _make_df().to_csv(csv_path, index=False)
            report = build_validation_report(history_path=csv_path)
            out_json = base / "out.json"
            out_md = base / "out.md"
            import tae_profit_protection_validation as mod

            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD)
            mod.OUTPUT_JSON, mod.OUTPUT_MD = out_json, out_md
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD = orig
            self.assertTrue(out_json.exists())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_profit_protection_validation")
            md = out_md.read_text(encoding="utf-8")
            self.assertIn("Gates G1–G6", md)

    def test_no_live_buy_sell_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "history.csv"
            _make_df().to_csv(csv_path, index=False)
            report = build_validation_report(history_path=csv_path)
            for rec in report["recommendations"]:
                self.assertIn(rec, SHADOW_RECOMMENDATIONS)
                self.assertNotIn(rec, FORBIDDEN_RECOMMENDATIONS)

    def test_load_history_excludes_data_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "history.csv"
            df = pd.DataFrame(
                [
                    {**SAMPLE_ROWS[0], "classification": "DATA_UNAVAILABLE"},
                    SAMPLE_ROWS[1],
                ]
            )
            df.to_csv(csv_path, index=False)
            loaded = load_history(csv_path)
            self.assertEqual(len(loaded), 1)

    def test_recommendations_insufficient_data(self) -> None:
        health = {"minimum_sample_warning": True, "observations": 2}
        gates = {"advisory_readiness": "NOT_READY"}
        best = {"strategy_id": "shadow_trailing_1", "delta_vs_hold_total": 10}
        recs = build_recommendations(health, gates, best)
        self.assertIn("INSUFFICIENT_DATA", recs)

    def test_render_markdown_contains_sections(self) -> None:
        report = build_validation_report(history_path=Path("/nonexistent/history.csv"))
        md = render_markdown(report)
        self.assertIn("Dataset health", md)
        self.assertIn("Strategy ranking", md)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
