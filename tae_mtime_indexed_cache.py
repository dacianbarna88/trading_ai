"""Shared helper for the "index a growing per-ticker journal once per file
version, not once per call" pattern.

Extracted 2026-09-15 after the same bug -- a function called once per ticker
in a hot per-ticker loop (100-500+ tickers/cycle) re-reading and re-parsing
an entire, ever-growing journal file from scratch on every call -- was found
and independently fixed four separate times in tae_paper_execution.py and
tae_strategy_v2_kelly_sizing.py, one of which was an incomplete fix that
directly caused a real 14h45m production hang. There was no shared utility
making "cache it, keyed by mtime" the obvious default, so it kept getting
reinvented or skipped. This module is that default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable


def iter_jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    """Yield each dict row of a JSONL file, tolerant of blank/malformed
    lines. Yields nothing (does not raise) if the file can't be read."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def group_rows_by_key(
    rows: Iterable[Any], *, key_fn: Callable[[dict[str, Any]], str]
) -> dict[str, list[dict[str, Any]]]:
    """Group dict rows by key_fn(row), preserving each group's relative
    order. Non-dict rows and empty keys are skipped."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = key_fn(row)
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def cached_mtime_index(
    path: Path,
    *,
    cache: dict[str, Any],
    build_index: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """Return build_index(path)'s result, rebuilding it only when path's
    mtime has changed since the last call -- otherwise reuse what's already
    in `cache`.

    `cache` is owned by the caller: a plain module-level dict, one per
    journal (e.g. {"mtime": None, "index": {}}), so this stays trivially
    testable and side-effect free beyond that one dict. Returns {} (without
    touching `cache`) if the file can't be stat'd.

    Keyed on (path, mtime) rather than mtime alone -- a cache dict reused
    across different paths (e.g. tests repointing a module-level path
    constant at a fresh temp file per test) must not serve a stale index
    built for a previous path that happened to share an mtime.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    path_str = str(path)
    if cache.get("mtime") != mtime or cache.get("path") != path_str:
        cache["index"] = build_index(path)
        cache["mtime"] = mtime
        cache["path"] = path_str
    return cache.get("index", {})
