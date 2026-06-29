#!/usr/bin/env python3
"""
TAE Runtime Startup Regression Test — market session guard dry-run vs live paths.

RUNTIME_OPS_ONLY | NO_BROKER | NO_EXECUTION (mocked starts)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

import market_session_guard
from research_core.runtime.dry_run_config import resolve_dry_run


def test_default_live_not_dry_run() -> None:
    env = {k: v for k, v in os.environ.items() if k not in market_session_guard.dry_run_diagnostics()}
    with patch.dict(os.environ, env, clear=True):
        dry_run, source = resolve_dry_run([])
    assert dry_run is False
    assert source == "default_live"


def test_explicit_env_dry_run() -> None:
    with patch.dict(os.environ, {"DRY_RUN": "1"}, clear=False):
        dry_run, source = resolve_dry_run([])
    assert dry_run is True
    assert source.startswith("env:DRY_RUN")


def test_cli_dry_run_flag() -> None:
    dry_run, source = resolve_dry_run(["--dry-run"])
    assert dry_run is True
    assert source == "cli_flag --dry-run"


def test_market_open_live_calls_start(monkeypatch=None) -> None:
    logs: list[str] = []

    def fake_log(msg: str) -> None:
        logs.append(msg)

    fake_start = MagicMock(
        return_value={
            "message": "Bot pornit: live_bot.py",
            "pid": 4242,
            "pid_alive": True,
            "pgrep_pids": [4242],
            "command": "python live_bot.py",
            "failure_reason": None,
        }
    )
    fake_dash = MagicMock(
        return_value={
            "message": "Dashboard pornit",
            "pid": 5151,
            "pid_alive": True,
            "pgrep_pids": [5151],
            "command": "streamlit",
            "failure_reason": None,
        }
    )

    with patch.object(market_session_guard, "log", side_effect=fake_log), patch.object(
        market_session_guard, "ensure_awake_guard", return_value="awake_guard invoked"
    ), patch(
        "bot_controller.get_status", return_value="STOPPED"
    ), patch(
        "bot_controller.get_dashboard_status", return_value="STOPPED"
    ), patch(
        "bot_controller.start_bot_verified", fake_start
    ), patch(
        "bot_controller.start_dashboard_verified", fake_dash
    ), patch(
        "bot_controller.get_bot_start_command", return_value="python live_bot.py"
    ), patch(
        "markets.market_hours.any_market_open", return_value=True
    ), patch(
        "markets.market_hours.get_market_statuses", return_value={"US": True, "EU": False}
    ), patch(
        "markets.market_hours.get_open_markets", return_value=["US"]
    ), patch.dict(os.environ, {}, clear=True):
        rc = market_session_guard.main([])

    assert rc == 0
    assert fake_start.called
    assert any("DRY_RUN=False" in line for line in logs)
    assert not any("DRY_RUN would start bot" in line for line in logs)


def test_market_open_dry_run_no_start() -> None:
    logs: list[str] = []
    fake_start = MagicMock()

    with patch.object(market_session_guard, "log", side_effect=logs.append), patch.object(
        market_session_guard, "ensure_awake_guard", return_value="DRY_RUN would run awake_guard.sh"
    ), patch(
        "bot_controller.get_status", return_value="STOPPED"
    ), patch(
        "bot_controller.get_dashboard_status", return_value="STOPPED"
    ), patch(
        "bot_controller.start_bot_verified", fake_start
    ), patch(
        "bot_controller.get_bot_start_command", return_value="python live_bot.py"
    ), patch(
        "markets.market_hours.any_market_open", return_value=True
    ), patch(
        "markets.market_hours.get_market_statuses", return_value={"US": True}
    ), patch(
        "markets.market_hours.get_open_markets", return_value=["US"]
    ):
        rc = market_session_guard.main(["--dry-run"])

    assert rc == 0
    assert not fake_start.called
    assert any("DRY_RUN=True" in line for line in logs)
    assert any("DRY_RUN would start bot" in line for line in logs)


def test_all_markets_closed_no_start() -> None:
    fake_start = MagicMock()

    with patch.object(market_session_guard, "log", MagicMock()), patch(
        "bot_controller.get_status", return_value="STOPPED"
    ), patch(
        "bot_controller.get_dashboard_status", return_value="STOPPED"
    ), patch(
        "bot_controller.start_bot_verified", fake_start
    ), patch(
        "markets.market_hours.any_market_open", return_value=False
    ), patch(
        "markets.market_hours.get_market_statuses",
        return_value={"US": False, "EU": False, "UK": False, "ASIA": False},
    ), patch(
        "markets.market_hours.get_open_markets", return_value=[]
    ), patch.dict(os.environ, {}, clear=True):
        rc = market_session_guard.main([])

    assert rc == 0
    assert not fake_start.called


def test_bot_already_running_no_duplicate_start() -> None:
    fake_start = MagicMock()

    with patch.object(market_session_guard, "log", MagicMock()), patch.object(
        market_session_guard, "ensure_awake_guard", return_value="awake_guard invoked"
    ), patch(
        "bot_controller.get_status", return_value="RUNNING"
    ), patch(
        "bot_controller.get_dashboard_status", return_value="RUNNING"
    ), patch(
        "bot_controller.start_bot_verified", fake_start
    ), patch(
        "markets.market_hours.any_market_open", return_value=True
    ), patch(
        "markets.market_hours.get_market_statuses", return_value={"US": True}
    ), patch(
        "markets.market_hours.get_open_markets", return_value=["US"]
    ), patch.dict(os.environ, {}, clear=True):
        market_session_guard.main([])

    assert not fake_start.called


def test_real_start_writes_pid(tmp_path: Path) -> None:
    import bot_controller

    pid_file = tmp_path / "bot_pid.txt"
    status_file = tmp_path / "bot_status.txt"
    log_file = tmp_path / "startup_ops.log"

    real_open = open

    def selective_open(file, *args, **kwargs):
        if any(x in str(file) for x in ("bot_output.log", "bot_error.log")):
            return MagicMock()
        return real_open(file, *args, **kwargs)

    with patch.object(bot_controller, "PID_FILE", str(pid_file)), patch.object(
        bot_controller, "STATUS_FILE", str(status_file)
    ), patch.object(bot_controller, "STARTUP_LOG", str(log_file)), patch.object(
        bot_controller, "get_bot_script", return_value="-c pass"
    ), patch.object(bot_controller, "_pid_alive", return_value=True), patch.object(
        bot_controller, "_pgrep_pids", return_value=[9876]
    ), patch("builtins.open", side_effect=selective_open), patch(
        "subprocess.Popen"
    ) as popen_mock:
        proc = MagicMock()
        proc.pid = 9876
        popen_mock.return_value = proc
        detail = bot_controller.start_bot_verified()

    assert detail["pid"] == 9876
    assert pid_file.read_text(encoding="utf-8").strip() == "9876"
    assert status_file.read_text(encoding="utf-8").strip() == "RUNNING"


def main() -> int:
    tests = [
        test_default_live_not_dry_run,
        test_explicit_env_dry_run,
        test_cli_dry_run_flag,
        test_market_open_live_calls_start,
        test_market_open_dry_run_no_start,
        test_all_markets_closed_no_start,
        test_bot_already_running_no_duplicate_start,
        test_real_start_writes_pid,
    ]
    failed = 0
    for test in tests:
        name = test.__name__
        try:
            if name == "test_real_start_writes_pid":
                import tempfile

                test_real_start_writes_pid(Path(tempfile.mkdtemp()))
            else:
                test()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"\nResult: {len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
