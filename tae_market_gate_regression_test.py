#!/usr/bin/env python3
"""
TAE Market Gate Regression Test — per-ticker session only, no global BUY block.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

import live_bot
from research_core.governance.live_advisory_runtime import LiveAdvisoryRuntimeState
from research_core.governance.shadow_validation_ledger import (
    EVENT_BUY_ALLOWED,
    EVENT_BUY_BLOCKED_BY_TAE,
    EVENT_BUY_SKIPPED_OTHER_REASON,
    ShadowValidationLedger,
)


def _empty_portfolio() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
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
        ]
    )


def _strong_buy_row(ticker: str, score: int = 100, price: float = 100.0) -> dict:
    return {
        "Ticker": ticker,
        "Signal": "STRONG BUY",
        "Score": score,
        "Price": price,
        "RSI": 55.0,
    }


class MarketGateRegressionHarness:
    def __init__(self) -> None:
        self.logs: list[str] = []
        self.buy_calls: list[str] = []
        self.ledger_rows_cache: list[dict[str, str]] = []
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None

    def log(self, message: str) -> None:
        self.logs.append(message)

    def fake_buy(self, row, portfolio, trade_usd):
        self.buy_calls.append(str(row["Ticker"]))
        return portfolio

    def advisory_ok(self) -> LiveAdvisoryRuntimeState:
        return LiveAdvisoryRuntimeState(
            path=Path("tae_live_advisory.json"),
            load_status="ok",
            action="SELL_ADVISORY",
            confidence=80,
            blockers=[],
            reasons=["demo ok"],
        )

    def advisory_risk(self) -> LiveAdvisoryRuntimeState:
        return LiveAdvisoryRuntimeState(
            path=Path("tae_live_advisory.json"),
            load_status="ok",
            action="RISK_ADVISORY",
            confidence=45,
            blockers=["demo risk blocker"],
            reasons=["RISK_ADVISORY active"],
        )

    def run_manage(
        self,
        tickers: list[str],
        *,
        ticker_open_map: dict[str, bool],
        advisory_state: LiveAdvisoryRuntimeState | None = None,
    ) -> None:
        self.logs.clear()
        self.buy_calls.clear()
        self.ledger_rows_cache.clear()

        if self._tmpdir is not None:
            self._tmpdir.cleanup()
        self._tmpdir = tempfile.TemporaryDirectory()
        ledger_path = Path(self._tmpdir.name) / "shadow_events.csv"
        ledger = ShadowValidationLedger(ledger_path, warn_fn=self.log)

        signals = pd.DataFrame([_strong_buy_row(t) for t in tickers])

        def open_fn(ticker: str) -> bool:
            return ticker_open_map.get(str(ticker).upper(), False)

        patches = [
            patch.object(live_bot, "log", side_effect=self.log),
            patch.object(live_bot, "load_portfolio", return_value=_empty_portfolio()),
            patch.object(live_bot, "save_portfolio"),
            patch.object(live_bot, "get_open_positions", return_value={}),
            patch.object(live_bot, "get_market_regime", return_value="BULL"),
            patch.object(live_bot, "get_dynamic_trade_size", return_value=2500.0),
            patch.object(live_bot, "buy_position", side_effect=self.fake_buy),
            patch.object(live_bot, "is_ticker_market_open", side_effect=open_fn),
            patch.object(live_bot, "log_market_session_summary"),
            patch(
                "research_core.governance.shadow_validation_ledger.get_default_ledger",
                return_value=ledger,
            ),
            patch(
                "research_core.governance.live_advisory_runtime.advisory_runtime_summary",
                return_value="demo advisory summary",
            ),
            patch(
                "research_core.governance.live_advisory_runtime.get_advisory_action",
                return_value=advisory_state.action if advisory_state else "SELL_ADVISORY",
            ),
            patch(
                "research_core.governance.live_advisory_runtime.should_block_new_buy",
                return_value=(
                    advisory_state.action == "RISK_ADVISORY",
                    "TAE RISK_ADVISORY — demo block",
                )
                if advisory_state
                else (False, ""),
            ),
        ]

        for item in patches:
            item.start()

        try:
            live_bot.manage_portfolio(
                signals,
                advisory_state=advisory_state or self.advisory_ok(),
                live_bot_cycle_id="regression-test",
            )
            if ledger_path.is_file():
                self.ledger_rows_cache = pd.read_csv(ledger_path).to_dict(orient="records")
        finally:
            for item in patches:
                item.stop()

    def ledger_rows(self) -> list[dict[str, str]]:
        return self.ledger_rows_cache


def test_global_gate_disabled_constant() -> None:
    assert live_bot.GLOBAL_MARKET_GATE_ENABLED is False


def test_us_closed_eu_open_mcpa_allowed() -> None:
    harness = MarketGateRegressionHarness()
    harness.run_manage(
        ["MC.PA"],
        ticker_open_map={"MC.PA": True},
    )
    assert "MC.PA" in harness.buy_calls
    assert not any("Piața este închisă" in line for line in harness.logs)
    allowed = [r for r in harness.ledger_rows() if r["event_type"] == EVENT_BUY_ALLOWED]
    assert allowed and allowed[0]["ticker"] == "MC.PA"


def test_us_closed_uk_open_aznl_allowed() -> None:
    harness = MarketGateRegressionHarness()
    harness.run_manage(
        ["AZN.L"],
        ticker_open_map={"AZN.L": True},
    )
    assert "AZN.L" in harness.buy_calls


def test_us_open_eu_closed_mcpa_skipped_per_ticker() -> None:
    harness = MarketGateRegressionHarness()
    harness.run_manage(
        ["MC.PA"],
        ticker_open_map={"MC.PA": False},
    )
    assert "MC.PA" not in harness.buy_calls
    assert any("BUY skipped for MC.PA: ticker market closed" in line for line in harness.logs)
    skipped = [
        r
        for r in harness.ledger_rows()
        if r["event_type"] == EVENT_BUY_SKIPPED_OTHER_REASON
        and r["ticker"] == "MC.PA"
    ]
    assert skipped and skipped[0]["block_reason"] == "MARKET_SESSION_FILTER"


def test_all_closed_skipped_per_ticker_not_global_return() -> None:
    harness = MarketGateRegressionHarness()
    harness.run_manage(
        ["MC.PA", "AZN.L", "SPY"],
        ticker_open_map={"MC.PA": False, "AZN.L": False, "SPY": False},
    )
    assert harness.buy_calls == []
    assert sum("BUY skipped for" in line for line in harness.logs) == 3
    assert not any("Piața este închisă" in line for line in harness.logs)
    assert not any("Nu execut BUY" in line for line in harness.logs)


def test_risk_advisory_blocks_even_if_ticker_open() -> None:
    harness = MarketGateRegressionHarness()
    harness.run_manage(
        ["SPY"],
        ticker_open_map={"SPY": True},
        advisory_state=harness.advisory_risk(),
    )
    assert "SPY" not in harness.buy_calls
    blocked = [
        r
        for r in harness.ledger_rows()
        if r["event_type"] == EVENT_BUY_BLOCKED_BY_TAE and r["ticker"] == "SPY"
    ]
    assert blocked


def test_sell_branch_untouched() -> None:
    """SELL logic path must remain in manage_portfolio (source-level check)."""
    source = Path("live_bot.py").read_text(encoding="utf-8")
    assert "STOP LOSS" in source
    assert "TAKE PROFIT SIGNAL" in source
    assert "sell_position" in source


def test_generate_signals_always_calls_manage_portfolio() -> None:
    source = Path("live_bot.py").read_text(encoding="utf-8")
    assert "manage_portfolio(" in source
    assert "Piața este închisă" not in source
    assert "Global market gate disabled" in source


def main() -> int:
    tests = [
        test_global_gate_disabled_constant,
        test_us_closed_eu_open_mcpa_allowed,
        test_us_closed_uk_open_aznl_allowed,
        test_us_open_eu_closed_mcpa_skipped_per_ticker,
        test_all_closed_skipped_per_ticker_not_global_return,
        test_risk_advisory_blocks_even_if_ticker_open,
        test_sell_branch_untouched,
        test_generate_signals_always_calls_manage_portfolio,
    ]

    failed = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")

    print()
    print(f"GLOBAL_MARKET_GATE_ENABLED={live_bot.GLOBAL_MARKET_GATE_ENABLED}")
    print("Sample log line: Global market gate disabled; evaluating BUY per ticker session.")
    print("Sample skip line: BUY skipped for MC.PA: ticker market closed")
    print(f"Result: {len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
