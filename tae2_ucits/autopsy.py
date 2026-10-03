"""Autopsy of core_gtaa_50's first-half underperformance on UCITS data
(2026-10-03 finding: isolate.py ruled out the EFA-blend and DBC-splice
approximations specifically -- three variants all showed the same ~0.99-1.02
first-half Sharpe vs the 60/40 benchmark's 1.16). This goes wider and deeper,
in the order requested: date/window -> proxy accuracy per asset -> per-asset
return contribution -> GTAA signal timing -> (strategy parameters, only if
nothing above explains it -- not touched here).

Every comparison below uses the SAME trading calendar: the intersection of
the US universe's trading days and the UCITS universe's trading days. That
way a difference between a "US" run and a "UCITS" run can only come from
what the prices/signals actually say, never from one dataset having decision
dates the other doesn't.
"""

from __future__ import annotations

import pandas as pd

from tae2 import backtest, stats
from tae2 import data as us_data
from tae2.config import COST_BPS
from tae2.strategies import GTAA_ASSETS, core_plus_sleeve, fixed_mix, gtaa

from tae2_ucits import data as ucits_data
from tae2_ucits.research import EVAL_START, SPLIT_DATE

ASSETS = ("SPY", "IEF", "VNQ", "SHY", "EFA", "DBC")


