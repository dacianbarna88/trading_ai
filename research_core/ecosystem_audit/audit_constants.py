"""
Ecosystem Audit — shared constants

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

CANONICAL_MODULES: dict[str, str] = {
    "accounting_source_of_truth": "research_core/accounting/independent_double_entry.py",
    "evidence_source_of_truth": "research_core/evidence_engine/evidence_registry.py",
    "strategy_evolution_pipeline": "research_core/strategy_evolution/daily_runner.py",
    "integration_approval": "integration_layer/evidence_gate.py",
    "ecosystem_overview": "research_core/orchestrator/ecosystem_orchestrator.py",
    "runtime_intelligence": "research_core/runtime/workflow_engine.py",
    "systemic_interconnection": "research_core/systemic_integration/module_interconnection.py",
    "ecosystem_inventory": "research_core/ecosystem_inventory/inventory_audit.py",
}

PRIMARY_RUNNERS: list[str] = [
    "research_core/orchestrator/ecosystem_orchestrator.py",
    "research_core/strategy_evolution/daily_runner.py",
    "research_core/runtime/workflow_engine.py",
]

COMPETING_RUNNER_PATTERNS: list[str] = [
    r"daily_runner\.py$",
    r"orchestrator\.py$",
    r"workflow_engine\.py$",
    r"_runner\.py$",
    r"tae_phase.*_demo\.py$",
]

DUPLICATE_THEMES: dict[str, dict[str, object]] = {
    "accounting_audit": {
        "theme": "Accounting / ledger verification",
        "patterns": [
            r"accounting/",
            r"ledger_audit",
            r"independent_double_entry",
            r"accounting_integrity",
            r"dashboard_account_reconcile",
        ],
        "canonical": "research_core/accounting/independent_double_entry.py",
        "connect": "Route all accounting views through independent_double_entry outputs.",
    },
    "evidence_reporting": {
        "theme": "Evidence aggregation and reporting",
        "patterns": [
            r"evidence_engine/",
            r"evidence_accumulator",
            r"evidence_gap",
            r"evidence_history/",
        ],
        "canonical": "research_core/evidence_engine/evidence_registry.py",
        "connect": "Register evidence_gap and accumulator as Evidence Engine readers.",
    },
    "simulation_ranking_validation": {
        "theme": "Simulation, ranking, and validation",
        "patterns": [
            r"simulation_lab/",
            r"strategy_evolution/",
            r"cross_regime_validator",
            r"regional_validation/",
            r"continuous_ranking",
            r"parallel_paper_validator",
        ],
        "canonical": "research_core/strategy_evolution/daily_runner.py",
        "connect": "Invoke ranking/validation only via Strategy Evolution daily runner.",
    },
    "strategy_evolution_generations": {
        "theme": "Strategy evolution (Phase V vs Phase VIII)",
        "patterns": [r"research_core/evolution/", r"research_core/strategy_evolution/"],
        "canonical": "research_core/strategy_evolution/daily_runner.py",
        "connect": "Demote Phase V evolution to planning-only; do not run in parallel.",
    },
    "orchestration_runners": {
        "theme": "Ecosystem orchestration and runtime",
        "patterns": [
            r"orchestrator/",
            r"runtime/workflow_engine",
            r"ecosystem_audit/",
        ],
        "canonical": "research_core/orchestrator/ecosystem_orchestrator.py",
        "connect": "Use Orchestrator as daily entry; Runtime reads JSON only.",
    },
}

OWNERSHIP_MATRIX: dict[str, str] = {
    "live_core": "Human Owner / Live Execution",
    "integration_layer": "Integration Layer",
    "runtime": "Runtime OS",
    "orchestrator": "Runtime OS",
    "strategy_evolution": "Research Pipeline",
    "evidence_engine": "Research Pipeline",
    "accounting": "Research Pipeline",
    "simulation_lab": "Research Pipeline",
    "analysis_phases": "Research Pipeline",
    "discovery_hypothesis": "Research Pipeline",
    "governance": "Research Pipeline",
    "tools": "Tools / Dashboard (read-only)",
    "demo": "Verification / Demo",
    "config": "Human Owner / Configuration",
}

INTEGRATION_GAPS_KNOWN: list[str] = [
    "Performance audit not invoked by daily runner or orchestrator",
    "Evidence gap analyzer not wired to evidence_registry refresh",
    "Regional validation not connected to promotion gate",
    "Confidence recalibration outputs not registered as evidence items",
    "Phase V evolution manager parallel to Phase VIII pipeline",
    "Integration gate not formally chained after promotion gate in orchestrator",
    "Governance daily intelligence does not consume Phase VIII outputs",
    "Runtime foundation does not refresh upstream JSON — reads existing only",
    "Ecosystem audit (IX.1) not yet chained into orchestrator daily flow",
]

SCAN_ROOTS = [
    "core",
    "research_core",
    "integration_layer",
    "tools",
    "config",
]

SCAN_FILES = [
    "live_bot.py",
    "dashboard_v2.py",
]

EXCLUDE_DIR_NAMES = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".cursor"}

PROTECTED_PATHS = [
    "live_bot.py",
    "dashboard_v2.py",
    "config/settings.py",
    "portfolio.csv",
    "core/trades.py",
    "core/portfolio_prices.py",
]
