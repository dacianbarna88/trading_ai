# TAE Long Term Learning Report

**Generated:** 2026-09-12T15:02:01+00:00

## Learning questions (evidence-based)

- In PAPER validation, HOLD_PAPER showed 92.1% PROMISING/CONTINUE rate over 76 decisions.
- In PAPER validation, SELL_PAPER showed 87.5% PROMISING/CONTINUE rate over 16 decisions.
- In PAPER validation, BUY_PAPER showed 40.6% PROMISING/CONTINUE rate over 9176 decisions.
- In PAPER validation, PROTECT_PAPER showed 18.8% PROMISING/CONTINUE rate over 16 decisions.
- In PAPER validation, SKIP_PAPER showed 1.5% PROMISING/CONTINUE rate over 201 decisions.
- PROTECT_PAPER decisions averaged expected risk delta -0.108 across 16 cases.
- In accumulated PAPER memory, COLLABORATIVE philosophy shows higher validation success (COLLABORATIVE 54.0%, COMPETITIVE 40.1%).
- Horizon alignment present in 9481 decisions; conflicts in 4 decisions.

## Adaptation hints (for existing PDE/LTP)

- Action biases: `{"SELL_PAPER": 0.375, "HOLD_PAPER": 0.421, "SKIP_PAPER": -0.485, "PROTECT_PAPER": -0.312, "BUY_PAPER": -0.094}`
- Philosophy biases: `{"COLLABORATIVE": 0.04, "COMPETITIVE": -0.099}`
