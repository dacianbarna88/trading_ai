#!/usr/bin/env python3
"""
Regression test for a real bug found 2026-09-08: generate_signals() crashed
with `NameError: name 'LIVE_SIGNALS_FILE' is not defined` at the point it
tries to write live_signals.csv (live_bot.py:708-710). The constant was
removed from live_bot.py during a recent consolidation merge (moved to
config.settings) but the write-path reference was never updated to import
it. Because this raises AFTER the per-ticker download loop completes, the
per-ticker try/except never sees it (it's outside that block) — the
exception propagated all the way out of the hourly single-shot subprocess,
silently killing live_signals.csv's refresh for over 33 hours (every
hourly cycle "succeeded" at the shell level since nothing downstream
checked this specific step's exit status).
"""

from __future__ import annotations

import unittest

import live_bot


class LiveSignalsFileConstantTest(unittest.TestCase):
    def test_live_signals_file_constant_is_importable_and_correct(self) -> None:
        self.assertTrue(hasattr(live_bot, "LIVE_SIGNALS_FILE"))
        self.assertEqual(live_bot.LIVE_SIGNALS_FILE, "live_signals.csv")


class WritePathReferencesResolveTest(unittest.TestCase):
    """Statically confirms every name the CSV-write path depends on is
    actually bound in live_bot's module namespace — the exact class of bug
    this regression guards against (a name used only inside a function
    body, so py_compile alone never catches it) — without invoking
    generate_signals() itself, which would trigger a real (paper) trading
    cycle as a side effect and is too heavy/network-dependent for a unit
    test."""

    def test_names_used_by_the_csv_write_path_are_bound(self) -> None:
        import inspect

        source = inspect.getsource(live_bot.generate_signals)
        # The exact expression that crashed: f"{LIVE_SIGNALS_FILE}.tmp"
        self.assertIn("LIVE_SIGNALS_FILE", source)
        used_names = {"LIVE_SIGNALS_FILE", "os", "pd"}
        module_globals = vars(live_bot)
        missing = [n for n in used_names if n not in module_globals]
        self.assertEqual(missing, [], f"names referenced in generate_signals() but not defined: {missing}")


if __name__ == "__main__":
    unittest.main()
