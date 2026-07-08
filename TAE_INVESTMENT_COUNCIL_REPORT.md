# TAE Investment Council Report

**Generated:** 2026-07-08T19:30:10+00:00
**Mode:** PAPER_ONLY — SYNTHESIS ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Governance verdict:** **READY_FOR_PAPER_DAY**

## 1. Executive recommendation

PAPER cycle READY_FOR_PAPER_DAY. Hard risk active: AMAT. PDE SELL: AMAT, HD. PDE PROTECT: AAPL, LLY, MC.PA. PDE BUY: HSBA.L, MU. Policy HIGH_RISK / PPG PORTFOLIO_HIGH_RISK. DPE philosophy COLLABORATIVE. Morning audit ATTENTION_REQUIRED. live_promotion_allowed=false.

## 2. Today's top BUY candidates

- **HSBA.L** | confidence=0.275 | pde_buy=True | gii_top_growth=False
- **MU** | confidence=0.275 | pde_buy=True | gii_top_growth=False
- **MRK** | growth_score=94.2 | pde_buy=False | gii_top_growth=True
- **PG** | growth_score=94.1 | pde_buy=False | gii_top_growth=True
- **PM** | growth_score=87.7 | pde_buy=False | gii_top_growth=True
- **SPY** | growth_score=83.9 | pde_buy=False | gii_top_growth=True
- **MC.PA** | growth_score=68.2 | pde_buy=False | gii_top_growth=True

## 3. Today's top SELL candidates

- **AMAT** | confidence=0.95 | hard_risk_override=True | hard_rule=HARD_STOP_LOSS_-3
- **HD** | confidence=0.5 | hard_risk_override=False

## 4. Today's top PROTECT candidates

- **AAPL** | confidence=0.931 | expected_profit_delta=5.43
- **LLY** | confidence=0.921 | expected_profit_delta=4.96
- **MC.PA** | confidence=0.461 | expected_profit_delta=3.31

## 5. Today's HOLD candidates

- **AIR.PA** | confidence=0.753
- **DIA** | confidence=0.753
- **GE** | confidence=0.753
- **SPY** | confidence=0.675
- **PM** | confidence=0.618
- **PG** | confidence=0.616
- **MRK** | confidence=0.593

## 6. Hard risk alerts

- **AMAT** | pnl_pct=-3.4959 | status=STOP_LOSS_BREACHED | required_action=SELL_REQUIRED | hard_rule=HARD_STOP_LOSS_-3

## 6b. Conflict resolution (EV evidence)

- Loaded: **True** | tickers: **25** | policy: **HIGH_RISK** | cash hint: **$2,335.28**

### Top conflicts

- **AAPL** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **AIR.PA** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **DIA** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **GE** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **HSBA.L** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **MU** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **QQQ** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **ABBV** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER

### BUY blocked despite idle cash (positive BUY EV)

- none

### STRONG BUY → SKIP cases

- none

## 6c. Decision state (anti-churn)

- Switch authorized (PDE): **6**
- Switch blocked (PDE): **3**
- Conflict switch authorized: **4**
- Conflict switch blocked: **0**
- Cooldown active tickers: **0**
- High churn risk tickers: **4**

### Proposed action changes

- **HSBA.L** SKIP_PAPER→BUY_PAPER authorized=yes reason=non_trade_or_allowed EV=1.4635/0.15
- **MU** SELL_PAPER→BUY_PAPER authorized=yes reason=ev_margin_met_post_cooldown EV=1.5435/0.15
- **HD** BUY_PAPER→SELL_PAPER authorized=yes reason=ev_margin_met EV=1.2481/0.15
- **MC.PA** HOLD_PAPER→PROTECT_PAPER authorized=yes reason=non_trade_or_allowed EV=-0.3168/0.15
- **AIR.PA** BUY_PAPER→HOLD_PAPER authorized=no reason=insufficient_ev_margin_hold EV=-1.0/0.15
- **DIA** BUY_PAPER→HOLD_PAPER authorized=no reason=insufficient_ev_margin_hold EV=-1.0/0.15
- **GE** BUY_PAPER→HOLD_PAPER authorized=no reason=insufficient_ev_margin_hold EV=-1.0/0.15
- **QQQ** SELL_PAPER→SKIP_PAPER authorized=yes reason=non_trade_or_allowed EV=0.0/0.15

