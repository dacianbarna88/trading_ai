# TAE V3 ("V_learning") — Research Note (Phase 1)

**Status:** DOCUMENT ONLY — no code, no config change, no execution.
**Scope:** synthesis to ground Phase 2 design, not a literature review.
**Constraint carried forward:** PAPER_ONLY · NO_BROKER · NO_LIVE_PROMOTION at every phase.

## 1. What "no fixed rules" means operationally

V1/V2 decide with hand-set thresholds (`Score >= MIN_SCORE_TO_BUY`, `SMA200`
regime veto, equal-cash-split sizing — see `live_bot.py:get_dynamic_trade_size`,
`get_market_regime`). "No fixed rules" for V3 does not mean no structure — it
means every number that currently comes from a human-picked constant should
instead come from a statistic fit to data and refreshed on a schedule. Three
areas need this treatment: **position sizing**, **regime awareness**, and
**entry/exit scoring**. Portfolio-level guardrails (max positions, cash
reserve, `live_allowed=false`) stay hard-coded — those are safety rails, not
trading opinions, and every serious adaptive system keeps them fixed too.

## 2. Adaptive position sizing

Two well-established, low-complexity approaches, both usable without a full
ML stack:

- **Volatility targeting.** Size a position so its expected contribution to
  portfolio volatility is constant: `size ∝ target_vol / realized_vol(ticker)`,
  with `realized_vol` as a rolling (e.g. 20-day) annualized stdev of returns.
  This alone would already be an improvement over V1/V2's equal-cash-split —
  it naturally shrinks size in choppy names and grows it in calm ones.
- **Fractional Kelly.** `f* = edge / odds` from the classic Kelly criterion,
  scaled down (typically 1/4–1/2 Kelly) because edge estimates from a few
  hundred decisions are noisy and full Kelly is provably too aggressive under
  estimation error. `edge` here would come from the scorer in §4 (predicted
  P(profitable) per ticker), not a fixed hit-rate assumption.
- **Practical combination:** `size = fractional_kelly_fraction × vol_target_scalar × available_cash`,
  clipped by the existing `MAX_POSITION_NOTIONAL` / cash-reserve guardrails.
  This is the standard pattern in systematic execution (vol-target sets the
  risk budget, Kelly-derived edge allocates within it).

Data already in-repo that a vol-target/Kelly sizer could consume without new
plumbing: live price history already pulled per ticker (`yfinance` calls in
`live_bot.py`), and outcome-labeled decisions in
`runtime_outputs/longitudinal_memory/decisions.jsonl` (303 records today) for
estimating `edge` per action type.

## 3. Regime detection

There is already a regime signal in production: `live_bot.py:get_market_regime()`
— binary BULL/BEAR from `SPY close vs SMA200`. It is currently informational
only in the per-ticker path (log shows "Global market gate disabled;
evaluating BUY per ticker session"). For V3 this is a reasonable **starting
point to extend, not replace**:

- **Add a volatility dimension.** Combine the existing trend signal (SMA200
  sign) with a realized-vol percentile (e.g. 20-day vol vs its trailing
  1-year distribution: LOW / MEDIUM / HIGH tercile). Result: a simple 2×3
  regime grid (BULL/BEAR × LOW/MED/HIGH vol) instead of one binary flag —
  cheap to compute, no new dependency, directly reusable by the sizer in §2
  (vol_target_scalar already needs realized vol) and the scorer in §4 (regime
  as a feature).
- **Skip HMM/changepoint models for v1 of V3.** They're the standard
  "next step up" in regime detection (2-3 state Gaussian HMM on returns, or
  CUSUM changepoint on the equity curve), but they add an estimation/retrain
  surface and a failure mode ("regime got stuck") that isn't justified before
  the simple grid has been tried and measured. Worth revisiting in a later
  iteration if the simple grid underperforms — not a Phase-2 requirement.

## 4. Replacing fixed-threshold scoring with an online/ensemble scorer

Today: `Score >= MIN_SCORE_TO_BUY` is a fixed cutoff on a hand-built score.
The adaptive replacement pattern used by most systematic shops for this exact
problem:

- **Train a probability model, not a cutoff.** A lightweight online-updatable
  classifier (logistic regression or gradient-boosted trees, retrained on a
  rolling window — daily or weekly, not truly online/streaming, which isn't
  necessary at this decision frequency) predicts `P(profitable | features)`
  per ticker/signal. Features: whatever V1/V2 already compute as "Score"
  inputs, plus the regime grid from §3.
- **Label source already exists.** `runtime_outputs/longitudinal_memory/`
  already stores decision → outcome pairs (PROMISING/CONTINUE/REJECT,
  303 records, action-level success rates already computed — e.g. today's
  data shows BUY_PAPER at 41.2% success over 257 decisions). This is a
  ready-made, if still small, training set. Sample size caveat: 257 BUY
  decisions is thin for a model with more than a handful of features —
  Phase 2 should size the feature count to the data, not the other way round,
  and treat early V3 output as high-variance until the sample grows during
  the Phase-5 soak.
- **Ensembling over retrains, not over models, to start.** Rather than
  standing up multiple model families immediately, the simplest defensible
  "ensemble" is: keep the last N periodic retrains and average their output
  probabilities — cheap variance reduction, no extra infra.
- **This subsumes, doesn't duplicate, `adaptive_weights`.** The existing
  `runtime_outputs/adaptive_weights/` mechanism nudges PDE scores with small
  fixed biases per action type. A trained P(profitable) model is a strict
  generalization of that (a bias is a 1-parameter, 0-feature version of the
  same idea) — V3's scorer should replace this mechanism for its own
  decisions rather than run both, to avoid two disagreeing "learned" signals
  inside the same arm.

## 5. How this composes into V3's decision function (preview for Phase 2)

```
for each ticker:
    regime      = regime_grid(spy, ticker_vol)              # §3
    p_profit    = scorer.predict(features, regime)          # §4, trained model
    edge        = f(p_profit)                                # §2, Kelly input
    raw_size    = fractional_kelly(edge) * vol_target_scalar(ticker_vol)
    size        = clip(raw_size * available_cash, guardrails)  # unchanged safety rails
    action      = BUY if p_profit > model's own calibrated threshold else HOLD/SELL
```

Note the "threshold" on the last line is not eliminated — it moves from a
human-picked constant to a value the model calibrates against its own
predicted-probability distribution (e.g. top-decile signals only), which is
the actual distinction between "fixed rule" and "learned policy": the
*decision procedure* is fixed (score, then act), but every *number* inside it
is fit, not chosen.

## 6. What Phase 2 should NOT attempt yet

- Full RL (PPO/DQN) for order execution — real SOTA territory, but needs a
  simulator/backtest environment this repo doesn't have yet, and the PAPER
  execution model here doesn't have per-fill microstructure detail RL would
  need to learn anything beyond what vol-targeting already gives cheaply.
  Flag as a possible Phase 6+ idea, not a Phase 2 dependency.
- HMM/changepoint regime models (see §3).
- Multi-model ensembling beyond retrain-averaging (see §4).

Keeping Phase 2 to vol-target/fractional-Kelly sizing + simple regime grid +
single retrained scorer gives V3 a real "no fixed thresholds" policy that is
buildable in a bounded amount of code, reuses existing data sources, and has
a plausible chance of producing a meaningful V1/V2/V3 comparison within the
Phase-5 soak window instead of stalling on infrastructure that doesn't exist
yet.
