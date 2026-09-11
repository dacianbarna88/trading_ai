"""Shared SIGALRM-based hard timeout for network calls (yfinance, urllib, ...).

Same fix class as the 2026-09-08 live_bot.py incident: a stalled TCP
connection can hang a blocking network call indefinitely even when the
library's own timeout= kwarg is set (yfinance/curl_cffi and urllib both
demonstrated this in practice) -- the library-level timeout does not
reliably bound the call. SIGALRM bounds it regardless of what the
underlying library is doing internally.

Deliberately kept separate from live_bot.py's own _yfinance_hard_timeout
(same pattern, intentionally duplicated) so this module has no dependency
on live_bot.py, which is on the project's do-not-rewrite list.

Main-thread only (SIGALRM requirement) -- every call site in this project
runs from the single-threaded hourly cycle, so this is not a new constraint.
"""

from __future__ import annotations

import signal
from contextlib import contextmanager
from typing import Iterator


class NetworkCallTimedOut(Exception):
    pass


@contextmanager
def hard_timeout(seconds: float) -> Iterator[None]:
    def _on_alarm(signum: int, frame: object) -> None:
        raise NetworkCallTimedOut(f"network call exceeded {seconds}s hard bound")

    previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
