TAE MORNING AUDIT
Timestamp: 2026-09-03T13:15:44+00:00
Runtime: live | write_report=False
Account value: $30,382.07
Cash: $229.72
Open positions: 12
Writer: PASS (SINGLE_OWNER_PROVEN) lock=HEALTHY
Portfolio integrity: PASS | shrink=SHRINK_GUARD_N_A_LIVE_WRITER_RETIRED
Decision/execution: PAPER integrity=PASS recon=PASS
Market data: session=CLOSED bot_running=True
Learning: DPE score=100
Repository: main @ dc5b244d0f7d
Score: 81/100
OPERATIONAL_STATUS: PASS
PAPER_INTEGRITY_STATUS: PASS
ECONOMIC_COMPARISON_STATUS: PASS
OVERALL_STATUS: PASS_WITH_WARNINGS
FINAL STATUS: ATTENTION_REQUIRED

DPE READY jobs are shadow evaluation artifacts and are not canonical PAPER execution instructions.
DPE_SHADOW_READY_CUMULATIVE=2772 DPE_SHADOW_READY_TODAY=44 PAPER_NEW_EXECUTION_CANDIDATES=1 PAPER_EXECUTED=0 PAPER_BLOCKED_AFTER_DECISION=1 block_reasons={'same_action': 97, 'other': 1}

INFO: dual-journal recording of the same economic fill is expected; execution_id integrity separates equivalent dual-journal rows from true conflicts.
STATE_OWNERSHIP_ISOLATION=PASS EXECUTION_ID_INTEGRITY=PASS DUAL_JOURNAL_EQUIVALENT_IDS=186 CROSS_ARM_CONTAMINATION=NONE

--- Failed / warning controls ---
  [WARNING] SOURCE_DIRTY: modified/untracked Python source present (expected during infrastructure closure)

--- Immediate risks ---
  - Historical ledger: stale reported SELL PnL in portfolio.csv — canonical corrected metrics reconciled; does not block current PAPER validation
  - Profit at risk positions: 2
  - SOURCE_DIRTY: modified/untracked Python source present (expected during infrastructure closure)
  - 182 unique historical shadow jobs have BLOCKED states across 3600 append-only evaluation events; 2 events were added today, primarily HSBA.L UNKNOWN.

--- Operator actions ---
  - DPE shadow READY=2772 unique cumulative (44 unique today) — not PAPER execution instructions
  - Continue PAPER experiment prioritizing COMPETITIVE philosophy (59% weight). Monitor collaborative arm at 41%. No live promotion.

============================================================
V1 vs V2 — ECONOMIC RESULTS
============================================================

Comparison period: V1_MODE=ISOLATED_PARALLEL_PAPER | V2_MODE=ISOLATED_PARALLEL_PAPER | scope=PARALLEL_PAPER
Identity-matched opportunities: 18
Economically comparable opportunities: 18 (closed=11)
Note: identity match and economic comparability evaluated separately
Data quality: state_ownership=PASS execution_id_integrity=PASS dual_journal=EXPECTED cross_arm=NONE capital_comparable=True unmatched=0
Execution-id diagnostics: within_exec=0 within_trades=0 cross_arm_shared=0 dual_journal_equivalent=186 conflicting=0 deduplicated_economic_trades=70
Comparison integrity: PASS | COMPARISON_STATUS=V2_ECONOMIC_LEADER
State isolation: {'V1_STATE_ISOLATION': 'PROVEN', 'V2_STATE_ISOLATION': 'PROVEN', 'CROSS_CONTAMINATION': 'NONE', 'CROSS_ARM_CONTAMINATION': 'NONE', 'V1_V2_SEMANTIC_CONTAMINATION': 'CLEAR'}

ACCOUNT_LEVEL_METRICS (SSOT; not journal-summed)
  V1 realized=$-1,025.70 V2 realized=$480.33
TRADE_QUALITY_METRICS_DEDUPED (one economic trade per equivalent execution_id)
  V1 closed=41 V2 closed=29

                                     V1             V2     Difference
Account value:               $29,032.50     $30,257.57      $1,225.07
Realized PnL:                $-1,025.70        $480.33      $1,506.02
Unrealized PnL:                  $58.20       $-222.76       $-280.96
Total PnL:                        $0.00        $257.57        $257.57
Net PnL:                          $0.00        $257.57        $257.57
ROI:                              0.00%          0.86%          0.86%
Max drawdown:                     $0.00          $0.00          $0.00
Profit factor:           0.523485481486917 10.489582465134554            N/A
Expectancy:                     $-18.55         $20.66         $39.21
Profit capture:                    None           None            N/A
Avoided loss:                       N/A            N/A            N/A

V1_TOTAL_PNL=0.0
V2_TOTAL_PNL=257.569428
CURRENT_DIFFERENCE=257.569428

PROFIT LEADER: V2
RISK-ADJUSTED LEADER: V2
PROFIT-CAPTURE LEADER: V2
LOSS-PROTECTION LEADER: V1
OVERALL ECONOMIC LEADER: V2

ECONOMIC ADVANTAGE: 257.569428
MAIN REASON: Matched closed economics favor V2.
CONFIDENCE: 0.7
VERDICT: V2_ECONOMIC_LEADER

V2 leads by +348.56 USD on matched sample.
Attribution:
  -18.69 USD avoided / hard-risk losses
  +125.34 USD take-profit exits
  +302.54 USD stop-loss exits
  -223.43 USD trailing
  +162.81 USD open MTM
ATTRIBUTION_RECONCILIATION=PASS

ATTENTION_REQUIRED

