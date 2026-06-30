#!/usr/bin/env python3
"""Tests for tae_intraday_fade_intelligence.py — shadow math and classification."""

from __future__ import annotations

import unittest

import pandas as pd

from tae_intraday_fade_intelligence import (
    IntradayQuote,
    OpenPosition,
    analyze_position,
    classify_position,
    fifo_open_positions,
    missed_opportunity_usd,
    simulate_shadow_strategies,
)


class IntradayFadeIntelligenceTest(unittest.TestCase):
    def test_fifo_open_position_avg(self) -> None:
        portfolio = pd.DataFrame(
            [
                {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10.0},
                {"Ticker": "AAPL", "Action": "SELL", "Price": 110.0, "Shares": 4.0},
                {"Ticker": "AAPL", "Action": "BUY", "Price": 120.0, "Shares": 5.0},
            ]
        )
        positions = fifo_open_positions(portfolio)
        self.assertIn("AAPL", positions)
        self.assertAlmostEqual(positions["AAPL"].shares, 11.0, places=4)
        # 6 shares @100 + 5 shares @120 = 1200/11
        self.assertAlmostEqual(positions["AAPL"].avg_price, 1200 / 11, places=4)

    def test_missed_opportunity_calculation(self) -> None:
        missed = missed_opportunity_usd(shares=10, avg=100, high=110, current=105)
        self.assertEqual(missed, 50.0)

    def test_classification_significant_intraday_fade(self) -> None:
        label = classify_position(
            high_pct=2.0,
            current_pct=0.5,
            low_pct=-1.0,
            missed_usd=70.0,
        )
        self.assertEqual(label, "SIGNIFICANT_INTRADAY_FADE")

    def test_no_data_data_unavailable(self) -> None:
        row = analyze_position(
            OpenPosition("SPY", 1.0, 500.0),
            None,
        )
        self.assertEqual(row["classification"], "DATA_UNAVAILABLE")

    def test_partial_sell_simulation_math(self) -> None:
        shadow = simulate_shadow_strategies(shares=10, avg=100, high=110, current=105)
        # 20% at high: 2*(110-100)=20; 80% at current: 8*(105-100)=40 => 60
        self.assertEqual(shadow.sell_20_at_high_pnl, 60.0)
        # 30% at high: 3*10=30; 70% at current: 7*5=35 => 65
        self.assertEqual(shadow.sell_30_at_high_pnl, 65.0)

    def test_analyze_position_fields(self) -> None:
        row = analyze_position(
            OpenPosition("PM", 10.0, 180.0),
            IntradayQuote(open_price=181.0, low=179.0, high=186.0, current=180.85, interval="1m"),
        )
        self.assertEqual(row["ticker"], "PM")
        self.assertGreater(row["missed_opportunity_usd"], 0)
        self.assertIn("shadow", row)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
