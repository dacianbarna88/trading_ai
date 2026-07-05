#!/usr/bin/env python3
"""Tests for tae_infrastructure_health.py."""

from __future__ import annotations

import json
import os
import plistlib
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_infrastructure_health import (
    SPAWN_BLOCKED,
    build_health_report,
    get_crontab,
    launchctl_labels,
    overall_status,
    write_outputs,
)

GOOD_CRON = "market_close_runner.sh\nmarket_session_guard.py\ndaily_intelligence"
LAUNCH_AGENTS_OK = {
    "com.tradingai.startup": "pid=- last_exit=0",
    "com.tradingai.market-session-guard": "pid=- last_exit=0",
    "com.tradingai.market-open": "pid=- last_exit=0",
}


class InfrastructureHealthTest(unittest.TestCase):
    def test_missing_file_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_health_report(
                project_dir=Path(tmp),
                crontab_fn=lambda: "",
                launchctl_fn=lambda: {},
                pgrep_fn=lambda _p: 0,
            )
            self.assertEqual(report["overall_status"], "FAIL")
            names = [c["name"] for c in report["checks"]]
            self.assertTrue(any("script_exists" in n for n in names))

    def test_non_executable_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script = base / "market_open_runner.sh"
            script.write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
            for name in (
                "market_close_runner.sh",
                "startup_runner.sh",
                "awake_guard.sh",
            ):
                path = base / name
                path.write_text("#!/bin/bash\n", encoding="utf-8")
                os.chmod(path, 0o755)
            os.chmod(script, 0o644)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            exec_checks = [c for c in report["checks"] if c["name"] == "script_executable:market_open_runner.sh"]
            self.assertTrue(exec_checks)
            self.assertEqual(exec_checks[0]["status"], "FAIL")

    def test_quarantine_detected_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            with mock.patch(
                "tae_infrastructure_health.read_xattrs",
                return_value={"com.apple.quarantine": "0081;..."},
            ):
                report = build_health_report(
                    project_dir=base,
                    crontab_fn=lambda: GOOD_CRON,
                    launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                    pgrep_fn=lambda _p: 1,
                )
            quarantine = [c for c in report["checks"] if c["name"].startswith("quarantine:")]
            self.assertTrue(quarantine)
            self.assertEqual(quarantine[0]["status"], "FAIL")

    def test_provenance_info_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            (base / "startup_runner.log").write_text(
                "Launcher: tae_startup_launcher.py\nSTARTUP COMPLETE\n",
                encoding="utf-8",
            )
            (base / "market_open_runner.log").write_text("", encoding="utf-8")
            (base / "startup_launchagent.out.log").write_text("OK\n", encoding="utf-8")
            (base / "market_open_launchagent.out.log").write_text("OK\n", encoding="utf-8")
            with mock.patch(
                "tae_infrastructure_health.read_xattrs",
                return_value={"com.apple.provenance": "1"},
            ):
                report = build_health_report(
                    project_dir=base,
                    crontab_fn=lambda: GOOD_CRON,
                    launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                    pgrep_fn=lambda _p: 1,
                )
            prov = [c for c in report["checks"] if c["name"].startswith("provenance:")]
            self.assertTrue(prov)
            self.assertEqual(prov[0]["status"], "INFO")
            self.assertEqual(report["overall_status"], "PASS")

    def test_historical_cleared_log_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            (base / "market_open_runner.log").write_text("", encoding="utf-8")
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            legacy = next(c for c in report["checks"] if c["name"] == "market_open_runner_log_legacy")
            self.assertEqual(legacy["status"], "PASS")

    def test_recent_operation_not_permitted_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            err_log = base / "market_open_launchagent.err.log"
            err_log.write_text(
                "Operation not permitted\n",
                encoding="utf-8",
            )
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            mo_log = next(c for c in report["checks"] if c["name"] == "market_open_launchagent_log")
            self.assertIn(mo_log["status"], {"FAIL", "WARN"})

    def test_valid_launchagents_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            for label in LAUNCH_AGENTS_OK:
                check = next(c for c in report["checks"] if c["name"] == f"launchagent:{label}")
                self.assertEqual(check["status"], "PASS")
            self.assertIn(report["overall_status"], {"PASS", "WARN"})

    def test_exit_126_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            agents = LAUNCH_AGENTS_OK.copy()
            agents["com.tradingai.startup"] = "pid=- last_exit=126"
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: agents,
                pgrep_fn=lambda _p: 1,
            )
            startup = next(c for c in report["checks"] if c["name"] == "launchagent:com.tradingai.startup")
            self.assertEqual(startup["status"], "FAIL")
            self.assertEqual(report["overall_status"], "FAIL")

    def test_startup_launchagent_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            startup = next(c for c in report["checks"] if c["name"] == "launchagent:com.tradingai.startup")
            self.assertEqual(startup["status"], "PASS")

    def test_market_open_launchagent_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            mo = next(c for c in report["checks"] if c["name"] == "launchagent:com.tradingai.market-open")
            self.assertEqual(mo["status"], "PASS")

    def test_duplicate_bot_process_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda pattern: 2 if "live_bot.py" in pattern else 1,
            )
            bot = next(c for c in report["checks"] if c["name"] == "live_bot_process")
            self.assertEqual(bot["status"], "FAIL")

    def test_duplicate_dashboard_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda pattern: 2 if "streamlit run dashboard_v2.py" in pattern else 1,
            )
            dash = next(c for c in report["checks"] if c["name"] == "dashboard_process")
            self.assertEqual(dash["status"], "WARN")

    def test_missing_plist_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base, install_plists=False)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: {},
                pgrep_fn=lambda _p: 1,
            )
            missing = [c for c in report["checks"] if c["name"].startswith("plist_exists:")]
            self.assertTrue(missing)
            self.assertEqual(missing[0]["status"], "FAIL")

    def test_invalid_plist_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            bad = base / "launchagents" / "com.tradingai.startup.plist"
            bad.write_text("not a plist", encoding="utf-8")
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            lint = next(c for c in report["checks"] if c["name"] == "plist_lint:com.tradingai.startup")
            self.assertEqual(lint["status"], "FAIL")

    def test_no_cron_market_open_duplicate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            dup = next(c for c in report["checks"] if c["name"] == "cron_duplicate:market_open_runner\\.sh")
            self.assertEqual(dup["status"], "PASS")

    def test_cron_duplicate_market_open_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON + "\nmarket_open_runner.sh",
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            dup = next(c for c in report["checks"] if c["name"] == "cron_duplicate:market_open_runner\\.sh")
            self.assertEqual(dup["status"], "WARN")

    def test_valid_config_pass_or_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            (base / "market_open_runner.log").write_text("OK run complete\n", encoding="utf-8")
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            self.assertIn(report["overall_status"], {"PASS", "WARN"})

    def test_overall_status_aggregation(self) -> None:
        self.assertEqual(overall_status([{"status": "PASS"}]), "PASS")
        self.assertEqual(overall_status([{"status": "WARN"}]), "WARN")
        self.assertEqual(overall_status([{"status": "PASS"}, {"status": "FAIL"}]), "FAIL")

    def test_get_crontab_spawn_blocked_returns_unavailable(self) -> None:
        blocked = subprocess.CompletedProcess(["crontab", "-l"], SPAWN_BLOCKED, "", "blocked")
        with mock.patch("tae_infrastructure_health._run", return_value=blocked):
            text, available = get_crontab()
        self.assertEqual(text, "")
        self.assertFalse(available)

    def test_launchctl_spawn_blocked_returns_unavailable(self) -> None:
        blocked = subprocess.CompletedProcess(["launchctl", "list"], SPAWN_BLOCKED, "", "blocked")
        with mock.patch("tae_infrastructure_health._run", return_value=blocked):
            labels, available = launchctl_labels()
        self.assertFalse(available)
        self.assertIsNone(labels["com.tradingai.startup"])

    def test_launchctl_nonzero_exit_returns_unavailable(self) -> None:
        failed = subprocess.CompletedProcess(["launchctl", "list"], 1, "", "restricted")
        with mock.patch("tae_infrastructure_health._run", return_value=failed):
            labels, available = launchctl_labels()
        self.assertFalse(available)
        self.assertIsNone(labels["com.tradingai.startup"])

    def test_launchctl_unavailable_warn_completes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            with mock.patch("tae_infrastructure_health.launchctl_labels", return_value=({}, False)):
                report = build_health_report(
                    project_dir=base,
                    crontab_fn=lambda: GOOD_CRON,
                    pgrep_fn=lambda _p: 1,
                )
            access = next(c for c in report["checks"] if c["name"] == "launchctl:access")
            self.assertEqual(access["status"], "WARN")
            launchagent_fail = [
                c for c in report["checks"] if c["name"].startswith("launchagent:") and c["status"] == "FAIL"
            ]
            self.assertEqual(launchagent_fail, [])
            self.assertIn(report["overall_status"], {"PASS", "WARN"})

    def test_crontab_unavailable_warn_completes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            with mock.patch("tae_infrastructure_health.get_crontab", return_value=("", False)):
                report = build_health_report(
                    project_dir=base,
                    launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                    pgrep_fn=lambda _p: 1,
                )
            access = next(c for c in report["checks"] if c["name"] == "cron:access")
            self.assertEqual(access["status"], "WARN")
            self.assertIn(report["overall_status"], {"PASS", "WARN"})
            cron_fail = [c for c in report["checks"] if c["name"].startswith("cron:") and c["status"] == "FAIL"]
            self.assertEqual(cron_fail, [])

    def test_json_md_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
            report = build_health_report(
                project_dir=base,
                crontab_fn=lambda: GOOD_CRON,
                launchctl_fn=lambda: LAUNCH_AGENTS_OK.copy(),
                pgrep_fn=lambda _p: 1,
            )
            import tae_infrastructure_health as mod

            out_json = base / "health.json"
            out_md = base / "health.md"
            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD)
            mod.OUTPUT_JSON, mod.OUTPUT_MD = out_json, out_md
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD = orig
            self.assertTrue(out_json.exists())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_infrastructure_health")

    def _bootstrap_project(self, base: Path, *, install_plists: bool = True) -> None:
        for name in (
            "market_open_runner.sh",
            "market_close_runner.sh",
            "startup_runner.sh",
            "awake_guard.sh",
        ):
            path = base / name
            path.write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
            os.chmod(path, stat.S_IRWXU)
        (base / "venv" / "bin").mkdir(parents=True)
        venv_py = base / "venv" / "bin" / "python3"
        venv_py.write_text("", encoding="utf-8")
        os.chmod(venv_py, stat.S_IRWXU)
        (base / "runtime_outputs").mkdir()
        if not install_plists:
            return
        repo = Path(__file__).resolve().parent / "launchagents"
        (base / "launchagents").mkdir(parents=True, exist_ok=True)
        for name in (
            "com.tradingai.market-open.plist",
            "com.tradingai.startup.plist",
            "com.tradingai.market-session-guard.plist",
        ):
            src = repo / name
            if src.is_file():
                (base / "launchagents" / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                self._write_minimal_plist(base / "launchagents" / name, label=name.replace(".plist", ""))

    def _write_minimal_plist(self, path: Path, *, label: str) -> None:
        data = {
            "Label": label,
            "ProgramArguments": ["/bin/bash", "/tmp/test.sh"],
            "WorkingDirectory": str(path.parent.parent),
        }
        with path.open("wb") as handle:
            plistlib.dump(data, handle)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
