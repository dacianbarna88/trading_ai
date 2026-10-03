"""Isolate which UCITS approximation drives core_gtaa_50's first-half
underperformance on UCITS data (found 2026-10-03, persisted after fixing
the IBTS.L/IUSP.L data-quality problem -- see research.py's history).

Builds a small set of variants, changing exactly one approximation at a
time against the same baseline, and compares each to the SAME 60/40 (UCITS)
benchmark on the SAME split, so differences are attributable to that one
change -- not a second grid search, not re-optimizing anything.
"""

from __future__ import annotations

import pandas as pd

from tae2 import backtest, stats
from tae2.config import COST_BPS
from tae2.strategies import core_plus_sleeve, fixed_mix, gtaa

from tae2_ucits import data as ucits_data
from tae2_ucits.research import EVAL_START, SPLIT_DATE


def _half_sharpes(returns: pd.Series, split: str = SPLIT_DATE) -> tuple[float, float]:
    split_ts = pd.Timestamp(split)
    return stats.sharpe(returns[returns.index < split_ts]), stats.sharpe(returns[returns.index >= split_ts])


def run() -> list[dict]:
    raw = ucits_data.fetch(ucits_data.ALL_TICKERS)
    baseline_prices = ucits_data.build_strict(raw).loc[EVAL_START:]

    europe_only_prices = baseline_prices.copy()
    europe_only_prices["EFA"] = raw[ucits_data.EUROPE_TICKER].loc[baseline_prices.index]
    europe_only_prices = europe_only_prices.dropna()

    bench_res = backtest.run("60/40", baseline_prices, fixed_mix(baseline_prices, {"SPY": 0.6, "IEF": 0.4}), cost_bps=COST_BPS)
    bench_h1, bench_h2 = _half_sharpes(bench_res.returns)

    variants: dict[str, pd.DataFrame] = {
        "Bază (EFA=Eur+Jap+Pac, DBC lipit)": core_plus_sleeve(
            baseline_prices, gtaa(baseline_prices, sma_months=6), core_weight=0.5
        ),
        "EFA = doar Europa (fără Japonia/Pacific)": core_plus_sleeve(
            europe_only_prices, gtaa(europe_only_prices, sma_months=6), core_weight=0.5
        ),
        "Fără mărfuri (GTAA pe SPY/EFA/IEF/VNQ)": core_plus_sleeve(
            baseline_prices,
            gtaa(baseline_prices, sma_months=6, assets=("SPY", "EFA", "IEF", "VNQ")),
            core_weight=0.5,
        ),
    }

    rows = []
    for name, weights in variants.items():
        prices_for_run = europe_only_prices if "Europa" in name else baseline_prices
        res = backtest.run(name, prices_for_run, weights, cost_bps=COST_BPS)
        h1, h2 = _half_sharpes(res.returns)
        full_stats = stats.summary(res.returns, res.turnover, split=SPLIT_DATE)
        rows.append(
            {
                "variant": name,
                "sharpe_h1": h1,
                "sharpe_h2": h2,
                "beats_bench_h1": h1 > bench_h1,
                "beats_bench_h2": h2 > bench_h2,
                "max_dd": full_stats["max_dd"],
                "cagr": full_stats["cagr"],
            }
        )
    rows.insert(0, {"variant": "60/40 (benchmark)", "sharpe_h1": bench_h1, "sharpe_h2": bench_h2,
                     "beats_bench_h1": None, "beats_bench_h2": None,
                     "max_dd": stats.summary(bench_res.returns, bench_res.turnover, split=SPLIT_DATE)["max_dd"],
                     "cagr": stats.summary(bench_res.returns, bench_res.turnover, split=SPLIT_DATE)["cagr"]})
    return rows


def to_markdown(rows: list[dict]) -> str:
    lines = [
        "| Variantă | Sharpe prima jumătate | Sharpe a doua jumătate | Bate benchmark J1 | Bate benchmark J2 | CAGR | Cădere max |",
        "|---|---:|---:|:---:|:---:|---:|---:|",
    ]
    for r in rows:
        b1 = "—" if r["beats_bench_h1"] is None else ("✓" if r["beats_bench_h1"] else "✗")
        b2 = "—" if r["beats_bench_h2"] is None else ("✓" if r["beats_bench_h2"] else "✗")
        lines.append(
            f"| {r['variant']} | {r['sharpe_h1']:.2f} | {r['sharpe_h2']:.2f} | {b1} | {b2} | "
            f"{r['cagr']:.1%} | {r['max_dd']:.1%} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    rows = run()
    print(to_markdown(rows))
