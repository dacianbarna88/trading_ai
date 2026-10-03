"""Rolling-window Sharpe-gap analysis, requested 2026-10-03 after the
autopsy found that core_gtaa_50's UCITS-twin first-half gate failure also
appears on pure US data restricted to the same short (2011-2019) window --
the 2008-2011 crisis, where trend-following earns its keep, was excluded by
a data-quality constraint, not by anything UCITS-specific.

Rather than one J1/J2 split, this slides a fixed-length window one year at
a time and reports Sharpe(core_gtaa_50) - Sharpe(60/40) on that window
alone, with no parameter touched (same live sma_months=6/core_weight=0.5).
The question this answers: does core_gtaa_50 systematically lose to 60/40
in long calm bull windows but win big in windows that contain a crisis --
i.e. does it behave like insurance, paying a premium most years and paying
off exactly when markets crash?
"""

from __future__ import annotations

import pandas as pd

from tae2 import backtest, stats
from tae2.config import COST_BPS
from tae2.engine import DEPLOYABLE
from tae2.strategies import fixed_mix


def windows(start_year: int, end_year: int, length_years: int = 7) -> list[tuple[str, str]]:
    """7-year windows starting each year from start_year, as long as the
    window's end doesn't exceed end_year (matches the user's own example:
    2008-2015, 2009-2016, ..., 2019-2026)."""
    return [
        (f"{y}-01-01", f"{y + length_years}-01-01")
        for y in range(start_year, end_year - length_years + 1)
    ]


def sharpe_gap(prices: pd.DataFrame, start: str, end: str, cost_bps: float = COST_BPS) -> dict | None:
    p = prices.loc[start:end]
    if len(p) < 200:  # not enough data in this window for this price series
        return None
    cand_res = backtest.run("core_gtaa_50", p, DEPLOYABLE["core_gtaa_50"](p), cost_bps=cost_bps, start=None)
    bench_res = backtest.run("60/40", p, fixed_mix(p, {"SPY": 0.6, "IEF": 0.4}), cost_bps=cost_bps, start=None)
    cand_sharpe = stats.sharpe(cand_res.returns)
    bench_sharpe = stats.sharpe(bench_res.returns)
    return {
        "window": f"{start[:4]}-{end[:4]}",
        "sharpe_tae2": cand_sharpe,
        "sharpe_6040": bench_sharpe,
        "gap": cand_sharpe - bench_sharpe,
        "max_dd_tae2": stats.max_drawdown(cand_res.returns),
        "max_dd_6040": stats.max_drawdown(bench_res.returns),
    }


def run(prices: pd.DataFrame, start_year: int = 2008, end_year: int = 2026, length_years: int = 7) -> list[dict]:
    rows = [sharpe_gap(prices, s, e, ) for s, e in windows(start_year, end_year, length_years)]
    return [r for r in rows if r is not None]


def to_markdown(rows: list[dict], label: str) -> str:
    lines = [
        f"### {label}",
        "",
        "| Fereastră | Sharpe TAE2 | Sharpe 60/40 | Diferență (TAE2 - 60/40) | Cădere max TAE2 | Cădere max 60/40 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['window']} | {r['sharpe_tae2']:.2f} | {r['sharpe_6040']:.2f} | {r['gap']:+.2f} | "
            f"{r['max_dd_tae2']:.1%} | {r['max_dd_6040']:.1%} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    from tae2 import data as us_data
    from tae2_ucits import data as ucits_data

    us_prices, _ = us_data.load(refresh=False)
    ext_prices = ucits_data.load(variant="extended", refresh=False)

    print(to_markdown(run(us_prices), "US original (istoric complet)"))
    print(to_markdown(run(ext_prices), "UCITS EXTENDED (lipit 2008-2011)"))
