"""Honest backtest of both BVB signals, same 5 gates tae2/the stocks lab
use (tae2.gates, unmodified), PLUS a current signal snapshot for Dacian to
act on by hand at bt-trade.ro. See bvb/__init__.py for what's reused vs
deliberately different here, and bvb/data.py for the data-quality fixes
this backtest depends on.

Parameters are NOT re-optimized for BVB -- same discipline tae2_ucits
followed: core_gtaa_50's own sma_months=6 for the trend sleeve, unchanged;
momentum_vt10's own lookback_months=9, with top_n scaled down from 75 to 3
ONLY because BVB's full universe (21 names) is ~23x smaller than the S&P
500 (so 75 would mean "hold almost everything, always" -- not a selection).
No vol-target overlay here (simpler, more transparent for a first pass);
that is a real, documented simplification, not an oversight.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from tae2 import backtest, gates, stats
from tae2.config import COST_BPS, Gates
from tae2.strategies import fixed_mix

from stocks.strategies import momentum, vol_target

from bvb import data as bvb_data
from bvb import strategies

TREND_SMA_MONTHS = 6
MOMENTUM_LOOKBACK_MONTHS = 9
MOMENTUM_TOP_N = 3
# momentum_vt10's own live risk control (stocks/engine.py), unchanged: raw
# momentum's drawdown is worse than the benchmark's on BVB too (-46.9% vs
# -43.9%, first pass below) -- the same "momentum crash" stocks/research.py
# already documented and already fixed this exact way, not a new workaround.
MOMENTUM_VOL_TARGET = 0.10
MOMENTUM_VOL_WINDOW_MONTHS = 3
TRADING_DAYS_PER_MONTH = 21


def _split_date(index: pd.DatetimeIndex) -> str:
    return str(index[len(index) // 2].date())


def trend_backtest(prices: pd.DataFrame, cost_bps: float = COST_BPS) -> dict:
    universe = bvb_data.LONG_HISTORY
    weights = strategies.trend_filter(prices, universe, bvb_data.CASH, sma_months=TREND_SMA_MONTHS)
    eval_start = weights.index[0]
    p = prices.loc[eval_start:]
    bench_weights = fixed_mix(p, {t: 1 / len(universe) for t in universe})

    cand_res = backtest.run("BVB trend sleeve", p, weights, cost_bps=cost_bps, start=None)
    bench_res = backtest.run("Equal-weight BVB (long-history)", p, bench_weights, cost_bps=cost_bps, start=None)
    split = _split_date(cand_res.returns.index)

    cand_stats = stats.summary(cand_res.returns, cand_res.turnover, split=split)
    bench_stats = stats.summary(bench_res.returns, bench_res.turnover, split=split)
    dsr = stats.deflated_sharpe(cand_res.returns, 1, [stats.sharpe(cand_res.returns)])
    gates_cfg = Gates(benchmark="Equal-weight BVB (long-history)")
    checks = gates.evaluate(cand_stats, bench_stats, dsr, cost_bps, gates=gates_cfg)
    return {
        "universe": universe,
        "data_start": str(p.index[0].date()),
        "data_end": str(p.index[-1].date()),
        "split": split,
        "candidate": cand_stats,
        "benchmark": bench_stats,
        "deflated_sharpe": dsr,
        "checks": checks,
        "passed": gates.passed(checks),
    }


def _momentum_weights(prices: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    base = momentum(
        prices, assets=universe, cash=bvb_data.CASH, lookback_months=MOMENTUM_LOOKBACK_MONTHS, top_n=MOMENTUM_TOP_N
    )
    return vol_target(
        prices, base, cash=bvb_data.CASH,
        target=MOMENTUM_VOL_TARGET, window=MOMENTUM_VOL_WINDOW_MONTHS * TRADING_DAYS_PER_MONTH,
    )


def momentum_backtest(prices: pd.DataFrame, cost_bps: float = COST_BPS) -> dict:
    universe = bvb_data.UNIVERSE
    weights = _momentum_weights(prices, universe)
    eval_start = weights.index[0]
    p = prices.loc[eval_start:]
    bench_weights = fixed_mix(p, {t: 1 / len(universe) for t in universe})

    cand_res = backtest.run("BVB momentum", p, weights, cost_bps=cost_bps, start=None)
    bench_res = backtest.run("Equal-weight BVB (full universe)", p, bench_weights, cost_bps=cost_bps, start=None)
    split = _split_date(cand_res.returns.index)

    cand_stats = stats.summary(cand_res.returns, cand_res.turnover, split=split)
    bench_stats = stats.summary(bench_res.returns, bench_res.turnover, split=split)
    dsr = stats.deflated_sharpe(cand_res.returns, 1, [stats.sharpe(cand_res.returns)])
    gates_cfg = Gates(benchmark="Equal-weight BVB (full universe)")
    checks = gates.evaluate(cand_stats, bench_stats, dsr, cost_bps, gates=gates_cfg)
    return {
        "universe": universe,
        "data_start": str(p.index[0].date()),
        "data_end": str(p.index[-1].date()),
        "split": split,
        "candidate": cand_stats,
        "benchmark": bench_stats,
        "deflated_sharpe": dsr,
        "checks": checks,
        "passed": gates.passed(checks),
    }


def signal_today(prices: pd.DataFrame) -> dict:
    """Current state of both signals, using ALL data through the latest
    available close -- this is what to act on, not a backtest."""
    trend_w = strategies.trend_filter(prices, bvb_data.LONG_HISTORY, bvb_data.CASH, sma_months=TREND_SMA_MONTHS)
    last_trend_date = trend_w.index[-1]
    trend_row = trend_w.loc[last_trend_date]
    trend_state = {t: ("ON" if trend_row[t] > 1e-9 else "off") for t in bvb_data.LONG_HISTORY}

    mom_w = _momentum_weights(prices, bvb_data.UNIVERSE)
    last_mom_date = mom_w.index[-1]
    mom_row = mom_w.loc[last_mom_date]
    held = sorted(
        [t for t in mom_row[mom_row > 1e-9].index if t != bvb_data.CASH], key=lambda t: -mom_row[t]
    )

    return {
        "trend_as_of": str(last_trend_date.date()),
        "trend_state": trend_state,
        "momentum_as_of": str(last_mom_date.date()),
        "momentum_held": [(t, float(mom_row[t])) for t in held],
        "momentum_cash_pct": float(mom_row.get(bvb_data.CASH, 0.0)),
    }


def _gate_block(result: dict) -> list[str]:
    lines = [f"- {'✓' if c.passed else '✗'} {c.gate}: {c.detail}" for c in result["checks"]]
    lines.append(f"**Verdict: {'PASS' if result['passed'] else 'FAIL'}**")
    return lines


def to_markdown(trend: dict, momentum_r: dict, signal: dict) -> str:
    lines = [f"# BVB research + signal, {date.today().isoformat()}", ""]

    lines += ["## 1. Trend sleeve (core_gtaa_50's own sma_months=6, unchanged)", "",
              f"Universe: {', '.join(trend['universe'])} ({len(trend['universe'])} names, each >=15y real history).",
              f"Data: {trend['data_start']} -> {trend['data_end']}, split {trend['split']}.", "",
              "| Metric | Equal-weight benchmark | Trend sleeve |", "|---|---:|---:|"]
    b, c = trend["benchmark"], trend["candidate"]
    lines += [
        f"| CAGR | {b['cagr']:.1%} | {c['cagr']:.1%} |",
        f"| Vol | {b['vol']:.1%} | {c['vol']:.1%} |",
        f"| Sharpe | {b['sharpe']:.2f} | {c['sharpe']:.2f} |",
        f"| Max drawdown | {b['max_dd']:.1%} | {c['max_dd']:.1%} |",
        f"| Sharpe J1/J2 | {b['sharpe_first_half']:.2f} / {b['sharpe_second_half']:.2f} | "
        f"{c['sharpe_first_half']:.2f} / {c['sharpe_second_half']:.2f} |",
        f"| Deflated Sharpe | — | {trend['deflated_sharpe']:.2f} |",
        "",
    ]
    lines += _gate_block(trend) + [""]

    lines += ["## 2. Momentum ranking (momentum_vt10's own 9-month lookback + 10%/3mo vol-target, top_n scaled to 3)", "",
              f"Universe: {', '.join(momentum_r['universe'])} ({len(momentum_r['universe'])} names).",
              f"Data: {momentum_r['data_start']} -> {momentum_r['data_end']}, split {momentum_r['split']}.", "",
              "| Metric | Equal-weight benchmark | Momentum |", "|---|---:|---:|"]
    b, c = momentum_r["benchmark"], momentum_r["candidate"]
    lines += [
        f"| CAGR | {b['cagr']:.1%} | {c['cagr']:.1%} |",
        f"| Vol | {b['vol']:.1%} | {c['vol']:.1%} |",
        f"| Sharpe | {b['sharpe']:.2f} | {c['sharpe']:.2f} |",
        f"| Max drawdown | {b['max_dd']:.1%} | {c['max_dd']:.1%} |",
        f"| Sharpe J1/J2 | {b['sharpe_first_half']:.2f} / {b['sharpe_second_half']:.2f} | "
        f"{c['sharpe_first_half']:.2f} / {c['sharpe_second_half']:.2f} |",
        f"| Deflated Sharpe | — | {momentum_r['deflated_sharpe']:.2f} |",
        "",
    ]
    lines += _gate_block(momentum_r) + [""]

    lines += ["## 3. Signal snapshot (act-by-hand on bt-trade.ro)", "",
              f"Trend, as of {signal['trend_as_of']}:"]
    lines += [f"- {t}: {state}" for t, state in signal["trend_state"].items()]
    held_txt = ", ".join(f"{t} ({w:.1%})" for t, w in signal["momentum_held"])
    lines += ["", f"Momentum, as of {signal['momentum_as_of']}:",
              f"- Held: {held_txt if held_txt else '(none)'}  ·  Cash: {signal['momentum_cash_pct']:.1%}"]
    return "\n".join(lines) + "\n"


def write_report(text: str, name: str = "report", out_dir: Path = Path("output")) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"bvb_{name}_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    prices = bvb_data.load(refresh=False)
    trend = trend_backtest(prices)
    mom = momentum_backtest(prices)
    sig = signal_today(prices)
    text = to_markdown(trend, mom, sig)
    print(text)
    path = write_report(text)
    print(f"Report written to {path}")
