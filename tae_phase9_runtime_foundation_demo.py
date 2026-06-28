"""
TAE Phase IX C2 — Trading AI Operating System Runtime Foundation Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only runtime foundation — no trade execution or live file changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.runtime import (
    RuntimeFoundationReportStore,
    SAFETY_BANNER,
    WorkflowEngine,
)
from research_core.runtime.learning_memory import LEARNING_JSON_PATH, LEARNING_TXT_PATH
from research_core.runtime.runtime_report import DEFAULT_JSON_PATH, DEFAULT_TXT_PATH

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]


def run_runtime_foundation_demo() -> None:
    print("===== TAE PHASE IX C2 — TRADING AI OS RUNTIME FOUNDATION =====")
    print(SAFETY_BANNER)
    print("Read-only runtime foundation — no trade execution.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    engine = WorkflowEngine()
    report = engine.run()

    store = RuntimeFoundationReportStore()
    store.persist(report)
    store.persist_txt(report)

    print(report.format_text())

    print("===== RUNTIME SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Health: {report.health_status}")
    print(f"Issues: {len(report.health_issues)}")
    print(f"Events: {len(report.events_emitted)}")
    print(f"Top ranked: {report.top_ranked_strategy_id or 'N/A'}")
    print(f"Review candidate: {report.promotion_review_candidate_id or 'None'}")
    print(f"Protected files unchanged: {report.protected_files_unchanged}")
    print(f"Runtime JSON: {DEFAULT_JSON_PATH}")
    print(f"Runtime TXT: {DEFAULT_TXT_PATH}")
    print(f"Learning memory JSON: {LEARNING_JSON_PATH}")
    print(f"Learning memory TXT: {LEARNING_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_runtime_foundation_demo()


if __name__ == "__main__":
    main()
