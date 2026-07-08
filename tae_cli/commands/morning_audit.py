"""TAE CLI — morning-audit command (consolidated operational audit)."""

from __future__ import annotations

import sys


def run(_args: list[str] | None = None) -> int:
    import tae_morning_operational_audit as audit

    return audit.main()
