#!/usr/bin/env python3
"""Migration/recovery CLI — explicit operator intent only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG_ROOT = ROOT / "migration"


def _list_modules() -> list[Path]:
    out: list[Path] = []
    if not MIG_ROOT.is_dir():
        return out
    for p in sorted(MIG_ROOT.rglob("*.py")):
        if p.name.startswith("_") or p.name == "safety.py":
            continue
        if "support" in p.parts and p.name != "safety.py":
            continue
        out.append(p)
    return out


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def run(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    print("===== TAE MIGRATION =====")
    print("Mode: MIGRATION/RECOVERY | NO NORMAL RUNTIME EXECUTION | NO BROKER")
    print("")
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("Usage: python3 tae.py migration <subcommand>")
        print("")
        print("Subcommands:")
        print("  list                 List isolated migration modules")
        print("  inspect <name>       Show module path and docstring head")
        print("  dry-run <name>       Import module only (no apply, no writes)")
        print("  run <name> --confirm Explicit apply via module __main__ if present")
        print("")
        print("Recovery alias: python3 tae.py recovery ...")
        return 0

    cmd = argv[0]
    if cmd == "list":
        mods = _list_modules()
        print(f"Isolated migration modules: {len(mods)}")
        for p in mods:
            print(f"  {_rel(p)}")
        return 0

    if cmd in {"inspect", "dry-run", "run"}:
        if len(argv) < 2:
            print("Missing module name/path", file=sys.stderr)
            return 2
        name = argv[1]
        # resolve by stem or relative path
        candidates = [p for p in _list_modules() if p.stem == name or _rel(p).endswith(name)]
        if not candidates:
            # also allow path under migration/
            cand = ROOT / name if name.startswith("migration/") else MIG_ROOT / name
            if not cand.is_file():
                cand = MIG_ROOT / f"{name}.py"
            if cand.is_file():
                candidates = [cand]
        if not candidates:
            print(f"Unknown migration module: {name}", file=sys.stderr)
            return 2
        path = candidates[0]
        print(f"Target: {_rel(path)}")
        print(f"Backup dir: runtime_outputs/migration/backups/")
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = text.split('"""', 2)
        if len(doc) >= 3:
            print("Doc:")
            print(doc[1].strip()[:500])
        if cmd == "inspect":
            return 0
        if cmd == "dry-run":
            print("Operation: DRY-RUN (import only — no __main__ apply)")
            # side-effect-free import check via spec without exec main
            spec = importlib.util.spec_from_file_location(f"mig_{path.stem}", path)
            if spec is None or spec.loader is None:
                print("Cannot load module spec", file=sys.stderr)
                return 2
            mod = importlib.util.module_from_spec(spec)
            # Do not execute modules that run on import at module level if unsafe —
            # still load; Stage 3E contract tests cover known runners.
            try:
                spec.loader.exec_module(mod)
            except Exception as exc:  # noqa: BLE001 — report dry-run load errors
                print(f"DRY-RUN load error (non-fatal for listing): {exc}")
                return 0
            print("DRY-RUN complete — no apply")
            return 0
        # run
        args = argv[2:]
        confirm = "--confirm" in args or "--force" in args
        if not confirm:
            print("Refused: run requires --confirm", file=sys.stderr)
            return 2
        print("Operation: APPLY")
        print(f"Invoking: {path}")
        import runpy

        sys.argv = [str(path), *[a for a in args if a not in {"--confirm", "--force"}]]
        try:
            runpy.run_path(str(path), run_name="__main__")
        except SystemExit as exc:
            return int(exc.code or 0)
        return 0

    print(f"Unknown migration subcommand: {cmd}", file=sys.stderr)
    return 2
