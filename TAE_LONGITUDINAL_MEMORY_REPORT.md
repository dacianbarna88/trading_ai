# TAE Longitudinal Memory Report

**Generated:** 2026-09-12T15:02:01+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

- Total memory records: **9485**
- New this run: **18**
- Checkpoints updated: **33**
- Outcome sources present: **18/19**

## Canonical storage

- `runtime_outputs/longitudinal_memory/decisions.jsonl`
- `runtime_outputs/longitudinal_memory/memory_index.json`
- `runtime_outputs/longitudinal_memory/knowledge.json`

## Action performance

| action | count | success % |
| --- | --- | --- |
| SELL_PAPER | 16 | 87.5 |
| HOLD_PAPER | 76 | 92.1 |
| SKIP_PAPER | 201 | 1.5 |
| PROTECT_PAPER | 16 | 18.8 |
| BUY_PAPER | 9176 | 40.6 |

## Knowledge rules

- In PAPER validation, HOLD_PAPER showed 92.1% PROMISING/CONTINUE rate over 76 decisions.
- In PAPER validation, SELL_PAPER showed 87.5% PROMISING/CONTINUE rate over 16 decisions.
- In PAPER validation, BUY_PAPER showed 40.6% PROMISING/CONTINUE rate over 9176 decisions.
- In PAPER validation, PROTECT_PAPER showed 18.8% PROMISING/CONTINUE rate over 16 decisions.
- In PAPER validation, SKIP_PAPER showed 1.5% PROMISING/CONTINUE rate over 201 decisions.
- PROTECT_PAPER decisions averaged expected risk delta -0.108 across 16 cases.
- In accumulated PAPER memory, COLLABORATIVE philosophy shows higher validation success (COLLABORATIVE 54.0%, COMPETITIVE 40.1%).
- Horizon alignment present in 9481 decisions; conflicts in 4 decisions.
