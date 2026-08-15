#!/usr/bin/env python3
"""TEST_ONLY — LEARNING_DECISION_TO_ECONOMIC_OUTCOME_CLOSURE invariants.

Fixtures are marked TEST_ONLY and must not enter economic datasets.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tae_learning_decision_to_economic_outcome_closure as closure


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jsonl":
        path.write_text(
            "".join(json.dumps(r) + "\n" for r in obj),
            encoding="utf-8",
        )
    else:
        path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _fixture_root() -> Path:
    """Build an isolated TEST_ONLY runtime tree."""
    td = Path(tempfile.mkdtemp(prefix="tae_closure_test_"))
    ro = td / "runtime_outputs"

    flips = []
    # 8 BUY→SKIP
    for i, t in enumerate(["AZN.L", "BP.L", "GE", "HSBA.L", "MSFT", "NVDA", "QQQ", "SAP.DE"]):
        flips.append(
            {
                "ledger_key": f"skip-{i}",
                "ticker": t,
                "base_action": "BUY_PAPER",
                "learned_action": "SKIP_PAPER",
                "base_score": 50.0,
                "learned_score": 6.67,
                "impact_class": "BLOCKED_BY_LEARNING",
                "decision_id_on": f"PDEC-{t}-0001",
                "decision_id_off": f"PDEC-{t}-0001",
                "decision_timestamp": "2026-07-23T22:35:36Z",
                "learning_state_note": "HISTORICAL_COUNTERFACTUAL_NOT_RECONSTRUCTIBLE",
                "learning_components_applied": [],
                "forward_matured": False,
                "TEST_ONLY": True,
            }
        )
    # 7 HOLD→PROTECT/REDUCE
    for i, (t, post) in enumerate(
        [
            ("AAPL", "PROTECT_PAPER"),
            ("ABBV", "PROTECT_PAPER"),
            ("DIA", "PROTECT_PAPER"),
            ("HD", "PROTECT_PAPER"),
            ("SHEL.L", "PROTECT_PAPER"),
            ("MC.PA", "REDUCE_PAPER"),
            ("PM", "REDUCE_PAPER"),
        ]
    ):
        flips.append(
            {
                "ledger_key": f"exit-{i}",
                "ticker": t,
                "base_action": "HOLD_PAPER",
                "learned_action": post,
                "base_score": 40.0,
                "learned_score": 60.0,
                "impact_class": "EXIT_TIMING_CHANGED",
                "decision_id_on": f"PDEC-{t}-0001",
                "decision_id_off": f"PDEC-{t}-0001",
                "decision_timestamp": "2026-07-23T22:35:36Z",
                "learning_state_note": "HISTORICAL_COUNTERFACTUAL_NOT_RECONSTRUCTIBLE",
                "learning_components_applied": [],
                "forward_matured": False,
                "TEST_ONLY": True,
            }
        )

    pending = {
        "schema": "test.pending",
        "outcomes": {
            r["ledger_key"]: {
                "outcome_id": r["ledger_key"],
                "status": "NOT_YET_MATURE",
                "TEST_ONLY": True,
            }
            for r in flips
        },
        "TEST_ONLY": True,
    }

    fpc = {
        "step_results": [
            {
                "step": "post_learning_execution",
                "ok": True,
                "candidates": 6,
                "orders_created": 6,
                "trades_written": 0,
                "executed_tickers": ["AIR.PA"],
                "skipped": [
                    {"ticker": "AAPL", "reason": "switch_not_authorized"},
                    {"ticker": "ABBV", "reason": "switch_not_authorized"},
                ],
                "TEST_ONLY": True,
            }
        ],
        "TEST_ONLY": True,
    }

    ce = {
        "decision_changes": [
            {
                "ticker": "AAPL",
                "action_before": "HOLD_PAPER",
                "action_after": "SELL_PAPER",
            },
            {
                "ticker": "AIR.PA",
                "action_before": "SELL_PAPER",
                "action_after": "BUY_PAPER",
            },
        ],
        "TEST_ONLY": True,
    }

    orders = [
        {
            "timestamp": "2026-07-31T20:16:05+00:00",
            "ticker": "AAPL",
            "action": "SELL_PAPER",
            "status": "SKIPPED_SWITCH_NOT_AUTHORIZED",
            "decision_id": "PDEC-AAPL-0001",
            "TEST_ONLY": True,
        },
        {
            "timestamp": "2026-07-31T20:15:57+00:00",
            "ticker": "AIR.PA",
            "action": "SELL_PAPER",
            "status": "EXECUTED",
            "decision_id": "PDEC-AIR.PA-0003",
            "reason": "PROFIT_TRAILING_EXIT_DRAWDOWN_2_PERCENT",
            "TEST_ONLY": True,
        },
    ]
    trades = [
        {
            "timestamp": "2026-07-31T20:15:57+00:00",
            "ticker": "AIR.PA",
            "action": "SELL_PAPER",
            "decision_id": "PDEC-AIR.PA-0003",
            "realized_pnl": 22.8,
            "execution_reason": "retry_after_non_terminal:SKIPPED_SWITCH_NOT_AUTHORIZED",
            "TEST_ONLY": True,
        }
    ]

    hard = {
        "exits": {
            f"PDEC-{t}-0001": {"ticker": t, "exit_reason": "HARD_RISK", "TEST_ONLY": True}
            for t in [
                "AMAT",
                "GE",
                "LLY",
                "MC.PA",
                "MRK",
                "MU",
                "NVDA",
                "PM",
                "QQQ",
                "SIE.DE",
                "X",
            ]
        },
        "TEST_ONLY": True,
    }
    # 11 exits
    assert len(hard["exits"]) == 11

    decisions = {
        "decisions": [
            {"ticker": "AMAT", "action": "SKIP_PAPER"},
            {"ticker": "MU", "action": "SKIP_PAPER"},
            {"ticker": "GE", "action": "BUY_PAPER"},
            {"ticker": "MC.PA", "action": "BUY_PAPER"},
            {"ticker": "NVDA", "action": "SKIP_PAPER"},
            {"ticker": "QQQ", "action": "SKIP_PAPER"},
            {"ticker": "LLY", "action": "HOLD_PAPER"},
            {"ticker": "MRK", "action": "HOLD_PAPER"},
            {"ticker": "PM", "action": "SELL_PAPER"},
            {"ticker": "SIE.DE", "action": "HOLD_PAPER"},
            {"ticker": "X", "action": "HOLD_PAPER"},
        ],
        "TEST_ONLY": True,
    }

    _write(ro / "learning_economic_attribution/ledger.jsonl", flips)
    _write(ro / "learning_economic_attribution/pending_outcomes.json", pending)
    _write(
        ro / "learning_economic_attribution/status.json",
        {"status": "FAILED", "last_error": "AttributeError: TEST_ONLY", "TEST_ONLY": True},
    )
    _write(
        ro / "learning_economic_attribution/summary.json",
        {
            "action_flips": 15,
            "matured_impact_decisions": 0,
            "pending_impact_decisions": 15,
            "economic_value_proven": False,
            "decision_impact_proven": True,
            "TEST_ONLY": True,
        },
    )
    _write(ro / "full_paper_cycle/summary.json", fpc)
    _write(ro / "governance/constitutional_evolution.json", ce)
    _write(ro / "paper_execution/paper_orders.jsonl", orders)
    _write(ro / "paper_execution/paper_trades.jsonl", trades)
    _write(ro / "longitudinal_memory/hard_risk_post_exit.json", hard)
    _write(ro / "paper_decisions/paper_decisions.json", decisions)
    _write(
        ro / "paper_execution/paper_daily_equity.jsonl",
        [{"timestamp": "2026-08-03", "reconciliation_status": "PASS", "reconciliation_delta": 0.0, "TEST_ONLY": True}],
    )
    return td


class TestLearningDecisionEconomicClosure(unittest.TestCase):
    def test_classify_skip_non_executable(self):
        row = {
            "ledger_key": "k1",
            "ticker": "MSFT",
            "base_action": "BUY_PAPER",
            "learned_action": "SKIP_PAPER",
            "impact_class": "BLOCKED_BY_LEARNING",
            "decision_id_on": "PDEC-MSFT-0001",
            "learning_state_note": "HISTORICAL_COUNTERFACTUAL_NOT_RECONSTRUCTIBLE",
            "learning_components_applied": [],
            "TEST_ONLY": True,
        }
        d = closure.classify_decision_delta(row, {"status": "NOT_YET_MATURE"})
        self.assertEqual(d["TERMINAL_STATUS"], "NON_EXECUTABLE_ACTION")
        self.assertFalse(d["EXECUTION_ELIGIBLE"])
        self.assertFalse(d["EXECUTION_ATTEMPTED"])
        self.assertIsNone(d["EXECUTION_ID"])

    def test_classify_counterfactual_protect_excluded(self):
        row = {
            "ledger_key": "k2",
            "ticker": "AAPL",
            "base_action": "HOLD_PAPER",
            "learned_action": "PROTECT_PAPER",
            "impact_class": "EXIT_TIMING_CHANGED",
            "decision_id_on": "PDEC-AAPL-0001",
            "learning_state_note": "HISTORICAL_COUNTERFACTUAL_NOT_RECONSTRUCTIBLE",
            "learning_components_applied": [],
            "TEST_ONLY": True,
        }
        d = closure.classify_decision_delta(row, {"status": "NOT_YET_MATURE"})
        self.assertEqual(d["TERMINAL_STATUS"], "EXCLUDED_NON_ECONOMIC")
        self.assertFalse(d["EXECUTION_ELIGIBLE"])
        self.assertEqual(d["BLOCK_REASON"], "HISTORICAL_COUNTERFACTUAL_MEASUREMENT_NOT_LIVE_HANDOFF")

    def test_full_fixture_audit_invariants(self):
        root = _fixture_root()
        audit = closure.build_audit(root=root)
        a = audit["audit_before_patch"]
        self.assertEqual(a["decision_deltas_found"], 15)
        self.assertEqual(a["executed_deltas"], 0)
        self.assertEqual(a["settled_deltas"], 0)
        self.assertEqual(a["true_wiring_gaps"], 0)
        self.assertEqual(a["execution_eligible_deltas"], 0)
        self.assertEqual(a["delta_status_counts"].get("NON_EXECUTABLE_ACTION"), 8)
        self.assertEqual(a["delta_status_counts"].get("EXCLUDED_NON_ECONOMIC"), 7)
        # All 15 have deterministic terminal status (no UNKNOWN)
        for d in a["deltas"]:
            self.assertNotIn(d["TERMINAL_STATUS"], {"UNKNOWN", "MISSING", "UNATTRIBUTED"})
            self.assertTrue(d["TERMINAL_STATUS"])
        self.assertFalse(audit["go_no_go"]["patch_required"])
        self.assertEqual(audit["final_verdict"], "NO_PATCH_REQUIRED_DELTAS_CORRECTLY_NOT_EXECUTED")

        h = audit["historical_post_learning_reconciliation"]
        self.assertEqual(h["verdict"], "B")
        self.assertEqual(h["ssot_orders_created"], 6)
        self.assertEqual(h["ssot_trades_written"], 0)
        self.assertFalse(h["claim_found_in_ssot"])
        self.assertFalse(h["air_pa_trade_caused_by_learning_delta"])

        sc = audit["stop_cluster_closed_loop"]
        self.assertEqual(sc["stop_clusters_found"], 11)
        self.assertEqual(sc["stop_clusters_learned"], 11)
        self.assertEqual(sc["stop_clusters_prevented"], 0)

        self.assertEqual(audit["accounting"]["status"], "PASS")
        self.assertEqual(audit["chain"]["OUTCOME_TO_MEMORY"], "PASS")
        self.assertEqual(audit["chain"]["MEMORY_TO_DECISION_DELTA"], "PASS")

    def test_v1_v2_not_merged_into_verdict(self):
        # Closure audit must not treat parallel arms as the 15-delta cohort.
        root = _fixture_root()
        audit = closure.build_audit(root=root)
        blob = json.dumps(audit)
        self.assertNotIn("PARALLEL_V1_AS_PROOF", blob)
        self.assertEqual(audit["paper_only"], True)
        self.assertEqual(audit["live_mutation_allowed"], False)

    def test_no_sell_or_hard_risk_semantic_change_in_module(self):
        src = Path(closure.__file__).read_text(encoding="utf-8")
        self.assertIn("NO_LIVE_CHANGE", src)
        self.assertIn("Does not mutate", src)
        # Module must remain report/audit — no order journal writes
        self.assertNotIn("paper_orders.jsonl\".write", src)
        self.assertNotIn("open(ORDERS_PATH", src)


if __name__ == "__main__":
    unittest.main()
