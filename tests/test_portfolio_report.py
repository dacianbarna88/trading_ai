from __future__ import annotations

import unittest
from datetime import datetime, timezone

import requests

import portfolio_report as pr


class FetchResilienceTest(unittest.TestCase):
    """Bug found 2026-10-02: a launchd catch-up run fired right after the
    Mac woke from sleep, before networking was back up. requests raised
    ConnectionError (not BrokerError), which _fetch() didn't catch -- it
    crashed collect() entirely, losing the OTHER account's report too and
    producing no file/notification for the whole run."""

    def test_a_network_error_is_captured_per_account_not_raised(self) -> None:
        def make_broker():
            class _Broker:
                def account(self):
                    raise requests.exceptions.ConnectionError("Failed to resolve host")

            return _Broker()

        report = pr._fetch("tae2", make_broker)
        self.assertIsNotNone(report.error)
        self.assertEqual(report.positions, [])

    def test_one_accounts_network_error_does_not_lose_the_others_report(self) -> None:
        def broken():
            class _Broker:
                def account(self):
                    raise requests.exceptions.ConnectionError("Failed to resolve host")

            return _Broker()

        def working():
            class _Broker:
                def account(self):
                    from tae2.broker import Account

                    return Account(1_000.0, 500.0, 500.0, "ACTIVE", False)

                def _call(self, method, path, **kwargs):
                    if path == "/v2/positions":
                        return []
                    if path == "/v2/account/portfolio/history":
                        return {"timestamp": [], "equity": []}
                    raise AssertionError(f"unexpected call: {method} {path}")

            return _Broker()

        reports = [pr._fetch("broken", broken), pr._fetch("working", working)]
        self.assertIsNotNone(reports[0].error)
        self.assertIsNone(reports[1].error)
        self.assertEqual(reports[1].equity, 1_000.0)


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


class ResolveDomainTest(unittest.TestCase):
    def test_etf_ticker_uses_tae2s_own_category_description(self) -> None:
        self.assertEqual(pr.resolve_domain("SPY", {}), "US large caps (S&P 500)")

    def test_stock_ticker_uses_the_supplied_gics_sector(self) -> None:
        self.assertEqual(pr.resolve_domain("AAPL", {"AAPL": "Information Technology"}), "Information Technology")

    def test_unknown_ticker_falls_back_to_a_dash(self) -> None:
        self.assertEqual(pr.resolve_domain("ZZZZ", {}), "—")


class PositionDetailTest(unittest.TestCase):
    def test_change_pct_compares_current_to_entry_price(self) -> None:
        p = pr.PositionDetail("SPY", qty=10, market_value=1100.0, avg_entry_price=100.0, current_price=110.0)
        self.assertAlmostEqual(p.change_pct, 0.10)

    def test_change_pct_is_zero_when_entry_price_is_zero(self) -> None:
        p = pr.PositionDetail("SPY", qty=10, market_value=0.0, avg_entry_price=0.0, current_price=0.0)
        self.assertEqual(p.change_pct, 0.0)


class ReportRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reports = [
            pr.AccountReport(
                "tae2",
                equity=10_000.0,
                cash=1_000.0,
                positions=[
                    pr.PositionDetail("SPY", qty=10, market_value=6_000.0, avg_entry_price=550.0, current_price=600.0),
                    pr.PositionDetail("IEF", qty=5, market_value=3_000.0, avg_entry_price=620.0, current_price=600.0),
                ],
                history=[
                    pr.EquityPoint(datetime(2026, 9, 23, tzinfo=timezone.utc), 10_000.0),
                    pr.EquityPoint(datetime(2026, 9, 24, tzinfo=timezone.utc), 10_100.0),
                ],
            ),
            pr.AccountReport("stocks (MoVo10)", equity=0.0, cash=0.0, positions=[], error="missing keys"),
        ]
        self.now = datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc)

    def test_markdown_includes_full_names_and_weights(self) -> None:
        md = pr.to_markdown(self.reports, {}, {}, self.now)
        self.assertIn("SPDR S&P 500 ETF Trust", md)
        self.assertIn("60.0%", md)  # 6000 / 10000

    def test_markdown_includes_domain_and_entry_price_change(self) -> None:
        md = pr.to_markdown(self.reports, {}, {}, self.now)
        self.assertIn("US large caps (S&P 500)", md)
        self.assertIn("+9.1%", md)  # SPY 550 -> 600

    def test_markdown_includes_equity_history(self) -> None:
        md = pr.to_markdown(self.reports, {}, {}, self.now)
        self.assertIn("2026-09-24", md)
        self.assertIn("+1.00%", md)

    def test_markdown_surfaces_a_broker_error_instead_of_hiding_it(self) -> None:
        md = pr.to_markdown(self.reports, {}, {}, self.now)
        self.assertIn("missing keys", md)

    def test_html_includes_full_names_and_totals(self) -> None:
        html = pr.to_html(self.reports, {}, {}, self.now)
        self.assertIn("SPDR S&P 500 ETF Trust", html)
        self.assertIn("$10,000.00", html)  # combined total (second account is 0 due to the error)


if __name__ == "__main__":
    unittest.main()
