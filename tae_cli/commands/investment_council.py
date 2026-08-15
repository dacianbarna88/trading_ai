"""TAE CLI — investment-council command (synthesis-only operator brief)."""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    import tae_investment_council as council

    return council.main()
