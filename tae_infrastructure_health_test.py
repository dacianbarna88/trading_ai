#!/usr/bin/env python3
"""Tests for tae_infrastructure_health.py."""

from __future__ import annotations

import json
import os
import plistlib
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_infrastructure_health import (
    build_health_report,
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

    def test_provenance_warn_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._bootstrap_project(base)
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
            self.assertEqual(prov[0]["status"], "WARN")
            self.assertNotEqual(report["overall_status"], "FAIL")

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
