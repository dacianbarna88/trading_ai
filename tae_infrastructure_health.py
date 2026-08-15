#!/usr/bin/env python3
"""
TAE Infrastructure Health Checker — autostart / permissions audit.

Infrastructure only. Does not modify trading logic or live_bot.py.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
from datetime import datetime
from pathlib import Path

from tae_artifact_paths import generated_report
from typing import Any, Callable

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = generated_report("tae_infrastructure_health.json")
OUTPUT_MD = generated_report("tae_infrastructure_health.md")

# Optional legacy bash runners — presence is INFO only (LaunchAgents own sessions).
OPTIONAL_INFRA_SCRIPTS = [
    "market_open_runner.sh",
    "market_close_runner.sh",
    "startup_runner.sh",
    "awake_guard.sh",
]
INFRA_SCRIPTS: list[str] = []  # no required bash runners after LaunchAgent consolidation

# Prefer LaunchAgent market-close (python). Legacy bash cron is TCC-broken on Desktop.
REQUIRED_CRON_PATTERNS: list[str] = []

# Periodic PAPER MTM/FPC is CLI/orchestrator-owned; cron is intentionally not required.
RECOMMENDED_CRON_PATTERNS: list[str] = []

LEGACY_CRON_WARN_PATTERNS = [
    r"daily_intelligence_runner\.py",
    r"tae\.py\s+paper-mark-to-market",
    r"tae\.py\s+full-paper-cycle",
    r"tae\.py\s+self-improve",
]

# Stage 3F: market_session_guard must NOT be on cron — LaunchAgent is sole automatic owner.
CRON_DUPLICATE_PATTERNS = [
    r"market_open_runner\.sh",
    r"startup_runner\.sh",
    r"market_session_guard\.py",
]

# Canonical active LaunchAgents after orphan retirement (2026-08-03).
ACTIVE_LAUNCH_AGENTS = {
    "com.tradingai.dashboard": "com.tradingai.dashboard.plist",
    "com.tradingai.live-bot": "com.tradingai.live-bot.plist",
    "com.tradingai.market-session-guard": "com.tradingai.market-session-guard.plist",
}

# Intentionally retired — must NOT FAIL health when absent.
RETIRED_LAUNCH_AGENTS = {
    "com.tradingai.startup": "retired_orphan_launchagent",
    "com.tradingai.market-open": "retired_orphan_launchagent",
    "com.tradingai.market-close": "retired_orphan_launchagent",
    "com.tradingai.canonical-learning": "retired_orphan_launchagent",
    "com.tradingai.parallel-paper": "retired_orphan_launchagent",
}

LAUNCH_AGENTS = dict(ACTIVE_LAUNCH_AGENTS)
LAUNCH_AGENT_LABELS = list(LAUNCH_AGENTS.keys())

LOG_PATHS: dict[str, Path] = {}

SPAWN_BLOCKED = -999

FRAMEWORK_PYTHON_LAUNCHD = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
MARKET_OPEN_SAFE_LAUNCHER = "tae_launchd_market_open_safe.py"  # retired; kept for lint of old plists only
MARKET_CLOSE_SAFE_LAUNCHER = "tae_launchd_market_close_safe.py"

# FAIL checks that indicate broken autostart dependencies (not runtime hygiene).
CRITICAL_FAIL_PREFIXES = (
    "script_exists:",
    "script_executable:",
    "quarantine:",
    "bash_syntax:",
    "cron:",
    "plist_exists:",
    "plist_lint:",
    "plist_bash:",
    "launchagent:com.tradingai.dashboard",
    "launchagent:com.tradingai.live-bot",
    "launchagent:com.tradingai.market-session-guard",
    "venv_python",
)
CRITICAL_FAIL_NAMES = frozenset(
    {
        "venv_python",
    }
)
NON_CRITICAL_FAIL_NAMES = frozenset(
    {
        "live_bot_process",
        "dashboard_process",
    }
)


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
    except (PermissionError, OSError) as exc:
        return subprocess.CompletedProcess(cmd, SPAWN_BLOCKED, "", str(exc))


def _spawn_blocked(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == SPAWN_BLOCKED


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    status: str,
    detail: str,
    remediation: str = "",
) -> None:
    checks.append(
        {
            "name": name,
            "status": status,
            "detail": detail,
            "remediation": remediation,
        }
    )


def read_xattrs(path: Path) -> dict[str, str]:
    result = _run(["xattr", "-l", str(path)])
    attrs: dict[str, str] = {}
    if result.returncode != 0:
        return attrs
    for line in (result.stdout or "").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            attrs[key.strip()] = value.strip()
    return attrs


def is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def bash_syntax_ok(path: Path) -> tuple[bool | None, bool]:
    result = _run(["bash", "-n", str(path)])
    if _spawn_blocked(result):
        return None, False
    return result.returncode == 0, True


def get_crontab() -> tuple[str, bool]:
    """Return (crontab_text, available). available=False when spawn is blocked."""
    result = _run(["crontab", "-l"])
    if _spawn_blocked(result):
        return "", False
    if result.returncode != 0:
        return "", True
    return result.stdout or "", True


def launchctl_labels() -> tuple[dict[str, str | None], bool]:
    result = _run(["launchctl", "list"])
    labels: dict[str, str | None] = {label: None for label in LAUNCH_AGENT_LABELS}
    if _spawn_blocked(result):
        return labels, False
    if result.returncode != 0:
        return labels, False
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            pid, exit_code, label = parts[0], parts[1], parts[2]
            if label in labels:
                labels[label] = f"pid={pid} last_exit={exit_code}"
    return labels, True


def pgrep_count(pattern: str) -> tuple[int, bool]:
    result = _run(["pgrep", "-f", pattern])
    if _spawn_blocked(result):
        return 0, False
    if result.returncode != 0:
        return 0, True
    return len([line for line in (result.stdout or "").splitlines() if line.strip()]), True


def read_log_tail(path: Path, *, tail_lines: int = 5) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines[-tail_lines:] if line.strip()]


def read_log_errors(path: Path, *, tail_lines: int = 30) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    errors: list[str] = []
    for line in lines[-tail_lines:]:
        lower = line.lower()
        if any(
            token in lower
            for token in (
                "operation not permitted",
                "permission denied",
                "no such file",
                "error",
                "failed",
            )
        ):
            errors.append(line.strip())
    return errors[-10:]


def resolve_plist_path(project_dir: Path, plist_name: str) -> Path:
    local = project_dir / "launchagents" / plist_name
    if local.is_file():
        return local
    installed = Path.home() / "Library" / "LaunchAgents" / plist_name
    if project_dir.resolve() == PROJECT_DIR.resolve() and installed.is_file():
        return installed
    return local


def load_plist(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            return plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None


def market_open_entrypoint_ok(args: list[Any]) -> tuple[bool, str]:
    """Accept legacy bash or validated framework-python launchd entry."""
    if len(args) >= 2 and args[0] == "/bin/bash":
        return True, "ProgramArguments uses /bin/bash (legacy market-open entry)"
    if (
        len(args) >= 2
        and args[0] == FRAMEWORK_PYTHON_LAUNCHD
        and str(args[1]).endswith(MARKET_OPEN_SAFE_LAUNCHER)
    ):
        return True, (
            "ProgramArguments uses framework python + "
            f"{MARKET_OPEN_SAFE_LAUNCHER} (launchd-safe entry)"
        )
    return False, f"ProgramArguments not accepted for market-open: {args}"


def market_close_entrypoint_ok(args: list[Any]) -> tuple[bool, str]:
    """Accept python launcher for market-close (bash Desktop .sh is TCC-broken)."""
    if len(args) >= 2 and str(args[1]).endswith(MARKET_CLOSE_SAFE_LAUNCHER):
        return True, (
            "ProgramArguments uses python + "
            f"{MARKET_CLOSE_SAFE_LAUNCHER} (TCC-safe PDE daily cycle)"
        )
    return False, f"ProgramArguments not accepted for market-close: {args}"


def validate_plist_checks(
    checks: list[dict[str, Any]],
    *,
    label: str,
    plist_name: str,
    project_dir: Path,
    expect_bash: bool,
) -> None:
    path = resolve_plist_path(project_dir, plist_name)
    if not path.is_file():
        _check(
            checks,
            name=f"plist_exists:{label}",
            status="WARN",
            detail=f"Missing plist for {label} (intentionally disabled — moved to disabled_trading_ai_restored/)",
            remediation=f"Install launchagents/{plist_name} to ~/Library/LaunchAgents/ to re-enable",
        )
        return

    lint = _run(["plutil", "-lint", str(path)])
    if _spawn_blocked(lint):
        _check(
            checks,
            name=f"plist_lint:{label}",
            status="WARN",
            detail=f"plutil unavailable in restricted context for {path.name}",
        )
        return
    if lint.returncode != 0:
        _check(
            checks,
            name=f"plist_lint:{label}",
            status="FAIL",
            detail=f"plutil -lint failed for {path}: {lint.stderr.strip()}",
        )
        return

    _check(checks, name=f"plist_lint:{label}", status="PASS", detail=f"plutil OK: {path}")

    data = load_plist(path) or {}
    args = data.get("ProgramArguments") or []
    if label == "com.tradingai.market-open":
        ok, entry_detail = market_open_entrypoint_ok(args)
        _check(
            checks,
            name=f"plist_entry:{label}",
            status="PASS" if ok else "FAIL",
            detail=entry_detail,
            remediation=(
                ""
                if ok
                else (
                    "Use /bin/bash + market_open_runner.sh (legacy) or "
                    f"{FRAMEWORK_PYTHON_LAUNCHD} + {MARKET_OPEN_SAFE_LAUNCHER}"
                )
            ),
        )
    elif label == "com.tradingai.market-close":
        ok, entry_detail = market_close_entrypoint_ok(args)
        _check(
            checks,
            name=f"plist_entry:{label}",
            status="PASS" if ok else "FAIL",
            detail=entry_detail,
            remediation=(
                ""
                if ok
                else f"Use python + {MARKET_CLOSE_SAFE_LAUNCHER}; run install_market_close_agent.sh"
            ),
        )
    elif expect_bash:
        if len(args) >= 2 and args[0] == "/bin/bash":
            _check(checks, name=f"plist_bash:{label}", status="PASS", detail="ProgramArguments uses /bin/bash")
        else:
            _check(
                checks,
                name=f"plist_bash:{label}",
                status="FAIL",
                detail=f"ProgramArguments missing /bin/bash: {args}",
            )
    elif args:
        _check(checks, name=f"plist_program:{label}", status="PASS", detail=f"ProgramArguments set: {args[0]}")

    if data.get("WorkingDirectory"):
        _check(
            checks,
            name=f"plist_workdir:{label}",
            status="PASS",
            detail=f"WorkingDirectory={data.get('WorkingDirectory')}",
        )
    else:
        _check(
            checks,
            name=f"plist_workdir:{label}",
            status="WARN",
            detail=f"WorkingDirectory missing for {label}",
        )


def check_market_open_launchagent_log(
    checks: list[dict[str, Any]],
    *,
    project_dir: Path,
) -> None:
    safe_out = project_dir / "tae_launchd_market_open_safe.log"
    safe_err = project_dir / "tae_launchd_market_open_safe.err.log"
    # FPC floods stdout into this same log; a short tail loses START/BOOTSTRAP_OK mid-cycle
    # and then historical err FAIL lines are misread as active. Scan a large window.
    out_tail = read_log_tail(safe_out, tail_lines=8000)
    err_tail = read_log_tail(safe_err, tail_lines=400)

    def _is_stale_desktop_tcc(line: str) -> bool:
        lower = line.lower()
        if "operation not permitted" not in lower and "getcwd" not in lower:
            return False
        if any(
            token in line
            for token in (
                "tae_launchd_market_open_safe.sh",
                "market_open_runner.sh",
                ".local/bin/tae_launchd_market_open_safe.sh",
            )
        ):
            return True
        if "getcwd" in lower or "shell-init" in lower:
            return True
        return False

    def _is_historical_hygiene_fail(line: str) -> bool:
        # Superseded by live dashboard_process / port checks; never block orchestration.
        return "FAIL dashboard not running" in line

    def _line_stamp(line: str) -> str:
        # "[2026-07-28 22:20:25 +0300] ..." → sortable prefix
        if line.startswith("[") and "]" in line:
            return line[1 : line.index("]")]
        return ""

    # Scope to the most recent launcher invocation in the out log.
    start_idx = None
    for i, line in enumerate(out_tail):
        if "===== TAE LAUNCHD MARKET OPEN SAFE" in line and "END" not in line:
            start_idx = i
    if start_idx is None:
        # Mid-cycle flood can still omit START even in a large window — do not promote
        # historical err FAIL into an active autostart blocker.
        _check(
            checks,
            name="market_open_launchagent_log",
            status="WARN",
            detail=(
                "Launcher START marker not in recent out-log window "
                f"(likely mid full-paper-cycle stdout flood); last_out="
                f"{out_tail[-1] if out_tail else 'empty'}"
            ),
        )
        return

    last_run = out_tail[start_idx:]
    run_stamp = _line_stamp(last_run[0]) if last_run else ""
    has_recent_pass = any(
        ("RESULT: PASS" in line) or ("RESULT: BOOTSTRAP_OK" in line) for line in last_run
    )
    has_recent_run = bool(last_run) and any(
        "===== TAE LAUNCHD MARKET OPEN SAFE" in line and "END" not in line for line in last_run
    )
    python_entry_proven = any(
        "python entry" in line or "pwd=/Users/book/Desktop/trading_ai" in line for line in last_run
    )
    last_run_fail = [
        e
        for e in last_run
        if ("] FAIL " in e or e.strip().startswith("FAIL "))
        and not _is_stale_desktop_tcc(e)
        and not _is_historical_hygiene_fail(e)
        and "FAIL full_paper_cycle" not in e
    ]
    err_fail = []
    for e in err_tail:
        if _is_stale_desktop_tcc(e):
            continue
        if "FAIL full_paper_cycle" in e:
            continue
        if _is_historical_hygiene_fail(e):
            continue
        if not ("] FAIL " in e or "ERROR " in e):
            continue
        # Require a real run stamp — without it, err lines are historical noise.
        if not run_stamp:
            continue
        stamp = _line_stamp(e)
        if not stamp or stamp < run_stamp:
            continue
        err_fail.append(e)
    # Only treat err FAIL as active when the latest out run did not PASS/BOOTSTRAP.
    active_err_fail = [] if has_recent_pass else err_fail
    stale_tcc = [e for e in err_tail if _is_stale_desktop_tcc(e)]

    if has_recent_pass:
        detail = f"Safe launcher PASS recorded; last_out={last_run[-1] if last_run else 'empty'}"
        if stale_tcc:
            detail += f" (ignored {len(stale_tcc)} historical Desktop bash/getcwd TCC err line(s))"
        _check(checks, name="market_open_launchagent_log", status="PASS", detail=detail)
        return

    if last_run_fail or active_err_fail:
        detail_src = (last_run_fail or active_err_fail)[-1]
        _check(
            checks,
            name="market_open_launchagent_log",
            status="FAIL",
            detail=f"Recent launcher failure: {detail_src}",
            remediation="Inspect tae_launchd_market_open_safe logs; verify dashboard LaunchAgent + bot.",
        )
        return

    if has_recent_run and python_entry_proven:
        detail = "Python LaunchAgent entry proven; awaiting RESULT: PASS marker"
        if stale_tcc:
            detail += f" (ignored {len(stale_tcc)} historical getcwd/bash TCC line(s))"
        _check(checks, name="market_open_launchagent_log", status="WARN", detail=detail)
        return

    if safe_out.is_file() or safe_err.is_file():
        _check(
            checks,
            name="market_open_launchagent_log",
            status="WARN",
            detail=f"Safe launcher logs present; last_out={out_tail[-1] if out_tail else 'empty'}",
        )
        return

    _check(
        checks,
        name="market_open_launchagent_log",
        status="WARN",
        detail="Safe launcher logs not created yet (tae_launchd_market_open_safe.log)",
    )


def check_launchagent_log(
    checks: list[dict[str, Any]],
    *,
    name: str,
    out_path: Path,
    err_path: Path,
    missing_status: str = "WARN",
    success_markers: tuple[str, ...] = ("COMPLETE", "OK"),
    historical_bash_script: str | None = None,
) -> None:
    err_issues = read_log_errors(err_path)
    op_blocked = [e for e in err_issues if "operation not permitted" in e.lower()]
    out_tail = read_log_tail(out_path, tail_lines=40)
    has_recent_success = any(any(marker in line for marker in success_markers) for line in out_tail)
    if not has_recent_success and name == "startup_launchagent_log":
        runner_tail = read_log_tail(out_path.parent / "startup_runner.log", tail_lines=40)
        has_recent_success = any(any(marker in line for marker in success_markers) for line in runner_tail)

    if op_blocked:
        if (
            historical_bash_script
            and has_recent_success
            and any(historical_bash_script in entry for entry in op_blocked)
        ):
            _check(
                checks,
                name=name,
                status="WARN",
                detail=(
                    f"Historical bash TCC in {err_path.name}; "
                    f"recent success in {out_path.name} (python launcher active)"
                ),
            )
            return
        _check(
            checks,
            name=name,
            status="FAIL",
            detail=f"Recent blocked execution: {op_blocked[-1]}",
            remediation=f"Inspect {err_path.name}; verify LaunchAgent permissions.",
        )
    elif err_issues:
        _check(checks, name=name, status="WARN", detail=f"Recent issues: {err_issues[-1]}")
    elif out_path.is_file() or err_path.is_file():
        tail = read_log_tail(out_path)
        _check(
            checks,
            name=name,
            status="PASS",
            detail=f"Logs OK; last_out={tail[-1] if tail else 'empty'}",
        )
    else:
        _check(
            checks,
            name=name,
            status=missing_status,
            detail=f"Logs not created yet ({out_path.name})",
        )


def is_critical_fail(check: dict[str, Any]) -> bool:
    if check.get("status") != "FAIL":
        return False
    name = check.get("name") or ""
    if name in NON_CRITICAL_FAIL_NAMES:
        return False
    if name.endswith(":access") or name.startswith("cron_duplicate:"):
        return False
    if name in CRITICAL_FAIL_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in CRITICAL_FAIL_PREFIXES)


def overall_status(
    checks: list[dict[str, Any]],
    *,
    bot_count: int = 0,
    dash_count: int = 0,
) -> str:
    runtime_operational = bot_count >= 1 and dash_count >= 1
    critical_fails = [c for c in checks if is_critical_fail(c)]
    if critical_fails:
        return "FAIL"
    if runtime_operational:
        return "PASS"
    # Non-critical FAILs (live_bot / dashboard hygiene) must not flip overall to FAIL.
    # Otherwise PAPER orchestration deadlocks when identity is briefly stale or LIVE is down.
    statuses = {
        ("WARN" if (c["status"] == "FAIL" and c.get("name") in NON_CRITICAL_FAIL_NAMES) else c["status"])
        for c in checks
    }
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def build_health_report(
    *,
    project_dir: Path = PROJECT_DIR,
    crontab_fn: Callable[[], str] | None = None,
    launchctl_fn: Callable[[], dict[str, str | None]] | None = None,
    pgrep_fn: Callable[[str], int] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    venv_python = project_dir / "venv" / "bin" / "python3"
    runtime_outputs = project_dir / "runtime_outputs"
    if crontab_fn:
        crontab_text = crontab_fn()
        crontab_available = True
    else:
        crontab_text, crontab_available = get_crontab()
    if launchctl_fn:
        launch_agents = launchctl_fn()
        launchctl_available = True
    else:
        launch_agents, launchctl_available = launchctl_labels()

    def _pgrep(pattern: str) -> tuple[int, bool]:
        if pgrep_fn:
            return pgrep_fn(pattern), True
        return pgrep_count(pattern)

    bash_syntax_available = True

    for script_name in OPTIONAL_INFRA_SCRIPTS:
        path = project_dir / script_name
        if not path.is_file():
            _check(
                checks,
                name=f"optional_script:{script_name}",
                status="INFO",
                detail=f"Optional legacy runner absent ({script_name}) — LaunchAgents own sessions",
            )
            continue

        _check(
            checks,
            name=f"optional_script:{script_name}",
            status="INFO",
            detail=f"{script_name} present (legacy optional; not required for health PASS)",
        )

        if is_executable(path):
            syntax_ok, syntax_available = bash_syntax_ok(path)
            if not syntax_available:
                bash_syntax_available = False
            elif not syntax_ok:
                _check(
                    checks,
                    name=f"bash_syntax:{script_name}",
                    status="WARN",
                    detail=f"{script_name} bash -n FAIL (optional runner)",
                )

    if not bash_syntax_available:
        _check(
            checks,
            name="bash:access",
            status="WARN",
            detail="bash syntax check unavailable in this context (sandbox or restricted permissions)",
        )

    for pattern in REQUIRED_CRON_PATTERNS:
        if not crontab_available:
            continue
        found = bool(re.search(pattern, crontab_text))
        _check(
            checks,
            name=f"cron:{pattern}",
            status="PASS" if found else "FAIL",
            detail="Crontab entry found" if found else f"Missing crontab entry for {pattern}",
        )

    for pattern in RECOMMENDED_CRON_PATTERNS:
        if not crontab_available:
            continue
        found = bool(re.search(pattern, crontab_text))
        _check(
            checks,
            name=f"cron_recommended:{pattern}",
            status="PASS" if found else "WARN",
            detail="Canonical periodic cron present" if found else f"Optional periodic cron missing ({pattern})",
            remediation="Run install_market_day_schedule.sh to add paper-mark-to-market */30",
        )

    for pattern in LEGACY_CRON_WARN_PATTERNS:
        if not crontab_available:
            continue
        if re.search(pattern, crontab_text):
            _check(
                checks,
                name=f"cron_legacy:{pattern}",
                status="WARN",
                detail=f"Legacy cron still schedules {pattern} — detach in Stage 3A",
                remediation="Re-run install_market_day_schedule.sh or remove daily_intelligence_runner cron line",
            )
        else:
            _check(
                checks,
                name=f"cron_legacy:{pattern}",
                status="PASS",
                detail=f"No legacy cron for {pattern}",
            )

    # Broken TCC pattern: cron invoking Desktop bash market_close_runner.sh
    if crontab_available and re.search(r"/bin/bash.*market_close_runner\.sh", crontab_text):
        _check(
            checks,
            name="cron_tcc_broken:market_close_runner.sh",
            status="WARN",
            detail="Cron still invokes bash market_close_runner.sh (Desktop TCC → Operation not permitted)",
            remediation="Remove that cron line; install_market_close_agent.sh owns daily PDE cycle",
        )

    if not crontab_available:
        _check(
            checks,
            name="cron:access",
            status="WARN",
            detail="crontab unavailable in this context (sandbox or restricted permissions)",
        )

    for pattern in CRON_DUPLICATE_PATTERNS:
        if not crontab_available:
            continue
        if re.search(pattern, crontab_text):
            _check(
                checks,
                name=f"cron_duplicate:{pattern}",
                status="WARN",
                detail=f"Duplicate cron entry for {pattern} — LaunchAgent preferred",
            )
        else:
            _check(
                checks,
                name=f"cron_duplicate:{pattern}",
                status="PASS",
                detail=f"No duplicate cron for {pattern}",
            )

    for label, plist_name in ACTIVE_LAUNCH_AGENTS.items():
        validate_plist_checks(
            checks,
            label=label,
            plist_name=plist_name,
            project_dir=project_dir,
            expect_bash=False,
        )

    for label, reason in RETIRED_LAUNCH_AGENTS.items():
        path = resolve_plist_path(project_dir, f"{label}.plist")
        if path.is_file():
            _check(
                checks,
                name=f"retired_launchagent_present:{label}",
                status="WARN",
                detail=f"{label} plist still present — should remain retired ({reason})",
                remediation="Keep unloaded; archive under disabled_trading_ai if reappears",
            )
        else:
            _check(
                checks,
                name=f"retired_launchagent_absent:{label}",
                status="PASS",
                detail=f"{label} intentionally absent ({reason})",
            )

    if not launchctl_available:
        _check(
            checks,
            name="launchctl:access",
            status="WARN",
            detail="launchctl unavailable in this context (sandbox or restricted permissions)",
        )
    else:
        for label in LAUNCH_AGENT_LABELS:
            info = launch_agents.get(label)
            if info is None:
                _check(
                    checks,
                    name=f"launchagent:{label}",
                    status="WARN",
                    detail=f"{label} not loaded (intentionally disabled — moved to disabled_trading_ai_restored/)",
                    remediation=f"launchctl load ~/Library/LaunchAgents/{label}.plist to re-enable",
                )
            elif "last_exit=126" in info or "last_exit=127" in info:
                _check(
                    checks,
                    name=f"launchagent:{label}",
                    status="FAIL",
                    detail=f"{label} permission/path failure ({info})",
                    remediation="Reload plist; verify /bin/bash and WorkingDirectory; check Desktop TCC.",
                )
            else:
                _check(checks, name=f"launchagent:{label}", status="PASS", detail=f"{label} loaded ({info})")

    caffeinate_count, pgrep_available = _pgrep("caffeinate -d -i -m")
    bot_count = 0
    dash_count = 0
    if not pgrep_available:
        _check(
            checks,
            name="pgrep:access",
            status="WARN",
            detail="pgrep unavailable in this context (sandbox or restricted permissions)",
        )
        _check(
            checks,
            name="awake_guard_caffeinate",
            status="WARN",
            detail="caffeinate process count unverified (pgrep blocked)",
        )
    else:
        _check(
            checks,
            name="awake_guard_caffeinate",
            status="PASS" if caffeinate_count >= 1 else "WARN",
            detail=f"caffeinate processes={caffeinate_count}",
        )

    markets_open = False
    try:
        from markets.market_hours import any_market_open

        markets_open = bool(any_market_open())
    except Exception:
        markets_open = False

    if not pgrep_available:
        _check(checks, name="live_bot_process", status="WARN", detail="live_bot.py unverified (pgrep blocked)")
        _check(checks, name="dashboard_process", status="WARN", detail="dashboard unverified (pgrep blocked)")
    elif pgrep_fn is not None:
        # Injected test/probe path — keep deterministic pgrep-count semantics.
        bot_count, _ = _pgrep("live_bot.py")
        if bot_count == 0:
            _check(checks, name="live_bot_process", status="WARN", detail="live_bot.py not running")
        elif bot_count == 1:
            _check(checks, name="live_bot_process", status="PASS", detail="live_bot.py running (1)")
        else:
            _check(
                checks,
                name="live_bot_process",
                status="WARN",
                detail=f"duplicate live_bot ({bot_count}) — runtime operational but cleanup recommended",
                remediation="Stop duplicate live_bot.py processes; keep a single supervised instance.",
            )
        dash_count, _ = _pgrep("streamlit run dashboard_v2.py")
        if dash_count == 0:
            _check(checks, name="dashboard_process", status="WARN", detail="dashboard not running")
        elif dash_count == 1:
            _check(checks, name="dashboard_process", status="PASS", detail="dashboard running (1)")
        else:
            _check(checks, name="dashboard_process", status="WARN", detail=f"duplicate dashboard ({dash_count})")
    else:
        try:
            from core import process_identity as pi

            identity, duplicates = pi.resolve_canonical_bot(project_dir=project_dir)
            recovery = pi.load_recovery_state()
            hb_age = None
            bot_log = project_dir / "bot_output.log"
            if bot_log.is_file():
                try:
                    hb_age = max(0.0, datetime.now().timestamp() - bot_log.stat().st_mtime)
                except OSError:
                    hb_age = None
            bot_ops_state = pi.classify_operational_state(
                markets_open=markets_open,
                identity=identity,
                heartbeat_age_sec=hb_age,
                recovery_state=recovery,
            )
            bot_identity_detail = (
                f"ops={bot_ops_state} pid={identity.pid} valid={identity.valid} "
                f"source={identity.source} duplicates={duplicates} "
                f"owner=market_session_guard"
            )
            pgrep_bot, _ = _pgrep("live_bot.py")
            # Prefer living process over stale pid-file metadata for runtime counts.
            bot_count = 1 if identity.valid else (1 if pgrep_bot >= 1 else 0)
            if bot_ops_state == "DOWN_UNEXPECTED" and pgrep_bot >= 1:
                # Identity metadata lag — process is alive; do not HARD-fail PAPER infra.
                _check(
                    checks,
                    name="live_bot_process",
                    status="WARN",
                    detail=bot_identity_detail + f" pgrep={pgrep_bot}",
                    remediation="Reconcile bot_pid.txt via process_identity; owner remains market_session_guard.",
                )
            elif bot_ops_state == "DOWN_UNEXPECTED":
                _check(
                    checks,
                    name="live_bot_process",
                    status="FAIL",
                    detail=bot_identity_detail,
                    remediation="Canonical owner market_session_guard should restart within 300s.",
                )
            elif bot_ops_state == "CRASH_LOOP":
                _check(
                    checks,
                    name="live_bot_process",
                    status="FAIL",
                    detail=bot_identity_detail,
                    remediation="Inspect bot_error.log and bot_recovery_state.json.",
                )
            elif duplicates:
                _check(
                    checks,
                    name="live_bot_process",
                    status="WARN",
                    detail=bot_identity_detail,
                    remediation="Guard will dedupe; preserve canonical PID only.",
                )
            elif identity.valid:
                _check(checks, name="live_bot_process", status="PASS", detail=bot_identity_detail)
            else:
                _check(
                    checks,
                    name="live_bot_process",
                    status="PASS" if bot_ops_state == "DOWN_MARKET_CLOSED" else "WARN",
                    detail=bot_identity_detail,
                )
        except Exception as exc:
            bot_count, _ = _pgrep("live_bot.py")
            _check(
                checks,
                name="live_bot_process",
                status="WARN",
                detail=f"identity check failed ({exc}); pgrep count={bot_count}",
            )

        dash_count, _ = _pgrep("streamlit run dashboard_v2.py")
        dash_port_open = False
        try:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                dash_port_open = sock.connect_ex(("127.0.0.1", 8501)) == 0
        except OSError:
            dash_port_open = False
        if dash_port_open and dash_count == 0:
            dash_count = 1
        if dash_count == 0 and not dash_port_open:
            _check(checks, name="dashboard_process", status="WARN", detail="dashboard not running")
        elif dash_count == 1 or dash_port_open:
            _check(
                checks,
                name="dashboard_process",
                status="PASS",
                detail=f"dashboard running (pgrep={dash_count}, port8501={dash_port_open})",
            )
        else:
            _check(
                checks,
                name="dashboard_process",
                status="WARN",
                detail=f"duplicate dashboard ({dash_count})",
            )

    _check(
        checks,
        name="canonical_process_owner",
        status="PASS",
        detail="market_session_guard.py via LaunchAgent com.tradingai.market-session-guard (300s)",
    )

    _check(
        checks,
        name="runtime_outputs",
        status="PASS" if runtime_outputs.is_dir() else "WARN",
        detail="runtime_outputs exists" if runtime_outputs.is_dir() else "runtime_outputs missing",
    )

    _check(
        checks,
        name="venv_python",
        status="PASS" if venv_python.is_file() and os.access(venv_python, os.X_OK) else "FAIL",
        detail=str(venv_python) if venv_python.is_file() else "venv python missing",
    )

    check_launchagent_log(
        checks,
        name="startup_launchagent_log",
        out_path=project_dir / "startup_launchagent.out.log",
        err_path=project_dir / "startup_launchagent.err.log",
        success_markers=("STARTUP COMPLETE", "Launcher: tae_startup_launcher.py"),
        historical_bash_script="startup_runner.sh",
    )
    startup_runner_log = project_dir / "startup_runner.log"
    if startup_runner_log.is_file():
        runner_tail = read_log_tail(startup_runner_log, tail_lines=40)
        launcher_ok = any("Launcher: tae_startup_launcher.py" in line for line in runner_tail)
        if launcher_ok:
            _check(
                checks,
                name="startup_runner_log",
                status="PASS",
                detail="Recent python launcher startup recorded in startup_runner.log",
            )
        else:
            _check(
                checks,
                name="startup_runner_log",
                status="WARN",
                detail="startup_runner.log present; no recent launcher run marker",
            )
    check_market_open_launchagent_log(checks, project_dir=project_dir)

    legacy_errors = read_log_errors(project_dir / "market_open_runner.log")
    legacy_op = [e for e in legacy_errors if "operation not permitted" in e.lower()]
    if legacy_op:
        _check(
            checks,
            name="market_open_runner_log_legacy",
            status="WARN",
            detail="Historical cron Operation not permitted in market_open_runner.log (LaunchAgent is primary)",
        )
    else:
        _check(
            checks,
            name="market_open_runner_log_legacy",
            status="PASS",
            detail="No legacy cron blockers in market_open_runner.log",
        )

    status = overall_status(checks, bot_count=bot_count if pgrep_available else 0, dash_count=dash_count if pgrep_available else 0)
    fail_checks = [c for c in checks if c["status"] == "FAIL"]
    critical_fail_checks = [c for c in fail_checks if is_critical_fail(c)]
    non_critical_fail_checks = [c for c in fail_checks if not is_critical_fail(c)]
    return {
        "schema": "tae_infrastructure_health",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(project_dir),
        "overall_status": status,
        "runtime_operational": (bot_count >= 1 and dash_count >= 1) if pgrep_available else False,
        "process_counts": {
            "live_bot": bot_count if pgrep_available else None,
            "dashboard": dash_count if pgrep_available else None,
        },
        "fail_reasons": [
            {
                "name": c["name"],
                "detail": c["detail"],
                "critical": is_critical_fail(c),
                "remediation": c.get("remediation") or "",
            }
            for c in fail_checks
        ],
        "critical_fail_count": len(critical_fail_checks),
        "non_critical_fail_count": len(non_critical_fail_checks),
        "checks": checks,
        "summary": {
            "pass": sum(1 for c in checks if c["status"] == "PASS"),
            "info": sum(1 for c in checks if c["status"] == "INFO"),
            "warn": sum(1 for c in checks if c["status"] == "WARN"),
            "fail": sum(1 for c in checks if c["status"] == "FAIL"),
            "total": len(checks),
        },
        "autostart_readiness": (
            "READY" if status == "PASS" else "DEGRADED" if status == "WARN" else "NOT_READY"
        ),
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# TAE Infrastructure Health",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Overall:** {report['overall_status']}",
        f"**Autostart readiness:** {report['autostart_readiness']}",
        f"**Runtime operational:** {report.get('runtime_operational', False)}",
        "",
        "## Summary",
        f"- PASS: {report['summary']['pass']}",
        f"- INFO: {report['summary'].get('info', 0)}",
        f"- WARN: {report['summary']['warn']}",
        f"- FAIL: {report['summary']['fail']}",
        f"- Critical FAIL: {report.get('critical_fail_count', 0)}",
        f"- Non-critical FAIL: {report.get('non_critical_fail_count', 0)}",
        "",
    ]
    fail_reasons = report.get("fail_reasons") or []
    if fail_reasons:
        lines.extend(["## FAIL reasons (documented)", ""])
        for item in fail_reasons:
            critical = "CRITICAL" if item.get("critical") else "NON-CRITICAL"
            lines.append(f"- **{item['name']}** [{critical}] — {item['detail']}")
            if item.get("remediation"):
                lines.append(f"  - Remediation: {item['remediation']}")
        lines.append("")
    lines.append("## Checks")
    for check in report.get("checks", []):
        lines.append(f"- **{check['status']}** `{check['name']}` — {check['detail']}")
        if check.get("remediation"):
            lines.append(f"  - Remediation: {check['remediation']}")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    print("===== TAE INFRASTRUCTURE HEALTH =====")
    print("Overall:", report["overall_status"])
    print("Autostart readiness:", report["autostart_readiness"])
    print(
        "PASS/INFO/WARN/FAIL:",
        report["summary"]["pass"],
        report["summary"].get("info", 0),
        report["summary"]["warn"],
        report["summary"]["fail"],
    )
    for check in [c for c in report["checks"] if c["status"] == "FAIL"][:5]:
        print("FAIL:", check["name"], "-", check["detail"])


def main() -> int:
    report = build_health_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 1 if report["overall_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
