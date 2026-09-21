#!/usr/bin/env python3
"""
Regression coverage for the "recycled PID mistaken for the retired
parallel-paper daemon" bug (found 2026-09-21).

Root cause: _resolve_parallel_daemon_pid()'s artifact-candidate loop
(pid_file / heartbeat / runtime_status.json) only checked _pid_alive(pid)
-- true whenever *some* process with that PID number exists, regardless
of what it actually is. A stale artifact left over from the retired
com.tradingai.parallel-paper daemon (dead since 2026-08-03) named PID 581;
macOS has since recycled that PID for the unrelated system process
useractivityd, so health_snapshot() reported the retired daemon as
RUNNING. find_parallel_paper_daemon_pids() (the "discovered" fallback
path) already verified cmdline via _cmdline_is_parallel_daemon() for its
own candidates -- the fix applies that same check to artifact-declared
candidates too.
"""

from __future__ import annotations

import unittest
import unittest.mock
from pathlib import Path

import tae_parallel_paper_runtime as runtime


class ResolveParallelDaemonPidIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_dir = Path("/Users/book/trading_ai_restored")
        self.p = {"pid": Path("/nonexistent/parallel_paper.pid")}

    def test_rejects_recycled_pid_whose_cmdline_is_not_the_daemon(self) -> None:
        """The exact real scenario: artifact says PID 581, that PID is alive,
        but it's macOS's useractivityd, not tae_parallel_paper_daemon.py."""
        with (
            unittest.mock.patch.object(runtime, "_pid_alive", return_value=True),
            unittest.mock.patch(
                "core.process_identity.read_cmdline",
                return_value="/System/Library/PrivateFrameworks/UserActivity.framework/Agents/useractivityd",
            ),
            unittest.mock.patch.object(runtime, "find_parallel_paper_daemon_pids", return_value=[]),
        ):
            pid, duplicates, source = runtime._resolve_parallel_daemon_pid(
                p=self.p,
                hb={},
                rt={"pid": 581},
                project_dir=self.project_dir,
                allow_process_discovery=False,
            )
        self.assertIsNone(pid)
        self.assertEqual(duplicates, [])
        self.assertEqual(source, "absent")

    def test_accepts_a_pid_whose_cmdline_really_is_the_daemon(self) -> None:
        """A genuine daemon process must still be recognized -- the fix only
        removes false positives, it must not introduce false negatives."""
        real_cmdline = f"/usr/bin/python3 {self.project_dir}/tae_parallel_paper_daemon.py"
        with (
            unittest.mock.patch.object(runtime, "_pid_alive", return_value=True),
            unittest.mock.patch("core.process_identity.read_cmdline", return_value=real_cmdline),
            unittest.mock.patch.object(runtime, "find_parallel_paper_daemon_pids", return_value=[]),
        ):
            pid, duplicates, source = runtime._resolve_parallel_daemon_pid(
                p=self.p,
                hb={},
                rt={"pid": 4242},
                project_dir=self.project_dir,
                allow_process_discovery=False,
            )
        self.assertEqual(pid, 4242)
        self.assertEqual(duplicates, [])
        self.assertEqual(source, "runtime_status")

    def test_no_candidates_and_no_discovery_is_absent(self) -> None:
        with unittest.mock.patch.object(runtime, "find_parallel_paper_daemon_pids", return_value=[]):
            pid, duplicates, source = runtime._resolve_parallel_daemon_pid(
                p=self.p,
                hb={},
                rt={},
                project_dir=self.project_dir,
                allow_process_discovery=False,
            )
        self.assertIsNone(pid)
        self.assertEqual(duplicates, [])
        self.assertEqual(source, "absent")


if __name__ == "__main__":
    unittest.main()
