"""TAE CLI — PAPER-only autonomous self-improvement orchestration."""

from __future__ import annotations


def run(args: list[str] | None = None) -> int:
    from tae_self_improve import main

    return int(main(list(args or [])))