## 7. Portfolio rebuild view

- GII portfolio strategy: **PROTECT_PROFIT_SHADOW**
- Would BUY: `['HSBA.L', 'MU']`
- Would SELL: `['AMAT', 'HD']`
- Would ROTATE: `[]`
- Would REDUCE: `[]`
- Note: Synthesis only — reflects existing PDE/GII outputs, not new decisions.

## 8. Strongest rules

- **MISSED_PROFIT_PROTECTION** | state=ACTIVE | net_pnl_impact=8010.7954 | win_rate=0.8889
- **LTB-CONF-MISSED_PROFIT_PROTECTION** | state=TRUSTED | net_pnl_impact=7979.7577 | win_rate=0.8
- **LTB-CONF-SCORE_PERSISTENCE_AFTER_** | state=TRUSTED | net_pnl_impact=7979.7577 | win_rate=0.8
- **LTB-CONF-STOP_REENTRY_CHURN** | state=TRUSTED | net_pnl_impact=7979.7577 | win_rate=0.8
- **LTB-DPE-PHIL-001** | state=TRUSTED | net_pnl_impact=7979.7577 | win_rate=0.8
- **LTB-REPLAY-04** | state=TRUSTED | net_pnl_impact=7979.7577 | win_rate=0.8
- **LTB-STALE-001** | state=ACTIVE | net_pnl_impact=7841.614 | win_rate=0.8
- **SCORE_DECAY_SHADOW** | state=ACTIVE | net_pnl_impact=6231.7027 | win_rate=0.8333

## 9. Weakest / disabled rules

- **LTB-OPP-AMAT-03** | state=TESTING | net_pnl_impact=-31.0377 | reason=insufficient evidence (1<5)
- **LTB-PROT-AMAT** | state=TESTING | net_pnl_impact=-31.0377 | reason=insufficient evidence (1<5)
- **LTB-LIFE-SPY-04** | state=TESTING | net_pnl_impact=-19.9769 | reason=insufficient evidence (1<5)
- **LTB-PROT-AAPL** | state=TESTING | net_pnl_impact=6.9258 | reason=insufficient evidence (1<5)
- **LTB-LIFE-PG-01** | state=TESTING | net_pnl_impact=28.124 | reason=insufficient evidence (1<5)
- **LTB-PROT-PG** | state=TESTING | net_pnl_impact=28.124 | reason=insufficient evidence (1<5)
- **LTB-LIFE-LLY-05** | state=TESTING | net_pnl_impact=39.9771 | reason=insufficient evidence (1<5)
- **LTB-PROT-LLY** | state=TESTING | net_pnl_impact=39.9771 | reason=insufficient evidence (1<5)

## 10. DPE philosophy view

- Preferred philosophy: **COLLABORATIVE**
- Adaptive confidence: **88.0**
- Competitive / Collaborative: **25.0% / 75.0%**
- Context: **HIGH RISK + MODERATE VOLATILITY**
- Evaluator winner: **N/A**
- Policy state: **HIGH_RISK** (CAPITAL_PRESERVATION_SHADOW)
- Recommendation: Continue PAPER experiment prioritizing COLLABORATIVE philosophy (75% weight). Monitor competitive arm at 25%. No live promotion.

## 11. Canonical vs PAPER result

- Canonical value: **$30,340.91**
- PAPER value: **$43,316.37**
- Delta: **$12,975.46**
- PAPER reconciliation: **PASS**
- Explanation: PAPER portfolio diverges by $12,975.46 total value (+0 positions, $13,355.73 cash delta, $6,699.04 realized delta, $6,276.41 unrealized delta) after isolated PAPER execution and mark-to-market.

## 12. Capital / cash status

- PAPER cash: **$15,691.01**
- PAPER total value: **$43,316.37**
- PAPER realized / unrealized PnL: **$6,699.04** / **$6,276.41**
- Open PAPER positions: **12**
- PPG verdict: **PORTFOLIO_HIGH_RISK**
- APPE policy: **HIGH_RISK**

