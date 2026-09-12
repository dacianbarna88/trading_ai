# TAE Investment Council Report

**Generated:** 2026-09-12T15:23:20+00:00
**Mode:** PAPER_ONLY — SYNTHESIS ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Governance verdict:** **READY_FOR_PAPER_DAY**

## 1. Executive recommendation

PAPER cycle READY_FOR_PAPER_DAY. PDE SELL: ANET, HSBA.L, BP.L, AMD. PDE PROTECT: QQQ. PDE BUY: CRWD, JPM, ALV.DE, NVDA, ADI. Policy WATCH / PPG PORTFOLIO_WATCH. DPE philosophy COMPETITIVE. live_promotion_allowed=false.

## 2. Today's top BUY candidates

- **CRWD** | confidence=0.773 | pde_buy=True | gii_top_growth=False
- **JPM** | confidence=0.773 | pde_buy=True | gii_top_growth=False
- **ALV.DE** | confidence=0.472 | pde_buy=True | gii_top_growth=False
- **NVDA** | confidence=0.465 | pde_buy=True | gii_top_growth=False
- **ADI** | confidence=0.355 | pde_buy=True | gii_top_growth=False
- **BAC** | confidence=0.355 | pde_buy=True | gii_top_growth=False
- **IBM** | confidence=0.355 | pde_buy=True | gii_top_growth=False
- **MET** | confidence=0.355 | pde_buy=True | gii_top_growth=False
- **ORCL** | confidence=0.355 | pde_buy=True | gii_top_growth=False
- **TER** | confidence=0.355 | pde_buy=True | gii_top_growth=False

## 3. Today's top SELL candidates

- **ANET** | confidence=0.95 | hard_risk_override=False
- **HSBA.L** | confidence=0.95 | hard_risk_override=False
- **BP.L** | confidence=0.794 | hard_risk_override=False
- **AMD** | confidence=0.656 | hard_risk_override=False

## 4. Today's top PROTECT candidates

- **QQQ** | confidence=0.568 | expected_profit_delta=1.97

## 5. Today's HOLD candidates

- **DELL** | confidence=0.95
- **HPQ** | confidence=0.95
- **PG** | confidence=0.95
- **PM** | confidence=0.95
- **LLY** | confidence=0.918
- **CME** | confidence=0.908
- **ICE** | confidence=0.908
- **MSFT** | confidence=0.908
- **NOW** | confidence=0.908
- **SNOW** | confidence=0.908

## 6. Hard risk alerts

- none

## 6b. Conflict resolution (EV evidence)

- Loaded: **True** | tickers: **98** | policy: **WATCH** | cash hint: **$196.27**

### Top conflicts

- **AAPL** | winning_scenario=HOLD_PAPER | final_authority=POLICY_CAUTION
- **ABBV** | winning_scenario=SELL_PAPER | final_authority=EV_OPTIMIZER
- **ADBE** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **ADI** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **ADSK** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **AFL** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **AIG** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **AIR.PA** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER

### BUY blocked despite idle cash (positive BUY EV)

- none

### STRONG BUY → SKIP cases

- none

## 6c. Decision state (anti-churn)

- Switch authorized (PDE): **68**
- Switch blocked (PDE): **6**
- Conflict switch authorized: **62**
- Conflict switch blocked: **0**
- Cooldown active tickers: **0**
- High churn risk tickers: **87**

### Proposed action changes

- **ANET** BUY_PAPER→SELL_PAPER authorized=yes reason=ev_margin_met EV=8.5367/0.15
- **BP.L** BUY_PAPER→SELL_PAPER authorized=yes reason=ev_margin_met EV=0.7687/0.15
- **AMD** BUY_PAPER→SELL_PAPER authorized=yes reason=ev_margin_met EV=0.3518/0.15
- **QQQ** BUY_PAPER→PROTECT_PAPER authorized=yes reason=non_trade_or_allowed EV=-5.8194/0.15
- **DELL** BUY_PAPER→HOLD_PAPER authorized=yes reason=ev_margin_met EV=7.8301/0.15
- **HPQ** BUY_PAPER→HOLD_PAPER authorized=yes reason=ev_margin_met EV=6.5073/0.15
- **PG** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-2.3538/0.15
- **PM** BUY_PAPER→HOLD_PAPER authorized=yes reason=non_trade_or_allowed EV=-1.7294/0.15

## 7. Portfolio rebuild view

- GII portfolio strategy: **HOLD_AND_MONITOR_SHADOW**
- Would BUY: `['CRWD', 'JPM', 'ALV.DE', 'NVDA', 'ADI', 'BAC', 'IBM', 'MET', 'ORCL', 'TER', 'AIG', 'AIR.PA', 'ALL', 'CB', 'FTNT', 'GS', 'INTU', 'SAP.DE']`
- Would SELL: `['ANET', 'HSBA.L', 'BP.L', 'AMD']`
- Would ROTATE: `[]`
- Would REDUCE: `[]`
- Note: Synthesis only — reflects existing PDE/GII outputs, not new decisions.

