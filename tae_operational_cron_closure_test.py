#!/usr/bin/env python3
"""TEST_ONLY — operational cron closure invariants for HEAD/main."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CRON_SSOT = ROOT / ".cron_tae_canonical.install"
SCANNER = ROOT / "tae_scanner_refresh.sh"


class TestOperationalCronClosure(unittest.TestCase):
    def test_cron_ssot_exists(self):
        self.assertTrue(CRON_SSOT.is_file())

    def test_no_active_tae_py_entries(self):
        lines = CRON_SSOT.read_text(encoding="utf-8").splitlines()
        active = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        stale = [l for l in active if "tae.py" in l]
        self.assertEqual(stale, [], msg=f"active tae.py cron entries remain: {stale}")

    def test_active_targets_exist(self):
        lines = CRON_SSOT.read_text(encoding="utf-8").splitlines()
        active = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        self.assertGreaterEqual(len(active), 1)
        for line in active:
            # Extract quoted paths that look like project scripts
            paths = re.findall(r'"([^"]+)"', line)
            scriptish = [p for p in paths if p.endswith((".sh", ".py"))]
            self.assertTrue(scriptish, msg=f"no script path in cron line: {line}")
            for p in scriptish:
                self.assertTrue(Path(p).exists(), msg=f"missing cron target: {p}")

    def test_scanner_refresh_present_and_executable_path(self):
        self.assertTrue(SCANNER.is_file())
        text = CRON_SSOT.read_text(encoding="utf-8")
        self.assertIn("tae_scanner_refresh.sh", text)

    def test_retired_tae_py_roles_are_documented(self):
        text = CRON_SSOT.read_text(encoding="utf-8")
        self.assertIn("RETIRED_STALE_TAE_PY", text)
        self.assertIn("paper-mark-to-market", text)
        self.assertIn("self-improve", text)
        self.assertIn("full-paper-cycle", text)

    def test_no_broker_policy_marker(self):
        text = CRON_SSOT.read_text(encoding="utf-8")
        self.assertIn("NO_BROKER", text)
        self.assertIn("PAPER_ONLY", text)


if __name__ == "__main__":
    unittest.main()