## 13. What changed since last cycle

- Executive recommendation: 'PAPER cycle READY_FOR_PAPER_DAY. Hard risk active: AMAT. PDE PROTECT: AAPL, LLY. PDE BUY: AMAT, AIR.PA, DIA, GE, HD. Policy HIGH_RISK / PPG PORTFOLIO_HIGH_RISK. DPE philosophy COLLABORATIVE. live_promotion_allowed=false.' → 'PAPER cycle READY_FOR_PAPER_DAY. Hard risk active: AMAT. PDE SELL: AMAT, HD. PDE PROTECT: AAPL, LLY, MC.PA. PDE BUY: HSBA.L, MU. Policy HIGH_RISK / PPG PORTFOLIO_HIGH_RISK. DPE philosophy COLLABORATIVE. Morning audit ATTENTION_REQUIRED. live_promotion_allowed=false.'
- PAPER portfolio value: 43316.3697 → 43316.3693
- PAPER cash: 13739.7094 → 15691.0138
- Action plan items: 12 → 14
- New action plan entries: [('AIR.PA', 'HOLD_PAPER'), ('AMAT', 'SELL_PAPER'), ('DIA', 'HOLD_PAPER'), ('GE', 'HOLD_PAPER'), ('HD', 'SELL_PAPER'), ('HSBA.L', 'BUY_PAPER'), ('MC.PA', 'PROTECT_PAPER'), ('MU', 'BUY_PAPER')]
- Removed action plan entries: [('AIR.PA', 'BUY_PAPER'), ('AMAT', 'BUY_PAPER'), ('DIA', 'BUY_PAPER'), ('GE', 'BUY_PAPER'), ('HD', 'BUY_PAPER'), ('MC.PA', 'HOLD_PAPER')]

## 14. Final PAPER action plan

Synthesized from existing PDE decisions — council does not override hard rules.

- **AMAT** → `SELL_PAPER` (conf=0.95, hard_override=True) — HARD RISK override (HARD_STOP_LOSS_-3): -3.50% loss → SELL_PAPER (required=SELL_REQUIRED, before soft logic)
- **HD** → `SELL_PAPER` (conf=0.5, hard_override=False) — low capital_efficiency=0.0; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_CHURN, TRAI
- **AAPL** → `PROTECT_PAPER` (conf=0.931, hard_override=False) — protection posture/signal=/TRAILING_PROTECTION_SHADOW; monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rules: M
- **LLY** → `PROTECT_PAPER` (conf=0.921, hard_override=False) — protection posture/signal=TRAIL_SHADOW/; monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rules: MISSED_PROFIT_P
- **MC.PA** → `PROTECT_PAPER` (conf=0.461, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENT
- **HSBA.L** → `BUY_PAPER` (conf=0.275, hard_override=False) — signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_D
- **MU** → `BUY_PAPER` (conf=0.275, hard_override=False) — signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_D
- **AIR.PA** → `HOLD_PAPER` (conf=0.753, hard_override=False) — low capital_efficiency=0.0; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_CHURN, TRAI
- **DIA** → `HOLD_PAPER` (conf=0.753, hard_override=False) — low capital_efficiency=0.0; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_CHURN, TRAI
- **GE** → `HOLD_PAPER` (conf=0.753, hard_override=False) — low capital_efficiency=0.0; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_CHURN, TRAI
- **SPY** → `HOLD_PAPER` (conf=0.675, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; horizon: candidate alignment beats weakest held position; knowledge base rules: M
- **PM** → `HOLD_PAPER` (conf=0.618, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_
- **PG** → `HOLD_PAPER` (conf=0.616, hard_override=False) — healthy winner lifecycle=SURVIVED; horizon: candidate alignment beats weakest held position; knowledge base rules: MISSE
- **MRK** → `HOLD_PAPER` (conf=0.593, hard_override=False) — healthy winner lifecycle=SURVIVED; horizon: candidate alignment beats weakest held position; knowledge base rules: MISSE

## Operator command

```bash
python3 tae.py investment-council
```
