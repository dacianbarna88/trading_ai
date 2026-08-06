#!/usr/bin/env python3
"""Targeted tests — unified profit-seeking recalibration (common V1/V2/Vx layer)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import tae_adaptive_deployment as adep
import tae_paper_execution as pe
import tae_paper_profit_trailing as pt
import tae_paper_shadow_sizing as pss
import tae_strategy_v2_buy_policy as v2bp
from tae_strategy_v2_foundation import (
    STOP_ACCUMULATION_COOLDOWN_SECONDS,
    apply_stop_accumulation,
    evaluate_accumulation_reactivation,
)


class UnifiedProfitSeekingRecalibrationTest(unittest.TestCase):
    def _challenger_state(self, root: Path) -> None:
        st = adep.load_state(root=root, create_default=True)
        st["deployment_state"] = adep.ST_PAPER_CHALLENGER
        st["ticker_scope"] = ["AAPL", "MSFT", "NVDA"]
        st["capital_limit"] = 500.0
        st["challenger_exposure_usd"] = 500.0
        st["challenger_formula_id"] = adep.FORMULA_LIVE_EQUAL_SPLIT
        st["capital_allocation_pct"] = 100.0
        st["live_allowed"] = False
        adep.save_state(st, root=root)

    def test_canonical_universe_ticker_not_blocked_by_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._challenger_state(root)
            sizing = adep.resolve_buy_notional(
                control_notional=1000.0,
                inputs={
                    "cash_available": 10000.0,
                    "cash_reserve": 500.0,
                    "maximum_position_notional": 2500.0,
                    "confidence": 0.85,
                },
                ticker="SAP.DE",
                arm="V1",
                root=root,
            )
            self.assertFalse(sizing["blocked"], sizing)
            self.assertEqual(sizing["decision"], "USE_CONTROL")
            self.assertEqual(sizing["scope_result"], adep.CONTROL_FALLBACK_CANONICAL_UNIVERSE)

    def test_non_canonical_ticker_still_blocked_by_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._challenger_state(root)
            sizing = adep.resolve_buy_notional(
                control_notional=1000.0,
                inputs={"cash_available": 10000.0, "cash_reserve": 500.0, "maximum_position_notional": 2500.0},
                ticker="GROW",
                arm="CANONICAL_PAPER",
                root=root,
            )
            self.assertTrue(sizing["blocked"])
            self.assertEqual(sizing["reason_code"], adep.BLOCKED_TICKER_SCOPE)

    def test_challenger_cap_exhausted_falls_back_to_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._challenger_state(root)
            sizing = adep.resolve_buy_notional(
                control_notional=1000.0,
                inputs={
                    "cash_available": 10000.0,
                    "cash_reserve": 500.0,
                    "maximum_position_notional": 2500.0,
                    "confidence": 0.8,
                },
                ticker="AAPL",
                arm="CANONICAL_PAPER",
                root=root,
            )
            self.assertFalse(sizing["blocked"], sizing)
            self.assertEqual(sizing["decision"], "USE_CONTROL")
            self.assertGreaterEqual(float(sizing["executed_notional"]), pss.PAPER_MIN_ORDER_USD)

    def test_common_deployable_fraction_exceeds_legacy_25pct(self) -> None:
        n = pss.paper_deployable_notional(10000.0, cash_reserve=500.0)
        legacy = min(2500.0, 9500.0 * 0.25)
        self.assertGreater(n, legacy)
        self.assertEqual(n, 2500.0)

    def test_stop_accumulation_reactivates_after_cooldown(self) -> None:
        cycle = {
            "cycle_id": "CYC-1",
            "ticker": "SAP.DE",
            "status": "ACCUMULATION_STOPPED",
            "accumulation_stop_reason": "STOP_INVALID_DATA",
            "accumulation_stop_until": (
                datetime.now(timezone.utc) - timedelta(seconds=10)
            )
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        out = evaluate_accumulation_reactivation(cycle, mark_ok=True)
        self.assertEqual(out["action"], "REACTIVATED")
        self.assertEqual(out["cycle"]["status"], "ACCUMULATING")

    def test_structural_stop_does_not_reactivate(self) -> None:
        cycle = {
            "cycle_id": "CYC-2",
            "ticker": "AAPL",
            "status": "ACCUMULATION_STOPPED",
            "accumulation_stop_reason": "STOP_MAX_TRANCHES",
            "accumulation_stop_until": (
                datetime.now(timezone.utc) - timedelta(seconds=10)
            )
            .isoformat()
            .replace("+00:00", "Z"),
        }
        out = evaluate_accumulation_reactivation(cycle, mark_ok=True)
        self.assertEqual(out["action"], "STOP")

    def test_profit_trailing_on_a_does_not_block_b(self) -> None:
        portfolio = {
            "cash": 10000.0,
            "realized_pnl": 0.0,
            "positions": {
                "MU": {
                    "ticker": "MU",
                    "shares": 5.0,
                    "avg_price": 100.0,
                    "current_price": 110.0,
                    "profit_trailing_active": True,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-REC-B",
            "ticker": "SAP.DE",
            "action": "BUY_PAPER",
            "confidence": 0.85,
        }
        with mock.patch.object(
            pe,
            "resolve_mark_price",
            return_value={
                "price": 100.0,
                "source": "fixture",
                "timestamp": "2026-08-06T12:00:00Z",
                "freshness": "FRESH",
                "attempts": [],
            },
        ), mock.patch.dict("os.environ", {"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}):
            order = pe.execute_decision(
                decision, portfolio, accounting=None, all_decisions=[decision]
            )
        self.assertNotEqual(order["status"], pt.REASON_BUY_BLOCKED)

    def test_vx_fixture_uses_common_adaptive_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._challenger_state(root)
            for arm in ("V1", "V2", "CANONICAL_PAPER"):
                sizing = adep.resolve_buy_notional(
                    control_notional=800.0,
                    inputs={
                        "cash_available": 12000.0,
                        "cash_reserve": 500.0,
                        "maximum_position_notional": 2500.0,
                        "confidence": 0.75,
                    },
                    ticker="HSBA.L",
                    arm=arm,
                    root=root,
                    v2_add_authorized=(arm == "V2"),
                )
                self.assertFalse(sizing["blocked"], f"{arm}: {sizing}")
                self.assertGreater(float(sizing["executed_notional"]), 0.0)

    def test_live_bot_unchanged(self) -> None:
        src = (Path(__file__).resolve().parent / "live_bot.py").read_text(encoding="utf-8")
        self.assertNotIn("common_control_buy_notional", src)
        self.assertNotIn("CONTROL_FALLBACK_CANONICAL_UNIVERSE", src)


if __name__ == "__main__":
    unittest.main()