## 8. Strongest rules

- **KNOW-BUY_PAPER** | state=ACTIVE | net_pnl_impact=1328.0469 | win_rate=0.4539
- **TAE_SHADOW_SIZING_COMPARISON_V1** | state=TESTING | net_pnl_impact=673.9334 | win_rate=0.4337
- **DO_NOT_PROMOTE_TO_LIVE** | state=ACTIVE | net_pnl_impact=657.1486 | win_rate=0.4777
- **KNOW-HOLD_PAPER** | state=ACTIVE | net_pnl_impact=657.1486 | win_rate=0.4777
- **LTB-PATTERN-001** | state=ACTIVE | net_pnl_impact=657.1486 | win_rate=0.4777
- **LTB-DPE-PHIL-001** | state=ACTIVE | net_pnl_impact=646.5567 | win_rate=0.4701
- **LTB-STALE-001** | state=ACTIVE | net_pnl_impact=646.5567 | win_rate=0.4701
- **KNOW-SELL_PAPER** | state=ACTIVE | net_pnl_impact=479.1027 | win_rate=0.4599

## 9. Weakest / disabled rules

- **LTB-CONF-MISSED_PROFIT_PROTECTION** | state=WATCHLIST | net_pnl_impact=-10.5919 | reason=win_rate=20.0% net_pnl=$-10.59
- **LTB-CONF-SCORE_PERSISTENCE_AFTER_** | state=WATCHLIST | net_pnl_impact=-10.5919 | reason=win_rate=20.0% net_pnl=$-10.59
- **LTB-CONF-STOP_REENTRY_CHURN** | state=WATCHLIST | net_pnl_impact=-10.5919 | reason=win_rate=20.0% net_pnl=$-10.59
- **LTB-LIFE-LLY-04** | state=DEPRECATED | net_pnl_impact=-62.9824 | reason=win_rate=0.0% net_pnl=$-62.98
- **LTB-LIFE-MRK-01** | state=DISABLED | net_pnl_impact=-1020.9888 | reason=win_rate=0.0% net_pnl=$-1020.99 n=12
- **LTB-REPLAY-04** | state=WATCHLIST | net_pnl_impact=-10.5919 | reason=win_rate=20.0% net_pnl=$-10.59
- **MISSED_PROFIT_PROTECTION** | state=WATCHLIST | net_pnl_impact=-10.5919 | reason=win_rate=20.0% net_pnl=$-10.59
- **SCORE_DECAY_SHADOW** | state=WATCHLIST | net_pnl_impact=-1.7084 | reason=win_rate=0.0% net_pnl=$-1.71

## 10. DPE philosophy view

- Preferred philosophy: **COMPETITIVE**
- Adaptive confidence: **66.9**
- Competitive / Collaborative: **52.9% / 47.1%**
- Context: **HIGH RISK + HIGH VOLATILITY**
- Evaluator winner: **N/A**
- Policy state: **WATCH** (REDUCE_NEW_BUY_AGGRESSION_SHADOW)
- Recommendation: Continue PAPER experiment prioritizing COMPETITIVE philosophy (53% weight). Monitor collaborative arm at 47%. No live promotion.

## 11. Canonical vs PAPER result

- Canonical value: **$29,871.02**
- PAPER value: **$30,040.47**
- Delta: **$169.45**
- PAPER reconciliation: **PASS**
- Explanation: PAPER portfolio diverges by $169.45 total value (+16 positions, $-3,474.77 cash delta, $-403.34 realized delta, $102.89 unrealized delta) after isolated PAPER execution and mark-to-market.

## 12. Capital / cash status

- PAPER cash: **$196.27**
- PAPER total value: **$30,040.47**
- PAPER realized / unrealized PnL: **$-403.34** / **$102.89**
- Open PAPER positions: **27**
- PPG verdict: **PORTFOLIO_WATCH**
- APPE policy: **WATCH**

## 13. What changed since last cycle

- Executive recommendation: 'PAPER cycle READY_FOR_PAPER_DAY. PDE SELL: ANET, HSBA.L, BP.L, AMD. PDE PROTECT: QQQ. PDE BUY: CRWD, JPM, NVDA, ALV.DE, ADI. Policy WATCH / PPG PORTFOLIO_WATCH. DPE philosophy COMPETITIVE. live_promotion_allowed=false.' → 'PAPER cycle READY_FOR_PAPER_DAY. PDE SELL: ANET, HSBA.L, BP.L, AMD. PDE PROTECT: QQQ. PDE BUY: CRWD, JPM, ALV.DE, NVDA, ADI. Policy WATCH / PPG PORTFOLIO_WATCH. DPE philosophy COMPETITIVE. live_promotion_allowed=false.'

## 14. Final PAPER action plan

Synthesized from existing PDE decisions — council does not override hard rules.

