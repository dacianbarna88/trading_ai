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

Update (2026-09-12): feature-starvation fix. shadow_entry_score() was only
ever called with growth_score/confidence, leaving 9 of the model's 11
features (capital_efficiency, horizon_alignment_score, horizon_conflict_
flag, regime_bull/bear, vol_low/med/high, holding_duration_hours) at fixed
neutral defaults for every candidate -- which is why the shadow score
clustered narrowly (0.91-0.94) instead of discriminating. horizon_
alignment_score/horizon_conflict_flag are now sourced from the same
same-day canonical PDE signal file V3 itself reads
(tae_parallel_paper_runtime._load_today_pde_signals), so this module now
matches V3's own real feature coverage. Regime/capital_efficiency stay
defaulted deliberately, not by omission: V3's own production decisions
never populate them either (regime is hard-coded UNKNOWN in
_run_v3_arm; capital_efficiency is never written by
_load_today_pde_signals), so the model was never trained on real
variation of them -- inventing real values here would score against
features the model can't actually use.
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
    horizon_alignment_score: float | None = None,
    horizon_conflict_flag: bool | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Returns a small dict {p_profit, source, n_train, shrinkage_weight,
    ...} for logging, or None if scoring failed for any reason (this must
    never raise into a caller's real decision path -- shadow-only).

    horizon_alignment_score/horizon_conflict_flag (2026-09-12): the caller
    should pass these from the same same-day canonical PDE signal lookup
    V3 itself uses (tae_parallel_paper_runtime._load_today_pde_signals),
    when available -- horizon_alignment_score has by far the largest
    learned weight of any feature (see tae_strategy_v3_learning_policy.py's
    HORIZON_ALIGNMENT_NEUTRAL_DEFAULT comment), and passing only
    growth_score/confidence left 9 of 11 features defaulted to fixed
    constants for every candidate, which is why the shadow score clustered
    narrowly (0.91-0.94) instead of discriminating. market_regime /
    volatility_regime / capital_efficiency are deliberately NOT computed
    here even when real per-ticker data could be fetched: V3's own
    production decisions default those to the same neutral constants too
    (regime is hard-coded "UNKNOWN" in _run_v3_arm, and capital_efficiency
    is never populated by _load_today_pde_signals either) -- the model was
    never trained on real variation of them, so inventing real values here
    would score against features the model can't actually use, not fix
    anything."""
    moment = now or datetime.now(timezone.utc)
    try:
        scorer = _get_scorer(now=moment)
        record = {
            "growth_score": growth_score,
            "confidence": confidence,
            "horizon_alignment_score": horizon_alignment_score,
            "horizon_conflict_flag": horizon_conflict_flag,
        }
        p_profit, diag = scorer.predict_proba(action, record)
        return {"p_profit": round(float(p_profit), 4), **diag}
    except Exception as exc:  # pragma: no cover - defensive, shadow-only
        return {"error": str(exc)}
