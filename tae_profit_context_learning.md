# TAE Profit Context Learning v2

**Generated:** 2026-09-03T16:01:32
**Mode:** SHADOW_ONLY — NONE

> **SHADOW_ONLY — no live or advisory integration**

## Component weights

| component | weight | default |
| --- | --- | --- |
| market_context | 0.1182 | 0.15 |
| sector_context | 0.1182 | 0.15 |
| trend_context | 0.1182 | 0.15 |
| momentum_context | 0.1182 | 0.15 |
| volatility_context | 0.0791 | 0.1 |
| psp_context | 0.1182 | 0.15 |
| memory_context | 0.3 | 0.1 |
| committee_context | 0.03 | 0.05 |

## Source of weights
- Committee learning loaded: **True**
- Memory accuracy: **0.615**
- Validation accuracy: **0.634**
- PSP accuracy: **0.764**

## Normalization
- Weight sum: **1.0001**
- Min weight: **0.03**
- Max weight: **0.3**

## Constraints applied
- Weights normalized to sum 1.0
- No component below 0.03 or above 0.30
- Conservative adjustments only (+/- 0.01 to 0.02)

## Adjustment notes
- Initialized from PCE v2 default weights.
- Loaded prior context weights from tae_profit_context_learning.json.
- Applied conservative adjustments from tae_profit_committee_learning.json.
- Normalized to sum=1.0001 with min=0.03, max=0.3.
- SHADOW_ONLY — no live or advisory integration.
- Weight updates are conservative; true outcome learning deferred.
