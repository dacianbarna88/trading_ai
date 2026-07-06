# TAE Profit Committee Learning v2

**Generated:** 2026-07-06T18:48:10
**Mode:** SHADOW_ONLY — NONE
**Final verdict:** PDC_V2_SHADOW_READY_FOR_OBSERVATION

> **NO BUY / NO SELL — SHADOW_ONLY adaptive learning**

## Committee member weights

| member | accuracy | weight | trend | votes | correct | incorrect | bias |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Rules | 53.8% | 0.8 | STABLE | 13 | 7 | 6 | NEUTRAL |
| PIB | 38.5% | 0.6 | STABLE | 13 | 5 | 8 | DISCOUNT |
| PSP | 53.8% | 0.8 | STABLE | 13 | 7 | 6 | NEUTRAL |
| Memory | 100.0% | 2.2 | STABLE | 13 | 13 | 0 | TRUST |
| Validation | 38.5% | 0.6 | IMPROVING | 13 | 5 | 8 | DISCOUNT |

## Member summary

### Rules
- accuracy: **53.8%**
- weight: **0.8**
- trend: **STABLE**
- votes: **13** (correct 7, incorrect 6)

### PIB
- accuracy: **38.5%**
- weight: **0.6**
- trend: **STABLE**
- votes: **13** (correct 5, incorrect 8)

### PSP
- accuracy: **53.8%**
- weight: **0.8**
- trend: **STABLE**
- votes: **13** (correct 7, incorrect 6)

### Memory
- accuracy: **100.0%**
- weight: **2.2**
- trend: **STABLE**
- votes: **13** (correct 13, incorrect 0)

### Validation
- accuracy: **38.5%**
- weight: **0.6**
- trend: **IMPROVING**
- votes: **13** (correct 5, incorrect 8)

## Weighted ticker decisions

| ticker | weighted result | confidence | member votes |
| --- | --- | --- | --- |
| AMAT | PARTIAL_PROTECT_SHADOW | MEDIUM | Rules 0.8 × EXIT_PROTECT_SHADOW; PIB 0.6 × WATCH; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × EXIT_PROTECT_SHADOW; Validation 0.6 × OBSERVE |
| HSBA.L | WATCH | MEDIUM | Rules 0.8 × EXIT_PROTECT_SHADOW; PIB 0.6 × WATCH; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × EXIT_PROTECT_SHADOW; Validation 0.6 × OBSERVE |
| LLY | TRAIL_PROTECT_SHADOW | LOW | Rules 0.8 × EXIT_PROTECT_SHADOW; PIB 0.6 × EXIT_PROTECT_SHADOW; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × OBSERVE; Validation 0.6 × OBSERVE |
| MU | PARTIAL_PROTECT_SHADOW | MEDIUM | Rules 0.8 × EXIT_PROTECT_SHADOW; PIB 0.6 × WATCH; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × EXIT_PROTECT_SHADOW; Validation 0.6 × OBSERVE |
| QQQ | OBSERVE | LOW | Rules 0.8 × NO_ACTION; PIB 0.6 × NO_ACTION; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × OBSERVE; Validation 0.6 × OBSERVE |
| MC.PA | OBSERVE | MEDIUM | Rules 0.8 × NO_ACTION; PIB 0.6 × WATCH; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × OBSERVE; Validation 0.6 × HOLD |
| AAPL | OBSERVE | MEDIUM | Rules 0.8 × NO_ACTION; PIB 0.6 × WATCH; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × OBSERVE; Validation 0.6 × HOLD |
| SIE.DE | OBSERVE | LOW | Rules 0.8 × NO_ACTION; PIB 0.6 × NO_ACTION; PSP 0.8 × EXIT_PROTECT_SHADOW; Memory 2.2 × OBSERVE; Validation 0.6 × OBSERVE |
| PG | HOLD | HIGH | Rules 0.8 × NO_ACTION; PIB 0.6 × WATCH; PSP 0.8 × HOLD; Memory 2.2 × HOLD; Validation 0.6 × HOLD |
| MRK | HOLD | HIGH | Rules 0.8 × NO_ACTION; PIB 0.6 × HOLD; PSP 0.8 × HOLD; Memory 2.2 × HOLD; Validation 0.6 × OBSERVE |
| PM | HOLD | HIGH | Rules 0.8 × NO_ACTION; PIB 0.6 × HOLD; PSP 0.8 × HOLD; Memory 2.2 × HOLD; Validation 0.6 × OBSERVE |
| SPY | HOLD | MEDIUM | Rules 0.8 × NO_ACTION; PIB 0.6 × HOLD; PSP 0.8 × HOLD; Memory 2.2 × OBSERVE; Validation 0.6 × HOLD |

## Example weighted decision

**AMAT**
- Rules: 0.8 × EXIT_PROTECT_SHADOW
- PIB: 0.6 × WATCH
- PSP: 0.8 × EXIT_PROTECT_SHADOW
- Memory: 2.2 × EXIT_PROTECT_SHADOW
- Validation: 0.6 × OBSERVE
- **Weighted result:** PARTIAL_PROTECT_SHADOW (MEDIUM)
