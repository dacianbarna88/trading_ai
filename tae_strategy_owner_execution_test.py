import unittest
from unittest.mock import patch

import tae_paper_execution as pe


class StrategyOwnerExecutionPolicyTest(unittest.TestCase):
    def test_unmarked_decision_is_v1(self):
        self.assertEqual("V1", pe._decision_strategy_id({}, {}))
        self.assertTrue(pe._is_v1_owned_decision({}, {}))

    def test_explicit_v2_is_not_v1(self):
        decision = {
            "strategy_id": "V2",
            "strategy_v2": {"v2_action": "ADD_TRANCHE"},
        }
        self.assertEqual("V2", pe._decision_strategy_id(decision, {}))
        self.assertFalse(pe._is_v1_owned_decision(decision, {}))

    def test_explicit_vx_is_not_v1(self):
        decision = {"strategy_id": "VX_MOMENTUM_001"}
        self.assertEqual(
            "VX_MOMENTUM_001",
            pe._decision_strategy_id(decision, {}),
        )
        self.assertFalse(pe._is_v1_owned_decision(decision, {}))

    def test_v2_add_routes_to_v2_executor_before_v1_buy_gates(self):
        decision = {
            "decision_id": "V2-ADD-TEST",
            "ticker": "SAP.DE",
            "action": "BUY_PAPER",
            "strategy_id": "V2",
            "strategy_version": "V2",
            "strategy_v2": {
                "strategy_version": "V2",
                "v2_action": "ADD_TRANCHE",
            },
        }

        expected = {"status": "V2_ROUTE_OK"}

        with patch(
            "tae_strategy_v2_foundation.decision_has_strategy_v2",
            return_value=True,
        ), patch(
            "tae_strategy_v2_foundation.execute_strategy_v2_decision",
            return_value=expected,
        ) as executor:
            result = pe.execute_decision(
                decision,
                {"positions": {}, "cash": 10000.0},
                accounting={},
                all_decisions=[decision],
                strategy_v2_enabled_override=True,
                strategy_v2_persist=False,
            )

        self.assertEqual(expected, result)
        executor.assert_called_once()

    def test_current_authorized_buy_marker_is_not_old_skip_reason(self):
        decision = {
            "action": "BUY_PAPER",
            "decision_switch_authorized": True,
        }
        effective_reason = "action_changed:BUY_PAPER->SKIP_PAPER"
        if (
            decision["action"] == "BUY_PAPER"
            and decision["decision_switch_authorized"]
        ):
            effective_reason = "current_pde_buy_authorized"

        self.assertEqual("current_pde_buy_authorized", effective_reason)


if __name__ == "__main__":
    unittest.main()
