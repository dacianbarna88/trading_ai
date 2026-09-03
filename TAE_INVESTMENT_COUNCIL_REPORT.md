# TAE Investment Council Report

**Generated:** 2026-09-03T13:15:23+00:00
**Mode:** PAPER_ONLY — SYNTHESIS ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Governance verdict:** **READY_FOR_PAPER_DAY**

## 1. Executive recommendation

PAPER cycle READY_FOR_PAPER_DAY. PDE PROTECT: QQQ. PDE BUY: PM, LLY, ADBE, HPQ, ICE. Policy WATCH / PPG PORTFOLIO_WATCH. DPE philosophy COMPETITIVE. live_promotion_allowed=false.

## 2. Today's top BUY candidates

- **PM** | confidence=0.946 | growth_score=83.6 | pde_buy=True | gii_top_growth=True
- **LLY** | confidence=0.727 | growth_score=75.2 | pde_buy=True | gii_top_growth=True
- **ADBE** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **HPQ** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **ICE** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **MCO** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **NOW** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **QRVO** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **SNPS** | confidence=0.717 | pde_buy=True | gii_top_growth=False
- **SPGI** | confidence=0.717 | pde_buy=True | gii_top_growth=False

## 3. Today's top SELL candidates

- none

## 4. Today's top PROTECT candidates

- **QQQ** | confidence=0.652 | expected_profit_delta=0.94

## 5. Today's HOLD candidates

- **SPY** | confidence=0.939
- **MRK** | confidence=0.817
- **PG** | confidence=0.817
- **DIA** | confidence=0.678
- **ALV.DE** | confidence=0.662
- **SAP.DE** | confidence=0.597
- **AAPL** | confidence=0.499
- **ULVR.L** | confidence=0.49
- **ABBV** | confidence=0.409
- **SHEL.L** | confidence=0.409

## 6. Hard risk alerts

- none

## 6b. Conflict resolution (EV evidence)

- Loaded: **True** | tickers: **98** | policy: **WATCH** | cash hint: **$94.58**

### Top conflicts

- **AAPL** | winning_scenario=SELL_PAPER | final_authority=EV_OPTIMIZER
- **ABBV** | winning_scenario=SELL_PAPER | final_authority=EV_OPTIMIZER
- **ADBE** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **ADI** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **ADSK** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **AFL** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **AIG** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **AIR.PA** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION

### BUY blocked despite idle cash (positive BUY EV)

- none

### STRONG BUY → SKIP cases

- none

## 6c. Decision state (anti-churn)

- Switch authorized (PDE): **52**
- Switch blocked (PDE): **0**
- Conflict switch authorized: **50**
- Conflict switch blocked: **0**
- Cooldown active tickers: **0**
- High churn risk tickers: **74**

### Proposed action changes

- **QQQ** BUY_PAPER→PROTECT_PAPER authorized=yes reason=non_trade_or_allowed EV=-12.7478/0.15
- **SPY** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-0.4003/0.15
- **MRK** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.5353/0.15
- **PG** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.127/0.15
- **DIA** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.7513/0.15
- **ALV.DE** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.014/0.15
- **SAP.DE** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.0234/0.15
- **AAPL** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.4908/0.15

## 7. Portfolio rebuild view

- GII portfolio strategy: **HOLD_AND_MONITOR_SHADOW**
- Would BUY: `['PM', 'LLY', 'ADBE', 'HPQ', 'ICE', 'MCO', 'NOW', 'QRVO', 'SNPS', 'SPGI', 'STT', 'SWKS', 'WFC', 'HSBA.L', 'BP.L', 'CRWD', 'DELL', 'ALL', 'BAC', 'CME', 'COF', 'INTU', 'MA', 'MET', 'MSFT', 'NVDA', 'PLTR', 'SCHW', 'TRV', 'V', 'WDAY', 'ADSK', 'AIG', 'AMD', 'ANET', 'BLK', 'CDNS', 'FTNT', 'QCOM']`
- Would SELL: `[]`
- Would ROTATE: `[]`
- Would REDUCE: `[]`
- Note: Synthesis only — reflects existing PDE/GII outputs, not new decisions.

## 8. Strongest rules

- **KNOW-BUY_PAPER** | state=ACTIVE | net_pnl_impact=1521.1979 | win_rate=0.4661
- **TAE_SHADOW_SIZING_COMPARISON_V1** | state=ACTIVE | net_pnl_impact=1499.7691 | win_rate=0.4756
- **LTB-LIFE-PG-02** | state=TRUSTED | net_pnl_impact=1178.562 | win_rate=1.0
- **KNOW-PROTECT_PAPER** | state=ACTIVE | net_pnl_impact=927.1093 | win_rate=0.493
- **LTB-DPE-PHIL-001** | state=TESTING | net_pnl_impact=529.8621 | win_rate=0.4157
- **LTB-STALE-001** | state=TESTING | net_pnl_impact=529.8621 | win_rate=0.4157
- **DO_NOT_PROMOTE_TO_LIVE** | state=TESTING | net_pnl_impact=484.9205 | win_rate=0.4167
- **KNOW-HOLD_PAPER** | state=TESTING | net_pnl_impact=484.9205 | win_rate=0.4167

## 9. Weakest / disabled rules

