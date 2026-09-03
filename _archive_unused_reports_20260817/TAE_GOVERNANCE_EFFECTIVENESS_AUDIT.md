# TAE Governance Policy Effectiveness Audit

**Generated:** 2026-07-08T16:21:29+00:00
**Mode:** READ ONLY — measure only
**Final verdict:** **GOVERNANCE_CONTRADICTORY**

## Executive summary

The current PAPER stack is **blocking all new BUY entry** under `policy_state=HIGH_RISK` / `CAPITAL_PRESERVATION_SHADOW`. **72%** of decisions are SKIP; **0 BUY_PAPER** this cycle despite **$12,322** idle cash (**41.0%** unallocated). Hard risk produced **1** hard-stop sell(s) in the trade ledger; soft loss discipline produced **3** policy sells. Governance layers are **fragmented** (PDE decides actions; APPE/DPE/PPG bias scores; structural governance blocks cycle only).

## Data limitations

- Single PDE snapshot (25 decisions, one timestamp)
- Trade ledger spans prior cycle sells (4 trades) vs current decisions (0 SELL)
- Forward returns are horizon-context proxies, not realized post-decision paths
- No counterfactual relaxation simulation performed

## Part 1 — Complete policy inventory

| module | rule | category | priority | execution order | thresholds | consumers |
| --- | --- | --- | ---: | --- | --- | --- |
| `hard_risk_guardian.py` | HARD_STOP_LOSS_-3 | HARD | 4 | 4 | pnl <= -3% → SELL_REQUIRED; <= -5% → FORCE_SELL | PDE, structural_governance |
| `hard_risk_guardian.py` | HARD_CRITICAL_STOP_-5 | HARD | 4 | 4 | pnl <= -5% | PDE |
| `tae_structural_governance.py` | data_validity_gate | HARD | 1 | 1 | critical_all_fresh required | full-paper-cycle |
| `tae_structural_governance.py` | accounting_reconciliation_gate | HARD | 2 | 2 | validate_portfolio_reconciliation ok | full-paper-cycle |
| `tae_structural_governance.py` | capital_safety_gate | HARD | 3 | 3 | broker_executed=false, live_money=false | full-paper-cycle |
| `tae_structural_governance.py` | MTM_ALL_STALE_block | HARD | 12 | 19 | ALL_STALE + open positions → BLOCK | final_verdict |
| `tae_paper_decision_engine.py` | enforce_hard_risk_discipline | HARD | 4 | PDE pre-soft | override → SELL_PAPER=100 | PDE |
| `tae_paper_decision_engine.py` | enforce_position_discipline | HARD | 5 | PDE post-score | zero SELL/PROTECT/REDUCE/ROTATE without position | PDE, execution |
| `tae_paper_decision_engine.py` | enforce_loss_discipline | POLICY | 7 | PDE post-score | -5%/+weak rules; -7% critical soft | PDE |
| `tae_paper_decision_engine.py` | apply_horizon_action_bias | POLICY | 8 | PDE scoring | BUY -28 misaligned; conflict SELL+14 | PDE |
| `tae_paper_decision_engine.py` | APPE_policy_state_HIGH_RISK | POLICY | 9 | PDE scoring | SKIP +15, BUY -8 when HIGH_RISK | PDE |
| `tae_paper_decision_engine.py` | capital_hint_gate | POLICY | 8 | PDE scoring | cash_hint < 1000 → SKIP +15 | PDE |
| `tae_paper_decision_engine.py` | minimum_confidence_18 | POLICY | 9 | PDE final | best score < 18 → SKIP | PDE |
| `tae_paper_decision_engine.py` | apply_hypothesis_rules | LEARNING | 9 | PDE post-select | REJECT → SKIP; no PROMISING → SKIP aggressive | PDE |
| `tae_paper_decision_engine.py` | apply_rule_lifecycle_bias | LEARNING | 9 | PDE scoring | DISABLED blocks; TESTING x0.85 | PDE |
| `tae_paper_decision_engine.py` | apply_adaptive_paper_weights | LEARNING | 9 | PDE scoring | weight multipliers per action | PDE |
| `tae_paper_decision_engine.py` | dpe_evaluator_high_risk_bias | LEARNING | 9 | PDE scoring | BUY -4, PROTECT +5, HOLD +3 | PDE |
| `tae_paper_decision_engine.py` | protection_validation_bias | POLICY | 6 | PDE scoring | prot_boost/reduce_boost/sell_penalty | PDE |
| `tae_paper_decision_engine.py` | apply_stale_source_penalty | HARD | 1 | PDE scoring | historical confidence_penalty | PDE |
| `tae_paper_decision_engine.py` | named_confidence_rules | LEARNING | 9 | PDE scoring | DO_NOT_PROMOTE BUY -10; SCORE_DECAY etc | PDE |
| `tae_portfolio_profit_governor.py` | PORTFOLIO_HIGH_RISK | SHADOW | - | upstream | portfolio_verdict shadow | APPE, GII |
| `tae_adaptive_profit_policy_engine.py` | CAPITAL_PRESERVATION_SHADOW | SHADOW | - | upstream | policy_state HIGH_RISK | PDE policy_context |
| `tae_profit_decision_governor.py` | shadow_protect_bands | SHADOW | - | not in PDE | WATCH/TRAIL/EXIT_PROTECT | GII only |
| `tae_rule_survival.py` | rule_lifecycle | LEARNING | 14 | 14 | DISABLED/DEPRECATED/TESTING states | PDE, governance |
| `tae_adaptive_paper_weights.py` | paper_action_weights | LEARNING | 15 | 15 | capped daily deltas | PDE next cycle |
| `tae_live_promotion_lock.py` | live_promotion_block | HARD | 18 | 18 | live_promotion_allowed=false | governance |
| `tae_investment_council.py` | synthesis_only | REPORT | 20 | 20 | no override | operator |
| `tae_decision_governor.py` | legacy_posture | LEGACY | - | market-open | ALLOWED/BLOCKED/WATCH | confidence evolution |

