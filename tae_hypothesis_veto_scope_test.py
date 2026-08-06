import unittest

from tae_paper_decision_engine import apply_hypothesis_rules


class HypothesisVetoScopeTest(unittest.TestCase):
    def test_portfolio_policy_reject_does_not_veto_canonical_buy(self):
        ctx = {
            "exp_by_ticker": {
                "NVDA": [],
                "_PORTFOLIO": [{
                    "hypothesis_id": "LTB-DPE-PHIL-001",
                    "verdict": "REJECT",
                    "paper_experiment_action": "PAPER_DPE_PHILOSOPHY_WEIGHT",
                }],
            },
            "hypotheses": [],
        }

        action, _, reason = apply_hypothesis_rules(
            "NVDA", "BUY_PAPER", 0.25, ctx
        )

        self.assertEqual("BUY_PAPER", action, reason)

    def test_unmapped_exit_experiment_does_not_veto_buy(self):
        ctx = {
            "exp_by_ticker": {
                "MRK": [{
                    "hypothesis_id": "LTB-LOSS-001",
                    "verdict": "REJECT",
                    "paper_experiment_action": "PAPER_EXIT_POLICY_CHALLENGER",
                }]
            },
            "hypotheses": [],
        }

        action, _, reason = apply_hypothesis_rules(
            "MRK", "BUY_PAPER", 0.25, ctx
        )

        self.assertEqual("BUY_PAPER", action, reason)

    def test_action_specific_reject_still_blocks_that_action(self):
        ctx = {
            "exp_by_ticker": {
                "ABC": [{
                    "hypothesis_id": "LTB-ROTATE-001",
                    "verdict": "REJECT",
                    "paper_experiment_action": "PAPER_REALLOCATION",
                }]
            },
            "hypotheses": [],
        }

        action, _, reason = apply_hypothesis_rules(
            "ABC", "ROTATE_PAPER", 0.80, ctx
        )

        self.assertEqual("SKIP_PAPER", action)
        self.assertIn("action-specific experiment REJECT", reason)

    def test_buy_does_not_require_promising_experiment(self):
        ctx = {
            "exp_by_ticker": {"ABC": []},
            "hypotheses": [],
        }

        action, _, reason = apply_hypothesis_rules(
            "ABC", "BUY_PAPER", 0.25, ctx
        )

        self.assertEqual("BUY_PAPER", action, reason)


if __name__ == "__main__":
    unittest.main()
