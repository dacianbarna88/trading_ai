#!/usr/bin/env python3
"""Canonical ROI queue SSOT bootstrap — restores gitignored runtime state when absent."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from tae_roi001_challenger import (
    ROI_QUEUE_JSON,
    ensure_single_active_roi,
    save_roi_queue_ssot,
)

_BOOTSTRAP_GIT_REF = "d7b67c2:tae_roi_queue.json"


def _load_bootstrap_doc() -> dict[str, Any] | None:
    """Last known valid queue from git history (read-only)."""
    try:
        raw = subprocess.check_output(
            ["git", "show", _BOOTSTRAP_GIT_REF],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parent,
        )
        doc = json.loads(raw)
        return doc if isinstance(doc, dict) and doc.get("queue") is not None else None
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None


def bootstrap_roi_queue_if_absent() -> bool:
    """Persist SSOT when missing. Returns True if a bootstrap write occurred."""
    if ROI_QUEUE_JSON.is_file():
        return False
    doc = _load_bootstrap_doc()
    if not doc:
        return False
    doc = ensure_single_active_roi(doc)
    if doc.get("orchestration_error"):
        return False
    save_roi_queue_ssot(doc)
    return True
