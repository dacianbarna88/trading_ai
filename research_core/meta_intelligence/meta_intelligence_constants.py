"""
Meta Intelligence constants — Phase X Sprint X.2A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

from pathlib import Path

CANONICAL_INPUTS: dict[str, Path] = {
    "runtime_foundation": Path("tae_runtime_foundation.json"),
    "ecosystem_orchestrator": Path("tae_ecosystem_orchestrator.json"),
    "strategy_evolution_daily_runner": Path("tae_strategy_evolution_daily_runner.json"),
    "candidate_strategy_registry": Path("tae_candidate_strategy_registry.json"),
    "continuous_strategy_ranking": Path("tae_continuous_strategy_ranking.json"),
    "strategic_performance_audit": Path("tae_strategic_performance_audit.json"),
    "paper_tracking_log": Path("tae_paper_tracking_log.json"),
    "daily_intelligence_report": Path("tae_daily_intelligence_report.json"),
}

MIN_REQUIRED_INPUTS = 6
BASELINE_CANDIDATE_ID = "LIVE_BASELINE"

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
    Path("config/settings.py"),
]

MODULE_PATH = Path("research_core/meta_intelligence/meta_intelligence_engine.py")
