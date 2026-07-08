"""TAE CLI — help command."""

from __future__ import annotations

BANNER = """=================================
TAE COMMAND CENTER

Available commands:
  health
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
  paper-experiments
  paper-decisions
  paper-execution
  paper-mark-to-market
  canonical-vs-paper
  full-paper-cycle
  historical-refresh
  outcome-memory
  strategy-survival
  long-term-learning
  philosophy-performance
  adaptive-weights
  paper-cycle-retest
  30-day-paper-validation
  promotion-lock
  morning-audit
  investment-council
  status
  help

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
  paper-experiments — run PAPER scoring experiments from hypothesis queue
  paper-decisions — explicit PAPER BUY/SELL/HOLD/REDUCE/PROTECT/ROTATE/SKIP decisions
  paper-execution — apply PDE decisions to isolated PAPER portfolio (no broker)
  paper-mark-to-market — mark PAPER portfolio to market with live prices (no broker)
  canonical-vs-paper — compare canonical accounting vs PAPER portfolio (read-only)
  full-paper-cycle — run complete PAPER intelligence loop (health → LTP → PDE → DPE → summary)
  historical-refresh — refresh stale historical/strategic SSOT before PAPER decisions
  outcome-memory — canonical longitudinal PAPER decision memory (ingest + checkpoints)
  strategy-survival — strategy survival via automatic decision checkpoints
  long-term-learning — aggregate PAPER learning and adaptation hints
  philosophy-performance — COLLABORATIVE vs COMPETITIVE evidence from memory
  adaptive-weights — evidence-driven PAPER action weights for PDE scoring
  paper-cycle-retest — Phase 7 full command-chain validation report
  30-day-paper-validation — Phase 8 plan, checklist, criteria, Day 0 baseline
  promotion-lock — Phase 9 live promotion hard-lock audit
  morning-audit — consolidated read-only morning operational brief
  investment-council — synthesis-only operator brief from existing PDE/GII/DPE/governance artifacts
================================="""


def run(_args: list[str] | None = None) -> int:
    print(BANNER)
    return 0
