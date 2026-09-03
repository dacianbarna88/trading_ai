"""V2 empirical-Kelly position sizing.

V2's entries used a flat, unconditional company-budget/tranche formula
(50% of investable cash, then a fixed 0.20 tranche_fraction — see
tae_strategy_v2_buy_policy.resolve_company_budget/proposed_tranche_value_usd)
with no weighting by V2's own measured edge. Audited real trade history
(41 days, 27 closed trades at audit time): 81.5% win rate, avg win $28.03,
avg loss $11.76 (payoff_ratio ~2.38), profit factor 10.49 — spread across
50 concurrent ~$520 positions, diluting a proven edge to near-index returns.

This computes a Kelly-scaled tranche_fraction from V2's own rolling closed-
trade history so sizing tracks V2's actual, provable edge instead of a
hand-picked constant — reusing tae_strategy_v3_learning_policy.kelly_fraction()
(a pure function with no V3-specific state) rather than reimplementing the
formula. V2's entry-signal logic is untouched; only how much capital goes
into each opened tranche changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tae_strategy_v3_learning_policy import kelly_fraction

DEFAULT_P_PROFIT = 0.55
DEFAULT_PAYOFF_RATIO = 1.5
MIN_SAMPLES = 15
SHRINKAGE_K = 20
LOOKBACK_TRADES = 200


def _load_closed_trades(trades_path: Path | str) -> list[dict[str, Any]]:
    path = Path(trades_path)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("action") == "CLOSE" and "realized_pnl" in d:
                out.append(d)
    return out


def compute_v2_empirical_edge(
    trades_path: Path | str,
    *,
    min_samples: int = MIN_SAMPLES,
    lookback: int = LOOKBACK_TRADES,
) -> tuple[float, float, dict[str, Any]]:
    """Returns (p_profit, payoff_ratio, diagnostics) from V2's own closed trades.

    Shrinks toward a conservative prior (DEFAULT_P_PROFIT/DEFAULT_PAYOFF_RATIO)
    using n/(n+SHRINKAGE_K) weighting — the same shrinkage spirit as V3's
    LearningScorer — so a thin or early sample can't produce an
    overconfident sizing multiplier.
    """
    closed = _load_closed_trades(trades_path)[-lookback:]
    pnls = [float(t.get("realized_pnl", 0.0)) for t in closed]
    n = len(pnls)

    if n == 0:
        return (
            DEFAULT_P_PROFIT,
            DEFAULT_PAYOFF_RATIO,
            {"n_samples": 0, "source": "PRIOR_ONLY_NO_DATA"},
        )

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    raw_p_profit = len(wins) / n
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(losses)) / len(losses)) if losses else 0.0
    raw_payoff = (avg_win / avg_loss) if avg_loss > 0 else DEFAULT_PAYOFF_RATIO

    weight = n / (n + SHRINKAGE_K)
    p_profit = weight * raw_p_profit + (1 - weight) * DEFAULT_P_PROFIT
    payoff_ratio = weight * raw_payoff + (1 - weight) * DEFAULT_PAYOFF_RATIO

    diagnostics = {
        "n_samples": n,
        "source": "EMPIRICAL" if n >= min_samples else "SHRUNK_TOWARD_PRIOR",
        "raw_p_profit": round(raw_p_profit, 4),
        "raw_payoff_ratio": round(raw_payoff, 4),
        "shrinkage_weight": round(weight, 4),
    }
    return p_profit, payoff_ratio, diagnostics


def v2_tranche_fraction_from_edge(
    trades_path: Path | str,
    *,
    base_fraction: float = 0.20,
    min_fraction: float = 0.05,
    max_fraction: float = 0.50,
) -> tuple[float, dict[str, Any]]:
    """Kelly-scaled tranche_fraction to replace V2's flat 0.20 constant.

    kelly_fraction() returns a fraction of full Kelly (30% of full Kelly by
    default). We rescale it so the conservative-prior edge maps back to
    roughly base_fraction (V2's old constant), and a stronger *measured*
    edge scales sizing up from there — clamped to [min_fraction,
    max_fraction] so a hot/cold streak can't push sizing to an extreme.
    """
    p_profit, payoff_ratio, diag = compute_v2_empirical_edge(trades_path)
    kelly = kelly_fraction(p_profit, payoff_ratio)
    kelly_at_prior = kelly_fraction(DEFAULT_P_PROFIT, DEFAULT_PAYOFF_RATIO)
    scale = (kelly / kelly_at_prior) if kelly_at_prior > 0 else 1.0
    fraction = max(min_fraction, min(max_fraction, base_fraction * scale))

    diag.update(
        {
            "p_profit": round(p_profit, 4),
            "payoff_ratio": round(payoff_ratio, 4),
            "kelly": round(kelly, 4),
            "tranche_fraction": round(fraction, 4),
        }
    )
    return fraction, diag
