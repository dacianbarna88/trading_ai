#!/usr/bin/env python3
"""
TAE Autonomous Historical Execution Runner

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Runs historical execution batches automatically until all jobs are processed.
Resumes from checkpoint on each batch. Graceful Ctrl+C stop.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from research_core.strategy_simulation.historical_execution_engine import (
    DEFAULT_RUNNER_BATCH_SIZE,
    HistoricalExecutionEngine,
)
from research_core.strategy_simulation.historical_execution_report import (
    EXECUTION_SAFETY_BANNER,
    HistoricalExecutionReportStore,
    HistoricalExecutionVerdict,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SUMMARY_EVERY_N_BATCHES = 10


class _GracefulStop:
    def __init__(self) -> None:
        self.requested = False

    def install(self) -> None:
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)

    def _handle(self, signum: int, frame: object | None) -> None:
        if not self.requested:
            logger.warning("Stop requested — finishing current batch then exiting.")
        self.requested = True


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


def _print_batch_progress(batch_num: int, report: object) -> None:
    message = (
        f"Batch {batch_num}: processed={report.jobs_processed_this_run} "
        f"completed={report.jobs_completed} blocked={report.jobs_blocked} "
        f"failed={report.jobs_failed} pending={report.jobs_pending}"
    )
    logger.info(message)
    print(message, flush=True)


def _print_summary(batch_num: int, report: object, elapsed: float, session_jobs: int) -> None:
    avg = elapsed / session_jobs if session_jobs > 0 else 0.0
    remaining = report.jobs_pending * avg if avg > 0 else 0.0
    print("")
    print(f"===== PROGRESS SUMMARY (batch {batch_num}) =====")
    print(f"  Completed: {report.jobs_completed}")
    print(f"  Blocked:   {report.jobs_blocked}")
    print(f"  Failed:    {report.jobs_failed}")
    print(f"  Pending:   {report.jobs_pending}")
    print(f"  Estimated remaining time: {_format_duration(remaining)}", flush=True)
    print("", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="TAE Autonomous Historical Execution Runner")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_RUNNER_BATCH_SIZE,
        help=f"Jobs per batch (default {DEFAULT_RUNNER_BATCH_SIZE})",
    )
    args = parser.parse_args()

    batch_size = args.batch_size if args.batch_size > 0 else DEFAULT_RUNNER_BATCH_SIZE
    root = Path(".")
    stop = _GracefulStop()
    stop.install()

    logger.info("TAE Autonomous Historical Execution Runner")
    logger.info("Safety: %s", EXECUTION_SAFETY_BANNER)
    logger.info("Batch size: %d", batch_size)

    engine = HistoricalExecutionEngine(root)
    store = HistoricalExecutionReportStore()
    batch_num = 0
    session_jobs = 0
    run_start = time.perf_counter()

    while not stop.requested:
        report = engine.run(batch_size=batch_size)
        json_path, txt_path = store.persist(report)
        batch_num += 1
        session_jobs += report.jobs_processed_this_run

        _print_batch_progress(batch_num, report)
        logger.info("Reports updated: %s, %s", json_path, txt_path)

        if report.verdict == HistoricalExecutionVerdict.HISTORICAL_EXECUTION_BLOCKED:
            if report.jobs_processed_this_run == 0:
                logger.error("Execution blocked: %s", report.warnings)
                print("HISTORICAL_EXECUTION_BLOCKED — cannot continue.")
                return 1

        if report.jobs_pending == 0:
            elapsed = time.perf_counter() - run_start
            print("", flush=True)
            print("HISTORICAL_RESEARCH_COMPLETE", flush=True)
            print(
                f"  Total jobs: {report.jobs_total} | "
                f"Completed: {report.jobs_completed} | "
                f"Blocked: {report.jobs_blocked} | "
                f"Failed: {report.jobs_failed} | "
                f"Elapsed: {_format_duration(elapsed)}"
            )
            return 0

        if report.jobs_processed_this_run == 0:
            logger.error(
                "No progress this batch despite %d pending jobs — stopping to avoid loop.",
                report.jobs_pending,
            )
            return 1

        if batch_num % SUMMARY_EVERY_N_BATCHES == 0:
            _print_summary(batch_num, report, time.perf_counter() - run_start, session_jobs)

    elapsed = time.perf_counter() - run_start
    print("")
    print("Graceful stop — checkpoint preserved.")
    print(
        f"  Completed: {report.jobs_completed} | "
        f"Blocked: {report.jobs_blocked} | "
        f"Failed: {report.jobs_failed} | "
        f"Pending: {report.jobs_pending} | "
        f"Elapsed: {_format_duration(elapsed)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
