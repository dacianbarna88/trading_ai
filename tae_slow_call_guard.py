"""Reusable "warn if this per-item call took too long" diagnostic.

Extracted 2026-09-15 from tae_canonical_dual_strategy.py's inline
SLOW_TICKER_THRESHOLD_SEC block (added 2026-09-12 after a real ~1h45m hang
in that module's per-ticker loop). That log line is what made the real
2026-09-14/15 14h45m hang's two root causes discoverable via `tail` on the
log instead of live process forensics -- but it only existed in the one
module where the earlier incident happened. This makes it trivial to apply
at every other per-ticker/per-item hot loop, so a *future* instance of the
same "re-parse a growing journal per-ticker" bug class surfaces as a log
line within the first slow cycle instead of requiring another multi-hour
outage to discover.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

DEFAULT_THRESHOLD_SEC = 2.0


@contextmanager
def warn_if_slow(label: str, *, threshold_sec: float = DEFAULT_THRESHOLD_SEC) -> Iterator[None]:
    """Time the wrapped block; print a ">>> {label} elapsed=Xs" line if it
    took at least `threshold_sec`. Silent otherwise. Never suppresses an
    exception raised inside the wrapped block -- if the caller wants to
    catch/continue on error (e.g. to isolate one ticker's failure in a
    per-ticker loop), do that inside the `with` body, same as before."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        if elapsed >= threshold_sec:
            print(f">>> {label} elapsed={elapsed:.1f}s", flush=True)
