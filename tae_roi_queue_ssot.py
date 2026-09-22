#!/usr/bin/env python3
"""Canonical ROI queue SSOT bootstrap — restores gitignored runtime state when absent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tae_roi001_challenger import (
    ROI_QUEUE_JSON,
    ensure_single_active_roi,
    save_roi_queue_ssot,
)

# Last known valid queue, snapshotted 2026-07-31 (previously read via
# `git show d7b67c2:tae_roi_queue.json` -- that commit was a local-only
# WIP commit, never pushed to origin and not part of main's history, so
# this bootstrap silently failed (returned None) anywhere except the one
# machine where it happened to still be reachable). Committed directly so
# recovery works identically on every checkout.
_BOOTSTRAP_SNAPSHOT_PATH = Path(__file__).resolve().parent / "tae_roi_queue_bootstrap_snapshot.json"


def _load_bootstrap_doc() -> dict[str, Any] | None:
    """Last known valid queue, from the committed bootstrap snapshot (read-only)."""
    try:
        raw = _BOOTSTRAP_SNAPSHOT_PATH.read_text(encoding="utf-8")
        doc = json.loads(raw)
        return doc if isinstance(doc, dict) and doc.get("queue") is not None else None
    except (OSError, json.JSONDecodeError):
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
