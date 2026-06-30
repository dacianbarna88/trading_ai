#!/usr/bin/env python3
"""Tests for independent position risk monitor (AAPL stop-loss resilience fix)."""

from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

import pandas as pd

import live_bot


def _empty_portfolio() -> pd.DataFrame:
    return live_bot.load_csv_safe(
        live_bot.PORTFOLIO_FILE,
        [
            "Date",
            "Ticker",
            "Action",
            "Price",
            "Shares",
            "Score",
            "Signal",
            "Reason",
            "Current_Price",
            "Invested",
            "Current_Value",
            "PnL",
            "PnL_%",
        ],
    )


def _aapl_buy_portfolio() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": "2026-06-24 18:53:50",
                "Ticker": "AAPL",
                "Action": "BUY",
                "Price": 299.59,
                "Shares": 8.3447,
                "Score": 80,
                "Signal": "STRONG BUY",
                "Reason": "TEST BUY",
                "Current_Price": 299.59,
                "Invested": 2499.9887,
                "Current_Value": 2499.9887,
                "PnL": 0.0,
                "PnL_%": 0.0,
            }
        ]
    )


class IndependentPositionRiskTest(unittest.TestCase):
    @patch("live_bot.send_telegram")
    @patch("core.market_data_layer.get_market_price")
    def test_stop_loss_when_ticker_absent_from_signals(self, mock_quote_fn, _mock_tg):
        from core.market_data_layer import PriceResult

        mock_quote_fn.return_value = PriceResult(
            ticker="AAPL",
            price=276.91,
            fetched_at=None,
            source="test",
            age_seconds=0.0,
            status="DATA_OK",
            consecutive_failures=0,
        )
        portfolio = _aapl_buy_portfolio()
        signals_df = pd.DataFrame(columns=["Ticker", "Signal", "Score", "Price", "RSI"])

        result = live_bot.manage_position_risk_independent(portfolio, signals_df)
        sells = result[result["Action"].astype(str).str.upper() == "SELL"]

        self.assertEqual(len(sells), 1)
        self.assertIn("INDEPENDENT RISK STOP LOSS", str(sells.iloc[0]["Reason"]))
        self.assertAlmostEqual(float(sells.iloc[0]["Price"]), 276.91, places=2)

        positions = live_bot.get_open_positions(result)
        self.assertNotIn("AAPL", positions)

    @patch("core.market_data_layer.get_market_price")
    def test_stale_price_skips_sell_and_logs(self, mock_quote_fn):
        from core.market_data_layer import PriceResult

        mock_quote_fn.return_value = PriceResult(
            ticker="AAPL",
            price=None,
            fetched_at=None,
            source=None,
            age_seconds=130.0,
            status="DATA_CRITICAL",
            consecutive_failures=6,
            error="all fetch paths failed",
        )
        portfolio = _aapl_buy_portfolio()
        log_buffer = StringIO()

        with patch("live_bot.log", side_effect=lambda msg: log_buffer.write(msg + "\n")):
            result = live_bot.manage_position_risk_independent(portfolio, None)

        sells = result[result["Action"].astype(str).str.upper() == "SELL"]
        self.assertTrue(sells.empty)
        self.assertIn("RISK DATA STALE pentru AAPL", log_buffer.getvalue())
        self.assertIn("AAPL", live_bot.get_open_positions(result))

    def test_fifo_avg_price_ignores_closed_lots(self):
        portfolio = pd.DataFrame(
            [
                {
                    "Date": "2026-06-07 02:59:02",
                    "Ticker": "AAPL",
                    "Action": "BUY",
                    "Price": 307.34,
                    "Shares": 3.2537,
                    "Score": 100,
                    "Signal": "STRONG BUY",
                    "Reason": "OLD BUY",
                    "Current_Price": None,
                    "Invested": None,
                    "Current_Value": None,
                    "PnL": None,
                    "PnL_%": None,
                },
                {
                    "Date": "2026-06-09 19:04:45",
                    "Ticker": "AAPL",
                    "Action": "SELL",
                    "Price": 291.26,
                    "Shares": 3.2537,
                    "Score": 80,
                    "Signal": "STRONG BUY",
                    "Reason": "OLD SELL",
                    "Current_Price": None,
                    "Invested": None,
                    "Current_Value": None,
                    "PnL": None,
                    "PnL_%": None,
                },
                {
                    "Date": "2026-06-24 18:53:50",
                    "Ticker": "AAPL",
                    "Action": "BUY",
                    "Price": 299.59,
                    "Shares": 8.3447,
                    "Score": 80,
                    "Signal": "STRONG BUY",
                    "Reason": "OPEN BUY",
                    "Current_Price": None,
                    "Invested": None,
                    "Current_Value": None,
                    "PnL": None,
                    "PnL_%": None,
                },
            ]
        )

        positions = live_bot.get_open_positions(portfolio)
        self.assertIn("AAPL", positions)
        self.assertAlmostEqual(positions["AAPL"]["avg_price"], 299.59, places=2)
        self.assertAlmostEqual(positions["AAPL"]["shares"], 8.3447, places=4)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
