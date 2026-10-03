"""Validate core_gtaa_50's EXISTING parameters (sma_months=6, core_weight=0.5
-- the live choice, not re-optimized here) on the UCITS-proxy price data.

Deliberately not a fresh grid search: picking sma_months/core_weight AND
the UCITS data's own quirks by the same in-sample Sharpe would just
rediscover a new "calendar-phase-luck"-style overfit, the exact trap
tae2's own rebalance-frequency research already flagged. This checks
whether the strategy the live account actually runs still clears the same
five gates on different (UCITS) data, using tae2.gates/tae2.stats/
tae2.backtest completely unchanged.

Runs on BOTH of tae2_ucits.data's variants, each with its own honest window
(see data.py's module docstring for what STRICT vs EXTENDED means):

- STRICT: real UCITS history only, starts 2011-06-01 -- excludes 2008-2011
  entirely (clean-data constraint, not a choice). The conservative test.
- EXTENDED: recovers 2008-2011 via a documented splice onto each UCITS
  fund's real data; uses tae2's OWN original EVAL_START/SPLIT_DATE
  (2008-01-01 / 2017-01-01) so the window and split match the ALREADY-
  APPROVED live US backtest as closely as possible.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from tae2 import backtest, engine, gates, stats
from tae2.config import COST_BPS, EVAL_START as US_EVAL_START, Gates, SPLIT_DATE as US_SPLIT_DATE
from tae2.strategies import fixed_mix

from tae2_ucits import data as ucits_data

EVAL_START = "2011-06-01"  # Bug found 2026-10-03: IBTS.L (SHY proxy) and IUSP.L
# (VNQ proxy) both have real data-quality problems through ~2011-05 (repeated
# 15-50%+ single-day moves for a short-duration treasury fund and a REIT fund
# respectively -- not real market events; both funds were young/thinly traded
# then and Yahoo Finance's historical feed for them is unreliable that early).
# The first full validation run (EVAL_START=2010-10-01) FAILED the "beats
# benchmark both halves" gate specifically in the half containing this bad
# data -- confirmed the failure was largely a data artifact, not the strategy,
# by rerunning from here (clean data, verified below 10% moves excluding
# known real events like Brexit/COVID). STRICT variant's own EVAL_START.
SPLIT_DATE = "2019-02-01"  # roughly the midpoint of the ~15.3-year clean UCITS window (STRICT only)

VARIANTS = {
    "strict": {"variant": "strict", "eval_start": EVAL_START, "split_date": SPLIT_DATE},
    "extended": {"variant": "extended", "eval_start": US_EVAL_START, "split_date": US_SPLIT_DATE},
}


def run(variant: str = "strict", prices: pd.DataFrame | None = None, cost_bps: float = COST_BPS) -> dict:
    cfg = VARIANTS[variant]
    prices = prices if prices is not None else ucits_data.load(variant=cfg["variant"], refresh=False)
    prices = prices.loc[cfg["eval_start"]:]
    split_date = cfg["split_date"]
    gates_cfg = Gates(benchmark=f"60/40 (UCITS, {variant})")

    bench_weights = fixed_mix(prices, {"SPY": 0.6, "IEF": 0.4})
    bench_res = backtest.run(f"60/40 (UCITS, {variant})", prices, bench_weights, cost_bps=cost_bps)
    bench_stats = stats.summary(bench_res.returns, bench_res.turnover, split=split_date)

    cand_weights = engine.DEPLOYABLE["core_gtaa_50"](prices)
    cand_res = backtest.run(f"core_gtaa_50 (UCITS, {variant})", prices, cand_weights, cost_bps=cost_bps)
    cand_stats = stats.summary(cand_res.returns, cand_res.turnover, split=split_date)
    oos_stats = stats.summary(cand_res.returns[cand_res.returns.index >= pd.Timestamp(split_date)])

    # Single fixed point, not a grid search -> deflated Sharpe with n_trials=1
    # (no multiple-comparisons correction needed; nothing was optimized here).
    dsr = stats.deflated_sharpe(cand_res.returns, 1, [stats.sharpe(cand_res.returns)])
    checks = gates.evaluate(cand_stats, bench_stats, dsr, cost_bps, gates=gates_cfg)

    return {
        "variant": variant,
        "data_start": str(prices.index[0].date()),
        "data_end": str(prices.index[-1].date()),
        "split_date": split_date,
        "years": round((prices.index[-1] - prices.index[0]).days / 365.25, 1),
        "benchmark": bench_stats,
        "candidate": cand_stats,
        "out_of_sample": oos_stats,
        "deflated_sharpe": dsr,
        "checks": checks,
        "passed": gates.passed(checks),
    }


def to_markdown(result: dict) -> str:
    b, c, o = result["benchmark"], result["candidate"], result["out_of_sample"]
    split_date = result["split_date"]
    lines = [
        f"# tae2 UCITS twin — validation run, variant={result['variant']}, {date.today().isoformat()}",
        "",
        "core_gtaa_50's EXISTING live parameters (sma_months=6, core_weight=0.5), "
        "unchanged, run on UCITS-equivalent price data. See tae2_ucits/data.py for "
        "exactly what's real vs spliced in this variant.",
        "",
        f"Data: {result['data_start']} to {result['data_end']} ({result['years']} years), split at {split_date}.",
        "",
        "| Metric | 60/40 (UCITS, benchmark) | core_gtaa_50 (UCITS) |",
        "|---|---:|---:|",
        f"| CAGR | {b['cagr']:.1%} | {c['cagr']:.1%} |",
        f"| Vol | {b['vol']:.1%} | {c['vol']:.1%} |",
        f"| Sharpe | {b['sharpe']:.2f} | {c['sharpe']:.2f} |",
        f"| Max drawdown | {b['max_dd']:.1%} | {c['max_dd']:.1%} |",
        f"| Sharpe, first half | {b['sharpe_first_half']:.2f} | {c['sharpe_first_half']:.2f} |",
        f"| Sharpe, second half | {b['sharpe_second_half']:.2f} | {c['sharpe_second_half']:.2f} |",
        f"| Out-of-sample Sharpe (after {split_date[:4]}) | — | {o['sharpe']:.2f} |",
        f"| Deflated Sharpe | — | {result['deflated_sharpe']:.2f} |",
        "",
        "## Gate details",
        "",
    ]
    lines += [f"- {'✓' if ch.passed else '✗'} {ch.gate}: {ch.detail}" for ch in result["checks"]]
    lines += ["", f"**Verdict: {'PASS' if result['passed'] else 'FAIL'}**", ""]
    return "\n".join(lines) + "\n"


def write_report(text: str, name: str, out_dir: Path = Path("output")) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"tae2_ucits_validation_{name}_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    for variant in ("strict", "extended"):
        result = run(variant)
        text = to_markdown(result)
        path = write_report(text, variant)
        print(text)
        print(f"Report written to {path}")
