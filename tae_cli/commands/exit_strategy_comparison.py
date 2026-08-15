"""TAE CLI — exit-strategy-comparison (READ_ONLY wrapper)."""

from __future__ import annotations


def run(args: list[str] | None = None) -> int:
    import tae_exit_strategy_comparison as cmp

    return int(cmp.main(args))
