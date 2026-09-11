# TAE Investment Council Report

**Generated:** 2026-09-11T13:14:47+00:00
**Mode:** PAPER_ONLY — SYNTHESIS ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Governance verdict:** **BLOCKED_WITH_REASONS**

## 1. Executive recommendation

PAPER BLOCKED by structural governance (forbidden content diff: core/market_data_layer.py). Do not execute PAPER actions until blockers clear. Observe only.

## 2. Today's top BUY candidates

- **MRK** | confidence=0.83 | growth_score=92.8 | pde_buy=True | gii_top_growth=True
- **CRWD** | confidence=0.67 | pde_buy=True | gii_top_growth=False
- **AAPL** | confidence=0.54 | pde_buy=True | gii_top_growth=False
- **ABBV** | confidence=0.54 | pde_buy=True | gii_top_growth=False
- **NVDA** | confidence=0.426 | pde_buy=True | gii_top_growth=False
- **ALV.DE** | confidence=0.367 | pde_buy=True | gii_top_growth=False
- **BAC** | confidence=0.34 | pde_buy=True | gii_top_growth=False
- **ORCL** | confidence=0.34 | pde_buy=True | gii_top_growth=False
- **V** | confidence=0.34 | pde_buy=True | gii_top_growth=False
- **FTNT** | confidence=0.25 | pde_buy=True | gii_top_growth=False

## 3. Today's top SELL candidates

- **HSBA.L** | confidence=0.95 | hard_risk_override=False
- **BP.L** | confidence=0.807 | hard_risk_override=False
- **AMD** | confidence=0.67 | hard_risk_override=False
- **ANET** | confidence=0.67 | hard_risk_override=False
- **CME** | confidence=0.67 | hard_risk_override=False
- **DELL** | confidence=0.67 | hard_risk_override=False
- **HPQ** | confidence=0.67 | hard_risk_override=False
- **ICE** | confidence=0.67 | hard_risk_override=False
- **JPM** | confidence=0.67 | hard_risk_override=False
- **MSFT** | confidence=0.67 | hard_risk_override=False

## 4. Today's top PROTECT candidates

- **QQQ** | confidence=0.484 | expected_profit_delta=0.94

## 5. Today's HOLD candidates

- **PG** | confidence=0.95
- **PM** | confidence=0.95
- **LLY** | confidence=0.918
- **SPY** | confidence=0.845
- **DIA** | confidence=0.653
- **ULVR.L** | confidence=0.653
- **SHEL.L** | confidence=0.573

## 6. Hard risk alerts

- none

## 6b. Conflict resolution (EV evidence)

- Loaded: **True** | tickers: **98** | policy: **WATCH** | cash hint: **$129.33**

### Top conflicts

- **AAPL** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **ABBV** | winning_scenario=BUY_PAPER | final_authority=EV_OPTIMIZER
- **ADBE** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **ADI** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **ADSK** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **AFL** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **AIG** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION
- **AIR.PA** | winning_scenario=SKIP_PAPER | final_authority=POLICY_CAUTION

### BUY blocked despite idle cash (positive BUY EV)

- none

### STRONG BUY → SKIP cases

- none

## 6c. Decision state (anti-churn)

- Switch authorized (PDE): **74**
- Switch blocked (PDE): **0**
- Conflict switch authorized: **64**
- Conflict switch blocked: **0**
- Cooldown active tickers: **0**
- High churn risk tickers: **87**

### Proposed action changes

- **BP.L** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=0.936/0.15
- **AMD** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-1.0295/0.15
- **ANET** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-11.7337/0.15
- **CME** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-1.0298/0.15
- **DELL** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-1.0295/0.15
- **HPQ** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-1.0331/0.15
- **ICE** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-1.0332/0.15
- **JPM** BUY_PAPER→SELL_PAPER authorized=yes reason=loss_breach_or_risk_deterioration EV=-0.5792/0.15

## 7. Portfolio rebuild view

- GII portfolio strategy: **HOLD_AND_MONITOR_SHADOW**
- Would BUY: `['MRK', 'CRWD', 'AAPL', 'ABBV', 'NVDA', 'ALV.DE', 'BAC', 'ORCL', 'V', 'FTNT', 'GS', 'INTC', 'MA', 'MET', 'PLTR', 'SCHW', 'TER', 'WDAY']`
- Would SELL: `['HSBA.L', 'BP.L', 'AMD', 'ANET', 'CME', 'DELL', 'HPQ', 'ICE', 'JPM', 'MSFT', 'NOW', 'SNOW', 'TEAM', 'TRV']`
- Would ROTATE: `[]`
- Would REDUCE: `[]`
- Note: Synthesis only — reflects existing PDE/GII outputs, not new decisions.