- **LTB-LIFE-LLY-04** | state=DISABLED | net_pnl_impact=-325.248 | reason=win_rate=0.0% net_pnl=$-325.25 n=12
- **LTB-LIFE-PM-05** | state=DISABLED | net_pnl_impact=-2163.6428 | reason=win_rate=0.0% net_pnl=$-2163.64 n=22
- **SCORE_DECAY_SHADOW** | state=WATCHLIST | net_pnl_impact=-1.7563 | reason=win_rate=16.7% net_pnl=$-1.76
- **LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990** | state=TESTING | net_pnl_impact=-1078.0166 | reason=mixed evidence win_rate=36.6% net_pnl=$-1078.02
- **KNOW-SELL_PAPER** | state=TESTING | net_pnl_impact=-174.3332 | reason=mixed evidence win_rate=38.1% net_pnl=$-174.33
- **LTB-LIFE-LLY-05** | state=TESTING | net_pnl_impact=-27.104 | reason=insufficient evidence (1<5)
- **LTB-PROT-PPG-HSBA.L** | state=TESTING | net_pnl_impact=0.0 | reason=insufficient evidence (3<5)
- **LTB-PROT-PPG-MC.PA** | state=TESTING | net_pnl_impact=0.0 | reason=insufficient evidence (3<5)

## 10. DPE philosophy view

- Preferred philosophy: **COMPETITIVE**
- Adaptive confidence: **72.1**
- Competitive / Collaborative: **58.8% / 41.2%**
- Context: **HIGH RISK + HIGH VOLATILITY**
- Evaluator winner: **N/A**
- Policy state: **WATCH** (REDUCE_NEW_BUY_AGGRESSION_SHADOW)
- Recommendation: Continue PAPER experiment prioritizing COMPETITIVE philosophy (59% weight). Monitor collaborative arm at 41%. No live promotion.

## 11. Canonical vs PAPER result

- Canonical value: **$30,382.07**
- PAPER value: **$30,705.22**
- Delta: **$323.15**
- PAPER reconciliation: **PASS**
- Explanation: PAPER portfolio diverges by $323.15 total value (+2 positions, $-135.14 cash delta, $102.10 realized delta, $262.20 unrealized delta) after isolated PAPER execution and mark-to-market.

## 12. Capital / cash status

- PAPER cash: **$94.58**
- PAPER total value: **$30,705.22**
- PAPER realized / unrealized PnL: **$102.10** / **$262.20**
- Open PAPER positions: **14**
- PPG verdict: **PORTFOLIO_WATCH**
- APPE policy: **WATCH**

## 13. What changed since last cycle

- PAPER portfolio value: 30721.5303 → 30705.221
- New action plan entries: [('BP.L', 'BUY_PAPER')]
- Removed action plan entries: [('BP.L', 'HOLD_PAPER')]

## 14. Final PAPER action plan

Synthesized from existing PDE decisions — council does not override hard rules.

- **QQQ** → `PROTECT_PAPER` (conf=0.652, hard_override=False) — weak lifecycle=WEAKENING; GII strategy=PROTECT_PROFIT_SHADOW; horizon BUY gate: short/medium not aligned — 7D=NEGATIVE(-
- **PM** → `BUY_PAPER` (conf=0.946, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; signal=STRONG BUY age=0.0h (held — scale-in eligible); top_growth_candidate growt
- **LLY** → `BUY_PAPER` (conf=0.727, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; top_growth_candidate growth_score=75.2 age=0.0h (held — scale-in eligible); live 
- **ADBE** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **HPQ** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **ICE** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **MCO** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **NOW** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **QRVO** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **SNPS** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **SPGI** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **STT** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **SWKS** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **WFC** → `BUY_PAPER` (conf=0.717, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_
- **HSBA.L** → `BUY_PAPER` (conf=0.714, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon: short volatility elevated (drawdo
- **BP.L** → `BUY_PAPER` (conf=0.66, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held — scale-in eligible); live promotion lock noted (DO_NOT_PRO
- **CRWD** → `BUY_PAPER` (conf=0.545, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **DELL** → `BUY_PAPER` (conf=0.545, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **ALL** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **BAC** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **CME** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **COF** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **INTU** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **MA** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **MET** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **MSFT** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **NVDA** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **PLTR** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **SCHW** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **TRV** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **V** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **WDAY** → `BUY_PAPER` (conf=0.543, hard_override=False) — signal=STRONG BUY; limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — P
- **ADSK** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **AIG** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **AMD** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **ANET** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **BLK** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **CDNS** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **FTNT** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **QCOM** → `BUY_PAPER` (conf=0.253, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **SPY** → `HOLD_PAPER` (conf=0.939, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; top_growth_candidate growth_score=86.5 age=0.0h (held — scale-in eligible); horiz
- **MRK** → `HOLD_PAPER` (conf=0.817, hard_override=False) — healthy winner lifecycle=SURVIVED; top_growth_candidate growth_score=92.8 age=0.0h (held — scale-in eligible); live prom
- **PG** → `HOLD_PAPER` (conf=0.817, hard_override=False) — healthy winner lifecycle=SURVIVED; signal=STRONG BUY age=0.0h (held — scale-in eligible); top_growth_candidate growth_sc
- **DIA** → `HOLD_PAPER` (conf=0.678, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; l
- **ALV.DE** → `HOLD_PAPER` (conf=0.662, hard_override=False) — profit trailing: PROFIT_TRAILING_HOLD; monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY score=100.0 age=0.0h 
- **SAP.DE** → `HOLD_PAPER` (conf=0.597, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); live promot
- **AAPL** → `HOLD_PAPER` (conf=0.499, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; l
- **ULVR.L** → `HOLD_PAPER` (conf=0.49, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY age=0.0h (held — scale-in eligible); live promotion lock not
- **ABBV** → `HOLD_PAPER` (conf=0.409, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY age=0.0h (held — scale-in eligible); live promotion lock not
- **SHEL.L** → `HOLD_PAPER` (conf=0.409, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; l

## Operator command

```bash
python3 tae.py investment-council
```
