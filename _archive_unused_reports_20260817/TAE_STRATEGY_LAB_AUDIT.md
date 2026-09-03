# TAE Strategy Lab Architectural Audit

**Mode:** READ ONLY — no code/runtime/commit changes.
**HEAD:** `fb584243a4a9453df38c0620e7d8cf16efd0b3d8`
**Generated:** `2026-07-29T23:48:05.642488+00:00`

## Verdict

No single Strategy Lab product. Closest research stack is StrategyEvolutionDailyRunner + Simulation Lab. Closest runtime multi-strategy system is parallel-paper V1/V2. Champion-challenger and economic evaluation exist as many parallel partial systems without a closed auto-promote loop.

| Flag | Value |
|---|---|
| STRATEGY_LAB_EXISTS | `PARTIAL_RESEARCH_ONLY` |
| CHAMPION_CHALLENGER_EXISTS | `PARTIAL_FRAGMENTED` |
| MULTI_STRATEGY_RUNTIME_EXISTS | `True` |
| AUTO_PROMOTION_EXISTS | `False` |
| ECONOMIC_EVALUATOR_EXISTS | `PARTIAL_FRAGMENTED` |
| CYCLE_ANALYTICS_EXISTS | `PARTIAL` |
| REUSE_POSSIBLE | `True` |

## Capability matrix (15 searches)

| # | Capability | Status |
|---:|---|---|
| 1 | strategy manager | `MISSING` |
| 2 | strategy registry | `PARTIAL_RESEARCH` |
| 3 | experiment manager | `PARTIAL_RUNTIME_PAPER` |
| 4 | ab testing | `PARTIAL_MIXED` |
| 5 | shadow strategies | `PARTIAL_MIXED` |
| 6 | replay comparators | `PARTIAL_MANUAL` |
| 7 | economic evaluator | `PARTIAL_FRAGMENTED` |
| 8 | learning engine | `PARTIAL_RUNTIME` |
| 9 | auto promotion champion challenger | `PARTIAL_NO_AUTO_FLIP` |
| 10 | roi sharpe sortino expectancy | `PARTIAL` |
| 11 | profit per cycle | `PARTIAL_V2` |
| 12 | cycle analytics | `PARTIAL` |
| 13 | strategy scorecards | `PARTIAL` |
| 14 | multi strategy runtime | `COMPLETE_V1_V2_PARALLEL_PAPER` |
| 15 | parallel strategy execution | `COMPLETE_V1_V2_PARALLEL_PAPER` |

## Components

### strategy_manager

- **Role:** No module named StrategyManager exists.
- **Usage:** `N/A`
- **Implementation:** `MISSING`
- **Files:** _none_

### strategy_registry

- **Role:** Registers research strategy candidates from Evidence Engine / Simulation Lab; not a live V1/V2/V3 runtime registry.
- **Usage:** `RESEARCH`
- **Implementation:** `PARTIAL`
- **Files:** `research_core/strategy_evolution/candidate_registry.py`, `research_core/strategy_simulation/simulation_registry.py`, `research_core/discovery/discovery_registry.py`
- **Aliases / same function:** CandidateStrategyRegistry, simulation_registry, discovery_registry
- **Notes:** ANALYSIS_ONLY / PAPER_ONLY / NO_EXECUTION. Not imported by parallel-paper or live runtime.

### experiment_manager

- **Role:** Scores PAPER hypotheses and assigns PROMISING/REJECT/NEEDS_MORE_DATA; wired into structural paper cycle via CLI.
- **Usage:** `RUNTIME_PAPER_CYCLE`
- **Implementation:** `PARTIAL`
- **Files:** `tae_paper_experiment_runner.py`, `tae_cli/commands/paper_experiments.py`, `research_core/hypothesis/experiment_runner.py`
- **Aliases / same function:** run_experiments, hypothesis experiment_runner
- **Notes:** Runtime paper experiments exist; research_core hypothesis runner is research-isolated. Not a full multi-strategy lab.

### ab_testing

- **Role:** Ablation ON/OFF learning arms with Sharpe/Sortino; adaptive deployment CONTROL vs CHALLENGER canary sizing; design docs for entry/stop A/B.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `tae_learning_economic_ablation.py`, `tae_adaptive_deployment.py`, `TAE_ENTRY_QUALITY_AB_DESIGN.md`, `TAE_STOP_REGIME_AB_DESIGN.md`
- **Aliases / same function:** ablation arms, PAPER_CHALLENGER canary, dual-arm learning
- **Notes:** No generic A/B framework for arbitrary V1/V2/V3 strategies. Adaptive deployment is runtime-wired into parallel V2 buys.

### shadow_strategies

- **Role:** Shadow sizing/protection/validation ledgers — observe alternate decisions without (or before) capital mutation.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `tae_profit_protection_shadow.py`, `tae_paper_shadow_sizing.py`, `tae_shadow_validation_report.py`, `tae_shadow_outcome_capture.py`, `research_core/governance/shadow_validation_ledger.py`, `core/v41_shadow.py`, `tae_stage3c_shadow_compare.py`
- **Aliases / same function:** shadow sizing, shadow validation ledger, v41_shadow
- **Notes:** Component-level shadows, not a full alternate strategy book like parallel V1/V2.