- **ANET** → `SELL_PAPER` (conf=0.95, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); live promotion lock noted
- **HSBA.L** → `SELL_PAPER` (conf=0.95, hard_override=False) — PROFIT_TRAILING_EXIT_DRAWDOWN_2_PERCENT: mark=1552.599976 peak=1669.711606468 drawdown=-0.0701388372 cycle=PPC-HSBA.L-20
- **BP.L** → `SELL_PAPER` (conf=0.794, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); live promotion lock noted
- **AMD** → `SELL_PAPER` (conf=0.656, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held — scale-in eligible); live promotion lock noted (DO_NOT_PRO
- **QQQ** → `PROTECT_PAPER` (conf=0.568, hard_override=False) — weak lifecycle=WEAKENING; GII strategy=PROTECT_PROFIT_SHADOW; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in el
- **CRWD** → `BUY_PAPER` (conf=0.773, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); live promotion lock noted
- **JPM** → `BUY_PAPER` (conf=0.773, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); live promotion lock noted
- **ALV.DE** → `BUY_PAPER` (conf=0.472, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); live promot
- **NVDA** → `BUY_PAPER` (conf=0.465, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); horizon BUY
- **ADI** → `BUY_PAPER` (conf=0.355, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon BUY gate: short/medium not aligned
- **BAC** → `BUY_PAPER` (conf=0.355, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon BUY gate: short/medium not aligned
- **IBM** → `BUY_PAPER` (conf=0.355, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon BUY gate: short/medium not aligned
- **MET** → `BUY_PAPER` (conf=0.355, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon BUY gate: short/medium not aligned
- **ORCL** → `BUY_PAPER` (conf=0.355, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon BUY gate: short/medium not aligned
- **TER** → `BUY_PAPER` (conf=0.355, hard_override=False) — signal=STRONG BUY score=100.0; limited capital hint from accounting snapshot; horizon BUY gate: short/medium not aligned
- **AIG** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **AIR.PA** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **ALL** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **CB** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **FTNT** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **GS** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **INTU** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **SAP.DE** → `BUY_PAPER` (conf=0.25, hard_override=False) — limited capital hint from accounting snapshot; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchang
- **DELL** → `HOLD_PAPER` (conf=0.95, hard_override=False) — profit trailing: PROFIT_TRAILING_HOLD; low capital_efficiency=0.0; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — 
- **HPQ** → `HOLD_PAPER` (conf=0.95, hard_override=False) — profit trailing: PROFIT_TRAILING_HOLD; low capital_efficiency=0.0; horizon BUY gate: short/medium not aligned — 7D=NEUTR
- **PG** → `HOLD_PAPER` (conf=0.95, hard_override=False) — healthy winner lifecycle=SURVIVED; top_growth_candidate growth_score=92.4 age=0.0h (held — scale-in eligible); horizon: 
- **PM** → `HOLD_PAPER` (conf=0.95, hard_override=False) — profit trailing: PROFIT_TRAILING_HOLD; healthy winner lifecycle=EARLY_WINNER; signal=STRONG BUY score=100.0 age=0.0h (he
- **LLY** → `HOLD_PAPER` (conf=0.918, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; top_growth_candidate growth_score=75.2 age=0.0h (held — scale-in eligible); horiz
- **CME** → `HOLD_PAPER` (conf=0.908, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); horizon BUY gate: short/m
- **ICE** → `HOLD_PAPER` (conf=0.908, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held — scale-in eligible); horizon BUY gate: short/medium not al
- **MSFT** → `HOLD_PAPER` (conf=0.908, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); horizon BUY gate: short/m
- **NOW** → `HOLD_PAPER` (conf=0.908, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); horizon BUY gate: short/m
- **SNOW** → `HOLD_PAPER` (conf=0.908, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held — scale-in eligible); horizon BUY gate: short/medium not al
- **TEAM** → `HOLD_PAPER` (conf=0.908, hard_override=False) — low capital_efficiency=0.0; signal=STRONG BUY score=100.0 age=0.0h (held — scale-in eligible); horizon BUY gate: short/m
- **SPY** → `HOLD_PAPER` (conf=0.845, hard_override=False) — healthy winner lifecycle=EARLY_WINNER; signal=STRONG BUY age=0.0h (held — scale-in eligible); top_growth_candidate growt
- **MRK** → `HOLD_PAPER` (conf=0.792, hard_override=False) — healthy winner lifecycle=SURVIVED; top_growth_candidate growth_score=92.8 age=0.0h (held — scale-in eligible); horizon: 
- **AAPL** → `HOLD_PAPER` (conf=0.664, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; l
- **DIA** → `HOLD_PAPER` (conf=0.653, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; horizon BUY gate: short/medium not aligned — 7D=NEUTRAL(0.0%); 1M=NEGATIVE(-2.
- **ULVR.L** → `HOLD_PAPER` (conf=0.653, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; l
- **ABBV** → `HOLD_PAPER` (conf=0.384, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY age=0.0h (held — scale-in eligible); live promotion lock not
- **SHEL.L** → `HOLD_PAPER` (conf=0.384, hard_override=False) — monitor strategy=HOLD_AND_MONITOR_SHADOW; live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; l

## Operator command

```bash
python3 tae.py investment-council
```