def aligned_prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(US prices, UCITS-proxy prices), same columns, same calendar, EVAL_START onward."""
    us_prices, _ = us_data.load(refresh=False)
    uc_prices = ucits_data.load(refresh=False)
    common = us_prices.index.intersection(uc_prices.index)
    common = common[common >= pd.Timestamp(EVAL_START)]
    return us_prices.loc[common, list(ASSETS)], uc_prices.loc[common, list(ASSETS)]


# --- Step 1: date/window is fixed by aligned_prices() + the existing
# EVAL_START/SPLIT_DATE from research.py (already chosen to exclude the
# known IBTS.L/IUSP.L data-quality period) -- reused, not re-derived here.


# --- Step 2: proxy accuracy, per asset, over the common window.
def proxy_report(us: pd.DataFrame, uc: pd.DataFrame, split: str = SPLIT_DATE) -> list[dict]:
    cut = pd.Timestamp(split)
    rows = []
    for a in ASSETS:
        ru, rc = us[a].pct_change().dropna(), uc[a].pct_change().dropna()
        idx = ru.index.intersection(rc.index)
        ru, rc = ru.loc[idx], rc.loc[idx]
        ru1, rc1 = ru[ru.index < cut], rc[rc.index < cut]
        rows.append(
            {
                "asset": a,
                "corr_full": float(ru.corr(rc)),
                "corr_h1": float(ru1.corr(rc1)),
                "cagr_us": stats.cagr(ru1),
                "cagr_ucits": stats.cagr(rc1),
                "vol_us": float(ru1.std() * (252**0.5)),
                "vol_ucits": float(rc1.std() * (252**0.5)),
            }
        )
    return rows


# --- Step 3: per-asset contribution to the first-half portfolio-return gap.
def contribution_report(
    us: pd.DataFrame, uc: pd.DataFrame, w_us: pd.DataFrame, w_uc: pd.DataFrame, split: str = SPLIT_DATE
) -> list[dict]:
    res_us = backtest.run("core_gtaa_50 (US aligned)", us, w_us, cost_bps=COST_BPS, start=None)
    res_uc = backtest.run("core_gtaa_50 (UCITS aligned)", uc, w_uc, cost_bps=COST_BPS, start=None)
    cut = pd.Timestamp(split)
    mask = res_us.returns.index < cut
    ret_us = us.pct_change().fillna(0.0).loc[mask, list(ASSETS)]
    ret_uc = uc.pct_change().fillna(0.0).loc[mask, list(ASSETS)]
    contrib_us = (res_us.weights.loc[mask, list(ASSETS)] * ret_us).sum()
    contrib_uc = (res_uc.weights.loc[mask, list(ASSETS)] * ret_uc).sum()
    rows = [
        {
            "asset": a,
            "contrib_us": float(contrib_us[a]),
            "contrib_ucits": float(contrib_uc[a]),
            "gap": float(contrib_us[a] - contrib_uc[a]),
        }
        for a in ASSETS
    ]
    return sorted(rows, key=lambda r: abs(r["gap"]), reverse=True)


# --- Step 4: GTAA signal timing -- does the trend on/off call flip on
# different dates for the UCITS proxy vs the US original, in the sleeve?
def signal_report(us: pd.DataFrame, uc: pd.DataFrame, split: str = SPLIT_DATE) -> dict:
    sleeve_us = gtaa(us, sma_months=6)
    sleeve_uc = gtaa(uc, sma_months=6)
    dates = sleeve_us.index.intersection(sleeve_uc.index)
    dates = dates[dates < pd.Timestamp(split)]
    inv_us = sleeve_us.loc[dates, list(GTAA_ASSETS)] > 1e-9
    inv_uc = sleeve_uc.loc[dates, list(GTAA_ASSETS)] > 1e-9
    disagree = inv_us != inv_uc
    per_asset = {a: int(disagree[a].sum()) for a in GTAA_ASSETS}
    total_months = len(dates)
    flip_dates = {
        a: [d.date().isoformat() for d in dates[disagree[a]]] for a in GTAA_ASSETS if disagree[a].any()
    }
    return {"months": total_months, "disagreements": per_asset, "dates": flip_dates}


# --- Mixed backtests: isolate "proxy returns" effect from "signal timing" effect.
def mixed_decomposition(
    us: pd.DataFrame, uc: pd.DataFrame, w_us: pd.DataFrame, w_uc: pd.DataFrame, split: str = SPLIT_DATE
) -> list[dict]:
    cut = pd.Timestamp(split)
    runs = {
        "US (preț+semnal US)": backtest.run("us", us, w_us, cost_bps=COST_BPS, start=None),
        "UCITS (preț+semnal UCITS)": backtest.run("uc", uc, w_uc, cost_bps=COST_BPS, start=None),
        "Semnal US x preț UCITS (efect proxy)": backtest.run("mix1", uc, w_us, cost_bps=COST_BPS, start=None),
        "Semnal UCITS x preț US (efect sincronizare)": backtest.run("mix2", us, w_uc, cost_bps=COST_BPS, start=None),
        "60/40 pe preț US": backtest.run("bench_us", us, fixed_mix(us, {"SPY": 0.6, "IEF": 0.4}), cost_bps=COST_BPS, start=None),
        "60/40 pe preț UCITS": backtest.run("bench_uc", uc, fixed_mix(uc, {"SPY": 0.6, "IEF": 0.4}), cost_bps=COST_BPS, start=None),
    }
    rows = []
    for name, res in runs.items():
        r = res.returns
        rows.append(
            {
                "variant": name,
                "sharpe_h1": stats.sharpe(r[r.index < cut]),
                "sharpe_h2": stats.sharpe(r[r.index >= cut]),
            }
        )
    return rows


def run() -> dict:
    us, uc = aligned_prices()
    sleeve_us = gtaa(us, sma_months=6)
    sleeve_uc = gtaa(uc, sma_months=6)
    w_us = core_plus_sleeve(us, sleeve_us, core_weight=0.5)
    w_uc = core_plus_sleeve(uc, sleeve_uc, core_weight=0.5)
    return {
        "window": (str(us.index[0].date()), str(us.index[-1].date()), SPLIT_DATE),
        "proxy": proxy_report(us, uc),
        "contribution": contribution_report(us, uc, w_us, w_uc),
        "signals": signal_report(us, uc),
        "decomposition": mixed_decomposition(us, uc, w_us, w_uc),
    }


def to_markdown(result: dict) -> str:
    start, end, split = result["window"]
    lines = [f"# Autopsie core_gtaa_50: US vs UCITS, {start} -> {end} (prima jumătate < {split})", ""]

    lines += ["## 2. Acuratețea proxy-urilor (randament zilnic, corelație, J1 = prima jumătate)", "",
              "| Activ | Corr (J1) | Corr (tot) | CAGR US (J1) | CAGR UCITS (J1) | Vol US (J1) | Vol UCITS (J1) |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for r in result["proxy"]:
        lines.append(
            f"| {r['asset']} | {r['corr_h1']:.3f} | {r['corr_full']:.3f} | {r['cagr_us']:.1%} | "
            f"{r['cagr_ucits']:.1%} | {r['vol_us']:.1%} | {r['vol_ucits']:.1%} |"
        )

    lines += ["", "## 3. Contribuția fiecărui activ la randamentul portofoliului (doar J1, aproximare aditivă)", "",
              "| Activ | Contribuție US | Contribuție UCITS | Diferență (US - UCITS) |",
              "|---|---:|---:|---:|"]
    for r in result["contribution"]:
        lines.append(f"| {r['asset']} | {r['contrib_us']:.1%} | {r['contrib_ucits']:.1%} | {r['gap']:+.1%} |")

    s = result["signals"]
    lines += ["", f"## 4. Sincronizarea semnalului de trend (din {s['months']} luni, J1)", "",
              "| Activ | Luni cu decizie diferită (investit/nu) |", "|---|---:|"]
    for a, n in s["disagreements"].items():
        lines.append(f"| {a} | {n} |")
    for a, ds in s["dates"].items():
        lines.append(f"\nDate cu decizie diferită pe {a}: {', '.join(ds)}")

    lines += ["", "## Descompunere: efect preț (proxy) vs efect sincronizare semnal", "",
              "| Variantă | Sharpe J1 | Sharpe J2 |", "|---|---:|---:|"]
    for r in result["decomposition"]:
        lines.append(f"| {r['variant']} | {r['sharpe_h1']:.2f} | {r['sharpe_h2']:.2f} |")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(to_markdown(run()))
