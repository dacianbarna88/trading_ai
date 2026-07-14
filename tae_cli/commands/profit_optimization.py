"""TAE CLI — profit-optimization command (evidence-based audit)."""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    from tae_profit_optimization import main

    return main()
