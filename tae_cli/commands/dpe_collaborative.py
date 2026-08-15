"""TAE CLI — dpe-collaborative command (Collaborative Paper Executor)."""

from __future__ import annotations

from pathlib import Path

from tae_cli.commands._dpe_shadow import run_shadow_backend

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print(f"===== TAE DPE-COLLABORATIVE — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no execution or live change")
    print("")
    return int(run_shadow_backend("tae_dpe_collaborative_executor.py", label="dpe-collaborative"))
