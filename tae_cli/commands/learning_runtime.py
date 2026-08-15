#!/usr/bin/env python3
"""TAE CLI — canonical PAPER learning runtime commands."""

from __future__ import annotations

import json
from typing import Any


def _print(obj: Any) -> None:
    if isinstance(obj, dict):
        print(json.dumps(obj, indent=2, sort_keys=True, default=str))
    else:
        print(obj)


def run_start(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_runtime import health_snapshot, start_runtime

    print("===== TAE LEARNING-RUNTIME-START — PAPER ONLY =====")
    st = start_runtime(spawn_daemon=True)
    if st.get("duplicate"):
        print("DUPLICATE_BLOCKED pid", st.get("pid"))
        _print(st)
        return 2
    h = health_snapshot()
    _print({"start": st, "health": h})
    return 0 if st.get("ok") else 1


def run_stop(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_runtime import stop_runtime

    print("===== TAE LEARNING-RUNTIME-STOP =====")
    st = stop_runtime(remove_enabled_flag=True)
    _print(st)
    return 0 if st.get("ok") else 1


def run_status(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_runtime import status_snapshot

    print("===== TAE LEARNING-RUNTIME-STATUS =====")
    _print(status_snapshot())
    return 0


def run_cycle(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_runtime import run_canonical_learning_cycle

    print("===== TAE LEARNING-RUNTIME-CYCLE — PAPER ONLY =====")
    force = bool(_args and "--force" in (_args or []))
    result = run_canonical_learning_cycle(
        source="learning-runtime-cycle",
        write_reports=False,
        force=force,
    )
    _print(result)
    if result.get("result") == "DUPLICATE_RUNTIME":
        return 2
    if result.get("result") == "PAPER_SAFETY_VIOLATION":
        return 3
    if result.get("result") == "STATE_CORRUPTION":
        return 4
    return 0 if result.get("ok") else 1


def run_health(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_autostart import status_autostart
    from tae_canonical_learning_runtime import health_snapshot

    print("===== TAE LEARNING-RUNTIME-HEALTH =====")
    h = health_snapshot()
    h["autostart"] = status_autostart()
    _print(h)
    ok_states = {
        "HEALTHY",
        "RUNNING_NO_ELIGIBLE_OUTCOMES",
    }
    return 0 if h.get("overall_status") in ok_states else 1


def run_autostart_install(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_autostart import install_autostart

    print("===== TAE LEARNING-RUNTIME-AUTOSTART-INSTALL — PAPER ONLY =====")
    st = install_autostart()
    _print(st)
    return 0 if st.get("ok") else 1


def run_autostart_status(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_autostart import status_autostart

    _print(status_autostart())
    return 0


def run_autostart_remove(_args: list[str] | None = None) -> int:
    from tae_canonical_learning_autostart import remove_autostart

    _print(remove_autostart())
    return 0
