#!/usr/bin/env python3
"""Tests for tae_intraday_discovery_engine.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tae_intraday_discovery_engine import (
    build_discovery_report,
    compute_classification_learning,
    compute_daily_learning,
    compute_dataset_health,
    compute_ticker_learning,
    confidence_level,
    discover_patterns,
    generate_recommendations,
    write_discovery_outputs,
)


def _sample_history() -> pd.DataFrame:
    rows = []
    for i in range(12):
        ticker = ["PM", "LLY", "MU", "MRK"][i % 4]
        classification = "SIGNIFICANT_INTRADAY_FADE" if ticker == "PM" and i % 2 == 0 else "WATCH_INTRADAY_FADE"
        if ticker == "MU":
            classification = "POTENTIAL_PARTIAL_TAKE_PROFIT"
        rows.append(
            {
                "date": f"2026-06-{30 + (i // 6):02d}" if i < 6 else "2026-07-01",
                "timestamp": "2026-07-01T12:00:00",
                "run_id": f"run{i}",
                "ticker": ticker,
                "shares": 10.0,
                "avg_price": 100.0,
                "open": 101.0,
                "high": 105.0,
                "low": 99.0,
                "current": 102.0,
                "current_pct": 2.0,
                "high_pct": 5.0,
                "low_pct": -1.0,
                "missed_opportunity_usd": 60.0 + i,
                "drawdown_from_high_pct": -2.5,
                "classification": classification,
                "shadow_sell_20": 20.0,
                "shadow_sell_30": 25.0,
                "shadow_trailing_1": 40.0 + i,
                "shadow_trailing_1_5": 35.0,
            }
        )
    return pd.DataFrame(rows)


def _sample_summaries() -> list[dict]:
    return [
        {
            "date": "2026-06-30",
            "total_missed_opportunity": 366.7,
            "total_current_unrealized": -68.21,
            "total_theoretical_high": 298.48,
            "shadow_sell20_total": 120.0,
            "shadow_sell30_total": 140.0,
            "shadow_trailing1_total": 200.0,
            "shadow_trailing15_total": 180.0,
            "verdict": "TAE missed meaningful intraday opportunity.",
        },
        {
            "date": "2026-07-01",
            "total_missed_opportunity": 456.52,
            "total_current_unrealized": -8.28,
            "total_theoretical_high": 448.29,
            "shadow_sell20_total": 83.05,
            "shadow_sell30_total": 128.7,
            "shadow_trailing1_total": 248.1,
            "shadow_trailing15_total": 171.38,
            "verdict": "TAE missed meaningful intraday opportunity.",
        },
    ]


class IntradayDiscoveryEngineTest(unittest.TestCase):
    def test_dataset_health(self) -> None:
        df = _sample_history()
        health = compute_dataset_health(df)
        self.assertEqual(health["observations"], 12)
        self.assertEqual(health["unique_tickers"], 4)
        self.assertTrue(health["minimum_sample_warning"])
        self.assertIn(health["data_quality"], ("GOOD", "PARTIAL", "POOR"))

    def test_ticker_aggregation(self) -> None:
        tickers = compute_ticker_learning(_sample_history())
        self.assertGreaterEqual(len(tickers), 4)
        pm = next(t for t in tickers if t["ticker"] == "PM")
        self.assertEqual(pm["observations"], 3)
        self.assertGreater(pm["total_missed_opportunity"], 0)
        self.assertIn("best_shadow_strategy", pm)

    def test_classification_aggregation(self) -> None:
        classes = compute_classification_learning(_sample_history())
        labels = {c["classification"] for c in classes}
        self.assertIn("SIGNIFICANT_INTRADAY_FADE", labels)
        self.assertIn("WATCH_INTRADAY_FADE", labels)
        for row in classes:
            self.assertIn("avg_missed_opportunity", row)
            self.assertIn("best_shadow_strategy", row)

    def test_best_shadow_strategy_selection(self) -> None:
        tickers = compute_ticker_learning(_sample_history())
        pm = next(t for t in tickers if t["ticker"] == "PM")
        self.assertEqual(pm["best_shadow_strategy"], "shadow_trailing_1")

        daily = compute_daily_learning(_sample_summaries())
        self.assertEqual(daily[0]["best_shadow_strategy"], "shadow_trailing_1")

    def test_confidence_scoring(self) -> None:
        self.assertEqual(confidence_level(5), "LOW")
        self.assertEqual(confidence_level(15), "MEDIUM")
        self.assertEqual(confidence_level(35), "HIGH")

    def test_insufficient_sample_warning(self) -> None:
        health = compute_dataset_health(_sample_history())
        patterns = discover_patterns(health, compute_ticker_learning(_sample_history()), compute_daily_learning(_sample_summaries()))
        types = {p["pattern_type"] for p in patterns}
        self.assertIn("LOW_CONFIDENCE_INSUFFICIENT_SAMPLE", types)

    def test_pattern_generation(self) -> None:
        df = _sample_history()
        health = compute_dataset_health(df)
        tickers = compute_ticker_learning(df)
        daily = compute_daily_learning(_sample_summaries())
        patterns = discover_patterns(health, tickers, daily)
        types = {p["pattern_type"] for p in patterns}
        self.assertTrue(types & {"BEST_SHADOW_TRAILING", "BEST_SHADOW_PARTIAL_SELL", "HIGH_FADE_TICKER", "REPEATED_SIGNIFICANT_FADE"})
        for pattern in patterns:
            for key in ("id", "pattern_type", "scope", "subject", "metric", "value", "confidence", "recommendation"):
                self.assertIn(key, pattern)

    def test_recommendations_generation(self) -> None:
        df = _sample_history()
        health = compute_dataset_health(df)
        tickers = compute_ticker_learning(df)
        patterns = discover_patterns(health, tickers, compute_daily_learning(_sample_summaries()))
        recs = generate_recommendations(health, patterns, tickers)
        self.assertTrue(recs)
        for rec in recs:
            self.assertEqual(rec["mode"], "SHADOW_ONLY")
            self.assertIn(rec["recommendation"], {
                "CONTINUE_OBSERVATION",
                "PRIORITIZE_TRACKING",
                "TEST_TRAILING_SHADOW",
                "TEST_PARTIAL_SELL_SHADOW",
                "INSUFFICIENT_DATA",
            })

    def test_markdown_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_path = base / "history.csv"
            json_path = base / "daily.json"
            _sample_history().to_csv(csv_path, index=False)
            json_path.write_text(
                json.dumps({"summaries": _sample_summaries()}),
                encoding="utf-8",
            )
            report = build_discovery_report(history_csv=csv_path, daily_json=json_path)
            out_json = base / "out.json"
            out_md = base / "out.md"

            import tae_intraday_discovery_engine as engine

            orig_json = engine.OUTPUT_JSON
            orig_md = engine.OUTPUT_MD
            engine.OUTPUT_JSON = out_json
            engine.OUTPUT_MD = out_md
            try:
                write_discovery_outputs(report)
            finally:
                engine.OUTPUT_JSON = orig_json
                engine.OUTPUT_MD = orig_md

            self.assertTrue(out_json.exists())
            self.assertTrue(out_md.exists())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_intraday_discovery_engine")
            self.assertIn("ticker_learning", loaded)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
