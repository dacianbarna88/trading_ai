#!/usr/bin/env python3
"""Research-only CLI namespace — no portfolio/execution side effects."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    print("===== TAE RESEARCH =====")
    print("Mode: RESEARCH ONLY | NO EXECUTION | NO BROKER | NO PORTFOLIO CHANGES")
    print("")
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("Usage: python3 tae.py research <subcommand>")
        print("")
        print("Subcommands:")
        print("  list     List relocated research packages under research/")
        print("  path     Print research root path")
        print("")
        print("Evidence engine (manual):")
        print("  python3 -m research.evidence.evidence_engine_v40")
        return 0
    cmd = argv[0]
    if cmd == "list":
        root = ROOT / "research"
        for child in sorted(root.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                n = sum(1 for _ in child.glob("*.py"))
                print(f"  {child.name}/  ({n} py modules)")
        return 0
    if cmd == "path":
        print(ROOT / "research")
        return 0
    print(f"Unknown research subcommand: {cmd}", file=sys.stderr)
    return 2