### replay_comparators

- **Role:** Historical/counterfactual replays comparing baseline vs alternate rules, exits, sizing, learning, ROI-001.
- **Usage:** `RESEARCH_MANUAL`
- **Implementation:** `PARTIAL`
- **Files:** `tae_chronological_portfolio_replay.py`, `tae_strategy_v2_stateful_replay.py`, `tae_decision_replay_composer.py`, `tae_decision_replay_promotion.py`, `tae_exit_strategy_comparison.py`, `tae_paper_sizing_counterfactual_replay.py`, `tae_economic_integrity_replay.py`, `tae_learning_economic_ablation.py`, `tae_roi001_challenger.py`, `tae_profit_optimization.py`
- **Aliases / same function:** stateful replay, counterfactual replay, decision replay promotion
- **Notes:** Many independent replays; no single comparator harness for N strategies.

### economic_evaluator

- **Role:** Computes realized/unrealized, expectancy, PF, DD, and (in ablation) Sharpe/Sortino/Calmar for arms or journals.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `tae_paper_economic_attribution.py`, `tae_learning_economic_attribution_engine.py`, `tae_roi001_challenger.py`, `tae_learning_economic_ablation.py`, `tae_profit_attribution.py`, `research_core/profit_attribution/attribution_report.py`, `TAE_DAILY_ECONOMIC_SCORECARD.json`
- **Aliases / same function:** paper economic attribution, learning economic attribution, daily economic scorecard
- **Notes:** Metrics exist across modules; no unified StrategyEconomicEvaluator API for arbitrary strategy IDs.

### learning_engine

- **Role:** Canonical/DPE learning updates from paper outcomes; attribution of learning→profit.
- **Usage:** `RUNTIME_PAPER`
- **Implementation:** `PARTIAL`
- **Files:** `tae_canonical_learning_runtime.py`, `tae_dpe_learning_engine.py`, `tae_learning_persistence.py`, `tae_learning_economic_attribution_engine.py`, `migration/legacy/tae_learning_runtime.py`
- **Aliases / same function:** canonical learning runtime, DPE learning engine
- **Notes:** Learning exists; not a strategy tournament engine.

### auto_promotion_champion_challenger

- **Role:** Capital challenger registry observe; ROI-001/profit-opt/replay promotion reports; live promotion lock; research promotion gate review-only.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `tae_paper_decision_engine.py`, `runtime_outputs/learning_to_profit/capital_challengers.json`, `tae_roi001_challenger.py`, `tae_profit_optimization.py`, `tae_decision_replay_promotion.py`, `tae_live_promotion_lock.py`, `tae_adaptive_deployment.py`, `research_core/strategy_evolution/promotion_gate.py`, `tae_promotion_queue.json`
- **Aliases / same function:** capital_challengers, ROI-001, promotion_gate REVIEW_ONLY, live_promotion_lock
- **Notes:** No closed auto-promote loop that flips production strategy. profit_optimization apply path has NotImplementedError. Live lock blocks auto live promotion. Research gate is review-only.

### roi_sharpe_sortino_expectancy

- **Role:** ROI queue (manual SSOT JSON); expectancy/PF widely; Sharpe/Sortino in learning ablation; Sortino less universal.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `tae_roi_queue.json`, `TAE_ROI_QUEUE.md`, `tae_roi001_challenger.py`, `tae_learning_economic_ablation.py`, `tae_paper_economic_attribution.py`, `research_core/simulation_lab/strategy_simulation_lab.py`
- **Aliases / same function:** ROI queue, arm_economic_summary
- **Notes:** ROI queue advance helpers live inside tae_roi001_challenger.py but are not an automatic cycle. No single metrics package used by all arms.

### profit_per_cycle

- **Role:** V2 cycles track realized_pnl per cycle; parallel accounting_snapshot economic_attribution has expectancy_per_closed_cycle; winner lifecycle profiles holdings.
- **Usage:** `RUNTIME_PARALLEL_V2`
- **Implementation:** `PARTIAL`
- **Files:** `tae_strategy_v2_foundation.py`, `tae_paper_economic_attribution.py`, `runtime_outputs/parallel_paper/v2/accounting_snapshot.json`, `tae_winner_lifecycle_profiler.py`
- **Aliases / same function:** cycle realized_pnl, expectancy_per_closed_cycle
- **Notes:** V2-native; not generalized across V1/V3 strategy lab.

### cycle_analytics

- **Role:** Parallel daily/cumulative reports; opportunity/growth/winner analytics; V2 cycle state journals.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `tae_parallel_paper_reports.py`, `tae_winner_lifecycle_profiler.py`, `tae_opportunity_cost_ledger.py`, `tae_growth_intelligence.py`, `tae_strategy_v2_foundation.py`
- **Aliases / same function:** parallel daily reports, winner lifecycle, opportunity cost ledger

### strategy_scorecards

