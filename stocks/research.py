"""Walk-forward research run for the stock lab -- same algorithm as
tae2/research.py (best in-sample variant per family, judged out-of-sample,
deflated Sharpe over every variant tried, same five gates), applied to a
stock universe instead of ETFs. This file owns its own run()/to_markdown()
so it never has to modify tae2's -- the two labs stay fully independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from tae2 import backtest, gates, stats
from tae2.research import Family, Row  # generic dataclasses, no ETF-specific fields
from tae2.strategies import blend, fixed_mix

from stocks import config, strategies


@dataclass
class StockPlan:
    """Parameter grids for the walk-forward search (every variant counts as a trial)."""

    momentum_months: tuple[int, ...] = (3, 6, 9, 12)
    momentum_top_n: tuple[int, ...] = (25, 50, 75)  # ~top 5% / 10% / 15% of a ~500-name universe
    vol_window_months: tuple[int, ...] = (3, 6, 12)
    vol_top_n: tuple[int, ...] = (50, 100, 150)
    blend_core_weight: tuple[float, ...] = (0.5,)
    # Momentum's raw drawdown (-65% vs the benchmark's -43%, 2026-09-24 run)
    # is exactly the "momentum crash" the literature warns about (150+ years
    # of evidence say the premium is real; the crash risk is just as real,
    # and volatility scaling is the literature's standard fix, not a fudge).
    # tae2.strategies.vol_target already does this generically -- scale
    # exposure down (into cash) when trailing realized vol exceeds a target,
    # never lever up. Same target/window grid tae2's own GTAA research used.
    vol_target_pct: tuple[float, ...] = (0.10, 0.15, 0.20)
    vol_target_window_months: tuple[int, ...] = (3,)  # 63 trading days, tae2's own default


PLAN = StockPlan()
TRADING_DAYS_PER_MONTH = 21


def families(tickers: list[str], plan: StockPlan = PLAN) -> list[Family]:
    equal_weight = {t: 1.0 / len(tickers) for t in tickers}
    # Fixed, literature-typical single point for the blend (not re-optimized
    # in-sample) -- picking momentum/vol params AND blend weight all by the
    # same in-sample Sharpe would just rediscover calendar-phase-style luck,
    # the exact trap tae2's rebalance-frequency research already documented.
    momentum_fixed: Callable[[pd.DataFrame], pd.DataFrame] = lambda p: strategies.momentum(
        p, assets=tickers, cash=config.CASH, lookback_months=12, top_n=50
    )
    lowvol_fixed: Callable[[pd.DataFrame], pd.DataFrame] = lambda p: strategies.low_volatility(
        p, assets=tickers, top_n=100, window=6 * TRADING_DAYS_PER_MONTH
    )
    return [
        Family("Equal-weight universe", lambda p: fixed_mix(p, equal_weight), benchmark=True),
        Family("SPY", lambda p: fixed_mix(p, {"SPY": 1.0}), benchmark=True),
        Family(
            "Momentum (top-N, 12-1 style)",
            lambda p, lookback_months, top_n: strategies.momentum(
                p, assets=tickers, cash=config.CASH, lookback_months=lookback_months, top_n=top_n
            ),
            {"lookback_months": plan.momentum_months, "top_n": plan.momentum_top_n},
        ),
        Family(
            "Low volatility (top-N)",
            lambda p, window_months, top_n: strategies.low_volatility(
                p, assets=tickers, top_n=top_n, window=window_months * TRADING_DAYS_PER_MONTH
            ),
            {"window_months": plan.vol_window_months, "top_n": plan.vol_top_n},
        ),
        Family(
            "Momentum + low-vol blend",
            lambda p, core_weight: blend([(momentum_fixed(p), core_weight), (lowvol_fixed(p), 1 - core_weight)]),
            {"core_weight": plan.blend_core_weight},
        ),
        Family(
            "Momentum + vol target",
            lambda p, lookback_months, top_n, target, window_months: strategies.vol_target(
                p,
                strategies.momentum(p, assets=tickers, cash=config.CASH, lookback_months=lookback_months, top_n=top_n),
                cash=config.CASH,
                target=target,
                window=window_months * TRADING_DAYS_PER_MONTH,
            ),
            {
                "lookback_months": plan.momentum_months,
                "top_n": plan.momentum_top_n,
                "target": plan.vol_target_pct,
                "window_months": plan.vol_target_window_months,
            },
        ),
        Family(
            "Momentum + low-vol blend + vol target",
            lambda p, core_weight, target: strategies.vol_target(
                p,
                blend([(momentum_fixed(p), core_weight), (lowvol_fixed(p), 1 - core_weight)]),
                cash=config.CASH,
                target=target,
                window=plan.vol_target_window_months[0] * TRADING_DAYS_PER_MONTH,
            ),
            {"core_weight": plan.blend_core_weight, "target": plan.vol_target_pct},
        ),
    ]


def run(
    prices: pd.DataFrame, tickers: list[str], cost_bps: float = config.COST_BPS, plan: StockPlan = PLAN
) -> tuple[list[Row], int]:
    """Best in-sample variant of each family, its out-of-sample stats and gate checks."""
    split = config.SPLIT_DATE
    chosen: list[tuple[Family, dict, backtest.Result]] = []
    all_sharpes: list[float] = []
    for fam in families(tickers, plan):
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
        checks = [] if fam.benchmark else gates.evaluate(full, bench_stats, dsr, cost_bps, gates=config.GATES)
        rows.append(Row(fam.name, params, full, oos, dsr, checks, fam.benchmark))
    return rows, n_trials


def to_markdown(rows: list[Row], n_trials: int, issues: list, prices: pd.DataFrame, n_tickers: int) -> str:
    first, last = prices.loc[config.EVAL_START:].index[[0, -1]]
    lines = [
        f"# Stock lab research run, {date.today().isoformat()}",
        "",
        "**Survivorship bias warning:** this universe is today's S&P 500 members "
        "applied to the whole history below, not point-in-time membership. Every "
        "number here is inflated by an unknown amount until a point-in-time "
        "constituents dataset replaces it. First-pass architecture check only.",
        "",
        f"Evaluated {first.date()} to {last.date()}, {n_tickers} tickers, {config.COST_BPS:g} bps per dollar "
        f"traded, trades one day after each decision. Parameters picked on {config.EVAL_START[:4]}"
        f"–{int(config.SPLIT_DATE[:4]) - 1} only; \"after {config.SPLIT_DATE[:4]}\" columns are years the choice "
        f"never saw. {n_trials} variants tried in total. Benchmark: {config.GATES.benchmark} (the rigorous bar -- "
        "did stock-picking beat just holding the universe, not only SPY).",
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
    path = out_dir / f"stock_research_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path
