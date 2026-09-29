from __future__ import annotations

import unittest
from datetime import datetime, timezone

import portfolio_report as pr
from tae2.broker import Position


class ResolveNameTest(unittest.TestCase):
    def test_etf_ticker_uses_the_real_fund_name(self) -> None:
        self.assertEqual(pr.resolve_name("SPY", {}), "SPDR S&P 500 ETF Trust")

    def test_stock_ticker_uses_the_supplied_company_name(self) -> None:
        self.assertEqual(pr.resolve_name("AAPL", {"AAPL": "Apple Inc."}), "Apple Inc.")

    def test_unknown_ticker_falls_back_to_the_bare_symbol(self) -> None:
        self.assertEqual(pr.resolve_name("ZZZZ", {}), "ZZZZ")

    def test_etf_names_take_priority_over_a_stock_name_collision(self) -> None:
        # SHY/SPY can appear inside the stocks account too (cash proxy / calendar ticker);
        # they must still show the ETF's real name, not something from the stock name map.
        self.assertEqual(pr.resolve_name("SHY", {"SHY": "Some Other Thing Inc."}), "iShares 1-3 Year Treasury Bond ETF")


class ReportRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reports = [
            pr.AccountReport(
                "tae2",
                equity=10_000.0,
                cash=1_000.0,
                positions=[Position("SPY", 10, 6_000.0), Position("IEF", 5, 3_000.0)],
            ),
            pr.AccountReport("stocks (MoVo10)", equity=0.0, cash=0.0, positions=[], error="missing keys"),
        ]
        self.now = datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc)

    def test_markdown_includes_full_names_and_weights(self) -> None:
        md = pr.to_markdown(self.reports, {}, self.now)
        self.assertIn("SPDR S&P 500 ETF Trust", md)
        self.assertIn("60.0%", md)  # 6000 / 10000

    def test_markdown_surfaces_a_broker_error_instead_of_hiding_it(self) -> None:
        md = pr.to_markdown(self.reports, {}, self.now)
        self.assertIn("missing keys", md)

    def test_html_includes_full_names_and_totals(self) -> None:
        html = pr.to_html(self.reports, {}, self.now)
        self.assertIn("SPDR S&P 500 ETF Trust", html)
        self.assertIn("$10,000.00", html)  # combined total (second account is 0 due to the error)


if __name__ == "__main__":
    unittest.main()
