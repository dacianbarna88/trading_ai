"""Shared fundamental quality-score math — Sprint 3 Phase 4.

A cross-sectional composite (z-scored against the same watchlist/universe
tae_fundamentals_snapshot.py fetched), not an arbitrary absolute cutoff —
same lesson already learned twice this sprint (the original technical
score's flat threshold, and the earlier score-decile finding that a
relative bar beats a fixed one).

Fields and direction (from tae_fundamentals_snapshot.FIELDS):
  higher-is-better: returnOnEquity, earningsGrowth, revenueGrowth, profitMargins
  lower-is-better:  pegRatio, debtToEquity
(trailingPE/forwardPE/priceToBook/marketCap/averageVolume are available in
the snapshot but deliberately excluded from the composite here — PE/PB
without a growth or sector adjustment are ambiguous in direction, and
averageVolume is already Phase 2's own signal.)

Backtest-first, same discipline as the rest of Sprint 3
(tae_fundamental_quality_backtest.py) — built to test whether high
composite quality at entry correlates with realized PnL before this
gates or scores anything live.
"""

from __future__ import annotations

import statistics
from typing import Any

FIELDS_HIGHER_BETTER = ["returnOnEquity", "earningsGrowth", "revenueGrowth", "profitMargins"]
FIELDS_LOWER_BETTER = ["pegRatio", "debtToEquity"]


def _zscores(values: dict[str, float | None]) -> dict[str, float | None]:
    nums = [v for v in values.values() if isinstance(v, (int, float))]
    if len(nums) < 2:
        return {k: None for k in values}
    mean = statistics.mean(nums)
    std = statistics.pstdev(nums)
    if std == 0:
        return {k: (0.0 if isinstance(v, (int, float)) else None) for k, v in values.items()}
    return {k: ((v - mean) / std if isinstance(v, (int, float)) else None) for k, v in values.items()}


def compute_quality_scores(snapshot: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    """Cross-sectional composite z-score across every ticker in
    `snapshot` (ticker -> field dict, e.g. tae_fundamentals_snapshot's
    output). None for a ticker means too little data to score it, not a
    bad score — callers must not treat None as "worst"."""
    per_field_z: dict[str, dict[str, float | None]] = {}
    for field in FIELDS_HIGHER_BETTER + FIELDS_LOWER_BETTER:
        raw = {t: (row or {}).get(field) for t, row in snapshot.items()}
        z = _zscores(raw)
        if field in FIELDS_LOWER_BETTER:
            z = {t: (-v if v is not None else None) for t, v in z.items()}
        per_field_z[field] = z

    composite: dict[str, float | None] = {}
    for t in snapshot:
        zs = [per_field_z[f][t] for f in per_field_z if per_field_z[f].get(t) is not None]
        composite[t] = (sum(zs) / len(zs)) if zs else None
    return composite
