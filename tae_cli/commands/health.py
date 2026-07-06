"""TAE CLI — health command (delegates to tae_quick_health_check)."""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    import tae_quick_health_check as qhc

    return qhc.main()
