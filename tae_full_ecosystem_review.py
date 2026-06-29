#!/usr/bin/env python3
"""
TAE Full Ecosystem Review — Sprint X.10 PREP

OBSERVABILITY | FINANCIAL_ANALYSIS | COUNTERFACTUAL_REPORTING
PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION

Read-only unified daily review. Does not modify live_bot, portfolio, or signals.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from research_core.governance.live_advisory_runtime import (
    load_live_advisory,
    should_block_new_buy,
)
from tae_shadow_validation_report import build_summary as build_shadow_summary
from tae_shadow_validation_report import load_events as load_shadow_events

logger = logging.getLogger(__name__)

SCHEMA = "tae.full_ecosystem_review.v1"
MODE = "OBSERVABILITY_FINANCIAL_ANALYSIS"
LIVE_TRADING_IMPACT = "NONE"
STARTING_CAPITAL = 30000.0
MIN_BUY_SCORE = 80

# Bot cycle is 60s; treat logs/signals as fresh within 5 minutes.
BOT_LOG_FRESH_SECONDS = 300
ARTIFACT_FRESH_SECONDS = 600

DEFAULT_JSON_OUT = Path("tae_full_ecosystem_review.json")
DEFAULT_MD_OUT = Path("tae_full_ecosystem_review.md")

LIVE_BOT_SCRIPT = "live_bot.py"
DASHBOARD_SCRIPT = "dashboard_v2.py"
BOT_LOG_FILE = "bot_output.log"
BOT_STATUS_FILE = "bot_status.txt"
BOT_PID_FILE = "bot_pid.txt"
DASHBOARD_PID_FILE = "dashboard_pid.txt"
DASHBOARD_STATUS_FILE = "dashboard_status.txt"
DASHBOARD_PORT = 8501
SESSION_GUARD_LOG = "market_session_guard.log"
SHADOW_LEDGER_MODULE = Path("research_core/governance/shadow_validation_ledger.py")
SHADOW_REPORT_SCRIPT = Path("tae_shadow_validation_report.py")

ARTIFACT_GLOBS = (
    "tae_*strategy*.json",
    "tae_*ranking*.json",
    "tae_*historical*.json",
    "tae_*counterfactual*.json",
    "tae_*performance*.json",
    "tae_evidence*.json",
)

CORE_ARTIFACTS = (
    "portfolio.csv",
    "live_signals.csv",
    "tae_live_advisory.json",
    "tae_shadow_validation_events.csv",
    "tae_shadow_validation_summary.json",
    "tae_advisory_index.json",
    "tae_historical_execution.json",
    "tae_historical_results_analysis.json",
    "tae_continuous_strategy_ranking.json",
    "tae_candidate_strategy_registry.json",
    "tae_meta_intelligence.json",
    "tae_meta_evolution.json",
    "tae_evidence_engine_report.json",
    "tae_quick_health_check.json",
    "tae_strategic_performance_audit.json",
    "bot_status.txt",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_age_seconds(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        return round(time.time() - path.stat().st_mtime, 1)
    except OSError:
        return None


def _process_running(pattern: str) -> bool:
    """Return True if a process matching pattern is running (read-only probe)."""
    for cmd in (
        ["pgrep", "-f", pattern],
        ["/usr/bin/pgrep", "-f", pattern],
    ):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False


def _process_status_label(running: bool) -> str:
    return "RUNNING" if running else "STOPPED"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid_file(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


def _probe_controller_runtime(root: Path) -> dict[str, Any]:
    bot_pid = _read_pid_file(root / BOT_PID_FILE)
    dashboard_pid = _read_pid_file(root / DASHBOARD_PID_FILE)
    dash_status_path = root / DASHBOARD_STATUS_FILE
    dashboard_status_file_value = (
        dash_status_path.read_text(encoding="utf-8").strip()
        if dash_status_path.is_file()
        else "UNKNOWN"
    )
    port_open = _port_in_use(DASHBOARD_PORT)
    bot_pid_alive = bot_pid is not None and _pid_alive(bot_pid)
    dashboard_pid_alive = dashboard_pid is not None and _pid_alive(dashboard_pid)
    return {
        "bot_pid": bot_pid,
        "bot_pid_alive": bot_pid_alive,
        "dashboard_pid": dashboard_pid,
        "dashboard_pid_alive": dashboard_pid_alive,
        "dashboard_port_open": port_open,
        "dashboard_status_file_value": dashboard_status_file_value,
    }


def _parse_market_session_guard_log(root: Path) -> dict[str, Any]:
    path = root / SESSION_GUARD_LOG
    if not path.is_file():
        return {"present": False, "last_line": None}

    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        return {"present": True, "last_line": None}

    last = lines[-1]
    parsed: dict[str, Any] = {"present": True, "last_line": last}
    for key in (
        "START_REASON",
        "BOT_ACTION",
        "DASHBOARD_ACTION",
        "BOT",
        "DASHBOARD",
        "OPEN",
        "DRY_RUN",
    ):
        match = re.search(rf"{key}=([^ ]+)", last)
        if match:
            parsed[key.lower()] = match.group(1)
    return parsed


def _derive_bot_status_effective(
    *,
    bot_process_running: bool,
    last_bot_log_age_seconds: float | None,
    live_signals_age_seconds: float | None,
    bot_status_file_value: str,
) -> tuple[str, bool]:
    """
    Effective bot status: process + fresh logs override stale bot_status.txt.
    Returns (effective_status, file_stale).
    """
    logs_recent = (
        last_bot_log_age_seconds is not None
        and last_bot_log_age_seconds <= BOT_LOG_FRESH_SECONDS
    )
    signals_recent = (
        live_signals_age_seconds is not None
        and live_signals_age_seconds <= ARTIFACT_FRESH_SECONDS
    )

    file_upper = str(bot_status_file_value or "UNKNOWN").upper()

    if bot_process_running and logs_recent:
        effective = "RUNNING"
    elif bot_process_running and signals_recent:
        effective = "RUNNING"
    elif bot_process_running:
        effective = "RUNNING"
    elif logs_recent or signals_recent:
        effective = "RUNNING"
    elif file_upper == "RUNNING":
        effective = "UNKNOWN"
    elif file_upper == "STOPPED":
        effective = "STOPPED"
    else:
        effective = "UNKNOWN"

    file_stale = file_upper != effective and effective in {"RUNNING", "STOPPED", "UNKNOWN"}
    if file_upper == "STOPPED" and effective == "RUNNING":
        file_stale = True

    return effective, file_stale


def _market_readiness(root: Path, runtime: dict[str, Any], advisory: dict[str, Any]) -> dict[str, Any]:
    local_now = datetime.now().astimezone()
    market_statuses: dict[str, Any] = {}
    any_open = False
    open_markets: list[str] = []

    try:
        from markets.market_hours import get_market_statuses, get_open_markets

        market_statuses = get_market_statuses()
        open_markets = get_open_markets()
        any_open = bool(open_markets)
    except Exception as exc:
        market_statuses = {"error": str(exc)}

    guard = runtime.get("session_guard") or {}
    start_reason = str(guard.get("start_reason") or "")
    bot_effective = runtime.get("bot_status_effective", "UNKNOWN")
    dashboard_running = runtime.get("dashboard_process_status") == "RUNNING"
    advisory_valid = advisory.get("present") and advisory.get("action")
    x8_active = bool(runtime.get("advisory_status", {}).get("block_new_buy") is not None)
    x8_blocks = bool(runtime.get("advisory_status", {}).get("block_new_buy"))

    bot_stopped_expected = (
        not any_open
        and start_reason == "all_markets_closed"
        and bot_effective == "STOPPED"
    )
    dashboard_stopped_expected = bot_stopped_expected and not dashboard_running

    x9 = runtime.get("x9_readiness") or {}
    shadow_csv_exists = (root / "tae_shadow_validation_events.csv").is_file()
    ledger_wired = x9.get("live_bot_wired") is True
    buy_can_log = ledger_wired and x9.get("ledger_module_present") and bot_effective == "RUNNING"

    warnings: list[str] = []
    notes: list[str] = []

    if bot_stopped_expected:
        notes.append(
            "Bot STOPPED is expected overnight: market_session_guard skips start when "
            "all markets are closed (startup_runner.sh behavior)."
        )
    if dashboard_stopped_expected:
        notes.append(
            "Dashboard STOPPED is expected overnight — session guard starts it when a market opens."
        )

    if bot_effective == "RUNNING" and not any_open:
        pre_open = [
            name
            for name, cfg_open in market_statuses.items()
            if isinstance(cfg_open, bool) and not cfg_open and name in {"US", "EU", "UK"}
        ]
        if pre_open:
            warnings.append(
                f"Bot RUNNING before/at market edge — waiting for session: {', '.join(pre_open)}"
            )

    if runtime.get("bot_status_file_stale"):
        warnings.append(
            f"bot_status.txt stale ({runtime.get('bot_status_file_value')}) — "
            f"using effective status {bot_effective}"
        )

    if not dashboard_running and not dashboard_stopped_expected:
        warnings.append("Dashboard not detected running (unexpected).")

    if bot_effective != "RUNNING" and any_open and not bot_stopped_expected:
        warnings.append("Market session open but bot is not RUNNING — investigate startup.")

    if not advisory_valid:
        warnings.append("tae_live_advisory.json missing or invalid.")

    if bot_stopped_expected and not any_open:
        verdict = "READY" if advisory_valid else "WARNING"
    elif bot_effective == "RUNNING" and advisory_valid:
        verdict = "READY"
    elif any_open and bot_effective != "RUNNING":
        verdict = "WARNING"
    elif warnings:
        verdict = "WARNING"
    else:
        verdict = "READY"

    if bot_stopped_expected and not any_open:
        next_action = "WAIT_FOR_MARKET_OPEN_THEN_SESSION_GUARD_START"
    elif bot_effective != "RUNNING" and any_open:
        next_action = "START_BOT_NOW_MARKET_IS_OPEN"
    elif bot_effective != "RUNNING":
        next_action = "START_BOT_BEFORE_MARKET_OPEN"
    elif x8_blocks:
        next_action = "MARKET_OPEN_WATCH_ONLY_NO_NEW_BUY"
    elif not shadow_csv_exists and ledger_wired:
        next_action = "MARKET_OPEN_COLLECT_X9_SHADOW_EVENTS"
    elif any_open:
        next_action = "MARKET_OPEN_MONITOR_SIGNALS_AND_LEDGER"
    else:
        next_action = "MONITOR_MARKET_OPEN"

    return {
        "local_time": local_now.isoformat(),
        "local_timezone": str(local_now.tzinfo),
        "market_statuses": market_statuses,
        "open_markets": open_markets,
        "any_market_open": any_open,
        "session_guard_start_reason": start_reason or None,
        "session_guard_last_line": guard.get("last_line"),
        "bot_stopped_expected": bot_stopped_expected,
        "dashboard_stopped_expected": dashboard_stopped_expected,
        "bot_running_before_open": bot_effective == "RUNNING" and not any_open,
        "dashboard_running": dashboard_running,
        "advisory_valid": bool(advisory_valid),
        "x8_risk_gate_active": x8_active,
        "x8_blocks_new_buy": x8_blocks,
        "x9_ledger_present": x9.get("ledger_module_present"),
        "x9_report_present": x9.get("report_script_present"),
        "shadow_events_csv_exists": shadow_csv_exists,
        "buy_path_will_log_on_open": ledger_wired and x9.get("ledger_module_present"),
        "x9_readiness_label": x9.get("readiness_label"),
        "notes": notes,
        "warnings": warnings,
        "verdict": verdict,
        "next_action_for_market_open": next_action,
    }


def _x9_readiness(root: Path) -> dict[str, Any]:
    ledger_path = root / SHADOW_LEDGER_MODULE
    report_path = root / SHADOW_REPORT_SCRIPT
    live_bot_path = root / LIVE_BOT_SCRIPT
    events_path = root / "tae_shadow_validation_events.csv"

    wired = False
    if live_bot_path.is_file():
        try:
            source = live_bot_path.read_text(encoding="utf-8")
            wired = all(
                fn in source
                for fn in (
                    "log_buy_allowed",
                    "log_buy_blocked_by_tae",
                    "log_buy_skipped_other_reason",
                )
            )
        except OSError:
            wired = False

    events_count = 0
    if events_path.is_file():
        events_count = len(load_shadow_events(events_path))

    if not ledger_path.is_file() or not report_path.is_file():
        label = "MISSING"
        message = "X.9 ledger modules missing."
    elif not wired:
        label = "MISSING"
        message = "live_bot.py missing shadow ledger hooks."
    elif events_count == 0:
        label = "NO_EVENTS_YET"
        message = "X.9 ledger ready; no runtime BUY events yet."
    else:
        label = "READY"
        message = f"X.9 ledger active with {events_count} event(s)."

    return {
        "ledger_module_present": ledger_path.is_file(),
        "report_script_present": report_path.is_file(),
        "live_bot_wired": wired,
        "shadow_events_csv_exists": events_path.is_file(),
        "shadow_events_count": events_count,
        "readiness_label": label,
        "message": message,
    }


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "invalid root"
    return payload, None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.median(values), 4)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 4)


def _outlier_warning(values: list[float], label: str) -> str | None:
    if len(values) < 3:
        return None
    med = statistics.median(values)
    if med == 0:
        mx = max(values)
        if mx > 1000:
            return f"{label}: extreme values detected (max={mx:.2f}, median=0)"
        return None
    mx = max(values)
    if mx > med * 10:
        return f"{label}: outlier detected (max={mx:.2f} vs median={med:.2f})"
    return None


def _read_git_status(root: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-b"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return {"available": False, "error": proc.stderr.strip() or "git failed"}
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        branch = lines[0] if lines else ""
        changes = lines[1:]
        return {
            "available": True,
            "branch_line": branch,
            "dirty_file_count": len(changes),
            "working_tree_clean": len(changes) == 0,
            "changes_preview": changes[:10],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}


def _discover_artifacts(root: Path) -> dict[str, Any]:
    found: list[str] = []
    missing: list[str] = []
    for name in CORE_ARTIFACTS:
        if (root / name).is_file():
            found.append(name)
        else:
            missing.append(name)

    globbed: set[str] = set()
    for pattern in ARTIFACT_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                globbed.add(path.name)

    return {
        "core_found": found,
        "core_missing": missing,
        "glob_matches": sorted(globbed),
        "total_artifact_files": len(found) + len(globbed),
    }


def _portfolio_financials(root: Path) -> dict[str, Any]:
    path = root / "portfolio.csv"
    result: dict[str, Any] = {
        "portfolio_readable": False,
        "cash_available": None,
        "open_positions_count": 0,
        "open_positions": [],
        "portfolio_value_estimated": None,
        "realized_pnl": None,
        "unrealized_pnl": None,
        "daily_pnl": None,
        "total_pnl": None,
        "profit_pct": None,
        "warnings": [],
        "calculation_notes": [],
    }
    if not path.is_file():
        result["warnings"].append("portfolio.csv missing")
        return result

    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        result["warnings"].append(f"portfolio.csv unreadable: {exc}")
        return result

    if not rows:
        result["warnings"].append("portfolio.csv empty")
        return result

    result["portfolio_readable"] = True
    spent = received = deposited = 0.0
    positions: dict[str, dict[str, Any]] = {}
    realized = 0.0
    today_str = date.today().isoformat()
    daily_pnl = 0.0
    daily_rows = 0

    for row in rows:
        action = str(row.get("Action", "")).upper()
        ticker = str(row.get("Ticker", "")).strip()
        price = _parse_float(row.get("Price")) or 0.0
        shares = _parse_float(row.get("Shares")) or 0.0
        pnl = _parse_float(row.get("PnL"))
        row_date = str(row.get("Date", ""))[:10]

        if row_date == today_str and pnl is not None:
            daily_pnl += pnl
            daily_rows += 1

        if action == "BUY":
            spent += price * shares
            if ticker:
                bucket = positions.setdefault(
                    ticker,
                    {"buy_shares": 0.0, "sell_shares": 0.0, "last_buy_row": None},
                )
                bucket["buy_shares"] += shares
                bucket["last_buy_row"] = row
        elif action == "SELL":
            received += price * shares
            if pnl is not None:
                realized += pnl
            if ticker and ticker in positions:
                positions[ticker]["sell_shares"] += shares
        elif action == "DEPOSIT":
            deposited += price * shares

    cash = STARTING_CAPITAL + deposited - spent + received
    result["cash_available"] = round(cash, 2)

    open_positions: list[dict[str, Any]] = []
    unrealized = 0.0
    positions_value = 0.0
    missing_marks = 0

    for ticker, bucket in positions.items():
        open_shares = bucket["buy_shares"] - bucket["sell_shares"]
        if open_shares <= 1e-9:
            continue
        last = bucket["last_buy_row"] or {}
        invested = _parse_float(last.get("Invested"))
        current_value = _parse_float(last.get("Current_Value"))
        pnl_pct = _parse_float(last.get("PnL_%"))
        pnl = _parse_float(last.get("PnL"))
        current_price = _parse_float(last.get("Current_Price"))

        if pnl is not None:
            unrealized += pnl
        elif invested is not None and current_value is not None:
            unrealized += current_value - invested

        if current_value is not None:
            positions_value += current_value
        elif invested is not None:
            positions_value += invested
            missing_marks += 1

        open_positions.append(
            {
                "ticker": ticker,
                "shares": round(open_shares, 4),
                "pnl": round(pnl, 4) if pnl is not None else None,
                "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
                "current_price": current_price,
            }
        )

    result["open_positions_count"] = len(open_positions)
    result["open_positions"] = open_positions
    result["realized_pnl"] = round(realized, 4)
    result["unrealized_pnl"] = round(unrealized, 4)
    result["total_pnl"] = round(realized + unrealized, 4)
    result["portfolio_value_estimated"] = round(cash + positions_value, 2)
    result["profit_pct"] = (
        round((result["total_pnl"] / STARTING_CAPITAL) * 100, 4)
        if result["total_pnl"] is not None
        else None
    )

    if daily_rows:
        result["daily_pnl"] = round(daily_pnl, 4)
        result["calculation_notes"].append(
            f"daily_pnl estimated from {daily_rows} portfolio row(s) on {today_str}"
        )
    else:
        result["daily_pnl"] = None
        result["calculation_notes"].append(
            f"no portfolio rows dated {today_str}; daily_pnl not estimated"
        )

    result["calculation_notes"].append("portfolio_value_estimated = cash + sum(Current_Value) marks")
    result["calculation_notes"].append("marks are estimated from portfolio.csv, not live broker")
    if missing_marks:
        result["warnings"].append(
            f"{missing_marks} open position(s) missing Current_Value; used Invested fallback"
        )

    return result


def _live_signals_today(root: Path) -> dict[str, Any]:
    path = root / "live_signals.csv"
    section: dict[str, Any] = {
        "signals_present": False,
        "total_signals": 0,
        "strong_buy_count": 0,
        "take_profit_count": 0,
        "wait_count": 0,
        "other_count": 0,
        "top_strong_buy": [],
        "top_take_profit": [],
        "latest_signal_time": None,
        "warnings": [],
    }
    if not path.is_file():
        section["warnings"].append("live_signals.csv missing")
        return section

    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        section["warnings"].append(f"live_signals.csv unreadable: {exc}")
        return section

    section["signals_present"] = True
    section["total_signals"] = len(rows)
    strong: list[dict[str, Any]] = []
    take_profit: list[dict[str, Any]] = []
    latest_time = None

    for row in rows:
        signal = str(row.get("Signal", "")).upper()
        score = _parse_float(row.get("Score")) or 0.0
        ticker = str(row.get("Ticker", "")).strip()
        price = _parse_float(row.get("Price"))
        ts = str(row.get("Time", "")).strip() or None
        if ts and (latest_time is None or ts > latest_time):
            latest_time = ts

        if signal == "STRONG BUY":
            section["strong_buy_count"] += 1
            strong.append({"ticker": ticker, "score": score, "price": price})
        elif signal == "TAKE PROFIT":
            section["take_profit_count"] += 1
            take_profit.append({"ticker": ticker, "score": score, "price": price})
        elif signal == "WAIT":
            section["wait_count"] += 1
        else:
            section["other_count"] += 1

    strong.sort(key=lambda x: (-(x["score"] or 0), x["ticker"]))
    take_profit.sort(key=lambda x: (-(x["score"] or 0), x["ticker"]))
    section["top_strong_buy"] = strong[:10]
    section["top_take_profit"] = take_profit[:10]
    section["latest_signal_time"] = latest_time
    return section


def _runtime_status(root: Path) -> dict[str, Any]:
    bot_path = root / BOT_STATUS_FILE
    bot_status_file_value = (
        bot_path.read_text(encoding="utf-8").strip() if bot_path.is_file() else "UNKNOWN"
    )

    controller = _probe_controller_runtime(root)
    session_guard = _parse_market_session_guard_log(root)

    bot_process_running = _process_running(LIVE_BOT_SCRIPT) or controller["bot_pid_alive"]
    dashboard_process_running = (
        _process_running(DASHBOARD_SCRIPT)
        or _process_running("streamlit run dashboard_v2.py")
        or _process_running("streamlit")
        or controller["dashboard_pid_alive"]
        or controller["dashboard_port_open"]
    )

    last_bot_log_age_seconds = _file_age_seconds(root / BOT_LOG_FILE)
    live_signals_age_seconds = _file_age_seconds(root / "live_signals.csv")
    portfolio_age_seconds = _file_age_seconds(root / "portfolio.csv")

    bot_status_effective, bot_status_file_stale = _derive_bot_status_effective(
        bot_process_running=bot_process_running,
        last_bot_log_age_seconds=last_bot_log_age_seconds,
        live_signals_age_seconds=live_signals_age_seconds,
        bot_status_file_value=bot_status_file_value,
    )

    x9_readiness = _x9_readiness(root)

    health, health_err = _load_json(root / "tae_quick_health_check.json")
    advisory_payload, advisory_err = _load_json(root / "tae_live_advisory.json")
    advisory_state = load_live_advisory(root / "tae_live_advisory.json")
    block_new_buy, block_reason = should_block_new_buy(advisory_state)

    return {
        "bot_status": bot_status_effective,
        "bot_process_status": _process_status_label(bot_process_running),
        "dashboard_process_status": _process_status_label(dashboard_process_running),
        "bot_status_file_value": bot_status_file_value,
        "bot_status_file_stale": bot_status_file_stale,
        "bot_status_effective": bot_status_effective,
        "last_bot_log_age_seconds": last_bot_log_age_seconds,
        "live_signals_age_seconds": live_signals_age_seconds,
        "portfolio_age_seconds": portfolio_age_seconds,
        "bot_log_fresh_threshold_seconds": BOT_LOG_FRESH_SECONDS,
        "bot_pid": controller["bot_pid"],
        "bot_pid_alive": controller["bot_pid_alive"],
        "dashboard_pid": controller["dashboard_pid"],
        "dashboard_pid_alive": controller["dashboard_pid_alive"],
        "dashboard_port_open": controller["dashboard_port_open"],
        "dashboard_status_file_value": controller["dashboard_status_file_value"],
        "session_guard": session_guard,
        "dashboard_status": _process_status_label(dashboard_process_running),
        "git_status": _read_git_status(root),
        "x9_readiness": x9_readiness,
        "advisory_status": {
            "load_status": advisory_state.load_status,
            "action": advisory_state.action,
            "confidence": advisory_state.confidence,
            "block_new_buy": block_new_buy,
            "block_reason": block_reason,
            "artifact_error": advisory_err,
        },
        "health_status": {
            "present": health is not None,
            "verdict": (health or {}).get("verdict"),
            "runtime_health_status": (health or {}).get("runtime_health_status"),
            "warning_count": len((health or {}).get("warnings") or []),
            "artifact_error": health_err,
        },
        "live_advisory_generated_at": (advisory_payload or {}).get("generated_at"),
    }


def _tae_advisory_section(root: Path) -> dict[str, Any]:
    payload, err = _load_json(root / "tae_live_advisory.json")
    if not payload:
        return {"present": False, "error": err, "warnings": ["tae_live_advisory.json unavailable"]}

    adv = payload.get("advisory") or {}
    runtime = payload.get("runtime_snapshot") or {}
    block_new_buy, block_reason = should_block_new_buy(
        load_live_advisory(root / "tae_live_advisory.json")
    )

    practical = []
    action = str(adv.get("action") or "NO_ACTION")
    strong_buys = int(runtime.get("strong_buy_signal_count") or 0)

    if action == "RISK_ADVISORY" and block_new_buy:
        practical.append(
            "RISK_ADVISORY active: new BUY orders would be blocked by X.8 gate in live_bot."
        )
        if strong_buys > 0:
            practical.append(
                f"{strong_buys} STRONG BUY signal(s) present — TAE would block new entries today."
            )
    elif action == "BUY_ADVISORY":
        practical.append("BUY_ADVISORY: supportive context only; no auto-buy.")
    elif action == "SELL_ADVISORY":
        practical.append("SELL_ADVISORY: review exits only; no auto-sell.")
    else:
        practical.append("NO_ACTION / neutral advisory — live bot uses inline rules only.")

    return {
        "present": True,
        "action": action,
        "confidence": adv.get("confidence"),
        "reasons": list(adv.get("reasons") or [])[:15],
        "blockers": list(adv.get("blockers") or [])[:15],
        "blocks_new_buy": block_new_buy,
        "block_reason": block_reason,
        "practical_meaning_today": practical,
        "runtime_snapshot": runtime,
    }


def _shadow_validation_section(root: Path) -> dict[str, Any]:
    events_path = root / "tae_shadow_validation_events.csv"
    summary_path = root / "tae_shadow_validation_summary.json"

    if summary_path.is_file():
        summary, _ = _load_json(summary_path)
    else:
        events = load_shadow_events(events_path)
        summary = build_shadow_summary(events)

    total = int(summary.get("total_events") or 0)
    notes = []
    if not events_path.is_file():
        notes.append(
            "tae_shadow_validation_events.csv missing — X.9 ledger connected in live_bot but "
            "no events recorded yet; cannot evaluate gate performance."
        )
    elif total == 0:
        notes.append(
            "Ledger file exists but empty — bot may be STOPPED or no STRONG BUY evaluations occurred."
        )

    return {
        "present": events_path.is_file() or summary_path.is_file(),
        "total_events": total,
        "buy_allowed": summary.get("buy_allowed", 0),
        "buy_blocked_by_tae": summary.get("buy_blocked_by_tae", 0),
        "buy_skipped_other_reason": summary.get("buy_skipped_other_reason", 0),
        "block_rate": summary.get("block_rate", 0.0),
        "outcome_tracking_status": summary.get("outcome_tracking_status", "PENDING_NEXT_PHASE"),
        "top_block_reasons": summary.get("top_block_reasons", {}),
        "gate_evaluation_ready": total >= 5,
        "notes": notes,
    }


def _collect_strategy_records(root: Path) -> dict[str, Any]:
    hist, _ = _load_json(root / "tae_historical_results_analysis.json")
    registry, _ = _load_json(root / "tae_candidate_strategy_registry.json")
    ranking, _ = _load_json(root / "tae_continuous_strategy_ranking.json")
    discovery, _ = _load_json(root / "tae_strategy_discovery.json")
    evidence, _ = _load_json(root / "tae_evidence_engine_report.json")

    robust = list((hist or {}).get("robust_strategy_shortlist") or [])
    weak = list((hist or {}).get("weak_strategy_shortlist") or [])
    top20 = list((hist or {}).get("top_20_global_results") or [])
    candidates = list((registry or {}).get("candidates") or [])
    rankings = list((ranking or {}).get("rankings") or [])

    robust.sort(key=lambda x: -(float(x.get("robustness_score") or 0)))

    accepted_statuses = {"PROMOTED", "ACCEPTED", "ROBUST", "LIVE_BASELINE"}
    rejected_statuses = {"REJECTED", "WEAK", "RETIRED"}

    registry_accepted = [
        c for c in candidates if str(c.get("status", "")).upper() in accepted_statuses
    ]
    registry_rejected = [
        c for c in candidates if str(c.get("status", "")).upper() in rejected_statuses
    ]
    registry_paper = [
        c
        for c in candidates
        if "PAPER" in str(c.get("status", "")).upper()
        or str(c.get("promotion_readiness", "")).upper() in {"PAPER_TRACKING", "PAPER_CANDIDATE"}
    ]

    all_ids: set[str] = set()
    for item in robust + weak + top20 + rankings:
        sid = item.get("strategy_id") or item.get("candidate_id")
        if sid:
            all_ids.add(str(sid))
    for c in candidates:
        if c.get("candidate_id"):
            all_ids.add(str(c["candidate_id"]))

    profit_values = [
        float(x["avg_profit_pct"])
        for x in robust
        if _parse_float(x.get("avg_profit_pct")) is not None
    ]
    sharpe_values = [
        float(x["avg_sharpe"])
        for x in robust
        if _parse_float(x.get("avg_sharpe")) is not None
    ]

    top_slices = {}
    for n in (1, 5, 10, 100, 200):
        available = len(robust)
        if available >= n:
            slice_rows = robust[:n]
            status = "OK"
        elif available > 0:
            slice_rows = robust[:available]
            status = "INSUFFICIENT_DATA"
        else:
            slice_rows = []
            status = "INSUFFICIENT_DATA"

        pcts = [
            float(r["avg_profit_pct"])
            for r in slice_rows
            if _parse_float(r.get("avg_profit_pct")) is not None
        ]
        shps = [
            float(r["avg_sharpe"])
            for r in slice_rows
            if _parse_float(r.get("avg_sharpe")) is not None
        ]
        top_slices[f"top_{n}"] = {
            "requested": n,
            "strategies_available": available,
            "strategies_used": len(slice_rows),
            "status": status,
            "strategy_ids": [r.get("strategy_id") for r in slice_rows],
            "median_profit_pct": _median(pcts),
            "median_sharpe": _median(shps),
            "profit_pct_p25": _percentile(pcts, 25),
            "profit_pct_p75": _percentile(pcts, 75),
            "outlier_warning": _outlier_warning(pcts, f"top_{n} profit_pct"),
        }

    return {
        "sources_loaded": {
            "historical_results_analysis": hist is not None,
            "candidate_strategy_registry": registry is not None,
            "continuous_strategy_ranking": ranking is not None,
            "strategy_discovery": discovery is not None,
            "evidence_engine_report": evidence is not None,
        },
        "counts": {
            "unique_strategy_ids_detected": len(all_ids),
            "historical_research_jobs_total": (hist or {}).get("jobs_total"),
            "robust_shortlist_count": len(robust),
            "weak_shortlist_count": len(weak),
            "top_20_global_results_count": len(top20),
            "registry_candidates_count": len(candidates),
            "registry_accepted_count": len(registry_accepted),
            "registry_rejected_count": len(registry_rejected),
            "registry_paper_count": len(registry_paper),
            "continuous_ranking_count": len(rankings),
            "discovery_hypothesis_count": (discovery or {}).get("hypothesis_count"),
            "discovery_candidate_count": (discovery or {}).get("candidate_count"),
            "evidence_confirmed": (evidence or {}).get("confirmed_count"),
            "evidence_rejected": (evidence or {}).get("rejected_count"),
            "evidence_inconclusive": (evidence or {}).get("inconclusive_count"),
        },
        "robust_median_profit_pct": _median(profit_values),
        "robust_median_sharpe": _median(sharpe_values),
        "robust_profit_pct_p25": _percentile(profit_values, 25),
        "robust_profit_pct_p75": _percentile(profit_values, 75),
        "outlier_warning": _outlier_warning(profit_values, "robust avg_profit_pct"),
        "top_slices": top_slices,
        "top_1_strategy_id": robust[0].get("strategy_id") if robust else None,
        "ranking_top": rankings[:5],
        "registry_summary": [
            {
                "candidate_id": c.get("candidate_id"),
                "status": c.get("status"),
                "promotion_readiness": c.get("promotion_readiness"),
            }
            for c in candidates
        ],
    }


def _counterfactual_section(strategy: dict[str, Any], financial: dict[str, Any]) -> dict[str, Any]:
    runtime_total_pnl = financial.get("total_pnl")
    groups: dict[str, Any] = {}

    for key, slice_data in strategy.get("top_slices", {}).items():
        entry = dict(slice_data)
        med_profit = entry.get("median_profit_pct")
        if runtime_total_pnl is not None and med_profit is not None:
            entry["vs_runtime_note"] = (
                f"Historical backtest median profit_pct ({med_profit}%) is not directly "
                f"comparable to live paper total_pnl ({runtime_total_pnl}); different units/horizons."
            )
        else:
            entry["vs_runtime_note"] = "INSUFFICIENT_DATA for runtime comparison"
        groups[key] = entry

    return {
        "methodology": "median-first on robust_strategy_shortlist; not live execution simulation",
        "runtime_actual_total_pnl": runtime_total_pnl,
        "groups": groups,
        "insufficient_for_top_100": strategy.get("counts", {}).get("robust_shortlist_count", 0) < 100,
        "insufficient_for_top_200": strategy.get("counts", {}).get("robust_shortlist_count", 0) < 200,
    }


def _learning_section(root: Path) -> dict[str, Any]:
    evidence, _ = _load_json(root / "tae_evidence_engine_report.json")
    meta, _ = _load_json(root / "tae_meta_intelligence.json")
    meta_evo, _ = _load_json(root / "tae_meta_evolution.json")
    ranking, _ = _load_json(root / "tae_continuous_strategy_ranking.json")
    hist, _ = _load_json(root / "tae_historical_results_analysis.json")
    health, _ = _load_json(root / "tae_quick_health_check.json")
    advisory, _ = _load_json(root / "tae_live_advisory.json")

    today = date.today().isoformat()
    generated_today: list[str] = []
    for name in CORE_ARTIFACTS:
        if not name.endswith(".json"):
            continue
        path = root / name
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                gen = str(payload.get("generated_at", ""))[:10]
                if gen == today:
                    generated_today.append(name)
            except (json.JSONDecodeError, OSError):
                pass

    obs = (meta or {}).get("strategic_observations") or {}
    return {
        "evidence_status": {
            "verdict": (evidence or {}).get("verdict"),
            "confirmed": (evidence or {}).get("confirmed_count"),
            "inconclusive": (evidence or {}).get("inconclusive_count"),
            "rejected": (evidence or {}).get("rejected_count"),
            "contradictions": len((evidence or {}).get("contradictions") or []),
        },
        "meta_intelligence": {
            "verdict": (meta or {}).get("verdict"),
            "overall_confidence": obs.get("overall_ecosystem_confidence"),
            "top_ranked_strategy_id": obs.get("top_ranked_strategy_id"),
            "highest_quality_strategy": obs.get("highest_quality_strategy"),
            "weakest_strategy": obs.get("weakest_strategy"),
        },
        "meta_evolution_present": meta_evo is not None,
        "strategy_ranking": {
            "verdict": (ranking or {}).get("verdict"),
            "count": len((ranking or {}).get("rankings") or []),
            "top": ((ranking or {}).get("rankings") or [])[:3],
        },
        "historical_results_analysis": {
            "verdict": (hist or {}).get("verdict"),
            "jobs_total": (hist or {}).get("jobs_total"),
            "robust_count": len((hist or {}).get("robust_strategy_shortlist") or []),
        },
        "advisory_bridge": {
            "action": ((advisory or {}).get("advisory") or {}).get("action"),
            "confidence": ((advisory or {}).get("advisory") or {}).get("confidence"),
            "generated_at": (advisory or {}).get("generated_at"),
        },
        "learning_status": {
            "quick_health_verdict": (health or {}).get("verdict"),
            "produces_new_signals": bool(generated_today),
            "artifacts_generated_today": generated_today,
            "static_reports_only": len(generated_today) == 0,
        },
    }


def _profit_advisory(
    runtime: dict[str, Any],
    financial: dict[str, Any],
    signals: dict[str, Any],
    advisory: dict[str, Any],
    shadow: dict[str, Any],
    strategy: dict[str, Any],
    learning: dict[str, Any],
) -> dict[str, Any]:
    recs: list[str] = []
    watch: list[str] = []
    missing_data: list[str] = []
    risks: list[str] = []

    bot = str(runtime.get("bot_status_effective") or runtime.get("bot_status", "")).upper()
    if bot == "STOPPED":
        recs.append("COLLECT_MORE_DATA")
        watch.append("Bot STOPPED — live results limited until next market cycle run.")
    elif bot == "UNKNOWN":
        watch.append("Bot status UNKNOWN — verify process and bot_output.log freshness.")
    else:
        watch.append("Bot running — monitor live_signals.csv and shadow ledger after cycle.")

    if advisory.get("blocks_new_buy"):
        recs.append("DO_NOT_BUY")
        risks.append(advisory.get("block_reason") or "RISK_ADVISORY blocks new BUY")

    if signals.get("take_profit_count", 0) > 0:
        recs.append("TAKE_PROFIT_REVIEW")
        watch.append(f"{signals['take_profit_count']} TAKE PROFIT signal(s) — manual exit review only.")

    if signals.get("strong_buy_count", 0) > 0 and advisory.get("blocks_new_buy"):
        watch.append("STRONG BUY present but TAE would block new entries — counterfactual gap to track.")

    if (financial.get("unrealized_pnl") or 0) < -500:
        recs.append("REDUCE_RISK")
        risks.append("Open unrealized PnL materially negative (estimated).")

    if learning.get("evidence_status", {}).get("contradictions", 0) > 0:
        recs.append("INVESTIGATE_WARNINGS")

    if not shadow.get("gate_evaluation_ready"):
        recs.append("COLLECT_MORE_DATA")
        missing_data.append("X.9 shadow ledger needs more BUY evaluation events for gate attribution.")

    if strategy.get("counts", {}).get("robust_shortlist_count", 0) < 100:
        missing_data.append(
            f"Only {strategy['counts']['robust_shortlist_count']} robust strategies — "
            "top_100/top_200 counterfactuals not available."
        )

    if strategy.get("top_1_strategy_id"):
        recs.append("CONSIDER_TOP_STRATEGY_ALIGNMENT")
        watch.append(
            f"Top robust historical strategy: {strategy['top_1_strategy_id']} — "
            "alignment review only, no auto switch."
        )

    recs = list(dict.fromkeys(recs))
    return {
        "recommendations": recs or ["WATCH"],
        "watch_tomorrow": watch,
        "profit_opportunities": [
            "Review TAKE PROFIT candidates before next session.",
            "Accumulate shadow ledger events to measure avoided/missed BUY outcomes.",
            "Compare live paper PnL vs robust-strategy medians once outcome tracking lands (X.10).",
        ],
        "risk_blockers": risks,
        "missing_data_for_better_decisions": missing_data,
        "advisory_only": True,
        "no_auto_execution": True,
    }


def _cannot_conclude(
    artifacts: dict[str, Any],
    shadow: dict[str, Any],
    strategy: dict[str, Any],
    financial: dict[str, Any],
    runtime: dict[str, Any],
) -> list[str]:
    gaps: list[str] = []
    if "tae_shadow_validation_events.csv" in artifacts.get("core_missing", []):
        gaps.append("Gate performance: no shadow validation events yet.")
    elif not shadow.get("gate_evaluation_ready"):
        gaps.append("Gate block/allow attribution: insufficient shadow events (<5).")
    if strategy.get("counts", {}).get("robust_shortlist_count", 0) < 100:
        gaps.append("Counterfactual top_100/top_200: not enough robust strategies in artifacts.")
    if financial.get("daily_pnl") is None:
        gaps.append("Daily PnL: no portfolio activity dated today.")
    if str(runtime.get("bot_status_effective") or runtime.get("bot_status", "")).upper() == "STOPPED":
        gaps.append("Live intraday behavior: bot STOPPED limits same-day observations.")
    if runtime.get("bot_status_file_stale"):
        gaps.append(
            f"bot_status.txt stale ({runtime.get('bot_status_file_value')}) — "
            f"effective status is {runtime.get('bot_status_effective')}."
        )
    gaps.append("Forward PnL on blocked BUYs: outcome_tracking_status PENDING_NEXT_PHASE.")
    return gaps


def _final_verdict(
    runtime: dict[str, Any],
    financial: dict[str, Any],
    shadow: dict[str, Any],
    learning: dict[str, Any],
    artifacts: dict[str, Any],
    market_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    health = runtime.get("health_status") or {}
    verdict = "ECOSYSTEM_HEALTHY"
    warnings: list[str] = []

    if not health.get("present"):
        verdict = "INSUFFICIENT_DATA"
        warnings.append("tae_quick_health_check.json missing")
    elif str(health.get("verdict", "")).endswith("NOT_READY"):
        verdict = "WARNING"
        warnings.append(f"quick health: {health.get('verdict')}")

    if int(health.get("warning_count") or 0) >= 5:
        verdict = "WARNING" if verdict == "ECOSYSTEM_HEALTHY" else verdict
        warnings.append("elevated health warnings")

    adv = runtime.get("advisory_status") or {}
    if adv.get("block_new_buy"):
        verdict = "WARNING" if verdict == "ECOSYSTEM_HEALTHY" else verdict
        warnings.append("RISK_ADVISORY blocks new BUY")

    bot_effective = str(runtime.get("bot_status_effective") or runtime.get("bot_status", "")).upper()
    if bot_effective == "STOPPED":
        warnings.append("bot STOPPED — live observations limited")
    elif bot_effective == "UNKNOWN":
        warnings.append("bot status UNKNOWN — verify process vs bot_status.txt")

    if runtime.get("bot_status_file_stale"):
        warnings.append(
            f"bot_status.txt stale ({runtime.get('bot_status_file_value')}) "
            f"vs effective {bot_effective}"
        )

    daily = financial.get("daily_pnl")
    fin_today = "UNKNOWN"
    if daily is not None:
        fin_today = "POSITIVE" if daily > 0 else ("NEGATIVE" if daily < 0 else "FLAT")

    learning_progress = "STATIC"
    if learning.get("learning_status", {}).get("artifacts_generated_today"):
        learning_progress = "ACTIVE_TODAY"
    elif shadow.get("total_events", 0) > 0:
        learning_progress = "SHADOW_EVENTS_ACCUMULATING"

    next_action = "WATCH_AND_COLLECT_DATA"
    if market_readiness:
        next_action = market_readiness.get("next_action_for_market_open", next_action)
    if adv.get("block_new_buy"):
        next_action = "DO_NOT_OPEN_NEW_BUY_REVIEW_EXISTING"
    if learning_progress == "ACTIVE_TODAY":
        next_action = "REVIEW_TAE_ARTIFACTS"

    return {
        "ecosystem_verdict": verdict,
        "financial_result_today": fin_today,
        "learning_progress": learning_progress,
        "next_action": next_action,
        "warnings": warnings,
    }


def build_review(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    artifacts = _discover_artifacts(root)
    runtime = _runtime_status(root)
    financial = _portfolio_financials(root)
    signals = _live_signals_today(root)
    advisory = _tae_advisory_section(root)
    market_readiness = _market_readiness(root, runtime, advisory)
    shadow = _shadow_validation_section(root)
    strategy = _collect_strategy_records(root)
    counterfactual = _counterfactual_section(strategy, financial)
    learning = _learning_section(root)
    profit_adv = _profit_advisory(runtime, financial, signals, advisory, shadow, strategy, learning)
    cannot = _cannot_conclude(artifacts, shadow, strategy, financial, runtime)
    final = _final_verdict(runtime, financial, shadow, learning, artifacts, market_readiness)

    return {
        "schema": SCHEMA,
        "mode": MODE,
        "live_trading_impact": LIVE_TRADING_IMPACT,
        "generated_at": _utc_now_iso(),
        "artifacts_read": artifacts,
        "A_runtime_status": runtime,
        "Market_Readiness": market_readiness,
        "B_financial_status": financial,
        "C_live_signals_today": signals,
        "D_tae_advisory": advisory,
        "E_shadow_validation": shadow,
        "F_strategy_universe": strategy,
        "G_counterfactual_comparison": counterfactual,
        "H_learning_evidence_meta": learning,
        "I_profit_maximization_advisory": profit_adv,
        "cannot_conclude_yet": cannot,
        "J_final_verdict": final,
    }


def _md_list(items: list[str]) -> str:
    if not items:
        return "- (none)\n"
    return "".join(f"- {item}\n" for item in items)


def render_markdown(review: dict[str, Any]) -> str:
    rt = review["A_runtime_status"]
    market = review.get("Market_Readiness") or {}
    fin = review["B_financial_status"]
    sig = review["C_live_signals_today"]
    adv = review["D_tae_advisory"]
    sh = review["E_shadow_validation"]
    st = review["F_strategy_universe"]
    cf = review["G_counterfactual_comparison"]
    learn = review["H_learning_evidence_meta"]
    prof = review["I_profit_maximization_advisory"]
    final = review["J_final_verdict"]

    lines = [
        "# TAE Full Ecosystem Review",
        "",
        f"**Generated:** {review['generated_at']}  ",
        f"**Mode:** {review['mode']}  ",
        f"**Live trading impact:** {review['live_trading_impact']}",
        "",
        "## A. Runtime Status",
        f"- Bot effective: **{rt.get('bot_status_effective')}**",
        f"- Bot process: {rt.get('bot_process_status')}",
        f"- Dashboard process: {rt.get('dashboard_process_status')}",
        f"- Status file: {rt.get('bot_status_file_value')}"
        + (" (stale)" if rt.get("bot_status_file_stale") else ""),
        f"- Bot log age (s): {rt.get('last_bot_log_age_seconds')}",
        f"- Live signals age (s): {rt.get('live_signals_age_seconds')}",
        f"- Health: {rt.get('health_status', {}).get('verdict')}",
        f"- Advisory: {rt.get('advisory_status', {}).get('action')} "
        f"(blocks new BUY: {rt.get('advisory_status', {}).get('block_new_buy')})",
        f"- Git clean: {rt.get('git_status', {}).get('working_tree_clean')}",
        "",
        "## Market Readiness",
        f"- Local time: {market.get('local_time')}",
        f"- Verdict: **{market.get('verdict')}**",
        f"- Session guard reason: {market.get('session_guard_start_reason')}",
        f"- Bot stopped expected: {market.get('bot_stopped_expected')}",
        f"- Markets: {market.get('market_statuses')}",
        f"- Dashboard running: {market.get('dashboard_running')}",
        f"- X.8 blocks new BUY: {market.get('x8_blocks_new_buy')}",
        f"- X.9 ledger: {market.get('x9_readiness_label')}",
        f"- BUY path will log on open: {market.get('buy_path_will_log_on_open')}",
        f"- Next action: {market.get('next_action_for_market_open')}",
        "",
        "## B. Financial Status (estimated)",
        f"- Cash: {fin.get('cash_available')} USD",
        f"- Open positions: {fin.get('open_positions_count')}",
        f"- Portfolio value (est.): {fin.get('portfolio_value_estimated')} USD",
        f"- Realized PnL: {fin.get('realized_pnl')}",
        f"- Unrealized PnL: {fin.get('unrealized_pnl')}",
        f"- Daily PnL: {fin.get('daily_pnl')}",
        f"- Total PnL: {fin.get('total_pnl')} ({fin.get('profit_pct')}%)",
        "",
        "## C. Live Signals Today",
        f"- Total: {sig.get('total_signals')} | STRONG BUY: {sig.get('strong_buy_count')} | "
        f"TAKE PROFIT: {sig.get('take_profit_count')} | WAIT: {sig.get('wait_count')}",
        "",
        "## D. TAE Advisory",
        f"- Action: **{adv.get('action')}** | Confidence: {adv.get('confidence')}",
    ]
    for note in adv.get("practical_meaning_today") or []:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## E. X.9 Shadow Validation",
            f"- Events: {sh.get('total_events')} | Allowed: {sh.get('buy_allowed')} | "
            f"Blocked: {sh.get('buy_blocked_by_tae')} | Skipped: {sh.get('buy_skipped_other_reason')}",
            f"- Block rate: {sh.get('block_rate')}",
        ]
    )
    for note in sh.get("notes") or []:
        lines.append(f"- {note}")

    counts = st.get("counts") or {}
    lines.extend(
        [
            "",
            "## F. Strategy Universe",
            f"- Unique strategy IDs: {counts.get('unique_strategy_ids_detected')}",
            f"- Robust shortlist: {counts.get('robust_shortlist_count')}",
            f"- Weak shortlist: {counts.get('weak_shortlist_count')}",
            f"- Registry candidates: {counts.get('registry_candidates_count')}",
            f"- Median robust profit_pct: {st.get('robust_median_profit_pct')}",
            f"- Median robust Sharpe: {st.get('robust_median_sharpe')}",
        ]
    )

    lines.extend(["", "## G. Counterfactual (robust shortlist, median-first)"])
    for key, grp in (cf.get("groups") or {}).items():
        lines.append(
            f"- {key}: used {grp.get('strategies_used')}/{grp.get('requested')} | "
            f"median profit_pct={grp.get('median_profit_pct')} | "
            f"median Sharpe={grp.get('median_sharpe')} | status={grp.get('status')}"
        )

    lines.extend(
        [
            "",
            "## H. Learning / Evidence / Meta",
            f"- Evidence verdict: {learn.get('evidence_status', {}).get('verdict')}",
            f"- Meta confidence: {learn.get('meta_intelligence', {}).get('overall_confidence')}",
            f"- Ranking count: {learn.get('strategy_ranking', {}).get('count')}",
            f"- Artifacts generated today: {learn.get('learning_status', {}).get('artifacts_generated_today')}",
            "",
            "## I. Profit Maximization Advisory (no auto execution)",
        ]
    )
    lines.append(_md_list(prof.get("recommendations") or []))

    lines.extend(
        [
            "## J. Final Verdict",
            f"- **{final.get('ecosystem_verdict')}**",
            f"- Financial today: {final.get('financial_result_today')}",
            f"- Learning progress: {final.get('learning_progress')}",
            f"- Next action: {final.get('next_action')}",
            "",
            "## Cannot Conclude Yet",
        ]
    )
    lines.append(_md_list(review.get("cannot_conclude_yet") or []))
    lines.append("")
    return "\n".join(lines)


def persist_review(review: dict[str, Any], root: Path | str = ".") -> tuple[Path, Path]:
    root = Path(root)
    json_path = root / DEFAULT_JSON_OUT
    md_path = root / DEFAULT_MD_OUT
    json_path.write_text(
        json.dumps(review, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(review), encoding="utf-8")
    return json_path, md_path


def print_terminal_summary(review: dict[str, Any]) -> None:
    final = review["J_final_verdict"]
    rt = review["A_runtime_status"]
    market = review.get("Market_Readiness") or {}
    fin = review["B_financial_status"]
    sig = review["C_live_signals_today"]
    adv = review["D_tae_advisory"]
    sh = review["E_shadow_validation"]
    st = review["F_strategy_universe"]
    counts = st.get("counts") or {}
    x9 = rt.get("x9_readiness") or {}

    status_file_note = rt.get("bot_status_file_value", "UNKNOWN")
    if rt.get("bot_status_file_stale"):
        status_file_note = f"{status_file_note} stale"

    bot_label = rt.get("bot_status_effective", "UNKNOWN")
    dash_label = rt.get("dashboard_process_status", "UNKNOWN")
    if market.get("bot_stopped_expected"):
        bot_label = f"{bot_label} (expected — all markets closed)"
    if market.get("dashboard_stopped_expected"):
        dash_label = f"{dash_label} (expected — premarket)"

    print("")
    print("===== TAE FULL ECOSYSTEM REVIEW =====")
    print(f"Verdict: {final.get('ecosystem_verdict')}")
    print(f"Bot: {bot_label}")
    print(f"Dashboard: {dash_label}")
    print(f"Status file: {status_file_note}")
    if market.get("session_guard_start_reason"):
        print(f"Session guard: {market.get('session_guard_start_reason')}")
    for note in (market.get("notes") or [])[:2]:
        print(f"  {note}")
    print(f"Advisory: {adv.get('action')} | blocks new BUY: {adv.get('blocks_new_buy')}")
    print(f"Market readiness: {market.get('verdict', 'UNKNOWN')}")
    print(f"X.9 ledger: {x9.get('readiness_label', 'UNKNOWN')}")
    if x9.get("message"):
        print(f"  {x9.get('message')}")
    print(
        f"Financial (est.): cash={fin.get('cash_available')} | "
        f"total_pnl={fin.get('total_pnl')} | daily_pnl={fin.get('daily_pnl')}"
    )
    print(
        f"Signals: STRONG BUY={sig.get('strong_buy_count')} | "
        f"TAKE PROFIT={sig.get('take_profit_count')}"
    )
    print(
        f"Shadow: events={sh.get('total_events')} | "
        f"blocked={sh.get('buy_blocked_by_tae')} | allowed={sh.get('buy_allowed')}"
    )
    print(
        f"Strategies: robust={counts.get('robust_shortlist_count')} | "
        f"weak={counts.get('weak_shortlist_count')} | "
        f"registry={counts.get('registry_candidates_count')}"
    )
    print(f"Next action for market open: {market.get('next_action_for_market_open')}")
    print(f"Output: {DEFAULT_JSON_OUT}, {DEFAULT_MD_OUT}")
    print("")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = Path(".")
    review = build_review(root)
    json_path, md_path = persist_review(review, root)
    logger.info("Wrote %s", json_path)
    logger.info("Wrote %s", md_path)
    print_terminal_summary(review)
    return 0


if __name__ == "__main__":
    sys.exit(main())
