#!/usr/bin/env python3
"""
TAE Market Open Intelligence Runner.

SHADOW_ONLY orchestrator for the intraday performance / knowledge stack.
Does NOT modify live_bot.py, trading logic, portfolio.csv, or live_signals.csv.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = PROJECT_DIR / "tae_market_open_intelligence_runner.json"
OUTPUT_MD = PROJECT_DIR / "tae_market_open_intelligence_runner.md"
LOG_FILE = PROJECT_DIR / "market_open_intelligence_runner.log"
LOCK_FILE = PROJECT_DIR / ".market_open_intelligence_runner.lock"

FORBIDDEN = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT"})
PROTECTED_FILES = (
    "live_bot.py",
    "portfolio.csv",
    "live_signals.csv",
)

MODULE_PIPELINE: list[dict[str, str]] = [
    {"id": "infrastructure_health", "script": "tae_infrastructure_health.py"},
    {"id": "intraday_fade_intelligence", "script": "tae_intraday_fade_intelligence.py"},
    {"id": "fade_history", "script": "tae_intraday_fade_history.py"},
    {"id": "intraday_discovery", "script": "tae_intraday_discovery_engine.py"},
    {"id": "profit_protection_shadow", "script": "tae_profit_protection_shadow.py"},
    {"id": "profit_protection_validation", "script": "tae_profit_protection_validation.py"},
    {"id": "cooldown_audit", "script": "tae_stop_reentry_cooldown_audit.py"},
    {"id": "decision_replay", "script": "tae_decision_replay_composer.py"},
    {"id": "confidence_evolution", "script": "tae_confidence_evolution.py"},
    {"id": "knowledge_base", "script": "tae_knowledge_base.py"},
    {"id": "decision_governor", "script": "tae_decision_governor.py"},
]

STDOUT_TAIL_LINES = 8
STDERR_TAIL_LINES = 5


def _tail(text: str, lines: int) -> str:
    if not text:
        return ""
    parts = text.strip().splitlines()
    return "\n".join(parts[-lines:])


def _file_snapshot(root: Path) -> dict[str, float | None]:
    snap: dict[str, float | None] = {}
    for name in PROTECTED_FILES:
        path = root / name
        snap[name] = path.stat().st_mtime if path.is_file() else None
    return snap


def _protected_files_unchanged(before: dict[str, float | None], after: dict[str, float | None]) -> bool:
    return before == after


def run_module(
    entry: dict[str, str],
    *,
    order: int,
    python_bin: str,
    root: Path,
) -> dict[str, Any]:
    script = entry["script"]
    script_path = root / script
    started = time.monotonic()

    if not script_path.is_file():
        return {
            "order": order,
            "id": entry["id"],
            "script": script,
            "status": "WARN",
            "exit_code": None,
            "duration_seconds": 0.0,
            "detail": "Module script missing — skipped",
            "stdout_tail": "",
            "stderr_tail": "",
        }

    try:
        result = subprocess.run(
            [python_bin, script],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        duration = round(time.monotonic() - started, 2)
        status = "PASS" if result.returncode == 0 else "FAIL"
        detail = "Completed successfully" if status == "PASS" else f"Exit code {result.returncode}"
        return {
            "order": order,
            "id": entry["id"],
            "script": script,
            "status": status,
            "exit_code": result.returncode,
            "duration_seconds": duration,
            "detail": detail,
            "stdout_tail": _tail(result.stdout, STDOUT_TAIL_LINES),
            "stderr_tail": _tail(result.stderr, STDERR_TAIL_LINES),
        }
    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - started, 2)
        return {
            "order": order,
            "id": entry["id"],
            "script": script,
            "status": "FAIL",
            "exit_code": -1,
            "duration_seconds": duration,
            "detail": "Timeout after 600s",
            "stdout_tail": _tail(exc.stdout or "", STDOUT_TAIL_LINES),
            "stderr_tail": _tail(exc.stderr or "", STDERR_TAIL_LINES),
        }
    except OSError as exc:
        duration = round(time.monotonic() - started, 2)
        return {
            "order": order,
            "id": entry["id"],
            "script": script,
            "status": "FAIL",
            "exit_code": -1,
            "duration_seconds": duration,
            "detail": f"Execution error: {exc}",
            "stdout_tail": "",
            "stderr_tail": "",
        }


def build_summary(modules: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for mod in modules:
        counts[mod["status"]] = counts.get(mod["status"], 0) + 1
    if counts["FAIL"] > 0:
        overall = "FAIL"
    elif counts["WARN"] > 0:
        overall = "WARN"
    else:
        overall = "PASS"
    return {
        "total": len(modules),
        "pass": counts["PASS"],
        "warn": counts["WARN"],
        "fail": counts["FAIL"],
        "overall_status": overall,
    }


def collect_recommendations(root: Path) -> list[str]:
    recs: list[str] = []
    for path in (
        root / "tae_decision_replay.json",
        root / "tae_confidence_evolution.json",
        root / "tae_profit_protection_validation.json",
    ):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for key in ("recommendations",):
            for item in data.get(key) or []:
                if item not in recs:
                    recs.append(str(item))
    return recs


def build_report(
    *,
    root: Path | None = None,
    python_bin: str | None = None,
    pipeline: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    root = root or PROJECT_DIR
    python_bin = python_bin or sys.executable
    pipeline = pipeline or MODULE_PIPELINE

    before = _file_snapshot(root)
    modules: list[dict[str, Any]] = []
    for idx, entry in enumerate(pipeline, start=1):
        modules.append(run_module(entry, order=idx, python_bin=python_bin, root=root))
    after = _file_snapshot(root)

    summary = build_summary(modules)
    recommendations = collect_recommendations(root)
    live_recommendations = [r for r in recommendations if r in FORBIDDEN]

    return {
        "schema": "tae_market_open_intelligence_runner",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "paper_only": True,
        "no_broker": True,
        "no_execution": True,
        "runner_note": "Orchestrates analysis modules only — does not place orders or modify live_bot.",
        "python_bin": python_bin,
        "modules": modules,
        "summary": summary,
        "protected_files_unchanged": _protected_files_unchanged(before, after),
        "recommendations_observed": recommendations,
        "live_trading_recommendations_detected": live_recommendations,
        "pipeline_order": [m["id"] for m in pipeline],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# TAE Market Open Intelligence Runner",
        "",
        f"**Generated:** {report.get('generated_at')}",
        f"**Mode:** SHADOW_ONLY | **Live impact:** NONE",
        "",
        "> PAPER_ONLY / NO_BROKER — analysis orchestration only. No orders placed.",
        "",
        "## Executive summary",
        "",
        f"- **Overall status:** {summary.get('overall_status')}",
        f"- **Modules:** {summary.get('pass')} PASS / {summary.get('warn')} WARN / {summary.get('fail')} FAIL",
        f"- **Protected files unchanged:** {report.get('protected_files_unchanged')}",
        f"- **Live trading recommendations detected:** {report.get('live_trading_recommendations_detected') or 'None'}",
        "",
        "## Module results",
        "",
        "| # | Module | Script | Status | Duration | Detail |",
        "|---|--------|--------|--------|----------|--------|",
    ]
    for mod in report.get("modules") or []:
        lines.append(
            f"| {mod.get('order')} | {mod.get('id')} | `{mod.get('script')}` | "
            f"**{mod.get('status')}** | {mod.get('duration_seconds')}s | {mod.get('detail')} |"
        )

    failed = [m for m in report.get("modules") or [] if m.get("status") == "FAIL"]
    if failed:
        lines.extend(["", "## Failures (bot continues)", ""])
        for mod in failed:
            lines.append(f"- **{mod.get('id')}** — {mod.get('detail')}")
            if mod.get("stderr_tail"):
                lines.append(f"  ```\n  {mod.get('stderr_tail')}\n  ```")

    lines.extend(
        [
            "",
            "## Pipeline order",
            "",
        ]
    )
    for idx, mod_id in enumerate(report.get("pipeline_order") or [], start=1):
        lines.append(f"{idx}. {mod_id}")

    lines.extend(["", "*Runner VIEW only. live_bot.py and trading logic untouched.*", ""])
    return "\n".join(lines)


def append_log(report: dict[str, Any], *, log_path: Path | None = None) -> None:
    log_path = log_path or LOG_FILE
    summary = report.get("summary") or {}
    lines = [
        "",
        f"===== MARKET OPEN INTELLIGENCE RUN {report.get('generated_at')} =====",
        f"Overall: {summary.get('overall_status')} | "
        f"PASS={summary.get('pass')} WARN={summary.get('warn')} FAIL={summary.get('fail')}",
    ]
    for mod in report.get("modules") or []:
        lines.append(f"  [{mod.get('status')}] {mod.get('order')}. {mod.get('id')} ({mod.get('duration_seconds')}s)")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    append_log(report)
    return OUTPUT_JSON, OUTPUT_MD


def acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < 1800:
                return False
        except OSError:
            pass
    try:
        LOCK_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
        return True
    except OSError:
        return True


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> int:
    if not acquire_lock():
        print("SKIP: market open intelligence runner lock active (<30 min)")
        return 0

    try:
        report = build_report()
        write_outputs(report)
        summary = report.get("summary") or {}
        print("===== TAE MARKET OPEN INTELLIGENCE RUNNER =====")
        print("Mode: SHADOW_ONLY | Live impact: NONE")
        print(
            f"Overall: {summary.get('overall_status')} — "
            f"{summary.get('pass')} PASS / {summary.get('warn')} WARN / {summary.get('fail')} FAIL"
        )
        for mod in report.get("modules") or []:
            print(f"  [{mod['status']}] {mod['order']:2d}. {mod['id']}")
        print("Wrote:", OUTPUT_JSON, OUTPUT_MD, LOG_FILE)
        return 0 if summary.get("overall_status") == "PASS" else 1
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
