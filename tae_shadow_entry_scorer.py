"""Shared shadow entry-scorer: logs a learned P(profitable) alongside an
arm's own entry decision, without ever changing that decision.

Context (2026-09-09): the whole system's aggregate return has hovered
around 0% for ~6 weeks (canonical account: -0.62% total, -3.34% from
peak). Root-cause analysis on 2,987 real (checkpoint-confirmed) BUY_PAPER
outcomes found the single-score entry threshold (MIN_SCORE_TO_BUY-style,
used by V1 and V2's `favorable` gate) is a weak, NON-monotonic predictor
of real outcomes (score 70-79 -> 1.1% win rate; score 90-99 -> 93.5% win
rate) -- a flat threshold cannot separate these. tae_strategy_v3_learning_
policy.LearningScorer already solves this correctly for V3 (a multi-
feature logistic model with shrinkage), trained on the shared canonical
BUY_PAPER pool (8,000+ samples) plus the V1/V2/V3 cross-arm bridge.

Rather than immediately gating V1/V2's real (paper) trades on this model
-- which would be a real behavior change with no track record yet on
THESE arms' own candidate distributions -- this module wires it in as a
SHADOW signal only: computed and logged next to every real entry
decision, changing nothing about whether the trade executes. Once enough
shadow predictions have matured against real outcomes, promoting it to
an actual gate (or blend) is a data-backed decision, not a guess -- the
same "prove it before it controls money" discipline this project already
uses elsewhere (see the SHADOW_SIZING_COMPARISON experiment convention in
V2's own trade records).

Fit-once-per-cycle caching: LearningScorer().fit() takes ~1s over 8,000+
samples; calling it once per candidate ticker (V1 evaluates ~100/cycle)
would be needless repeated work of exactly the kind found and fixed
elsewhere this session. Cached module-level with a TTL comfortably
shorter than the hourly cycle cadence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SHADOW_SCORER_CACHE_TTL_SECONDS = 1800.0

_cache: dict[str, Any] = {}


def _get_scorer(*, now: datetime):
    cached = _cache.get("scorer")
    if cached is not None and (now - cached["fitted_at"]).total_seconds() < SHADOW_SCORER_CACHE_TTL_SECONDS:
        return cached["scorer"]
    import tae_strategy_v3_learning_policy as v3pol

    scorer = v3pol.LearningScorer().fit()
    _cache["scorer"] = {"fitted_at": now, "scorer": scorer}
    return scorer


def shadow_entry_score(
    *,
    action: str = "BUY_PAPER",
    growth_score: float | None,
    confidence: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Returns a small dict {p_profit, source, n_train, shrinkage_weight,
    ...} for logging, or None if scoring failed for any reason (this must
    never raise into a caller's real decision path -- shadow-only)."""
    moment = now or datetime.now(timezone.utc)
    try:
        scorer = _get_scorer(now=moment)
        record = {"growth_score": growth_score, "confidence": confidence}
        p_profit, diag = scorer.predict_proba(action, record)
        return {"p_profit": round(float(p_profit), 4), **diag}
    except Exception as exc:  # pragma: no cover - defensive, shadow-only
        return {"error": str(exc)}
