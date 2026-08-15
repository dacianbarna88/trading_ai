"""TAE CLI — canonical unit/integration test suite runner.

Discovers project ``*_test.py`` hermetically (excludes archive, restore snapshots,
venv, runtime_outputs). Exit non-zero on failure/error.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXCLUDE_DIR_NAMES = frozenset(
    {
        ".git",
        "venv",
        ".venv",
        "archive",
        "__pycache__",
        "node_modules",
        "restore_2026_06_22",
        "runtime_outputs",
        ".cursor",
        "htmlcov",
        ".pytest_cache",
        ".mypy_cache",
        "research",  # research package demos/engines — not the unit suite
    }
)


def _should_skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIR_NAMES or name.startswith("restore_")


def iter_test_modules() -> list[str]:
    modules: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if not _should_skip_dir(d))
        rel_dir = Path(dirpath).resolve().relative_to(ROOT)
        rel_s = str(rel_dir).replace("\\", "/")
        if rel_s.startswith("research/") or rel_s == "research":
            continue
        for name in sorted(filenames):
            if not name.endswith("_test.py"):
                continue
            rel = (rel_dir / name).as_posix() if str(rel_dir) != "." else name
            mod = rel[:-3].replace("/", ".")  # strip .py
            modules.append(mod)
    return modules


def discover_suite() -> tuple[unittest.TestSuite, list[str]]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    errors: list[str] = []
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for modname in iter_test_modules():
        try:
            module = importlib.import_module(modname)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{modname}: {type(exc).__name__}: {exc}")
            continue
        suite.addTests(loader.loadTestsFromModule(module))
    return suite, errors


def run(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tae.py test", description="Canonical TAE unittest suite")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="Print discovered test modules and exit",
    )
    parsed = parser.parse_args(list(args or []))

    os.chdir(ROOT)
    modules = iter_test_modules()
    if parsed.list_modules:
        for m in modules:
            print(m)
        print(f"modules={len(modules)}")
        return 0

    t0 = time.time()
    suite, discovery_errors = discover_suite()
    count = suite.countTestCases()
    for err in discovery_errors:
        print(f"DISCOVERY_ERROR {err}", file=sys.stderr)
    verbosity = 0 if parsed.quiet else (2 if parsed.verbose else 1)
    result = unittest.TextTestRunner(verbosity=verbosity, buffer=True).run(suite)
    elapsed = time.time() - t0
    failed = len(result.failures)
    errors = len(result.errors) + len(discovery_errors)
    skipped = len(result.skipped)
    ok = result.wasSuccessful() and not discovery_errors
    print(
        "\n===== TAE TEST SUITE =====\n"
        f"modules={len(modules)} discovered={count} "
        f"failures={failed} errors={errors} skipped={skipped} "
        f"ok={ok} elapsed_s={elapsed:.1f}",
        flush=True,
    )
    return 0 if ok else 1
