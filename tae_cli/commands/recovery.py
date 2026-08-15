#!/usr/bin/env python3
"""Recovery CLI alias — same surface as migration."""

from __future__ import annotations

from tae_cli.commands import migration


def run(argv: list[str] | None = None) -> int:
    print("===== TAE RECOVERY =====")
    print("Alias of: python3 tae.py migration ...")
    print("")
    return migration.run(argv)
