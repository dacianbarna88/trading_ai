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
  morning-audit
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
  morning-audit — consolidated read-only morning operational brief
================================="""


def run(_args: list[str] | None = None) -> int:
    print(BANNER)
    return 0
