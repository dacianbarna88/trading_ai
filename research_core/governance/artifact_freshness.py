"""Artifact freshness helpers for SSOT selection (Stage 3A)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DEFAULT_MAX_AGE_SEC = 72 * 3600


def artifact_mtime(path: Path) -> float | None:
    if not path.is_file():
        return None
    return path.stat().st_mtime


def artifact_age_sec(path: Path, *, now: float | None = None) -> float | None:
    mtime = artifact_mtime(path)
    if mtime is None:
        return None
    return (now or time.time()) - mtime


def is_fresh(path: Path, max_age_sec: float = DEFAULT_MAX_AGE_SEC, *, now: float | None = None) -> bool:
    age = artifact_age_sec(path, now=now)
    return age is not None and age <= max_age_sec


def load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def is_fresher_than(left: Path, right: Path) -> bool:
    left_m = artifact_mtime(left)
    right_m = artifact_mtime(right)
    if left_m is None:
        return False
    if right_m is None:
        return True
    return left_m > right_m
