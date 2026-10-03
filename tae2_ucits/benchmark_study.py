"""Where does core_gtaa_50 (TAE2) actually sit on the RETURN <-> RISK <->
CRISIS-PROTECTION axis -- requested 2026-10-03, after the autopsy+recovery
work established that the UCITS twin reproduces the US original's behavior
(same gate pass/fail under the same window, same rolling-window pattern).

TAE2/core_gtaa_50 is completely unchanged here: same sma_months=6,
core_weight=0.5, same assets, same signals. Only the benchmark changes --
a full family of fixed equity/bond mixes (SPY/IEF) from 100/0 to 20/80,
replacing the single 60/40 comparison with a whole risk axis. The existing
60/40 gate in tae2_ucits.research is untouched; this is a separate,
informational study, run on all three datasets without mixing their results:
US original, UCITS STRICT (real data only), UCITS EXTENDED (2008-2011
recovered via the documented splice).

No TAE2 parameter is tuned against any of this. If a later experimental
variant comes out of this analysis, it gets its own name and its own
from-scratch validation -- never a silent edit of core_gtaa_50.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tae2 import backtest, stats
from tae2 import data as us_data
from tae2.config import COST_BPS
from tae2.engine import DEPLOYABLE
from tae2.strategies import GTAA_ASSETS, fixed_mix, gtaa

from tae2_ucits import data as ucits_data

RATIOS = [(100, 0), (90, 10), (80, 20), (70, 30), (60, 40), (50, 50), (40, 60), (30, 70), (20, 80)]
ROLLING_SUBSET = [(80, 20), (70, 30), (60, 40), (50, 50), (40, 60)]
START_CAPITAL = 10_000.0

# Major US-equity stress episodes, 2007-2026. Each is included in a
# variant's crisis table only if fully covered by that variant's own date
# range (STRICT starts 2011-06 -> the 2008 crisis is correctly absent there).
EPISODES = [
    ("Criza financiară 2008", "2007-10-09", "2009-03-09"),
    ("Criza datoriilor din zona euro 2011", "2011-07-07", "2011-10-03"),
    ("Corecția China/petrol 2015-2016", "2015-08-01", "2016-02-11"),
    ("Vânzarea de pe final de 2018", "2018-10-01", "2018-12-24"),
    ("Prăbușirea COVID 2020", "2020-02-19", "2020-03-23"),
    ("Piața de urs 2022", "2022-01-03", "2022-10-12"),
]


def label(e: int, b: int) -> str:
    return f"{e}/{b}"


def benchmark_weights(prices: pd.DataFrame, equity_pct: int, bond_pct: int) -> pd.DataFrame:
    return fixed_mix(prices, {"SPY": equity_pct / 100, "IEF": bond_pct / 100})


def annual_returns(r: pd.Series) -> pd.Series:
    return r.groupby(r.index.year).apply(lambda x: float((1 + x).prod() - 1))


def recovery_days(r: pd.Series) -> float | None:
    """Calendar days from the GLOBAL max-drawdown trough until equity first
    re-exceeds the peak that preceded it. None if never recovered by the
    end of the series (an open wound, not a bug)."""
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    trough = dd.idxmin()
    prior_peak = peak.loc[trough]
    after = eq.loc[trough:]
    recovered = after[after >= prior_peak]
    return float((recovered.index[0] - trough).days) if len(recovered) else None


@dataclass
class SeriesStats:
    name: str
    returns: pd.Series

    @property
    def cagr(self) -> float:
        return stats.cagr(self.returns)

    @property
    def vol(self) -> float:
        return float(self.returns.std() * np.sqrt(252))

    @property
    def sharpe(self) -> float:
        return stats.sharpe(self.returns)

    @property
    def max_dd(self) -> float:
        return stats.max_drawdown(self.returns)

    @property
    def best_year(self) -> float:
        return float(annual_returns(self.returns).max())

    @property
    def worst_year(self) -> float:
        return float(annual_returns(self.returns).min())

    @property
    def recovery(self) -> float | None:
        return recovery_days(self.returns)

    @property
    def final_value(self) -> float:
        return START_CAPITAL * float((1 + self.returns).prod())

    @property
    def total_return(self) -> float:
        return self.final_value / START_CAPITAL - 1

    def half_sharpe(self, split: str) -> tuple[float, float]:
        cut = pd.Timestamp(split)
        return stats.sharpe(self.returns[self.returns.index < cut]), stats.sharpe(self.returns[self.returns.index >= cut])


def run_all(prices: pd.DataFrame, cost_bps: float = COST_BPS) -> dict[str, SeriesStats]:
    out: dict[str, SeriesStats] = {}
    for e, b in RATIOS:
        res = backtest.run(label(e, b), prices, benchmark_weights(prices, e, b), cost_bps=cost_bps, start=None)
        out[label(e, b)] = SeriesStats(label(e, b), res.returns)
    cand_res = backtest.run("TAE2", prices, DEPLOYABLE["core_gtaa_50"](prices), cost_bps=cost_bps, start=None)
    out["TAE2"] = SeriesStats("TAE2", cand_res.returns)
    return out


def risk_comparable(all_stats: dict[str, SeriesStats]) -> dict[str, str]:
    tae2 = all_stats["TAE2"]
    benches = {k: v for k, v in all_stats.items() if k != "TAE2"}
    by_vol = min(benches.values(), key=lambda s: abs(s.vol - tae2.vol))
    by_dd = min(benches.values(), key=lambda s: abs(s.max_dd - tae2.max_dd))
    return {"by_vol": by_vol.name, "by_dd": by_dd.name}


def cost_of_insurance(prices: pd.DataFrame, all_stats: dict[str, SeriesStats]) -> list[dict]:
    """Per benchmark: avg annual giveup in SPY-up years, avg annual edge in SPY-down years."""
    spy_annual = annual_returns(prices["SPY"].pct_change().fillna(0.0))
    up_years = spy_annual[spy_annual > 0].index
    down_years = spy_annual[spy_annual <= 0].index
    tae2_annual = annual_returns(all_stats["TAE2"].returns)
    rows = []
    for e, b in RATIOS:
        bench_annual = annual_returns(all_stats[label(e, b)].returns)
        common_up = [y for y in up_years if y in bench_annual.index and y in tae2_annual.index]
        common_down = [y for y in down_years if y in bench_annual.index and y in tae2_annual.index]
        giveup = float((bench_annual.loc[common_up] - tae2_annual.loc[common_up]).mean()) if common_up else float("nan")
        edge = float((tae2_annual.loc[common_down] - bench_annual.loc[common_down]).mean()) if common_down else float("nan")
        rows.append({"benchmark": label(e, b), "n_up": len(common_up), "giveup_up": giveup, "n_down": len(common_down), "edge_down": edge})
    return rows


def rolling_windows(start_year: int, end_year: int, length: int = 7) -> list[tuple[str, str]]:
    return [(f"{y}-01-01", f"{y + length}-01-01") for y in range(start_year, end_year - length + 1)]


def rolling_vs_many(prices: pd.DataFrame, start_year: int, end_year: int, cost_bps: float = COST_BPS) -> list[dict]:
    rows = []
    for ws, we in rolling_windows(start_year, end_year):
        p = prices.loc[ws:we]
        if len(p) < 200:
            continue
        cand = backtest.run("TAE2", p, DEPLOYABLE["core_gtaa_50"](p), cost_bps=cost_bps, start=None)
        cand_sharpe = stats.sharpe(cand.returns)
        row = {"window": f"{ws[:4]}-{we[:4]}", "tae2": cand_sharpe}
        for e, b in ROLLING_SUBSET:
            bench = backtest.run(label(e, b), p, benchmark_weights(p, e, b), cost_bps=cost_bps, start=None)
            row[label(e, b)] = cand_sharpe - stats.sharpe(bench.returns)
        rows.append(row)
    return rows


def crisis_table(prices: pd.DataFrame, all_stats: dict[str, SeriesStats], cost_bps: float = COST_BPS) -> list[dict]:
    rows = []
    sleeve = gtaa(prices, sma_months=6)
    spy_on = sleeve["SPY"] > 1e-9 if "SPY" in sleeve.columns else None
    for name, start, end in EPISODES:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        if prices.index.max() < e or prices.index.min() > e:
            rows.append({"episode": name, "available": False})
            continue
        partial = prices.index.min() > s
        s_eff = max(s, prices.index.min())
        window = prices.loc[s_eff:end]
        row: dict = {"episode": name, "available": True, "partial": partial}
        cand_ep = backtest.run("TAE2", window, DEPLOYABLE["core_gtaa_50"](window), cost_bps=cost_bps, start=None)
        row["tae2_loss"] = float((1 + cand_ep.returns).prod() - 1)
        row["tae2_dd"] = stats.max_drawdown(cand_ep.returns)
        for key in ("100/0", "80/20", "60/40", "40/60"):
            bw = benchmark_weights(window, *[int(x) for x in key.split("/")])
            bres = backtest.run(key, window, bw, cost_bps=cost_bps, start=None)
            row[f"{key}_loss"] = float((1 + bres.returns).prod() - 1)
            row[f"{key}_dd"] = stats.max_drawdown(bres.returns)
        if spy_on is not None:
            on_near = spy_on.loc[s - pd.Timedelta(days=45): e + pd.Timedelta(days=200)]
            off_mask = ~on_near
            first_off = on_near.index[off_mask].min() if off_mask.any() else None
            if first_off is not None and pd.notna(first_off):
                after_off = on_near.loc[first_off:]
                reentry = after_off.index[after_off].min() if after_off.any() else None
            else:
                reentry = None
            row["exit_date"] = str(first_off.date()) if first_off is not None and pd.notna(first_off) else "—"
            row["reentry_date"] = str(reentry.date()) if reentry is not None and pd.notna(reentry) else "—"
        rows.append(row)
    return rows


def full_markdown(label_name: str, prices: pd.DataFrame, split_date: str, start_year: int, end_year: int) -> str:
    all_stats = run_all(prices)
    rc = risk_comparable(all_stats)
    coi = cost_of_insurance(prices, all_stats)
    rolling = rolling_vs_many(prices, start_year, end_year)
    crises = crisis_table(prices, all_stats)

    lines = [f"# TAE2 vs familia de benchmark-uri — {label_name}", "",
             f"Perioadă: {prices.index[0].date()} -> {prices.index[-1].date()} "
             f"({(prices.index[-1]-prices.index[0]).days/365.25:.1f} ani), split J1/J2 la {split_date}", "",
             "## Statistici complete", "",
             "| Strategie | CAGR | Vol | Sharpe | Max DD | Cel mai bun an | Cel mai slab an | Recovery (zile) | Valoare finală ($10k inițial) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    order = [label(e, b) for e, b in RATIOS] + ["TAE2"]
    for k in order:
        s = all_stats[k]
        rec = f"{s.recovery:.0f}" if s.recovery is not None else "neîncheiat"
        lines.append(f"| {k} | {s.cagr:.1%} | {s.vol:.1%} | {s.sharpe:.2f} | {s.max_dd:.1%} | "
                      f"{s.best_year:+.1%} | {s.worst_year:+.1%} | {rec} | ${s.final_value:,.0f} |")

    lines += ["", "## Δ față de TAE2 (TAE2 − benchmark)", "",
              "| Benchmark | Δ CAGR | Δ Sharpe | Δ Max DD | Δ Vol |", "|---|---:|---:|---:|---:|"]
    t = all_stats["TAE2"]
    for e, b in RATIOS:
        s = all_stats[label(e, b)]
        lines.append(f"| {label(e,b)} | {t.cagr-s.cagr:+.1%} | {t.sharpe-s.sharpe:+.2f} | {t.max_dd-s.max_dd:+.1%} | {t.vol-s.vol:+.1%} |")

    lines += ["", f"## Benchmark cu risc comparabil",
              f"- Cea mai apropiată volatilitate de TAE2: **{rc['by_vol']}** (TAE2 vol={t.vol:.1%}, {rc['by_vol']} vol={all_stats[rc['by_vol']].vol:.1%})",
              f"- Cel mai apropiat Max Drawdown de TAE2: **{rc['by_dd']}** (TAE2 DD={t.max_dd:.1%}, {rc['by_dd']} DD={all_stats[rc['by_dd']].max_dd:.1%})",
              f"- La risc comparabil (vol): CAGR TAE2 {t.cagr:.1%} vs {rc['by_vol']} {all_stats[rc['by_vol']].cagr:.1%}",
              f"- La risc comparabil (DD): CAGR TAE2 {t.cagr:.1%} vs {rc['by_dd']} {all_stats[rc['by_dd']].cagr:.1%}", ""]

    lines += ["## J1/J2 pe toată familia", "", "| Benchmark | Sharpe J1 | Sharpe J2 | TAE2 J1 | TAE2 J2 |", "|---|---:|---:|---:|---:|"]
    t1, t2 = t.half_sharpe(split_date)
    for e, b in RATIOS:
        s = all_stats[label(e, b)]
        s1, s2 = s.half_sharpe(split_date)
        lines.append(f"| {label(e,b)} | {s1:.2f} | {s2:.2f} | {t1:.2f} | {t2:.2f} |")

    lines += ["", "## Costul asigurării (ani SPY-pozitivi vs SPY-negativi)", "",
              "| Benchmark | Ani favorabili (n) | Randament cedat/an | Ani nefavorabili (n) | Avantaj/an |",
              "|---|---:|---:|---:|---:|"]
    for r in coi:
        lines.append(f"| {r['benchmark']} | {r['n_up']} | {r['giveup_up']:+.1%} | {r['n_down']} | {r['edge_down']:+.1%} |")

    lines += ["", "## Ferestre mobile de 7 ani — Sharpe(TAE2) − Sharpe(benchmark)", "",
              "| Fereastră | TAE2 Sharpe | " + " | ".join(label(e, b) for e, b in ROLLING_SUBSET) + " |",
              "|---|---:|" + "---:|" * len(ROLLING_SUBSET)]
    for row in rolling:
        cells = " | ".join(f"{row[label(e,b)]:+.2f}" for e, b in ROLLING_SUBSET)
        lines.append(f"| {row['window']} | {row['tae2']:.2f} | {cells} |")

    lines += ["", "## Episoade de criză", ""]
    for c in crises:
        if not c["available"]:
            lines.append(f"- **{c['episode']}**: în afara ferestrei de date pentru {label_name}, sărit.")
            continue
        note = " (parțial — lipsește începutul episodului, în afara ferestrei de date)" if c.get("partial") else ""
        lines += [f"- **{c['episode']}**{note}:",
                  f"  - TAE2: {c['tae2_loss']:+.1%} randament, {c['tae2_dd']:.1%} drawdown"
                  + (f", ieșire semnal SPY ~{c['exit_date']}, reintrare ~{c['reentry_date']}" if c.get("exit_date") else ""),
                  f"  - 100/0: {c['100/0_loss']:+.1%} ({c['100/0_dd']:.1%} DD) · 80/20: {c['80/20_loss']:+.1%} ({c['80/20_dd']:.1%} DD) · "
                  f"60/40: {c['60/40_loss']:+.1%} ({c['60/40_dd']:.1%} DD) · 40/60: {c['40/60_loss']:+.1%} ({c['40/60_dd']:.1%} DD)"]
    return "\n".join(lines) + "\n"


def write_report(variant_label: str, prices: pd.DataFrame, split_date: str, start_year: int, end_year: int) -> str:
    from datetime import date
    from pathlib import Path

    text = full_markdown(variant_label, prices, split_date, start_year, end_year)
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"tae2_benchmark_family_{variant_label}_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    us_prices, _ = us_data.load(refresh=False)
    us_prices = us_prices[["SPY", "IEF", "VNQ", "SHY", "EFA", "DBC"]]
    strict_prices = ucits_data.load(variant="strict", refresh=False)
    extended_prices = ucits_data.load(variant="extended", refresh=False)

    jobs = [
        ("US_original", us_prices.loc["2008-01-01":], "2017-01-01", 2008, 2026),
        ("UCITS_strict", strict_prices.loc["2011-06-01":], "2019-02-01", 2012, 2026),
        ("UCITS_extended", extended_prices.loc["2008-01-01":], "2017-01-01", 2008, 2026),
    ]
    for name, prices, split, sy, ey in jobs:
        path = write_report(name, prices, split, sy, ey)
        print(f"{name}: report written to {path}")
