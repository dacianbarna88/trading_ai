#!/usr/bin/env python3
"""TAE CLI — today activity report (read-only)."""

from __future__ import annotations


def run(args: list[str] | None = None) -> int:
    from tae_today_activity_report import main

    return main(list(args) if args is not None else [])
