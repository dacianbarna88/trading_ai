"""Live vs paper allocation SSOT selection (Stage 3A)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_core.governance.artifact_freshness import (
    DEFAULT_MAX_AGE_SEC,
    is_fresh,
    is_fresher_than,
    load_json_dict,
)
from research_core.meta_intelligence_runtime.unified_runtime_ssot import (
    UNIFIED_RUNTIME_JSON,
    UnifiedRuntimeSSOT,
)

PAPER_ALLOCATION_JSON = "tae_growth_intelligence.json"
STRATEGIC_ALLOCATION_JSON = "tae_strategic_allocation_runtime.json"
ALLOCATION_ENRICH_JSON = "tae_live_signals_allocation_enrich.json"

PAPER_ALLOCATION_OWNER = "tae_growth_intelligence.py"
LIVE_ALLOCATION_OWNER = UNIFIED_RUNTIME_JSON


def paper_allocation_owner() -> str:
    return PAPER_ALLOCATION_OWNER


def live_allocation_owner() -> str:
    return LIVE_ALLOCATION_OWNER


def _allocation_from_unified(root: Path) -> dict[str, Any] | None:
    ssot = UnifiedRuntimeSSOT.load(root)
    if not ssot.ok:
        return None
    rows = ssot.records_with_signal("STRONG BUY")
    if not rows:
        return None
    return {
        "allocation_score_avg": round(
            sum(float(r.get("Allocation_Score") or 0) for r in rows) / len(rows),
            2,
        ),
        "allocation_confidence_avg": round(
            sum(float(r.get("Allocation_Confidence") or 0) for r in rows) / len(rows),
            2,
        ),
        "source": UNIFIED_RUNTIME_JSON,
    }


def select_live_allocation_summary(
    root: Path | str = ".",
    *,
    max_age_sec: float = DEFAULT_MAX_AGE_SEC,
    now: float | None = None,
) -> tuple[dict[str, Any], str]:
    """Pick live-advisory allocation; stale legacy cannot override canonical unified."""
    root = Path(root)
    unified_path = root / UNIFIED_RUNTIME_JSON
    enrich_path = root / ALLOCATION_ENRICH_JSON
    strategic_path = root / STRATEGIC_ALLOCATION_JSON

    summary = _allocation_from_unified(root)
    if summary:
        return summary, UNIFIED_RUNTIME_JSON

    if enrich_path.is_file() and is_fresh(enrich_path, max_age_sec, now=now):
        payload = load_json_dict(enrich_path) or {}
        advisory = payload.get("advisory_summary")
        if isinstance(advisory, dict) and advisory:
            out = dict(advisory)
            out["source"] = ALLOCATION_ENRICH_JSON
            return out, ALLOCATION_ENRICH_JSON

    if strategic_path.is_file():
        if not is_fresh(strategic_path, max_age_sec, now=now):
            return {}, "blocked_stale_strategic"
        if unified_path.is_file() and is_fresher_than(unified_path, strategic_path):
            return {}, "blocked_stale_strategic"
        payload = load_json_dict(strategic_path) or {}
        advisory = payload.get("advisory_summary")
        if isinstance(advisory, dict) and advisory:
            out = dict(advisory)
            out["source"] = STRATEGIC_ALLOCATION_JSON
            return out, STRATEGIC_ALLOCATION_JSON

    return {}, "none"
