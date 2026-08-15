#!/usr/bin/env python3
"""
Shared persistence for canonical PAPER learning SSOT.

PAPER_ONLY — atomic JSON writes + exclusive flock for learning state files.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_LOCK_DEPTH = 0
_LOCK_FH: Any | None = None
_LOCK_PATH: Path | None = None
_LOCK_GUARD = threading.RLock()


def atomic_write_json(path: Path, payload: dict[str, Any] | list[Any], *, sort_keys: bool = False) -> None:
    """Write JSON via temp file → fsync → os.replace. Never truncates mid-write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=sort_keys, default=str) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


class LearningLockBusy(RuntimeError):
    """Another process holds the canonical learning lock."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"DUPLICATE_LEARNING_RUNTIME lock busy: {path}")
        self.path = path


def default_lock_path(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root) / "learning_state.lock"
    env = os.environ.get("TAE_CANONICAL_LEARNING_ROOT")
    if env:
        return Path(env) / "learning_state.lock"
    return Path("runtime_outputs/canonical_learning") / "learning_state.lock"


@contextmanager
def learning_state_lock(
    lock_path: Path | None = None,
    *,
    blocking: bool = False,
) -> Iterator[Path]:
    """
    Exclusive flock around learning SSOT mutations.

    Re-entrant within the same process (depth counter) so
    run_canonical_learning_cycle → runners do not deadlock.
    """
    global _LOCK_DEPTH, _LOCK_FH, _LOCK_PATH
    path = Path(lock_path) if lock_path is not None else default_lock_path()
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK_GUARD:
        if _LOCK_DEPTH > 0 and _LOCK_PATH == path and _LOCK_FH is not None:
            _LOCK_DEPTH += 1
            try:
                yield path
            finally:
                with _LOCK_GUARD:
                    _LOCK_DEPTH = max(0, _LOCK_DEPTH - 1)
            return

        fh = path.open("a+", encoding="utf-8")
        flags = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            fcntl.flock(fh.fileno(), flags)
        except BlockingIOError as exc:
            fh.close()
            raise LearningLockBusy(path) from exc

        _LOCK_FH = fh
        _LOCK_PATH = path
        _LOCK_DEPTH = 1
        try:
            yield path
        finally:
            with _LOCK_GUARD:
                _LOCK_DEPTH = max(0, _LOCK_DEPTH - 1)
                if _LOCK_DEPTH == 0 and _LOCK_FH is not None:
                    try:
                        fcntl.flock(_LOCK_FH.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                    try:
                        _LOCK_FH.close()
                    except OSError:
                        pass
                    _LOCK_FH = None
                    _LOCK_PATH = None


def load_json_safe(path: Path) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    """Return (payload, error). error set on corruption / unreadable."""
    p = Path(path)
    if not p.is_file():
        return None, None
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable:{exc}"
    except json.JSONDecodeError as exc:
        return None, f"json_corrupt:{exc}"
    if not isinstance(data, (dict, list)):
        return None, "json_type_invalid"
    return data, None
