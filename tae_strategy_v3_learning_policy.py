#!/usr/bin/env python3
"""
TAE V3 ("V_learning") decision policy — Phase 2 DESIGN DRAFT.

PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION | live_allowed=false always.

STATUS: standalone module, NOT wired into tae_parallel_paper_runtime.py yet.
Calling `decide_v3(...)` here has no side effects on any portfolio, book, or
canonical PAPER state — it only reads runtime_outputs/longitudinal_memory/
for training data. Wiring into run_cycle() as `_run_v3_arm` is Phase 3 and is
a separate, explicitly approved step.

Design basis: TAE_V3_LEARNING_RESEARCH_NOTE.md (Phase 1). Three fixed-rule
numbers from V1/V2 are replaced with fitted/adaptive equivalents:

  1. MIN_SCORE_TO_BUY (fixed cutoff)      -> calibrated P(profit) threshold
  2. get_market_regime() BULL/BEAR only   -> BULL/BEAR x LOW/MED/HIGH vol grid
  3. equal-cash-split sizing              -> fractional-Kelly x vol-target

Portfolio guardrails (MAX_POSITIONS, cash reserve, MAX_TRADE_USD ceiling,
live_allowed=false) are intentionally NOT replaced — they are safety rails,
not trading opinions, and every arm (V1/V2/V3) keeps them identical.

No new dependency was added for the learning model: sklearn is not installed
in this venv, and pulling it in is a scope decision for the user, not this
module — so the scorer is a small hand-rolled L2-regularized logistic
regression on numpy (already a dependency), with a shrinkage-to-prior
fallback for the (currently thin) sample size. This is a deliberate,
reversible choice: swapping in sklearn later only touches LearningScorer.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
LONGITUDINAL_MEMORY_PATH = (
    PROJECT_ROOT / "runtime_outputs" / "longitudinal_memory" / "decisions.jsonl"
)

# Guardrails — same constants V1/V2 already operate under (live_bot.py).
# V3 does not get its own, looser or stricter, safety limits.
MAX_POSITIONS = 12
MIN_TRADE_USD = 250.0
MAX_TRADE_USD = 2500.0
MIN_CASH_RESERVE = 500.0

# Labels treated as positive/negative outcome, matching the scheme already
# used by TAE_LONG_TERM_LEARNING_REPORT.md ("PROMISING/CONTINUE rate").
# NEEDS_MORE_DATA is excluded from training — not yet enough evidence either way.
POSITIVE_VERDICTS = {"PROMISING", "CONTINUE", "CONTINUE_TESTING"}
NEGATIVE_VERDICTS = {"REJECT"}

# Minimum samples (per class) before the logistic model is trusted at full
# weight. Below this, predictions shrink toward the action's own base rate.
# See LearningScorer.predict_proba for the shrinkage formula.
SHRINKAGE_K = 40

# Minimum shrinkage_weight (n/(n+SHRINKAGE_K)) required before an exit
# signal is trusted enough to fire a SELL — see decide_v3. At SHRINKAGE_K=40,
# 0.3 requires roughly n>=17 resolved SELL_PAPER outcomes.
MIN_EXIT_SHRINKAGE = 0.3


# ---------------------------------------------------------------------------
# 1. Regime grid — extends live_bot.get_market_regime(), does not replace it.
# ---------------------------------------------------------------------------


@dataclass
class RegimeGrid:
    trend: str          # "BULL" | "BEAR" | "UNKNOWN"  (from live_bot.get_market_regime)
    vol_tercile: str     # "LOW" | "MED" | "HIGH" | "UNKNOWN"
    realized_vol_annualized: float | None

    @property
    def regime_id(self) -> str:
        return f"{self.trend}_{self.vol_tercile}"


def realized_vol_annualized(closes: list[float], window: int = 20) -> float | None:
    """Annualized stdev of daily log returns over the trailing `window` bars."""
    if len(closes) < window + 1:
        return None
    arr = np.asarray(closes[-(window + 1):], dtype=float)
    if np.any(arr <= 0):
        return None
    log_returns = np.diff(np.log(arr))
    daily_vol = float(np.std(log_returns, ddof=1))
    return daily_vol * math.sqrt(252)


def classify_vol_tercile(current_vol: float | None, vol_history: list[float]) -> str:
    """
    Tercile of `current_vol` against its own trailing 1y distribution.
    `vol_history` = prior daily realized_vol_annualized values (already
    computed, e.g. one per trading day over the last ~252 days). Cheap and
    dependency-free; deliberately not a fitted HMM (see research note §3).
    """
    if current_vol is None or len(vol_history) < 30:
        return "UNKNOWN"
    sorted_hist = sorted(v for v in vol_history if v is not None)
    if not sorted_hist:
        return "UNKNOWN"
    lo = sorted_hist[len(sorted_hist) // 3]
    hi = sorted_hist[(2 * len(sorted_hist)) // 3]
    if current_vol <= lo:
        return "LOW"
    if current_vol >= hi:
        return "HIGH"
    return "MED"


def classify_regime(
    *,
    market_trend: str,
    ticker_closes: list[float],
    ticker_vol_history: list[float],
    window: int = 20,
) -> RegimeGrid:
    """
    market_trend: pass-through from the existing live_bot.get_market_regime()
    call — V3 reuses that signal rather than recomputing SPY/SMA200 itself.
    ticker_closes / ticker_vol_history: per-ticker price history already
    available wherever V1/V2 pull marks today.
    """
    vol = realized_vol_annualized(ticker_closes, window=window)
    tercile = classify_vol_tercile(vol, ticker_vol_history)
    trend = market_trend if market_trend in {"BULL", "BEAR"} else "UNKNOWN"
    return RegimeGrid(trend=trend, vol_tercile=tercile, realized_vol_annualized=vol)


# ---------------------------------------------------------------------------
# 2. Scorer — replaces MIN_SCORE_TO_BUY with a fitted P(profitable).
# ---------------------------------------------------------------------------

FEATURE_NAMES = [
    "growth_score",
    "capital_efficiency",
    "horizon_alignment_score",
    "confidence",
    "horizon_conflict_flag",
    "regime_bull",
    "regime_bear",
    "vol_low",
    "vol_med",
    "vol_high",
]

ACTION_TYPES = ["BUY_PAPER", "SELL_PAPER", "HOLD_PAPER", "PROTECT_PAPER", "SKIP_PAPER"]



# Neutral fallback for horizon_alignment_score when no real value is
# available (e.g. a ticker the same-day canonical PDE pass didn't evaluate).
# This is by far the largest-magnitude learned coefficient (~0.75 vs <0.15
# for every other continuous feature) and its training mean/std are ~67/~10
# — defaulting a MISSING value to 0.0 (the generic numeric default used
# elsewhere in this function) reads as "6.8 standard deviations misaligned",
# an extreme, false negative signal that alone was enough to suppress every
# BUY prediction below the 0.5 floor in decide_v3 (found in the Phase 5 soak
# — see tae_parallel_paper_runtime.py's PDE-signal enrichment, which is the
# real fix; this is the safety net for tickers that enrichment still misses).
HORIZON_ALIGNMENT_NEUTRAL_DEFAULT = 50.0


def _extract_features(record: dict[str, Any]) -> np.ndarray:
    regime = _s(record.get("market_regime")).upper()
    vol = _s(record.get("volatility_regime")).upper()
    return np.array(
        [
            _f(record.get("growth_score")),
            _f(record.get("capital_efficiency")),
            _f(record.get("horizon_alignment_score"), HORIZON_ALIGNMENT_NEUTRAL_DEFAULT),
            _f(record.get("confidence")),
            1.0 if record.get("horizon_conflict_flag") else 0.0,
            1.0 if regime == "BULL" else 0.0,
            1.0 if regime == "BEAR" else 0.0,
            1.0 if vol == "LOW" else 0.0,
            1.0 if vol == "MED" else 0.0,
            1.0 if vol == "HIGH" else 0.0,
        ],
        dtype=float,
    )


def _s(v: Any) -> str:
    return "" if v is None else str(v)


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class TrainingSet:
    action: str
    X: np.ndarray
    y: np.ndarray
    n_pos: int
    n_neg: int
    base_rate: float
    label_source_counts: dict[str, int] = field(default_factory=dict)


# Label priority (strongest ground truth first). `validation_verdict` alone
# was tried first (Phase 2 v1) and found nearly useless: REJECT appears once
# in 303 records, so every action model degenerated to a ~1.0 base rate.
# Resolved checkpoints carry a real realized outcome (actual_profit_delta /
# pnl_pct against an actual price observation N days later) and are a much
# stronger, better-balanced ground truth (218 real failures / 561 real
# successes across 1115 resolved checkpoints) — use those first. Only fall
# back to the weaker signals for decisions that have no resolved checkpoint
# yet (recent decisions still in-flight).
LABEL_SOURCE_CHECKPOINT = "REALIZED_CHECKPOINT_OUTCOME"
LABEL_SOURCE_EXPECTED_DELTA = "EXPECTED_PROFIT_DELTA_SIGN"
LABEL_SOURCE_VERDICT = "VALIDATION_VERDICT"


def _label_from_checkpoint(cp: dict[str, Any]) -> int | None:
    if _s(cp.get("status")).upper() != "RECORDED":
        return None
    outcome = _s(cp.get("outcome")).lower()
    if outcome == "success":
        return 1
    if outcome == "failure":
        return 0
    return None  # needs_more_data at this checkpoint horizon


def _label_from_expected_delta(rec: dict[str, Any]) -> int | None:
    delta = rec.get("expected_profit_delta")
    if delta is None:
        return None
    delta = _f(delta)
    if delta > 0:
        return 1
    if delta < 0:
        return 0
    return None  # exactly zero — no signal either way


def _label_from_verdict(rec: dict[str, Any]) -> int | None:
    verdict = _s(rec.get("validation_verdict")).upper()
    if verdict in POSITIVE_VERDICTS:
        return 1
    if verdict in NEGATIVE_VERDICTS:
        return 0
    return None


def load_training_data(
    path: Path = LONGITUDINAL_MEMORY_PATH,
) -> dict[str, TrainingSet]:
    """
    One TrainingSet per action type — action identity is by far the
    strongest signal here (HOLD ~95% vs SKIP ~0% success in current data),
    so pooling across actions into one model would wash that out. A
    per-action model with shared feature extraction is the simplest design
    that respects this without hand-coding the action effect as a rule.

    A decision with resolved checkpoints contributes one training row per
    resolved checkpoint (same decision-time features, real realized label).

    One row per decision (not one per resolved checkpoint). An earlier draft
    emitted one row per resolved checkpoint (+1d, +3d, ... up to 8 per
    decision) — that inflated BUY_PAPER to 674 "samples" that were really
    ~150 underlying decisions repeated up to 8x each, understating standard
    errors and making weak correlations look more solid than the data
    supports. Fixed by taking, per decision, only the MOST MATURE resolved
    checkpoint (largest offset_days) — the least noisy available read of
    "did this decision actually work out", and exactly one row per decision
    so training rows are independent across decisions (decisions on the same
    ticker over time are still not perfectly independent of each other, but
    that's a smaller, harder-to-fix effect than 8x-replicating one outcome).
    """
    rows_by_action: dict[str, list[tuple[np.ndarray, int, str]]] = {a: [] for a in ACTION_TYPES}
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            action = _s(rec.get("action")).upper()
            if action not in rows_by_action:
                continue
            features = _extract_features(rec)

            best_offset = -1.0
            best_label: int | None = None
            for cp in rec.get("checkpoints") or []:
                lbl = _label_from_checkpoint(cp)
                if lbl is None:
                    continue
                offset = _f(cp.get("offset_days"), -1.0)
                if offset >= best_offset:
                    best_offset = offset
                    best_label = lbl
            if best_label is not None:
                rows_by_action[action].append((features, best_label, LABEL_SOURCE_CHECKPOINT))
                continue

            lbl = _label_from_expected_delta(rec)
            if lbl is not None:
                rows_by_action[action].append((features, lbl, LABEL_SOURCE_EXPECTED_DELTA))
                continue

            lbl = _label_from_verdict(rec)
            if lbl is not None:
                rows_by_action[action].append((features, lbl, LABEL_SOURCE_VERDICT))
                continue
            # No usable label from any source (e.g. NEEDS_MORE_DATA, no
            # checkpoints resolved, expected_profit_delta unset) — skip.

    out: dict[str, TrainingSet] = {}
    for action, rows in rows_by_action.items():
        if not rows:
            continue
        X = np.stack([r[0] for r in rows])
        y = np.array([r[1] for r in rows], dtype=float)
        n_pos = int(y.sum())
        n_neg = int(len(y) - n_pos)
        source_counts: dict[str, int] = {}
        for _, _, src in rows:
            source_counts[src] = source_counts.get(src, 0) + 1
        out[action] = TrainingSet(
            action=action, X=X, y=y, n_pos=n_pos, n_neg=n_neg,
            base_rate=float(y.mean()) if len(y) else 0.5,
            label_source_counts=source_counts,
        )
    return out


def _standardize(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    safe_std = np.where(std < 1e-9, 1.0, std)
    return (X - mean) / safe_std


def _fit_logistic(
    X: np.ndarray, y: np.ndarray, *, l2: float = 1.0, lr: float = 0.1, iters: int = 500
) -> np.ndarray:
    """
    Minimal L2-regularized logistic regression via batch gradient descent.
    No sklearn dependency (not installed in this venv — see module docstring).
    Fine at this scale: <10 features, low hundreds of rows, retrained fresh
    each call rather than incrementally updated (see research note §4 —
    periodic full retrain, not true streaming, at this decision frequency).
    """
    n, d = X.shape
    weights = np.zeros(d + 1)  # +1 bias
    X_aug = np.hstack([np.ones((n, 1)), X])
    for _ in range(iters):
        z = X_aug @ weights
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        grad = X_aug.T @ (p - y) / n
        grad[1:] += (l2 / n) * weights[1:]  # no penalty on bias
        weights -= lr * grad
    return weights


@dataclass
class ActionModel:
    action: str
    weights: np.ndarray | None
    mean: np.ndarray
    std: np.ndarray
    base_rate: float
    n_train: int


class LearningScorer:
    """
    Per-action-type P(profitable | features) estimator with shrinkage toward
    the action's own base rate when sample size is thin. This is what
    replaces MIN_SCORE_TO_BUY and, for V3's own decisions, replaces
    runtime_outputs/adaptive_weights (per research note §4 — one learned
    signal per arm, not two disagreeing ones).
    """

    def __init__(self) -> None:
        self.models: dict[str, ActionModel] = {}

    def fit(self, training: dict[str, TrainingSet] | None = None) -> "LearningScorer":
        training = training if training is not None else load_training_data()
        for action, ts in training.items():
            mean = ts.X.mean(axis=0)
            std = ts.X.std(axis=0)
            min_class = min(ts.n_pos, ts.n_neg)
            if min_class < 5 or len(ts.y) < 15:
                # Too little signal to fit anything beyond the base rate.
                self.models[action] = ActionModel(
                    action=action, weights=None, mean=mean, std=std,
                    base_rate=ts.base_rate, n_train=len(ts.y),
                )
                continue
            Xs = _standardize(ts.X, mean, std)
            weights = _fit_logistic(Xs, ts.y)
            self.models[action] = ActionModel(
                action=action, weights=weights, mean=mean, std=std,
                base_rate=ts.base_rate, n_train=len(ts.y),
            )
        return self

    def predict_proba(self, action: str, record: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        """
        Returns (p_profit, diagnostics). Diagnostics always include
        `n_train` and `shrinkage_weight` so a caller/report can show how much
        of the number is "learned" vs "cold-start prior" — important given
        the current sample sizes (see research note §4 sample-size caveat).
        """
        model = self.models.get(action)
        if model is None:
            return 0.5, {"n_train": 0, "shrinkage_weight": 0.0, "source": "NO_DATA_UNKNOWN_PRIOR"}

        n = model.n_train
        shrink_w = n / (n + SHRINKAGE_K)  # 0 at n=0, ->1 as n grows

        if model.weights is None:
            return model.base_rate, {
                "n_train": n, "shrinkage_weight": 0.0, "source": "BASE_RATE_ONLY_INSUFFICIENT_DATA",
            }

        x = _extract_features(record).reshape(1, -1)
        xs = _standardize(x, model.mean, model.std)
        x_aug = np.hstack([np.ones((1, 1)), xs])
        z = float((x_aug @ model.weights).item())
        p_model = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

        p_blended = shrink_w * p_model + (1 - shrink_w) * model.base_rate
        return p_blended, {
            "n_train": n, "shrinkage_weight": round(shrink_w, 3),
            "p_model": round(p_model, 4), "base_rate": round(model.base_rate, 4),
            "source": "LOGISTIC_SHRUNK_TO_BASE_RATE",
        }


# ---------------------------------------------------------------------------
# 3. Sizing — fractional Kelly x vol-target, clipped by fixed guardrails.
# ---------------------------------------------------------------------------


def kelly_fraction(p_profit: float, payoff_ratio: float = 1.5, *, fraction: float = 0.3) -> float:
    """
    f* = p - (1-p)/b   (b = payoff_ratio = avg win / avg loss)
    `fraction` applies fractional Kelly (0.3 = 30% of full Kelly) — full
    Kelly is provably too aggressive under the estimation error inherent in
    a few-hundred-sample edge estimate (research note §2). Clipped to
    [0, 1] — Kelly can go negative (don't trade) or, in edge cases, above 1.
    """
    b = max(payoff_ratio, 1e-6)
    f_star = p_profit - (1.0 - p_profit) / b
    return float(np.clip(f_star * fraction, 0.0, 1.0))


def vol_target_scalar(realized_vol: float | None, target_vol: float = 0.20) -> float:
    """size multiplier = target_vol / realized_vol, capped to keep sizing sane."""
    if not realized_vol or realized_vol <= 0:
        return 1.0
    return float(np.clip(target_vol / realized_vol, 0.25, 2.0))


def size_position(
    *,
    p_profit: float,
    regime: RegimeGrid,
    cash_available: float,
    open_positions: int,
    payoff_ratio: float = 1.5,
) -> float:
    """
    Returns a USD trade size, already clipped by the same guardrails V1/V2
    operate under (MIN/MAX_TRADE_USD, cash reserve, MAX_POSITIONS gate
    checked by the caller before calling this). This function does not
    decide BUY/HOLD/SELL — see decide_v3 — it only sizes an already-decided
    entry.
    """
    if open_positions >= MAX_POSITIONS:
        return 0.0
    investable_cash = max(cash_available - MIN_CASH_RESERVE, 0.0)
    if investable_cash <= 0:
        return 0.0

    f = kelly_fraction(p_profit, payoff_ratio=payoff_ratio)
    vol_scalar = vol_target_scalar(regime.realized_vol_annualized)
    raw = investable_cash * f * vol_scalar
    sized = float(np.clip(raw, 0.0, min(MAX_TRADE_USD, investable_cash)))
    if sized < MIN_TRADE_USD:
        return 0.0
    return round(sized, 2)


# ---------------------------------------------------------------------------
# 4. Top-level decision — mirrors the _run_v1_arm/_run_v2_arm return shape
#    (see tae_parallel_paper_runtime.py) so Phase 3 wiring is a thin wrapper,
#    not a redesign. Pure function: no portfolio mutation, no file writes.
# ---------------------------------------------------------------------------


@dataclass
class V3Decision:
    ticker: str
    action: str          # "BUY" | "HOLD" | "SELL"
    reason: str
    quantity_usd: float
    p_profit: float
    regime: str
    diagnostics: dict[str, Any] = field(default_factory=dict)


def build_pseudo_record(snap: dict[str, Any], regime: RegimeGrid) -> dict[str, Any]:
    """
    Shared feature-context builder — used both by decide_v3 (per-ticker
    decision) and by the run_cycle pre-pass that builds today's candidate
    p_profit pool for threshold calibration (see decide_v3 docstring). Kept
    as one function so the two call sites can never drift out of sync on
    what "the same features" means.
    """
    return {
        "growth_score": snap.get("score"),
        "capital_efficiency": snap.get("capital_efficiency"),
        "horizon_alignment_score": snap.get("horizon_alignment_score"),
        "confidence": snap.get("confidence", 0.5),
        "horizon_conflict_flag": snap.get("horizon_conflict_flag", False),
        "market_regime": regime.trend,
        "volatility_regime": regime.vol_tercile,
    }


def decide_v3(
    *,
    ticker: str,
    snap: dict[str, Any],
    scorer: LearningScorer,
    regime: RegimeGrid,
    has_position: bool,
    cash_available: float,
    open_positions: int,
    calibration_quantile: float = 0.7,
    candidate_pool_p_profit: list[float] | None = None,
) -> V3Decision:
    """
    calibration_quantile / candidate_pool_p_profit: this is where the "no
    fixed threshold" property actually lives (research note §5) — rather
    than a hand-picked cutoff like MIN_SCORE_TO_BUY=80, BUY fires only if
    this ticker's p_profit is in the top (1-calibration_quantile) of
    *today's* candidate pool, i.e. the bar is set by the model's own output
    distribution each cycle, not by a constant carried in source code.
    `calibration_quantile` itself is a knob (default: top 30%), not a
    per-ticker rule — same knob applies to every ticker every cycle.
    Caller (run_cycle) is expected to build `candidate_pool_p_profit` from a
    pre-pass over today's entry candidates using build_pseudo_record() +
    scorer.predict_proba() directly — passing None here degrades to a fixed
    0.5 threshold, which defeats the calibration design, so callers wiring
    this into a real cycle should always supply the pool.
    """
    pseudo_record = build_pseudo_record(snap, regime)

    if has_position:
        p_exit, diag = scorer.predict_proba("SELL_PAPER", pseudo_record)
        # MIN_EXIT_SHRINKAGE guards against acting on a coin-flip prior.
        # SELL_PAPER has very few resolved outcomes (n=3 as of the Phase 5
        # soak) -> shrinkage_weight stays near 0 and predict_proba returns
        # ~base_rate (~0.5) for every ticker. An unguarded `p_exit >= 0.5`
        # fires on that tie for essentially every open position, which
        # (caught in Phase-3 dry-run testing) causes a same-cycle
        # SELL-then-immediately-BUY-back churn loop that only burns
        # transaction costs. Requiring a minimum trained-signal weight
        # before trusting SELL_PAPER keeps that specific model out of the
        # decision until it has actually learned something.
        has_real_exit_signal = diag.get("shrinkage_weight", 0.0) >= MIN_EXIT_SHRINKAGE

        # But SELL_PAPER staying starved of data (V3 never sells -> never
        # generates a SELL_PAPER outcome -> never earns enough data to
        # sell) combined with hitting MAX_POSITIONS on day one freezes the
        # whole arm permanently: can't buy (full), can't sell (no exit
        # signal ever clears the bar). Found in the Phase 5 soak — V3 sat
        # on the same 12 positions for a week with zero realized PnL.
        # Fallback: re-score the held ticker with the much more mature
        # BUY_PAPER model — "would I still buy this today, at the current
        # price?" is a standard portfolio-review heuristic, not a new
        # fixed rule; p_rebuy < 0.5 means the model itself, with real
        # trained weight behind it, now leans against this position.
        p_rebuy, rebuy_diag = scorer.predict_proba("BUY_PAPER", pseudo_record)
        rebuy_has_signal = rebuy_diag.get("shrinkage_weight", 0.0) >= MIN_EXIT_SHRINKAGE
        sell_via_exit_model = has_real_exit_signal and p_exit > 0.5
        sell_via_rebuy_check = rebuy_has_signal and p_rebuy < 0.5

        if sell_via_exit_model or sell_via_rebuy_check:
            reason = "V3_LEARNED_EXIT_SIGNAL" if sell_via_exit_model else "V3_NO_LONGER_BUY_WORTHY"
            chosen_p = p_exit if sell_via_exit_model else p_rebuy
            chosen_diag = diag if sell_via_exit_model else rebuy_diag
            return V3Decision(
                ticker=ticker, action="SELL", reason=reason,
                quantity_usd=0.0, p_profit=chosen_p, regime=regime.regime_id, diagnostics=chosen_diag,
            )
        reason = "V3_LEARNED_HOLD_OPEN" if (has_real_exit_signal or rebuy_has_signal) else "V3_INSUFFICIENT_EXIT_SIGNAL"
        return V3Decision(
            ticker=ticker, action="HOLD", reason=reason,
            quantity_usd=0.0, p_profit=p_exit, regime=regime.regime_id, diagnostics=diag,
        )

    p_buy, diag = scorer.predict_proba("BUY_PAPER", pseudo_record)
    threshold = 0.5
    if candidate_pool_p_profit:
        sorted_pool = sorted(candidate_pool_p_profit)
        idx = min(len(sorted_pool) - 1, int(calibration_quantile * len(sorted_pool)))
        threshold = max(threshold, sorted_pool[idx])

    if p_buy < threshold:
        return V3Decision(
            ticker=ticker, action="HOLD", reason="V3_BELOW_CALIBRATED_THRESHOLD",
            quantity_usd=0.0, p_profit=p_buy, regime=regime.regime_id, diagnostics=diag,
        )

    size = size_position(
        p_profit=p_buy, regime=regime, cash_available=cash_available,
        open_positions=open_positions,
    )
    if size <= 0.0:
        return V3Decision(
            ticker=ticker, action="HOLD", reason="V3_SIZE_ZERO_AFTER_GUARDRAILS",
            quantity_usd=0.0, p_profit=p_buy, regime=regime.regime_id, diagnostics=diag,
        )
    return V3Decision(
        ticker=ticker, action="BUY", reason="V3_LEARNED_ENTRY_SIGNAL",
        quantity_usd=size, p_profit=p_buy, regime=regime.regime_id, diagnostics=diag,
    )


# ---------------------------------------------------------------------------
# Standalone smoke test — read-only, no runtime wiring. Run directly:
#   ./venv/bin/python3 tae_strategy_v3_learning_policy.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    training = load_training_data()
    print("=== V3 learning policy — training data diagnostics (read-only) ===")
    if not training:
        print("No training data found at", LONGITUDINAL_MEMORY_PATH)
    for action, ts in sorted(training.items()):
        print(
            f"{action:14s} n={len(ts.y):4d}  pos={ts.n_pos:4d}  neg={ts.n_neg:4d}  "
            f"base_rate={ts.base_rate:.3f}  sources={ts.label_source_counts}"
        )

    scorer = LearningScorer().fit(training)
    print("\n=== Fitted model summary ===")
    for action, model in sorted(scorer.models.items()):
        mode = "LOGISTIC" if model.weights is not None else "BASE_RATE_ONLY"
        print(f"{action:14s} n_train={model.n_train:4d}  mode={mode}  base_rate={model.base_rate:.3f}")

    print("\n=== Example scoring on a synthetic BULL/LOW-vol candidate ===")
    example = {
        "score": 82, "capital_efficiency": 40.0, "horizon_alignment_score": 70.0,
        "confidence": 0.6, "horizon_conflict_flag": False,
    }
    regime = RegimeGrid(trend="BULL", vol_tercile="LOW", realized_vol_annualized=0.15)
    p, diag = scorer.predict_proba(
        "BUY_PAPER",
        {**example, "market_regime": regime.trend, "volatility_regime": regime.vol_tercile},
    )
    print(f"p_profit={p:.4f}  diagnostics={diag}")
    size = size_position(p_profit=p, regime=regime, cash_available=5000.0, open_positions=3)
    print(f"sized_usd={size}")
