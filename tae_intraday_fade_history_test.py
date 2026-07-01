#!/usr/bin/env python3
"""Tests for tae_intraday_fade_history.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tae_intraday_fade_history import (
    append_history,
    build_aggregate_summary,
    daily_summary_from_report,
    dedupe_position_rows,
    load_daily_summaries,
    load_history_records,
    position_row_from_report,
    record_fade_report,
    run_id_exists,
)


def _sample_report(run_id: str = "run20260630T120000") -> dict:
    return {
        "generated_at": "2026-06-30T12:00:00",
        "run_id": run_id,
        "daily_verdict": "TAE missed meaningful intraday opportunity.",
        "totals": {
            "total_current_unrealized_usd": -68.21,
            "total_at_high_usd": 298.48,
            "total_missed_opportunity_usd": 366.7,
            "total_shadow_sell_20_at_high_usd": 120.0,
            "total_shadow_sell_30_at_high_usd": 140.0,
            "total_shadow_trailing_1pct_usd": 200.0,
            "total_shadow_trailing_1_5pct_usd": 180.0,
        },
        "positions": [
            {
                "ticker": "PM",
                "shares": 10.0,
                "avg_price": 180.0,
                "open_price": 181.0,
                "high": 186.0,
                "low": 179.0,
                "current": 180.85,
                "current_pct": 0.47,
                "high_pct": 3.33,
                "low_pct": -0.56,
                "missed_opportunity_usd": 70.41,
                "drawdown_from_high_pct": -2.77,
                "classification": "SIGNIFICANT_INTRADAY_FADE",
                "shadow": {
                    "sell_20_at_high_pnl": 60.0,
                    "sell_30_at_high_pnl": 65.0,
                    "trailing_1pct_pnl": 58.0,
                    "trailing_1_5pct_pnl": 55.0,
                },
            },
            {
                "ticker": "PM",
                "shares": 10.0,
                "avg_price": 180.0,
                "classification": "SIGNIFICANT_INTRADAY_FADE",
            },
            {
                "ticker": "LLY",
                "shares": 2.0,
                "avg_price": 1200.0,
                "open_price": 1205.0,
                "high": 1230.0,
                "low": 1190.0,
                "current": 1198.0,
                "current_pct": -0.17,
                "high_pct": 2.5,
                "low_pct": -0.83,
                "missed_opportunity_usd": 63.08,
                "drawdown_from_high_pct": -2.6,
                "classification": "WATCH_INTRADAY_FADE",
                "shadow": {
                    "sell_20_at_high_pnl": 12.0,
                    "sell_30_at_high_pnl": 18.0,
                    "trailing_1pct_pnl": 20.0,
                    "trailing_1_5pct_pnl": 19.0,
                },
            },
        ],
    }


class IntradayFadeHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.history_json = self.base / "history.json"
        self.history_csv = self.base / "history.csv"
        self.daily_json = self.base / "daily.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_append_csv_and_json(self) -> None:
        report = _sample_report()
        result = append_history(
            report,
            history_json=self.history_json,
            history_csv=self.history_csv,
            daily_summary_json=self.daily_json,
        )
        self.assertTrue(result["appended"])
        self.assertEqual(result["records_added"], 2)

        records = load_history_records(self.history_json)
        self.assertEqual(len(records), 2)
        self.assertTrue(self.history_csv.exists())
        csv_text = self.history_csv.read_text(encoding="utf-8")
        self.assertIn("PM", csv_text)
        self.assertIn("LLY", csv_text)

        summaries = load_daily_summaries(self.daily_json)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["total_missed_opportunity"], 366.7)

    def test_duplicate_run_id_protection(self) -> None:
        report = _sample_report()
        first = append_history(
            report,
            history_json=self.history_json,
            history_csv=self.history_csv,
            daily_summary_json=self.daily_json,
        )
        second = append_history(
            report,
            history_json=self.history_json,
            history_csv=self.history_csv,
            daily_summary_json=self.daily_json,
        )
        self.assertTrue(first["appended"])
        self.assertFalse(second["appended"])
        self.assertEqual(second["reason"], "duplicate_run_id")
        self.assertEqual(len(load_history_records(self.history_json)), 2)

    def test_dedupe_ticker_within_run(self) -> None:
        rows = dedupe_position_rows(
            [
                {"ticker": "PM", "missed_opportunity_usd": 70.0},
                {"ticker": "pm", "missed_opportunity_usd": 1.0},
                {"ticker": "LLY", "missed_opportunity_usd": 63.0},
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ticker"], "PM")

    def test_daily_summary_generation(self) -> None:
        summary = daily_summary_from_report(
            _sample_report(),
            date="2026-06-30",
            timestamp="2026-06-30T12:00:00",
            run_id="run20260630T120000",
        )
        self.assertEqual(summary["num_significant_intraday_fade"], 1)
        self.assertEqual(summary["num_watch_intraday_fade"], 1)
        self.assertEqual(summary["shadow_trailing1_total"], 200.0)
        self.assertIn("missed", summary["verdict"].lower())

    def test_top_missed_and_classification_counts(self) -> None:
        records = [
            position_row_from_report(
                _sample_report()["positions"][0],
                date="2026-06-30",
                timestamp="2026-06-30T12:00:00",
                run_id="r1",
            ),
            position_row_from_report(
                _sample_report()["positions"][2],
                date="2026-06-30",
                timestamp="2026-06-30T13:00:00",
                run_id="r2",
            ),
            {
                **position_row_from_report(
                    _sample_report()["positions"][0],
                    date="2026-07-01",
                    timestamp="2026-07-01T12:00:00",
                    run_id="r3",
                ),
                "ticker": "PM",
                "missed_opportunity_usd": 50.0,
            },
        ]
        summaries = [
            daily_summary_from_report(
                _sample_report("r1"),
                date="2026-06-30",
                timestamp="2026-06-30T12:00:00",
                run_id="r1",
            )
        ]
        agg = build_aggregate_summary(records, summaries)
        self.assertEqual(agg["number_of_observations"], 3)
        self.assertEqual(agg["number_of_days_observed"], 2)
        self.assertEqual(agg["top_tickers_by_missed_opportunity"][0]["ticker"], "PM")
        self.assertGreaterEqual(
            agg["classification_totals"]["SIGNIFICANT_INTRADAY_FADE"], 2
        )

    def test_best_shadow_strategy_selection(self) -> None:
        summaries = [
            {
                "shadow_sell20_total": 100.0,
                "shadow_sell30_total": 120.0,
                "shadow_trailing1_total": 250.0,
                "shadow_trailing15_total": 200.0,
            },
            {
                "shadow_sell20_total": 50.0,
                "shadow_sell30_total": 60.0,
                "shadow_trailing1_total": 80.0,
                "shadow_trailing15_total": 90.0,
            },
        ]
        agg = build_aggregate_summary([], summaries)
        best = agg["best_shadow_strategy"]
        self.assertIsNotNone(best)
        self.assertEqual(best["strategy"], "shadow_trailing1_total")
        self.assertEqual(best["total_usd"], 330.0)

    def test_record_fade_report_wrapper(self) -> None:
        report = _sample_report("wrapper_run")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            hist = base / "h.json"
            csv = base / "h.csv"
            daily = base / "d.json"
            result = record_fade_report(report)
            self.assertIn("appended", result)
            # default paths not used; call append directly for isolated test
            isolated = append_history(
                report,
                history_json=hist,
                history_csv=csv,
                daily_summary_json=daily,
            )
            self.assertTrue(isolated["appended"])

    def test_run_id_exists(self) -> None:
        rows = [{"run_id": "abc"}, {"run_id": "def"}]
        self.assertTrue(run_id_exists("abc", rows))
        self.assertFalse(run_id_exists("xyz", rows))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
