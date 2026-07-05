#!/usr/bin/env python3
"""Tests for shadow outcome attribution (X.10)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_core.governance.shadow_outcome_attribution import (
    HEADLINE_WINDOW,
    STOP_LOSS_PCT,
    PriceMarkStore,
    assign_primary_blocker,
    build_outcomes_report,
    classify_window,
    evaluate_blocked_event,
    extract_shadow_context_tags,
    reconstruct_notional,
    WindowSimulation,
)
from research_core.governance.shadow_validation_ledger import (
    CSV_FIELDNAMES,
    EVENT_BUY_ALLOWED,
    EVENT_BUY_BLOCKED_BY_TAE,
)


def _write_events(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in CSV_FIELDNAMES})


def _write_portfolio(path: Path, rows: list[dict]) -> None:
    fields = [
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


class ShadowOutcomeAttributionTest(unittest.TestCase):
    def test_assign_primary_blocker_precedence(self) -> None:
        blockers = [
            "Quick health not ready: TAE_QUICK_HEALTH_FAIL",
            "2 open positions below -3% PnL",
        ]
        primary, contributing = assign_primary_blocker(blockers)
        self.assertEqual(primary, "OPEN_BOOK_STRESS")
        self.assertEqual(len(contributing), 1)

    def test_extract_shadow_context_tags(self) -> None:
        tags = extract_shadow_context_tags(
            ["[REPLAY_CONTEXT] MU STOP_REENTRY", "[GOVERNOR_CONTEXT] posture=WATCH"]
        )
        self.assertTrue(any("REPLAY" in tag for tag in tags))

    def test_reconstruct_notional_from_same_cycle(self) -> None:
        blocked = {
            "live_bot_cycle_id": "cycle1",
            "intended_trade_usd": None,
            "price": 100.0,
        }
        allowed = {
            "event_type": EVENT_BUY_ALLOWED,
            "live_bot_cycle_id": "cycle1",
            "intended_trade_usd": 1000.0,
        }
        notional, shares, source = reconstruct_notional(blocked, [blocked, allowed])
        self.assertEqual(notional, 1000.0)
        self.assertEqual(shares, 10.0)
        self.assertEqual(source, "SAME_CYCLE_BUY_ALLOWED")

    def test_classify_win_on_negative_counterfactual(self) -> None:
        sim = WindowSimulation(
            window_trading_days=10,
            counterfactual_pnl_usd=-50.0,
            counterfactual_pnl_pct=-5.0,
            intervention_value_usd=50.0,
            mae_pct=-5.0,
            stop_hit=True,
            resolution_status="RESOLVED",
        )
        classify_window(
            sim,
            notional=1000.0,
            signal_expired=False,
            expired_before_5d=False,
            superseded=False,
            unmeasurable=False,
            not_evaluable=False,
        )
        self.assertEqual(sim.classification, "WIN")

    def test_classify_loss_on_missed_gain(self) -> None:
        sim = WindowSimulation(
            window_trading_days=10,
            counterfactual_pnl_usd=80.0,
            counterfactual_pnl_pct=8.0,
            intervention_value_usd=-80.0,
            stop_hit=False,
            resolution_status="RESOLVED",
        )
        classify_window(
            sim,
            notional=1000.0,
            signal_expired=False,
            expired_before_5d=False,
            superseded=False,
            unmeasurable=False,
            not_evaluable=False,
        )
        self.assertEqual(sim.classification, "LOSS")

    def test_evaluate_blocked_event_stop_loss_win(self) -> None:
        base = datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc)
        event = {
            "timestamp": base.isoformat(),
            "ticker": "MU",
            "event_type": EVENT_BUY_BLOCKED_BY_TAE,
            "signal": "STRONG BUY",
            "score": 90.0,
            "price": 100.0,
            "intended_trade_usd": 1000.0,
            "shares": 10.0,
            "advisory_action": "RISK_ADVISORY",
            "advisory_confidence": 80,
            "advisory_reasons": ["[REPLAY_CONTEXT] test"],
            "advisory_blockers": ["Quick health not ready: WARN"],
            "block_reason": "TAE RISK_ADVISORY — new BUY blocked",
            "live_bot_cycle_id": "cycle-win",
        }
        portfolio_rows = []
        for offset in range(6):
            day = base + timedelta(days=offset)
            price = 100.0 - (offset * 1.0)
            portfolio_rows.append(
                {
                    "Date": day.strftime("%Y-%m-%d %H:%M:%S"),
                    "Ticker": "MU",
                    "Action": "HOLD",
                    "Price": price,
                    "Shares": 0,
                    "Score": 90,
                    "Signal": "STRONG BUY",
                    "Reason": "",
                    "Current_Price": price,
                    "Invested": 0,
                    "Current_Value": 0,
                    "PnL": 0,
                    "PnL_%": 0,
                }
            )
        portfolio_rows.append(
            {
                "Date": (base + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": "SPY",
                "Action": "HOLD",
                "Price": 500,
                "Shares": 0,
                "Score": 80,
                "Signal": "STRONG BUY",
                "Reason": "",
                "Current_Price": 500,
                "Invested": 0,
                "Current_Value": 0,
                "PnL": 0,
                "PnL_%": 0,
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_path = root / "portfolio.csv"
            _write_portfolio(portfolio_path, portfolio_rows)
            marks = PriceMarkStore(root, portfolio_path=portfolio_path, signals_path=root / "missing.csv")
            record = evaluate_blocked_event(
                event,
                [event],
                marks,
                median_notional=1000.0,
                as_of=base + timedelta(days=10),
            )
            headline = record.windows[str(HEADLINE_WINDOW)]
            self.assertIn(headline.classification, {"WIN", "NEUTRAL"})
            self.assertLessEqual(headline.mae_pct or 0.0, STOP_LOSS_PCT + 0.01)

    def test_build_outcomes_report_zero_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "events.csv"
            _write_events(
                events_path,
                [
                    {
                        "timestamp": "2026-06-01T10:00:00+00:00",
                        "ticker": "MU",
                        "event_type": "BUY_SKIPPED_OTHER_REASON",
                        "signal": "STRONG BUY",
                        "score": 90,
                        "price": 100,
                        "block_reason": "MARKET_SESSION_FILTER",
                        "live_bot_cycle_id": "x1",
                    }
                ],
            )
            from tae_shadow_validation_report import load_events

            events = load_events(events_path)
            report = build_outcomes_report(
                events,
                root=root,
                events_path=events_path,
                portfolio_path=root / "portfolio.csv",
                signals_path=root / "signals.csv",
            )
            self.assertEqual(report["eligible_events"], 0)
            self.assertEqual(report["outcome_tracking_status"], "PENDING_NEXT_PHASE")
            self.assertFalse(report["policy_change_allowed"])

    def test_build_outcomes_report_with_blocked_event(self) -> None:
        base = datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "events.csv"
            _write_events(
                events_path,
                [
                    {
                        "timestamp": base.isoformat(),
                        "ticker": "MU",
                        "event_type": EVENT_BUY_BLOCKED_BY_TAE,
                        "signal": "STRONG BUY",
                        "score": 90,
                        "price": 100,
                        "intended_trade_usd": 1000,
                        "shares": 10,
                        "advisory_action": "RISK_ADVISORY",
                        "advisory_confidence": 80,
                        "advisory_reasons": "[]",
                        "advisory_blockers": '["Quick health not ready: WARN"]',
                        "block_new_buy": "true",
                        "block_reason": "TAE RISK_ADVISORY — new BUY blocked",
                        "live_bot_cycle_id": "cycle1",
                    }
                ],
            )
            portfolio_rows = []
            for offset in range(12):
                day = base + timedelta(days=offset)
                price = 100.0 - offset
                portfolio_rows.append(
                    {
                        "Date": day.strftime("%Y-%m-%d %H:%M:%S"),
                        "Ticker": "MU",
                        "Action": "HOLD",
                        "Price": price,
                        "Shares": 0,
                        "Score": 90,
                        "Signal": "STRONG BUY",
                        "Reason": "",
                        "Current_Price": price,
                        "Invested": 0,
                        "Current_Value": 0,
                        "PnL": 0,
                        "PnL_%": 0,
                    }
                )
            _write_portfolio(root / "portfolio.csv", portfolio_rows)
            from tae_shadow_validation_report import load_events

            events = load_events(events_path)
            report = build_outcomes_report(
                events,
                root=root,
                events_path=events_path,
                portfolio_path=root / "portfolio.csv",
                signals_path=root / "signals.csv",
                as_of=base + timedelta(days=15),
            )
            self.assertEqual(report["eligible_events"], 1)
            self.assertEqual(len(report["resolved_events"]), 1)
            self.assertIn("aggregate_statistics", report)
            self.assertIn("learning_promotion", report)


if __name__ == "__main__":
    unittest.main()
