# TAE DPE-5 — Result Evaluator Sprint Report

**Date:** 2026-09-03T13:15:15+00:00
**Mode:** READ_ONLY · PAPER_ONLY · SHADOW_ONLY · NO_BROKER
**Status:** PASS

## Files created

| File | Role |
| --- | --- |
| `tae_dpe_result_evaluator.py` | Evaluator engine |
| `runtime_outputs/dpe/result_evaluator/evaluation.json` | Machine-readable comparison |
| `runtime_outputs/dpe/result_evaluator/evaluation.md` | Human report |
| `tae_cli/commands/dpe_evaluator.py` | CLI command |

## Metrics compared

Portfolio value, cash, open positions, realized/unrealized/total PnL, win rate, average winner/loser, profit factor, max drawdown, profit capture rate, opportunity cost, capital efficiency, trade/trim/protect/hold counts.

## Winner per metric

- portfolio_value: **COLLABORATIVE**
- cash: **COLLABORATIVE**
- open_positions_value: **COMPETITIVE**
- realized_pnl: **COLLABORATIVE**
- unrealized_pnl: **COMPETITIVE**
- total_pnl: **COMPETITIVE**
- win_rate: **COLLABORATIVE**
- average_winner: **COMPETITIVE**
- average_loser: **COMPETITIVE**
- profit_factor: **COMPETITIVE**
- max_drawdown: **COLLABORATIVE**
- profit_capture_rate: **COMPETITIVE**
- opportunity_cost: **TIE**
- capital_efficiency: **COMPETITIVE**
- trade_count: **TIE**
- trim_count: **COLLABORATIVE**
- protect_count: **COLLABORATIVE**
- hold_count: **COMPETITIVE**
- open_positions: **COMPETITIVE**

## Overall winner

- **COMPETITIVE**
- Confidence: **58.9%**
- Reason: Higher unrealized growth (1413.2962) with competitive hold bias; realized PnL -111.6023 vs 85.0105.

## Architecture confirmation

- Evaluator reads only `paper_competitive/` and `paper_collaborative/`
- No executor code modified
- No live SSOT touched

## Validation result

- Competitive evaluated: **yes**
- Collaborative evaluated: **yes**
- Overall recommendation generated: **yes**

## Safety confirmation

| Rule | Status |
| --- | --- |
| READ_ONLY | ✅ |
| PAPER_ONLY | ✅ |
| SHADOW_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_BOT_CHANGE | ✅ |
| NO_PORTFOLIO_CSV_CHANGE | ✅ |
| NO_COMMIT | ✅ |

## Recommended next sprint

**TAE DPE-6 — Learning Engine**
