#!/usr/bin/env python3
"""
TAE runtime dry-run resolution — explicit opt-in only, default live startup.
"""

from __future__ import annotations

import os
import sys
from typing import Any

DRY_RUN_ENV_KEYS = (
    "DRY_RUN",
    "TAE_DRY_RUN",
    "MARKET_GUARD_DRY_RUN",
)

TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_truthy(name: str) -> bool:
    value = os.getenv(name, "")
    if value is None:
        return False
    return str(value).strip().lower() in TRUTHY


def resolve_dry_run(argv: list[str] | None = None) -> tuple[bool, str]:
    """
    Return (dry_run, source).

    Dry-run is enabled only when:
    - argv contains --dry-run / -n
    - or an env var is explicitly truthy (DRY_RUN, TAE_DRY_RUN, MARKET_GUARD_DRY_RUN)
    """
    args = list(argv if argv is not None else sys.argv[1:])
    if "--dry-run" in args or "-n" in args:
        return True, "cli_flag --dry-run"

    for key in DRY_RUN_ENV_KEYS:
        if _env_truthy(key):
            return True, f"env:{key}={os.getenv(key)!r}"

    return False, "default_live"


def dry_run_diagnostics() -> dict[str, Any]:
    return {
        key: os.getenv(key)
        for key in DRY_RUN_ENV_KEYS
    }
