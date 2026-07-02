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
from typing import Any, Callable

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = PROJECT_DIR / "tae_infrastructure_health.json"
OUTPUT_MD = PROJECT_DIR / "tae_infrastructure_health.md"

INFRA_SCRIPTS = [
    "market_open_runner.sh",
    "market_close_runner.sh",
    "startup_runner.sh",
    "awake_guard.sh",
]

EXPECTED_CRON_PATTERNS = [
    r"market_close_runner\.sh",
    r"market_session_guard\.py",
    r"daily_intelligence",
]

CRON_DUPLICATE_PATTERNS = [
    r"market_open_runner\.sh",
    r"startup_runner\.sh",
]

LAUNCH_AGENTS = {
    "com.tradingai.startup": "com.tradingai.startup.plist",
    "com.tradingai.market-open": "com.tradingai.market-open.plist",
    "com.tradingai.market-session-guard": "com.tradingai.market-session-guard.plist",
}

LAUNCH_AGENT_LABELS = list(LAUNCH_AGENTS.keys())

LOG_PATHS = {
    "startup_out": PROJECT_DIR / "startup_launchagent.out.log",
    "startup_err": PROJECT_DIR / "startup_launchagent.err.log",
    "market_open_out": PROJECT_DIR / "market_open_launchagent.out.log",
    "market_open_err": PROJECT_DIR / "market_open_launchagent.err.log",
    "market_open_legacy": PROJECT_DIR / "market_open_runner.log",
}


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )


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


def bash_syntax_ok(path: Path) -> bool:
    return _run(["bash", "-n", str(path)]).returncode == 0


def get_crontab() -> str:
    result = _run(["crontab", "-l"])
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def launchctl_labels() -> dict[str, str | None]:
    result = _run(["launchctl", "list"])
    labels: dict[str, str | None] = {label: None for label in LAUNCH_AGENT_LABELS}
    if result.returncode != 0:
        return labels
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            pid, exit_code, label = parts[0], parts[1], parts[2]
            if label in labels:
                labels[label] = f"pid={pid} last_exit={exit_code}"
    return labels


def pgrep_count(pattern: str) -> int:
    result = _run(["pgrep", "-f", pattern])
    if result.returncode != 0:
        return 0
    return len([line for line in (result.stdout or "").splitlines() if line.strip()])


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
            status="FAIL",
            detail=f"Missing plist for {label}",
            remediation=f"Install launchagents/{plist_name} to ~/Library/LaunchAgents/",
        )
        return

    lint = _run(["plutil", "-lint", str(path)])
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
    if expect_bash:
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


def overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {c["status"] for c in checks}
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
    crontab_text = crontab_fn() if crontab_fn else get_crontab()
    launch_agents = launchctl_fn() if launchctl_fn else launchctl_labels()
    pgrep = pgrep_fn or pgrep_count

    for script_name in INFRA_SCRIPTS:
        path = project_dir / script_name
        if not path.is_file():
            _check(
                checks,
                name=f"script_exists:{script_name}",
                status="FAIL",
                detail=f"Missing {script_name}",
            )
            continue

        _check(checks, name=f"script_exists:{script_name}", status="PASS", detail=f"{script_name} present")

        _check(
            checks,
            name=f"script_executable:{script_name}",
            status="PASS" if is_executable(path) else "FAIL",
            detail=f"{script_name} executable" if is_executable(path) else f"{script_name} not executable",
        )

        xattrs = read_xattrs(path)
        if "com.apple.quarantine" in xattrs:
            _check(checks, name=f"quarantine:{script_name}", status="FAIL", detail="quarantine present")
        elif "com.apple.provenance" in xattrs:
            _check(checks, name=f"provenance:{script_name}", status="WARN", detail="provenance present")
        else:
            _check(checks, name=f"xattrs:{script_name}", status="PASS", detail="no blocking xattrs")

        _check(
            checks,
            name=f"bash_syntax:{script_name}",
            status="PASS" if bash_syntax_ok(path) else "FAIL",
            detail=f"{script_name} bash -n OK" if bash_syntax_ok(path) else f"{script_name} bash -n FAIL",
        )

    for pattern in EXPECTED_CRON_PATTERNS:
        found = bool(re.search(pattern, crontab_text))
        _check(
            checks,
            name=f"cron:{pattern}",
            status="PASS" if found else "FAIL",
            detail="Crontab entry found" if found else f"Missing crontab entry for {pattern}",
        )

    for pattern in CRON_DUPLICATE_PATTERNS:
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

    validate_plist_checks(
        checks,
        label="com.tradingai.startup",
        plist_name="com.tradingai.startup.plist",
        project_dir=project_dir,
        expect_bash=False,
    )
    validate_plist_checks(
        checks,
        label="com.tradingai.market-open",
        plist_name="com.tradingai.market-open.plist",
        project_dir=project_dir,
        expect_bash=True,
    )
    validate_plist_checks(
        checks,
        label="com.tradingai.market-session-guard",
        plist_name="com.tradingai.market-session-guard.plist",
        project_dir=project_dir,
        expect_bash=False,
    )

    for label in LAUNCH_AGENT_LABELS:
        info = launch_agents.get(label)
        if info is None:
            _check(checks, name=f"launchagent:{label}", status="FAIL", detail=f"{label} not loaded")
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

    caffeinate_count = pgrep("caffeinate -d -i -m")
    _check(
        checks,
        name="awake_guard_caffeinate",
        status="PASS" if caffeinate_count >= 1 else "WARN",
        detail=f"caffeinate processes={caffeinate_count}",
    )

    bot_count = pgrep("live_bot.py")
    if bot_count == 0:
        _check(checks, name="live_bot_process", status="WARN", detail="live_bot.py not running")
    elif bot_count == 1:
        _check(checks, name="live_bot_process", status="PASS", detail="live_bot.py running (1)")
    else:
        _check(checks, name="live_bot_process", status="FAIL", detail=f"duplicate live_bot ({bot_count})")

    dash_count = pgrep("streamlit run dashboard_v2.py")
    if dash_count == 0:
        _check(checks, name="dashboard_process", status="WARN", detail="dashboard not running")
    elif dash_count == 1:
        _check(checks, name="dashboard_process", status="PASS", detail="dashboard running (1)")
    else:
        _check(checks, name="dashboard_process", status="WARN", detail=f"duplicate dashboard ({dash_count})")

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
    check_launchagent_log(
        checks,
        name="market_open_launchagent_log",
        out_path=project_dir / "market_open_launchagent.out.log",
        err_path=project_dir / "market_open_launchagent.err.log",
    )

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

    status = overall_status(checks)
    return {
        "schema": "tae_infrastructure_health",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(project_dir),
        "overall_status": status,
        "checks": checks,
        "summary": {
            "pass": sum(1 for c in checks if c["status"] == "PASS"),
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
        "",
        "## Summary",
        f"- PASS: {report['summary']['pass']}",
        f"- WARN: {report['summary']['warn']}",
        f"- FAIL: {report['summary']['fail']}",
        "",
        "## Checks",
    ]
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
    print("PASS/WARN/FAIL:", report["summary"]["pass"], report["summary"]["warn"], report["summary"]["fail"])
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
