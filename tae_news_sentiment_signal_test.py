#!/usr/bin/env python3
"""Regression coverage for tae_news_sentiment_signal.py — post-Sprint-3
roadmap item 1 (2026-09-14): the first genuinely independent (non-
price-derived) signal in this system, shadow/log-only for now (no
historical news archive exists to backtest against)."""

from __future__ import annotations

import unittest
from unittest import mock

import tae_news_sentiment_signal as news


class ScoreTextTest(unittest.TestCase):
    def test_positive_word_scores_positive(self) -> None:
        self.assertGreater(news.score_text("Company beats earnings estimates"), 0)

    def test_negative_word_scores_negative(self) -> None:
        self.assertLess(news.score_text("Company misses on weak guidance"), 0)

    def test_no_keyword_hits_scores_zero(self) -> None:
        self.assertEqual(news.score_text("Company announces annual meeting date"), 0)

    def test_case_insensitive(self) -> None:
        self.assertEqual(news.score_text("STRONG BEAT"), news.score_text("strong beat"))


class ScoreHeadlinesTest(unittest.TestCase):
    def test_empty_list_is_neutral_not_an_error(self) -> None:
        result = news.score_headlines([])
        self.assertEqual(result["news_count"], 0)
        self.assertEqual(result["bias"], "NEUTRAL")

    def test_all_positive_headlines_bias_positive(self) -> None:
        result = news.score_headlines(["Stock surges on strong earnings beat", "Analysts raises price target on growth"])
        self.assertEqual(result["bias"], "POSITIVE")
        self.assertEqual(result["positive_count"], 2)
        self.assertEqual(result["negative_count"], 0)

    def test_all_negative_headlines_bias_negative(self) -> None:
        result = news.score_headlines(["Company warns of weak demand", "Shares drop on downgrade"])
        self.assertEqual(result["bias"], "NEGATIVE")
        self.assertEqual(result["negative_count"], 2)

    def test_mixed_headlines_average_correctly(self) -> None:
        result = news.score_headlines(["Strong beat drives rally", "Lawsuit and probe weigh on shares"])
        self.assertEqual(result["news_count"], 2)
        self.assertEqual(result["positive_count"], 1)
        self.assertEqual(result["negative_count"], 1)

    def test_neutral_headline_with_no_keywords(self) -> None:
        result = news.score_headlines(["Company to present at investor conference"])
        self.assertEqual(result["bias"], "NEUTRAL")
        self.assertEqual(result["neutral_count"], 1)


class FetchTickerNewsTest(unittest.TestCase):
    def test_fetch_failure_returns_empty_list_not_a_crash(self) -> None:
        with mock.patch("yfinance.Ticker", side_effect=RuntimeError("network down")):
            result = news.fetch_ticker_news("AAPL")
        self.assertEqual(result, [])

    def test_normalizes_title_from_top_level_or_content(self) -> None:
        fake_news = [
            {"title": "Top-level title headline"},
            {"content": {"title": "Nested content title headline"}},
            {"content": {}},  # no title anywhere -- must be skipped, not crash
        ]
        mock_ticker = mock.Mock()
        mock_ticker.news = fake_news
        with mock.patch("yfinance.Ticker", return_value=mock_ticker):
            result = news.fetch_ticker_news("AAPL", limit=10)
        self.assertIn("Top-level title headline", result)
        self.assertIn("Nested content title headline", result)
        self.assertEqual(len(result), 2)

    def test_respects_limit(self) -> None:
        fake_news = [{"title": f"Headline {i}"} for i in range(10)]
        mock_ticker = mock.Mock()
        mock_ticker.news = fake_news
        with mock.patch("yfinance.Ticker", return_value=mock_ticker):
            result = news.fetch_ticker_news("AAPL", limit=3)
        self.assertEqual(len(result), 3)


class ShadowNewsSentimentTest(unittest.TestCase):
    def test_never_raises_even_if_fetch_breaks(self) -> None:
        with mock.patch.object(news, "fetch_ticker_news", side_effect=RuntimeError("boom")):
            result = news.shadow_news_sentiment("AAPL")
        self.assertIsNotNone(result)
        self.assertIn("error", result)

    def test_returns_scored_result_with_timestamp(self) -> None:
        with mock.patch.object(news, "fetch_ticker_news", return_value=["Strong beat drives rally"]):
            result = news.shadow_news_sentiment("AAPL")
        self.assertEqual(result["bias"], "POSITIVE")
        self.assertIn("fetched_at", result)


class FetchShadowNewsBatchTest(unittest.TestCase):
    """Disk-cache behavior: a fresh Python process per hourly cycle means
    an in-memory cache buys nothing -- this must persist across calls
    that simulate separate cycles (same pattern as tae_fundamentals_
    snapshot.py's cache tests)."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._patcher = mock.patch.object(news, "CACHE_PATH", __import__("pathlib").Path(self._tmp.name) / "cache.json")
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self._tmp.cleanup()

    def test_second_call_within_ttl_does_not_refetch(self) -> None:
        calls = []

        def _fake_shadow(ticker, *, limit=news.DEFAULT_HEADLINE_LIMIT):
            calls.append(ticker)
            return {"news_count": 1, "bias": "POSITIVE"}

        with mock.patch.object(news, "shadow_news_sentiment", side_effect=_fake_shadow):
            news.fetch_shadow_news_batch(["AAA"])
            news.fetch_shadow_news_batch(["AAA"])
        self.assertEqual(calls, ["AAA"])  # second call served from disk cache

    def test_expired_entry_is_refetched(self) -> None:
        calls = []

        def _fake_shadow(ticker, *, limit=news.DEFAULT_HEADLINE_LIMIT):
            calls.append(ticker)
            return {"news_count": 1, "bias": "POSITIVE"}

        with mock.patch.object(news, "shadow_news_sentiment", side_effect=_fake_shadow):
            news.fetch_shadow_news_batch(["AAA"], ttl_seconds=0.0)
            news.fetch_shadow_news_batch(["AAA"], ttl_seconds=0.0)
        self.assertEqual(calls, ["AAA", "AAA"])

    def test_returns_a_result_per_ticker(self) -> None:
        with mock.patch.object(news, "shadow_news_sentiment", return_value={"news_count": 0, "bias": "NEUTRAL"}):
            result = news.fetch_shadow_news_batch(["AAA", "BBB"])
        self.assertIn("AAA", result)
        self.assertIn("BBB", result)


class RuntimeWiringSmokeTest(unittest.TestCase):
    """Confirms V1's real entry path computes and logs the news-sentiment
    shadow signal WITHOUT it ever influencing `favorable`/`action` --
    without a real network-dependent cycle. Mirrors tae_shadow_entry_
    scorer_test.py's wiring check."""

    def test_v1_arm_logs_news_shadow_but_never_gates_on_it(self) -> None:
        import inspect

        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr._run_v1_arm)
        self.assertIn('.get("news_sentiment_shadow")', source)
        self.assertIn('"news_sentiment_shadow": news_shadow', source)
        lines_with_favorable = [line for line in source.splitlines() if "favorable" in line]
        self.assertTrue(lines_with_favorable)
        for line in lines_with_favorable:
            self.assertNotIn("news_shadow", line)

    def test_run_cycle_fetches_news_shadow_batch_once_per_cycle(self) -> None:
        import inspect

        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr)
        self.assertIn("news_signal.fetch_shadow_news_batch(", source)
        self.assertIn('snap["news_sentiment_shadow"] = news_shadow_batch.get(t)', source)


if __name__ == "__main__":
    unittest.main()
