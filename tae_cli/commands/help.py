"""TAE CLI — help command."""

from __future__ import annotations

BANNER = """=================================
TAE COMMAND CENTER

Available commands:
  health
  final-check
  test
  protect

  portfolio-protect
  policy
  growth-analytics
  opportunity
  winner
  growth-intelligence
  profit-targets
  philosophy
  dpe-events
  dpe-splitter
  dpe-competitive
  dpe-collaborative
  dpe-evaluator
  dpe-learning
  dpe-adaptive
  learning-profit
  learning-economic-ablation
  learning-attribution-run
  learning-attribution-status
  learning-attribution-report
  learning-attribution-verify
  learning-runtime-start
  learning-runtime-stop
  learning-runtime-status
  learning-runtime-cycle
  learning-runtime-health
  learning-runtime-autostart-install
  learning-runtime-autostart-status
  learning-runtime-autostart-remove
  decision-state-refresh
  executive-review
  exit-strategy-comparison
  exit-replay-horizon-audit
  conflict-resolution-refresh
  paper-experiments
  self-improve
  paper-decisions
  paper-execution
  paper-mark-to-market
  parallel-paper-start
  parallel-paper-run-once
  parallel-paper-health
  parallel-paper-report
  parallel-paper-report-3way
  parallel-paper-stop
  parallel-paper-cycle
  parallel-paper-autostart-install
  parallel-paper-autostart-status
  parallel-paper-autostart-remove
  strategy-lab
  strategy-lab-status
  strategy-lab-scoreboard
  strategy-lab-explain
  strategy-lab-health
  strategy-lab-research
  strategy-lab-metrics
  strategy-lab-recommend
  strategy-lab-promotion
  today
  canonical-vs-paper
  full-paper-cycle
  historical-refresh
  outcome-memory
  strategy-survival
  long-term-learning
  philosophy-performance
  adaptive-weights
  adaptive-deployment
  paper-cycle-retest
  30-day-paper-validation
  promotion-lock
  morning-audit
  profit-pipeline
  profit-optimization
  conversion-breakthrough
  investment-council
  research
  migration
  recovery
  status
  help

Foundation (Stage 5): see TAE_FOUNDATION_STATUS.md · TAE_OPERATOR_RUNBOOK.md · TAE_CANONICAL_ARCHITECTURE.md

  protect — run shadow profit protection + adaptive committee + context pipeline
  portfolio-protect — portfolio-level profit governor (PDG + PPG)
  policy — adaptive profit policy memory + evaluation (PPG + APPE)
  growth-analytics — profit growth analytics SSOT (read-only join)
  opportunity — opportunity cost ledger (why profit was missed)
  winner — winner lifecycle profiler (how winners grow and die)
  growth-intelligence — unified profit growth intelligence integrator (GII)
  profit-targets — dynamic profit target adapter (numeric shadow targets)
  philosophy — market philosophy lab (competitive vs collaborative models)
  dpe-events — decision event bus (immutable DPE snapshots)
  dpe-splitter — execution splitter (competitive + collaborative jobs)
  dpe-competitive — competitive paper executor (isolated DPE portfolio)
  dpe-collaborative — collaborative paper executor (isolated DPE portfolio)
  dpe-evaluator — compare competitive vs collaborative paper results
  dpe-learning — learn from evaluation results (append-only history)
  dpe-adaptive — adaptive philosophy selector (learning → recommendation)
  learning-profit — learning-to-profit bridge (ranked PAPER hypotheses + queue)
  learning-economic-ablation — LEARNING ON vs OFF economic attribution (PAPER ONLY; no SSOT write)
  learning-attribution-run — canonical measurement-only learning attribution (no weight/PAPER mutation)
  learning-attribution-status — READY / NO_MATURED / PARTIAL / COMPLETE / CORRUPTION / FAILED
  learning-attribution-report — technical + economic verdicts and evidence paths
  learning-attribution-verify — reconcile ledger totals and detect duplicates
  learning-runtime-start — start canonical PAPER learning daemon (no LIVE; no implicit cycle)
  learning-runtime-stop — stop canonical learning daemon
  learning-runtime-status — read-only learning runtime status
  learning-runtime-cycle — one deterministic PAPER learning cycle (longitudinal+weights+lifecycle)
  learning-runtime-health — HEALTHY / NO_ELIGIBLE / STALE / FAILED / CORRUPTION / DUPLICATE
  learning-runtime-autostart-install — LaunchAgent for canonical learning (PAPER only)
  learning-runtime-autostart-status — show learning autostart / PID
  learning-runtime-autostart-remove — unload learning LaunchAgent
  decision-state-refresh — build active per-ticker decision state from PAPER execution artifacts
  conflict-resolution-refresh — EV-ranked scenario evidence for PDE (no new decision engine)
  paper-experiments — run PAPER scoring experiments from hypothesis queue
  self-improve — PAPER-only lifecycle; post-close includes bounded autonomous evolution
                 autonomy-status|lineage|champion|mutations|pause-autonomy|resume-autonomy
  paper-decisions — explicit PAPER BUY/SELL/HOLD/REDUCE/PROTECT/ROTATE/SKIP decisions
  paper-execution — apply PDE decisions to isolated PAPER portfolio (no broker)
  paper-mark-to-market — mark PAPER portfolio to market with live prices (no broker)
  parallel-paper-start — start persistent isolated V1/V2 parallel PAPER daemon (no cycle, no LIVE)
  parallel-paper-run-once — run exactly one parallel cycle (explicit; not a start)
  parallel-paper-health — process/state/accounting/data health (RUNNING_* vs STOPPED_HEALTHY_STATE)
  parallel-paper-report — generate daily V1 vs V2 comparative report
  parallel-paper-report-3way — generate daily V1/V2/V3 comparative report (Phase 4)
  parallel-paper-stop — stop persistent parallel PAPER runtime cleanly
  parallel-paper-cycle — alias of parallel-paper-run-once
  parallel-paper-autostart-install — install LaunchAgent KeepAlive for parallel PAPER only
  parallel-paper-autostart-status — show parallel PAPER autostart / PID / LIVE=false
  parallel-paper-autostart-remove — unload LaunchAgent and stop daemon
  strategy-lab — Strategy Lab SSOT (+ human-gated ticket|approve|reject|apply|rollback)
  strategy-lab-status — Strategy Lab registry + reconcile status (no trades)
  strategy-lab-scoreboard — build/persist economic scoreboard vs parallel books
  strategy-lab-explain — WHY_PNL/DRAWDOWN/CAPITAL/EXPECTANCY/RANK from attribution
  strategy-lab-health — per-strategy health + promotion readiness (no auto-promote)
  strategy-lab-research — research/replay/candidate/gate summary (read-only)
  strategy-lab-metrics — economic metrics SSOT (null if missing; no invented formulas)
  strategy-lab-recommend — promotion recommendation (read-only; never applies)
  strategy-lab-promotion — promotion domain status / tickets / champion (PAPER only)
  canonical-vs-paper — compare canonical accounting vs PAPER portfolio (read-only)
  full-paper-cycle — run complete PAPER intelligence loop (health → LTP → PDE → DPE → summary)
  historical-refresh — refresh stale historical/strategic SSOT before PAPER decisions
  outcome-memory — canonical longitudinal PAPER decision memory (ingest + checkpoints)
  strategy-survival — strategy survival via automatic decision checkpoints
  long-term-learning — aggregate PAPER learning and adaptation hints
  philosophy-performance — COLLABORATIVE vs COMPETITIVE evidence from memory
  adaptive-weights — evidence-driven PAPER action weights for PDE scoring
  adaptive-deployment — PAPER adaptive deployment SSOT (activate/pause/rollback; LIVE locked)
  paper-cycle-retest — Phase 7 full command-chain validation report
  30-day-paper-validation — Phase 8 plan, checklist, criteria, Day 0 baseline
  promotion-lock — Phase 9 live promotion hard-lock audit
  today — decision-traceable read-only daily operating table
          optional: --day YYYY-MM-DD · --json · --ticker AIR.PA · --cio
                    --strategy V1|V2 · --all-events (flags may be combined)
  morning-audit — canonical daily read-only operational brief (LIVE writer/shrink/lock + PAPER SSOT)
                  optional: --write-report (persist infra/pipeline JSON) · --verbose
  final-check — non-destructive closure gate (agents/processes/isolation/accounting)
  test — canonical hermetic unittest suite (excludes archive/research/runtime_outputs)
  profit-pipeline — end-to-end PAPER profit pipeline read-only consolidation
  profit-optimization — evidence-based profit audit, challenger replay, calibration selection
  conversion-breakthrough — opportunity→order conversion audit, blocker ROI, challenger promotion
  opportunity-attrition — upstream attrition trace, death map, blocker challenger replay
  investment-council — synthesis-only operator brief from existing PDE/GII/DPE/governance artifacts
  research — RESEARCH ONLY namespace (list/path); no execution, no broker, no portfolio changes
  migration — MIGRATION/RECOVERY namespace (list/inspect/dry-run/run --confirm); no normal runtime
  recovery — alias of migration
================================="""


def run(_args: list[str] | None = None) -> int:
    print(BANNER)
    return 0
