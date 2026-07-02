# TAE Stop Re-entry Cooldown Audit (X.COOLDOWN-1)

**Generated:** 2026-07-02T14:24:33
**Mode:** SHADOW_ONLY | **Verdict:** INSUFFICIENT_SAMPLE

## Summary
- Total STOP events: **15**
- Total reentries after STOP: **8**
- Immediate (≤5m): 5
- Fast (≤30m): 5
- Same session: 6
- Second STOP after reentry: 2
- Total reentry PnL: **114.94 USD**
- Best cooldown: **cooldown_15m**

## Cooldown simulations

| Policy | Blocked | Avoided loss | Missed gain | Net effect |
|--------|---------|--------------|-------------|------------|
| cooldown_15m | 5 | 100.46 | 76.48 | **23.98** |
| cooldown_30m | 5 | 100.46 | 76.48 | **23.98** |
| cooldown_60m | 5 | 100.46 | 76.48 | **23.98** |
| cooldown_until_next_session | 6 | 100.46 | 163.75 | **-63.29** |
| cooldown_until_new_signal_confirmation | 8 | 100.46 | 215.4 | **-114.94** |

## Score persistence after STOP
- Cases (score≥80 + STRONG BUY): **8**
- Average leg PnL: 14.37 USD
- Loss rate: 25%
- Second STOP rate: 25%

## Gates G1–G5
- Advisory readiness: **NOT_READY**
- Gates passed: False
- Failed: G1, G3, G4, G5

- **G1** (at least 10 stop-reentry cases): FAIL
- **G2** (cooldown net_effect > 0): PASS
- **G3** (second_stop_rate reduced by >= 30%): FAIL
- **G4** (missed_winner_cost <= avoided_loss * 0.5): FAIL
- **G5** (score_persistence_loss_rate > 0.5): FAIL

## Notable sequences

- **AAPL** — 21589.08m after STOP, score=80.0, outcome=REENTRY_SECOND_STOP, leg_pnl=40.3 (ACTUAL)
- **AAPL** — 8569.02m after STOP, score=100.0, outcome=REENTRY_OPEN_UNREALIZED, leg_pnl=11.35 (ESTIMATED)
- **SIE.DE** — 1.28m after STOP, score=80.0, outcome=REENTRY_WIN, leg_pnl=46.48 (ACTUAL)
- **MC.PA** — 103.12m after STOP, score=80.0, outcome=REENTRY_OPEN_UNREALIZED, leg_pnl=87.27 (ESTIMATED)
- **PM** — 1.3m after STOP, score=80.0, outcome=REENTRY_OPEN_UNREALIZED, leg_pnl=2.54 (ESTIMATED)
- **MU** — 1.33m after STOP, score=100.0, outcome=REENTRY_SECOND_STOP, leg_pnl=-75.71 (ACTUAL)
- **MU** — 1.32m after STOP, score=100.0, outcome=REENTRY_OPEN_UNREALIZED, leg_pnl=-24.75 (ESTIMATED)
- **LLY** — 1.32m after STOP, score=100.0, outcome=REENTRY_OPEN_UNREALIZED, leg_pnl=27.46 (ESTIMATED)

## Recommendations (SHADOW_ONLY)

- CONTINUE_OBSERVATION
- DO_NOT_PROMOTE_TO_LIVE
- TEST_15M_COOLDOWN_SHADOW

## Next step
Proceed to X.REPLAY-1 to integrate stop-reentry cost with exit protection findings.

*No live BUY/SELL. Shadow audit only.*
