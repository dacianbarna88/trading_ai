"""Mechanics of the 2022 whipsaw flagged in the benchmark-family checkpoint
(tae2_ucits/__init__.py): the GTAA sleeve's SPY leg exited 2022-01-31 but
re-entered 2022-03-31, mid-bear-market, one month too early. This answers
*why*, numerically, using the exact same sma_months=6 signal core_gtaa_50
runs live -- no parameter touched, this only prints the month-end price and
its trailing 6-month average for each GTAA asset around the episode.

core_gtaa_50's signal is pure SMA-crossover: price above its OWN trailing
6-month average -> in, else -> cash. The average is a TRAILING window, so
right after a strong bull run (SPY made new highs Oct-Dec 2021) the average
itself sits close to the still-high recent price level. A single month's
bear-market relief rally is then enough to nudge price back above that
still-elevated average, even though the broader trend has turned down --
this is the generic whipsaw failure mode of any SMA-crossover system on a
choppy, rally-interrupted bear market (2022), as opposed to a persistent,
one-directional crash (2008, COVID) where price stays convincingly below a
falling average for months.
"""

from __future__ import annotations

import pandas as pd

from tae2.strategies import GTAA_ASSETS

from tae2_ucits import data as ucits_data


def monthly_signal(prices: pd.DataFrame, sma_months: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(month-end price, trailing N-month average), for every GTAA asset."""
    month_end = prices.groupby([prices.index.year, prices.index.month]).tail(1)
    m = month_end[list(GTAA_ASSETS)]
    avg = m.rolling(sma_months).mean()
    return m, avg


def table(prices: pd.DataFrame, start: str, end: str, sma_months: int = 6) -> list[dict]:
    m, avg = monthly_signal(prices, sma_months)
    rows = []
    for d in m.loc[start:end].index:
        row = {"date": str(d.date())}
        for a in GTAA_ASSETS:
            p, s = m.loc[d, a], avg.loc[d, a]
            row[a] = {"price": float(p), "sma6": float(s), "pct_above": float(p / s - 1), "on": bool(p > s)}
        rows.append(row)
    return rows


def to_text(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        parts = [f"{a}:{'ON ' if r[a]['on'] else 'off'}(preț={r[a]['price']:7.2f} SMA6={r[a]['sma6']:7.2f} {r[a]['pct_above']:+5.1%})" for a in GTAA_ASSETS]
        lines.append(f"{r['date']}  " + " | ".join(parts))
    return "\n".join(lines)


if __name__ == "__main__":
    prices = ucits_data.load(variant="extended", refresh=False)
    rows = table(prices, "2021-06-01", "2022-12-31")
    print(to_text(rows))