## Part 2 — BUY blocker analysis

Candidates: **5** | Blocked: **5** | Authority: **PDE**

**MC.PA** — BUY score `0.0` → `PROTECT_PAPER` | held=True | top_growth=True
- Chain: `HELD_POSITION_PATH → HIGH_RISK → CAPITAL_PRESERVATION → DPE_HIGH_RISK_BUY_PENALTY → PROTECT_PAPER`
- First blocker: **HELD_POSITION_PATH**

**SPY** — BUY score `0.0` → `HOLD_PAPER` | held=True | top_growth=True
- Chain: `HELD_POSITION_PATH → HIGH_RISK → CAPITAL_PRESERVATION → DPE_HIGH_RISK_BUY_PENALTY → HOLD_PAPER`
- First blocker: **HELD_POSITION_PATH**

**PM** — BUY score `0.0` → `HOLD_PAPER` | held=True | top_growth=True
- Chain: `HELD_POSITION_PATH → HIGH_RISK → CAPITAL_PRESERVATION → DPE_HIGH_RISK_BUY_PENALTY → HOLD_PAPER`
- First blocker: **HELD_POSITION_PATH**

**PG** — BUY score `0.0` → `HOLD_PAPER` | held=True | top_growth=True
- Chain: `HELD_POSITION_PATH → HIGH_RISK → CAPITAL_PRESERVATION → DPE_HIGH_RISK_BUY_PENALTY → HOLD_PAPER`
- First blocker: **HELD_POSITION_PATH**

**MRK** — BUY score `0.0` → `HOLD_PAPER` | held=True | top_growth=True
- Chain: `HELD_POSITION_PATH → HIGH_RISK → CAPITAL_PRESERVATION → DPE_HIGH_RISK_BUY_PENALTY → HOLD_PAPER`
- First blocker: **HELD_POSITION_PATH**

## Part 3 — Missed opportunity (proxy)

| blocker | count | missed 5d% | avoided 5d% |
| --- | ---: | ---: | ---: |
| HELD_POSITION_PATH | 5 | 4.35 | 0.9929 |

## Part 4 — SELL analysis (trade ledger + decisions)

- **MU** realized=$-141.54 hard=False policy=True protect→sell=True
  - weak lifecycle=PROFIT_DECAY; weak lifecycle + -6.8% loss favors SELL over PROTECT; GII strategy=TIGHTEN_TRAIL_SHADOW; horizon supports BUY (short+medium positive); knowledge base r
- **AMAT** realized=$-124.60 hard=False policy=True protect→sell=True
  - weak lifecycle=PROFIT_DECAY; weak lifecycle + -6.0% loss favors SELL over PROTECT; GII strategy=TIGHTEN_TRAIL_SHADOW; horizon supports BUY (short+medium positive); knowledge base r
- **SIE.DE** realized=$-140.27 hard=False policy=False protect→sell=True
  - protection posture/signal=/TRAILING_PROTECTION_SHADOW; monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_CH