## 8. Strongest rules

- **LTB-LIFE-PM-05** | state=TRUSTED | net_pnl_impact=225.1976 | win_rate=1.0
- **LTB-OPP-HSBA.L-01** | state=ACTIVE | net_pnl_impact=22.1205 | win_rate=1.0
- **LTB-PROT-ALV.DE** | state=TESTING | net_pnl_impact=17.8996 | win_rate=1.0
- **LTB-PROT-PPG-HSBA.L** | state=TESTING | net_pnl_impact=17.6964 | win_rate=1.0
- **LTB-CONF-MISSED_PROFIT_PROTECTION** | state=TESTING | net_pnl_impact=1.5675 | win_rate=0.2
- **LTB-CONF-SCORE_PERSISTENCE_AFTER_** | state=TESTING | net_pnl_impact=1.5675 | win_rate=0.2
- **LTB-CONF-STOP_REENTRY_CHURN** | state=TESTING | net_pnl_impact=1.5675 | win_rate=0.2
- **LTB-REPLAY-04** | state=TESTING | net_pnl_impact=1.5675 | win_rate=0.2

## 9. Weakest / disabled rules

- **DO_NOT_PROMOTE_TO_LIVE** | state=DEPRECATED | net_pnl_impact=-1957.4006 | reason=win_rate=22.1% net_pnl=$-1957.40
- **KNOW-BUY_PAPER** | state=DEPRECATED | net_pnl_impact=-509.4811 | reason=win_rate=17.8% net_pnl=$-509.48
- **KNOW-HOLD_PAPER** | state=DEPRECATED | net_pnl_impact=-1957.4006 | reason=win_rate=22.1% net_pnl=$-1957.40
- **KNOW-PROTECT_PAPER** | state=WATCHLIST | net_pnl_impact=-289.4529 | reason=win_rate=32.4% net_pnl=$-289.45
- **KNOW-SELL_PAPER** | state=DEPRECATED | net_pnl_impact=-1670.7947 | reason=win_rate=19.6% net_pnl=$-1670.79
- **LTB-DPE-PHIL-001** | state=DEPRECATED | net_pnl_impact=-1955.8331 | reason=win_rate=22.1% net_pnl=$-1955.83
- **LTB-LIFE-LLY-04** | state=WATCHLIST | net_pnl_impact=-33.8377 | reason=win_rate=0.0% net_pnl=$-33.84
- **LTB-LIFE-MRK-01** | state=DISABLED | net_pnl_impact=-772.7364 | reason=win_rate=0.0% net_pnl=$-772.74 n=12

## 10. DPE philosophy view

- Preferred philosophy: **COMPETITIVE**
- Adaptive confidence: **67.2**
- Competitive / Collaborative: **52.9% / 47.1%**
- Context: **HIGH RISK + HIGH VOLATILITY**
- Evaluator winner: **N/A**
- Policy state: **WATCH** (REDUCE_NEW_BUY_AGGRESSION_SHADOW)
- Recommendation: Continue PAPER experiment prioritizing COMPETITIVE philosophy (53% weight). Monitor collaborative arm at 47%. No live promotion.

## 11. Canonical vs PAPER result

- Canonical value: **$29,864.54**
- PAPER value: **$29,754.83**
- Delta: **$-109.71**
- PAPER reconciliation: **PASS**
- Explanation: PAPER portfolio diverges by $-109.71 total value (+17 positions, $-4,374.97 cash delta, $-427.00 realized delta, $-159.09 unrealized delta) after isolated PAPER execution and mark-to-market.

## 12. Capital / cash status

- PAPER cash: **$129.33**
- PAPER total value: **$29,754.83**
- PAPER realized / unrealized PnL: **$-427.00** / **$-159.09**
- Open PAPER positions: **28**
- PPG verdict: **PORTFOLIO_WATCH**
- APPE policy: **WATCH**

## 13. What changed since last cycle

- PAPER portfolio value: 29750.0091 → 29754.8283

## 14. Final PAPER action plan

Synthesized from existing PDE decisions — council does not override hard rules.

- **_PORTFOLIO** → `NO_PAPER_ACTION` (conf=None, hard_override=None) — 

## Operator command

```bash
python3 tae.py investment-council
```
