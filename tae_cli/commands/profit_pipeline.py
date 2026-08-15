"""TAE CLI — profit-pipeline command (read-only consolidation)."""

from __future__ import annotations

import sys


def run(_args: list[str] | None = None) -> int:
    from tae_profit_pipeline import main

    return main()
