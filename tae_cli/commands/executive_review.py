"""TAE CLI — executive-review command (three-part READ_ONLY consolidator)."""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    import tae_executive_review as review

    return review.main()
