# TAE 30-Day PAPER Validation Plan

**Created:** 2026-07-07T15:25:27+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_EXECUTION — NO_LIVE_PROMOTION

## Objective

Run disciplined daily PAPER validation for 30 calendar days before any live promotion review.

## Daily command

```bash
python3 tae.py full-paper-cycle
```

## Daily evidence to record

- Portfolio value, cash, open positions
- Realized / unrealized / total PnL
- Top BUY_PAPER, SELL_PAPER, PROTECT_PAPER, HOLD_PAPER, ROTATE_PAPER
- PROMISING / CONTINUE / REJECT / NEEDS_MORE_DATA counts
- DPE winner, adaptive philosophy, adaptive confidence
- Adaptive action weights (`runtime_outputs/adaptive_weights/paper_action_weights.json`)
- Capital efficiency, opportunity cost
- Profit protection / PPG / APPE state
- Horizon conflicts, stale sources, blocked jobs
- Infrastructure status and final verdict

## Weekly review

- `python3 tae.py outcome-memory`
- `python3 tae.py strategy-survival`
- `python3 tae.py long-term-learning`
- `python3 tae.py philosophy-performance`

## End-of-period gate

After 30 days, operator may review `PROMOTE_TO_LIVE_CANDIDATE` recommendations only.
Machine outputs remain `live_promotion_allowed=false` until manual approval outside TAE.
