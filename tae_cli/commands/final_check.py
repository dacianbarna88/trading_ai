"""TAE CLI — final-check (non-destructive closure verification)."""

from __future__ import annotations


def run(args: list[str] | None = None) -> int:
    import tae_final_check as fc

    return fc.main(list(args or []))
