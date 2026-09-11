# TAE Longitudinal Memory Report

**Generated:** 2026-09-11T14:01:50+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

- Total memory records: **9249**
- New this run: **16**
- Checkpoints updated: **98**
- Outcome sources present: **18/19**

## Canonical storage

- `runtime_outputs/longitudinal_memory/decisions.jsonl`
- `runtime_outputs/longitudinal_memory/memory_index.json`
- `runtime_outputs/longitudinal_memory/knowledge.json`

## Action performance

| action | count | success % |
| --- | --- | --- |
| SELL_PAPER | 30 | 90.0 |
| HOLD_PAPER | 57 | 93.0 |
| SKIP_PAPER | 195 | 2.1 |
| PROTECT_PAPER | 16 | 18.8 |
| BUY_PAPER | 8951 | 41.3 |

## Knowledge rules

- In PAPER validation, HOLD_PAPER showed 93.0% PROMISING/CONTINUE rate over 57 decisions.
- In PAPER validation, SELL_PAPER showed 90.0% PROMISING/CONTINUE rate over 30 decisions.
- In PAPER validation, BUY_PAPER showed 41.3% PROMISING/CONTINUE rate over 8951 decisions.
- In PAPER validation, PROTECT_PAPER showed 18.8% PROMISING/CONTINUE rate over 16 decisions.
- In PAPER validation, SKIP_PAPER showed 2.1% PROMISING/CONTINUE rate over 195 decisions.
- PROTECT_PAPER decisions averaged expected risk delta -0.108 across 16 cases.
- In accumulated PAPER memory, COLLABORATIVE philosophy shows higher validation success (COLLABORATIVE 56.0%, COMPETITIVE 40.9%).
- Horizon alignment present in 9245 decisions; conflicts in 4 decisions.
