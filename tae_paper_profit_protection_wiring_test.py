#!/usr/bin/env python3
"""Targeted tests: PCE/GII winner protection → canonical PAPER profit trailing."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import tae_paper_execution as pe
import tae_paper_profit_trailing as pt

from tae_test_isolation import isolate_adaptive_deployment as _isolate_adaptive_deployment


def _winner_fixture(
    ticker: str,
    *,
    shares: float,
    avg_price: float,
    current_price: float,
    pce_verdict: str,
    gii: dict,
) -> tuple[dict, dict, dict]:
    pos = {
        "ticker": ticker,
        "shares": shares,
        "avg_price": avg_price,
        "current_price": current_price,
        "status": "OPEN",
    }
    pce = {"ticker": ticker, "context_verdict": pce_verdict, "shadow_only": True}
    gii_row = {"ticker": ticker, **gii}
    return pos, pce, gii_row


HSBA = (
    "HSBA.L",
    *_winner_fixture(
        "HSBA.L",
        shares=1.7173,
        avg_price=1455.8,
        current_price=1465.6,
        pce_verdict="CONTEXT_WEAKENING",
        gii={
            "pce_verdict": "PROTECT_NOW",
            "high_pct": 9.22,
            "governor_recommendation": "TRAIL_PROTECT_SHADOW",
            "recommended_shadow_strategy": "REDUCE_EXPOSURE_SHADOW",
        },
    ),
)

MU = (
    "MU",
    *_winner_fixture(
        "MU",
        shares=2.5626,
        avg_price=975.56,
        current_price=984.75,
        pce_verdict="CONTEXT_WEAKENING",
        gii={
            "pce_verdict": "CONTEXT_WEAKENING",
            "high_pct": 9.13,
            "governor_recommendation": "PARTIAL_PROTECT_SHADOW",
            "recommended_shadow_strategy": "TIGHTEN_TRAIL_SHADOW",
        },
    ),
)

AMAT = (
    "AMAT",
    *_winner_fixture(
        "AMAT",
        shares=4.1457,
        avg_price=603.04,
        current_price=592.79,
        pce_verdict="CONTEXT_WEAKENING",
        gii={
            "pce_verdict": "CONTEXT_WEAKENING",
            "high_pct": 8.95,
            "governor_recommendation": "PARTIAL_PROTECT_SHADOW",
            "recommended_shadow_strategy": "TIGHTEN_TRAIL_SHADOW",
        },
    ),
)


class PaperProfitProtectionWiringTest(unittest.TestCase):
    """Reproduce HSBA.L / MU / AMAT winner-protection wiring (PAPER only)."""

    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )

    def _wire(self, ticker: str, pos: dict, pce: dict, gii_row: dict) -> dict:
        portfolio = {"cash": 5000.0, "realized_pnl": 0.0, "positions": {ticker: pos}}
        events, changed = pt.wire_paper_profit_protection(
            portfolio,
            pce_by={ticker: pce},
            gii_by={ticker: gii_row},
        )
        self.assertTrue(changed, f"{ticker}: portfolio should change after PCE wiring")
        ev = next(e for e in events if e.get("ticker") == ticker)
        self.assertTrue(ev.get("applied"), f"{ticker}: wiring not applied — {ev}")
        self.assertTrue(ev.get("pce_execution_eligible"), f"{ticker}: not execution eligible")
        self.assertTrue(pt.trailing_active_on_position(pos), f"{ticker}: trailing not armed")
        self.assertGreaterEqual(
            float(ev.get("peak_profit_pct") or 0.0),
            pt.PAPER_PROFIT_TRAILING_ACTIVATION_PCT,
            f"{ticker}: peak below activation threshold",
        )
        return ev

    def test_hsba_l_pce_protection_arms_trailing(self) -> None:
        ticker, pos, pce, gii_row = HSBA
        ev = self._wire(ticker, pos, pce, gii_row)
        self.assertIn(ev.get("pce_verdict"), pt.PCE_PROTECTION_VERDICTS)
        self.assertEqual(pos.get("profit_trailing_pce_verdict"), ev.get("pce_verdict"))

    def test_mu_pce_protection_arms_trailing(self) -> None:
        ticker, pos, pce, gii_row = MU
        ev = self._wire(ticker, pos, pce, gii_row)
        self.assertEqual(ev.get("pce_verdict"), "CONTEXT_WEAKENING")

    def test_amat_pce_protection_arms_trailing(self) -> None:
        ticker, pos, pce, gii_row = AMAT
        self._wire(ticker, pos, pce, gii_row)

    def test_shadow_only_pce_still_execution_eligible(self) -> None:
        _, pos, pce, gii_row = MU
        self.assertTrue(pce.get("shadow_only"))
        self.assertTrue(
            pt.pce_protection_execution_eligible(pce_row=pce, gii_row=gii_row),
        )

    def test_buy_scale_in_blocked_during_active_protection(self) -> None:
        ticker, pos, pce, gii_row = MU
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {ticker: pos}}
        pt.wire_paper_profit_protection(
            portfolio,
            pce_by={ticker: pce},
            gii_by={ticker: gii_row},
        )
        decision = {
            "decision_id": "PDEC-PCE-BUY-BLOCK",
            "ticker": ticker,
            "action": "BUY_PAPER",
            "confidence": 0.9,
        }
        with mock.patch.object(
            pe,
            "resolve_mark_price",
            return_value={
                "price": float(pos["current_price"]),
                "source": "fixture",
                "timestamp": "2026-08-06T12:00:00Z",
                "freshness": "FRESH",
                "attempts": [],
            },
        ):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
            )
        self.assertEqual(order["status"], pt.REASON_BUY_BLOCKED)
        self.assertEqual(portfolio["positions"][ticker]["shares"], pos["shares"])

    def test_live_execution_module_unchanged(self) -> None:
        live_path = Path(__file__).resolve().parent / "live_bot.py"
        with open(live_path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("wire_paper_profit_protection", src)
        self.assertNotIn("load_pce_by_ticker", src)


if __name__ == "__main__":
    unittest.main()
