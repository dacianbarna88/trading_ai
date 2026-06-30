#!/usr/bin/env python3
"""Tests for core/market_data_layer.py — cache, retry, fallback, health."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import live_bot
from core.market_data_layer import (
    DISPLAY_CACHE_MAX_AGE,
    RISK_CACHE_MAX_AGE,
    STATUS_CRITICAL,
    STATUS_FAILING,
    STATUS_OK,
    STATUS_STALE,
    get_market_price,
    reset_market_data_state,
)


class MarketDataLayerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.tempdir.name) / "market_data_cache.json"
        self.health_path = Path(self.tempdir.name) / "market_data_health.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _seed_cache(
        self,
        ticker: str,
        price: float,
        age_seconds: float,
        failures: int = 0,
    ) -> None:
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        payload = {
            ticker.upper(): {
                "price": price,
                "fetched_at": fetched_at.isoformat(),
                "source": "seed",
                "consecutive_failures": failures,
                "status": STATUS_STALE,
            }
        }
        self.cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_retry_recovers_after_transient_failures(self) -> None:
        calls = {"count": 0}

        def fetch(_ticker: str):
            calls["count"] += 1
            if calls["count"] < 2:
                return None, None, "transient"
            return 101.25, "mock_live", None

        first = get_market_price(
            "SPY",
            purpose="risk",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=fetch,
        )
        self.assertIsNone(first.price)
        self.assertEqual(first.consecutive_failures, 1)

        second = get_market_price(
            "SPY",
            purpose="risk",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=fetch,
        )
        self.assertEqual(second.price, 101.25)
        self.assertEqual(second.status, STATUS_OK)
        self.assertEqual(second.consecutive_failures, 0)

    def test_fast_info_fallback_when_download_empty(self) -> None:
        with patch("core.market_data_layer._fetch_yf_download", return_value=(None, "empty")):
            with patch(
                "core.market_data_layer._fetch_fast_info",
                return_value=(287.5, None),
            ):
                result = get_market_price(
                    "AAPL",
                    purpose="risk",
                    cache_path=self.cache_path,
                    health_path=self.health_path,
                )
        self.assertEqual(result.price, 287.5)
        self.assertEqual(result.source, "yfinance_fast_info")
        self.assertEqual(result.status, STATUS_OK)

    def test_cache_json_roundtrip(self) -> None:
        get_market_price(
            "QQQ",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=lambda _t: (450.12, "mock", None),
        )
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertIn("QQQ", payload)
        self.assertEqual(payload["QQQ"]["price"], 450.12)
        health = json.loads(self.health_path.read_text(encoding="utf-8"))
        self.assertIn("QQQ", health["tickers"])

    def test_risk_rejects_cache_over_45s(self) -> None:
        self._seed_cache("AAPL", 280.0, age_seconds=RISK_CACHE_MAX_AGE + 30, failures=1)
        result = get_market_price(
            "AAPL",
            purpose="risk",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=lambda _t: (None, None, "down"),
        )
        self.assertIsNone(result.price)
        self.assertIn(result.status, {STATUS_STALE, STATUS_FAILING, STATUS_CRITICAL})

    def test_risk_accepts_cache_under_45s(self) -> None:
        self._seed_cache("AAPL", 280.0, age_seconds=30, failures=1)
        result = get_market_price(
            "AAPL",
            purpose="risk",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=lambda _t: (None, None, "down"),
        )
        self.assertEqual(result.price, 280.0)
        self.assertEqual(result.status, STATUS_STALE)

    def test_health_escalation_ok_to_failing_to_critical(self) -> None:
        fetch_fail = lambda _t: (None, None, "down")

        get_market_price(
            "NVDA",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=lambda _t: (200.0, "mock", None),
        )
        ok = get_market_price(
            "NVDA",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=lambda _t: (200.0, "mock", None),
        )
        self.assertEqual(ok.status, STATUS_OK)

        failing = get_market_price(
            "NVDA",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=fetch_fail,
        )
        self.assertEqual(failing.consecutive_failures, 1)
        self.assertEqual(failing.status, STATUS_STALE)

        for _ in range(2):
            get_market_price(
                "NVDA",
                purpose="display",
                cache_path=self.cache_path,
                health_path=self.health_path,
                fetch_fn=fetch_fail,
            )
        mid = get_market_price(
            "NVDA",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=fetch_fail,
        )
        self.assertGreaterEqual(mid.consecutive_failures, 3)
        self.assertEqual(mid.status, STATUS_FAILING)

        for _ in range(3):
            get_market_price(
                "NVDA",
                purpose="display",
                cache_path=self.cache_path,
                health_path=self.health_path,
                fetch_fn=fetch_fail,
            )
        critical = get_market_price(
            "NVDA",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=fetch_fail,
        )
        self.assertGreater(critical.consecutive_failures, 5)
        self.assertEqual(critical.status, STATUS_CRITICAL)

    def test_display_accepts_cache_up_to_300s(self) -> None:
        self._seed_cache("SPY", 747.0, age_seconds=DISPLAY_CACHE_MAX_AGE - 10, failures=0)
        result = get_market_price(
            "SPY",
            purpose="display",
            cache_path=self.cache_path,
            health_path=self.health_path,
            fetch_fn=lambda _t: (None, None, "down"),
        )
        self.assertEqual(result.price, 747.0)

    def test_update_portfolio_prices_no_buy_price_fallback(self) -> None:
        portfolio = pd.DataFrame(
            [
                {
                    "Date": "2026-06-24 18:53:50",
                    "Ticker": "AAPL",
                    "Action": "BUY",
                    "Price": 299.59,
                    "Shares": 1.0,
                    "Score": 80,
                    "Signal": "STRONG BUY",
                    "Reason": "TEST",
                    "Current_Price": 285.0,
                    "Invested": 299.59,
                    "Current_Value": 285.0,
                    "PnL": -14.59,
                    "PnL_%": -4.87,
                }
            ]
        )
        log_lines: list[str] = []

        with patch("live_bot.load_portfolio", return_value=portfolio.copy()):
            with patch("live_bot.save_portfolio") as save_mock:
                with patch("core.market_data_layer.get_market_price") as quote_mock:
                    from core.market_data_layer import PriceResult

                    quote_mock.return_value = PriceResult(
                        ticker="AAPL",
                        price=None,
                        fetched_at=None,
                        source=None,
                        age_seconds=200.0,
                        status=STATUS_FAILING,
                        consecutive_failures=4,
                        error="down",
                    )
                    with patch("live_bot.log", side_effect=lambda msg: log_lines.append(msg)):
                        live_bot.update_portfolio_prices()

        saved = save_mock.call_args[0][0]
        self.assertAlmostEqual(float(saved.iloc[0]["Current_Price"]), 285.0, places=2)
        self.assertTrue(any("keeping previous Current_Price" in line for line in log_lines))
        self.assertFalse(any("299.59" in line and "Current_Price" in line for line in log_lines))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
