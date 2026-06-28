"""
TAE Phase VIII B8 — Ecosystem Orchestrator Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Runs the full read-only ecosystem chain — no trade execution.
"""

from __future__ import annotations

from pathlib import Path

from research_core.orchestrator import (
    EcosystemOrchestrator,
    EcosystemOrchestratorReportStore,
    SAFETY_BANNER,
)
from research_core.orchestrator.orchestrator_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]


def run_ecosystem_orchestrator_demo() -> None:
    print("===== TAE PHASE VIII B8 — ECOSYSTEM ORCHESTRATOR =====")
    print(SAFETY_BANNER)
    print("Full read-only ecosystem chain — no trade execution.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    orchestrator = EcosystemOrchestrator(protected_paths=PROTECTED_PATHS)
    report = orchestrator.run()

    store = EcosystemOrchestratorReportStore()
    store.persist(report)
    store.persist_txt(report)

    print(report.format_text())

    print("===== ORCHESTRATOR SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Steps succeeded: {sum(1 for s in report.steps if s.succeeded)}/{len(report.steps)}")
    print(f"Top ranked: {report.top_ranked_strategy_id or 'N/A'}")
    print(f"Review candidate: {report.promotion_review_candidate_id or 'None'}")
    print(f"Protected files unchanged: {report.protected_files_unchanged}")
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_ecosystem_orchestrator_demo()


if __name__ == "__main__":
    main()
