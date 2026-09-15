import unittest
from unittest import mock

import tae_adaptive_deployment as adep


class GitHeadMemoizationTest(unittest.TestCase):
    """Perf fix (2026-09-15): git_head() used to shell out to `git
    rev-parse` on every call -- deployment_metadata() calls it once per
    BUY-candidate ticker via resolve_buy_notional(), and an occasional slow
    subprocess spawn showed up as a real multi-second SLOW-ticker warning
    once tae_slow_call_guard instrumentation was added to that loop. Now
    memoized per-process."""

    def setUp(self) -> None:
        adep._git_head_cache = None

    def tearDown(self) -> None:
        adep._git_head_cache = None

    def test_first_call_shells_out_and_caches(self) -> None:
        with mock.patch.object(adep.subprocess, "check_output", return_value="abc1234\n") as co:
            first = adep.git_head()
            second = adep.git_head()
        self.assertEqual(first, "abc1234")
        self.assertEqual(second, "abc1234")
        co.assert_called_once()

    def test_subprocess_failure_caches_unknown_not_a_crash(self) -> None:
        with mock.patch.object(
            adep.subprocess, "check_output", side_effect=OSError("no git")
        ) as co:
            first = adep.git_head()
            second = adep.git_head()
        self.assertEqual(first, "UNKNOWN")
        self.assertEqual(second, "UNKNOWN")
        co.assert_called_once()


if __name__ == "__main__":
    unittest.main()