- **Role:** Daily economic / E3 / effervescence scorecards; continuous ranking scores research candidates.
- **Usage:** `MIXED`
- **Implementation:** `PARTIAL`
- **Files:** `TAE_DAILY_ECONOMIC_SCORECARD.json`, `TAE_DAILY_ECONOMIC_SCORECARD.csv`, `tae_e3_forward_daily_scorecard.csv`, `TAE_MARKET_EFFERVESCENCE_DAILY_SCORECARD.csv`, `research_core/strategy_evolution/continuous_ranking_engine.py`
- **Aliases / same function:** daily economic scorecard, continuous ranking
- **Notes:** Scorecards exist but are not a unified multi-strategy tournament scoreboard.

### multi_strategy_runtime

- **Role:** Isolated parallel PAPER books for V1 and V2 with separate cash/positions/journals; daemon + CLI + reports.
- **Usage:** `RUNTIME_ACTIVE`
- **Implementation:** `COMPLETE`
- **Files:** `tae_parallel_paper_runtime.py`, `tae_parallel_paper_daemon.py`, `tae_parallel_paper_config.py`, `tae_cli/commands/parallel_paper.py`, `launchd/com.tradingai.parallel-paper.plist`, `runtime_outputs/parallel_paper/v1/`, `runtime_outputs/parallel_paper/v2/`
- **Aliases / same function:** parallel paper, ISOLATED_PARALLEL_PAPER, dual-arm V1/V2
- **Notes:** Strongest existing multi-strategy runtime. V3 not present. Not a general N-strategy plugin host.

### strategy_simulation_lab

- **Role:** Research lab comparing baseline BUY filters vs alternate entry strategies; feeds candidate registry via StrategyEvolutionDailyRunner.
- **Usage:** `RESEARCH`
- **Implementation:** `PARTIAL`
- **Files:** `research_core/simulation_lab/strategy_simulation_lab.py`, `research_core/strategy_evolution/daily_runner.py`
- **Aliases / same function:** Continuous Strategy Simulation Lab, StrategyEvolutionDailyRunner
- **Notes:** Closest named 'Strategy Lab'. ANALYSIS_ONLY; not connected to parallel-paper runtime or auto capital mutation.

### research_strategy_evolution_pipeline

- **Role:** End-to-end research pipeline: register → validate → rank → review-only promote → paper tracking.
- **Usage:** `RESEARCH`
- **Implementation:** `PARTIAL`
- **Files:** `research_core/strategy_evolution/daily_runner.py`, `research_core/strategy_evolution/candidate_registry.py`, `research_core/strategy_evolution/parallel_paper_validator.py`, `research_core/strategy_evolution/continuous_ranking_engine.py`, `research_core/strategy_evolution/promotion_gate.py`, `research_core/strategy_evolution/paper_tracking_log.py`
- **Aliases / same function:** Phase VIII/IX strategy evolution
- **Notes:** parallel_paper_validator here is research report validator, distinct from tae_parallel_paper_runtime daemon.

## Missing components

- Unified StrategyManager / plugin host for V1/V2/V3+
- Single champion-challenger SSOT spanning capital/ROI/profit-opt/parallel arms
- Closed auto-promotion loop with rollback that mutates production config
- General N-strategy economic comparator used by both research and runtime
- V3 (or N) arm in parallel-paper runtime
- Automatic ROI queue regeneration/advance each paper cycle

## Recommendation

REUSE parallel-paper (V1/V2 dual book) + paper economic attribution + capital_challengers observe + research StrategyEvolutionDailyRunner metrics/gates as libraries; DO NOT invent a second runtime. If building a Strategy Lab, make it an orchestration façade over these existing pieces with one SSOT scoreboard — not a greenfield engine. Auto-promotion to live must remain human-gated (live_promotion_lock).

## Explicit answers

```
STRATEGY_LAB_EXISTS=PARTIAL_RESEARCH_ONLY
CHAMPION_CHALLENGER_EXISTS=PARTIAL_FRAGMENTED
MULTI_STRATEGY_RUNTIME_EXISTS=True
AUTO_PROMOTION_EXISTS=False
ECONOMIC_EVALUATOR_EXISTS=PARTIAL_FRAGMENTED
CYCLE_ANALYTICS_EXISTS=PARTIAL
REUSE_POSSIBLE=True
MISSING_COMPONENTS=Unified StrategyManager / plugin host for V1/V2/V3+ | Single champion-challenger SSOT spanning capital/ROI/profit-opt/parallel arms | Closed auto-promotion loop with rollback that mutates production config | General N-strategy economic comparator used by both research and runtime | V3 (or N) arm in parallel-paper runtime | Automatic ROI queue regeneration/advance each paper cycle
RECOMMENDATION=REUSE parallel-paper (V1/V2 dual book) + paper economic attribution + capital_challengers observe + research StrategyEvolutionDailyRunner metrics/gates as libraries; DO NOT invent a second runtime. If building a Strategy Lab, make it an orchestration façade over these existing pieces with one SSOT scoreboard — not a greenfield engine. Auto-promotion to live must remain human-gated (live_promotion_lock).
```
