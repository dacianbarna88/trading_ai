"""TAE CLI-1 — command dispatcher."""

from __future__ import annotations

import sys

from tae_cli.commands import (
    adaptive_weights,
    dpe_adaptive,
    dpe_collaborative,
    dpe_competitive,
    dpe_evaluator,
    dpe_learning,
    dpe_events,
    dpe_splitter,
    decision_state,
    full_paper_cycle,
    growth_analytics,
    growth_intelligence,
    health,
    help as help_cmd,
    historical_refresh,
    learning_profit,
    investment_council,
    conflict_resolution,
    long_term_learning,
    morning_audit,
    opportunity,
    outcome_memory,
    paper_experiments,
    paper_decisions,
    paper_execution,
    paper_mark_to_market,
    canonical_vs_paper,
    paper_cycle_retest,
    paper_validation_30d,
    philosophy,
    philosophy_performance,
    policy,
    portfolio_protect,
    profit_pipeline,
    profit_optimization,
    profit_targets,
    promotion_lock,
    protect,
    status,
    strategy_survival,
    winner,
)

COMMANDS = {
    "full-paper-cycle": full_paper_cycle.run,
    "historical-refresh": historical_refresh.run,
    "outcome-memory": outcome_memory.run,
    "strategy-survival": strategy_survival.run,
    "long-term-learning": long_term_learning.run,
    "philosophy-performance": philosophy_performance.run,
    "adaptive-weights": adaptive_weights.run,
    "paper-cycle-retest": paper_cycle_retest.run,
    "30-day-paper-validation": paper_validation_30d.run,
    "promotion-lock": promotion_lock.run,
    "health": health.run,
    "protect": protect.run,
    "portfolio-protect": portfolio_protect.run,
    "policy": policy.run,
    "growth-analytics": growth_analytics.run,
    "opportunity": opportunity.run,
    "winner": winner.run,
    "growth-intelligence": growth_intelligence.run,
    "profit-targets": profit_targets.run,
    "profit-pipeline": profit_pipeline.run,
    "profit-optimization": profit_optimization.run,
    "philosophy": philosophy.run,
    "dpe-events": dpe_events.run,
    "dpe-splitter": dpe_splitter.run,
    "dpe-competitive": dpe_competitive.run,
    "dpe-collaborative": dpe_collaborative.run,
    "dpe-evaluator": dpe_evaluator.run,
    "dpe-learning": dpe_learning.run,
    "dpe-adaptive": dpe_adaptive.run,
    "learning-profit": learning_profit.run,
    "decision-state-refresh": decision_state.run,
    "conflict-resolution-refresh": conflict_resolution.run,
    "paper-experiments": paper_experiments.run,
    "paper-decisions": paper_decisions.run,
    "paper-execution": paper_execution.run,
    "paper-mark-to-market": paper_mark_to_market.run,
    "canonical-vs-paper": canonical_vs_paper.run,
    "morning-audit": morning_audit.run,
    "investment-council": investment_council.run,
    "status": status.run,
    "help": help_cmd.run,
}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    command = args[0].lower() if args else "help"
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        help_cmd.run([])
        return 2
    return int(handler(args[1:]))
