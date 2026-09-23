"""Walk-forward research run: every candidate, every variant, the same gates.

For each strategy family, parameters are chosen on the in-sample years only
(EVAL_START to SPLIT_DATE) and then judged on the years after, which the
choice never saw. Every variant tried counts toward the deflated Sharpe.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from tae2 import backtest, config, gates, stats, strategies

Builder = Callable[..., pd.DataFrame]


@dataclass
class Family:
    name: str
    build: Builder
    grid: dict[str, tuple] = field(default_factory=dict)
    benchmark: bool = False

    def variants(self) -> list[dict]:
        if not self.grid:
            return [{}]
        keys = list(self.grid)
        return [dict(zip(keys, combo)) for combo in itertools.product(*(self.grid[k] for k in keys))]


def _with_vol_target(builder: Builder) -> Builder:
    def build(prices: pd.DataFrame, target: float, **params) -> pd.DataFrame:
        return strategies.vol_target(prices, builder(prices, **params), target=target)

    return build


def families(plan: config.ResearchPlan = config.PLAN) -> list[Family]:
    return [
        Family("SPY", lambda p: strategies.fixed_mix(p, {"SPY": 1.0}), benchmark=True),
        Family("60/40", lambda p: strategies.fixed_mix(p, {"SPY": 0.6, "IEF": 0.4}), benchmark=True),
        Family("GTAA trend", strategies.gtaa, {"sma_months": plan.sma_months}),
        Family(
            "GTAA trend + vol target",
            _with_vol_target(strategies.gtaa),
            {"sma_months": plan.sma_months, "target": plan.vol_target},
        ),
        Family("Dual momentum", strategies.dual_momentum, {"lookback_months": plan.momentum_months}),
        Family(
            "Relative momentum",
            strategies.relative_momentum,
            {"lookback_months": plan.momentum_months, "top_n": plan.top_n},
        ),
        Family(
            "Relative momentum + vol target",
            _with_vol_target(strategies.relative_momentum),
            {"lookback_months": plan.momentum_months, "top_n": plan.top_n, "target": plan.vol_target},
        ),
        Family("Inverse volatility", strategies.inverse_volatility),
        Family("Inverse volatility + vol target", _with_vol_target(strategies.inverse_volatility), {"target": plan.vol_target}),
        # Phase 2: keep a 60/40 core and add a trend-following layer.
        Family("60/40 with trend filter", strategies.trend_filtered_mix, {"sma_months": plan.sma_months}),
        Family(
            "60/40 core + GTAA sleeve",
            lambda p, sma_months, core_weight: strategies.core_plus_sleeve(
                p, strategies.gtaa(p, sma_months=sma_months), core_weight
            ),
            {"sma_months": plan.sma_months, "core_weight": plan.core_weight},
        ),
        Family(
            "60/40 core + dual momentum sleeve",
            lambda p, lookback_months, core_weight: strategies.core_plus_sleeve(
                p, strategies.dual_momentum(p, lookback_months=lookback_months), core_weight
            ),
            {"lookback_months": plan.momentum_months, "core_weight": plan.core_weight},
        ),
    ]


@dataclass
class Row:
    family: str
    params: dict
    full: dict
    out_of_sample: dict
    deflated_sharpe: float = 0.0
    checks: list[gates.Check] = field(default_factory=list)
    benchmark: bool = False


def run(prices: pd.DataFrame, cost_bps: float = config.COST_BPS) -> tuple[list[Row], int]:
    """Best in-sample variant of each family, its out-of-sample stats and gate checks."""
    split = config.SPLIT_DATE
    chosen: list[tuple[Family, dict, backtest.Result]] = []
    all_sharpes: list[float] = []
    for fam in families():
        best = None
        for params in fam.variants():
            res = backtest.run(fam.name, prices, fam.build(prices, **params), cost_bps=cost_bps)
            all_sharpes.append(stats.sharpe(res.returns))
            in_sample = stats.sharpe(res.returns[res.returns.index < pd.Timestamp(split)])
            if best is None or in_sample > best[0]:
                best = (in_sample, params, res)
        chosen.append((fam, best[1], best[2]))

    n_trials = len(all_sharpes)
    bench = next(res for fam, _, res in chosen if fam.name == config.GATES.benchmark)
    bench_stats = stats.summary(bench.returns, bench.turnover, split=split)
    rows = []
    for fam, params, res in chosen:
        full = stats.summary(res.returns, res.turnover, split=split)
        oos = stats.summary(res.returns[res.returns.index >= pd.Timestamp(split)])
        dsr = stats.deflated_sharpe(res.returns, n_trials, all_sharpes)
        checks = [] if fam.benchmark else gates.evaluate(full, bench_stats, dsr, cost_bps)
        rows.append(Row(fam.name, params, full, oos, dsr, checks, fam.benchmark))
    return rows, n_trials


def to_markdown(rows: list[Row], n_trials: int, issues: list, prices: pd.DataFrame) -> str:
    first, last = prices.loc[config.EVAL_START:].index[[0, -1]]
    lines = [
        f"# TAE 2.0 research run, {date.today().isoformat()}",
        "",
        f"Evaluated {first.date()} to {last.date()}, {config.COST_BPS:g} bps per dollar traded, "
        f"trades one day after each decision. Parameters picked on {config.EVAL_START[:4]}–{int(config.SPLIT_DATE[:4]) - 1} only; "
        f"\"after {config.SPLIT_DATE[:4]}\" columns are years the choice never saw. {n_trials} variants tried in total.",
        "",
        "| Strategy | Chosen parameters | CAGR | Vol | Sharpe | Max DD | Sharpe after split | CAGR after split | Turnover/yr | Deflated Sharpe | Gates |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        f, o = r.full, r.out_of_sample
        params = ", ".join(f"{k}={v}" for k, v in r.params.items()) or "—"
        verdict = "benchmark" if r.benchmark else ("PASS" if gates.passed(r.checks) else "fail")
        lines.append(
            f"| {r.family} | {params} | {f['cagr']:.1%} | {f['vol']:.1%} | {f['sharpe']:.2f} | {f['max_dd']:.1%} | "
            f"{o['sharpe']:.2f} | {o['cagr']:.1%} | {f['turnover_per_year']:.1f} | {r.deflated_sharpe:.2f} | {verdict} |"
        )
    lines += ["", "## Gate details", ""]
    for r in rows:
        if r.benchmark:
            continue
        lines.append(f"**{r.family}**")
        lines += [f"- {'✓' if c.passed else '✗'} {c.gate}: {c.detail}" for c in r.checks]
        lines.append("")
    lines += ["## Data checks", ""]
    lines += [f"- {i.ticker} {i.kind}: {i.detail}" for i in issues] or ["- no issues"]
    return "\n".join(lines) + "\n"


def write_report(text: str, out_dir: Path = Path("output")) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"research_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path
