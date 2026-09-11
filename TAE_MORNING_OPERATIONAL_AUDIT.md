TAE MORNING AUDIT
Timestamp: 2026-09-11T13:15:06+00:00
Runtime: live | write_report=False
Account value: $29,864.54
Cash: $4,504.30
Open positions: 11
Writer: PASS (SINGLE_OWNER_PROVEN) lock=HEALTHY
Portfolio integrity: PASS | shrink=SHRINK_GUARD_N_A_LIVE_WRITER_RETIRED
Decision/execution: PAPER integrity=PASS recon=PASS
Market data: session=CLOSED bot_running=False
Learning: DPE score=100
Repository: main @ 898cad1b949d
Score: 79/100
OPERATIONAL_STATUS: PASS
PAPER_INTEGRITY_STATUS: PASS
ECONOMIC_COMPARISON_STATUS: PASS
OVERALL_STATUS: PASS_WITH_WARNINGS
FINAL STATUS: ATTENTION_REQUIRED

DPE READY jobs are shadow evaluation artifacts and are not canonical PAPER execution instructions.
DPE_SHADOW_READY_CUMULATIVE=3124 DPE_SHADOW_READY_TODAY=44 PAPER_NEW_EXECUTION_CANDIDATES=0 PAPER_EXECUTED=0 PAPER_BLOCKED_AFTER_DECISION=0 block_reasons={'same_action': 98}

INFO: dual-journal recording of the same economic fill is expected; execution_id integrity separates equivalent dual-journal rows from true conflicts.
STATE_OWNERSHIP_ISOLATION=PASS EXECUTION_ID_INTEGRITY=PASS DUAL_JOURNAL_EQUIVALENT_IDS=359 CROSS_ARM_CONTAMINATION=NONE

--- Failed / warning controls ---
  [WARNING] LIVE_BOT_NOT_RUNNING: live_bot not detected
  [WARNING] SOURCE_DIRTY: modified/untracked Python source present (expected during infrastructure closure)

--- Warnings ---
  live_bot.py process not detected

--- Immediate risks ---
  - Historical ledger: stale reported SELL PnL in portfolio.csv — canonical corrected metrics reconciled; does not block current PAPER validation
  - live_bot.py process not detected
  - Non-critical infra notes: 1
  - LIVE_BOT_NOT_RUNNING: live_bot not detected
  - SOURCE_DIRTY: modified/untracked Python source present (expected during infrastructure closure)
  - 198 unique historical shadow jobs have BLOCKED states across 3616 append-only evaluation events; 2 events were added today, primarily HSBA.L UNKNOWN.

--- Operator actions ---
  - DPE shadow READY=3124 unique cumulative (44 unique today) — not PAPER execution instructions
  - Verify live_bot autostart / process health
  - Continue PAPER experiment prioritizing COMPETITIVE philosophy (53% weight). Monitor collaborative arm at 47%. No live promotion.

============================================================
V1 vs V2 — ECONOMIC RESULTS
============================================================

Comparison period: V1_MODE=ISOLATED_PARALLEL_PAPER | V2_MODE=ISOLATED_PARALLEL_PAPER | scope=PARALLEL_PAPER
Identity-matched opportunities: 18
Economically comparable opportunities: 18 (closed=17)
Note: identity match and economic comparability evaluated separately
Data quality: state_ownership=PASS execution_id_integrity=PASS dual_journal=EXPECTED cross_arm=NONE capital_comparable=True unmatched=0
Execution-id diagnostics: within_exec=0 within_trades=0 cross_arm_shared=0 dual_journal_equivalent=359 conflicting=0 deduplicated_economic_trades=178
Comparison integrity: PASS | COMPARISON_STATUS=V1_ECONOMIC_LEADER
State isolation: {'V1_STATE_ISOLATION': 'PROVEN', 'V2_STATE_ISOLATION': 'PROVEN', 'CROSS_CONTAMINATION': 'NONE', 'CROSS_ARM_CONTAMINATION': 'NONE', 'V1_V2_SEMANTIC_CONTAMINATION': 'CLEAR'}

ACCOUNT_LEVEL_METRICS (SSOT; not journal-summed)
  V1 realized=$-1,795.46 V2 realized=$250.55
TRADE_QUALITY_METRICS_DEDUPED (one economic trade per equivalent execution_id)
  V1 closed=65 V2 closed=113

                                     V1             V2     Difference
Account value:               $28,200.41     $30,216.36      $2,015.96
Realized PnL:                $-1,795.46        $250.55      $2,046.02
Unrealized PnL:                  $-4.13        $-34.19        $-30.06
Total PnL:                        $0.00        $216.36        $216.36
Net PnL:                          $0.00        $216.36        $216.36
ROI:                              0.00%          0.72%          0.72%
Max drawdown:                     $0.00          $0.00          $0.00
Profit factor:           0.38679019122194436 0.9304073519191991            N/A
Expectancy:                     $-23.87         $-0.76         $23.11
Profit capture:                    None           None            N/A
Avoided loss:                       N/A            N/A            N/A

V1_TOTAL_PNL=0.0
V2_TOTAL_PNL=216.364319
CURRENT_DIFFERENCE=216.364319

PROFIT LEADER: V2
RISK-ADJUSTED LEADER: V2
PROFIT-CAPTURE LEADER: V1
LOSS-PROTECTION LEADER: V1
OVERALL ECONOMIC LEADER: V1

ECONOMIC ADVANTAGE: 216.364319
MAIN REASON: Matched closed economics favor V1.
CONFIDENCE: 0.7
VERDICT: V1_ECONOMIC_LEADER

V2 leads by +642.63 USD on matched sample.
Attribution:
  +611.39 USD stop-loss exits
  +18.31 USD trailing
  +12.94 USD open MTM
ATTRIBUTION_RECONCILIATION=PASS

ATTENTION_REQUIRED