- **QQQ** realized=$-9.12 hard=True policy=False protect→sell=True
  - HARD RISK override (HARD_STOP_LOSS_-3): -3.21% loss → SELL_PAPER (required=SELL_REQUIRED, before soft logic); longitudinal memory action bias -0.500

## Part 5 — Policy effectiveness

| policy | applied | blocked | net | rec |
| --- | ---: | ---: | --- | --- |
| HARD_STOP_-3% | 1 | 0 | caps loss at -3% | **KEEP** |
| APPE_HIGH_RISK | 25 | 5 | 0 BUY this cycle | **TUNE** |
| DPE_BUY_PENALTY | 25 | 25 | BUY -4 all tickers in HIGH_RISK | **TUNE** |
| MIN_CONFIDENCE_18 | 18 | - | - | **KEEP** |
| LOSS_DISCIPLINE_-5/-7 | 3 | - | -275.2629 | **KEEP** |
| PROTECT→SELL_FLIP | 4 | - | -415.5322 | **TUNE** |

### Top rules by net PnL impact

| rule | state | net $ | rec |
| --- | --- | ---: | --- |
| LTB-CONF-MISSED_PROFIT_PROTECTION | ACTIVE | 113.63 | **KEEP** |
| LTB-CONF-SCORE_PERSISTENCE_AFTER_ | ACTIVE | 113.63 | **KEEP** |
| LTB-CONF-STOP_REENTRY_CHURN | ACTIVE | 113.63 | **KEEP** |
| LTB-DPE-PHIL-001 | ACTIVE | 113.63 | **KEEP** |
| LTB-REPLAY-04 | ACTIVE | 113.63 | **KEEP** |
| MISSED_PROFIT_PROTECTION | ACTIVE | 113.63 | **KEEP** |
| LTB-LIFE-PM-03 | TESTING | 98.73 | **TUNE** |
| LTB-LIFE-LLY-05 | TESTING | 59.05 | **TUNE** |

## Part 6 — Authority influence ranking

| component | score |
| --- | ---: |
| PDE | 50 |
| DPE Evaluator | 25 |
| Adaptive Weights | 25 |
| Rule Survival | 25 |
| Knowledge Base | 25 |
| APPE/PPG (shadow) | 25 |
| Structural Governance | 10 |
| Hard Risk | 2 |
| Investment Council | 0 |

## Part 7 — Contradictions

- **MC.PA** — TOP_GROWTH→PROTECT: GII top growth candidate received PROTECT not BUY/HOLD
- **MU** — PROTECT→SELL (execution): action_changed
- **AMAT** — PROTECT→SELL (execution): action_changed
- **SIE.DE** — PROTECT→SELL (execution): action_changed
- **QQQ** — PROTECT→SELL (execution): action_changed

## Part 8 — Capital efficiency

- Cash: **$12,321.97** (41.0% of portfolio idle)
- Utilization: **59.0%**
- GII top growth (unbought): `['MC.PA', 'MRK', 'PG', 'PM', 'SPY']`
- PDE BUY this cycle: **0**
- Relaxation counterfactual: **NOT MEASURED**

## Part 9 — Governance scorecard (sample)

| restriction | category | recommendation |
| --- | --- | --- |
| HARD_STOP_LOSS_-3 | HARD | **KEEP** |
| HARD_CRITICAL_STOP_-5 | HARD | **KEEP** |
| data_validity_gate | HARD | **KEEP** |
| accounting_reconciliation_gate | HARD | **KEEP** |
| capital_safety_gate | HARD | **KEEP** |
| MTM_ALL_STALE_block | HARD | **KEEP** |
| enforce_hard_risk_discipline | HARD | **KEEP** |
| enforce_position_discipline | HARD | **KEEP** |
| enforce_loss_discipline | POLICY | **TUNE** |
| apply_horizon_action_bias | POLICY | **TUNE** |
| APPE_policy_state_HIGH_RISK | POLICY | **TUNE** |
| capital_hint_gate | POLICY | **TUNE** |
| minimum_confidence_18 | POLICY | **TUNE** |
| apply_hypothesis_rules | LEARNING | **TUNE** |
| apply_rule_lifecycle_bias | LEARNING | **TUNE** |

## Final verdict: **GOVERNANCE_CONTRADICTORY**

Governance **reduces PAPER profitability** in the measured window by: (1) zero BUY deployment under HIGH_RISK, (2) stacked BUY penalties (APPE + DPE), (3) PROTECT→SELL flips realizing losses. Hard -3% stop **preserved capital** on QQQ (-$9.12 vs deeper hold). Net effect: **conservative — capital preserved but opportunity cost elevated**.
