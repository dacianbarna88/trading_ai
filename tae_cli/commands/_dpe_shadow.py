"""Shared DPE CLI helper — skip shadow backends that are intentionally absent on HEAD."""

from __future__ import annotations

from pathlib import Path


def run_shadow_backend(script: str, *, label: str) -> int:
    """Run a SHADOW_ONLY DPE backend; exit 0 with skip if script is not on HEAD."""
    import subprocess
    import sys

    root = Path(".")
    path = root / script
    if not path.is_file():
        print(f"{label}: backend absent on HEAD ({script}) — SKIPPED_BY_INFRASTRUCTURE_CLOSURE")
        print("Mode: SHADOW_ONLY | NO_BROKER | non-blocking for full-paper-cycle")
        return 0
    print(f">>> {sys.executable} {script}")
    return int(subprocess.run([sys.executable, script], cwd=root, check=False).returncode)
